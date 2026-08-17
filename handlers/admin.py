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


# --- CHANNEL ADD CONVERSATION (SUPPORTS SINGLE & BULK ADD) ---

def extract_chat_identifier(chat_input: str, msg: Any = None) -> Any:
    """Extracts chat ID or username from text, t.me links, or forwarded messages."""
    if msg:
        if hasattr(msg, "forward_from_chat") and msg.forward_from_chat:
            return msg.forward_from_chat.id
        if hasattr(msg, "forward_origin") and getattr(msg.forward_origin, "chat", None):
            return msg.forward_origin.chat.id

    raw = chat_input.strip()
    if (raw.startswith("-") and raw[1:].isdigit()) or raw.isdigit():
        return int(raw)

    cleaned = (
        raw.replace("@http://", "")
        .replace("@https://", "")
        .replace("https://", "")
        .replace("http://", "")
        .replace("t.me/", "")
        .replace("telegram.me/", "")
        .strip("/")
    )
    if not cleaned.startswith("@") and not cleaned.startswith("+"):
        cleaned = f"@{cleaned}"
    return cleaned


async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts add channel/group flow (supports single and bulk/multiple channels at once)."""
    query = update.callback_query
    await query.answer()

    text = (
        f"➕ <b>Add Channel(s) or Group(s)</b>\n\n"
        f"⚡ <b>Bulk Add Supported:</b> You can send <b>ONE or ALL your channels at once</b>!\n\n"
        f"1. Make sure this bot is added as an <b>ADMIN</b> in each channel/group.\n"
        f"2. Send usernames or links (one per line, separated by space or commas), or forward a message:\n\n"
        f"<i>Example:</i>\n"
        f"<code>@MyChannel1\nhttps://t.me/MyChannel2\n@MyGroup3</code>\n\n"
        f"Send /cancel to abort."
    )
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_channels"), parse_mode=ParseMode.HTML)
    return STATE_ADD_CHANNEL_ID


async def add_channel_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles channel ID/username/link input (single or multiple lines/links) from admin."""
    msg = update.message
    if not msg:
        return STATE_ADD_CHANNEL_ID

    # If forwarded from channel
    if msg.forward_from_chat or (hasattr(msg, "forward_origin") and getattr(msg.forward_origin, "chat", None)):
        forward_chat = msg.forward_from_chat or getattr(msg.forward_origin, "chat", None)
        raw_items = [forward_chat.id]
    else:
        text_input = msg.text or ""
        import re
        raw_tokens = re.split(r'[\r\n, \t]+', text_input.strip())
        raw_items = [t.strip() for t in raw_tokens if t.strip()]

    if not raw_items:
        await msg.reply_text("❌ Please send at least one channel username or link, or send /cancel.")
        return STATE_ADD_CHANNEL_ID

    status_msg = await msg.reply_text(f"⏳ Verifying and adding {len(raw_items)} channel(s)...")

    added_channels = []
    failed_channels = []

    for item in raw_items:
        parsed_id = extract_chat_identifier(str(item), msg if len(raw_items) == 1 else None)
        try:
            chat = await context.bot.get_chat(chat_id=parsed_id)
            
            # Check bot admin status
            try:
                bot_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=context.bot.id)
                if bot_member.status not in ["administrator", "creator"]:
                    failed_channels.append(f"• <b>{chat.title}</b>: Bot is not an Admin.")
                    continue
            except Exception as e:
                failed_channels.append(f"• <b>{chat.title}</b>: Bot must be Admin ({e}).")
                continue

            # Determine invite link automatically
            invite_link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or "")
            if not invite_link:
                try:
                    invite_link = await context.bot.export_chat_invite_link(chat_id=chat.id)
                except Exception:
                    invite_link = f"https://t.me/{chat.id}"

            database.add_channel(chat_id=str(chat.id), title=chat.title or str(parsed_id), invite_link=invite_link)
            added_channels.append(f"• ✅ <b>{chat.title}</b> (<code>{invite_link}</code>)")

        except Exception as e:
            failed_channels.append(f"• <code>{item}</code>: {e}")

    result_text = "📊 <b>Channel Addition Summary</b>\n\n"
    if added_channels:
        result_text += f"🎉 <b>Successfully Added ({len(added_channels)}):</b>\n" + "\n".join(added_channels) + "\n\n"
    if failed_channels:
        result_text += f"⚠️ <b>Failed / Not Admin ({len(failed_channels)}):</b>\n" + "\n".join(failed_channels) + "\n\n"
        
    result_text += "<i>Users must now join all active channels to use the bot.</i>"

    channels = database.get_all_channels()
    try:
        await status_msg.edit_text(
            result_text,
            reply_markup=get_channels_manager_keyboard(channels),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        await msg.reply_text(
            result_text,
            reply_markup=get_channels_manager_keyboard(channels),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
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


async def _run_broadcast_worker(bot, admin_chat_id: int, status_message_id: int, message_to_copy, user_ids: list):
    """Background asynchronous worker for broadcast that never blocks the bot or other users."""
    success = 0
    failed = 0
    total = len(user_ids)
    
    for idx, uid in enumerate(user_ids, 1):
        try:
            await message_to_copy.copy(chat_id=uid)
            success += 1
        except TelegramError as e:
            failed += 1
            if "RetryAfter" in str(e):
                import re
                match = re.search(r'(\d+)', str(e))
                delay = int(match.group(1)) if match else 2
                await asyncio.sleep(delay)
        except Exception:
            failed += 1

        # Smooth rate limiting
        await asyncio.sleep(0.035)

        # Update progress report every 40 messages or at finish
        if idx % 40 == 0 or idx == total:
            try:
                await bot.edit_message_text(
                    chat_id=admin_chat_id,
                    message_id=status_message_id,
                    text=(
                        f"📤 <b>Broadcast in Progress...</b>\n\n"
                        f"📊 Progress: <code>{idx} / {total}</code> ({(idx/total)*100:.1f}%)\n"
                        f"✅ Delivered: <code>{success}</code>\n"
                        f"❌ Failed/Blocked: <code>{failed}</code>\n\n"
                        f"<i>⚡ Bot remains 100% active and lightning fast for all users!</i>"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

    try:
        await bot.edit_message_text(
            chat_id=admin_chat_id,
            message_id=status_message_id,
            text=(
                f"🎉 <b>Broadcast Finished Successfully!</b>\n\n"
                f"📊 Total Target: <code>{total}</code> users\n"
                f"✅ Successfully Delivered: <code>{success}</code>\n"
                f"❌ Failed / Blocked: <code>{failed}</code>\n\n"
                f"<i>All users received the message in background.</i>"
            ),
            reply_markup=get_admin_inline_menu(),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def broadcast_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Launches non-blocking background broadcast."""
    user_ids = database.get_all_user_ids()
    msg = update.message
    admin_id = update.effective_user.id

    if not user_ids:
        await msg.reply_text("❌ No active users found to broadcast.")
        return ConversationHandler.END

    status_msg = await msg.reply_text(
        f"🚀 <b>Broadcast Launched in Background!</b>\n\n"
        f"👥 Target: <b>{len(user_ids)} users</b>\n"
        f"⚡ <i>Broadcasting in background. You and all users can continue using the bot smoothly!</i>",
        parse_mode=ParseMode.HTML
    )
    
    # Run in background task so main loop is never blocked!
    asyncio.create_task(
        _run_broadcast_worker(
            bot=context.bot,
            admin_chat_id=admin_id,
            status_message_id=status_msg.message_id,
            message_to_copy=msg,
            user_ids=user_ids
        )
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
            "👉 <b>Step 1/4:</b> Send the <b>Button Title / Name</b> for this method (e.g. <code>🌐 Free Domain Method</code> or <code>💎 Gemini 18 Month Method</code>):\n\n"
            "Send /cancel to abort."
        )
        try:
            await query.edit_message_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_TITLE


async def admin_add_m_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles method title input."""
    msg = update.message
    if not msg:
        return STATE_ADD_M_TITLE

    # If admin sent a photo with caption right away (or forwarded a photo post)
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        caption = msg.caption_html if msg.caption_html else (msg.caption or "")
        
        lines = [l.strip() for l in caption.split("\n") if l.strip()]
        title = lines[0][:45] if lines else "Premium Method"
        desc = caption if caption else "Premium Method Tutorial & Details."

        context.user_data["new_m_title"] = title
        context.user_data["new_m_photo"] = photo_file_id
        context.user_data["new_m_desc"] = desc

        text = (
            f"✅ <b>Button Title:</b> <code>{title}</code>\n"
            f"🖼 <b>Photo & Post Content Saved!</b>\n\n"
            f"👉 <b>Step 3/4:</b> Send the <b>Required Referrals</b> needed to unlock this method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
            f"Send /cancel to abort."
        )
        await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
        return STATE_ADD_M_REFS

    # Normal title text
    raw_text = msg.text_html if msg.text_html else (msg.text or "")
    plain_text = msg.text or ""
    title = plain_text.strip()
    context.user_data["new_m_title"] = title
    
    text = (
        f"✅ <b>Button Title:</b> <code>{title}</code>\n\n"
        f"👉 <b>Step 2/4:</b> Now please send or <b>FORWARD the complete post / tutorial</b>.\n"
        f"<i>(You can forward a post with Photo, Caption, Links, Code Blocks, or plain Text)</i>:\n\n"
        f"Send /cancel to abort."
    )
    await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_CONTENT


async def admin_add_m_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles method content (Text, Photo, Document, or Forwarded Post)."""
    msg = update.message
    if not msg:
        return STATE_ADD_M_CONTENT
        
    photo_file_id = ""
    description = ""
    
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id
        description = msg.caption_html if msg.caption_html else (msg.caption or "Method guide & details.")
    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        photo_file_id = msg.document.file_id
        description = msg.caption_html if msg.caption_html else (msg.caption or "Method guide & details.")
    elif msg.text:
        description = msg.text_html if msg.text_html else msg.text
    else:
        await msg.reply_text("❌ Please send either a text message or a photo with a caption.")
        return STATE_ADD_M_CONTENT

    context.user_data["new_m_photo"] = photo_file_id
    context.user_data["new_m_desc"] = description
    
    text = (
        f"✅ <b>Post & Tutorial Saved!</b>\n\n"
        f"👉 <b>Step 3/4:</b> Send the <b>Required Referrals</b> number needed to unlock this method (e.g. <code>5</code>, <code>10</code>, or <code>0</code> for free):\n\n"
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
        f"✅ <b>Required Referrals:</b> <code>{text_input} invites</code>\n\n"
        f"👉 <b>Step 4/4:</b> Send the <b>Price in {currency}</b> (e.g. <code>0</code> for free with referrals, or <code>5.0</code>):\n\n"
        f"Send /cancel to abort."
    )
    await update.message.reply_text(text, reply_markup=get_cancel_keyboard("admin_methods"), parse_mode=ParseMode.HTML)
    return STATE_ADD_M_PRICE


async def admin_add_m_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves new dynamic method to database and Firebase."""
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
        f"💎 <b>Button Title:</b> <code>{title}</code>\n"
        f"👥 <b>Required Referrals:</b> <code>{refs} invites</code>\n"
        f"💵 <b>Price:</b> <code>{price} {currency}</code>\n"
        f"🖼 <b>Photo/Media:</b> {'✅ Attached' if photo else '❌ None'}\n\n"
        f"Users will now see the <b>[{title}]</b> button directly in their main menu!",
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
