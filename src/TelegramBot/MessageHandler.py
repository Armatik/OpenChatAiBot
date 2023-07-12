# Получение сообщений в чате, и запись их в базу данных
from aiogram import types

from src.TelegramBot.main import dp

from main import cursor, config

#импортировать функцию для обработки сообщений из OpenAI
