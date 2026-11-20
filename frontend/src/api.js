const STATUSES = ['reserved', 'packed', 'shipped', 'delivered'];
export { STATUSES };
const text = value => typeof value === 'string' && value.trim().length > 0;
const units = value => Number.isSafeInteger(value) && value >= 0;
export const validId = id => text(id) && id.length <= 256 && !/[\x00-\x1f\x7f/\\]/.test(id) && id !== '.' && id !== '..';

function inventory(data) {
  if (!Array.isArray(data) || !data.every(row => row && text(row.sku) && text(row.name) &&
    ['on_hand', 'reserved', 'available'].every(field => units(row[field])))) {
    throw new Error('The local API returned an unreadable inventory.');
  }
  return data;
}

function order(data) {
  const id = Number.isSafeInteger(data?.id) ? String(data.id) : data?.id;
  if (!validId(id) || !STATUSES.includes(data.status) || !Array.isArray(data.lines) ||
    !data.lines.every(row => row && text(row.sku) && text(row.name) && units(row.quantity)) ||
    !Array.isArray(data.events) || !data.events.every(event => event && STATUSES.includes(event.status) && text(event.at))) {
    throw new Error('The local API returned an unreadable order. Look it up before trying again.');
  }
  return { ...data, id };
}

function detail(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map(detail).filter(Boolean).join('; ');
  return value && typeof value === 'object' ? detail(value.detail ?? value.message ?? value.msg ?? value.error ?? value.code) : '';
}

export async function request(path, { body, signal, timeoutMs = 15000, networkMessage } = {}) {
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
      const message = detail(data) || `The local API returned HTTP ${response.status}.`;
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

function orderPath(id) {
  if (!validId(id)) throw new Error('Enter a valid order ID.');
  return `/api/orders/${encodeURIComponent(id)}`;
}

export const api = {
  inventory: (query, signal) => request(`/api/inventory?${new URLSearchParams({ q: query })}`, { signal }).then(inventory),
  reserve: (sku, quantity) => request('/api/orders', { body: { sku, quantity } }).then(order),
  order: (id, signal) => request(orderPath(id), { signal }).then(order),
  advance: (id, status) => request(`${orderPath(id)}/advance`, { body: { expected_status: status } }).then(order),
};
