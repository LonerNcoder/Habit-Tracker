
from typing import OrderedDict
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

db = SQLAlchemy()

from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required
from flask_security.models import fsqla_v2 as fsqla

fsqla.FsModels.set_db_info(db)

# roles_users = db.Table('roles_users',
#         db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
#         db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class Role(db.Model, fsqla.FsRoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, fsqla.FsUserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    confirmed_at = db.Column(db.DateTime(),nullable=True)
    trackers = db.relationship("Tracker", backref="user",cascade="all, delete-orphan", order_by="Tracker.updated_at")
    stats = db.relationship("MonthlyTracker", backref="user",cascade="all, delete-orphan")
    NotificationType = db.relationship("NotificationType", backref="user",cascade="all, delete-orphan")
    MonthlyReportType = db.relationship("MonthlyReportType", backref="user",cascade="all, delete-orphan")
    # roles = db.relationship('Role', secondary=roles_users,
    #                         backref=db.backref('users', lazy='dynamic'))


    
class Tracker(db.Model):
    __tablename__ = 'tracker'
    tracker_id = db.Column(db.Integer, primary_key=True)
    tracker_name = db.Column(db.String(255), nullable=False)
    tracker_desc = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(), nullable=False)
    updated_at = db.Column(db.DateTime(), nullable=True)
    tracker_type = db.Column(db.String(255), nullable=False)
    tracker_what_to_track = db.Column(db.String(255), nullable=True)
    tracker_unit = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'))
    logs = db.relationship("Logs", backref="tracker",cascade="all, delete-orphan", order_by="Logs.log_created")

    def __init__(self,tracker_name,tracker_type,tracker_desc,created_at,updated_at,user_id):
        self.tracker_name = tracker_name
        self.tracker_type = tracker_type
        self.tracker_desc = tracker_desc
        self.created_at = created_at
        self.updated_at = updated_at
        self.user_id = user_id


class Logs(db.Model):
    __tablename__ = 'logs'
    log_id = db.Column(db.Integer, primary_key=True)
    tracker_id = db.Column(db.Integer, db.ForeignKey('tracker.tracker_id', ondelete='CASCADE'))
    log_value = db.Column(db.String(255), nullable=False)
    log_desc = db.Column(db.String(255), nullable=True)
    event_reminder_msg = db.Column(db.String(255), nullable=True)
    event_date = db.Column(db.DateTime(), nullable=True)
    emotion = db.Column(db.String(255), nullable=True)
    log_created = db.Column(db.DateTime(), nullable=True)
    log_updated = db.Column(db.DateTime(), nullable=False)



class MonthlyTracker(db.Model):
    __tablename__ = 'monthly_tracker'
    id = db.Column(db.Integer,primary_key=True)
    total_trackers = db.Column(db.Integer,nullable=False)
    total_logs = db.Column(db.Integer,nullable=False)
    most_used_tracker = db.Column(db.String(255),nullable=True)
    frequent_emotional_state = db.Column(db.String(255),nullable=True)
    logs_created_this_month = db.Column(db.Integer,nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'))
    logged_in = db.Column(db.Integer, nullable=True)

class NotificationType(db.Model):
    __tablename__ = 'notification_type'
    id = db.Column(db.Integer,primary_key=True,autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'))
    type = db.Column(db.String(255),nullable=False)

class MonthlyReportType(db.Model):
    __tablename__ = 'monthly_report_type'
    id = db.Column(db.Integer,primary_key=True,autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete='CASCADE'))
    type = db.Column(db.String(255),nullable=False)

user_datastore = SQLAlchemyUserDatastore(db, User, Role)



