import string

import numpy as np
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import arrow


engine = sqlalchemy.create_engine('sqlite:///test.db')
Session = sessionmaker(bind=engine)
Base = declarative_base()

MAX_STATUS = 10

KEY_LEN = 8
KEY_CHARS = string.digits + string.ascii_letters


def gen_key():
    return ''.join([KEY_CHARS[np.random.choice(len(KEY_CHARS))] for _ in range(KEY_LEN)])


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    state = Column(String)

    deadlines = relationship('UserDeadlineAssociation', back_populates='user')
    groups = relationship('Group', secondary=lambda: user_group_assoc_table, back_populates='users')

    def get_assoc(self, deadline=None, deadline_id=None):
        if deadline_id is None:
            deadline_id = deadline.id
        return session.query(UserDeadlineAssociation).filter_by(
            user_id=self.id,
            deadline_id=deadline_id,
        ).first()

    def add_deadline(self, deadline, group_name=None):
        if self.get_assoc(deadline) is None:
            session.add(
                UserDeadlineAssociation(
                    user=self,
                    deadline=deadline,
                    group_name=group_name,
                    status=0,
                )
            )
        session.commit()

    def remove_deadline(self, deadline=None, deadline_id=None):
        assoc = self.get_assoc(deadline, deadline_id)
        if assoc is None or assoc.status != 0:
            return None
        else:
            deadline = assoc.deadline
            session.delete(assoc)
            session.commit()
            return deadline

    def shift_status(self, shift, lb=0):
        for assoc in self.deadlines:
            if assoc.status > lb:
                assoc.status += shift
            if assoc.status > MAX_STATUS:
                session.delete(assoc)
        session.commit()

    def mark_done(self, deadline=None, deadline_id=None):
        assoc = self.get_assoc(deadline, deadline_id)
        if assoc is None or assoc.status != 0:
            return None
        self.shift_status(1)
        assoc.status = 1
        session.commit()
        return assoc.deadline

    def mark_undone(self, deadline=None, deadline_id=None):
        assoc = self.get_assoc(deadline, deadline_id)
        if assoc is None or assoc.status == 0:
            return None
        self.shift_status(-1, assoc.status)
        assoc.status = 0
        session.commit()
        return assoc.deadline

    def add_group(self, group):
        self.groups.append(group)
        session.commit()

    def get_groups(self):
        return sorted(self.groups, key=lambda x: (x.name, x.id))

    def leave_group(self, group=None, group_id=None):
        if group is None:
            group = session.query(Group).filter_by(id=group_id).first()
        if group is None:
            return None
        self.groups.remove(group)
        session.commit()
        return group

    def set_state(self, state):
        self.state = state
        session.commit()

    def get_done_deadlines(self):
        done_deadlines = []
        for i in self.deadlines:
            if i.status != 0:
                done_deadlines.append(i)
        done_deadlines.sort(key=lambda x: x.status)
        return list(map(lambda x: x.deadline, done_deadlines))

    def get_undone_deadlines(self):
        undone_deadlines = []
        for i in self.deadlines:
            if i.status == 0:
                undone_deadlines.append(i.deadline)
        undone_deadlines.sort(key=lambda x: (x.timestamp, x.id))
        return undone_deadlines


class Group(Base):
    __tablename__ = 'groups'
    MAX_DEADLINES = 10

    id = Column(String, primary_key=True)
    name = Column(String)

    users = relationship('User', secondary=lambda: user_group_assoc_table, back_populates='groups')
    deadlines = relationship('Deadline', secondary=lambda: group_deadline_assoc_table)
    # deadlines = relationship('GroupDeadlineAssociation', back_populates='group')

    def __init__(self, name: str):
        self.name = name
        while True:
            self.id = gen_key()
            if session.query(Group).filter_by(id=self.id).count() == 0:
                break
        session.add(self)
        session.commit()

    def add_deadline(self, deadline):
        if deadline in self.deadlines:
            return None
        else:
            self.deadlines.append(deadline)
            if len(self.deadlines) > Group.MAX_DEADLINES:
                pass  # TODO by date
            session.commit()

            return deadline


