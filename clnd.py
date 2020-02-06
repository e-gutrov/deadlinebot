import calendar

import arrow
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


class Calendar:
    def __init__(self, date=None):
        if date is None:
            self.date = arrow.now().replace(day=1, hour=0, minute=0, second=0)
        else:
            self.date = arrow.get(date, 'MM.YYYY')
            if date.endswith('<'):
                self.date = self.date.shift(months=-1)
            else:
                self.date = self.date.shift(months=1)

    def get_markup(self, user, cb_prefix='clnd'):
        callback_txt = cb_prefix + ' {}.' + self.date.format('MM.YYYY') + ' {}'
        markup = InlineKeyboardMarkup(row_width=7)

        markup.add(
            InlineKeyboardButton('<', callback_data=callback_txt.format('', '<')),
            InlineKeyboardButton(self.date.format('MMM YYYY'), callback_data=callback_txt.format('', 'nothing')),
            InlineKeyboardButton('>', callback_data=callback_txt.format('', '>')),
        )
        markup.add(*map(
            lambda x: InlineKeyboardButton(x, callback_data=callback_txt.format('', 'nothing')),
            ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        ))

        cnt = [0] * 32
        for i in user.deadlines:
            if i.status != 0:
                continue
            i_date = arrow.get(i.deadline.timestamp).shift(minutes=user.time_shift)
            if i_date.month == self.date.month and i_date.year == self.date.year:
                cnt[i_date.day] += 1

        days = list(calendar.Calendar().itermonthdays(self.date.year, self.date.month))
        for i in range(0, len(days), 7):
            row = []
            for j in range(i, i + 7):
                if days[j] == 0:
                    row.append(InlineKeyboardButton('.', callback_data=callback_txt.format('', 'dot')))
                else:
                    btn_txt = str(days[j])
                    if cnt[days[j]] > 0:
                        btn_txt += f'({cnt[days[j]]})'
                    row.append(InlineKeyboardButton(btn_txt, callback_data=callback_txt.format(str(days[j]), 'set')))
            markup.add(*row)
        return markup

