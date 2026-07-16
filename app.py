# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_file, jsonify
import os
from datetime import datetime, timedelta
import hashlib
import json
import pandas as pd
from io import BytesIO
import shutil
from collections import defaultdict
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import sys

app = Flask(__name__)
app.secret_key = 'tipaza_secret_key_2026_v3'
app.permanent_session_lifetime = timedelta(minutes=30)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(os.path.join(BASE_DIR, 'static'), exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# -------------------- DATABASE CONNECTION --------------------
def get_db_url():
    """الحصول على رابط قاعدة البيانات من متغيرات البيئة"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        # استخدام الرابط المحلي للتجربة
        database_url = "postgresql://postgres:Tipaza0777600442@aws-0-eu-central-1.pooler.supabase.com:6543/tipaza_db"
        print("⚠️ DATABASE_URL not set, using default Supabase URL")
    return database_url

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    url = get_db_url()
    try:
        conn = psycopg2.connect(url)
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
    
    # إنشاء الجداول
    tables = [
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            theme TEXT DEFAULT 'light',
            full_name TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            item_name TEXT UNIQUE NOT NULL,
            quantity INTEGER NOT NULL,
            category TEXT NOT NULL,
            inventory_num TEXT,
            min_stock INTEGER DEFAULT 5,
            unit TEXT DEFAULT 'قطعة',
            price REAL DEFAULT 0,
            last_updated TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS discharges (
            id SERIAL PRIMARY KEY,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            receiver_id INTEGER,
            user_charged TEXT,
            date_time TEXT,
            category TEXT,
            inventory_num TEXT,
            notes TEXT,
            decharge_number TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS beneficiaries (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            grade TEXT,
            structure TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS general_inventory (
            id SERIAL PRIMARY KEY,
            ordre_num TEXT,
            inventory_num TEXT UNIQUE,
            designation TEXT,
            bureau_num TEXT,
            observation TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS maintenance_equipment (
            id SERIAL PRIMARY KEY,
            item_name TEXT,
            item_type TEXT,
            inventory_num TEXT UNIQUE,
            assigned_to TEXT,
            status TEXT DEFAULT 'available',
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id SERIAL PRIMARY KEY,
            equipment_id INTEGER,
            item_name TEXT,
            inventory_num TEXT,
            sent_date TEXT,
            repair_shop TEXT,
            issue_description TEXT,
            expected_return_date TEXT,
            actual_return_date TEXT,
            repair_cost REAL DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT 'sent',
            decharge_number TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            contact TEXT,
            address TEXT,
            created_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            supplier_id INTEGER,
            purchase_date TEXT,
            item_name TEXT,
            quantity REAL,
            unit_price REAL,
            total_price REAL,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            supplier_id INTEGER,
            payment_date TEXT,
            amount REAL,
            payment_method TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
        """
    ]
    
    for table_sql in tables:
        try:
            cur.execute(table_sql)
        except Exception as e:
            print(f"⚠️ Error creating table: {e}")
    
    # إضافة مستخدم افتراضي (admin / 1234)
    try:
        cur.execute("""
            INSERT INTO users (username, password, role, theme, full_name) 
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        """, ('admin', hash_password('1234'), 'مدير', 'light', 'مدير النظام'))
    except Exception as e:
        print(f"⚠️ Error adding default user: {e}")
    
    # إضافة مستفيدين افتراضيين
    try:
        cur.execute("SELECT COUNT(*) FROM beneficiaries")
        count = cur.fetchone()[0]
        if count == 0:
            beneficiaries = [
                ('أحمد علي', 'مدير', 'الإدارة'),
                ('كريمة بن سالم', 'رئيسة قسم', 'الموارد البشرية'),
                ('محمد لمين', 'موظف', 'التقني')
            ]
            for name, grade, structure in beneficiaries:
                cur.execute("INSERT INTO beneficiaries (full_name, grade, structure) VALUES (%s, %s, %s)", (name, grade, structure))
    except Exception as e:
        print(f"⚠️ Error adding default beneficiaries: {e}")
    
    # إضافة موردين افتراضيين
    try:
        cur.execute("SELECT COUNT(*) FROM suppliers")
        count = cur.fetchone()[0]
        if count == 0:
            suppliers = ['بودومة عمر', 'ولد ضي الله', 'sbi', 'مورد 4', 'مورد 5']
            for name in suppliers:
                cur.execute("INSERT INTO suppliers (name, contact, address, created_at) VALUES (%s, %s, %s, %s)", 
                           (name, '', '', datetime.now().isoformat()))
    except Exception as e:
        print(f"⚠️ Error adding default suppliers: {e}")
    
    # إضافة عناصر افتراضية للجرد العام
    try:
        cur.execute("SELECT COUNT(*) FROM general_inventory")
        count = cur.fetchone()[0]
        if count == 0:
            items = [
                ('1', '26-2015', 'Bureau + bibliothèque', '6', ''),
                ('2', '145-2009', 'Bureau marron avec retour', '6', ''),
                ('3', '137-2008', 'Bureau Informatique', '6', ''),
                ('4', '06-2023', 'Armoire métallique', '6', ''),
                ('5', '13-2020', 'Clapet métallique 10 cases', '6', ''),
                ('6', '12-2015', 'chaise opérateur', '6', ''),
                ('7', '20-2015', 'chaise opérateur', '6', ''),
                ('8', '', 'Chaise visiteور', '6', '')
            ]
            for ordre, inv_num, desig, bureau, obs in items:
                cur.execute("""
                    INSERT INTO general_inventory (ordre_num, inventory_num, designation, bureau_num, observation, created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ordre, inv_num, desig, bureau, obs, datetime.now().isoformat(), datetime.now().isoformat()))
    except Exception as e:
        print(f"⚠️ Error adding default general inventory: {e}")
    
    # إضافة معدات صيانة افتراضية
    try:
        cur.execute("SELECT COUNT(*) FROM maintenance_equipment")
        count = cur.fetchone()[0]
        if count == 0:
            equipments = [
                ('طابعة HP', 'طابعة', 'PR-001', 'أحمد علي', 'available'),
                ('آلة تصوير كانون', 'آلة تصوير', 'PH-002', 'كريمة بن سالم', 'available'),
                ('حاسوب ديل', 'حاسوب', 'PC-003', 'محمد لمين', 'available')
            ]
            for name, typ, inv, assigned, status in equipments:
                cur.execute("""
                    INSERT INTO maintenance_equipment (item_name, item_type, inventory_num, assigned_to, status, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, typ, inv, assigned, status, datetime.now().isoformat()))
    except Exception as e:
        print(f"⚠️ Error adding default equipment: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully")

# تهيئة قاعدة البيانات عند بدء التشغيل
print("🔄 Initializing database...")
init_db()

# -------------------- CATEGORIES --------------------
CATEGORIES = {
    'office': {'ar': 'قسم الأوراق واللوازم المكتبية', 'icon': '📝'},
    'it': {'ar': 'قسم الحبر ولوازم الإعلام الآلي', 'icon': '💻'},
    'cleaning': {'ar': 'قسم مواد التنظيف', 'icon': '🧹'},
    'maintenance': {'ar': 'قسم الصيانة', 'icon': '🔧'},
    'general_inv': {'ar': 'قسم الجرد العام', 'icon': '🏢'},
    'purchases': {'ar': 'المشتريات والحسابات', 'icon': '💰'}
}

