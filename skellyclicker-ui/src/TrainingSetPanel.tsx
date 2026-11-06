import {useEffect,useMemo,useState,type ReactNode} from 'react';
import {ButtonSm,PipelinePanel,PipelineWindow,SettingFilePath,SettingRow,SettingSelectInput,SettingToggleSwitch,ValueSelector,AnchoredInfo,SettingsSummaryChip,type PipelineStagePresentation} from '@freemocap/ui';
import type {ProjectView} from './ProjectPanel';
import {trainingGraph,defaultConfig,validateConfig,candidateFrames,readConfig,type PreparedSummary,type TrainingConfig} from './training-workflow';
import './training-set.css';
import type {PipelineSnapshot} from '@freemocap/client';
import {useLabelRun} from './useLabelRun';
import {useStlSelection} from './useStlSelection';

/** Core-derived SDK rows and composition; this app supplies only labeling semantics and state. */
export function TrainingSetPanel({baseUrl,project,snapshots,onClose}:{baseUrl:string;project:ProjectView;snapshots:Record<string,PipelineSnapshot>;onClose:()=>void}) {
  const [showRun,setShowRun]=useState(true);
  const [view,setView]=useState<'graph'|'list'>('graph');
  const [summary,setSummary]=useState<PreparedSummary|null>(null),[loaded,setLoaded]=useState(false),[error,setError]=useState('');
  const [config,setConfig]=useState<TrainingConfig>(defaultConfig(null)),[saveError,setSaveError]=useState('');
  const binding=JSON.stringify([project.project.uuid,project.project.sample_result,project.project.playback_result,project.recordings.map(r=>[r.recording_id,r.source.sha256]),project.targets.map(t=>[t.object_id,t.geometry?.sha256,t.geometry?.path,t.authored_units,t.authored_geometry?.sha256])]);
  const stl=useStlSelection(baseUrl,project,binding);
  const storageKey='skellyclicker.training-config.v1:'+project.project.uuid;
  useEffect(()=>{
    const abort=new AbortController();setLoaded(false);setError('');
    void fetch(baseUrl+'/api/preparation/result?project_path='+encodeURIComponent(project.manifest_path),{signal:abort.signal}).then(async response=>{
      if(!response.ok)throw new Error('Could not read prepared result (HTTP '+response.status+').');
      const value=await response.json() as PreparedSummary|null;
      if(value&&(!Array.isArray(value.frames)||!value.calibration||!Number.isSafeInteger(value.calibration.source_frame_count)))throw new Error('Prepared result has an unsupported summary.');
      if(abort.signal.aborted)return;
      setSummary(value);let draft=defaultConfig(value);
      try {const stored=JSON.parse(localStorage.getItem(storageKey)??'null');if(stored?.binding===binding)draft=readConfig(stored.config)??draft;}catch {setSaveError('Saved configuration could not be read. Using project defaults.');}
      setConfig(draft);setLoaded(true);
    }).catch(e=>{if(!abort.signal.aborted){setError(String(e));setLoaded(true);}});
    return()=>abort.abort();
  },[baseUrl,project.manifest_path,binding,storageKey]);
  function change<K extends keyof TrainingConfig>(key:K,value:TrainingConfig[K]) {
    const next={...config,[key]:value};setConfig(next);
    try {localStorage.setItem(storageKey,JSON.stringify({version:1,binding,config:next}));setSaveError('');}catch {setSaveError('Configuration is not saved: browser storage is unavailable.');}
  }
  const run=useLabelRun(baseUrl,project.manifest_path,config,snapshots);
  const problems=validateConfig(config,summary);
  const candidates=useMemo(()=>candidateFrames(config,summary),[config,summary]);
  const sourceValid=project.issues.length===0&&project.recordings.length===1&&project.targets.length===1;
  const reusable=sourceValid&&stl.compatible&&config.mode==='reuse'&&!!summary&&!problems.length&&!error;
  const record=project.recordings[0],target=project.targets[0];
  const range=summary?.frames.length?`${summary.frames[0].source_frame}–${summary.frames.at(-1)!.source_frame}`:'—';
  const row=(label:string,text:ReactNode,control:ReactNode,promoted=false)=><SettingRow label={label} info={{title:label,text}} control={control} promoted={promoted}/>;
  const value=(text:ReactNode)=><span className="training-field-value">{text}</span>;
  const numeric=(label:string,key:'first'|'count'|'step'|'limit',min:number,max:number)=><ValueSelector label={label} value={Number(config[key])||min} min={min} max={max} onChange={v=>change(key,String(v))}/>;
  const fixedNumber=(label:string,n:number,unit:string)=><ValueSelector label={label} value={n} unit={unit} min={0} max={10000} disabled/>;
  const nodePresentation:Record<string,PipelineStagePresentation>={
    source_inputs:{label:'Source inputs',kind:'source',availability:sourceValid?'available':'unavailable',reason:sourceValid?'Linked inputs are available. Execution must revalidate source and target hashes.':'Open a valid project with one recording and one target.',description:'The linked recording, calibration and arbitrary STL define this workflow. Existing artifacts must match their source identities.',
      summary:<SettingsSummaryChip>{target?.object_id}</SettingsSummaryChip>,
      configuration:<>
        {row('Recording',<>Linked original; source SHA {record?.source.sha256??'unavailable'}.</>,value(record?.recording_id??'—'))}
        {row('STL target',<>Source STL SHA {target?.geometry?.sha256??'unavailable'}. Automatic initialization must work for arbitrary STL geometry.</>,<SettingFilePath label="STL target" path={stl.path} onBrowse={()=>void stl.browse()} disabled={stl.busy}/>)}
        {row('STL units','Declared units of this STL draft. Changing units invalidates reuse of existing poses and target points.',<SettingSelectInput label="STL units" value={stl.units} options={[{value:'mm',label:'Millimetres'},{value:'m',label:'Metres'}]} onChange={stl.changeUnits} disabled={stl.busy}/>)}
        {row('Source frames','Full recording frame count. Preparing a range does not truncate or replace the original recording.',value(summary?.calibration.source_frame_count??'—'))}
      </>},
    extract_images:{label:'Extract synchronized images',kind:'computation',availability:reusable?'reusable':sourceValid?'available':'unavailable',reason:reusable?'Existing images cover the selected range; input hashes must be verified before reuse.':'Fresh extraction exists in the separate preparation adapter. This panel does not start it.',description:'Extract paired native-resolution images, exact source timestamps and rectified calibration from the linked recording.',
      summary:<SettingsSummaryChip>{range}</SettingsSummaryChip>,
      configuration:<>
        {row('Input strategy','Reuse selects the current prepared result. Fresh preparation records intent only; changing this setting never starts processing.',<SettingSelectInput label="Input strategy" value={config.mode} options={[{value:'reuse',label:'Reuse prepared'},{value:'fresh',label:'Fresh preparation'}]} onChange={v=>change('mode',v)}/>,true)}
        {row('First source frame','Zero-based source frame, not the clip index. Reuse requires every frame in the range.',numeric('First source frame','first',0,Math.max(0,(summary?.calibration.source_frame_count??1000000)-1)))}
        {row('Frame count','The current preparation adapter supports 1–900 consecutive source frames.',numeric('Frame count','count',1,900))}
        {row('Image size','Native rectified image resolution. No resizing is introduced by this workflow.',value(summary?`${summary.calibration.image_width} × ${summary.calibration.image_height}`:'—'))}
      </>},
    stereo_3d:{label:'Reconstruct stereo 3D',kind:'computation',availability:reusable?'reusable':'unavailable',reason:reusable?'Existing depth/cloud artifacts can be reused after provenance validation.':'Depth is currently coupled to ZED replay; an independent stage runner is not implemented.',description:'Estimate stereo depth and project finite samples into colored 3D points. Optical coordinates use metres; display world coordinates use millimetres.',
      summary:<SettingsSummaryChip>ZED NEURAL</SettingsSummaryChip>,
      configuration:<>
        {row('Depth method','Current fixed adapter: ZED NEURAL replay. Stereo reconstruction is not an editable model choice yet.',<SettingSelectInput label="Depth method" value="neural" options={[{value:'neural',label:'ZED NEURAL'}]} onChange={()=>{}} disabled/>,true)}
        {row('Cloud pixel stride','Current cloud projection samples every fourth image pixel in each dimension.',fixedNumber('Cloud pixel stride',4,'px'))}
        {row('Near depth','Fixed lower bound for the current cloud artifact; not the fitting depth gate.',fixedNumber('Near depth',.17,'m'))}
        {row('Far depth','Fixed upper bound for the current cloud artifact.',fixedNumber('Far depth',3,'m'))}
      </>},
    fit_stl:{label:'Fit STL poses',kind:'computation',availability:reusable?'reusable':'unimplemented',reason:reusable?'Prepared poses are reusable. Passing pilot gates is not human approval.':'General arbitrary-STL initialization is not connected. The existing demonstration adapter is recording-specific.',description:'Fit the original STL against stereo images and depth. Retain original-STL transforms for each camera, rejected fits and diagnostic measurements.',
      summary:<SettingsSummaryChip>FoundationPose</SettingsSummaryChip>,
      configuration:<>
        {row('Pose estimator','The existing adapter runs FoundationPose registration and tracking.',<SettingSelectInput label="Pose estimator" value="foundationpose" options={[{value:'foundationpose',label:'FoundationPose'}]} onChange={()=>{}} disabled/>,true)}
        {row('Initialization',<>Current preset: {summary?.mask_preset??'none'}. This recording-specific color mask is a fixture limitation, not the arbitrary-STL initialization interface.</>,value('Recording preset'))}
        {row('Register iterations','Fixed registration iteration count in the existing adapter.',fixedNumber('Register iterations',2,''))}
        {row('Track iterations','Fixed tracking iteration count in the existing adapter.',fixedNumber('Track iterations',3,''))}
        {row('Depth error gate','Pilot median absolute depth error threshold, with stereo IoU/coverage gates. Not a camera accuracy claim or label approval.',fixedNumber('Depth error gate',5,'mm'))}
      </>},
    generate_candidates:{label:'Generate keypoint candidates',kind:'computation',availability:reusable?'available':'unavailable',reason:'Generate unreviewed candidate labels from verified prepared poses and the ordered target definition.',description:'Prepared-data subgraph: bind verified inputs → choose moments → project the ordered target definition → publish unreviewed candidates. Store moments/labels/images in Parquet with source provenance.',
      summary:reusable?<SettingsSummaryChip>{candidates.length} pairs · {candidates.length*2} images</SettingsSummaryChip>:null,
      configuration:<>
        {row('Fit filter','Apply range, then fit filter, stride and optional cap. Failed fits remain available for review; selection never implies approval.',<SettingSelectInput label="Fit filter" value={config.fit} options={[{value:'all',label:'All candidates'},{value:'passed',label:'Passed gates'},{value:'failed',label:'Failed gates'}]} onChange={v=>change('fit',v)}/>,true)}
        {row('Candidate stride','Select every Nth eligible paired moment after the fit filter.',numeric('Candidate stride','step',1,900))}
        {row('Limit moments','Cap the number of paired moments. Both camera images remain grouped.',<SettingToggleSwitch label="Limit moments" isToggled={config.limit!==''} onToggle={enabled=>change('limit',enabled?'30':'')}/>)}
        {config.limit!==''&&row('Maximum moments','Maximum paired moments after range/filter/stride.',numeric('Maximum moments','limit',1,900))}
        {row('Candidate pairs',<>Configuration preview only. Source frames: {candidates.slice(0,10).join(', ')}{candidates.length>10?' …':''}. No labels have been generated or approved.</>,value(reusable?candidates.length:'—'))}
        {row('Target points','Use the target’s exact ordered definition; retain invalid and out-of-bounds rows. Self-visibility differs from unknown external occlusion. Automatic point construction for a new STL is upstream work.',value(stl.compatible&&target?.authored_geometry?'Target definition':'Not configured'))}
      </>},
    review_labels:{label:'Select, review and correct',kind:'review',availability:'manual',reason:'Required human gate. Selection saving and correction tools are not yet implemented.',description:'Inspect synchronized images and STL placement together. Correct rigid pose first, then individual keypoints. Previous/next generated and selected moments preserve exact source identity. Save versioned reviews; selection is not approval.',
      configuration:<>
        {row('Correction order','First correct the rigid STL pose, then individual keypoints where necessary. The editor is not implemented in this panel.',value('Rigid pose → keypoints'))}
        {row('Selection unit','A moment groups both camera images and exact source timestamp.',value('Stereo moment'))}
      </>},
    publish_dataset:{label:'Publish training dataset',kind:'publication',availability:'unimplemented',reason:'A reviewed dataset publisher is not connected. Training is a later workflow.',description:'Publish an immutable dataset from human-reviewed labels and original images, with exact target order and source hashes. Keep stereo pairs and temporal neighborhoods together when defining splits before training.',
      configuration:<>
        {row('Label state','Only explicitly human-reviewed labels are eligible. Generated candidates and selected moments are not approved labels.',value('Reviewed only'))}
        {row('Image source','Use original native images, never annotated overlays.',value('Original images'))}
      </>},
  };
  const executionPresentation:Record<string,PipelineStagePresentation>={
    bind_inputs:{label:'Bind verified inputs',kind:'source',availability:'available',description:'Verify the selected recording, poses, calibration, STL and ordered keypoints.',reason:'Uses the current prepared-data identities.'},
    choose_moments:{label:'Choose paired moments',kind:'computation',availability:'available',description:'Apply range, fit filter, stride and optional cap in order.',reason:'Retains exact source frames and integer timestamps.'},
    project_labels:{label:'Project candidate labels',kind:'computation',availability:'available',description:'Reuse identity-verified projections or the established authored geometry projector.',reason:'Keeps all ordered points, invalid rows and visibility meaning.'},
    publish_candidates:{label:'Save unreviewed candidates',kind:'publication',availability:'available',description:'Publish immutable label, image-index and moment tables with provenance.',reason:'Generated candidates are not an approved training dataset.'},
  };
  const showingRun=!!run.snapshot&&showRun;
  const messages=[...project.issues,...problems,...(error?[error]:[]),...(saveError?[saveError]:[]),...(stl.error?[stl.error]:[]),...(run.error?[run.error]:[]),...(run.snapshot?.error?[run.snapshot.error]:[]),...(stl.validated&&!stl.compatible?['Selected STL or units differ from the current target. Existing poses and target points cannot be reused; prepare this target before generating labels.']:[])];
  return <PipelineWindow title="Create image training set" subtitle={project.project.project_id} onClose={onClose}>
    {!loaded?<p role="status">Loading…</p>:<PipelinePanel locked={run.running} graph={showingRun?run.snapshot!.graph:trainingGraph} nodePresentation={showingRun?executionPresentation:nodePresentation} operations={showingRun?run.snapshot!.operations:[]} view={view} onViewChange={setView}
      notice={messages.length?<ul className="training-errors">{messages.map(message=><li key={message}>{message}</li>)}</ul>:null}
      actions={<>{run.snapshot&&<ButtonSm text={showRun?"Workflow settings":"Run progress"} onClick={()=>setShowRun(v=>!v)}/>}<span role="status">{run.snapshot?`${run.snapshot.status}${run.snapshot.cancel_requested?" (cancellation requested)":""} · ${run.snapshot.operations.find(op=>op.status==='running')?.detail??''}`:run.preview?`${run.preview.moment_count} pairs · ${run.preview.image_count} images · ${run.preview.label_count} labels`:null}</span><AnchoredInfo title="Training-set workflow" text="Preview validates the current prepared inputs without processing. Generate candidates publishes unreviewed projected labels; selection for review is separate from human approval and dataset publication."/>
        <ButtonSm text="Preview candidates" onClick={()=>void run.inspect()} disabled={!reusable||run.running}/>
        <ButtonSm text="Generate candidates" iconClass="processmocap-icon" className="primary accent mp-process" textColor="text-white" onClick={()=>void run.start()} disabled={!reusable||!run.preview||run.running}/>
        {run.running&&<ButtonSm text="Cancel run" onClick={()=>void run.cancel()} disabled={!run.snapshot}/>}
        {run.snapshot?.status==='complete'&&<ButtonSm text="Review candidates" onClick={onClose}/>}
      </>}/>
    }
  </PipelineWindow>;
}
