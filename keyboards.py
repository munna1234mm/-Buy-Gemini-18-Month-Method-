from typing import List, Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import database

def get_user_inline_menu(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    """Clean user menu with Buy Gemini 18 Month Method, Referral Link and Balance."""
    keyboard = [
        [
            InlineKeyboardButton("💎 Buy Gemini 18 Month Method", callback_data="user_gemini_method")
        ],
        [
            InlineKeyboardButton("🔗 Referral Link", callback_data="user_ref_link"),
            InlineKeyboardButton("💰 My Balance", callback_data="user_balance")
        ]
    ]

    if is_admin_user:
        keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_main")])

    return InlineKeyboardMarkup(keyboard)


def get_admin_inline_menu() -> InlineKeyboardMarkup:
    """Clean admin panel menu with Gemini Method Settings."""
    keyboard = [
        [
            InlineKeyboardButton("📢 Manage Channels/Groups", callback_data="admin_channels"),
            InlineKeyboardButton("📊 Bot Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("⚙️ Set Referral Reward", callback_data="admin_reward"),
            InlineKeyboardButton("💎 Gemini Method Settings", callback_data="admin_gemini_settings")
        ],
        [
            InlineKeyboardButton("📣 Broadcast Message", callback_data="admin_broadcast"),
            InlineKeyboardButton("🔙 Back to User Menu", callback_data="user_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_gemini_settings_keyboard() -> InlineKeyboardMarkup:
    """Admin settings menu for Gemini 18 Month Method."""
    keyboard = [
        [
            InlineKeyboardButton("📝 Edit Method Content/Details", callback_data="admin_set_gemini_content")
        ],
        [
            InlineKeyboardButton("👥 Set Required Referrals", callback_data="admin_set_gemini_refs"),
            InlineKeyboardButton("💵 Set USDT Price", callback_data="admin_set_gemini_price")
        ],
        [
            InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_user_keyboard() -> InlineKeyboardMarkup:
    """Inline button to return to user main menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")]
    ])


def get_channels_manager_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Channel/Group list and management keyboard."""
    keyboard = []
    for ch in channels:
        btn_text = f"❌ Remove: {ch['title'][:20]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"del_channel_{ch['id']}")])
        
    keyboard.append([
        InlineKeyboardButton("➕ Add Channel / Group", callback_data="add_channel"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_main")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard(callback_data: str = "admin_main") -> InlineKeyboardMarkup:
    """Cancel button inline keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data=callback_data)]
    ])
