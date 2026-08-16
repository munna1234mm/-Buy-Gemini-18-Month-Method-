import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

import database
import config
from keyboards import get_admin_inline_menu, get_channels_manager_keyboard, get_gemini_settings_keyboard, get_cancel_keyboard

logger = logging.getLogger(__name__)

# Conversation states
STATE_ADD_CHANNEL_ID = 1
STATE_ADD_CHANNEL_LINK = 2
STATE_SET_REWARD = 3
STATE_BROADCAST = 4
STATE_SET_GEMINI_CONTENT = 5
STATE_SET_GEMINI_REFS = 6
STATE_SET_GEMINI_PRICE = 7

async def is_admin_authorized(update: Update) -> bool:
    """Helper to check if user is admin."""
    user = update.effective_user
    if not user:
        return False
    all_admins = database.get_all_admins()
    if not all_admins:
        database.add_admin(user.id)
        return True
    return database.is_admin(user.id)


async def admin_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entrypoint for /admin command."""
    if not update.effective_user or not update.effective_message:
        return

    if not await is_admin_authorized(update):
        await update.effective_message.reply_text(
            f"⛔ <b>Access Denied:</b> You are not an admin.\n\n"
            f"Your Telegram ID: <code>{update.effective_user.id}</code>\n"
            f"Add this ID to <code>ADMIN_IDS</code> in <code>.env</code> file.",
            parse_mode=ParseMode.HTML
        )
        return

    stats = database.get_stats()
    text = (
        f"🛠 <b>Admin Control Panel</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"✅ <b>Verified Members:</b> <code>{stats['verified_users']}</code>\n"
        f"📢 <b>Active Channels/Groups:</b> <code>{stats['total_channels']}</code>\n"
        f"🏆 <b>Total Referrals:</b> <code>{stats['total_referrals']}</code>\n"
        f"💰 <b>Total Balance Issued:</b> <code>{stats['total_balance']}</code>\n\n"
        f"<i>Select an option from the menu below:</i>"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=get_admin_inline_menu(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=get_admin_inline_menu(),
            parse_mode=ParseMode.HTML
        )


async def admin_menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin main navigation callbacks."""
    query = update.callback_query
    await query.answer()

    if not await is_admin_authorized(update):
        await query.answer("⛔ Unauthorized", show_alert=True)
        return

    data = query.data

    if data == "admin_main" or data == "admin_stats":
        stats = database.get_stats()
        text = (
            f"🛠 <b>Admin Control Panel</b>\n\n"
            f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
            f"✅ <b>Verified Members:</b> <code>{stats['verified_users']}</code>\n"
            f"📢 <b>Active Channels/Groups:</b> <code>{stats['total_channels']}</code>\n"
            f"🏆 <b>Total Referrals:</b> <code>{stats['total_referrals']}</code>\n"
            f"💰 <b>Total Balance Issued:</b> <code>{stats['total_balance']}</code>\n\n"
            f"<i>Select an option below:</i>"
        )
        await query.edit_message_text(text, reply_markup=get_admin_inline_menu(), parse_mode=ParseMode.HTML)

    elif data == "admin_gemini_settings":
        required_refs = database.get_setting("gemini_required_referrals", "5")
        method_price = database.get_setting("gemini_method_price", "0.0")
        currency = database.get_setting("currency_name", config.CURRENCY_NAME)
        content_preview = database.get_setting("gemini_method_content", "No content set yet.")

        text = (
            f"💎 <b>Gemini 18 Month Method Settings</b>\n\n"
            f"👥 <b>Required Referrals to Unlock:</b> <code>{required_refs} invites</code>\n"
            f"💵 <b>USDT Price:</b> <code>{method_price} {currency}</code>\n\n"
            f"📝 <b>Current Method Content / Details:</b>\n"
            f"<blockquote>{content_preview[:300]}...</blockquote>\n\n"
            f"<i>Choose an option below to update:</i>"
        )
        await query.edit_message_text(text, reply_markup=get_gemini_settings_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "admin_channels":
        channels = database.get_all_channels()
        text = (
            f"📢 <b>Mandatory Channels & Groups Manager</b>\n\n"
            f"Total Configured: <b>{len(channels)}</b>\n\n"
            f"Users MUST join all these channels and groups before using the bot.\n\n"
            f"<i>Click on any channel below to remove it, or click '➕ Add Channel / Group'.</i>"
        )
        await query.edit_message_text(
            text,
            reply_markup=get_channels_manager_keyboard(channels),
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("del_channel_"):
        channel_id = int(data.split("_")[2])
        ch = database.get_channel(channel_id)
        if ch:
            database.remove_channel(channel_id)
            await query.answer(f"✅ Removed {ch['title']}", show_alert=True)
        channels = database.get_all_channels()
        await query.edit_message_text(
            f"📢 <b>Mandatory Channels & Groups Manager</b>\n\nChannel removed successfully!\nTotal Channels: <b>{len(channels)}</b>",
            reply_markup=get_channels_manager_keyboard(channels),
            parse_mode=ParseMode.HTML
        )

    elif data == "admin_close":
        await query.edit_message_text("🔒 Admin panel closed.")



# --- CHANNEL ADD CONVERSATION ---

async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts add channel/group flow."""
    query = update.callback_query
    await query.answer()

    text = (
        f"➕ <b>Add Channel or Group</b>\n\n"
        f"1. <b>First, make sure to add this bot as an ADMIN in your Channel or Group!</b>\n"
        f"2. Send the Channel/Group <b>Username</b> (e.g. <code>@MyChannel</code>) or <b>Chat ID</b> (e.g. <code>-1001234567890</code>):\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_channels"), parse_mode=ParseMode.HTML)
    return STATE_ADD_CHANNEL_ID


async def add_channel_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles channel ID/username input from admin."""
    chat_input = update.message.text.strip()
    parsed_id = int(chat_input) if (chat_input.startswith("-") or chat_input.isdigit()) else chat_input
    
    try:
        chat = await context.bot.get_chat(chat_id=parsed_id)
        context.user_data["new_channel_chat_id"] = str(chat.id)
        context.user_data["new_channel_title"] = chat.title or chat_input
        
        default_link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
        context.user_data["new_channel_link"] = default_link

        if default_link:
            text = (
                f"✅ Found: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)\n"
                f"🔗 Detected Link: <code>{default_link}</code>\n\n"
                f"Send a custom invite link if you wish, or reply <code>default</code> to use the detected link:"
            )
        else:
            text = (
                f"✅ Found: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)\n\n"
                f"🔗 Please send the <b>Invite Link</b> for this channel/group (e.g. <code>https://t.me/+AbCdEfGh</code>):"
            )

        await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_channels"), parse_mode=ParseMode.HTML)
        return STATE_ADD_CHANNEL_LINK

    except TelegramError as e:
        await update.message.reply_text(
            f"❌ <b>Could not access channel:</b> {e}\n\n"
            f"⚠️ <b>Reminder:</b> The bot must be an <b>Administrator</b> in the channel/group!\n"
            f"Please add the bot as admin and try sending the username/ID again, or /cancel."
        )
        return STATE_ADD_CHANNEL_ID


async def add_channel_link_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves the channel with invite link."""
    link_input = update.message.text.strip()
    
    if link_input.lower() == "default":
        invite_link = context.user_data.get("new_channel_link", "")
    else:
        invite_link = link_input

    if not invite_link.startswith("http"):
        await update.message.reply_text("❌ Link must start with http:// or https://, or send 'default'.")
        return STATE_ADD_CHANNEL_LINK

    chat_id = context.user_data.get("new_channel_chat_id")
    title = context.user_data.get("new_channel_title", "Channel")

    database.add_channel(chat_id=chat_id, title=title, invite_link=invite_link)

    channels = database.get_all_channels()
    await update.message.reply_text(
        f"🎉 <b>Channel Added Successfully!</b>\n\n"
        f"📢 <b>Title:</b> {title}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"🔗 <b>Invite Link:</b> {invite_link}\n\n"
        f"All bot users will now be required to join this channel before using the bot.",
        reply_markup=get_channels_manager_keyboard(channels),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# --- SET REWARD CONVERSATION ---

async def set_reward_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts reward modification."""
    query = update.callback_query
    await query.answer()

    current_reward = database.get_setting("referral_reward", str(config.DEFAULT_REFERRAL_REWARD))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)

    text = (
        f"⚙️ <b>Set Referral Reward</b>\n\n"
        f"Current Reward: <b>{current_reward} {currency}</b> per referral.\n\n"
        f"Send the new reward amount (e.g. <code>10</code>, <code>25</code>) or /cancel:"
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_main"), parse_mode=ParseMode.HTML)
    return STATE_SET_REWARD


async def set_reward_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new referral reward."""
    input_text = update.message.text.strip()
    try:
        val = float(input_text)
        if val < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return STATE_SET_REWARD

    database.set_setting("referral_reward", str(val))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)

    await update.message.reply_text(
        f"✅ <b>Referral reward updated to {val} {currency} per invite!</b>",
        reply_markup=get_admin_inline_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# --- BROADCAST CONVERSATION ---

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts broadcast workflow."""
    query = update.callback_query
    await query.answer()

    user_ids = database.get_all_user_ids()
    text = (
        f"📣 <b>Broadcast Message</b>\n\n"
        f"Total Recipients: <b>{len(user_ids)} active users</b>\n\n"
        f"Send the message (Text, Photo with Caption, or Forward) you want to broadcast.\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_main"), parse_mode=ParseMode.HTML)
    return STATE_BROADCAST


async def broadcast_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts message to all users."""
    user_ids = database.get_all_user_ids()
    msg = update.message

    status_msg = await update.message.reply_text(f"🚀 Broadcast started to {len(user_ids)} users...")
    
    success = 0
    failed = 0

    for idx, uid in enumerate(user_ids, 1):
        try:
            await msg.copy(chat_id=uid)
            success += 1
        except Exception as e:
            failed += 1
            logger.debug(f"Failed broadcast to {uid}: {e}")

        if idx % 25 == 0 or idx == len(user_ids):
            try:
                await status_msg.edit_text(
                    f"📤 <b>Broadcasting...</b>\n"
                    f"Progress: {idx}/{len(user_ids)}\n"
                    f"✅ Sent: {success}\n"
                    f"❌ Failed/Blocked: {failed}",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
        await asyncio.sleep(0.04)

    await status_msg.edit_text(
        f"🎉 <b>Broadcast Complete!</b>\n\n"
        f"📊 Total Target: {len(user_ids)}\n"
        f"✅ Sent Successfully: {success}\n"
        f"❌ Failed / Blocked: {failed}",
        reply_markup=get_admin_inline_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# --- GEMINI METHOD SETTINGS CONVERSATIONS ---

# 1. Method Content / Tutorial / Delivery Text
async def set_gemini_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompts admin for new method content/text/links."""
    query = update.callback_query
    await query.answer()

    text = (
        f"📝 <b>Edit Gemini 18 Month Method Content</b>\n\n"
        f"Send the complete text, guide, instructions, accounts, or links that users will see when they unlock/purchase the method.\n\n"
        f"<i>Supports Telegram HTML formatting.</i>\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_gemini_settings"), parse_mode=ParseMode.HTML)
    return STATE_SET_GEMINI_CONTENT


