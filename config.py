import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
	#generate good secret key: python -c 'import secrets; print(secrets.token_hex())'
	SECRET_KEY = os.environ.get('SECRET_KEY')
	SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
		'sqlite:///' + os.path.join(basedir, 'app.db')
	
	REDIS_URL = os.environ.get('REDIS_URL') or 'redis://'

	ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL')

	MAIL_SERVER = os.environ.get('MAIL_SERVER')
	MAIL_PORT = int(os.environ.get('MAIL_PORT'))
	MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
	MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
	MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
	ADMINS = os.environ.get('ADMINS').split(',')

	LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
	ITEMS_PER_PAGE = 20
	LANGUAGES = ['en', 'es']