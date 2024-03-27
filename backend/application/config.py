import os
basedir = os.path.abspath(os.path.dirname(__file__))
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

os.environ.setdefault("FORKED_BY_MULTIPROCESSING", '1')
class Config():
    #cache
    CACHE_TYPE = 'simple'
    SECURITY_CHANGEABLE = True
    SECURITY_TRACKABLE = True
    SECURITY_POST_CHANGE_VIEW = "http://localhost:8081/"
    SECURITY_CSRF_PROTECT_MECHANISMS= ['session', 'token']
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT")
    SECURITY_PASSWORD_HASH = 'bcrypt'
    SECURITY_CSRF_COOKIE_NAME = 'XSRF-TOKEN'
    SECURITY_DEFAULT_REMEMBER_ME = True
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_HEADERS = ['X-CSRF-Token']
    SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS = True
    WTF_CSRF_CHECK_DEFAULT = False
    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # CELERY_BROKER_URL = "redis://localhost:9001/1"
    CELERY_BROKER_URL = "pyamqp://guest:guest@localhost:5672//"
    # CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/2"

    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = "sqlite:///db.sqlite3"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_RECOVERABLE = True

    DIST_DIR = os.path.join(basedir, "dist")

    MAIL_SENDER = "paragsarkar@gmail.com"
    ALLOWED_EXTENSIONS = {"zip","pdf","csv","txt"}



class LocalDevelopmentConfig(Config):
    SQLITE_DB_DIR = os.path.join(basedir, "../db_directory")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(SQLITE_DB_DIR, "db.sqlite3")
    DEBUG = True
    SECRET_KEY =  "ash ah secet"
    SECURITY_PASSWORD_HASH = "bcrypt"    
    SECURITY_PASSWORD_SALT = "really super secret"
    SECURITY_REGISTERABLE = True
    SECURITY_CONFIRMABLE = False
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_UNAUTHORIZED_VIEW = None
    WTF_CSRF_ENABLED = False
    CELERY_BROKER_URL = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/2"
    
