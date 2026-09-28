require('dotenv').config();
const { Telegraf } = require('telegraf');

const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
  console.error('TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in.');
  process.exit(1);
}

const bot = new Telegraf(token);

bot.start((ctx) => ctx.reply('YoonSquads 봇에 연결되었습니다. /help 로 사용 가능한 명령어를 확인하세요.'));
bot.help((ctx) => ctx.reply('사용 가능한 명령어:\n/start - 봇 시작\n/help - 도움말'));

bot.catch((err, ctx) => {
  console.error(`Error while handling update ${ctx.update.update_id}:`, err);
});

bot.launch();
console.log('YoonSquads bot is running.');

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
