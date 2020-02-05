import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import arrow

import utilities as util
import default_messages
from utilities import User, Deadline, Group
from clnd import Calendar

with open('token.txt', 'r') as fin:
    TOKEN = fin.readline().strip()

bot = telebot.TeleBot(TOKEN, threaded=False)  # threaded kills sqlalchemy, need to fix(?)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    util.get_user(message).set_state('')
    bot.send_message(message.chat.id, default_messages.welcome)


@bot.message_handler(commands=['help'])
def send_help(message):
    util.get_user(message).set_state('')
    bot.send_message(message.chat.id, default_messages.helpmsg)


@bot.message_handler(commands=['reset'])
def reset_state(message):
    util.get_user(message).set_state('')
    bot.send_message(message.chat.id, default_messages.ok)


@bot.message_handler(func=lambda x: util.get_user(x).state.startswith('settime'))
def add_deadline_time(message):
    try:
        time = arrow.get(message.text, ['HH:mm', 'H:mm'])
    except (arrow.ParserError, ValueError):
        bot.send_message(message.chat.id, default_messages.invalid_time)
        return

    user = util.get_user(message, count_request=False)
    tokens = user.state.split()
    deadline_date = arrow.get(tokens[1], 'DD.MM.YY').replace(hour=time.hour, minute=time.minute)
    deadline_title = ' '.join(tokens[2:])

    deadline = Deadline(title=deadline_title, timestamp=deadline_date.timestamp, creator_id=user.id)
    user.add_deadline(util.add_deadline(deadline))
    user.set_state('')
    bot.send_message(message.chat.id, default_messages.ok)


@bot.callback_query_handler(func=lambda x: x.data.startswith('settime'))
def add_deadline_time_cb(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    time = arrow.get(call.data.split()[1], 'HH:mm')
    msg_strs = call.message.text.split('\n')
    deadline_title = msg_strs[0][len('Дедлайн: '):]
    deadline_date = arrow.get(msg_strs[1][len('Дата: '):], 'DD.MM.YY').replace(hour=time.hour, minute=time.minute)

    deadline = Deadline(title=deadline_title, timestamp=deadline_date.timestamp, creator_id=user.id)
    user.add_deadline(util.add_deadline(deadline))
    user.set_state('')

    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, 'OK')


@bot.message_handler(commands=['add'])
def add_deadline(message):
    user = util.get_user(message)
    user.set_state('add')
    bot.send_message(message.chat.id, default_messages.add_deadline)


