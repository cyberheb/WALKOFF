import json

from sqlalchemy import func

from server.extensions import db
from server.messaging import MessageAction

user_messages_association = db.Table('user_messages',
                                  db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                                  db.Column('message_id', db.Integer, db.ForeignKey('message.id')))


class Message(db.Model):
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String())
    body = db.Column(db.String(), nullable=False)
    users = db.relationship('User', secondary=user_messages_association,
                            backref=db.backref('messages', lazy='dynamic'))
    workflow_execution_uid = db.Column(db.String(25))
    requires_reauth = db.Column(db.Boolean, default=False)
    requires_action = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=func.current_timestamp())
    history = db.relationship('MessageHistory', backref='message', lazy=True)

    def __init__(self, subject, body, workflow_execution_uid, users, requires_reauth=False, requires_action=False):
        self.subject = subject
        self.body = body
        self.workflow_execution_uid = workflow_execution_uid
        self.users = users
        self.requires_reauth = requires_reauth
        self.requires_action = requires_action

    def record_user_action(self, user, action):
        if user in self.users:
            if ((action == MessageAction.unread and not self.user_has_read(user))
                    or (action == MessageAction.respond and (not self.requires_action or self.is_acted_on()[0]))):
                return
            elif action == MessageAction.delete:
                self.users.remove(user)
            self.history.append(MessageHistory(user, action))

    def user_has_read(self, user):
        user_history = [history_entry for history_entry in self.history if history_entry.user_id == user.id]
        for history_entry in user_history[::-1]:
            if history_entry.action in (MessageAction.read, MessageAction.unread):
                if history_entry.action == MessageAction.unread:
                    return False
                if history_entry.action == MessageAction.read:
                    return True
        else:
            return False

    def user_last_read_at(self, user):
        user_history = [history_entry for history_entry in self.history if history_entry.user_id == user.id]
        for history_entry in user_history[::-1]:
            if history_entry.action == MessageAction.read:
                return history_entry.timestamp
        else:
            return None

    def get_read_by(self):
        return {entry.username for entry in self.history if entry.action == MessageAction.read}

    def is_acted_on(self):
        if not self.requires_action:
            return False, None, None
        for history_entry in self.history[::-1]:
            if history_entry.action == MessageAction.respond:
                return True, history_entry.timestamp, history_entry.username
        else:
            return False, None, None

    def as_json(self, with_read_by=True, user=None):
        is_acted_on, acted_on_timestamp, acted_on_by = self.is_acted_on()
        ret = {'id': self.id,
               'subject': self.subject,
               'body': json.loads(self.body),
               'workflow_execution_uid': self.workflow_execution_uid,
               'requires_reauthorization': self.requires_reauth,
               'requires_action': self.requires_action,
               'created_at': str(self.created_at),
               'awaiting_action': self.requires_action and not is_acted_on}
        if is_acted_on:
            ret['acted_on_at'] = str(acted_on_timestamp)
            ret['acted_on_by'] = acted_on_by
        if with_read_by:
            ret['read_by'] = list(self.get_read_by())
        if user:
            ret['is_read'] = self.user_has_read(user)
            ret['last_read_at'] = str(self.user_last_read_at(user))
        return ret


class MessageHistory(db.Model):
    __tablename__ = 'message_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.Enum(MessageAction))
    timestamp = db.Column(db.DateTime, default=func.current_timestamp())
    user_id = db.Column(db.Integer)
    username = db.Column(db.String)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'))

    def __init__(self, user, action):
        self.action = action
        self.user_id = user.id
        self.username = user.username

    def as_json(self):
        return {'action': self.action.name,
                'user_id': self.user_id,
                'username': self.username,
                'id': self.id,
                'timestamp': str(self.timestamp)}