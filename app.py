from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
# تغيير اسم الملف يضمن بناء قاعدة بيانات نظيفة وخالية من الأخطاء السابقة فوراً
DB_NAME = "storage_v2.db"

if not os.path.exists('static'):
    os.makedirs('static')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password TEXT, role TEXT
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT UNIQUE, quantity INTEGER, category TEXT
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discharges (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT, quantity INTEGER,
            receiver TEXT, user_charged TEXT, date_time TEXT, category TEXT
        )''')
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users VALUES ('admin', '1234', 'مدير')")
        cursor.execute("INSERT INTO users VALUES ('user1', '0000', 'موظف')")
        
        # سلع افتراضية موزعة على الأقسام
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('ورق طباعة A4 (80 غرام)', 150, 'papers')")
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('قلم حبر جاف (أزرق)', 500, 'papers')")
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('حبر طابعة HP 85A', 30, 'hardware')")
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('لوحة مفاتيح USB', 15, 'hardware')")
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('سائل تنظيف الأرضيات 5L', 40, 'cleaning')")
        cursor.execute("INSERT OR IGNORE INTO inventory (item_name, quantity, category) VALUES ('صابون سائل للأيدي', 60, 'cleaning')")
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# --- واجهات العرض وتصاميم الـ HTML ---
# ==========================================

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl" id="html-tag">
<head>
    <meta charset="UTF-8"><title>مديرية التشغيل لولاية تيبازة - تسجيل الدخول</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #2c3e50, #1abc9c); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background: white; padding: 35px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); width: 380px; text-align: center; border-top: 6px solid #e67e22; position: relative; }
        .gov-title { font-size: 13px; color: #7f8c8d; font-weight: bold; margin-bottom: 5px; line-height: 1.4; }
        .main-title { font-size: 18px; color: #2c3e50; font-weight: bold; margin-bottom: 20px; }
        .logo-placeholder { width: 100px; height: 100px; margin: 0 auto 15px auto; border-radius: 50%; background: #f4f6f9; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 2px solid #ddd; }
        .logo-placeholder img { width: 100%; height: 100%; object-fit: cover; }
        input, button { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-size: 15px; }
        input:focus { border-color: #1abc9c; outline: none; box-shadow: 0 0 5px rgba(26,188,156,0.3); }
        button { background-color: #2c3e50; color: white; border: none; cursor: pointer; font-weight: bold; transition: background 0.3s; }
        button:hover { background-color: #1a252f; }
        .error { color: #e74c3c; font-size: 14px; font-weight: bold; }
        .lang-switch { position: absolute; top: 15px; left: 15px; background: #f4f6f9; padding: 5px 10px; border-radius: 20px; font-size: 12px; cursor: pointer; font-weight: bold; border: 1px solid #ddd; color: #34495e; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="lang-switch" onclick="toggleLanguage()" id="lang-btn">FR</div>
        <div class="gov-title" id="gov-text">الجمهورية الجزائرية الديمقراطية الشعبية<br>وزارة العمل والتشغيل والضمان الاجتماعي</div>
        <div class="logo-placeholder">
            <img src="/static/logo.png" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
            <span style="display:none; font-weight:bold; color:#27ae60; font-size:12px;">لوغو المديرية</span>
        </div>
        <div class="main-title" id="main-text">مديرية التشغيل لولاية تيبازة<br><span style="font-size:14px; color:#7f8c8d;">نظام تسيير المخزن المركزي</span></div>
        <form method="POST">
            <input type="text" name="username" id="username-field" placeholder="اسم المستخدم" required>
            <input type="password" name="password" id="password-field" placeholder="كلمة المرور" required>
            <button type="submit" id="login-btn-text">دخول</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
    </div>

    <script>
        let currentLang = 'ar';
        function toggleLanguage() {
            const html = document.getElementById('html-tag');
            const govText = document.getElementById('gov-text');
            const mainText = document.getElementById('main-text');
            const usernameField = document.getElementById('username-field');
            const passwordField = document.getElementById('password-field');
            const loginBtn = document.getElementById('login-btn-text');
            const langBtn = document.getElementById('lang-btn');

            if (currentLang === 'ar') {
                html.setAttribute('dir', 'ltr'); html.setAttribute('lang', 'fr');
                govText.innerHTML = "République Algérienne Démocratique et Populaire<br>Ministère de l'Emploi et de la Sécurité Sociale";
                mainText.innerHTML = "Direction de l'Emploi - Tipaza<br><span style='font-size:14px; color:#7f8c8d;'>Gestion de Stock Central</span>";
                usernameField.placeholder = "Nom d'utilisateur"; passwordField.placeholder = "Mot de passe";
                loginBtn.innerText = "Se Connecter"; langBtn.innerText = "AR";
                currentLang = 'fr';
            } else {
                html.setAttribute('dir', 'rtl'); html.setAttribute('lang', 'ar');
                govText.innerHTML = "الجمهورية الجزائرية الديمقراطية الشعبية<br>وزارة العمل والتشغيل والضمان الاجتماعي";
                mainText.innerHTML = "مديرية التشغيل لولاية تيبازة<br><span style='font-size:14px; color:#7f8c8d;'>نظام تسيير المخزن المركزي</span>";
                usernameField.placeholder = "اسم المستخدم"; passwordField.placeholder = "كلمة المرور";
                loginBtn.innerText = "دخول"; langBtn.innerText = "FR";
                currentLang = 'ar';
            }
        }
    </script>
</body>
</html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl" id="html-tag">
<head>
    <meta charset="UTF-8"><title>لوحة تسيير مخزن مديرية التشغيل</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 15px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 4px solid #1abc9c; }
        .header-title-box { display: flex; align-items: center; gap: 15px; }
        .header-logo { width: 50px; height: 50px; background: white; border-radius: 50%; overflow: hidden; display: flex; align-items: center; justify-content: center; }
        .header-logo img { width: 100%; height: 100%; object-fit: cover; }
        .container { margin-top: 30px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 25px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); text-align: center; border-top: 6px solid #3498db; transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
        .btn { display: inline-block; margin-top: 15px; padding: 10px 25px; background: #2c3e50; color: white; border-radius: 5px; text-decoration: none; font-weight: bold; }
        .btn-logout { background: #e74c3c; color: white; padding: 8px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; }
        .top-ctrls { display: flex; align-items: center; gap: 15px; }
        .lang-btn { background: #1abc9c; color: white; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; border: none; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title-box">
            <div class="header-logo"><img src="/static/logo.png" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"><span style="display:none; font-weight:bold; color:#2c3e50; font-size:9px;">لوغو</span></div>
            <div>
                <h3 style="margin:0;" id="nav-head">مديرية التشغيل لولاية تيبازة - المخزن الرئيسي</h3>
                <small style="color:#1abc9c;" id="nav-sub">المستخدم الحالي: {{ username }}</small>
            </div>
        </div>
        <div class="top-ctrls">
            <button class="lang-btn" onclick="toggleLanguage()" id="lang-btn">FR</button>
            <a href="/" class="btn-logout" id="logout-btn">تسجيل الخروج</a>
        </div>
    </div>

    <div class="container">
        <div class="card" style="border-top-color: #3498db;">
            <h2 id="c1-title">📄 الأوراق واللوازم المكتبية</h2>
            <p id="c1-desc">تسيير مخزون السجلات، الأوراق، الأقلام والمستندات الإدارية.</p>
            <a href="/section/papers/{{ username }}" class="btn" id="c1-btn">دخول القسم</a>
        </div>
        <div class="card" style="border-top-color: #e67e22;">
            <h2 id="c2-title">🖥️ الحبر وعتاد الإعلام الآلي</h2>
            <p id="c2-desc">متابعة مخزون حبر الطابعات، لوحات المفاتيح والأجهزة الملحقة.</p>
            <a href="/section/hardware/{{ username }}" class="btn" style="background:#e67e22;" id="c2-btn">دخول القسم</a>
        </div>
        <div class="card" style="border-top-color: #2ecc71;">
            <h2 id="c3-title">🧼 مواد ومستهلكات التنظيف</h2>
            <p id="c3-desc">مراقبة وتوزيع سوائل التنظيف والمطهرات الخاصة بالمديرية.</p>
            <a href="/section/cleaning/{{ username }}" class="btn" style="background:#2ecc71;" id="c3-btn">دخول القسم</a>
        </div>
        <div class="card" style="border-top-color: #9b59b6;">
            <h2 id="c4-title">📊 السجلات والتقارير الدورية</h2>
            <p id="c4-desc">استخراج وصولات التسليم (Décharges) وإعداد الجرد الدوري السنوي.</p>
            <a href="/logs/{{ username }}" class="btn" style="background:#9b59b6;" id="c4-btn">عرض السجل والتقارير</a>
        </div>
    </div>

    <script>
        let currentLang = 'ar';
        function toggleLanguage() {
            const html = document.getElementById('html-tag');
            const langBtn = document.getElementById('lang-btn');
            const logoutBtn = document.getElementById('logout-btn');
            const navHead = document.getElementById('nav-head');
            const c1Title = document.getElementById('c1-title'); const c1Desc = document.getElementById('c1-desc'); const c1Btn = document.getElementById('c1-btn');
            const c2Title = document.getElementById('c2-title'); const c2Desc = document.getElementById('c2-desc'); const c2Btn = document.getElementById('c2-btn');
            const c3Title = document.getElementById('c3-title'); const c3Desc = document.getElementById('c3-desc'); const c3Btn = document.getElementById('c3-btn');
            const c4Title = document.getElementById('c4-title'); const c4Desc = document.getElementById('c4-desc'); const c4Btn = document.getElementById('c4-btn');

            if (currentLang === 'ar') {
                html.setAttribute('dir', 'ltr'); html.setAttribute('lang', 'fr');
                navHead.innerText = "Direction de l'Emploi Tipaza - Stock Central";
                logoutBtn.innerText = "Déconnexion"; langBtn.innerText = "AR";
                c1Title.innerText = "📄 Papiers & Fournitures de Bureau"; c1Desc.innerText = "Gestion du stock de papier, registres, stylos et fournitures."; c1Btn.innerText = "Entrer";
                c2Title.innerText = "🖥️ Encre & Matériel Informatique"; c2Desc.innerText = "Suivi des cartouches d'encre, claviers et consommables."; c2Btn.innerText = "Entrer";
                c3Title.innerText = "🧼 Produits de Nettoyage"; c3Desc.innerText = "Contrôle des détergents, désinfectants et articles d'hygiène."; c3Btn.innerText = "Entrer";
                c4Title.innerText = "📊 Registres & Rapports Périodiques"; c4Desc.innerText = "Extraction des décharges et états de mouvements."; c4Btn.innerText = "Afficher";
                currentLang = 'fr';
            } else {
                html.setAttribute('dir', 'rtl'); html.setAttribute('lang', 'ar');
                navHead.innerText = "مديرية التشغيل لولاية تيبازة - المخزن الرئيسي";
                logoutBtn.innerText = "تسجيل الخروج"; langBtn.innerText = "FR";
                c1Title.innerText = "📄 الأوراق واللوازم المكتبية"; c1Desc.innerText = "تسيير مخزون السجلات، الأوراق، الأقلام والمستندات الإدارية."; c1Btn.innerText = "دخول القسم";
                c2Title.innerText = "🖥️ الحبر وعتاد الإعلام الآلي"; c2Desc.innerText = "متابعة مخزون حبر الطابعات، لوحات المفاتيح والأجهزة الملحقة."; c2Btn.innerText = "دخول القسم";
                c3Title.innerText = "🧼 مواد ومستهلكات التنظيف"; c3Desc.innerText = "مراقبة وتوزيع سوائل التنظيف والمطهرات الخاصة بالمديرية."; c3Btn.innerText = "دخول القسم";
                c4Title.innerText = "📊 السجلات والتقارير الدورية"; c4Desc.innerText = "استخراج وصولات التسليم (Décharges) وإعداد الجرد الدوري السنوي."; c4Btn.innerText = "عرض السجل والتقارير";
                currentLang = 'ar';
            }
        }
    </script>
</body>
</html>
'''

