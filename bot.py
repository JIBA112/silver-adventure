import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from database import init_db, get_cooldown_remaining, update_cooldown, is_allowed, get_setting, set_setting
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

# 定义新的触发词状态
SET_TRIGGERS = 99

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 你好！我是 AI 助理，直接发消息和我聊天吧～\n\n"
        "管理员可以使用 /set 进入设置面板\n"
        "使用 /id 查看当前聊天 ID"
    )

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
# 处理普通消息（AI 回复核心逻辑）
# ────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    user_text = update.message.text

    # --- 触发词逻辑判断 ---
    trigger_words = await get_setting("trigger_words", [])
    
    if chat.type in ("group", "supergroup"):
        bot_username = context.bot.username
        is_mention = f"@{bot_username}" in user_text
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.username == bot_username
        )
        # 检查是否包含设置的触发词
        has_trigger = any(word in user_text for word in trigger_words) if trigger_words else False

        # 如果三个条件都不满足，直接保持沉默
        if not (is_mention or is_reply_to_bot or has_trigger):
            return

    # 权限检查
    allowed = await is_allowed(user.id, chat.id, chat.type)
    if not allowed:
        if chat.type == "private":
            await update.message.reply_text("⛔ 抱歉，您没有使用权限。")
        return

    # 冷却检查
    remaining = await get_cooldown_remaining(user.id)
    if remaining > 0:
        if chat.type == "private":
            await update.message.reply_text(f"⏳ 冷却中，请等待 {remaining:.1f} 秒后再试。")
        return

    # 清理文本
    clean_text = user_text
    if context.bot.username:
        clean_text = clean_text.replace(f"@{context.bot.username}", "").strip()

    if not clean_text and chat.type != "private":
        return

    await update_cooldown(user.id)
    await context.bot.send_chat_action(chat_id=chat.id, action="typing")

    user_name = user.first_name or str(user.id)
    response = await get_ai_response(clean_text, user_name)

    await update.message.reply_text(response)

# ────────────────────────────────
# 设置触发词相关的函数
# ────────────────────────────────
async def ask_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = await get_setting("trigger_words", [])
    text = (
        "💬 **设置群聊触发词**\n\n"
        f"当前触发词：`{', '.join(current) if current else '未设置'}`\n\n"
        "请直接回复触发词，多个词请用 **空格** 隔开。\n"
        "设置后，群内消息只要包含这些词，机器人就会回复。"
    )
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SET_TRIGGERS

async def save_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    words = [w.strip() for w in text.replace(',', ' ').split() if w.strip()]
    await set_setting("trigger_words", words)
    await update.message.reply_text(f"✅ 触发词设置成功：`{', '.join(words)}`", parse_mode="Markdown")
    return await show_main_menu(update, context)

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ 你没有管理员权限。")
        return ConversationHandler.END
    return await show_main_menu(update, context)

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

def main():
    asyncio.get_event_loop().run_until_complete(init_db())
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set", set_command)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(ask_persona, pattern="^set_persona$"),
                CallbackQueryHandler(ask_preset, pattern="^set_preset$"),
                CallbackQueryHandler(ask_whitelist, pattern="^set_whitelist$"),
                CallbackQueryHandler(ask_cooldown, pattern="^set_cooldown$"),
                CallbackQueryHandler(ask_triggers, pattern="^set_triggers$"),
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
            SET_TRIGGERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_triggers),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 机器人启动中...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
