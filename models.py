from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from passlib.hash import bcrypt
from datetime import datetime

DATABASE_URL = "sqlite:///./users.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    conversions = relationship("Conversion", back_populates="user")

class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    file_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="conversions")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
