from datetime import datetime, timezone
from hashlib import md5
import json
from time import time
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app import db, login
from app.search import add_to_index, remove_from_index, query_index

class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return [], 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        query = sa.select(cls).where(cls.id.in_(ids)).order_by(
            db.case(*when, value=cls.id))
        return db.session.scalars(query), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in db.session.scalars(sa.select(cls)):
            add_to_index(cls.__tablename__, obj)

db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


class User(UserMixin, db.Model):
	#so.Mapped[type] makes fields required unless the Optional key is present!
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
	email: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
	password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
	about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
	pref_language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))

	#user_tz: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: timezone.utc)
	#last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(user_tz))
	last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
	last_message_read_time: so.Mapped[Optional[datetime]]

	companions: so.WriteOnlyMapped['Companion'] = so.relationship(back_populates='creator')
	#messages: so.WriteOnlyMapped['Message'] = so.relationship(back_populates='author')

	messages_sent: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.sender_id', back_populates='author')
	messages_received: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.recipient_id', back_populates='recipient')
	notifications: so.WriteOnlyMapped['Notification'] = so.relationship(
        back_populates='user')


	def __repr__(self):
		return '<User {0}'.format(self.username)

	def set_password(self, password):
		self.password_hash = generate_password_hash(password)

	def check_password(self, password):
		return check_password_hash(self.password_hash, password)

	def avatar(self, size):
		digest = md5(self.email.lower().encode('utf-8')).hexdigest()
		return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

	def get_reset_password_token(self, expires_in=900):
		return jwt.encode({'reset_password': self.id, 'exp': time() + expires_in}, current_app.config['SECRET_KEY'], algorithm='HS256')

	@staticmethod
	def verify_reset_password_token(token):
		try:
			id = jwt.decode(token, current_app.config['SECRET_KEY'],
				algorithms=['HS256'])['reset_password']
		except:
			return
		return db.session.get(User, id)

	def unread_message_count(self):
		last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
		query = sa.select(Message).where(Message.recipient == self,
                                         Message.timestamp > last_read_time)
		return db.session.scalar(sa.select(sa.func.count()).select_from(
            query.subquery()))

	def add_notification(self, name, data):
		db.session.execute(self.notifications.delete().where(
            Notification.name == name))
		n = Notification(name=name, payload_json=json.dumps(data), user=self)
		db.session.add(n)
		return n


@login.user_loader
def load_user(id):
	return db.session.get(User, int(id))

class Companion(db.Model):
	#need to add many more of these companion details later!
	#probably need a full list of all of their details as mentioned in the ipynb
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	associated_user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
	gender: so.Mapped[str] = so.mapped_column(sa.String(64), server_default="Other")
	realism: so.Mapped[str] = so.mapped_column(sa.String(64), server_default="Realistic")
	companion_name: so.Mapped[str] = so.mapped_column(sa.String(64))
	created_at_ts: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))

	creator: so.Mapped[User] = so.relationship(back_populates='companions')

	def __repr__(self):
		return '<Companion: {}>'.format(self.companion_name)

class Message(SearchableMixin, db.Model):
	__searchable__ = ['body']
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	body: so.Mapped[str] = so.mapped_column(sa.String(140))
	timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
	sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
	recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
	language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))

	
	author: so.Mapped[User] = so.relationship(
		foreign_keys='Message.sender_id',
		back_populates='messages_sent')
	recipient: so.Mapped[User] = so.relationship(
		foreign_keys='Message.recipient_id',
		back_populates='messages_received')

	def __repr__(self):
		return '<Message {}>'.format(self.body)

class Notification(db.Model):
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
	user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
	                                           index=True)
	timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
	payload_json: so.Mapped[str] = so.mapped_column(sa.Text)

	user: so.Mapped[User] = so.relationship(back_populates='notifications')

	def get_data(self):
		return json.loads(str(self.payload_json))

