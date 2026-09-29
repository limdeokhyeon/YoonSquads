// 텔레그램 사진(+캡션) → 확인 버튼 → 인스타그램 게시
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { Markup } = require('telegraf');
const { createInstagramClient } = require('./instagram');
const { startMediaServer } = require('./mediaServer');

const CAPTION_LIMIT = 2200;

function loadConfig(env = process.env) {
  if (!env.INSTAGRAM_USER_ID || !env.INSTAGRAM_ACCESS_TOKEN) return null;

  const allowed = (env.TELEGRAM_ALLOWED_USER_IDS || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)
    .map(Number);
  if (allowed.length === 0) {
    throw new Error('TELEGRAM_ALLOWED_USER_IDS must be set to enable Instagram posting.');
  }
  if (!env.PUBLIC_BASE_URL) {
    throw new Error('PUBLIC_BASE_URL must be set to enable Instagram posting.');
  }

  return {
    allowed: new Set(allowed),
    publicBaseUrl: env.PUBLIC_BASE_URL.replace(/\/+$/, ''),
    mediaDir: path.resolve(env.MEDIA_DIR || 'media'),
    mediaPort: Number(env.MEDIA_PORT || 8080),
    client: createInstagramClient({
      userId: env.INSTAGRAM_USER_ID,
      accessToken: env.INSTAGRAM_ACCESS_TOKEN,
      version: env.INSTAGRAM_GRAPH_VERSION || 'v21.0',
    }),
  };
}

// 설정이 없으면 false 를 반환하고 아무것도 등록하지 않는다.
function registerInstagramPoster(bot, env = process.env) {
  const config = loadConfig(env);
  if (!config) return false;

  startMediaServer(config.mediaDir, config.mediaPort);
  const pending = new Map();

  const discard = (job) => job && fs.rmSync(path.join(config.mediaDir, job.filename), { force: true });

  bot.on('photo', async (ctx) => {
    if (!config.allowed.has(ctx.from.id)) return;

    const caption = ctx.message.caption || '';
    if (caption.length > CAPTION_LIMIT) {
      await ctx.reply(`캡션이 너무 깁니다. (${caption.length}/${CAPTION_LIMIT}자)`);
      return;
    }

    const photo = ctx.message.photo[ctx.message.photo.length - 1]; // 가장 큰 해상도
    const link = await ctx.telegram.getFileLink(photo.file_id);
    const res = await fetch(link);
    if (!res.ok) throw new Error(`Telegram file download failed: ${res.status}`);

    const id = crypto.randomUUID();
    const filename = `${id}.jpg`;
    fs.writeFileSync(path.join(config.mediaDir, filename), Buffer.from(await res.arrayBuffer()));
    pending.set(id, { filename, caption, userId: ctx.from.id });

    await ctx.reply(
      `인스타그램에 게시할까요?\n\n캡션: ${caption || '(없음)'}`,
      Markup.inlineKeyboard([
        Markup.button.callback('✅ 게시', `ig_post:${id}`),
        Markup.button.callback('❌ 취소', `ig_cancel:${id}`),
      ])
    );
  });

  bot.action(/^ig_(post|cancel):([a-f0-9-]+)$/, async (ctx) => {
    await ctx.answerCbQuery();
    const [, action, id] = ctx.match;
    const job = pending.get(id);
    if (!job || job.userId !== ctx.from.id) {
      await ctx.editMessageText('대기 중인 게시물이 없습니다. 사진을 다시 보내주세요.');
      return;
    }
    pending.delete(id);

    if (action === 'cancel') {
      discard(job);
      await ctx.editMessageText('취소했습니다.');
      return;
    }

    await ctx.editMessageText('게시 중...');
    try {
      const permalink = await config.client.publishPhoto(
        `${config.publicBaseUrl}/media/${job.filename}`,
        job.caption
      );
      await ctx.editMessageText(`게시 완료 🎉\n${permalink}`);
    } catch (err) {
      console.error('Instagram publish failed:', err);
      await ctx.editMessageText(`게시 실패: ${err.message}`);
    } finally {
      discard(job);
    }
  });

  return true;
}

module.exports = { registerInstagramPoster };
