# Файл с инициализацией всех процессов телеграмм бота и запуском API OpenAI

# Импорт библиотек
import os
import openai
import configparser
import sqlite3

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from MessageHandler import *


# Импорт переменных из файла .ini
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'config.ini'))

TOKEN = config['Telegram']['token']
OPENAI_API_KEY = config['OpenAI']['api_key']

# Инициализация бота

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Инициализация API OpenAI

openai.api_key = OPENAI_API_KEY

# Инициализация базы данных OCAB_DB в папке DataBase/OCAB_DB.db
database = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'DataBase/OCAB_DB.db'))
cursor = database.cursor()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)