import {useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject} from 'react';
import type {ImageOverlayContext, LoadedCalibration, PlaybackWorkspaceHandle, PresentedFrame, PresentedImage, SceneAnnotations} from '@freemocap/ui';
import {cameraModelFromCalibration, type CameraModel, type Vec2} from './camera-geometry';
import {
    emptyDocument, frameEvidence, sceneAnnotations, withObservation, withPointNames, withSession,
    type FrameEvidence, type LabelDocument,
} from './labels';
import {loadLabels, saveLabels, type RecordingKey} from './labels-api';
import {LabelImageOverlay} from './LabelImageOverlay';

const SESSION_SAVE_DELAY_MS = 800;
const NO_VIEWS: Readonly<Record<string, {width: number; height: number}>> = {};

export type CameraStatus =
    | {readonly cameraId: string; readonly state: 'calibrated'}
    | {readonly cameraId: string; readonly state: 'no_calibration' | 'size_mismatch' | 'invalid_calibration'; readonly detail: string};

export interface Labeling {
    readonly status: 'no_recording' | 'loading' | 'ready' | 'error';
    readonly error: string | null;
    readonly saveError: string | null;
    waitForSave(): Promise<void>;
    readonly notice: string | null;
    readonly document: LabelDocument | null;
    readonly evidence: FrameEvidence | null;
    readonly cameraStatuses: readonly CameraStatus[];
    readonly cameras: ReadonlyMap<string, CameraModel>;
    readonly calibrationLoaded: boolean;
    readonly presented: PresentedFrame | null;
    readonly sceneAnnotations: SceneAnnotations | undefined;
    renderImageOverlay(context: ImageOverlayContext): ReactNode;
    onCalibration(calibration: LoadedCalibration | null): void;
    setPointNames(names: readonly string[]): void;
    setActivePoint(point: string): void;
    acceptProjection(cameraId: string): void;
    clearObservation(cameraId: string): void;
    retry(): void;
}

const keyOf = (recording: RecordingKey): string => JSON.stringify([recording.recordingId, recording.parentDirectory]);

