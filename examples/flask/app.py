"""Minimal Flask app used by the Regression Firewall example.

Install deps:  pip install flask
"""

from flask import Flask, jsonify, request

app = Flask(__name__)

_USERS = {42: {"id": 42, "username": "alice", "email": "alice@example.com"}}
_CREDENTIALS = {"alice": "wonderland"}


@app.get("/users/<int:user_id>")
def get_user(user_id):
    user = _USERS.get(user_id)
    if user is None:
        return jsonify(error="user not found"), 404
    return jsonify(user)


@app.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    password = payload.get("password")
    if _CREDENTIALS.get(username) != password:
        return jsonify(error="invalid credentials"), 401
    return jsonify(status="logged_in")
