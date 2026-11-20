import React, { useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { Icon, PanelTitle } from './graphics.jsx';

function ReserveDialog({ item, onClose, onSuccess, onRefresh }) {
  const dialogRef = useRef(null);
  const submitLock = useRef(false);
  const [quantity, setQuantity] = useState('1');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    if (submitLock.current) return;
    const count = Number(quantity);
    if (!Number.isSafeInteger(count) || count < 1) {
      setError('Enter a positive whole number.');
      return;
    }
    submitLock.current = true;
    setBusy(true);
    setError('');
    try {
      const order = await api.reserve(item.sku, count);
      onSuccess(order);
    } catch (err) {
      const shortage = [400, 409, 422].includes(err.status) && (count > item.available || /stock|available|shortage|insufficient/i.test(err.message));
      setError(`${shortage ? 'Not enough stock. ' : ''}${err.message}`);
      onRefresh();
    } finally {
      submitLock.current = false;
      setBusy(false);
    }
  }

  return <dialog ref={dialogRef} aria-labelledby="reserve-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={onSubmit}>
      <div className="eyebrow accent">RESERVATION / SIMULATED</div>
      <h2 id="reserve-title">Reserve equipment</h2>
      <div className="picked"><Icon name="box" size={28}/><div><strong>{item.name}</strong><small className="mono">{item.sku}</small></div><span className="stock-tag">{item.available} available</span></div>
      <label htmlFor="quantity">Quantity</label>
      <input autoFocus id="quantity" type="number" inputMode="numeric" min="1" step="1" required value={quantity} onChange={e => { setQuantity(e.target.value); setError(''); }} disabled={busy} aria-describedby="quantity-hint"/>
      <p className="hint" id="quantity-hint">To demonstrate a shortage, request more units than are available. The local API checks every request.</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="dialog-actions"><button type="button" className="secondary" onClick={onClose} disabled={busy}>Cancel</button><button className="primary" disabled={busy}>{busy ? 'Submitting…' : 'Confirm reservation'}<Icon name="arrow" size={16}/></button></div>
    </form>
  </dialog>;
}

export function Inventory({ refreshKey, onRefresh, onReserved, orderBusy }) {
  const [query, setQuery] = useState('');
  const [state, setState] = useState({ phase: 'loading', rows: [] });
  const [selected, setSelected] = useState(null);
  const searchBox = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    setState({ phase: 'loading', rows: [] });
    const timer = setTimeout(async () => {
      try {
        const rows = await api.inventory(query.trim(), controller.signal);
        if (!controller.signal.aborted) setState({ phase: 'ready', rows });
      } catch (error) {
        if (!controller.signal.aborted) setState({ phase: 'error', rows: [], message: error.message });
      }
    }, query ? 180 : 0);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [query, refreshKey]);
  const { rows, phase } = state;
  function clearSearch() { setQuery(''); searchBox.current?.focus(); }
  return <section className="panel inventory" aria-labelledby="inventory-title">
    <PanelTitle icon="stock" index="01" id="inventory-title" action={<button className="icon-button" aria-label="Refresh inventory" title="Refresh inventory" onClick={onRefresh}><Icon name="refresh" size={17}/></button>}>Equipment inventory</PanelTitle>
    <div className="search-wrap"><label htmlFor="inventory-query">Search inventory</label><div className="search-field"><Icon name="search" size={19}/><input ref={searchBox} id="inventory-query" type="search" autoComplete="off" placeholder="Item name or SKU" value={query} onChange={e => setQuery(e.target.value)}/>{query && <button className="mini-icon" aria-label="Clear search" onClick={clearSearch}><Icon name="close" size={16}/></button>}</div></div>
    <div className="ledger-strip"><span>STOCK REGISTER</span><span role="status">{phase === 'ready' ? `${rows.length} ${rows.length === 1 ? 'ITEM' : 'ITEMS'}` : '—'}</span></div>
    {phase === 'loading' ? <p className="empty-block" role="status">Loading inventory…</p> : phase === 'error' ? <div className="panel-message"><p className="notice error" role="alert">{state.message}</p><button className="secondary" onClick={onRefresh}>Retry inventory</button></div> : rows.length === 0 ? <div className="empty-block" role="status"><Icon name="search" size={27}/><h3>{query ? 'No matching equipment' : 'No equipment yet'}</h3><p>{query ? 'Try a different name or SKU.' : 'The local inventory is empty.'}</p></div> :
      <ul className="equipment-list" aria-label="Inventory results">{rows.map(item => <li key={item.sku}>
        <div className="item-heading"><span className="sku mono">{item.sku}</span><span className={`stock-tag ${item.available === 0 ? 'zero' : ''}`}><span className="dot"/>{item.available ? 'In stock' : 'Out of stock'}</span></div>
        <h3>{item.name}</h3><div className="item-bottom"><dl className="counts">{[['On hand',item.on_hand],['Reserved',item.reserved],['Available',item.available]].map(([key,value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
        <button className="reserve" disabled={orderBusy} aria-label={`Reserve ${item.name}`} onClick={() => setSelected(item)}>Reserve <Icon name="arrow" size={16}/></button></div>
      </li>)}</ul>}
    {selected && <ReserveDialog item={rows.find(row => row.sku === selected.sku) || selected} onClose={() => setSelected(null)} onRefresh={onRefresh} onSuccess={order => { setSelected(null); onReserved(order); }}/>}
  </section>;
}
