import { sendRequest, isValidId } from './api.js';

export const PROVIDERS = Object.freeze({ openai: 'OpenAI', anthropic: 'Anthropic' });
export const QUESTION_LIMIT = 800;

export async function checkProviders(signal) {
  const data = await sendRequest('/api/ask/providers', { signal });
  if (!data || Object.keys(PROVIDERS).some(name => typeof data[name] !== 'boolean')) {
    throw new Error('Cannot read the server’s provider configuration.');
  }
  return { openai: data.openai, anthropic: data.anthropic };
}

export async function askMai({ configured, provider, question, orderId = null }, signal) {
  if (!Object.hasOwn(PROVIDERS, provider) || configured?.[provider] !== true) {
    throw new Error('Select a configured provider first.');
  }
  if (typeof question !== 'string' || !question.trim() || question.length > QUESTION_LIMIT) {
    throw new Error(`Enter a question of 1–${QUESTION_LIMIT} characters.`);
  }
  if (orderId !== null && !isValidId(orderId)) throw new Error('Select a valid demo order.');
  const body = { provider, question: question.trim() };
  if (orderId !== null) body.order_id = orderId;
  const data = await sendRequest('/api/ask', {
    body, signal, timeoutMs: 90000,
    networkMessage: 'No answer received. The vendor may have processed this request; nothing was retried.',
  });
  if (data?.provider !== provider || typeof data.answer !== 'string' || !data.answer.trim()) {
    throw new Error('No usable answer was returned for the selected provider. Nothing was retried.');
  }
  return { provider, answer: data.answer };
}
