import {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PlaybackWorkspace, BottomLogPanel, LogStore} from '@freemocap/ui';
import '@freemocap/ui/styles.css';
import {createHttpClient, TransportService} from '@freemocap/client';
import {stateKind} from './state-message';
import {AppShell} from './AppShell';
import {resolveBackendUrl} from './config';
import './shell.css';
import {ProjectPanel, type ProjectView} from './ProjectPanel';

function App({backendUrl}: {backendUrl: string}) {
  const [logs] = useState(() => new LogStore({storageKey: 'skellyclicker.logs'}));
  const [project, setProject] = useState<ProjectView | null>(null);
  const [status, setStatus] = useState('Connecting to backend…');
  const [messages, setMessages] = useState(0);
  useEffect(() => {
    const client = createHttpClient({baseUrl: backendUrl});
    const streamUrl = new URL(backendUrl + '/websocket/connect');
    streamUrl.protocol = streamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const stream = new TransportService({url: streamUrl.href, kinds: {skellyclicker_state: stateKind}});
    logs.start();
    const unsubscribeLogs = stream.subscribeToLog(record => logs.add(record));
    const abort = new AbortController();
    let active = true;
    const unsubscribe = stream.subscribeToKind('skellyclicker_state', () => {
      if (active) setMessages(count => count + 1);
    });
    const unsubscribeErrors = stream.subscribeToProtocolErrors(error => {
      if (active) setStatus(`Stream error: ${String(error)}`);
    });
    void client.assetResponse('/api/status', {signal: abort.signal}).then(async response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      if (result.application !== 'skellyclicker') throw new Error('The endpoint is not a SkellyClicker backend.');
      if (active) setStatus('Backend connected');
      const remembered = localStorage.getItem('skellyclicker.projectPath');
      if (remembered) {
        const opened = await fetch(backendUrl + '/api/projects/open', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({project_path:remembered}), signal:abort.signal});
        if (opened.ok && active) setProject(await opened.json());
      }
    }).catch(error => {
      if (active) setStatus(`Backend unavailable: ${String(error)}`);
    });
    stream.connect();
    return () => {active = false; abort.abort(); unsubscribe(); unsubscribeErrors(); unsubscribeLogs(); stream.disconnect(); logs.dispose();};
  }, [backendUrl, logs]);
  return <AppShell sidebar={<ProjectPanel baseUrl={backendUrl} project={project} onProject={setProject}/>}
    bottom={<BottomLogPanel store={logs} title="Backend logs" initialHeight={230}/>}
    status={<><span>{status}</span><span>Stream updates: {messages}</span></>}>
    <PlaybackWorkspace baseUrl={backendUrl} recording={null}/>
  </AppShell>;
}

const root = createRoot(document.getElementById('root')!);
void resolveBackendUrl().then(backendUrl => root.render(<App backendUrl={backendUrl}/>)).catch(error => {
  root.render(<main role="alert"><h1>SkellyClicker could not start</h1><pre>{String(error)}</pre></main>);
});


