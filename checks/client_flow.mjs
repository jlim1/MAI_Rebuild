import assert from 'node:assert/strict';
import { api } from '../frontend/src/api.js';
import { checkProviders, askMai } from '../frontend/src/ask.js';

const origin = process.argv[2];
assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
const fetchLocally = globalThis.fetch;
globalThis.fetch = (path, options) => {
  const url = new URL(path, origin);
  assert.equal(url.origin, origin);
  return fetchLocally(url, { ...options, headers: { ...options.headers, Origin: origin } });
};

const [lamp] = await api.inventory('ARC-01');
assert.equal(lamp.available, 2);
const order = await api.reserve(lamp.sku, 1);
await assert.rejects(api.reserve(lamp.sku, 2), { status: 409 });
const configured = await checkProviders();
assert.deepEqual(configured, { openai: true, anthropic: true });
for (const [provider, answer] of [['openai', 'one available'], ['anthropic', 'one reserved']]) {
  assert.deepEqual(await askMai({ configured, provider, question: 'How many lamps?', orderId: order.id }),
    { provider, answer });
}
let current = await api.order(order.id);
for (const status of ['packed', 'shipped', 'delivered']) {
  current = await api.advance(order.id, current.status);
  assert.equal(current.status, status);
}
assert.deepEqual((await api.order(order.id)).events.map(event => event.status),
  ['reserved', 'packed', 'shipped', 'delivered']);
const [after] = await api.inventory(lamp.sku);
assert.deepEqual([after.on_hand, after.reserved, after.available], [1, 0, 1]);
