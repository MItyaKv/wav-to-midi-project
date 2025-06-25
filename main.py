from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime, timedelta
from audio_utils import mp3_to_wav

from models import Base, engine, SessionLocal, User, Conversion, get_db
from auth import get_current_user, create_access_token
from midi_converter import convert_wav_to_midi

# --- FastAPI App ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Create DB ---
Base.metadata.create_all(bind=engine)

# --- Directories ---
os.makedirs("uploads", exist_ok=True)
os.makedirs("midi", exist_ok=True)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {"request": request, "error": "Пользователь уже существует."})
    user = User.create(db, username, password)
    return RedirectResponse("/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = User.authenticate(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверные данные для входа."})
    token = create_access_token({"sub": username}, timedelta(minutes=60))
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    conversions = db.query(Conversion).filter(Conversion.user_id == user.id).order_by(Conversion.created_at.desc()).all()
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "conversions": conversions})

@app.post("/upload/", response_class=HTMLResponse)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    instrument: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    file_id = str(uuid.uuid4())
    orig_ext = os.path.splitext(file.filename)[1].lower()
    raw_path = f"uploads/{file_id}{orig_ext}"
    wav_path = f"uploads/{file_id}.wav"       # конечный wav
    midi_path = f"midi/{file_id}.mid"

    # сохраняем оригинальный файл
    with open(raw_path, "wb") as f:
        f.write(file.file.read())

    # если mp3 — конвертируем во временный wav
    if orig_ext == ".mp3":
        wav_path = mp3_to_wav(raw_path)

    # далее как раньше
    convert_wav_to_midi(wav_path, midi_path, instrument=instrument)

    conv = Conversion(filename=file.filename, file_id=file_id, user_id=user.id)
    db.add(conv)
    db.commit()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "download_link": f"/download/{file_id}"
    })

@app.get("/download/{file_id}")
def download_midi(file_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    path = f"midi/{file_id}.mid"
    if os.path.exists(path):
        return FileResponse(path, media_type="audio/midi", filename=f"{file_id}.mid")
    raise HTTPException(status_code=404, detail="Файл не найден")

@app.post("/delete/{file_id}")
def delete_file(
    file_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    conv = (
        db.query(Conversion)
        .filter(Conversion.file_id == file_id, Conversion.user_id == user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # удалить физические файлы
    for path in (f"uploads/{file_id}.wav", f"midi/{file_id}.mid"):
        if os.path.exists(path):
            os.remove(path)

    # удалить запись из БД
    db.delete(conv)
    db.commit()

    return RedirectResponse("/profile", status_code=302)