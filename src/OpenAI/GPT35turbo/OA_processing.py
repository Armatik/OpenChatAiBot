import sqlite3
import os
import configparser

mother_path = os.path.dirname(os.path.dirname(os.getcwd()))

config = configparser.ConfigParser()
config.read(os.path.join(mother_path, 'src/config.ini'))

database = sqlite3.connect(os.path.join(mother_path, 'DataBase/OCAB_DB.db'))
cursor = database.cursor()
reply_ignore = config['Telegram']['reply_ignore'].split('| ')

# Импорт библиотек

import openai
max_token_count = int(config['Openai']['max_token_count'])

base_message_formated_text = [
    {
        "role": "system",
        "content": config['Openai']['story_model']
    }
]


def openai_response(message_formated_text):
    # Запуск OpenAI
    # Считаем размер полученного текста
    print(message_formated_text)
    count_length = 0
    for message in message_formated_text:
        print(message["content"])
        count_length += len(message["content"])
    print(count_length)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=message_formated_text,
        max_tokens=max_token_count - count_length
    )
    return response

def sort_message_from_user(message_formated_text, message_id):
    print(int(*(
        cursor.execute("SELECT message_sender FROM message_list WHERE message_id = ?", (message_id,)).fetchone())))
    if int(*(
            cursor.execute("SELECT message_sender FROM message_list WHERE message_id = ?",
                           (message_id,)).fetchone())) == 0:
        message_formated_text.append({
            "role": "assistant",
            "content": str(*(cursor.execute("SELECT message_text FROM message_list WHERE message_id = ?",
                                            (message_id,)).fetchone()))
        })
    else:
        message_formated_text.append({
            "role": "user",
            "content": str(*(cursor.execute("SELECT message_text FROM message_list WHERE message_id = ?",
                                            (message_id,)).fetchone()))
        })
    #Проверка что длина всех сообщений в кортеже не превышает max_token_count-500
    count_length = 0
    for message in message_formated_text:
        count_length += len(message['content'])
    if count_length > max_token_count-800:
        message_formated_text.pop(1)
    return message_formated_text

def openai_collecting_message(message_id, message_formated_text):
    # собирает цепочку сообщений для OpenAI длинной до max_token_count
    # проверяем что сообщение отвечает на другое сообщение
    if int(*(cursor.execute("SELECT answer_id FROM message_list WHERE message_id = ?", (message_id,)).fetchone())) not in (0, 643885, 476959, 1, 476977, 633077, 630664, 476966, 634567):
        # Продолжаем искать ответы на сообщения
        print(int(*(cursor.execute("SELECT answer_id FROM message_list WHERE message_id = ?", (message_id,)).fetchone())))
        message_formated_text = openai_collecting_message(int(*(cursor.execute("SELECT answer_id FROM message_list WHERE message_id = ?", (message_id,)).fetchone())), message_formated_text)
        #Проверяем ID отправителя сообщения, если 0 то это сообщение от бота
        sort_message_from_user(message_formated_text, message_id)
    else:
        # Проверяем ID отправителя сообщения, если 0 то это сообщение от бота
        sort_message_from_user(message_formated_text, message_id)
    return message_formated_text


def openai_message_processing(message_id):
    #проверяем на наличие сообщения в базе данных
    if cursor.execute("SELECT message_text FROM message_list WHERE message_id = ?", (message_id,)).fetchone() is None:
        return None
    else:
        # проверяем на то что сообщение влезает в max_token_count с учётом message_formated_text
        #print((len(str(cursor.execute("SELECT message_text FROM message_list WHERE message_id")))))
        #print(len(message_formated_text[0]['content']))
        #print(max_token_count)
        #print(max_token_count - len(message_formated_text[0]['content']))
        message_formated_text = base_message_formated_text
        if ((len(str(cursor.execute("SELECT message_text FROM message_list WHERE message_id")))) < (max_token_count - len(message_formated_text[0]['content']))):
            message_formated_text = openai_collecting_message(message_id, message_formated_text)
            response = openai_response(message_formated_text)
            return response
        else:
            return f"Сообщение слишком длинное, максимальная длина сообщения \
            {max_token_count - len(message_formated_text[0]['content'])} символов, укоротите его на \
            {len(str(cursor.execute('SELECT message_text FROM message_list WHERE message_id'))) - max_token_count} символов"