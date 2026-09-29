const Anthropic = require('@anthropic-ai/sdk');

const apiKey = process.env.ANTHROPIC_API_KEY;
const model = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5';
const MAX_HISTORY = 20;

const client = apiKey ? new Anthropic({ apiKey }) : null;
const histories = new Map();

function isEnabled() {
  return Boolean(client);
}

function getHistory(chatId) {
  if (!histories.has(chatId)) {
    histories.set(chatId, []);
  }
  return histories.get(chatId);
}

function resetHistory(chatId) {
  histories.set(chatId, []);
}

async function reply(chatId, text) {
  const history = getHistory(chatId);
  history.push({ role: 'user', content: text });

  const response = await client.messages.create({
    model,
    max_tokens: 1024,
    messages: history,
  });

  const answer = response.content
    .filter((block) => block.type === 'text')
    .map((block) => block.text)
    .join('\n');

  history.push({ role: 'assistant', content: answer });
  while (history.length > MAX_HISTORY) {
    history.shift();
  }

  return answer;
}

module.exports = { isEnabled, reply, resetHistory };
