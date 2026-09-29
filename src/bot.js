require('dotenv').config();
const { Telegraf } = require('telegraf');
const { searchNews, stripTags } = require('./naverSearch');

const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
  console.error('TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in.');
  process.exit(1);
}

const bot = new Telegraf(token);

bot.start((ctx) => ctx.reply('YoonSquads 봇에 연결되었습니다. /help 로 사용 가능한 명령어를 확인하세요.'));
bot.help((ctx) =>
  ctx.reply(
    '사용 가능한 명령어:\n' +
      '/start - 봇 시작\n' +
      '/help - 도움말\n' +
      '/뉴스 <검색어> - 네이버 뉴스 검색'
  )
);

bot.command('뉴스', async (ctx) => {
  const query = ctx.message.text.split(' ').slice(1).join(' ').trim();
  if (!query) {
    return ctx.reply('검색어를 입력하세요. 예: /뉴스 맛집');
  }

  try {
    const result = await searchNews(query);
    if (!result.items || result.items.length === 0) {
      return ctx.reply('검색 결과가 없습니다.');
    }

    const lines = result.items.map((item, i) => `${i + 1}. ${stripTags(item.title)}\n${item.link}`);
    await ctx.reply(`[뉴스] "${query}" 검색 결과\n\n${lines.join('\n\n')}`);
  } catch (err) {
    console.error('뉴스 search failed:', err);
    await ctx.reply('검색 중 오류가 발생했습니다.');
  }
});

bot.catch((err, ctx) => {
  console.error(`Error while handling update ${ctx.update.update_id}:`, err);
});

bot.launch();
console.log('YoonSquads bot is running.');

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
