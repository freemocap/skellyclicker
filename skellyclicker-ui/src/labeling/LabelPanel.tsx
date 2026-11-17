import {useState, type CSSProperties} from 'react';
import {AnchoredInfo} from '@freemocap/ui';
import {droppedObservationCount, parsePointFile, parsePointNames, type PointEvidence, type ViewEvidenceKind} from './labels';
import type {Labeling} from './useLabeling';

const KIND_LABEL: Record<ViewEvidenceKind, string> = {click: 'Clicked', accepted: 'Accepted projection', projected: 'Projected', none: 'No observation'};
const GAP_TEXT: Record<NonNullable<PointEvidence['gap']>, string> = {
    no_clicks: 'Not labeled on this frame',
    one_view: 'Needs one more calibrated view',
    no_calibration: 'No calibration · 2D only',
    rays_do_not_meet: 'Rays do not meet in front of the cameras',
};

const colorStyle = (color: string): CSSProperties => ({'--point-color': color} as CSSProperties);

function Glyph({kind, color, title}: {kind: ViewEvidenceKind; color: string; title: string}) {
    return <span className="label-glyph" data-kind={kind} style={colorStyle(color)} title={title}/>;
}

function PointDefinition({labeling, onDone}: {labeling: Labeling; onDone: (() => void) | null}) {
    const document = labeling.document!;
    const [draft, setDraft] = useState(document.tracked_point_names.join('\n'));
    const [problem, setProblem] = useState<string | null>(null);
    const [confirmDrop, setConfirmDrop] = useState(false);
    let names: string[] = [];
    let parseError: string | null = null;
    try { names = parsePointNames(draft); } catch (reason) { parseError = String(reason); }
    const dropped = parseError ? 0 : droppedObservationCount(document, names);
    const save = (): void => {
        if (dropped > 0 && !confirmDrop) { setConfirmDrop(true); return; }
        labeling.setPointNames(names);
        setConfirmDrop(false);
        onDone?.();
    };
    const loadFile = async (file: File): Promise<void> => {
        try {
            setDraft(parsePointFile(await file.text()).join('\n'));
            setProblem(null);
        } catch (reason) {
            setProblem(`${file.name}: ${String(reason)}`);
        }
    };
    return <section className="label-define" aria-label="Define points">
        <div className="label-points-head">
            <label htmlFor="label-point-names">Point names</label>
            <AnchoredInfo title="Point names" text="Enter one point per line in the order you want to label them."/>
        </div>
        <textarea id="label-point-names" rows={6} value={draft} spellCheck={false} onChange={event => { setDraft(event.target.value); setConfirmDrop(false); }}/>
        <label className="label-file">Load point list (.json)
            <input type="file" accept=".json,application/json" onChange={event => {
                const file = event.target.files?.[0];
                if (file) void loadFile(file);
                event.target.value = '';
            }}/>
        </label>
        {problem && <p role="alert" className="label-error">{problem}</p>}
        {parseError && <p role="alert" className="label-error">{parseError}</p>}
        {confirmDrop && <p role="alert" className="label-warning">This removes {dropped} saved observation{dropped === 1 ? '' : 's'} of points no longer in the list. Save again to confirm.</p>}
        <div className="label-actions">
            {onDone && <button type="button" onClick={() => { setConfirmDrop(false); onDone(); }}>Cancel</button>}
            <button type="button" className="label-primary" disabled={parseError !== null || names.length === 0} onClick={save}>
                {confirmDrop ? 'Remove and save' : document.tracked_point_names.length ? 'Save points' : 'Start labeling'}
            </button>
        </div>
    </section>;
}

