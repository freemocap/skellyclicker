import {useEffect,useRef,useState} from 'react';
import type {PipelineSnapshot} from '@freemocap/client';
import type {TrainingConfig} from './training-workflow';

interface Preview {expected_pose_manifest_sha256:string;expected_target_manifest_sha256:string;moment_count:number;image_count:number;label_count:number;source_frames:number[]}
export function useLabelRun(baseUrl:string,projectPath:string,config:TrainingConfig,snapshots:Record<string,PipelineSnapshot>) {
 const [preview,setPreview]=useState<Preview|null>(null),[runId,setRunId]=useState<string|null>(null),[error,setError]=useState(''),[pending,setPending]=useState(false);
 const body={project_path:projectPath,start_frame:Number(config.first),end_frame:Number(config.first)+Number(config.count)-1,step:Number(config.step),max_moments:config.limit===''?null:Number(config.limit),fit_filter:config.fit};
 const binding=JSON.stringify({mode:config.mode,...body});
 const previewSequence=useRef(0);
 const runKey='skellyclicker.label-run:'+projectPath;
 useEffect(()=>{const remembered=localStorage.getItem(runKey);if(!remembered)return;void fetch(baseUrl+'/api/label-tasks/'+remembered).then(r=>{if(r.ok)setRunId(remembered);else if(r.status===404)localStorage.removeItem(runKey);}).catch(()=>{});},[baseUrl,runKey]);
 useEffect(()=>{previewSequence.current++;setPreview(null);setError('');setPending(false);},[binding]);
 const snapshot=runId?snapshots[runId]:null;
 const running=pending||!!(runId&&(!snapshot||snapshot.status==='queued'||snapshot.status==='running'));
 async function post(path:string,data:unknown) {
  const response=await fetch(baseUrl+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));return result;
 }
 async function inspect(){const sequence=++previewSequence.current;setPending(true);setError('');try{const value=await post('/api/labels/preview',body);if(sequence===previewSequence.current)setPreview(value);}catch(e){if(sequence===previewSequence.current)setError(String(e));}finally{if(sequence===previewSequence.current)setPending(false);}}
 async function start(){if(!preview)return;setPending(true);setError('');try{const run=await post('/api/labels/runs',{...body,expected_pose_manifest_sha256:preview.expected_pose_manifest_sha256,expected_target_manifest_sha256:preview.expected_target_manifest_sha256});setRunId(run.run_id);localStorage.setItem(runKey,run.run_id);}catch(e){setError(String(e));}finally{setPending(false);}}
 async function cancel(){if(!runId)return;try{await post('/api/label-tasks/'+runId+'/cancel',{});}catch(e){setError(String(e));}}
 return {preview,snapshot,running,error,inspect,start,cancel};
}
