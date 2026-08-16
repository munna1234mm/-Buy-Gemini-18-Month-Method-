import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database
import config
from verification import check_user_membership, build_join_keyboard
from keyboards import get_user_inline_menu, get_back_to_user_keyboard

logger = logging.getLogger(__name__)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start command, referral link registration, and mandatory channel/group check."""
    if not update.effective_user or not update.effective_message:
        return

    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or "Friend"

    # Check for referral payload: /start <referrer_id>
    referrer_id = None
    if context.args and len(context.args) > 0:
        arg = context.args[0].strip()
        if arg.isdigit() and int(arg) != user_id:
            referrer_id = int(arg)

    # Register user in database
    db_user, is_new = database.get_or_create_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referrer_id=referrer_id
    )

    if db_user.get("is_banned"):
        await update.effective_message.reply_text("🚫 You are banned from using this bot.")
        return

    # Check mandatory channels and groups join status
    is_joined, unjoined = await check_user_membership(context.bot, user_id)

    if not is_joined:
        keyboard = build_join_keyboard(unjoined)
        welcome_text = (
            f"👋 <b>Hello {first_name}!</b>\n\n"
            f"⚠️ <b>Action Required:</b>\n"
            f"To access the bot and start earning rewards, please join our official channels & groups below:\n\n"
            f"<i>After joining all of them, click the '✅ I Have Joined / Verify' button.</i>"
        )
        await update.effective_message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        return

    # If verified/joined all channels
    database.set_user_verified(user_id, True)
    await process_referral_reward_if_needed(context, user_id, first_name)

    is_admin_user = database.is_admin(user_id)
    menu_keyboard = get_user_inline_menu(is_admin_user=is_admin_user)
    
    welcome_text = (
        f"👋 <b>Welcome {first_name}!</b>\n\n"
        f"🚀 <b>Referral & Earning Program</b>\n"
        f"Invite your friends and earn points easily!\n\n"
        f"<i>Select an option from the menu below:</i>"
    )
    await update.effective_message.reply_text(
        welcome_text,
        reply_markup=menu_keyboard,
        parse_mode=ParseMode.HTML
    )


async def check_join_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles '✅ I Have Joined / Verify' click."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user:
        return

    user_id = user.id
    first_name = user.first_name or "Friend"

    # Re-check membership using get_chat_member
    is_joined, unjoined = await check_user_membership(context.bot, user_id)

    if not is_joined:
        await query.answer("❌ You have not joined all channels yet! Please join and try again.", show_alert=True)
        keyboard = build_join_keyboard(unjoined)
        try:
            await query.edit_message_text(
                f"⚠️ <b>Missing Channels / Groups:</b>\n\n"
                f"You must join all channels and groups listed below before using the bot:",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    # User joined all channels successfully
    database.set_user_verified(user_id, True)
    await process_referral_reward_if_needed(context, user_id, first_name)

    is_admin_user = database.is_admin(user_id)
    menu_keyboard = get_user_inline_menu(is_admin_user=is_admin_user)

    welcome_text = (
        f"🎉 <b>Membership Verified!</b>\n\n"
        f"👋 <b>Welcome {first_name}!</b>\n"
        f"🚀 <b>Referral & Earning Program</b>\n"
        f"Invite your friends and earn rewards!\n\n"
        f"<i>Select an option from the menu below:</i>"
    )
    await query.edit_message_text(
        welcome_text,
        reply_markup=menu_keyboard,
        parse_mode=ParseMode.HTML
    )


async def process_referral_reward_if_needed(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    """Rewards the referrer when the invited user joins mandatory channels."""
    reward_info = database.complete_referral_reward(user_id)
    if reward_info:
        referrer_id, reward = reward_info
        currency = database.get_setting("currency_name", config.CURRENCY_NAME)
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=(
                    f"🎉 <b>New Referral Joined!</b>\n\n"
                    f"👤 <b>{first_name}</b> joined all channels and verified.\n"
                    f"💰 <b>+{reward} {currency}</b> has been credited to your balance!"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Could not notify referrer {referrer_id}: {e}")


# --- USER MENU HANDLERS ---

async def user_main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns to user main menu."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "Friend"
    is_admin_user = database.is_admin(user_id)

    welcome_text = (
        f"👋 <b>Welcome {first_name}!</b>\n\n"
        f"🚀 <b>Referral & Earning Program</b>\n"
        f"Invite your friends and earn rewards!\n\n"
        f"<i>Select an option from the menu below:</i>"
    )
    await query.edit_message_text(
        welcome_text,
        reply_markup=get_user_inline_menu(is_admin_user=is_admin_user),
        parse_mode=ParseMode.HTML
    )


async def user_ref_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's unique referral link and sharing options."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user:
        return

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    reward = database.get_setting("referral_reward", str(config.DEFAULT_REFERRAL_REWARD))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    referral_count = user.get("referral_count", 0)

    share_url = f"https://t.me/share/url?url={ref_link}&text=Join+and+earn+{reward}+{currency}!"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link With Friends", url=share_url)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
    ])

    text = (
        f"👥 <b>Your Referral Program</b>\n\n"
        f"🔗 <b>Your Unique Invite Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"💵 <b>Reward per Referral:</b> {reward} {currency}\n"
        f"📊 <b>Total Friends Invited:</b> {referral_count}\n\n"
        f"<i>Share this invite link with your friends. Once they join all required channels and verify, you will instantly receive your reward!</i>"
    )

    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


async def user_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's balance and earning stats."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user:
        return

    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    balance = float(user.get("balance", 0.0))
    referral_count = user.get("referral_count", 0)

    text = (
        f"💰 <b>Your Account Balance</b>\n\n"
        f"💳 <b>Current Balance:</b> <code>{balance:.2f} {currency}</code>\n"
        f"👥 <b>Total Referrals:</b> <code>{referral_count}</code>\n"
    )

    await query.edit_message_text(
        text,
        reply_markup=get_back_to_user_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def user_gemini_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles '💎 Buy Gemini 18 Month Method' button click."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user:
        return

    # Check required referrals limit set by admin
    required_refs = int(database.get_setting("gemini_required_referrals", "5"))
    method_price = float(database.get_setting("gemini_method_price", "0.0"))
    method_content = database.get_setting("gemini_method_content", "Method details will be added soon by admin.")
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    user_refs = user.get("referral_count", 0)
    user_balance = float(user.get("balance", 0.0))

    if user_refs < required_refs:
        # User has not reached the referral requirement
        remaining = required_refs - user_refs
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Get Referral Link", callback_data="user_ref_link")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        text = (
            f"🔒 <b>Gemini 18 Month Method is Locked!</b>\n\n"
            f"⚠️ <b>Referral Requirement:</b>\n"
            f"You need at least <b>{required_refs} referrals</b> to unlock this method.\n\n"
            f"📊 <b>Your Progress:</b>\n"
            f"• Current Referrals: <code>{user_refs} / {required_refs}</code>\n"
            f"• Still Needed: <b>{remaining} more friend(s)</b>\n\n"
            f"<i>Invite your friends using your referral link to unlock full access to the method!</i>"
        )
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        return

    # If price is required and balance is not enough
    if method_price > 0 and user_balance < method_price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Earn by Referring", callback_data="user_ref_link")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        text = (
            f"💎 <b>Gemini 18 Month Method</b>\n\n"
            f"✅ Referral Requirement Met ({user_refs}/{required_refs} invites)!\n"
            f"💵 <b>Price:</b> <code>{method_price:.2f} {currency}</code>\n"
            f"💳 <b>Your Balance:</b> <code>{user_balance:.2f} {currency}</code>\n\n"
            f"⚠️ Insufficient balance to purchase. Refer more friends to earn USDT!"
        )
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        return

    # If requirements met: display full method content & details configured by Admin
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
    ])

    text = (
        f"💎 <b>Gemini 18 Month Method (UNLOCKED)</b>\n\n"
        f"{method_content}\n\n"
        f"<i>Status: ✅ Verified & Active Access</i>"
    )

    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


