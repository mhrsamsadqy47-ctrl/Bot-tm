# data/database_ops.py
import sqlite3
import logging
import json # برای ذخیره لیست API ها و ادمین ها
import config

logger = logging.getLogger(__name__)

# --- توابع مربوط به اکانت‌ها ---
def add_account_to_db(phone_number: str, user_id: int, username: str | None, session_file: str, account_category: str) -> bool:
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO accounts (phone_number, user_id, username, session_file, account_category, is_active, added_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (phone_number, user_id, username, session_file, account_category, 1)
        )
        conn.commit()
        logger.info(f"Account {phone_number} (Category: {account_category}, User ID: {user_id}) successfully added to database. Session: {session_file}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Account {phone_number} (User ID: {user_id}) already exists in database or another integrity constraint failed.")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error while adding account {phone_number}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_accounts(category_filter: str | None = None) -> list[dict]:
    accounts_list = []
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT id, phone_number, user_id, username, session_file, account_category, is_active, added_at FROM accounts"
        params = []
        if category_filter and category_filter in ['iranian', 'foreign']:
            query += " WHERE account_category = ?"
            params.append(category_filter)
        query += " ORDER BY added_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        for row in rows:
            accounts_list.append(dict(row))
        
    except sqlite3.Error as e:
        logger.error(f"Database error fetching accounts with filter '{category_filter}': {e}")
    finally:
        if conn:
            conn.close()
    return accounts_list

def get_account_details_by_id(account_db_id: int) -> dict | None:
    account_details = None
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone_number, user_id, username, session_file, account_category, is_active FROM accounts WHERE id = ?", (account_db_id,))
        row = cursor.fetchone()
        if row:
            account_details = dict(row)
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching account DB ID {account_db_id}: {e}")
    finally:
        if conn:
            conn.close()
    return account_details

