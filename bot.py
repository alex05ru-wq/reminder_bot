import os
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import telebot
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
# Часовой пояс берём из .env, по умолчанию Москва.
# Так бот работает одинаково и на вашем ПК, и на сервере в UTC.
TZ = ZoneInfo(os.getenv('TIMEZONE', 'Europe/Moscow'))
DATE_FORMAT = '%Y-%m-%d %H:%M'

bot = telebot.TeleBot(TOKEN)

# --- База данных ---
# Одно соединение на оба потока + замок (lock),
# чтобы потоки не лезли в базу одновременно.
conn = sqlite3.connect('reminders.db', check_same_thread=False)
db_lock = threading.Lock()

with db_lock:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            remind_at TEXT
        )
    ''')
    conn.commit()


def now_local():
    """Текущее время в часовом поясе бота (без привязки к времени сервера)."""
    return datetime.now(TZ).replace(tzinfo=None)


def get_user_reminders(user_id):
    """Напоминания пользователя по порядку времени: [(id, text, remind_at), ...]."""
    with db_lock:
        return conn.execute(
            'SELECT id, text, remind_at FROM reminders '
            'WHERE user_id = ? ORDER BY remind_at, id',
            (user_id,)
        ).fetchall()


def pretty(remind_at):
    """'2026-10-15 18:30' -> '15.10.2026 в 18:30'"""
    return datetime.strptime(remind_at, DATE_FORMAT).strftime('%d.%m.%Y в %H:%M')


@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.send_message(
        message.chat.id,
        'Привет! Я бот-напоминалка.\n\n'
        'Добавить: /remind ГГГГ-ММ-ДД ЧЧ:ММ текст\n'
        'Пример: /remind 2026-10-15 18:30 позвонить маме\n\n'
        'Список: /list\n'
        'Удалить: /delete номер (номер из /list)'
    )


@bot.message_handler(commands=['remind'])
def add_reminder(message):
    # /remind 2026-10-15 18:30 позвонить маме -> 4 части
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.send_message(
            message.chat.id,
            'Неверный формат. Пример:\n/remind 2026-10-15 18:30 позвонить маме'
        )
        return

    date_str = parts[1] + ' ' + parts[2]
    text = parts[3]

    try:
        remind_at = datetime.strptime(date_str, DATE_FORMAT)
    except ValueError:
        bot.send_message(
            message.chat.id,
            'Не могу разобрать дату. Формат: ГГГГ-ММ-ДД ЧЧ:ММ\n'
            'Пример: 2026-10-15 18:30'
        )
        return

    # Нельзя поставить напоминание в прошлое
    if remind_at <= now_local():
        bot.send_message(message.chat.id, 'Это время уже прошло. Укажи дату в будущем.')
        return

    with db_lock:
        conn.execute(
            'INSERT INTO reminders (user_id, text, remind_at) VALUES (?, ?, ?)',
            (message.chat.id, text, remind_at.strftime(DATE_FORMAT))
        )
        conn.commit()

    bot.send_message(message.chat.id, f'Ок! Напомню {pretty(remind_at.strftime(DATE_FORMAT))}:\n{text}')


@bot.message_handler(commands=['list'])
def list_reminders(message):
    rows = get_user_reminders(message.chat.id)
    if not rows:
        bot.send_message(message.chat.id, 'У тебя нет активных напоминаний.')
        return

    lines = [f'{i}. {pretty(remind_at)} — {text}'
             for i, (_id, text, remind_at) in enumerate(rows, start=1)]
    bot.send_message(
        message.chat.id,
        'Твои напоминания:\n\n' + '\n'.join(lines) + '\n\nУдалить: /delete номер'
    )


@bot.message_handler(commands=['delete'])
def delete_reminder(message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, 'Укажи номер из /list. Пример: /delete 2')
        return

    number = int(parts[1])
    rows = get_user_reminders(message.chat.id)
    if not 1 <= number <= len(rows):
        bot.send_message(message.chat.id, 'Нет напоминания с таким номером. Посмотри /list')
        return

    rid, text, remind_at = rows[number - 1]
    with db_lock:
        conn.execute('DELETE FROM reminders WHERE id = ?', (rid,))
        conn.commit()
    bot.send_message(message.chat.id, f'Удалил: {pretty(remind_at)} — {text}')


def check_reminders():
    """Фоновый поток: раз в 30 секунд отправляет напоминания, время которых наступило."""
    while True:
        try:
            now = now_local().strftime(DATE_FORMAT)
            # <= а не = : если бот был выключен в нужную минуту,
            # напоминание всё равно придёт сразу после запуска
            with db_lock:
                rows = conn.execute(
                    'SELECT id, user_id, text FROM reminders WHERE remind_at <= ?',
                    (now,)
                ).fetchall()

            for rid, uid, text in rows:
                try:
                    bot.send_message(uid, f'⏰ Напоминание: {text}')
                except Exception as e:
                    print('Ошибка отправки:', e)
                with db_lock:
                    conn.execute('DELETE FROM reminders WHERE id = ?', (rid,))
                    conn.commit()
        except Exception as e:
            # Любая ошибка не должна убить фоновый поток
            print('Ошибка планировщика:', e)

        time.sleep(30)


threading.Thread(target=check_reminders, daemon=True).start()

print('Бот-напоминалка запущен...')
# infinity_polling сам переподключается при обрывах связи
bot.infinity_polling()
