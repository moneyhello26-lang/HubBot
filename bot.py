import telebot
import sqlite3
import os
import time
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден! Проверьте файл .env")

bot = telebot.TeleBot(BOT_TOKEN)

DB_PATH = 'data/taskmanager.db'

user_data = {}

def get_manager_chat_id():
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        import requests
        resp = requests.get(url).json()
        if resp.get("ok") and resp.get("result"):
            return str(resp["result"][-1]["message"]["chat"]["id"])
    except:
        pass
    return None

def task_cleaner_thread():
    """Background thread to delete expired tasks every minute."""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, title, status, accept_deadline, completion_deadline FROM tasks')
            tasks = cursor.fetchall()
            
            now = datetime.now()
            expired_ids = []
            
            for task in tasks:
                t_id, title, status, accept_dl, comp_dl = task
                if status == 'Не выполнено' and accept_dl:
                    try:
                        dt = datetime.strptime(accept_dl, '%Y-%m-%d %H:%M')
                        if now > dt:
                            expired_ids.append((t_id, title, "принятие"))
                    except ValueError:
                        pass
                elif status == 'В процессе' and comp_dl:
                    try:
                        dt = datetime.strptime(comp_dl, '%Y-%m-%d %H:%M')
                        if now > dt:
                            expired_ids.append((t_id, title, "выполнение"))
                    except ValueError:
                        pass
                        
            for t_id, title, dl_type in expired_ids:
                cursor.execute("UPDATE tasks SET status = 'Просрочено' WHERE id = ?", (t_id,))
                print(f"Task #{t_id} marked as expired (expired {dl_type} deadline)")
                
                chat_id = get_manager_chat_id()
                if chat_id:
                    try:
                        bot.send_message(chat_id, f"⚠️ Задача #{t_id} «{title}» перешла в статус 'Просрочено' (дедлайн на {dl_type}).")
                    except Exception as e:
                        print(f"Failed to send notification: {e}")
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Cleaner thread error: {e}")
            
        time.sleep(60)

cleaner = threading.Thread(target=task_cleaner_thread, daemon=True)
cleaner.start()




@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Я бот для управления задачами. Используй команду /help, чтобы узнать, что я умею.")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "Меню команд:\n\n"
        "/add — Создать новую задачу\n"
        "/list — Полный список всех задач\n"
        "/status — Посмотреть общую статистику (статусы)\n"
        "/delete — Удалить задачу\n"
        "/help — Показать это меню"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['add'])
def add_task(message):
    msg = bot.reply_to(message, "Введите название задачи:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_title_step)

def process_title_step(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'title': message.text}

    msg = bot.reply_to(message, "Введите описание задачи:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_description_step)

def process_description_step(message):
    chat_id = message.chat.id
    user_data[chat_id]['description'] = message.text

    msg = bot.reply_to(message, "Введите дедлайн на ПРИНЯТИЕ задачи (например: 2026-07-10 15:00):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_accept_deadline_step)

def process_accept_deadline_step(message):
    chat_id = message.chat.id
    accept_dl = message.text.strip()
    
    try:
        datetime.strptime(accept_dl, '%Y-%m-%d %H:%M')
        user_data[chat_id]['accept_deadline'] = accept_dl
        
        msg = bot.reply_to(message, "Введите дедлайн на ВЫПОЛНЕНИЕ задачи (например: 2026-07-15 18:00):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_completion_deadline_step)
    except ValueError:
        msg = bot.reply_to(message, "Неверный формат даты. Пожалуйста, введите в формате ГГГГ-ММ-ДД ЧЧ:ММ (например: 2026-07-10 15:00):")
        bot.register_next_step_handler(msg, process_accept_deadline_step)

def process_completion_deadline_step(message):
    chat_id = message.chat.id
    comp_dl = message.text.strip()
    
    try:
        datetime.strptime(comp_dl, '%Y-%m-%d %H:%M')
        
        title = user_data[chat_id]['title']
        description = user_data[chat_id]['description']
        accept_dl = user_data[chat_id]['accept_deadline']
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (title, description, accept_deadline, completion_deadline) 
            VALUES (?, ?, ?, ?)
        ''', (title, description, accept_dl, comp_dl))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ Задача успешно добавлена!\n\n*{title}*\n{description}\n\n⏳ Принять до: {accept_dl}\n⏳ Выполнить до: {comp_dl}", parse_mode='Markdown')
        user_data.pop(chat_id, None)
    except ValueError:
        msg = bot.reply_to(message, "Неверный формат даты. Пожалуйста, введите в формате ГГГГ-ММ-ДД ЧЧ:ММ (например: 2026-07-15 18:00):")
        bot.register_next_step_handler(msg, process_completion_deadline_step)

@bot.message_handler(commands=['list'])
def list_tasks(message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, status, assignee FROM tasks ORDER BY id DESC')
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        bot.reply_to(message, "Список задач пуст.")
        return

    response = "Список задач:\n\n"
    for task_id, title, status, assignee in tasks:
        worker = f"{assignee}" if assignee else "Не назначен"
        response += f"#{task_id} - {title}-[{status}]-{worker}\n"

    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def task_status(message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT title, status FROM tasks')
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        bot.reply_to(message, "Пока нет ни одной задачи.")
        return
        
    response = "Текущие статусы:\n\n"
    for title, status in tasks:
        response += f"{title} - [{status}]\n"
        
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['delete'])
def delete_task(message):
    msg = bot.reply_to(message, "Введите ID задачи, которую хотите удалить:")
    bot.register_next_step_handler(msg, process_delete_step)

def process_delete_step(message):
    task_id = message.text.strip()
    if not task_id.isdigit():
        bot.reply_to(message, "ID задачи должен быть числом. Попробуйте снова.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (int(task_id),))
    conn.commit()
    conn.close()

    bot.reply_to(message, f"Задача с ID {task_id} успешно удалена.", parse_mode='Markdown')

if __name__ == '__main__':
    print("Бот запущен, процесс очистки активен...")
    bot.polling(none_stop=True)
