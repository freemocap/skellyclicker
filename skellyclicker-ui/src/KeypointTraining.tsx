import {useEffect, useMemo, useState} from 'react';
import {AnchoredInfo, ButtonSm} from '@freemocap/ui';
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

export function KeypointTraining({baseUrl, id, parent, labeling}:{
  baseUrl:string; id:string; parent:string; labeling:Labeling;
}) {
  const [rounds,setRounds] = useState<Round[]|null>(null);
  const [parentId,setParentId] = useState('');
  const [heldOut,setHeldOut] = useState<number[]|null>(null);
  const [epochs,setEpochs] = useState(10);
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

  useEffect(()=>{
    const abort = new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function refresh(){
      try {
        const values:Round[] = await json(url+'?'+query,{signal:abort.signal});
        if (abort.signal.aborted) return;
        setRounds(values); setLoadError('');
        if(values.some(round=>['queued','running','cancelling'].includes(round.status))) timer=setTimeout(refresh,1000);
      } catch(e) {if(!abort.signal.aborted)setLoadError(String(e));}
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
        await json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
          recording_id:id,recording_parent_directory:parent,training_frames:training,validation_frames:validation,
          parent_run_id:parentId||null,epochs,
        })});
      }
      setRevision(n=>n+1);
    }catch(e){setError(String(e));}
    finally {setPending(false);}
  }
  return <div className="keypoint-training">
    <header><h2>Keypoint training</h2><span>{id}</span></header>
    <div className="keypoint-training-grid">
    <section className="keypoint-section"><h3>Training settings</h3>
    <fieldset disabled={pending||!!active}>
      <div className="training-model-field"><span>Starting model <StartingModelHelp/></span><select aria-label="Starting model" value={parentId} onChange={e=>setParentId(e.target.value)}>
        <option value="">{newModelLabel}</option>
        {rounds?.filter(round=>round.status==='complete').map(round=><option key={round.id} value={round.id}>Continue run {round.id.slice(0,8)} · epoch {round.epochs}</option>)}
      </select></div>
      <label>Epochs<input type="number" min={1} max={10000} value={epochs} onChange={e=>setEpochs(Number(e.target.value))}/></label>
    </fieldset>
    <div className="keypoint-actions"><ButtonSm text="Start training" buttonType="primary accent" textColor="" disabled={pending||!!active||!rounds||!!loadError||!training.length||!validation.length||!Number.isInteger(epochs)||epochs<1||epochs>10000}
      onClick={()=>void submit()}/>
      {active&&<ButtonSm text="Cancel training" disabled={pending} onClick={()=>void submit(true)}/>}</div>
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
    {!!rounds?.length&&<section className="keypoint-section keypoint-history"><h3>Training runs</h3>
      {rounds.map(round=><p key={round.id}><code>{round.id.slice(0,8)}</code><strong data-status={round.status}>{round.status}</strong>
        <span>{round.epochs} {round.epochs===1?'epoch':'epochs'}</span>{round.stage&&<span>{round.stage}</span>}{round.error&&<span role="alert">{round.error}</span>}</p>)}
    </section>}
  </div>;
}
