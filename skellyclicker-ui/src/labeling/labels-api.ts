import type {LabelDocument, Observation} from './labels';

/**
 * Backend contract (owned by the backend agent; see docs/skellyclicker-multicamera-handoff.md):
 *   GET /api/labels?recording_id=…[&recording_parent_directory=…] → {document: LabelDocument | null}
 *   PUT /api/labels {recording_id, recording_parent_directory, document} → {document: LabelDocument}
 * Labels live in the recording's own skellyclicker/ directory.
 */
export interface RecordingKey {
    readonly recordingId: string;
    readonly parentDirectory: string | null;
}

function fail(message: string): never {
    throw new Error(`Label document: ${message}`);
}

function parseObservation(value: unknown, index: number): Observation {
    if (typeof value !== 'object' || value === null) fail(`observation ${index} is not an object`);
    const o = value as Record<string, unknown>;
    if (typeof o.point !== 'string') fail(`observation ${index} has no point`);
    if (typeof o.camera_id !== 'string') fail(`observation ${index} has no camera_id`);
    if (!Number.isInteger(o.source_frame)) fail(`observation ${index} source_frame must be an integer`);
    if (typeof o.x_px !== 'number' || !Number.isFinite(o.x_px)) fail(`observation ${index} x_px must be finite`);
    if (typeof o.y_px !== 'number' || !Number.isFinite(o.y_px)) fail(`observation ${index} y_px must be finite`);
    if (o.origin !== 'click' && o.origin !== 'accepted') fail(`observation ${index} origin must be click or accepted`);
    return {point: o.point, camera_id: o.camera_id, source_frame: o.source_frame as number, x_px: o.x_px, y_px: o.y_px, origin: o.origin};
}

export function parseLabelDocument(value: unknown, recordingId: string): LabelDocument {
    if (typeof value !== 'object' || value === null) fail('not an object');
    const d = value as Record<string, unknown>;
    if (d.schema_version !== 1) fail(`unsupported schema_version ${String(d.schema_version)}`);
    if (d.recording_id !== recordingId) fail(`belongs to ${String(d.recording_id)}, not ${recordingId}`);
    if (!Array.isArray(d.tracked_point_names) || !d.tracked_point_names.every(name => typeof name === 'string')) fail('tracked_point_names must be strings');
    const names = d.tracked_point_names as string[];
    if (!Array.isArray(d.observations)) fail('observations must be a list');
    const observations = d.observations.map(parseObservation);
    const unknown = observations.find(observation => !names.includes(observation.point));
    if (unknown) fail(`observation for unknown point "${unknown.point}"`);
    const s = d.session as Record<string, unknown> | null;
    if (typeof s !== 'object' || s === null) fail('session missing');
    const optionalString = (field: string): string | null => {
        const v = s[field];
        if (v !== null && typeof v !== 'string') fail(`session.${field} must be a string or null`);
        return v as string | null;
    };
    const optionalInteger = (field: string): number | null => {
        const v = s[field];
        if (v !== null && !Number.isInteger(v)) fail(`session.${field} must be an integer or null`);
        return v as number | null;
    };
    return {schema_version: 1, recording_id: recordingId, tracked_point_names: names, observations,
        session: {active_point: optionalString('active_point'), active_camera: optionalString('active_camera'),
            source_frame: optionalInteger('source_frame'), local_frame_index: optionalInteger('local_frame_index')}};
}

async function errorDetail(response: Response): Promise<string> {
    const text = await response.text();
    try { return String((JSON.parse(text) as {detail?: unknown}).detail ?? text); } catch { return text; }
}

export async function loadLabels(baseUrl: string, key: RecordingKey, signal: AbortSignal): Promise<LabelDocument | null> {
    const query = new URLSearchParams({recording_id: key.recordingId});
    if (key.parentDirectory !== null) query.set('recording_parent_directory', key.parentDirectory);
    const response = await fetch(`${baseUrl}/api/labels?${query}`, {signal});
    if (!response.ok) throw new Error(`Loading labels failed (${response.status}): ${await errorDetail(response)}`);
    const body = await response.json() as {document?: unknown};
    if (!('document' in body)) throw new Error('Loading labels failed: response has no "document" field');
    return body.document === null ? null : parseLabelDocument(body.document, key.recordingId);
}

export async function saveLabels(baseUrl: string, key: RecordingKey, document: LabelDocument): Promise<void> {
    const response = await fetch(`${baseUrl}/api/labels`, {method: 'PUT', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({recording_id: key.recordingId, recording_parent_directory: key.parentDirectory, document})});
    if (!response.ok) throw new Error(`Saving labels failed (${response.status}): ${await errorDetail(response)}`);
}
