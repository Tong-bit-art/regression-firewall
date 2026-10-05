"""Minimal FastAPI app used by the Regression Firewall example.

Install deps:  pip install fastapi uvicorn
Run:           regression-firewall baseline   (the tool starts/stops the app)
"""

from fastapi import FastAPI, HTTPException

app = FastAPI()

_USERS = {42: {"id": 42, "username": "alice", "email": "alice@example.com"}}
_CREDENTIALS = {"alice": "wonderland"}


@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.post("/login")
def login(payload: dict):
    username = payload.get("username")
    password = payload.get("password")
    if _CREDENTIALS.get(username) != password:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"status": "logged_in"}
