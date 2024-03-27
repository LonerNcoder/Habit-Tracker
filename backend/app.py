import os
from celery.schedules import crontab
from datetime import datetime, timedelta
from turtle import back, delay, up
from flask import Flask, request, jsonify, url_for, session, make_response
from flask_caching import Cache
from flask_mail import Mail,Message
from flask_login import current_user, logout_user
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import json
from flask_bcrypt import Bcrypt
from flask_session import Session
# from application import config
from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin, auth_required,auth_token_required
from application.models import *
from application import workers
# import workers
from application.config import Config
from application import tasks
from celery.result import AsyncResult
##importing blueprints
from flask import Blueprint, send_file
from application.tasks import task_path
## for reports
from weasyprint import HTML
from jinja2 import Template
import time
import random
import csv
import shutil

from zipfile import ZipFile
import pandas as pd
import numpy as np

##for api documentation purposes
from flask_selfdoc import Autodoc




#initiating variables


app = None
bcrypt = Bcrypt()
cache = Cache()
email = Mail()


basedir = os.path.dirname(__file__)
report_template = "report\\template\\reportTemplate.html"
report_mail_template = "report\\template\\reportMailTemplate.html"
report_template_path = os.path.join(basedir, report_template)
report_mail_template_path = os.path.join(basedir, report_mail_template)


def create_app():
    app = Flask(__name__,template_folder="templates")
    
    app.config.from_object(Config)
    app.config.update(
        SESSION_COOKIE_SECURE = True,
        REMEMBER_COOKIE_HTTPONLY = True,
        SESSION_COOKIE_HTTPONLY = True,
        SESSION_COOKIE_SAMESITE = "None",
        # REMEMBER_COOKIE_SAMESITE = "None",
        # REMEMBER_COOKIE_SECURE = True
    )



    app.config["SESSION_PERMANENT"] = True
    app.config["SESSION_TYPE"] = "redis"
    db.init_app(app)
    Session(app)
    app.app_context().push()

    cache.init_app(app)
    app.app_context().push()
    
    CORS(app,resources={r"/*": {"origins": "*"}},expose_headers=["content-type", "X-CSRFToken","X-CSRF-Token"],supports_credentials=True)
    CSRFProtect(app)

    app.app_context().push()
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_datastore)
    bcrypt.init_app(app)
    app.app_context().push()

    app.config.update({
        "MAIL_SERVER":'smtp.gmail.com',
        "MAIL_PORT" : 465,
        "MAIL_USERNAME" : 'purgusarkar@gmail.com',
        "MAIL_PASSWORD" : os.getenv('MAIL_PASSWORD'),
        "MAIL_USE_TLS" : False,
        "MAIL_USE_SSL" : True,
    })

    email.init_app(app)
    app.app_context().push()
    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1000 * 1000 * 100
    app.app_context().push()
    celery = workers.celery

    # Update with configuration
    celery.conf.update(
        broker_url = app.config["CELERY_BROKER_URL"],
        result_backend = app.config["CELERY_RESULT_BACKEND"],
        result_expires=3600,
        enable_utc = False,
        timezone = "Asia/Calcutta"
    )
    celery.Task = workers.ContextTask
    app.app_context().push()
    return app,celery,user_datastore,security



app,celery,user_datastore,security = create_app()
auto = Autodoc(app)

s = URLSafeTimedSerializer("thisissecretkey")
salt = os.getenv("SALT")


## starting periodic tasks

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(minute=0,hour=22,day_of_month='*/30'), send_monthly_report.s(), name='send monthly report every 30 Days at 10pm')
    sender.add_periodic_task(crontab(minute=0,hour=23,day_of_month='*/2'),garbage_collection.s(), name='garbage collection every 2 days')
    sender.add_periodic_task(crontab(minute=0,hour=20,day_of_month='*/30'), setup_for_monthly_report.s(), name='start setting up monyhly report every 30 Days at 9 pm')
    sender.add_periodic_task(crontab(minute=0,hour=6), sending_reminder_to_the_user_who_has_set_any_reminder_msg.s(), name='task reminder')
    sender.add_periodic_task(crontab(minute=0,hour=20),sending_notification_daily.s(),name="send notification daily at 8 pm")
    sender.add_periodic_task(crontab(minute=0,hour=20,day_of_month='*/7'),sending_notification_weekly.s(),name="send notification weekly at 8pm")
    # sender.add_periodic_task(100, sending_reminder_to_the_user_who_has_set_any_reminder_msg.s(), name='start')
    # sender.add_periodic_task(50, setup_for_monthly_report.s(), name='send monthly x')
    # sender.add_periodic_task(600, send_monthly_report.s(), name='send monthly xxx')
    # sender.add_periodic_task(20, garbage_collection.s(), name='send monthly xxxxx')


@celery.task
def setup_for_monthly_report():#resets the monthly tracker database
    users = User.query.all()
    for i in users:
        tasks.background_monthly_tracker_setup.delay(i.id)
    print("done")

@celery.task
def garbage_collection():
    dist = os.path.join(basedir,"report\\dist")
    zipfiles = os.path.join(basedir,"zipfiles")
    now = time.time()
    for f in os.listdir(dist):
        f = os.path.join(dist, f)
        if os.stat(f).st_mtime < now - 1 * 86400:
            if os.path.isdir(f):
                shutil.rmtree(f)
            if os.path.isfile(f):
                os.remove(f)
    for z in os.listdir(zipfiles):
        zipname = os.path.join(zipfiles, z)
        if os.stat(zipname).st_mtime < now - 1 * 86400:
            os.remove(zipname)
    print("COMPLETED GARBAGE COLLECTION")




def render_file(path, data):
    with open(path) as f:
        template = Template(f.read())
        return template.render(data=data)

def render_reminder_template(path, username,message):
    with open(path) as f:
        template = Template(f.read())
        return template.render(username=username,message=message)


@celery.task
def send_monthly_report():
    with email.connect() as conn:
        users = User.query.all()
        for user in users:
            username =  user.username
            dist = f"report\\dist\\{username}{datetime.now().timestamp()}_report.pdf"
            target_path = os.path.join(basedir, dist)

            logs_created_this_month = user.stats[0].logs_created_this_month
            data = {"username": username,
                    "total_trackers" : user.stats[0].total_trackers,
                    "log_created_this_month": logs_created_this_month,
                    "total_logs" : user.stats[0].total_logs,
                    "frequent_emotional_state" : user.stats[0].frequent_emotional_state,
                    "total_logged_in":user.login_count
                    }
            html_message = render_file(report_template_path,data=data)
            html = HTML(string=html_message)
            pdf_data=html.write_pdf()

            if user.confirmed_at is not None:
                message = "This is your monthly Report"
                subject = f"Hello {username},Its your HabbitBOT from Habbit Experience"
                msg = Message(recipients=[user.email],body=message,subject=subject,sender=app.config["MAIL_SENDER"])
                if user.MonthlyReportType[0].type == "PDF":
                    msg.attach(filename="report.pdf",disposition="attachment",content_type="application/pdf",data=pdf_data)
                else:
                    html_message = render_file(report_mail_template_path,data=data)
                    msg.html = html_message
                conn.send(msg)
        print("Monthly report sent")



@celery.task
def sending_reminder_to_the_user_who_has_set_any_reminder_msg():
    with email.connect() as conn:
        users = User.query.all()
        dist = "report\\template\\reminder_msg_template.txt"
        path = os.path.join(basedir, dist)
        today = datetime.now().date()

        for user in users:
            message_list = []
            if user.confirmed_at is not None and user.trackers:
                trackers = user.trackers
                for tracker in trackers:
                    if tracker.logs:
                        logs = tracker.logs
                        message_obj = []
                        for log in logs:
                            if log.event_date:
                                if log.event_date.date() == today:
                                    obj = {"msg": log.event_reminder_msg, "at": log.event_date.strftime("%H:%M %p")}
                                    message_list.append(obj)
                        
            if message_list:
                message = render_reminder_template(path, user.username, message_list)
                subject = "Your Task Reminder"
                msg = Message(recipients=[user.email],body=message,subject=subject,sender=app.config["MAIL_SENDER"])
                conn.send(msg)

@celery.task
def sending_notification_daily():
    today = datetime.now().date()
    with email.connect() as conn:
        users = User.query.all()
        for user in users:
            if user.last_login_at is not None and user.last_login_at.date() != today:
                if user.confirmed_at is not None and user.NotificationType[0].type == "Daily":
                    message=f"Hi {user.username} your Trackers are waiting for you !"
                    subject = "Daily Notification"
                    msg = Message(recipients=[user.email],body=message,subject=subject,sender=app.config["MAIL_SENDER"])
                    conn.send(msg)


@celery.task
def sending_notification_weekly():
    with email.connect() as conn:
        users = User.query.all()
        for user in users:
            if user.confirmed_at is not None and user.NotificationType[0].type == "Weekly":
                message=f"Hi {user.username} it's been a week, your Trackers are waiting for you !"
                subject = "Weekly Notification"
                msg = Message(recipients=[user.email],body=message,subject=subject,sender=app.config["MAIL_SENDER"])
                conn.send(msg)


###--------API ROUTES--------------------------------

@app.before_first_request
def set():
    db.create_all()
    return

@app.before_request
def setSession():
    session.permanent_session = True
    app.permanent_session_lifetime = timedelta(minutes=30)
    session.modified = True
    
    
@auto.doc()
@app.route("/")
def greet():
    return "welcome to Habbit Experience open source api, go to /login to access your account"


@auto.doc()
@app.route('/create_user', methods=['POST'])
def post():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    user_email = user_datastore.find_user(email=email)
    user = user_datastore.find_user(username=username)
    if user is not None:
        return jsonify({'msg': 'Username already exists'}),200
    if user_email is not None:
        return jsonify({'msg': 'Email already exists'}),200
    userc = user_datastore.create_user(username=username,email=email,password=password)

    #whenever a new user regestered, api  creates assign a default value to Notification types

    a = NotificationType(type="Daily")
    userc.NotificationType.append(a)
    b = MonthlyReportType(type="HTML")
    userc.MonthlyReportType.append(b)
    db.session.commit()
    return {'msg': 'OK'}, 200

# POST API to login user with param email and password
@auto.doc()
@app.route('/login', methods=['POST'])
def login():
    password = request.json.get("password")
    email = request.json.get("email")

    user = user_datastore.find_user(email=email)
    if not user or not bcrypt.check_password_hash(user.password,password):
        return jsonify("Wrong username or password"), 400

    return jsonify({'user': user })

# POST API to logout user
@auto.doc()
@app.route('/logout',methods=['POST'])
@auth_required()
def logout():
    resp = make_response(jsonify({'msg': 'OK'}))
    resp.set_cookie('session', '', expires=0)
    resp.set_cookie('remember_token', '', expires=0)
    logout_user()
    return resp



# GET API to get user details
@auto.doc()
@app.route('/user_details',methods=['GET'])
@auth_required()
@cache.cached(timeout=30)
def user_details():
    return jsonify(
        {
            'username': current_user.username,
            "unique_id": current_user.fs_uniquifier,
            'email': current_user.email,
            'last_login_at': current_user.last_login_at,
            'created_at': current_user.create_datetime,
            'confirmed_at': current_user.confirmed_at,
            'notification_type': current_user.NotificationType[0].type,
            'monthly_report_type': current_user.MonthlyReportType[0].type

        }
    ), 200

