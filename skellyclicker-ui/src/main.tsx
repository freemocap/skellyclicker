import {useEffect, useRef, useState, lazy, Suspense} from 'react';
import {createRoot} from 'react-dom/client';
import {PlaybackWorkspace, Legend, BottomLogPanel, LogStore, ServerConnectionStatus, type PlaybackWorkspaceHandle, type PresentedFrame} from '@freemocap/ui';
import '@freemocap/ui/styles.css';
import {createHttpClient, TransportService, ConnectionState, pipelineSnapshotKind, type PipelineSnapshot} from '@freemocap/client';
import {stateKind} from './state-message';
import {AppShell} from './AppShell';
import {TrainingDashboard} from './TrainingDashboard';
import {resolveBackendUrl} from './config';
import './shell.css';
import {useTargetCrop} from './useTargetCrop';
import {useCandidateReview} from './CandidateReviewPanel';
import {PreparationPanel} from './PreparationPanel';
import {ProjectPanel, type ProjectView} from './ProjectPanel';
import {SidebarProcessingAction,ButtonSm} from '@freemocap/ui';
import './training-set.css';
import {emptySession,type SessionState} from './session';

const TrainingSetPanel = lazy(() => import('./TrainingSetPanel').then(module => ({default: module.TrainingSetPanel})));

