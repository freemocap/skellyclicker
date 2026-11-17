import {useEffect,useMemo,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import type {PlaybackWorkspaceHandle} from '@freemocap/ui';
import {frameEvidence,type Observation} from './labeling/labels';
import type {Labeling} from './labeling/useLabeling';
import type {OpenRecording} from './RecordingPicker';
import type {useRecordingReview} from './RecordingReview';

type Review=ReturnType<typeof useRecordingReview>;
type Media={video_source:string;video_filename:string;timeline:{frame_numbers:number[]}};
type Bundle={media:Media[];videos:{sources:Record<string,{videos:{filename:string}[]}>}};
type Score=Map<number,number|null>;
const mean=(values:number[])=>values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
function describe(error:number|null|undefined) {
  return error===undefined?'no data':error===null?'unscored':error.toFixed(1)+' px';
}
function QualityTrack({name,scores,indices,current,frames,seek}:{name:string;scores:Score;indices:Map<number,number>;current:number;frames:number[];seek:(index:number)=>void}) {
  const position=(index:number)=>100*index/Math.max(1,frames.length-1)+'%';
  const summary=name+' · '+describe(scores.get(current));
  return <svg className="label-quality-track" role="img" aria-label={summary} onClick={e=>{
      const box=e.currentTarget.getBoundingClientRect();
      seek(Math.max(0,Math.min(frames.length-1,Math.round((e.clientX-box.left)/box.width*(frames.length-1)))));
    }}><title>{summary} · green 0 px · yellow 6 px · red 12+ px · gray unscored</title>
      {Array.from(scores,([frame,error])=>{
        const index=indices.get(frame);
        if(index===undefined) return null;
        return <rect key={frame} x={position(index)} y="0" width="3" height="100%" transform="translate(-1.5 0)"
          fill={error===null?'#adb4c0':`hsl(${125*(1-Math.min(error/12,1))} 82% 60%)`}>
          <title>Frame {frame} · {name} · {describe(error)}</title></rect>;
      })}
    </svg>;
}
/** Source frame number at each local playback index for the presented media source. */
export function usePlaybackFrames(recording:OpenRecording|null,baseUrl:string,mediaSource:string) {
  const [bundle,setBundle]=useState<Bundle|null>(null);
  const [error,setError]=useState('');
  const source=recording?.labelSource;
  useEffect(()=>{
    setBundle(null);setError('');
    if(!source) return;
    const abort=new AbortController();
    const query=new URLSearchParams({recording_parent_directory:source.parent});
    fetch(baseUrl+'/core/freemocap/recordings/'+encodeURIComponent(source.id)+'/playback/bundle?'+query,{signal:abort.signal})
      .then(async r=>{if(!r.ok) throw Error('Playback timeline unavailable ('+r.status+')');return r.json();})
      .then(data=>{if(!abort.signal.aborted)setBundle(data);}).catch(e=>{if(!abort.signal.aborted)setError(String(e));});
    return ()=>abort.abort();
  },[source?.id,source?.parent,baseUrl]);
  const filename=bundle?.videos.sources[mediaSource]?.videos[0]?.filename;
  const frames=bundle?.media.find(m=>m.video_source===mediaSource&&m.video_filename===filename)?.timeline.frame_numbers;
  return {frames,error};
}
export function LabelQualityTimeline({frames,error,labeling,review,controls}:{frames:number[]|undefined;error:string;labeling:Labeling;review:Review;controls:React.RefObject<PlaybackWorkspaceHandle|null>}) {
  const anchor=useRef<HTMLSpanElement>(null);
  const [scrubber,setScrubber]=useState<HTMLElement|null>(null);
  useEffect(()=>{
    const panel=anchor.current?.closest('[role=tabpanel]');
    if(!panel) return;
    const locate=()=>setScrubber(panel.querySelector<HTMLElement>('.playback-timeline-scrubber'));
    locate();
    const observer=new MutationObserver(locate);
    observer.observe(panel,{childList:true,subtree:true});
    return ()=>observer.disconnect();
  },[]);
  const indices=useMemo(()=>new Map(frames?.map((n,i)=>[n,i])),[frames]);
  const observations=labeling.document?.observations,names=labeling.document?.tracked_point_names;
  const scores=useMemo(()=>{
    const human:Score=new Map(),machine:Score=new Map();
    if(!observations||!names) return {human,machine};
    const grouped=new Map<number,Observation[]>();
    for(const row of observations) {
      if(row.origin!=='click') continue;
      const rows=grouped.get(row.source_frame);
      if(rows) rows.push(row);else grouped.set(row.source_frame,[row]);
    }
    const cameraIds=Array.from(labeling.cameras.keys());
    for(const [frame,rows] of grouped) {
      const evidence=frameEvidence({observations:rows,tracked_point_names:names},frame,cameraIds,labeling.cameras);
      human.set(frame,mean(evidence.points.flatMap(p=>p.triangulation?.errorsPx??[])));
    }
    const distances=new Map<number,number[]>();
    for(const [key,points] of review.predictions.images??[]) {
      const [camera,frame]=JSON.parse(key) as [string,number];
      const atFrame=distances.get(frame)??[];
      for(const row of grouped.get(frame)??[]) {
        if(row.camera_id!==camera) continue;
        const p=points.find(p=>p.name===row.point);
        if(p) atFrame.push(Math.hypot(row.x_px-p.x,row.y_px-p.y));
      }
      distances.set(frame,atFrame);
    }
    for(const [frame,values] of distances) machine.set(frame,mean(values));
    return {human,machine};
  },[observations,names,labeling.cameras,review.predictions.images]);
  const current=labeling.presented?.sourceFrameNumber??-1;
  function seek(index:number) {controls.current?.pause();void controls.current?.seekFrame(index);}
  return <><span hidden ref={anchor}/>{scrubber&&createPortal(<div className="label-quality-timeline">
    {!error&&!!frames?.length&&<>
      <QualityTrack name="Label reprojection error" scores={scores.human} {...{indices,current,frames,seek}}/>
      {scores.machine.size>0&&<QualityTrack name="Model error vs. clicks" scores={scores.machine} {...{indices,current,frames,seek}}/>}
    </>}
  </div>,scrubber)}</>;
}
