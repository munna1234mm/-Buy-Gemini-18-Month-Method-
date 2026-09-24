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

    # Bot should only start in private chat with users, never spam public groups
    if update.effective_chat and update.effective_chat.type != "private":
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
    if not user:
        return
    user_id = user.id
    first_name = user.first_name or "Friend"
    is_admin_user = database.is_admin(user_id)

    welcome_text = (
        f"👋 <b>Welcome {first_name}!</b>\n\n"
        f"🚀 <b>Referral & Earning Program</b>\n"
        f"Invite your friends and earn rewards!\n\n"
        f"<i>Select an option from the menu below:</i>"
    )
    try:
        await query.edit_message_text(
            welcome_text,
            reply_markup=get_user_inline_menu(is_admin_user=is_admin_user),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=welcome_text,
            reply_markup=get_user_inline_menu(is_admin_user=is_admin_user),
            parse_mode=ParseMode.HTML
        )


async def user_ref_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's unique referral link and sharing options."""
    query = update.callback_query
    await query.answer()

    eff_user = update.effective_user
    if not eff_user:
        return
    user_id = eff_user.id
    user, _ = database.get_or_create_user(
        user_id=user_id,
        username=eff_user.username,
        first_name=eff_user.first_name
    )

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

    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )


async def user_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays user's balance and earning stats."""
    query = update.callback_query
    await query.answer()

    eff_user = update.effective_user
    if not eff_user:
        return
    user_id = eff_user.id
    user, _ = database.get_or_create_user(
        user_id=user_id,
        username=eff_user.username,
        first_name=eff_user.first_name
    )

    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    balance = float(user.get("balance", 0.0))
    referral_count = user.get("referral_count", 0)

    text = (
        f"💰 <b>Your Account Balance</b>\n\n"
        f"💳 <b>Current Balance:</b> <code>{balance:.2f} {currency}</code>\n"
        f"👥 <b>Total Referrals:</b> <code>{referral_count}</code>\n"
    )

    try:
        await query.edit_message_text(
            text,
            reply_markup=get_back_to_user_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=get_back_to_user_keyboard(),
            parse_mode=ParseMode.HTML
        )


