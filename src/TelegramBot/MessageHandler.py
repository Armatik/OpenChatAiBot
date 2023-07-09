# Получение сообщений в чате, и запись их в базу данных
from aiogram import types

from src.TelegramBot.main import dp


@dp.message_handler()
async def send(message: types.Message):
    # Получение сообщений в чате, и запись их в базу данных
    # Проверка на то, что сообщение не пустое и не отправлено в чате содержащим ChatType = 1 в базе данных chatlist
    if (message.chat.type == "group" or message.chat.type == "supergroup") and \
            message.text != '' and message.text != ' ': return None
    else:
        # Проверка статуса ChatType в базе данных chatlist
