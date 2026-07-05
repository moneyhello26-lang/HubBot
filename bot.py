import telebot
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден! Проверьте файл .env")

bot = telebot.TeleBot(BOT_TOKEN)

DB_PATH = 'data/taskmanager.db'

user_data = {}

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
    description = message.text
    title = user_data[chat_id]['title']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description) 
        VALUES (?, ?)
    ''', (title, description))
    conn.commit()
    conn.close()

    bot.reply_to(message, f"Задача успешно добавлена!\n\n {title}:\n {description}", parse_mode='Markdown')
    user_data.pop(chat_id, None)

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

if __name__ == '__main__':
    print("Бот запущен")
    bot.polling(none_stop=True)
