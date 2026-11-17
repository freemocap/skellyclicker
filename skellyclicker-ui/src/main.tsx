import {useEffect, useMemo, useRef, useState, lazy, Suspense} from 'react';
import {createRoot} from 'react-dom/client';
import {PlaybackWorkspace, Legend, BottomLogPanel, LogStore, ServerConnectionStatus, type PlaybackWorkspaceHandle, type PresentedFrame} from '@freemocap/ui';
import '@freemocap/ui/styles.css';
import {createHttpClient, TransportService, ConnectionState, pipelineSnapshotKind, type PipelineSnapshot} from '@freemocap/client';
import {stateKind} from './state-message';
import {AppShell,type WorkspaceView} from './AppShell';
import {KeypointTraining} from './KeypointTraining';
import {TrainingDashboard} from './TrainingDashboard';
import {resolveBackendUrl} from './config';
import './shell.css';
import {useTargetCrop} from './useTargetCrop';
import {useCandidateReview} from './CandidateReviewPanel';
import {DatasetQualityPanel,type GenerationMode} from './DatasetQualityPanel';
import {PreparationPanel} from './PreparationPanel';
import {ProjectPanel, type ProjectView} from './ProjectPanel';
import {SidebarProcessingAction,ButtonSm} from '@freemocap/ui';
import './training-set.css';
import {emptySession,type SessionState} from './session';
import {useFolderPicker, readFolder, type OpenRecording} from './RecordingPicker';
import {useLabeling} from './labeling/useLabeling';
import {LabelPanel} from './labeling/LabelPanel';
import './labeling/labeling.css';

const TrainingSetPanel = lazy(() => import('./TrainingSetPanel').then(module => ({default: module.TrainingSetPanel})));

