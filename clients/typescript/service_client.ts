/** TypeScript worker client for the local JSONL Unix socket. */

import { createConnection, type Socket } from 'node:net';
import {
  decodeResponse,
  encodeRequest,
  MAX_PROTOCOL_MESSAGE_BYTES,
  type ProtocolRequest,
  type ProtocolResponse,
} from './protocol.ts';

export class ServiceUnavailableError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = 'ServiceUnavailableError';
  }
}

export class ServiceTimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ServiceTimeoutError';
  }
}

export function callService(
  socketPath: string,
  request: ProtocolRequest,
  timeoutMilliseconds = 5000,
): Promise<ProtocolResponse> {
  if (typeof socketPath !== 'string' || socketPath.length === 0) {
    throw new TypeError('socketPath must be a non-empty string');
  }
  if (!Number.isFinite(timeoutMilliseconds) || timeoutMilliseconds <= 0) {
    throw new RangeError('timeoutMilliseconds must be positive');
  }
  const payload = `${encodeRequest(request)}\n`;
  if (Buffer.byteLength(payload, 'utf8') - 1 > MAX_PROTOCOL_MESSAGE_BYTES) {
    throw new RangeError('request exceeds 4 MiB');
  }

  return new Promise((resolve, reject) => {
    let socket: Socket | undefined;
    let settled = false;
    let response = Buffer.alloc(0);
    const finish = (error?: Error, value?: ProtocolResponse): void => {
      if (settled) return;
      settled = true;
      clearTimeout(deadline);
      socket?.destroy();
      if (error !== undefined) reject(error);
      else resolve(value as ProtocolResponse);
    };
    const deadline = setTimeout(() => {
      finish(new ServiceTimeoutError('service request exceeded its deadline'));
    }, timeoutMilliseconds);
    socket = createConnection({ path: socketPath });
    socket.setNoDelay(true);
    socket.once('connect', () => socket?.write(payload));
    socket.on('data', (chunk: Buffer) => {
      response = Buffer.concat([response, chunk]);
      const newline = response.indexOf(0x0a);
      if (newline >= 0) {
        if (newline > MAX_PROTOCOL_MESSAGE_BYTES) {
          finish(new ServiceUnavailableError('service response exceeded 4 MiB'));
          return;
        }
        try {
          finish(undefined, decodeResponse(response.subarray(0, newline), request));
        } catch (error) {
          finish(error instanceof Error ? error : new Error(String(error)));
        }
      } else if (response.byteLength > MAX_PROTOCOL_MESSAGE_BYTES) {
        finish(new ServiceUnavailableError('service response exceeded 4 MiB'));
      }
    });
    socket.once('error', (error: NodeJS.ErrnoException) => {
      const unavailable = new ServiceUnavailableError(
        `service is unavailable: ${error.message}`,
        { cause: error },
      );
      finish(unavailable);
    });
    socket.once('end', () => {
      if (!settled) finish(new ServiceUnavailableError('service closed before a complete response'));
    });
  });
}
