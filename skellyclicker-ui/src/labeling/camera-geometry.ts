import type {CalibrationCameraData} from '@freemocap/ui';

export type Vec2 = readonly [number, number];
export type Vec3 = readonly [number, number, number];
type Mat3 = readonly [Vec3, Vec3, Vec3];

/** Pinhole camera with OpenCV Brown distortion (k1, k2, p1, p2); world-to-optical extrinsics in mm. */
export interface CameraModel {
    readonly id: string;
    readonly imageWidth: number;
    readonly imageHeight: number;
    readonly fx: number;
    readonly fy: number;
    readonly cx: number;
    readonly cy: number;
    readonly k1: number;
    readonly k2: number;
    readonly p1: number;
    readonly p2: number;
    /** World-to-camera rotation. */
    readonly rotation: Mat3;
    /** World-to-camera translation (mm). */
    readonly translation: Vec3;
    /** Camera center in world coordinates (mm). */
    readonly center: Vec3;
}

export interface Ray {
    readonly origin: Vec3;
    /** Unit direction in world coordinates. */
    readonly direction: Vec3;
}

export interface PixelObservation {
    readonly camera: CameraModel;
    readonly pixel: Vec2;
}

export interface Triangulation {
    readonly position: Vec3;
    /** Reprojection error (px) for each observation, in input order. */
    readonly errorsPx: readonly number[];
    readonly meanErrorPx: number;
}

const transpose = (m: Mat3): Mat3 => [
    [m[0][0], m[1][0], m[2][0]],
    [m[0][1], m[1][1], m[2][1]],
    [m[0][2], m[1][2], m[2][2]],
];
const multiply = (m: Mat3, v: Vec3): Vec3 => [
    m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
    m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
    m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
];
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const scale = (v: Vec3, s: number): Vec3 => [v[0] * s, v[1] * s, v[2] * s];
const norm = (v: Vec3): number => Math.hypot(v[0], v[1], v[2]);
export const distance = (a: Vec3, b: Vec3): number => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/**
 * Build a camera from a FreeMoCap calibration entry. `world_orientation` is the camera-to-world
 * rotation and `world_position` the camera center, so the world-to-camera rotation is its transpose.
 * Throws when the entry's center and extrinsic translation disagree.
 */
export function cameraModelFromCalibration(camera: CalibrationCameraData): CameraModel {
    const orientation = camera.world_orientation;
    if (orientation.length !== 3) throw new Error(`Camera ${camera.id}: world_orientation must be 3x3`);
    const cameraToWorld: Mat3 = [orientation[0], orientation[1], orientation[2]];
    const rotation = transpose(cameraToWorld);
    const translation: Vec3 = camera.extrinsics.translation;
    const center: Vec3 = camera.world_position;
    const implied = scale(multiply(cameraToWorld, translation), -1);
    const tolerance = Math.max(1e-3, 1e-6 * norm(center));
    if (distance(implied, center) > tolerance) {
        throw new Error(`Camera ${camera.id}: world_position ${JSON.stringify(center)} disagrees with -Rᵀt ${JSON.stringify(implied)}`);
    }
    const [imageWidth, imageHeight] = camera.image_size;
    const {fx, fy, cx, cy, k1, k2, p1, p2} = camera.intrinsics;
    if (!(fx > 0 && fy > 0)) throw new Error(`Camera ${camera.id}: focal lengths must be positive`);
    return {id: camera.id, imageWidth, imageHeight, fx, fy, cx, cy, k1, k2, p1, p2, rotation, translation, center};
}

/** Distort a normalized image point and map it to pixels. */
function distortToPixel(camera: CameraModel, x: number, y: number): Vec2 {
    const r2 = x * x + y * y;
    const radial = 1 + camera.k1 * r2 + camera.k2 * r2 * r2;
    const xd = x * radial + 2 * camera.p1 * x * y + camera.p2 * (r2 + 2 * x * x);
    const yd = y * radial + camera.p1 * (r2 + 2 * y * y) + 2 * camera.p2 * x * y;
    return [camera.fx * xd + camera.cx, camera.fy * yd + camera.cy];
}

