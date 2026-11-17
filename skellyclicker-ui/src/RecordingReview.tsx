import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import type {ImageOverlayContext,TargetCropRequest} from '@freemocap/ui';
import type {Observation,LabelDocument} from './labeling/labels';
import type {OpenRecording} from './RecordingPicker';
import type {Labeling} from './labeling/useLabeling';
import {useLabelDrag} from './labeling/useLabelDrag';
import {pointColor} from './labeling/labels';

type Point = {x:number; y:number; name:string};
type PredictionImage = {camera_id:string; source_frame:number; keypoints:(number|null)[][]};
export type CheckpointSource = {artifact:string; epoch:number; runId:string};
function useRecordingPredictions(source:CheckpointSource|null) {
  const [loaded,setLoaded]=useState<{source:CheckpointSource; images:Map<string,Point[]>}|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    setError('');
    if (!source) return;
    const checkpoint=source;
    const abort=new AbortController();
    async function read(path:string) {
      const response=await fetch(checkpoint.artifact+encodeURIComponent(path),{signal:abort.signal});
      if (!response.ok) throw Error('Could not load saved checkpoint predictions ('+response.status+')');
      return response.json();
    }
    // Preview events arrive before the worker atomically publishes predictions.json.
    let retry:ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const [manifest,saved]=await Promise.all([read('dataset/manifest.json'),read('previews/epoch-'+String(checkpoint.epoch).padStart(6,'0')+'/predictions.json')]);
        const images=new Map<string,Point[]>();
        for (const image of saved.images as PredictionImage[]) {
          images.set(imageKey(image.camera_id,image.source_frame),image.keypoints.flatMap(([x,y],index)=>
            typeof x==='number'&&typeof y==='number'?[{x,y,name:manifest.keypoint_names[index]}]:[]));
        }
        if (!abort.signal.aborted) {setLoaded({source:checkpoint,images});setError('');}
      } catch(e) {if (!abort.signal.aborted) {setError(String(e));retry=setTimeout(load,5000);}}
    }
    void load();
    return ()=>{abort.abort();clearTimeout(retry);};
  },[source]);
  return {images:loaded?.source===source?loaded?.images:undefined,error};
}
const imageKey=(camera:string,frame:number)=>JSON.stringify([camera,frame]);
/** Close-up bounds around the points with enough surrounding image to stay sharp and recognizable. */
function crop(points:Point[],width:number,height:number) {
  if (!points.length) return null;
  const pad=Math.max(24,0.06*Math.max(width,height));
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  const x=Math.max(0,Math.min(...xs)-pad),y=Math.max(0,Math.min(...ys)-pad);
  const right=Math.min(width,Math.max(...xs)+pad),bottom=Math.min(height,Math.max(...ys)+pad);
  return right>x&&bottom>y?{x,y,width:right-x,height:bottom-y}:null;
}
const observed=(o:Observation):Point=>({x:o.x_px,y:o.y_px,name:o.point});
/** Label: filled circle with its point number. Prediction: hollow diamond in the same color, joined to its label by an error line. */
function Marks({labels,predictions,names,anchors=labels}:{labels:Point[];predictions:Point[];names:readonly string[];anchors?:Point[]}) {
  const color=(name:string)=>pointColor(Math.max(0,names.indexOf(name)));
  const number=(name:string)=>names.indexOf(name)+1;
  return <>
    {predictions.map(p=>{
      const label=anchors.find(l=>l.name===p.name);
      return <g key={'p'+p.name} stroke={color(p.name)} fill="none" strokeWidth="2" vectorEffect="non-scaling-stroke">
        {label&&<line x1={label.x} y1={label.y} x2={p.x} y2={p.y} strokeWidth="1.5" vectorEffect="non-scaling-stroke"/>}
        <path d={`M${p.x} ${p.y-6}L${p.x+6} ${p.y}L${p.x} ${p.y+6}L${p.x-6} ${p.y}Z`} vectorEffect="non-scaling-stroke"/>
        <title>{number(p.name)} · {p.name} · model prediction</title></g>;
    })}
    {labels.map(p=><g key={'l'+p.name}>
      <circle cx={p.x} cy={p.y} r="5" fill={color(p.name)} stroke="#0b1111" strokeWidth="1.5" vectorEffect="non-scaling-stroke"/>
      <text x={p.x+7} y={p.y-7} fill={color(p.name)} fontSize="12" fontWeight="700" paintOrder="stroke" stroke="#0b1111" strokeWidth="3">{number(p.name)}</text>
      <title>{number(p.name)} · {p.name} · clicked label</title></g>)}
  </>;
}
export function useRecordingReview(recording:OpenRecording|null,doc:LabelDocument|null,source:CheckpointSource|null) {
  const predictions=useRecordingPredictions(source);
  const groups=useMemo(()=>{
    const byImage=new Map<string,Observation[]>();
    for(const row of doc?.observations??[]) {
      const key=imageKey(row.camera_id,row.source_frame);
      const rows=byImage.get(key);
      if(rows) rows.push(row); else byImage.set(key,[row]);
    }
    return byImage;
  },[doc?.observations]);
  const getCrop=useCallback((request:TargetCropRequest)=>{
    if(request.recording.id!==recording?.id) return null;
    const [w,h]=recording.sourceSizes[request.filename]??[request.imageWidth,request.imageHeight];
    const key=imageKey(request.videoId,request.sourceFrameNumber);
    const points=(groups.get(key)??[]).map(observed);
    const bounds=crop([...points,...predictions.images?.get(key)??[]],w,h);
    return bounds&&{x:bounds.x*request.imageWidth/w,y:bounds.y*request.imageHeight/h,width:bounds.width*request.imageWidth/w,height:bounds.height*request.imageHeight/h};
  },[recording,groups,predictions.images]);
  return {groups,predictions,getCrop};
}
type Review=ReturnType<typeof useRecordingReview>;
export function RecordingOverlay({context,recording,review,frame,showPredictions,names}:{context:ImageOverlayContext;recording:OpenRecording;review:Review;frame:number;showPredictions:boolean;names:readonly string[]}) {
  const anchor=useRef<SVGSVGElement>(null);
  const [closeup,setCloseup]=useState<HTMLElement|null>(null);
  // The SDK positions and resizes the close-up independently of the full image.
  useLayoutEffect(()=>{setCloseup(anchor.current?.closest('.video-feed-tile')?.querySelector<HTMLElement>('.playback-target-closeup')??null);},[context.videoId]);
  const key=imageKey(context.videoId,frame);
  const predictions=review.predictions.images?.get(key)??[],labels=(review.groups.get(key)??[]).map(observed);
  const [width,height]=recording.sourceSizes[context.filename]??[context.imageWidth,context.imageHeight];
  const bounds=crop([...labels,...predictions],width,height);
  return <><svg ref={anchor} className="recording-overlay" aria-label="Model predictions" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMin meet">
    {showPredictions&&<Marks labels={[]} anchors={labels} predictions={predictions} names={names}/>}</svg>
    {closeup&&bounds&&createPortal(<svg className="recording-overlay" aria-label="Close-up model predictions"
      viewBox={`${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`} preserveAspectRatio="none">
      <Marks labels={[]} anchors={labels} predictions={showPredictions?predictions:[]} names={names}/></svg>,closeup)}</>;
}
function ImagePair({url,rows,predictions,onMove,names}:{url:string;rows:Observation[];predictions:Point[];onMove:Labeling['moveTrainingLabel'];names:readonly string[]}) {
  const [size,setSize]=useState<number[]>([]);
  const [failed,setFailed]=useState(false);
  const labels=rows.map(observed);
  const [width,height]=size;
  const {preview,bind}=useLabelDrag(width,height);
  const bounds=width&&crop(labels,width,height);
  const marks=<>{labels.map(point=>{
    const [x,y]=preview?.point===point.name?preview.pixel:[point.x,point.y];
    return <g key={point.name} aria-label={'Drag '+point.name} className="training-label-handle"
      {...bind(point.name,[point.x,point.y],()=>pixel=>onMove(rows[0].camera_id,rows[0].source_frame,point.name,pixel))}>
      <circle cx={x} cy={y} r="4" fill="transparent" stroke="transparent" strokeWidth="12" vectorEffect="non-scaling-stroke"/>
      <Marks labels={[{...point,x,y}]} predictions={[]} names={names}/>
    </g>;
  })}<g pointerEvents="none"><Marks labels={[]} anchors={labels} predictions={predictions} names={names}/></g></>;
  const errors=labels.flatMap(p=>{
    const match=predictions.find(m=>m.name===p.name);
    return match?[Math.hypot(match.x-p.x,match.y-p.y)]:[];
  });
  return <article className="keypoint-section"><h3>{rows[0].camera_id} · frame {rows[0].source_frame}</h3>
    <div className="recording-image-pair"><div><img src={url} loading="lazy" alt="Full labeled frame" onError={()=>setFailed(true)}
      onLoad={e=>setSize([e.currentTarget.naturalWidth,e.currentTarget.naturalHeight])}/>
      {width>0&&<svg viewBox={`0 0 ${width} ${height}`}>{marks}</svg>}</div>
      {bounds&&<svg role="img" aria-label="Labeled target close-up" viewBox={`${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`} preserveAspectRatio="xMidYMid meet" style={{aspectRatio:bounds.width/bounds.height}}>
        <image href={url} width={width} height={height}/>{marks}</svg>}</div>
    {failed&&<p role="alert">Source image unavailable</p>}
    <p>{rows.map(o=>o.point).join(' · ')}{errors.length>0?` · mean label–prediction distance ${(errors.reduce((a,b)=>a+b)/errors.length).toFixed(1)} px`:''}</p></article>;
}
export function RecordingTrainingSet({review,recording,baseUrl,labeling}:{review:Review;recording:OpenRecording;baseUrl:string;labeling:Labeling}) {
  const source=recording.labelSource!;
  const images=[...review.groups.values()].map(rows=>rows.filter(o=>o.origin==='click')).filter(rows=>rows.length)
    .sort((a,b)=>a[0].source_frame-b[0].source_frame||a[0].camera_id.localeCompare(b[0].camera_id));
  return <div className="keypoint-training"><header><h2>Training set</h2><span>{images.length} labeled camera images</span></header>
    {images.length>0?<p>Drag a numbered label in either view to adjust it. Diamonds are model predictions in the same point color, joined to their label.</p>:<p>No clicked images yet.</p>}
    {labeling.saveError&&<p role="alert">Could not save label edits. {labeling.saveError}</p>}
    <div className="recording-gallery">{images.map(rows=>{
      const {source_frame,camera_id}=rows[0],key=imageKey(camera_id,source_frame);
      const query=new URLSearchParams({recording_id:source.id,recording_parent_directory:source.parent,camera_id,source_frame:String(source_frame)});
      return <ImagePair key={key} rows={rows} onMove={labeling.moveTrainingLabel} url={baseUrl+'/api/labels/source-image?'+query} predictions={review.predictions.images?.get(key)??[]} names={labeling.document?.tracked_point_names??[]}/>;
    })}</div></div>;
}
