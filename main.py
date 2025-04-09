import os
import json
import logging
import time
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.error import NetworkError, TelegramError

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL")

# Системная инструкция для Claude
SYSTEM_INSTRUCTION = "Ты должен ответить на следующий запрос максимально подробно и понятно."

# Глобальный кэш для хранения контекста диалога для каждого пользователя
# Для каждого chat_id будем хранить список последних сообщений (до 5 сообщений: сообщения пользователя и ответы ассистента)
user_context = {}

def start(update: Update, context: CallbackContext):
    """Обработчик команды /start."""
    update.message.reply_text("Привет! Отправь сообщение, и я передам его в API Claude. Используй /reset для сброса контекста.")

def reset_context(update: Update, context: CallbackContext):
    """Сброс контекста диалога для данного пользователя."""
    chat_id = update.message.chat_id
    if chat_id in user_context:
        del user_context[chat_id]
    update.message.reply_text("Контекст диалога сброшен.")

def send_claude_request(payload, headers, max_retries=3, base_timeout=30):
    """Отправляет запрос к API Claude с механизмом повторных попыток."""
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Увеличиваем timeout и добавляем экспоненциальную задержку при повторных попытках
            current_timeout = base_timeout * (2 ** retry_count)
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload, 
                headers=headers, 
                timeout=current_timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            retry_count += 1
            logger.warning(f"Попытка {retry_count}/{max_retries} не удалась: {e}")
            if retry_count < max_retries:
                # Экспоненциальная задержка перед следующей попыткой
                sleep_time = 2 ** retry_count
                logger.info(f"Ожидание {sleep_time} секунд перед следующей попыткой...")
                time.sleep(sleep_time)
            else:
                # Исчерпаны все попытки
                logger.error(f"Все попытки исчерпаны. Последняя ошибка: {e}")
                raise

def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает входящие сообщения, сохраняет контекст и отправляет запрос к API Claude."""
    user_text = update.message.text
    if not user_text:
        return

    chat_id = update.message.chat_id

    # Инициализируем контекст для пользователя, если его нет
    if chat_id not in user_context:
        user_context[chat_id] = []

    # Добавляем новое сообщение пользователя в контекст
    user_context[chat_id].append({"role": "user", "content": user_text})
    # Ограничиваем контекст: оставляем только последние 5 сообщений
    if len(user_context[chat_id]) > 5:
        user_context[chat_id] = user_context[chat_id][-5:]

    # Формируем payload для API Claude
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "system": SYSTEM_INSTRUCTION,
        "messages": user_context[chat_id]
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    try:
        # Отправляем запрос с механизмом повторных попыток
        data = send_claude_request(payload, headers)

        # Извлекаем текст ответа (в рабочем варианте API возвращает ответ в поле content)
        if "content" in data and isinstance(data["content"], list) and len(data["content"]) > 0:
            reply_text = data["content"][0].get("text", "")
        elif "completion" in data:
            reply_text = data["completion"]
        else:
            reply_text = json.dumps(data)

        # Добавляем ответ ассистента в контекст
        user_context[chat_id].append({"role": "assistant", "content": reply_text})
        if len(user_context[chat_id]) > 10:
            user_context[chat_id] = user_context[chat_id][-10:]

        # Разбиваем длинные сообщения на части, если они превышают лимит Telegram
        if len(reply_text) > 4096:
            chunks = [reply_text[i:i+4096] for i in range(0, len(reply_text), 4096)]
            for chunk in chunks:
                update.message.reply_text(chunk)
        else:
            update.message.reply_text(reply_text)

    except requests.exceptions.RequestException as e:
        logger.error("Ошибка при запросе к API Claude: %s", e)
        update.message.reply_text("Произошла ошибка при обращении к API Claude. Попробуйте позже.")

def error_handler(update: Update, context: CallbackContext):
    """Обработчик ошибок для диспетчера Telegram."""
    try:
        raise context.error
    except NetworkError as e:
        # Обработка сетевых ошибок
        logger.warning(f"Сетевая ошибка: {e}")
        # Если обновление доступно, отправляем сообщение пользователю
        if update and update.effective_message:
            update.effective_message.reply_text(
                "Произошла сетевая ошибка при обращении к Telegram API. Попробуйте позже."
            )
    except TelegramError as e:
        # Обработка других ошибок Telegram
        logger.warning(f"Ошибка Telegram: {e}")
        if update and update.effective_message:
            update.effective_message.reply_text(
                "Произошла ошибка при обработке запроса. Попробуйте позже."
            )
    except Exception as e:
        # Обработка всех остальных ошибок
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)
        if update and update.effective_message:
            update.effective_message.reply_text(
                "Произошла неизвестная ошибка. Пожалуйста, попробуйте позже."
            )

def main():
    """Запуск бота."""
    if not BOT_TOKEN or not CLAUDE_API_KEY:
        logger.error("Не заданы BOT_TOKEN или CLAUDE_API_KEY в переменных окружения.")
        return

    # Настройка повторных попыток для Updater
    updater = Updater(
        BOT_TOKEN, 
        use_context=True,
        request_kwargs={
            'read_timeout': 30,
            'connect_timeout': 30
        }
    )
    dp = updater.dispatcher

    # Регистрация обработчиков
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("reset", reset_context))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Регистрация обработчика ошибок
    dp.add_error_handler(error_handler)

    # Запуск бота с повторными попытками при ошибках
    updater.start_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=["message"]
    )
    logger.info("Бот запущен и ожидает сообщений.")
    updater.idle()

if __name__ == '__main__':
    main()
