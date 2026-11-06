import {useCallback,useEffect,useRef,useState,type RefObject} from 'react';
import {ImageCatalog,ImageSelectionToggle,type ImageControlContext,type PlaybackWorkspaceHandle,type PresentedFrame} from '@freemocap/ui';
import type {ProjectView} from './ProjectPanel';
interface ImageRow {image_id:string;moment_id:string;camera_id:string;source_frame:number;timestamp_ns:string;playback_frame:number|null}
interface Result {path:string;manifest_sha256:string;playback_id:string|null;images:ImageRow[];manifest:{moment_count:number;image_count:number;label_count:number}}
interface Selection {sha256:string|null;selected_image_ids:string[];review_state:string}
const empty:Selection={sha256:null,selected_image_ids:[],review_state:'unreviewed'};
export function useCandidateReview({baseUrl,project,refreshKey,controls,presented}:{baseUrl:string;project:ProjectView|null;refreshKey:string;controls:RefObject<PlaybackWorkspaceHandle|null>;presented:PresentedFrame|null}) {
 const [loaded,setLoaded]=useState<{projectPath:string;result:Result|null;selection:Selection}|null>(null);
 const [error,setError]=useState(''),[pending,setPending]=useState(false),[activeCamera,setActiveCamera]=useState<string>('left');
 const [mode,setMode]=useState<'included'|'generated'>('included');
 const [filter,setFilter]=useState<{inclusion:'all'|'included'|'excluded';camera:string|null}>({inclusion:'all',camera:null});
 const admission=useRef(false);
 const projectPath=project?.manifest_path;
 const result=loaded?.projectPath===projectPath?loaded?.result:null;
 const selection=loaded?.projectPath===projectPath?loaded?.selection??empty:empty;
 useEffect(()=>{
  if(!projectPath)return;const abort=new AbortController();setError('');
  void Promise.all(['/result','/selection'].map(path=>fetch(baseUrl+'/api/labels'+path+'?project_path='+encodeURIComponent(projectPath),{signal:abort.signal}).then(async response=>{const value=await response.json();if(!response.ok)throw new Error(value.detail);return value;}))).then(([result,selection])=>{if(!abort.signal.aborted)setLoaded({projectPath,result,selection});}).catch(e=>{if(!abort.signal.aborted)setError(String(e));});return()=>abort.abort();
 },[baseUrl,projectPath,refreshKey]);
 const selected=new Set(selection.selected_image_ids);
 const currentSource=presented?.recording.id===result?.playback_id?presented?.sourceFrameNumber:undefined;
 const current=result?.images.find(r=>r.source_frame===currentSource&&r.camera_id===activeCamera);
 async function navigate(id:string){
  const image=result?.images.find(r=>r.image_id===id);if(!image||image.playback_frame===null||admission.current)return;
  admission.current=true;setPending(true);setError('');setActiveCamera(image.camera_id);
  try{controls.current?.pause();const frame=await controls.current?.seekFrame(image.playback_frame);
   if(!frame||frame.recording.id!==result?.playback_id||frame.sourceFrameNumber!==image.source_frame)throw new Error('Requested image was not presented.');
  }catch(e){setError(String(e));}finally{admission.current=false;setPending(false);}
 }
 async function toggle(image:ImageRow){
  if(!result||!projectPath||admission.current)return;
  admission.current=true;setPending(true);setError('');controls.current?.pause();
  try{
   const response=await fetch(baseUrl+'/api/labels/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:projectPath,expected_label_manifest_sha256:result.manifest_sha256,expected_selection_sha256:selection.sha256,moment_id:image.moment_id,camera_id:image.camera_id,source_frame:image.source_frame,timestamp_ns:image.timestamp_ns,selected:!selected.has(image.image_id)})});
   const value=await response.json();if(!response.ok)throw new Error(value.detail);
   setLoaded(previous=>previous?.projectPath===projectPath&&previous.result?.manifest_sha256===result.manifest_sha256?{...previous,selection:value}:previous);
  }catch(e){setError(String(e));}finally{admission.current=false;setPending(false);}
 }
 function renderImageControls(context:ImageControlContext){
  const frame=context.getPresentedFrame();
  const image=frame&&frame.recording.id===result?.playback_id?result?.images.find(r=>r.source_frame===frame.sourceFrameNumber&&r.camera_id===context.videoId):undefined;
  return <ImageSelectionToggle included={image?selected.has(image.image_id):null} pending={pending} disabled={!image||pending} error={error||undefined} onToggle={()=>{
   context.pause();const fresh=context.getPresentedFrame();
   if(!image||!fresh||fresh.recording.id!==result?.playback_id||fresh.sourceFrameNumber!==image.source_frame||fresh.videoId!==image.camera_id||fresh.presentationEpoch!==frame?.presentationEpoch){setError('Image changed. Pause and try again.');return;}
   void toggle(image);
  }}/>;
 }
 const candidates=(result?.images??[]).filter(r=>(!filter.camera||r.camera_id===filter.camera)&&(mode==='generated'||selected.has(r.image_id)));
 const moments=[...new Map(candidates.map(r=>[r.source_frame,r])).values()].sort((a,b)=>a.source_frame-b.source_frame);
 const previous=currentSource===undefined?undefined:[...moments].reverse().find(r=>r.source_frame<currentSource);
 const next=moments.find(r=>currentSource===undefined||r.source_frame>currentSource);
 const start=result?.images[0]?.timestamp_ns;
 const items=(result?.images??[]).map(r=>({id:r.image_id,groupId:r.moment_id,groupLabel:'Frame '+r.source_frame,camera:r.camera_id,
  thumbnailUrl:baseUrl+'/api/labels/thumbnail?'+new URLSearchParams({project_path:projectPath!,label_manifest_sha256:result!.manifest_sha256,image_id:r.image_id}),
  label:r.camera_id==='left'?'Left camera':r.camera_id==='right'?'Right camera':r.camera_id,
  detail:start?((Number(BigInt(r.timestamp_ns)-BigInt(start))/1e9).toFixed(3)+' s'):undefined,included:selected.has(r.image_id),pending}));
 const onFilterChange=useCallback((value:{inclusion:'all'|'included'|'excluded';camera:string|null})=>setFilter(value),[]);
 const catalog=result?<ImageCatalog items={items} activeId={current?.image_id} onNavigate={id=>void navigate(id)} onToggle={id=>{const image=result.images.find(r=>r.image_id===id);if(image)void toggle(image);}} pending={pending} error={error||undefined} onFilterChange={onFilterChange} navigation={{mode,onModeChange:setMode,previousId:previous?.image_id,nextId:next?.image_id,pending}}/>:null;
 return {catalog,renderImageControls,activeVideoId:activeCamera};
}
