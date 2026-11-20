import React, { useEffect, useRef, useState } from 'react';
import { askMai, checkProviders, PROVIDERS, QUESTION_LIMIT } from './ask.js';
import { Icon, PanelTitle } from './graphics.jsx';
import './ask.css';

const SAMPLE_QUESTION = 'Which equipment is available to reserve?';

export function AskMai({ orderId }) {
  const [configured, setConfigured] = useState(null);
  const [provider, setProvider] = useState('');
  const [question, setQuestion] = useState('');
  const [approvedId, setApprovedId] = useState(null);
  const [reply, setReply] = useState(null);
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');
  const activeReq = useRef(null);
  const questionBox = useRef(null);
  const includedId = approvedId === orderId ? orderId : null;
  const canSend = !pending && configured?.[provider] === true && question.trim() && question.length <= QUESTION_LIMIT;
  const noKeysConfigured = configured && !configured.openai && !configured.anthropic;

  useEffect(() => { setApprovedId(null); }, [orderId]);
  useEffect(() => () => activeReq.current?.abort(), []);

  // Only explicit button actions enter here. Never replay a failed question.
  async function runAction(actionType, action) {
    if (activeReq.current) return;
    const controller = new AbortController();
    activeReq.current = controller;
    setPending(actionType); setError('');
    try { await action(controller.signal); }
    catch (err) {
      if (controller.signal.aborted) return;
      const genericMsg = actionType === 'checking' ? 'Could not check configuration. Check the local server, then check again.' : 'No answer received. Check the server configuration and vendor limits. Nothing was retried.';
      setError(err.status ? `${genericMsg} (HTTP ${err.status})` : err.message);
    } finally {
      if (!controller.signal.aborted) setPending('');
      activeReq.current = null;
    }
  }

  function onCheck() {
    runAction('checking', async signal => {
      setConfigured(null); setProvider(''); setApprovedId(null);
      const result = await checkProviders(signal);
      if (!signal.aborted) setConfigured(result);
    });
  }
  function onSend(event) {
    event.preventDefault();
    if (!canSend) return;
    runAction('sending', async signal => {
      setReply(null);
      const result = await askMai({ configured, provider, question, orderId: includedId }, signal);
      if (!signal.aborted) setReply({ ...result, question: question.trim(), orderId: includedId });
    });
  }
  function onClear() {
    setQuestion(''); setReply(null); setApprovedId(null); setProvider(''); setError('');
    questionBox.current?.focus();
  }

  return <section className="panel ask-mai" aria-labelledby="ask-title">
    <PanelTitle icon="slip" index="03" id="ask-title">Ask Mai</PanelTitle>
    <p className="ask-intro">Ask a question about the synthetic stock register. This optional tool uses an external AI provider; the rest of the workbench does not need one.</p>
    <form className="ask-form" onSubmit={onSend} autoComplete="off">
      <div className="ask-routing">
        <fieldset aria-describedby="provider-hint"><legend>Choose a provider</legend>
          <p className="hint" id="provider-hint">Check the local server settings, then choose where to send your question. A configured key has not been validated.</p>
          {Object.entries(PROVIDERS).map(([id, name]) => <label className="vendor-option" key={id}>
            <input type="radio" name="ask-provider" value={id} checked={provider === id} aria-label={name} aria-describedby={`status-${id}`} disabled={Boolean(pending) || configured?.[id] !== true} onChange={() => { setProvider(id); setApprovedId(null); setError(''); }}/>
            <span>{name}</span><small id={`status-${id}`}>{configured ? (configured[id] ? 'Configured' : 'Not configured') : 'Not checked'}</small>
          </label>)}
        </fieldset>
        <button className="secondary" type="button" disabled={Boolean(pending)} onClick={onCheck}>Check provider configuration</button>
        <p role="status" className="hint">{pending === 'checking' ? 'Checking local configuration…' : configured ? 'Configuration checked. No vendor was contacted by this check.' : ''}</p>
        {noKeysConfigured && <p className="notice">To enable Ask Mai, set <code>OPENAI_API_KEY</code> or <code>ANTHROPIC_API_KEY</code> on the server, restart it, and check again. Inventory and orders still work without keys.</p>}
      </div>
      <div className="ask-compose">
        <div className="ask-label"><label htmlFor="ask-question">Question</label><span className="mono hint" id="ask-count">{question.length} / {QUESTION_LIMIT}</span></div>
        <textarea ref={questionBox} id="ask-question" rows={3} maxLength={QUESTION_LIMIT} autoComplete="off" spellCheck={false} value={question} disabled={Boolean(pending)} aria-describedby="ask-count" placeholder="Ask about this demo’s equipment…" onChange={event => { setQuestion(event.target.value); setError(''); }}/>
        <button type="button" className="text-button" disabled={Boolean(pending)} onClick={() => { setQuestion(SAMPLE_QUESTION); questionBox.current?.focus(); }}>Use sample question</button>
        <label className="ask-consent"><input type="checkbox" checked={Boolean(includedId)} disabled={!orderId || !provider || Boolean(pending)} onChange={event => setApprovedId(event.target.checked ? orderId : null)}/><span>Include selected demo order{orderId && <>: <code>{orderId}</code></>}</span></label>
        <p className="hint">{orderId ? 'Unchecked sends inventory context only.' : 'Reserve or look up an order to make it available here.'}</p>
        <div className="ask-disclosure" id="ask-disclosure"><strong>Before you send</strong><p>Your question and synthetic inventory context{includedId ? ', including the selected demo order,' : ''} will go to {PROVIDERS[provider] || 'the provider you choose'} via the local server. Vendor charges may apply. Don’t enter secrets or personal information.</p></div>
        <div className="ask-actions"><button type="submit" className="primary" aria-describedby="ask-disclosure" disabled={!canSend}>Send question <Icon name="arrow" size={16}/></button><button type="button" className="text-button" disabled={Boolean(pending) || !(question || reply || error || provider)} onClick={onClear}>Clear exchange</button></div>
        <p role="status" className="hint">{pending === 'sending' ? `Waiting for ${PROVIDERS[provider]}…` : reply ? `Answer received from ${PROVIDERS[reply.provider]}.` : ''}</p>
      </div>
    </form>
    {error && <p className="notice error ask-result" role="alert">{error}</p>}
    {reply && <section className="ask-reply ask-result" aria-labelledby="reply-title"><div className="eyebrow">{PROVIDERS[reply.provider]} · AI RESPONSE</div><h3 id="reply-title">Answer</h3><p className="hint">Asked: {reply.question} · {reply.orderId ? `Demo order ${reply.orderId} included` : 'Inventory only'}</p><p className="answer-text">{reply.answer}</p></section>}
  </section>;
}
