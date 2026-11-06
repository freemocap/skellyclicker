import {useEffect,useRef,useState} from 'react';
import type {PipelineSnapshot} from '@freemocap/client';
import type {PreparedSummary,TrainingConfig} from './training-workflow';

interface Preview {expected_pose_manifest_sha256:string;expected_target_manifest_sha256:string;moment_count:number;image_count:number;label_count:number;source_frames:number[]}
interface Attempt {phase:'preparation'|'labels';id:string;config:TrainingConfig;started:number}
interface Preparation {job_id:string;state:string;stage:string;completed:number;total:number|null;error?:string;updated_at?:string}
/** The app coordinates preparation and labeling; both existing backend runners retain ownership of execution. */
export function useLabelRun(baseUrl:string,projectPath:string,config:TrainingConfig,_snapshots:Record<string,PipelineSnapshot>) {
 const [preview,setPreview]=useState<Preview|null>(null),[snapshot,setSnapshot]=useState<PipelineSnapshot|null>(null);
 const [preparation,setPreparation]=useState<Preparation|null>(null),[error,setError]=useState(''),[running,setRunning]=useState(false),[phase,setPhase]=useState('');
 const [started,setStarted]=useState(0),[now,setNow]=useState(Date.now());
 const lock=useRef(false),cancelled=useRef(false),current=useRef<Attempt|null>(null),alive=useRef(true);
 const runKey='skellyclicker.image-set-run.v2:'+projectPath;
 async function request(path:string,data?:unknown) {
  const response=await fetch(baseUrl+path,data===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail??result));return result;
 }
 function remember(attempt:Attempt){current.current=attempt;localStorage.setItem(runKey,JSON.stringify(attempt));}
 async function execute(draft:TrainingConfig,resume?:Attempt) {
  if(lock.current)return;lock.current=true;cancelled.current=false;setRunning(true);setError('');setStarted(resume?.started??Date.now());
  const began=resume?.started??Date.now();if(resume)current.current=resume;
  try {
   let attempt=resume;
   if(!attempt){
    setSnapshot(null);setPreview(null);setPreparation(null);
    if(draft.mode==='fresh'){
     setPhase('Starting full preparation…');
     const job:Preparation=await request('/api/preparation/start',{project_path:projectPath,start_frame:draft.scope==='all'?0:Number(draft.first),frame_count:draft.scope==='all'?null:Number(draft.count)});
     attempt={phase:'preparation',id:job.job_id,config:draft,started:began};remember(attempt);setPreparation(job);if(cancelled.current)await request('/api/preparation/cancel/'+job.job_id,{});
    }
   }
   if(attempt?.phase==='preparation'){
    while(alive.current){
     const job:Preparation=await request('/api/preparation/status/'+attempt.id);setPreparation(job);setPhase(job.stage);
     if(job.state==='failed'||job.state==='cancelled'){localStorage.removeItem(runKey);current.current=null;throw new Error(job.error??`Preparation ${job.state}.`);}
     if(job.state==='complete')break;
     await new Promise(resolve=>setTimeout(resolve,1000));
    }
   }
   if(!alive.current)return;
   if(cancelled.current)throw new Error('Generation cancelled. Completed preparation remains available.');
   if(attempt?.phase!=='labels'){
    setPhase('Checking inputs…');
    const summary:PreparedSummary=await request('/api/preparation/result?project_path='+encodeURIComponent(projectPath));
    if(!summary)throw new Error('Preparation did not produce any images. Retry generation.');
    const body={project_path:projectPath,start_frame:draft.scope==='all'?0:Number(draft.first),end_frame:draft.scope==='all'?summary.calibration.source_frame_count-1:Number(draft.first)+Number(draft.count)-1,step:draft.scope==='all'?1:Number(draft.step),max_moments:draft.scope==='all'||draft.limit===''?null:Number(draft.limit),fit_filter:draft.scope==='all'?'all':draft.fit};
    const checked:Preview=await request('/api/labels/preview',body);setPreview(checked);
    if(!alive.current)return;
    if(cancelled.current)throw new Error('Generation cancelled.');
    setPhase('Starting label generation…');
    const run=await request('/api/labels/runs',{...body,expected_pose_manifest_sha256:checked.expected_pose_manifest_sha256,expected_target_manifest_sha256:checked.expected_target_manifest_sha256});
    attempt={phase:'labels',id:run.run_id,config:draft,started:began};remember(attempt);if(cancelled.current)await request('/api/label-tasks/'+run.run_id+'/cancel',{});
   }
   while(alive.current){
    const value:PipelineSnapshot=await request('/api/label-tasks/'+attempt.id);setSnapshot(value);
    setPhase(value.operations.find(op=>op.status==='running')?.detail||'Generating labeled images…');
    if(value.status==='complete'){setPhase('Images ready');localStorage.removeItem(runKey);current.current=null;break;}
    if(value.status==='failed'||value.status==='cancelled'){localStorage.removeItem(runKey);current.current=null;throw new Error(value.error??`Generation ${value.status}.`);}
    await new Promise(resolve=>setTimeout(resolve,1000));
   }
  }catch(e){if(alive.current){setError(String(e));setPhase('Generation stopped');}}
  finally{lock.current=false;if(alive.current)setRunning(false);}
 }
 useEffect(()=>{
  alive.current=true;
  try{const saved=JSON.parse(localStorage.getItem(runKey)??'null') as Attempt|null;if(saved?.id&&saved.config)void execute(saved.config,saved);}catch(e){setError('Could not restore the last generation: '+String(e));}
  return()=>{alive.current=false;};
 },[baseUrl,projectPath]);
 useEffect(()=>{if(!running)return;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[running]);
 async function start(){const previous=current.current;await execute(previous?.config??config,previous??undefined);}
 async function cancel(){cancelled.current=true;setPhase('Cancelling…');const attempt=current.current;if(!attempt)return;try{await request(attempt.phase==='preparation'?'/api/preparation/cancel/'+attempt.id:'/api/label-tasks/'+attempt.id+'/cancel',{});}catch(e){setError(String(e));}}
 const operation=snapshot?.operations.find(op=>op.status==='running');
 return {preview,snapshot,preparation,running,error,phase,start,cancel,elapsedSeconds:started?Math.max(0,(now-started)/1000):0,operation};
}