class Deadline(Base):
    __tablename__ = 'deadlines'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    timestamp = Column(Integer)
    creator_id = Column(Integer)

    users = relationship('UserDeadlineAssociation', back_populates='deadline')

    def __str__(self):
        return f'id={self.id}, title={self.title}, timestamp={self.timestamp}, creator_id={self.creator_id}'


class UserDeadlineAssociation(Base):
    __tablename__ = 'user_deadline_association'

    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    deadline_id = Column(Integer, ForeignKey('deadlines.id'), primary_key=True)
    group_name = Column(String)

    status = Column(Integer)  # 0 for undone, 1..MAX_DONE for done (1-latest)

    user = relationship('User', back_populates='deadlines')
    deadline = relationship('Deadline', back_populates='users')

# class GroupDeadlineAssociation(Base):
#     __tablename__ = 'group_deadline_association'
#
#     group_id = Column(String, ForeignKey('groups.id'), primary_key=True)
#     deadline_id = Column(Integer, ForeignKey('deadlines.id'), primary_key=True)
#     status = Column(Integer)
#
#     group = relationship('Group', back_populates='deadlines')
#     deadline = relationship('Deadline')


user_group_assoc_table = sqlalchemy.Table(
    'user_group_association', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', String, ForeignKey('groups.id'))
)
group_deadline_assoc_table = sqlalchemy.Table(
    'group_deadline_association', Base.metadata,
    Column('group_id', String, ForeignKey('groups.id')),
    Column('deadline_id', Integer, ForeignKey('deadlines.id')),
)
Base.metadata.create_all(engine)
session = Session()


def add_deadline(deadline):
    session.add(deadline)
    session.commit()
    return deadline


def get_user(message=None, from_user=None):
    if from_user is None:
        from_user = message.from_user
    # print('getting user', from_user)
    user = session.query(User).filter_by(id=from_user.id).first()
    if user is None:
        user = User(id=from_user.id)
        session.add(user)
        user.state = ''
    user.first_name = from_user.first_name
    user.last_name = from_user.last_name
    session.commit()
    return user


def get_group(group_id):
    return session.query(Group).filter_by(id=group_id).first()


def get_deadline(deadline_id):
    return session.query(Deadline).filter_by(id=deadline_id).first()


def get_deadlines_markup(deadlines, cb_data_prefix):
    markup = InlineKeyboardMarkup()
    for deadline in deadlines:
        markup.add(InlineKeyboardButton(
            f'[{arrow.get(deadline.timestamp).format("DD.MM HH:mm")}] {deadline.title}',
            callback_data=f'{cb_data_prefix} {deadline.id}',
        ))
    return markup


def get_groups_markup(groups, cb_data_prefix):
    markup = InlineKeyboardMarkup()
    for group in groups:
        markup.add(InlineKeyboardButton(group.name, callback_data=f'{cb_data_prefix} {group.id}'))
    return markup


def deadlines_to_str(deadlines, sep='\n', with_group=False):
    strs = []
    group_deadlines = dict()
    id_to_group = dict()

    for i in range(len(deadlines)):
        date = arrow.get(deadlines[i].timestamp).format("DD.MM.YY HH:mm")
        if not with_group:
            strs.append(f'[{i + 1}] {date} - {deadlines[i].title}')
        else:
            group_id = deadlines[i].group_id

            if group_id == 0:
                strs.append(f'{date} - {deadlines[i].title}')  # personal
                continue
            if group_id not in id_to_group:
                id_to_group[group_id] = get_group(group_id).name
            name = id_to_group[group_id]
            if name not in group_deadlines:
                group_deadlines[name] = []
            group_deadlines[name].append(f'{date} - {deadlines[i].title}')

    if not with_group:
        return sep.join(strs)
    else:
        result = ''