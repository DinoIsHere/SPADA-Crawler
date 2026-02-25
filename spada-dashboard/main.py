from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from scraper import DATA_FILE, load_data, login, auto_attendance, auto_solve_quiz
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv
import db_utils

# Create a FastAPI app
app = FastAPI()

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), 'login.env')
load_dotenv(dotenv_path=dotenv_path)

# Check for required config
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    print("WARNING: SUPABASE_URL or SUPABASE_KEY missing in login.env!")
if not os.getenv("ENCRYPTION_KEY"):
    print("WARNING: ENCRYPTION_KEY missing! Password encryption will generate a new key on every restart (this will break existing saved passwords).")

# Mount static files (for CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Dependency to get current user
async def get_current_user(request: Request):
    session = request.cookies.get("session")
    if not session:
        return None
    try:
        user = db_utils.supabase.auth.get_user(session)
        return user.user
    except:
        return None

def require_auth(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=302, detail="Not authenticated", headers={"Location": "/login"})
    return user

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_action(response: Response, email: str = Form(...), password: str = Form(...)):
    try:
        res = db_utils.supabase.auth.sign_in_with_password({"email": email, "password": password})
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session", value=res.session.access_token, httponly=True)
        return response
    except Exception as e:
        return HTMLResponse(content=f"Login failed: {str(e)}", status_code=400)

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup_action(email: str = Form(...), password: str = Form(...), username: str = Form(...)):
    try:
        # 1. Sign up user
        res = db_utils.supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            # 2. Create profile
            db_utils.supabase.table("profiles").insert({
                "id": res.user.id,
                "username": username
            }).execute()
        return RedirectResponse(url="/login", status_code=302)
    except Exception as e:
        return HTMLResponse(content=f"Signup failed: {str(e)}", status_code=400)

@app.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response

@app.get("/ai-config")
async def get_ai_config(user = Depends(require_auth)):
    profile = db_utils.get_user_profile(user.id)
    return profile.get("ai_config", {})

@app.post("/ai-config")
async def update_ai_config(request: Request, user = Depends(require_auth)):
    payload = await request.json()
    db_utils.update_user_profile(user.id, {"ai_config": payload})
    return {"success": True}

@app.post("/run-collective-automation")
async def run_collective(user = Depends(require_auth)):
    profile = db_utils.get_user_profile(user.id)
    config = profile.get("ai_config", {})
    gemini_key = profile.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    
    # Decrypt SPADA credentials
    spada_user = profile.get("spada_username")
    spada_pass_enc = profile.get("spada_password")
    
    if not (spada_user and spada_pass_enc):
        return {"error": "SPADA credentials not configured in profile."}
        
    spada_pass = db_utils.decrypt_password(spada_pass_enc)
    data = profile.get("scraped_data", [])
    
    results = []
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            # Modify login to accept credentials
            login(page, spada_user, spada_pass) 
            for course in data:
                course_title = course.get("course_title")
                course_cfg = config.get("auto_courses", {}).get(course_title, {"enabled": True, "attendance": False, "quiz": False})
                
                if not course_cfg.get("enabled", True):
                    continue

                # Auto-Attendance
                if course_cfg.get("attendance"):
                    for attend in course.get("attendance", []):
                        success = auto_attendance(page, attend["url"])
                        results.append({"type": "attendance", "course": course_title, "url": attend["url"], "success": success})
                
                # Auto-Quiz
                if course_cfg.get("quiz"):
                    for quiz in course.get("quizzes", []):
                        success = auto_solve_quiz(page, quiz["url"], gemini_key, config.get("ai_model", "gemini-1.5-flash"))
                        results.append({"type": "quiz", "course": course_title, "url": quiz["url"], "success": success})
        finally:
            browser.close()
            
    return {"results": results}

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    return {}

def run_automation_task(task_type, url):
    """
    Helper to run a playwright task for automation.
    """
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            login(page)
            if task_type == "attendance":
                success = auto_attendance(page, url)
            elif task_type == "quiz":
                api_key = os.getenv("GEMINI_API_KEY")
                success = auto_solve_quiz(page, url, api_key)
            else:
                success = False
        finally:
            browser.close()
    return success

@app.post("/run-attendance")
async def run_attendance(request: Request):
    payload = await request.json()
    url = payload.get("url")
    success = run_automation_task("attendance", url)
    return {"success": success}

@app.post("/run-quiz")
async def run_quiz(request: Request):
    payload = await request.json()
    url = payload.get("url")
    success = run_automation_task("quiz", url)
    return {"success": success}

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_status(status):
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=4)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user = Depends(require_auth)):
    profile = db_utils.get_user_profile(user.id)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "title": "SPADA Dashboard",
        "username": profile.get("username", "User")
    })

@app.get("/data")
async def get_dashboard_data(user = Depends(require_auth)):
    profile = db_utils.get_user_profile(user.id)
    data = profile.get("scraped_data", [])
    status = profile.get("task_status", {})
    return {"data": data, "status": status, "profile": profile}

@app.post("/toggle-task")
async def toggle_task(request: Request, user = Depends(require_auth)):
    payload = await request.json()
    url = payload.get("url")
    completed = payload.get("completed")
    
    profile = db_utils.get_user_profile(user.id)
    status = profile.get("task_status", {})
    status[url] = completed
    
    db_utils.update_user_profile(user.id, {"task_status": status})
    return {"success": True}

@app.post("/update-profile")
async def update_profile(request: Request, user = Depends(require_auth)):
    payload = await request.json()
    data_to_update = {}
    
    if "spada_username" in payload:
        data_to_update["spada_username"] = payload["spada_username"]
    if "spada_password" in payload and payload["spada_password"]:
        data_to_update["spada_password"] = db_utils.encrypt_password(payload["spada_password"])
    if "gemini_api_key" in payload:
        data_to_update["gemini_api_key"] = payload["gemini_api_key"]
    if "discord_webhook" in payload:
        data_to_update["discord_webhook"] = payload["discord_webhook"]
        
    if data_to_update:
        db_utils.update_user_profile(user.id, data_to_update)
    
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"FastAPI app is set up. Running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
