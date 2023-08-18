# Импорт библиотек
import os
from contextlib import suppress

import openai
import configparser
import sqlite3
import asyncio
import sys
import datetime
from time import mktime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToDeleteNotFound

mother_path = os.path.dirname(os.path.dirname(os.getcwd()))
sys.path.insert(1, mother_path)


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
DB_message_limit = int(config['DataBase']['message_limit'])

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
    user_name TEXT NOT NULL,
    user_role INTEGER,
    user_stats INTEGER
)""")
#запись информации о чате в базу данных

async def empty_role(id):
    cursor.execute("UPDATE user_list SET user_role = ? WHERE user_id = ?", (0, id))
    database.commit()


async def check(id):
    #проверка что у человека есть роль
    user_role = cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (id,)).fetchone()[0]
    if user_role not in [0, 1, 2]:
        await empty_role(id)


async def get_role_name(rolenum):
    rolenum = int(rolenum)
    if rolenum == 0:
        role = config['Roles']['user']
    elif rolenum == 1:
        role = config['Roles']['moderator']
    elif rolenum == 2:
        role = config['Roles']['admin']
    return role


async def check_admin(id, chat_id):
    #Проверка что человек есть в списке администраторов чата
    chat_admins = await bot.get_chat_administrators(chat_id)
    flag = False
    for admin in chat_admins:
        if admin.user.id == id:
            flag = True
    return flag


async def check_moderator(id):
    #Проверка что человек имеет роль модератора
    if cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (id,)).fetchone()[0] >= 1:
        return True
    else:
        return False



async def time_to_seconds(time):
    #Конвертация текстового указания времени по типу 3h, 5m, 10s в минуты
    print("t_to_s")
    if time[-1] == 'd':
        return int(time[:-1])*86400
    elif time[-1] == 'h':
        return int(time[:-1])*3600
    elif time[-1] == 'm':
        return int(time[:-1])*60
    elif time[-1] == 's':
        return int(time[:-1])


async def short_time_to_time(time):
    #Конвертация времени в длинное название
    if time[-1] == 'd':
        return f"{time[:-1]} дней"
    elif time[-1] == 'h':
        return f"{time[:-1]} часов"
    elif time[-1] == 'm':
        return f"{time[:-1]} минут"
    elif time[-1] == 's':
        return f"{time[:-1]} секунд"


@dp.message_handler(commands=['mute'])
async def mute(message: types.Message):
    #Проверка что отправитель является администратором чата
    print("start mute")
    if await check_moderator(message.from_user.id):
        print("moderator checked")
        #Проверка отвечает ли сообщение на другое сообщение
        if message.reply_to_message is not None:
            time = message.text.split(' ')[1]
            #получаем id отправителя сообщение на которое отвечает message
            target_id = message.reply_to_message.from_user.id
            target_name = cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
            #Проверка что человек пользователь
            if cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0] == 0:
                #ограничения прав пользователя по отправке сообщений на time секунд
                time_sec = await time_to_seconds(message.text.split(' ')[1])
                if time_sec <= 30 or time_sec >= 31536000:
                    await message.reply("Время мута должно быть больше 30 секунд и меньше 365 дней")
                    return
                await bot.restrict_chat_member(message.chat.id, target_id, until_date=time.time()+time_sec)
                await message.reply(
                    f"Пользователь {target_name} замьючен на {short_time_to_time(time)}")
        else:
            target_tag = message.text.split(' ')[1]
            target_tag = target_tag[1:]
            target_id = int(cursor.execute("SELECT user_id FROM user_list WHERE user_name = ?", (target_tag,)).fetchone()[0])
            target_name = cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
            #ограничения прав пользователя по отправке сообщений на time секунд
            time_mute = message.text.split(' ')[2]

            if cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0] == 0:
                #ограничения прав пользователя по отправке сообщений на time секунд
                time_sec = await time_to_seconds(message.text.split(' ')[2])
                if time_sec <= 30 or time_sec >= 31536000:
                    await message.reply("Время мута должно быть больше 30 секунд и меньше 365 дней")
                    return
                date_string = "2022-01-01 00:00:00"
                date_time = datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
                unix_time = int(mktime(date_time.timetuple()))
                await bot.restrict_chat_member(message.chat.id, target_id, until_date=unix_time+time_sec, permissions=types.ChatPermissions(can_send_messages=False))
                await message.reply(
                    f"Пользователь {target_name} замьючен на {short_time_to_time(time_mute)}.")


@dp.message_handler(commands=['unmute'])
async def unmute(message: types.Message):
    if await check_moderator(message.from_user.id):
        if message.reply_to_message is not None:
            target_id = message.reply_to_message.from_user.id
            target_name = cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
            await bot.restrict_chat_member(message.chat.id, target_id, until_date=0, permissions=types.ChatPermissions(can_send_messages=True))
            await message.reply(
                f"Пользователь [{target_name}](tg://user?id={target_id}) размьючен",
                parse_mode="Markdown")
        else:
            target_tag = message.text.split(' ')[1]
            target_tag = target_tag[1:]
            target_id = int(cursor.execute("SELECT user_id FROM user_list WHERE user_name = ?", (target_tag,)).fetchone()[0])
            target_name = cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
            if cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0] == 0:
                await bot.restrict_chat_member(message.chat.id, target_id, until_date=0, permissions=types.ChatPermissions(can_send_messages=True))
                await message.reply(
                    f"Пользователь [{target_name}](tg://user?id={target_id}) размьючен",
                    parse_mode="Markdown")


@dp.message_handler(commands=['chat_info'])
async def chat_info(message: types.Message):
    #Выводит информацию о чате. Название, количество пользователей, количество администраторов, количество модераторов, количество сообщений.
    if await check_moderator(message.from_user.id):
        chat_id = message.chat.id
        chat_title = message.chat.title
        chat_members = await bot.get_chat_members_count(chat_id)
        chat_admins = await bot.get_chat_administrators(chat_id)
        chat_moderators = cursor.execute("SELECT COUNT(user_id) FROM user_list WHERE user_role = 1").fetchone()[0]
        chat_messages = cursor.execute("SELECT COUNT(message_id) FROM message_list WHERE chat_id = ?", (chat_id,)).fetchone()[0]
        print("ready")
        await message.reply(
            f"Название чата: {chat_title}\n"
            f"Количество пользователей: {chat_members}\n"
            f"Количество администраторов: {len(chat_admins)}\n"
            f"Количество модераторов: {chat_moderators}\n"
            f"Количество сообщений: {chat_messages}")
    else:
        await message.reply(
            f"У вас недостаточно прав для выполнения этой команды.")

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    #проверка что чат есть в базе данных
    if cursor.execute("SELECT chat_id FROM chat_list WHERE chat_id = ?", (message.chat.id,)).fetchone() is None:
        chat_id = message.chat.id
        chat_role = 0
        chat_stats = 1
        cursor.execute("INSERT INTO chat_list VALUES (?, ?, ?)", (chat_id, chat_role, chat_stats))
        database.commit()
        await message.reply(
                f"{config['Telegram']['start_answer']}",
                parse_mode="Markdown")
    else:
        await message.reply(
                f"Чат уже инициализирован.",
                parse_mode="Markdown")
    # Проверка наличия столбца имени пользователя в базе данных, если его нет, то добавить.
    try:
        cursor.execute("SELECT user_name FROM user_list")
    # sqlite3.OperationalError: no such column: user_name
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE user_list ADD COLUMN user_name TEXT")
        database.commit()
        await message.reply("База данных пользователей реструктурирована.")


@dp.message_handler(commands=['top10'])
async def top10(message: types.Message):
    #топ 10 пользователей по количеству сообщений в user_stats в формате: Имя пользователя - количество сообщений
    top10 = cursor.execute("SELECT user_id, user_stats FROM user_list ORDER BY user_stats DESC LIMIT 10").fetchall()
    top10_message = ''
    for user in top10:
        username = (cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (user[0],)).fetchone())[0]
        top10_message += f"{username} - {user[1]}\n"
        #в начале сообщения берём текст из config.ini и вставляем в него топ 10 пользователей
    await message.reply(
            f"{config['Telegram']['top10_answer']}\n{top10_message}")


@dp.message_handler(commands=['stats'])
async def stat(message: types.Message):
    #статистика пользователя в формате: Имя пользователя - количество сообщений
    user_stats = cursor.execute("SELECT user_stats FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone()
    your_id = message.from_id
    your_name = message.from_user.username
    await message.reply(
            f"[{your_name}](tg://user?id={str(your_id)}) - {user_stats[0]}",
            parse_mode="Markdown")


@dp.message_handler(commands=['aboutme'])
async def aboutme(message: types.Message):
    your_id = message.from_id
    await check(your_id)
    your_name = message.from_user.username
    user_stats = cursor.execute("SELECT user_stats FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone()
    rolenum = cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone()
    role = await get_role_name(rolenum[0])
    #Имя пользователя на следующей строке статистика сообщений на следующей строке права пользователя
    #если пользователь есть в списке администраторов чата, то выдаём роль администратор
    chat_admins = await bot.get_chat_administrators(message.chat.id)
    default_for_admin = int(config['Roles']['default_for_admin'])
    no_answer = False
    if rolenum[0] < default_for_admin:
        for admin in chat_admins:
            if admin.user.id == your_id:
                if default_for_admin == 0:
                    await message.reply(
                        f"Вы обнаружены в списке администраторов чата! \n"
                        f"Вам будет выдана роль: {config['Roles']['user']}\n"
                        f"Имя: [{your_name}](tg://user?id={str(your_id)})\n"
                        f"Кол-во сообщений: {user_stats[0]}\n"
                        f"Роль: {role}",
                        parse_mode="Markdown")
                    no_answer = True
                elif default_for_admin == 1:
                    await message.reply(
                        f"Вы обнаружены в списке администраторов чата.\n"
                        f"Вам будет выдана роль: {config['Roles']['moderator']}\n"
                        f"Имя: [{your_name}](tg://user?id={str(your_id)})\n"
                        f"Кол-во сообщений: {user_stats[0]}\n"
                        f"Роль: {role}",
                        parse_mode="Markdown")
                    no_answer = True
                elif default_for_admin == 2:
                    await message.reply(
                        f"Вы обнаружены в списке администраторов чата.\n"
                        f"Вам будет выдана роль: {config['Roles']['admin']}\n"
                        f"Имя: [{your_name}](tg://user?id={str(your_id)})\n"
                        f"Кол-во сообщений: {user_stats[0]}\n"
                        f"Роль: {role}",
                        parse_mode="Markdown")
                    no_answer = True
                cursor.execute("UPDATE user_list SET user_role = ? WHERE user_id = ?", (default_for_admin, your_id))
                database.commit()
    if no_answer == False:
        await message.reply(
            f"Имя: [{your_name}](tg://user?id={str(your_id)})\n"
            f"Кол-во сообщений: {user_stats[0]}\n"
            f"Роль: {role}",
            parse_mode="Markdown")

@dp.message_handler(commands=['setrole'])
async def setrole(message: types.Message):
    user_role = cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone()
    user_name = message.from_user.username
    target_name = message.text.split()[1]
    target_name = target_name[1:]
    target_role = cursor.execute("SELECT user_role FROM user_list WHERE user_name = ?", (target_name,)).fetchone()[0]
    user_id = cursor.execute("SELECT user_id FROM user_list WHERE user_name = ?", (target_name,)).fetchone()
    user_id = user_id[0]
    if await check_admin(user_id, message.chat.id) and target_role == 2:
        await message.reply("Вы не можете изменить роль этому пользователю!")
    else:
        if user_role[0] == 2:
            try:
                #Получаем id пользователя по нику в базе данных
                role = message.text.split()[2]
                if role == "0" or role == config['Roles']['user']:
                    role = config['Roles']['user']
                    rolenum = 0
                elif role == "1" or role == config['Roles']['moderator']:
                    role = config['Roles']['moderator']
                    rolenum = 1
                elif role == "2" or role == config['Roles']['admin']:
                    role = config['Roles']['admin']
                    rolenum = 2
                cursor.execute("UPDATE user_list SET user_role = ? WHERE user_id = ?", (rolenum, user_id))
                database.commit()
                await message.reply(
                    f"Пользователю [{target_name}](tg://user?id={str(user_id)}) выдана роль: {role}",
                    parse_mode="Markdown")
            except:
                await message.reply(
                    f"Ошибка! Проверьте правильность написания команды.",
                    parse_mode="Markdown")
        else:
            await message.reply(
                f"Ошибка! У вас нет прав на использование этой команды.",
                parse_mode="Markdown")


@dp.message_handler(commands=['about'])
async def about(message: types.Message):
    #проверка что в сообщении есть тег пользователя
    if len(message.text.split()) == 2:
        try:
            target_name = message.text.split()[1]
            target_name = target_name[1:]
            target_id = cursor.execute("SELECT user_id FROM user_list WHERE user_name = ?", (target_name,)).fetchone()
            target_id = target_id[0]
            await check(target_id)
        except:
            await message.reply(
                f"Ошибка! Проверьте правильность написания тега пользователя.",
                parse_mode="Markdown")
        user_stats = cursor.execute("SELECT user_stats FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
        user_role = cursor.execute("SELECT user_role FROM user_list WHERE user_id = ?", (target_id,)).fetchone()[0]
        user_role = await get_role_name(user_role)
        await message.reply(
            f"Имя: {target_name}\n"    
            f"Кол-во сообщений: {user_stats}\n"
            f"Роль: {user_role}")
    else:
        await message.reply(
            f"Ошибка! Проверьте правильность написания команды.")

from src.OpenAI.GPT35turbo.OA_processing import openai_message_processing


async def delete_message(message: types.Message, sleep_time: int = 0):
    await asyncio.sleep(sleep_time)
    with suppress(MessageCantBeDeleted, MessageToDeleteNotFound):
        await message.delete()

@dp.message_handler()
async def in_message(message: types.Message):
    chat_id = message.chat.id
    # Получение сообщений в чате, и запись их в базу данных
    if (message.chat.type == "private" or message.chat.type == "channel"):
        await message.reply(
            f"{config['Telegram']['private_answer']}",
            parse_mode="Markdown")
    elif (message.chat.type != "group" or message.chat.type != "supergroup") and \
            message.text != '' and message.text != ' ' and \
            (cursor.execute("SELECT chat_role FROM chat_list WHERE chat_id;") == 1): return None
    else:
        # Запись сообщения в базу данных
        cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                       (message.message_id, message.text, message.from_user.id,  0))
        #Проверка что отправителя сообщения нет в базе данных
        if cursor.execute("SELECT user_id FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone() is None:
            # Запись отправителя сообщения в базу данных
            cursor.execute("INSERT INTO user_list VALUES (?, ?, ?, ?)",
                           (message.from_user.id, message.from_user.username, 1, 0))
        #Запись статистики отправителя сообщения в базу данных
        else:
            cursor.execute("UPDATE user_list SET user_stats = user_stats + 1 WHERE user_id = ?",
                           (message.from_user.id,))
            #Записываем информацию в статистику чата.
            cursor.execute("UPDATE chat_list SET chat_stats = chat_stats + 1 WHERE chat_id = ?", (chat_id,))
            #Проверка на наличие имени пользователя в базе данных
            if cursor.execute("SELECT user_name FROM user_list WHERE user_id = ?", (message.from_user.id,)).fetchone() is not message.from_user.username:
                cursor.execute("UPDATE user_list SET user_name = ? WHERE user_id = ?",
                               (message.from_user.username, message.from_user.id))
        if message.reply_to_message is not None:
            # Запись ответа на сообщение в базу данных
            cursor.execute("UPDATE message_list SET answer_id = ? WHERE message_id = ?",
                           (message.reply_to_message.message_id, message.message_id))
        database.commit()
        # Обработка сообщения OpenAI
        send_answer = False
        typing_mode = False
        # импортируем массив триггеров из файла .ini
        if message.reply_to_message and message.reply_to_message.from_user.id == (await bot.me).id:
            send_answer = True
            typing_mode = True
        for trigger in bot_trigger_all:
            if trigger.lower() in message.text.lower():
                send_answer = True
                typing_mode = False
        for trigger in bot_trigger_front:
            if message.text.lower().startswith(trigger.lower()):
                send_answer = True
                typing_mode = False

        if send_answer:
            if typing_mode is False:
                your_id = message.from_id
                your_name = message.from_user.username
                temp_msg = await message.reply(
                    f"[{your_name}](tg://user?id={str(your_id)}), Подожди немного и я обязательно отвечу тебе!",
                    parse_mode="Markdown")
            # Пишем что бот печатает
            await bot.send_chat_action(message.chat.id, "typing")
            response = openai_message_processing(message.message_id)
            if response is None:
                bot_message_id = await message.reply("Я не понял тебя, попробуй перефразировать")
                if typing_mode is False:
                    asyncio.create_task(delete_message(temp_msg, 0))
                # заносим сообщение в базу данных в качестве message_id пишем id сообщения которое отправил бот
                cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                                    (bot_message_id, "Я не понял тебя, попробуй перефразировать", 0, message.message_id))
            else:
                bot_message_id = await message.reply(response['choices'][0]['message']['content'], parse_mode="markdown")
                if typing_mode is False:
                    asyncio.create_task(delete_message(temp_msg, 0))
                # заносим сообщение в базу данных в качестве message_id мы пишем id сообщения в bot_message_id
                cursor.execute("INSERT INTO message_list VALUES (?, ?, ?, ?)",
                                    (bot_message_id.message_id, response['choices'][0]['message']['content'], 0, message.message_id))
            # очищаем базу данных от старых сообщений
            cursor.execute("DELETE FROM message_list WHERE message_id < ?", (bot_message_id.message_id - DB_message_limit,))
            database.commit()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)