# Telegram‑бот на Python для API Claude

Этот проект содержит Telegram‑бота, написанного на Python с использованием библиотеки [python-telegram-bot](https://python-telegram-bot.org/), который перенаправляет входящие сообщения в API Claude от Anthropic и возвращает полученный ответ пользователю.

## Функционал

- При получении текстового сообщения бот отправляет запрос в API Claude, используя фиксированную системную инструкцию.
- Ответ от API Claude отправляется обратно пользователю.
- Реализована базовая обработка ошибок (нет ответа от API, проблемы с сетью и т.д.).
- В текущей версии бот отвечает только текстом. В будущих версиях планируется интеграция с БД (Postgres) и взаимодействие с веб‑приложением.

## Переменные окружения

Бот использует следующие переменные окружения:
- `BOT_TOKEN` – токен вашего Telegram‑бота (получите у [BotFather](https://t.me/BotFather)).
- `CLAUDE_API_KEY` – API‑ключ для доступа к API Claude от Anthropic.
- `CLAUDE_MODEL` – модель Claude (по умолчанию `claude-2`).

Создайте файл `.env` в корне проекта и заполните его, например:

```dotenv
BOT_TOKEN=ваш_токен
CLAUDE_API_KEY=ваш_ключ_api_claude
CLAUDE_MODEL=claude-23