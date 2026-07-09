from flask import Flask, request, render_template, redirect, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'secret_key'

DB_PATH = 'data/taskmanager.db'

def taskmanager_db():
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Не выполнено',
            assignee TEXT,
            result_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar_file TEXT DEFAULT 'default.png',
            about_me TEXT,
            github_link TEXT,
            linkedin_link TEXT
        )
    ''')

    conn.commit()
    conn.close()
    
taskmanager_db()

@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE status = "Не выполнено" ORDER BY RANDOM() LIMIT 3')
    recommended_tasks = cursor.fetchall()
    conn.close()
    return render_template('home.html', recommended_tasks=recommended_tasks)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Пользователь с таким именем уже существует.")
        finally:
            conn.close()

        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, avatar_file FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            session['avatar_file'] = user[2]
            return redirect('/')
        
    return render_template('login.html', error="Неверное имя пользователя или пароль.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/tasks')
def tasks():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
    tasks = cursor.fetchall()
    conn.close()
    return render_template('tasks.html', tasks=tasks)

@app.route('/take_task/<int:task_id>', methods=['POST'])
def take_task(task_id):
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']


    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks SET status='В процессе', assignee=? WHERE id=?
    ''', (username, task_id))
    conn.commit()
    conn.close()

    return redirect('/tasks')

@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'username' not in session:
        return redirect('/login')

    result_file = request.files.get('result_file')
    filename = None
    if result_file and result_file.filename != '':
        os.makedirs('data/uploads', exist_ok=True)
        from werkzeug.utils import secure_filename
        filename = f"{task_id}-{secure_filename(result_file.filename)}" 
        result_file.save(os.path.join('data/uploads', filename))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if filename:
        cursor.execute('''
            UPDATE tasks SET status='Выполнено', result_file=? WHERE id=?
        ''', (filename, task_id))

    conn.commit()
    conn.close()

    return redirect('/tasks')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        about_me = request.form.get('about_me', '')
        github_link = request.form.get('github_link', '')
        linkedin_link = request.form.get('linkedin_link', '')

        avatar = request.files.get('avatar')
        avatar_filename = None
        
        if avatar and avatar.filename != '':
            os.makedirs('data/avatars', exist_ok=True)
            from werkzeug.utils import secure_filename
            filename = secure_filename(avatar.filename)
            avatar_filename = f"user_{user_id}_{filename}"
            avatar.save(os.path.join('data/avatars', avatar_filename))

        if avatar_filename:
            cursor.execute('''
                UPDATE users SET about_me=?, github_link=?, linkedin_link=?, avatar_file=?
                WHERE id=?
            ''', (about_me, github_link, linkedin_link, avatar_filename, user_id))
            session['avatar_file'] = avatar_filename
        else:
            cursor.execute('''
                UPDATE users SET about_me=?, github_link=?, linkedin_link=?
                WHERE id=?
            ''', (about_me, github_link, linkedin_link, user_id))

        conn.commit()
        conn.close()
        return redirect('/settings')

    cursor.execute('SELECT username, avatar_file, about_me, github_link, linkedin_link FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return render_template('settings.html', user=user_data)

@app.route('/profile/<username>')
def profile(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    profile_user = cursor.fetchone()
    
    if not profile_user:
        conn.close()
        return "Пользователь не найден", 404

    cursor.execute('SELECT id, title, status FROM tasks WHERE assignee = ? ORDER BY created_at DESC', (username,))
    user_tasks = cursor.fetchall()
    conn.close()
        
    return render_template('public_profile.html', profile_user=profile_user, user_tasks=user_tasks)

@app.route('/avatar/<filename>')
def get_avatar(filename):
    return send_from_directory('data/avatars', filename)

@app.route('/uploads/<filename>')
def get_upload(filename):
    return send_from_directory('data/uploads', filename)

app.run(debug=True, host="0.0.0.0", port=5000)