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
import redis
import rq

class Base(so.DeclarativeBase):
    metadata = sa.MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    })

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
	# TODO: deleting a user passive_deletes ALL references to that user (companions, messages, tasks etc.). Maybe this is bad...
	# so.Mapped[type] makes fields required unless the Optional key is present!

	# Notes on relationships as I slowly go insane:
	# cascade="all, delete-orphan" behavior implies that WHEN an operation is cascaded these params detail how to behave
	# (cascading means that a parent is being operated on in a way that requires a child update e.g. associated_user_id is deleted)
	# ondelete='CASCADE' means that when this CHILD record is deleted, cascade up to the parent record according to the cascade= rules set in the parent table.
	# passive_deletes=True means overriding the default MySQL behavior, which automatically changes all FK references to that ID to null. It just does that, idk why.
	# This command tells MySQL that instead of NULLing those IDs, to instead delete any records (on the DB side, not SQL-A side) with NULL IDs.

	# At least, that's what's supposed to be happening. Idk why it's not working.
	# It works if the user has no associated FKs initialized yet. But not if they have any companions or notifs. UGH

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

	companions: so.WriteOnlyMapped['Companion'] = so.relationship(
		back_populates='creator',
		cascade="all, delete-orphan",
		passive_deletes=True)

	messages_sent: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.sender_id',
        back_populates='author',
        cascade="all, delete-orphan",
        passive_deletes=True)

	messages_received: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.recipient_id',
        back_populates='recipient',
        cascade="all, delete-orphan",
        passive_deletes=True)

	notifications: so.WriteOnlyMapped['Notification'] = so.relationship(
        back_populates='user',
        cascade="all, delete-orphan",
        passive_deletes=True)

	tasks: so.WriteOnlyMapped['Task'] = so.relationship(
		back_populates='user',
		cascade="all, delete-orphan",
		passive_deletes=True)


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

	def launch_task(self, name, description, *args, **kwargs):
		rq_job = current_app.task_queue.enqueue(f'app.tasks.{name}', self.id,
                                                *args, **kwargs)
		task = Task(id=rq_job.get_id(), name=name, description=description,
                    user=self)
		db.session.add(task)
		return task

	def get_tasks_in_progress(self):
		query = self.tasks.select().where(Task.complete == False)
		return db.session.scalars(query)

	def get_task_in_progress(self, name):
		query = self.tasks.select().where(Task.name == name,
			Task.complete == False)
		return db.session.scalar(query)



@login.user_loader
def load_user(id):
	return db.session.get(User, int(id))

class Companion(db.Model):
	#need to add many more of these companion details later!
	#probably need a full list of all of their details as mentioned in the ipynb
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	associated_user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, onupdate='CASCADE', ondelete='CASCADE'), nullable=False, index=True)
	gender: so.Mapped[str] = so.mapped_column(sa.String(64), server_default="Other")
	realism: so.Mapped[str] = so.mapped_column(sa.String(64), server_default="Realistic")
	companion_name: so.Mapped[str] = so.mapped_column(sa.String(64))
	created_at_ts: so.Mapped[datetime] = so.mapped_column(index=True, default=lambda: datetime.now(timezone.utc))

	creator: so.Mapped[User] = so.relationship(
		back_populates='companions')

	def __repr__(self):
		return '<Companion: {}>'.format(self.companion_name)

class Message(SearchableMixin, db.Model):
	__searchable__ = ['body']
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	body: so.Mapped[str] = so.mapped_column(sa.String(140))
	timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
	sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, onupdate='CASCADE', ondelete='CASCADE'),
                                               nullable=False, index=True)
	recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, onupdate='CASCADE', ondelete='CASCADE'),
                                               nullable=False, index=True)
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
	user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, onupdate='CASCADE', ondelete='CASCADE'),
	                                           nullable=False, index=True)
	timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
	payload_json: so.Mapped[str] = so.mapped_column(sa.Text)

	user: so.Mapped[User] = so.relationship(
		back_populates='notifications')

	def get_data(self):
		return json.loads(str(self.payload_json))

class Task(db.Model):
    id: so.Mapped[str] = so.mapped_column(sa.String(36), primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id, onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    complete: so.Mapped[bool] = so.mapped_column(default=False)

    user: so.Mapped[User] = so.relationship(
    	back_populates='tasks')

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100