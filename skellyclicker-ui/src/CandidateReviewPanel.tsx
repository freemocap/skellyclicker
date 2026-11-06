import {useEffect,useState,type RefObject} from 'react';
import {ButtonSm, type PlaybackWorkspaceHandle, type PresentedFrame} from '@freemocap/ui';
import type {ProjectView} from './ProjectPanel';
interface Moment {moment_id:string;source_frame:number;timestamp_ns:string;playback_frame:number|null;fit_passed:boolean}
interface Result {path:string;manifest_sha256:string;playback_id:string|null;manifest:{moment_count:number;image_count:number;label_count:number};moments:Moment[]}
interface Selection {sha256:string|null;selected_moment_ids:string[];review_state:string}
export function CandidateReviewPanel({baseUrl,project,refreshKey,controls,presented}:{baseUrl:string;project:ProjectView;refreshKey:string;controls:RefObject<PlaybackWorkspaceHandle|null>;presented:PresentedFrame|null}) {
 const [result,setResult]=useState<Result|null>(null),[selection,setSelection]=useState<Selection>({sha256:null,selected_moment_ids:[],review_state:'unreviewed'});
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{const abort=new AbortController();
  void Promise.all(['/result','/selection'].map(path=>fetch(baseUrl+'/api/labels'+path+'?project_path='+encodeURIComponent(project.manifest_path),{signal:abort.signal}).then(async response=>{const value=await response.json();if(!response.ok)throw new Error(value.detail);return value;}))).then(([r,s])=>{setResult(r);setSelection(s);setError('');}).catch(e=>{if(!abort.signal.aborted)setError(String(e));});return()=>abort.abort();
 },[baseUrl,project.manifest_path,refreshKey]);
 const current=result&&presented?.recording.id===result.playback_id?result.moments.find(m=>m.source_frame===presented.sourceFrameNumber):undefined;
 async function navigate(direction:number,selectedOnly=false){if(!result)return;setBusy(true);setError('');try{
  const moments=selectedOnly?result.moments.filter(m=>selection.selected_moment_ids.includes(m.moment_id)):result.moments;
  const source=controls.current?.getPresentedFrame()?.sourceFrameNumber;
  const next=direction>0?moments.find(m=>source===undefined||m.source_frame>source):[...moments].reverse().find(m=>source===undefined||m.source_frame<source);
  if(!next||next.playback_frame===null)return;
  controls.current?.pause();const committed=await controls.current?.seekFrame(next.playback_frame);
  if(!committed||committed.recording.id!==result.playback_id||committed.sourceFrameNumber!==next.source_frame)throw new Error('The requested stereo moment was not presented. Selection was not changed.');
 }catch(e){setError(String(e));}finally{setBusy(false);}}
 async function mark(){if(!result)return;controls.current?.pause();const frame=controls.current?.getPresentedFrame();
  const moment=frame?.recording.id===result.playback_id?result.moments.find(m=>m.source_frame===frame.sourceFrameNumber):undefined;
  if(!moment){setError('Present a generated stereo moment before selecting it.');return;}
  setBusy(true);setError('');try{const response=await fetch(baseUrl+'/api/labels/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:project.manifest_path,expected_label_manifest_sha256:result.manifest_sha256,expected_selection_sha256:selection.sha256,moment_id:moment.moment_id,source_frame:moment.source_frame,timestamp_ns:moment.timestamp_ns,selected:!selection.selected_moment_ids.includes(moment.moment_id)})});const value=await response.json();if(!response.ok)throw new Error(value.detail);setSelection(value);}catch(e){setError(String(e));}finally{setBusy(false);}}
 if(!result)return error?<p role="alert">{error}</p>:null;
 return <section className="candidate-review" aria-label="Generated candidate review"><h3>Generated candidates</h3>
  <p>{result.manifest.moment_count} pairs · {result.manifest.image_count} images · {result.manifest.label_count} labels</p>
  <p>{selection.selected_moment_ids.length} selected for review · All unreviewed</p>
  <p role="status">{current?`Source frame ${current.source_frame} · ${current.fit_passed?'Passed':'Failed'} pilot gates`:'Navigate to a generated moment'}</p>
  <div><ButtonSm text="Previous candidate" disabled={busy} onClick={()=>void navigate(-1)}/><ButtonSm text="Next candidate" disabled={busy} onClick={()=>void navigate(1)}/></div>
  <ButtonSm text={current&&selection.selected_moment_ids.includes(current.moment_id)?'Deselect moment':'Select moment'} disabled={busy||!current} onClick={()=>void mark()}/>
  <div><ButtonSm text="Previous selected" disabled={busy||!selection.selected_moment_ids.length} onClick={()=>void navigate(-1,true)}/><ButtonSm text="Next selected" disabled={busy||!selection.selected_moment_ids.length} onClick={()=>void navigate(1,true)}/></div>
  {error&&<p role="alert">{error}</p>}
 </section>;
}
