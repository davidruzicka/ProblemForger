import { createConnection } from 'node:net';

type Request = {
  protocol_version: 1;
  kind: 'request';
  request_id: string;
  method: 'echo' | 'stream_observations';
  params: { payload?: string; count?: number };
};

type Response = {
  protocol_version: 1;
  kind: 'response' | 'event';
  request_id: string;
  result?: { payload?: string; event_count?: number };
  event?: { type: string; sequence: number; attributes: Record<string, string> };
  error?: { code: string; message: string };
};

const [transport, target, sizeText = '256', methodText = 'echo'] = process.argv.slice(2);
if (!['http', 'unix'].includes(transport) || !target) {
  throw new Error('usage: client.ts <http|unix> <URL|socket-path> [payload-bytes] [echo|stream_observations]');
}
const size = Number(sizeText);
if (!Number.isSafeInteger(size) || size < 0 || size > 1024 * 1024) {
  throw new Error('payload-bytes must be an integer from 0 through 1048576');
}
if (!['echo', 'stream_observations'].includes(methodText)) {
  throw new Error('method must be echo or stream_observations');
}

const request: Request = {
  protocol_version: 1,
  kind: 'request',
  request_id: 'typescript-demo-1',
  method: methodText as Request['method'],
  params: methodText === 'echo' ? { payload: 'x'.repeat(size) } : { count: 3 },
};

function parseSse(text: string): { events: Response[]; response?: Response } {
  const events: Response[] = [];
  let response: Response | undefined;
  for (const block of text.split('\n\n')) {
    const eventName = block.split('\n').find((line) => line.startsWith('event: '))?.slice(7);
    const data = block.split('\n').find((line) => line.startsWith('data: '))?.slice(6);
    if (!data) continue;
    const message = JSON.parse(data) as Response;
    if (eventName === 'observation') events.push(message);
    if (eventName === 'complete') response = message;
  }
  return { events, response };
}

async function callHttp(): Promise<{ events: Response[]; response: Response }> {
  const streaming = request.method === 'stream_observations';
  const result = await fetch(`${target}${streaming ? '/v1/observations' : '/v1/request'}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(2000),
  });
  if (!result.ok) throw new Error(`HTTP ${result.status}`);
  if (!streaming) return { events: [], response: await result.json() as Response };
  const parsed = parseSse(await result.text());
  if (!parsed.response) throw new Error('HTTP stream closed without completion');
  return { events: parsed.events, response: parsed.response };
}

function callUnix(): Promise<{ events: Response[]; response: Response }> {
  return new Promise((resolve, reject) => {
    const socket = createConnection(target);
    let buffer = '';
    const events: Response[] = [];
    const timer = setTimeout(() => socket.destroy(new Error('TIMEOUT')), 2000);
    socket.once('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
    socket.once('connect', () => socket.write(`${JSON.stringify(request)}\n`));
    socket.on('data', (chunk: Buffer) => {
      buffer += chunk.toString('utf8');
      while (buffer.includes('\n')) {
        const end = buffer.indexOf('\n');
        const line = buffer.slice(0, end);
        buffer = buffer.slice(end + 1);
        if (!line) continue;
        const message = JSON.parse(line) as Response;
        if (message.kind === 'event') {
          events.push(message);
          continue;
        }
        if (message.kind !== 'response' || message.request_id !== request.request_id) {
          socket.destroy(new Error('response id or kind does not match request'));
          return;
        }
        clearTimeout(timer);
        socket.end();
        resolve({ events, response: message });
      }
    });
  });
}

const result = transport === 'http' ? await callHttp() : await callUnix();
if (result.response.error) throw new Error(`${result.response.error.code}: ${result.response.error.message}`);
if (request.method === 'echo' && result.response.result?.payload !== request.params.payload) {
  throw new Error('echo response changed the payload');
}
console.log(JSON.stringify({ transport, request_id: result.response.request_id, events: result.events.length, response_bytes: JSON.stringify(result.response).length }));
