require('dotenv').config();
const { Telegraf } = require('telegraf');
const cron = require('node-cron');
const { buildNewsSource } = require('./newsSource');
const seenStore = require('./seenStore');

const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
  console.error('TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in.');
  process.exit(1);
}

const chatId = process.env.TELEGRAM_CHAT_ID;

let newsSource;
try {
  newsSource = buildNewsSource();
} catch (err) {
  console.error(err.message);
  process.exit(1);
}

const bot = new Telegraf(token);
const seen = seenStore.load();

function formatNewsItem(item) {
  return `📰 ${item.title}\n${item.link}`;
}

async function checkForNews() {
  const items = await newsSource.fetchLatestNews(20);
  const freshItems = items.filter((item) => !seen.has(item.id)).reverse();

  freshItems.forEach((item) => seen.add(item.id));
  if (freshItems.length > 0) {
    seenStore.save(seen);
  }

  if (!chatId) {
    return;
  }
  for (const item of freshItems) {
    await bot.telegram.sendMessage(chatId, formatNewsItem(item));
  }
}

bot.start((ctx) => ctx.reply('YoonSquads 봇에 연결되었습니다. /help 로 사용 가능한 명령어를 확인하세요.'));
bot.help((ctx) => ctx.reply('사용 가능한 명령어:\n/start - 봇 시작\n/help - 도움말\n/news - 최신 뉴스 확인'));

bot.command('news', async (ctx) => {
  try {
    const items = await newsSource.fetchLatestNews(5);
    if (items.length === 0) {
      await ctx.reply('가져올 수 있는 뉴스가 없습니다.');
      return;
    }
    await ctx.reply(items.map(formatNewsItem).join('\n\n'));
  } catch (err) {
    console.error('Failed to fetch news:', err);
    await ctx.reply('뉴스를 가져오는 중 오류가 발생했습니다.');
  }
});

bot.catch((err, ctx) => {
  console.error(`Error while handling update ${ctx.update.update_id}:`, err);
});

bot.launch();
console.log('YoonSquads bot is running.');
console.log(`News source: ${newsSource.description}`);

if (chatId) {
  cron.schedule('*/30 * * * *', () => {
    checkForNews().catch((err) => console.error('Failed to check news feed:', err));
  });
  console.log('News feed polling every 30 minutes.');
} else {
  console.warn('TELEGRAM_CHAT_ID is not set. Scheduled news alerts are disabled; /news command still works.');
}

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