/** World point → pixel. Null when the point is at or behind the camera plane. */
export function projectPoint(camera: CameraModel, point: Vec3): Vec2 | null {
    const local = add(multiply(camera.rotation, point), camera.translation);
    if (local[2] <= 1e-9) return null;
    return distortToPixel(camera, local[0] / local[2], local[1] / local[2]);
}

/**
 * Largest undistorted normalized radius the image covers, padded by 20%. The distortion
 * polynomial folds back beyond the calibrated field of view, so directions outside it are not drawn.
 */
function fieldOfViewRadius(camera: CameraModel): number {
    // r_distorted = r + k1*r³ + k2*r⁵. Beyond its first turning point,
    // off-axis rays can project back into the image a second time.
    const b = 3 * camera.k1;
    const discriminant = b * b - 20 * camera.k2;
    if (discriminant > 0) {
        const denominator = Math.sqrt(discriminant) - b;
        if (denominator > 0) return Math.sqrt(2 / denominator);
    }
    const corners: Vec2[] = [[0, 0], [camera.imageWidth, 0], [0, camera.imageHeight], [camera.imageWidth, camera.imageHeight]];
    return 1.2 * Math.max(...corners.map(corner => Math.hypot(...undistortPixel(camera, corner))));
}

/** Pixel → undistorted normalized coordinates (OpenCV fixed-point iteration). */
export function undistortPixel(camera: CameraModel, pixel: Vec2): Vec2 {
    const xd = (pixel[0] - camera.cx) / camera.fx;
    const yd = (pixel[1] - camera.cy) / camera.fy;
    let x = xd;
    let y = yd;
    for (let iteration = 0; iteration < 30; iteration += 1) {
        const r2 = x * x + y * y;
        const radial = 1 + camera.k1 * r2 + camera.k2 * r2 * r2;
        const dx = 2 * camera.p1 * x * y + camera.p2 * (r2 + 2 * x * x);
        const dy = camera.p1 * (r2 + 2 * y * y) + 2 * camera.p2 * x * y;
        x = (xd - dx) / radial;
        y = (yd - dy) / radial;
    }
    return [x, y];
}

/** The world-space ray through a pixel. */
export function pixelRay(camera: CameraModel, pixel: Vec2): Ray {
    const [x, y] = undistortPixel(camera, pixel);
    const local: Vec3 = [x, y, 1];
    const world = multiply(transpose(camera.rotation), local);
    return {origin: camera.center, direction: scale(world, 1 / norm(world))};
}

export const pointOnRay = (ray: Ray, depthMm: number): Vec3 => add(ray.origin, scale(ray.direction, depthMm));

/** Largest distance between any two camera centers; sets the scale for rays and epipolar sampling. */
export function rigBaselineMm(cameras: readonly CameraModel[]): number {
    let largest = 0;
    for (const a of cameras) for (const b of cameras) largest = Math.max(largest, distance(a.center, b.center));
    if (!(largest > 0)) throw new Error('Camera rig needs at least two distinct camera centers');
    return largest;
}

/**
 * Epipolar curve of `ray` in `camera`: the ray sampled from near to far depth and projected.
 * Distortion bends it, so it is returned as polylines; pieces behind the camera or outside the
 * calibrated field of view split the curve.
 */
export function epipolarPolylines(camera: CameraModel, ray: Ray, nearMm: number, farMm: number, samples: number): Vec2[][] {
    if (!(nearMm > 0 && farMm > nearMm && samples >= 2)) throw new Error('Epipolar sampling needs 0 < near < far and at least two samples');
    const maxRadius = fieldOfViewRadius(camera);
    const lines: Vec2[][] = [];
    let current: Vec2[] = [];
    const ratio = Math.pow(farMm / nearMm, 1 / (samples - 1));
    for (let index = 0; index < samples; index += 1) {
        const local = add(multiply(camera.rotation, pointOnRay(ray, nearMm * Math.pow(ratio, index))), camera.translation);
        const usable = local[2] > 1e-9 && Math.hypot(local[0] / local[2], local[1] / local[2]) <= maxRadius;
        if (usable) current.push(distortToPixel(camera, local[0] / local[2], local[1] / local[2]));
        else if (current.length) { if (current.length > 1) lines.push(current); current = []; }
    }
    if (current.length > 1) lines.push(current);
    return lines;
}

