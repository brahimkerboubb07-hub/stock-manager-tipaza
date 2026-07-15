import os
import psycopg2
from psycopg2.extras import RealDictCursor

# رابط قاعدة البيانات من متغيرات البيئة
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:Brahkingdz1134@db.ozrbnxfabnuhxpitgbrt.supabase.co:5432/postgres"
    print("⚠️ Using default Supabase URL")

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def init_db():
    """إنشاء الجداول إذا لم تكن موجودة"""
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to database")
        return
    
    cur = conn.cursor()
    
    # جدول users (بسيط)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            theme TEXT DEFAULT 'light',
            full_name TEXT
        )
    """)
    
    # إضافة مستخدم admin إذا لم يكن موجوداً
    cur.execute("""
        INSERT INTO users (username, password, role, theme, full_name) 
        VALUES ('admin', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'مدير', 'light', 'مدير النظام')
        ON CONFLICT (username) DO NOTHING
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully")

# تهيئة قاعدة البيانات عند بدء التشغيل
init_db()
