import {
    epipolarPolylines, pixelRay, pointOnRay, projectPoint, rigBaselineMm, triangulate,
    type CameraModel, type Ray, type Triangulation, type Vec2, type Vec3,
} from './camera-geometry';

/** `click` is an independent observation; `accepted` is a projection the user confirmed. */
export type ObservationOrigin = 'click' | 'accepted';

export interface Observation {
    readonly point: string;
    readonly camera_id: string;
    readonly source_frame: number;
    readonly x_px: number;
    readonly y_px: number;
    readonly origin: ObservationOrigin;
}

export interface LabelSession {
    readonly active_point: string | null;
    readonly active_camera: string | null;
    /** Source-frame identity of the frame being labeled. */
    readonly source_frame: number | null;
    /** Playback index used to seek back to that frame on reopen. */
    readonly local_frame_index: number | null;
}

/** The persisted label document for one recording. Projections are never stored. */
export interface LabelDocument {
    readonly schema_version: 1;
    readonly recording_id: string;
    readonly tracked_point_names: readonly string[];
    readonly observations: readonly Observation[];
    readonly session: LabelSession;
}

export const POINT_COLORS: readonly string[] = ['#ffd166', '#c39bff', '#ff8a7a', '#7fd6ff', '#9be38b', '#ffa8e0', '#f3c490', '#a2cfd1'];
export const pointColor = (index: number): string => POINT_COLORS[index % POINT_COLORS.length];

export function emptyDocument(recordingId: string): LabelDocument {
    return {schema_version: 1, recording_id: recordingId, tracked_point_names: [],
        observations: [], session: {active_point: null, active_camera: null, source_frame: null, local_frame_index: null}};
}

/** Parse ordered point names, one per line. Throws on duplicates. */
export function parsePointNames(text: string): string[] {
    const names = text.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);
    const duplicate = names.find((name, index) => names.indexOf(name) !== index);
    if (duplicate !== undefined) throw new Error(`"${duplicate}" appears more than once; point names must be unique.`);
    return names;
}

/** Parse the original SkellyClicker point file: {"tracked_point_names": [...]}. */
export function parsePointFile(text: string): string[] {
    const value: unknown = JSON.parse(text);
    if (typeof value !== 'object' || value === null || !('tracked_point_names' in value)) {
        throw new Error('Point file must be a JSON object with "tracked_point_names".');
    }
    const names = (value as {tracked_point_names: unknown}).tracked_point_names;
    if (!Array.isArray(names) || !names.every((name): name is string => typeof name === 'string' && name.trim().length > 0)) {
        throw new Error('"tracked_point_names" must be a list of non-empty strings.');
    }
    return parsePointNames(names.join('\n'));
}

/** Replace the point list. Observations of removed points are dropped; the caller confirms that first. */
export function withPointNames(document: LabelDocument, names: readonly string[]): LabelDocument {
    const keep = new Set(names);
    const active = document.session.active_point;
    return {...document, tracked_point_names: [...names],
        observations: document.observations.filter(observation => keep.has(observation.point)),
        session: {...document.session, active_point: active !== null && keep.has(active) ? active : names[0] ?? null}};
}

export function droppedObservationCount(document: LabelDocument, names: readonly string[]): number {
    const keep = new Set(names);
    return document.observations.filter(observation => !keep.has(observation.point)).length;
}

/** Set (or with `null`, clear) the observation of one point in one camera at one frame. */
export function withObservation(document: LabelDocument, point: string, cameraId: string, sourceFrame: number,
    value: {x_px: number; y_px: number; origin: ObservationOrigin} | null): LabelDocument {
    if (!document.tracked_point_names.includes(point)) throw new Error(`Unknown point "${point}"`);
    const others = document.observations.filter(observation => !(observation.point === point
        && observation.camera_id === cameraId && observation.source_frame === sourceFrame));
    return {...document, observations: value ? [...others, {point, camera_id: cameraId, source_frame: sourceFrame, ...value}] : others};
}

export function withSession(document: LabelDocument, session: Partial<LabelSession>): LabelDocument {
    return {...document, session: {...document.session, ...session}};
}

// ── Derived evidence (never persisted) ──────────────────────────────────

export type ViewEvidenceKind = 'click' | 'accepted' | 'projected' | 'none';

export interface ViewEvidence {
    readonly cameraId: string;
    readonly kind: ViewEvidenceKind;
    /** Pixel of the click, accepted projection, or live projection. */
    readonly pixel: Vec2 | null;
    /** Reprojection error of this camera's click against the triangulated point. */
    readonly errorPx: number | null;
}

export interface PointEvidence {
    readonly point: string;
    readonly index: number;
    readonly color: string;
    readonly views: readonly ViewEvidence[];
    /** Rays from cameras with independent clicks. */
    readonly rays: ReadonlyMap<string, Ray>;
    readonly triangulation: Triangulation | null;
    /** Calibrated cameras whose clicks fed the triangulation. */
    readonly triangulatedFrom: readonly string[];
    /** Why there is no triangulation, when there is none. */
    readonly gap: 'no_clicks' | 'one_view' | 'no_calibration' | 'rays_do_not_meet' | null;
}