function App({backendUrl}: {backendUrl: string}) {
  const [logs] = useState(() => new LogStore({storageKey: 'skellyclicker.logs'}));
  const [project, setProject] = useState<ProjectView | null>(null);
  const [pipelineSnapshots,setPipelineSnapshots]=useState<Record<string,PipelineSnapshot>>({});
  const getTargetCrop=useTargetCrop(backendUrl,project?.playback?.targetCropUrl);
  const playbackControls=useRef<PlaybackWorkspaceHandle|null>(null);
  const [presented,setPresented]=useState<PresentedFrame|null>(null);
  const review=useCandidateReview({baseUrl:backendUrl,project,controls:playbackControls,presented,refreshKey:Object.values(pipelineSnapshots).filter(s=>s.status==='complete').map(s=>s.run_id).join(',')});
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
  function acceptProject(value:ProjectView){setProject(value);setSessionError('');if(value.session_state)setSession(value.session_state);}
  async function restoreSession(signal?:AbortSignal){
    setRestoring(true);setSessionError('');
    try{
      const ready=await fetch(backendUrl+'/api/status',{signal});if(!ready.ok)throw new Error('Backend unavailable. Retry when connected.');
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
  const [trainingOpen,setTrainingOpen]=useState(false);
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED);
  const [httpStatus, setHttpStatus] = useState<'checking'|'available'|'unavailable'>('checking');
  const [connectionError, setConnectionError] = useState<string|null>(null);
  const [messages, setMessages] = useState(0);
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
    logs.start();
    const unsubscribeLogs = stream.subscribeToLog(record => logs.add(record));
    const unsubscribe = stream.subscribeToKind('skellyclicker_state', () => {
      if (active) setMessages(count => count + 1);
    });
    const unsubscribePipeline=stream.subscribeToKind('pipeline_snapshot',message=>{if(active)setPipelineSnapshots(previous=>{const next=message.snapshot;return previous[next.run_id]?.sequence>=next.sequence?previous:{...previous,[next.run_id]:next};});});
    const unsubscribeErrors = stream.subscribeToProtocolErrors(error => {
      if (active) setConnectionError(`Stream error: ${String(error)}`);
    });
    async function checkHttp() {
      if(active)setHttpStatus('checking');
      try {
        const response=await client.assetResponse('/api/status',{signal:abort.signal});
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        if((await response.json()).application!=='skellyclicker')throw new Error('The endpoint is not a SkellyClicker backend.');
        if(active)setHttpStatus('available');
      }catch(error){if(active){setHttpStatus('unavailable');setConnectionError(String(error));}}
    }
    actions.current={reconnect:()=>{stream.disconnect();stream.connect();void checkHttp();},disconnect:()=>stream.disconnect()};
    void checkHttp();
    stream.connect();
    return () => {active=false;actions.current=null;abort.abort();stream.off('state-change',stateChanged);unsubscribe();unsubscribePipeline();unsubscribeErrors();unsubscribeLogs();stream.disconnect();logs.dispose();};
  }, [backendUrl, logs]);
  return <AppShell view={session.workspace} onView={workspace=>saveSession({workspace})} training={restoring?<p role="status">Restoring your last project...</p>:<TrainingDashboard baseUrl={backendUrl} project={project} snapshots={pipelineSnapshots} rememberedRun={session.training_run_id} onRememberRun={training_run_id=>saveSession({training_run_id})}/>} sidebar={<>
    {restoring&&<p role="status">Restoring your last project...</p>}
    {sessionError&&<div role="alert" className="session-recovery"><p>{sessionError}</p><SidebarProcessingAction text="Retry saved session" iconClass="rotate-icon" onClick={()=>void restoreSession()}/><SidebarProcessingAction text="Show projects" iconClass="import-icon" onClick={()=>setSession(s=>({...s,sidebar:'project'}))}/></div>}
    {review.catalog&&<div className="review-sidebar-tabs" role="group" aria-label="Sidebar view">
      <ButtonSm text="Images" textColor="" ariaPressed={sidebarMode==='images'} onClick={()=>saveSession({sidebar:'images'})}/>
      <ButtonSm text="Project" textColor="" ariaPressed={sidebarMode==='project'} onClick={()=>saveSession({sidebar:'project'})}/>
    </div>}
    {project&&<div className="training-entry"><SidebarProcessingAction text="Create image training set" iconClass="importVideos-icon" onClick={()=>setTrainingOpen(true)}/></div>}
    {!restoring&&(review.catalog&&sidebarMode==='images'?review.catalog:<><ProjectPanel baseUrl={backendUrl} project={project} onProject={acceptProject} recordingId={session.recording_id} onRecording={recording_id=>saveSession({recording_id})}/>{project&&<PreparationPanel baseUrl={backendUrl} project={project} onComplete={acceptProject}/>}</>)}
  </>}
    connection={<ServerConnectionStatus state={connectionState} endpoint={backendUrl} httpStatus={httpStatus} error={connectionError} onReconnect={()=>actions.current?.reconnect()} onDisconnect={()=>actions.current?.disconnect()}/>}
    bottom={<BottomLogPanel store={logs} title="Backend logs" initialHeight={230} showHeader={false}/>}
    status={<><span>{connectionError??(connectionState===ConnectionState.CONNECTED?'Backend connected':`Backend ${connectionState.toLowerCase()}`)}</span><span>Stream updates: {messages}</span></>}>
    {trainingOpen&&project&&<Suspense fallback={null}><TrainingSetPanel key={project.project.uuid} baseUrl={backendUrl} project={project} snapshots={pipelineSnapshots} onClose={()=>setTrainingOpen(false)}/></Suspense>}
    {project?.playback&&<Legend label="Pose candidates" items={[
      {label:'Passed gates',color:'#5ce69a',description:'Passed the configured pilot gates; not human approval'},
      {label:'Rejected',color:'#ffa244',description:'Failed one or more pilot gates; shown for inspection'},
      {label:'Authored reference',color:'#b99aff',description:'Unposed STL at the world origin; not a detected object'},
      ...(project.targets.some(t=>t.authored_geometry)?[
        {label:'Keypoints',color:'#ff45e6',description:'Authored points projected through the fitted pose; hollow image points are mesh-self-occluded'},
        {label:'Mesh outline',color:'#37eaff',description:'Thin visible mesh crease and silhouette edges in annotated images'},
      ]:[]),
    ]} note="Include images to approve them for training" details={<>
      <p>Points show target geometry projected through the fitted pose, not detector predictions. Inclusion records your approval for training.</p>
      <p>The purple reference shows the authored geometry at the origin. Green and orange show fitted candidates.</p>
    </>}/> }
    <PlaybackWorkspace navigationGroups={review.navigationGroups} renderImageControls={review.renderImageControls} activeVideoId={review.activeVideoId} getTargetCrop={getTargetCrop} controlsRef={playbackControls} onPresentedFrame={setPresented} pointCloud={project?.playback?.pointCloudManifest?{manifestUrl:backendUrl+project.playback.pointCloudManifest,loading:{concurrency:16,maxResidentBytes:512*1024*1024}}:undefined} baseUrl={backendUrl} recording={project?.playback?{...project.playback,displayName:project.project.project_id+' - fresh pose candidates'}:null} showTimingNotice={false}/>
  </AppShell>;
}

const root = createRoot(document.getElementById('root')!);
void resolveBackendUrl().then(backendUrl => root.render(<App backendUrl={backendUrl}/>)).catch(error => {
  root.render(<main role="alert"><h1>SkellyClicker could not start</h1><pre>{String(error)}</pre></main>);
});
