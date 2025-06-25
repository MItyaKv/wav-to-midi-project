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

    @classmethod
    def create(cls, db: Session, username: str, password: str):
        """
        Создает нового пользователя и сохраняет его в базе данных.
        """
        hashed_password = bcrypt.hash(password)
        new_user = cls(username=username, hashed_password=hashed_password)
        db.add(new_user)
        db.commit()
        return new_user

    @classmethod
    def authenticate(cls, db: Session, username: str, password: str):
        """
        Аутентификация пользователя по имени и паролю.
        Возвращает пользователя, если он существует и пароль верный.
        """
        user = db.query(User).filter(User.username == username).first()
        if user and bcrypt.verify(password, user.hashed_password):
            return user
        return None

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
