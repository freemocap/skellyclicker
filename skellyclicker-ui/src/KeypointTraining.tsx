import {useEffect, useMemo, useState} from 'react';
import {createPortal} from 'react-dom';
import {AnchoredInfo, MetricSeriesChart, PipelinePanel, PipelineWindow, ResizableHandle, ResizablePanel, ResizablePanelGroup, RunActivity, SamplePreviewGrid, SettingRow, SettingSelectInput, ValueSelector, WorkspaceToolbar, type PipelineStagePresentation} from '@freemocap/ui';
import type {PipelineSnapshot} from '@freemocap/client';
import {trainingState} from './training-state';
import {TrainingActions} from './TrainingActions';
import type {CheckpointSource} from './RecordingReview';
import type {Labeling} from './labeling/useLabeling';
import {newModelLabel, StartingModelHelp} from './TrainingSettings';

type Round = {id:string; status:string; stage:string|null; error:string|null; epochs:number; validation_frames:number[]};
type ReportCheckpoint = (source:CheckpointSource|null)=>void;
const ACTIVE_STATUSES = ['queued','running','cancelling'];

async function json(url:string, options?:RequestInit) {
  const response = await fetch(url, options);
  const body = await response.json();
  if(response.status===404 && body.detail==='Not Found' && url.includes('/api/keypoint-training/'))
    throw new Error('The running backend predates keypoint training. Close SkellyClicker and run poe dev again.');
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body));
  return body;
}

const stages:Record<string,PipelineStagePresentation>={
  freeze_inputs:{label:'Freeze labeled images',kind:'source',availability:'available',description:'Decode the clicked camera frames and freeze their labels.',reason:'Keep the training and validation moments separate.'},
  prepare_trainer:{label:'Prepare DeepLabCut',kind:'computation',availability:'available',description:'Build the DLC dataset and verify the saved split.',reason:'Use the frozen images for this run.'},
  train_model:{label:'Train and evaluate',kind:'computation',availability:'available',description:'Optimize the model, save checkpoints and measure prediction error.',reason:'Use held-out frames for validation.'},
  publish_run:{label:'Save run artifacts',kind:'publication',availability:'available',description:'Verify and publish the trained checkpoint.',reason:'Retain this model for inspection and continuation.'},
};

/** Polls the displayed run's status file while it is active and reports its latest evaluated checkpoint. */
function useRoundSnapshot(round:Round|undefined, artifactUrl:string|null, onCheckpoint:ReportCheckpoint|undefined) {
  const [snapshot,setSnapshot] = useState<PipelineSnapshot|null>(null);
  const [error,setError] = useState('');
  const [receivedAt,setReceivedAt] = useState(Date.now);
  const [now,setNow] = useState(Date.now);
  const active = !!round && ACTIVE_STATUSES.includes(round.status);
  const epoch = Math.max(0,...(snapshot?.previews.map(p=>p.step)??[]));
  useEffect(()=>{
    setSnapshot(null); setError('');
    if (!artifactUrl) return;
    const abort = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const value:PipelineSnapshot = await json(artifactUrl+'status.json',{signal:abort.signal,cache:'no-store'});
        if (abort.signal.aborted) return;
        setSnapshot(value); setError('');
      } catch(e) {if (!abort.signal.aborted) setError(String(e));}
      if (active && !abort.signal.aborted) timer=setTimeout(refresh,1000);
    }
    void refresh();
    return ()=>{abort.abort(); clearTimeout(timer);};
  },[artifactUrl,active]);
  useEffect(()=>{
    if(round && artifactUrl && epoch) onCheckpoint?.({runId:round.id,epoch,artifact:artifactUrl});
    return ()=>onCheckpoint?.(null);
  },[round?.id,epoch,artifactUrl,onCheckpoint]);
  useEffect(()=>{setReceivedAt(Date.now());setNow(Date.now());},[snapshot?.sequence]);
  useEffect(()=>{
    if (!active) return;
    const timer=setInterval(()=>setNow(Date.now()),1000);
    return ()=>clearInterval(timer);
  },[active]);
  // The round list also detects runs interrupted by a backend restart.
  const state = trainingState(snapshot && !active ? {...snapshot,status:round!.status as PipelineSnapshot['status']} : snapshot);
  const updateAge = Math.max(0,(now-receivedAt)/1000);
  return {snapshot,error,active,state,updateAge};
}

