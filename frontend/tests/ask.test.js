import test from 'node:test';
import assert from 'node:assert/strict';
import { askMai, checkProviders } from '../src/ask.js';

const configured = { openai: true, anthropic: false };
const prompt = { configured, provider: 'openai', question: 'Which items are available?' };

test('configuration check uses only the local GET and requires real booleans', async t => {
  let data = { openai: false, anthropic: false };
  const spy = t.mock.method(globalThis, 'fetch', async (path, opts) => {
    assert.equal(path, '/api/ask/providers');
    assert.equal(opts.method, 'GET');
    return Response.json(data);
  });
  assert.deepEqual(await checkProviders(), data);
  data = { openai: 'false', anthropic: true };
  await assert.rejects(checkProviders(), /configuration/);
  assert.equal(spy.mock.callCount(), 2);
});

test('invalid provider, question or order never initiates a request', async t => {
  const spy = t.mock.method(globalThis, 'fetch', () => assert.fail('unexpected request'));
  for (const override of [{ provider: '' }, { provider: 'other' }, { provider: 'anthropic' }, { configured: null }, { question: '  ' }, { question: 'x'.repeat(801) }, { orderId: '../' }]) {
    await assert.rejects(askMai({ ...prompt, ...override }));
  }
  assert.equal(spy.mock.callCount(), 0);
});

test('send omits unapproved context; approved ID and exact-length question are accepted', async t => {
  const bodies = [];
  const answer = '<em>Only synthetic fixtures.</em>\nNo transactions performed.';
  t.mock.method(globalThis, 'fetch', async (path, opts) => {
    assert.equal(path, '/api/ask');
    assert.equal(opts.method, 'POST');
    assert.equal(opts.cache, 'no-store');
    bodies.push(JSON.parse(opts.body));
    return Response.json({ provider: 'openai', answer });
  });
  assert.deepEqual(await askMai(prompt), { provider: 'openai', answer });
  const question = 'Q'.repeat(800);
  await askMai({ ...prompt, question, orderId: 'DEMO-1' });
  assert.deepEqual(bodies, [{ provider: 'openai', question: prompt.question }, { provider: 'openai', question, order_id: 'DEMO-1' }]);
});

test('vendor failure or mismatched provider does not trigger a retry or fallback', async t => {
  const both = { openai: true, anthropic: true };
  let status = 503;
  const spy = t.mock.method(globalThis, 'fetch', async () => Response.json({ provider: 'anthropic', answer: 'wrong route' }, { status }));
  await assert.rejects(askMai({ ...prompt, configured: both }), { status: 503 });
  assert.equal(spy.mock.callCount(), 1);
  status = 200;
  await assert.rejects(askMai({ ...prompt, configured: both }), /selected provider/);
  assert.equal(spy.mock.callCount(), 2);
});
