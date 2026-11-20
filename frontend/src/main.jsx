import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, validId } from './api.js';
import { readOrderRef, saveOrderRef } from './orderMemory.js';
import { CaseDrawing, Icon } from './graphics.jsx';
import { Inventory } from './Inventory.jsx';
import { OrderDesk } from './OrderDesk.jsx';
import { AskMai } from './AskMai.jsx';
import './style.css';

function App() {
  const [revision, setRevision] = useState(0);
  const [order, setOrder] = useState(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const active = useRef(null);
  const writeLock = useRef(false);
  const refresh = () => setRevision(n => n + 1);

  const showOrder = useCallback((data, message) => {
    setOrder(data); setDraft(data.id); saveOrderRef(data.id);
    setNotice({ text: message }); setBusy('');
  }, []);

  const clear = useCallback(message => {
    active.current?.abort(); active.current = null;
    setOrder(null); setDraft(''); setBusy(''); saveOrderRef('');
    setNotice(message ? { text: message } : null);
  }, []);

  const lookup = useCallback(async (id, restore = false) => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    if (!validId(id)) { setBusy(''); setNotice({ error: true, text: 'Enter a valid order ID.' }); return; }
    setOrder(null); setNotice(null); setBusy('loading'); setDraft(id);
    try {
      const data = await api.order(id, controller.signal);
      if (!controller.signal.aborted) showOrder(data, restore ? 'Last selected order restored.' : 'Order loaded.');
    } catch (err) {
      if (controller.signal.aborted) return;
      if ([404, 410, 422].includes(err.status)) {
        clear(restore ? 'Saved order no longer exists. Its reference was cleared; you can start a new reservation.' : 'Order not found. Check the ID or create a new reservation.');
      } else { setBusy(''); setNotice({ error: true, text: `${err.message} Use Look up order to retry.` }); }
    }
  }, [clear, showOrder]);

  useEffect(() => {
    function restore() {
      const ref = readOrderRef();
      if (ref.id) lookup(ref.id, true);
      else clear(ref.invalid ? 'Invalid saved order ID cleared. You can start a new reservation.' : '');
    }
    restore(); window.addEventListener('hashchange', restore);
    return () => { active.current?.abort(); window.removeEventListener('hashchange', restore); };
  }, [lookup, clear]);

  async function advance() {
    if (!order || busy || writeLock.current) return;
    writeLock.current = true;
    active.current?.abort();
    const op = new AbortController(); active.current = op;
    setBusy('advancing'); setNotice(null);
    try {
      const data = await api.advance(order.id, order.status);
      refresh();
      if (!op.signal.aborted) showOrder(data, `Order marked as ${data.status}.`);
    } catch (err) {
      if (op.signal.aborted) return;
      if ([404, 410].includes(err.status)) { clear('Order no longer exists. Its reference was cleared.'); return; }
      // Do not offer another write on an unconfirmed or out-of-date status.
      setOrder(null); setDraft(order.id); setBusy('');
      setNotice({ error: true, text: `${err.message} Use Look up order to reload its current status.` });
    } finally { writeLock.current = false; }
  }

  function reserved(data) {
    active.current?.abort();
    showOrder(data, 'Reservation confirmed. Your order is ready to pack.'); refresh();
    requestAnimationFrame(() => document.getElementById('order-title')?.focus());
  }

  return <>
    <a className="skip" href="#main" onClick={event => { event.preventDefault(); document.getElementById('main').focus(); }}>Skip to workbench</a>
    <header className="mast"><div className="frame mast-inner"><div className="brand"><span className="brand-icon"><Icon name="box" size={23}/></span>Parcel Workbench</div><span className="sim-flag"><i/>Local simulation</span></div></header>
    <main id="main" tabIndex={-1} className="frame"><div className="hero"><div className="intro"><div className="eyebrow hero-kicker"><span/>EQUIPMENT OPERATIONS</div><h1>Dispatch desk<span>.</span></h1><p>Find equipment, reserve stock, and guide a simulated order from shelf to delivery.</p></div><CaseDrawing/></div>
      <div className="stations"><Inventory revision={revision} onRefresh={refresh} onReserved={reserved} orderBusy={Boolean(busy)}/><OrderDesk order={order} draft={draft} setDraft={setDraft} busy={busy} lookup={lookup} advance={advance} notice={notice} reset={() => { clear('Selected order cleared.'); document.getElementById('order-id')?.focus(); }}/></div>
      <AskMai orderId={order?.id ?? null}/>
    </main>
    <footer className="frame footer"><span><b>PW</b> / Parcel Workbench</span><span>Synthetic equipment · No real shipments</span></footer>
  </>;
}

createRoot(document.getElementById('root')).render(<App/>);
