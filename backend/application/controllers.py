# from flask import current_app as app
# from flask import Flask, request, jsonify
# from flask_login import current_user, logout_user
# from flask_cors import CORS
# from flask_wtf.csrf import CSRFProtect
# import json
# from flask_bcrypt import Bcrypt
# # from application import config
# from flask_security import auth_required
# from application.models import *





# @app.route('/')
# def show():
#     user = user_datastore.find_user(username='Parag')
#     user_datastore.set_token_uniquifier(user)
#     return {'id': user.id, 'token': user.fs_uniquifier}

# @app.route('/login', methods=['POST'])
# def login():
#     username = request.json.get("username", None)
#     password = request.json.get("password", None)
#     email = request.json.get("email", None)

#     user = user_datastore.find(username=username,email=email)
#     if not user or not bcrypt.check_password_hash(user.password,password):
#         return jsonify("Wrong username or password"), 401

#     # we are passing in the actual sqlalchemy user object here
#     access_token = user.fs_uniquifier
#     return {'user': user }, 200


# @app.route('/check',methods=['POST'])
# @auth_required()
# def check():
#     user = current_user
#     # user = user_datastore.find(fs_uniquifier=identity)
#     return f"hello {user.username} " if user else "bad token"

# @app.route('/logout', methods=['POST'])
# @auth_required()
# def logout():
#     logout_user()
#     return {'logged out': True}