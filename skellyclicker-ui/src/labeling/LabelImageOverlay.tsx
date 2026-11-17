import {useEffect, useLayoutEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent} from 'react';
import type {ImageOverlayContext, PresentedImage} from '@freemocap/ui';
import type {CameraModel, Vec2} from './camera-geometry';
import {epipolarCurves, type FrameEvidence, type PointEvidence, type ViewEvidence} from './labels';

const CLICK_SLOP_SCREEN_PX = 5;

export interface LabelImageOverlayProps {
    readonly sourceSize?: readonly [number,number];
    readonly context: ImageOverlayContext;
    readonly evidence: FrameEvidence | null;
    readonly activePoint: string | null;
    readonly cameras: ReadonlyMap<string, CameraModel>;
    readonly onRegisterView: (videoId: string, width: number, height: number) => void;
    readonly onPlace: (videoId: string, pixel: Vec2, frame: PresentedImage) => void;
    readonly onClear: (videoId: string, frame: PresentedImage) => void;
    readonly onFrameUnavailable: () => void;
}

/** Image pixels per screen pixel, re-measured when the tile resizes, zooms or pans. */
function useImagePixelsPerScreenPixel(svg: SVGSVGElement | null): number {
    const [ratio, setRatio] = useState(1);
    useEffect(() => {
        if (!svg) return;
        let frame = 0;
        const measure = (): void => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                const matrix = svg.getScreenCTM();
                if (!matrix || matrix.a <= 0) return;
                setRatio(1 / matrix.a);
            });
        };
        measure();
        const resize = new ResizeObserver(measure);
        resize.observe(svg);
        const tile = svg.closest('.video-feed-tile') ?? svg;
        const events = ['wheel', 'pointerup', 'dblclick', 'touchend'] as const;
        events.forEach(name => tile.addEventListener(name, measure, {passive: true}));
        return () => {
            cancelAnimationFrame(frame);
            resize.disconnect();
            events.forEach(name => tile.removeEventListener(name, measure));
        };
    }, [svg]);
    return ratio;
}

function polylinePoints(line: readonly Vec2[]): string {
    return line.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
}

function Marker({point, view, active, s}: {point: PointEvidence; view: ViewEvidence; active: boolean; s: number}) {
    if (!view.pixel) return null;
    const [x, y] = view.pixel;
    const number = String(point.index + 1);
    const grow = active ? 1.2 : 1;
    const opacity = active ? 1 : 0.8;
    const label = active ? `${point.point}${view.kind === 'projected' ? ' · projected' : view.kind === 'accepted' ? ' · accepted' : ''}` : null;
    return <g opacity={opacity}>
        {view.kind === 'click' && <>
            <circle cx={x} cy={y} r={7 * s * grow} fill={point.color} stroke="#0b1111" strokeWidth={2 * s}/>
            <text x={x} y={y} dy={3.2 * s * grow} textAnchor="middle" fontSize={9 * s * grow} fontWeight={700} fill="#0b1111">{number}</text>
        </>}
        {view.kind === 'accepted' && <>
            <circle cx={x} cy={y} r={8 * s * grow} fill={point.color}/>
            <circle cx={x} cy={y} r={5.5 * s * grow} fill="none" stroke="#0b1111" strokeWidth={2.5 * s}/>
        </>}
        {view.kind === 'projected' && <>
            <circle cx={x} cy={y} r={12 * s * grow} fill="rgba(11,17,17,0.3)" stroke={point.color} strokeWidth={2 * s}
                strokeDasharray={`${4 * s} ${3 * s}`}/>
            <circle cx={x} cy={y} r={1.5 * s} fill={point.color}/>
        </>}
        {label && <text x={x + 16 * s} y={y} dy={4 * s} fontSize={12 * s} fontWeight={600} fill={point.color}
            stroke="#0b1111" strokeWidth={3 * s} paintOrder="stroke">{label}</text>}
    </g>;
}

