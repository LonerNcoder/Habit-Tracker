# MAD-2 PROJECT SUMMERY   
   
   This term we got an outstanding project to work on while upgrading the previous term project. And this is how i did it   

## Backend   
For the backend i used popular python library Flask to create a simple yet powerful API to handle frontend's requests.   
To integrate Flask-Security and Flask-Login i added two database models User and Roles, As it is not important for this app to have role based authorization system, I mainly focused on User models.It got Id as Primary key, and usual columns for user like Email, Password and Username, to check if the user's email is verified or not it also got an column called Confirmed_at which will store the datatime at which the user has been verified.   
```python3
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
```
As you can see it also got some relationship with other models, i'll talk about those in a moment.
   
      
To store user's created Tracker and their logs i also need two additional models, Tracker to store the tracker details and Logs to store the logs.   
Tracker model got usual columns such that, tracker_name,tracker_desc,tracker_type,created_at,updated_at,and tracker_id as primary key.   
User can choose two types of Tracker to add, one is ```note``` type for more descriptive information and ```numerical``` type for numerical values like daily expense, profit loss etc nad user will get different type of charts based on these which will enrich the user experience.  
That's why the Tracker model also get some nullable columns like ```what_to_track,tracker_unit```.what_to_track  column will store additional information about the numerical type tracker.

Each respective Tracker should have their one logs which will hold all the information user adds. So the Logs model has columns ```log_id,tracker_id(foreign key reference to Tracker),log_value,log_desc(description),event_reminder_msg(optional for a user if they want any alarm or not),event_date(date for alarm),emotion(to track the user's emotion everyday),log_created and log_updated```   

I also want to send user daily/weekly Notification and A report Monthly to implement those i also created two models called NotificationType,MonthlyReportType   

NotificationType model has only main columns, ```user_id and type ```, type column stores two types of string, "Daily" or "Weekly". and user_id stores the respective user's id as foreign key.

MonthlyReportType model has also same functionality and columns as NotificationType, but it's ```type``` column stores "PDF" or "HTML" string , as user can choose which format they want to receive report in mail.   

Every Month we want to send a beautiful  report to user via mail, and to store the data we created another model called ```MonthlyTracker```. in the backend we defined a calery periodic task which will start every 28 days at 8 PM and populate this table with ```total_trackers(total trackers created this month),total_logs,most_used_tracker,frequent_emotional_state,logs_created_this_month,logged_in(number of time user logged in),user_id```

Now that all the  models has been created lets define relationship between them. A user can have many trackers and a tracker can have many logs, so between user and tracker there is one-to many relationship and also ont-to many between tracker nad logs. a user canm have only a single type of Notification and Monthly report type, so there are one to one relationship between ```User-NotificationType``` and also ```User-MonthlyReportType```.
User has only one-to one relation with MonthlyTracker too.
   
In the above mentioned User Model you can clearly see the relationships.

### Exploring Flask Security   
Flask Security has a predefined SQLAlchemyUserDatastore which takes User and Roles models as input and adds extra featurs to the User Model. such as ```fs_uniquifier,login_count,login_ip,tracking login time,password hashing``` etc. Defining 
```python3
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
```
will do the trick.   

## Configuring Flask Security
Though i can create my own function and route to login and logout a user, Flask-Security provides countless features to secure our api as a profesonally build api. In this Project i only used it to Login,Logout,Changing Password,and checking Authentication.
```python3
from flask_security import Security
app = Flask(__name__)
Security(app,user_datastore)
```
it is so simple !
it also provides default rotes to login,logout,and change password, and it works like charm !.
To  workl with all these features you have to configure Flask and you can do this by 
```python3
app.config["SECRET_KEY"] = "this is secret key"
```
my config.py looks like this
```python3
class Config():
    CACHE_TYPE = 'simple'
    SECURITY_CSRF_PROTECT_MECHANISMS= ['session', 'token']
    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT")
    SECURITY_PASSWORD_HASH = 'bcrypt'
    SECURITY_CSRF_COOKIE_NAME = 'XSRF-TOKEN'
    CELERY_BROKER_URL = "pyamqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/2"
```
defined CACHE_TYPE to cache responses of the routes. and to setup celery task i also defined CELERY_BROKER_URL,CELERY_RESULT_BACKEND to to work with background tasks.   

I have secured my routes with token and session based Authentication system as you can see from the config.py.   
everytime a user is logged in and authenticated the server responds with a csrf_token and set cookie to client side. To secure the cookie and setting it up i have defined some additional conf.
```python3
        SESSION_COOKIE_SECURE = True,
        REMEMBER_COOKIE_HTTPONLY = True,
        SESSION_COOKIE_HTTPONLY = True,
        SESSION_COOKIE_SAMESITE = "None",
        SESSION_PERMANENT= True
        SESSION_TYPE= "filesystem"
```
normally session cookies are cleared after a user exits the browser, to counter this i have set up SESSION_PERMANENT to True.   
For background tasks i used Rabbitmq as broker url and redis as result backend, and Flask celery library makes it easier.   

after setting up all these configuration a simple
```python3   
app.run()
```
works like charm!.