export interface FrameEvidence {
    readonly sourceFrame: number;
    readonly points: readonly PointEvidence[];
}

/**
 * Everything the views, panel and 3D viewport show for one frame.
 * `cameraIds` lists every video; `cameras` holds the calibrated ones by id.
 */
export function frameEvidence(document: Pick<LabelDocument,'observations'|'tracked_point_names'>, sourceFrame: number, cameraIds: readonly string[],
    cameras: ReadonlyMap<string, CameraModel>): FrameEvidence {
    const atFrame = document.observations.filter(observation => observation.source_frame === sourceFrame);
    const points = document.tracked_point_names.map((point, index): PointEvidence => {
        const byCamera = new Map(atFrame.filter(observation => observation.point === point)
            .map(observation => [observation.camera_id, observation]));
        const clicks = [...byCamera.values()].filter(observation => observation.origin === 'click');
        const calibratedClicks = clicks.filter(observation => cameras.has(observation.camera_id));
        const rays = new Map(calibratedClicks.map(observation => {
            const camera = cameras.get(observation.camera_id)!;
            return [observation.camera_id, pixelRay(camera, [observation.x_px, observation.y_px])] as const;
        }));
        const triangulation = calibratedClicks.length >= 2
            ? triangulate(calibratedClicks.map(observation => ({camera: cameras.get(observation.camera_id)!, pixel: [observation.x_px, observation.y_px] as const})))
            : null;
        const triangulatedFrom = triangulation ? calibratedClicks.map(observation => observation.camera_id) : [];
        const views = cameraIds.map((cameraId): ViewEvidence => {
            const observation = byCamera.get(cameraId);
            if (observation) {
                const index = triangulatedFrom.indexOf(cameraId);
                return {cameraId, kind: observation.origin, pixel: [observation.x_px, observation.y_px],
                    errorPx: triangulation && index >= 0 ? triangulation.errorsPx[index] : null};
            }
            const camera = cameras.get(cameraId);
            const projected = triangulation && camera ? projectPoint(camera, triangulation.position) : null;
            return projected && camera && projected[0] >= 0 && projected[0] < camera.imageWidth && projected[1] >= 0 && projected[1] < camera.imageHeight ? {cameraId, kind: 'projected', pixel: projected, errorPx: null} : {cameraId, kind: 'none', pixel: null, errorPx: null};
        });
        const gap = triangulation ? null
            : clicks.length === 0 ? 'no_clicks'
            : cameras.size === 0 ? 'no_calibration'
            : calibratedClicks.length < 2 ? 'one_view'
            : 'rays_do_not_meet';
        return {point, index, color: pointColor(index), views, rays, triangulation, triangulatedFrom, gap};
    });
    return {sourceFrame, points};
}

/** Epipolar curves of every other camera's click ray in `cameraId`. */
export function epipolarCurves(point: PointEvidence, cameraId: string, cameras: ReadonlyMap<string, CameraModel>): {fromCamera: string; lines: Vec2[][]}[] {
    const camera = cameras.get(cameraId);
    if (!camera || cameras.size < 2) return [];
    const baseline = rigBaselineMm([...cameras.values()]);
    return [...point.rays.entries()].filter(([source]) => source !== cameraId)
        .map(([fromCamera, ray]) => ({fromCamera, lines: epipolarPolylines(camera, ray, baseline * 0.02, baseline * 20, 96)}));
}

/** Rays (as finite segments) and triangulated points for the 3D viewport, in calibration mm. */
export function sceneAnnotations(evidence: FrameEvidence, activePoint: string | null, cameras: ReadonlyMap<string, CameraModel>) {
    const baseline = cameras.size >= 2 ? rigBaselineMm([...cameras.values()]) : 0;
    const segments = evidence.points.filter(point => point.point === activePoint).flatMap(point =>
        [...point.rays.entries()].map(([cameraId, ray]) => {
            const end: Vec3 = point.triangulation
                ? pointOnRay(ray, Math.hypot(...point.triangulation.position.map((value, axis) => value - ray.origin[axis])) * 1.25)
                : pointOnRay(ray, baseline * 2.5);
            return {id: `${point.point}:${cameraId}`, start: [...ray.origin] as [number, number, number],
                end: [...end] as [number, number, number], color: point.color, dashed: point.triangulation === null};
        }));
    const points = evidence.points.flatMap(point => point.triangulation ? [{
        id: point.point, position: [...point.triangulation.position] as [number, number, number],
        color: point.color, radiusMm: Math.max(2, baseline * (point.point === activePoint ? 0.008 : 0.005)),
    }] : []);
    return {points, segments};
}