/** Clicks, projections and epipolar curves for one camera, drawn in that camera's source pixels. */
export function LabelImageOverlay({context, sourceSize, evidence, activePoint, cameras, onRegisterView, onPlace, onClear, onFrameUnavailable}: LabelImageOverlayProps) {
    const {videoId} = context;
    const [imageWidth,imageHeight] = sourceSize ?? [context.imageWidth,context.imageHeight];
    const scaleX = context.imageWidth/imageWidth, scaleY = context.imageHeight/imageHeight;
    const [svg, setSvg] = useState<SVGSVGElement | null>(null);
    const s = useImagePixelsPerScreenPixel(svg);
    const pressed = useRef<{x: number; y: number; frame: PresentedImage | null} | null>(null);
    useLayoutEffect(() => { onRegisterView(videoId, imageWidth, imageHeight); }, [onRegisterView, videoId, imageWidth, imageHeight]);

    const active = evidence?.points.find(point => point.point === activePoint) ?? null;
    const curves = active ? epipolarCurves(active, videoId, cameras) : [];

    const toImage = (clientX: number, clientY: number): Vec2 | null => {
        const matrix = svg?.getScreenCTM();
        if (!svg || !matrix) return null;
        const local = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
        return local.x >= 0 && local.x < context.imageWidth && local.y >= 0 && local.y < context.imageHeight ? [local.x/scaleX, local.y/scaleY] : null;
    };
    const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>): void => {
        if (event.button !== 0 || !activePoint) return;
        pressed.current = {x: event.clientX, y: event.clientY, frame: context.getPresentedFrame()};
        context.pause();
    };
    const onPointerUp = (event: ReactPointerEvent<SVGSVGElement>): void => {
        const start = pressed.current;
        pressed.current = null;
        if (!start || event.button !== 0 || !activePoint) return;
        if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > CLICK_SLOP_SCREEN_PX) return;
        const pixel = toImage(event.clientX, event.clientY);
        if (!pixel) return;
        const frame = context.getPresentedFrame();
        if (!frame || !start.frame || frame.recording.id !== start.frame.recording.id || frame.sourceFrameNumber !== start.frame.sourceFrameNumber) { onFrameUnavailable(); return; }
        onPlace(videoId, pixel, frame);
    };
    const onContextMenu = (event: ReactMouseEvent<SVGSVGElement>): void => {
        if (!activePoint) return;
        event.preventDefault();
        const frame = context.getPresentedFrame();
        if (!frame) { onFrameUnavailable(); return; }
        onClear(videoId, frame);
    };

    return <svg ref={setSvg} className="label-image-overlay" viewBox={`0 0 ${context.imageWidth} ${context.imageHeight}`}
        preserveAspectRatio="xMidYMin meet" role="img"
        aria-label={activePoint ? `Click to place ${activePoint} in ${videoId}; right-click to clear` : `${videoId} labels`}
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'hidden', cursor: activePoint ? 'crosshair' : 'inherit'}}
        onPointerDown={onPointerDown} onPointerUp={onPointerUp} onContextMenu={onContextMenu}>
        <g transform={`scale(${scaleX} ${scaleY})`}>
        {active && curves.map(curve => curve.lines.map((line, index) => <polyline key={`${curve.fromCamera}:${index}`}
            points={polylinePoints(line)} fill="none" stroke={active.color} strokeOpacity={0.85} strokeWidth={1.5 * s}
            strokeDasharray={`${8 * s} ${5 * s}`}>
            <title>{`Epipolar line of ${active.point} from ${curve.fromCamera}`}</title>
        </polyline>))}
        {evidence?.points.map(point => {
            const view = point.views.find(candidate => candidate.cameraId === videoId);
            return view ? <Marker key={point.point} point={point} view={view} active={point.point === activePoint} s={s}/> : null;
        })}
        </g>
    </svg>;
}