export function KeypointTraining({baseUrl, id, parent, labeling, onCheckpoint, toolbarTarget}:{
  baseUrl:string; id:string; parent:string; labeling:Labeling; onCheckpoint?:ReportCheckpoint; toolbarTarget:HTMLDivElement|null;
}) {
  const [rounds,setRounds] = useState<Round[]|null>(null);
  const [parentId,setParentId] = useState('');
  const [displayId,setDisplayId] = useState('');
  const [heldOut,setHeldOut] = useState<number[]|null>(null);
  const [epochs,setEpochs] = useState(10);
  const [saveEvery,setSaveEvery] = useState(1);
  const [pending,setPending] = useState<'starting'|'cancelling'|null>(null);
  const [configuring,setConfiguring] = useState(false);
  const [view,setView] = useState<'graph'|'list'>('list');
  const [error,setError] = useState('');
  const [loadError,setLoadError] = useState('');
  const [revision,setRevision] = useState(0);
  const url = baseUrl+'/api/keypoint-training/runs';
  const query = new URLSearchParams({recording_id:id, recording_parent_directory:parent}).toString();
  const frames = useMemo(()=>[...new Set(labeling.document?.observations.filter(o=>o.origin==='click').map(o=>o.source_frame))].sort((a,b)=>a-b),[labeling.document]);
  const previous = rounds?.find(round=>round.id===parentId);
  const validation = previous?.validation_frames ?? heldOut ?? frames.slice(-1);
  const training = frames.filter(frame=>!validation.includes(frame));
  const activeRound = rounds?.find(round=>ACTIVE_STATUSES.includes(round.status));
  const displayed = activeRound ?? rounds?.find(round=>round.id===displayId) ?? rounds?.[0];
  const artifactUrl = displayed ? url+'/'+displayed.id+'/artifact?'+query+'&path=' : null;
  const run = useRoundSnapshot(displayed, artifactUrl, onCheckpoint);

  useEffect(()=>{
    const abort = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh(){
      try {
        const values:Round[] = await json(url+'?'+query,{signal:abort.signal});
        if (abort.signal.aborted) return;
        setRounds(values); setLoadError('');
        if(values.some(round=>ACTIVE_STATUSES.includes(round.status))) timer=setTimeout(refresh,1000);
      } catch(e) {if(!abort.signal.aborted){setLoadError(String(e));timer=setTimeout(refresh,3000);}}
    }
    void refresh();
    return ()=>{abort.abort(); clearTimeout(timer);};
  },[url,query,revision]);

  async function start(){
    setPending('starting'); setError('');
    try {
      await labeling.waitForSave();
      const started = await json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        recording_id:id,recording_parent_directory:parent,training_frames:training,validation_frames:validation,
        parent_run_id:parentId||null,epochs,save_every:saveEvery,
      })});
      setDisplayId(started.run_id);
      setRevision(n=>n+1);
    }catch(e){setError(String(e));}
    finally {setPending(null);}
  }
  async function cancel(){
    if(!activeRound) return;
    setPending('cancelling'); setError('');
    try {await json(baseUrl+'/api/label-tasks/'+activeRound.id+'/cancel',{method:'POST'}); setRevision(n=>n+1);}
    catch(e){setError(String(e));}
    finally {setPending(null);}
  }

  const settingsValid = [epochs,saveEvery].every(v=>Number.isInteger(v)&&v>=1&&v<=10000);
  const blocked = loadError || (!rounds ? 'Loading training runs…' : frames.length<2 ? 'Click keypoints on at least two frames to train.' : !training.length ? 'Keep at least one labeled frame for training.' : !validation.length ? 'Hold out at least one labeled frame for validation.' : !settingsValid ? 'Epochs and evaluation interval must be whole numbers from 1 to 10000.' : '');
  const actions = <TrainingActions canConfigure={!!rounds} canStart={!blocked&&!activeRound&&!pending} canCancel={!!activeRound&&!pending}
    starting={pending==='starting'} cancelling={pending==='cancelling'||activeRound?.status==='cancelling'}
    onConfigure={()=>setConfiguring(true)} onStart={()=>void start()} onCancel={()=>void cancel()}/>;
  const startingModel = <div className="training-starting-model training-model-field"><span>Starting model <StartingModelHelp/></span>
    <select aria-label="Starting model" disabled={!!activeRound||!!pending} value={parentId} onChange={e=>setParentId(e.target.value)}>
      <option value="">{newModelLabel}</option>
      {rounds?.filter(round=>round.status==='complete').map(round=><option key={round.id} value={round.id}>Continue run {round.id.slice(0,8)} · epoch {round.epochs}</option>)}
    </select></div>;
  const operation = run.snapshot?.operations.find(o=>o.status==='running');
  const preparation = operation?.operation_id==='prepare_trainer' && operation.unit==='steps' ? operation : null;
  const status = <RunActivity className="run-summary" stage={pending==='starting'?'Starting':displayed?run.state.stage:'Ready'} active={run.active}
    elapsedSeconds={(run.snapshot?.elapsed_seconds??0)+(run.active?run.updateAge:0)} updateAgeSeconds={run.active?run.updateAge:undefined}
    completed={preparation?.completed??run.state.epoch?.completed} total={preparation?.total??run.state.epoch?.total} unit={preparation?'Preparation step':'Epoch'}
    detail={run.active?operation?.detail:displayed?`Run ${displayed.id.slice(0,8)} · ${displayed.status}`:undefined}/>;
  const notice = error||displayed?.error||blocked;
  const commands = <><WorkspaceToolbar label="Next training run" details={<><span>{parentId?`Continue ${parentId.slice(0,8)}`:'New keypoint model'}</span><span>{epochs} epochs · evaluate every {saveEvery}</span><AnchoredInfo title="Stopping training" text="Stopping keeps completed checkpoints, curves and images."/></>}>
      <div className="training-input-count"><strong>{training.length} training · {validation.length} validation frames</strong>
        <AnchoredInfo title="Labeled frames" text="Every clicked moment trains the model except the held-out validation frames. Choose validation frames in Configure training."/></div>
      {startingModel}
      <div className="training-command-bar">{actions}</div>
    </WorkspaceToolbar>
    {status}
    {notice&&<div className="training-command-notice" role={error||displayed?.error?'alert':'status'}>{notice}</div>}</>;

  const validationChoices = <fieldset className="keypoint-frames" disabled={!!activeRound||!!pending||!!previous}>
    <legend>Validation frames <AnchoredInfo title="Validation frames" text="Hold out whole synchronized moments. All other clicked moments are used for training. Continuing a checkpoint preserves its validation set."/></legend>
    {frames.length?frames.map(frame=><label key={frame}><input type="checkbox" checked={validation.includes(frame)}
      onChange={e=>setHeldOut(e.target.checked?[...validation,frame]:validation.filter(v=>v!==frame))}/>{frame}</label>):<p role="status">No labeled frames yet.</p>}
  </fieldset>;

  return <div className="training-dashboard">
    {toolbarTarget?createPortal(commands,toolbarTarget):commands}
    <header className="training-results-heading">
      <div><h2>Training results</h2><p>{id} · {displayed?`run ${displayed.id.slice(0,8)} · ${displayed.status}`:'No run yet'}</p></div>
      <div className="training-run-options">{!!rounds?.length&&<SettingSelectInput label="Displayed run" value={displayed?.id??''} disabled={!!activeRound}
        options={rounds.map(round=>({value:round.id,label:`${round.id.slice(0,8)} · ${round.status} · ${round.epochs} ${round.epochs===1?'epoch':'epochs'}`}))}
        onChange={value=>setDisplayId(value)}/>}</div>
    </header>
    <ResizablePanelGroup direction="horizontal" autoSaveId="skellyclicker-keypoint-training-columns" className="training-columns">
      <ResizablePanel defaultSize={48} minSize={25}><div className="training-results-body">
        {run.error&&<p role="alert">Could not load run measurements. {run.error}</p>}
        {run.snapshot?.metrics.length
          ? <div className="metric-grid">{run.snapshot.metrics.map(series=><MetricSeriesChart key={series.operation_id+series.id} series={series} height={200} color={series.id.includes('train_')?'var(--color-info)':'#c7a4ff'}/>)}</div>
          : <p role="status">{!displayed?'No measurements':run.active?'Awaiting measurements…':run.snapshot?'No epoch measurements were recorded.':'Loading run measurements…'}</p>}
      </div></ResizablePanel>
      <ResizableHandle aria-label="Resize training results and checkpoint images"/>
      <ResizablePanel defaultSize={52} minSize={25}><section className="checkpoint-browser" aria-label="Checkpoint images">
        <header><h2>Checkpoint images</h2><AnchoredInfo title="Checkpoint images" text="Numbered filled circles are your clicked labels. Hollow diamonds in the same color are this checkpoint's predictions, joined to their label by a line whose length is the error."/></header>
        {run.snapshot?.previews.length
          ? <SamplePreviewGrid previews={run.snapshot.previews} resolveImageUrl={path=>baseUrl+path}/>
          : <p role="status">{!displayed?'Train a model to see its predictions.':run.active?'Awaiting the first saved evaluation epoch…':'No saved checkpoint images for this run.'}</p>}
      </section></ResizablePanel>
    </ResizablePanelGroup>
    {configuring&&createPortal(<PipelineWindow title="Configure training" subtitle={id} onClose={()=>setConfiguring(false)}>
      <div className="training-configuration">
        <div className="training-command-bar">{actions}</div>
        {status}
        <section className="keypoint-configuration" aria-label="Training settings">
          <SettingRow label="Epochs" info={{title:'Epochs',text:'Saved with the run configuration.'}} control={<ValueSelector label="Epochs" value={epochs} min={1} max={10000} step={1} onChange={setEpochs}/>}/>
          <SettingRow label="Evaluate / save every N epochs" info={{title:'Evaluation interval',text:'Each evaluation saves a checkpoint, measures validation error and renders checkpoint images.'}} control={<ValueSelector label="Evaluate / save every N epochs" value={saveEvery} min={1} max={10000} step={1} onChange={setSaveEvery}/>}/>
          {validationChoices}
        </section>
        {run.snapshot?.graph&&<PipelinePanel graph={run.snapshot.graph} graphLayout="single-row" nodePresentation={stages} operations={run.snapshot.operations} locked={run.active} view={view} onViewChange={setView}/>}
      </div>
    </PipelineWindow>,document.body)}
  </div>;
}
