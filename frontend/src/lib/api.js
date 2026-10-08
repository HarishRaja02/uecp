const API_HOST = (typeof window !== 'undefined' && window.location.hostname) || 'localhost';
const isDevStandalone = typeof window !== 'undefined' && (window.location.port === '5174' || window.location.port === '5173');
export const API_BASE = import.meta.env.VITE_API_URL || (isDevStandalone ? `http://${API_HOST}:8001/api/v1` : '/api/v1');
const BASE = API_BASE;

let accessToken = null;
let refreshPromise = null;

// In-memory cache for fast tab navigation and instant responses
const apiCache = new Map();
const inFlightRequests = new Map();

export function clearApiCache() {
  apiCache.clear();
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = fetch(BASE + '/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Session expired');
        const value = await response.json();
        accessToken = value.access_token;
        if (typeof window !== 'undefined') localStorage.setItem('uecp_logged_in', '1');
        return value;
      })
      .catch((err) => {
        if (typeof window !== 'undefined') localStorage.removeItem('uecp_logged_in');
        throw err;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export function clearAccessToken() {
  accessToken = null;
  apiCache.clear();
  if (typeof window !== 'undefined') localStorage.removeItem('uecp_logged_in');
}

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const isGet = method === 'GET';
  const cacheKey = path;
  const ttl = options.ttl ?? 15000; // 15 seconds cache by default for GET

  // Mutation automatically busts GET cache
  if (!isGet) {
    apiCache.clear();
  }

  // Check cache for GET requests unless force fresh is requested
  if (isGet && !options.fresh) {
    const cached = apiCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < ttl) {
      return cached.data;
    }
  }

  // Deduplicate identical in-flight GET requests
  if (isGet && inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey);
  }

  const exec = async () => {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }

    let r = await fetch(BASE + path, { ...options, headers, credentials: 'include' });

    if (r.status === 401 && path !== '/auth/refresh' && path !== '/auth/login') {
      try {
        await refreshAccessToken();
        headers.set('Authorization', `Bearer ${accessToken}`);
        r = await fetch(BASE + path, { ...options, headers, credentials: 'include' });
      } catch (error) {
        clearAccessToken();
        throw error;
      }
    }

    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(body.message || body.error || 'Request failed');
    }

    if (isGet) {
      apiCache.set(cacheKey, { timestamp: Date.now(), data: body });
    }

    return body;
  };

  if (isGet) {
    const promise = exec().finally(() => {
      inFlightRequests.delete(cacheKey);
    });
    inFlightRequests.set(cacheKey, promise);
    return promise;
  }

  return exec();
}

export async function login(email, password) {
  const x = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  accessToken = x.access_token;
  if (typeof window !== 'undefined') localStorage.setItem('uecp_logged_in', '1');
  return x;
}

export async function refresh() {
  const x = await api('/auth/refresh', { method: 'POST' });
  accessToken = x.access_token;
  if (typeof window !== 'undefined') localStorage.setItem('uecp_logged_in', '1');
  return x;
}

export async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' });
  } finally {
    clearAccessToken();
  }
}

