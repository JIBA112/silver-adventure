from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS, MIN_COOLDOWN
from database import get_setting, set_setting

# 会话状态
(
    MAIN_MENU,
    SET_PERSONA,
    SET_PRESET,
    SET_WHITELIST_MODE,
    SET_WHITELIST_INPUT,
    SET_COOLDOWN,
) = range(6)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ────────────────────────────────
# 主菜单
# ────────────────────────────────
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    persona = await get_setting("persona", "（未设置）")
    preset = await get_setting("preset", "（未设置）")
    cooldown = await get_setting("cooldown", 10)
    mode = await get_setting("whitelist_mode", "all")
    whitelist = await get_setting("whitelist", [])

    mode_text = "全部用户" if mode == "all" else f"白名单（{len(whitelist)} 个）"

    text = (
        "⚙️ <b>AI 机器人设置面板</b>\n\n"
        f"🧬 <b>人设：</b>{str(persona)[:50]}...\n"
        f"📌 <b>预设指令：</b>{str(preset)[:50] if preset and preset != '（未设置）' else '（未设置）'}\n"
        f"💬 <b>聊天权限：</b>{mode_text}\n"
        f"⏱ <b>冷却时间：</b>{cooldown} 秒\n"
    )

    keyboard = [
        [InlineKeyboardButton("🧬 设置人设", callback_data="set_persona")],
        [InlineKeyboardButton("📌 设置预设指令", callback_data="set_preset")],
        [InlineKeyboardButton("💬 聊天权限设置", callback_data="set_whitelist")],
        [InlineKeyboardButton("⏱ 冷却时间设置", callback_data="set_cooldown")],
        [InlineKeyboardButton("❌ 关闭", callback_data="close")],
        [InlineKeyboardButton("💬 设置触发词", callback_data="set_triggers")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    return MAIN_MENU


# ────────────────────────────────
# 人设设置
# ────────────────────────────────
async def ask_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    current = await get_setting("persona", "（未设置）")
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back_main")]]
    await update.callback_query.edit_message_text(
        f"🧬 <b>设置人设</b>\n\n"
        f"当前人设：\n<code>{current}</code>\n\n"
        f"请发送新的人设内容：\n"
        f"<i>（描述AI的性格、说话风格等）</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return SET_PERSONA


async def save_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await set_setting("persona", text)
    await update.message.reply_text("✅ 人设已保存！")
    return await show_main_menu(update, context)


# ────────────────────────────────
# 预设指令设置
# ────────────────────────────────
async def ask_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    current = await get_setting("preset", "（未设置）")
    keyboard = [
        [InlineKeyboardButton("🗑 清除预设", callback_data="clear_preset")],
        [InlineKeyboardButton("🔙 返回", callback_data="back_main")],
    ]
    await update.callback_query.edit_message_text(
        f"📌 <b>设置预设指令</b>\n\n"
        f"当前预设：\n<code>{current}</code>\n\n"
        f"请发送预设内容：\n"
        f"<i>（此内容优先级高于用户输入和人设）</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return SET_PRESET


async def save_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    await set_setting("preset", text)
    await update.message.reply_text("✅ 预设指令已保存！")
    return await show_main_menu(update, context)


async def clear_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await set_setting("preset", "")
    await update.callback_query.answer("✅ 预设已清除", show_alert=True)
    return await show_main_menu(update, context)


# ────────────────────────────────
# 聊天权限设置
# ────────────────────────────────
async def ask_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    mode = await get_setting("whitelist_mode", "all")
    whitelist = await get_setting("whitelist", [])

    wl_text = "\n".join(str(x) for x in whitelist) if whitelist else "（空）"
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ 全部用户" if mode == "all" else "全部用户",
                callback_data="wl_mode_all",
            ),
            InlineKeyboardButton(
                "✅ 白名单模式" if mode == "whitelist" else "白名单模式",
                callback_data="wl_mode_whitelist",
            ),
        ],
        [InlineKeyboardButton("➕ 添加白名单", callback_data="wl_add")],
        [InlineKeyboardButton("🗑 清空白名单", callback_data="wl_clear")],
        [InlineKeyboardButton("🔙 返回", callback_data="back_main")],
    ]
    await update.callback_query.edit_message_text(
        f"💬 <b>聊天权限设置</b>\n\n"
        f"当前模式：{'全部用户' if mode == 'all' else '白名单模式'}\n\n"
        f"白名单列表（用户ID或群ID）：\n<code>{wl_text}</code>\n\n"
        f"<i>支持：私聊用户ID、群组ID</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return SET_WHITELIST_MODE


async def set_wl_mode_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await set_setting("whitelist_mode", "all")
    return await ask_whitelist(update, context)


async def set_wl_mode_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await set_setting("whitelist_mode", "whitelist")
    return await ask_whitelist(update, context)


async def ask_wl_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back_whitelist")]]
    await update.callback_query.edit_message_text(
        "➕ <b>添加白名单</b>\n\n"
        "请发送要添加的 <b>用户ID</b> 或 <b>群组ID</b>\n\n"
        "<i>获取ID方法：在群里或私聊发送 /id 即可查看</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return SET_WHITELIST_INPUT


async def save_wl_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        new_id = int(text)
        whitelist = await get_setting("whitelist", [])
        if new_id not in whitelist:
            whitelist.append(new_id)
            await set_setting("whitelist", whitelist)
            await update.message.reply_text(f"✅ 已添加 {new_id} 到白名单！")
        else:
            await update.message.reply_text(f"⚠️ {new_id} 已在白名单中")
    except ValueError:
        await update.message.reply_text("❌ 请输入纯数字 ID")
    return await show_main_menu(update, context)


async def clear_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await set_setting("whitelist", [])
    await update.callback_query.answer("✅ 白名单已清空", show_alert=True)
    return await ask_whitelist(update, context)


# ────────────────────────────────
# 冷却时间设置
# ────────────────────────────────
async def ask_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    current = await get_setting("cooldown", 10)
    keyboard = [
        [
            InlineKeyboardButton("5秒", callback_data="cd_5"),
            InlineKeyboardButton("10秒", callback_data="cd_10"),
            InlineKeyboardButton("30秒", callback_data="cd_30"),
        ],
        [
            InlineKeyboardButton("60秒", callback_data="cd_60"),
            InlineKeyboardButton("300秒", callback_data="cd_300"),
        ],
        [InlineKeyboardButton("✏️ 自定义", callback_data="cd_custom")],
        [InlineKeyboardButton("🔙 返回", callback_data="back_main")],
    ]
    await update.callback_query.edit_message_text(
        f"⏱ <b>冷却时间设置</b>\n\n"
        f"当前冷却：<b>{current} 秒</b>\n\n"
        f"选择预设或自定义（最低 {MIN_COOLDOWN} 秒）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return SET_COOLDOWN


async def set_cooldown_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    seconds = int(data.split("_")[1])
    await set_setting("cooldown", seconds)
    await update.callback_query.answer(f"✅ 冷却时间设为 {seconds} 秒", show_alert=True)
    return await show_main_menu(update, context)


async def ask_cooldown_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="back_cooldown")]]
    await update.callback_query.edit_message_text(
        f"✏️ <b>自定义冷却时间</b>\n\n"
        f"请发送秒数（最低 {MIN_COOLDOWN} 秒，无上限）：",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    context.user_data["waiting_cooldown"] = True
    return SET_COOLDOWN


async def save_cooldown_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_cooldown"):
        return SET_COOLDOWN
    text = update.message.text.strip()
    try:
        seconds = int(text)
        if seconds < MIN_COOLDOWN:
            await update.message.reply_text(
                f"❌ 冷却时间不能低于 {MIN_COOLDOWN} 秒！"
            )
            return SET_COOLDOWN
        await set_setting("cooldown", seconds)
        context.user_data.pop("waiting_cooldown", None)
        await update.message.reply_text(f"✅ 冷却时间已设为 {seconds} 秒！")
        return await show_main_menu(update, context)
    except ValueError:
        await update.message.reply_text("❌ 请输入纯数字")
        return SET_COOLDOWN

