# Implementation Plan - Auto Attendance & Auto Assignments

## Objective
Add automation modules for attendance and multiple-choice assignments (quizzes) to the SPADA Tracker dashboard.

## 1. Scraper Enhancements (`scraper.py`)
- [ ] **Quiz Detection**: Update `scrape_course_data` to detect Moodle quizzes (`/mod/quiz/view.php`).
- [ ] **Auto Attendance Logic**:
    - Implement `auto_attendance(page, url)`:
        - Navigate to attendance URL.
        - Check for "Submit attendance" / "Ajukan kehadiran" links.
        - Select "Hadir" / "Present" and save.
- [ ] **Auto Quiz Logic (AI)**:
    - Implement `auto_solve_quiz(page, url)`:
        - Navigate to quiz.
        - "Attempt quiz now".
        - Scrape questions/options.
        - Use AI (Gemini/OpenAI) to select the correct answer.
        - Navigate through pages.
        - Submit.

## 2. API Endpoints (`main.py`)
- [ ] Add `/run-attendance` POST endpoint.
- [ ] Add `/run-quizzes` POST endpoint.
- [ ] Update `/data` to include found quizzes.

## 3. Frontend Updates (`templates/index.html`, `static/script.js`, `static/style.css`)
- [ ] **UI Update**:
    - Enable checkboxes in "AI Insights" section.
    - Add buttons to trigger automation.
    - Add status indicators for automation tasks.
- [ ] **JS Logic**:
    - Add event handlers for the new buttons.
    - Handle API calls to the new endpoints.

## 4. Configuration
- [ ] Add `GEMINI_API_KEY` to `login.env`.
- [ ] Update `requirements.txt` with `google-generativeai`.

## 5. Security & Safety
- [ ] Ensure AI only targets "Multiple Choice" quizzes as requested (titles like "Post Test", "Quiz").
- [ ] Add logging for all automated actions.

## 6. Multi-Person & Cloud Sync (Free Tier)
- [x] **Database Strategy**: 
    - Use "Git-Persistence" via GitHub Actions.
    - Data stored in `course_data.json` and `ai_config.json`.
    - Updates are committed/pushed by GitHub Actions.
- [ ] **Cloud Hosting**: 
    - Deploy to Hugging Face Spaces (Docker).
    - Use GitHub Actions for scheduled background scraping.
- [ ] **Privacy Layer**: 
    - Implement a simple "System Password" for shared access.
    - Refactor main.py to handle sensitive env vars in cloud secrets.