/** Eigenvector of the smallest eigenvalue of a symmetric 4x4 matrix (cyclic Jacobi). */
function smallestEigenvector(input: number[][]): number[] {
    const a = input.map(row => [...row]);
    const v = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    for (let sweep = 0; sweep < 60; sweep += 1) {
        let off = 0;
        for (let p = 0; p < 4; p += 1) for (let q = p + 1; q < 4; q += 1) off += a[p][q] * a[p][q];
        if (off < 1e-24) break;
        for (let p = 0; p < 4; p += 1) {
            for (let q = p + 1; q < 4; q += 1) {
                if (Math.abs(a[p][q]) < 1e-300) continue;
                const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
                const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
                const c = 1 / Math.sqrt(t * t + 1);
                const s = t * c;
                for (let k = 0; k < 4; k += 1) {
                    const akp = a[k][p];
                    const akq = a[k][q];
                    a[k][p] = c * akp - s * akq;
                    a[k][q] = s * akp + c * akq;
                }
                for (let k = 0; k < 4; k += 1) {
                    const apk = a[p][k];
                    const aqk = a[q][k];
                    a[p][k] = c * apk - s * aqk;
                    a[q][k] = s * apk + c * aqk;
                }
                for (let k = 0; k < 4; k += 1) {
                    const vkp = v[k][p];
                    const vkq = v[k][q];
                    v[k][p] = c * vkp - s * vkq;
                    v[k][q] = s * vkp + c * vkq;
                }
            }
        }
    }
    let smallest = 0;
    for (let i = 1; i < 4; i += 1) if (a[i][i] < a[smallest][smallest]) smallest = i;
    return [v[0][smallest], v[1][smallest], v[2][smallest], v[3][smallest]];
}

/**
 * Linear (DLT) triangulation from undistorted normalized coordinates of two or more views.
 * Null when the rays are parallel or the solution lies behind any observing camera.
 */
export function triangulate(observations: readonly PixelObservation[]): Triangulation | null {
    if (observations.length < 2) throw new Error('Triangulation needs at least two observations');
    const ata = Array.from({length: 4}, () => [0, 0, 0, 0]);
    for (const {camera, pixel} of observations) {
        const [x, y] = undistortPixel(camera, pixel);
        const r = camera.rotation;
        const t = camera.translation;
        const rows = [0, 1].map(axis => {
            const coordinate = axis === 0 ? x : y;
            return [0, 1, 2, 3].map(column => {
                const p3 = column < 3 ? r[2][column] : t[2];
                const pAxis = column < 3 ? r[axis][column] : t[axis];
                return coordinate * p3 - pAxis;
            });
        });
        for (const row of rows) for (let i = 0; i < 4; i += 1) for (let j = 0; j < 4; j += 1) ata[i][j] += row[i] * row[j];
    }
    const solution = smallestEigenvector(ata);
    if (Math.abs(solution[3]) < 1e-12) return null;
    const position: Vec3 = [solution[0] / solution[3], solution[1] / solution[3], solution[2] / solution[3]];
    const errorsPx: number[] = [];
    for (const {camera, pixel} of observations) {
        const projected = projectPoint(camera, position);
        if (!projected) return null;
        errorsPx.push(Math.hypot(projected[0] - pixel[0], projected[1] - pixel[1]));
    }
    return {position, errorsPx, meanErrorPx: errorsPx.reduce((sum, value) => sum + value, 0) / errorsPx.length};
}