async def set_gemini_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new Gemini Method content."""
    content = update.message.text_html if update.message.text_html else update.message.text
    database.set_setting("gemini_method_content", content)

    await update.message.reply_text(
        f"✅ <b>Gemini 18 Month Method content updated successfully!</b>\n\n"
        f"Eligible users who click the button will now receive this updated guide.",
        reply_markup=get_admin_inline_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# 2. Required Referrals Limit
async def set_gemini_refs_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompts admin for required referrals limit."""
    query = update.callback_query
    await query.answer()

    current_refs = database.get_setting("gemini_required_referrals", "5")
    text = (
        f"👥 <b>Set Required Referrals Limit</b>\n\n"
        f"Current Requirement: <b>{current_refs} referrals</b>\n\n"
        f"Send the number of invited friends needed to unlock the method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_gemini_settings"), parse_mode=ParseMode.HTML)
    return STATE_SET_GEMINI_REFS


async def set_gemini_refs_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new referral limit requirement."""
    input_text = update.message.text.strip()
    if not input_text.isdigit():
        await update.message.reply_text("❌ Please enter a valid integer number (e.g. 5 or 10).")
        return STATE_SET_GEMINI_REFS

    val = int(input_text)
    database.set_setting("gemini_required_referrals", str(val))

    await update.message.reply_text(
        f"✅ <b>Required referral limit updated to {val} invites!</b>\n\n"
        f"Users now must invite at least {val} friends to unlock the Gemini 18 Month Method.",
        reply_markup=get_admin_inline_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# 3. USDT Price (Optional)
async def set_gemini_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompts admin for USDT price."""
    query = update.callback_query
    await query.answer()

    current_price = database.get_setting("gemini_method_price", "0.0")
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)

    text = (
        f"💵 <b>Set Gemini Method USDT Price</b>\n\n"
        f"Current Price: <b>{current_price} {currency}</b>\n\n"
        f"Send the price in USDT (e.g. <code>0</code> for free with referrals, or <code>10.0</code>):\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_gemini_settings"), parse_mode=ParseMode.HTML)
    return STATE_SET_GEMINI_PRICE


async def set_gemini_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new USDT price."""
    input_text = update.message.text.strip()
    try:
        val = float(input_text)
        if val < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return STATE_SET_GEMINI_PRICE

    database.set_setting("gemini_method_price", str(val))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)

    await update.message.reply_text(
        f"✅ <b>Gemini Method price updated to {val:.2f} {currency}!</b>",
        reply_markup=get_admin_inline_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels ongoing conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Action cancelled.", reply_markup=get_admin_inline_menu())
    elif update.message:
        await update.message.reply_text("❌ Action cancelled.", reply_markup=get_admin_inline_menu())
    return ConversationHandler.END

