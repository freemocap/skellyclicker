import {useEffect,useState} from 'react';

import {SidebarProcessingAction as ButtonSm,SettingSelectInput,AnchoredInfo,PipelinePanel,PipelineWindow,SettingRow,ValueSelector,MetricSeriesChart,SamplePreviewGrid,type PipelineGraph,type PipelineStagePresentation} from '@freemocap/ui';

import type {PipelineSnapshot} from '@freemocap/client';

import type {ProjectView} from './ProjectPanel';



type Config={python_path:string;epochs:number;batch_size:number;save_every:number;seed:number;max_seconds:number;validation_fraction:number;guard_seconds:number};

type SavedRun={run_id:string;status:string;counts:{training:number;validation:number;guard:number}|null;keypoint_count:number|null;epoch:number};

type Preview={image_count:number;moment_count:number;keypoint_count:number;counts:{training:number;validation:number;guard:number};expected_selection_sha256:string;expected_label_manifest_sha256:string};

const labels={freeze_inputs:'Freeze included images',prepare_trainer:'Prepare DeepLabCut',train_model:'Train and evaluate',publish_run:'Save run artifacts'};

export function TrainingDashboard({baseUrl,project,snapshots}:{baseUrl:string;project:ProjectView|null;snapshots:Record<string,PipelineSnapshot>}) {

 const [history,setHistory]=useState<SavedRun[]>([]);

 const [configuration,setConfiguration]=useState<{graph:PipelineGraph;defaults:Config;backend:string}|null>(null);

 const [config,setConfig]=useState<Config|null>(null),[preview,setPreview]=useState<Preview|null>(null);

 const [open,setOpen]=useState(false),[view,setView]=useState<'graph'|'list'>('graph'),[error,setError]=useState(''),[pending,setPending]=useState(false);

 const [now,setNow]=useState(Date.now());

 const [receivedAt,setReceivedAt]=useState(Date.now());

 const [runId,setRunId]=useState<string|null>(null),[recovered,setRecovered]=useState<PipelineSnapshot|null>(null);

 const snapshot=runId?(snapshots[runId]??recovered):null;

 useEffect(()=>{setReceivedAt(Date.now());},[snapshot?.sequence,runId]);

 useEffect(()=>{if(!snapshot||!['queued','running'].includes(snapshot.status))return;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[snapshot?.status]);

 const running=pending||!!snapshot&&['queued','running'].includes(snapshot.status);

 const key='skellyclicker.training-run:'+project?.manifest_path;

 const selectedRun=history.find(r=>r.run_id===runId);
 const displayedCounts=selectedRun?.counts??preview?.counts;
 const displayedKeypoints=selectedRun?.keypoint_count??preview?.keypoint_count;

 useEffect(()=>{if(!project)return;const abort=new AbortController();void fetch(baseUrl+'/api/training/runs?project_path='+encodeURIComponent(project.manifest_path),{signal:abort.signal}).then(async r=>{if(r.ok)setHistory(await r.json());}).catch(()=>{});return()=>abort.abort();},[baseUrl,project?.manifest_path,snapshot?.status]);

 async function selectRun(id:string){if(!project)return;try{const r=await fetch(baseUrl+'/api/training/runs/'+id+'?project_path='+encodeURIComponent(project.manifest_path));if(!r.ok)throw new Error('Saved run unavailable');setRecovered(await r.json());setRunId(id);localStorage.setItem(key,id);setError('');}catch(e){setError(String(e));}}



 useEffect(()=>{const abort=new AbortController();void fetch(baseUrl+'/api/training/configuration',{signal:abort.signal}).then(async r=>{if(!r.ok)throw new Error('Training configuration unavailable');const value=await r.json();setConfiguration(value);setConfig(value.defaults);}).catch(e=>{if(!abort.signal.aborted)setError(String(e));});return()=>abort.abort();},[baseUrl]);

 useEffect(()=>{setRunId(null);setRecovered(null);setPreview(null);const id=localStorage.getItem(key);if(!id)return;const abort=new AbortController();void fetch(baseUrl+'/api/training/runs/'+id+'?project_path='+encodeURIComponent(project!.manifest_path),{signal:abort.signal}).then(async r=>{if(r.ok){const value=await r.json();setRunId(id);setRecovered(value);}else if(r.status===404)localStorage.removeItem(key);}).catch(()=>{});return()=>abort.abort();},[key,baseUrl]);

 async function post(path:string,body:unknown){const response=await fetch(baseUrl+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));return result;}

 async function inspect(){if(!config||!project)return;setPending(true);setError('');try{setPreview(await post('/api/training/preview',{...config,project_path:project.manifest_path}));}catch(e){setPreview(null);setError(String(e));}finally{setPending(false);}}

 function change<K extends keyof Config>(k:K,v:Config[K]){setConfig(c=>c?{...c,[k]:v}:c);setPreview(null);}

 async function start(){if(!preview||!project||!config)return;setPending(true);setError('');try{const value=await post('/api/training/runs',{...config,project_path:project.manifest_path,expected_selection_sha256:preview.expected_selection_sha256,expected_label_manifest_sha256:preview.expected_label_manifest_sha256});setRunId(value.run_id);setRecovered(value.snapshot);localStorage.setItem(key,value.run_id);setOpen(false);}catch(e){setError(String(e));}finally{setPending(false);}}

 async function cancel(){if(!runId)return;try{await post('/api/label-tasks/'+runId+'/cancel',{});}catch(e){setError(String(e));}}

 const number=(label:string,k:Exclude<keyof Config,'python_path'>,min:number,max:number,unit='')=><SettingRow label={label} info={{title:label,text:"Saved with the run configuration."}} control={<ValueSelector label={label} value={config?.[k]??min} min={min} max={max} step={k==='validation_fraction'?.05:k==='guard_seconds'?.1:1} unit={unit} onChange={v=>change(k,v)}/>}/>;

 const presentations:Record<string,PipelineStagePresentation>={

  freeze_inputs:{label:labels.freeze_inputs,kind:'source',availability:'available',description:'Preserve included images, exact source identities, ordered keypoints, STL and calibration in an immutable dataset. Inclusion is approval.',reason:'Stereo moments stay together; a final time block is validation, with a timestamp-based guard interval.',configuration:<>{number('Validation fraction','validation_fraction',.05,.45)}{number('Temporal guard','guard_seconds',0,60,'s')}<p>{preview?`${preview.image_count} approved images · ${preview.counts.training} train · ${preview.counts.validation} validation · ${preview.counts.guard} guard`:'Preview to read the current included images.'}</p></>},

  prepare_trainer:{label:labels.prepare_trainer,kind:'computation',availability:'available',description:'Create an official DLC project and verify the saved train/validation filenames. Start from the pretrained backbone with a fresh object-specific head.',reason:'Full camera images; authored keypoint order; no old object checkpoint.',configuration:<><SettingRow label="Backend" info={{title:"Backend",text:"Official DLC training with a fresh object model."}} control={<span>DeepLabCut 3.0.2 · ResNet-50</span>}/><SettingRow label="Training Python" info={{title:"Training Python",text:"Isolated environment containing DeepLabCut 3.0.2 and CUDA PyTorch."}} control={<textarea rows={6} className="training-python-input" aria-label="Training Python" value={config?.python_path??''} onChange={e=>change('python_path',e.target.value)}/>}/>{number('Random seed','seed',0,2147483647)}</>},

  train_model:{label:labels.train_model,kind:'computation',availability:'available',description:'Run bounded GPU training with actual epoch losses, validation metrics, saved checkpoints and fixed sample predictions.',reason:'Cancellation stops the owned worker; saved inputs and checkpoints remain available.',configuration:<>{number('Epochs','epochs',1,10000)}{number('Batch size','batch_size',1,32)}{number('Evaluate / save every N epochs','save_every',1,1000)}{number('Maximum duration','max_seconds',30,86400,'s')}</>},

  publish_run:{label:labels.publish_run,kind:'publication',availability:'available',description:'Retain configurations, dataset hashes, full metric history, checkpoints and sample predictions with their actual epoch identity.',reason:'Loss and label-agreement errors are distinct. The small validation set measures this run, not generalization.'},

 };

 return <div className="training-dashboard"><header><div><h2>Training dashboard</h2><p>{project?.project.project_id??'Open a project to train'} · DeepLabCut</p></div><div className="training-actions">{!!history.length&&<SettingSelectInput label="Saved training run" value={runId??''} options={[{value:'',label:'Select saved run'},...history.map(r=>({value:r.run_id,label:`${r.run_id.slice(0,8)} · ${r.status} · epoch ${r.epoch}`}))]} onChange={id=>{if(id)void selectRun(id);}}/>}<ButtonSm text="Start training run" disabled={!project||!config||running} onClick={()=>{setOpen(true);void inspect();}}/>{snapshot&&<ButtonSm text="Run pipeline" onClick={()=>setOpen(true)}/>} {running&&<ButtonSm text="Cancel training" disabled={snapshot?.cancel_requested} onClick={()=>void cancel()}/>}</div></header>

 {error&&<p role="alert">{error}</p>}

 <div className="run-summary" role="status"><strong>{snapshot?.status??'Ready'}</strong>{snapshot&&<><span>{snapshot.operations.find(o=>o.status==='running')?.detail??'Run artifacts retained'}</span><span>{Math.round(snapshot.elapsed_seconds+(['queued','running'].includes(snapshot.status)?Math.max(0,now-receivedAt)/1000:0))} s</span><span>{snapshot.cancel_requested?'Cancellation requested':snapshot.previews.length?`Checkpoint epoch ${snapshot.previews[0].step}`:''}</span></>}{displayedCounts&&<span>{displayedCounts.training} train / {displayedCounts.validation} validation / {displayedCounts.guard} guard · {displayedKeypoints} keypoints</span>}</div>

 {snapshot?.error&&<p role="alert">{snapshot.error}</p>}

 <div className="metric-grid">{snapshot?.metrics.map(series=><MetricSeriesChart key={series.operation_id+series.id} series={series} height={150} color={series.id.includes("train_")?"var(--color-info)":"#c7a4ff"}/>)}</div>

 {!!snapshot?.previews.length&&<SamplePreviewGrid previews={snapshot.previews} resolveImageUrl={url=>new URL(url,baseUrl).href}/>}

 <AnchoredInfo title="Training dashboard" text="Included images are approved for training. Magenta circles show approved labels; cyan crosses show checkpoint predictions. Loss and validation pixel error are separate measurements. Guard images stay in the snapshot but are excluded from optimization and validation."/>

 {open&&configuration&&config&&<PipelineWindow title="Start training run" subtitle={project?.project.project_id} onClose={()=>setOpen(false)}><PipelinePanel graph={snapshot&&running?snapshot.graph:configuration.graph} nodePresentation={presentations} operations={snapshot?.operations??[]} locked={running} view={view} onViewChange={setView} notice={error?<p role="alert">{error}</p>:null} actions={<div className="training-actions"><ButtonSm text="Preview inputs" disabled={running} onClick={()=>void inspect()}/><ButtonSm text="Start training" disabled={running||!preview||!config.python_path} onClick={()=>void start()}/>{running&&<ButtonSm text="Cancel training" disabled={snapshot?.cancel_requested} onClick={()=>void cancel()}/>}<span>{preview?`${preview.image_count} images · ${preview.counts.training} train / ${preview.counts.validation} validation / ${preview.counts.guard} guard`:''}</span></div>}/></PipelineWindow>}

 </div>;

}