def delete_account_from_db(account_db_id: int) -> bool:
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_db_id,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Account with DB ID {account_db_id} successfully deleted from database.")
            return True
        else:
            logger.warning(f"No account found with DB ID {account_db_id} to delete.")
            return False
    except sqlite3.Error as e:
        logger.error(f"Database error while deleting account DB ID {account_db_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- توابع برای جدول bot_settings ---
def get_bot_setting(key: str, default_value: any = None) -> any:
    """مقدار یک تنظیم خاص را از جدول bot_settings می‌خواند. اگر default_value مشخص شده باشد و کلید یافت نشود یا خطای JSON رخ دهد، آن را برمیگرداند."""
    value_str = None
    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            value_str = row[0]
            
    except sqlite3.Error as e:
        logger.error(f"Database error fetching bot setting '{key}': {e}")
        # در صورت خطای دیتابیس، مقدار پیش‌فرض را برمی‌گردانیم
        return default_value
    finally:
        if conn:
            conn.close()

    if value_str is None:
        return default_value

    
    json_keys = ['TELETHON_API_KEYS', 'ADMIN_IDS_DB', 'SPAM_KEYWORDS_DB']
    if key in json_keys:
        try:
            # اگر مقدار رشته خالی است و پیش‌فرض یک لیست یا دیکشنری است، پیش‌فرض را برگردان
            if not value_str.strip() and isinstance(default_value, (list, dict)):
                logger.warning(f"Empty string found for JSON key '{key}', returning default value.")
                return default_value
            return json.loads(value_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON for bot setting '{key}': {e}. Value was: '{value_str[:100]}...'. Returning default value.")
            # در صورت خطای دیکد کردن JSON، همیشه مقدار پیش‌فرض را برگردان
            return default_value
    return value_str


def set_bot_setting(key: str, value: any) -> bool:
    """یک تنظیم را در جدول bot_settings ذخیره یا به‌روزرسانی می‌کند. اگر مقدار لیست یا دیکشنری باشد، به JSON تبدیل میشود."""
    value_to_store = value
    is_json_type = isinstance(value, (list, dict))

    if is_json_type:
        try:
            value_to_store = json.dumps(value, ensure_ascii=False) # ensure_ascii برای پشتیبانی بهتر از فارسی
        except TypeError as e:
            logger.error(f"Could not serialize value for key '{key}' to JSON: {e}. Value type: {type(value)}. Aborting set.")
            
            return False
    elif not isinstance(value, (str, int, float, bool)) and value is not None : # برای انواع پایه دیگر یا None
        
        logger.warning(f"Value for key '{key}' is not a basic type or JSON serializable, storing as string: {type(value)}")
        value_to_store = str(value)
    

    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value_to_store))
        conn.commit()
        
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error setting bot setting '{key}': {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- توابع مدیریت API Keys ---
def get_api_keys() -> list[dict]:
    """لیست API ID/Hash ها را از دیتابیس میخواند."""
    return get_bot_setting('TELETHON_API_KEYS', []) # مقدار پیشفرض لیست خالی

def add_api_key(api_id: int, api_hash: str) -> bool:
    """یک جفت API ID/Hash جدید به لیست اضافه میکند."""
    keys = get_api_keys()
    # جلوگیری از افزودن موارد تکراری (بر اساس api_id)
    if any(k.get('api_id') == api_id for k in keys):
        logger.warning(f"API ID {api_id} already exists. Not adding.")
        return False
    keys.append({"api_id": api_id, "api_hash": api_hash})
    return set_bot_setting('TELETHON_API_KEYS', keys)

def remove_api_key(api_id_to_remove: int) -> bool:
    """یک جفت API ID/Hash را از لیست بر اساس api_id حذف میکند."""
    keys = get_api_keys()
    initial_len = len(keys)
    keys = [k for k in keys if k.get('api_id') != api_id_to_remove]
    if len(keys) < initial_len:
        return set_bot_setting('TELETHON_API_KEYS', keys)
    logger.warning(f"API ID {api_id_to_remove} not found for removal.")
    return False

# --- توابع مدیریت ادمین‌ها ---
def get_db_admins() -> list[int]:
    """لیست شناسه عددی ادمین‌ها را از دیتابیس میخواند."""
    admin_ids_json = get_bot_setting('ADMIN_IDS_DB')
    if isinstance(admin_ids_json, list): 
        return admin_ids_json
    elif isinstance(admin_ids_json, str): # اگر رشته JSON باشد
        try:
            return json.loads(admin_ids_json)
        except json.JSONDecodeError:
            logger.error("Failed to decode ADMIN_IDS_DB from JSON.")
            return []
    return [] # مقدار پیشفرض لیست خالی

def add_db_admin(admin_id: int) -> bool:
    """یک ادمین جدید به لیست ادمین‌های دیتابیس اضافه می‌کند."""
    admins = get_db_admins()
    if admin_id not in admins:
        admins.append(admin_id)
        return set_bot_setting('ADMIN_IDS_DB', admins)
    logger.info(f"Admin ID {admin_id} already in DB admin list.")
    return True # اگر از قبل وجود داشت هم موفقیت آمیز است

def remove_db_admin(admin_id_to_remove: int) -> bool:
    """یک ادمین را از لیست ادمین‌های دیتابیس حذف می‌کند."""
    admins = get_db_admins()
    if admin_id_to_remove in admins:
        admins.remove(admin_id_to_remove)
        return set_bot_setting('ADMIN_IDS_DB', admins)
    logger.warning(f"Admin ID {admin_id_to_remove} not found in DB admin list for removal.")
    return False

# --- توابع مدیریت کلمات اسپم ---
def get_spam_keywords() -> list[str]:
    """لیست کلمات کلیدی اسپم را از دیتابیس میخواند."""
    keywords_json = get_bot_setting('SPAM_KEYWORDS_DB')
    if isinstance(keywords_json, list):
        return keywords_json
    elif isinstance(keywords_json, str):
        try:
            return json.loads(keywords_json)
        except json.JSONDecodeError:
            logger.error("Failed to decode SPAM_KEYWORDS_DB from JSON.")
            return []
    return [] # مقدار پیشفرض لیست خالی

def add_spam_keyword(keyword: str) -> bool:
    """یک کلمه کلیدی جدید به لیست اسپم اضافه می‌کند."""
    keywords = get_spam_keywords()
    normalized_keyword = keyword.strip().lower()
    if normalized_keyword and normalized_keyword not in [k.lower() for k in keywords]:
        keywords.append(keyword.strip()) # ذخیره با حروف اصلی اما بررسی بدون توجه به حروف
        return set_bot_setting('SPAM_KEYWORDS_DB', keywords)
    elif not normalized_keyword:
        logger.warning("Cannot add empty spam keyword.")
        return False
    else:
        logger.info(f"Spam keyword '{keyword}' already exists.")
        return True

def remove_spam_keyword(keyword_to_remove: str) -> bool:
    """یک کلمه کلیدی را از لیست اسپم حذف می‌کند (بدون توجه به بزرگی و کوچکی حروف)."""
    keywords = get_spam_keywords()
    initial_len = len(keywords)
    normalized_keyword_to_remove = keyword_to_remove.strip().lower()
    keywords = [k for k in keywords if k.strip().lower() != normalized_keyword_to_remove]
    if len(keywords) < initial_len:
        return set_bot_setting('SPAM_KEYWORDS_DB', keywords)
    logger.warning(f"Spam keyword '{keyword_to_remove}' not found for removal.")
    return False
