import {useRef,useState,type PointerEvent} from 'react';
import type {Vec2} from './camera-geometry';

export const CLICK_SLOP_SCREEN_PX = 5;
type MarkerEvent = PointerEvent<SVGGElement>;
type Commit = (pixel:Vec2)=>void;

/** Freeze the source-to-screen transform on grab, including for an off-center crop. */
export function useLabelDrag(width:number,height:number) {
    const drag=useRef<{id:number;point:string;pixel:Vec2;x:number;y:number;inverse:DOMMatrix;commit:Commit}|null>(null);
    const [preview,setPreview]=useState<{point:string;pixel:Vec2}|null>(null);
    function pixelAt(event:MarkerEvent):Vec2|null {
        const start=drag.current;
        if (!start || start.id!==event.pointerId) return null;
        const dx=event.clientX-start.x,dy=event.clientY-start.y;
        if (Math.hypot(dx,dy)<CLICK_SLOP_SCREEN_PX) return null;
        const m=start.inverse;
        return [Math.max(0,Math.min(width-1,start.pixel[0]+m.a*dx+m.c*dy)),
            Math.max(0,Math.min(height-1,start.pixel[1]+m.b*dx+m.d*dy))];
    }
    function clear() {drag.current=null;setPreview(null);}
    function bind(point:string,pixel:Vec2,begin:()=>Commit|null) {
        return {
            onPointerDown(event:MarkerEvent) {
                if (event.button!==0 || !event.isPrimary || drag.current) return;
                event.stopPropagation();
                const matrix=event.currentTarget.getScreenCTM(),commit=begin();
                if (!matrix || !commit) return;
                drag.current={id:event.pointerId,point,pixel,x:event.clientX,y:event.clientY,inverse:matrix.inverse(),commit};
                event.currentTarget.setPointerCapture(event.pointerId);
            },
            onPointerMove(event:MarkerEvent) {
                if (drag.current?.id!==event.pointerId) return;
                const pixel=pixelAt(event);
                setPreview(pixel?{point,pixel}:null);
            },
            onPointerUp(event:MarkerEvent) {
                const start=drag.current;
                if (!start || start.id!==event.pointerId) return;
                event.stopPropagation();
                const pixel=pixelAt(event);
                clear();
                if (pixel) start.commit(pixel);
            },
            onPointerCancel(event:MarkerEvent) {if(drag.current?.id===event.pointerId) clear();},
            onLostPointerCapture(event:MarkerEvent) {if(drag.current?.id===event.pointerId) clear();},
        };
    }
    return {preview,bind};
}
