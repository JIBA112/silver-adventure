import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS
from database import (
    init_db, get_cooldown_remaining, update_cooldown, is_allowed, 
    get_setting, set_setting, save_history, get_history
)
from ai_handler import get_ai_response
from admin_panel import (
    is_admin, show_main_menu, ask_persona, save_persona, ask_preset, save_preset,
    clear_preset, ask_whitelist, set_wl_mode_all, set_wl_mode_whitelist,
    ask_wl_add, save_wl_item, clear_whitelist, ask_cooldown,
    set_cooldown_preset, ask_cooldown_custom, save_cooldown_custom,
    MAIN_MENU, SET_PERSONA, SET_PRESET, SET_WHITELIST_MODE, SET_WHITELIST_INPUT, SET_COOLDOWN
)

# 触发词设置状态
SET_TRIGGERS = 99

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────────────────────────
# 核心消息处理（支持群聊、频道、私聊）
# ────────────────────────────────
async def unified_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, is_channel=False):
    msg = update.channel_post if is_channel else update.message
    if not msg or not msg.text: return

    user = msg.from_user
    chat = msg.chat
    text = msg.text
    
    # 确定显示的名字
    if is_channel:
        user_name = "频道发布者"
        user_id = chat.id 
    else:
        user_name = user.first_name or "未知"
        user_id = user.id

    # 1. 记录消息到历史记录（无论是否触发AI）
    await save_history(chat.id, user_name, text)

    # 2. 判断是否触发AI回复
    bot_username = context.bot.username
    trigger_words = await get_setting("trigger_words", [])
    
    should_respond = False
    
    if chat.type == "private":
        should_respond = True
    else:
        # 群组或频道的触发逻辑
        is_mention = bot_username and f"@{bot_username}" in text
        is_reply = (msg.reply_to_message and msg.reply_to_message.from_user 
                    and msg.reply_to_message.from_user.username == bot_username)
        has_trigger = any(word in text for word in trigger_words) if trigger_words else False
        
        if is_mention or is_reply or has_trigger:
            should_respond = True

    if not should_respond:
        return

    # 3. 权限检查
    if not await is_allowed(user_id, chat.id, chat.type):
        if chat.type == "private": await msg.reply_text("⛔ 您没有权限使用此机器人。")
        return

    # 4. 冷却检查
    remaining = await get_cooldown_remaining(user_id)
    if remaining > 0:
        if chat.type == "private": await msg.reply_text(f"⏳ 冷却中，请等待 {remaining:.1f} 秒。")
        return

    # 5. 调用 AI
    clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text
    if not clean_text and chat.type != "private": return

    await update_cooldown(user_id)
    await context.bot.send_chat_action(chat_id=chat.id, action="typing")

    # 获取上下文记录（最近15条）
    history = await get_history(chat.id, limit=15)
    
    response = await get_ai_response(clean_text, user_name, history)
    await msg.reply_text(response)

# 处理函数包装
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await unified_message_handler(update, context, is_channel=False)

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await unified_message_handler(update, context, is_channel=True)

# ────────────────────────────────
# 触发词设置逻辑
# ────────────────────────────────
async def ask_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current = await get_setting("trigger_words", [])
    text = (
        "💬 **设置群聊触发词**\n\n"
        f"当前触发词：`{', '.join(current) if current else '未设置'}`\n\n"
        "请直接发送触发词，多个词请用 **空格** 隔开。"
    )
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SET_TRIGGERS

async def save_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = [w.strip() for w in update.message.text.replace(',', ' ').split() if w.strip()]
    await set_setting("trigger_words", words)
    await update.message.reply_text(f"✅ 触发词已更新：`{', '.join(words)}`", parse_mode="Markdown")
    return await show_main_menu(update, context)

# ────────────────────────────────
# 其他命令
# ────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 AI 助手已就绪！\n群聊触发方式：包含触发词、回复机器人、或 @ 机器人。\n管理请输入 /set")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"💬 当前 Chat ID: <code>{chat.id}</code>\n类型: {chat.type}", parse_mode="HTML")

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    return await show_main_menu(update, context)

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_main_menu(update, context)

async def close_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("✅ 设置面板已关闭。")
    return ConversationHandler.END

# ────────────────────────────────
# 主入口
# ────────────────────────────────
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
            SET_PERSONA: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_persona), CallbackQueryHandler(back_main, pattern="^back_main$")],
            SET_PRESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_preset), CallbackQueryHandler(back_main, pattern="^back_main$")],
            SET_TRIGGERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_triggers), CallbackQueryHandler(back_main, pattern="^back_main$")],
            SET_WHITELIST_MODE: [
                CallbackQueryHandler(set_wl_mode_all, pattern="^wl_mode_all$"),
                CallbackQueryHandler(set_wl_mode_whitelist, pattern="^wl_mode_whitelist$"),
                CallbackQueryHandler(ask_wl_add, pattern="^wl_add$"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
            ],
            SET_WHITELIST_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_wl_item), CallbackQueryHandler(back_main, pattern="^back_main$")],
            SET_COOLDOWN: [
                CallbackQueryHandler(set_cooldown_preset, pattern="^cd_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_cooldown_custom),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
            ],
        },
        fallbacks=[CommandHandler("set", set_command)],
        per_chat=False, per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    
    # 核心：处理普通消息
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # 核心：处理频道消息
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & filters.TEXT, handle_channel_post))

    logger.info("🤖 机器人启动成功（支持记忆与频道记录）...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
