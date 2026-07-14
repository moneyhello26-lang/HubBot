from flask import Flask, request, render_template, redirect, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import requests
from dotenv import load_dotenv

load_dotenv()



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
    
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'Обычный'")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN accept_deadline DATETIME")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN completion_deadline DATETIME")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    
taskmanager_db()

@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, status, assignee, result_file, created_at, priority, accept_deadline FROM tasks WHERE status = 'Не выполнено' ORDER BY created_at DESC")
    all_free_tasks = cursor.fetchall()
    conn.close()
    
    # Отфильтровываем просроченные
    recommended_tasks = []
    from datetime import datetime
    now = datetime.now()
    for task in all_free_tasks:
        accept_dl = task[8] if len(task) > 8 else None
        if accept_dl:
            try:
                dt = datetime.strptime(accept_dl, '%Y-%m-%d %H:%M')
                if now > dt:
                    continue
            except ValueError:
                pass
        recommended_tasks.append(task)
        
    import random
    if recommended_tasks:
        if len(recommended_tasks) >= 3:
            recommended_tasks = random.sample(recommended_tasks, 3)
    
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
    cursor.execute('SELECT id, title, description, status, assignee, result_file, created_at, priority, accept_deadline, completion_deadline FROM tasks ORDER BY created_at DESC')
    all_tasks = cursor.fetchall()
    conn.close()
    
    valid_tasks = []
    from datetime import datetime
    now = datetime.now()
    for task in all_tasks:
        status = task[3]
        accept_dl = task[8] if len(task) > 8 else None
        comp_dl = task[9] if len(task) > 9 else None
        
        is_expired = False
        if status == 'Не выполнено' and accept_dl:
            try:
                dt = datetime.strptime(accept_dl, '%Y-%m-%d %H:%M')
                if now > dt:
                    is_expired = True
            except ValueError:
                pass
        elif status == 'В процессе' and comp_dl:
            try:
                dt = datetime.strptime(comp_dl, '%Y-%m-%d %H:%M')
                if now > dt:
                    is_expired = True
            except ValueError:
                pass
                
        if not is_expired:
            valid_tasks.append(task)
            
    return render_template('tasks.html', tasks=valid_tasks)

@app.route('/take_task/<int:task_id>', methods=['POST'])
def take_task(task_id):
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']


    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT title, accept_deadline FROM tasks WHERE id=?', (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return redirect('/tasks')

    if task[1]:
        from datetime import datetime
        try:
            dt = datetime.strptime(task[1], '%Y-%m-%d %H:%M')
            if datetime.now() > dt:
                conn.close()
                return "Ошибка: Срок принятия этой задачи уже истек.", 400
        except ValueError:
            pass
            


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
    cursor.execute('SELECT title, completion_deadline FROM tasks WHERE id=?', (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return redirect('/tasks')

    if task[1]:
        from datetime import datetime
        try:
            dt = datetime.strptime(task[1], '%Y-%m-%d %H:%M')
            if datetime.now() > dt:
                conn.close()
                return "Ошибка: Срок выполнения этой задачи уже истек.", 400
        except ValueError:
            pass


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

    cursor.execute('SELECT id, title, status, completion_deadline FROM tasks WHERE assignee = ? ORDER BY created_at DESC', (username,))
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