@bot.callback_query_handler(func=lambda x: x.data.startswith('clnd'))
def add_calendar(call):
    if call.data.endswith('nothing'):
        pass
    elif call.data.endswith(('<', '>')):
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=Calendar(call.data).get_markup(util.get_user(from_user=call.from_user)),
        )
    elif call.data.endswith('dot'):
        bot.answer_callback_query(call.id, 'Этот день не принадлежит выбранному месяцу.')
    else:
        msg_strs = call.message.text.split('\n')
        deadline_title = msg_strs[0][len('Дедлайн: '):]
        deadline_date = arrow.get(call.data, 'D.MM.YYYY')

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('00:00', callback_data='settime 00:00'),
            InlineKeyboardButton('23:59', callback_data='settime 23:59'),
        )

        bot.edit_message_text(
            f'Дедлайн: {deadline_title}\nДата: {deadline_date.format("DD.MM.YY")}\nПришли мне время в формате чч:мм',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
        util.get_user(
            from_user=call.from_user,
            count_request=False
        ).set_state(f'settime {deadline_date.format("DD.MM.YY")} {deadline_title}')


@bot.message_handler(commands=['list_done'])
def list_done(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_done_deadlines()
    if len(deadlines) == 0:
        bot.send_message(message.chat.id, default_messages.no_done_deadlines)
    else:
        bot.send_message(message.chat.id, 'Закрытые дедлайны:\n' + util.deadlines_to_str(deadlines))


@bot.message_handler(commands=['list'])
def list_undone(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines(raw=True)
    if len(deadlines) == 0:
        bot.send_message(message.chat.id, default_messages.no_active_deadlines)
    else:
        bot.send_message(message.chat.id, 'Дедлайны\n\n' + util.deadlines_to_str(deadlines, done=True))


@bot.message_handler(commands=['done'])
def mark_done(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()
    if len(deadlines) == 0:
        bot.send_message(message.chat.id, default_messages.no_active_deadlines)
    else:
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
            text=f'Дедлайн "{deadline.title}" отмечен выполненным.',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )


@bot.message_handler(commands=['undone'])
def mark_undone(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_done_deadlines()
    if len(deadlines) == 0:
        bot.send_message(message.chat.id, default_messages.no_done_deadlines)
    else:
        bot.send_message(
            message.chat.id,
            default_messages.mark_undone,
            reply_markup=util.get_deadlines_markup(user.get_done_deadlines(), 'undone'),
        )


@bot.callback_query_handler(func=lambda x: x.data.startswith('undone'))
def mark_undone_cb(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    deadline = user.mark_undone(deadline_id=call.data.split()[1])

    if deadline is None:
        bot.answer_callback_query(call.id, 'Дедлайн уже отмечен невыполненным/удален.')
    else:
        bot.edit_message_text(
            text=f'Дедлайн "{deadline.title}" отмечен невыполненным.',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )

@bot.message_handler(commands=['create_group'])
def create_group(message):
    user = util.get_user(message)
    user.set_state("create_group")
    bot.send_message(message.chat.id, 'Как назовем?')


@bot.message_handler(commands=['groups'])
def list_groups(message):
    user = util.get_user(message)
    user.set_state('')
    groups = user.get_groups()
    if len(groups) == 0:
        bot.send_message(message.chat.id, default_messages.no_groups)
    else:
        strs = []
        for i in range(len(groups)):
            strs.append(f'[{i + 1}] {groups[i].name}')
        bot.send_message(message.chat.id, 'Список групп:\n' + '\n'.join(strs))


@bot.callback_query_handler(lambda x: x.data.startswith('leave'))
def leave_group_cb(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    group = user.leave_group(group_id=call.data.split()[1])
    if group is None:
        bot.answer_callback_query(call.id, 'Группа уже удалена.')
    else:
        bot.edit_message_text(
            text=f'Если захочешь вернуться в "{group.name}", знаешь ключ: {group.id}',
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
        bot.send_message(message.chat.id, default_messages.no_groups)
    else:
        bot.send_message(
            message.chat.id, default_messages.leave_group,
            reply_markup=util.get_groups_markup(groups, 'leave'),
        )


@bot.message_handler(commands=['join'])
def join_group(message):
    user = util.get_user(message)
    user.set_state('join')
    bot.send_message(message.chat.id, 'Пришли мне ключ группы',)


@bot.callback_query_handler(func=lambda x: x.data.startswith('shareb'))
def share_back_to_deadlines(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    deadlines = user.get_undone_deadlines()
    if len(deadlines) == 0:
        text = default_messages.no_active_deadlines
        markup = None
    elif len(user.groups) == 0:
        text = default_messages.no_groups
        markup = None
    else:
        text = 'Каким дедлайном поделимся?'
        markup = util.get_deadlines_markup(deadlines, 'shared')

    bot.edit_message_text(
        text=text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('shared'))
def share_deadline_chosen_cb(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    groups = user.get_groups()
    deadline = util.get_deadline(deadline_id=call.data.split()[1])

    markup = util.get_groups_markup(groups, f'shareg {deadline.id}')
    markup.add(InlineKeyboardButton('К выбору дедлайна', callback_data='shareb'))

    bot.edit_message_text(
        text=f'Ты делишься дедлайном "{deadline.title}".\nКакую группу осчастливим?',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('shareg'))
def share_group_chosen_cb(call):
    tokens = call.data.split()
    deadline = util.get_deadline(tokens[1])
    group = util.get_group(tokens[2])
    group.add_deadline(deadline)
    for user in group.users:
        user.add_deadline(deadline, group.name)
    bot.edit_message_text(
        f'Ты поделился дедлайном "{deadline.title}" с "{group.name}".',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('del'))
def delete_deadline_cb(call):
    user = util.get_user(from_user=call.from_user, count_request=False)
    deadline = user.remove_deadline(deadline_id=call.data.split()[1])

    if deadline is None:
        bot.answer_callback_query(call.id, 'Дедлайн отмечен выполненным/удалён.')
    else:
        bot.edit_message_text(
            text=f'Дедлайн "{deadline.title}" в {arrow.get(deadline.timestamp).format("DD.MM.YY HH:mm")} удалён.',
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )


@bot.message_handler(commands=['delete'])
def delete_deadline(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()

    bot.send_message(
        message.chat.id, 'Какой дедлайн удалим?',
        reply_markup=util.get_deadlines_markup(deadlines, 'del')
    )


@bot.message_handler(commands=['share'])
def share(message):
    user = util.get_user(message)
    user.set_state('')
    deadlines = user.get_undone_deadlines()
    if len(deadlines) == 0:
        bot.send_message(message.chat.id, default_messages.no_active_deadlines)
    elif len(user.groups) == 0:
        bot.send_message(message.chat.id, default_messages.no_groups)
    else:
        bot.send_message(
            message.chat.id, 'Каким дедлайном поделимся?',
            reply_markup=util.get_deadlines_markup(deadlines, 'shared'),
        )


@bot.callback_query_handler(func=lambda x: x.data.startswith('view'))
def calendar_cb(call):
    if call.data.endswith('nothing'):
        pass
    elif call.data.endswith(('<', '>')):
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=Calendar(call.data).get_markup(util.get_user(from_user=call.from_user), 'view'),
        )
    elif call.data.endswith('dot'):
        bot.answer_callback_query(call.id, 'Этот день не принадлежит выбранному месяцу.')
    else:
        chosen_date_from = arrow.get(call.data, 'D.MM.YYYY').replace(hour=0, minute=0, second=0)
        chosen_date_to = chosen_date_from.shift(days=1)
        chosen_date_from = chosen_date_from.timestamp
        chosen_date_to = chosen_date_to.timestamp
        user = util.get_user(from_user=call.from_user)
        deadlines = user.get_undone_deadlines()
        strs = []
        for i in range(len(deadlines)):
            if chosen_date_from <= deadlines[i].timestamp <= chosen_date_to:
                strs.append(
                    f'[{len(strs) + 1}] '
                    f'{arrow.get(deadlines[i].timestamp).format("DD.MM.YY HH:mm")} - '
                    f'{deadlines[i].title}'
                )

        if len(strs) == 0:
            text = f'На {arrow.get(chosen_date_from).format("DD.MM.YY")} дедлайнов нет.'
        else:
            text = f'Дедлайны на {arrow.get(chosen_date_from).format("DD.MM.YY")}:\n' + '\n'.join(strs)

        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id)


@bot.message_handler(commands=['calendar'])
def give_calendar(message):
    bot.send_message(
        message.chat.id,
        'Нажми на дату, чтобы посмотреть на все дедлайны в этот день',
        reply_markup=Calendar().get_markup(util.get_user(message), 'view'),
    )


@bot.callback_query_handler(func=lambda x: x.data.startswith('key'))
def get_key_cb(call):
    group = util.get_group(call.data.split()[1])
    bot.edit_message_text(
        f'Высылаю ключ для присоединения к группе "{group.name}"',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )
    bot.send_message(call.message.chat.id, {group.id})


@bot.message_handler(commands=['key'])
def get_key(message):
    user = util.get_user(message)
    user.set_state('')

    groups = user.get_groups()
    if len(groups) == 0:
        bot.send_message(message.chat.id, default_messages.no_groups)
    else:
        bot.send_message(
            message.chat.id, default_messages.key,
            reply_markup=util.get_groups_markup(groups, 'key'),
        )


@bot.message_handler(func=lambda x: True)
def free_of_commands(message):
    user = util.get_user(message)
    cid = message.chat.id

    if user.state == "" or user.state is None:
        bot.send_message(cid, default_messages.unknown_state)
        return

    if user.state == "add":
        deadline_title = ' '.join(message.text.split())
        bot.send_message(
            cid,
            f'Дедлайн: {deadline_title}\nВыбери дату:',
            reply_markup=Calendar().get_markup(user),
        )

    elif user.state == "create_group":
        name = ' '.join(message.text.split())
        group = Group(name)
        user.add_group(group)
        bot.send_message(cid, f'Группа "{name}" создана. Ключ: {group.id}.')

    elif user.state == "join":
        key = message.text
        group = util.get_group(key)
        if group is None:
            bot.send_message(cid, f'Группа с ключом {key} не найдена. Попробуй еще.',)
            return
        user.add_group(group)
        bot.send_message(cid, f'Ты присоединился к группе "{group.name}".')
        for deadline in group.deadlines:
            user.add_deadline(deadline)

    user.set_state('')


while True:
    try:
        bot.polling(timeout=50, none_stop=True)
    except Exception as e:
        util.logger.error(e)
