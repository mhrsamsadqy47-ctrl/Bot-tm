# main.py
import asyncio
import logging
import os
import random
import time
import json
import shutil  
import zipfile
from datetime import datetime 
from html import escape 

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, ContextTypes,
    PicklePersistence, Defaults, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError, BadRequest

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError,
    PhoneNumberBannedError, PhoneNumberInvalidError, PhoneCodeExpiredError, UserDeactivatedBanError,
    UserAlreadyParticipantError, UserBannedInChannelError, InviteHashExpiredError, InviteHashInvalidError,
    UserNotParticipantError, ChannelsTooMuchError, UserChannelsTooMuchError,
    UserIdInvalidError, PeerIdInvalidError, UserPrivacyRestrictedError, ChatAdminRequiredError,
    FloodWaitError, UserAdminInvalidError, ChatNotModifiedError, ParticipantsTooFewError, BotGroupsBlockedError,
    RightForbiddenError, ChatWriteForbiddenError, UserNotMutualContactError, AuthRestartError, AuthKeyUnregisteredError,
    PhoneNumberUnoccupiedError
)
from telethon.tl import functions, types
from telethon.tl.types import ChatAdminRights, ChannelParticipantsAdmins, ChannelParticipantsRecent, ChannelParticipantsSearch, ChatBannedRights, ChannelParticipantsKicked


import config
from data.database_setup import init_db
from data.database_ops import (
    add_account_to_db, get_all_accounts, get_account_details_by_id, delete_account_from_db,
    get_bot_setting, set_bot_setting,
    get_api_keys, add_api_key, remove_api_key,
    get_db_admins, add_db_admin, remove_db_admin,
    get_spam_keywords, add_spam_keyword, remove_spam_keyword
)

