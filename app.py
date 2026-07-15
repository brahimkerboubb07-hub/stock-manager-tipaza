import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'tipaza_secret_key_2026_v3'

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tipaza_inventory.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'موظف'
        )
    ''')
    cur.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'مدير')")
    conn.commit()
    conn.close()
    print("✅ Database initialized with SQLite")

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if user:
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash("بيانات الدخول غير صحيحة", "danger")
    return render_template_string('''
    <form method="POST">
        <input type="text" name="username" placeholder="اسم المستخدم">
        <input type="password" name="password" placeholder="كلمة المرور">
        <button type="submit">دخول</button>
    </form>
    <p>admin / 1234</p>
    ''')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return f"مرحباً {session['username']}! 🎉"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