# DELETE API to delete user account
@auto.doc()
@app.route("/delete_user", methods=["DELETE"])
@auth_required()
def deleteUser():
    try:
        User.query.filter_by(id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success' : True}), 200
    except Exception as e:
        return jsonify({'success' : False}), 400

# POST API to verify email addresses
@auto.doc()
@app.route("/confirm_email", methods=["POST"])
@auth_required()
def verify_email():
    if current_user.confirmed_at is not None:
        return jsonify({"msg": "you are already verified"}),200
    mail = request.json.get("email")
    token = s.dumps(mail, salt=salt)
    msg = Message('Confirm Email', sender=app.config["MAIL_SENDER"], recipients=[mail])
    link = url_for("confirm_email", token=token,user_id=current_user.id, _external=True)
    msg.body = f"Your confirmation link is {link}"
    try:
        email.send(msg)
    except Exception as e:
        return "failed", 400
    return jsonify({"msg": "confirmation link has been sent, please check your email"}),200


@auto.doc()
@app.route("/confirm_email/<token>/<int:user_id>")
def confirm_email(token,user_id):
    try:
        email = s.loads(token, salt=salt, max_age=3600)
    except SignatureExpired:
        return "<h1>The Token is Expired</h1>"
    current_user = user_datastore.find_user(id=user_id)
    current_user.confirmed_at = datetime.now()
    current_user.verified = True
    db.session.commit()
    return """
    <h1>Thank You for Confirming Your Email<h1><br />
    <p>go back to your app, you can access your notification functions</p>
    """, 200

# GET API to get user verification status
@auto.doc()
@app.route("/user/verification_status", methods=["GET"])
@auth_required()
def verify_status():
    isverified = current_user.confirmed_at
    return ("True", 200) if isverified is not None else ("False", 400)



##----------TRACKERS API----------------------------------------------------------------

# GET API to get all trackers availabe to the user
@auto.doc()
@app.route("/user/trackers", methods=["GET"])
@auth_required("session","token")
@cache.cached(timeout=5)
def getallTrackers():
    user_id = current_user.id
    try:
        trackerObj = []
        trackers = current_user.trackers
        reversed_trackers = trackers[::-1]
        for i in reversed_trackers:
            number_of_logs = len(i.logs) if i.logs else 0
            obj = {"tracker_name": i.tracker_name, "tracker_type": i.tracker_type, "tracker_id": i.tracker_id, "tracker_desc": i.tracker_desc, "created_at": i.created_at, "updated_at": i.updated_at, "number_of_logs": number_of_logs}
            if i.tracker_type == "numerical":
                obj["tracker_unit"] = i.tracker_unit
                obj["tracker_what_to_track"] = i.tracker_what_to_track
            trackerObj.append(obj)
        return jsonify(trackerObj)
    except Exception as e:
        print(e)
        return jsonify({'msg': 'No Tracker available'}), 400

# GET APi to get a single tracker with param tracker id
@auto.doc()
@app.route("/user/trackers/<int:id>", methods=["GET"])
@cache.memoize(timeout=10)
@auth_required()
def getSingleTracker(id):
    try:
        tracker = Tracker.query.filter_by(tracker_id=int(id)).first()
        obj = {"tracker_name": tracker.tracker_name, "tracker_type": tracker.tracker_type, "tracker_id": tracker.tracker_id, "tracker_desc": tracker.tracker_desc, "created_at": tracker.created_at, "updated_at": tracker.updated_at}
        if tracker.tracker_type == "numerical":
            obj["tracker_unit"] = tracker.tracker_unit
            obj["tracker_what_to_track"] = tracker.tracker_what_to_track
        return jsonify(obj),200
    except Exception as e:

        return jsonify({'msg': 'No Tracker available'}), 400


#POST to create a new Tracker with param tracker obj with tracker_name,tracker_type,tracker_desc
@auto.doc()
@app.route("/user/trackers", methods=["POST"])
@auth_required()
def createTracker():

    try:
        user_id = current_user.id
        TrackerObj = request.json.get('tracker')
        created_at=datetime.now()
        updated_at = created_at
        if current_user.trackers:
            lists = [i.tracker_name for i in current_user.trackers]
            if lists.count(TrackerObj['tracker_name']) > 0:
                return jsonify({"msg": "Tracker already exists"}), 201

        tracker = Tracker(tracker_name=TrackerObj['tracker_name'], tracker_type=TrackerObj['tracker_type'], tracker_desc=TrackerObj['tracker_desc'], created_at=created_at,updated_at=updated_at,user_id=user_id)
        if TrackerObj['tracker_type'] == "numerical":
            tracker.tracker_unit = TrackerObj['tracker_unit']
            tracker.tracker_what_to_track = TrackerObj["tracker_what_to_track"]
        db.session.add(tracker)
        db.session.commit()


        return jsonify({'msg' : 'OK'}), 200
    except Exception as e:
        print(e)
        return jsonify({'msg' : 'ERROR'}), 400
# PUT API to update a tracker with params tracker_id,and tracker object
@auto.doc()
@app.route("/user/trackers", methods=["PUT"])
@auth_required()
def updateTrackers():
    try:
        user_id = current_user.id
        tracker_id = int(request.json.get('tracker_id'))
        TrackerObj = request.json.get('tracker')

        tracker = Tracker.query.filter_by(user_id=user_id,tracker_id=tracker_id).first()

        tracker.tracker_name=TrackerObj['tracker_name']
        # tracker.tracker_type=TrackerObj['tracker_type']
        tracker.tracker_desc=TrackerObj['tracker_desc']
        tracker.updated_at = datetime.now()
    #tracker.tracker_created=str(date.today())
        db.session.commit()
        return jsonify({'msg' : 'OK'}) , 200
    except Exception as e:
        return jsonify({'msg' : 'ERROR'}) , 400

#DELETE API to delete a perticular tracker with param tracker_id
@auto.doc()
@app.route("/user/trackers/<int:tracker_id>", methods=["DELETE"])
@auth_required()
def deleteTrackers(tracker_id):
    
    try:
        tracker_id = int(tracker_id)

        tracker = Tracker.query.filter_by(tracker_id=tracker_id).first()
        db.session.delete(tracker)
        db.session.commit()
        return jsonify({'msg' : 'OK'} ), 200

    except Exception as e:
        return jsonify({'msg' : 'ERROR'}) , 400


##----------------LOGS----------------------------------------------------------------  

@auto.doc()
@app.route("/user/trackers/<int:id>/logs", methods=["GET"])
@auth_required()
def get_logs(id):
    try:
        user_id = current_user.id
        tracker_id = int(id)
        tracker = Tracker.query.filter_by(user_id=user_id, tracker_id=tracker_id).first()
        all_logs = tracker.logs
        # all_logs = all_logs[::-1]
        logObj = []
        for i in all_logs:
            # if i.event_reminder_msg is not None:
            #     event_reminder_msg = i.event_reminder_msg
            #     event_date = i.event_date
            # else:
            #     event_reminder_msg = ""
            #     event_date = ""
            obj = {
                "log_id": i.log_id,
                "log_value": i.log_value,
                "log_desc": i.log_desc if i.log_desc else "",
                "log_created": i.log_created,
                "log_updated": i.log_updated,
                "event_reminder_msg": i.event_reminder_msg if i.event_reminder_msg else "",
                "event_date": i.event_date if i.event_date else "",
                "emotion": i.emotion,
            }
            logObj.append(obj)
        return (jsonify(logObj), 200) if logObj else (jsonify({'msg': 'no logs available'}), 201)
    except Exception as e:
        return jsonify({'msg': 'no logs available'}), 400



@auto.doc()
@app.route("/user/trackers/<int:id>/logs", methods=["POST"])
@auth_required()
def addLogs(id):
    try:
        tracker_id = int(id)
        logData = request.json.get('logData')
        log_value = logData['log_value'].strip()
        log_desc = logData['log_desc'].strip()
        
        event_date = logData['event_date']
        if event_date != "":
            event_date = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        emotion = logData['emotion']
    
        log_created = datetime.now()
        log_updated = log_created 
        event_reminder_msg = logData['event_reminder_msg']
        if " ".join(event_reminder_msg.split()) == "":
            log = Logs(tracker_id=tracker_id,log_value=log_value,log_desc=log_desc,log_created=log_created,log_updated=log_updated,emotion=emotion)
        else:
            log = Logs(tracker_id=tracker_id,log_value=log_value,log_desc=log_desc,log_created=log_created,log_updated=log_updated,event_date=event_date,emotion=emotion)
            log.event_reminder_msg = logData['event_reminder_msg']
        Tracker.query.filter_by(tracker_id=tracker_id).first().updated_at = log_updated
        db.session.add(log)
        db.session.commit()
        return jsonify({'msg' : "Success"}), 200
    except Exception as e:
        return jsonify({'msg' : "an error occurred"}),


@auto.doc()
@app.route("/user/trackers/<int:id>/logs", methods=["PUT"])
@auth_required()
def updateLogs(id):

    try:
        tracker_id = int(id)
        updatedLog = request.json.get('updatedLog')
        log_id = int(updatedLog['log_id'])
        log_value = updatedLog['log_value'].strip()
        log_desc = updatedLog['log_desc'].strip()
        event_reminder_msg =  updatedLog['event_reminder_msg']
        event_date = updatedLog['event_date']
        emotion = updatedLog['emotion']
        if event_date != "":
            event_date = datetime.strptime(event_date, "%Y-%m-%dT%H:%M")
        log_updated = datetime.now()

        log = Logs.query.filter_by(log_id=log_id).first()
        log.log_value = log_value
        log.log_desc = log_desc

        log.log_updated = log_updated

        if event_date != "":
            log.event_date = event_date
            log.event_reminder_msg = event_reminder_msg
        log.emotion = emotion

        Tracker.query.filter_by(tracker_id=tracker_id).first().updated_at = log_updated
        db.session.commit()
        return jsonify({'msg': "success"}), 200
    except Exception as e:
        print(e)
        return jsonify({'msg': "an error occurred"}), 400


@auto.doc()
@app.route("/user/trackers/<int:id>/logs/<int:log_id>/delete", methods=["DELETE"])
@auth_required()
def deleteLog(id,log_id):
    try:
        tracker_id=int(id)
        log_id = int(log_id)
        Logs.query.filter_by(log_id=log_id).delete()
        Tracker.query.filter_by(tracker_id=tracker_id).first().updated_at = datetime.now()
        db.session.commit()
        return jsonify({"msg": "success"}), 200
    except Exception as e:
        return jsonify({"msg": "failed"}), 400


####------------------------NOTIFICATION AND MONTHLY REPORT SETTINGS------------------------

@auto.doc()
@app.route("/notification_type",methods=["POST"])
@auth_required()
def daily_notification_type():
    
    try:
        daily_notification_type = request.json.get("notification-type")
        current_user.NotificationType[0].type = daily_notification_type
        db.session.commit()
        return jsonify({'msg': 'OK'}), 200
    except Exception as e:
        return jsonify({'msg': 'ERROR'}), 400

#####################-----CHANGE Monthly Report Type-------########################################################################


@auto.doc()
@app.route("/monthly_report_type", methods=["POST"])
@auth_required()
def monthly_report_type():
    try:
        monthly_report_type = request.json.get("monthly-report-type")
        current_user.MonthlyReportType[0].type = monthly_report_type
        db.session.commit()
        return jsonify({'msg': 'OK'}), 200
    except Exception as e:
        return jsonify({'msg': 'ERROR'}), 400




####################----EXPORTING ROUTES---------------------####################################################


@auto.doc()
@app.route("/tracker_csv_token",methods=["GET"])
@auth_required()
# @cache.cached(timeout=50,key_prefix="tracker_csv_token")
def send_tracker_csv_token():
    user_name = current_user.username
    user_id = current_user.id
    dist_path = "report\\dist"
    dist = os.path.join(basedir,dist_path)

    filename = f"Log_Report{random.randint(1,9999999)}{datetime.now().timestamp()}{user_name}.csv"
    filepath = os.path.join(dist,filename)
    if current_user.trackers:
        tasks.generate_trackers_csv.delay(user_id,filepath)
        return jsonify({"csv_token": f"{filepath}"}), 200
    else:
        return jsonify({"msg": "you have no trackers available"}),400



@auto.doc()
@app.route("/tracker_csv_download",methods=["POST"])
@auth_required()
# @cache.cached(timeout=50,key_prefix="tracker_csv_download")
def send_tracker_csv():
    filename = request.json.get("csv_token")
    try:
        return send_file(filename, as_attachment=True, download_name="Trackers.csv")
    except Exception as e:
        print(e)
        return jsonify({"msg": "corrupted token to download, request for token again"}),400


@auto.doc()
@app.route("/tracker_logs_zip_token")
@auth_required()
# @cache.cached(timeout=50)
def zipfile():
    user_id = current_user.id
    dist = dist = os.path.dirname(__file__)
    dist = os.path.join(dist, "zipfiles")
    path = f"{current_user.username}-{datetime.now().timestamp()}"
    zip_file_name = os.path.join(dist,path)
    if current_user.trackers:
        tasks.background_job_for_trackers_logs_zip.delay(user_id, path)
        zip_file_token = zip_file_name
        return jsonify({"zip_token":f"{zip_file_token}.zip"}),200
    else:
        return jsonify({"msg": "you have no trackers available"}),400

@auto.doc()
@app.route("/tracker_logs_zip_download",methods=["POST"])
@auth_required()
# @cache.cached(timeout=50)
def send_log_zip():
    try:
        filename = request.json.get("zip_token")
        return send_file(filename, as_attachment=True, download_name="Tracker-Logs.zip")
    except Exception as e:
        print(e)
        return jsonify({"msg": "corrupted token to download, request for tocken again"}),400


## everytime user changes password fs_uniquifier changes. so reload that uniquifier

@auto.doc()
@app.route("/reload_uniqfier", methods=["GET"])
@auth_required()
def reload_uniqfier():
    unique_id = current_user.fs_uniquifier
    return jsonify({"unique_id": unique_id}) , 200


# backup restore routes
 

@auto.doc()
@app.route("/backup", methods=["POST"])
@auth_required()
def backup():

    username = current_user.username
    user_id = current_user.id
    existed_trackers = [i.tracker_name for i in current_user.trackers]
    file = request.files["my-file"]
    filename = f"{username}-{file.filename}"
    path = os.path.join(basedir, f"uploads\\{filename}")
    file.save(path)
    tasks.background_job_for_restore.delay(filepath=path, user_id=user_id, existed_trackers=existed_trackers)

    return "Backup is under process please check your dashboard"


#API DOCUMENTATION ENDPOINTS

@auto.doc()
@app.route("/doc")
def document():
    return auto.html()



@app.route('/doc/json')
def public_doc_json():
    return jsonify(auto.generate())


######-------------------INITIALIZING--------------------################################################

if __name__ == '__main__':
    app.run(
        port=8080,
        debug=False,
    )