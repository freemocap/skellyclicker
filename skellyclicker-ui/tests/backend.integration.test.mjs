import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createHttpClient, TransportService} from '@freemocap/client';
import {stateKind} from '../src/state-message.ts';

const baseUrl = process.env.SKELLYCLICKER_TEST_URL || 'http://127.0.0.1:8006';

test('the app HTTP identity and self-describing WebSocket updates agree', async () => {
  const http = createHttpClient({baseUrl});
  const response = await http.assetResponse('/api/status');
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {application: 'skellyclicker', mode: 'playback', recording: null});
  const url = new URL(baseUrl + '/websocket/connect');
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  const stream = new TransportService({url: url.href, kinds: {skellyclicker_state: stateKind}});
  let count = 0;
  let timer;
  try {
    await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('No app update within 10 seconds')), 10000);
      stream.subscribeToProtocolErrors(reject);
      stream.subscribeToKind('skellyclicker_state', state => {
        try {
          assert.equal(state.ready, true);
          count += 1;
          if (count === 1) stream.send({command: 'status'});
          if (count === 2) resolve();
        } catch (error) {reject(error);}
      });
      stream.connect();
    });
    assert.equal(count, 2);
  } finally {
    clearTimeout(timer);
    stream.disconnect();
  }
});
