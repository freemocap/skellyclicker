import {useEffect, useMemo, useState} from 'react';
import {AnchoredInfo, ButtonSm, MetricSeriesChart, PipelinePanel, RunActivity, SamplePreviewGrid,type PipelineStagePresentation} from '@freemocap/ui';
import type {PipelineSnapshot} from '@freemocap/client';
import {trainingState} from './training-state';
import type {CheckpointSource} from './RecordingReview';
import type {Labeling} from './labeling/useLabeling';
import {newModelLabel, StartingModelHelp} from './TrainingSettings';

type Round = {id:string; status:string; stage:string|null; error:string|null; epochs:number; validation_frames:number[]};
async function json(url:string, options?:RequestInit) {
  const response = await fetch(url, options);
  const body = await response.json();
  if(response.status===404 && body.detail==='Not Found' && url.includes('/api/keypoint-training/'))
    throw new Error('The running backend predates keypoint training. Close SkellyClicker and run poe dev again.');
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body));
  return body;
}

type ReportCheckpoint = (source:CheckpointSource|null)=>void;
const stages:Record<string,PipelineStagePresentation>={
  freeze_inputs:{label:'Freeze labeled images',kind:'source',availability:'available',description:'Decode the clicked camera frames and freeze their labels.',reason:'Keep the training and validation moments separate.'},
  prepare_trainer:{label:'Prepare DeepLabCut',kind:'computation',availability:'available',description:'Build the DLC dataset and verify the saved split.',reason:'Use the frozen images for this run.'},
  train_model:{label:'Train and evaluate',kind:'computation',availability:'available',description:'Optimize the model, save checkpoints and measure prediction error.',reason:'Use held-out frames for validation.'},
  publish_run:{label:'Save run artifacts',kind:'publication',availability:'available',description:'Verify and publish the trained checkpoint.',reason:'Retain this model for inspection and continuation.'},
};
function RoundFeedback({round, url, baseUrl,onCheckpoint}: {round:Round; url:string; baseUrl:string;onCheckpoint?:ReportCheckpoint}) {
  const [snapshot,setSnapshot] = useState<PipelineSnapshot|null>(null);
  const [error,setError] = useState('');
  const [receivedAt,setReceivedAt] = useState(Date.now);
  const [now,setNow] = useState(Date.now);
  const [view,setView]=useState<'graph'|'list'>('list');
  const active = ['queued','running','cancelling'].includes(round.status);
  const epoch=Math.max(0,...(snapshot?.previews.map(p=>p.step)??[]));
  useEffect(()=>{
    if(epoch) onCheckpoint?.({runId:round.id,epoch,artifact:url});
    return ()=>onCheckpoint?.(null);
  },[round.id,epoch,url,onCheckpoint]);
  useEffect(()=>{
    const abort = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const value:PipelineSnapshot = await json(url+'status.json',{signal:abort.signal,cache:'no-store'});
        if (abort.signal.aborted) return;
        setSnapshot(value); setError('');
      } catch(e) {if (!abort.signal.aborted) setError(String(e));}
      if (active && !abort.signal.aborted) timer=setTimeout(refresh,1000);
    }
    void refresh();
    return ()=>{abort.abort(); clearTimeout(timer);};
  },[url,active]);
  useEffect(()=>{setReceivedAt(Date.now());setNow(Date.now());},[snapshot?.sequence]);
  useEffect(()=>{
    if (!active) return;
    const timer=setInterval(()=>setNow(Date.now()),1000);
    return ()=>clearInterval(timer);
  },[active]);
  // The round list also detects runs interrupted by a backend restart.
  const state = trainingState(snapshot && !active ? {...snapshot,status:round.status as PipelineSnapshot['status']} : snapshot);
  const operation = snapshot?.operations.find(o=>o.status==='running');
  const preparation = operation?.operation_id==='prepare_trainer' && operation.unit==='steps' ? operation : null;
  const age = Math.max(0,(now-receivedAt)/1000);
  return <section className="keypoint-feedback" aria-label="Training results">
    <h3>Training results · {round.id.slice(0,8)}</h3>
    {snapshot && <RunActivity stage={state.stage} active={active} elapsedSeconds={snapshot.elapsed_seconds+(active?age:0)}
      updateAgeSeconds={active&&error?age:undefined} completed={preparation?.completed??state.epoch?.completed}
      total={preparation?.total??state.epoch?.total} unit={preparation?'Preparation step':'Epoch'}
      detail={active?operation?.detail:undefined}/>}
    {error && <p role="alert">Could not load run measurements. {error}</p>}
    {snapshot?.graph&&<section className="training-stage-panel" aria-label="Training stages" data-view={view}>
      <PipelinePanel graph={snapshot.graph} graphLayout="single-row" nodePresentation={stages} operations={snapshot.operations}
        locked={false} view={view} onViewChange={setView}/></section>}
    {snapshot?.metrics.length ? <div className="keypoint-metrics">{snapshot.metrics.map(series=>
      <MetricSeriesChart key={series.operation_id+series.id} series={series} height={200}/>)}</div> :
      <p role="status">{active?'Waiting for the first measured epoch.':snapshot?'No epoch measurements were recorded.':'Loading run measurements…'}</p>}
    {!!snapshot?.previews.length && <SamplePreviewGrid previews={snapshot.previews} resolveImageUrl={path=>baseUrl+path}/>}
  </section>;
}

