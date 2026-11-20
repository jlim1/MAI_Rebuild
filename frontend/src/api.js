const STATUSES = ['reserved', 'packed', 'shipped', 'delivered'];
export { STATUSES };
const isText = value => typeof value === 'string' && value.trim().length > 0;
const isCount = value => Number.isSafeInteger(value) && value >= 0;
export const isValidId = id => isText(id) && id.length <= 256 && !/[\x00-\x1f\x7f/\\]/.test(id) && id !== '.' && id !== '..';

function validateInventory(data) {
  if (!Array.isArray(data) || !data.every(row => row && isText(row.sku) && isText(row.name) &&
    ['on_hand', 'reserved', 'available'].every(field => isCount(row[field])))) {
    throw new Error('The local API returned an unreadable inventory.');
  }
  return data;
}

function validateOrder(data) {
  const id = Number.isSafeInteger(data?.id) ? String(data.id) : data?.id;
  if (!isValidId(id) || !STATUSES.includes(data.status) || !Array.isArray(data.lines) ||
    !data.lines.every(row => row && isText(row.sku) && isText(row.name) && isCount(row.quantity)) ||
    !Array.isArray(data.events) || !data.events.every(event => event && STATUSES.includes(event.status) && isText(event.at))) {
    throw new Error('The local API returned an unreadable order. Look it up before trying again.');
  }
  return { ...data, id };
}

function getErrorDetail(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map(getErrorDetail).filter(Boolean).join('; ');
  return value && typeof value === 'object' ? getErrorDetail(value.detail ?? value.message ?? value.msg ?? value.error ?? value.code) : '';
}

export async function sendRequest(path, { body, signal, timeoutMs = 15000, networkMessage } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(abort, timeoutMs);
  try {
    const response = await fetch(path, {
      method: body ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error',
      signal: controller.signal,
      headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
      ...(body && { body: JSON.stringify(body) }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = getErrorDetail(data) || `The local API returned HTTP ${response.status}.`;
      throw Object.assign(new Error(message), { status: response.status });
    }
    return data;
  } catch (error) {
    if (error.status || signal?.aborted) throw error;
    throw new Error(networkMessage ?? (body ? 'No confirmation from the local API. Check the order or stock before retrying.' : 'Cannot reach the local API. Check that the local server is running, then retry.'));
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

function getOrderPath(id) {
  if (!isValidId(id)) throw new Error('Enter a valid order ID.');
  return `/api/orders/${encodeURIComponent(id)}`;
}

export const api = {
  inventory: (query, signal) => sendRequest(`/api/inventory?${new URLSearchParams({ q: query })}`, { signal }).then(validateInventory),
  reserve: (sku, quantity) => sendRequest('/api/orders', { body: { sku, quantity } }).then(validateOrder),
  order: (id, signal) => sendRequest(getOrderPath(id), { signal }).then(validateOrder),
  advance: (id, status) => sendRequest(`${getOrderPath(id)}/advance`, { body: { expected_status: status } }).then(validateOrder),
};
