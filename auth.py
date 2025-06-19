from jose import jwt, JWTError
from passlib.hash import bcrypt
from models import User
from sqlalchemy.orm import Session
from fastapi import Request
from datetime import datetime, timedelta

SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

def register_user(db: Session, username: str, password: str):
    if db.query(User).filter(User.username == username).first():
        return "Имя занято"
    user = User(username=username, hashed_password=bcrypt.hash(password))
    db.add(user)
    db.commit()

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.verify(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + expires_delta})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        return db.query(User).filter(User.username == username).first()
    except JWTError:
        return None