export function useLabeling({baseUrl, recording, playbackId, sourceSizes, cameraEntries, presented, controls}: {
    sourceSizes?: Record<string,[number,number]>; playbackId?: string; cameraEntries?: LoadedCalibration['cameras']; baseUrl: string; recording: RecordingKey | null; presented: PresentedFrame | null;
    controls: RefObject<PlaybackWorkspaceHandle | null>;
}): Labeling {
    const recordingKey = recording ? keyOf(recording) : null;
    const [loaded, setLoaded] = useState<{key: string; document: LabelDocument} | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [revision, setRevision] = useState(0);
    const [calibration, setCalibration] = useState<LoadedCalibration | null>(null);
    const [registered, setRegistered] = useState<{key: string | null; views: Readonly<Record<string, {width: number; height: number}>>}>({key: null, views: {}});
    const documentRef = useRef<LabelDocument | null>(null);
    const saveChain = useRef(Promise.resolve());
    const latestSave = useRef(saveChain.current);
    const restoredKey = useRef<string | null>(null);

    // Load the recording's labels.
    useEffect(() => {
        setLoaded(null); setError(null); setSaveError(null); setNotice(null);
        documentRef.current = null;
        restoredKey.current = null;
        if (!recordingKey) return;
        const [recordingId, parentDirectory] = JSON.parse(recordingKey) as [string, string | null];
        const abort = new AbortController();
        saveChain.current.then(() => loadLabels(baseUrl, {recordingId, parentDirectory}, abort.signal)).then(document => {
            if (abort.signal.aborted) return;
            const value = document ?? emptyDocument(recordingId);
            documentRef.current = value;
            setLoaded({key: recordingKey, document: value});
        }).catch((reason: unknown) => {
            if (!abort.signal.aborted) setError(String(reason));
        });
        return () => abort.abort();
    }, [baseUrl, recordingKey, revision]);

    const document = loaded && loaded.key === recordingKey ? loaded.document : null;

    const commit = useCallback((change: (current: LabelDocument) => LabelDocument): void => {
        const current = documentRef.current;
        if (!current || !recording || !recordingKey) throw new Error('Labels are not loaded for this recording');
        const next = change(current);
        documentRef.current = next;
        setLoaded({key: recordingKey, document: next});
        latestSave.current = saveChain.current.then(() => saveLabels(baseUrl, recording, next));
        saveChain.current = latestSave.current
            .then(() => setSaveError(null))
            .catch((reason: unknown) => setSaveError(String(reason)));
    }, [baseUrl, recording, recordingKey]);

    // Frame this recording is showing; frames from a previous recording do not count.
    const frame = presented && recording && presented.recording.id === playbackId ? presented : null;

    // Reopen at the saved frame once playback can seek.
    useEffect(() => {
        if (!document || !frame || !recordingKey || restoredKey.current === recordingKey) return;
        restoredKey.current = recordingKey;
        const {local_frame_index: localIndex, source_frame: sourceFrame} = document.session;
        if (localIndex === null || localIndex === frame.localFrameIndex) return;
        const handle = controls.current;
        if (!handle) throw new Error('Playback controls are not mounted');
        handle.seekFrame(localIndex).then(result => {
            if (!result) setNotice(`Could not return to saved frame ${localIndex}.`);
            else if (sourceFrame !== null && result.sourceFrameNumber !== sourceFrame) {
                setNotice(`Saved frame ${localIndex} now shows source frame ${result.sourceFrameNumber}, not ${sourceFrame}. Check the recording's frame layout.`);
            }
        }).catch((reason: unknown) => setNotice(`Could not return to saved frame: ${String(reason)}`));
    }, [document, frame, recordingKey, controls]);

    // Remember the current frame (debounced) after the restore has happened.
    const frameIndex = frame?.localFrameIndex ?? null;
    const sourceFrame = frame?.sourceFrameNumber ?? null;
    useEffect(() => {
        if (!document || frameIndex === null || sourceFrame === null || restoredKey.current !== recordingKey) return;
        if (document.session.local_frame_index === frameIndex && document.session.source_frame === sourceFrame) return;
        const timer = setTimeout(() => commit(current => withSession(current, {local_frame_index: frameIndex, source_frame: sourceFrame})), SESSION_SAVE_DELAY_MS);
        return () => clearTimeout(timer);
    }, [document, frameIndex, sourceFrame, recordingKey, commit]);

    // Tiles report their decoded size; the callback changes per recording so remounted tiles re-register.
    const onRegisterView = useCallback((videoId: string, width: number, height: number): void => {
        setRegistered(previous => {
            const views = previous.key === recordingKey ? previous.views : NO_VIEWS;
            if (previous.key === recordingKey && views[videoId]?.width === width && views[videoId]?.height === height) return previous;
            return {key: recordingKey, views: {...views, [videoId]: {width, height}}};
        });
    }, [recordingKey]);
    const views = registered.key === recordingKey ? registered.views : NO_VIEWS;

    const {cameras, cameraStatuses} = useMemo(() => {
        const models = new Map<string, CameraModel>();
        const statuses: CameraStatus[] = [];
        const byId = new Map((cameraEntries ?? calibration?.cameras ?? []).map(camera => [camera.id, camera]));
        for (const cameraId of Object.keys(views).sort()) {
            const entry = byId.get(cameraId);
            const size = views[cameraId];
            if (!entry) {
                statuses.push({cameraId, state: 'no_calibration', detail: calibration ? `${calibration.path} has no camera "${cameraId}"` : 'This recording has no calibration'});
                continue;
            }
            if (entry.image_size[0] !== size.width || entry.image_size[1] !== size.height) {
                statuses.push({cameraId, state: 'size_mismatch', detail: `Video is ${size.width}×${size.height}; calibration expects ${entry.image_size[0]}×${entry.image_size[1]}`});
                continue;
            }
            try {
                models.set(cameraId, cameraModelFromCalibration(entry));
                statuses.push({cameraId, state: 'calibrated'});
            } catch (reason) {
                statuses.push({cameraId, state: 'invalid_calibration', detail: String(reason)});
            }
        }
        return {cameras: models, cameraStatuses: statuses};
    }, [cameraEntries, calibration, views]);

    const evidence = useMemo(() => document && frame
        ? frameEvidence(document, frame.sourceFrameNumber, Object.keys(views).sort(), cameras)
        : null, [document, frame, views, cameras]);

    const activePoint = document?.session.active_point ?? null;
    const annotations = useMemo(() => evidence ? sceneAnnotations(evidence, activePoint, cameras) : undefined,
        [evidence, activePoint, cameras]);

    const place = useCallback((videoId: string, pixel: Vec2, image: PresentedImage): void => {
        setNotice(null);
        commit(current => {
            const point = current.session.active_point;
            if (point === null) throw new Error('No active point to place');
            return withSession(withObservation(current, point, videoId, image.sourceFrameNumber, {x_px: pixel[0], y_px: pixel[1], origin: 'click'}),
                {active_camera: videoId, source_frame: image.sourceFrameNumber, local_frame_index: image.localFrameIndex});
        });
    }, [commit]);

    const clearAt = useCallback((videoId: string, image: PresentedImage): void => {
        setNotice(null);
        commit(current => {
            const point = current.session.active_point;
            if (point === null) throw new Error('No active point to clear');
            return withObservation(current, point, videoId, image.sourceFrameNumber, null);
        });
    }, [commit]);

    const frameUnavailable = useCallback((): void => setNotice('The frame is still loading. Click again once it shows.'), []);

    const renderImageOverlay = useCallback((context: ImageOverlayContext): ReactNode => <LabelImageOverlay
        context={context} sourceSize={sourceSizes?.[context.filename]} evidence={evidence} activePoint={activePoint} cameras={cameras}
        onRegisterView={onRegisterView} onPlace={place} onClear={clearAt} onFrameUnavailable={frameUnavailable}/>,
    [sourceSizes, evidence, activePoint, cameras, onRegisterView, place, clearAt, frameUnavailable]);

    const currentFrame = (): PresentedFrame => {
        if (!frame) throw new Error('No presented frame');
        return frame;
    };

    return {
        status: !recording ? 'no_recording' : error ? 'error' : document ? 'ready' : 'loading',
        error, saveError, notice, document, evidence, cameraStatuses, cameras,
        waitForSave: () => latestSave.current,
        calibrationLoaded: !!cameraEntries?.length || calibration !== null,
        presented: frame,
        sceneAnnotations: annotations,
        renderImageOverlay,
        onCalibration: setCalibration,
        setPointNames: names => commit(current => withPointNames(current, names)),
        setActivePoint: point => commit(current => withSession(current, {active_point: point})),
        acceptProjection: cameraId => {
            const shown = currentFrame();
            const view = evidence?.points.find(point => point.point === activePoint)?.views.find(candidate => candidate.cameraId === cameraId);
            if (!view || view.kind !== 'projected' || !view.pixel) throw new Error(`No projection of ${String(activePoint)} in ${cameraId} to accept`);
            const pixel = view.pixel;
            commit(current => withObservation(current, current.session.active_point!, cameraId, shown.sourceFrameNumber, {x_px: pixel[0], y_px: pixel[1], origin: 'accepted'}));
        },
        clearObservation: cameraId => {
            const shown = currentFrame();
            commit(current => withObservation(current, current.session.active_point!, cameraId, shown.sourceFrameNumber, null));
        },
        retry: () => setRevision(value => value + 1),
    };
}
