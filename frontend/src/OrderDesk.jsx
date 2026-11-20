import React from 'react';
import { STATUSES } from './api.js';
import { Icon, PanelTitle } from './graphics.jsx';

const titleCase = value => value[0].toUpperCase() + value.slice(1);
const DATE_FORMAT = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit', timeZoneName: 'short' });
function EventTime({ at }) {
  const date = new Date(at);
  return Number.isNaN(date.valueOf()) ? <small>{at}</small> : <time dateTime={at}>{DATE_FORMAT.format(date)}</time>;
}

export function OrderDesk({ order, draft, setDraft, busy, lookup, advance, notice, reset }) {
  const step = STATUSES.indexOf(order?.status);
  const nextStatus = order && STATUSES[step + 1];
  return <section className="panel orders" aria-labelledby="order-title">
    <PanelTitle icon="slip" index="02" id="order-title">Order desk</PanelTitle>
    <form className="lookup" onSubmit={event => { event.preventDefault(); lookup(draft.trim()); }}><label htmlFor="order-id">Order ID</label><div className="lookup-row"><input id="order-id" type="text" autoComplete="off" spellCheck="false" placeholder="Enter an order ID" value={draft} required maxLength="256" onChange={e => setDraft(e.target.value)} disabled={Boolean(busy)}/><button className="secondary" disabled={Boolean(busy)}>Look up order</button></div></form>
    {notice && <div className={`notice ${notice.error ? 'error' : ''}`} role={notice.error ? 'alert' : 'status'}>{notice.text}</div>}
    {busy === 'loading' ? <p className="empty-block" role="status">Loading order…</p> : !order ? <div className="blank-docket"><div className="docket-sketch" aria-hidden="true"><i/><Icon name="slip" size={30}/><i/></div><h3>No order selected</h3><p>Reserve equipment or look up an order to see its fulfillment timeline.</p></div> : <>
      <div className="docket"><div className="docket-heading"><div className="eyebrow">RESERVATION RECORD</div><span className="order-badge">{titleCase(order.status)}</span></div><p className="order-number mono" aria-label={`Order ${order.id}`}>{order.id}</p>
        <ul className="lines" aria-label="Reserved equipment">{order.lines.map((line, index) => <li key={`${line.sku}:${index}`}><span><strong>{line.name}</strong><small className="mono">{line.sku}</small></span><span><span className="sr-only">Quantity </span>× {line.quantity}</span></li>)}</ul>
      </div>
      <div className="timeline-wrap"><div className="timeline-heading"><h3 id="timeline-title">Fulfillment timeline</h3><span className="mono">0{step + 1} / 04</span></div>
        <ol aria-labelledby="timeline-title" className="timeline">{STATUSES.map((status,index) => {
          const at = order.events.find(event => event.status === status)?.at;
          return <li key={status} className={index <= step ? 'done' : ''} aria-current={index === step ? 'step' : undefined}><span className="node" aria-hidden="true">{index <= step ? <Icon name="check" size={12}/> : index + 1}</span><div><strong>{titleCase(status)}</strong>{at ? <EventTime at={at}/> : <small>{index <= step ? 'No event time supplied' : 'Pending'}</small>}</div></li>;
        })}</ol>
        {nextStatus ? <><button className="primary next" disabled={Boolean(busy)} onClick={advance}>{busy === 'advancing' ? 'Updating order…' : `Mark as ${nextStatus}`}<Icon name="arrow" size={17}/></button><p className="timeline-note">Presenter-controlled. One step per click.</p></> : <p className="complete"><Icon name="check" size={16}/> Simulated fulfillment complete</p>}
        <button type="button" className="text-button" onClick={reset} disabled={Boolean(busy)}>Clear selected order</button>
      </div>
    </>}
  </section>;
}