UNITS = ['قطعة', 'متر', 'كيلو', 'لتر', 'علبة', 'كرتونة', 'حزمة', 'ربطة', 'صندوق', 'طرد']

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- HELPER FUNCTIONS --------------------
def get_last_decharge_number():
    current_year = datetime.now().year
    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()
    cur.execute("SELECT decharge_number FROM discharges WHERE decharge_number LIKE %s ORDER BY id DESC LIMIT 1", (f"%/{current_year}",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def get_next_decharge_number_for_inventory():
    current_year = datetime.now().year
    conn = get_db_connection()
    if not conn:
        return f"1/{current_year}"
    cur = conn.cursor()
    cur.execute("SELECT decharge_number FROM discharges WHERE decharge_number LIKE %s ORDER BY id DESC LIMIT 1", (f"%/{current_year}",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0]:
        try:
            last_num = int(row[0].split('/')[0])
            return f"{last_num + 1}/{current_year}"
        except:
            pass
    return f"1/{current_year}"

def get_next_decharge_number_for_maintenance():
    current_year = datetime.now().year
    conn = get_db_connection()
    if not conn:
        return f"1/{current_year}"
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM maintenance_logs WHERE EXTRACT(YEAR FROM sent_date::date)=%s", (str(current_year),))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return f"{count+1}/{current_year}"

def get_filtered_logs(period, start, end, recipient, item):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    q = """SELECT d.id, d.item_name, d.quantity, b.full_name, d.user_charged, d.date_time, d.category, d.inventory_num, d.notes
           FROM discharges d LEFT JOIN beneficiaries b ON d.receiver_id = b.id WHERE 1=1"""
    p = []
    if period == 'today':
        q += " AND d.date_time LIKE %s"; p.append(f"{datetime.now().strftime('%Y-%m-%d')}%")
    elif period == 'month':
        q += " AND d.date_time LIKE %s"; p.append(f"{datetime.now().strftime('%Y-%m')}%")
    elif period == 'year':
        q += " AND d.date_time LIKE %s"; p.append(f"{datetime.now().strftime('%Y')}%")
    elif period == 'custom' and start and end:
        q += " AND d.date_time::date BETWEEN %s AND %s"; p.extend([start, end])
    if recipient:
        q += " AND b.full_name LIKE %s"; p.append(f"%{recipient}%")
    if item:
        q += " AND d.item_name LIKE %s"; p.append(f"%{item}%")
    q += " ORDER BY d.id DESC"
    cur.execute(q, p)
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

def get_low_stock():
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("SELECT item_name, quantity, min_stock, category FROM inventory WHERE quantity <= min_stock ORDER BY quantity")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_stats():
    conn = get_db_connection()
    if not conn:
        return {}
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM inventory")
    total_items = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM inventory")
    total_quantity = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COALESCE(SUM(quantity * price), 0) FROM inventory")
    total_value = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM discharges")
    total_discharges = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM inventory WHERE quantity <= min_stock")
    low_count = cur.fetchone()[0] or 0
    
    cur.execute("SELECT category, COUNT(*) FROM inventory GROUP BY category")
    cat_dist = cur.fetchall()
    
    cur.execute("SELECT item_name, SUM(quantity) as total FROM discharges GROUP BY item_name ORDER BY total DESC LIMIT 10")
    top_items = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) FROM maintenance_logs WHERE status='sent'")
    ongoing_maintenance = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM maintenance_logs WHERE status='returned'")
    completed_maintenance = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COALESCE(SUM(repair_cost), 0) FROM maintenance_logs WHERE status='returned'")
    total_repair_cost = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM maintenance_equipment")
    total_equipment = cur.fetchone()[0] or 0
    
    cur.close()
    conn.close()
    
    cat_data = {CATEGORIES.get(c[0], {}).get('ar', c[0]): c[1] for c in cat_dist}
    top_data = [{'name': t[0], 'total': t[1]} for t in top_items]
    
    return {
        'total_items': total_items,
        'total_quantity': total_quantity,
        'total_value': total_value,
        'total_discharges': total_discharges,
        'low_stock_count': low_count,
        'category_data': cat_data,
        'top_items_data': top_data,
        'ongoing_maintenance': ongoing_maintenance,
        'completed_maintenance': completed_maintenance,
        'total_repair_cost': total_repair_cost,
        'total_equipment': total_equipment
    }

def get_beneficiaries():
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, grade, structure FROM beneficiaries ORDER BY full_name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{'id': r[0], 'full_name': r[1], 'grade': r[2], 'structure': r[3]} for r in rows]

def add_beneficiary(full_name, grade='', structure=''):
    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()
    cur.execute("INSERT INTO beneficiaries (full_name, grade, structure) VALUES (%s, %s, %s) RETURNING id", (full_name, grade, structure))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id

def get_next_ordre_num():
    conn = get_db_connection()
    if not conn:
        return "1"
    cur = conn.cursor()
    cur.execute("SELECT MAX(CAST(ordre_num AS INTEGER)) FROM general_inventory WHERE ordre_num ~ '^[0-9]+$'")
    max_num = cur.fetchone()[0]
    cur.close()
    conn.close()
    return str(int(max_num)+1) if max_num else "1"

def get_completed_maintenance_by_year(year=None):
    if year is None:
        year = datetime.now().year
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM maintenance_logs 
        WHERE status='returned' AND EXTRACT(YEAR FROM actual_return_date::date)=%s
        ORDER BY actual_return_date DESC
    """, (str(year),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def backup_db():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"tipaza_backup_{timestamp}.sql"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    conn = get_db_connection()
    if not conn:
        return backup_path
    
    try:
        import subprocess
        url = get_db_url()
        cmd = f"pg_dump {url} > {backup_path}"
        subprocess.run(cmd, shell=True, check=True)
        print(f"✅ Backup created: {backup_path}")
    except Exception as e:
        print(f"⚠️ Backup failed: {e}")
        with open(backup_path, 'w') as f:
            f.write(f"-- Backup failed: {e}")
    
    conn.close()
    return backup_path

def export_inventory_excel():
    conn = get_db_connection()
    if not conn:
        return BytesIO()
    df = pd.read_sql_query("SELECT id, item_name, quantity, category, inventory_num, min_stock, unit, price, last_updated FROM inventory", conn)
    conn.close()
    df.columns = ['الرقم','اسم المادة','الكمية','القسم','رقم الجرد','الحد الأدنى','الوحدة','السعر','آخر تحديث']
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='المخزون')
    out.seek(0)
    return out

def export_logs_excel(discharges_data):
    data = [list(row) for row in discharges_data]
    df = pd.DataFrame(data, columns=['الرقم','المادة','الكمية','المستلم','المستخدم','التاريخ','القسم','رقم الجرد','ملاحظات'])
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='سجل_العمليات')
    out.seek(0)
    return out

def get_consumption_timeline(months=12):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    result = []
    today = datetime.now()
    for i in range(months-1, -1, -1):
        dt = today.replace(day=1) - timedelta(days=30*i)
        month_str = dt.strftime("%Y-%m")
        cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM discharges WHERE date_time LIKE %s", (month_str + '%',))
        total = cur.fetchone()[0] or 0
        result.append({'month': month_str, 'total': total})
    cur.close()
    conn.close()
    return result

def import_inventory_excel(file):
    try:
        df = pd.read_excel(file, header=0)
        df.columns = df.columns.str.strip().str.lower()
        col_mapping = {
            'اسم المادة': 'item_name', 'المادة': 'item_name', 'designation': 'item_name',
            'الكمية': 'quantity', 'quantité': 'quantity', 'qty': 'quantity',
            'القسم': 'category', 'catégorie': 'category', 'category': 'category',
            'رقم الجرد': 'inventory_num', 'n° inventaire': 'inventory_num', 'inventory num': 'inventory_num',
            'الحد الأدنى': 'min_stock', 'stock min': 'min_stock', 'min stock': 'min_stock',
            'الوحدة': 'unit', 'unité': 'unit',
            'السعر': 'price', 'prix': 'price'
        }
        rename_dict = {}
        for col in df.columns:
            for pattern, new_name in col_mapping.items():
                if pattern in col:
                    rename_dict[col] = new_name
                    break
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        conn = get_db_connection()
        if not conn:
            return False, "خطأ في الاتصال بقاعدة البيانات"
        cur = conn.cursor()
        for _, row in df.iterrows():
            name = None
            if 'item_name' in df.columns and pd.notna(row['item_name']):
                name = row['item_name']
            elif 'designation' in df.columns and pd.notna(row['designation']):
                name = row['designation']
            if not name:
                continue
            qty = 0
            if 'quantity' in df.columns and pd.notna(row['quantity']):
                try: qty = int(row['quantity'])
                except: pass
            cat = 'office'
            if 'category' in df.columns and pd.notna(row['category']):
                cat = str(row['category'])
            inv_num = ''
            if 'inventory_num' in df.columns and pd.notna(row['inventory_num']):
                inv_num = str(row['inventory_num'])
            min_stock = 5
            if 'min_stock' in df.columns and pd.notna(row['min_stock']):
                try: min_stock = int(row['min_stock'])
                except: pass
            unit = 'قطعة'
            if 'unit' in df.columns and pd.notna(row['unit']):
                unit = str(row['unit'])
            price = 0.0
            if 'price' in df.columns and pd.notna(row['price']):
                try: price = float(row['price'])
                except: pass
            cur.execute("SELECT id FROM inventory WHERE item_name=%s", (name,))
            if cur.fetchone():
                cur.execute("""UPDATE inventory SET quantity=%s, category=%s, inventory_num=%s, min_stock=%s, unit=%s, price=%s, last_updated=%s
                               WHERE item_name=%s""",
                            (qty, cat, inv_num, min_stock, unit, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name))
            else:
                cur.execute("""INSERT INTO inventory (item_name, quantity, category, inventory_num, min_stock, unit, price, last_updated)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (name, qty, cat, inv_num, min_stock, unit, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        cur.close()
        conn.close()
        return True, "تم الاستيراد بنجاح"
    except Exception as e:
        return False, str(e)

# -------------------- HTML TEMPLATES --------------------
BASE_HTML = '''
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
    :root {--bg-light: #f0f2f5; --card-light: #fff; --text-light: #212529; --bg-dark: #1a1a2e; --card-dark: #16213e; --text-dark: #eee;}
    body {font-family: 'Cairo', sans-serif; background: var(--bg-light); color: var(--text-light); transition: 0.3s;}
    body.dark-mode {background: var(--bg-dark); color: var(--text-dark);}
    body.dark-mode .card {background: var(--card-dark); color: var(--text-dark); border: 1px solid #0f3460;}
    .navbar-custom {background: linear-gradient(90deg, #1e3c72, #2a5298); padding: 15px 0;}
    .navbar-custom .navbar-brand, .navbar-custom .btn, .navbar-custom .text-light {color: #fff!important;}
    .card {border: none; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05);}
    .cat-card:hover {transform: translateY(-5px);}
    .low-stock {background: #fff3cd; border-right: 4px solid #ffc107;}
    .stats-card {background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; border-radius: 15px; padding: 20px; text-align: center;}
    .stats-card h2 {font-size: 2.5rem; margin: 0;}
    .toast-container {position: fixed; bottom: 20px; left: 20px; z-index: 1055;}
    .theme-toggle {background: #ffc107; border-radius: 20px; padding: 5px 12px; border: none;}
    .dashboard-card {transition: 0.3s; border-radius: 20px; padding: 1.5rem; margin-bottom: 1rem;}
    .dashboard-card:hover {transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1);}
    .table td, .table th {white-space: normal; word-wrap: break-word; text-align: center; vertical-align: middle;}
    .table .btn-sm {white-space: nowrap;}
    @media (max-width: 768px) { .table td, .table th { font-size: 0.8rem; } .btn-sm { padding: 0.2rem 0.4rem; font-size: 0.7rem; } }
</style>
<script>
    if (localStorage.theme === 'dark') document.body.classList.add('dark-mode');
    function toggleTheme(){ 
        let dark = document.body.classList.toggle('dark-mode'); 
        localStorage.theme = dark ? 'dark' : 'light'; 
        fetch('/set_theme', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({theme:localStorage.theme})}); 
    }
    function showToast(msg,type='success'){ 
        $('.toast-container').append(`<div class="toast align-items-center text-white bg-${type} show"><div class="d-flex"><div class="toast-body">${msg}</div><button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button></div></div>`); 
        setTimeout(()=>$('.toast').last().remove(),3000); 
    }
    let timer; 
    function reset(){ clearTimeout(timer); timer=setTimeout(()=>window.location='/logout',30*60*1000); }
    window.onload=reset; document.onmousemove=reset; document.onkeypress=reset;
</script>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>تسجيل الدخول</title>'''+BASE_HTML+'''</head>
<body class="d-flex align-items-center justify-content-center" style="height:100vh">
<div class="card p-5" style="width:450px">
    <div class="text-center mb-4">
        <h4 class="fw-bold text-primary">إدارة المخزون<br>مديرية التشغيل تيبازة</h4>
        <p class="text-muted">تسجيل الدخول للنظام</p>
    </div>
    {% with msgs = get_flashed_messages(with_categories=true) %}
        {% if msgs %}{% for cat,msg in msgs %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}
    {% endwith %}
    <form method="POST">
        <div class="mb-3"><label class="fw-bold">اسم المستخدم</label><input type="text" name="username" class="form-control" required></div>
        <div class="mb-4"><label class="fw-bold">كلمة المرور</label><input type="password" name="password" class="form-control" required></div>
        <button type="submit" class="btn btn-primary w-100">دخول</button>
    </form>
</div>
<div class="toast-container"></div>
</body></html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>لوحة التحكم</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><a class="navbar-brand" href="#">📦 مديرية التشغيل تيبازة</a>
<div class="d-flex gap-2"><span class="text-light">مرحباً، {{ username }}</span>
<a href="/logs/{{ username }}" class="btn btn-outline-light btn-sm">سجل العمليات</a>
<a href="/statistics/{{ username }}" class="btn btn-outline-light btn-sm">إحصائيات عامة</a>
<a href="/export_inventory/{{ username }}" class="btn btn-outline-light btn-sm"><i class="fas fa-file-excel"></i> تصدير المخزون</a>
<a href="/backup/{{ username }}" class="btn btn-outline-light btn-sm"><i class="fas fa-database"></i> نسخ احتياطي</a>
<button class="btn btn-outline-light btn-sm" data-bs-toggle="modal" data-bs-target="#importModal"><i class="fas fa-upload"></i> استيراد</button>
<a href="/manage_beneficiaries/{{ username }}" class="btn btn-outline-light btn-sm"><i class="fas fa-users"></i> المستلمون</a>
{% if session.role == 'مدير' %}<a href="/manage_users/{{ username }}" class="btn btn-outline-light btn-sm">المستخدمون</a>{% endif %}
<a href="/logout" class="btn btn-danger btn-sm">خروج</a>
<button onclick="toggleTheme()" class="theme-toggle"><i class="fas fa-moon"></i> وضع داكن</button>
</div></div></nav>
<div class="container mt-4">
    {% with msgs = get_flashed_messages(with_categories=true) %}{% if msgs %}{% for cat,msg in msgs %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}
    <div class="row mb-4">
        <div class="col-md-3"><div class="dashboard-card text-white" style="background:linear-gradient(135deg,#667eea,#764ba2)"><div class="d-flex justify-content-between"><div><h2 class="mb-0">{{ stats.total_items }}</h2><p>إجمالي المواد</p></div><i class="fas fa-boxes fa-3x opacity-50"></i></div></div></div>
        <div class="col-md-3"><div class="dashboard-card text-white" style="background:linear-gradient(135deg,#f093fb,#f5576c)"><div><h2 class="mb-0">{{ stats.total_quantity }}</h2><p>إجمالي الكميات</p><i class="fas fa-cubes fa-3x opacity-50"></i></div></div></div>
        <div class="col-md-3"><div class="dashboard-card text-white" style="background:linear-gradient(135deg,#4facfe,#00f2fe)"><div><h2 class="mb-0">{{ stats.total_discharges }}</h2><p>عمليات السحب</p><i class="fas fa-exchange-alt fa-3x opacity-50"></i></div></div></div>
        <div class="col-md-3"><div class="dashboard-card text-white" style="background:linear-gradient(135deg,#43e97b,#38f9d7)"><div><h2 class="mb-0">{{ stats.low_stock_count }}</h2><p>مواد منخفضة</p><i class="fas fa-exclamation-triangle fa-3x opacity-50"></i></div></div></div>
    </div>
    {% if low_stock %}<div class="alert alert-warning"><h5><i class="fas fa-exclamation-triangle"></i> تنبيه: مواد منخفضة المخزون</h5><ul>{% for i in low_stock %}<li>{{ i[0] }} - الكمية: {{ i[1] }} (الحد الأدنى: {{ i[2] }})</li>{% endfor %}</ul></div>{% endif %}
    <h4 class="mb-4">الأقسام المتاحة</h4>
    <div class="row g-4">{% for slug,cat in categories.items() %}<div class="col-md-4 col-sm-6"><a href="/section/{{ slug }}/{{ username }}" class="text-decoration-none"><div class="card h-100 p-4 text-center cat-card"><div class="display-4 mb-3">{{ cat.icon }}</div><h5 class="fw-bold">{{ cat.ar }}</h5></div></a></div>{% endfor %}</div>
</div>
<div class="modal fade" id="importModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">استيراد المخزون من Excel</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <form action="/import_inventory/{{ username }}" method="POST" enctype="multipart/form-data">
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">اختر ملف Excel</label>
            <input type="file" name="file" class="form-control" accept=".xlsx, .xls" required>
          </div>
          <div class="alert alert-info">
            <small>يجب أن يحتوي الملف على أعمدة: اسم المادة، الكمية، القسم، رقم الجرد، الحد الأدنى، الوحدة، السعر (يمكن أن تكون بأسماء مختلفة)</small>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button>
          <button type="submit" class="btn btn-primary">رفع واستيراد</button>
        </div>
      </form>
    </div>
  </div>
</div>
<div class="toast-container"></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
'''

SECTION_COMMON = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>{{ cat_name }}</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">{{ cat_name }}</span><div class="d-flex gap-2"><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a></div></div></nav>
<div class="container mt-4">
    {% with msgs = get_flashed_messages(with_categories=true) %}{% if msgs %}{% for cat,msg in msgs %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}
    <div class="row mb-3"><div class="col"><button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#consumptionModal">📊 إحصاء المواد المستهلكة</button><button class="btn btn-success ms-2" data-bs-toggle="modal" data-bs-target="#purchaseModal">🛒 الشراء (توقع الاحتياجات)</button></div></div>
    <div class="row">
        <div class="col-md-8 mb-4"><div class="card p-4"><h5 class="fw-bold mb-3">قائمة المواد</h5><div class="search-box"><input type="text" id="searchInput" onkeyup="filterTable()" class="form-control" placeholder="بحث..."></div>
        <div class="table-responsive"><table class="table table-hover" id="itemsTable"><thead class="table-light"><tr><th>المادة</th><th>الوحدة</th><th>الكمية</th><th>الحد الأدنى</th><th>إجراءات</th></tr></thead><tbody>
        {% for item in items %}<tr class="{% if item[2] <= item[5] %}low-stock{% endif %}"><td class="fw-bold">{{ item[1] }}{% if item[4] %}<br><small class="text-muted">({{ item[4] }})</small>{% endif %} </td><td class="text-nowrap">{{ item[6] or 'قطعة' }} </td><td><span class="badge {{ 'bg-danger' if item[2] <= item[5] else 'bg-success' }}">{{ item[2] }}</span> <td><td class="align-middle">{{ item[5] }} </td><td class="align-middle"><div class="d-flex gap-2"><form action="/add_to_cart" method="POST" class="d-flex gap-1"><input type="hidden" name="item_name" value="{{ item[1] }}"><input type="hidden" name="category" value="{{ cat_slug }}"><input type="hidden" name="username" value="{{ username }}"><input type="number" name="quantity" class="form-control form-control-sm" style="width:70px" value="1" min="1" max="{{ item[2] }}" required><button type="submit" class="btn btn-sm btn-primary" {% if item[2]==0 %}disabled{% endif %}>سحب</button></form>{% if session.role in ['مدير','مشرف'] %}<button class="btn btn-sm btn-outline-info" onclick="editItem({{ item[0] }},'{{ item[1] }}',{{ item[2] }},{{ item[5] }},'{{ item[6] }}',{{ item[7] }},'{{ item[4] or '' }}')">تعديل</button>{% endif %}{% if session.role == 'مدير' %}<a href="/delete_item/{{ item[0] }}/{{ cat_slug }}/{{ username }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('حذف؟')">حذف</a>{% endif %}</div></td></tr>{% else %}<tr><td colspan="5" class="text-center">لا توجد بيانات</td>{% endfor %}</tbody></table></div></div></div>
        <div class="col-md-4"><div class="card p-4 border-primary mb-4"><div class="d-flex justify-content-between mb-3"><h5 class="fw-bold">🛒 السلة</h5>{% if session.cart %}<a href="/clear_cart/{{ cat_slug }}/{{ username }}" class="text-danger small">تفريغ</a>{% endif %}</div>
        {% if session.cart %}<ul class="list-group mb-3">{% for ci in session.cart %}<li class="list-group-item d-flex justify-content-between"><span>{{ ci.item_name }} <span class="badge bg-primary">{{ ci.quantity }}</span></span><a href="/remove_from_cart/{{ loop.index0 }}/{{ cat_slug }}/{{ username }}" class="text-danger">✖</a></li>{% endfor %}</ul>
        <form action="/prepare_discharge/{{ username }}" method="POST"><input type="hidden" name="category" value="{{ cat_slug }}"><div class="mb-2"><label class="form-label">المستلم</label><select name="receiver_id" class="form-select" required><option value="">اختر مستلم...</option>{% for b in beneficiaries %}<option value="{{ b.id }}">{{ b.full_name }} ({{ b.grade or '-' }}) - {{ b.structure or '-' }}</option>{% endfor %}</select><div class="mt-1 small"><a href="/manage_beneficiaries/{{ username }}" target="_blank">+ إضافة مستلم جديد</a></div></div><div class="mb-2"><label>ملاحظات</label><textarea name="notes" class="form-control" rows="2"></textarea></div><button type="submit" class="btn btn-primary w-100">تأكيد وطباعة</button></form>
        {% else %}<div class="text-center text-muted py-5"><div class="display-1">🛒</div><p>السلة فارغة</p></div>{% endif %}</div>
        {% if session.role in ['مدير','مشرف'] %}<div class="card p-4"><h6 class="fw-bold text-primary">➕ إدراج مادة جديدة</h6><form action="/add_item/{{ cat_slug }}/{{ username }}" method="POST" class="row g-2"><div class="col-12"><input type="text" name="item_name" class="form-control" placeholder="اسم المادة" required></div><div class="col-6"><input type="number" name="quantity" class="form-control" placeholder="الكمية" value="0" min="0" required></div><div class="col-6"><input type="number" name="min_stock" class="form-control" placeholder="الحد الأدنى" value="5"></div><div class="col-6"><select name="unit" class="form-select">{% for u in units %}<option>{{ u }}</option>{% endfor %}</select></div><div class="col-6"><input type="number" name="price" class="form-control" placeholder="السعر (دج)" value="0" step="0.01"></div><div class="col-12"><input type="text" name="inventory_num" class="form-control" placeholder="رقم الجرد (اختياري)"></div><div class="col-12"><button type="submit" class="btn btn-success w-100">حفظ</button></div></form></div>{% endif %}</div>
    </div>
</div>
<div class="modal fade" id="consumptionModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">إحصاء المواد المستهلكة</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><form id="consForm"><input type="hidden" name="category" value="{{ cat_slug }}"><div class="row g-2"><div class="col-3"><label>الفترة</label><select name="period_type" class="form-select" id="periodType"><option value="year">سنة</option><option value="month">شهر</option><option value="custom">مخصص</option></select></div><div class="col-3" id="yearDiv"><label>السنة</label><input type="number" name="year" class="form-control" value="{{ now.year }}"></div><div class="col-3" id="monthDiv" style="display:none"><label>الشهر</label><input type="month" name="month" class="form-control" value="{{ now.strftime('%Y-%m') }}"></div><div class="col-6" id="customDiv" style="display:none"><label>من تاريخ</label><input type="date" name="start_date" class="form-control"><label>إلى تاريخ</label><input type="date" name="end_date" class="form-control"></div><div class="col-3"><label>المادة</label><select name="item_name" id="consItemSelect" class="form-select"><option value="all">كل المواد</option></select></div><div class="col-3"><label>المستلم</label><input type="text" name="receiver" class="form-control"></div><div class="col-3"><button type="submit" class="btn btn-primary mt-4">عرض</button></div></div></form><div id="consResults" class="mt-4"></div></div></div></div></div>
<div class="modal fade" id="purchaseModal" tabindex="-1"><div class="modal-dialog modal-xl"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">الشراء - توقع الاحتياجات</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="alert alert-info">تعرض القائمة جميع المواد مع السعر واستهلاك السنة الماضية والكمية المقترحة (+10%). يمكن تعديل الكميات.</div><div id="purchaseTable"></div><button id="exportPurchaseBtn" class="btn btn-success mt-3">تصدير إلى Excel</button></div></div></div></div>
<div class="modal fade" id="editModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">تعديل المادة</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form id="editForm" method="POST"><div class="modal-body"><input type="hidden" id="edit_id" name="item_id"><div class="mb-2"><label>اسم المادة</label><input type="text" id="edit_name" name="item_name" class="form-control" required></div><div class="mb-2"><label>الكمية</label><input type="number" id="edit_quantity" name="quantity" class="form-control" required></div><div class="mb-2"><label>الحد الأدنى</label><input type="number" id="edit_min_stock" name="min_stock" class="form-control"></div><div class="mb-2"><label>الوحدة</label><select id="edit_unit" name="unit" class="form-select">{% for u in units %}<option>{{ u }}</option>{% endfor %}</select></div><div class="mb-2"><label>السعر (دج)</label><input type="number" id="edit_price" name="price" class="form-control" step="0.01"></div><div class="mb-2"><label>رقم الجرد</label><input type="text" id="edit_inv_num" name="inventory_num" class="form-control"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">حفظ</button></div></form></div></div></div>
<script>
function filterTable(){let inp=document.getElementById('searchInput'), filter=inp.value.toUpperCase(), table=document.getElementById('itemsTable'), tr=table.getElementsByTagName('tr');for(let i=1;i<tr.length;i++){let td=tr[i].getElementsByTagName('td')[0];if(td) tr[i].style.display=td.innerText.toUpperCase().indexOf(filter)>-1?'':'none';}}
fetch('/get_items_by_category/{{ cat_slug }}').then(r=>r.json()).then(d=>{let sel=document.getElementById('consItemSelect');d.items.forEach(i=>{let opt=document.createElement('option');opt.value=i;opt.text=i;sel.appendChild(opt);});});
document.getElementById('periodType').addEventListener('change',function(){let y=document.getElementById('yearDiv'), m=document.getElementById('monthDiv'), c=document.getElementById('customDiv');if(this.value==='year'){ y.style.display='block'; m.style.display='none'; c.style.display='none'; }else if(this.value==='month'){ y.style.display='none'; m.style.display='block'; c.style.display='none'; }else{ y.style.display='none'; m.style.display='none'; c.style.display='block'; }});
document.getElementById('consForm').addEventListener('submit',function(e){e.preventDefault();let params=new URLSearchParams(new FormData(this));fetch('/consumption_stats?'+params).then(r=>r.json()).then(d=>{document.getElementById('consResults').innerHTML=d.html;});});
document.getElementById('purchaseModal').addEventListener('show.bs.modal',function(){fetch('/purchase_needs/{{ cat_slug }}').then(r=>r.json()).then(d=>{let html='<table class="table table-bordered"><thead><tr><th>المادة</th><th>الوحدة</th><th>السعر</th><th>استهلاك السنة الماضية</th><th>المقترح</th><th>التكلفة</th><th>تعديل الكمية</th></tr></thead><tbody>';d.forEach(it=>{html+=`<tr><td>${it.name}</td><td>${it.unit}</td><td>${it.price}</td><td>${it.last_year_consumption}</td><td>${it.suggested_quantity}</td><td>${(it.suggested_quantity*it.price).toFixed(2)} دج</td><td><input type="number" class="qty-input" data-price="${it.price}" value="${it.suggested_quantity}" style="width:80px"></td>`;});html+='</tbody></table><p class="mt-2">الإجمالي: <span id="totalCost">0</span> دج</p>';document.getElementById('purchaseTable').innerHTML=html;function update(){let t=0;document.querySelectorAll('.qty-input').forEach(inp=>{let q=parseFloat(inp.value)||0; let p=parseFloat(inp.dataset.price)||0; t+=q*p;});document.getElementById('totalCost').innerText=t.toFixed(2);}document.querySelectorAll('.qty-input').forEach(inp=>inp.addEventListener('input',update));update();});});
document.getElementById('exportPurchaseBtn').addEventListener('click',function(){let data=[];document.querySelectorAll('#purchaseTable tbody tr').forEach(row=>{let cells=row.querySelectorAll('td');if(cells.length){data.push({'المادة':cells[0].innerText,'الوحدة':cells[1].innerText,'السعر':parseFloat(cells[2].innerText),'استهلاك السنة الماضية':parseFloat(cells[3].innerText),'المقترح شراؤه':parseFloat(cells[4].innerText),'التكلفة المتوقعة':cells[5].innerText,'الكمية المعدلة':parseFloat(row.querySelector('.qty-input').value)});}});fetch('/export_purchase_needs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(res=>res.blob()).then(blob=>{let a=document.createElement('a'), url=URL.createObjectURL(blob);a.href=url; a.download='purchase_needs.xlsx'; a.click(); URL.revokeObjectURL(url);});});
function editItem(id,name,qty,minStock,unit,price,invNum){
    document.getElementById('edit_id').value=id;
    document.getElementById('edit_name').value=name;
    document.getElementById('edit_quantity').value=qty;
    document.getElementById('edit_min_stock').value=minStock;
    document.getElementById('edit_unit').value=unit;
    document.getElementById('edit_price').value=price;
    document.getElementById('edit_inv_num').value=invNum;
    document.getElementById('editForm').action = "/edit_item/{{ cat_slug }}/{{ username }}";
    new bootstrap.Modal(document.getElementById('editModal')).show();
}
</script>
<div class="toast-container"></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
'''

GENERAL_INV_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>الجرد العام</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">الجرد العام</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><h5>إضافة عنصر جديد</h5><form method="POST" action="/add_general_item/{{ username }}" class="row g-2"><div class="col-md-2"><input type="text" name="ordre_num" class="form-control" placeholder="رقم التسلسل" readonly value="{{ next_num }}"></div><div class="col-md-2"><input type="text" name="inventory_num" class="form-control" placeholder="رقم الجرد" required></div><div class="col-md-4"><input type="text" name="designation" class="form-control" placeholder="التسمية" required></div><div class="col-md-2"><input type="text" name="bureau_num" class="form-control" placeholder="المكتب"></div><div class="col-md-2"><input type="text" name="observation" class="form-control" placeholder="ملاحظات"></div><div class="col-md-12"><button type="submit" class="btn btn-primary">إضافة</button></div></form></div>
<div class="card p-4"><div class="d-flex justify-content-between mb-3"><h5>قائمة الممتلكات</h5><div><button class="btn btn-secondary" onclick="preparePrint()">طباعة</button></div></div><div class="row g-2 mb-3"><div class="col-md-4"><input type="text" id="filterDesignation" class="form-control" placeholder="فلتر بالتسمية"></div><div class="col-md-4"><input type="text" id="filterBureau" class="form-control" placeholder="فلتر بالمكتب"></div><div class="col-md-4"><button class="btn btn-outline-primary" onclick="filterTable()">فلترة</button></div></div>
<div class="table-responsive"><table class="table table-bordered" id="invTable"><thead class="table-light"><tr><th>رقم التسلسل</th><th>رقم الجرد</th><th>التسمية</th><th>المكتب</th><th>ملاحظات</th><th>إجراءات</th></tr></thead><tbody>{% for item in items %}<tr><td class="align-middle">{{ item[1] }}</td><td class="align-middle">{{ item[2] }}</td><td class="align-middle">{{ item[3] }}</td><td class="align-middle">{{ item[4] }}</td><td class="align-middle">{{ item[5] }}</td><td class="align-middle"><button class="btn btn-sm btn-info" onclick="editItem({{ item[0] }},'{{ item[1] }}','{{ item[2] }}','{{ item[3] }}','{{ item[4] }}','{{ item[5] }}')">تعديل</button><a href="/delete_general_item/{{ item[0] }}/{{ username }}" class="btn btn-sm btn-danger ms-1" onclick="return confirm('حذف؟')">حذف</a></td></tr>{% endfor %}</tbody></table></div></div></div>
<div class="modal fade" id="employeeModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>إضافة أسماء الموظفين وشاغل المكتب</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>الموظفون (افصل بينهم بفاصلة)</label><input type="text" id="employeesList" class="form-control" placeholder="مثال: أحمد علي، كريمة بن سالم"></div><div class="mb-3"><label>شاغل المكتب</label><input type="text" id="officeOccupant" class="form-control" placeholder="اسم شاغل المكتب"></div><div class="mb-3"><label>رقم المكتب</label><input type="text" id="bureauNum" class="form-control" placeholder="مثلاً: 6"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="button" class="btn btn-primary" onclick="printWithFilter()">طباعة</button></div></div></div></div>
<div class="modal fade" id="editModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>تعديل</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="editForm"><div class="modal-body"><input type="hidden" name="id" id="edit_id"><div class="mb-2"><label>رقم التسلسل</label><input type="text" name="ordre_num" id="edit_ordre" class="form-control" required></div><div class="mb-2"><label>رقم الجرد</label><input type="text" name="inventory_num" id="edit_inv" class="form-control" required></div><div class="mb-2"><label>التسمية</label><input type="text" name="designation" id="edit_desig" class="form-control" required></div><div class="mb-2"><label>المكتب</label><input type="text" name="bureau_num" id="edit_bureau" class="form-control"></div><div class="mb-2"><label>ملاحظات</label><input type="text" name="observation" id="edit_obs" class="form-control"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">حفظ</button></div></form></div></div></div>
<script>
function editItem(id,ordre,inv,desig,bureau,obs){document.getElementById('edit_id').value=id;document.getElementById('edit_ordre').value=ordre;document.getElementById('edit_inv').value=inv;document.getElementById('edit_desig').value=desig;document.getElementById('edit_bureau').value=bureau;document.getElementById('edit_obs').value=obs;document.getElementById('editForm').action="/edit_general_item/"+id+"/{{ username }}";new bootstrap.Modal(document.getElementById('editModal')).show();}
function filterTable(){let desig=document.getElementById('filterDesignation').value.toUpperCase();let bureau=document.getElementById('filterBureau').value.toUpperCase();let table=document.getElementById('invTable');let tr=table.getElementsByTagName('tr');for(let i=1;i<tr.length;i++){let tdDesig=tr[i].getElementsByTagName('td')[2];let tdBur=tr[i].getElementsByTagName('td')[3];let show=true;if(tdDesig && desig!='' && tdDesig.innerText.toUpperCase().indexOf(desig)==-1) show=false;if(tdBur && bureau!='' && tdBur.innerText.toUpperCase().indexOf(bureau)==-1) show=false;tr[i].style.display=show?'':'none';}}
function preparePrint(){new bootstrap.Modal(document.getElementById('employeeModal')).show();}
function printWithFilter(){let employees=document.getElementById('employeesList').value;let officeOccupant=document.getElementById('officeOccupant').value||'';let bureau=document.getElementById('bureauNum').value||'_____';let visibleRows=[];let table=document.getElementById('invTable');let tr=table.getElementsByTagName('tr');for(let i=1;i<tr.length;i++){if(tr[i].style.display!=='none') visibleRows.push(tr[i]);}let data=[];for(let row of visibleRows){let cells=row.getElementsByTagName('td');data.push({ordre_num:cells[0].innerText,inventory_num:cells[1].innerText,designation:cells[2].innerText,observation:cells[4].innerText});}let form=document.createElement('form');form.method='POST';form.action='/print_general_inventory_filtered';form.target='_blank';let inputEmployees=document.createElement('input');inputEmployees.type='hidden';inputEmployees.name='employees';inputEmployees.value=employees;form.appendChild(inputEmployees);let inputOfficeOccupant=document.createElement('input');inputOfficeOccupant.type='hidden';inputOfficeOccupant.name='office_occupant';inputOfficeOccupant.value=officeOccupant;form.appendChild(inputOfficeOccupant);let inputBureau=document.createElement('input');inputBureau.type='hidden';inputBureau.name='bureau_num';inputBureau.value=bureau;form.appendChild(inputBureau);let inputData=document.createElement('input');inputData.type='hidden';inputData.name='data';inputData.value=JSON.stringify(data);form.appendChild(inputData);document.body.appendChild(form);form.submit();document.body.removeChild(form);bootstrap.Modal.getInstance(document.getElementById('employeeModal')).hide();}
</script>
<div class="toast-container"></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
'''

GENERAL_PRINT_FILTERED_HTML = '''
<!DOCTYPE html>
<html lang="fr" dir="ltr">
<head>
    <meta charset="UTF-8">
    <title>Inventaire Général</title>
    <style>
        body {font-family: Tahoma; padding: 20px; direction: ltr;}
        .header-left {text-align: left; margin-bottom: 20px;}
        .header-left h3, .header-left h4, .header-left h5 {margin: 3px 0;}
        table {border-collapse: collapse; width: 100%; margin-top: 20px;}
        th, td {border: 1px solid #000; padding: 8px; text-align: center;}
        .office-occupant {text-align: left; margin-top: 20px; font-weight: bold;}
        .signature-line {display: flex; justify-content: space-between; align-items: center; margin-top: 60px; font-weight: bold; font-size: 16px; padding: 0 20px;}
        .signature-line .name {text-align: center; flex: 1;}
        .signature-line .directeur {text-align: center; flex: 1;}
        @media print { .no-print {display: none;} }
    </style>
</head>
<body>
    <button class="no-print" onclick="window.print()" style="margin-bottom:20px;">Imprimer</button>
    <div class="header-left">
        <h3>Wilaya de Tipaza</h3>
        <h4>Direction de l'Emploi</h4>
        <h4>Service de l'Administration et Budget</h4>
        <h5>Bureau N°: {{ bureau_num }}</h5>
        <br><br><br>
    </div>
    <h3 style="text-align:center">FICHE D'INVENTAIRE</h3>
    <table border="1">
        <thead><tr><th>N° ordre</th><th>N° Inventaire</th><th>Désignation</th><th>Observation</th></tr></thead>
        <tbody>
            {% for item in items %}
            <tr><td style="text-align:center">{{ item.ordre_num }}</td><td style="text-align:center">{{ item.inventory_num }}</td><td style="text-align:center">{{ item.designation }}</td><td style="text-align:center">{{ item.observation }}</td></tr>
            {% endfor %}
        </tbody>
    </table>
    <div class="office-occupant"><strong>Occupant du bureau :</strong> {{ office_occupant }}</div>
    
    <div class="signature-line">
        {% set employees_list = employees.split('،') if employees else [] %}
        {% for emp in employees_list %}
            {% set emp_name = emp.strip() %}
            {% if emp_name %}
                <span class="name">{{ emp_name }}</span>
            {% endif %}
        {% endfor %}
        <span class="directeur">Directeur</span>
    </div>
</body>
</html>
'''

MAINTENANCE_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>قسم الصيانة</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">قسم الصيانة - تتبع المعدات</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a><a href="/print_completed_maintenance/{{ username }}" class="btn btn-outline-light btn-sm ms-2" target="_blank">📄 تقرير الصيانة المكتملة</a></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><h5>إضافة معدات جديدة</h5><form method="POST" action="/add_equipment/{{ username }}" class="row g-2"><div class="col-md-3"><input type="text" name="item_name" class="form-control" placeholder="اسم المعدة" required></div><div class="col-md-2"><input type="text" name="item_type" class="form-control" placeholder="النوع" required></div><div class="col-md-2"><input type="text" name="inventory_num" class="form-control" placeholder="رقم الجرد" required></div><div class="col-md-3"><input type="text" name="assigned_to" class="form-control" placeholder="الموظف المكلف" required></div><div class="col-md-2"><button type="submit" class="btn btn-primary">إضافة</button></div></form></div>
<div class="card p-4"><h5>المعدات المسجلة</h5><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>اسم المعدة</th><th>النوع</th><th>رقم الجرد</th><th>الموظف المكلف</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>{% for eq in equipment %}<tr><td class="align-middle">{{ eq[1] }}</td><td class="align-middle">{{ eq[2] }}</td><td class="align-middle">{{ eq[3] }}</td><td class="align-middle">{{ eq[4] }}</td><td class="align-middle">{% if eq[5] == 'available' %}متاحة{% else %}قيد الصيانة{% endif %}</td><td class="align-middle"><button class="btn btn-sm btn-warning" onclick="editEquipment({{ eq[0] }},'{{ eq[1] }}','{{ eq[2] }}','{{ eq[3] }}','{{ eq[4] }}')">تعديل</button><a href="/delete_equipment/{{ eq[0] }}/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف المعدة؟')">حذف</a>{% if eq[5] == 'available' %}<button class="btn btn-sm btn-primary mt-1" onclick="sendToMaintenance({{ eq[0] }},'{{ eq[1] }}','{{ eq[3] }}')">إرسال للصيانة</button>{% endif %}</td></tr>{% else %}<tr><td colspan="6">لا توجد معدات مسجلة</td>{% endfor %}</tbody></table></div></div>
<div class="card p-4 mt-4"><div class="d-flex justify-content-between"><h5>المعدات تحت الصيانة حالياً</h5><button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#multiMaintenanceModal">📄 وصل صيانة متعدد</button></div><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>المادة</th><th>رقم الجرد</th><th>تاريخ الإرسال</th><th>المصلح</th><th>الإجراء</th></tr></thead><tbody>{% for log in ongoing %}<tr><td class="align-middle">{{ log[2] }}</td><td class="align-middle">{{ log[3] }}</td><td class="align-middle">{{ log[4] }}</td><td class="align-middle">{{ log[5] }}</td><td class="align-middle"><button class="btn btn-sm btn-success" onclick="returnFromMaintenance({{ log[0] }},'{{ log[2] }}')">استلام</button><a href="/print_maintenance_slip/{{ log[0] }}/{{ username }}" target="_blank" class="btn btn-sm btn-info">وصل الصيانة</a><a href="/maintenance_decharge_form/{{ log[0] }}/{{ username }}" class="btn btn-sm btn-secondary ms-1">وصل التسليم</a><a href="/delete_maintenance_log/{{ log[0] }}/ongoing/{{ username }}" class="btn btn-sm btn-danger ms-1" onclick="return confirm('حذف هذا السجل؟')">حذف</a></td></tr>{% else %}<tr><td colspan="5">لا توجد عمليات صيانة جارية</td>{% endfor %}</tbody></table></div></div>
<div class="card p-4 mt-4"><h5>الصيانة المكتملة</h5><div class="table-responsive"><table class="table table-sm table-bordered"><thead class="table-light"><tr><th>المادة</th><th>رقم الجرد</th><th>تاريخ الإرسال</th><th>تاريخ العودة</th><th>التكلفة</th><th>إجراءات</th></tr></thead><tbody>{% for log in completed %}<tr><td class="align-middle">{{ log[2] }}</td><td class="align-middle">{{ log[3] }}</td><td class="align-middle">{{ log[4] }}</td><td class="align-middle">{{ log[7] }}</td><td class="align-middle">{{ log[8] }} دج</td><td class="align-middle"><a href="/delete_maintenance_log/{{ log[0] }}/completed/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف السجل؟')">حذف</a></td></td>{% else %}<tr><td colspan="6" class="text-center">لا توجد صيانة مكتملة</td>{% endfor %}</tbody></table></div></div></div>
<div class="modal fade" id="sendModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>إرسال للصيانة الخارجية</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="sendForm"><div class="modal-body"><input type="hidden" name="equipment_id" id="send_equip_id"><div class="mb-2"><label>المادة</label><input type="text" id="send_item_name" class="form-control" readonly></div><div class="mb-2"><label>رقم الجرد</label><input type="text" id="send_inv_num" class="form-control" readonly></div><div class="mb-2"><label>المصلح الخارجي</label><input type="text" name="repair_shop" class="form-control" required></div><div class="mb-2"><label>وصف العطل</label><textarea name="issue_description" class="form-control" rows="2" required></textarea></div><div class="mb-2"><label>تاريخ العودة المتوقع (اختياري)</label><input type="date" name="expected_return_date" class="form-control"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">إرسال</button></div></form></div></div></div>
<div class="modal fade" id="multiMaintenanceModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5>وصل صيانة متعدد</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" action="/send_multi_equipment_to_maintenance/{{ username }}"><div class="modal-body"><div class="mb-3"><label>المصلح الخارجي</label><input type="text" name="repair_shop" class="form-control" required></div><div class="mb-3"><label>وصف العطل (عام)</label><textarea name="issue_description" class="form-control" rows="2" required></textarea></div><div class="mb-3"><label>تاريخ العودة المتوقع (اختياري)</label><input type="date" name="expected_return_date" class="form-control"></div><h6>اختر المعدات المراد إرسالها:</h6><div class="table-responsive"><table class="table table-bordered"><thead><tr><th><input type="checkbox" id="selectAllMulti"> الكل</th><th>المعدة</th><th>رقم الجرد</th></tr></thead><tbody>{% for eq in equipment if eq[5] == 'available' %}<tr><td><input type="checkbox" name="equipment_ids" value="{{ eq[0] }}" class="multi-checkbox"></td><td>{{ eq[1] }}</td><td>{{ eq[3] }}</td></tr>{% else %}<tr><td colspan="3">لا توجد معدات متاحة</td>{% endfor %}</tbody></table></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">إنشاء وصل وإرسال</button></div></form></div></div></div>
<div class="modal fade" id="returnModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>استلام من الصيانة</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="returnForm"><div class="modal-body"><input type="hidden" name="log_id" id="return_log_id"><div class="mb-2"><label>تاريخ العودة الفعلي</label><input type="date" name="actual_return_date" class="form-control" required value="{{ now.strftime('%Y-%m-%d') }}"></div><div class="mb-2"><label>تكلفة الإصلاح (دج)</label><input type="number" name="repair_cost" class="form-control" step="0.01" value="0"></div><div class="mb-2"><label>ملاحظات</label><textarea name="notes" class="form-control" rows="2"></textarea></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">تسجيل العودة</button></div></form></div></div></div>
<div class="modal fade" id="editEquipmentModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>تعديل المعدة</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="editEquipmentForm"><div class="modal-body"><input type="hidden" name="equipment_id" id="edit_equipment_id"><div class="mb-2"><label>اسم المعدة</label><input type="text" name="item_name" id="edit_item_name" class="form-control" required></div><div class="mb-2"><label>النوع</label><input type="text" name="item_type" id="edit_item_type" class="form-control" required></div><div class="mb-2"><label>رقم الجرد</label><input type="text" name="inventory_num" id="edit_inventory_num" class="form-control" required></div><div class="mb-2"><label>الموظف المكلف</label><input type="text" name="assigned_to" id="edit_assigned_to" class="form-control" required></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button><button type="submit" class="btn btn-primary">حفظ</button></div></form></div></div></div>
<script>
function sendToMaintenance(id,name,invNum){document.getElementById('send_equip_id').value=id;document.getElementById('send_item_name').value=name;document.getElementById('send_inv_num').value=invNum;document.getElementById('sendForm').action="/send_equipment_to_maintenance/{{ username }}";new bootstrap.Modal(document.getElementById('sendModal')).show();}
function returnFromMaintenance(logId,name){document.getElementById('return_log_id').value=logId;document.getElementById('returnForm').action="/return_equipment_from_maintenance/"+logId+"/{{ username }}";new bootstrap.Modal(document.getElementById('returnModal')).show();}
function editEquipment(id,name,typ,inv,assigned){document.getElementById('edit_equipment_id').value=id;document.getElementById('edit_item_name').value=name;document.getElementById('edit_item_type').value=typ;document.getElementById('edit_inventory_num').value=inv;document.getElementById('edit_assigned_to').value=assigned;document.getElementById('editEquipmentForm').action="/edit_equipment/"+id+"/{{ username }}";new bootstrap.Modal(document.getElementById('editEquipmentModal')).show();}
document.getElementById('selectAllMulti')?.addEventListener('change',function(e){document.querySelectorAll('.multi-checkbox').forEach(cb=>cb.checked=e.target.checked);});
</script>
<div class="toast-container"></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
'''

COMPLETED_MAINTENANCE_PRINT_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>تقرير الصيانة المكتملة</title>
<style>body{font-family:Tahoma;padding:20px;direction:rtl;}h3,h4{text-align:center;}table{width:100%;border-collapse:collapse;margin-top:20px;}th,td{border:1px solid #000;padding:8px;text-align:center;}.footer{margin-top:30px;text-align:center;}.year-select{text-align:center;margin-bottom:20px;}@media print{.no-print{display:none;}}</style></head>
<body><div class="no-print" style="margin-bottom:20px;"><button onclick="window.print()">طباعة</button> | 
<select id="yearSelect" onchange="window.location.href='/print_completed_maintenance/{{ username }}?year='+this.value"><option value="{{ current_year }}">{{ current_year }}</option>{% for y in years %}<option value="{{ y }}">{{ y }}</option>{% endfor %}</select></div>
<h3>مديرية التشغيل لولاية تيبازة</h3>
<h4>تقرير الصيانة المكتملة للسنة {{ current_year }}</h4>
<table border="1"><thead><tr><th>#</th><th>المادة</th><th>رقم الجرد</th><th>تاريخ الإرسال</th><th>تاريخ العودة</th><th>المصلح</th><th>العطل</th><th>التكلفة (دج)</th></tr></thead><tbody>{% for log in logs %}<tr><td style="text-align:center">{{ loop.index }}</td><td style="text-align:center">{{ log[2] }}</td><td style="text-align:center">{{ log[3] }}</td><td style="text-align:center">{{ log[4] }}</td><td style="text-align:center">{{ log[7] }}</td><td style="text-align:center">{{ log[5] }}</td><td style="text-align:center">{{ log[6] }}</td><td style="text-align:center">{{ log[8] }}</td></tr>{% endfor %}</tbody></table><div class="footer">تم الإنشاء في {{ now }}</div></body></html>
'''

LOGS_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>سجل العمليات</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">سجل العمليات</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a><a href="/export_logs/{{ username }}?period={{ period }}&recipient={{ recipient }}&item_name={{ item_name }}" class="btn btn-outline-light btn-sm">تصدير Excel</a><button onclick="printAllDischarges()" class="btn btn-secondary btn-sm ms-2">طباعة الكل</button></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><form method="GET" class="row g-2"><div class="col-md-3"><label>الفترة</label><select name="period" class="form-select"><option value="all" {{ 'selected' if period=='all' else '' }}>الكل</option><option value="today" {{ 'selected' if period=='today' else '' }}>اليوم</option><option value="month" {{ 'selected' if period=='month' else '' }}>الشهر</option><option value="year" {{ 'selected' if period=='year' else '' }}>السنة</option></select></div><div class="col-md-3"><label>المستلم</label><input type="text" name="recipient" class="form-control" value="{{ recipient }}"></div><div class="col-md-4"><label>المادة</label><input type="text" name="item_name" class="form-control" value="{{ item_name }}"></div><div class="col-md-2"><button type="submit" class="btn btn-primary w-100">بحث</button></div></form></div>
<div class="card p-4"><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>#</th><th>المادة</th><th>الكمية</th><th>المستلم</th><th>التاريخ</th><th>ملاحظات</th><th>إجراءات</th></tr></thead><tbody>{% for row in discharges %}<tr><td class="align-middle">#{{ row[0] }}</td><td class="align-middle">{{ row[1] }}</td><td class="align-middle">{{ row[2] }}</td><td class="align-middle">{{ row[3] }}</td><td class="align-middle">{{ row[5] }}</td><td class="align-middle">{{ row[8] or '' }}</td><td class="align-middle"><a href="javascript:void(0)" onclick="printSingleDischarge({{ row[0] }})" class="btn btn-sm btn-secondary">وصل</a>{% if session.role == 'مدير' %}<a href="/delete_log/{{ row[0] }}/{{ username }}" class="btn btn-sm btn-danger ms-1" onclick="return confirm('إلغاء الوصل؟')">إلغاء</a>{% endif %}</td></tr>{% else %}<tr><td colspan="7">لا توجد نتائج</td>{% endfor %}</tbody></table></div></div></div>
<script>
function printSingleDischarge(dischargeId){window.open(`/print_discharge_by_id/${dischargeId}`,'_blank');}
function printAllDischarges(){let params=new URLSearchParams(window.location.search);window.open(`/print_all_discharges?${params.toString()}`,'_blank');}
</script>
</body></html>
'''

STATISTICS_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>الإحصائيات العامة</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">📊 الإحصائيات العامة</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm ms-2">الرئيسية</a></div></div></nav>
<div class="container mt-4"><div class="row mb-4"><div class="col-md-3"><div class="stats-card"><i class="fas fa-boxes fa-2x"></i><h2>{{ stats.total_items }}</h2><p>إجمالي المواد</p></div></div><div class="col-md-3"><div class="stats-card" style="background:linear-gradient(135deg,#f093fb,#f5576c)"><i class="fas fa-cubes fa-2x"></i><h2>{{ stats.total_quantity }}</h2><p>إجمالي الكميات</p></div></div><div class="col-md-3"><div class="stats-card" style="background:linear-gradient(135deg,#4facfe,#00f2fe)"><i class="fas fa-exchange-alt fa-2x"></i><h2>{{ stats.total_discharges }}</h2><p>عمليات السحب</p></div></div><div class="col-md-3"><div class="stats-card" style="background:linear-gradient(135deg,#43e97b,#38f9d7)"><i class="fas fa-exclamation-triangle fa-2x"></i><h2>{{ stats.low_stock_count }}</h2><p>مواد منخفضة</p></div></div></div>
<div class="row mb-4"><div class="col-md-4"><div class="stats-card" style="background:linear-gradient(135deg,#6a3093,#a044ff)"><i class="fas fa-tools fa-2x"></i><h2>{{ stats.ongoing_maintenance }}</h2><p>قيد الصيانة</p></div></div><div class="col-md-4"><div class="stats-card" style="background:linear-gradient(135deg,#1c8d3c,#31d65c)"><i class="fas fa-check-circle fa-2x"></i><h2>{{ stats.completed_maintenance }}</h2><p>صيانة مكتملة</p></div></div><div class="col-md-4"><div class="stats-card" style="background:linear-gradient(135deg,#d76d07,#f6a831)"><i class="fas fa-coins fa-2x"></i><h2>{{ "%.0f"|format(stats.total_repair_cost) }}</h2><p>توضيح تكاليف الإصلاح (دج)</p></div></div></div>
<div class="row"><div class="col-md-6"><div class="card p-4"><h5>توزيع المواد حسب الأقسام</h5><canvas id="catChart" height="250"></canvas></div></div><div class="col-md-6"><div class="card p-4"><h5>أكثر 10 مواد استهلاكاً</h5><canvas id="topChart" height="250"></canvas></div></div></div>
<div class="row mt-4"><div class="col-md-6"><div class="card p-4"><h5>القيمة الإجمالية للمخزون</h5><h2>{{ stats.total_value }} دج</h2></div></div><div class="col-md-6"><div class="card p-4"><h5>عدد المعدات المسجلة</h5><h2>{{ stats.total_equipment }} قطعة</h2></div></div></div>
<div class="row mt-4"><div class="col-md-12"><div class="card p-4"><h5>اتجاه الاستهلاك الشهري (آخر 12 شهراً)</h5><canvas id="timelineChart" height="200"></canvas></div></div></div></div>
<script>const catData={{ category_data|safe }}, topData={{ top_items_data|safe }};new Chart(document.getElementById('catChart'),{type:'pie',data:{labels:Object.keys(catData),datasets:[{data:Object.values(catData),backgroundColor:['#FF6384','#36A2EB','#FFCE56','#4BC0C0','#9966FF']}]}});new Chart(document.getElementById('topChart'),{type:'bar',data:{labels:topData.map(i=>i.name),datasets:[{label:'الكمية المسحوبة',data:topData.map(i=>i.total),backgroundColor:'#36A2EB'}]},options:{responsive:true}});fetch('/consumption_timeline').then(r=>r.json()).then(data=>{const months=data.map(d=>d.month);const totals=data.map(d=>d.total);new Chart(document.getElementById('timelineChart'),{type:'line',data:{labels:months,datasets:[{label:'الاستهلاك الشهري',data:totals,borderColor:'#f39c12',fill:false}]},options:{responsive:true}});});</script>
</body></html>
'''

PRINT_HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Décharge</title>
<style>
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:'Times New Roman',Arial,sans-serif;margin:0;padding:0;background:white;}
    .container{max-width:100%;margin:0;padding:0.5cm 1cm;}
    .header{text-align:left;margin-bottom:0;}
    .header div{margin:2px 0;font-weight:bold;}
    .decharge-title{font-size:28px;font-weight:bold;text-align:center;margin:30px 0 40px 0;}
    .info-row{margin-bottom:10px; font-size:16px;}
    .info-label{font-weight:bold;}
    table{width:100%;border-collapse:collapse;margin:20px 0;}
    th,td{border:1px solid #000;padding:8px;text-align:center;}
    .signature {margin-top:50px; text-align:center; font-weight:bold;}
    @media print{.no-print{display:none;}}
</style>
</head>
<body><button class="no-print" onclick="window.print()" style="margin:10px;padding:5px 10px;">Imprimer</button>
<div class="container"><div class="header"><div>RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE</div><div>MINISTÈRE DU TRAVAIL DE L'EMPLOI ET DE LA SÉCURITÉ SOCIALE</div><div>DIRECTION DE L'EMPLOI DE LA WILAYA TIPAZA</div><div>SERVICE DE L'ADMINISTRATION ET BUDGET</div></div>
<div class="decharge-title">DÉCHARGE N° {{ decharge_number }}</div>
<div class="info-row"><span class="info-label">Nom et prénom: </span>{{ receiver_name }}</div>
<div class="info-row"><span class="info-label">Grade / État: </span>{{ receiver_grade }}</div>
<div class="info-row"><span class="info-label">Structure / Service: </span>{{ receiver_structure }}</div>
<div class="info-row"><span class="info-label">Date de réception: </span>{{ date_received }}</div>
<div class="info-row"><span class="info-label">Lieu de réception: </span>{{ lieu_reception or 'DEW' }}</div>
<div style="margin-top: 15px;">Détails des articles remis :</div>
<table border="1"><thead><tr><th>N°</th><th>Désignation des articles</th><th>Quantité</th><th>Observations</th></tr></thead><tbody>{% for item in items %}<tr><td style="text-align:center">{{ loop.index }}</td><td style="text-align:center">{{ item.item_name }}</td><td style="text-align:center">{{ item.quantity }}</td><td style="text-align:center">{{ item.notes or '' }}</td></tr>{% endfor %}</tbody></table>
<div>Je soussigné(e), reconnais avoir reçu personnellement et en bon état les articles mentionnés ci-dessus.</div>
<div class="signature">Signature</div>
</div>
</body></html>
'''

MANAGE_BENEFICIARIES_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>إدارة المستلمين</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">إدارة المستلمين (الموظفين)</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><h5>إضافة مستلم جديد</h5><form method="POST" action="/add_beneficiary/{{ username }}" class="row g-3"><div class="col-md-4"><label>الاسم الكامل</label><input type="text" name="full_name" class="form-control" required></div><div class="col-md-3"><label>الرتبة/المنصب</label><input type="text" name="grade" class="form-control"></div><div class="col-md-3"><label>الهيكل/المصلحة</label><input type="text" name="structure" class="form-control"></div><div class="col-md-2"><button type="submit" class="btn btn-primary mt-4">إضافة</button></div></form></div>
<div class="card p-4"><h5>قائمة المستلمين</h5><table class="table table-bordered"><thead><tr><th>الاسم الكامل</th><th>الرتبة</th><th>الهيكل</th><th>إجراءات</th></tr></thead><tbody>{% for b in beneficiaries %}<tr><td class="align-middle">{{ b.full_name }}</td><td class="align-middle">{{ b.grade or '-' }}</td><td class="align-middle">{{ b.structure or '-' }}</td><td class="align-middle"><a href="/delete_beneficiary/{{ b.id }}/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف المستلم؟')">حذف</a></td></tr>{% endfor %}</tbody></table></div></div>
</body></html>
'''

MAINTENANCE_DECHARGE_FORM_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>تعديل معلومات وصل التسليم</title>'''+BASE_HTML+'''</head>
<body><div class="container mt-4"><div class="card p-4"><h4 class="mb-3">تعديل معلومات وصل التسليم</h4><form method="POST" action="/print_maintenance_decharge/{{ log_id }}/{{ username }}"><div class="row"><div class="col-md-6 mb-3"><label>رقم الوصل</label><input type="text" name="decharge_number" class="form-control" value="{{ decharge_number }}" required></div><div class="col-md-6 mb-3"><label>التاريخ</label><input type="text" name="decharge_date" class="form-control" value="{{ decharge_date }}" required placeholder="dd/mm/yyyy"></div><div class="col-md-12 mb-3"><label>المصلح / المقاول</label><input type="text" name="repair_shop" class="form-control" value="{{ repair_shop }}" required></div><div class="col-md-12 mb-3"><label>وصف العطل</label><textarea name="issue_description" class="form-control" rows="3" required>{{ issue_description }}</textarea></div><div class="col-md-12"><h5>المعدات المراد إصلاحها</h5><table class="table table-bordered" id="itemsTable"><thead><tr><th>التسمية</th><th>رقم الجرد</th><th>إجراء</th></tr></thead><tbody><tr><td><input type="text" name="item_name" class="form-control" value="{{ item_name }}" required></td><td><input type="text" name="inventory_num" class="form-control" value="{{ inventory_num }}" required></td><td><button type="button" class="btn btn-danger btn-sm remove-row">×</button></td></tr></tbody></table><button type="button" class="btn btn-sm btn-secondary" id="addRow">+ إضافة معدات</button></div></div><button type="submit" class="btn btn-primary mt-3">طباعة الوصل</button><a href="/section/maintenance/{{ username }}" class="btn btn-secondary mt-3">إلغاء</a></form></div></div>
<script>document.getElementById('addRow')?.addEventListener('click',function(){let tbody=document.querySelector('#itemsTable tbody');let newRow=tbody.insertRow();newRow.innerHTML=`<td><input type="text" name="item_name" class="form-control" required></td><td><input type="text" name="inventory_num" class="form-control" required></td><td><button type="button" class="btn btn-danger btn-sm remove-row">×</button></td>`;newRow.querySelector('.remove-row').addEventListener('click',function(){newRow.remove();});});document.querySelectorAll('.remove-row').forEach(btn=>btn.addEventListener('click',function(){btn.closest('tr').remove();}));</script>
</body></html>
'''

MAINTENANCE_DECHARGE_PRINT_HTML = '''
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Décharge Maintenance</title>
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Times New Roman',Arial,sans-serif;margin:0;padding:0;background:white;}.container{max-width:100%;margin:0;padding:0.5cm 1cm;}.header{text-align:left;margin-bottom:0;}.header div{margin:2px 0;font-weight:bold;}.decharge-title{font-size:28px;font-weight:bold;text-align:center;margin:30px 0 80px 0;}.date-line{text-align:left;margin:20px 0 20px 0;}.info-text{text-align:left;margin:15px 0;}table{width:100%;border-collapse:collapse;margin:20px 0;}th,td{border:1px solid #000;padding:8px;text-align:left;}.description{text-align:left;margin:15px 0;}.signature-row{display:flex;justify-content:space-between;margin-top:50px;}</style></head>
<body><button class="no-print" onclick="window.print()" style="margin:10px;padding:5px 10px;">Imprimer</button>
<div class="container"><div class="header"><div>RÉPUBLIQUE ALGÉRIENNE DÉMOCRATIQUE ET POPULAIRE</div><div>MINISTÈRE DU TRAVAIL DE L'EMPLOI ET DE LA SÉCURITÉ SOCIALE</div><div>DIRECTION DE L'EMPLOI DE LA WILAYA TIPAZA</div><div>SERVICE DE L'ADMINISTRATION ET BUDGET</div></div>
<div class="decharge-title">DÉCHARGE N° {{ decharge_number }}</div>
<div class="date-line"><strong>Tipaza le :</strong> {{ decharge_date }}</div>
<div class="info-text">Je soussigné(e), Chef du Service de l'Administration et du Budget, certifie avoir remis ce jour à <strong>{{ repair_shop }}</strong> l'équipement désigné ci-dessous pour diagnostic et réparation.</div>
<div class="info-text">Le prestataire reconnaît avoir réceptionné ledit équipement et s'engage à effectuer les réparations nécessaires et à le restituer en bon état de fonctionnement dans les délais convenus.</div>
<table border="1"><thead><tr><th>N°</th><th>Désignation de l'article</th><th>N° d'inventaire</th></tr></thead><tbody>{% for item in items %}<tr><td style="text-align:center">{{ loop.index }}</td><td style="text-align:center">{{ item.item_name }}</td><td style="text-align:center">{{ item.inventory_num }}</td></tr>{% endfor %}</tbody></table>
<div class="description"><strong>Description de la panne :</strong> {{ issue_description }}</div>
<div class="signature-row"><div><strong>{{ repair_shop }}</strong></div><div><strong>DIRECTION DE L'EMPLOI</strong></div></div></div>
</body></html>
'''

EDIT_DECHARGE_NUMBER_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>تعديل رقم الوصل</title>'''+BASE_HTML+'''<style>.alert-info{background-color:#d1ecf1;border-color:#bee5eb;color:#0c5460;}</style></head>
<body><div class="container mt-5"><div class="card p-4"><h4 class="text-center mb-4">تعديل رقم الوصل</h4><div class="alert alert-info text-center"><strong>آخر رقم تم استخدامه:</strong> {{ last_number if last_number else 'لا يوجد' }}</div><form method="POST" action="/confirm_decharge_number/{{ username }}"><div class="mb-3"><label>رقم الوصل (مثال: 5/2026)</label><input type="text" name="decharge_number" class="form-control" value="{{ default_number }}" required></div><button type="submit" class="btn btn-primary w-100">تأكيد وترحيل المخزون للطباعة</button><a href="/dashboard/{{ username }}" class="btn btn-secondary w-100 mt-2">إلغاء</a></form></div></div>
</body></html>
'''

PURCHASES_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>المشتريات والحسابات</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">💰 المشتريات والحسابات (مدين / دائن)</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><h5>➕ إضافة عملية شراء جديدة</h5><form method="POST" action="/add_purchase/{{ username }}"><div class="row g-2"><div class="col-md-3"><label>المورد</label><select name="supplier_id" class="form-select" required><option value="">اختر المورد...</option>{% for sup in suppliers %}<option value="{{ sup.id }}">{{ sup.name }}</option>{% endfor %}</select></div><div class="col-md-2"><label>التاريخ</label><input type="date" name="purchase_date" class="form-control" value="{{ now }}" required></div><div class="col-md-3"><label>اسم المادة</label><input type="text" name="item_name" class="form-control" required></div><div class="col-md-1"><label>الكمية</label><input type="number" name="quantity" step="0.01" class="form-control" required></div><div class="col-md-1"><label>سعر الوحدة</label><input type="number" name="unit_price" step="0.01" class="form-control" required></div><div class="col-md-2"><label>ملاحظات</label><input type="text" name="notes" class="form-control"></div><div class="col-md-12 mt-2"><button type="submit" class="btn btn-primary">تسجيل الشراء</button></div></div></form></div>
<div class="card p-4 mb-4"><h5>💰 تسجيل دفعة (سداد)</h5><form method="POST" action="/add_payment/{{ username }}"><div class="row g-2"><div class="col-md-3"><label>المورد</label><select name="supplier_id" class="form-select" required><option value="">اختر المورد...</option>{% for sup in suppliers %}<option value="{{ sup.id }}">{{ sup.name }}</option>{% endfor %}</select></div><div class="col-md-2"><label>تاريخ الدفع</label><input type="date" name="payment_date" class="form-control" value="{{ now }}" required></div><div class="col-md-2"><label>المبلغ (دج)</label><input type="number" name="amount" step="0.01" class="form-control" required></div><div class="col-md-3"><label>طريقة الدفع</label><select name="payment_method" class="form-select"><option>نقدي</option><option>شيك</option><option>تحويل بنكي</option></select></div><div class="col-md-2"><label>ملاحظات</label><input type="text" name="notes" class="form-control"></div><div class="col-md-12 mt-2"><button type="submit" class="btn btn-success">تسجيل الدفعة</button></div></div></form></div>
<div class="card p-4 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h5>🏢 الموردين والرصيد الحالي</h5><button class="btn btn-sm btn-primary" onclick="showAddSupplierModal()">➕ إضافة مورد جديد</button></div><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>المورد</th><th>إجمالي المشتريات</th><th>إجمالي المدفوعات</th><th>الرصيد (دج)</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>{% for sup in suppliers %}<tr><td class="align-middle">{{ sup.name }}</td><td class="align-middle">{{ sup.total_purchases|round(2) }}</td><td class="align-middle">{{ sup.total_payments|round(2) }}</td><td class="align-middle fw-bold {% if sup.balance > 0 %}text-danger{% elif sup.balance < 0 %}text-success{% endif %}">{% if sup.balance > 0 %}+{% elif sup.balance < 0 %}-{% endif %}{{ sup.balance|round(2) }}</td><td class="align-middle">{% if sup.balance > 0 %}<span class="badge bg-danger">علينا (مدين)</span>{% elif sup.balance < 0 %}<span class="badge bg-success">لهم (دائن)</span>{% else %}<span class="badge bg-secondary">متساوية</span>{% endif %}</td><td class="align-middle"><button class="btn btn-sm btn-info" onclick="showDetails({{ sup.id }}, '{{ sup.name }}')">تفاصيل</button><a href="/supplier_transactions/{{ sup.id }}/{{ username }}" class="btn btn-sm btn-secondary">كشف الحساب</a><button class="btn btn-sm btn-warning" onclick="editSupplier({{ sup.id }}, '{{ sup.name }}', '{{ sup.contact or '' }}', '{{ sup.address or '' }}')">تعديل</button><button class="btn btn-sm btn-danger" onclick="deleteSupplier({{ sup.id }}, '{{ sup.name }}')">حذف</button></td></tr>{% endfor %}</tbody></table></div></div></div>
<div class="modal fade" id="detailsModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 id="modalTitle">تفاصيل المعاملات</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body" id="modalBody">...</div></div></div></div>
<div class="modal fade" id="supplierModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 id="supplierModalTitle">إضافة مورد جديد</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" id="supplierForm">
                <div class="modal-body">
                    <input type="hidden" name="supplier_id" id="supplier_id">
                    <div class="mb-2">
                        <label>الاسم</label>
                        <input type="text" name="name" id="supplier_name" class="form-control" required>
                    </div>
                    <div class="mb-2">
                        <label>رقم الهاتف</label>
                        <input type="text" name="contact" id="supplier_contact" class="form-control">
                    </div>
                    <div class="mb-2">
                        <label>العنوان</label>
                        <input type="text" name="address" id="supplier_address" class="form-control">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">حفظ</button>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button>
                </div>
            </form>
        </div>
    </div>
</div>
<script>
function showDetails(supplierId,name){document.getElementById('modalTitle').innerText='تفاصيل المعاملات - '+name;fetch('/supplier_details/'+supplierId).then(r=>r.json()).then(data=>{let html='<h6>المشتريات</h6><ul>';data.purchases.forEach(p=>{html+=`<li>${p.date} - ${p.item_name} (${p.quantity} × ${p.unit_price}) = ${p.total_price} دج</li>`;});html+='</ul><h6>المدفوعات</h6><ul>';data.payments.forEach(p=>{html+=`<li>${p.date} - ${p.amount} دج (${p.method})</li>`;});html+='</ul>';document.getElementById('modalBody').innerHTML=html;bootstrap.Modal.getOrCreateInstance(document.getElementById('detailsModal')).show();});}
function showAddSupplierModal(){
    document.getElementById('supplierModalTitle').innerText='إضافة مورد جديد';
    document.getElementById('supplier_id').value='';
    document.getElementById('supplier_name').value='';
    document.getElementById('supplier_contact').value='';
    document.getElementById('supplier_address').value='';
    document.getElementById('supplierForm').action="/add_supplier/{{ username }}";
    var modal = new bootstrap.Modal(document.getElementById('supplierModal'));
    modal.show();
}
function editSupplier(id,name,contact,address){document.getElementById('supplierModalTitle').innerText='تعديل بيانات المورد';document.getElementById('supplier_id').value=id;document.getElementById('supplier_name').value=name;document.getElementById('supplier_contact').value=contact;document.getElementById('supplier_address').value=address;document.getElementById('supplierForm').action="/edit_supplier/{{ username }}";var modal = new bootstrap.Modal(document.getElementById('supplierModal'));modal.show();}
function deleteSupplier(id,name){if(confirm(`هل أنت متأكد من حذف المورد "${name}"؟ سيتم حذف جميع مشترياته ومدفوعاته تلقائياً.`)){window.location.href="/delete_supplier/"+id+"/{{ username }}";}}
</script>
</body></html>
'''

SUPPLIER_TRANSACTIONS_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>كشف حساب المورد</title>'''+BASE_HTML+'''
<style>
    @media print{.no-print{display:none;}body{padding:0;margin:0;}.container{width:100%;}.print-balance{font-size:16px;font-weight:bold;}}
    .balance-positive{color:red;}.balance-negative{color:green;}
    .table th{background-color:#f8f9fa;font-weight:bold;text-align:center;vertical-align:middle;}
    .table td{text-align:center;vertical-align:middle;}
</style>
</head>
<body><nav class="navbar navbar-custom no-print"><div class="container"><span class="navbar-brand">كشف حساب : {{ supplier.name }}</span><div><a href="/section/purchases/{{ username }}" class="btn btn-outline-light btn-sm">العودة للمشتريات</a><button onclick="window.print()" class="btn btn-outline-light btn-sm">طباعة</button></div></div></nav>
<div class="container mt-4"><div class="card p-4"><h3 class="text-center mb-4">كشف حساب المورد: {{ supplier.name }}</h3>

<h5>المشتريات</h5>
<div class="table-responsive">
    <table class="table table-bordered table-hover">
        <thead class="table-light">
            <tr>
                <th>التاريخ</th>
                <th>المادة</th>
                <th>الكمية</th>
                <th>سعر الوحدة</th>
                <th>الإجمالي</th>
                <th>ملاحظات</th>
                <th class="no-print">إجراءات</th>
            </tr>
        </thead>
        <tbody>
            {% for p in purchases %}
            <tr>
                <td class="text-nowrap align-middle">{{ p[2] }}</td>
                <td class="align-middle">{{ p[3] }}</td>
                <td class="align-middle">{{ p[4] }}</td>
                <td class="align-middle">{{ p[5] }}</td>
                <td class="align-middle">{{ p[6] }}</td>
                <td class="align-middle">{{ p[7] or '' }}</td>
                <td class="align-middle no-print">
                    <button class="btn btn-sm btn-warning" onclick="editPurchase({{ p[0] }}, '{{ p[3] }}', {{ p[4] }}, {{ p[5] }}, '{{ p[2] }}', '{{ p[7] or '' }}')">تعديل</button>
                    <a href="/delete_purchase/{{ p[0] }}/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف عملية الشراء؟')">حذف</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="7" class="text-center">لا توجد مشتريات مسجلة</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<h5 class="mt-4">المدفوعات</h5>
<div class="table-responsive">
    <table class="table table-bordered table-hover">
        <thead class="table-light">
            <tr>
                <th>التاريخ</th>
                <th>المبلغ</th>
                <th>طريقة الدفع</th>
                <th>ملاحظات</th>
                <th class="no-print">إجراءات</th>
            </tr>
        </thead>
        <tbody>
            {% for pay in payments %}
            <tr>
                <td class="text-nowrap align-middle">{{ pay[2] }}</td>
                <td class="align-middle">{{ pay[3] }}</td>
                <td class="align-middle">{{ pay[4] }}</td>
                <td class="align-middle">{{ pay[5] or '' }}</td>
                <td class="align-middle no-print">
                    <button class="btn btn-sm btn-warning" onclick="editPayment({{ pay[0] }}, {{ pay[3] }}, '{{ pay[2] }}', '{{ pay[4] }}', '{{ pay[5] or '' }}')">تعديل</button>
                    <a href="/delete_payment/{{ pay[0] }}/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف الدفعة؟')">حذف</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="5" class="text-center">لا توجد مدفوعات مسجلة</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="mt-3 print-balance"><strong>إجمالي المشتريات:</strong> {{ total_purchases }} دج &nbsp;|&nbsp;<strong>إجمالي المدفوعات:</strong> {{ total_payments }} دج &nbsp;|&nbsp;<strong>الرصيد المتبقي:</strong> <span class="{% if balance > 0 %}balance-positive{% elif balance < 0 %}balance-negative{% endif %}">{% if balance > 0 %}+{% elif balance < 0 %}-{% endif %}{{ balance }} دج</span> ({% if balance > 0 %}علينا (مدين){% elif balance < 0 %}لهم (دائن){% else %}متساوية{% endif %})</div>
</div></div>

<div class="modal fade" id="editPurchaseModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>تعديل الشراء</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="editPurchaseForm"><div class="modal-body"><input type="hidden" name="purchase_id" id="edit_purchase_id"><div class="mb-2"><label>التاريخ</label><input type="date" name="purchase_date" id="edit_purchase_date" class="form-control" required></div><div class="mb-2"><label>اسم المادة</label><input type="text" name="item_name" id="edit_item_name" class="form-control" required></div><div class="mb-2"><label>الكمية</label><input type="number" name="quantity" id="edit_quantity" step="0.01" class="form-control" required></div><div class="mb-2"><label>سعر الوحدة</label><input type="number" name="unit_price" id="edit_unit_price" step="0.01" class="form-control" required></div><div class="mb-2"><label>ملاحظات</label><input type="text" name="notes" id="edit_notes" class="form-control"></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">حفظ</button><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button></div></form></div></div></div>

<div class="modal fade" id="editPaymentModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>تعديل الدفعة</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="editPaymentForm"><div class="modal-body"><input type="hidden" name="payment_id" id="edit_payment_id"><div class="mb-2"><label>التاريخ</label><input type="date" name="payment_date" id="edit_payment_date" class="form-control" required></div><div class="mb-2"><label>المبلغ</label><input type="number" name="amount" id="edit_amount" step="0.01" class="form-control" required></div><div class="mb-2"><label>طريقة الدفع</label><select name="payment_method" id="edit_payment_method" class="form-select"><option>نقدي</option><option>شيك</option><option>تحويل بنكي</option></select></div><div class="mb-2"><label>ملاحظات</label><input type="text" name="notes" id="edit_payment_notes" class="form-control"></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">حفظ</button><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">إلغاء</button></div></form></div></div></div>

<script>
function editPurchase(id,name,qty,price,date,notes){document.getElementById('edit_purchase_id').value=id;document.getElementById('edit_item_name').value=name;document.getElementById('edit_quantity').value=qty;document.getElementById('edit_unit_price').value=price;document.getElementById('edit_purchase_date').value=date;document.getElementById('edit_notes').value=notes;document.getElementById('editPurchaseForm').action="/edit_purchase/{{ supplier.id }}/{{ username }}";bootstrap.Modal.getOrCreateInstance(document.getElementById('editPurchaseModal')).show();}
function editPayment(id,amount,date,method,notes){document.getElementById('edit_payment_id').value=id;document.getElementById('edit_amount').value=amount;document.getElementById('edit_payment_date').value=date;document.getElementById('edit_payment_method').value=method;document.getElementById('edit_payment_notes').value=notes;document.getElementById('editPaymentForm').action="/edit_payment/{{ supplier.id }}/{{ username }}";bootstrap.Modal.getOrCreateInstance(document.getElementById('editPaymentModal')).show();}
</script>
</body></html>
'''

MANAGE_USERS_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><title>إدارة المستخدمين</title>'''+BASE_HTML+'''</head>
<body>
<nav class="navbar navbar-custom"><div class="container"><span class="navbar-brand">إدارة المستخدمين</span><div><a href="/dashboard/{{ username }}" class="btn btn-outline-light btn-sm">الرئيسية</a></div></div></nav>
<div class="container mt-4"><div class="card p-4 mb-4"><h5>تغيير كلمة المرور الخاصة بي</h5><form method="POST" action="/change_password/{{ username }}"><div class="row"><div class="col-md-4"><label>كلمة المرور الحالية</label><input type="password" name="old_password" class="form-control" required></div><div class="col-md-4"><label>كلمة المرور الجديدة</label><input type="password" name="new_password" class="form-control" required></div><div class="col-md-4"><button type="submit" class="btn btn-warning mt-4">تغيير كلمة المرور</button></div></div></form></div>
{% if session.role == 'مدير' %}<div class="card p-4"><h5>إضافة مستخدم جديد</h5><form method="POST" action="/add_user/{{ username }}"><div class="row g-2"><div class="col-md-3"><label>اسم المستخدم</label><input type="text" name="username" class="form-control" required></div><div class="col-md-3"><label>كلمة المرور</label><input type="password" name="password" class="form-control" required></div><div class="col-md-3"><label>الدور</label><select name="role" class="form-select"><option>موظف</option><option>مشرف</option><option>مدير</option></select></div><div class="col-md-3"><label>الاسم الكامل</label><input type="text" name="full_name" class="form-control"></div><div class="col-md-12"><button type="submit" class="btn btn-primary">إضافة مستخدم</button></div></div></form></div>
<div class="card p-4 mt-4"><h5>قائمة المستخدمين</h5><div class="table-responsive"><table class="table table-bordered"><thead><tr><th>اسم المستخدم</th><th>الدور</th><th>الاسم الكامل</th><th>إجراءات</th></tr></thead><tbody>{% for u in users %}<tr><td class="align-middle">{{ u[0] }}</td><td class="align-middle">{{ u[2] }}</td><td class="align-middle">{{ u[4] or '' }}</td><td class="align-middle"><button class="btn btn-sm btn-warning" onclick="editUser('{{ u[0] }}', '{{ u[2] }}', '{{ u[4] or '' }}')">تعديل</button>{% if u[0] != 'admin' %}<a href="/delete_user/{{ u[0] }}/{{ username }}" class="btn btn-sm btn-danger" onclick="return confirm('حذف مستخدم؟')">حذف</a>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div>{% endif %}</div>
<div class="modal fade" id="editUserModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5>تعديل المستخدم</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form method="POST" id="editUserForm"><div class="modal-body"><input type="hidden" name="username" id="edit_username"><div class="mb-2"><label>الدور</label><select name="role" id="edit_role" class="form-select"><option>موظف</option><option>مشرف</option><option>مدير</option></select></div><div class="mb-2"><label>الاسم الكامل</label><input type="text" name="full_name" id="edit_full_name" class="form-control"></div><div class="mb-2"><label>كلمة المرور الجديدة (اتركها فارغة لعدم التغيير)</label><input type="password" name="new_password" class="form-control"></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">حفظ</button></div></form></div></div></div>
<script>
function editUser(username,role,full_name){document.getElementById('edit_username').value=username;document.getElementById('edit_role').value=role;document.getElementById('edit_full_name').value=full_name;document.getElementById('editUserForm').action="/edit_user/{{ username }}";bootstrap.Modal.getOrCreateInstance(document.getElementById('editUserModal')).show();}
</script>
</body></html>
'''

# -------------------- ROUTES --------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        if not conn:
            flash("خطأ في الاتصال بقاعدة البيانات", "danger")
            return render_template_string(LOGIN_HTML)
        cur = conn.cursor()
        cur.execute("SELECT username, password, role, theme FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and user[1] == hash_password(password):
            session['username'] = user[0]
            session['role'] = user[2]
            session['cart'] = []
            session['theme'] = user[3] if user[3] else 'light'
            session.permanent = True
            return redirect(url_for('dashboard', username=user[0]))
        flash("بيانات الدخول غير صحيحة", "danger")
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if 'username' in session:
        theme = request.json.get('theme', 'light')
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET theme=%s WHERE username=%s", (theme, session['username']))
            conn.commit()
            cur.close()
            conn.close()
            session['theme'] = theme
    return '', 204

@app.route('/dashboard/<username>')
def dashboard(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    stats = get_stats()
    low_stock = get_low_stock()
    return render_template_string(DASHBOARD_HTML, username=username, stats=stats, low_stock=low_stock, categories=CATEGORIES)

@app.route('/section/<slug>/<username>')
def section(slug, username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    
    if slug == 'general_inv':
        conn = get_db_connection()
        if not conn:
            flash("خطأ في الاتصال بقاعدة البيانات", "danger")
            return redirect(url_for('dashboard', username=username))
        cur = conn.cursor()
        cur.execute("SELECT * FROM general_inventory ORDER BY id DESC")
        items = cur.fetchall()
        next_num = get_next_ordre_num()
        cur.close()
        conn.close()
        return render_template_string(GENERAL_INV_HTML, username=username, items=items, next_num=next_num)
    
    elif slug == 'maintenance':
        conn = get_db_connection()
        if not conn:
            flash("خطأ في الاتصال بقاعدة البيانات", "danger")
            return redirect(url_for('dashboard', username=username))
        cur = conn.cursor()
        cur.execute("SELECT * FROM maintenance_equipment ORDER BY id DESC")
        equipment = cur.fetchall()
        cur.execute("SELECT * FROM maintenance_logs WHERE status='sent' ORDER BY id DESC")
        ongoing = cur.fetchall()
        cur.execute("SELECT * FROM maintenance_logs WHERE status='returned' ORDER BY id DESC LIMIT 50")
        completed = cur.fetchall()
        cur.close()
        conn.close()
        return render_template_string(MAINTENANCE_HTML, username=username, equipment=equipment, ongoing=ongoing, completed=completed, now=datetime.now())
    
    elif slug == 'purchases':
        conn = get_db_connection()
        if not conn:
            flash("خطأ في الاتصال بقاعدة البيانات", "danger")
            return redirect(url_for('dashboard', username=username))
        cur = conn.cursor()
        cur.execute("SELECT * FROM suppliers ORDER BY id DESC")
        suppliers_raw = cur.fetchall()
        suppliers = []
        for s in suppliers_raw:
            cur.execute("SELECT COALESCE(SUM(total_price), 0) FROM purchases WHERE supplier_id=%s", (s[0],))
            tot_p = cur.fetchone()[0] or 0
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE supplier_id=%s", (s[0],))
            tot_pay = cur.fetchone()[0] or 0
            balance = tot_p - tot_pay
            suppliers.append({
                'id': s[0], 'name': s[1], 'contact': s[2] or '', 'address': s[3] or '',
                'total_purchases': tot_p, 'total_payments': tot_pay, 'balance': balance
            })
        cur.close()
        conn.close()
        return render_template_string(PURCHASES_HTML, username=username, suppliers=suppliers, now=datetime.now().strftime('%Y-%m-%d'))
    
    else:
        conn = get_db_connection()
        if not conn:
            flash("خطأ في الاتصال بقاعدة البيانات", "danger")
            return redirect(url_for('dashboard', username=username))
        cur = conn.cursor()
        cur.execute("SELECT id, item_name, quantity, category, inventory_num, min_stock, unit, price FROM inventory WHERE category=%s", (slug,))
        items = cur.fetchall()
        cur.close()
        conn.close()
        beneficiaries = get_beneficiaries()
        cat_name = CATEGORIES.get(slug, {}).get('ar', slug)
        return render_template_string(SECTION_COMMON, cat_name=cat_name, cat_slug=slug, username=username, items=items, beneficiaries=beneficiaries, units=UNITS, now=datetime.now())

@app.route('/manage_users/<username>')
def manage_users(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('dashboard', username=username))
    cur = conn.cursor()
    cur.execute("SELECT username, password, role, theme, full_name FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(MANAGE_USERS_HTML, username=username, users=users)

@app.route('/change_password/<username>', methods=['POST'])
def change_password(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    old_p = request.form.get('old_password')
    new_p = request.form.get('new_password')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('manage_users', username=username))
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    if row and row[0] == hash_password(old_p):
        cur.execute("UPDATE users SET password=%s WHERE username=%s", (hash_password(new_p), username))
        conn.commit()
        flash("تم تغيير كلمة المرور بنجاح", "success")
    else:
        flash("كلمة المرور الحالية غير صحيحة", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('manage_users', username=username))

@app.route('/add_user/<username>', methods=['POST'])
def add_user(username):
    if 'username' not in session or session['role'] != 'مدير':
        return redirect(url_for('login'))
    u = request.form.get('username')
    p = request.form.get('password')
    r = request.form.get('role')
    f = request.form.get('full_name')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('manage_users', username=username))
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s)", (u, hash_password(p), r, f))
        conn.commit()
        flash("تم إضافة المستخدم بنجاح", "success")
    except Exception as e:
        flash(f"خطأ: {str(e)}", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('manage_users', username=username))

@app.route('/edit_user/<username>', methods=['POST'])
def edit_user(username):
    if 'username' not in session or session['role'] != 'مدير':
        return redirect(url_for('login'))
    u = request.form.get('username')
    r = request.form.get('role')
    f = request.form.get('full_name')
    new_p = request.form.get('new_password')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('manage_users', username=username))
    cur = conn.cursor()
    if new_p:
        cur.execute("UPDATE users SET role=%s, full_name=%s, password=%s WHERE username=%s", (r, f, hash_password(new_p), u))
    else:
        cur.execute("UPDATE users SET role=%s, full_name=%s WHERE username=%s", (r, f, u))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم تعديل المستخدم بنجاح", "success")
    return redirect(url_for('manage_users', username=username))

@app.route('/delete_user/<target_username>/<username>')
def delete_user(target_username, username):
    if 'username' not in session or session['role'] != 'مدير' or target_username == 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('manage_users', username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username=%s", (target_username,))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم حذف المستخدم من النظام", "success")
    return redirect(url_for('manage_users', username=username))

@app.route('/get_items_by_category/<slug>')
def get_items_by_category(slug):
    conn = get_db_connection()
    if not conn:
        return jsonify({'items': []})
    cur = conn.cursor()
    cur.execute("SELECT item_name FROM inventory WHERE category=%s", (slug,))
    items = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({'items': items})

@app.route('/add_item/<slug>/<username>', methods=['POST'])
def add_item(slug, username):
    if 'username' not in session or session['role'] not in ['مدير', 'مشرف']:
        return redirect(url_for('login'))
    name = request.form.get('item_name')
    qty = int(request.form.get('quantity') or 0)
    min_s = int(request.form.get('min_stock') or 5)
    unit = request.form.get('unit') or 'قطعة'
    price = float(request.form.get('price') or 0)
    inv_num = request.form.get('inventory_num') or ''
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO inventory (item_name, quantity, category, inventory_num, min_stock, unit, price, last_updated) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (name, qty, slug, inv_num, min_s, unit, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        flash("تم إضافة المادة بنجاح", "success")
    except Exception as e:
        flash(f"خطأ: {str(e)}", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/edit_item/<slug>/<username>', methods=['POST'])
def edit_item(slug, username):
    if 'username' not in session or session['role'] not in ['مدير', 'مشرف']:
        return redirect(url_for('login'))
    item_id = request.form.get('item_id')
    name = request.form.get('item_name')
    qty = int(request.form.get('quantity') or 0)
    min_s = int(request.form.get('min_stock') or 5)
    unit = request.form.get('unit') or 'قطعة'
    price = float(request.form.get('price') or 0)
    inv_num = request.form.get('inventory_num') or ''
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    cur = conn.cursor()
    cur.execute("""UPDATE inventory SET item_name=%s, quantity=%s, min_stock=%s, unit=%s, price=%s, inventory_num=%s, last_updated=%s 
                   WHERE id=%s""",
                (name, qty, min_s, unit, price, inv_num, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم التحديث بنجاح", "success")
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/delete_item/<int:item_id>/<slug>/<username>')
def delete_item(item_id, slug, username):
    if 'username' not in session or session['role'] != 'مدير':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM inventory WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم حذف المادة نهائياً من الجرد الحالي", "success")
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    username = request.form.get('username')
    slug = request.form.get('category')
    item_name = request.form.get('item_name')
    qty = int(request.form.get('quantity') or 1)
    if 'cart' not in session:
        session['cart'] = []
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM inventory WHERE item_name=%s", (item_name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0] >= qty:
        session['cart'].append({'item_name': item_name, 'quantity': qty})
        session.modified = True
        flash("أضيفت المادة بنجاح إلى سلة الصرف الجاري", "success")
    else:
        flash("الكمية المتاحة في المخزن غير كافية", "danger")
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/clear_cart/<slug>/<username>')
def clear_cart(slug, username):
    session['cart'] = []
    session.modified = True
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/remove_from_cart/<int:index>/<slug>/<username>')
def remove_from_cart(index, slug, username):
    if 'cart' in session and len(session['cart']) > index:
        session['cart'].pop(index)
        session.modified = True
    return redirect(url_for('section', slug=slug, username=username))

@app.route('/prepare_discharge/<username>', methods=['POST'])
def prepare_discharge(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    session['discharge_receiver_id'] = request.form.get('receiver_id')
    session['discharge_notes'] = request.form.get('notes')
    session['discharge_slug'] = request.form.get('category')
    last_num = get_last_decharge_number()
    default_num = get_next_decharge_number_for_inventory()
    return render_template_string(EDIT_DECHARGE_NUMBER_HTML, username=username, last_number=last_num, default_number=default_num)

@app.route('/confirm_decharge_number/<username>', methods=['POST'])
def confirm_decharge_number(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    decharge_num = request.form.get('decharge_number')
    receiver_id = session.get('discharge_receiver_id')
    notes = session.get('discharge_notes')
    slug = session.get('discharge_slug')
    cart = session.get('cart', [])
    if not cart:
        flash("السلة فارغة حالياً", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug=slug, username=username))
    cur = conn.cursor()
    cur.execute("SELECT full_name, grade, structure FROM beneficiaries WHERE id=%s", (receiver_id,))
    rec_row = cur.fetchone()
    rec_name = rec_row[0] if rec_row else ''
    rec_grade = rec_row[1] if rec_row else ''
    rec_structure = rec_row[2] if rec_row else ''
    discharge_items = []
    for ci in cart:
        cur.execute("SELECT quantity, inventory_num FROM inventory WHERE item_name=%s", (ci['item_name'],))
        inv_row = cur.fetchone()
        if inv_row and inv_row[0] >= ci['quantity']:
            new_qty = inv_row[0] - ci['quantity']
            inv_num = inv_row[1] if inv_row else ''
            cur.execute("UPDATE inventory SET quantity=%s, last_updated=%s WHERE item_name=%s", 
                        (new_qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ci['item_name']))
            cur.execute("""INSERT INTO discharges (item_name, quantity, receiver_id, user_charged, date_time, category, inventory_num, notes, decharge_number) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (ci['item_name'], ci['quantity'], receiver_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), slug, inv_num, notes, decharge_num))
            discharge_items.append({'item_name': ci['item_name'], 'quantity': ci['quantity'], 'notes': notes})
    conn.commit()
    cur.close()
    conn.close()
    session['cart'] = []
    session.modified = True
    return render_template_string(PRINT_HTML, decharge_number=decharge_num, receiver_name=rec_name, receiver_grade=rec_grade, receiver_structure=rec_structure, date_received=datetime.now().strftime("%Y-%m-%d"), items=discharge_items)

@app.route('/print_discharge_by_id/<int:discharge_id>')
def print_discharge_by_id(discharge_id):
    conn = get_db_connection()
    if not conn:
        return "خطأ في الاتصال بقاعدة البيانات", 500
    cur = conn.cursor()
    cur.execute("""SELECT d.decharge_number, b.full_name, b.grade, b.structure, d.date_time, d.item_name, d.quantity, d.notes 
                   FROM discharges d LEFT JOIN beneficiaries b ON d.receiver_id = b.id WHERE d.id=%s""", (discharge_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        item = {'item_name': row[5], 'quantity': row[6], 'notes': row[7]}
        return render_template_string(PRINT_HTML, decharge_number=row[0], receiver_name=row[1], receiver_grade=row[2], receiver_structure=row[3], date_received=row[4], items=[item])
    return "الوصل غير موجود", 404

@app.route('/print_all_discharges')
def print_all_discharges():
    period = request.args.get('period', 'all')
    recipient = request.args.get('recipient','')
    item = request.args.get('item_name','')
    data = get_filtered_logs(period, None, None, recipient, item)
    items = []
    for row in data:
        items.append({'item_name': f"{row[1]} (للمستلم: {row[3]})", 'quantity': row[2], 'notes': row[8]})
    return render_template_string(PRINT_HTML, decharge_number="سجل مجمع", receiver_name="متعدد", receiver_grade="-", receiver_structure="-", date_received=datetime.now().strftime("%Y-%m-%d"), items=items)

@app.route('/logs/<username>')
def logs(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    period = request.args.get('period', 'all')
    recipient = request.args.get('recipient', '')
    item_name = request.args.get('item_name', '')
    data = get_filtered_logs(period, None, None, recipient, item_name)
    return render_template_string(LOGS_HTML, username=username, discharges=data, period=period, recipient=recipient, item_name=item_name)

@app.route('/delete_log/<int:log_id>/<username>')
def delete_log(log_id, username):
    if 'username' not in session or session['role'] != 'مدير':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('logs', username=username))
    cur = conn.cursor()
    cur.execute("SELECT item_name, quantity FROM discharges WHERE id=%s", (log_id,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE inventory SET quantity = quantity + %s WHERE item_name=%s", (row[1], row[0]))
        cur.execute("DELETE FROM discharges WHERE id=%s", (log_id,))
        conn.commit()
        flash("تم إلغاء ترحيل الوصل وإعادة السلع المدفوعة إلى المخزون الجاري", "success")
    cur.close()
    conn.close()
    return redirect(url_for('logs', username=username))

@app.route('/manage_beneficiaries/<username>')
def manage_beneficiaries(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    bens = get_beneficiaries()
    return render_template_string(MANAGE_BENEFICIARIES_HTML, username=username, beneficiaries=bens)

@app.route('/add_beneficiary/<username>', methods=['POST'])
def add_beneficiary_route(username):
    name = request.form.get('full_name')
    grade = request.form.get('grade', '')
    struct = request.form.get('structure', '')
    add_beneficiary(name, grade, struct)
    flash("تم تسجيل المستلم بنجاح في قاعدة البيانات", "success")
    return redirect(url_for('manage_beneficiaries', username=username))

@app.route('/delete_beneficiary/<int:b_id>/<username>')
def delete_beneficiary(b_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('manage_beneficiaries', username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM beneficiaries WHERE id=%s", (b_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم الحذف بنجاح", "success")
    return redirect(url_for('manage_beneficiaries', username=username))

@app.route('/export_inventory/<username>')
def export_inventory(username):
    out = export_inventory_excel()
    return send_file(out, download_name="inventory_tipaza.xlsx", as_attachment=True)

@app.route('/export_logs/<username>')
def export_logs(username):
    period = request.args.get('period', 'all')
    recipient = request.args.get('recipient', '')
    item_name = request.args.get('item_name', '')
    data = get_filtered_logs(period, None, None, recipient, item_name)
    out = export_logs_excel(data)
    return send_file(out, download_name="logs_discharges.xlsx", as_attachment=True)

@app.route('/backup/<username>')
def backup(username):
    try:
        backup_path = backup_db()
        return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))
    except Exception as e:
        flash(f"فشل توليد النسخة: {str(e)}", "danger")
        return redirect(url_for('dashboard', username=username))

@app.route('/import_inventory/<username>', methods=['POST'])
def import_inventory(username):
    file = request.files.get('file')
    if file:
        success, msg = import_inventory_excel(file)
        flash(msg, "success" if success else "danger")
    else:
        flash("الرجاء اختيار ملف جرد صالح بصيغة Excel أولاً", "danger")
    return redirect(url_for('dashboard', username=username))

@app.route('/add_general_item/<username>', methods=['POST'])
def add_general_item(username):
    ord_num = request.form.get('ordre_num')
    inv_num = request.form.get('inventory_num')
    desig = request.form.get('designation')
    bureau = request.form.get('bureau_num')
    obs = request.form.get('observation')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='general_inv', username=username))
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO general_inventory (ordre_num, inventory_num, designation, bureau_num, observation, created_at, updated_at) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (ord_num, inv_num, desig, bureau, obs, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        flash("تمت الإضافة بنجاح", "success")
    except Exception as e:
        flash(f"خطأ: {str(e)}", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='general_inv', username=username))

@app.route('/edit_general_item/<int:item_id>/<username>', methods=['POST'])
def edit_general_item(item_id, username):
    ord_num = request.form.get('ordre_num')
    inv_num = request.form.get('inventory_num')
    desig = request.form.get('designation')
    bureau = request.form.get('bureau_num')
    obs = request.form.get('observation')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='general_inv', username=username))
    cur = conn.cursor()
    cur.execute("""UPDATE general_inventory SET ordre_num=%s, inventory_num=%s, designation=%s, bureau_num=%s, observation=%s, updated_at=%s 
                   WHERE id=%s""",
                (ord_num, inv_num, desig, bureau, obs, datetime.now().isoformat(), item_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم التعديل", "success")
    return redirect(url_for('section', slug='general_inv', username=username))

@app.route('/delete_general_item/<int:item_id>/<username>')
def delete_general_item(item_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='general_inv', username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM general_inventory WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='general_inv', username=username))

@app.route('/print_general_inventory_filtered', methods=['POST'])
def print_general_inventory_filtered():
    bureau_num = request.form.get('bureau_num', '_____')
    office_occupant = request.form.get('office_occupant', '')
    employees = request.form.get('employees', '')
    raw_data = request.form.get('data', '[]')
    items = json.loads(raw_data)
    return render_template_string(GENERAL_PRINT_FILTERED_HTML, bureau_num=bureau_num, office_occupant=office_occupant, employees=employees, items=items)

@app.route('/add_equipment/<username>', methods=['POST'])
def add_equipment(username):
    name = request.form.get('item_name')
    typ = request.form.get('item_type')
    inv = request.form.get('inventory_num')
    assigned = request.form.get('assigned_to')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO maintenance_equipment (item_name, item_type, inventory_num, assigned_to, created_at) 
                       VALUES (%s, %s, %s, %s, %s)""",
                    (name, typ, inv, assigned, datetime.now().isoformat()))
        conn.commit()
        flash("تم حفظ العتاد بنجاح", "success")
    except Exception as e:
        flash(f"خطأ: {str(e)}", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/edit_equipment/<int:eq_id>/<username>', methods=['POST'])
def edit_equipment(eq_id, username):
    name = request.form.get('item_name')
    typ = request.form.get('item_type')
    inv = request.form.get('inventory_num')
    assigned = request.form.get('assigned_to')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    cur.execute("""UPDATE maintenance_equipment SET item_name=%s, item_type=%s, inventory_num=%s, assigned_to=%s WHERE id=%s""",
                (name, typ, inv, assigned, eq_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/delete_equipment/<int:eq_id>/<username>')
def delete_equipment(eq_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM maintenance_equipment WHERE id=%s", (eq_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/send_equipment_to_maintenance/<username>', methods=['POST'])
def send_equipment_to_maintenance(username):
    eq_id = request.form.get('equipment_id')
    shop = request.form.get('repair_shop')
    desc = request.form.get('issue_description')
    ret_d = request.form.get('expected_return_date')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    cur.execute("SELECT item_name, inventory_num FROM maintenance_equipment WHERE id=%s", (eq_id,))
    eq = cur.fetchone()
    if eq:
        decharge_num = get_next_decharge_number_for_maintenance()
        cur.execute("""INSERT INTO maintenance_logs (equipment_id, item_name, inventory_num, sent_date, repair_shop, issue_description, expected_return_date, status, decharge_number) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (eq_id, eq[0], eq[1], datetime.now().strftime("%Y-%m-%d"), shop, desc, ret_d, 'sent', decharge_num))
        cur.execute("UPDATE maintenance_equipment SET status='maintenance' WHERE id=%s", (eq_id,))
        conn.commit()
        flash("تم إرسال العتاد لورشة الصيانة الجارية بنجاح", "success")
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/send_multi_equipment_to_maintenance/<username>', methods=['POST'])
def send_multi_equipment_to_maintenance(username):
    eq_ids = request.form.getlist('equipment_ids')
    shop = request.form.get('repair_shop')
    desc = request.form.get('issue_description')
    ret_d = request.form.get('expected_return_date')
    if not eq_ids:
        flash("الرجاء اختيار مادة واحدة على الأقل لإدراجها في الكشف المشترك", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    decharge_num = get_next_decharge_number_for_maintenance()
    for eq_id in eq_ids:
        cur.execute("SELECT item_name, inventory_num FROM maintenance_equipment WHERE id=%s", (eq_id,))
        eq = cur.fetchone()
        if eq:
            cur.execute("""INSERT INTO maintenance_logs (equipment_id, item_name, inventory_num, sent_date, repair_shop, issue_description, expected_return_date, status, decharge_number) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (eq_id, eq[0], eq[1], datetime.now().strftime("%Y-%m-%d"), shop, desc, ret_d, 'sent', decharge_num))
            cur.execute("UPDATE maintenance_equipment SET status='maintenance' WHERE id=%s", (eq_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم إرسال الأجهزة دفعة واحدة بموجب وصل واحد", "success")
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/return_equipment_from_maintenance/<int:log_id>/<username>', methods=['POST'])
def return_equipment_from_maintenance(log_id, username):
    actual_d = request.form.get('actual_return_date')
    cost = float(request.form.get('repair_cost') or 0)
    notes = request.form.get('notes', '')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    cur.execute("SELECT equipment_id FROM maintenance_logs WHERE id=%s", (log_id,))
    row = cur.fetchone()
    if row:
        cur.execute("""UPDATE maintenance_logs SET actual_return_date=%s, repair_cost=%s, notes=%s, status='returned' WHERE id=%s""",
                    (actual_d, cost, notes, log_id))
        cur.execute("UPDATE maintenance_equipment SET status='available' WHERE id=%s", (row[0],))
        conn.commit()
        flash("تم تسجيل الاستلام النهائي للعتاد بعد الصيانة وإعادته للحالة المتاحة", "success")
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/delete_maintenance_log/<int:log_id>/<status>/<username>')
def delete_maintenance_log(log_id, status, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='maintenance', username=username))
    cur = conn.cursor()
    if status == 'ongoing':
        cur.execute("SELECT equipment_id FROM maintenance_logs WHERE id=%s", (log_id,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE maintenance_equipment SET status='available' WHERE id=%s", (row[0],))
    cur.execute("DELETE FROM maintenance_logs WHERE id=%s", (log_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='maintenance', username=username))

@app.route('/print_maintenance_slip/<int:log_id>/<username>')
def print_maintenance_slip(log_id, username):
    conn = get_db_connection()
    if not conn:
        return "خطأ في الاتصال بقاعدة البيانات", 500
    cur = conn.cursor()
    cur.execute("SELECT * FROM maintenance_logs WHERE id=%s", (log_id,))
    log = cur.fetchone()
    cur.close()
    conn.close()
    if log:
        items = [{'item_name': log[2], 'inventory_num': log[3]}]
        return render_template_string(MAINTENANCE_DECHARGE_PRINT_HTML, 
                                      decharge_number=log[12], decharge_date=log[4], 
                                      repair_shop=log[5], items=items, issue_description=log[6])
    return "غير موجود", 404

@app.route('/maintenance_decharge_form/<int:log_id>/<username>')
def maintenance_decharge_form(log_id, username):
    conn = get_db_connection()
    if not conn:
        return "خطأ في الاتصال بقاعدة البيانات", 500
    cur = conn.cursor()
    cur.execute("SELECT * FROM maintenance_logs WHERE id=%s", (log_id,))
    log = cur.fetchone()
    cur.close()
    conn.close()
    if log:
        return render_template_string(MAINTENANCE_DECHARGE_FORM_HTML, log_id=log_id, username=username,
                                      decharge_number=log[12], decharge_date=log[4], 
                                      repair_shop=log[5], issue_description=log[6],
                                      item_name=log[2], inventory_num=log[3])
    return "غير موجود", 404

@app.route('/print_maintenance_decharge/<int:log_id>/<username>', methods=['POST'])
def print_maintenance_decharge(log_id, username):
    d_num = request.form.get('decharge_number')
    d_date = request.form.get('decharge_date')
    shop = request.form.get('repair_shop')
    desc = request.form.get('issue_description')
    names = request.form.getlist('item_name')
    invs = request.form.getlist('inventory_num')
    items = []
    for i in range(len(names)):
        items.append({'item_name': names[i], 'inventory_num': invs[i]})
    return render_template_string(MAINTENANCE_DECHARGE_PRINT_HTML, 
                                  decharge_number=d_num, 
                                  decharge_date=d_date, 
                                  repair_shop=shop, 
                                  items=items, 
                                  issue_description=desc)

@app.route('/print_completed_maintenance/<username>')
def print_completed_maintenance(username):
    year = request.args.get('year', datetime.now().year)
    logs = get_completed_maintenance_by_year(year)
    years = [datetime.now().year - i for i in range(5)]
    return render_template_string(COMPLETED_MAINTENANCE_PRINT_HTML, username=username, current_year=year, logs=logs, years=years, now=datetime.now().strftime("%Y-%m-%d %H:%M"))

@app.route('/add_purchase/<username>', methods=['POST'])
def add_purchase(username):
    sup_id = request.form.get('supplier_id')
    p_date = request.form.get('purchase_date')
    name = request.form.get('item_name')
    qty = float(request.form.get('quantity') or 0)
    price = float(request.form.get('unit_price') or 0)
    notes = request.form.get('notes', '')
    tot = qty * price
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("""INSERT INTO purchases (supplier_id, purchase_date, item_name, quantity, unit_price, total_price, notes, created_at, updated_at) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (sup_id, p_date, name, qty, price, tot, notes, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم قيد الفاتورة بنجاح وتحديث حساب المستحقات للمورد", "success")
    return redirect(url_for('section', slug='purchases', username=username))

@app.route('/add_payment/<username>', methods=['POST'])
def add_payment(username):
    sup_id = request.form.get('supplier_id')
    p_date = request.form.get('payment_date')
    amount = float(request.form.get('amount') or 0)
    method = request.form.get('payment_method')
    notes = request.form.get('notes', '')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("""INSERT INTO payments (supplier_id, payment_date, amount, payment_method, notes, created_at) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (sup_id, p_date, amount, method, notes, datetime.now().isoformat()))
    conn.commit()
    cur.close()
    conn.close()
    flash("تم تسجيل عملية الدفع والسداد بنجاح", "success")
    return redirect(url_for('section', slug='purchases', username=username))

@app.route('/add_supplier/<username>', methods=['POST'])
def add_supplier(username):
    name = request.form.get('name')
    contact = request.form.get('contact', '')
    address = request.form.get('address', '')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("INSERT INTO suppliers (name, contact, address, created_at) VALUES (%s, %s, %s, %s)", (name, contact, address, datetime.now().isoformat()))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='purchases', username=username))

@app.route('/edit_supplier/<username>', methods=['POST'])
def edit_supplier(username):
    sup_id = request.form.get('supplier_id')
    name = request.form.get('name')
    contact = request.form.get('contact', '')
    address = request.form.get('address', '')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("UPDATE suppliers SET name=%s, contact=%s, address=%s WHERE id=%s", (name, contact, address, sup_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='purchases', username=username))

@app.route('/delete_supplier/<int:sup_id>/<username>')
def delete_supplier(sup_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("DELETE FROM purchases WHERE supplier_id=%s", (sup_id,))
    cur.execute("DELETE FROM payments WHERE supplier_id=%s", (sup_id,))
    cur.execute("DELETE FROM suppliers WHERE id=%s", (sup_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('section', slug='purchases', username=username))

@app.route('/supplier_details/<int:supplier_id>')
def supplier_details(supplier_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'purchases': [], 'payments': []})
    cur = conn.cursor()
    cur.execute("SELECT purchase_date as date, item_name, quantity, unit_price, total_price FROM purchases WHERE supplier_id=%s", (supplier_id,))
    purchases = cur.fetchall()
    cur.execute("SELECT payment_date as date, amount, payment_method as method FROM payments WHERE supplier_id=%s", (supplier_id,))
    payments = cur.fetchall()
    cur.close()
    conn.close()
    purchases_list = [{'date': p[0], 'item_name': p[1], 'quantity': p[2], 'unit_price': p[3], 'total_price': p[4]} for p in purchases]
    payments_list = [{'date': p[0], 'amount': p[1], 'method': p[2]} for p in payments]
    return jsonify({'purchases': purchases_list, 'payments': payments_list})

@app.route('/supplier_transactions/<int:supplier_id>/<username>')
def supplier_transactions(supplier_id, username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("SELECT * FROM suppliers WHERE id=%s", (supplier_id,))
    supplier = cur.fetchone()
    cur.execute("SELECT * FROM purchases WHERE supplier_id=%s ORDER BY purchase_date DESC", (supplier_id,))
    purchases = cur.fetchall()
    cur.execute("SELECT * FROM payments WHERE supplier_id=%s ORDER BY payment_date DESC", (supplier_id,))
    payments = cur.fetchall()
    cur.execute("SELECT COALESCE(SUM(total_price), 0) FROM purchases WHERE supplier_id=%s", (supplier_id,))
    tot_p = cur.fetchone()[0] or 0
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE supplier_id=%s", (supplier_id,))
    tot_pay = cur.fetchone()[0] or 0
    balance = tot_p - tot_pay
    cur.close()
    conn.close()
    return render_template_string(SUPPLIER_TRANSACTIONS_HTML, supplier=supplier, purchases=purchases, payments=payments, total_purchases=tot_p, total_payments=tot_pay, balance=balance, username=username)

@app.route('/edit_purchase/<int:supplier_id>/<username>', methods=['POST'])
def edit_purchase(supplier_id, username):
    p_id = request.form.get('purchase_id')
    p_date = request.form.get('purchase_date')
    name = request.form.get('item_name')
    qty = float(request.form.get('quantity') or 0)
    price = float(request.form.get('unit_price') or 0)
    notes = request.form.get('notes', '')
    tot = qty * price
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('supplier_transactions', supplier_id=supplier_id, username=username))
    cur = conn.cursor()
    cur.execute("""UPDATE purchases SET purchase_date=%s, item_name=%s, quantity=%s, unit_price=%s, total_price=%s, notes=%s, updated_at=%s 
                   WHERE id=%s""",
                (p_date, name, qty, price, tot, notes, datetime.now().isoformat(), p_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('supplier_transactions', supplier_id=supplier_id, username=username))

@app.route('/delete_purchase/<int:p_id>/<username>')
def delete_purchase(p_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("SELECT supplier_id FROM purchases WHERE id=%s", (p_id,))
    row = cur.fetchone()
    sid = row[0] if row else 1
    cur.execute("DELETE FROM purchases WHERE id=%s", (p_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('supplier_transactions', supplier_id=sid, username=username))

@app.route('/edit_payment/<int:supplier_id>/<username>', methods=['POST'])
def edit_payment(supplier_id, username):
    pay_id = request.form.get('payment_id')
    p_date = request.form.get('payment_date')
    amount = float(request.form.get('amount') or 0)
    method = request.form.get('payment_method')
    notes = request.form.get('notes', '')
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('supplier_transactions', supplier_id=supplier_id, username=username))
    cur = conn.cursor()
    cur.execute("UPDATE payments SET payment_date=%s, amount=%s, payment_method=%s, notes=%s WHERE id=%s",
                (p_date, amount, method, notes, pay_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('supplier_transactions', supplier_id=supplier_id, username=username))

@app.route('/delete_payment/<int:pay_id>/<username>')
def delete_payment(pay_id, username):
    conn = get_db_connection()
    if not conn:
        flash("خطأ في الاتصال بقاعدة البيانات", "danger")
        return redirect(url_for('section', slug='purchases', username=username))
    cur = conn.cursor()
    cur.execute("SELECT supplier_id FROM payments WHERE id=%s", (pay_id,))
    row = cur.fetchone()
    sid = row[0] if row else 1
    cur.execute("DELETE FROM payments WHERE id=%s", (pay_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('supplier_transactions', supplier_id=sid, username=username))

@app.route('/consumption_stats')
def consumption_stats():
    slug = request.args.get('category')
    period_type = request.args.get('period_type')
    year = request.args.get('year')
    month = request.args.get('month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    item_name = request.args.get('item_name')
    receiver = request.args.get('receiver', '')
    conn = get_db_connection()
    if not conn:
        return jsonify({'html': '<p class="text-danger">خطأ في الاتصال بقاعدة البيانات</p>'})
    cur = conn.cursor()
    q = """SELECT d.item_name, COALESCE(SUM(d.quantity), 0) FROM discharges d 
           LEFT JOIN beneficiaries b ON d.receiver_id = b.id WHERE d.category=%s"""
    p = [slug]
    if period_type == 'year' and year:
        q += " AND d.date_time LIKE %s"; p.append(str(year) + '%')
    elif period_type == 'month' and month:
        q += " AND d.date_time LIKE %s"; p.append(month + '%')
    elif period_type == 'custom' and start_date and end_date:
        q += " AND d.date_time::date BETWEEN %s AND %s"; p.extend([start_date, end_date])
    if item_name and item_name != 'all':
        q += " AND d.item_name = %s"; p.append(item_name)
    if receiver:
        q += " AND b.full_name LIKE %s"; p.append(f"%{receiver}%")
    q += " GROUP BY d.item_name"
    cur.execute(q, p)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    html = '<table class="table table-sm table-bordered"><thead><tr><th>المادة</th><th>إجمالي الاستهلاك</th></tr></thead><tbody>'
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td></tr>"
    if not rows:
        html += '<tr><td colspan="2" class="text-center">لا توجد سجلات استهلاك مطابقة للفترة المختارة</td></tr>'
    html += '</tbody></table>'
    return jsonify({'html': html})

@app.route('/purchase_needs/<slug>')
def purchase_needs(slug):
    current_year = datetime.now().year
    last_year = current_year - 1
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    cur = conn.cursor()
    cur.execute("SELECT item_name, unit, price FROM inventory WHERE category=%s", (slug,))
    inv_items = cur.fetchall()
    data = []
    for name, unit, price in inv_items:
        cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM discharges WHERE item_name=%s AND date_time LIKE %s", (name, str(last_year) + '%'))
        last_val = cur.fetchone()[0] or 0
        suggested = int(last_val * 1.1) if last_val > 0 else 5
        data.append({
            'name': name, 'unit': unit or 'قطعة', 'price': price or 0,
            'last_year_consumption': last_val, 'suggested_quantity': suggested
        })
    cur.close()
    conn.close()
    return jsonify(data)

@app.route('/export_purchase_needs', methods=['POST'])
def export_purchase_needs():
    req_data = request.json or []
    df = pd.DataFrame(req_data)
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='توقعات_الشراء')
    out.seek(0)
    return send_file(out, download_name="purchase_needs_forecast.xlsx", as_attachment=True)

@app.route('/statistics/<username>')
def statistics(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    stats = get_stats()
    return render_template_string(STATISTICS_HTML, username=username, stats=stats, category_data=stats.get('category_data', {}), top_items_data=stats.get('top_items_data', []))

@app.route('/consumption_timeline')
def consumption_timeline_route():
    data = get_consumption_timeline()
    return jsonify(data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
