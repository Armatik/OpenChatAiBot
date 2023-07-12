# Импорт библиотек
import os
from contextlib import suppress

import openai
import configparser
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToDeleteNotFound

mother_path = os.path.dirname(os.path.dirname(os.getcwd()))


# Импорт переменных из файла .ini
config = configparser.ConfigParser()
config.read(os.path.join(mother_path, 'src/config.ini'))
TOKEN = config['Telegram']['token']
OPENAI_API_KEY = (config['Openai']['api_key'])
bot_trigger_front = (config['Telegram']['bot_trigger_front']).split('|')
bot_trigger_all = (config['Telegram']['bot_trigger_all']).split('|')
# удаление лишних элементов массивов
bot_trigger_front.remove('')
bot_trigger_all.remove('')

# Инициализация бота

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Инициализация API OpenAI

openai.api_key = OPENAI_API_KEY

# Инициализация базы данных OCAB_DB в папке DataBase/OCAB_DB.db
# Создаём базу данных sqlite3 по пути /home/armatik/PycharmProjects/OpenChatAiBot/DataBase/OCAB_DB.db
database = sqlite3.connect(os.path.join(mother_path, 'DataBase/OCAB_DB.db'))
cursor = database.cursor()
# Создаём таблицу chat_list
cursor.execute("""CREATE TABLE IF NOT EXISTS chat_list (
    chat_id INTEGER PRIMARY KEY,
    chat_role INTEGER NOT NULL,
    chat_stats INTEGER NOT NULL
)""")
# Создаём таблицу message_list
cursor.execute("""CREATE TABLE IF NOT EXISTS message_list (
    message_id INTEGER PRIMARY KEY,
    message_text TEXT NOT NULL,
    message_sender INTEGER NOT NULL,
    answer_id INTEGER
)""")
# Создаём таблицу user_list
cursor.execute("""CREATE TABLE IF NOT EXISTS user_list (
    user_id INTEGER PRIMARY KEY,
    user_role INTEGER,
    user_stats INTEGER
)""")

#запись информации о чате в базу данных
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    chat_id = message.chat.id
    chat_role = 0
    chat_stats = 1
    cursor.execute("INSERT INTO chat_list VALUES (?, ?, ?)", (chat_id, chat_role, chat_stats))
    database.commit()
    await message.reply("Привет, я бот, который учится на основе модели GPT-3.5. "
                        "Я могу поговорить с тобой на любую тему, но пока что я не очень умный, поэтому не обижайся, "
                        "если я не пойму тебя. Чтобы начать общение со мной, напиши мне сообщение, начинающееся с "
                        "слова Арма, например: Арма, как дела?")

from src.OpenAI.GPT35turbo.OA_processing import openai_message_processing


async def delete_message(message: types.Message, sleep_time: int = 0):
    await asyncio.sleep(sleep_time)
    with suppress(MessageCantBeDeleted, MessageToDeleteNotFound):
        await message.delete()

@dp.message_handler()
async def in_message(message: types.Message):
    chat_id = message.chat.id
    # Получение сообщений в чате, и запись их в базу данных
    # Проверка на то, что сообщение не пустое и не отправлено в чате содержащим ChatType = 1 в базе данных chatlist
    if (message.chat.type != "group" or message.chat.type != "supergroup") and \
            message.text != '' and message.text != ' ' and \
            (cursor.execute("SELECT chat_role FROM chat_list WHERE chat_id;") == 1): return None
    else:
        # Запись сообщения в базу данных
        cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                       (message.message_id, message.text, message.from_user.id,  None))
        if message.reply_to_message is not None:
            # Запись ответа на сообщение в базу данных
            cursor.execute("UPDATE message_list SET answer_id = ? WHERE message_id = ?",
                           (message.reply_to_message.message_id, message.message_id))
        database.commit()
        # Обработка сообщения OpenAI
        send_answer = False
        # импортируем массив триггеров из файла .ini
        if message.reply_to_message and message.reply_to_message.from_user.id == (await bot.me).id:
            send_answer = True
        for trigger in bot_trigger_all:
            if trigger.lower() in message.text.lower():
                send_answer = True
        for trigger in bot_trigger_front:
            if message.text.lower().startswith(trigger.lower()):
                send_answer = True

        if send_answer:
            your_id = message.from_id
            your_name = message.from_user.username
            temp_msg = await message.reply(
                f"[{your_name}](tg://user?id={str(your_id)}), Подожди немного и я обязательно отвечу тебе!",
                parse_mode="Markdown")
            response = openai_message_processing(message.message_id)
            if response is None:
                bot_message_id = await message.reply("Я не понял тебя, попробуй перефразировать")
                asyncio.create_task(delete_message(temp_msg, 0))
                #заносим сообщение в базу данных в качестве message_id пишем id сообщения которое отправил бот
                cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                                    (bot_message_id, "Я не понял тебя, попробуй перефразировать", 0, message.message_id))
            else:
                bot_message_id = await message.reply(response['choices'][0]['message']['content'], parse_mode="markdown")
                asyncio.create_task(delete_message(temp_msg, 0))
                #заносим сообщение в базу данных в качестве message_id мы пишем id сообщения в bot_message_id
                cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                                    (bot_message_id.message_id, response['choices'][0]['message']['content'], 0, message.message_id))
            database.commit()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)