function Inspector({labeling, point}: {labeling: Labeling; point: PointEvidence}) {
    const frame = labeling.presented!;
    return <section className="label-inspector" aria-label={`${point.point} at this frame`}>
        <h3><span className="label-badge" style={colorStyle(point.color)}>{point.index + 1}</span>{point.point}</h3>
        <p className="label-muted">Source frame {frame.sourceFrameNumber} · {frame.timestampSeconds.toFixed(2)} s</p>
        <ul className="label-views">
            {point.views.map(view => <li key={view.cameraId}>
                <span className="label-view-head">
                    <Glyph kind={view.kind} color={point.color} title={KIND_LABEL[view.kind]}/>
                    <code>{view.cameraId}</code>
                    <span className="label-kind">{KIND_LABEL[view.kind]}</span>
                </span>
                {view.pixel && <span className="label-muted">
                    x {view.pixel[0].toFixed(1)}, y {view.pixel[1].toFixed(1)} px
                    {view.errorPx !== null && ` · ${view.errorPx.toFixed(1)} px from triangulated`}
                </span>}
                <span className="label-actions">
                    {view.kind === 'projected' && <button type="button" className="label-primary" onClick={() => labeling.acceptProjection(view.cameraId)}>Accept projection</button>}
                    {(view.kind === 'click' || view.kind === 'accepted') && <button type="button" onClick={() => labeling.clearObservation(view.cameraId)}>Clear</button>}
                </span>
            </li>)}
        </ul>
        <div className="label-triangulation">
            <h4>3D</h4>
            {point.triangulation ? <>
                <p>Triangulated from {point.triangulatedFrom.join(' + ')}</p>
                <p className="label-muted">Position {point.triangulation.position.map(value => value.toFixed(1)).join(', ')} mm</p>
                <p className={point.triangulation.meanErrorPx > 6 ? 'label-warning' : 'label-muted'}>
                    Mean reprojection error {point.triangulation.meanErrorPx.toFixed(1)} px
                </p>
            </> : <p className="label-warning">{GAP_TEXT[point.gap!]}</p>}
        </div>
    </section>;
}

/** Sidebar for defining points and reviewing the active point's evidence at the presented frame. */
export function LabelPanel({labeling}: {labeling: Labeling}) {
    const [editing, setEditing] = useState(false);
    if (labeling.status === 'no_recording') return null;
    if (labeling.status === 'error') return <div role="alert" className="label-error">
        <p>{labeling.error}</p>
        <button type="button" onClick={labeling.retry}>Retry</button>
    </div>;
    if (labeling.status === 'loading') return <p role="status">Loading labels…</p>;
    const document = labeling.document!;
    const evidence = labeling.evidence;
    const active = evidence?.points.find(point => point.point === document.session.active_point) ?? null;
    const unusable = labeling.cameraStatuses.flatMap(status => status.state === 'calibrated' ? [] : [status]);
    return <div className="label-panel">
        {labeling.saveError && <p role="alert" className="label-error">{labeling.saveError}</p>}
        {labeling.notice && <p role="status" className="label-warning">{labeling.notice}</p>}
        {!labeling.calibrationLoaded && <p className="label-muted">2D only · No calibration</p>}
        {unusable.length > 0 && <ul className="label-camera-issues" aria-label="Cameras without usable calibration">
            {unusable.map(status => <li key={status.cameraId}><code>{status.cameraId}</code> {status.detail}</li>)}
        </ul>}

        {(editing || document.tracked_point_names.length === 0)
            ? <PointDefinition labeling={labeling} onDone={document.tracked_point_names.length ? () => setEditing(false) : null}/>
            : <section aria-label="Points">
                <div className="label-points-head">
                    <h3>Points</h3>
                    <AnchoredInfo title="Label controls" text="Click to place the active point, right-click to clear it, and scroll to zoom. After the first click, the dashed line guides placement in another calibrated view."/>
                    <button type="button" onClick={() => setEditing(true)}>Edit points</button>
                </div>
                {!evidence && <p className="label-muted">Waiting for a frame…</p>}
                <ul className="label-points">
                    {(evidence?.points ?? []).map(point => {
                        const selected = point.point === document.session.active_point;
                        return <li key={point.point}>
                            <button type="button" aria-pressed={selected} className="label-point" onClick={() => labeling.setActivePoint(point.point)}>
                                <span className="label-badge" style={colorStyle(point.color)}>{point.index + 1}</span>
                                <span className="label-point-text">
                                    <strong>{point.point}</strong>
                                    <span className={point.gap && point.gap !== 'no_calibration' ? 'label-warning' : 'label-muted'}>
                                        {point.triangulation ? `3D · ${point.triangulation.meanErrorPx.toFixed(1)} px` : GAP_TEXT[point.gap!]}
                                    </span>
                                </span>
                                <span className="label-glyphs">
                                    {point.views.map(view => <Glyph key={view.cameraId} kind={view.kind} color={point.color} title={`${view.cameraId}: ${KIND_LABEL[view.kind]}`}/>)}
                                </span>
                            </button>
                        </li>;
                    })}
                </ul>
            </section>}

        {active && labeling.presented && !editing && <Inspector labeling={labeling} point={active}/>}
    </div>;
}
