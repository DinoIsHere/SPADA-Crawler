from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json # Import json to load data
from scraper import DATA_FILE, load_data # Import DATA_FILE and load_data from scraper

# Create a FastAPI app
app = FastAPI()

# Mount static files (for CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "SPADA Dashboard"})

@app.get("/data")
async def get_dashboard_data():
    """
    API endpoint to serve the scraped data.
    """
    data = load_data(os.path.join(os.path.dirname(__file__), DATA_FILE))
    return {"data": data}

if __name__ == "__main__":
    import uvicorn
    # To run this, you would use 'uvicorn main:app --reload'
    print("FastAPI app is set up. To run, use 'uvicorn main:app --reload'")
    uvicorn.run(app, host="0.0.0.0", port=8000)
