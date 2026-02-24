import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, get_cooldown_remaining, update_cooldown, is_allowed
from ai_handler import get_ai_response
from admin_panel import (
    is_admin,
    show_main_menu,
    ask_persona,
    save_persona,
    ask_preset,
    save_preset,
    clear_preset,
    ask_whitelist,
    set_wl_mode_all,
    set_wl_mode_whitelist,
    ask_wl_add,
    save_wl_item,
    clear_whitelist,
    ask_cooldown,
    set_cooldown_preset,
    ask_cooldown_custom,
    save_cooldown_custom,
    MAIN_MENU,
    SET_PERSONA,
    SET_PRESET,
    SET_WHITELIST_MODE,
    SET_WHITELIST_INPUT,
    SET_COOLDOWN,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ────────────────────────────────
# /start 命令
# ────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 你好！我是 AI 助理，直接发消息和我聊天吧～\n\n"
        "管理员可以使用 /set 进入设置面板\n"
        "使用 /id 查看当前聊天 ID"
    )


# ────────────────────────────────
# /id 命令（查看ID）
# ────────────────────────────────
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    text = (
        f"👤 你的用户 ID：<code>{user.id}</code>\n"
        f"💬 当前聊天 ID：<code>{chat.id}</code>\n"
        f"📁 聊天类型：{chat.type}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ────────────────────────────────
# 处理普通消息（AI 回复）
# ────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat

    # 群里需要@机器人或回复机器人才触发
    if chat.type in ("group", "supergroup"):
        bot_username = context.bot.username
        message = update.message
        is_mention = (
            f"@{bot_username}" in (message.text or "")
        )
        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.username == bot_username
        )
        if not is_mention and not is_reply_to_bot:
            return

    # 检查权限
    allowed = await is_allowed(user.id, chat.id, chat.type)
    if not allowed:
        await update.message.reply_text("⛔ 抱歉，您没有使用权限。")
        return

    # 检查冷却
    remaining = await get_cooldown_remaining(user.id)
    if remaining > 0:
        await update.message.reply_text(
            f"⏳ 冷却中，请等待 {remaining:.1f} 秒后再试。"
        )
        return

    # 处理消息内容（去掉@机器人部分）
    user_text = update.message.text
    if context.bot.username:
        user_text = user_text.replace(f"@{context.bot.username}", "").strip()

    if not user_text:
        return

    # 更新冷却
    await update_cooldown(user.id)

    # 发送"正在输入"状态
    await context.bot.send_chat_action(chat_id=chat.id, action="typing")

    # 获取 AI 回复
    user_name = user.first_name or str(user.id)
    response = await get_ai_response(user_text, user_name)

    await update.message.reply_text(response)


# ────────────────────────────────
# /set 命令入口（仅管理员）
# ────────────────────────────────
async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ 你没有管理员权限。")
        return ConversationHandler.END
    return await show_main_menu(update, context)


# ────────────────────────────────
# 回调：返回按钮
# ────────────────────────────────
async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_main_menu(update, context)


async def back_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_whitelist(update, context)


async def back_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_cooldown(update, context)


async def close_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("✅ 设置面板已关闭。")
    return ConversationHandler.END


# ────────────────────────────────
# 主函数
# ────────────────────────────────
def main():
    asyncio.get_event_loop().run_until_complete(init_db())

    app = Application.builder().token(BOT_TOKEN).build()

    # 管理员设置会话
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set", set_command)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(ask_persona, pattern="^set_persona$"),
                CallbackQueryHandler(ask_preset, pattern="^set_preset$"),
                CallbackQueryHandler(ask_whitelist, pattern="^set_whitelist$"),
                CallbackQueryHandler(ask_cooldown, pattern="^set_cooldown$"),
                CallbackQueryHandler(close_panel, pattern="^close$"),
            ],
            SET_PERSONA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_persona),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
            ],
            SET_PRESET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_preset),
                CallbackQueryHandler(clear_preset, pattern="^clear_preset$"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
            ],
            SET_WHITELIST_MODE: [
                CallbackQueryHandler(set_wl_mode_all, pattern="^wl_mode_all$"),
                CallbackQueryHandler(set_wl_mode_whitelist, pattern="^wl_mode_whitelist$"),
                CallbackQueryHandler(ask_wl_add, pattern="^wl_add$"),
                CallbackQueryHandler(clear_whitelist, pattern="^wl_clear$"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
            ],
            SET_WHITELIST_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_wl_item),
                CallbackQueryHandler(back_whitelist, pattern="^back_whitelist$"),
            ],
            SET_COOLDOWN: [
                CallbackQueryHandler(set_cooldown_preset, pattern="^cd_(5|10|30|60|300)$"),
                CallbackQueryHandler(ask_cooldown_custom, pattern="^cd_custom$"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                CallbackQueryHandler(back_cooldown, pattern="^back_cooldown$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_cooldown_custom),
            ],
        },
        fallbacks=[
            CommandHandler("set", set_command),
            CallbackQueryHandler(close_panel, pattern="^close$"),
        ],
        per_chat=False,
        per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("🤖 机器人启动中...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()