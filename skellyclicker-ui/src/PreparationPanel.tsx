import {useEffect,useState} from 'react';
import type {ProjectView} from './ProjectPanel';
type Job={job_id:string;state:string;stage:string;completed:number;total:number;accepted?:number;error?:string};
/** Preparation controls never own playback; completed resources go to PlaybackWorkspace. */
export function PreparationPanel({baseUrl,project,onComplete}:{baseUrl:string;project:ProjectView;onComplete:(p:ProjectView)=>void}) {
 const [start,setStart]=useState(0),[count,setCount]=useState(30),[job,setJob]=useState<Job|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const active=!!job&&['queued','running','cancelling'].includes(job.state);
 async function request(url:string,body?:unknown) {const r=await fetch(baseUrl+url,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;}
 useEffect(()=>{if(!active)return;let alive=true;const timer=setInterval(()=>{void request('/api/preparation/status/'+job!.job_id).then(value=>{if(alive)setJob(value);}).catch(e=>{if(alive)setError(String(e));});},1000);return()=>{alive=false;clearInterval(timer);};},[job?.job_id,active,baseUrl]);
 useEffect(()=>{if(job?.state!=='complete')return;let alive=true;void request('/api/projects/open',{project_path:project.manifest_path}).then(p=>{if(alive)onComplete(p);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[job?.state,project.manifest_path,baseUrl]);
 async function prepare(){setBusy(true);setError('');try{setJob(await request('/api/preparation/start',{project_path:project.manifest_path,start_frame:start,frame_count:count}));}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <details className="preparation-controls"><summary>Prepare another sample range</summary>
  <p>Fresh stereo/depth and pose candidates. This recording uses its explicit color-mask preset.</p>
  <label>First source frame<input type="number" min="0" value={start} disabled={active||busy} onChange={e=>setStart(Number(e.target.value))}/></label>
  <label>Frames<input type="number" min="1" max="60" value={count} disabled={active||busy} onChange={e=>setCount(Number(e.target.value))}/></label>
  <button disabled={active||busy||project.issues.length>0} onClick={()=>void prepare()}>{busy?'Verifying source…':'Prepare fresh samples'}</button>
  {active&&<button onClick={()=>void request('/api/preparation/cancel/'+job!.job_id,{}).then(setJob).catch(e=>setError(String(e)))}>Cancel preparation</button>}
  {job&&<p role="status">{job.state} · {job.stage} · {job.completed}/{job.total}</p>}
  {(error||job?.error)&&<p role="alert">{error||job?.error}</p>}
 </details>;
}
