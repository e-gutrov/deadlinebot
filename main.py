import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import arrow

import utilities as util
import default_messages
from utilities import User, Deadline, Group
from clnd import Calendar

TOKEN = input('Enter token: ')

bot = telebot.TeleBot(TOKEN, threaded=False)  # threaded kills sqlalchemy, need to fix(?)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    util.get_user(message).set_state('')
    bot.send_message(message.chat.id, default_messages.welcome)


@bot.message_handler(commands=['help'])
def send_help(message):
    util.get_user(message).set_state('')
    bot.send_message(message.chat.id, default_messages.helpmsg)


@bot.message_handler(commands=['add'])
def add_deadline(message):
    user = util.get_user(message)
    user.set_state('add')
    bot.send_message(
        message.chat.id,
        default_messages.add_deadline,
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('clnd'))
def add_calendar(call):
    if call.data.endswith('nothing'):
        bot.answer_callback_query(call.id, 'Передвинь месяц или выбери дату.')
    elif call.data.endswith(('<', '>')):
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=Calendar(call.data).get_markup(
                util.get_user(from_user=call.from_user)
            ),
        )
    elif call.data.endswith('dot'):
        bot.answer_callback_query(call.id, 'Этот день не принадлежит выбранному месяцу.')
    else:
        msg_strs = call.message.text.split('\n')
        deadline_title = msg_strs[0][len('Дедлайн: '):]
        deadline_time = msg_strs[1][len('Время: '):].split(':')
        deadline_date = arrow.get(call.data, 'D.MM.YYYY').replace(
            hour=int(deadline_time[0]),
            minute=int(deadline_time[1]),
        )

        bot.edit_message_text(
            text=f'Дедлайн добавлен.\nНазвание: {deadline_title}\nДата: {deadline_date.format("DD.MM.YYYY HH:mm")}',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        user = util.get_user(from_user=call.from_user)
        deadline = Deadline(title=deadline_title, timestamp=deadline_date.timestamp, creator_id=user.id)
        user.add_deadline(util.add_deadline(deadline))


@bot.message_handler(commands=['list_done'])
def list_done(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_done_deadlines()
    if len(deadlines) == 0:
        bot.send_message(
            message.chat.id,
            default_messages.no_done_deadlines,
        )
    else:
        strs = []
        for i in range(len(deadlines)):
            strs.append(
                f'[{i+1}] '
                f'{arrow.get(deadlines[i].timestamp).format("DD.MM.YY HH:mm")} - '
                f'{deadlines[i].title}'
            )
        bot.send_message(message.chat.id, 'Закрытые дедлайны:\n' + '\n'.join(strs))


@bot.message_handler(commands=['list'])
def list_undone(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()
    if len(deadlines) == 0:
        bot.send_message(
            message.chat.id,
            default_messages.no_active_deadlines,
        )
    else:
        strs = []
        for i in range(len(deadlines)):
            strs.append(
                f'[{i+1}] '
                f'{arrow.get(deadlines[i].timestamp).format("DD.MM.YY HH:mm")} - '
                f'{deadlines[i].title}'
            )
        bot.send_message(message.chat.id, 'Дедлайны:\n' + '\n'.join(strs))


@bot.message_handler(commands=['done'])
def mark_done(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()

    bot.send_message(
        message.chat.id,
        default_messages.mark_done,
        reply_markup=util.get_deadlines_markup(deadlines, 'done'),
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('done'))
def mark_done_cb(call):
    user = util.get_user(from_user=call.from_user)
    deadline = user.mark_done(deadline_id=call.data.split()[1])
    if deadline is None:
        bot.answer_callback_query(call.id, 'Дедлайн уже выполнен/удален.')
    else:
        bot.edit_message_text(
            text=f'Дедлайн {deadline.title} отмечен выполненным.',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )


@bot.message_handler(commands=['undone'])
def mark_undone(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_done_deadlines()

    bot.send_message(
        message.chat.id,
        default_messages.mark_undone,
        reply_markup=util.get_deadlines_markup(deadlines, 'undone'),
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('undone'))
def mark_undone_cb(call):
    user = util.get_user(from_user=call.from_user)
    deadline = user.mark_undone(deadline_id=call.data.split()[1])

    if deadline is None:
        bot.answer_callback_query(call.id, 'Дедлайн уже отмечен невыполненным/удален.')
    else:
        bot.edit_message_text(
            text=f'Дедлайн {deadline.title} отмечен невыполненным',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )


@bot.message_handler(commands=['create_group'])
def create_group(message):
    user = util.get_user(message)
    user.set_state("create_group")
    bot.send_message(
        message.chat.id,
        'Как назовем?',
    )


@bot.message_handler(commands=['list_groups'])
def list_groups(message):
    user = util.get_user(message)
    user.set_state('')
    groups = user.get_groups()
    if len(groups) == 0:
        bot.send_message(
            message.chat.id,
            default_messages.no_groups,
        )
    else:
        strs = []
        for i in range(len(groups)):
            strs.append(f'{groups[i].name}; ключ {groups[i].id}')
        bot.send_message(message.chat.id, 'Список групп:\n' + '\n'.join(strs))


@bot.callback_query_handler(lambda x: x.data.startswith('leave'))
def leave_group_cb(call):
    user = util.get_user(from_user=call.from_user)
    group = user.leave_group(group_id=call.data.split()[1])
    if group is None:
        bot.answer_callback_query(call.id, 'Группа уже удалена.')
    else:
        bot.edit_message_text(
            text=f'Если захочешь вернуться в {group.name}, знаешь ключ: {group.id}',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )


@bot.message_handler(commands=['leave'])
def leave_group(message):
    user = util.get_user(message)
    user.set_state('')
    groups = user.get_groups()
    if len(groups) == 0:
        bot.send_message(
            message.chat.id,
            'У тебя нет групп.',
        )
    else:
        markup = InlineKeyboardMarkup()
        for group in groups:
            markup.add(InlineKeyboardButton(
                group.name,
                callback_data=f'leave {group.id}',
            ))
        bot.send_message(
            message.chat.id,
            default_messages.leave_group,
            reply_markup=markup,
        )


@bot.message_handler(commands=['join'])
def join_group(message):
    user = util.get_user(message)
    user.set_state('join')
    cid = message.chat.id
    bot.send_message(
        cid,
        'Пришли мне ключ группы',
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('shareb'))
def share_back_to_deadlines(call):
    user = util.get_user(from_user=call.from_user)
    deadlines = user.get_undone_deadlines()
    bot.edit_message_text(
        'Каким дедлайном поделимся?',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=util.get_deadlines_markup(deadlines, 'shared'),
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('shared'))
def share_deadline_chosen_cb(call):
    user = util.get_user(from_user=call.from_user)
    groups = user.get_groups()
    deadline = util.get_deadline(deadline_id=call.data.split()[1])

    markup = InlineKeyboardMarkup()

    for group in groups:
        markup.add(InlineKeyboardButton(
            group.name,
            callback_data=f'shareg {deadline.id} {group.id}',
        ))
    markup.add(InlineKeyboardButton(
        'К выбору дедлайна',
        callback_data='shareb',
    ))
    bot.edit_message_text(
        text=f'Ты делишься дедлайном {deadline.title}.\nКакую группу осчастливим?',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('shareg'))
def share_group_chosen_cb(call):
    deadline = util.get_deadline(call.data.split()[1])
    group = util.get_group(call.data.split()[2])
    # group.add_deadline() TODO
    for user in group.users:
        user.add_deadline(deadline)
    bot.edit_message_text(
        f'Ты поделился дедлайном {deadline.title} с {group.name}',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )


@bot.message_handler(commands=['share'])
def share(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()

    bot.send_message(
        message.chat.id,
        'Каким дедлайном поделимся?',
        reply_markup=util.get_deadlines_markup(deadlines, 'shared'),
    )


@bot.message_handler(func=lambda x: True)
def free_of_commands(message):
    user = util.get_user(message)
    cid = message.chat.id

    if user.state == "" or user.state is None:
        bot.send_message(
            cid,
            default_messages.unknown_state,
        )
        return

    if user.state == "add":
        msg_tokens = message.text.split()
        try:
            deadline_time = arrow.get(msg_tokens[-1], ['HH:mm', 'HH.mm', 'H:mm', 'H.mm']).format('HH:mm')
            deadline_title = ' '.join(msg_tokens[:-1])
        except (IndexError, arrow.parser.ParserError, arrow.parser.ParserMatchError):
            deadline_time = '23:59'
            deadline_title = ' '.join(msg_tokens)

        bot.send_message(
            cid,
            f'Дедлайн: {deadline_title}\nВремя: {deadline_time}\nВыбери дату:',
            reply_markup=Calendar().get_markup(user),
        )

    elif user.state == "create_group":
        name = ' '.join(message.text.split())
        group = Group(name)
        user.add_group(group)
        bot.send_message(
            cid,
            f'Группа {name} создана. Ключ: {group.id}.'
        )

    elif user.state == "join":
        key = message.text
        group = util.get_group(key)
        if group is None:
            bot.send_message(
                cid,
                f'Группа с ключом {key} не найдена. Попробуй еще.',
            )
            return
        user.add_group(group)
        bot.send_message(
            cid,
            f'Ты присоединился к группе {group.name}.',
        )  # TODO add last group deadlines

    user.set_state('')


bot.polling(timeout=50, none_stop=True)