SECTION_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>قسم: {{ cat_title_ar }}</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .header { background: {{ cat_color }}; color: white; padding: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-top: 20px; }
        .box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; border: 1px solid #ddd; text-align: right; }
        th { background: #f2f2f2; }
        select, input, button { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        button { background: #2ecc71; color: white; border: none; font-size: 16px; cursor: pointer; }
        .back-link { color: white; text-decoration: none; font-weight: bold; }
        .admin-box { border-top: 5px solid #e67e22; } .admin-box button { background: #e67e22; }
        .admin-box-new { border-top: 5px solid #9b59b6; } .admin-box-new button { background: #9b59b6; }
        
        .icon-btn { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px 6px; margin: 0 2px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s ease; vertical-align: middle; }
        .icon-btn:hover { transform: scale(1.2); }
        .btn-edit-name { color: #3498db; background-color: #e8f4fd; }
        .btn-edit-name:hover { background-color: #3498db; color: white; }
        .btn-delete-item { color: #e74c3c; background-color: #fceae9; }
        .btn-delete-item:hover { background-color: #e74c3c; color: white; }
        .btn-update-qty { color: #e67e22; background-color: #fdf2e9; margin-right: 10px; }
        .btn-update-qty:hover { background-color: #e67e22; color: white; }
        
        .flex-container { display: flex; justify-content: space-between; align-items: center; }
        .btn-print-inv { background: #2c3e50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 15px; font-weight: bold; }
        .alert { padding: 10px; margin: 10px 0; border-radius: 5px; font-weight: bold; }
        .success { background: #d4edda; color: #155724; } .error { background: #f8d7da; color: #721c24; }
    </style>
    <script>
        function renameItem(oldName) {
            var newName = prompt("أدخل الاسم الجديد للمنتج:", oldName);
            if (newName && newName.trim() !== "") {
                window.location.href = "/section/{{ cat_slug }}/{{ username }}/rename?old=" + encodeURIComponent(oldName) + "&new=" + encodeURIComponent(newName.trim());
            }
        }
        function updateQty(itemName, currentQty) {
            var newQty = prompt("تعديل الكمية المتبقية لـ '" + itemName + "' إلى الرقم الجديد:", currentQty);
            if (newQty !== null && newQty.trim() !== "" && !isNaN(newQty)) {
                window.location.href = "/section/{{ cat_slug }}/{{ username }}/update_qty?item=" + encodeURIComponent(itemName) + "&qty=" + encodeURIComponent(newQty.trim());
            }
        }
        function deleteItem(itemName) {
            if (confirm("هل أنت متأكد من حذف '" + itemName + "' نهائياً؟")) {
                window.location.href = "/section/{{ cat_slug }}/{{ username }}/delete?item=" + encodeURIComponent(itemName);
            }
        }
    </script>
</head>
<body>
    <div class="header">
        <h2>قسم: {{ cat_title_ar }} (الحساب: {{ username }})</h2>
        <div>
            <a href="/print_inventory/{{ cat_slug }}" target="_blank" class="btn-print-inv" style="margin-left:15px; background:#27ae60;">🖨️ طباعة حالة هذا القسم</a>
            <a href="/dashboard/{{ username }}" class="back-link">← العودة للرئيسية</a>
        </div>
    </div>
    
    {% if success %}<div class="alert success">{{ success }}</div>{% endif %}
    {% if error %}<div class="alert error">{{ error }}</div>{% endif %}

    <div class="grid">
        <div class="box">
            <h3>📋 السلع الحالية في المخزن</h3>
            <table>
                <thead>
                    <tr><th>اسم المادة</th><th>الكمية المتبقية</th></tr>
                </thead>
                <tbody>
                    {% for row in inventory %}
                    <tr>
                        <td>
                            <div class="flex-container">
                                <span><strong>{{ row[0] }}</strong></span>
                                {% if username == 'admin' %}
                                <div>
                                    <button onclick="renameItem('{{ row[0] }}')" class="icon-btn btn-edit-name" title="تعديل الاسم">✏️</button>
                                    <button onclick="deleteItem('{{ row[0] }}')" class="icon-btn btn-delete-item" title="حذف">🗑️</button>
                                </div>
                                {% endif %}
                            </div>
                        </td>
                        <td>
                            <div class="flex-container">
                                <span style="color: {% if row[1] < 15 %}red{% else %}green{% endif %}; font-weight: bold;">{{ row[1] }} قطعة/علبة</span>
                                {% if username == 'admin' %}
                                <button onclick="updateQty('{{ row[0] }}', '{{ row[1] }}')" class="icon-btn btn-update-qty" title="تعديل مباشر للكمية">🔄</button>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div>
            <div class="box" style="border-top: 5px solid #2ecc71;">
                <h3>تسليم مادة (خصم من المخزن)</h3>
                <form method="POST" action="/section/{{ cat_slug }}/{{ username }}/discharge">
                    <label>اختر المادة:</label>
                    <select name="item">
                        {% for row in inventory %}
                            <option value="{{ row[0] }}">{{ row[0] }}</option>
                        {% endfor %}
                    </select>
                    <label>الكمية الصادرة:</label>
                    <input type="number" name="qty" min="1" value="1" required>
                    <label>المصلحة المستلمة:</label>
                    <input type="text" name="receiver" placeholder="مثلا: مصلحة الميزانية والوسائل" required>
                    <button type="submit">تأكيد السحب والخصم</button>
                </form>
            </div>

            {% if username == 'admin' %}
            <div class="box admin-box">
                <h3>⚙️ تموين سلعة (زيادة كمية)</h3>
                <form method="POST" action="/section/{{ cat_slug }}/{{ username }}/restock">
                    <label>اختر المادة:</label>
                    <select name="item_name">
                        {% for row in inventory %}
                            <option value="{{ row[0] }}">{{ row[0] }}</option>
                        {% endfor %}
                    </select>
                    <label>الكمية المضافة:</label>
                    <input type="number" name="qty" min="1" value="50" required>
                    <button type="submit">إضافة الكمية للمخزن ↑</button>
                </form>
            </div>

            <div class="box admin-box-new">
                <h3>➕ إضافة منتج جديد في هذا القسم</h3>
                <form method="POST" action="/section/{{ cat_slug }}/{{ username }}/add_new">
                    <label>اسم السلعة الجديدة:</label>
                    <input type="text" name="new_item_name" required>
                    <label>الكمية الابتدائية:</label>
                    <input type="number" name="qty" min="0" value="10" required>
                    <button type="submit">إدراج في القائمة +</button>
                </form>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

LOGS_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>سجل العمليات والتقارير</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .header { background: #9b59b6; color: white; padding: 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .box { background: white; padding: 20px; border-radius: 8px; margin-top:20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; border: 1px solid #ddd; text-align: right; }
        th { background: #f2f2f2; }
        .btn-print { background: #3498db; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; font-size: 13px; }
        .back-link { color: white; text-decoration: none; font-weight: bold; }
        .filter-form { display: flex; gap: 15px; align-items: center; background: #eee; padding: 15px; border-radius: 5px; margin-bottom: 15px; flex-wrap: wrap; }
        .filter-form select, .filter-form input, .filter-form button { padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        .btn-filter { background: #9b59b6; color: white; border: none; cursor: pointer; font-weight: bold; }
        .btn-print-report { background: #e67e22; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; margin-right: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h2>سجل التوزيع والتقارير - مديرية التشغيل تيبازة</h2>
        <a href="/dashboard/{{ username }}" class="back-link">← العودة للرئيسية</a>
    </div>
    
    <div class="box">
        <h3>🔍 تصفية وجرد التوزيعات حسب الوقت</h3>
        <form method="GET" class="filter-form">
            <select name="period" onchange="this.form.submit()">
                <option value="all" {% if period == 'all' %}selected{% endif %}>كل الأوقات</option>
                <option value="today" {% if period == 'today' %}selected{% endif %}>اليوم</option>
                <option value="month" {% if period == 'month' %}selected{% endif %}>الشهر الحالي</option>
                <option value="year" {% if period == 'year' %}selected{% endif %}>السنة الحالية</option>
                <option value="custom" {% if period == 'custom' %}selected{% endif %}>حيز زمني مخصص</option>
            </select>
            {% if period == 'custom' %}
                <input type="date" name="start_date" value="{{ start_date }}">
                <input type="date" name="end_date" value="{{ end_date }}">
                <button type="submit" class="btn-filter">تطبيق</button>
            {% endif %}
            <a href="/print_report?period={{ period }}&start_date={{ start_date }}&end_date={{ end_date }}" target="_blank" class="btn-print-report">🖨️ طباعة التقرير الحالي كوثيقة رسمية</a>
        </form>

        <table>
            <thead>
                <tr><th>رقم الوصل</th><th>المادة</th><th>الكمية</th><th>المستلم</th><th>الموظف الصارف</th><th>التاريخ</th><th>الإجراء</th></tr>
            </thead>
            <tbody>
                {% for log in discharges %}
                <tr>
                    <td>#{{ log[0] }}</td>
                    <td>{{ log[1] }}</td>
                    <td><strong>{{ log[2] }}</strong></td>
                    <td>{{ log[3] }}</td>
                    <td><mark>{{ log[4] }}</mark></td>
                    <td style="font-size:12px; color:#666;">{{ log[5] }}</td>
                    <td><a href="/print/{{ log[0] }}" target="_blank" class="btn-print">🖨️ الوصل</a></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
'''

PRINT_INVENTORY_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>تقرير حالة جرد المخزون</title>
    <style>
        body { font-family: 'Arial', sans-serif; padding: 40px; background: white; }
        .text-center { text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 30px; }
        th, td { padding: 12px; border: 1px solid #000; text-align: right; }
        th { background: #eee; }
        .btn-print { background: #2c3e50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: block; max-width: 150px; margin: 20px auto; text-align: center; }
        @media print { .btn-print { display: none; } }
    </style>
</head>
<body>
    <h3 class="text-center">الجمهورية الجزائرية الديمقراطية الشعبية</h3>
    <h4 class="text-center">وزارة العمل والتشغيل والضمان الاجتماعي - مديرية التشغيل لولاية تيبازة</h4>
    <h2 class="text-center" style="text-decoration: underline; margin-top:30px;">الحالة العامة لجرد السلع المتبقية لقسم ({{ cat_name }})</h2>
    <p><strong>تاريخ الاستخراج:</strong> {{ current_time }}</p>
    <table>
        <thead>
            <tr><th>الرقم</th><th>اسم المادة</th><th>الكمية المتوفرة حالياً</th></tr>
        </thead>
        <tbody>
            {% for row in inventory %}
            <tr>
                <td>{{ loop.index }}</td>
                <td><strong>{{ row[0] }}</strong></td>
                <td><strong>{{ row[1] }}</strong> وحدة</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <div style="margin-top: 50px; text-align: left; padding-left: 50px;"><strong>ختم وتوقيع المديرية:</strong></div>
    <a href="#" onclick="window.print(); return false;" class="btn-print">إرسال للطابعة</a>
</body>
</html>
'''

PRINT_REPORT_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>تقرير التوزيعات الدوري</title>
    <style>
        body { font-family: 'Arial', sans-serif; padding: 40px; background: white; }
        .text-center { text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 30px; }
        th, td { padding: 12px; border: 1px solid #000; text-align: right; }
        th { background: #eee; }
        .btn-print { background: #2c3e50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: block; max-width: 150px; margin: 20px auto; text-align: center; }
        @media print { .btn-print { display: none; } }
    </style>
</head>
<body>
    <h3 class="text-center">الجمهورية الجزائرية الديمقراطية الشعبية</h3>
    <h4 class="text-center">مديرية التشغيل لولاية تيبازة</h4>
    <h2 class="text-center" style="text-decoration: underline; margin-top:30px;">تقرير وتفاصيل حركية التوزيع والاستهلاك</h2>
    <table>
        <thead>
            <tr><th>رقم الوصل</th><th>المادة</th><th>الكمية</th><th>الجهة المستلمة</th><th>الموظف الصارف</th><th>التاريخ</th></tr>
        </thead>
        <tbody>
            {% for log in discharges %}
            <tr>
                <td>#{{ log[0] }}</td>
                <td>{{ log[1] }}</td>
                <td><strong>{{ log[2] }}</strong></td>
                <td>{{ log[3] }}</td>
                <td>{{ log[4] }}</td>
                <td>{{ log[5] }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <a href="#" onclick="window.print(); return false;" class="btn-print">إرسال للطابعة</a>
</body>
</html>
'''

PRINT_HTML = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>وصل استلام رقم #{{ log[0] }}</title>
    <style>
        body { font-family: 'Arial', sans-serif; padding: 40px; background: white; }
        .ticket-box { border: 2px dashed #000; padding: 30px; max-width: 600px; margin: 0 auto; }
        .text-center { text-align: center; }
        .title { font-size: 22px; font-weight: bold; margin-bottom: 5px; text-decoration: underline; }
        .signature-section { margin-top: 60px; display: flex; justify-content: space-between; }
        .btn-trigger { background: #2c3e50; color:white; padding:10px; text-align:center; display:block; max-width:200px; margin:20px auto; text-decoration:none; border-radius:5px;}
        @media print { .btn-trigger { display: none; } .ticket-box { border: 2px solid #000; } }
    </style>
</head>
<body>
    <div class="ticket-box">
        <h3 class="text-center" style="margin:0;">الجمهورية الجزائرية الديمقراطية الشعبية</h3>
        <h4 class="text-center" style="margin:5px 0 20px 0; font-size:14px;">مديرية التشغيل لولاية تيبازة - المخزن المركزي</h4>
        <div class="title text-center">وصل تسليم مستهلكات (Décharge)</div>
        <p class="text-center"><strong>رقم الوصل:</strong> {{ log[0] }} / 2026</p>
        <div class="meta-info">
            <p><strong>تاريخ العملية:</strong> {{ log[5] }}</p>
            <p><strong>الموظف الموزع:</strong> {{ log[4] }}</p>
            <p><strong>الجهة المستلمة (المصلحة):</strong> {{ log[3] }}</p>
            <table style="width:100%; border-collapse: collapse; font-size:18px; margin-top:15px;">
                <thead><tr style="background:#eee;"><th style="border:1px solid #000; padding:8px;">المادة المستلمة</th><th style="border:1px solid #000; padding:8px; text-align:center;">الكمية</th></tr></thead>
                <tbody><tr><td style="border:1px solid #000; padding:12px;">{{ log[1] }}</td><td style="border:1px solid #000; padding:12px; text-align:center; font-weight:bold;">{{ log[2] }}</td></tr></tbody>
            </table>
        </div>
        <div class="signature-section">
            <div><strong>توقيع أمين المخزن:</strong><br><br>............</div>
            <div style="text-align: left;"><strong>توقيع المستلم والختم:</strong><br><br>............</div>
        </div>
    </div>
    <a href="#" onclick="window.print(); return false;" class="btn-trigger">👉 اضغط هنا للطباعة</a>
</body>
</html>
'''

# ==========================================
# --- مسارات التحكم البرمجية (Routes) ---
# ==========================================

CATEGORIES = {
    'papers': {'ar': 'الأوراق واللوازم المكتبية', 'color': '#3498db'},
    'hardware': {'ar': 'الحبر وعتاد الإعلام الآلي', 'color': '#e67e22'},
    'cleaning': {'ar': 'مواد ومستهلكات التنظيف', 'color': '#2ecc71'}
}

def get_filtered_logs(period, start_date, end_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    query = "SELECT id, item_name, quantity, receiver, user_charged, date_time FROM discharges"
    params = []
    if period == 'today':
        query += " WHERE date_time LIKE ?"
        params.append(f"{datetime.now().strftime('%Y-%m-%d')}%")
    elif period == 'month':
        query += " WHERE date_time LIKE ?"
        params.append(f"{datetime.now().strftime('%Y-%m')}%")
    elif period == 'year':
        query += " WHERE date_time LIKE ?"
        params.append(f"{datetime.now().strftime('%Y')}%")
    elif period == 'custom' and start_date and end_date:
        query += " WHERE date(date_time) BETWEEN date(?) AND date(?)"
        params.append(start_date)
        params.append(end_date)
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()
    return data

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user: return redirect(url_for('dashboard', username=username))
        error = "اسم المستخدم أو كلمة المرور خاطئة!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/dashboard/<username>')
def dashboard(username):
    return render_template_string(DASHBOARD_HTML, username=username)

@app.route('/section/<cat_slug>/<username>', methods=['GET'])
def section_view(cat_slug, username):
    if cat_slug not in CATEGORIES: return "القسم غير موجود"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, quantity FROM inventory WHERE category=?", (cat_slug,))
    inventory_data = cursor.fetchall()
    conn.close()
    return render_template_string(
        SECTION_HTML, username=username, inventory=inventory_data,
        cat_slug=cat_slug, cat_title_ar=CATEGORIES[cat_slug]['ar'], cat_color=CATEGORIES[cat_slug]['color'],
        error=request.args.get('error'), success=request.args.get('success')
    )

@app.route('/section/<cat_slug>/<username>/discharge', methods=['POST'])
def section_discharge(cat_slug, username):
    item = request.form['item']
    qty = int(request.form['qty'])
    receiver = request.form['receiver']
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT quantity FROM inventory WHERE item_name=? AND category=?", (item, cat_slug))
    current_qty = cursor.fetchone()[0]
    if current_qty >= qty:
        cursor.execute("UPDATE inventory SET quantity=? WHERE item_name=? AND category=?", (current_qty - qty, item, cat_slug))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO discharges (item_name, quantity, receiver, user_charged, date_time, category) VALUES (?, ?, ?, ?, ?, ?)",
                       (item, qty, receiver, username, now, cat_slug))
        conn.commit()
        conn.close()
        return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success=f"تم الخصم وصرف الوصل بنجاح"))
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, error="الكمية المتوفرة غير كافية"))

@app.route('/section/<cat_slug>/<username>/restock', methods=['POST'])
def section_restock(cat_slug, username):
    if username != 'admin': return "غير مسموح"
    item_name = request.form['item_name']
    qty = int(request.form['qty'])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET quantity = quantity + ? WHERE item_name=? AND category=?", (qty, item_name, cat_slug))
    conn.commit()
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success="تم تموين المادة بنجاح"))

@app.route('/section/<cat_slug>/<username>/add_new', methods=['POST'])
def section_add_new(cat_slug, username):
    if username != 'admin': return "غير مسموح"
    new_item_name = request.form['new_item_name'].strip()
    qty = int(request.form['qty'])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO inventory (item_name, quantity, category) VALUES (?, ?, ?)", (new_item_name, qty, cat_slug))
        conn.commit()
        success = "تم إدراج المادة الجديدة بنجاح"
        error = None
    except sqlite3.IntegrityError:
        error = "المادة مسجلة مسبقاً!"
        success = None
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success=success, error=error))

@app.route('/section/<cat_slug>/<username>/rename')
def section_rename(cat_slug, username):
    if username != 'admin': return "غير مسموح"
    old_name = request.args.get('old')
    new_name = request.args.get('new')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE inventory SET item_name=? WHERE item_name=? AND category=?", (new_name, old_name, cat_slug))
        conn.commit()
        success = "تم تعديل الاسم"
        error = None
    except sqlite3.IntegrityError:
        error = "الاسم مستخدم بالفعل"
        success = None
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success=success, error=error))

@app.route('/section/<cat_slug>/<username>/update_qty')
def section_update_qty(cat_slug, username):
    if username != 'admin': return "غير مسموح"
    item_name = request.args.get('item')
    new_qty = int(request.args.get('qty'))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET quantity=? WHERE item_name=? AND category=?", (new_qty, item_name, cat_slug))
    conn.commit()
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success="تم تحديث المخزون الحقيقي"))

@app.route('/section/<cat_slug>/<username>/delete')
def section_delete(cat_slug, username):
    if username != 'admin': return "غير مسموح"
    item_name = request.args.get('item')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE item_name=? AND category=?", (item_name, cat_slug))
    conn.commit()
    conn.close()
    return redirect(url_for('section_view', cat_slug=cat_slug, username=username, success="تم الحذف نهائياً"))

@app.route('/logs/<username>')
def logs(username):
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    discharges_data = get_filtered_logs(period, start_date, end_date)
    return render_template_string(LOGS_HTML, username=username, discharges=discharges_data, period=period, start_date=start_date, end_date=end_date)

@app.route('/print_inventory/<cat_slug>')
def print_inventory(cat_slug):
    if cat_slug not in CATEGORIES: return "القسم غير موجود"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, quantity FROM inventory WHERE category=?", (cat_slug,))
    inventory_data = cursor.fetchall()
    conn.close()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    return render_template_string(PRINT_INVENTORY_HTML, inventory=inventory_data, cat_name=CATEGORIES[cat_slug]['ar'], current_time=current_time)

@app.route('/print_report')
def print_report():
    period = request.args.get('period', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    discharges_data = get_filtered_logs(period, start_date, end_date)
    return render_template_string(PRINT_REPORT_HTML, discharges=discharges_data)

@app.route('/print/<int:log_id>')
def print_ticket(log_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, item_name, quantity, receiver, user_charged, date_time FROM discharges WHERE id=?", (log_id,))
    log = cursor.fetchone()
    conn.close()
    if log: return render_template_string(PRINT_HTML, log=log)
    return "الوصل غير موجود"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)