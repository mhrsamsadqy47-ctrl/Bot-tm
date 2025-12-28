# data/database_setup.py
import sqlite3
import logging
import config

logger = logging.getLogger(__name__) 

def init_db():
    conn = None # مقداردهی اولیه conn
    try:
        conn = sqlite3.connect(config.DATABASE_NAME)
        cursor = conn.cursor()

        # جدول برای ذخیره اطلاعات اکانت‌های تلگرامی اضافه شده
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            user_id INTEGER UNIQUE,
            username TEXT,
            session_file TEXT NOT NULL,
            account_category TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # جدول برای تنظیمات ربات (API Keys، ادمین‌های دیتابیس، کلمات اسپم و سایر تنظیمات به صورت JSON در اینجا ذخیره می‌شوند)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')

        

        conn.commit()
        # تغییر پیام لاگ برای وضوح بیشتر
        logger.info("دیتابیس و جداول ضروری (accounts, bot_settings) با موفقیت بررسی/ایجاد شدند.")
    except sqlite3.Error as e:
        logger.error(f"خطا در اتصال یا ایجاد جداول دیتابیس: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # برای اجرای مستقیم و ساخت اولیه دیتابیس
    # اضافه کردن basicConfig برای لاگ در صورت اجرای مستقیم
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    init_db()
    print("Database (accounts, bot_settings) initialized.")
