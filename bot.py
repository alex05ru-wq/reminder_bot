import os
import sqlite3
import telebot
from dotenv import load_dotenv
import threading
import time

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# --- Подключение к базе данных ---
conn = sqlite3.connect('reminders.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицу, если её ещё нет
cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        remind_at TEXT
    )
''')
conn.commit()


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        'Привет! Я бот-напоминалка.\n\n'
        'Формат: /remind ГГГГ-ММ-ДД ЧЧ:ММ текст\n'
        'Пример: /remind 2026-10-15 18:30 позвонить маме'
    )
from datetime import datetime


@bot.message_handler(commands=['remind'])
def add_reminder(message):
    # Разбиваем сообщение на части: /remind, дата, время, текст
    parts = message.text.split(maxsplit=3)

    # Проверяем, что пользователь ввёл всё нужное
    if len(parts) < 4:
        bot.send_message(
            message.chat.id,
            'Неверный формат. Пример:\n/remind 2026-10-15 18:30 позвонить маме'
        )
        return

    # parts = ['/remind', '2026-10-15', '18:30', 'позвонить маме']
    date_str = parts[1] + ' ' + parts[2]   # '2026-10-15 18:30'
    text = parts[3]                        # 'позвонить маме'

    # Пробуем превратить строку в дату
    try:
        remind_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
    except ValueError:
        bot.send_message(
            message.chat.id,
            'Не могу разобрать дату. Формат: ГГГГ-ММ-ДД ЧЧ:ММ\n'
            'Пример: 2026-10-15 18:30'
        )
        return

    # Сохраняем в базу
    cursor.execute(
        'INSERT INTO reminders (user_id, text, remind_at) VALUES (?, ?, ?)',
        (message.chat.id, text, remind_at.strftime('%Y-%m-%d %H:%M'))
    )
    conn.commit()

    # Отвечаем пользователю
    bot.send_message(
        message.chat.id,
        f'Ок! Напомню {remind_at.strftime("%d.%m.%Y в %H:%M")}:\n{text}'
    )

def check_reminders():
    while True:
        # Текущее время в том же формате, что и в базе
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Ищем напоминания, которые пора отправить
        cursor.execute(
            'SELECT id, user_id, text FROM reminders WHERE remind_at = ?',
            (now,)
        )
        rows = cursor.fetchall()

        for rid, uid, text in rows:
            try:
                bot.send_message(uid, f'⏰ Напоминание: {text}')
            except Exception as e:
                print('Ошибка отправки:', e)

            # Удаляем напоминание, чтобы не отправить повторно
            cursor.execute('DELETE FROM reminders WHERE id = ?', (rid,))

        conn.commit()
        time.sleep(30)  # проверять каждые 30 секунд


# Запускаем планировщик в фоновом потоке
threading.Thread(target=check_reminders, daemon=True).start()

@bot.message_handler(commands=['list'])
def list_reminders(message):
    # Берём все напоминания пользователя, отсортированные по времени
    cursor.execute(
        'SELECT text, remind_at FROM reminders WHERE user_id = ? ORDER BY remind_at',
        (message.chat.id,)
    )
    rows = cursor.fetchall()

    # Если напоминаний нет
    if not rows:
        bot.send_message(message.chat.id, 'У тебя нет активных напоминаний.')
        return

    # Собираем красивое сообщение
    lines = []
    for i, (text, remind_at) in enumerate(rows, start=1):
        # Превращаем '2026-10-15 18:30' в '15.10.2026 в 18:30'
        dt = datetime.strptime(remind_at, '%Y-%m-%d %H:%M')
        pretty = dt.strftime('%d.%m.%Y в %H:%M')
        lines.append(f'{i}. {pretty} — {text}')

    bot.send_message(
        message.chat.id,
        'Твои напоминания:\n\n' + '\n'.join(lines)
    )

print('Бот-напоминалка запущен...')
bot.polling(none_stop=True)