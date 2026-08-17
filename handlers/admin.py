import logging
import asyncio
from typing import Any
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
from keyboards import (
    get_admin_inline_menu,
    get_channels_manager_keyboard,
    get_methods_manager_keyboard,
    get_single_method_manage_keyboard,
    get_cancel_keyboard
)

logger = logging.getLogger(__name__)

# Conversation states
STATE_ADD_CHANNEL_ID = 1
STATE_ADD_CHANNEL_LINK = 2
STATE_SET_REWARD = 3
STATE_BROADCAST = 4
STATE_ADD_M_TITLE = 5
STATE_ADD_M_CONTENT = 6
STATE_ADD_M_REFS = 7
STATE_ADD_M_PRICE = 8
STATE_EDIT_M_CONTENT = 9
STATE_EDIT_M_REFS = 10
STATE_EDIT_M_PRICE = 11


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
        f"📚 <b>Active Methods:</b> <code>{stats.get('total_methods', 1)}</code>\n"
        f"🏆 <b>Total Referrals:</b> <code>{stats['total_referrals']}</code>\n"
        f"💰 <b>Total Balance Issued:</b> <code>{stats['total_balance']}</code>\n\n"
        f"<i>Select an option from the menu below:</i>"
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=get_admin_inline_menu(),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await update.callback_query.message.reply_text(
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
            f"📚 <b>Active Methods:</b> <code>{stats.get('total_methods', 1)}</code>\n"
            f"🏆 <b>Total Referrals:</b> <code>{stats['total_referrals']}</code>\n"
            f"💰 <b>Total Balance Issued:</b> <code>{stats['total_balance']}</code>\n\n"
            f"<i>Select an option below:</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=get_admin_inline_menu(), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_admin_inline_menu(), parse_mode=ParseMode.HTML)

    elif data == "admin_methods":
        methods = database.get_all_methods()
        text = (
            f"📚 <b>Methods & Courses Manager</b>\n\n"
            f"Total Available Methods: <b>{len(methods)}</b>\n\n"
            f"<i>Click on any method below to view, edit content/photo, required referrals, price, or delete. Click '➕ Add New Method' to create a new one:</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=get_methods_manager_keyboard(methods), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_methods_manager_keyboard(methods), parse_mode=ParseMode.HTML)

    elif data.startswith("manage_method_"):
        mid = int(data.split("_")[2])
        m = database.get_method(mid)
        if not m:
            await query.answer("❌ Method not found.", show_alert=True)
            return
        
        currency = database.get_setting("currency_name", config.CURRENCY_NAME)
        import re
        clean_desc = re.sub(r'<[^>]+>', '', m.get("description", "")).strip()
        if len(clean_desc) > 150:
            clean_desc = clean_desc[:150] + "..."
            
        has_photo = "✅ Yes" if m.get("photo_file_id") else "❌ No"
        
        text = (
            f"💎 <b>Method Settings: {m['title']}</b>\n\n"
            f"👥 <b>Required Referrals:</b> <code>{m['required_referrals']} invites</code>\n"
            f"💵 <b>USDT Price:</b> <code>{m['price']} {currency}</code>\n"
            f"🖼 <b>Has Photo/Image:</b> {has_photo}\n\n"
            f"📝 <b>Content Preview:</b>\n"
            f"<i>{clean_desc}</i>\n\n"
            f"<i>Choose an action below to update or delete:</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=get_single_method_manage_keyboard(mid), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_single_method_manage_keyboard(mid), parse_mode=ParseMode.HTML)

    elif data.startswith("del_method_"):
        mid = int(data.split("_")[2])
        m = database.get_method(mid)
        if m:
            database.delete_method(mid)
            await query.answer(f"✅ Deleted {m['title']}", show_alert=True)
        methods = database.get_all_methods()
        text = (
            f"📚 <b>Methods & Courses Manager</b>\n\n"
            f"Method deleted successfully!\n"
            f"Total Available Methods: <b>{len(methods)}</b>\n\n"
            f"<i>Click on any method below or add a new one:</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=get_methods_manager_keyboard(methods), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_methods_manager_keyboard(methods), parse_mode=ParseMode.HTML)

    elif data == "admin_channels":
        channels = database.get_all_channels()
        text = (
            f"📢 <b>Mandatory Channels & Groups Manager</b>\n\n"
            f"Total Configured: <b>{len(channels)}</b>\n\n"
            f"Users MUST join all these channels and groups before using the bot.\n\n"
            f"<i>Click on any channel below to remove it, or click '➕ Add Channel / Group'.</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=get_channels_manager_keyboard(channels), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_channels_manager_keyboard(channels), parse_mode=ParseMode.HTML)

    elif data.startswith("del_channel_"):
        channel_id = int(data.split("_")[2])
        ch = database.get_channel(channel_id)
        if ch:
            database.remove_channel(channel_id)
            await query.answer(f"✅ Removed {ch['title']}", show_alert=True)
        channels = database.get_all_channels()
        try:
            await query.edit_message_text(
                f"📢 <b>Mandatory Channels & Groups Manager</b>\n\nChannel removed successfully!\nTotal Channels: <b>{len(channels)}</b>",
                reply_markup=get_channels_manager_keyboard(channels),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

    elif data == "admin_close":
        await query.edit_message_text("🔒 Admin panel closed.")


# --- CHANNEL ADD CONVERSATION ---

def extract_chat_identifier(chat_input: str, msg: Any) -> Any:
    """Extracts chat ID or username from text, t.me links, or forwarded messages."""
    if msg:
        if hasattr(msg, "forward_from_chat") and msg.forward_from_chat:
            return msg.forward_from_chat.id
        if hasattr(msg, "forward_origin") and getattr(msg.forward_origin, "chat", None):
            return msg.forward_origin.chat.id

    raw = chat_input.strip()
    if (raw.startswith("-") and raw[1:].isdigit()) or raw.isdigit():
        return int(raw)

    cleaned = raw.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "").strip("/")
    if not cleaned.startswith("@") and not cleaned.startswith("+"):
        cleaned = f"@{cleaned}"
    return cleaned


async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts add channel/group flow."""
    query = update.callback_query
    await query.answer()

    text = (
        f"➕ <b>Add Channel or Group</b>\n\n"
        f"1. <b>First, make sure to add this bot as an ADMIN in your Channel or Group!</b>\n"
        f"2. Send the Channel/Group <b>Username</b> (e.g. <code>@MyChannel</code>), <b>Link</b> (e.g. <code>https://t.me/MyChannel</code>), or <b>Forward a message</b> here:\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_channels"), parse_mode=ParseMode.HTML)
    return STATE_ADD_CHANNEL_ID


async def add_channel_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles channel ID/username/link input from admin."""
    chat_input = update.message.text.strip() if update.message and update.message.text else ""
    parsed_id = extract_chat_identifier(chat_input, update.message)
    
    try:
        chat = await context.bot.get_chat(chat_id=parsed_id)
        
        # Verify bot is an admin in the channel
        bot_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=context.bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            await update.message.reply_text(
                f"⚠️ <b>Bot is not an Admin!</b>\n\n"
                f"Found channel: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)\n"
                f"However, this bot is NOT an administrator in this channel.\n\n"
                f"👉 <b>Please promote the bot to Administrator in {chat.title}</b> with 'Invite Users' permission and try again, or send /cancel.",
                parse_mode=ParseMode.HTML
            )
            return STATE_ADD_CHANNEL_ID

        context.user_data["new_channel_chat_id"] = str(chat.id)
        context.user_data["new_channel_title"] = chat.title or str(parsed_id)
        
        default_link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
        context.user_data["new_channel_link"] = default_link

        if default_link:
            text = (
                f"✅ Found & Verified: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)\n"
                f"🔗 Detected Link: <code>{default_link}</code>\n\n"
                f"Send a custom invite link if you wish, or reply <code>default</code> to use the detected link:"
            )
        else:
            text = (
                f"✅ Found & Verified: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)\n\n"
                f"🔗 Please send the <b>Invite Link</b> for this channel/group (e.g. <code>https://t.me/+AbCdEfGh</code>):"
            )

        await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_channels"), parse_mode=ParseMode.HTML)
        return STATE_ADD_CHANNEL_LINK

    except TelegramError as e:
        await update.message.reply_text(
            f"❌ <b>Could not access channel:</b> {e}\n\n"
            f"⚠️ <b>Important Checklist:</b>\n"
            f"1. Make sure you added <b>this bot</b> into the channel/group as an <b>ADMINISTRATOR</b>.\n"
            f"2. You can send the username (e.g. <code>@bdhitlog</code>), the full link (<code>https://t.me/bdhitlog</code>), or simply <b>forward any message</b> from the channel here.\n\n"
            f"Please check and send again, or send /cancel.",
            parse_mode=ParseMode.HTML
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


# --- ADD METHOD CONVERSATION ---

async def admin_add_method_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the dynamic method creation flow."""
    query = update.callback_query
    if query:
        await query.answer()
        text = (
            "➕ <b>Add New Method / Course</b>\n\n"
            "Step 1/4: Send the <b>Title / Name</b> for this method (e.g. <code>💎 Gemini 18 Month Method</code> or <code>🎨 Canva Pro Lifetime</code>):\n\n"
            "Send /cancel to abort."
        )
        try:
            await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_TITLE


async def admin_add_m_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles method title or direct photo/post forward."""
    msg = update.message
    if not msg:
        return STATE_ADD_M_TITLE

    # If admin sent a photo with caption right away (or forwarded a photo post)
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        caption = msg.caption_html if msg.caption_html else (msg.caption or "")
        
        # Extract title from caption first line, or use default
        lines = [l.strip() for l in caption.split("\n") if l.strip()]
        title = lines[0][:45] if lines else "Premium Method"
        desc = caption if caption else "Premium Method Tutorial & Details."

        context.user_data["new_m_title"] = title
        context.user_data["new_m_photo"] = photo_file_id
        context.user_data["new_m_desc"] = desc

        text = (
            f"✅ <b>Detected Title:</b> <code>{title}</code>\n"
            f"🖼 <b>Photo & Content Saved!</b>\n\n"
            f"Step 3/4: Send the <b>Required Referrals</b> number to unlock this method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
            f"Send /cancel to abort."
        )
        await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
        return STATE_ADD_M_REFS

    # If admin sent text
    raw_text = msg.text_html if msg.text_html else (msg.text or "")
    plain_text = msg.text or ""
    lines = [l.strip() for l in plain_text.split("\n") if l.strip()]

    # If multi-line post forwarded as text
    if len(lines) > 2 or len(plain_text) > 80:
        title = lines[0][:45]
        context.user_data["new_m_title"] = title
        context.user_data["new_m_photo"] = ""
        context.user_data["new_m_desc"] = raw_text

        text = (
            f"✅ <b>Detected Title:</b> <code>{title}</code>\n"
            f"📝 <b>Content Guide Saved!</b>\n\n"
            f"Step 3/4: Send the <b>Required Referrals</b> number to unlock this method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
            f"Send /cancel to abort."
        )
        await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
        return STATE_ADD_M_REFS

    # Normal single-line title
    title = plain_text.strip()
    context.user_data["new_m_title"] = title
    
    text = (
        f"✅ Title: <b>{title}</b>\n\n"
        f"Step 2/4: Send the <b>Content / Guide</b> for this method.\n\n"
        f"📷 <b>You can send a PHOTO with a caption</b>, or just send a <b>TEXT message</b> with instructions/links:\n\n"
        f"Send /cancel to abort."
    )
    await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_CONTENT


async def admin_add_m_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles method content (Text or Photo with caption)."""
    msg = update.message
    if not msg:
        return STATE_ADD_M_CONTENT
        
    photo_file_id = ""
    description = ""
    
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        description = msg.caption_html if msg.caption_html else (msg.caption or "Method guide & details.")
    elif msg.text:
        description = msg.text_html if msg.text_html else msg.text
    else:
        await msg.reply_text("❌ Please send either a text message or a photo with a caption.")
        return STATE_ADD_M_CONTENT

    context.user_data["new_m_photo"] = photo_file_id
    context.user_data["new_m_desc"] = description
    
    text = (
        f"✅ Content & Photo saved!\n\n"
        f"Step 3/4: Send the <b>Required Referrals</b> number to unlock this method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
        f"Send /cancel to abort."
    )
    await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_REFS


async def admin_add_m_refs_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles required referrals input."""
    text_input = update.message.text.strip()
    if not text_input.isdigit():
        await update.message.reply_text("❌ Please enter a valid integer number (e.g. 5 or 0).")
        return STATE_ADD_M_REFS
        
    context.user_data["new_m_refs"] = int(text_input)
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    
    text = (
        f"✅ Required Referrals: <b>{text_input}</b>\n\n"
        f"Step 4/4: Send the <b>Price in {currency}</b> (e.g. <code>0</code> for free with referrals, or <code>5.0</code>):\n\n"
        f"Send /cancel to abort."
    )
    await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_PRICE


async def admin_add_m_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new dynamic method to database."""
    text_input = update.message.text.strip()
    try:
        price = float(text_input)
        if price < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return STATE_ADD_M_PRICE

    title = context.user_data.get("new_m_title", "New Method")
    desc = context.user_data.get("new_m_desc", "")
    photo = context.user_data.get("new_m_photo", "")
    refs = context.user_data.get("new_m_refs", 5)
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)

    database.add_method(title=title, description=desc, photo_file_id=photo, required_referrals=refs, price=price)
    
    methods = database.get_all_methods()
    await update.message.reply_text(
        f"🎉 <b>Method Created Successfully!</b>\n\n"
        f"💎 <b>Title:</b> {title}\n"
        f"👥 <b>Required Referrals:</b> {refs}\n"
        f"💵 <b>Price:</b> {price} {currency}\n"
        f"🖼 <b>Photo:</b> {'Attached' if photo else 'None'}\n\n"
        f"Users can now access and unlock this method directly from the bot menu!",
        reply_markup=get_methods_manager_keyboard(methods),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# --- EDIT METHOD CONVERSATIONS ---

async def admin_edit_m_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts editing content/photo for a specific method."""
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[3])
    context.user_data["edit_target_method_id"] = mid
    
    m = database.get_method(mid)
    title = m["title"] if m else "Method"
    
    text = (
        f"📝 <b>Edit Content & Photo for: {title}</b>\n\n"
        f"Send the new text guide OR send a <b>PHOTO with caption</b>:\n\n"
        f"Send /cancel to abort."
    )
    try:
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    except Exception:
        await query.message.reply_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    return STATE_EDIT_M_CONTENT


async def admin_edit_m_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves updated content/photo for method."""
    mid = context.user_data.get("edit_target_method_id")
    msg = update.message
    photo_file_id = ""
    description = ""
    
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        description = msg.caption_html if msg.caption_html else (msg.caption or "")
    elif msg.text:
        description = msg.text_html if msg.text_html else msg.text
        
    database.update_method(mid, description=description, photo_file_id=photo_file_id)
    
    await update.message.reply_text(
        "✅ <b>Method content & photo updated successfully!</b>",
        reply_markup=get_single_method_manage_keyboard(mid),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def admin_edit_m_refs_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts editing required referrals for a method."""
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[3])
    context.user_data["edit_target_method_id"] = mid
    m = database.get_method(mid)
    current_refs = m["required_referrals"] if m else 5
    
    text = (
        f"👥 <b>Set Required Referrals for: {m['title'] if m else ''}</b>\n\n"
        f"Current: <b>{current_refs} referrals</b>\n\n"
        f"Send the new number of referrals needed to unlock (e.g. <code>5</code>, <code>10</code>, or <code>0</code>):\n\n"
        f"Send /cancel to abort."
    )
    try:
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    except Exception:
        await query.message.reply_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    return STATE_EDIT_M_REFS


async def admin_edit_m_refs_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves updated referrals limit."""
    mid = context.user_data.get("edit_target_method_id")
    text_input = update.message.text.strip()
    if not text_input.isdigit():
        await update.message.reply_text("❌ Please enter a valid number (e.g. 5 or 0).")
        return STATE_EDIT_M_REFS
        
    refs = int(text_input)
    database.update_method(mid, required_referrals=refs)
    
    await update.message.reply_text(
        f"✅ <b>Required referrals updated to {refs} invites!</b>",
        reply_markup=get_single_method_manage_keyboard(mid),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def admin_edit_m_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts editing price for a method."""
    query = update.callback_query
    await query.answer()
    mid = int(query.data.split("_")[3])
    context.user_data["edit_target_method_id"] = mid
    m = database.get_method(mid)
    current_price = m["price"] if m else 0.0
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    
    text = (
        f"💵 <b>Set USDT Price for: {m['title'] if m else ''}</b>\n\n"
        f"Current Price: <b>{current_price} {currency}</b>\n\n"
        f"Send the new price in USDT (e.g. <code>0</code> or <code>10.0</code>):\n\n"
        f"Send /cancel to abort."
    )
    try:
        await query.edit_message_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    except Exception:
        await query.message.reply_text(text, reply_markup=get_cancel_keyboard(f"manage_method_{mid}"), parse_mode=ParseMode.HTML)
    return STATE_EDIT_M_PRICE


async def admin_edit_m_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves updated price."""
    mid = context.user_data.get("edit_target_method_id")
    text_input = update.message.text.strip()
    try:
        price = float(text_input)
        if price < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return STATE_EDIT_M_PRICE
        
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    database.update_method(mid, price=price)
    
    await update.message.reply_text(
        f"✅ <b>Price updated to {price:.2f} {currency}!</b>",
        reply_markup=get_single_method_manage_keyboard(mid),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels ongoing conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text("❌ Action cancelled.", reply_markup=get_admin_inline_menu())
        except Exception:
            await update.callback_query.message.reply_text("❌ Action cancelled.", reply_markup=get_admin_inline_menu())
    elif update.message:
        await update.message.reply_text("❌ Action cancelled.", reply_markup=get_admin_inline_menu())
    return ConversationHandler.END