os.makedirs(config.LOGS_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(config.LOGS_DIR, "bot.log")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'), # ذخیره در فایل
        logging.StreamHandler() # نمایش در کنسول
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BACKUP_TEMP_DIR = "bot_backup_temp" # برای فایل‌های موقت پشتیبان‌گیری و بازیابی
# --- مراحل ConversationHandler ها ---
ADD_ACC_ASK_CATEGORY, ADD_ACC_ASK_PHONE, ADD_ACC_ASK_CODE, ADD_ACC_ASK_2FA_PASS = range(4)
TOOL_ASK_ACCOUNT_CATEGORY_FILTER, TOOL_SELECT_ACCOUNT_METHOD, TOOL_ASK_SPECIFIC_COUNT, TOOL_ASK_TARGET_INPUT = range(4, 8)
REPORTER_USER_ASK_REASON, REPORTER_USER_ASK_CUSTOM_REASON = range(8, 10)
REPORTER_CHAT_ASK_REASON, REPORTER_CHAT_ASK_CUSTOM_REASON = range(10, 12)
SPAMMER_ASK_MESSAGE_COUNT, SPAMMER_ASK_MESSAGE_TEXT, SPAMMER_ASK_DELAY = range(12, 15)
ADD_ADMIN_ASK_USERS_TO_PROMOTE = range(15, 16)
BOT_OP_SPAM_GROUP_ASK_TARGET, BOT_OP_SPAM_GROUP_ASK_COUNT, BOT_OP_SPAM_GROUP_ASK_TEXT, BOT_OP_SPAM_GROUP_ASK_DELAY = range(16, 20)
BOT_OP_SPAM_CHANNEL_ASK_TARGET, BOT_OP_SPAM_CHANNEL_ASK_COUNT, BOT_OP_SPAM_CHANNEL_ASK_TEXT, BOT_OP_SPAM_CHANNEL_ASK_DELAY = range(20, 24)
BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_TARGET, BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_HELPER_ACCOUNT, BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_CONFIRM = range(24, 27)
BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_TARGET, BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_HELPER_ACCOUNT, BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_CONFIRM = range(27, 30)
BOT_OP_ADD_ADMIN_CHAT_ASK_TARGET, BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_CATEGORY, \
BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_COUNT_METHOD, \
BOT_OP_ADD_ADMIN_CHAT_ASK_USERS_TO_PROMOTE, BOT_OP_ADD_ADMIN_CHAT_ASK_CONFIRM = range(30, 35)
SETTINGS_MENU, SETTINGS_API_MENU, SETTINGS_ASK_API_ID, SETTINGS_ASK_API_HASH, \
SETTINGS_ADMINS_MENU, SETTINGS_ADMINS_ASK_ADD_ID, SETTINGS_ADMINS_ASK_REMOVE_SELECT, \
SETTINGS_SPAM_MENU, SETTINGS_SPAM_ASK_ADD, SETTINGS_SPAM_ASK_REMOVE_SELECT, \
SETTINGS_DELAY_MENU, SETTINGS_DELAY_ASK_VALUE = range(35, 47)
RESTORE_ASK_FILE, RESTORE_CONFIRM_ACTION = range(47, 49)
LIST_ACC_SELECT_CATEGORY, LIST_ACC_SHOW_PAGE = range(49, 51)


# نام کانورسیشن‌های فعال
ADD_ACCOUNT_CONV = "add_account_conv"
JOINER_TOOL_CONV = "joiner_tool_conv"
LEAVER_TOOL_CONV = "leaver_tool_conv"
BLOCKER_TOOL_CONV = "blocker_tool_conv"
REPORTER_USER_TOOL_CONV = "reporter_user_tool_conv"
REPORTER_CHAT_TOOL_CONV = "reporter_chat_tool_conv"
SPAMMER_TOOL_CONV = "spammer_tool_conv"
REMOVER_TOOL_CONV = "remover_tool_conv"
ADD_ADMIN_TOOL_CONV = "add_admin_tool_conv"
BOT_OP_SPAM_GROUP_CONV = "bot_op_spam_group_conv"
BOT_OP_SPAM_CHANNEL_CONV = "bot_op_spam_channel_conv"
BOT_OP_ADV_REMOVE_GROUP_MEMBERS_CONV = "bot_op_adv_remove_group_members_conv"
BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_CONV = "bot_op_adv_remove_channel_members_conv"
BOT_OP_ADD_ADMIN_GROUP_CONV = "bot_op_add_admin_group_conv"
BOT_OP_ADD_ADMIN_CHANNEL_CONV = "bot_op_add_admin_channel_conv"
SETTINGS_CONV = "settings_conv"
RESTORE_CONV = "restore_conversation" # نام کانورسیشن بازیابی
LIST_ACCOUNTS_CONV = "list_accounts_conversation"

ACCOUNTS_PER_PAGE = 10

CANCEL_CONVERSATION = ConversationHandler.END

# --- دکوراتور ادمین ---
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        admin_list = context.bot_data.get('admin_ids_master_list', config.ADMIN_IDS)
        if user_id not in admin_list:
            message_text = "🚫 شما دسترسی لازم برای استفاده از این دستور/عملیات را ندارید برای تهیه اشتراک به @Ivfio مراجعه کنید."
            if update.message: await update.message.reply_text(message_text)
            elif update.callback_query: await update.callback_query.answer(message_text, show_alert=True)
            logger.warning(f"User {user_id} ({update.effective_user.full_name if update.effective_user else 'Unknown'}) tried an admin command/feature with admin_list: {admin_list}.")
            active_conv_name = context.user_data.get('_active_conversation_name')
            if active_conv_name:
                context.user_data.clear()
                logger.info(f"Cleared user_data for unauthorized user in conversation {active_conv_name}.")
                return ConversationHandler.END
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# --- توابع ساخت منو ---
def build_main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⚙️ مدیریت اکانت‌ها", callback_data="main_menu_accounts")],
        [InlineKeyboardButton("🛠 ابزارها (با اکانت‌ها)", callback_data="main_menu_tools")],
        [InlineKeyboardButton("🤖 عملیات با ربات", callback_data="main_menu_bot_operations")],
        [InlineKeyboardButton("🔧 تنظیمات ربات", callback_data="main_menu_settings")],
        [InlineKeyboardButton("📋 دریافت لاگ‌ها", callback_data="main_menu_logs")], 
        [InlineKeyboardButton("💾 پشتیبان‌گیری و بازیابی", callback_data="main_menu_backup_restore_options")], 
        [InlineKeyboardButton("❔ راهنما", callback_data="main_menu_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_accounts_menu() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("➕ افزودن اکانت جدید", callback_data="accounts_add_start")],[InlineKeyboardButton("➖ حذف اکانت", callback_data="accounts_delete_start")],[InlineKeyboardButton("📊 نمایش لیست اکانت‌ها", callback_data="accounts_list")],[InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]]
    return InlineKeyboardMarkup(keyboard)

def build_tools_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔗 پیوستن به کانال/گروه", callback_data="tools_joiner_entry")],
        [InlineKeyboardButton("🚪 ترک کانال/گروه", callback_data="tools_leaver_entry")],
        [InlineKeyboardButton("🚫 بلاک کردن کاربر", callback_data="tools_blocker_entry")],
        [InlineKeyboardButton("🗣 ریپورت کردن کاربر", callback_data="tools_reporter_user_entry")],
        [InlineKeyboardButton("📢 ریپورت کانال/گروه", callback_data="tools_reporter_chat_entry")],
        [InlineKeyboardButton("💬 ارسال پیام اسپم", callback_data="tools_spammer_entry")],
        [InlineKeyboardButton("🗑 حذف اعضا از گروه (با اکانت‌ها)", callback_data="tools_remover_entry")],
        [InlineKeyboardButton("👑 ارتقا به ادمین در گروه (با اکانت‌ها)", callback_data="tools_add_admin_entry")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_bot_operations_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💬 اسپم به گروه (با ربات)", callback_data="bot_op_spam_group_start")],
        [InlineKeyboardButton("📢 اسپم به کانال (با ربات)", callback_data="bot_op_spam_channel_start")],
        [InlineKeyboardButton("🗑 حذف مشترکین کانال (پیشرفته)", callback_data="bot_op_adv_remove_channel_members_start")],
        [InlineKeyboardButton("🗑 حذف اعضای گروه (پیشرفته)", callback_data="bot_op_adv_remove_group_members_start")],
        [InlineKeyboardButton("👑 افزودن ادمین در کانال (با ربات)", callback_data="bot_op_add_admin_channel_start")],
        [InlineKeyboardButton("👑 افزودن ادمین در گروه (با ربات)", callback_data="bot_op_add_admin_group_start")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_help_options_submenu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⚙️ راهنمای مدیریت اکانت‌ها", callback_data="help_section_accounts")],
        [InlineKeyboardButton("🛠 راهنمای ابزارها (با اکانت‌ها)", callback_data="help_section_tools")],
        [InlineKeyboardButton("🤖 راهنمای عملیات با ربات", callback_data="help_section_bot_ops")],
        [InlineKeyboardButton("🔧 راهنمای تنظیمات ربات", callback_data="help_section_settings")],
        [InlineKeyboardButton("💾 راهنمای پشتیبان‌گیری و بازیابی", callback_data="help_section_backup_restore")],
        [InlineKeyboardButton("📋 راهنمای لاگ‌ها و خطایابی", callback_data="help_section_logs_guide")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_settings_menu_content(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    """محتوا و دکمه‌های منوی اصلی تنظیمات را می‌سازد."""
    text = "⚙️ **بخش تنظیمات ربات**\n\nلطفاً یک گزینه را انتخاب کنید:"
    keyboard = [
        [InlineKeyboardButton("🔑 مدیریت API ID/Hash", callback_data="settings_api_management")],
        [InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="settings_admins_management")],
        [InlineKeyboardButton("📝 مدیریت کلمات اسپم", callback_data="settings_spam_keywords_management")],
        [InlineKeyboardButton("⏱️ مدیریت تأخیر عمومی", callback_data="settings_delay_management")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def build_backup_restore_options_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📥 تهیه فایل پشتیبان", callback_data="backup_create_now")],
        [InlineKeyboardButton("📤 بازیابی از فایل پشتیبان", callback_data="restore_start_process")],
        [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_api_management_menu_content(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    api_keys_list = context.bot_data.get('api_keys_list', [])

    text = "🔑 **مدیریت API ID/Hash تلگرام**\n\n"
    if not api_keys_list:
        text += "هنوز هیچ API ID/Hash ای در دیتابیس ذخیره نشده است.\n"
        text += "ربات از مقادیر پیش‌فرض `config.py` (اگر موجود باشند) یا اولین API ذخیره شده در صورت وجود استفاده خواهد کرد.\n"
    else:
        text += "لیست API های ذخیره شده (ربات به صورت تصادفی از یکی استفاده می‌کند):\n"
        for i, key_pair in enumerate(api_keys_list):
            api_id_display = key_pair.get('api_id', 'N/A')
            api_hash_val = key_pair.get('api_hash', '')
            api_hash_display = api_hash_val[:4] + "****" if len(api_hash_val) > 4 else "****"
            text += f"{i+1}. API ID: `{api_id_display}` - Hash: `{api_hash_display}`\n"

    keyboard = [
        [InlineKeyboardButton("➕ افزودن API ID/Hash جدید", callback_data="settings_api_add_new")],
    ]
    if api_keys_list:
        keyboard.append([InlineKeyboardButton("➖ حذف API ID/Hash", callback_data="settings_api_remove_select")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت به تنظیمات", callback_data="main_menu_settings_from_action")])

    return text, InlineKeyboardMarkup(keyboard)

def build_admins_management_menu_content(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    config_admin_ids = set(config.ADMIN_IDS)
    db_admin_ids = set(context.bot_data.get('db_admin_ids', [])) # ادمین های دیتابیس
    
    text = "👤 **مدیریت ادمین‌های ربات**\n\n"
    text += "ادمین‌های اصلی (از `config.py` - غیرقابل حذف از اینجا):\n"
    if config_admin_ids:
        for admin_id in config_admin_ids:
            text += f"- `{admin_id}`\n"
    else:
        text += "- (هیچ ادمین اصلی در کانفیگ تعریف نشده!)\n"

    db_only_admins = db_admin_ids - config_admin_ids
    if db_only_admins:
        text += "\nادمین‌های اضافه شده از طریق ربات (قابل حذف):\n"
        for admin_id in db_only_admins:
            text += f"- `{admin_id}`\n"
    else:
        text += "\nهنوز ادمینی از طریق ربات (به دیتابیس) اضافه نشده است.\n"
        
    keyboard = [
        [InlineKeyboardButton("➕ افزودن ادمین جدید (به دیتابیس)", callback_data="settings_admins_add_db")],
    ]
    
    if db_only_admins:
         keyboard.append([InlineKeyboardButton("➖ حذف ادمین (از دیتابیس)", callback_data="settings_admins_remove_db_select")])
    
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت به تنظیمات", callback_data="main_menu_settings_from_action")])
    return text, InlineKeyboardMarkup(keyboard)

def build_spam_keywords_menu_content(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    keywords = context.bot_data.get('spam_keywords_list', [])
    text = "📝 <b>مدیریت کلمات اسپم</b>\n\n" 
    if not keywords:
        text += "هنوز هیچ کلمه کلیدی اسپمی در دیتابیس ذخیره نشده است.\n"
    else:
        text += "کلمات کلیدی اسپم فعلی:\n"
        
        keyword_lines = ["- <code>" + escape(keyword) + "</code>" for keyword in keywords]
        text += "\n".join(keyword_lines)
        if len(text) > 3800: 
            text = text[:3800] + "\n... (لیست طولانی‌تر است)"

    keyboard = [
        [InlineKeyboardButton("➕ افزودن کلمه/عبارت جدید", callback_data="settings_spam_add_keyword")],
    ]
    if keywords:
        keyboard.append([InlineKeyboardButton("➖ حذف کلمه/عبارت", callback_data="settings_spam_remove_select_keyword")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت به تنظیمات", callback_data="main_menu_settings_from_action")])
    return text, InlineKeyboardMarkup(keyboard)

def build_delay_management_menu_content(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    current_delay_str = context.bot_data.get('default_operation_delay', "1.5")
    try:
        current_delay = float(current_delay_str)
    except ValueError:
        current_delay = 1.5
        # application.bot_data هم باید آپدیت شود اگر در post_init به درستی مقداردهی نشده
        context.bot_data['default_operation_delay'] = str(current_delay) # ذخیره به عنوان رشته
        set_bot_setting('DEFAULT_OPERATION_DELAY', str(current_delay))

    text = (f"⏱️ <b>مدیریت تأخیر عمومی عملیات</b>\n\n"
            f"تأخیر عمومی فعلی بین برخی عملیات: <code>{current_delay:.1f}</code> ثانیه.\n"
            f"مقدار پیشنهادی بین 0.5 تا 3 ثانیه است.")
    
    keyboard = [
        [InlineKeyboardButton("✏️ تغییر تأخیر عمومی", callback_data="settings_delay_change_value")],
        [InlineKeyboardButton("⬅️ بازگشت به تنظیمات", callback_data="main_menu_settings_from_action")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def build_account_category_selection_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🇮🇷 اکانت ایرانی", callback_data="add_acc_cat_iranian")],
        [InlineKeyboardButton("🌍 اکانت خارجی", callback_data="add_acc_cat_foreign")],
        [InlineKeyboardButton("⬅️ لغو و بازگشت به منوی اکانت‌ها", callback_data="add_account_cancel_to_accounts_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_tool_account_category_filter_menu(tool_prefix: str, cancel_callback: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🇮🇷 فقط اکانت‌های ایرانی", callback_data=f"{tool_prefix}_filter_iranian")],
        [InlineKeyboardButton("🌍 فقط اکانت‌های خارجی", callback_data=f"{tool_prefix}_filter_foreign")],
        [InlineKeyboardButton("💠 همه اکانت‌ها", callback_data=f"{tool_prefix}_filter_all")],
        [InlineKeyboardButton("⬅️ لغو و بازگشت", callback_data=cancel_callback)]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cancel_button(callback_data="general_cancel_to_main_menu") -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("❌ لغو عملیات", callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)

def build_confirm_cancel_buttons(confirm_callback: str, cancel_callback: str, confirm_text="✅ تایید", cancel_text="❌ لغو") -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(confirm_text, callback_data=confirm_callback),
         InlineKeyboardButton(cancel_text, callback_data=cancel_callback)]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_account_count_selection_menu(tool_prefix: str, cancel_callback: str) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("همه اکانت‌های فیلتر شده", callback_data=f"{tool_prefix}_use_all")],[InlineKeyboardButton("تعداد مشخص از اکانت‌های فیلتر شده", callback_data=f"{tool_prefix}_specify_count")],[InlineKeyboardButton("⬅️ لغو و بازگشت", callback_data=cancel_callback)]]
    return InlineKeyboardMarkup(keyboard)

def build_report_reason_menu(reasons_data_map: dict, callback_data_prefix: str, cancel_callback: str) -> InlineKeyboardMarkup:
    keyboard = []
    for reason_key, reason_info in reasons_data_map.items():
        keyboard.append([InlineKeyboardButton(reason_info["display"], callback_data=f"{callback_data_prefix}{reason_key}")])
    keyboard.append([InlineKeyboardButton("⬅️ لغو و بازگشت", callback_data=cancel_callback)])
    return InlineKeyboardMarkup(keyboard)

def build_select_helper_account_menu(accounts: list[dict], callback_prefix: str, cancel_callback: str) -> InlineKeyboardMarkup:
    keyboard = []
    if not accounts:
        keyboard.append([InlineKeyboardButton("هیچ اکانت فعالی برای کمک یافت نشد!", callback_data=f"{callback_prefix}_no_helpers")])
    else:
        for acc in accounts:
            category_emoji = "🇮🇷" if acc.get('account_category') == 'iranian' else "🌍"
            button_text = f"{category_emoji} {acc.get('phone_number')}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"{callback_prefix}_{acc.get('id')}")])
    keyboard.append([InlineKeyboardButton("⬅️ لغو و بازگشت", callback_data=cancel_callback)])
    return InlineKeyboardMarkup(keyboard)

# --- توابع مربوط به افزودن اکانت ---
@admin_only
async def accounts_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        logger.warning("accounts_add_start called without a callback_query.")
        return ConversationHandler.END

    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None
    current_api_id = None
    current_api_hash = None

    if api_keys_list:
        selected_api_pair = random.choice(api_keys_list)
        current_api_id = selected_api_pair.get('api_id')
        current_api_hash = selected_api_pair.get('api_hash')
        logger.info(f"Using random API ID: {current_api_id} for new account addition.")
    elif config.API_ID and config.API_HASH:
        current_api_id = str(config.API_ID)
        current_api_hash = config.API_HASH
        logger.info(f"Using API ID from config.py for new account addition.")
    
    if not current_api_id or not current_api_hash:
        text_to_send = ("⚠️ خطا: هیچ `API_ID` یا `API_HASH` ای در تنظیمات ربات یا فایل `config.py` یافت نشد.\n"
                        "لطفاً ابتدا از بخش 'تنظیمات ربات > مدیریت API' این مقادیر را تنظیم کنید.")
        await query.answer("خطا در تنظیمات API!", show_alert=True)
        try: 
            await query.edit_message_text(text=text_to_send, reply_markup=build_accounts_menu(), parse_mode=ParseMode.HTML)
        except BadRequest as e:
            if "Message is not modified" in str(e): 
                logger.info("Message not modified on API error (add account).")
            else: 
                raise e
        return ConversationHandler.END
    
    await query.answer()
    try:
        await query.edit_message_text(
            "لطفاً نوع اکانتی که می‌خواهید اضافه کنید را انتخاب نمایید:",
            reply_markup=build_account_category_selection_menu()
        )
    except BadRequest as e:
        if "Message is not modified" in str(e): logger.info("Message not modified on add_accounts_start.")
        else: raise e
            
    # context.user_data.clear() # پاک کردن دیتا در شروع مکالمه جدید
    context.user_data['_active_conversation_name'] = ADD_ACCOUNT_CONV
    context.user_data['new_account'] = {} # اطمینان از ایجاد دیکشنری
    context.user_data['new_account']['api_id'] = current_api_id
    context.user_data['new_account']['api_hash'] = current_api_hash

    return ADD_ACC_ASK_CATEGORY

async def ask_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category_type = query.data.replace("add_acc_cat_", "")
    if 'new_account' not in context.user_data: context.user_data['new_account'] = {} # اطمینان
    context.user_data['new_account']['category_type'] = category_type
    prompt_message = ""
    if category_type == 'iranian': prompt_message = "🇮🇷 لطفاً شماره تلفن اکانت ایرانی را با پیش‌شماره کشور +98 ارسال کنید (مثلاً +989123456789):"
    elif category_type == 'foreign': prompt_message = "🌍 لطفاً شماره تلفن اکانت خارجی را با پیش‌شماره کشور ارسال کنید (مثلاً +1XXXXXXXXXX):"
    await query.edit_message_text(prompt_message, reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu"))
    return ADD_ACC_ASK_PHONE

async def ask_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text.strip()
    if 'new_account' not in context.user_data or \
       'api_id' not in context.user_data['new_account'] or \
       'api_hash' not in context.user_data['new_account']:
        logger.error("ask_phone_received: 'new_account' or API details not in user_data. Cancelling.")
        await update.message.reply_text("خطای داخلی (اطلاعات API یافت نشد). لطفاً عملیات را از ابتدا شروع کنید.", reply_markup=build_accounts_menu())
        context.user_data.clear(); return ConversationHandler.END
        
    category_type = context.user_data['new_account'].get('category_type')

    if not phone_number.startswith("+") or not phone_number[1:].isdigit() or len(phone_number) < 10:
        await update.message.reply_text("فرمت شماره تلفن نامعتبر است...", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu")); return ADD_ACC_ASK_PHONE
    if category_type == 'iranian' and not phone_number.startswith("+98"):
        await update.message.reply_text("❌ شماره تلفن برای اکانت ایرانی باید با +98 شروع شود...", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu")); return ADD_ACC_ASK_PHONE
    elif category_type == 'foreign' and phone_number.startswith("+98"):
        await update.message.reply_text("❌ شماره تلفن برای اکانت خارجی نباید با +98 شروع شود...", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu")); return ADD_ACC_ASK_PHONE
    
    context.user_data['new_account']['phone'] = phone_number
    context.user_data['new_account']['account_category_for_db'] = category_type
    session_filename = os.path.join(config.SESSIONS_DIR, f"{phone_number.replace('+', '')}.session")
    context.user_data['new_account']['session_file'] = session_filename
    
    api_id_to_use = context.user_data['new_account']['api_id']
    api_hash_to_use = context.user_data['new_account']['api_hash']

    try: api_id_int = int(api_id_to_use)
    except (ValueError, TypeError): 
        logger.critical(f"CRITICAL: API_ID '{api_id_to_use}' for account add is invalid."); 
        await update.message.reply_text("خطای سیستمی: API_ID انتخاب شده نادرست است.", reply_markup=build_accounts_menu()); 
        context.user_data.clear(); return ConversationHandler.END
    
    client = TelegramClient(session_filename, api_id_int, api_hash_to_use)
    context.user_data['telethon_client'] = client
    
    try:
        await update.message.reply_text("⏳ در حال اتصال و ارسال کد تأیید...")
        logger.info(f"Connecting Telethon for {phone_number} (Cat: {category_type}) using API ID: {api_id_int}...")
        if client.is_connected(): await client.disconnect() 
        await client.connect()
        if not client.is_connected(): raise ConnectionError("Failed to connect to Telegram.")
        
        logger.info(f"Connected. Sending code to {phone_number}.")
        sent_code_info = await client.send_code_request(phone_number, force_sms=False)
        context.user_data['new_account']['phone_code_hash'] = sent_code_info.phone_code_hash
        await update.message.reply_text("🔢 کد تاییدی که به تلگرام شما ارسال شده را وارد کنید:", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu"))
        return ADD_ACC_ASK_CODE
        
    except (PhoneNumberBannedError, PhoneNumberInvalidError, UserDeactivatedBanError, PhoneNumberUnoccupiedError) as e:
        logger.error(f"Telethon phone error for {phone_number}: {type(e).__name__} - {e}")
        await update.message.reply_text(f"⚠️ خطا در شماره {phone_number}: مسدود/نامعتبر/غیرفعال/ثبت نشده.\n({type(e).__name__})", reply_markup=build_accounts_menu())
    except AuthRestartError:
        logger.warning(f"Telethon AuthRestartError for {phone_number}. Asking to retry.")
        await update.message.reply_text("⚠️ تلگرام درخواست شروع مجدد فرآیند احراز هویت را دارد. لطفاً عملیات افزودن اکانت را از ابتدا شروع کنید.", reply_markup=build_accounts_menu())
        if client and client.is_connected(): await client.disconnect()
        context.user_data.clear(); return ConversationHandler.END
    except ConnectionError as e:
        logger.error(f"Telethon ConnectionError during send_code for {phone_number}: {e}")
        await update.message.reply_text(f"خطا در اتصال برای ارسال کد به {phone_number}. لطفاً از پایداری اینترنت خود مطمئن شده و مجدداً تلاش کنید.", reply_markup=build_accounts_menu())
    except FloodWaitError as e:
        logger.error(f"Telethon FloodWaitError for {phone_number}: {e}")
        await update.message.reply_text(f"⚠️ محدودیت ارسال درخواست (Flood). لطفاً پس از {e.seconds} ثانیه دوباره تلاش کنید.", reply_markup=build_accounts_menu())
    except Exception as e:
        logger.error(f"Telethon send_code error for {phone_number}: {type(e).__name__} - {e}")
        await update.message.reply_text(f"خطا در ارسال کد به {phone_number}: {str(e)[:200]}", reply_markup=build_accounts_menu())
    
    if client and client.is_connected(): await client.disconnect()
    context.user_data.clear(); return ConversationHandler.END

async def ask_code_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code_from_user = update.message.text.strip()
    if not code_from_user.isdigit():
        await update.message.reply_text("کد وارد شده نامعتبر است. فقط عدد وارد کنید.\nدوباره تلاش کنید:", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu"))
        return ADD_ACC_ASK_CODE
        
    new_account_data = context.user_data.get('new_account', {})
    phone_number = new_account_data.get('phone')
    phone_code_hash = new_account_data.get('phone_code_hash')
    account_category_for_db = new_account_data.get('account_category_for_db')
    client = context.user_data.get('telethon_client')

    if not all([phone_number, phone_code_hash, account_category_for_db, client]):
        logger.error(f"Missing data in ask_code_received. Data: {new_account_data}, Client: {client is not None}")
        await update.message.reply_text("خطای داخلی (اطلاعات ناقص). لطفاً از ابتدا شروع کنید.", reply_markup=build_accounts_menu())
        if client and client.is_connected(): await client.disconnect()
        context.user_data.clear(); return ConversationHandler.END
    
    next_state = ConversationHandler.END 
    try:
        await update.message.reply_text(f"⏳ در حال بررسی کد {code_from_user}...")
        logger.info(f"Checking code {code_from_user} for {phone_number}.")
        if not client.is_connected():
            logger.info("Reconnecting client before sign_in...")
            await client.connect()
            if not client.is_connected(): raise ConnectionError("Failed to reconnect for sign_in.")
            
        await client.sign_in(phone=phone_number, code=code_from_user, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        logger.info(f"Sign_in successful (no 2FA) for {phone_number}, User ID: {me.id}, Username: {me.username}")
        
        session_file = new_account_data['session_file']
        add_account_to_db(
            phone_number=phone_number, user_id=me.id, username=me.username,
            session_file=session_file, account_category=account_category_for_db
        )
        await update.message.reply_text(
            f"✅ اکانت {me.first_name or ''} (@{me.username or 'بدون یوزرنیم'}) با موفقیت به عنوان اکانت {account_category_for_db} اضافه شد!",
            reply_markup=build_accounts_menu()
        )
    except SessionPasswordNeededError:
        logger.info(f"2FA password needed for {phone_number}.")
        await update.message.reply_text(
            "🔒 این اکانت دارای تایید دو مرحله‌ای (رمز عبور) است. لطفاً رمز عبور را وارد کنید:",
            reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu")
        )
        next_state = ADD_ACC_ASK_2FA_PASS
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        logger.warning(f"Invalid or expired code entered for {phone_number}.")
        await update.message.reply_text(
            "❌ کد وارد شده غلط یا منقضی شده است. لطفاً کد جدید را وارد کنید:",
            reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu")
        )
        next_state = ADD_ACC_ASK_CODE
    except ConnectionError as e:
        logger.error(f"Telethon ConnectionError during sign_in for {phone_number}: {e}")
        await update.message.reply_text(f"خطا در اتصال برای ورود با کد. لطفاً مجدداً تلاش کنید.", reply_markup=build_accounts_menu())
    except Exception as e:
        logger.error(f"Sign_in error for {phone_number} after code: {type(e).__name__} - {e}")
        await update.message.reply_text(f"خطا در ورود با کد: {str(e)[:200]}", reply_markup=build_accounts_menu())
    finally:
        if next_state == ConversationHandler.END: 
            if client and client.is_connected(): await client.disconnect()
            context.user_data.clear()
            
    return next_state

async def ask_2fa_pass_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text.strip()
    new_account_data = context.user_data.get('new_account', {})
    phone_number = new_account_data.get('phone')
    account_category_for_db = new_account_data.get('account_category_for_db')
    client = context.user_data.get('telethon_client')
    next_state = ConversationHandler.END

    if not all([phone_number, account_category_for_db, client]):
        logger.error(f"Missing data in 2FA. Data: {new_account_data}, Client: {client is not None}")
        await update.message.reply_text("خطای داخلی. از ابتدا شروع کنید.", reply_markup=build_accounts_menu())
        if client and client.is_connected(): await client.disconnect()
        context.user_data.clear(); return ConversationHandler.END
    try:
        await update.message.reply_text(f"⏳ در حال بررسی رمز 2FA برای {phone_number}..."); logger.info(f"Checking 2FA for {phone_number}.")
        if not client.is_connected(): logger.info("Reconnecting client for 2FA..."); await client.connect();
        if not client.is_connected(): raise ConnectionError("Failed to reconnect for 2FA sign_in.")
        
        await client.sign_in(password=password)
        me = await client.get_me()
        logger.info(f"2FA Sign_in OK for {phone_number}, ID: {me.id}, Username: {me.username}")
        session_file = new_account_data['session_file']
        add_account_to_db(phone_number, me.id, me.username, session_file, account_category_for_db)
        await update.message.reply_text(f"✅ اکانت {me.first_name or ''} (@{me.username or 'NoUser'}) ({account_category_for_db}) با 2FA اضافه شد!", reply_markup=build_accounts_menu())
    except PasswordHashInvalidError: 
        logger.warning(f"Invalid 2FA pass for {phone_number}."); 
        await update.message.reply_text("❌ رمز 2FA غلط. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data="add_account_cancel_to_accounts_menu"))
        next_state = ADD_ACC_ASK_2FA_PASS
    except ConnectionError as e: 
        logger.error(f"Telethon ConnectionError during 2FA for {phone_number}: {e}")
        await update.message.reply_text(f"خطا در اتصال برای ورود با 2FA. مجدداً تلاش کنید.", reply_markup=build_accounts_menu())
    except Exception as e: 
        logger.error(f"2FA sign_in error for {phone_number}: {type(e).__name__} - {e}")
        await update.message.reply_text(f"خطا در ورود با 2FA: {str(e)[:200]}", reply_markup=build_accounts_menu())
    finally:
        if next_state == ConversationHandler.END: 
            if client and client.is_connected(): logger.info(f"Ending 2FA conv for {phone_number}. Disconnecting."); await client.disconnect()
            context.user_data.clear(); logger.info(f"Cleaned user_data for {phone_number} after 2FA attempt.")
            
    return next_state
# --- دستور /start ---
@admin_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    user = update.effective_user; logger.info(f"Admin {user.full_name} (ID: {user.id}) started the bot.")
    welcome_text = (rf"سلام ادمین گرامی <b>{user.full_name}</b>! 👋\nبه ربات مدیریت اکانت‌های تلگرام خوش آمدید.\nلطفا یک گزینه را از منوی زیر انتخاب کنید:")
    if update.message: await update.message.reply_html(welcome_text, reply_markup=build_main_menu())
    elif update.callback_query:
        try: await update.callback_query.edit_message_text(welcome_text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
        except BadRequest as e:
            if "Message is not modified" in str(e): logger.info("Start message not modified.")
            else: raise e
    return CANCEL_CONVERSATION

# --- توابع مدیریت اکانت ---
@admin_only
async def list_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    accounts = get_all_accounts()
    if not accounts: message_text = "هنوز هیچ اکانتی اضافه نشده است."
    else:
        message_text = "📄 **لیست اکانت‌های ذخیره شده:**\n------------------------------------\n"
        for acc_dict in accounts:
            status_emoji = "✅" if acc_dict.get('is_active', 1) else "❌"
            category_display = acc_dict.get('account_category', 'نامشخص')
            category_emoji = "🇮🇷" if category_display == 'iranian' else "🌍" if category_display == 'foreign' else "❔"
            username_display = f"@{acc_dict.get('username')}" if acc_dict.get('username') else "<i>(بدون یوزرنیم)</i>"
            added_time_full = acc_dict.get('added_at', 'N/A'); added_time_short = added_time_full.split('.')[0] if '.' in added_time_full else added_time_full
            message_text += (f"{status_emoji} {category_emoji} 📞 **شماره:** `{acc_dict.get('phone_number')}` ({category_display})\n"
                             f"   👤 **یوزرنیم:** {username_display}\n"
                             f"   🆔 **آیدی تلگرام:** `{acc_dict.get('user_id')}`\n"
                             f"   🗓 **تاریخ افزودن:** {added_time_short}\n------------------------------------\n")
        if len(message_text) > 4000: message_text = message_text[:3900] + "\n\n... (لیست کامل طولانی‌تر است)"

    try:
        if query:
            await query.edit_message_text(text=message_text, reply_markup=build_accounts_menu(), parse_mode=ParseMode.HTML)
            await query.answer()
        elif update.message:
            await update.message.reply_html(text=message_text, reply_markup=build_accounts_menu())
    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.info("Message not modified, skipping edit for accounts_list.")
            if query: await query.answer(text="لیست اکانت‌ها به‌روز است.", show_alert=False)
        else:
            logger.error(f"BadRequest in list_accounts_command: {e}")
            if query: await query.answer(text="خطا در به‌روزرسانی لیست.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in list_accounts_command: {e}")
        if query: await query.answer(text="خطای ناشناخته در نمایش لیست.", show_alert=True)

@admin_only
async def accounts_delete_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); accounts = get_all_accounts()
    if not accounts: await query.edit_message_text("هیچ اکانتی برای حذف وجود ندارد.", reply_markup=build_accounts_menu()); return
    keyboard_buttons = []
    for acc in accounts:
        category_display = acc.get('account_category', 'نامشخص')
        category_emoji = "🇮🇷" if category_display == 'iranian' else "🌍" if category_display == 'foreign' else "❔"
        button_text = f"🗑 {category_emoji} {acc.get('phone_number')}"
        keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"delete_select_{acc.get('id')}")])
    keyboard_buttons.append([InlineKeyboardButton("⬅️ بازگشت به منوی اکانت‌ها", callback_data="main_menu_accounts_from_action")])
    await query.edit_message_text("لطفاً اکانتی که می‌خواهید حذف کنید را از لیست زیر انتخاب نمایید:", reply_markup=InlineKeyboardMarkup(keyboard_buttons))

@admin_only
async def delete_account_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); account_db_id = int(query.data.split("_")[-1]); account_details = get_account_details_by_id(account_db_id)
    if not account_details: await query.edit_message_text("خطا: اکانت مورد نظر یافت نشد.", reply_markup=build_accounts_menu()); return
    phone_number = account_details.get('phone_number')
    category = account_details.get('account_category', 'نامشخص')
    category_display_text = "ایرانی 🇮🇷" if category == 'iranian' else "خارجی 🌍" if category == 'foreign' else "نامشخص ❔"
    confirmation_text = (f"⚠️ **تأیید حذف اکانت** ⚠️\n\n"
                         f"آیا از حذف اکانت با شماره `{phone_number}` (نوع: {category_display_text}) مطمئن هستید؟\n"
                         f"این عملیات غیرقابل بازگشت است و فایل نشست نیز حذف خواهد شد.")
    keyboard = [[InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"delete_confirm_{account_db_id}"), InlineKeyboardButton("❌ خیر، لغو", callback_data="accounts_delete_start")],[InlineKeyboardButton("⬅️ بازگشت به منوی اکانت‌ها", callback_data="main_menu_accounts_from_action")]]
    await query.edit_message_text(text=confirmation_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

@admin_only
async def delete_account_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); account_db_id = int(query.data.split("_")[-1]); account_details = get_account_details_by_id(account_db_id)
    if not account_details: await query.edit_message_text("خطا: اکانت مورد نظر برای حذف یافت نشد.", reply_markup=build_accounts_menu()); return
    session_file_path = account_details.get('session_file'); phone_number_deleted = account_details.get('phone_number'); file_deleted_successfully = False
    if session_file_path and os.path.exists(session_file_path):
        try: os.remove(session_file_path); logger.info(f"Session file {session_file_path} deleted."); file_deleted_successfully = True
        except OSError as e: logger.error(f"Error deleting session file {session_file_path}: {e}"); await query.edit_message_text(f"خطا در حذف فایل سشن برای اکانت {phone_number_deleted}.", reply_markup=build_accounts_menu()); return
    elif session_file_path: logger.warning(f"Session file {session_file_path} not found for {phone_number_deleted}. Marked as successful for DB deletion."); file_deleted_successfully = True
    else: logger.warning(f"No session file path for {phone_number_deleted}. Marked as successful for DB deletion."); file_deleted_successfully = True
    db_deleted_successfully = False
    if file_deleted_successfully:
        if delete_account_from_db(account_db_id): db_deleted_successfully = True
    message = f"✅ اکانت `{phone_number_deleted}` با موفقیت حذف شد." if db_deleted_successfully else f"⚠️ اکانت `{phone_number_deleted}` از دیتابیس حذف نشد (با اینکه فایل سشن بررسی شد)."
    if session_file_path and not file_deleted_successfully :
        message += "\nفایل سشن نیز حذف نشد."
    await query.edit_message_text(message, reply_markup=build_accounts_menu(), parse_mode=ParseMode.HTML)

# --- تابع عمومی لغو کانورسیشن ---
@admin_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; from_user_id = update.effective_user.id if update.effective_user else "Unknown"; active_conv_name = context.user_data.get('_active_conversation_name', "Unknown Conv"); tool_prefix = context.user_data.get('tool_prefix', "N/A"); bot_op_conv_prefix = context.user_data.get('bot_op_conv_prefix', "N/A"); logger.info(f"User {from_user_id} cancelled conv: {active_conv_name} (ToolPrefix: {tool_prefix}, BotOpPrefix: {bot_op_conv_prefix}).")
    client = context.user_data.get('telethon_client')
    if active_conv_name == ADD_ACCOUNT_CONV and client and client.is_connected(): logger.info(f"Disconnecting Telethon client on '{ADD_ACCOUNT_CONV}' cancel."); await client.disconnect()
    context.user_data.clear(); logger.info(f"Cleared user_data for conv '{active_conv_name}'.")
    text_to_send = "عملیات لغو شد."; reply_markup_to_send = build_main_menu()
    if query:
        await query.answer()
        callback_data = query.data
        if callback_data.startswith("add_account_cancel_to_accounts_menu") or callback_data == "cancel_to_accounts_menu_generic": text_to_send = "عملیات لغو شد. بازگشت به منوی اکانت‌ها."; reply_markup_to_send = build_accounts_menu()
        elif "_cancel_to_tools_menu" in callback_data: text_to_send = "عملیات لغو شد. بازگشت به منوی ابزارها."; reply_markup_to_send = build_tools_menu()
        elif "_cancel_to_bot_operations_menu" in callback_data: text_to_send = "عملیات لغو شد. بازگشت به منوی عملیات با ربات."; reply_markup_to_send = build_bot_operations_menu()
        try: await query.edit_message_text(text=text_to_send, reply_markup=reply_markup_to_send)
        except BadRequest as e:
            if "Message is not modified" in str(e): logger.info("Msg not modified on cancel.")
            else: logger.warning(f"Could not edit msg on cancel: {e}. Sending new."); await context.bot.send_message(chat_id=update.effective_chat.id, text=text_to_send, reply_markup=reply_markup_to_send)
        except Exception as e: logger.warning(f"Unexpected error editing msg on cancel: {e}. Sending new."); await context.bot.send_message(chat_id=update.effective_chat.id, text=text_to_send, reply_markup=reply_markup_to_send)
    elif update.message: await update.message.reply_text(text=text_to_send, reply_markup=reply_markup_to_send)
    return ConversationHandler.END
#----------پشتيبان گيري
@admin_only
async def backup_restore_options_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "لطفاً عملیات مورد نظر خود را برای پشتیبان‌گیری یا بازیابی انتخاب کنید:"
    await query.edit_message_text(text=text, reply_markup=build_backup_restore_options_menu())
#---------------backup
@admin_only
async def create_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("⏳ در حال تهیه فایل پشتیبان... لطفاً صبور باشید.")
    logger.info(f"Backup creation requested by admin {update.effective_user.id}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename_zip = f"bot_backup_{timestamp}.zip"
    
    db_path = config.DATABASE_NAME
    sessions_dir = config.SESSIONS_DIR

    # ایجاد پوشه موقت
    if os.path.exists(BACKUP_TEMP_DIR):
        try:
            shutil.rmtree(BACKUP_TEMP_DIR)
        except Exception as e_rm:
            logger.error(f"Could not remove old temp backup dir: {e_rm}")
    os.makedirs(BACKUP_TEMP_DIR, exist_ok=True)
    
    # مسیر فایل زیپ در پوشه موقت
    zip_file_path = os.path.join(BACKUP_TEMP_DIR, backup_filename_zip)

    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. افزودن فایل دیتابیس
            if os.path.exists(db_path):
                zf.write(db_path, arcname=os.path.basename(db_path))
                logger.info(f"Database file '{db_path}' added to backup.")
            else:
                logger.warning(f"Database file '{db_path}' not found for backup.")

            # 2. افزودن فایل های نشست
            if os.path.exists(sessions_dir) and os.path.isdir(sessions_dir):
                copied_sessions_count = 0
                for item in os.listdir(sessions_dir):
                    s_path = os.path.join(sessions_dir, item)
                    if os.path.isfile(s_path) and item.endswith(".session"):
                        zf.write(s_path, arcname=os.path.join("sessions", item)) # ذخیره در پوشه sessions داخل zip
                        copied_sessions_count += 1
                if copied_sessions_count > 0:
                    logger.info(f"{copied_sessions_count} session files added to backup.")
                else:
                    logger.info("No session files found to add to backup.")
            else:
                logger.info(f"Sessions directory '{sessions_dir}' not found for backup.")
        
        logger.info(f"Backup ZIP file created: {zip_file_path}")

        # ارسال فایل ZIP
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        with open(zip_file_path, 'rb') as backup_file_obj:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=backup_file_obj,
                filename=backup_filename_zip,
                caption=(f"✅ فایل پشتیبان با موفقیت ایجاد شد.\nتاریخ: {timestamp}\n\n"
                         f"شامل فایل دیتابیس و فایل‌های نشست.\n"
                         f"لطفاً این فایل را در جای امنی نگهداری کنید.")
            )
        # بازگرداندن کاربر به منوی گزینه‌های پشتیبان/بازیابی
        await query.edit_message_text("عملیات تهیه پشتیبان انجام شد. فایل برای شما ارسال گردید.",
                                      reply_markup=build_backup_restore_options_menu())

    except Exception as e:
        logger.error(f"Failed during backup process: {e}")
        try:
            await query.edit_message_text(f"⚠️ خطایی در ایجاد یا ارسال فایل پشتیبان رخ داد: {e}",
                                          reply_markup=build_backup_restore_options_menu())
        except Exception as e_edit: # اگر edit_message_text هم خطا داد
             await context.bot.send_message(chat_id=update.effective_chat.id, 
                                            text=f"⚠️ خطایی جدی در ایجاد یا ارسال فایل پشتیبان رخ داد: {e}",
                                            reply_markup=build_backup_restore_options_menu())
    finally:
        if os.path.exists(BACKUP_TEMP_DIR):
            try:
                shutil.rmtree(BACKUP_TEMP_DIR)
                logger.info(f"Temporary backup directory {BACKUP_TEMP_DIR} deleted.")
            except Exception as e_clean:
                logger.error(f"Error deleting temp backup directory {BACKUP_TEMP_DIR}: {e_clean}")
#----------------restore backup
@admin_only
async def restore_receive_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if not message.document or not message.document.file_name.endswith(".zip"):
        await message.reply_text("فایل نامعتبر است. لطفاً یک فایل پشتیبان با فرمت `.zip` ارسال کنید.",
                                 reply_markup=build_cancel_button(callback_data="restore_cancel_to_backup_options"))
        return RESTORE_ASK_FILE

    file_id = message.document.file_id
    file_name = message.document.file_name
    
    temp_zip_path = os.path.join(BACKUP_TEMP_DIR, file_name) 
    
    try:
        bot_file = await context.bot.get_file(file_id)
        await bot_file.download_to_drive(custom_path=temp_zip_path)
        logger.info(f"Restore file '{file_name}' received and saved to '{temp_zip_path}' by admin {update.effective_user.id}")
        context.user_data['restore_zip_path'] = temp_zip_path
    except Exception as e:
        logger.error(f"Failed to download restore file: {e}")
        await message.reply_text(f"خطا در دانلود فایل پشتیبان: {e}",
                                 reply_markup=build_cancel_button(callback_data="restore_cancel_to_backup_options"))
        return RESTORE_ASK_FILE

    # ---------- شروع بخش اصلاح شده برای ارسال پیام تأییدیه ----------
    confirm_text = (f"فایل پشتیبان <code>{escape(file_name)}</code> دریافت شد.\n\n" 
                    f"⚠️ <b>آیا از بازنویسی تمام اطلاعات فعلی ربات (دیتابیس و فایل‌های نشست) با محتویات این فایل پشتیبان مطمئن هستید؟</b>\n"
                    f"این عمل غیرقابل بازگشت است! پس از تأیید، لطفاً ربات را برای اعمال تغییرات به صورت دستی ری‌استارت کنید.")
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، بازیابی و بازنویسی کن", callback_data="restore_confirm_execute")],
        [InlineKeyboardButton("❌ خیر، لغو کن", callback_data="restore_cancel_to_backup_options")]
    ])
    
    
    await message.reply_text(confirm_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    # ---------- پایان بخش اصلاح شده ----------
    return RESTORE_CONFIRM_ACTION

async def restore_execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("⏳ در حال اجرای عملیات بازیابی...")
    
    zip_file_path = context.user_data.get('restore_zip_path')
    if not zip_file_path or not os.path.exists(zip_file_path):
        await query.edit_message_text("خطا: فایل پشتیبان برای بازیابی یافت نشد. لطفاً دوباره تلاش کنید.",
                                      reply_markup=build_backup_restore_options_menu())
        context.user_data.clear(); return ConversationHandler.END

    extract_path = os.path.join(BACKUP_TEMP_DIR, "extracted_backup")
    if os.path.exists(extract_path):
        shutil.rmtree(extract_path)
    os.makedirs(extract_path, exist_ok=True)

    restored_db = False
    restored_sessions_count = 0

    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zf:
            zf.extractall(path=extract_path)
            logger.info(f"Extracted backup content to {extract_path}")

        # بازیابی دیتابیس
        extracted_db_name = os.path.basename(config.DATABASE_NAME) # e.g., database.db
        source_db_path = os.path.join(extract_path, extracted_db_name)
        target_db_path = config.DATABASE_NAME
        
        if os.path.exists(source_db_path):
            # برای جلوگیری از خرابی، ابتدا دیتابیس فعلی را به یک نام دیگر تغییر می‌دهیم.
            current_db_backup_name = target_db_path + ".before_restore_" + datetime.now().strftime("%Y%m%d%H%M%S")
            if os.path.exists(target_db_path):
                os.rename(target_db_path, current_db_backup_name)
                logger.info(f"Current database backed up to {current_db_backup_name}")
            
            shutil.move(source_db_path, target_db_path) # انتقال فایل جدید دیتابیس
            restored_db = True
            logger.info(f"Database restored from {source_db_path} to {target_db_path}")
        else:
            logger.warning(f"Database file not found in backup: {source_db_path}")

        # بازیابی فایل‌های نشست
        extracted_sessions_path = os.path.join(extract_path, "sessions") # اگر در فایل زیپ در پوشه sessions باشند
        target_sessions_dir = config.SESSIONS_DIR
        
        if os.path.exists(extracted_sessions_path) and os.path.isdir(extracted_sessions_path):
            if not os.path.exists(target_sessions_dir):
                os.makedirs(target_sessions_dir, exist_ok=True)
            
            for item in os.listdir(extracted_sessions_path):
                if item.endswith(".session"):
                    source_session_file = os.path.join(extracted_sessions_path, item)
                    target_session_file = os.path.join(target_sessions_dir, item)
                    shutil.move(source_session_file, target_session_file) # جایگزینی فایل‌های نشست
                    restored_sessions_count += 1
            logger.info(f"{restored_sessions_count} session files restored to {target_sessions_dir}")
        else:
            logger.warning(f"Sessions folder not found in backup at {extracted_sessions_path}")

        result_message = "✅ عملیات بازیابی با موفقیت انجام شد.\n"
        if restored_db: result_message += "- دیتابیس بازیابی شد.\n"
        if restored_sessions_count > 0: result_message += f"- تعداد {restored_sessions_count} فایل نشست بازیابی شد.\n"
        if not restored_db and restored_sessions_count == 0: result_message = "⚠️ هیچ فایلی (دیتابیس یا نشست) در پشتیبان برای بازیابی یافت نشد."
        
        result_message += "\n\n**‼️ لطفاً برای اعمال کامل تغییرات، ربات را به صورت دستی راه‌اندازی مجدد (Restart) کنید.**"
        await query.edit_message_text(result_message, reply_markup=build_backup_restore_options_menu())

    except Exception as e:
        logger.error(f"Error during restore execution: {e}")
        await query.edit_message_text(f"⚠️ خطایی در حین عملیات بازیابی رخ داد: {e}\n"
                                      "ممکن است اطلاعات به طور ناقص بازیابی شده باشند. لطفاً وضعیت را بررسی کنید.",
                                      reply_markup=build_backup_restore_options_menu())
    finally:
        if os.path.exists(BACKUP_TEMP_DIR):
            shutil.rmtree(BACKUP_TEMP_DIR)
            logger.info(f"Temporary restore directory {BACKUP_TEMP_DIR} deleted.")
        context.user_data.clear()
        
    return ConversationHandler.END

async def restore_cancel_to_backup_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    # بازگشت به منوی گزینه‌های پشتیبان/بازیابی
    await query.edit_message_text("عملیات بازیابی لغو شد.", reply_markup=build_backup_restore_options_menu())
    return ConversationHandler.END
#----------------jadid
@admin_only
async def restore_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data.clear() # پاک کردن user_data برای این مکالمه
    context.user_data['_active_conversation_name'] = RESTORE_CONV # نام کانورسیشن در user_data

    # ایجاد پوشه موقت برای آپلودها اگر وجود ندارد
    if os.path.exists(BACKUP_TEMP_DIR): 
        try: shutil.rmtree(BACKUP_TEMP_DIR)
        except Exception as e: logger.warning(f"Could not clear temp dir before restore: {e}")
    os.makedirs(BACKUP_TEMP_DIR, exist_ok=True)

    text = ("📤 **بازیابی از فایل پشتیبان** 📤\n\n"
            "لطفاً فایل پشتیبان `.zip` که قبلاً از ربات دریافت کرده‌اید را ارسال کنید.\n\n"
            "⚠️ **هشدار بسیار مهم:**\n"
            "- بازیابی اطلاعات، تمام داده‌های فعلی ربات (اکانت‌ها، تنظیمات، فایل‌های نشست) را با اطلاعات داخل فایل پشتیبان **جایگزین و بازنویسی** خواهد کرد.\n"
            "- این عملیات **غیرقابل بازگشت** است.\n"
            "- مطمئن شوید که فایل پشتیبان معتبر و مربوط به همین ربات است.\n"
            "- پس از بازیابی موفق، **راه‌اندازی مجدد ربات توسط شما** برای اعمال کامل تغییرات (به خصوص فایل‌های نشست و تنظیمات در حافظه) ضروری است.\n\n"
            "برای لغو، از دکمه زیر استفاده کنید یا دستور /cancel را بفرستید.")

    # دکمه لغو باید به منوی گزینه‌های پشتیبان/بازیابی بازگردد
    await query.edit_message_text(text, 
                                  reply_markup=build_cancel_button(callback_data="restore_cancel_to_backup_options"),
                                  parse_mode=ParseMode.HTML)
    return RESTORE_ASK_FILE
# ConversationHandler برای بازیابی
restore_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(restore_start_command, pattern=r"^restore_start_process$")],
    states={
        RESTORE_ASK_FILE: [MessageHandler(filters.Document.ZIP, restore_receive_file_command)],
        RESTORE_CONFIRM_ACTION: [CallbackQueryHandler(restore_execute_command, pattern=r"^restore_confirm_execute$")]
    },
    fallbacks=[
        CallbackQueryHandler(restore_cancel_to_backup_options_menu, pattern=r"^restore_cancel_to_backup_options$"),
        CommandHandler("cancel", lambda u,c: restore_cancel_to_backup_options_menu(u,c)) # فرض میکنیم cancel به همین منو برگردد
    ],
    name=RESTORE_CONV,
    per_user=True,
    per_chat=True,
)
#----------logs
@admin_only
async def send_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    logger.info(f"Log file requested by admin {update.effective_user.id}")

    log_summary_text = "📝 خلاصه‌ای از آخرین لاگ‌ها:\n\n"
    log_file_sent = False

    if os.path.exists(LOG_FILE_PATH):
        try:
            # ارسال فایل کامل لاگ
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
            with open(LOG_FILE_PATH, 'rb') as log_file_obj:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=log_file_obj,
                    filename="bot_logs.txt", # نام فایل ارسالی می‌تواند متفاوت باشد
                    caption="فایل کامل لاگ‌های ربات."
                )
            log_file_sent = True

            # تهیه و ارسال خلاصه‌ای از چند خط آخر لاگ
            try:
                with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    last_n_lines = lines[-50:] # به عنوان مثال ۵۰ خط آخر
                    if last_n_lines:
                        log_summary_text += "```\n" # شروع بلوک کد برای خوانایی بهتر
                        log_summary_text += "".join(last_n_lines)
                        log_summary_text += "\n```" # پایان بلوک کد
                    else:
                        log_summary_text += "(فایل لاگ خالی است یا خطوط کمی دارد)"
            except Exception as e_read:
                logger.error(f"Could not read log file for summary: {e_read}")
                log_summary_text += "(خطا در خواندن خلاصه لاگ)"

        except Exception as e:
            logger.error(f"Failed to send log file: {e}")
            log_summary_text = f"⚠️ خطایی در ارسال فایل لاگ رخ داد: {e}"
    else:
        log_summary_text = "فایل لاگ یافت نشد. ممکن است هنوز هیچ لاگی ثبت نشده باشد."

    
    reply_m = build_main_menu()
    if len(log_summary_text) > 4096: # محدودیت طول پیام تلگرام
        # ارسال خلاصه در چند پیام اگر خیلی طولانی است (اینجا ساده شده و فقط بخش اول ارسال می‌شود)
        summary_part1 = log_summary_text[:4000] + "\n... (ادامه دارد)"
        if log_file_sent:
             summary_part1 += "\n\nفایل کامل لاگ نیز ارسال شد."
        try:
            await query.edit_message_text(summary_part1, reply_markup=reply_m, parse_mode=ParseMode.HTML)
        except BadRequest: # اگر ویرایش ممکن نبود
            await context.bot.send_message(update.effective_chat.id, summary_part1, reply_markup=reply_m, parse_mode=ParseMode.HTML)
    else:
        if log_file_sent and log_summary_text.startswith("📝"):
             log_summary_text += "\n\nفایل کامل لاگ نیز ارسال شد."
        try:
            await query.edit_message_text(log_summary_text, reply_markup=reply_m, parse_mode=ParseMode.HTML)
        except BadRequest:
            await context.bot.send_message(update.effective_chat.id, log_summary_text, reply_markup=reply_m, parse_mode=ParseMode.HTML)
#---------------------help
@admin_only
async def send_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_full_name = update.effective_user.full_name

    help_text = f"<b>راهنمای جامع ربات مدیریت تلگرام برای ادمین {user_full_name}</b>\n\n"
    help_text += "این ربات برای مدیریت اکانت‌های تلگرام و انجام عملیات مختلف با آن‌ها و همچنین با خود ربات طراحی شده است.\n\n"

    help_text += "<b>۱. مدیریت اکانت‌ها (⚙️)</b>\n"
    help_text += "- <u>افزودن اکانت جدید:</u> می‌توانید اکانت‌های تلگرام ایرانی یا خارجی را به ربات اضافه کنید. ربات از شما شماره تلفن، کد تایید و در صورت نیاز رمز عبور تایید دو مرحله‌ای را سوال خواهد کرد. هر اکانت به یک فایل نشست مجزا ذخیره می‌شود.\n"
    help_text += "- <u>حذف اکانت:</u> اکانت‌های اضافه شده را از لیست و فایل نشست مربوطه را از سرور حذف می‌کند.\n"
    help_text += "- <u>نمایش لیست اکانت‌ها:</u> تمام اکانت‌های اضافه شده به همراه وضعیت (فعال/غیرفعال)، نوع (ایرانی/خارجی)، شماره، یوزرنیم و تاریخ افزودن را نمایش می‌دهد.\n\n"

    help_text += "<b>۲. ابزارها (با اکانت‌ها) (🛠)</b>\n"
    help_text += "این ابزارها عملیات را با استفاده از اکانت‌های تلگرامی که به ربات اضافه کرده‌اید، انجام می‌دهند:\n"
    help_text += "- <u>پیوستن به کانال/گروه:</u> اکانت(های) منتخب شما را عضو کانال یا گروه مورد نظر می‌کند (با لینک خصوصی یا عمومی/آیدی).\n"
    help_text += "- <u>ترک کانال/گروه:</u> اکانت(های) منتخب را از کانال/گروه خارج می‌کند.\n"
    help_text += "- <u>بلاک کردن کاربر:</u> کاربر مورد نظر را توسط اکانت(های) منتخب بلاک می‌کند.\n"
    help_text += "- <u>ریپورت کردن کاربر/کانال/گروه:</u> با دلایل استاندارد تلگرام، کاربر یا چت مورد نظر را توسط اکانت(های) منتخب ریپورت می‌کند.\n"
    help_text += "- <u>ارسال پیام اسپم:</u> به کاربر یا چت هدف، تعدادی پیام با متن و تاخیر مشخص توسط اکانت(های) منتخب ارسال می‌کند.\n"
    help_text += "- <u>حذف اعضا از گروه (با اکانت‌ها):</u> اعضای عادی (غیر ادمین) یک گروه را توسط اکانت(های) منتخب (که باید در گروه ادمین با دسترسی حذف باشند) حذف می‌کند.\n"
    help_text += "- <u>ارتقا به ادمین در گروه (با اکانت‌ها):</u> کاربران مشخص شده را در گروه هدف توسط اکانت(های) منتخب (که باید دسترسی افزودن ادمین داشته باشند) به ادمین ارتقا می‌دهد.\n"
    help_text += "<i>نکته برای ابزارها:</i> ابتدا باید دسته‌بندی اکانت‌ها (ایرانی، خارجی، همه) و سپس تعداد آن‌ها (همه یا تعداد مشخص) را برای انجام عملیات انتخاب کنید.\n\n"

    help_text += "<b>۳. عملیات با ربات (🤖)</b>\n"
    help_text += "این عملیات مستقیماً توسط خود ربات اصلی انجام می‌شوند:\n"
    help_text += "- <u>اسپم به گروه/کانال (با ربات):</u> ربات پیام‌های مشخصی را به گروه یا کانال هدف ارسال می‌کند (ربات باید عضو و دارای دسترسی ارسال پیام باشد).\n"
    help_text += "- <u>حذف مشترکین کانال/اعضای گروه (پیشرفته):</u> ربات با کمک یک اکانت تلگرامی (برای لیست کردن اعضا) و سپس با دسترسی ادمینی خود، اعضای عادی یک گروه یا مشترکین یک کانال را حذف/مسدود می‌کند.\n"
    help_text += "- <u>افزودن ادمین در کانال/گروه (با ربات):</u> ربات کاربران مشخص شده را در چت هدف به ادمین ارتقا می‌دهد (ربات باید ادمین با دسترسی افزودن ادمین جدید باشد).\n\n"

    help_text += "<b>۴. تنظیمات ربات (🔧)</b>\n"
    help_text += "- <u>مدیریت API ID/Hash:</u> می‌توانید جفت‌های API ID و Hash تلگرام را برای استفاده در افزودن اکانت‌ها و برخی ابزارها مدیریت (افزودن/حذف) کنید.\n"
    help_text += "- <u>مدیریت ادمین‌ها:</u> ادمین‌های جدیدی را به دیتابیس ربات اضافه یا حذف کنید (علاوه بر ادمین‌های تعریف شده در فایل کانفیگ).\n"
    help_text += "- <u>مدیریت کلمات اسپم:</u> لیست کلمات یا عباراتی که در عملیات اسپم به عنوان پیام پیش‌فرض استفاده می‌شوند را مدیریت کنید.\n"
    help_text += "- <u>مدیریت تأخیر عمومی:</u> یک مقدار تأخیر پیش‌فرض (به ثانیه) برای برخی عملیات گروهی (مانند اسپم یا حذف اعضا) تنظیم کنید.\n\n"
    
    # بخش راهنمای پشتیبان گیری و لاگ به متن اصلی اضافه می شود.
    # اگر متن خیلی طولانی شد، باید به چند پیام تقسیم شود.
    help_text_part2 = "<b>۵. دریافت لاگ‌ها (📋)</b>\n"
    help_text_part2 += "- این گزینه فایل کامل لاگ‌های ثبت شده توسط ربات را به همراه خلاصه‌ای از چند ده خط آخر برای شما ارسال می‌کند. این لاگ‌ها برای بررسی خطاها و عملکرد ربات مفید هستند.\n\n"

    help_text_part2 += "<b>۶. پشتیبان‌گیری و بازیابی (💾)</b>\n"
    help_text_part2 += "- <u>تهیه فایل پشتیبان:</u> از تمام اطلاعات مهم ربات شامل دیتابیس (اکانت‌ها، تنظیمات) و فایل‌های نشست اکانت‌های تلگرام یک فایل فشرده `.zip` تهیه و برای شما ارسال می‌کند. این فایل را در جای امنی نگهداری کنید.\n"
    help_text_part2 += "- <u>بازیابی از فایل پشتیبان:</u> به شما امکان می‌دهد اطلاعات ربات را از یک فایل پشتیبان قبلی بازگردانی کنید. <b>هشدار: این عملیات تمام اطلاعات فعلی را بازنویسی می‌کند و غیرقابل بازگشت است. پس از بازیابی، ربات نیاز به راه‌اندازی مجدد دستی دارد.</b>\n\n"

    help_text_part2 += "<b>لغو عملیات:</b>\n"
    help_text_part2 += "در بیشتر مراحل چندمرحله‌ای، دکمه 'لغو' یا 'بازگشت' وجود دارد. همچنین می‌توانید از دستور /cancel برای لغو مکالمه فعلی و بازگشت به منوی اصلی یا منوی مربوطه استفاده کنید.\n\n"
    help_text_part2 += "موفق باشید!"

    # ارسال در دو بخش به دلیل محدودیت طول پیام تلگرام
    try:
        await query.edit_message_text(help_text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text_part2, reply_markup=None, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # اگر پیام اول تغییر نکرده، فقط قسمت دوم را بفرست
            await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text_part2, reply_markup=None, parse_mode=ParseMode.HTML)
        else: # خطای دیگر در ویرایش
            logger.error(f"Error sending help text (edit): {e}")
            # ارسال هر دو بخش به عنوان پیام جدید
            await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text_part2, reply_markup=None, parse_mode=ParseMode.HTML)
    except Exception as e_final:
        logger.error(f"Error sending help text: {e_final}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="خطا در نمایش راهنما.", reply_markup=build_main_menu())
#-------------dok help
@admin_only
async def show_help_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = "📖 **بخش راهنمای ربات**\n\nلطفاً موضوع مورد نظر خود را برای مشاهده راهنما انتخاب کنید:"
    await query.edit_message_text(text=text, reply_markup=build_help_options_submenu(), parse_mode=ParseMode.HTML)

@admin_only
async def show_help_accounts_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای مدیریت اکانت‌ها (⚙️)</b>

    این بخش به شما امکان مدیریت اکانت‌های تلگرامی که ربات از آن‌ها برای انجام برخی عملیات استفاده می‌کند را می‌دهد.

    🔸 <b>افزودن اکانت جدید:</b>
       - می‌توانید اکانت‌های تلگرام ایرانی (با پیش‌شماره <code>+98</code>) یا خارجی را به ربات اضافه کنید.
       - ربات از شما به ترتیب شماره تلفن، کد تاییدی که به تلگرام ارسال می‌شود، و در صورت فعال بودن تایید دو مرحله‌ای، رمز عبور آن را سوال خواهد کرد.
       - پس از افزودن موفق، یک فایل نشست (session) برای آن اکانت در پوشه <code>data/sessions/</code> روی سرور ایجاد می‌شود. این فایل حاوی اطلاعات ورود اکانت است.

    🔸 <b>حذف اکانت:</b>
       - با انتخاب این گزینه، لیستی از اکانت‌های اضافه شده نمایش داده می‌شود.
       - با انتخاب هر اکانت و تایید نهایی، اطلاعات آن از دیتابیس ربات و همچنین فایل نشست مربوطه از سرور حذف خواهد شد. این عملیات غیرقابل بازگشت است.

    🔸 <b>نمایش لیست اکانت‌ها:</b>
       - این گزینه لیستی از تمام اکانت‌های تلگرامی اضافه شده به ربات را نمایش می‌دهد.
       - اطلاعات شامل: وضعیت فعالیت (✅ فعال / ❌ غیرفعال یا مشکل‌دار)، نوع اکانت (🇮🇷 ایرانی / 🌍 خارجی)، شماره تلفن، یوزرنیم (در صورت وجود)، شناسه کاربری تلگرام، و تاریخ افزودن اکانت به ربات است.

    <i>نکته: فعال یا غیرفعال بودن اکانت‌ها در آینده می‌تواند برای محدود کردن عملیات به اکانت‌های سالم استفاده شود (این قابلیت هنوز به طور کامل در همه بخش‌ها پیاده نشده است).</i>
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@admin_only
async def show_help_tools_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای ابزارها (با اکانت‌ها) (🛠)</b>

    این ابزارها عملیات مختلف را با استفاده از اکانت‌های تلگرامی که شما به ربات اضافه کرده‌اید، انجام می‌دهند. برای استفاده از هر ابزار:
    ۱. ابتدا دسته‌بندی اکانت‌هایی که می‌خواهید استفاده شوند (ایرانی، خارجی، یا همه) را انتخاب کنید.
    ۲. سپس مشخص کنید که آیا از تمام اکانت‌های فیلتر شده در آن دسته استفاده شود یا تعداد مشخصی از آن‌ها.
    ۳. در نهایت، ورودی مورد نیاز ابزار (مانند لینک گروه، یوزرنیم کاربر و ...) را وارد کنید.

    🔸 <b>پیوستن به کانال/گروه:</b>
       - اکانت(های) منتخب شما را عضو کانال یا گروه مورد نظر (با لینک عمومی یا خصوصی مانند <code>t.me/joinchat/...</code> یا <code>t.me/+...</code> یا یوزرنیم مانند <code>@channelname</code>) می‌کند.

    🔸 <b>ترک کانال/گروه:</b>
       - اکانت(های) منتخب را از کانال یا گروهی که با لینک یا یوزرنیم مشخص می‌کنید، خارج می‌کند.

    🔸 <b>بلاک کردن کاربر:</b>
       - کاربر مورد نظر (با یوزرنیم یا شناسه عددی) را توسط اکانت(های) منتخب بلاک می‌کند.

    🔸 <b>ریپورت کردن کاربر / کانال/گروه:</b>
       - با انتخاب دلیل مناسب از لیست دلایل استاندارد تلگرام (یا وارد کردن دلیل سفارشی برای گزینه "سایر")، کاربر یا چت مورد نظر (با یوزرنیم یا شناسه عددی) را توسط اکانت(های) منتخب ریپورت می‌کند.

    🔸 <b>ارسال پیام اسپم:</b>
       - به کاربر یا چت هدف (با یوزرنیم یا شناسه عددی)، تعدادی پیام با متن و تأخیر مشخص توسط اکانت(های) منتخب ارسال می‌کند. می‌توانید از پیام‌های پیش‌فرض یا متن دلخواه خود استفاده کنید.

    🔸 <b>حذف اعضا از گروه (با اکانت‌ها):</b>
       - اعضای عادی (غیر ادمین و غیر ربات) یک گروه را توسط اکانت(های) منتخب شما حذف (kick) می‌کند. اکانت‌های انجام دهنده باید در گروه هدف ادمین باشند و دسترسی لازم برای حذف اعضا را داشته باشند.

    🔸 <b>ارتقا به ادمین در گروه (با اکانت‌ها):</b>
       - کاربران مشخص شده (با یوزرنیم یا شناسه عددی) را در گروه هدف، توسط اکانت(های) منتخب شما به ادمین با دسترسی کامل ارتقا می‌دهد. اکانت‌های انجام دهنده باید دسترسی افزودن ادمین جدید را در گروه هدف داشته باشند.
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@admin_only
async def show_help_bot_ops_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای عملیات با ربات (🤖)</b>

    این عملیات مستقیماً توسط خود ربات اصلی (نه اکانت‌های تلگرامی اضافه شده) انجام می‌شوند.

    🔸 <b>اسپم به گروه/کانال (با ربات):</b>
       - ربات تعدادی پیام با متن و تأخیر مشخص را به گروه یا کانال هدف ارسال می‌کند.
       - ربات باید عضو گروه/کانال باشد و دسترسی لازم برای ارسال پیام را داشته باشد.
       - هدف می‌تواند شناسه عددی یا لینک/یوزرنیم باشد.

    🔸 <b>حذف مشترکین کانال/اعضای گروه (پیشرفته):</b>
       - این عملیات برای حذف انبوه اعضای عادی از گروه‌ها یا مسدود کردن مشترکین از کانال‌ها طراحی شده است.
       - <u>مراحل کار:</u>
         ۱. ابتدا شناسه/لینک گروه یا کانال هدف را وارد می‌کنید.
         ۲. سپس یک اکانت تلگرامی فعال (که قبلاً به ربات اضافه کرده‌اید و عضو چت هدف است) را به عنوان "اکانت کمکی" انتخاب می‌کنید. این اکانت فقط برای دریافت لیست اولیه اعضا/مشترکین استفاده می‌شود.
         ۳. پس از دریافت لیست و تأیید شما، ربات اصلی (نه اکانت کمکی) شروع به حذف (برای گروه) یا مسدود کردن (برای کانال) کاربران می‌کند.
       - <b>نیازها:</b>
         - ربات اصلی باید در گروه/کانال هدف ادمین باشد و دسترسی لازم برای حذف/مسدود کردن کاربران را داشته باشد.
         - اکانت کمکی باید عضو چت هدف باشد تا بتواند لیست کاربران را بخواند.

    🔸 <b>افزودن ادمین در کانال/گروه (با ربات):</b>
       - ربات کاربران مشخص شده (با شناسه عددی یا یوزرنیم) را در چت هدف (کانال یا گروه) به ادمین با دسترسی‌های کامل ارتقا می‌دهد.
       - <u>مراحل کار:</u>
         ۱. شناسه/لینک چت هدف را وارد می‌کنید.
         ۲. سپس می‌توانید یا از بین دسته‌بندی اکانت‌های تلگرامی ذخیره شده در ربات انتخاب کنید که کدام‌ها ادمین شوند، یا لیست مشخصی از شناسه‌ها/یوزرنیم‌ها را برای ارتقا وارد نمایید.
       - <b>نیازها:</b>
         - ربات اصلی باید در چت هدف ادمین باشد و دسترسی "افزودن ادمین‌های جدید" را داشته باشد.
         - کاربرانی که قرار است ادمین شوند، باید عضو آن چت باشند.
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@admin_only
async def show_help_settings_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای تنظیمات ربات (🔧)</b>

    این بخش به شما امکان پیکربندی جنبه‌های مختلف عملکرد ربات را می‌دهد.

    🔸 <b>مدیریت API ID/Hash:</b>
       - برای افزودن اکانت‌های تلگرام جدید به ربات، نیاز به یک جفت <code>API ID</code> و <code>API Hash</code> معتبر از تلگرام دارید (می‌توانید از <a href="https://my.telegram.org/apps">my.telegram.org/apps</a> دریافت کنید).
       - در این بخش می‌توانید چندین جفت API را اضافه یا حذف کنید. ربات هنگام افزودن اکانت جدید، به صورت تصادفی از یکی از این جفت‌های ذخیره شده استفاده می‌کند.
       - اگر هیچ API در دیتابیس ذخیره نشده باشد، ربات از مقادیر پیش‌فرض تعریف شده در فایل <code>config.py</code> (در صورت وجود) استفاده خواهد کرد.

    🔸 <b>مدیریت ادمین‌ها:</b>
       - علاوه بر ادمین‌هایی که شناسه‌شان مستقیماً در فایل <code>config.py</code> وارد شده (و از اینجا قابل حذف نیستند)، می‌توانید ادمین‌های دیگری را از طریق ربات به دیتابیس اضافه یا حذف کنید.
       - این ادمین‌ها نیز دسترسی کامل به تمام قابلیت‌های ربات خواهند داشت.

    🔸 <b>مدیریت کلمات اسپم:</b>
       - لیستی از کلمات یا عباراتی که می‌توانید برای عملیات "ارسال پیام اسپم" (هم در ابزارها و هم در عملیات با ربات) استفاده کنید.
       - اگر هنگام اسپم کردن، به جای متن پیام، کلمه "default" را وارد کنید، ربات به صورت تصادفی از این لیست یک پیام انتخاب و ارسال می‌کند.

    🔸 <b>مدیریت تأخیر عمومی:</b>
       - یک مقدار تأخیر پیش‌فرض (به ثانیه) برای برخی عملیات گروهی و زمان‌بر مانند اسپم کردن یا حذف اعضا تنظیم می‌کند.
       - این تأخیر بین هر اقدام کوچک (مثلاً ارسال هر پیام یا حذف هر عضو) اعمال می‌شود تا از محدودیت‌های تلگرام (Flood) جلوگیری شود.
       - مقدار پیشنهادی بین 0.5 تا 3 ثانیه است.
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@admin_only
async def show_help_backup_restore_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای پشتیبان‌گیری و بازیابی (💾)</b>

    این بخش برای حفظ اطلاعات ربات شما و بازیابی آن‌ها در صورت نیاز ضروری است.

    🔸 <b>تهیه فایل پشتیبان:</b>
       - با انتخاب این گزینه، ربات یک فایل فشرده (<code>.zip</code>) شامل موارد زیر ایجاد و برای شما ارسال می‌کند:
         - <b>فایل دیتابیس (<code>database.db</code>):</b> حاوی تمام اطلاعات اکانت‌های اضافه شده، تنظیمات ربات (API ها، ادمین‌های دیتابیس، کلمات اسپم، تأخیر) و سایر داده‌های ذخیره شده.
         - <b>پوشه فایل‌های نشست (<code>sessions</code>):</b> شامل تمام فایل‌های <code>.session</code> مربوط به اکانت‌های تلگرامی که به ربات اضافه کرده‌اید. این فایل‌ها برای ورود مجدد به اکانت‌ها بدون نیاز به کد تایید ضروری هستند.
       - نام فایل پشتیبان شامل تاریخ و زمان ایجاد آن خواهد بود.
       - <b>توصیه می‌شود این فایل را به طور منظم تهیه کرده و در مکانی امن نگهداری کنید.</b>

    🔸 <b>بازیابی از فایل پشتیبان:</b>
       - این گزینه به شما امکان می‌دهد اطلاعات ربات را از یک فایل پشتیبان (<code>.zip</code>) که قبلاً تهیه کرده‌اید، بازگردانی کنید.
       - <u>مراحل کار:</u>
         ۱. پس از انتخاب این گزینه، ربات از شما می‌خواهد فایل <code>.zip</code> پشتیبان را ارسال کنید.
         ۲. پس از دریافت فایل، از شما تأیید نهایی برای شروع عملیات بازنویسی اطلاعات گرفته می‌شود.
       - ⚠️ <b>هشدارهای بسیار مهم:</b>
         - عملیات بازیابی، تمام اطلاعات فعلی ربات (دیتابیس و فایل‌های نشست) را با محتویات فایل پشتیبان <b>جایگزین و بازنویسی کامل</b> خواهد کرد.
         - این عملیات <b>غیرقابل بازگشت</b> است. قبل از تأیید، از انتخاب فایل صحیح مطمئن شوید.
         - برای اعمال کامل تغییرات پس از بازیابی موفقیت‌آمیز (به خصوص بارگذاری مجدد اطلاعات دیتابیس و فایل‌های نشست توسط ربات)، <b>نیاز است که ربات را به صورت دستی راه‌اندازی مجدد (Restart) کنید.</b> ربات پس از اتمام بازیابی این موضوع را به شما یادآوری خواهد کرد.
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@admin_only
async def show_help_logs_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = """
    📖 <b>راهنمای لاگ‌ها و خطایابی (📋)</b>

    بخش "دریافت لاگ‌ها" از منوی اصلی به شما امکان می‌دهد فایل کامل لاگ‌های ربات و خلاصه‌ای از چند ده خط آخر آن را دریافت کنید. این لاگ‌ها برای درک عملکرد ربات و شناسایی مشکلات احتمالی بسیار مفید هستند.

    <b>فایل لاگ چیست؟</b>
    فایل لاگ (<code>bot.log</code> در پوشه <code>logs</code>) سابقه‌ای از فعالیت‌ها، هشدارها و خطاهای ربات را در خود ذخیره می‌کند. هر خط لاگ معمولاً شامل تاریخ و زمان، سطح لاگ (INFO, WARNING, ERROR)، نام ماژول و خود پیام لاگ است.

    <b>تفسیر برخی از پیام‌های لاگ رایج:</b>

    🔸 <b>سطح INFO (اطلاعاتی):</b>
       - <code>Admin ... started the bot.</code>: یک ادمین ربات را با دستور /start فراخوانی کرده است.
       - <code>MenuRouter: Admin ... pressed: ...</code>: ادمین یک دکمه در منوها را فشار داده است.
       - <code>Connecting Telethon for ...</code>: ربات در حال تلاش برای اتصال یک اکانت تلگرام است.
       - <code>Backup creation requested... / Backup ZIP file created...</code>: عملیات پشتیبان‌گیری شروع یا تمام شده.
       - <code>Default operation delay set to ...</code>: تنظیمات تأخیر تغییر کرده.
       - این لاگ‌ها معمولاً نشان‌دهنده عملکرد عادی ربات هستند.

    🔸 <b>سطح WARNING (هشدار):</b>
       - <code>API ID/Hash is not set...</code>: کلید API در تنظیمات یا کانفیگ موجود نیست. ممکن است برخی عملیات با خطا مواجه شوند.
       - 
       - <code>User ... not authorized.</code> (در لاگ‌های Telethon): اکانت تلگرام نیاز به احراز هویت مجدد دارد.
       - <code>Message is not modified...</code>: ربات سعی کرده پیامی را ویرایش کند که محتوای آن تغییری نکرده است (معمولاً مشکل‌ساز نیست).
       - <code>Failed to ... (e.g., copy session file, delete keyword)</code>: یک عملیات جزئی با موفقیت انجام نشده اما ربات به کار خود ادامه می‌دهد.
       - <code>User_privacy_restricted</code> (در عملیات افزودن ادمین یا بلاک): کاربر هدف به دلیل تنظیمات حریم خصوصی خود قابل مدیریت نیست.

    🔸 <b>سطح ERROR (خطا):</b>
       - <code>Could not resolve or validate ID ... Chat not found</code>: ربات نتوانسته چت (گروه/کانال/کاربر) مورد نظر را با شناسه یا لینک داده شده پیدا کند. (علت: لینک اشتباه، ربات عضو نیست، چت وجود ندارد).
       - <code>AttributeError: 'NoneType' object has no attribute 'reply_text'</code>: یک خطای برنامه‌نویسی داخلی، معمولاً به این معنی که سعی شده روی یک آبجکت خالی (None) عملیاتی انجام شود (مثلاً ارسال پاسخ به پیامی که وجود ندارد).
       - <code>BadRequest: Can't parse entities: character 'X' is reserved...</code>: خطای فرمت‌بندی متن هنگام ارسال پیام با MarkdownV2 یا HTML. کاراکتر خاصی escape نشده.
       - <code>telegram.error.TimedOut / httpx.ConnectTimeout</code>: مشکل در اتصال به سرورهای تلگرام (احتمالاً مشکل شبکه یا قطعی موقت).
       - <code>KeyError: 'some_key'</code>: یک کلید مورد انتظار در دیکشنری (معمولاً <code>context.user_data</code> یا <code>context.bot_data</code>) یافت نشده (خطای برنامه‌نویسی).
       - <code>No error handlers are registered...</code>: خطایی رخ داده ولی تابع عمومی مدیریت خطا در ربات ثبت نشده. (باید همیشه یک error_handler فعال باشد).
       - <code>Telethon errors (e.g., FloodWaitError, PhoneNumberBannedError)</code>: خطاهای مربوط به کتابخانه Telethon هنگام کار با اکانت‌های تلگرام. برخی (مثل FloodWait) توسط ربات مدیریت می‌شوند، برخی دیگر (مثل Banned) نشان‌دهنده مشکل در اکانت هستند.

    <b>خطایابی عمومی:</b>
    - همیشه به تاریخ و زمان لاگ توجه کنید تا آن را با زمان بروز مشکل تطبیق دهید.
    - پیام‌های ERROR معمولاً حاوی یک Traceback (ردپای خطا) هستند که نشان می‌دهد خطا دقیقاً در کدام قسمت از کد رخ داده است. این اطلاعات برای توسعه‌دهنده بسیار مفید است.
    - اگر با خطایی مواجه شدید که نمی‌توانید علت آن را پیدا کنید، ارسال متن کامل لاگ (به خصوص Traceback) به توسعه‌دهنده یا برای دریافت پشتیبانی بسیار کمک‌کننده خواهد بود.
    """
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت به منوی راهنما", callback_data="main_menu_help")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="general_back_to_main_menu")]
    ])
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest as e: # اگر پیام خیلی طولانی شد
        logger.warning(f"Help text for logs guide too long: {e}")
        # ارسال بخش اول و اطلاع رسانی
        first_part = text[:4000] + "\n\n<b>(ادامه راهنما در پیام بعدی...)</b>"
        await query.edit_message_text(text=first_part, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
        await context.bot.send_message(chat_id=update.effective_chat.id, text="بخش راهنمای لاگ‌ها به دلیل طولانی بودن، به طور کامل نمایش داده نشد. لطفاً متن کامل را از توسعه دهنده دریافت کنید یا این متن را کپی کنید.", disable_web_page_preview=True)

#---------------ليست اکانت ها
def build_accounts_page_keyboard(accounts_on_page: list[dict], current_page: int, total_pages: int, category_filter_cb: str) -> InlineKeyboardMarkup:
    keyboard = []
    for acc in accounts_on_page:
        category_emoji = "🇮🇷" if acc.get('account_category') == 'iranian' else "🌍" if acc.get('account_category') == 'foreign' else "❔"
        button_text = f"{category_emoji} {acc.get('phone_number')} ({acc.get('username', 'بدون یوزرنیم') or ' '})" # یا هر فرمت دیگری که میخواهید
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"list_acc_detail_{acc.get('id')}")])

    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ صفحه قبل", callback_data=f"list_acc_page_prev_{category_filter_cb}"))
    if current_page < total_pages - 1:
        pagination_buttons.append(InlineKeyboardButton("➡️ صفحه بعد", callback_data=f"list_acc_page_next_{category_filter_cb}"))
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    keyboard.append([InlineKeyboardButton("🔁 انتخاب مجدد دسته‌بندی", callback_data="list_acc_back_to_cat_select")])
    keyboard.append([InlineKeyboardButton("⬅️ بازگشت به منوی اکانت‌ها", callback_data="list_acc_cancel_to_accounts_menu")])
    return InlineKeyboardMarkup(keyboard)

async def display_accounts_page(update: Update, context: ContextTypes.DEFAULT_TYPE, category_filter: str | None) -> int:
    query = update.callback_query # میتواند از message هم بیاید اگر از entry point است
    
    accounts_full_list = context.user_data.get(f'list_accounts_cat_{category_filter if category_filter else "all"}', [])
    current_page = context.user_data.get('list_accounts_current_page', 0)

    if not accounts_full_list:
        text = "هیچ اکانتی در این دسته‌بندی یافت نشد."
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 انتخاب مجدد دسته‌بندی", callback_data="list_acc_back_to_cat_select")],
            [InlineKeyboardButton("⬅️ بازگشت به منوی اکانت‌ها", callback_data="list_acc_cancel_to_accounts_menu")]
        ])
    else:
        start_index = current_page * ACCOUNTS_PER_PAGE
        end_index = start_index + ACCOUNTS_PER_PAGE
        accounts_on_page = accounts_full_list[start_index:end_index]
        
        total_pages = (len(accounts_full_list) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE
        
        category_display_name = "ایرانی" if category_filter == "iranian" else "خارجی" if category_filter == "foreign" else "همه اکانت‌ها"
        text = f"📄 **لیست اکانت‌های {category_display_name}** (صفحه {current_page + 1} از {total_pages})\n"
        text += "روی هر اکانت کلیک کنید تا جزئیات آن نمایش داده شود:"
        
        # برای callback_data دکمه های pagination، خود فیلتر دسته را هم پاس میدهیم
        category_filter_cb_suffix = category_filter if category_filter else "all"
        reply_markup = build_accounts_page_keyboard(accounts_on_page, current_page, total_pages, category_filter_cb_suffix)

    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    elif update.message: # اگر از نقطه ورود اولیه آمده باشد
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    return LIST_ACC_SHOW_PAGE
# --- مسیریاب اصلی منوها ---
@admin_only
async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query; await query.answer(); callback_data = query.data; user_full_name = update.effective_user.full_name if update.effective_user else "Unknown"; logger.info(f"MenuRouter: Admin {user_full_name} pressed: {callback_data}")
    current_text = query.message.text if query and query.message else ""
    current_reply_markup = query.message.reply_markup if query and query.message else None
    current_parse_mode = query.message.parse_mode if query and query.message and hasattr(query.message, 'parse_mode') else None

    async def edit_or_send(text, reply_markup, parse_mode=ParseMode.HTML):
        nonlocal current_text, current_reply_markup, current_parse_mode
        if text == current_text and reply_markup == current_reply_markup and parse_mode == current_parse_mode : logger.info(f"MenuRouter: Content for {callback_data} is identical. Skipping edit."); return
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            current_text = text; current_reply_markup = reply_markup; current_parse_mode = parse_mode
        except BadRequest as e:
            if "Message is not modified" in str(e): logger.info(f"MenuRouter: Message not modified for {callback_data}.")
            else: logger.warning(f"MenuRouter: BadRequest for {callback_data}: {e}. Sending new."); await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e: logger.warning(f"MenuRouter: Unexpected error for {callback_data}: {e}. Sending new."); await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

    # --- مدیریت دکمه‌های راهنما ---
    if callback_data == "main_menu_help":
        return await show_help_options_menu(update, context) # نمایش منوی داخلی راهنما
    elif callback_data == "help_section_accounts":
        return await show_help_accounts_guide(update, context)
    elif callback_data == "help_section_tools":
        return await show_help_tools_guide(update, context)
    elif callback_data == "help_section_bot_ops":
        return await show_help_bot_ops_guide(update, context)
    elif callback_data == "help_section_settings":
        return await show_help_settings_guide(update, context)
    elif callback_data == "help_section_backup_restore":
        return await show_help_backup_restore_guide(update, context)
    elif callback_data == "help_section_logs_guide":
        return await show_help_logs_guide(update, context)
    # --- پایان مدیریت دکمه‌های راهنما ---
    elif callback_data == "main_menu_logs":
        return await send_logs_command(update, context)
    elif callback_data == "main_menu_backup_restore_options":
        return await backup_restore_options_menu_callback(update, context)
    elif callback_data == "backup_create_now":
        return await create_backup_command(update, context)
    if callback_data.startswith("main_menu_") or callback_data.startswith("general_back_to_main_menu") or \
       callback_data.startswith("accounts_") or callback_data.startswith("delete_select_") or callback_data.startswith("delete_confirm_"):
        if callback_data == "main_menu_accounts" or callback_data == "main_menu_accounts_from_action": await edit_or_send(text="بخش مدیریت اکانت‌ها:", reply_markup=build_accounts_menu())
        elif callback_data == "main_menu_tools" or callback_data == "main_menu_tools_from_action": await edit_or_send(text="بخش ابزارها (با اکانت‌ها):", reply_markup=build_tools_menu())
        elif callback_data == "main_menu_bot_operations": await edit_or_send(text="بخش عملیات با ربات:", reply_markup=build_bot_operations_menu())
        elif callback_data == "general_back_to_main_menu": await edit_or_send(text=rf"سلام ادمین گرامی <b>{user_full_name}</b>! 👋\nبه ربات مدیریت اکانت‌های تلگرام خوش آمدید.\nلطفا یک گزینه را از منوی زیر انتخاب کنید:", reply_markup=build_main_menu())
        elif callback_data == "accounts_delete_start": return await accounts_delete_start_callback(update, context)
        elif callback_data.startswith("delete_select_"): return await delete_account_selection_callback(update, context)
        elif callback_data.startswith("delete_confirm_"): return await delete_account_confirm_callback(update, context)
        elif callback_data.endswith("_placeholder"):
            placeholder_name = callback_data.replace("_placeholder", "").replace("main_menu_", "").replace("accounts_", "").replace("tools_", "").replace("bot_op_", "").replace("_", " ").title()
            back_menu = build_main_menu()
            if "accounts_" in callback_data : back_menu = build_accounts_menu()
            elif "tools_" in callback_data : back_menu = build_tools_menu()
            elif "bot_op_" in callback_data : back_menu = build_bot_operations_menu()
            elif "settings" in callback_data: back_menu = build_main_menu()
            await edit_or_send(text=f"بخش '{placeholder_name}' هنوز پیاده‌سازی نشده.", reply_markup=back_menu)
    return None

# --- توابع اجرایی برای ابزارها ---
# این تابع باید قبل از build_tool_conv_handler تعریف شود
async def tool_target_input_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tool_prefix = context.user_data.get('tool_prefix')
    target_input = update.message.text.strip()
    context.user_data[f'{tool_prefix}_target_input'] = target_input 

    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"

    if tool_prefix == "joiner": return await joiner_execute_logic(update, context)
    elif tool_prefix == "leaver": return await leaver_execute_logic(update, context)
    elif tool_prefix == "blocker": return await blocker_execute_logic(update, context)
    elif tool_prefix == "reporter_user":
        await update.message.reply_text("دلیل ریپورت کاربر را انتخاب کنید:", reply_markup=build_report_reason_menu(config.REPORT_REASONS_USER_DATA, config.REPORT_REASON_CALLBACK_PREFIX_USER, cancel_cb_data))
        return REPORTER_USER_ASK_REASON
    elif tool_prefix == "reporter_chat":
        await update.message.reply_text("دلیل ریپورت کانال/گروه را انتخاب کنید:", reply_markup=build_report_reason_menu(config.REPORT_REASONS_CHAT_DATA, config.REPORT_REASON_CALLBACK_PREFIX_CHAT, cancel_cb_data))
        return REPORTER_CHAT_ASK_REASON
    elif tool_prefix == "spammer":
        context.user_data[f'{tool_prefix}_target_id'] = target_input 
        await update.message.reply_text("💬 تعداد پیام‌هایی که می‌خواهید ارسال شوند را وارد کنید (مثلاً 5):", reply_markup=build_cancel_button(callback_data=cancel_cb_data))
        return SPAMMER_ASK_MESSAGE_COUNT
    elif tool_prefix == "remover":
        return await remover_execute_logic(update, context) 
    elif tool_prefix == "add_admin":
        context.user_data[f'{tool_prefix}_target_group_link'] = target_input 
        await update.message.reply_text("👑 لطفاً یوزرنیم یا آیدی عددی کاربر(ان)ی که می‌خواهید ادمین شوند را وارد کنید (هر کدام در یک خط، یا با کاما و فاصله جدا شده):", reply_markup=build_cancel_button(callback_data=cancel_cb_data))
        return ADD_ADMIN_ASK_USERS_TO_PROMOTE
        
    logger.error(f"Unknown tool_prefix in tool_target_input_received: {tool_prefix}")
    await update.message.reply_text("خطای داخلی در تشخیص ابزار.", reply_markup=build_tools_menu())
    context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_joiner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "پیوستن به کانال/گروه", "joiner", "joiner_cancel_to_tools_menu", JOINER_TOOL_CONV)
async def joiner_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    target_chat = context.user_data.get(f"{context.user_data['tool_prefix']}_target_input"); tool_prefix = context.user_data['tool_prefix']; logger.info(f"JoinerTool: Executing for target: {target_chat}"); accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await update.message.reply_text("هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ تلاش برای پیوستن {len(accounts_to_use)} اکانت به '{target_chat}'...");
    success_count = 0; failure_count = 0; results_summary = []
    for acc in accounts_to_use:
        phone = acc['phone_number']; session_file = acc['session_file']
        # استفاده از مقادیر انتخاب شده
        client = TelegramClient(session_file, api_id_int_for_tool, api_hash_to_use)
        try:
            logger.info(f"Joiner: Processing {phone} for {target_chat}"); await client.connect()
            if not await client.is_user_authorized(): logger.warning(f"Joiner: {phone} not authorized."); results_summary.append((phone, "❌", "نیاز به احراز هویت مجدد")); failure_count += 1; await client.disconnect(); continue
            if "joinchat/" in target_chat or "/+" in target_chat: hash_val = target_chat.split('/')[-1].replace("+", ""); await client(functions.messages.ImportChatInviteRequest(hash_val))
            else: entity = await client.get_entity(target_chat); await client(functions.channels.JoinChannelRequest(channel=entity))
            results_summary.append((phone, "✅", "موفق/از قبل عضو")); success_count += 1
        except UserAlreadyParticipantError: results_summary.append((phone, "✅", "از قبل عضو")); success_count += 1
        except (UserBannedInChannelError, InviteHashExpiredError, InviteHashInvalidError, ValueError, ChannelsTooMuchError, UserChannelsTooMuchError) as e: logger.warning(f"Joiner: {phone} failed for {target_chat}: {type(e).__name__}"); results_summary.append((phone, "❌", f"{type(e).__name__}")); failure_count += 1
        except ConnectionError as e: logger.error(f"Joiner: Connection error for {phone} on {target_chat}: {e}"); results_summary.append((phone, "❌", f"خطای اتصال: {type(e).__name__}")) ; failure_count +=1
        except Exception as e: logger.error(f"Joiner: Unknown error for {phone} on {target_chat}: {type(e).__name__} - {e}"); results_summary.append((phone, "❌", f"خطای ناشناخته: {type(e).__name__}")) ; failure_count +=1
        finally:
            if client.is_connected(): await client.disconnect()
    report = f"🏁 **گزارش پیوستن به '{target_chat}':**\nانتخابی: {len(accounts_to_use)}, موفق: {success_count}✅, ناموفق: {failure_count}❌\n\nجزئیات:\n"; [report := report + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary];
    if len(report) > 4096: report = report[:4000] + "\n\n..."
    await update.message.reply_html(report, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_leaver_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "ترک کانال/گروه", "leaver", "leaver_cancel_to_tools_menu", LEAVER_TOOL_CONV)
async def leaver_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    target_chat = context.user_data.get(f"{context.user_data['tool_prefix']}_target_input"); tool_prefix = context.user_data['tool_prefix']; logger.info(f"LeaverTool: Executing for target: {target_chat}"); accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await update.message.reply_text("هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ تلاش برای خروج {len(accounts_to_use)} اکانت از '{target_chat}'...");
    success_count = 0; failure_count = 0; results_summary = []
    for acc in accounts_to_use:
        phone = acc['phone_number']; session_file = acc['session_file']
        client = TelegramClient(session_file, api_id_int_for_tool, api_hash_to_use)
        try:
            logger.info(f"Leaver: Processing {phone} for {target_chat}"); await client.connect()
            if not await client.is_user_authorized(): logger.warning(f"Leaver: {phone} not authorized."); results_summary.append((phone, "❌", "نیاز به احراز هویت مجدد")); failure_count += 1; await client.disconnect(); continue
            entity_to_leave = await client.get_entity(target_chat)
            if isinstance(entity_to_leave, (types.Channel, types.Chat)): await client(functions.channels.LeaveChannelRequest(entity_to_leave))
            elif isinstance(entity_to_leave, types.User): 
                 logger.warning(f"Leaver: Target {target_chat} for {phone} is a user, not a channel/chat."); results_summary.append((phone, "❌", "هدف کاربر است، نه کانال/گروه")); failure_count +=1; await client.disconnect(); continue
            else: logger.warning(f"Leaver: Entity {target_chat} for {phone} not channel/chat. Type: {type(entity_to_leave)}"); results_summary.append((phone, "❌", "نوع موجودیت نامناسب")); failure_count +=1; await client.disconnect(); continue
            results_summary.append((phone, "✅", "موفق/عضو نبود")); success_count += 1
        except UserNotParticipantError: results_summary.append((phone, "✅", "از قبل عضو نبود")); success_count += 1
        except (ValueError, TypeError) as e: logger.warning(f"Leaver: Invalid target {target_chat} for {phone}: {type(e).__name__}"); results_summary.append((phone, "❌", f"لینک/آیدی نامعتبر: {str(e)[:100]}")); failure_count += 1
        except ChatAdminRequiredError: logger.warning(f"Leaver: {phone} is admin in {target_chat}."); results_summary.append((phone, "❌", "ادمین است و نمی‌تواند خارج شود.")); failure_count += 1
        except ConnectionError as e: logger.error(f"Leaver: Connection error for {phone} on {target_chat}: {e}"); results_summary.append((phone, "❌", f"خطای اتصال: {type(e).__name__}")) ; failure_count +=1
        except Exception as e: logger.error(f"Leaver: Unknown error for {phone} on {target_chat}: {type(e).__name__} - {e}"); results_summary.append((phone, "❌", f"خطای ناشناخته: {type(e).__name__}")); failure_count += 1
        finally:
            if client.is_connected(): await client.disconnect()
    report = f"🏁 **گزارش ترک '{target_chat}':**\nانتخابی: {len(accounts_to_use)}, موفق: {success_count}✅, ناموفق: {failure_count}❌\n\nجزئیات:\n"; [report := report + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary];
    if len(report) > 4096: report = report[:4000] + "\n\n..."
    await update.message.reply_html(report, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_blocker_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "بلاک کردن کاربر", "blocker", "blocker_cancel_to_tools_menu", BLOCKER_TOOL_CONV)
async def blocker_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    target_user_to_block = context.user_data.get(f"{context.user_data['tool_prefix']}_target_input"); tool_prefix = context.user_data['tool_prefix']; logger.info(f"BlockerTool: Executing to block: {target_user_to_block}"); accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await update.message.reply_text("هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ تلاش برای بلاک کردن '{target_user_to_block}' توسط {len(accounts_to_use)} اکانت...")
    success_count = 0; failure_count = 0; results_summary = []
    for acc in accounts_to_use:
        phone = acc['phone_number']; session_file = acc['session_file']
        client = TelegramClient(session_file, api_id_int_for_tool, api_hash_to_use)
        try:
            logger.info(f"Blocker: Processing {phone} to block {target_user_to_block}"); await client.connect()
            if not await client.is_user_authorized(): logger.warning(f"Blocker: {phone} not authorized."); results_summary.append((phone, "❌", "نیاز به احراز هویت مجدد")); failure_count += 1; await client.disconnect(); continue
            try: target_entity = await client.get_entity(target_user_to_block)
            except (ValueError, UserIdInvalidError, PeerIdInvalidError) as e_entity: logger.warning(f"Blocker: Entity not found for '{target_user_to_block}' by {phone}: {e_entity}"); results_summary.append((phone, "❌", f"کاربر '{target_user_to_block}' یافت نشد.")); failure_count += 1; await client.disconnect(); continue
            if not isinstance(target_entity, types.User): 
                logger.warning(f"Blocker: Target '{target_user_to_block}' is not a user (Type: {type(target_entity)}). Cannot block."); results_summary.append((phone, "❌", "هدف کاربر نیست.")); failure_count += 1; await client.disconnect(); continue
            await client(functions.contacts.BlockRequest(id=target_entity))
            logger.info(f"Blocker: {phone} blocked {target_user_to_block} (ID: {target_entity.id})"); results_summary.append((phone, "✅", "بلاک شد.")); success_count += 1
        except UserPrivacyRestrictedError: logger.warning(f"Blocker: {phone} couldn't block {target_user_to_block} (privacy/already blocked)."); results_summary.append((phone, "⚠️", "حریم خصوصی/از قبل بلاک")); failure_count +=1 
        except ConnectionError as e: logger.error(f"Blocker: Connection error for {phone} blocking {target_user_to_block}: {e}"); results_summary.append((phone, "❌", f"خطای اتصال: {type(e).__name__}")); failure_count += 1
        except Exception as e: logger.error(f"Blocker: Unknown error for {phone} blocking {target_user_to_block}: {type(e).__name__} - {e}"); results_summary.append((phone, "❌", f"خطای ناشناخته: {type(e).__name__}")); failure_count += 1
        finally:
            if client.is_connected(): await client.disconnect()
    report = f"🏁 **گزارش بلاک کردن '{target_user_to_block}':**\nانتخابی: {len(accounts_to_use)}, موفق: {success_count}✅, ناموفق/هشدار: {failure_count}❌/⚠️\n\nجزئیات:\n"; [report := report + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary];
    if len(report) > 4096: report = report[:4000] + "\n\n..."
    await update.message.reply_html(report, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_reporter_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "ریپورت کردن کاربر", "reporter_user", "reporter_user_cancel_to_tools_menu", REPORTER_USER_TOOL_CONV)
async def reporter_user_reason_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    query = update.callback_query; await query.answer(); reason_key_from_callback = query.data.replace(config.REPORT_REASON_CALLBACK_PREFIX_USER, "")
    tool_prefix = context.user_data['tool_prefix']; context.user_data[f'{tool_prefix}_report_reason_key'] = reason_key_from_callback 
    selected_reason_info = config.REPORT_REASONS_USER_DATA.get(reason_key_from_callback)
    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"
    if not selected_reason_info: logger.warning(f"Invalid reason key '{reason_key_from_callback}' for user report."); await query.edit_message_text("خطا: دلیل نامعتبر.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END


    if reason_key_from_callback == "other": 
        await query.edit_message_text("لطفاً متن توضیحی برای دلیل 'سایر' ریپورت را وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb_data)); return REPORTER_USER_ASK_CUSTOM_REASON
    else: 
        try: await query.edit_message_text("⏳ آماده سازی برای ریپورت کاربر...")
        except BadRequest as e:
            if "Message is not modified" in str(e): logger.info("Message not modified on reporter_user_reason_selected.")
            else: raise e
        return await reporter_user_execute_logic(update, context) 
async def reporter_user_custom_reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    custom_reason_text = update.message.text.strip(); tool_prefix = context.user_data['tool_prefix']; context.user_data[f'{tool_prefix}_custom_report_message'] = custom_reason_text
    await update.message.reply_text("⏳ آماده سازی برای ریپورت کاربر با دلیل سفارشی...")
    return await reporter_user_execute_logic(update, context) 
async def reporter_user_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    tool_prefix = context.user_data.get('tool_prefix'); target_user_to_report = context.user_data.get(f'{tool_prefix}_target_input'); reason_key = context.user_data.get(f'{tool_prefix}_report_reason_key'); custom_message = context.user_data.get(f'{tool_prefix}_custom_report_message', '')
    reason_info = config.REPORT_REASONS_USER_DATA.get(reason_key) 
    if not reason_info: logger.error(f"ReporterUser: Invalid reason_key '{reason_key}'"); await context.bot.send_message(update.effective_chat.id, "خطای داخلی: دلیل ریپورت نامعتبر.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    report_reason_obj = reason_info["obj"]; accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await context.bot.send_message(update.effective_chat.id, "هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            # پیام باید توسط message_sender ارسال شود
            err_msg = "خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد."
            if update.callback_query and update.callback_query.message: await update.callback_query.edit_message_text(err_msg, reply_markup=build_tools_menu())
            elif update.message: await update.message.reply_text(err_msg, reply_markup=build_tools_menu())
            else: await context.bot.send_message(chat_id=update.effective_chat.id, text=err_msg, reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        err_msg = "خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی)."
        if update.callback_query and update.callback_query.message: await update.callback_query.edit_message_text(err_msg, reply_markup=build_tools_menu())
        elif update.message: await update.message.reply_text(err_msg, reply_markup=build_tools_menu())
        else: await context.bot.send_message(chat_id=update.effective_chat.id, text=err_msg, reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        err_msg = f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد)."
        if update.callback_query and update.callback_query.message: await update.callback_query.edit_message_text(err_msg, reply_markup=build_tools_menu())
        elif update.message: await update.message.reply_text(err_msg, reply_markup=build_tools_menu())
        else: await context.bot.send_message(chat_id=update.effective_chat.id, text=err_msg, reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    display_reason_text = reason_info["display"]
    message_sender = None 
   
    success_count = 0; failure_count = 0; results_summary = []
    for acc in accounts_to_use:
        phone = acc['phone_number']; session_file = acc['session_file']
        client = TelegramClient(session_file, api_id_int_for_tool, api_hash_to_use)
        try:
            
            logger.info(f"ReporterUser: Processing {phone} to report {target_user_to_report}"); await client.connect()
            if not await client.is_user_authorized(): results_summary.append((phone, "❌", "نیاز به احراز هویت مجدد")); failure_count += 1; await client.disconnect(); continue
            try: target_entity = await client.get_entity(target_user_to_report)
            except (ValueError, UserIdInvalidError, PeerIdInvalidError) as e_entity: results_summary.append((phone, "❌", f"کاربر '{target_user_to_report}' یافت نشد.")); failure_count += 1; await client.disconnect(); continue
            if not isinstance(target_entity, types.User): 
                results_summary.append((phone, "❌", f"هدف '{target_user_to_report}' کاربر نیست.")); failure_count += 1; await client.disconnect(); continue
            current_custom_message = custom_message if reason_key == "other" else '' 
            await client(functions.account.ReportPeerRequest(peer=target_entity, reason=report_reason_obj, message=current_custom_message))
            results_summary.append((phone, "✅", f"ریپورت شد ({display_reason_text}).")); success_count += 1
        except ConnectionError as e: logger.error(f"ReporterUser: Connection error for {phone} reporting {target_user_to_report}: {e}"); results_summary.append((phone, "❌", f"خطای اتصال: {type(e).__name__}")); failure_count += 1
        except Exception as e: logger.error(f"ReporterUser: Unknown error for {phone} reporting {target_user_to_report}: {type(e).__name__} - {e}"); results_summary.append((phone, "❌", f"خطای ناشناخته: {type(e).__name__}")); failure_count += 1
        finally:
            if client.is_connected(): await client.disconnect()
    report_msg_text = f"🏁 **گزارش ریپورت کاربر '{target_user_to_report}':**\nانتخابی: {len(accounts_to_use)}, موفق: {success_count}✅, ناموفق: {failure_count}❌\n\nجزئیات:\n"; [report_msg_text := report_msg_text + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary];
    if len(report_msg_text) > 4096: report_msg_text = report_msg_text[:4000] + "\n\n..."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=report_msg_text, reply_markup=build_tools_menu(), parse_mode=ParseMode.HTML)
    context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_reporter_chat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "ریپورت کردن کانال/گروه", "reporter_chat", "reporter_chat_cancel_to_tools_menu", REPORTER_CHAT_TOOL_CONV)

async def reporter_chat_reason_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    reason_key_from_callback = query.data.replace(config.REPORT_REASON_CALLBACK_PREFIX_CHAT, "")
    
    # اطمینان از وجود tool_prefix در user_data
    tool_prefix = context.user_data.get('tool_prefix')
    if not tool_prefix:
        logger.error("reporter_chat_reason_selected: tool_prefix not found in user_data.")
        await query.edit_message_text("خطای داخلی: اطلاعات ابزار یافت نشد. لطفاً دوباره از منوی ابزارها شروع کنید.",
                                      reply_markup=build_tools_menu())
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data[f'{tool_prefix}_report_reason_key'] = reason_key_from_callback
    selected_reason_info = config.REPORT_REASONS_CHAT_DATA.get(reason_key_from_callback)
    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"

    if not selected_reason_info:
        logger.warning(f"Invalid reason key '{reason_key_from_callback}' for chat report.")
        await query.edit_message_text("خطا: دلیل ریپورت نامعتبر انتخاب شده است.",
                                      reply_markup=build_tools_menu())
        context.user_data.clear()
        return ConversationHandler.END

#------------------بررسي

    if reason_key_from_callback == "other":
        await query.edit_message_text("لطفاً متن توضیحی برای دلیل 'سایر' ریپورت را وارد کنید:",
                                      reply_markup=build_cancel_button(callback_data=cancel_cb_data))
        return REPORTER_CHAT_ASK_CUSTOM_REASON
    else:
        try:
            await query.edit_message_text("⏳ آماده سازی برای ریپورت کانال/گروه...")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message not modified on reporter_chat_reason_selected.")
            else:
                
                logger.error(f"Error editing message in reporter_chat_reason_selected: {e}")
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text="خطایی در به‌روزرسانی پیام رخ داد، لطفاً دوباره تلاش کنید.",
                                               reply_markup=build_tools_menu())
                context.user_data.clear()
                return ConversationHandler.END
        return await reporter_chat_execute_logic(update, context)
async def reporter_chat_custom_reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    custom_reason_text = update.message.text.strip(); tool_prefix = context.user_data['tool_prefix']; context.user_data[f'{tool_prefix}_custom_report_message'] = custom_reason_text
    await update.message.reply_text("⏳ آماده سازی برای ریپورت کانال/گروه با دلیل سفارشی...")
    return await reporter_chat_execute_logic(update, context)
async def reporter_chat_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    tool_prefix = context.user_data.get('tool_prefix'); target_chat_to_report = context.user_data.get(f'{tool_prefix}_target_input'); reason_key = context.user_data.get(f'{tool_prefix}_report_reason_key'); custom_message = context.user_data.get(f'{tool_prefix}_custom_report_message', '')
    reason_info = config.REPORT_REASONS_CHAT_DATA.get(reason_key)
    if not reason_info: logger.error(f"ReporterChat: Invalid reason_key '{reason_key}'"); await context.bot.send_message(update.effective_chat.id, "خطای داخلی: دلیل ریپورت نامعتبر.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    report_reason_obj = reason_info["obj"]; accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await context.bot.send_message(update.effective_chat.id, "هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    display_reason_text = reason_info["display"]
    message_sender = None
    if update.callback_query and update.callback_query.message: message_sender = update.callback_query.message.edit_text
    elif update.message: message_sender = update.message.reply_text
    else: message_sender = lambda text, **kwargs: context.bot.send_message(chat_id=update.effective_chat.id, text=text, **kwargs)
    try: await message_sender(f"⏳ در حال تلاش برای ریپورت '{target_chat_to_report}' توسط {len(accounts_to_use)} اکانت با دلیل '{display_reason_text}'...")
    except BadRequest as e:
        if "Message is not modified" in str(e): logger.info("Message not modified on reporter_chat_execute_logic start.")
        else: raise e
    api_id_int = int(config.API_ID); api_hash = config.API_HASH; success_count = 0; failure_count = 0; results_summary = []
    for acc in accounts_to_use:
        phone = acc['phone_number']; session_file = acc['session_file']; client = TelegramClient(session_file, api_id_int, api_hash)
        try:
            logger.info(f"ReporterChat: Processing {phone} to report {target_chat_to_report}"); await client.connect()
            if not await client.is_user_authorized(): results_summary.append((phone, "❌", "نیاز به احراز هویت مجدد")); failure_count += 1; await client.disconnect(); continue
            try: target_entity = await client.get_entity(target_chat_to_report)
            except (ValueError, PeerIdInvalidError) as e_entity: results_summary.append((phone, "❌", f"کانال/گروه '{target_chat_to_report}' یافت نشد.")); failure_count += 1; await client.disconnect(); continue
            if not isinstance(target_entity, (types.Chat, types.Channel)): 
                results_summary.append((phone, "❌", f"هدف '{target_chat_to_report}' چت یا کانال نیست.")); failure_count += 1; await client.disconnect(); continue
            current_custom_message = custom_message if reason_key == "other" else ''
            await client(functions.account.ReportPeerRequest(peer=target_entity, reason=report_reason_obj, message=current_custom_message))
            results_summary.append((phone, "✅", f"ریپورت شد ({display_reason_text}).")); success_count += 1
        except ConnectionError as e: logger.error(f"ReporterChat: Connection error for {phone} reporting {target_chat_to_report}: {e}"); results_summary.append((phone, "❌", f"خطای اتصال: {type(e).__name__}")); failure_count += 1
        except Exception as e: logger.error(f"ReporterChat: Unknown error for {phone} reporting {target_chat_to_report}: {type(e).__name__} - {e}"); results_summary.append((phone, "❌", f"خطای ناشناخته: {type(e).__name__}")); failure_count += 1
        finally:
            if client.is_connected(): await client.disconnect()
    report_msg_text = f"🏁 **گزارش ریپورت کانال/گروه '{target_chat_to_report}':**\nانتخابی: {len(accounts_to_use)}, موفق: {success_count}✅, ناموفق: {failure_count}❌\n\nجزئیات:\n"; [report_msg_text := report_msg_text + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary];
    if len(report_msg_text) > 4096: report_msg_text = report_msg_text[:4000] + "\n\n..."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=report_msg_text, reply_markup=build_tools_menu(), parse_mode=ParseMode.HTML)
    context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_spammer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    return await tool_entry_point(update, context, "ارسال پیام اسپم", "spammer", "spammer_cancel_to_tools_menu", SPAMMER_TOOL_CONV)
async def spammer_count_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    tool_prefix = context.user_data.get('tool_prefix')
    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"
    try:
        count = int(update.message.text.strip());
        if count <= 0: await update.message.reply_text("تعداد پیام باید مثبت باشد.", reply_markup=build_cancel_button(callback_data=cancel_cb_data)); return SPAMMER_ASK_MESSAGE_COUNT
        context.user_data[f'{tool_prefix}_message_count'] = count
        default_msgs_preview = ", ".join(f"'{m}'" for m in config.DEFAULT_SPAM_MESSAGES[:3]) + ("..." if len(config.DEFAULT_SPAM_MESSAGES) > 3 else "")
        await update.message.reply_text(f"📝 متن پیام را وارد کنید یا `default` برای پیام‌های پیش‌فرض ({default_msgs_preview}):", reply_markup=build_cancel_button(callback_data=cancel_cb_data))
        return SPAMMER_ASK_MESSAGE_TEXT
    except ValueError: await update.message.reply_text("لطفاً تعداد را عددی وارد کنید.", reply_markup=build_cancel_button(callback_data=cancel_cb_data)); return SPAMMER_ASK_MESSAGE_COUNT
async def spammer_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    tool_prefix = context.user_data.get('tool_prefix'); context.user_data[f'{tool_prefix}_message_text'] = update.message.text.strip()
    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"
    await update.message.reply_text("⏱️ تأخیر بین پیام‌ها (ثانیه، مثلا 2 یا 0 برای بدون تاخیر):", reply_markup=build_cancel_button(callback_data=cancel_cb_data))
    return SPAMMER_ASK_DELAY
async def spammer_delay_received_and_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    accounts_to_use = get_selected_accounts(context, tool_prefix) # tool_prefix باید از user_data گرفته شود
    if not accounts_to_use: await update.message.reply_text("هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ آماده سازی برای ارسال {message_count} پیام به '{target_user_id}' با تأخیر {delay_seconds} ثانیه توسط {len(accounts_to_use)} اکانت...")
    try:
        temp_client_for_entity = None
        if accounts_to_use: temp_client_for_entity = TelegramClient(accounts_to_use[0]['session_file'], api_id_int, api_hash); await temp_client_for_entity.connect()
        target_entity = None
        if temp_client_for_entity and await temp_client_for_entity.is_user_authorized():
            try: target_entity = await temp_client_for_entity.get_entity(target_user_id)
            except ValueError: 
                if "joinchat/" in target_user_id or "/+" in target_user_id:
                    try: hash_val = target_user_id.split('/')[-1].replace("+", ""); updates = await temp_client_for_entity(functions.messages.ImportChatInviteRequest(hash_val)); target_entity = updates.chats[0] if updates.chats else None
                    except Exception as e_import: logger.error(f"Spammer: Could not import chat invite {target_user_id}: {e_import}")
        if temp_client_for_entity and temp_client_for_entity.is_connected(): await temp_client_for_entity.disconnect()
        if not target_entity: await update.message.reply_text(f"❌ کاربر یا چت هدف '{target_user_id}' یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
        for acc in accounts_to_use:
            phone = acc['phone_number']; session_file = acc['session_file']; client = TelegramClient(session_file, api_id_int, api_hash); acc_sent = 0; acc_failed = 0
            try:
                logger.info(f"Spammer: {phone} preparing to spam {target_user_id}"); await client.connect()
                if not await client.is_user_authorized(): results_summary.append((phone, "❌", f"نیاز به احراز هویت مجدد (0/{message_count})")); acc_failed=message_count; await client.disconnect(); continue 
                current_target_entity = None
                try: current_target_entity = await client.get_entity(target_entity.id if hasattr(target_entity, 'id') else target_entity)
                except ValueError: 
                    if isinstance(target_entity, (types.Channel, types.Chat)) and ("joinchat/" in target_user_id or "/+" in target_user_id):
                        try: hash_val = target_user_id.split('/')[-1].replace("+", ""); updates = await client(functions.messages.ImportChatInviteRequest(hash_val)); current_target_entity = updates.chats[0] if updates.chats else None
                        except Exception as e_join_spam: logger.warning(f"Spammer: Acc {phone} could not join {target_user_id}: {e_join_spam}")
                    if not current_target_entity: results_summary.append((phone, "❌", f"عدم دسترسی به هدف '{target_user_id}' (0/{message_count})")); acc_failed=message_count; await client.disconnect(); continue
                for i in range(message_count):
                    msg_txt = random.choice(config.DEFAULT_SPAM_MESSAGES) if message_text_template.lower() == "default" else message_text_template
                    try: await client.send_message(current_target_entity, msg_txt); acc_sent += 1
                    except FloodWaitError as fwe: logger.warning(f"Spammer: FloodWait {phone}. Wait {fwe.seconds}s."); results_summary.append((phone, "⚠️", f"Flood: {fwe.seconds}s ({acc_sent}/{message_count})")); acc_failed += (message_count - acc_sent); break 
                    except UserPrivacyRestrictedError: logger.warning(f"Spammer: PrivacyRestricted {phone} to {target_user_id}."); results_summary.append((phone, "❌", f"Privacy ({acc_sent}/{message_count})")); acc_failed += (message_count - acc_sent); break 
                    except BotGroupsBlockedError: logger.warning(f"Spammer: BotGroupsBlockedError {phone} to {target_user_id}."); results_summary.append((phone, "❌", f"Bot Blocked ({acc_sent}/{message_count})")); acc_failed += (message_count - acc_sent); break
                    except RightForbiddenError: logger.warning(f"Spammer: RightForbiddenError {phone} to {target_user_id}."); results_summary.append((phone, "❌", f"No Permission ({acc_sent}/{message_count})")); acc_failed += (message_count - acc_sent); break
                    except Exception as e_msg: logger.error(f"Spammer: Error sending from {phone} to {target_user_id}: {type(e_msg).__name__}"); acc_failed +=1 
                    if delay_seconds > 0 and i < message_count -1 : await asyncio.sleep(delay_seconds)
                if acc_sent > 0 or acc_failed > 0 : results_summary.append((phone, f"ارسال: {acc_sent}/{message_count}", f"ناموفق: {acc_failed}"))
            except ConnectionError as e_acc: logger.error(f"Spammer: Conn error acc {phone}: {e_acc}"); results_summary.append((phone, "❌", f"خطای اتصال اکانت (0/{message_count})")); acc_failed = message_count
            except Exception as e_acc: logger.error(f"Spammer: Gen acc error {phone}: {type(e_acc).__name__}"); results_summary.append((phone, "❌", f"خطای کلی اکانت: {type(e_acc).__name__} (0/{message_count})")); acc_failed = message_count
            finally: total_sent_overall += acc_sent; total_failed_overall += acc_failed; 
            if client.is_connected(): await client.disconnect()
    except Exception as e_main: logger.error(f"Spammer: Main error: {e_main}"); await update.message.reply_text(f"خطای پردازش اسپم: {e_main}", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    report = f"🏁 **گزارش اسپم به '{target_user_id}':**\nکل درخواست: {message_count * len(accounts_to_use)}\nموفق: {total_sent_overall} ✅, ناموفق: {total_failed_overall} ❌\n\n"; 
    if results_summary: report += "جزئیات:\n"; [report := report + f"- `{p}`: {s} ({d})\n" for p,s,d in results_summary]
    else: report += "نتیجه‌ای برای نمایش وجود ندارد."
    if len(report) > 4096: report = report[:4000] + "\n\n..."
    await update.message.reply_html(report, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_remover_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await tool_entry_point(update, context, "حذف اعضا از گروه (با اکانت‌ها)", "remover", "remover_cancel_to_tools_menu", REMOVER_TOOL_CONV)
async def remover_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_to_clear = context.user_data.get(f"{context.user_data['tool_prefix']}_target_input"); tool_prefix = context.user_data['tool_prefix']; logger.info(f"RemoverTool: Removing from: {target_chat_to_clear}"); accounts_to_use = get_selected_accounts(context, tool_prefix)
    if not accounts_to_use: await update.message.reply_text("هیچ اکانت فعالی در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    
    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str) # نام متغیر را تغییر دادم تا با api_id_int قبلی تداخل نداشته باشد
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ تلاش برای حذف اعضا از '{target_chat_to_clear}' توسط {len(accounts_to_use)} اکانت...");

    try:
        if not accounts_to_use: raise ValueError("No accounts selected.")
        first_performer_session = accounts_to_use[0]['session_file']; temp_client = TelegramClient(first_performer_session, api_id_int, api_hash); chat_entity = None; initial_admins_ids = set()
        try:
            await temp_client.connect()
            if not await temp_client.is_user_authorized(): raise ConnectionError(f"First performer ({accounts_to_use[0]['phone_number']}) not authorized.")
            chat_entity = await temp_client.get_entity(target_chat_to_clear)
            if not (isinstance(chat_entity, types.Chat) or (isinstance(chat_entity, types.Channel) and chat_entity.megagroup)): await update.message.reply_text(f"❌ هدف '{target_chat_to_clear}' گروه معتبر نیست.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
            async for admin_user in temp_client.iter_participants(chat_entity, filter=ChannelParticipantsAdmins): initial_admins_ids.add(admin_user.id)
        finally:
            if temp_client.is_connected(): await temp_client.disconnect()
        if not chat_entity: raise ValueError(f"Target chat '{target_chat_to_clear}' not resolved.")
        logger.info(f"RemoverTool: Admins in '{target_chat_to_clear}': {initial_admins_ids}")
        all_participants_to_check = []; client_for_listing = TelegramClient(accounts_to_use[0]['session_file'], api_id_int, api_hash)
        try:
            await client_for_listing.connect()
            if await client_for_listing.is_user_authorized():
                current_chat_entity_for_listing = await client_for_listing.get_entity(chat_entity)
                async for user in client_for_listing.iter_participants(current_chat_entity_for_listing, filter=ChannelParticipantsSearch('')): 
                    if user.id not in initial_admins_ids and not user.is_self and not user.bot: all_participants_to_check.append(user)
            else: raise ConnectionError(f"Acc ({accounts_to_use[0]['phone_number']}) for listing not authorized.")
        finally:
            if client_for_listing.is_connected(): await client_for_listing.disconnect()
        all_participants_to_check_len = len(all_participants_to_check)
        logger.info(f"RemoverTool: Found {all_participants_to_check_len} members to remove from '{target_chat_to_clear}'.")
        if not all_participants_to_check: await update.message.reply_text(f"هیچ عضو غیر ادمینی برای حذف در '{target_chat_to_clear}' یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
        participants_per_performer = [all_participants_to_check[i::len(accounts_to_use)] for i in range(len(accounts_to_use))]
        for idx, acc_dict in enumerate(accounts_to_use):
            phone = acc_dict['phone_number']; session_file = acc_dict['session_file']; client_remover = TelegramClient(session_file, api_id_int, api_hash); participants_for_this_account = participants_per_performer[idx]
            if not participants_for_this_account: continue
            try:
                logger.info(f"RemoverTool: Acc {phone} removing {len(participants_for_this_account)} members..."); await client_remover.connect()
                if not await client_remover.is_user_authorized(): errors_summary.append((phone, "اکانت احراز هویت نشده.")); overall_failed_to_remove_count += len(participants_for_this_account); continue
                current_entity_remover = await client_remover.get_entity(chat_entity); promoter_perms = await client_remover.get_permissions(current_entity_remover, 'me'); can_ban = promoter_perms.ban_users if promoter_perms else False 
                if not can_ban : errors_summary.append((phone, "دسترسی حذف اعضا ندارد.")); overall_failed_to_remove_count += len(participants_for_this_account); continue
                for user_to_remove in participants_for_this_account:
                    try:
                        logger.info(f"RemoverTool: {phone} kicking User ID {user_to_remove.id} from {target_chat_to_clear}"); user_input_entity = await client_remover.get_input_entity(user_to_remove)
                        await client_remover(functions.channels.EditBannedRequest(channel=current_entity_remover, participant=user_input_entity, banned_rights=types.ChatBannedRights(until_date=None, view_messages=True)))
                        overall_removed_count += 1; await asyncio.sleep(random.uniform(0.8, 2.0)) 
                    except FloodWaitError as fwe: logger.warning(f"RemoverTool: FloodWait {phone}. Wait {fwe.seconds}s."); await asyncio.sleep(fwe.seconds + 1); overall_failed_to_remove_count +=1; errors_summary.append((phone, f"Flood: {fwe.seconds}s")) ; break 
                    except (ChatAdminRequiredError, UserAdminInvalidError, RightForbiddenError, UserIdInvalidError, PeerIdInvalidError) as e_kick: logger.warning(f"RemoverTool: Error kicking {user_to_remove.id} by {phone}: {type(e_kick).__name__}"); overall_failed_to_remove_count +=1; errors_summary.append((phone, f"خطا حذف {user_to_remove.username or user_to_remove.id}: {type(e_kick).__name__}"))
                    except Exception as e_kick_unknown: logger.error(f"RemoverTool: Unknown error kicking {user_to_remove.id} by {phone}: {e_kick_unknown}"); overall_failed_to_remove_count +=1; errors_summary.append((phone, f"خطای ناشناخته حذف {user_to_remove.username or user_to_remove.id}: {type(e_kick_unknown).__name__}"))
            except ConnectionError as e_acc: logger.error(f"RemoverTool: Conn error acc {phone}: {e_acc}"); errors_summary.append((phone, f"خطای اتصال اکانت")); overall_failed_to_remove_count += len(participants_for_this_account)
            except Exception as e_acc: logger.error(f"RemoverTool: Acc {phone} general error: {e_acc}"); errors_summary.append((phone, f"خطای کلی اکانت: {type(e_acc).__name__}")); overall_failed_to_remove_count += len(participants_for_this_account)
            finally:
                if client_remover.is_connected(): await client_remover.disconnect()
    except Exception as e_main_remover: logger.error(f"RemoverTool: Main error: {e_main_remover}"); await update.message.reply_text(f"خطای پردازش حذف اعضا: {e_main_remover}", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    report_message = f"🏁 **گزارش حذف اعضا از '{target_chat_to_clear}':**\nکل اعضای (غیر ادمین) یافت شده: {all_participants_to_check_len}\nکل حذف شده: {overall_removed_count} ✅\nکل تلاش ناموفق: {overall_failed_to_remove_count} ❌\n\n"; 
    if errors_summary: report_message += "جزئیات خطاها:\n"; [report_message := report_message + f"- اکانت `{ph}`: {err}\n" for ph, err in errors_summary]
    if len(report_message) > 4096: report_message = report_message[:4000] + "\n\n..."
    await update.message.reply_html(report_message, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

@admin_only
async def tools_add_admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await tool_entry_point(update, context, "ارتقا به ادمین در گروه", "add_admin", "add_admin_cancel_to_tools_menu", ADD_ADMIN_TOOL_CONV)
async def add_admin_users_to_promote_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    users_to_promote_str = update.message.text.strip(); user_identifiers = [u.strip() for u in users_to_promote_str.replace(',', '\n').split('\n') if u.strip()]
    tool_prefix = context.user_data.get('tool_prefix')
    cancel_cb_data = f"{tool_prefix}_cancel_to_tools_menu"
    if not user_identifiers: await update.message.reply_text("لیست کاربران خالی است.", reply_markup=build_cancel_button(callback_data=cancel_cb_data)); return ADD_ADMIN_ASK_USERS_TO_PROMOTE
    context.user_data[f'{tool_prefix}_users_to_promote_list'] = user_identifiers
    return await add_admin_execute_logic(update, context)
async def add_admin_execute_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tool_prefix = context.user_data.get('tool_prefix'); target_group_link_or_id = context.user_data.get(f'{tool_prefix}_target_input'); users_to_promote_ids = context.user_data.get(f'{tool_prefix}_users_to_promote_list', []); logger.info(f"AddAdminTool: Promoting {users_to_promote_ids} in {target_group_link_or_id}"); performing_accounts = get_selected_accounts(context, tool_prefix)
    if not performing_accounts: await update.message.reply_text("هیچ اکانت مجری در دسته‌بندی انتخاب شده یافت نشد.", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    
    # ---------- شروع بخش اصلاح شده برای انتخاب API Key ----------
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None

    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
            logger.warning(f"Tool {tool_prefix}: No API keys in bot_data list, using directly from config.py.")
        else:
            await update.message.reply_text("خطا: هیچ API ID/Hash معتبری در تنظیمات ربات یا فایل کانفیگ یافت نشد.", reply_markup=build_tools_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)
        logger.info(f"Tool {tool_prefix}: Using API pair ID: {selected_api_pair.get('api_id')}")

    api_id_to_use_str = selected_api_pair.get('api_id')
    api_hash_to_use = selected_api_pair.get('api_hash')

    if not api_id_to_use_str or not api_hash_to_use:
        await update.message.reply_text("خطا: API ID/Hash انتخاب شده نامعتبر است (مقادیر خالی).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    try:
        api_id_int_for_tool = int(api_id_to_use_str)
    except (ValueError, TypeError):
        await update.message.reply_text(f"خطا: API ID '{api_id_to_use_str}' انتخاب شده برای ابزار نامعتبر است (باید عدد باشد).", reply_markup=build_tools_menu())
        context.user_data.clear(); return ConversationHandler.END
    # ---------- پایان بخش اصلاح شده ----------

    await update.message.reply_text(f"⏳ تلاش برای ارتقا کاربران در '{target_group_link_or_id}' توسط {len(performing_accounts)} اکانت...");

    try: 
        temp_client_check = TelegramClient(performing_accounts[0]['session_file'], api_id_int, api_hash); await temp_client_check.connect()
        if not await temp_client_check.is_user_authorized(): raise ConnectionError(f"Acc اول ({performing_accounts[0]['phone_number']}) احراز نشده.")
        target_group_entity_ref = await temp_client_check.get_entity(target_group_link_or_id); await temp_client_check.disconnect()
        if not (isinstance(target_group_entity_ref, types.Chat) or (isinstance(target_group_entity_ref, types.Channel) and target_group_entity_ref.megagroup)): raise ValueError(f"هدف '{target_group_link_or_id}' گروه معتبر نیست. نوع: {type(target_group_entity_ref)}")
    except Exception as e_group: logger.error(f"AddAdminTool: Error group entity '{target_group_link_or_id}': {e_group}"); await update.message.reply_text(f"❌ خطا یافتن گروه '{target_group_link_or_id}': {e_group}", reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END
    full_admin_rights = types.ChatAdminRights(change_info=True, post_messages=True, edit_messages=True, delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, add_admins=True, anonymous=False, manage_call=True, other=True)
    for acc_performer in performing_accounts:
        performer_phone = acc_performer['phone_number']; session_file = acc_performer['session_file']; client_promoter = TelegramClient(session_file, api_id_int, api_hash)
        try:
            logger.info(f"AddAdmin: Performer {performer_phone} connecting..."); await client_promoter.connect()
            if not await client_promoter.is_user_authorized(): results_summary.append((performer_phone, "همه کاربران", "❌", "اکانت مجری احراز نشده.")); continue
            current_group_entity_promoter = await client_promoter.get_entity(target_group_entity_ref); promoter_perms = await client_promoter.get_permissions(current_group_entity_promoter, 'me')
            if not promoter_perms or not promoter_perms.add_admins: results_summary.append((performer_phone, "همه کاربران", "❌", "اکانت مجری دسترسی افزودن ادمین ندارد.")); continue
            for user_id_or_username in users_to_promote_ids:
                try:
                    user_to_promote_entity = await client_promoter.get_entity(user_id_or_username)
                    if not isinstance(user_to_promote_entity, types.User): results_summary.append((performer_phone, user_id_or_username, "❌", "هدف کاربر نیست.")); continue
                    logger.info(f"AddAdmin: {performer_phone} promoting {user_id_or_username} (ID: {user_to_promote_entity.id}) in {target_group_link_or_id}")
                    await client_promoter(functions.channels.EditAdminRequest(channel=current_group_entity_promoter, user_id=user_to_promote_entity, admin_rights=full_admin_rights, rank='Admin (توسط ربات)'))
                    results_summary.append((performer_phone, user_id_or_username, "✅", "ادمین شد."))
                except UserNotParticipantError: results_summary.append((performer_phone, user_id_or_username, "❌", "کاربر عضو گروه نیست."))
                except (UserAdminInvalidError, ChatAdminRequiredError, RightForbiddenError, ChatNotModifiedError) as e_promote: results_summary.append((performer_phone, user_id_or_username, "❌", f"خطا ارتقا: {type(e_promote).__name__}"))
                except (ValueError, UserIdInvalidError, PeerIdInvalidError) : results_summary.append((performer_phone, user_id_or_username, "❌", f"کاربر هدف '{user_id_or_username}' یافت نشد."))
                except Exception as e_unk: results_summary.append((performer_phone, user_id_or_username, "❌", f"خطای ناشناخته ارتقا: {type(e_unk).__name__} - {e_unk}"))
                await asyncio.sleep(random.uniform(0.8, 1.5))
        except ConnectionError as e_acc_promoter: results_summary.append((performer_phone, "همه کاربران", "❌", f"خطای اتصال اکانت مجری: {type(e_acc_promoter).__name__}"))
        except Exception as e_acc_promoter: results_summary.append((performer_phone, "همه کاربران", "❌", f"خطای کلی اکانت مجری: {type(e_acc_promoter).__name__} - {e_acc_promoter}"))
        finally:
            if client_promoter.is_connected(): await client_promoter.disconnect()
    report = f"🏁 **گزارش ارتقا به ادمین در گروه '{target_group_link_or_id}':**\n\n"; 
    if not results_summary: report += "نتیجه‌ای برای نمایش نیست."
    else: [report := report + f"- توسط `{p_phone}` برای `{target}`: {status} ({detail})\n" for p_phone,target,status,detail in results_summary]
    if len(report) > 4096: report = report[:4000] + "\n\n..."
    await update.message.reply_html(report, reply_markup=build_tools_menu()); context.user_data.clear(); return ConversationHandler.END

# --- توابع برای عملیات با ربات ---

# اسپم گروه با ربات
@admin_only
async def bot_op_spam_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['_active_conversation_name'] = BOT_OP_SPAM_GROUP_CONV
    context.user_data['bot_op_conv_prefix'] = "bot_op_spam_group" 
    cancel_cb = "bot_op_spam_group_cancel_to_bot_operations_menu"
    await query.edit_message_text(text="لطفاً شناسه عددی گروه یا لینک عمومی/خصوصی گروهی که می‌خواهید در آن پیام اسپم ارسال شود را وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_GROUP_ASK_TARGET

async def bot_op_spam_group_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_group_id_str = update.message.text.strip()
    context.user_data['target_group_id'] = target_group_id_str
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    if not target_group_id_str: await update.message.reply_text("شناسه گروه نمی‌تواند خالی باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_GROUP_ASK_TARGET
    await update.message.reply_text("💬 تعداد پیام‌هایی که می‌خواهید توسط ربات ارسال شوند را وارد کنید (مثلاً 5):", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_GROUP_ASK_COUNT

async def bot_op_spam_group_count_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    try:
        count = int(update.message.text.strip())
        if count <= 0: await update.message.reply_text("تعداد پیام باید عدد مثبت باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_GROUP_ASK_COUNT
        context.user_data['message_count'] = count
        default_msgs_preview = ", ".join(f"'{m}'" for m in config.DEFAULT_SPAM_MESSAGES[:3]) + ("..." if len(config.DEFAULT_SPAM_MESSAGES) > 3 else "")
        await update.message.reply_text(f"📝 متن پیام را وارد کنید یا `default` برای پیام‌های پیش‌فرض ({default_msgs_preview}):", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_SPAM_GROUP_ASK_TEXT
    except ValueError: await update.message.reply_text("ورودی نامعتبر. تعداد پیام را عددی وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_GROUP_ASK_COUNT

async def bot_op_spam_group_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['message_text_template'] = update.message.text.strip()
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    await update.message.reply_text("⏱️ تأخیر بین ارسال پیام‌ها (ثانیه، مثلا 2 یا 0 برای بدون تاخیر):", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_GROUP_ASK_DELAY

async def bot_op_spam_group_delay_received_and_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    try:
        delay_seconds = float(update.message.text.strip())
        if delay_seconds < 0: await update.message.reply_text("تأخیر منفی مجاز نیست. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_GROUP_ASK_DELAY
        context.user_data['delay_seconds'] = delay_seconds
    except ValueError: await update.message.reply_text("ورودی نامعتبر. تأخیر را عددی وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_GROUP_ASK_DELAY
    target_group_id_str = context.user_data['target_group_id']; message_count = context.user_data['message_count']; message_text_template = context.user_data['message_text_template']
    try: chat_id_to_send = int(target_group_id_str)
    except ValueError: chat_id_to_send = target_group_id_str
    await update.message.reply_text(f"⏳ ربات در حال آماده‌سازی برای ارسال {message_count} پیام به گروه '{target_group_id_str}' با تأخیر {delay_seconds} ثانیه..."); sent_count = 0; failed_count = 0
    try:
        await context.bot.send_chat_action(chat_id=chat_id_to_send, action=ChatAction.TYPING)
        chat_info = await context.bot.get_chat(chat_id=chat_id_to_send); chat_id_numeric = chat_info.id
        logger.info(f"Bot can access group '{chat_info.title if chat_info.title else chat_id_to_send}' (ID: {chat_id_numeric}) for bot spamming.")
    except BadRequest as e: logger.error(f"Bot Spam Group: BadRequest accessing group {target_group_id_str}: {e}"); await update.message.reply_text(f"❌ ربات نتوانست به گروه '{target_group_id_str}' دسترسی پیدا کند. خطا: {e.message}", reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END
    except TelegramError as e: logger.error(f"Bot Spam Group: TelegramError accessing group {target_group_id_str}: {e}"); await update.message.reply_text(f"❌ خطای تلگرامی هنگام دسترسی به گروه '{target_group_id_str}': {e.message}", reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END
    for i in range(message_count):
        current_message_text = random.choice(config.DEFAULT_SPAM_MESSAGES) if message_text_template.lower() == "default" and config.DEFAULT_SPAM_MESSAGES else message_text_template
        if message_text_template.lower() == "default" and not config.DEFAULT_SPAM_MESSAGES: current_message_text = "پیام پیش‌فرض اسپم تنظیم نشده."
        try:
            await context.bot.send_message(chat_id=chat_id_numeric, text=current_message_text); sent_count += 1
            logger.info(f"Bot sent message {i+1}/{message_count} to group {chat_id_numeric}")
        except ChatWriteForbiddenError as e: logger.error(f"Bot Spam Group: ChatWriteForbiddenError for group {chat_id_numeric}: {e}"); await update.message.reply_text(f"❌ ربات اجازه ارسال پیام در گروه '{target_group_id_str}' را ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu()); failed_count = message_count - sent_count; break 
        except TelegramError as e: logger.error(f"Bot Spam Group: TelegramError sending to {chat_id_numeric}: {e}"); failed_count += 1
        if i < message_count - 1 and delay_seconds > 0: await asyncio.sleep(delay_seconds)
    report_message = f"🏁 **گزارش اسپم به گروه '{target_group_id_str}' (توسط ربات):**\n\nدرخواست: {message_count}\nموفق: {sent_count} ✅\nناموفق: {failed_count} ❌"
    await update.message.reply_html(report_message, reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END

# اسپم کانال با ربات
@admin_only
async def bot_op_spam_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['_active_conversation_name'] = BOT_OP_SPAM_CHANNEL_CONV
    context.user_data['bot_op_conv_prefix'] = "bot_op_spam_channel"
    cancel_cb = "bot_op_spam_channel_cancel_to_bot_operations_menu"
    await query.edit_message_text(text="لطفاً شناسه عددی کانال یا نام کاربری کانال (با @) که می‌خواهید در آن پیام اسپم ارسال شود را وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_CHANNEL_ASK_TARGET

async def bot_op_spam_channel_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_channel_id_str = update.message.text.strip()
    context.user_data['target_channel_id'] = target_channel_id_str
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    if not target_channel_id_str: await update.message.reply_text("شناسه کانال نمی‌تواند خالی باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_CHANNEL_ASK_TARGET
    await update.message.reply_text("📢 تعداد پیام‌هایی که می‌خواهید توسط ربات به کانال ارسال شوند را وارد کنید (مثلاً 5):", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_CHANNEL_ASK_COUNT

async def bot_op_spam_channel_count_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    try:
        count = int(update.message.text.strip())
        if count <= 0: await update.message.reply_text("تعداد پیام باید عدد مثبت باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_CHANNEL_ASK_COUNT
        context.user_data['message_count'] = count
        default_msgs_preview = ", ".join(f"'{m}'" for m in config.DEFAULT_SPAM_MESSAGES[:3]) + ("..." if len(config.DEFAULT_SPAM_MESSAGES) > 3 else "")
        await update.message.reply_text(f"📝 متن پیام را وارد کنید یا `default` برای پیام‌های پیش‌فرض ({default_msgs_preview}):", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_SPAM_CHANNEL_ASK_TEXT
    except ValueError: await update.message.reply_text("ورودی نامعتبر. تعداد پیام را عددی وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_CHANNEL_ASK_COUNT

async def bot_op_spam_channel_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['message_text_template'] = update.message.text.strip()
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    await update.message.reply_text("⏱️ تأخیر بین ارسال پیام‌ها (ثانیه، مثلا 2 یا 0 برای بدون تاخیر):", reply_markup=build_cancel_button(callback_data=cancel_cb))
    return BOT_OP_SPAM_CHANNEL_ASK_DELAY

async def bot_op_spam_channel_delay_received_and_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cancel_cb = f"{context.user_data['bot_op_conv_prefix']}_cancel_to_bot_operations_menu"
    try:
        delay_seconds = float(update.message.text.strip())
        if delay_seconds < 0: await update.message.reply_text("تأخیر منفی مجاز نیست. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_CHANNEL_ASK_DELAY
        context.user_data['delay_seconds'] = delay_seconds
    except ValueError: await update.message.reply_text("ورودی نامعتبر. تأخیر را عددی وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb)); return BOT_OP_SPAM_CHANNEL_ASK_DELAY
    target_channel_id_str = context.user_data['target_channel_id']; message_count = context.user_data['message_count']; message_text_template = context.user_data['message_text_template']
    try: chat_id_to_send = int(target_channel_id_str)
    except ValueError: chat_id_to_send = target_channel_id_str
    await update.message.reply_text(f"⏳ ربات در حال آماده‌سازی برای ارسال {message_count} پیام به کانال '{target_channel_id_str}' با تأخیر {delay_seconds} ثانیه..."); sent_count = 0; failed_count = 0
    try:
        chat_info = await context.bot.get_chat(chat_id=chat_id_to_send)
        if chat_info.type != "channel": await update.message.reply_text(f"❌ هدف '{target_channel_id_str}' یک کانال نیست.", reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END
        logger.info(f"Bot attempting to spam channel '{chat_info.title if chat_info.title else chat_id_to_send}' (ID: {chat_info.id})."); chat_id_numeric = chat_info.id
    except BadRequest as e: logger.error(f"Bot Spam Channel: BadRequest accessing channel {target_channel_id_str}: {e}"); await update.message.reply_text(f"❌ ربات نتوانست به کانال '{target_channel_id_str}' دسترسی پیدا کند. خطا: {e.message}", reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END
    except TelegramError as e: logger.error(f"Bot Spam Channel: TelegramError accessing channel {target_channel_id_str}: {e}"); await update.message.reply_text(f"❌ خطای تلگرامی هنگام دسترسی به کانال '{target_channel_id_str}': {e.message}", reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END
    for i in range(message_count):
        current_message_text = random.choice(config.DEFAULT_SPAM_MESSAGES) if message_text_template.lower() == "default" and config.DEFAULT_SPAM_MESSAGES else message_text_template
        if message_text_template.lower() == "default" and not config.DEFAULT_SPAM_MESSAGES: current_message_text = "پیام پیش‌فرض اسپم تنظیم نشده."
        try:
            await context.bot.send_message(chat_id=chat_id_numeric, text=current_message_text); sent_count += 1
            logger.info(f"Bot sent message {i+1}/{message_count} to channel {chat_id_numeric}")
        except ChatWriteForbiddenError as e: logger.error(f"Bot Spam Channel: ChatWriteForbiddenError for channel {chat_id_numeric}: {e}"); await update.message.reply_text(f"❌ ربات اجازه ارسال پیام در کانال '{target_channel_id_str}' را ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu()); failed_count = message_count - sent_count; break 
        except TelegramError as e: logger.error(f"Bot Spam Channel: TelegramError sending to {chat_id_numeric}: {e}"); failed_count += 1
        if i < message_count - 1 and delay_seconds > 0: await asyncio.sleep(delay_seconds)
    report_message = f"🏁 **گزارش اسپم به کانال '{target_channel_id_str}' (توسط ربات):**\n\nدرخواست: {message_count}\nموفق: {sent_count} ✅\nناموفق: {failed_count} ❌"
    await update.message.reply_html(report_message, reply_markup=build_bot_operations_menu()); context.user_data.clear(); return ConversationHandler.END

# --- توابع برای عملیات حذف پیشرفته اعضای گروه با ربات ---
@admin_only
async def bot_op_adv_remove_group_members_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['_active_conversation_name'] = BOT_OP_ADV_REMOVE_GROUP_MEMBERS_CONV
    context.user_data['bot_op_conv_prefix'] = "bot_op_adv_remove_group_members"
    cancel_cb = "bot_op_adv_remove_group_members_cancel_to_bot_operations_menu"
    await query.edit_message_text(
        text="🗑️ **حذف پیشرفته اعضای گروه (با ربات)**\n\n"
             "۱. لطفاً شناسه عددی گروه یا لینک گروهی که می‌خواهید اعضای آن حذف شوند را وارد کنید:",
        reply_markup=build_cancel_button(callback_data=cancel_cb),
        parse_mode=ParseMode.HTML
    )
    return BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_TARGET

async def bot_op_adv_remove_group_members_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_group_id_str = update.message.text.strip()
    context.user_data['target_group_id_str'] = target_group_id_str
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"

    if not target_group_id_str:
        await update.message.reply_text("شناسه گروه نمی‌تواند خالی باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_TARGET

    try:
        chat_id_for_info = int(target_group_id_str) if target_group_id_str.lstrip('-').isdigit() else target_group_id_str
        chat_info = await context.bot.get_chat(chat_id=chat_id_for_info)
        if chat_info.type == 'channel' and not getattr(chat_info, 'is_supergroup', False) and not getattr(chat_info, 'megagroup', False) : 
             await update.message.reply_text(f"❌ عملیات حذف اعضا فقط برای گروه‌ها و سوپرگروه‌ها امکان‌پذیر است. '{target_group_id_str}' یک کانال است.", reply_markup=build_bot_operations_menu())
             context.user_data.clear(); return ConversationHandler.END
        context.user_data['target_chat_id_numeric'] = chat_info.id
        context.user_data['target_chat_title'] = chat_info.title or target_group_id_str
    except Exception as e:
        logger.error(f"Bot Adv Remove Group: Could not resolve or validate group ID {target_group_id_str}: {e}")
        await update.message.reply_text(f"❌ خطای دسترسی به گروه یا نامعتبر بودن شناسه '{target_group_id_str}'. ربات باید عضو گروه باشد.\nخطا: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    active_accounts = [acc for acc in get_all_accounts() if acc.get('is_active', 1)]
    if not active_accounts:
        await update.message.reply_text("هیچ اکانت فعالی (ایرانی یا خارجی) برای کمک به دریافت لیست اعضا یافت نشد. لطفاً ابتدا یک اکانت اضافه کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END # بازگشت به منوی عملیات ربات

    await update.message.reply_text(
        text="۲. لطفاً یک اکانت فعال از لیست زیر انتخاب کنید تا برای دریافت لیست اعضای گروه کمک کند (این اکانت باید عضو گروه هدف باشد):",
        reply_markup=build_select_helper_account_menu(
            accounts=active_accounts,
            callback_prefix=f"{prefix}_select_helper",
            cancel_callback=cancel_cb
        )
    )
    return BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_HELPER_ACCOUNT

async def bot_op_adv_remove_group_members_helper_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    prefix = context.user_data.get('bot_op_conv_prefix') # باید از get استفاده شود و وجودش بررسی شود
    if not prefix:
        logger.error("bot_op_adv_remove_group_members_helper_selected: bot_op_conv_prefix not in user_data.")
        await query.edit_message_text("خطای داخلی، لطفاً دوباره شروع کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    confirm_cb = f"{prefix}_confirm_final_removal"


    # (اطمینان حاصل کنید که helper_account_phone و helper_account_session به user_data اضافه می‌شوند)
    helper_account_db_id_str = query.data.replace(f"{prefix}_select_helper_", "")
    helper_account_phone_for_log = "Unknown_helper" # مقدار پیش فرض برای لاگ
    try:
        helper_account_db_id = int(helper_account_db_id_str)
        helper_account_details = get_account_details_by_id(helper_account_db_id)
        if not helper_account_details or not helper_account_details.get('is_active'):
            raise ValueError("Helper account not found or not active in DB.")
        context.user_data['helper_account_session'] = helper_account_details['session_file']
        context.user_data['helper_account_phone'] = helper_account_details['phone_number']
        helper_account_phone_for_log = helper_account_details['phone_number'] # برای استفاده در finally
        logger.info(f"Helper account selected for member listing: {helper_account_phone_for_log}")
    except Exception as e:
        logger.error(f"Error selecting helper account: {e}")
        await query.edit_message_text("خطا در انتخاب اکانت کمکی. لطفاً دوباره تلاش کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END


    target_chat_id_numeric = context.user_data.get('target_chat_id_numeric')
    target_chat_title = context.user_data.get('target_chat_title')
    helper_session = context.user_data.get('helper_account_session')

    if not all([target_chat_id_numeric, target_chat_title, helper_session]):
        logger.error("Missing critical data for remove_group_members_helper_selected.")
        await query.edit_message_text("خطای داخلی (اطلاعات ناقص). لطفاً از ابتدا شروع کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    
    await query.edit_message_text("⏳ در حال دریافت لیست اعضای گروه با استفاده از اکانت کمکی... این ممکن است زمان‌بر باشد.", reply_markup=None)

    members_to_remove_ids = []
    admin_ids_in_group = set()
    
    # ... (کد دریافت admin_ids_in_group مشابه قبل) ...
    try:
        chat_admins = await context.bot.get_chat_administrators(chat_id=target_chat_id_numeric)
        admin_ids_in_group = {admin.user.id for admin in chat_admins}
        admin_ids_in_group.add(context.bot.id) 
    except Exception as e:
        logger.error(f"Could not get admin list for group {target_chat_id_numeric} by main bot: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در دریافت لیست ادمین‌های گروه '{target_chat_title}'. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    # --- بخش اصلاح شده برای Telethon ---
    # اطمینان از انتخاب صحیح API ID/Hash برای کلاینت کمکی
    api_keys_list = context.bot_data.get('api_keys_list', [])
    selected_api_pair = None
    if not api_keys_list:
        if config.API_ID and config.API_HASH:
            selected_api_pair = {"api_id": str(config.API_ID), "api_hash": config.API_HASH}
        else: # خطا اگر هیچ API موجود نباشد
            logger.error("No API ID/Hash available for helper client.")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="خطای داخلی: API ID/Hash برای اکانت کمکی یافت نشد.", reply_markup=build_bot_operations_menu())
            context.user_data.clear(); return ConversationHandler.END
    else:
        selected_api_pair = random.choice(api_keys_list)

    api_id_int_for_helper = int(selected_api_pair['api_id'])
    api_hash_for_helper = selected_api_pair['api_hash']
    # --- پایان بخش انتخاب API ---

    helper_client = TelegramClient(helper_session, api_id_int_for_helper, api_hash_for_helper)
    try:
        logger.info(f"Helper client {helper_account_phone_for_log} connecting...") # استفاده از متغیر محلی
        await helper_client.connect()
        if not await helper_client.is_user_authorized():
            raise ConnectionError(f"Helper account {helper_account_phone_for_log} is not authorized.")
        
        # برای get_entity بهتر است از شناسه عددی استفاده شود اگر موجود است
        target_entity = await helper_client.get_entity(target_chat_id_numeric)
        if not target_entity: # بررسی اضافه شده
            raise ValueError(f"Could not resolve entity for {target_chat_id_numeric} with helper client.")

        logger.info(f"Fetching participants from {target_chat_title} (ID: {target_entity.id}) using helper {helper_account_phone_for_log}...")
        count = 0
        async for user in helper_client.iter_participants(target_entity, aggressive=True): # aggressive=True ممکن است در برخی شرایط کمک کند
            if not user.bot and user.id not in admin_ids_in_group:
                members_to_remove_ids.append(user.id)
                count +=1
                if count % 100 == 0: 
                    logger.info(f"Fetched {count} potential members so far...")
        logger.info(f"Found {len(members_to_remove_ids)} members to remove from group {target_chat_title} using helper {helper_account_phone_for_log}.")

    except UserNotParticipantError: # این خطا باید مشخصاً برای زمانی باشد که اکانت کمکی عضو گروه نیست
        logger.error(f"Helper account {helper_account_phone_for_log} is not a participant of group {target_chat_title}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"اکانت کمکی ({helper_account_phone_for_log}) عضو گروه '{target_chat_title}' نیست. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END # خروج از مکالمه
    except ValueError as e: # این خطا می‌تواند شامل "Could not find the input entity" باشد
        logger.error(f"Error getting entity or member list with helper account {helper_account_phone_for_log} for chat ID {target_chat_id_numeric}: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در دسترسی به اطلاعات گروه یا لیست اعضا با اکانت کمکی ({helper_account_phone_for_log}): {str(e)[:200]}. لطفاً عضویت اکانت کمکی در گروه را بررسی کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    except ConnectionError as e:
        logger.error(f"Connection error with helper account {helper_account_phone_for_log}: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در اتصال با اکانت کمکی: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    except Exception as e: # خطاهای دیگر
        logger.error(f"Unexpected error getting member list with helper {helper_account_phone_for_log}: {type(e).__name__} - {e}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطای ناشناخته در دریافت لیست اعضا با اکانت کمکی: {type(e).__name__}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    finally:
        if helper_client.is_connected():
            logger.info(f"Helper client {helper_account_phone_for_log} disconnecting...")
            await helper_client.disconnect()

  
    if not members_to_remove_ids:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"هیچ عضو عادی (غیر ادمین و غیر ربات) در گروه '{target_chat_title}' برای حذف یافت نشد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
        
    context.user_data['members_to_remove_ids'] = members_to_remove_ids

    confirmation_message = (
        f"تعداد {len(members_to_remove_ids)} عضو عادی برای حذف از گروه '{target_chat_title}' شناسایی شد.\n"
        f"ربات اصلی این عملیات را انجام خواهد داد. این کار ممکن است بسیار زمان‌بر باشد و **غیرقابل بازگشت** است.\n\n"
        f"آیا برای شروع عملیات حذف مطمئن هستید؟"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=confirmation_message,
        reply_markup=build_confirm_cancel_buttons(confirm_callback=confirm_cb, cancel_callback=cancel_cb),
        parse_mode=ParseMode.HTML
    )
    return BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_CONFIRM

async def bot_op_adv_remove_group_members_confirmed_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    target_chat_id_numeric = context.user_data['target_chat_id_numeric']
    target_chat_title = context.user_data['target_chat_title']
    members_to_remove_ids = context.user_data.get('members_to_remove_ids', [])

    if not members_to_remove_ids:
        await query.edit_message_text(f"لیست اعضا برای حذف خالی است. عملیات لغو شد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    original_message = await query.edit_message_text(f"⏳ **شروع عملیات حذف اعضا از گروه '{target_chat_title}' توسط ربات...**\n"
                                  f"تعداد کل اعضا برای حذف: {len(members_to_remove_ids)}\n"
                                  f"این فرآیند ممکن است دقایق زیادی طول بکشد. لطفاً صبور باشید.", 
                                  reply_markup=None, parse_mode=ParseMode.HTML)
    
    removed_count = 0
    failed_count = 0
    delay_between_kicks = 1.0 

    try:
        bot_member = await context.bot.get_chat_member(chat_id=target_chat_id_numeric, user_id=context.bot.id)
        if not bot_member.status == "administrator" or not bot_member.can_restrict_members:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ ربات دسترسی لازم (اخراج کاربران) را در گروه '{target_chat_title}' ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
            context.user_data.clear(); return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking bot permissions in group {target_chat_id_numeric}: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ خطا در بررسی دسترسی ربات در گروه '{target_chat_title}'.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    for i, user_id_to_remove in enumerate(members_to_remove_ids):
        try:
            await context.bot.ban_chat_member(chat_id=target_chat_id_numeric, user_id=user_id_to_remove)
            removed_count += 1
            logger.info(f"Bot removed user {user_id_to_remove} from group {target_chat_id_numeric}. ({removed_count}/{len(members_to_remove_ids)})")
            
            if (i + 1) % 25 == 0 or (i + 1) == len(members_to_remove_ids) : 
                try:
                    await original_message.edit_text(
                        text=f"⏳ در حال حذف اعضا از گروه '{target_chat_title}'...\n"
                             f"{removed_count} از {len(members_to_remove_ids)} نفر حذف شده‌اند.\n"
                             f"{failed_count} تلاش ناموفق.",
                        parse_mode=ParseMode.HTML
                    )
                except BadRequest as e_edit:
                    if "Message is not modified" not in str(e_edit): 
                        logger.warning(f"Could not edit progress message: {e_edit}")
                except Exception as e_edit_unknown:
                     logger.warning(f"Unknown error editing progress message: {e_edit_unknown}")
        except BadRequest as e: 
            if "user_id_invalid" in str(e).lower() or "user_not_participant" in str(e).lower() or "member_invalid" in str(e).lower():
                logger.warning(f"Bot: User {user_id_to_remove} not found or not participant in group {target_chat_id_numeric}: {e.message}")
            else:
                logger.warning(f"Bot failed to remove user {user_id_to_remove} from group {target_chat_id_numeric}: {e.message}")
            failed_count += 1
        except TelegramError as e_telegram: 
            logger.error(f"Bot TelegramError removing user {user_id_to_remove} from group {target_chat_id_numeric}: {e_telegram}")
            failed_count += 1
            if "flood_wait_" in str(e_telegram).lower(): 
                try: flood_wait_time = int(str(e_telegram).split("FLOOD_WAIT_")[1].split(" ")[0])
                except: flood_wait_time = 30 
                logger.warning(f"Flood control hit. Waiting for {flood_wait_time} seconds.")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ محدودیت تلگرام (Flood). ربات به مدت {flood_wait_time} ثانیه متوقف می‌شود و سپس ادامه می‌دهد...")
                await asyncio.sleep(flood_wait_time)
                delay_between_kicks = min(delay_between_kicks + 0.5, 5.0) 
        except Exception as e_unknown:
            logger.error(f"Bot unknown error removing user {user_id_to_remove} from group {target_chat_id_numeric}: {e_unknown}")
            failed_count += 1
        
        await asyncio.sleep(delay_between_kicks) 

    report_message = f"🏁 **گزارش نهایی حذف اعضای گروه '{target_chat_title}' (توسط ربات):**\n\n"
    report_message += f"تعداد کل اعضای شناسایی شده برای حذف: {len(members_to_remove_ids)}\n"
    report_message += f"تعداد اعضای با موفقیت حذف شده: {removed_count} ✅\n"
    report_message += f"تعداد تلاش‌های ناموفق برای حذف: {failed_count} ❌"

    # اگر پیام اصلی (original_message) هنوز وجود دارد، آن را با گزارش نهایی ویرایش کن
    # در غیر این صورت (مثلا اگر در حین عملیات خطایی رخ داده و پیام جدیدی ارسال شده)، گزارش را به عنوان پیام جدید بفرست
    try:
        await original_message.edit_text(text=report_message, reply_markup=build_bot_operations_menu(), parse_mode=ParseMode.HTML)
    except Exception: # اگر ویرایش پیام قبلی ممکن نبود
        await context.bot.send_message(chat_id=update.effective_chat.id, text=report_message, reply_markup=build_bot_operations_menu(), parse_mode=ParseMode.HTML)

    context.user_data.clear()
    return ConversationHandler.END


# --- توابع برای عملیات حذف پیشرفته مشترکین کانال با ربات (جدید) ---
@admin_only
async def bot_op_adv_remove_channel_members_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['_active_conversation_name'] = BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_CONV
    context.user_data['bot_op_conv_prefix'] = "bot_op_adv_remove_channel_members"
    cancel_cb = "bot_op_adv_remove_channel_members_cancel_to_bot_operations_menu"

    await query.edit_message_text(
        text="🗑️ **حذف پیشرفته مشترکین کانال (با ربات)**\n\n"
             "۱. لطفاً شناسه عددی کانال یا نام کاربری کانال (با @) که می‌خواهید مشترکین آن حذف (مسدود) شوند را وارد کنید:",
        reply_markup=build_cancel_button(callback_data=cancel_cb),
        parse_mode=ParseMode.HTML
    )
    return BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_TARGET

async def bot_op_adv_remove_channel_members_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_channel_id_str = update.message.text.strip()
    context.user_data['target_channel_id_str'] = target_channel_id_str
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"

    if not target_channel_id_str:
        await update.message.reply_text("شناسه کانال نمی‌تواند خالی باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_TARGET

    try:
        chat_id_for_info = int(target_channel_id_str) if target_channel_id_str.lstrip('-').isdigit() else target_channel_id_str
        chat_info = await context.bot.get_chat(chat_id=chat_id_for_info)
        if chat_info.type != 'channel':
             await update.message.reply_text(f"❌ هدف '{target_channel_id_str}' یک کانال نیست. لطفاً شناسه کانال معتبر وارد کنید.", reply_markup=build_bot_operations_menu())
             context.user_data.clear(); return ConversationHandler.END
        context.user_data['target_chat_id_numeric'] = chat_info.id
        context.user_data['target_chat_title'] = chat_info.title or target_channel_id_str
    except Exception as e:
        logger.error(f"Bot Adv Remove Channel Members: Could not resolve or validate channel ID {target_channel_id_str}: {e}")
        await update.message.reply_text(f"❌ خطای دسترسی به کانال یا نامعتبر بودن شناسه '{target_channel_id_str}'. ربات باید ادمین کانال باشد.\nخطا: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    active_accounts = [acc for acc in get_all_accounts() if acc.get('is_active', 1)]
    if not active_accounts:
        await update.message.reply_text("هیچ اکانت فعالی برای کمک به دریافت لیست مشترکین یافت نشد. لطفاً ابتدا یک اکانت اضافه کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    await update.message.reply_text(
        text="۲. لطفاً یک اکانت فعال از لیست زیر انتخاب کنید تا برای دریافت لیست مشترکین کانال کمک کند (این اکانت باید دسترسی لازم برای مشاهده مشترکین را داشته باشد، معمولاً ادمین بودن در کانال خصوصی یا عضویت در کانال عمومی کافی است اما ممکن است محدودیت وجود داشته باشد):",
        reply_markup=build_select_helper_account_menu(
            accounts=active_accounts,
            callback_prefix=f"{prefix}_select_helper",
            cancel_callback=cancel_cb
        )
    )
    return BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_HELPER_ACCOUNT

async def bot_op_adv_remove_channel_members_helper_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    confirm_cb = f"{prefix}_confirm_final_removal"

    if query.data == "no_helper_accounts_available":
        await query.edit_message_text("عملیات لغو شد چون هیچ اکانت کمکی فعالی یافت نشد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    helper_account_db_id_str = query.data.replace(f"{prefix}_select_helper_", "")
    try:
        helper_account_db_id = int(helper_account_db_id_str)
        helper_account_details = get_account_details_by_id(helper_account_db_id)
        if not helper_account_details or not helper_account_details.get('is_active'):
            raise ValueError("Helper account not found or not active in DB.")
        context.user_data['helper_account_session'] = helper_account_details['session_file']
        context.user_data['helper_account_phone'] = helper_account_details['phone_number']
        logger.info(f"Helper account selected for channel subscriber listing: {helper_account_details['phone_number']}")
    except Exception as e:
        logger.error(f"Error selecting helper account for channel: {e}")
        await query.edit_message_text("خطا در انتخاب اکانت کمکی. لطفاً دوباره تلاش کنید.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    target_chat_id_numeric = context.user_data['target_chat_id_numeric']
    target_chat_title = context.user_data['target_chat_title']
    helper_session = context.user_data['helper_account_session']
    
    await query.edit_message_text("⏳ در حال دریافت لیست مشترکین کانال با استفاده از اکانت کمکی... این ممکن است زمان‌بر باشد و به دسترسی اکانت کمکی بستگی دارد.", reply_markup=None)

    subscribers_to_remove_ids = []
    # در کانال، همه غیر از خود ربات و سازنده (اگر قابل تشخیص باشد) باید حذف شوند اگر ادمین نباشند
    
    helper_client = TelegramClient(helper_session, int(config.API_ID), config.API_HASH)
    try:
        logger.info(f"Helper client {context.user_data['helper_account_phone']} connecting for channel subscribers...")
        await helper_client.connect()
        if not await helper_client.is_user_authorized():
            raise ConnectionError(f"Helper account {context.user_data['helper_account_phone']} is not authorized.")
        
        target_entity = await helper_client.get_entity(target_chat_id_numeric)
        
        logger.info(f"Fetching subscribers from channel {target_chat_title}...")
        count = 0
        # برای کانال، ممکن است فقط بتوانیم تعداد محدودی از مشترکین را بگیریم یا نیاز به دسترسی خاصی باشد
        # filter=ChannelParticipantsSearch('') برای گرفتن همه است، اما ممکن است برای کانال‌ها محدود باشد
        async for user in helper_client.iter_participants(target_entity, filter=ChannelParticipantsSearch(''), aggressive=False):
            if not user.bot and user.id != context.bot.id : # ربات نباشد و خود ربات اصلی هم نباشد
                # در کانال‌ها، مفهوم ادمین متفاوت است. اگر بخواهیم ادمین‌ها را حذف نکنیم، باید لیست ادمین‌ها را جداگانه بگیریم
                # فعلا همه مشترکین عادی را در نظر میگیریم
                subscribers_to_remove_ids.append(user.id)
                count +=1
                if count % 100 == 0: 
                    logger.info(f"Fetched {count} potential subscribers so far...")
        logger.info(f"Found {len(subscribers_to_remove_ids)} subscribers to remove from channel {target_chat_title} using helper {context.user_data['helper_account_phone']}.")

    except UserNotMutualContactError as e: 
        logger.error(f"Helper account cannot access channel {target_chat_title}: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"اکانت کمکی ({context.user_data['helper_account_phone']}) به کانال '{target_chat_title}' دسترسی ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    except ConnectionError as e:
        logger.error(f"Connection error with helper account {context.user_data['helper_account_phone']} for channel: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در اتصال با اکانت کمکی: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error getting subscriber list with helper account for channel: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در دریافت لیست مشترکین با اکانت کمکی: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    finally:
        if helper_client.is_connected():
            logger.info(f"Helper client {context.user_data['helper_account_phone']} disconnecting...")
            await helper_client.disconnect()

    if not subscribers_to_remove_ids:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"هیچ مشترک عادی (غیر ربات) در کانال '{target_chat_title}' برای حذف یافت نشد یا اکانت کمکی دسترسی لازم را نداشت.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
        
    context.user_data['members_to_remove_ids'] = subscribers_to_remove_ids # استفاده از همان کلید برای سادگی

    confirmation_message = (
        f"تعداد {len(subscribers_to_remove_ids)} مشترک برای حذف (مسدود کردن) از کانال '{target_chat_title}' شناسایی شد.\n"
        f"ربات اصلی این عملیات را انجام خواهد داد (باید ادمین کانال با دسترسی مسدود کردن کاربران باشد). این کار ممکن است بسیار زمان‌بر باشد و **غیرقابل بازگشت** است.\n\n"
        f"آیا برای شروع عملیات حذف مطمئن هستید؟"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=confirmation_message,
        reply_markup=build_confirm_cancel_buttons(confirm_callback=confirm_cb, cancel_callback=cancel_cb),
        parse_mode=ParseMode.HTML
    )
    return BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_CONFIRM


async def bot_op_adv_remove_channel_members_confirmed_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    target_chat_id_numeric = context.user_data['target_chat_id_numeric']
    target_chat_title = context.user_data['target_chat_title']
    members_to_remove_ids = context.user_data.get('members_to_remove_ids', [])

    if not members_to_remove_ids:
        await query.edit_message_text(f"لیست مشترکین برای حذف خالی است. عملیات لغو شد.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    original_message = await query.edit_message_text(f"⏳ **شروع عملیات حذف مشترکین از کانال '{target_chat_title}' توسط ربات...**\n"
                                  f"تعداد کل مشترکین برای حذف: {len(members_to_remove_ids)}\n"
                                  f"این فرآیند ممکن است دقایق زیادی طول بکشد. لطفاً صبور باشید.", 
                                  reply_markup=None, parse_mode=ParseMode.HTML)
    
    removed_count = 0
    failed_count = 0
    delay_between_actions = 1.2 # ثانیه

    try:
        bot_member = await context.bot.get_chat_member(chat_id=target_chat_id_numeric, user_id=context.bot.id)
        if not bot_member.status == "administrator" or not bot_member.can_restrict_members:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ ربات دسترسی لازم (ادمین با قابلیت مسدود کردن کاربران) را در کانال '{target_chat_title}' ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
            context.user_data.clear(); return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking bot permissions in channel {target_chat_id_numeric}: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ خطا در بررسی دسترسی ربات در کانال '{target_chat_title}'.", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    for i, user_id_to_remove in enumerate(members_to_remove_ids):
        try:
            # در کانال‌ها، حذف مشترک معادل ban کردن اوست
            await context.bot.ban_chat_member(chat_id=target_chat_id_numeric, user_id=user_id_to_remove)
            removed_count += 1
            logger.info(f"Bot banned subscriber {user_id_to_remove} from channel {target_chat_id_numeric}. ({removed_count}/{len(members_to_remove_ids)})")
            
            if (i + 1) % 25 == 0 or (i + 1) == len(members_to_remove_ids) : 
                try:
                    await original_message.edit_text(
                        text=f"⏳ در حال حذف مشترکین از کانال '{target_chat_title}'...\n"
                             f"{removed_count} از {len(members_to_remove_ids)} نفر حذف (مسدود) شده‌اند.\n"
                             f"{failed_count} تلاش ناموفق.",
                        parse_mode=ParseMode.HTML
                    )
                except BadRequest as e_edit:
                    if "Message is not modified" not in str(e_edit): 
                        logger.warning(f"Could not edit progress message: {e_edit}")
                except Exception as e_edit_unknown:
                     logger.warning(f"Unknown error editing progress message: {e_edit_unknown}")
        except BadRequest as e: 
            if "user_not_participant" in str(e).lower() or "user_id_invalid" in str(e).lower():
                logger.warning(f"Bot: Subscriber {user_id_to_remove} not found or not participant in channel {target_chat_id_numeric}: {e.message}")
            elif "rights_forbidden" in str(e).lower(): # اگر ربات دسترسی مسدود کردن نداشته باشد
                 logger.error(f"Bot has no rights to ban in channel {target_chat_id_numeric}: {e.message}")
                 await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ ربات دسترسی لازم برای مسدود کردن کاربران در کانال '{target_chat_title}' را ندارد. عملیات متوقف شد.", reply_markup=build_bot_operations_menu())
                 failed_count += (len(members_to_remove_ids) - removed_count); break
            else:
                logger.warning(f"Bot failed to ban subscriber {user_id_to_remove} from channel {target_chat_id_numeric}: {e.message}")
            failed_count += 1
        except TelegramError as e_telegram: 
            logger.error(f"Bot TelegramError banning subscriber {user_id_to_remove} from channel {target_chat_id_numeric}: {e_telegram}")
            failed_count += 1
            if "flood_wait_" in str(e_telegram).lower(): 
                try: flood_wait_time = int(str(e_telegram).split("FLOOD_WAIT_")[1].split(" ")[0])
                except: flood_wait_time = 30 
                logger.warning(f"Flood control hit. Waiting for {flood_wait_time} seconds.")
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ محدودیت تلگرام (Flood). ربات به مدت {flood_wait_time} ثانیه متوقف می‌شود و سپس ادامه می‌دهد...")
                await asyncio.sleep(flood_wait_time)
                delay_between_actions = min(delay_between_actions + 0.5, 5.0) 
        except Exception as e_unknown:
            logger.error(f"Bot unknown error banning subscriber {user_id_to_remove} from channel {target_chat_id_numeric}: {e_unknown}")
            failed_count += 1
        
        await asyncio.sleep(delay_between_actions) 

    report_message = f"🏁 **گزارش نهایی حذف مشترکین از کانال '{target_chat_title}' (توسط ربات):**\n\n"
    report_message += f"تعداد کل مشترکین شناسایی شده برای حذف: {len(members_to_remove_ids)}\n"
    report_message += f"تعداد مشترکین با موفقیت حذف (مسدود) شده: {removed_count} ✅\n"
    report_message += f"تعداد تلاش‌های ناموفق: {failed_count} ❌"

    try:
        await original_message.edit_text(text=report_message, reply_markup=build_bot_operations_menu(), parse_mode=ParseMode.HTML)
    except Exception: 
        await context.bot.send_message(chat_id=update.effective_chat.id, text=report_message, reply_markup=build_bot_operations_menu(), parse_mode=ParseMode.HTML)

    context.user_data.clear()
    return ConversationHandler.END
# --- توابع برای افزودن ادمین در چت (کانال/گروه) با ربات (جدید) ---
async def bot_op_add_admin_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_type: str) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    
    conv_name = BOT_OP_ADD_ADMIN_GROUP_CONV if chat_type == "group" else BOT_OP_ADD_ADMIN_CHANNEL_CONV
    prefix = f"bot_op_add_admin_{chat_type}"
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    
    context.user_data['_active_conversation_name'] = conv_name
    context.user_data['bot_op_conv_prefix'] = prefix
    context.user_data['chat_type_for_add_admin'] = chat_type # "group" or "channel"

    type_fa = "گروه" if chat_type == "group" else "کانال"
    await query.edit_message_text(
        text=f"👑 **افزودن ادمین در {type_fa} (با ربات)**\n\n"
             f"۱. لطفاً شناسه عددی یا لینک/یوزرنیم {type_fa} هدف را وارد کنید:",
        reply_markup=build_cancel_button(callback_data=cancel_cb),
        parse_mode=ParseMode.HTML
    )
    return BOT_OP_ADD_ADMIN_CHAT_ASK_TARGET

async def bot_op_add_admin_chat_target_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    target_chat_input = update.message.text.strip() # تغییر نام متغیر برای وضوح
    context.user_data['target_chat_id_str'] = target_chat_input # ذخیره ورودی خام کاربر
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    chat_type = context.user_data['chat_type_for_add_admin']
    type_fa = "گروه" if chat_type == "group" else "کانال"

    if not target_chat_input:
        await update.message.reply_text(f"شناسه {type_fa} نمی‌تواند خالی باشد. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_ADD_ADMIN_CHAT_ASK_TARGET

    chat_id_to_fetch = target_chat_input
    # تلاش برای استخراج یوزرنیم اگر لینک است
    if "t.me/" in target_chat_input:
        parts = target_chat_input.split("/")
        if len(parts) > 0:
            potential_username = parts[-1]
            if not potential_username.startswith("+") and not potential_username.isdigit(): # اگر شبیه join link یا شماره نیست
                chat_id_to_fetch = "@" + potential_username if not potential_username.startswith("@") else potential_username
            # برای لینک‌های خصوصی joinchat، get_chat مستقیماً کار نمی‌کند؛ ربات باید عضو باشد.
            # در اینجا فرض می‌کنیم کاربر یا آیدی عددی یا یوزرنیم/لینک عمومی می‌دهد.

    try:
        logger.info(f"Bot Add Admin: Attempting to get chat info for: {chat_id_to_fetch}")
        chat_info = await context.bot.get_chat(chat_id=chat_id_to_fetch)
        # ... (بقیه کد شما برای بررسی type و دسترسی‌ها) ...
        context.user_data['target_chat_id_numeric'] = chat_info.id
        context.user_data['target_chat_title'] = chat_info.title or target_chat_input
        
        bot_member = await context.bot.get_chat_member(chat_id=chat_info.id, user_id=context.bot.id)
        if not bot_member.status == "administrator" or not bot_member.can_promote_members:
            await update.message.reply_text(f"❌ ربات دسترسی لازم (افزودن ادمین‌های جدید) را در {type_fa} '{chat_info.title or target_chat_input}' ندارد.", reply_markup=build_bot_operations_menu())
            context.user_data.clear(); return ConversationHandler.END

    except BadRequest as e:
        if "Chat not found" in str(e.message):
            logger.error(f"Bot Add Admin to {chat_type}: Chat not found for '{target_chat_input}' (tried fetching '{chat_id_to_fetch}'). Error: {e}")
            await update.message.reply_text(f"❌ {type_fa} با شناسه/لینک '{target_chat_input}' یافت نشد. لطفاً از صحت آن و عضویت ربات (در صورت نیاز) مطمئن شوید.", reply_markup=build_bot_operations_menu())
        else:
            logger.error(f"Bot Add Admin to {chat_type}: BadRequest for '{target_chat_input}'. Error: {e}")
            await update.message.reply_text(f"❌ خطای BadRequest در دسترسی به {type_fa} '{target_chat_input}'.\nخطا: {e.message}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END
    except Exception as e:
        logger.error(f"Bot Add Admin to {chat_type}: Could not resolve or validate ID {target_chat_input} (tried fetching '{chat_id_to_fetch}'): {e}")
        await update.message.reply_text(f"❌ خطای دسترسی به {type_fa} یا نامعتبر بودن شناسه '{target_chat_input}'.\nخطا: {e}", reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    # ... (ادامه تابع برای رفتن به مرحله بعدی)
    await update.message.reply_text(
        text=f"۲. کدام دسته از اکانت‌های ذخیره شده در ربات را می‌خواهید در {type_fa} '{context.user_data['target_chat_title']}' به ادمین ارتقا دهید؟",
        reply_markup=build_tool_account_category_filter_menu(tool_prefix=prefix, cancel_callback=cancel_cb)
    )
    return BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_CATEGORY

async def bot_op_add_admin_chat_acc_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    chat_type = context.user_data['chat_type_for_add_admin']
    type_fa = "گروه" if chat_type == "group" else "کانال"
    
    category_filter = None
    if callback_data == f"{prefix}_filter_iranian": category_filter = 'iranian'
    elif callback_data == f"{prefix}_filter_foreign": category_filter = 'foreign'
    elif callback_data == f"{prefix}_filter_all": category_filter = None

    context.user_data[f'{prefix}_acc_category_filter'] = category_filter
    
    filtered_accounts = get_all_accounts(category_filter=category_filter)
    active_filtered_accounts = [acc for acc in filtered_accounts if acc.get('is_active', 1)]

    if not active_filtered_accounts:
        cat_name = "ایرانی" if category_filter == "iranian" else "خارجی" if category_filter == "foreign" else "کلی"
        await query.edit_message_text(
            text=f"⚠️ هیچ اکانت فعالی در دسته‌بندی «{cat_name}» برای ارتقا به ادمین یافت نشد.\nلطفاً ابتدا اکانت اضافه کنید یا دسته‌بندی دیگری را انتخاب نمایید.",
            reply_markup=build_tool_account_category_filter_menu(tool_prefix=prefix, cancel_callback=cancel_cb)
        )
        return BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_CATEGORY

    context.user_data['eligible_accounts_for_promotion'] = active_filtered_accounts # لیست اکانت های کاندید

    await query.edit_message_text(
        text=f"۳. چگونه می‌خواهید از بین {len(active_filtered_accounts)} اکانت فعال در دسته‌بندی انتخاب شده، اکانت(ها)یی که باید ادمین شوند را انتخاب کنید؟",
        reply_markup=build_account_count_selection_menu(tool_prefix=prefix, cancel_callback=cancel_cb) # از همان منوی انتخاب تعداد ابزارها استفاده میکنیم
    )
    return BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_COUNT_METHOD

async def bot_op_add_admin_chat_acc_count_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    chat_type = context.user_data['chat_type_for_add_admin']
    type_fa = "گروه" if chat_type == "group" else "کانال"

    ask_users_prompt = f"۴. لطفاً یوزرنیم یا شناسه عددی اکانت(های) Telethon که می‌خواهید در {type_fa} '{context.user_data['target_chat_title']}' ادمین شوند را وارد کنید (هر کدام در یک خط یا با کاما جدا شده):"

    if callback_data == f"{prefix}_use_all":
        context.user_data[f'{prefix}_acc_mode'] = 'all'
        # اگر "همه" انتخاب شد، لیست کاربران از eligible_accounts_for_promotion ساخته میشود
        eligible_accounts = context.user_data.get('eligible_accounts_for_promotion', [])
        user_ids_to_promote = [str(acc['user_id']) for acc in eligible_accounts if acc.get('user_id')]
        context.user_data[f'{prefix}_users_to_promote_ids_list'] = user_ids_to_promote
        
        if not user_ids_to_promote:
            await query.edit_message_text(f"هیچ اکانت واجد شرایطی برای ارتقا به ادمین یافت نشد (ممکن است شناسه تلگرامی آنها ثبت نشده باشد).", reply_markup=build_bot_operations_menu())
            context.user_data.clear(); return ConversationHandler.END

        # مستقیم برو به تایید نهایی چون لیست کاربران مشخص است
        return await bot_op_add_admin_chat_ask_final_confirm(update, context) # یک تابع جدید برای این کار

    elif callback_data == f"{prefix}_specify_count":
        # این حالت برای انتخاب اکانت‌های خاص از لیست نیست، بلکه برای تعیین تعداد از لیست کلی است.
        
        context.user_data[f'{prefix}_acc_mode'] = 'specific_list_input' # حالت جدید
        await query.edit_message_text(text=ask_users_prompt, reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_ADD_ADMIN_CHAT_ASK_USERS_TO_PROMOTE # مرحله دریافت لیست کاربران
        
    return ConversationHandler.END


async def bot_op_add_admin_chat_users_to_promote_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    users_input_str = update.message.text.strip()
    user_identifiers = [u.strip() for u in users_input_str.replace(',', '\n').split('\n') if u.strip()]
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"

    if not user_identifiers:
        await update.message.reply_text("لیست کاربران برای ارتقا خالی است. دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return BOT_OP_ADD_ADMIN_CHAT_ASK_USERS_TO_PROMOTE
    
    context.user_data[f'{prefix}_users_to_promote_ids_list'] = user_identifiers
    return await bot_op_add_admin_chat_ask_final_confirm(update, context)


async def bot_op_add_admin_chat_ask_final_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # این تابع هم از callback (اگر 'همه' انتخاب شده) و هم از message (اگر لیست وارد شده) می آید
    prefix = context.user_data['bot_op_conv_prefix']
    cancel_cb = f"{prefix}_cancel_to_bot_operations_menu"
    confirm_cb = f"{prefix}_confirm_final_promotion"
    chat_type = context.user_data['chat_type_for_add_admin']
    type_fa = "گروه" if chat_type == "group" else "کانال"
    target_chat_title = context.user_data['target_chat_title']
    users_to_promote_ids_list = context.user_data.get(f'{prefix}_users_to_promote_ids_list', [])

    if not users_to_promote_ids_list:
        msg_text = "لیستی از کاربران برای ادمین شدن مشخص نشده است. عملیات لغو شد."
        if update.callback_query: await update.callback_query.edit_message_text(msg_text, reply_markup=build_bot_operations_menu())
        else: await update.message.reply_text(msg_text, reply_markup=build_bot_operations_menu())
        context.user_data.clear(); return ConversationHandler.END

    users_preview = "\n- ".join(users_to_promote_ids_list[:5]) # نمایش ۵ تای اول
    if len(users_to_promote_ids_list) > 5: users_preview += "\n- و ..."

    confirmation_message = (
        f"👑 **تأیید نهایی عملیات افزودن ادمین** 👑\n\n"
        f"ربات تلاش خواهد کرد تا کاربران زیر را در {type_fa} «{target_chat_title}» به ادمین (با دسترسی کامل) ارتقا دهد:\n"
        f"- {users_preview}\n\n"
        f"تعداد کل کاربران برای ارتقا: {len(users_to_promote_ids_list)}\n"
        f"توجه: ربات باید ادمین {type_fa} با دسترسی 'افزودن ادمین‌های جدید' باشد و کاربران هدف نیز باید عضو {type_fa} باشند.\n\n"
        f"آیا مطمئن هستید؟"
    )
    
    if update.callback_query: # اگر از انتخاب 'همه' آمده
        await update.callback_query.edit_message_text(text=confirmation_message, reply_markup=build_confirm_cancel_buttons(confirm_cb, cancel_cb), parse_mode=ParseMode.HTML)
    else: # اگر از وارد کردن لیست کاربران آمده
        await update.message.reply_text(text=confirmation_message, reply_markup=build_confirm_cancel_buttons(confirm_cb, cancel_cb), parse_mode=ParseMode.HTML)
        
    return BOT_OP_ADD_ADMIN_CHAT_ASK_CONFIRM


async def bot_op_add_admin_chat_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    prefix = context.user_data['bot_op_conv_prefix']
    chat_type = context.user_data['chat_type_for_add_admin']
    type_fa = "گروه" if chat_type == "group" else "کانال"
    target_chat_id_numeric = context.user_data['target_chat_id_numeric']
    target_chat_title = context.user_data['target_chat_title']
    users_to_promote_input_list = context.user_data.get(f'{prefix}_users_to_promote_ids_list', [])

    await query.edit_message_text(f"⏳ در حال تلاش برای ارتقا {len(users_to_promote_input_list)} کاربر به ادمین در {type_fa} '{target_chat_title}' توسط ربات...", reply_markup=None)

    success_count = 0
    failure_count = 0
    results_summary = [] # (user_identifier, status_emoji, detail)
    
    
    
    for user_identifier in users_to_promote_input_list:
        user_id_to_promote = None
        try:
            # ابتدا سعی میکنیم به عنوان شناسه عددی در نظر بگیریم
            try: user_id_to_promote = int(user_identifier)
            except ValueError:
                # اگر عدد نبود، سعی میکنیم به عنوان یوزرنیم (بدون @) در نظر بگیریم
                # get_chat برای یوزرنیم هم کار میکند و یوزر را برمیگرداند
                user_info = await context.bot.get_chat(chat_id=user_identifier.replace("@", ""))
                user_id_to_promote = user_info.id
            
            if not user_id_to_promote:
                raise ValueError(f"Could not resolve user: {user_identifier}")

            await context.bot.promote_chat_member(
                chat_id=target_chat_id_numeric,
                user_id=user_id_to_promote,
                can_change_info=True,
                can_post_messages=True if chat_type == "channel" else None, # فقط برای کانال
                can_edit_messages=True if chat_type == "channel" else None, # فقط برای کانال
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=True, # اجازه دادن به این ادمین برای افزودن ادمین های دیگر
                can_manage_chat=True, # معادل manage_topics در سوپرگروه ها، و سایر تنظیمات
                can_manage_video_chats=True,
                # is_anonymous برای ربات ها قابل تنظیم نیست، برای کاربران هم اینجا True نمیکنیم
            )
            results_summary.append((user_identifier, "✅", "با موفقیت ادمین شد."))
            success_count += 1
            logger.info(f"Bot successfully promoted {user_identifier} (ID: {user_id_to_promote}) in {chat_type} {target_chat_title}")

        except UserNotParticipantError: 
            results_summary.append((user_identifier, "❌", "کاربر عضو نیست."))
            failure_count += 1
            logger.warning(f"Bot: User {user_identifier} not participant in {chat_type} {target_chat_title}.")
        except BadRequest as e:
            error_message = str(e.message).lower()
            if "user_not_participant" in error_message or "participant_not_found" in error_message:
                results_summary.append((user_identifier, "❌", "کاربر عضو نیست."))
            elif "not_enough_rights" in error_message or "rights_forbidden" in error_message:
                results_summary.append((user_identifier, "❌", "ربات دسترسی کافی برای ارتقا ندارد."))
            elif "user_is_bot" in error_message and chat_type == "group": # ربات نمیتواند ربات دیگر را با همه دسترسی ها ادمین گروه کند
                 results_summary.append((user_identifier, "⚠️", "ربات است (برخی دسترسی‌ها داده نشد)."))
                
            else:
                results_summary.append((user_identifier, "❌", f"خطا: {e.message}"))
            failure_count += 1
            logger.warning(f"Bot: Failed to promote {user_identifier} in {chat_type} {target_chat_title}: {e.message}")
        except Exception as e:
            results_summary.append((user_identifier, "❌", f"خطای ناشناخته: {type(e).__name__}"))
            failure_count += 1
            logger.error(f"Bot: Unknown error promoting {user_identifier} in {chat_type} {target_chat_title}: {e}")
        
        await asyncio.sleep(random.uniform(1.0, 2.0)) # تاخیر

    report_message = f"🏁 **گزارش نهایی افزودن ادمین در {type_fa} '{target_chat_title}' (توسط ربات):**\n\n"
    report_message += f"تعداد کل کاربران درخواستی برای ارتقا: {len(users_to_promote_input_list)}\n"
    report_message += f"تعداد ارتقاهای موفق: {success_count} ✅\n"
    report_message += f"تعداد ارتقاهای ناموفق: {failure_count} ❌\n\n"
    if results_summary:
        report_message += "جزئیات:\n"
        for user, status, detail in results_summary:
            report_message += f"- کاربر `{user}`: {status} ({detail})\n"
    
    if len(report_message) > 4090: report_message = report_message[:4000] + "\n..."


    await context.bot.send_message(chat_id=update.effective_chat.id, text=report_message, reply_markup=build_bot_operations_menu(), parse_mode=ParseMode.HTML)
    context.user_data.clear()
    return ConversationHandler.END

# --- توابع برای تنظیمات ربات ---
@admin_only
async def settings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    logger.info(f"SETTINGS_ENTRY called. User_data: {context.user_data}, Callback: {query.data if query else 'No Query'}") # <--- لاگ جدید
    context.user_data['_active_conversation_name'] = SETTINGS_CONV
    if query: 
        await query.answer()
        text, markup = build_settings_menu_content(context) 
        try:
            await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        except BadRequest as e:
            if "Message is not modified" in str(e): 
                logger.info("Settings menu not modified.")
            else: 
                logger.error(f"BadRequest in settings_entry: {e}", exc_info=True) # لاگ کردن خطا
                
                await context.bot.send_message(chat_id=update.effective_chat.id, text="خطا در نمایش منوی تنظیمات.")
        except Exception as e_gen:
            logger.error(f"Generic Exception in settings_entry: {e_gen}", exc_info=True)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="خطای ناشناخته در نمایش منوی تنظیمات.")

    return SETTINGS_MENU

async def settings_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "settings_api_management":
        text, markup = build_api_management_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_API_MENU
    elif callback_data == "settings_admins_management":
        text, markup = build_admins_management_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_ADMINS_MENU
    elif callback_data == "settings_spam_keywords_management":
        text, markup = build_spam_keywords_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML) 
        return SETTINGS_SPAM_MENU
    elif callback_data == "settings_delay_management":
        text, markup = build_delay_management_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_DELAY_MENU
        
    elif callback_data.endswith("_placeholder"):
        placeholder_name = callback_data.replace("_placeholder", "").replace("settings_", "").replace("_", " ").title()
        text, markup = build_settings_menu_content(context)
        await query.edit_message_text(f"بخش '{placeholder_name}' هنوز پیاده‌سازی نشده.", reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_MENU
    elif callback_data == "general_back_to_main_menu":
        user = update.effective_user
        welcome_text = (rf"سلام ادمین گرامی <b>{user.full_name}</b>! 👋\nبه ربات مدیریت اکانت‌های تلگرام خوش آمدید.\nلطفا یک گزینه را از منوی زیر انتخاب کنید:")
        await query.edit_message_text(welcome_text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    return SETTINGS_MENU

# --- توابع برای مدیریت API ID/Hash ---
async def settings_api_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    
    if callback_data == "settings_api_add_new":
        context.user_data['current_api_setting_action'] = 'add'
        await query.edit_message_text("لطفاً API ID جدید را وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_api_menu"))
        return SETTINGS_ASK_API_ID
    elif callback_data == "settings_api_remove_select":
        api_keys_list = context.bot_data.get('api_keys_list', [])
        if not api_keys_list:
            await query.answer("لیستی برای حذف وجود ندارد.", show_alert=True)
            return SETTINGS_API_MENU
        buttons = []
        for i, key_pair in enumerate(api_keys_list):
            api_id_display = key_pair.get('api_id', f'اندیس {i}')
            buttons.append([InlineKeyboardButton(f"🗑 حذف API ID: {api_id_display}", callback_data=f"settings_api_confirm_remove_{key_pair.get('api_id')}")])
        buttons.append([InlineKeyboardButton("⬅️ لغو", callback_data="settings_cancel_to_api_menu_no_edit")])
        # ارسال پیام جدید برای نمایش دکمه های حذف، چون edit_message_text ممکن است دکمه های قبلی را نگه دارد
        await context.bot.send_message(chat_id=query.message.chat_id, text="لطفاً API ID/Hash ای که می‌خواهید حذف شود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
        try: await query.delete_message() # حذف پیام قبلی منوی API
        except: pass
        return SETTINGS_API_MENU 
    elif callback_data.startswith("settings_api_confirm_remove_"):
        api_id_to_remove_str = callback_data.replace("settings_api_confirm_remove_", "")
        try:
            api_id_to_remove = int(api_id_to_remove_str)
            if remove_api_key(api_id_to_remove): 
                context.bot_data['api_keys_list'] = get_api_keys() 
                await query.answer("API Key با موفقیت حذف شد.", show_alert=True)
            else:
                await query.answer("خطا در حذف API Key یا یافت نشد.", show_alert=True)
        except ValueError:
            await query.answer("خطا در پردازش حذف.", show_alert=True)
        
        text, markup = build_api_management_menu_content(context) 
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_API_MENU
    elif callback_data == "main_menu_settings_from_action": 
        text, markup = build_settings_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_MENU
    elif callback_data == "settings_cancel_to_api_menu_no_edit": # فقط برای بستن دکمه های حذف بدون ویرایش پیام اصلی
         text, markup = build_api_management_menu_content(context) 
         try: await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML) # بازگشت به منوی API
         except: pass # اگر پیام قبلا حذف شده باشد
         return SETTINGS_API_MENU

    return SETTINGS_API_MENU

async def settings_api_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_api_id_str = update.message.text.strip()
    if not new_api_id_str.isdigit():
        await update.message.reply_text("API ID باید فقط شامل اعداد باشد. لطفاً دوباره وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_api_menu"))
        return SETTINGS_ASK_API_ID
    
    context.user_data['pending_api_id'] = int(new_api_id_str)
    await update.message.reply_text("حالا لطفاً API Hash مربوط به این API ID را وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_api_menu"))
    return SETTINGS_ASK_API_HASH

async def settings_api_hash_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_api_hash = update.message.text.strip()
    pending_api_id = context.user_data.get('pending_api_id')

    if not pending_api_id: 
        text_err, markup_err = build_api_management_menu_content(context)
        await update.message.reply_text("خطای داخلی، API ID یافت نشد. لطفاً از ابتدا شروع کنید.", reply_markup=markup_err, parse_mode=ParseMode.HTML)
        return SETTINGS_API_MENU
        
    if not new_api_hash or len(new_api_hash) < 30 :
        await update.message.reply_text("API Hash وارد شده معتبر به نظر نمی‌رسد. لطفاً دوباره وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_api_menu"))
        return SETTINGS_ASK_API_HASH

    if add_api_key(pending_api_id, new_api_hash): 
        context.bot_data['api_keys_list'] = get_api_keys() 
        await update.message.reply_text(f"✅ API ID/Hash جدید با موفقیت اضافه شد.")
    else:
        await update.message.reply_text(f"⚠️ این API ID (`{pending_api_id}`) قبلاً اضافه شده بود یا خطایی در ذخیره رخ داد.")

    text, markup = build_api_management_menu_content(context) 
    await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML) 
    context.user_data.pop('pending_api_id', None)
    return SETTINGS_API_MENU

async def settings_cancel_to_api_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text, markup = build_api_management_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_API_MENU

# --- توابع برای مدیریت ادمین ها ---
async def settings_admins_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "settings_admins_add_db":
        await query.edit_message_text("➕ لطفاً شناسه عددی ادمین جدید را برای افزودن به دیتابیس وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_admins_menu"))
        return SETTINGS_ADMINS_ASK_ADD_ID
    elif callback_data == "settings_admins_remove_db_select":
        db_admin_ids = context.bot_data.get('db_admin_ids', [])
        config_admin_ids = set(config.ADMIN_IDS)
        removable_admins = [admin_id for admin_id in db_admin_ids if admin_id not in config_admin_ids]

        if not removable_admins:
             text, markup = build_admins_management_menu_content(context)
             await query.edit_message_text("هیچ ادمینی (که از طریق ربات اضافه شده باشد) برای حذف وجود ندارد.", reply_markup=markup, parse_mode=ParseMode.HTML)
             return SETTINGS_ADMINS_MENU
        
        buttons = []
        for admin_id in removable_admins:
            buttons.append([InlineKeyboardButton(f"🗑 حذف ادمین: {admin_id}", callback_data=f"settings_admin_remove_db_confirm_{admin_id}")])
        buttons.append([InlineKeyboardButton("⬅️ لغو", callback_data="settings_cancel_to_admins_menu_no_edit")])
        await query.edit_message_text("لطفاً ادمینی که می‌خواهید از دیتابیس حذف شود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
        return SETTINGS_ADMINS_MENU 
        
    elif callback_data.startswith("settings_admin_remove_db_confirm_"):
        try:
            admin_id_to_remove = int(callback_data.split("_")[-1])
            if remove_db_admin(admin_id_to_remove):
                context.bot_data['db_admin_ids'] = get_db_admins() # بازخوانی ادمین های دیتابیس
                context.bot_data['admin_ids_master_list'] = list(set(config.ADMIN_IDS + context.bot_data['db_admin_ids']))
                logger.info(f"Admin {admin_id_to_remove} removed from DB by {update.effective_user.id}. New master list: {context.bot_data['admin_ids_master_list']}")
                await query.answer("ادمین با موفقیت از دیتابیس حذف شد.", show_alert=True)
            else:
                await query.answer("خطا در حذف ادمین یا یافت نشد.", show_alert=True)
        except ValueError:
            await query.answer("خطا در پردازش حذف.", show_alert=True)
        
        text, markup = build_admins_management_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_ADMINS_MENU
    elif callback_data == "settings_cancel_to_admins_menu_no_edit":
         text, markup = build_admins_management_menu_content(context) 
         try: await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
         except: pass
         return SETTINGS_ADMINS_MENU

    elif callback_data == "main_menu_settings_from_action": 
        text, markup = build_settings_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_MENU
    
    text, markup = build_admins_management_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_ADMINS_MENU


async def settings_admin_add_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_admin_id = int(update.message.text.strip())
        if add_db_admin(new_admin_id):
            context.bot_data['db_admin_ids'] = get_db_admins()
            context.bot_data['admin_ids_master_list'] = list(set(config.ADMIN_IDS + context.bot_data['db_admin_ids']))
            logger.info(f"Admin {new_admin_id} added to DB by {update.effective_user.id}. New master list: {context.bot_data['admin_ids_master_list']}")
            text, markup = build_admins_management_menu_content(context)
            await update.message.reply_html(f"✅ ادمین با شناسه `{new_admin_id}` با موفقیت به دیتابیس اضافه شد.\n\n{text}", reply_markup=markup)
        else: 
            text, markup = build_admins_management_menu_content(context)
            await update.message.reply_html(f"این کاربر در حال حاضر ادمین است یا خطایی در افزودن رخ داد.\n\n{text}", reply_markup=markup)
            
    except ValueError:
        await update.message.reply_text("شناسه وارد شده نامعتبر است. لطفاً فقط عدد وارد کنید.", reply_markup=build_cancel_button("settings_cancel_to_admins_menu"))
        return SETTINGS_ADMINS_ASK_ADD_ID
    return SETTINGS_ADMINS_MENU

async def settings_cancel_to_admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text, markup = build_admins_management_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_ADMINS_MENU

# --- توابع برای مدیریت کلمات اسپم ---
async def settings_spam_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "settings_spam_add_keyword":
        await query.edit_message_text("لطفاً کلمه یا عبارت اسپم جدید را وارد کنید:", reply_markup=build_cancel_button("settings_cancel_to_spam_menu"))
        return SETTINGS_SPAM_ASK_ADD
    elif callback_data == "settings_spam_remove_select_keyword":
        keywords = context.bot_data.get('spam_keywords_list', [])
        if not keywords:
            await query.answer("هیچ کلمه ای برای حذف وجود ندارد.", show_alert=True)
            return SETTINGS_SPAM_MENU
        buttons = []
        for i, kw in enumerate(keywords[:50]): # نمایش حداکثر 50 کلمه برای انتخاب
            buttons.append([InlineKeyboardButton(f"🗑 {kw[:20]}{'...' if len(kw)>20 else ''}", callback_data=f"settings_spam_confirm_remove_{i}")]) # استفاده از اندیس برای callback
        buttons.append([InlineKeyboardButton("⬅️ لغو", callback_data="settings_cancel_to_spam_menu_no_edit")])
        await query.edit_message_text("کدام کلمه/عبارت اسپم حذف شود؟ (نمایش حداکثر 50 مورد)", reply_markup=InlineKeyboardMarkup(buttons))
        return SETTINGS_SPAM_MENU 
    elif callback_data.startswith("settings_spam_confirm_remove_"):
        try:
            keyword_index_to_remove = int(callback_data.replace("settings_spam_confirm_remove_", ""))
            keywords_list = context.bot_data.get('spam_keywords_list', [])
            if 0 <= keyword_index_to_remove < len(keywords_list):
                keyword_to_remove = keywords_list[keyword_index_to_remove]
                if remove_spam_keyword(keyword_to_remove):
                    context.bot_data['spam_keywords_list'] = get_spam_keywords()
                    await query.answer(f"کلمه '{keyword_to_remove}' حذف شد.", show_alert=True)
                else:
                    await query.answer("خطا در حذف یا کلمه یافت نشد.", show_alert=True)
            else:
                await query.answer("اندیس کلمه نامعتبر است.", show_alert=True)
        except ValueError:
            await query.answer("خطا در پردازش حذف.", show_alert=True)
        
        text, markup = build_spam_keywords_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_SPAM_MENU
    elif callback_data == "settings_cancel_to_spam_menu_no_edit":
         text, markup = build_spam_keywords_menu_content(context)
         try: await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
         except: pass
         return SETTINGS_SPAM_MENU
    elif callback_data == "main_menu_settings_from_action": 
        text, markup = build_settings_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_MENU
    
    text, markup = build_spam_keywords_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_SPAM_MENU

async def settings_spam_add_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_keyword = update.message.text.strip()
    if new_keyword:
        if add_spam_keyword(new_keyword):
            context.bot_data['spam_keywords_list'] = get_spam_keywords()
            await update.message.reply_text(f"✅ کلمه/عبارت '{new_keyword}' با موفقیت به لیست اسپم اضافه شد.")
        else:
            await update.message.reply_text(f"⚠️ کلمه/عبارت '{new_keyword}' از قبل وجود دارد یا خطایی رخ داد.")
    else:
        await update.message.reply_text("کلمه/عبارت اسپم نمی‌تواند خالی باشد.")
    
    text, markup = build_spam_keywords_menu_content(context)
    await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_SPAM_MENU

async def settings_cancel_to_spam_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text, markup = build_spam_keywords_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_SPAM_MENU

# --- توابع برای مدیریت تاخیر عمومی ---
async def settings_delay_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback_data = query.data

    if callback_data == "settings_delay_change_value":
        current_delay_str = context.bot_data.get('default_operation_delay', "1.5")
        # برای اطمینان، current_delay را به float تبدیل می‌کنیم
        try: current_delay_float = float(current_delay_str)
        except ValueError: current_delay_float = 1.5
        
        await query.edit_message_text(f"تأخیر فعلی: <code>{current_delay_float:.1f}</code> ثانیه.\nلطفاً مقدار تأخیر جدید را به ثانیه وارد کنید (مثلاً 1 یا 0.5):",
                                      reply_markup=build_cancel_button("settings_cancel_to_delay_menu"),
                                      parse_mode=ParseMode.HTML)
        return SETTINGS_DELAY_ASK_VALUE
    elif callback_data == "main_menu_settings_from_action":
        text, markup = build_settings_menu_content(context)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return SETTINGS_MENU
    
    text, markup = build_delay_management_menu_content(context) 
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_DELAY_MENU

async def settings_delay_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_delay = float(update.message.text.strip())
        if new_delay < 0:
            await update.message.reply_text("مقدار تأخیر نمی‌تواند منفی باشد. لطفاً دوباره وارد کنید:", 
                                            reply_markup=build_cancel_button("settings_cancel_to_delay_menu"))
            return SETTINGS_DELAY_ASK_VALUE
        
        set_bot_setting('DEFAULT_OPERATION_DELAY', str(new_delay)) # در دیتابیس به عنوان رشته ذخیره شود
        context.bot_data['default_operation_delay'] = str(new_delay)
        logger.info(f"Default operation delay set to {new_delay} seconds by admin {update.effective_user.id}")
        
        text_reply = f"✅ تأخیر عمومی با موفقیت به <code>{new_delay:.1f}</code> ثانیه تغییر یافت." 
        text_menu, markup_menu = build_delay_management_menu_content(context) 
        await update.message.reply_text(text_reply, parse_mode=ParseMode.HTML) 
        await update.message.reply_text(text_menu, reply_markup=markup_menu, parse_mode=ParseMode.HTML) 
        return SETTINGS_DELAY_MENU

    except ValueError:
        await update.message.reply_text("مقدار وارد شده نامعتبر است. لطفاً یک عدد (مثلاً 1.5) وارد کنید:", 
                                        reply_markup=build_cancel_button("settings_cancel_to_delay_menu"))
        return SETTINGS_DELAY_ASK_VALUE

async def settings_cancel_to_delay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text, markup = build_delay_management_menu_content(context)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    return SETTINGS_DELAY_MENU
#----------------بررسي ارور ها
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates and send a message to the admin."""
    logger.error(f"Update:\n{update}\n\nContext Error:\n{context.error}\n", exc_info=context.error)

    # اختیاری: ارسال پیام خطا به ادمین اصلی (اولین ادمین در لیست کانفیگ)
    # این کار به شما کمک می‌کند حتی اگر به کنسول دسترسی ندارید، از خطاها مطلع شوید.
    if config.ADMIN_IDS:
        admin_id_to_notify = config.ADMIN_IDS[0]
        error_message_for_admin = (
            f"⚠️ ربات با یک خطا مواجه شد! ⚠️\n\n"
            f"نوع خطا: {type(context.error).__name__}\n"
            f"پیام خطا: {str(context.error)[:1000]}\n\n" # نمایش بخشی از پیام خطا
            f"لطفاً لاگ‌های سرور را برای جزئیات بیشتر بررسی کنید (traceback کامل در لاگ‌ها ثبت شده است)."
        )
        try:
            
            chat_id_to_reply = None
            if hasattr(update, 'effective_chat') and update.effective_chat:
                chat_id_to_reply = update.effective_chat.id

            if chat_id_to_reply: # اگر چت مشخصی بود، به همانجا بفرست
                 await context.bot.send_message(chat_id=chat_id_to_reply, text="یک خطای داخلی رخ داده است. ادمین مطلع شد.")

            # همیشه به ادمین اصلی هم اطلاع بده
            await context.bot.send_message(chat_id=admin_id_to_notify, text=error_message_for_admin)
        except Exception as e_send:
            logger.error(f"Failed to send error notification to admin {admin_id_to_notify}: {e_send}")
# --- توابع راه‌اندازی و اصلی ربات ---
async def post_init(application: Application) -> None:
    logger.info("ربات در حال انجام اقدامات پس از راه‌اندازی اولیه...")
    
    # بارگذاری API ID/Hash ها
    api_keys_from_db = get_api_keys()
    if api_keys_from_db:
        application.bot_data['api_keys_list'] = api_keys_from_db
        logger.info(f"{len(api_keys_from_db)} API Key pair(s) loaded from DB.")
    elif config.API_ID and config.API_HASH:
        default_api_pair = [{"api_id": str(config.API_ID), "api_hash": config.API_HASH}]
        application.bot_data['api_keys_list'] = default_api_pair
        logger.info(f"API Keys loaded from config.py as no DB entries found: {default_api_pair[0]['api_id']}")
    else:
        application.bot_data['api_keys_list'] = []
        logger.warning("API ID/Hash is not set in DB or config.py! Account addition and tools requiring Telethon might fail.")

    # بارگذاری لیست ادمین ها
    db_admins = get_db_admins()
    application.bot_data['db_admin_ids'] = db_admins # ادمین های فقط دیتابیسی
    config_admins = list(config.ADMIN_IDS)
    application.bot_data['admin_ids_master_list'] = list(set(config_admins + db_admins))
    logger.info(f"Master admin IDs loaded: {application.bot_data['admin_ids_master_list']}")

    application.bot_data['spam_keywords_list'] = get_spam_keywords()
    logger.info(f"Loaded {len(application.bot_data['spam_keywords_list'])} spam keywords from DB.")

    default_delay = get_bot_setting('DEFAULT_OPERATION_DELAY', "1.5")
    try:
        application.bot_data['default_operation_delay'] = str(float(default_delay))
    except ValueError:
        logger.warning(f"Invalid DEFAULT_OPERATION_DELAY ('{default_delay}') in DB, using 1.5s.")
        application.bot_data['default_operation_delay'] = "1.5"
        set_bot_setting('DEFAULT_OPERATION_DELAY', "1.5")
    logger.info(f"Default operation delay set to: {application.bot_data['default_operation_delay']}s")

    try:
        os.makedirs(config.SESSIONS_DIR, exist_ok=True)
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        logger.info(f"پوشه {config.SESSIONS_DIR} و {config.LOGS_DIR} بررسی/ایجاد شدند.")
    except OSError as e:
        logger.error(f"خطا در ایجاد پوشه‌ها: {e}")
    logger.info("اقدامات پس از راه‌اندازی اولیه با موفقیت انجام شد.")

#-------------- توابع جا افتاده برای مدیریت جریان ابزارها 

async def tool_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_name_fa: str, tool_prefix: str, cancel_cb: str, tool_conv_const: str) -> int:
    """
    نقطه ورود برای همه ابزارهای مبتنی بر اکانت.
    اطلاعات ابزار را در user_data ذخیره کرده و درخواست انتخاب دسته‌بندی اکانت را ارسال می‌کند.
    """
    query = update.callback_query
    await query.answer()

    keys_to_clear = [k for k in context.user_data if k.startswith("joiner_") or \
                     k.startswith("leaver_") or k.startswith("blocker_") or \
                     k.startswith("reporter_user_") or k.startswith("reporter_chat_") or \
                     k.startswith("spammer_") or k.startswith("remover_") or \
                     k.startswith("add_admin_")]
    for key in keys_to_clear:
        del context.user_data[key]
    general_tool_keys = ['_active_conversation_name', 'tool_prefix', 'tool_name_fa',
                         'tool_conv_const_for_cancel', 'cancel_callback_data_for_tool',
                         'filtered_accounts_for_tool', 'tool_account_selection_mode',
                         'tool_specific_account_count']
    for key in general_tool_keys:
        if key in context.user_data:
            del context.user_data[key]

    context.user_data['_active_conversation_name'] = tool_conv_const
    context.user_data['tool_prefix'] = tool_prefix
    context.user_data['tool_name_fa'] = tool_name_fa
    context.user_data['tool_conv_const_for_cancel'] = tool_conv_const
    context.user_data['cancel_callback_data_for_tool'] = cancel_cb

    logger.info(f"Tool entry: {tool_name_fa} (Prefix: {tool_prefix}). User: {update.effective_user.id}")

    text = f"شما ابزار «{tool_name_fa}» را انتخاب کرده‌اید.\n"
    text += "۱. لطفاً مشخص کنید از کدام دسته اکانت‌ها می‌خواهید برای این عملیات استفاده کنید:"
    reply_markup = build_tool_account_category_filter_menu(tool_prefix=tool_prefix, cancel_callback=cancel_cb)

    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.info(f"Message not modified on tool_entry_point for {tool_prefix}.")
        else:
            raise e
    return TOOL_ASK_ACCOUNT_CATEGORY_FILTER

async def tool_account_category_filter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_name_fa: str, cancel_cb: str) -> int:
    """
    پس از انتخاب دسته‌بندی اکانت (ایرانی، خارجی، همه).
    اکانت‌های موجود را فیلتر کرده و درخواست انتخاب تعداد (همه یا مشخص) را ارسال می‌کند.
    """
    query = update.callback_query
    await query.answer()

    tool_prefix = context.user_data.get('tool_prefix')
    if not tool_prefix:
        logger.error("tool_prefix not found in user_data for tool_account_category_filter_selected.")
        await query.edit_message_text("خطای داخلی: اطلاعات ابزار یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=build_tools_menu())
        return ConversationHandler.END

    category_filter_value = query.data.replace(f"{tool_prefix}_filter_", "")

    if category_filter_value == "all":
        actual_filter_for_db = None
        category_display_name = "همه اکانت‌ها"
    elif category_filter_value == "iranian":
        actual_filter_for_db = "iranian"
        category_display_name = "اکانت‌های ایرانی"
    elif category_filter_value == "foreign":
        actual_filter_for_db = "foreign"
        category_display_name = "اکانت‌های خارجی"
    else:
        logger.warning(f"Invalid category filter value: {category_filter_value}")
        await query.edit_message_text("خطای داخلی: دسته‌بندی نامعتبر است.", reply_markup=build_tools_menu())
        return ConversationHandler.END

    context.user_data[f'{tool_prefix}_category_filter'] = actual_filter_for_db

    all_accounts_in_category = get_all_accounts(category_filter=actual_filter_for_db)
    active_filtered_accounts = [acc for acc in all_accounts_in_category if acc.get('is_active', 1)]

    if not active_filtered_accounts:
        text = f"هیچ اکانت فعالی در دسته‌بندی «{category_display_name}» یافت نشد.\n"
        text += "لطفاً ابتدا اکانت اضافه کنید یا دسته‌بندی دیگری را انتخاب نمایید."
        reply_markup = build_tool_account_category_filter_menu(tool_prefix=tool_prefix, cancel_callback=cancel_cb)
        await query.edit_message_text(text=text, reply_markup=reply_markup)
        return TOOL_ASK_ACCOUNT_CATEGORY_FILTER

    context.user_data['filtered_accounts_for_tool'] = active_filtered_accounts
    logger.info(f"Tool {tool_prefix}: {len(active_filtered_accounts)} active accounts found for category '{category_display_name}'.")

    text = f"۲. تعداد {len(active_filtered_accounts)} اکانت فعال در دسته «{category_display_name}» یافت شد.\n"
    text += "چگونه می‌خواهید اکانت‌های مورد استفاده برای این عملیات را انتخاب کنید؟"
    reply_markup = build_account_count_selection_menu(tool_prefix=tool_prefix, cancel_callback=cancel_cb)

    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return TOOL_SELECT_ACCOUNT_METHOD

async def tool_account_count_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, target_prompt: str, cancel_cb: str) -> int:
    """
    پس از انتخاب روش گزینش تعداد اکانت (همه یا تعداد مشخص).
    اگر "همه" انتخاب شود، به مرحله دریافت هدف ابزار می‌رود.
    اگر "تعداد مشخص" انتخاب شود، درخواست وارد کردن تعداد را ارسال می‌کند.
    """
    query = update.callback_query
    await query.answer()

    tool_prefix = context.user_data.get('tool_prefix')
    if not tool_prefix:
        logger.error("tool_prefix not found in user_data for tool_account_count_method_selected.")
        await query.edit_message_text("خطای داخلی: اطلاعات ابزار یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=build_tools_menu())
        return ConversationHandler.END

    selection_mode = query.data.replace(f"{tool_prefix}_", "")
    context.user_data['tool_account_selection_mode'] = selection_mode

    if selection_mode == "use_all":
        logger.info(f"Tool {tool_prefix}: User selected 'use_all' accounts.")
        await query.edit_message_text(text=f"۳. {target_prompt}", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return TOOL_ASK_TARGET_INPUT
    elif selection_mode == "specify_count":
        filtered_accounts_count = len(context.user_data.get('filtered_accounts_for_tool', []))
        logger.info(f"Tool {tool_prefix}: User selected 'specify_count'.")
        await query.edit_message_text(
            text=f"۳. لطفاً تعداد اکانت‌هایی که می‌خواهید از بین {filtered_accounts_count} اکانت موجود استفاده شود را وارد کنید:",
            reply_markup=build_cancel_button(callback_data=cancel_cb)
        )
        return TOOL_ASK_SPECIFIC_COUNT
    else:
        logger.warning(f"Invalid selection mode: {selection_mode} for tool {tool_prefix}")
        await query.edit_message_text("خطای داخلی: روش انتخاب نامعتبر.", reply_markup=build_tools_menu())
        return ConversationHandler.END

async def tool_specific_account_count_received(update: Update, context: ContextTypes.DEFAULT_TYPE, target_prompt: str, cancel_cb: str) -> int:
    """
    پس از دریافت تعداد مشخص اکانت از کاربر.
    تعداد را اعتبارسنجی کرده و سپس درخواست هدف ابزار را ارسال می‌کند.
    """
    tool_prefix = context.user_data.get('tool_prefix')
    if not tool_prefix:
        logger.error("tool_prefix not found in user_data for tool_specific_account_count_received.")
        await update.message.reply_text("خطای داخلی: اطلاعات ابزار یافت نشد. لطفاً دوباره تلاش کنید.", reply_markup=build_tools_menu())
        return ConversationHandler.END

    try:
        count_to_use = int(update.message.text.strip())
        filtered_accounts = context.user_data.get('filtered_accounts_for_tool', [])
        available_count = len(filtered_accounts)

        if count_to_use <= 0:
            await update.message.reply_text("تعداد باید یک عدد مثبت باشد. لطفاً دوباره وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
            return TOOL_ASK_SPECIFIC_COUNT
        if count_to_use > available_count:
            await update.message.reply_text(
                f"تعداد درخواستی ({count_to_use}) بیشتر از تعداد اکانت‌های موجود ({available_count}) است. لطفاً تعداد کمتری وارد کنید یا 'لغو' را بزنید:",
                reply_markup=build_cancel_button(callback_data=cancel_cb)
            )
            return TOOL_ASK_SPECIFIC_COUNT

        context.user_data['tool_specific_account_count'] = count_to_use
        logger.info(f"Tool {tool_prefix}: User wants to use {count_to_use} specific accounts.")
        await update.message.reply_text(text=f"۴. {target_prompt}", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return TOOL_ASK_TARGET_INPUT

    except ValueError:
        await update.message.reply_text("ورودی نامعتبر است. لطفاً تعداد را به صورت عددی وارد کنید:", reply_markup=build_cancel_button(callback_data=cancel_cb))
        return TOOL_ASK_SPECIFIC_COUNT

def get_selected_accounts(context: ContextTypes.DEFAULT_TYPE, tool_prefix: str) -> list[dict]:
    """
    بر اساس اطلاعات ذخیره شده در user_data (فیلتر دسته، حالت انتخاب، تعداد مشخص)،
    لیست اکانت‌هایی که باید برای عملیات ابزار استفاده شوند را برمی‌گرداند.
    """
    if not tool_prefix:
        logger.error("get_selected_accounts called without tool_prefix in user_data.")
        return []

    filtered_accounts = context.user_data.get('filtered_accounts_for_tool', [])
    selection_mode = context.user_data.get('tool_account_selection_mode')

    if not filtered_accounts:
        logger.warning(f"Tool {tool_prefix}: No filtered accounts found in get_selected_accounts.")
        return []

    if selection_mode == "use_all":
        logger.info(f"Tool {tool_prefix}: Using all {len(filtered_accounts)} filtered accounts.")
        return filtered_accounts
    elif selection_mode == "specify_count":
        specific_count = context.user_data.get('tool_specific_account_count')
        if specific_count is None or not isinstance(specific_count, int) or specific_count <= 0:
            logger.error(f"Tool {tool_prefix}: Invalid specific_count ({specific_count}) in get_selected_accounts. Defaulting to all filtered accounts.")
            return filtered_accounts

        selected_subset = filtered_accounts[:specific_count]
        logger.info(f"Tool {tool_prefix}: Using {len(selected_subset)} (specified count) accounts from filtered list.")
        return selected_subset
    else:
        logger.error(f"Tool {tool_prefix}: Unknown account selection mode '{selection_mode}'. Returning empty list.")
        return []


#------------------ پایان توابع جا افتاده برای مدیریت جریان ابزارها 


def main() -> None: 
    init_db(); logger.info("دیتابیس با موفقیت بررسی/ایجاد شد.")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init) 
        .build()
    )

    # --- تعریف ConversationHandlers ---
    add_account_conv = ConversationHandler( 
        entry_points=[CallbackQueryHandler(accounts_add_start, pattern=r"^accounts_add_start$")],
        states={ ADD_ACC_ASK_CATEGORY: [CallbackQueryHandler(ask_category_selected, pattern=r"^add_acc_cat_(iranian|foreign)$")], ADD_ACC_ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone_received)], ADD_ACC_ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code_received)], ADD_ACC_ASK_2FA_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_2fa_pass_received)],},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^(add_account_cancel_to_accounts_menu|cancel_to_accounts_menu_generic)$"), CommandHandler("cancel", cancel_conversation)],
        name=ADD_ACCOUNT_CONV, per_user=True, per_chat=True,
    )
    # --- ConversationHandler برای نمایش لیست اکانت‌ها ---
    async def list_accounts_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نقطه ورود برای نمایش لیست اکانت‌ها - نمایش دکمه‌های انتخاب دسته."""
        query = update.callback_query
        await query.answer()
        context.user_data.clear() # پاک کردن user_data های قبلی این مکالمه
        context.user_data['_active_conversation_name'] = LIST_ACCOUNTS_CONV

        keyboard = [
            [InlineKeyboardButton("🇮🇷 اکانت‌های ایرانی", callback_data="list_acc_cat_iranian")],
            [InlineKeyboardButton("🌍 اکانت‌های خارجی", callback_data="list_acc_cat_foreign")],
            [InlineKeyboardButton("💠 همه اکانت‌ها", callback_data="list_acc_cat_all")],
            [InlineKeyboardButton("⬅️ بازگشت به منوی اکانت‌ها", callback_data="list_acc_cancel_to_accounts_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "لطفاً دسته‌بندی اکانت‌هایی که می‌خواهید لیست شوند را انتخاب کنید:",
            reply_markup=reply_markup
        )
        return LIST_ACC_SELECT_CATEGORY

    async def list_accounts_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پس از انتخاب دسته، اکانت‌ها را گرفته و صفحه اول را نمایش می‌دهد."""
        query = update.callback_query
        await query.answer()
        
        category_filter_cb = query.data.replace("list_acc_cat_", "") # iranian, foreign, all
        category_filter_for_db = None
        if category_filter_cb == "iranian": category_filter_for_db = "iranian"
        elif category_filter_cb == "foreign": category_filter_for_db = "foreign"
        # برای "all"، category_filter_for_db همان None باقی می‌ماند

        context.user_data['list_accounts_current_category_filter_cb'] = category_filter_cb
        context.user_data['list_accounts_current_category_filter_db'] = category_filter_for_db

        all_cat_accounts = get_all_accounts(category_filter=category_filter_for_db)
        # active_cat_accounts = [acc for acc in all_cat_accounts if acc.get('is_active', 1)]
        # context.user_data[f'list_accounts_cat_{category_filter_cb}'] = active_cat_accounts
        context.user_data[f'list_accounts_cat_{category_filter_cb}'] = all_cat_accounts # نمایش همه، فعال و غیرفعال
        
        context.user_data['list_accounts_current_page'] = 0
        
        return await display_accounts_page(update, context, category_filter_cb)


    async def list_accounts_pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """مدیریت دکمه‌های صفحه بعد/قبل."""
        query = update.callback_query
        await query.answer()
        
        action_parts = query.data.split("_") # e.g. list_acc_page_next_iranian
        action = action_parts[3] # next or prev
        category_filter_cb = action_parts[4] # iranian, foreign, all
        
        current_page = context.user_data.get('list_accounts_current_page', 0)
        
        if action == "next":
            current_page += 1
        elif action == "prev":
            current_page -= 1
        
        context.user_data['list_accounts_current_page'] = current_page
        return await display_accounts_page(update, context, category_filter_cb)

    async def show_account_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش جزئیات یک اکانت خاص."""
        query = update.callback_query
        await query.answer()
        
        account_db_id = int(query.data.replace("list_acc_detail_", ""))
        account_details = get_account_details_by_id(account_db_id)
        
        current_page_num = context.user_data.get('list_accounts_current_page', 0) # برای دکمه بازگشت به لیست
        current_category_filter_cb = context.user_data.get('list_accounts_current_category_filter_cb', 'all')


        if not account_details:
            await query.edit_message_text("خطا: اکانت یافت نشد.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت به لیست", callback_data=f"list_acc_back_to_page_{current_page_num}_{current_category_filter_cb}")]]))
            return LIST_ACC_SHOW_PAGE # یا یک state خطا
        
        status_emoji = "✅ فعال" if account_details.get('is_active', 1) else "❌ غیرفعال"
        category_display = account_details.get('account_category', 'نامشخص')
        category_text = "🇮🇷 ایرانی" if category_display == 'iranian' else "🌍 خارجی" if category_display == 'foreign' else "❔ نامشخص"
        username_display = f"@{account_details.get('username')}" if account_details.get('username') else "<i>(بدون یوزرنیم)</i>"
        added_at_full = account_details.get('added_at', 'N/A')
        added_at_short = added_at_full.split('.')[0] if '.' in added_at_full else added_at_full

        text = f"📄 **جزئیات اکانت:**\n\n"
        text += f"📞 **شماره تلفن:** <code>{account_details.get('phone_number')}</code>\n"
        text += f"👤 **یوزرنیم:** {username_display}\n"
        text += f"🆔 **آیدی تلگرام:** <code>{account_details.get('user_id', 'N/A')}</code>\n"
        text += f"🗂 **دسته‌بندی:** {category_text}\n"
        text += f"🚦 **وضعیت:** {status_emoji}\n"
        text += f"🗓 **تاریخ افزودن:** {added_at_short}\n"
        text += f"📄 **فایل نشست:** <code>{os.path.basename(account_details.get('session_file', 'N/A'))}</code>\n"
        
        keyboard = [
            [InlineKeyboardButton(f"⬅️ بازگشت به لیست (صفحه {current_page_num + 1})", callback_data=f"list_acc_back_to_page_{current_page_num}_{current_category_filter_cb}")],
            [InlineKeyboardButton("🔁 انتخاب مجدد دسته‌بندی", callback_data="list_acc_back_to_cat_select")],
            [InlineKeyboardButton("🏠 بازگشت به منوی اکانت‌ها", callback_data="list_acc_cancel_to_accounts_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return LIST_ACC_SHOW_PAGE # کاربر پس از دیدن جزئیات، به همان صفحه لیست برمی‌گردد

    async def list_accounts_cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """لغو عملیات لیست کردن و بازگشت به منوی اکانت‌ها."""
        query = update.callback_query
        await query.answer()
        context.user_data.clear()
        await query.edit_message_text("بازگشت به منوی مدیریت اکانت‌ها:", reply_markup=build_accounts_menu())
        return ConversationHandler.END

    list_accounts_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(list_accounts_entry_point, pattern=r"^accounts_list$")],
        states={
            LIST_ACC_SELECT_CATEGORY: [
                CallbackQueryHandler(list_accounts_category_selected, pattern=r"^list_acc_cat_(iranian|foreign|all)$")
            ],
            LIST_ACC_SHOW_PAGE: [
                CallbackQueryHandler(list_accounts_pagination_handler, pattern=r"^list_acc_page_(next|prev)_(iranian|foreign|all)$"),
                CallbackQueryHandler(show_account_details_callback, pattern=r"^list_acc_detail_(\d+)$"),
                CallbackQueryHandler(list_accounts_entry_point, pattern=r"^list_acc_back_to_cat_select$"), # بازگشت به انتخاب دسته
                # برای بازگشت از جزئیات به صفحه لیست خاص
                CallbackQueryHandler(lambda u,c: display_accounts_page(u,c, c.user_data.get('list_accounts_current_category_filter_cb', 'all')), 
                                     pattern=r"^list_acc_back_to_page_\d+_(iranian|foreign|all)$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(list_accounts_cancel_to_menu, pattern=r"^list_acc_cancel_to_accounts_menu$"),
            CommandHandler("cancel", list_accounts_cancel_to_menu) # یا cancel_conversation عمومی
        ],
        name=LIST_ACCOUNTS_CONV,
        per_user=True,
        per_chat=True,
    )
    #--------------پايان
    def build_tool_conv_handler(tool_name_fa, tool_prefix, tool_conv_const, target_prompt, reporter_ask_reason_state=None, reporter_reason_selected_func=None, reporter_custom_reason_state=None, reporter_custom_reason_func=None, reporter_reason_pattern=None, spammer_ask_count_state=None, spammer_count_func=None, spammer_ask_text_state=None, spammer_text_func=None, spammer_ask_delay_state=None, spammer_delay_func=None, add_admin_ask_users_state=None, add_admin_users_func=None):
        cancel_cb = f"{tool_prefix}_cancel_to_tools_menu"
        states = {
            TOOL_ASK_ACCOUNT_CATEGORY_FILTER: [CallbackQueryHandler(lambda u, c: tool_account_category_filter_selected(u, c, tool_name_fa, cancel_cb), pattern=f"^{tool_prefix}_filter_(iranian|foreign|all)$")],
            TOOL_SELECT_ACCOUNT_METHOD: [CallbackQueryHandler(lambda u, c: tool_account_count_method_selected(u, c, target_prompt, cancel_cb), pattern=f"^{tool_prefix}_(use_all|specify_count)$")],
            TOOL_ASK_SPECIFIC_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: tool_specific_account_count_received(u, c, target_prompt, cancel_cb))],
            TOOL_ASK_TARGET_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tool_target_input_received)],
        }
        if reporter_ask_reason_state and reporter_reason_selected_func and reporter_reason_pattern: states[reporter_ask_reason_state] = [CallbackQueryHandler(reporter_reason_selected_func, pattern=reporter_reason_pattern)]
        if reporter_custom_reason_state and reporter_custom_reason_func: states[reporter_custom_reason_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, reporter_custom_reason_func)]
        if spammer_ask_count_state and spammer_count_func: states[spammer_ask_count_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, spammer_count_func)]
        if spammer_ask_text_state and spammer_text_func: states[spammer_ask_text_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, spammer_text_func)]
        if spammer_ask_delay_state and spammer_delay_func: states[spammer_ask_delay_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, spammer_delay_func)]
        if add_admin_ask_users_state and add_admin_users_func: states[add_admin_ask_users_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_users_func)]
        
        return ConversationHandler(
            entry_points=[CallbackQueryHandler(lambda u,c: tool_entry_point(u,c, tool_name_fa, tool_prefix, cancel_cb, tool_conv_const) , pattern=f"^tools_{tool_prefix}_entry$")],
            states=states, 
            fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=f"^{cancel_cb}$"), CommandHandler("cancel", cancel_conversation)],
            name=tool_conv_const, 
            per_user=True, 
            per_chat=True,
        )

    joiner_tool_conv = build_tool_conv_handler("پیوستن به کانال/گروه", "joiner", JOINER_TOOL_CONV, "🔗 لینک/آیدی کانال/گروه برای پیوستن:")
    leaver_tool_conv = build_tool_conv_handler("ترک کانال/گروه", "leaver", LEAVER_TOOL_CONV, "🚪 لینک/آیدی کانال/گروه برای ترک:")
    blocker_tool_conv = build_tool_conv_handler("بلاک کردن کاربر", "blocker", BLOCKER_TOOL_CONV, "🚫 آیدی عددی یا یوزرنیم کاربر برای بلاک:")
    reporter_user_tool_conv = build_tool_conv_handler(
        "ریپورت کردن کاربر", "reporter_user", REPORTER_USER_TOOL_CONV, "🗣 آیدی عددی یا یوزرنیم کاربر برای ریپورت:",
        reporter_ask_reason_state=REPORTER_USER_ASK_REASON, reporter_reason_selected_func=reporter_user_reason_selected,
        reporter_custom_reason_state=REPORTER_USER_ASK_CUSTOM_REASON, reporter_custom_reason_func=reporter_user_custom_reason_received,
        reporter_reason_pattern=f"^{config.REPORT_REASON_CALLBACK_PREFIX_USER}(spam|violence|pornography|child_abuse|fake_account|drugs|other)$"
    )
    reporter_chat_tool_conv = build_tool_conv_handler(
        "ریپورت کانال/گروه", "reporter_chat", REPORTER_CHAT_TOOL_CONV, "📢 لینک یا آیدی کانال/گروه برای ریپورت:",
        reporter_ask_reason_state=REPORTER_CHAT_ASK_REASON, reporter_reason_selected_func=reporter_chat_reason_selected,
        reporter_custom_reason_state=REPORTER_CHAT_ASK_CUSTOM_REASON, reporter_custom_reason_func=reporter_chat_custom_reason_received,
        reporter_reason_pattern=f"^{config.REPORT_REASON_CALLBACK_PREFIX_CHAT}(spam|violence|pornography|child_abuse|copyright|fake_chat|drugs|geo_irrelevant|other)$"
    )
    spammer_tool_conv = build_tool_conv_handler(
        "ارسال پیام اسپم", "spammer", SPAMMER_TOOL_CONV, "🎯 آیدی عددی یا یوزرنیم کاربر/چت هدف برای اسپم:",
        spammer_ask_count_state=SPAMMER_ASK_MESSAGE_COUNT, spammer_count_func=spammer_count_received,
        spammer_ask_text_state=SPAMMER_ASK_MESSAGE_TEXT, spammer_text_func=spammer_text_received,
        spammer_ask_delay_state=SPAMMER_ASK_DELAY, spammer_delay_func=spammer_delay_received_and_execute
    )
    remover_tool_conv = build_tool_conv_handler("حذف اعضا از گروه (با اکانت‌ها)", "remover", REMOVER_TOOL_CONV, "🗑 لینک یا آیدی گروه برای حذف اعضا:")
    add_admin_tool_conv = build_tool_conv_handler(
        "ارتقا به ادمین در گروه (با اکانت‌ها)", "add_admin", ADD_ADMIN_TOOL_CONV, "👑 لینک یا آیدی گروهی که می‌خواهید در آن ادمین اضافه کنید:",
        add_admin_ask_users_state=ADD_ADMIN_ASK_USERS_TO_PROMOTE, add_admin_users_func=add_admin_users_to_promote_received
    )
    
    bot_op_spam_group_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_op_spam_group_start, pattern=r"^bot_op_spam_group_start$")],
        states={BOT_OP_SPAM_GROUP_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_group_target_received)], BOT_OP_SPAM_GROUP_ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_group_count_received)], BOT_OP_SPAM_GROUP_ASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_group_text_received)], BOT_OP_SPAM_GROUP_ASK_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_group_delay_received_and_execute)],},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_spam_group_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_SPAM_GROUP_CONV, per_user=True, per_chat=True
    )
    bot_op_spam_channel_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_op_spam_channel_start, pattern=r"^bot_op_spam_channel_start$")],
        states={BOT_OP_SPAM_CHANNEL_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_channel_target_received)], BOT_OP_SPAM_CHANNEL_ASK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_channel_count_received)], BOT_OP_SPAM_CHANNEL_ASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_channel_text_received)], BOT_OP_SPAM_CHANNEL_ASK_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_spam_channel_delay_received_and_execute)],},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_spam_channel_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_SPAM_CHANNEL_CONV, per_user=True, per_chat=True
    )
    bot_op_adv_remove_group_members_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_op_adv_remove_group_members_start, pattern=r"^bot_op_adv_remove_group_members_start$")],
        states={BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_adv_remove_group_members_target_received)], BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_HELPER_ACCOUNT: [CallbackQueryHandler(bot_op_adv_remove_group_members_helper_selected, pattern=r"^bot_op_adv_remove_group_members_select_helper_(\d+|no_helpers)$")], BOT_OP_ADV_REMOVE_GROUP_MEMBERS_ASK_CONFIRM: [CallbackQueryHandler(bot_op_adv_remove_group_members_confirmed_final, pattern=r"^bot_op_adv_remove_group_members_confirm_final_removal$")],},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_adv_remove_group_members_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_ADV_REMOVE_GROUP_MEMBERS_CONV, per_user=True, per_chat=True
    )
    bot_op_adv_remove_channel_members_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_op_adv_remove_channel_members_start, pattern=r"^bot_op_adv_remove_channel_members_start$")],
        states={BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_adv_remove_channel_members_target_received)], BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_HELPER_ACCOUNT: [CallbackQueryHandler(bot_op_adv_remove_channel_members_helper_selected, pattern=r"^bot_op_adv_remove_channel_members_select_helper_(\d+|no_helpers)$")], BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_ASK_CONFIRM: [CallbackQueryHandler(bot_op_adv_remove_channel_members_confirmed_final, pattern=r"^bot_op_adv_remove_channel_members_confirm_final_removal$")],},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_adv_remove_channel_members_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_ADV_REMOVE_CHANNEL_MEMBERS_CONV, per_user=True, per_chat=True
    )
    add_admin_group_bot_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: bot_op_add_admin_chat_start(u, c, "group"), pattern=r"^bot_op_add_admin_group_start$")],
        states={
            BOT_OP_ADD_ADMIN_CHAT_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_add_admin_chat_target_received)],
            BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_CATEGORY: [CallbackQueryHandler(bot_op_add_admin_chat_acc_category_selected, pattern=r"^bot_op_add_admin_group_filter_(iranian|foreign|all)$")],
            BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_COUNT_METHOD: [CallbackQueryHandler(bot_op_add_admin_chat_acc_count_method_selected, pattern=r"^bot_op_add_admin_group_(use_all|specify_count)$")],
            BOT_OP_ADD_ADMIN_CHAT_ASK_USERS_TO_PROMOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_add_admin_chat_users_to_promote_received)],
            BOT_OP_ADD_ADMIN_CHAT_ASK_CONFIRM: [CallbackQueryHandler(bot_op_add_admin_chat_execute, pattern=r"^bot_op_add_admin_group_confirm_final_promotion$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_add_admin_group_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_ADD_ADMIN_GROUP_CONV, per_user=True, per_chat=True
    )
    add_admin_channel_bot_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: bot_op_add_admin_chat_start(u, c, "channel"), pattern=r"^bot_op_add_admin_channel_start$")],
        states={
            BOT_OP_ADD_ADMIN_CHAT_ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_add_admin_chat_target_received)],
            BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_CATEGORY: [CallbackQueryHandler(bot_op_add_admin_chat_acc_category_selected, pattern=r"^bot_op_add_admin_channel_filter_(iranian|foreign|all)$")],
            BOT_OP_ADD_ADMIN_CHAT_ASK_ACC_COUNT_METHOD: [CallbackQueryHandler(bot_op_add_admin_chat_acc_count_method_selected, pattern=r"^bot_op_add_admin_channel_(use_all|specify_count)$")],
            BOT_OP_ADD_ADMIN_CHAT_ASK_USERS_TO_PROMOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_op_add_admin_chat_users_to_promote_received)],
            BOT_OP_ADD_ADMIN_CHAT_ASK_CONFIRM: [CallbackQueryHandler(bot_op_add_admin_chat_execute, pattern=r"^bot_op_add_admin_channel_confirm_final_promotion$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern=r"^bot_op_add_admin_channel_cancel_to_bot_operations_menu$"), CommandHandler("cancel", cancel_conversation)],
        name=BOT_OP_ADD_ADMIN_CHANNEL_CONV, per_user=True, per_chat=True
    )
    settings_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(settings_entry, pattern=r"^main_menu_settings$")], # ورود از منوی اصلی
        states={
            SETTINGS_MENU: [CallbackQueryHandler(settings_menu_handler)],
            SETTINGS_API_MENU: [CallbackQueryHandler(settings_api_menu_handler, pattern=r"^(settings_api_management|settings_api_add_new|settings_api_remove_select|settings_api_confirm_remove_\d+|main_menu_settings_from_action|settings_cancel_to_api_menu_no_edit)$")], # پترن برای همه callback های این منو
            SETTINGS_ASK_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_api_id_received)],
            SETTINGS_ASK_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_api_hash_received)],
            SETTINGS_ADMINS_MENU: [CallbackQueryHandler(settings_admins_menu_handler, pattern=r"^(settings_admins_management|settings_admins_add_db|settings_admins_remove_db_select|settings_admin_remove_db_confirm_\d+|settings_admins_list|settings_cancel_to_admins_menu_no_edit)$")],
            SETTINGS_ADMINS_ASK_ADD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_admin_add_id_received)],
            SETTINGS_SPAM_MENU: [CallbackQueryHandler(settings_spam_menu_handler, pattern=r"^(settings_spam_keywords_management|settings_spam_add_keyword|settings_spam_remove_select_keyword|settings_spam_confirm_remove_.*|settings_cancel_to_spam_menu_no_edit)$")],
            SETTINGS_SPAM_ASK_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_spam_add_received)],
            SETTINGS_DELAY_MENU: [CallbackQueryHandler(settings_delay_menu_handler, pattern=r"^(settings_delay_management|settings_delay_change_value)$")],
            SETTINGS_DELAY_ASK_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_delay_value_received)],
        },
        fallbacks=[
    CallbackQueryHandler(cancel_conversation, pattern=r"^general_back_to_main_menu$"),
    CallbackQueryHandler(settings_cancel_to_api_menu, pattern=r"^settings_cancel_to_api_menu$"),
    CallbackQueryHandler(settings_cancel_to_admins_menu, pattern=r"^settings_cancel_to_admins_menu$"),
    CallbackQueryHandler(settings_cancel_to_spam_menu, pattern=r"^settings_cancel_to_spam_menu$"),
    CallbackQueryHandler(settings_cancel_to_delay_menu, pattern=r"^settings_cancel_to_delay_menu$"),
    CallbackQueryHandler(lambda u,c: settings_entry(u,c), pattern=r"^settings_cancel_to_main_settings_menu$"), # <--- این باید به منوی اصلی تنظیمات برگردد
    CommandHandler("cancel", cancel_conversation)
        ],
        name=SETTINGS_CONV,
        per_user=True,
        per_chat=True
    )
    application.add_handler(restore_conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(add_account_conv)
    application.add_handler(list_accounts_conv)
    application.add_handler(joiner_tool_conv)
    application.add_handler(leaver_tool_conv)
    application.add_handler(blocker_tool_conv)
    application.add_handler(reporter_user_tool_conv)
    application.add_handler(reporter_chat_tool_conv)
    application.add_handler(spammer_tool_conv)
    application.add_handler(remover_tool_conv) 
    application.add_handler(add_admin_tool_conv) 
    application.add_handler(bot_op_spam_group_conv_handler)
    application.add_handler(bot_op_spam_channel_conv_handler)
    application.add_handler(bot_op_adv_remove_group_members_conv_handler)
    application.add_handler(bot_op_adv_remove_channel_members_conv_handler)
    application.add_handler(add_admin_group_bot_conv)
    application.add_handler(add_admin_channel_bot_conv)
    application.add_handler(settings_conv_handler)
    application.add_handler(CallbackQueryHandler(menu_router)) 
    application.add_error_handler(error_handler)
    

    logger.info("ربات در حال راه‌اندازی (Polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
