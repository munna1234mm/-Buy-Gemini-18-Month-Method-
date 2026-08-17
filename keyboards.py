from typing import List, Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import database

def get_user_inline_menu(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    """User menu with dynamically loaded methods, Referral Link, and Balance."""
    keyboard = []
    
    # Load all dynamic methods from database
    methods = database.get_all_methods()
    for m in methods:
        btn_title = m.get("title", "💎 Premium Method")
        keyboard.append([InlineKeyboardButton(btn_title, callback_data=f"user_method_{m['id']}")])
    
    # Main action buttons
    keyboard.append([
        InlineKeyboardButton("🔗 Referral Link", callback_data="user_ref_link"),
        InlineKeyboardButton("💰 My Balance", callback_data="user_balance")
    ])

    if is_admin_user:
        keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_main")])

    return InlineKeyboardMarkup(keyboard)


def get_admin_inline_menu() -> InlineKeyboardMarkup:
    """Admin panel menu with Methods Manager."""
    keyboard = [
        [
            InlineKeyboardButton("📢 Manage Channels/Groups", callback_data="admin_channels"),
            InlineKeyboardButton("📊 Bot Statistics", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("⚙️ Set Referral Reward", callback_data="admin_reward"),
            InlineKeyboardButton("📚 Manage Methods", callback_data="admin_methods")
        ],
        [
            InlineKeyboardButton("📣 Broadcast Message", callback_data="admin_broadcast"),
            InlineKeyboardButton("🔙 Back to User Menu", callback_data="user_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_methods_manager_keyboard(methods: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List of methods with Add and Manage options."""
    keyboard = []
    for m in methods:
        title = m.get("title", f"Method #{m['id']}")
        keyboard.append([InlineKeyboardButton(f"⚙️ {title[:25]}", callback_data=f"manage_method_{m['id']}")])
    
    keyboard.append([
        InlineKeyboardButton("➕ Add New Method", callback_data="admin_add_method")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_main")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_single_method_manage_keyboard(method_id: int) -> InlineKeyboardMarkup:
    """Settings menu for a specific method."""
    keyboard = [
        [
            InlineKeyboardButton("📝 Edit Content & Photo", callback_data=f"edit_m_content_{method_id}")
        ],
        [
            InlineKeyboardButton("👥 Set Required Refs", callback_data=f"edit_m_refs_{method_id}"),
            InlineKeyboardButton("💵 Set USDT Price", callback_data=f"edit_m_price_{method_id}")
        ],
        [
            InlineKeyboardButton("❌ Delete This Method", callback_data=f"del_method_{method_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Methods List", callback_data="admin_methods")
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