async def user_method_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles click on any dynamic method button."""
    query = update.callback_query
    await query.answer()

    eff_user = update.effective_user
    if not eff_user:
        return
    user_id = eff_user.id
    user, _ = database.get_or_create_user(
        user_id=user_id,
        username=eff_user.username,
        first_name=eff_user.first_name
    )

    data = query.data
    try:
        method_id = int(data.split("_")[2])
    except (IndexError, ValueError):
        method_id = 1

    method = database.get_method(method_id)
    if not method:
        await query.answer("❌ This method is no longer available.", show_alert=True)
        try:
            await query.edit_message_text(
                "❌ This method is no longer available.",
                reply_markup=get_back_to_user_keyboard()
            )
        except Exception:
            pass
        return

    required_refs = int(method.get("required_referrals", 0))
    method_price = float(method.get("price", 0.0))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    user_refs = user.get("referral_count", 0)
    user_balance = float(user.get("balance", 0.0))

    # 1. Check if user already purchased / unlocked this method
    is_purchased = database.has_user_purchased(user_id, method_id)
    if is_purchased or (required_refs == 0 and method_price == 0.0):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        unlocked_text = (
            f"💎 <b>{method['title']} (UNLOCKED)</b>\n\n"
            f"{method['description']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Status: ✅ Permanent Access Unlocked</i>"
        )
        photo_id = method.get("photo_file_id")
        if photo_id:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=unlocked_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            try:
                await query.edit_message_text(
                    unlocked_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception:
                await query.message.reply_text(
                    unlocked_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
        return

    # 2. Check Referral Requirement
    if user_refs < required_refs:
        remaining = required_refs - user_refs
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Get Referral Link", callback_data="user_ref_link")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        text = (
            f"🔒 <b>{method['title']} is Locked!</b>\n\n"
            f"📋 <b>Requirements to Unlock:</b>\n"
            f"👥 Required Referrals: <b>{required_refs} invites</b>\n"
            f"💵 Method Price: <b>{method_price:.2f} {currency}</b>\n\n"
            f"📊 <b>Your Current Progress:</b>\n"
            f"• Current Referrals: <code>{user_refs} / {required_refs}</code>\n"
            f"• Still Needed: <b>{remaining} more friend(s)</b>\n"
            f"• Your Balance: <code>{user_balance:.2f} {currency}</code>\n\n"
            f"<i>Invite your friends using your referral link to reach {required_refs} referrals and unlock this method!</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    # 3. Referral Requirement Met - Check Price
    if method_price <= 0.0:
        # Free method with referrals met - record purchase and deliver
        database.record_purchase(user_id, method_id, 0.0, method['title'])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        unlocked_text = (
            f"🎉 <b>Method Unlocked!</b>\n\n"
            f"💎 <b>{method['title']}</b>\n\n"
            f"{method['description']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Status: ✅ Free Access Unlocked via Referrals</i>"
        )
        photo_id = method.get("photo_file_id")
        if photo_id:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=unlocked_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            try:
                await query.edit_message_text(unlocked_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            except Exception:
                await query.message.reply_text(unlocked_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    # Method requires USDT payment
    if user_balance < method_price:
        needed = method_price - user_balance
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Earn by Referring", callback_data="user_ref_link")],
            [InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
        ])
        text = (
            f"💎 <b>{method['title']}</b>\n\n"
            f"✅ <b>Referral Requirement Met:</b> <code>{user_refs}/{required_refs} invites</code>\n\n"
            f"💵 <b>Price:</b> <code>{method_price:.2f} {currency}</code>\n"
            f"💳 <b>Your Balance:</b> <code>{user_balance:.2f} {currency}</code>\n"
            f"⚠️ <b>Balance Needed:</b> <code>{needed:.2f} {currency}</code>\n\n"
            f"<i>You do not have enough {currency} to buy this method. Invite friends using your referral link to earn more balance!</i>"
        )
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    # Balance is sufficient - Show Buy / Unlock confirmation button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Buy / Unlock with {method_price:.2f} {currency}", callback_data=f"buy_method_{method_id}")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
    ])
    text = (
        f"💎 <b>{method['title']}</b>\n\n"
        f"✅ <b>Referral Requirement Met:</b> <code>{user_refs}/{required_refs} invites</code>\n\n"
        f"💵 <b>Price:</b> <code>{method_price:.2f} {currency}</code>\n"
        f"💳 <b>Your Balance:</b> <code>{user_balance:.2f} {currency}</code>\n"
        f"💰 <b>Remaining After Purchase:</b> <code>{user_balance - method_price:.2f} {currency}</code>\n\n"
        f"<i>Click the button below to confirm your purchase and permanently unlock this method:</i>"
    )
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception:
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def buy_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles purchase confirmation and balance deduction for a method."""
    query = update.callback_query
    await query.answer()

    eff_user = update.effective_user
    if not eff_user:
        return
    user_id = eff_user.id
    user = database.get_user(user_id)
    if not user:
        return

    data = query.data
    try:
        method_id = int(data.split("_")[2])
    except (IndexError, ValueError):
        return

    method = database.get_method(method_id)
    if not method:
        await query.answer("❌ This method is no longer available.", show_alert=True)
        return

    # Check if already purchased
    if database.has_user_purchased(user_id, method_id):
        await query.answer("✅ You have already purchased this method!", show_alert=True)
        await user_method_details_callback(update, context)
        return

    required_refs = int(method.get("required_referrals", 0))
    method_price = float(method.get("price", 0.0))
    currency = database.get_setting("currency_name", config.CURRENCY_NAME)
    user_refs = user.get("referral_count", 0)
    user_balance = float(user.get("balance", 0.0))

    if user_refs < required_refs:
        await query.answer(f"❌ You need {required_refs} referrals to buy this method.", show_alert=True)
        await user_method_details_callback(update, context)
        return

    if user_balance < method_price:
        await query.answer(f"❌ Insufficient balance! You need {method_price:.2f} {currency}.", show_alert=True)
        await user_method_details_callback(update, context)
        return

    # Deduct balance and record purchase
    if method_price > 0:
        database.update_balance(user_id, -method_price)
    database.record_purchase(user_id, method_id, method_price, method['title'])

    new_balance = max(0.0, user_balance - method_price)
    await query.answer(f"🎉 Purchase successful! Unlocked {method['title']}", show_alert=True)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
    ])

    congrats_text = (
        f"🎉 <b>Purchase Successful!</b>\n\n"
        f"💰 <b>Amount Deducted:</b> <code>{method_price:.2f} {currency}</code>\n"
        f"💳 <b>New Balance:</b> <code>{new_balance:.2f} {currency}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>{method['title']} (UNLOCKED)</b>\n\n"
        f"{method['description']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Status: ✅ Permanent Access Unlocked</i>"
    )

    photo_id = method.get("photo_file_id")
    if photo_id:
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_photo(
            chat_id=user_id,
            photo=photo_id,
            caption=congrats_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        try:
            await query.edit_message_text(
                congrats_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            await query.message.reply_text(
                congrats_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )




