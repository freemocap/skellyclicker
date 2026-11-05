import {useEffect,useState} from 'react';
import type {ProjectView} from './ProjectPanel';
type Job={job_id:string;state:string;stage:string;completed:number;total:number;accepted?:number;error?:string};
type Frame={source_frame:number;timestamp_ns:number;status:string;left_iou?:number;right_iou?:number;median_abs_depth_mm?:number;reason:string};
type Result={job_id:string;frames:Frame[];accepted:number;calibration:{nominal_fps:number;depth_units:string};mask_preset:string};
export function PreparationPanel({baseUrl,project}:{baseUrl:string;project:ProjectView}) {
 const [start,setStart]=useState(0),[count,setCount]=useState(30),[job,setJob]=useState<Job|null>(null),[result,setResult]=useState<Result|null>(null),[index,setIndex]=useState(0),[view,setView]=useState('candidate'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[playing,setPlaying]=useState(false);
 const path=project.manifest_path,active=!!job&&['queued','running','cancelling'].includes(job.state);
 async function request(url:string,body?:unknown) {const r=await fetch(baseUrl+'/api/preparation/'+url,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));return value;}
 useEffect(()=>{let alive=true;setJob(null);setResult(null);setIndex(0);setPlaying(false);void request('result?project_path='+encodeURIComponent(path)).then(v=>{if(alive)setResult(v);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[path,baseUrl]);
 useEffect(()=>{if(!active)return;let alive=true;const timer=setInterval(()=>{void request('status/'+job!.job_id).then(value=>{if(alive)setJob(value);}).catch(e=>{if(alive)setError(String(e));});},1000);return()=>{alive=false;clearInterval(timer);};},[job?.job_id,active,path,baseUrl]);
 useEffect(()=>{if(job?.state!=='complete')return;let alive=true;void request('result?project_path='+encodeURIComponent(path)).then(r=>{if(alive){setResult(r);setIndex(0);}}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[job?.state,path,baseUrl]);
 useEffect(()=>{if(!playing||!result)return;const timer=setInterval(()=>setIndex(i=>(i+1)%result.frames.length),1000/Math.min(30,result.calibration.nominal_fps));return()=>clearInterval(timer);},[playing,result]);
 async function prepare(){setBusy(true);setError('');setPlaying(false);try{setJob(await request('start',{project_path:path,start_frame:start,frame_count:count}));}catch(e){setError(String(e));}finally{setBusy(false);}}
 const frame=result?.frames[index];
 const [readyKey,setReadyKey]=useState('');
 const imageKey=`${result?.job_id}:${index}:${view}`;
 useEffect(()=>{if(!result)return;let alive=true;const names=view==='depth'?['depth','mask']:view==='source'?['left','right']:['left-candidate','right-candidate'];setReadyKey('');void Promise.all(names.map(name=>new Promise<void>((resolve,reject)=>{const img=new Image();img.onload=()=>resolve();img.onerror=()=>reject(new Error('Sample image could not load'));img.src=baseUrl+'/api/preparation/image?'+new URLSearchParams({project_path:path,frame:String(result.frames[index].source_frame),view:name,revision:result.job_id});}))).then(()=>{if(alive)setReadyKey(imageKey);}).catch(e=>{if(alive)setError(String(e));});return()=>{alive=false;};},[imageKey,path,baseUrl]);
 const image=(name:string)=>baseUrl+'/api/preparation/image?'+new URLSearchParams({project_path:path,frame:String(frame!.source_frame),view:name,revision:result!.job_id});
 return <section className="sample-preparation" aria-label="Fresh sample preparation">
  <header><h2>Recording samples</h2><span>Fresh stereo replay → depth → pose candidates</span></header>
  <div className="sample-actions"><label>First source frame<input aria-label="First source frame" type="number" min="0" value={start} disabled={active||busy} onChange={e=>setStart(Number(e.target.value))}/></label><label>Frames<input aria-label="Sample count" type="number" min="1" max="60" value={count} disabled={active||busy} onChange={e=>setCount(Number(e.target.value))}/></label><button disabled={active||busy||project.issues.length>0} onClick={()=>void prepare()}>{busy?'Verifying source…':'Prepare fresh samples'}</button>{active&&<button onClick={()=>void request('cancel/'+job!.job_id,{}).then(setJob).catch(e=>setError(String(e)))}>Cancel preparation</button>}</div>
  <p className="sample-note">This recording uses an explicit yellow-object mask preset. The STL remains the geometry reference. Pose candidates and gate results require review.</p>
  {job&&<div role="status"><strong>{job.state} · {job.stage}</strong> · {job.completed}/{job.total}{job.accepted!==undefined?` · ${job.accepted} passed pilot gates`:''}{active&&<progress max={job.total} value={job.completed}/>}</div>}
  {(error||job?.error)&&<p role="alert">{error||job?.error}</p>}
  {!result&&<p>Prepare a bounded range to inspect synchronized camera images, replayed depth, masks and fitted silhouettes here. Progress and worker output appear in the log panel.</p>}
  {result&&frame&&<>
   <div className="sample-actions"><button onClick={()=>setPlaying(!playing)}>{playing?'Pause samples':'Play samples'}</button><input aria-label="Sample frame" type="range" min="0" max={result.frames.length-1} value={index} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><select aria-label="Sample view" value={view} onChange={e=>setView(e.target.value)}><option value="candidate">Pose candidate outlines</option><option value="source">Original rectified stereo</option><option value="depth">Depth and mask</option></select></div>
   <p>Source frame <strong>{frame.source_frame}</strong> · {index+1}/{result.frames.length} · {frame.status} · {result.accepted} / {result.frames.length} passed pilot gates · human review pending</p>
   {readyKey!==imageKey&&<p role="status">Loading paired images…</p>}<div className="sample-images" style={{visibility:readyKey===imageKey?'visible':'hidden'}}>{(view==='depth'?['depth','mask']:view==='source'?['left','right']:['left-candidate','right-candidate']).map(name=><figure key={name}><figcaption>{name}</figcaption><img src={image(name)} alt={`${name}, source frame ${frame.source_frame}`}/></figure>)}</div>
   <p className="sample-note">{frame.reason}{frame.left_iou!==undefined?` · left IoU ${frame.left_iou.toFixed(3)} · right IoU ${frame.right_iou?.toFixed(3)} · median depth residual ${frame.median_abs_depth_mm?.toFixed(2)} mm`:''}</p>
   <p className="sample-note">ZED image clock · timestamps retained as int64 nanoseconds in Parquet · depth in metres · right-mask agreement is pose-conditioned evidence. Playback here is an image sample preview, not an exported video.</p>
  </>}
 </section>;
}
