import {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PlaybackWorkspace} from '@freemocap/ui';
import '@freemocap/ui/styles.css';
import {createHttpClient, TransportService} from '@freemocap/client';
import {stateKind} from './state-message';
import {AppShell} from './AppShell';
import {backendUrl} from './config';
import './shell.css';

function App() {
  const [status, setStatus] = useState('Connecting to backend…');
  const [messages, setMessages] = useState(0);
  useEffect(() => {
    const client = createHttpClient({baseUrl: backendUrl});
    const streamUrl = new URL(backendUrl + '/websocket/connect');
    streamUrl.protocol = streamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const stream = new TransportService({url: streamUrl.href, kinds: {skellyclicker_state: stateKind}});
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
    }).catch(error => {
      if (active) setStatus(`Backend unavailable: ${String(error)}`);
    });
    stream.connect();
    return () => {active = false; abort.abort(); unsubscribe(); unsubscribeErrors(); stream.disconnect();};
  }, []);
  return <AppShell sidebar={<section className="skellyclicker-recordings"><h2>Recordings</h2><p>No recording selected.</p></section>}
    status={<><span>{status}</span><span>Stream updates: {messages}</span></>}>
    <PlaybackWorkspace baseUrl={backendUrl} recording={null}/>
  </AppShell>;
}

createRoot(document.getElementById('root')!).render(<App/>);
