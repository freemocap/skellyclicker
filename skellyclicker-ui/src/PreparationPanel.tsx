import {useEffect,useState} from 'react';
import {ButtonSm, ControlSection, NumberField} from '@freemocap/ui';
import type {ProjectView} from './ProjectPanel';
type Job={job_id:string;state:string;stage:string;completed:number;total:number;accepted?:number;error?:string};
/** Preparation controls never own playback; completed resources go to PlaybackWorkspace. */
export function PreparationPanel({baseUrl,project,onComplete}:{baseUrl:string;project:ProjectView;onComplete:(p:ProjectView)=>void}) {
 const [start,setStart]=useState('0'),[count,setCount]=useState('30'),[job,setJob]=useState<Job|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const validRange=start.trim()!==''&&count.trim()!==''&&Number.isInteger(Number(start))&&Number(start)>=0&&Number.isInteger(Number(count))&&Number(count)>=1&&Number(count)<=900;
 const active=!!job&&['queued','running','cancelling'].includes(job.state);
 async function request(url:string,body?:unknown) {const r=await fetch(baseUrl+url,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;}
 useEffect(()=>{let alive=true;void request('/api/preparation/current?project_path='+encodeURIComponent(project.manifest_path)).then(value=>{if(alive)setJob(value);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[baseUrl,project.manifest_path]);
 useEffect(()=>{if(!active)return;let alive=true;const timer=setInterval(()=>{void request('/api/preparation/status/'+job!.job_id).then(value=>{if(alive)setJob(value);}).catch(e=>{if(alive)setError(String(e));});},1000);return()=>{alive=false;clearInterval(timer);};},[job?.job_id,active,baseUrl]);
 useEffect(()=>{if(job?.state!=='complete')return;let alive=true;void request('/api/projects/open',{project_path:project.manifest_path}).then(p=>{if(alive)onComplete(p);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[job?.state,project.manifest_path,baseUrl]);
 async function prepare(){setBusy(true);setError('');try{setJob(await request('/api/preparation/start',{project_path:project.manifest_path,start_frame:Number(start),frame_count:Number(count)}));}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <ControlSection title="Prepare another sample range" collapsible
  description="Generate stereo, depth and pose candidates from the linked recording.">
  <NumberField label="First source frame" min={0} value={start} disabled={active||busy} onChange={setStart}/>
  <NumberField label="Frames" min={1} max={900} value={count} disabled={active||busy} onChange={setCount} description="1–900 consecutive source frames"/>
  <ButtonSm buttonType="secondary" disabled={!validRange||active||busy||project.issues.length>0}
   onClick={()=>void prepare()} text={busy?'Verifying source…':'Prepare fresh samples'}/>
  {active&&<ButtonSm buttonType="secondary" text="Cancel preparation" onClick={()=>void request('/api/preparation/cancel/'+job!.job_id,{}).then(setJob).catch(e=>setError(String(e)))}/>}
  {job&&<p className="sdk-control-description" role="status">{job.state} · {job.stage} · {job.completed}/{job.total}</p>}
  {(error||job?.error)&&<p className="sdk-browser-error" role="alert">{error||job?.error}</p>}
  <details><summary className="sdk-control-description">Preparation details</summary><p className="sdk-control-description">This recording uses its configured color-mask preset. Generated candidates require human review.</p></details>
 </ControlSection>;
}
