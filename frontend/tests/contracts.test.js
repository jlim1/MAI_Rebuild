import test from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/api.js';
import { LAST_ORDER_KEY, readOrderRef, saveOrderRef } from '../src/orderMemory.js';

function makeTestWindow() {
  const map = new Map();
  const win = {
    location: new URL('http://127.0.0.1:8000/'),
    localStorage: { getItem: k => map.get(k) ?? null, setItem: (k,v) => map.set(k,v), removeItem: k => map.delete(k) },
    history: { replaceState: (_, __, url) => { win.location = new URL(url); } },
  };
  return win;
}

test('hash overrides local ID; stale reset removes both and preserves the page query', () => {
  const win = makeTestWindow();
  win.location.search = '?desk=1';
  saveOrderRef('case #2',win);
  assert.equal(win.location.hash,'#order=case+%232');
  win.localStorage.setItem(LAST_ORDER_KEY,'previous');
  assert.deepEqual(readOrderRef(win),{id:'case #2',invalid:false});
  win.location.hash = '';
  assert.equal(readOrderRef(win).id,'previous');
  win.location.hash = '#order=..';
  assert.deepEqual(readOrderRef(win),{id:'',invalid:true});
  saveOrderRef('',win);
  assert.equal(win.location.search,'?desk=1');
  assert.equal(win.location.hash,'');
  assert.equal(win.localStorage.getItem(LAST_ORDER_KEY),null);
});

test('order ID survives refresh by hash alone when persistent storage is disabled', () => {
  const win = makeTestWindow();
  Object.defineProperty(win,'localStorage',{ get() { throw Error('Unavailable'); } });
  saveOrderRef('mock-3',win);
  assert.equal(readOrderRef(win).id,'mock-3');
  saveOrderRef('',win);
  assert.deepEqual(readOrderRef(win),{id:'',invalid:false});
});

test('an over-stock request reaches the API and preserves a shortage explanation', async t => {
  const spy = t.mock.method(globalThis,'fetch', async (url,options) => {
    assert.equal(url,'/api/orders');
    assert.equal(options.method,'POST');
    assert.deepEqual(JSON.parse(options.body),{sku:'ARC-01',quantity:3});
    return Response.json({detail:{message:'Only 2 available.'}},{status:409});
  });
  await assert.rejects(api.reserve('ARC-01',3),{status:409,message:'Only 2 available.'});
  assert.equal(spy.mock.callCount(),1);
});

test('advance supplies the viewed status once, with no automatic follow-up write', async t => {
  const result = {id:'order 1',status:'packed',lines:[{sku:'ARC-01',name:'Arc lamp',quantity:1}],events:[{status:'packed',at:'2026-01-01T12:00:00Z'}]};
  const spy = t.mock.method(globalThis,'fetch', async (url, options) => {
    assert.equal(url,'/api/orders/order%201/advance');
    assert.deepEqual(JSON.parse(options.body),{expected_status:'reserved'});
    return Response.json(result);
  });
  assert.deepEqual(await api.advance('order 1','reserved'),result);
  assert.equal(spy.mock.callCount(),1);
});

test('inventory query is encoded and malformed success is not shown as an empty shelf', async t => {
  t.mock.method(globalThis,'fetch', async url => {
    assert.equal(url,'/api/inventory?q=A%26B');
    return Response.json({error:'bad inventory'});
  });
  await assert.rejects(api.inventory('A&B'),/unreadable inventory/);
});
