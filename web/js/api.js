// Thin API client. All state-changing calls carry the X-Kizuna-Client header
// (CSRF defence, see kizuna/web.py). Errors are thrown as ApiError.

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status; this.code = code; this.details = details;
  }
}

let onUnauthenticated = () => {};
export function setUnauthenticatedHandler(fn) { onUnauthenticated = fn; }

async function request(method, url, body, { raw = false, headers = {} } = {}) {
  const opts = { method, headers: { 'X-Kizuna-Client': 'web', ...headers }, credentials: 'same-origin' };
  if (body !== undefined && !(body instanceof Blob) && !(body instanceof File)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body !== undefined) {
    opts.body = body;
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    throw new ApiError(0, 'network', 'Cannot reach the Kizuna Forge server. Is it running?');
  }
  if (raw && res.ok) return res;
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) {
    const err = (data && data.error) || { code: 'http_' + res.status, message: res.statusText || 'Request failed' };
    if (res.status === 401 && !url.startsWith('/api/auth/')) onUnauthenticated();
    throw new ApiError(res.status, err.code, err.message, err.details);
  }
  return data;
}

export const api = {
  get: (url) => request('GET', url),
  post: (url, body = {}) => request('POST', url, body),
  put: (url, body = {}) => request('PUT', url, body),
  patch: (url, body = {}) => request('PATCH', url, body),
  del: (url) => request('DELETE', url),
  upload: (url, file) => request('PUT', url, file, { headers: { 'Content-Type': file.type || 'application/octet-stream' } }),
  text: async (url) => (await request('GET', url, undefined, { raw: true })).text(),
};
