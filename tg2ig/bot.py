import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Config, load_config
from .instagram import InstagramClient, InstagramError
from .media_server import start_media_server

log = logging.getLogger("tg2ig")

CAPTION_LIMIT = 2200  # 인스타그램 캡션 최대 글자 수


def _allowed(update: Update, cfg: Config) -> bool:
    user = update.effective_user
    return user is not None and user.id in cfg.allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data["cfg"]
    if not _allowed(update, cfg):
        await update.message.reply_text(f"권한이 없습니다. (내 ID: {update.effective_user.id})")
        return
    await update.message.reply_text(
        "사진을 캡션과 함께 보내면 인스타그램 게시 여부를 물어볼게요."
    )


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data["cfg"]
    msg = update.message
    if not _allowed(update, cfg):
        return
    caption = msg.caption or ""
    if len(caption) > CAPTION_LIMIT:
        await msg.reply_text(f"캡션이 너무 깁니다. ({len(caption)}/{CAPTION_LIMIT}자)")
        return

    file = await msg.photo[-1].get_file()  # 가장 큰 해상도
    filename = f"{uuid.uuid4().hex}.jpg"
    await file.download_to_drive(cfg.media_dir / filename)

    context.user_data["pending"] = {"filename": filename, "caption": caption}
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ 게시", callback_data="post"),
            InlineKeyboardButton("❌ 취소", callback_data="cancel"),
        ]]
    )
    await msg.reply_text(
        f"인스타그램에 게시할까요?\n\n캡션: {caption or '(없음)'}", reply_markup=keyboard
    )


def _discard(cfg: Config, pending: dict | None) -> None:
    if pending:
        (cfg.media_dir / pending["filename"]).unlink(missing_ok=True)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data["cfg"]
    ig: InstagramClient = context.bot_data["ig"]
    query = update.callback_query
    await query.answer()
    if not _allowed(update, cfg):
        return

    pending = context.user_data.pop("pending", None)
    if pending is None:
        await query.edit_message_text("대기 중인 게시물이 없습니다. 사진을 다시 보내주세요.")
        return
    if query.data == "cancel":
        _discard(cfg, pending)
        await query.edit_message_text("취소했습니다.")
        return

    await query.edit_message_text("게시 중...")
    try:
        image_url = f"{cfg.public_base_url}/media/{pending['filename']}"
        media_id = await ig.publish_photo(image_url, pending["caption"])
        link = await ig.permalink(media_id)
        await query.edit_message_text(f"게시 완료 🎉\n{link or media_id}")
    except InstagramError as e:
        log.exception("Instagram 게시 실패")
        await query.edit_message_text(f"게시 실패: {e}")
    finally:
        _discard(cfg, pending)


async def _post_init(app: Application) -> None:
    cfg: Config = app.bot_data["cfg"]
    app.bot_data["media_runner"] = await start_media_server(cfg.media_dir, cfg.media_port)


async def _post_shutdown(app: Application) -> None:
    await app.bot_data["media_runner"].cleanup()
    await app.bot_data["ig"].aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # 요청 URL에 토큰이 찍히지 않도록

    cfg = load_config()
    app = (
        Application.builder()
        .token(cfg.telegram_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["cfg"] = cfg
    app.bot_data["ig"] = InstagramClient(cfg.ig_user_id, cfg.ig_access_token, cfg.graph_version)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()


if __name__ == "__main__":
    main()
