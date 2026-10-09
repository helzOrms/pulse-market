import sqlite3
import hashlib
from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            tariff TEXT DEFAULT 'free'
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def read_root(request: Request, session_user: Optional[str] = Cookie(None)):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": session_user
    })

@app.get("/auth")
def show_auth_page(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), action: Optional[str] = Form(None)):
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    hashed_input_password = hash_password(password)

    if action == "register":
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_input_password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return HTMLResponse("<h2>Логин занят! <a href='/auth'>Назад</a></h2>")
        
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0] == hashed_input_password:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_user", value=username)
        return response
    
    return HTMLResponse("<h2>Неверный логин или пароль! <a href='/auth'>Назад</a></h2>")

@app.post("/buy-premium")
def buy_premium(session_user: Optional[str] = Cookie(None)):
    if not session_user:
        return RedirectResponse(url="/auth", status_code=303)
        
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET tariff = 'premium' WHERE username = ?", (session_user,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/profile", status_code=303)

@app.get("/profile")
def show_profile(request: Request, session_user: Optional[str] = Cookie(None)):
    if not session_user:
        return RedirectResponse(url="/auth", status_code=303)
        
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tariff FROM users WHERE username = ?", (session_user,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return RedirectResponse(url="/logout", status_code=303)
        
    user_tariff = row[0]
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user_name": session_user,
        "user_tariff": user_tariff
    })

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_user")
    return response


# ==========================================
# НОВЫЙ БЛОК: СЕКРЕТНАЯ ПАНЕЛЬ АДМИНИСТРАТОРА
# ==========================================

# 1. Маршрут отображения админки (Защищённый)
@app.get("/admin")
def show_admin_page(request: Request, session_user: Optional[str] = Cookie(None)):
    # Строгая проверка: если зашёл НЕ "admin", выкидываем его на главную
    if session_user != "admin":
        return RedirectResponse(url="/", status_code=303)
        
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    # Достаем всех зарегистрированных пользователей из базы
    cursor.execute("SELECT id, username, tariff FROM users")
    users_list = cursor.fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "all_users": users_list
    })

# 2. Логика переключения тарифа кнопкой
@app.post("/admin/toggle-tariff")
def toggle_tariff(user_id: int = Form(...), current_tariff: str = Form(...), session_user: Optional[str] = Cookie(None)):
    # Защита: только админ может слать сюда POST-запросы
    if session_user != "admin":
        return RedirectResponse(url="/", status_code=303)
        
    # Определяем новый статус тарифа
    new_tariff = "free" if current_tariff == "premium" else "premium"
    
    conn = sqlite3.connect("pulse.db")
    cursor = conn.cursor()
    # Обновляем тариф пользователя по его уникальному ID
    cursor.execute("UPDATE users SET tariff = ? WHERE id = ?", (new_tariff, user_id))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/admin", status_code=303)
