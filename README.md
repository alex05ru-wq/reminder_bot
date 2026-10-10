# Telegram-бот «Эхо»

Мой первый Telegram-бот на Python. Отвечает на команду `/start` и повторяет любое текстовое сообщение пользователя.

## Возможности

- Команда `/start` — приветствие с именем пользователя
- Эхо-ответ на любое текстовое сообщение
- Токен бота хранится в `.env` (не попадает в репозиторий)

## Технологии

- Python 3
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) — библиотека для работы с Telegram Bot API
- python-dotenv — загрузка токена из `.env`

## Установка и запуск

1. Клонируй репозиторий:
   ```bash
   git clone https://github.com/alex05ru-wq/my_first_bot.git
   cd my_first_bot