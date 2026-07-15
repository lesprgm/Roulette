export class GenerationHttpError extends Error {
  constructor(
    readonly status: number,
    readonly payload: any,
  ) {
    super(`Generate failed (${status})`);
  }
}

function authHeaders(): Record<string, string> {
  const appWindow = window as Window & { API_KEY?: string };
  const apiKey = String(appWindow.API_KEY || document.body.dataset.apiKey || '');
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (apiKey) headers['x-api-key'] = apiKey;
  return headers;
}

async function errorPayload(response: Response): Promise<any> {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { error: text || response.statusText };
  }
}

export async function generateOnce(seed: number): Promise<any> {
  const response = await fetch('/generate', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ brief: '', seed }),
  });
  if (!response.ok) throw new GenerationHttpError(response.status, await errorPayload(response));
  return response.json();
}

export async function streamGeneration(
  seed: number,
  signal: AbortSignal,
  onEvent: (event: string, data: any) => Promise<void>,
  onActivity: () => void,
): Promise<void> {
  const response = await fetch('/generate/stream', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ brief: '', seed }),
    signal,
  });
  if (!response.ok) throw new GenerationHttpError(response.status, await errorPayload(response));

  const reader = response.body?.getReader();
  if (!reader) throw new Error('Generation stream has no response body.');

  const decoder = new TextDecoder();
  let buffer = '';
  let currentEvent = '';
  onActivity();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onActivity();
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith('event: ')) {
        currentEvent = trimmed.slice(7);
        continue;
      }
      try {
        if (trimmed.startsWith('data: ')) {
          await onEvent(currentEvent, JSON.parse(trimmed.slice(6)));
        } else if (trimmed.startsWith('{')) {
          const payload = JSON.parse(trimmed);
          if (payload?.event) await onEvent(payload.event, payload.data ?? payload);
        }
      } catch (error) {
        console.warn('[ndw] generation stream parse error', error);
      }
    }
  }
}
