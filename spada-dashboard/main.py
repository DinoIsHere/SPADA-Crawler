from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from scraper import DATA_FILE, load_data, login, auto_attendance, auto_solve_quiz
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv

# Create a FastAPI app
app = FastAPI()

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), 'login.env')
load_dotenv(dotenv_path=dotenv_path)

# Mount static files (for CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

STATUS_FILE = "task_status.json"
CONFIG_FILE = "ai_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "ai_model": "gemini-1.5-flash",
        "auto_courses": {} # course_url: {attendance: bool, quiz: bool}
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@app.get("/ai-config")
async def get_ai_config():
    return load_config()

@app.post("/ai-config")
async def update_ai_config(request: Request):
    payload = await request.json()
    save_config(payload)
    return {"success": True}

@app.post("/run-collective-automation")
async def run_collective():
    config = load_config()
    data = load_data(os.path.join(os.path.dirname(__file__), DATA_FILE))
    
    results = []
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            login(page)
            for course in data:
                course_url = course.get("url") # We need to make sure course objects have URLs
                # Wait, course data from scraper has course_url in some places, but let's check
                # Actually, course_data.json structure is:
                # [ { "course_title": "...", "assignments": [...], "attendance": [...], "quizzes": [...] } ]
                # We might need to add the course URL to the course_data.json if it's not there.
                
                # For now, let's iterate through all tasks in all courses that match the config
                for attend in course.get("attendance", []):
                    if config["auto_courses"].get(attend["url"], {}).get("attendance"):
                        success = auto_attendance(page, attend["url"])
                        results.append({"type": "attendance", "url": attend["url"], "success": success})
                
                for quiz in course.get("quizzes", []):
                    if config["auto_courses"].get(quiz["url"], {}).get("quiz"):
                        success = auto_solve_quiz(page, quiz["url"], config["gemini_api_key"], config["ai_model"])
                        results.append({"type": "quiz", "url": quiz["url"], "success": success})
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
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "SPADA Dashboard"})

@app.get("/data")
async def get_dashboard_data():
    """
    API endpoint to serve the scraped data with completion status.
    """
    data = load_data(os.path.join(os.path.dirname(__file__), DATA_FILE))
    status = load_status()
    return {"data": data, "status": status}

@app.post("/toggle-task")
async def toggle_task(request: Request):
    payload = await request.json()
    url = payload.get("url")
    completed = payload.get("completed")
    
    status = load_status()
    status[url] = completed
    save_status(status)
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    # To run this, you would use 'uvicorn main:app --reload'
    print("FastAPI app is set up. To run, use 'uvicorn main:app --reload'")
    uvicorn.run(app, host="0.0.0.0", port=8000)
