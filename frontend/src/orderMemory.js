import { validId } from './api.js';

export const LAST_ORDER_KEY = 'parcel-workbench:last-order-id';

export function readOrderRef(win = window) {
  const hash = win.location.hash;
  const params = new URLSearchParams(hash.slice(1));
  let id = params.get('order');
  if (id === null) {
    try { id = win.localStorage.getItem(LAST_ORDER_KEY); } catch { /* Storage can be disabled. */ }
  }
  return { id: validId(id) ? id : '', invalid: id !== null && !validId(id) };
}

export function saveOrderRef(id, win = window) {
  try {
    if (id) win.localStorage.setItem(LAST_ORDER_KEY, id);
    else win.localStorage.removeItem(LAST_ORDER_KEY);
  } catch { /* The hash works without persistent storage. */ }
  const url = new URL(win.location.href);
  if (id) url.hash = new URLSearchParams({ order: id }).toString();
  else if (new URLSearchParams(url.hash.slice(1)).has('order')) url.hash = '';
  try { win.history.replaceState(win.history.state, '', url); } catch { /* Storage remains a fallback. */ }
}
