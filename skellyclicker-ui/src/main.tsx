import {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PlaybackWorkspace, Legend, BottomLogPanel, LogStore, ServerConnectionStatus} from '@freemocap/ui';
import '@freemocap/ui/styles.css';
import {createHttpClient, TransportService, ConnectionState} from '@freemocap/client';
import {stateKind} from './state-message';
import {AppShell} from './AppShell';
import {resolveBackendUrl} from './config';
import './shell.css';
import {PreparationPanel} from './PreparationPanel';
import {ProjectPanel, type ProjectView} from './ProjectPanel';

function App({backendUrl}: {backendUrl: string}) {
  const [logs] = useState(() => new LogStore({storageKey: 'skellyclicker.logs'}));
  const [project, setProject] = useState<ProjectView | null>(null);
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED);
  const [httpStatus, setHttpStatus] = useState<'checking'|'available'|'unavailable'>('checking');
  const [connectionError, setConnectionError] = useState<string|null>(null);
  const [messages, setMessages] = useState(0);
  const actions = useRef<{reconnect:()=>void; disconnect:()=>void}|null>(null);
  useEffect(() => {
    const client = createHttpClient({baseUrl: backendUrl});
    const streamUrl = new URL(backendUrl + '/websocket/connect');
    streamUrl.protocol = streamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const stream = new TransportService({url: streamUrl.href, kinds: {skellyclicker_state: stateKind}});
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
    const remembered=localStorage.getItem('skellyclicker.projectPath');
    if(remembered)void fetch(backendUrl+'/api/projects/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:remembered}),signal:abort.signal}).then(async response=>{
      if(response.ok&&active)setProject(await response.json());
    }).catch(()=>{/* Backend logs retain project errors; connection monitor owns transport errors. */});
    stream.connect();
    return () => {active=false;actions.current=null;abort.abort();stream.off('state-change',stateChanged);unsubscribe();unsubscribeErrors();unsubscribeLogs();stream.disconnect();logs.dispose();};
  }, [backendUrl, logs]);
  return <AppShell sidebar={<><ProjectPanel baseUrl={backendUrl} project={project} onProject={setProject}/>{project&&<PreparationPanel baseUrl={backendUrl} project={project} onComplete={setProject}/>}</>}
    connection={<ServerConnectionStatus state={connectionState} endpoint={backendUrl} httpStatus={httpStatus} error={connectionError} onReconnect={()=>actions.current?.reconnect()} onDisconnect={()=>actions.current?.disconnect()}/>}
    bottom={<BottomLogPanel store={logs} title="Backend logs" initialHeight={230} showHeader={false}/>}
    status={<><span>{connectionError??(connectionState===ConnectionState.CONNECTED?'Backend connected':`Backend ${connectionState.toLowerCase()}`)}</span><span>Stream updates: {messages}</span></>}>
    {project?.playback&&<Legend label="Pose candidates" items={[
      {label:'Passed gates',color:'#5ce69a',description:'Passed the configured pilot gates; not human approval'},
      {label:'Rejected',color:'#ffa244',description:'Failed one or more pilot gates; shown for inspection'},
      {label:'Authored reference',color:'#b99aff',description:'Unposed STL at the world origin; not a detected object'},
      ...(project.targets.some(t=>t.authored_geometry)?[
        {label:'Keypoints',color:'#ff45e6',description:'Authored points projected through the fitted pose; hollow image points are mesh-self-occluded'},
        {label:'Mesh outline',color:'#37eaff',description:'Thin visible mesh crease and silhouette edges in annotated images'},
      ]:[]),
    ]} note="All unreviewed" details={<>
      <p>Points show target geometry projected through the fitted pose, not detector predictions or approved labels.</p>
      <p>The purple reference shows the authored geometry at the origin. Green and orange show fitted candidates.</p>
    </>}/> }
    <PlaybackWorkspace pointCloud={project?.playback?.pointCloudManifest?{manifestUrl:backendUrl+project.playback.pointCloudManifest,loading:{concurrency:16,maxResidentBytes:512*1024*1024}}:undefined} baseUrl={backendUrl} recording={project?.playback?{...project.playback,displayName:project.project.project_id+' - fresh pose candidates'}:null} showTimingNotice={false}/>
  </AppShell>;
}

const root = createRoot(document.getElementById('root')!);
void resolveBackendUrl().then(backendUrl => root.render(<App backendUrl={backendUrl}/>)).catch(error => {
  root.render(<main role="alert"><h1>SkellyClicker could not start</h1><pre>{String(error)}</pre></main>);
});
