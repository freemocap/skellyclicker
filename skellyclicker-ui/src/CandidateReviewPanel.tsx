import {trainingNavigation} from './training-navigation';
import {useCallback,useEffect,useRef,useState,type RefObject} from 'react';
import {ImageCatalog,ButtonSm,type PlaybackNavigationGroup,type ImageControlContext,type PlaybackWorkspaceHandle,type PresentedFrame} from '@freemocap/ui';
import type {ProjectView} from './ProjectPanel';
interface ImageRow {image_id:string;moment_id:string;camera_id:string;source_frame:number;timestamp_ns:string;playback_frame:number|null}
interface Result {path:string;manifest_sha256:string;playback_id:string|null;images:ImageRow[];manifest:{moment_count:number;image_count:number;label_count:number}}
interface Selection {sha256:string|null;selected_image_ids:string[];review_state:string}
const empty:Selection={sha256:null,selected_image_ids:[],review_state:'unreviewed'};
export function useCandidateReview({baseUrl,project,refreshKey,controls,presented}:{baseUrl:string;project:ProjectView|null;refreshKey:string;controls:RefObject<PlaybackWorkspaceHandle|null>;presented:PresentedFrame|null}) {
 const [loaded,setLoaded]=useState<{projectPath:string;result:Result|null;selection:Selection}|null>(null);
 const [error,setError]=useState(''),[pending,setPending]=useState(false),[activeCamera,setActiveCamera]=useState<string>('left');
 const [camera,setCamera]=useState<string|null>(null);
 const [lastRemoved,setLastRemoved]=useState<ImageRow|null>(null);
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
 async function setMembership(image:ImageRow,included:boolean){
  if(!result||!projectPath||admission.current)return;
  admission.current=true;setPending(true);setError('');controls.current?.pause();
  try{
   const response=await fetch(baseUrl+'/api/labels/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:projectPath,expected_label_manifest_sha256:result.manifest_sha256,expected_selection_sha256:selection.sha256,moment_id:image.moment_id,camera_id:image.camera_id,source_frame:image.source_frame,timestamp_ns:image.timestamp_ns,selected:included})});
   const value=await response.json();if(!response.ok)throw new Error(value.detail);
   setLoaded(previous=>previous?.projectPath===projectPath&&previous.result?.manifest_sha256===result.manifest_sha256?{...previous,selection:value}:previous);
   setLastRemoved(included?null:image);
  }catch(e){setError(String(e));}finally{admission.current=false;setPending(false);}
 }
 function renderImageControls(context:ImageControlContext){
  const frame=context.getPresentedFrame();
  const image=frame&&frame.recording.id===result?.playback_id?result?.images.find(r=>r.source_frame===frame.sourceFrameNumber&&r.camera_id===context.videoId):undefined;
  if(!image||!selected.has(image.image_id))return null;
  return <ButtonSm text="Remove from training set" buttonType="secondary btn-danger" textColor="" iconClass="close-icon" disabled={pending} onClick={()=>{
   context.pause();const fresh=context.getPresentedFrame();
   if(!fresh||fresh.recording.id!==result?.playback_id||fresh.sourceFrameNumber!==image.source_frame||fresh.videoId!==image.camera_id||fresh.presentationEpoch!==frame?.presentationEpoch){setError('Image changed. Pause and try again.');return;}
   void setMembership(image,false);
  }}/>;
 }
 const {moments,previous,next}=trainingNavigation(result?.images??[],selected,camera,currentSource);
 const matchingPlayback=!!result?.playback_id&&result.playback_id===project?.playback?.id;
 const navigationGroups:PlaybackNavigationGroup[]=[{id:'training-images',label:'Training frames',itemLabel:'training frame',count:moments.length,pending,
  detail:error||(!loaded?'Loading membership…':!matchingPlayback?'Training playback unavailable':pending?'Seeking…':`${camera?camera+' camera · ':''}${currentSource===undefined?'No frame presented':'Source frame '+currentSource}`),
  previous:matchingPlayback&&previous?()=>void navigate(previous.image_id):undefined,next:matchingPlayback&&next?()=>void navigate(next.image_id):undefined}];

 const start=result?.images[0]?.timestamp_ns;
 const items=(result?.images??[]).filter(r=>selected.has(r.image_id)).map(r=>({id:r.image_id,groupId:r.moment_id,groupLabel:'Frame '+r.source_frame,camera:r.camera_id,
  thumbnailUrl:baseUrl+'/api/labels/thumbnail?'+new URLSearchParams({project_path:projectPath!,label_manifest_sha256:result!.manifest_sha256,image_id:r.image_id,view:'target-outline-v3'}),
  label:`${r.camera_id} camera · frame ${r.source_frame}`,sourceFrameNumber:r.source_frame,cameraId:r.camera_id,momentId:r.moment_id,
  detail:start?((Number(BigInt(r.timestamp_ns)-BigInt(start))/1e9).toFixed(3)+' s'):undefined,included:selected.has(r.image_id),pending}));
 const onFilterChange=useCallback((value:{camera:string|null})=>setCamera(value.camera),[]);
 const undo=lastRemoved&&result?.images.some(r=>r.image_id===lastRemoved.image_id)&&!selected.has(lastRemoved.image_id)?<ButtonSm text="Undo removal" buttonType="secondary" textColor="" iconClass="rotate-icon" disabled={pending} onClick={()=>void setMembership(lastRemoved,true)}/>:undefined;
 const catalog=result?<ImageCatalog mode="members" items={items} activeId={current?.image_id} onNavigate={id=>void navigate(id)} onRemove={id=>{const image=result.images.find(r=>r.image_id===id);if(image)void setMembership(image,false);}} pending={pending} error={error||undefined} onFilterChange={onFilterChange} actions={undo}/>:null;
 return {catalog,renderImageControls,navigationGroups,activeVideoId:activeCamera,selectionRevision:selection.sha256};
}