function App({backendUrl}: {backendUrl: string}) {
  const [logs] = useState(() => new LogStore({storageKey: 'skellyclicker.logs'}));
  const [logPersistenceError,setLogPersistenceError]=useState<string|null>(null);
  const [project, setProject] = useState<ProjectView | null>(null);
  const [pipelineSnapshots,setPipelineSnapshots]=useState<Record<string,PipelineSnapshot>>({});
  const getTargetCrop=useTargetCrop(backendUrl,project?.playback?.targetCropUrl);
  const playbackControls=useRef<PlaybackWorkspaceHandle|null>(null);
  const [presented,setPresented]=useState<PresentedFrame|null>(null);
  const [manual,setManual] = useState<OpenRecording|null>(null);
  const playback = manual ?? project?.playback;
  const labelSource = playback?.labelSource;
  const labelRecording = useMemo(() => labelSource ? {recordingId:labelSource.id,parentDirectory:labelSource.parent} : null, [labelSource]);
  const labeling=useLabeling({baseUrl:backendUrl,recording:labelRecording,sourceSizes:manual?.sourceSizes,playbackId:playback?.id,cameraEntries:playback?.cameras,presented,controls:playbackControls});
  const [datasetRefreshRevision,setDatasetRefreshRevision]=useState('');
  const review=useCandidateReview({baseUrl:backendUrl,project,controls:playbackControls,presented,refreshKey:Object.values(pipelineSnapshots).filter(s=>s.status==='complete').map(s=>s.run_id).join(',')+':'+datasetRefreshRevision});
  const [session,setSession]=useState<SessionState>(emptySession);
  const [restoring,setRestoring]=useState(true),[sessionError,setSessionError]=useState('');
  const saveQueue=useRef(Promise.resolve());
  const sidebarMode=session.sidebar;
  function saveSession(changes:Partial<SessionState>){
    const projectPath=project?.manifest_path;
    setSession(previous=>({...previous,...changes}));
    if(!projectPath)return;
    saveQueue.current=saveQueue.current.catch(()=>{}).then(async()=>{
      const response=await fetch(backendUrl+'/api/session',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...changes,project_path:projectPath})});
      if(!response.ok)throw new Error((await response.json()).detail??'Session save failed');
    }).catch(error=>setSessionError(String(error)));
  }
  function acceptRecording(value:OpenRecording){
    localStorage.setItem('skellyclicker.manualRecording',value.root);
    setManual(value);setProject(null);setSession({...emptySession,sidebar:'labels',workspace:'viewer'});
    setSessionError('');setSidebarRequest(v=>v+1);
  }
  function acceptProject(value:ProjectView){localStorage.setItem('skellyclicker.projectPath',value.manifest_path);localStorage.removeItem('skellyclicker.manualRecording');setManual(null);setProject(value);setSessionError('');if(value.session_state)setSession(value.session_state);}
  const folderPicker = useFolderPicker(backendUrl, acceptRecording, acceptProject);
  async function restoreSession(signal?:AbortSignal){
    setRestoring(true);setSessionError('');
    try{
      const ready=await fetch(backendUrl+'/api/status',{signal});if(!ready.ok)throw new Error('Backend unavailable. Retry when connected.');
      const lastRecording = localStorage.getItem('skellyclicker.manualRecording');
      if(lastRecording){
        const result=await readFolder(backendUrl,lastRecording);
        if(!signal?.aborted && !('candidates' in result))acceptRecording(result);
        return;
      }
      const response=await fetch(backendUrl+'/api/session',{signal});if(!response.ok)throw new Error('Saved session unavailable. Retry when connected.');
      const saved=await response.json();if(signal?.aborted)return;
      if(saved.state)setSession(saved.state);
      if(saved.error){setSessionError(saved.error);return;}
      if(saved.project){setProject(saved.project);return;}
      const legacy=localStorage.getItem('skellyclicker.projectPath');
      if(legacy){const opened=await fetch(backendUrl+'/api/projects/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:legacy}),signal});const value=await opened.json();if(!opened.ok)throw new Error(`Could not reopen ${legacy}: ${value.detail}. Open its current location or retry.`);if(!signal?.aborted)acceptProject(value);}
    }catch(error){if(!signal?.aborted)setSessionError(String(error));}
    finally{if(!signal?.aborted)setRestoring(false);}
  }
  useEffect(()=>{const abort=new AbortController();void restoreSession(abort.signal);return()=>abort.abort();},[backendUrl]);
  const [generationTarget,setGenerationTarget]=useState<HTMLDivElement|null>(null);
  const [generationMode,setGenerationMode]=useState<GenerationMode>(()=>{const saved=localStorage.getItem('skellyclicker.generation-view');return saved==='model'||saved==='recording'?saved:'selection';});
  const [sidebarRequest,setSidebarRequest]=useState(0);
  const [toolbarTarget,setToolbarTarget]=useState<HTMLDivElement|null>(null);
  const [resultView,setResultView]=useState<'generation'|'training'>(()=>{const saved=localStorage.getItem('skellyclicker.results-view');return saved==='generation'?saved:'training';});
  function goTo(view:WorkspaceView){if(view!=='viewer'){setResultView(view);localStorage.setItem('skellyclicker.results-view',view);}saveSession({workspace:view==='viewer'?'viewer':'training'});}
  async function openGeneratedImages(){if(!project)return;const response=await fetch(backendUrl+'/api/projects/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:project.manifest_path})});if(!response.ok)throw new Error('Could not open generated images. Retry.');acceptProject(await response.json());saveSession({sidebar:'images',workspace:'viewer'});setSidebarRequest(v=>v+1);}
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED);
  const [httpStatus, setHttpStatus] = useState<'checking'|'available'|'unavailable'>('checking');
  const [connectionError, setConnectionError] = useState<string|null>(null);
  const actions = useRef<{reconnect:()=>void; disconnect:()=>void}|null>(null);
  useEffect(() => {
    const client = createHttpClient({baseUrl: backendUrl});
    const streamUrl = new URL(backendUrl + '/websocket/connect');
    streamUrl.protocol = streamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const stream = new TransportService({url: streamUrl.href, kinds: {skellyclicker_state: stateKind,pipeline_snapshot:pipelineSnapshotKind}});
    const abort = new AbortController();
    let active = true;
    const stateChanged = (state: ConnectionState) => {
      if (active) {setConnectionState(state);if(state===ConnectionState.CONNECTED)setConnectionError(null);}
    };
    stream.on('state-change',stateChanged);
    stateChanged(stream.getState());
    let unsubscribeLogs=()=>{};
    const persistLogs=()=>logs.persistNow();
    window.addEventListener('beforeunload',persistLogs);
    const logErrorTimer=setInterval(()=>setLogPersistenceError(logs.persistenceError),1000);
    const unsubscribePipeline=stream.subscribeToKind('pipeline_snapshot',message=>{if(active)setPipelineSnapshots(previous=>{const next=message.snapshot;return previous[next.run_id]?.sequence>=next.sequence?previous:{...previous,[next.run_id]:next};});});
    const unsubscribeErrors = stream.subscribeToProtocolErrors(error => {
      if (active) setConnectionError(`Stream error: ${String(error)}`);
    });
    async function checkHttp() {
      if(active)setHttpStatus('checking');
      try {
        const response=await client.assetResponse('/api/status',{signal:abort.signal});
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        const identity=await response.json();
        if(identity.application!=='skellyclicker')throw new Error('The endpoint is not a SkellyClicker backend.');
        if(typeof identity.log_session_id!=='string')throw new Error('Restart SkellyClicker to activate the updated backend and log session.');
        if(!active)return;
        await logs.beginSession(identity.log_session_id);if(!active)return;logs.start();
        unsubscribeLogs();unsubscribeLogs=stream.subscribeToLog(record=>logs.add(record));
        stream.connect();
        if(active)setHttpStatus('available');
      }catch(error){if(active){setHttpStatus('unavailable');setConnectionError(String(error));}}
    }
    actions.current={reconnect:()=>{stream.disconnect();void checkHttp();},disconnect:()=>stream.disconnect()};
    void checkHttp();
    return () => {active=false;window.removeEventListener('beforeunload',persistLogs);clearInterval(logErrorTimer);actions.current=null;abort.abort();stream.off('state-change',stateChanged);unsubscribePipeline();unsubscribeErrors();unsubscribeLogs();stream.disconnect();logs.dispose();};
  }, [backendUrl, logs]);
return <><AppShell manualRecording={!!manual} sidebarRequest={sidebarRequest} recordingPicker={<><ButtonSm text="Open folder…" buttonType="secondary" disabled={folderPicker.busy||restoring} onClick={()=>void folderPicker.browse()}/>{folderPicker.dialog}</>} projectName={manual?.displayName??project?.project.project_id} onCreateTrainingSet={project?()=>{setGenerationMode('recording');localStorage.setItem('skellyclicker.generation-view','recording');goTo('generation');}:undefined} onToolbarTarget={manual?undefined:setToolbarTarget} view={session.workspace==='viewer'?'viewer':resultView} onView={goTo} training={restoring?<p role="status">Restoring your last project...</p>:manual?.labelSource?<KeypointTraining key={manual.root} baseUrl={backendUrl} id={manual.labelSource.id} parent={manual.labelSource.parent} labeling={labeling}/>:<TrainingDashboard validateInputs={session.workspace!=='viewer'&&resultView==='training'} includedImageCount={review.result?review.selection.selected_image_ids.length:undefined} generationTarget={generationTarget} onGoTraining={()=>goTo('training')} onDatasetChanged={(revision)=>setDatasetRefreshRevision(revision)} toolbarTarget={project?toolbarTarget:null} baseUrl={backendUrl} project={project} snapshots={pipelineSnapshots} selectionRevision={review.selectionRevision} rememberedRun={session.training_run_id} onRememberRun={training_run_id=>saveSession({training_run_id})}/>} sidebar={<>
    {restoring&&<p role="status">Restoring your last project...</p>}
    {logPersistenceError&&<p role="alert">Log history cannot be saved for reload: {logPersistenceError}</p>}
    {sessionError&&<div role="alert" className="session-recovery"><p>{sessionError}</p><SidebarProcessingAction text="Retry saved session" iconClass="rotate-icon" onClick={()=>void restoreSession()}/><SidebarProcessingAction text="Show projects" iconClass="import-icon" onClick={()=>setSession(s=>({...s,sidebar:'project'}))}/></div>}
    {(manual||project)&&<div className="review-sidebar-tabs" role="group" aria-label="Sidebar view">
      {playback&&<ButtonSm text="Labels" textColor="" ariaPressed={sidebarMode==='labels'} onClick={()=>saveSession({sidebar:'labels'})}/>}
      {review.catalog&&<ButtonSm text="Images" textColor="" ariaPressed={sidebarMode==='images'} onClick={()=>saveSession({sidebar:'images'})}/>}
      <ButtonSm text="Project" textColor="" ariaPressed={sidebarMode==='project'} onClick={()=>saveSession({sidebar:'project'})}/>
    </div>}
    {!restoring&&(playback&&sidebarMode==='labels'?<>{manual?.issues.map(issue=><p key={issue}>{issue}</p>)}<LabelPanel labeling={labeling}/></>:review.catalog&&sidebarMode==='images'?review.catalog:<><ProjectPanel onBrowseFolder={folderPicker.browse} baseUrl={backendUrl} project={project} onProject={acceptProject} recordingId={session.recording_id} onRecording={recording_id=>saveSession({recording_id})}/>{project&&<PreparationPanel baseUrl={backendUrl} project={project} onComplete={acceptProject}/>}</>)}
  </>}
    generation={<DatasetQualityPanel onRefresh={()=>setDatasetRefreshRevision('refresh:'+Date.now())} baseUrl={backendUrl} projectPath={project?.manifest_path} result={review.result} selection={review.selection} onSelection={value=>{review.applySelection(value);setDatasetRefreshRevision(value.sha256??'');}} onNavigate={id=>{void review.navigate(id);goTo('viewer');}} mode={generationMode} onMode={mode=>{setGenerationMode(mode);localStorage.setItem('skellyclicker.generation-view',mode);}}
      recording={project?<Suspense fallback={<p role="status">Loading recording…</p>}><TrainingSetPanel embedded key={project.project.uuid} baseUrl={backendUrl} project={project} snapshots={pipelineSnapshots} onClose={()=>goTo('viewer')} onReview={openGeneratedImages}/></Suspense>:<p role="status">No project selected</p>}
      model={<div ref={setGenerationTarget} className="generation-refinement-target"/>}/>}
    connection={<ServerConnectionStatus state={connectionState} endpoint={backendUrl} httpStatus={httpStatus} error={connectionError} onReconnect={()=>actions.current?.reconnect()} onDisconnect={()=>actions.current?.disconnect()}/>}
    bottom={<BottomLogPanel store={logs} title="Backend logs" initialHeight={230} showHeader={false}/>}
    >
    {project?.playback&&<Legend label="Pose candidates" items={[
      {label:'Passed gates',color:'#5ce69a',description:'Passed the configured pilot gates; not human approval'},
      {label:'Rejected',color:'#ffa244',description:'Failed one or more pilot gates; shown for inspection'},
      {label:'Authored reference',color:'#b99aff',description:'Unposed STL at the world origin; not a detected object'},
      ...(project.targets.some(t=>t.authored_geometry)?[
        {label:'Keypoints',color:'#ff45e6',description:'Authored points projected through the fitted pose; hollow image points are mesh-self-occluded'},
        {label:'Mesh outline',color:'#37eaff',description:'Thin visible mesh crease and silhouette edges in annotated images'},
      ]:[]),
    ]} details={<>
      <p>Points show target geometry projected through the fitted pose, not detector predictions. Training-set membership records your approval for training.</p>
      <p>The purple reference shows the authored geometry at the origin. Green and orange show fitted candidates.</p>
    </>}/> }
    <PlaybackWorkspace navigationGroups={manual?undefined:review.navigationGroups} renderImageControls={manual?undefined:review.renderImageControls} renderImageOverlay={sidebarMode==='labels' && session.workspace==='viewer' ? labeling.renderImageOverlay : undefined} sceneAnnotations={labeling.sceneAnnotations} onCalibration={labeling.onCalibration} activeVideoId={sidebarMode==='labels'?labeling.document?.session.active_camera??undefined:review.activeVideoId} getTargetCrop={manual?undefined:getTargetCrop} controlsRef={playbackControls} onPresentedFrame={setPresented} pointCloud={project?.playback?.pointCloudManifest?{manifestUrl:backendUrl+project.playback.pointCloudManifest,loading:{concurrency:16,maxResidentBytes:512*1024*1024}}:undefined} baseUrl={manual?backendUrl+'/core':backendUrl} recording={playback??null} showTimingNotice={false}/>
  </AppShell>

  </>;
}

const root = createRoot(document.getElementById('root')!);
void resolveBackendUrl().then(backendUrl => root.render(<App backendUrl={backendUrl}/>)).catch(error => {
  root.render(<main role="alert"><h1>SkellyClicker could not start</h1><pre>{String(error)}</pre></main>);
});
