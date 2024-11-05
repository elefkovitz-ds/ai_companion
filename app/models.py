from datetime import datetime, timezone
from hashlib import md5
from time import time
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app import db, login

class User(UserMixin, db.Model):
	#so.Mapped[type] makes fields required unless the Optional key is present!
	id: so.Mapped[int] = so.mapped_column(primary_key=True)
	username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
	email: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
	password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
	about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
	pref_language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))

	user_tz: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: timezone.utc)
	last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(user_tz))
	#last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

	companions: so.WriteOnlyMapped['Companion'] = so.relationship(back_populates='creator')
	messages: so.WriteOnlyMapped['Message'] = so.relationship(back_populates='author')

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
		return jwt.encode({'reset_password': self.id, 'exp': time() + expires_in}, app.config['SECRET_KEY'], algorithm='HS256')

	@staticmethod
	def verify_reset_password_token(token):
		try:
			id = jwt.decode(token, app.config['SECRET_KEY'],
				algorithms=['HS256'])['reset_password']
		except:
			return
		return db.session.get(User, id)

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

class Message(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
    language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))

    author: so.Mapped[User] = so.relationship(back_populates='messages')

    def __repr__(self):
        return '<Message {}>'.format(self.body)

@login.user_loader
def load_user(id):
	return db.session.get(User, int(id))
