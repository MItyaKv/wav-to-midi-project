from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.hash import bcrypt
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import uuid
import mido
import soundfile as sf
from datetime import datetime, timedelta
import numpy as np

# --- Config ---
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- FastAPI App ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DB Setup ---
DATABASE_URL = "sqlite:///./users.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

Base.metadata.create_all(bind=engine)

# --- Auth Utils ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session = Depends(SessionLocal)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return db.query(User).filter(User.username == username).first()
    except JWTError:
        return None

# --- Directories ---
os.makedirs("uploads", exist_ok=True)
os.makedirs("midi", exist_ok=True)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    db = SessionLocal()
    user = get_current_user(request, db)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already taken."})
    user = User(username=username, hashed_password=bcrypt.hash(password))
    db.add(user)
    db.commit()
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    token = create_access_token({"sub": username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=ACCESS_TOKEN_EXPIRE_MINUTES*60)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    db = SessionLocal()
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from models import Conversion
    conversions = db.query(Conversion).filter(Conversion.user_id == user.id).order_by(Conversion.created_at.desc()).all()
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "conversions": conversions})

@app.post("/upload/", response_class=HTMLResponse)
def upload_file(request: Request, file: UploadFile = File(...)):
    db = SessionLocal()
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    file_id = str(uuid.uuid4())
    wav_path = f"uploads/{file_id}.wav"
    midi_path = f"midi/{file_id}.mid"

    with open(wav_path, "wb") as f:
        f.write(file.file.read())

    y, sr = sf.read(wav_path)
    if len(y.shape) > 1:
        y = np.mean(y, axis=1)  # Convert to mono if stereo

    frame_size = 2048
    hop_length = 512
    window = np.hanning(frame_size)
    threshold = 0.02
    onsets = []

    energy = []
    pitches = []
    times = []

    for i in range(0, len(y) - frame_size, hop_length):
        frame = y[i:i+frame_size] * window
        spectrum = np.fft.rfft(frame)
        mag = np.abs(spectrum)
        energy_val = np.sum(mag)
        energy.append(energy_val)

        freq_res = sr / frame_size
        peak_index = np.argmax(mag)
        freq = peak_index * freq_res
        pitch = 69 + 12 * np.log2(freq / 440.0) if freq > 0 else 60
        pitches.append(int(round(pitch)))
        times.append(i / sr)

    energy = np.array(energy)
    energy_diff = np.diff(energy, prepend=0)

    for i in range(1, len(energy_diff)):
        if energy_diff[i] > threshold and energy_diff[i - 1] <= threshold:
            t = times[i]
            note = pitches[i]
            onsets.append((t, note))

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    prev_ticks = 0
    for t, note in onsets:
        ticks = int(mido.second2tick(t, 480, mido.bpm2tempo(120)))
        delta = ticks - prev_ticks
        track.append(mido.Message('note_on', note=note, velocity=64, time=delta))
        track.append(mido.Message('note_off', note=note, velocity=64, time=100))
        prev_ticks = ticks

    mid.save(midi_path)

    from models import Conversion
    conv = Conversion(filename=file.filename, file_id=file_id, user_id=user.id)
    db.add(conv)
    db.commit()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "download_link": f"/download/{file_id}"
    })

@app.get("/download/{file_id}")
def download_midi(file_id: str, request: Request):
    db = SessionLocal()
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    path = f"midi/{file_id}.mid"
    if os.path.exists(path):
        return FileResponse(path, media_type="audio/midi", filename=f"{file_id}.mid")
    raise HTTPException(status_code=404, detail="File not found")