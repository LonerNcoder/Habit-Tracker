import os
from application.workers import celery
from application.models import db
from .models import *
from datetime import datetime
from flask import current_app as app
from flask import Blueprint


task_path = Blueprint("task_path", __name__)


## for asynchronous background tasks

@celery.task
def background_monthly_tracker_setup(id):
    user_id = id
    current_user = User.query.filter_by(id=user_id).first()
    print(current_user)
    emotional_state = {}
    frequent_used_tracker = {}
    trackers = current_user.trackers
    total_logs = sum(len(i.logs) for i in trackers)
    if (current_user.stats):
        print("true")
    for i in trackers:
        for j in i.logs:
            try:
                emotional_state[j.emotion] += 1
            except KeyError as e:
                emotional_state[j.emotion] = 1
        frequent_used_tracker[i.tracker_name] = len(i.logs)
    total_trackers = len(trackers)
    most_used_tracker = "None"
    frequent_emotional_state = "None"
    max_tracker = 0
    max_emotion=0
    for v in emotional_state.values():
        max_emotion = max(v,max_emotion)
    for v in frequent_used_tracker.values():
        max_tracker = max(v,max_tracker)
    for k in emotional_state.keys():
        if emotional_state[k] == max_emotion:
            frequent_emotional_state = k
    for k in frequent_used_tracker.keys():
        if frequent_used_tracker[k] == max_tracker:
            most_used_tracker = k
    if current_user.stats:
        for i in current_user.stats:
            i.total_trackers=total_trackers
            temp = i.total_logs
            temp2 = i.logged_in
            i.total_logs=total_logs
            i.most_used_tracker=most_used_tracker
            i.frequent_emotional_state=frequent_emotional_state
            i.logs_created_this_month= total_logs - temp
            i.logged_in = current_user.stats[0].logged_in - temp2
            db.session.commit()
        return "success"
    log_created_this_month = total_logs
    most_use_tracker = most_used_tracker
    frequent_emo_state=frequent_emotional_state
    monthly_tracker = MonthlyTracker(user_id=user_id,
    total_trackers=total_trackers,total_logs=total_logs,
    most_used_tracker=most_use_tracker,frequent_emotional_state=frequent_emo_state,
    logs_created_this_month=log_created_this_month)
    monthly_tracker.logged_in = current_user.login_count if current_user.login_count else 0
    db.session.add(monthly_tracker)
    db.session.commit()
    return "success"

import shutil
import csv
from flask import send_file
basedir = os.path.abspath(os.path.dirname(__file__))
basedir = os.path.dirname(basedir)