export function KeypointTraining({baseUrl, id, parent, labeling,onCheckpoint}:{
  baseUrl:string; id:string; parent:string; labeling:Labeling;onCheckpoint?:ReportCheckpoint;
}) {
  const [rounds,setRounds] = useState<Round[]|null>(null);
  const [parentId,setParentId] = useState('');
  const [displayId,setDisplayId] = useState('');
  const [heldOut,setHeldOut] = useState<number[]|null>(null);
  const [epochs,setEpochs] = useState(10);
  const [saveEvery,setSaveEvery] = useState(1);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState('');
  const [loadError,setLoadError] = useState('');
  const [revision,setRevision] = useState(0);
  const url = baseUrl+'/api/keypoint-training/runs';
  const query = new URLSearchParams({recording_id:id, recording_parent_directory:parent}).toString();
  const frames = useMemo(()=>[...new Set(labeling.document?.observations.filter(o=>o.origin==='click').map(o=>o.source_frame))].sort((a,b)=>a-b),[labeling.document]);
  const previous = rounds?.find(round=>round.id===parentId);
  const validation = previous?.validation_frames ?? heldOut ?? frames.slice(-1);
  const training = frames.filter(frame=>!validation.includes(frame));
  const active = rounds?.find(round=>['queued','running','cancelling'].includes(round.status));
  const displayed = active ?? rounds?.find(round=>round.id===displayId) ?? rounds?.[0];

  useEffect(()=>{
    const abort = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh(){
      try {
        const values:Round[] = await json(url+'?'+query,{signal:abort.signal});
        if (abort.signal.aborted) return;
        setRounds(values); setLoadError('');
        if(values.some(round=>['queued','running','cancelling'].includes(round.status))) timer=setTimeout(refresh,1000);
      } catch(e) {if(!abort.signal.aborted){setLoadError(String(e));timer=setTimeout(refresh,3000);}}
    }
    void refresh();
    return ()=>{abort.abort(); clearTimeout(timer);};
  },[url,query,revision]);

  async function submit(cancel=false){
    setPending(true); setError('');
    try {
      if(cancel && active) await json(baseUrl+'/api/label-tasks/'+active.id+'/cancel',{method:'POST'});
      else {
        await labeling.waitForSave();
        const started = await json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          recording_id:id,recording_parent_directory:parent,training_frames:training,validation_frames:validation,
          parent_run_id:parentId||null,epochs,save_every:saveEvery,
        })});
        setDisplayId(started.run_id);
      }
      setRevision(n=>n+1);
    }catch(e){setError(String(e));}
    finally {setPending(false);}
  }
  return <div className="keypoint-training" data-training-active={!!active}>
    <header><h2>Keypoint training</h2><span>{id}</span>
      {active&&<ButtonSm text="Cancel training" disabled={pending} onClick={()=>void submit(true)}/>}</header>
    <div className="keypoint-training-grid">
    <section className="keypoint-section"><h3>Training settings</h3>
    <fieldset disabled={pending||!!active}>
      <div className="training-model-field"><span>Starting model <StartingModelHelp/></span><select aria-label="Starting model" value={parentId} onChange={e=>setParentId(e.target.value)}>
        <option value="">{newModelLabel}</option>
        {rounds?.filter(round=>round.status==='complete').map(round=><option key={round.id} value={round.id}>Continue run {round.id.slice(0,8)} · epoch {round.epochs}</option>)}
      </select></div>
      <label>Epochs<input type="number" min={1} max={10000} value={epochs} onChange={e=>setEpochs(Number(e.target.value))}/></label>
      <label>Evaluate and save every N epochs<input type="number" min={1} max={10000} value={saveEvery} onChange={e=>setSaveEvery(Number(e.target.value))}/></label>
    </fieldset>
    <div className="keypoint-actions"><ButtonSm text="Start training" buttonType="primary accent" textColor="" disabled={pending||!!active||!rounds||!!loadError||!training.length||!validation.length||![epochs,saveEvery].every(v=>Number.isInteger(v)&&v>=1&&v<=10000)}
      onClick={()=>void submit()}/>
    </div>
    {loadError&&<div role="alert">{loadError} <ButtonSm text="Retry" onClick={()=>setRevision(n=>n+1)}/></div>}
    {error&&<p role="alert">{error}</p>}
    </section>
    <section className="keypoint-section"><h3>Labeled frames</h3>
      <div className="keypoint-counts">{training.length} training · {validation.length} validation</div>
      {labeling.document?.tracked_point_names.length ? <p className="keypoint-names">{labeling.document.tracked_point_names.join(' · ')}</p>:null}
      {frames.length<2 && <p role="status">Click keypoints on at least two frames to train.</p>}
      {frames.length>0 && <fieldset disabled={pending||!!active}><legend>Validation frames <AnchoredInfo title="Validation frames" text="Hold out whole synchronized moments. All other clicked moments are used for training. Continuing a checkpoint preserves its validation set."/></legend>
      <div className="keypoint-frames">{frames.map(frame=><label key={frame}><input type="checkbox" disabled={!!previous}
        checked={validation.includes(frame)} onChange={e=>setHeldOut(e.target.checked?[...validation,frame]:validation.filter(v=>v!==frame))}/>{frame}</label>)}</div>
    </fieldset>}</section></div>
    {displayed && <RoundFeedback key={displayed.id} round={displayed} baseUrl={baseUrl}
      onCheckpoint={onCheckpoint} url={url+'/'+displayed.id+'/artifact?'+query+'&path='}/>}
    {!!rounds?.length&&<section className="keypoint-section keypoint-history"><h3>Training runs</h3>
      {rounds.map(round=><p key={round.id}><ButtonSm text={round.id.slice(0,8)} disabled={!!active||displayed?.id===round.id} onClick={()=>setDisplayId(round.id)}/><strong data-status={round.status}>{round.status}</strong>
        <span>{round.epochs} {round.epochs===1?'epoch':'epochs'}</span>{round.stage&&<span>{round.stage}</span>}{round.error&&<span role="alert">{round.error}</span>}</p>)}
    </section>}
  </div>;
}