@celery.task
def generate_trackers_csv(user_id,filepath):
    user = User.query.filter_by(id=user_id).first()
    trackers = user.trackers
    with open(filepath, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(["Tracker Name", "Tracker Description", "Type","What To Track", "Tracker Unit", "Created At", "Last Updated At"])
        for tracker in trackers:
            unit = tracker.tracker_unit if tracker.tracker_unit is not None else "NULL"
            what_to_track = tracker.tracker_what_to_track if tracker.tracker_what_to_track is not None else "NULL"
            writer.writerow([tracker.tracker_name, tracker.tracker_desc, tracker.tracker_type, tracker.tracker_what_to_track, tracker.tracker_unit, tracker.created_at, tracker.updated_at])
        f.close()
    print("DONE CREATING CSV FILE")

@celery.task
def background_job_for_trackers_logs_zip(user_id, path):
    user = User.query.filter_by(id=user_id).first()
    trackers = user.trackers
    dist_path = f"report\\dist\\{user.username}"
    dist = os.path.join(basedir, dist_path)
    isExists = os.path.isdir(dist)
    if os.path.exists(dist) and isExists:
        shutil.rmtree(dist)
        #delete previous file and create file again
        os.mkdir(dist)
    else:
        os.mkdir(dist)
    for tracker in trackers:
        filename = tracker.tracker_name
        filepath = os.path.join(dist, filename)
        os.mkdir(filepath)
        tracker_csv = f"{filename}.csv"
        tracker_csv_path = os.path.join(filepath, tracker_csv)
        
        unit = tracker.tracker_unit if tracker.tracker_unit is not None else "NULL"
        what_to_track = tracker.tracker_what_to_track if tracker.tracker_what_to_track is not None else "NULL"

        with open(tracker_csv_path, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(["Tracker Name", "Tracker Description", "Type", "What to Track", "Tracker Unit", "Created At", "Last Updated At"])
            writer.writerow([tracker.tracker_name, tracker.tracker_desc, tracker.tracker_type, tracker.tracker_what_to_track, tracker.tracker_unit, tracker.created_at, tracker.updated_at])
            f.close()
            log_csv_path = os.path.join(filepath, "logs.csv")
            logs = tracker.logs
            with open(log_csv_path, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(["log_value", "log Description", "event_reminder_msg", "event_date", "emotion", "Created At", "Last Updated At"])
                for log in logs:
                    if log.event_reminder_msg is not None:
                        event_reminder_msg = log.event_reminder_msg
                        event_date = log.event_date
                    else:
                        event_reminder_msg = "NULL"
                        event_date = "NULL"
                    writer.writerow([log.log_value, log.log_desc, log.event_reminder_msg, log.event_date, log.emotion, log.log_created, log.log_updated])
                f.close()
    zip_file_name = path

    zip_dist = os.path.join(basedir, "zipfiles")
    zip_file_name = os.path.join(zip_dist, zip_file_name)
    shutil.make_archive(base_name=zip_file_name,
                            root_dir=dist_path, format="zip")
    print("TRACKER LOG CREATED")



from zipfile import ZipFile
import pandas as pd
import numpy as np
import random

@celery.task
def background_job_for_restore(filepath,user_id,existed_trackers):
    existed_trackers = existed_trackers
    user_id = user_id
    path=filepath
    try:
        with ZipFile(path, 'r') as zip:
            path_to_extract = path.split(".")[0]
            zip.extractall(path_to_extract)

            for file in os.listdir(path_to_extract):
                f = os.path.join(path_to_extract, file)
                t_name=file
                if (file in existed_trackers):
                    t_name = f"{file}{random.randint(0, 100)}"
                restored_tracker = Tracker(tracker_name=t_name,tracker_type="default",tracker_desc="default",created_at=datetime.now(),updated_at=datetime.now(),user_id=user_id)
                for cssv in os.listdir(f):
                    csv_to_read = os.path.join(f,cssv)
                    data = pd.read_csv(csv_to_read)
                    print(cssv)
                    if cssv != "logs.csv":
                        tracker_desc = data["Tracker Description"][0]
                        tracker_type = data["Type"][0]
                        what_to_track = data["What to Track"][0]
                        tracker_unit = data["Tracker Unit"][0]
                        created_at = datetime.strptime(data["Created At"][0], "%Y-%m-%d %H:%M:%S.%f")
                        updated_at = datetime.now()

                        restored_tracker.tracker_type = tracker_type
                        restored_tracker.created_at = created_at
                        restored_tracker.updated_at = updated_at
                        restored_tracker.tracker_desc = tracker_desc

                        restored_tracker.tracker_what_to_track = what_to_track
                        restored_tracker.tracker_unit = tracker_unit

                    else:
                        log_value = data["log_value"]
                        if len(log_value) > 0:
                            for i in range(len(log_value)):
                                value = str(data["log_value"][i])
                                # if tracker_type == "numerical":
                                #     value = int(value)
                                desc = data["log Description"][i]
                                event_msg = data["event_reminder_msg"][i]
                                event_date = data["event_date"][i]
                                emotion = data["emotion"][i]
                                created_at = datetime.strptime(data["Created At"][i], "%Y-%m-%d %H:%M:%S.%f")
                                updated_at = datetime.now()

                                log = Logs(log_value=value,log_desc=desc,emotion=emotion,log_created=created_at,log_updated=updated_at)

                                if not pd.isna(event_msg):
                                    event_date = datetime.strptime(event_date, "%Y-%m-%d %H:%M:%S")
                                    log.event_date = event_date
                                    log.event_reminder_msg = event_msg
                                restored_tracker.logs.append(log)
                try:
                    db.session.add(restored_tracker)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    db.session.commit()
        return "Restored"
    except Exception as e:
        print(e)
        return "Corrupted"


