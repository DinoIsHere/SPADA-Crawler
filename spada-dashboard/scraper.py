import os
import requests
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

DATA_FILE = "course_data.json"

def save_data(data, filename=DATA_FILE):
    """
    Saves data to a JSON file.
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {filename}")

def load_data(filename=DATA_FILE):
    """
    Loads data from a JSON file.
    """
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
        print(f"Data loaded from {filename}")
        return data
    print(f"No existing data found at {filename}")
    return []

def login(page):
    """
    Logs in to the website.
    """
    print("Logging in...")
    username = os.getenv("SPADA_USERNAME")
    password = os.getenv("SPADA_PASSWORD")
    page.goto("https://spada.teknokrat.ac.id/login/index.php")
    page.fill("input#username", username)
    page.fill("input#password", password)
    page.click("button#loginbtn")
    page.wait_for_url("https://spada.teknokrat.ac.id/my/")
    print("Login successful!")

def get_courses(page):
    """
    Extracts course titles and URLs from the courses page.
    """
    print("Extracting courses...")
    courses = []
    course_elements = page.locator("div.course-info-container").all()

    for course_element in course_elements:
        title_element = course_element.locator("a.aalink.coursename")
        full_title = title_element.inner_text().strip()
        
        # Remove "Course name\n" prefix and clean up
        title = full_title.replace("Course name\n", "").strip()
        
        url = title_element.get_attribute("href")
        if title and url:
            courses.append({"title": title, "url": url})
    print(f"Found {len(courses)} courses.")
    return courses

def scrape_course_data(page, course_title, course_url):
    """
    Navigates to a course page and extracts assignments, attendance, and quizzes.
    """
    print(f"Scraping data for course: {course_title} ({course_url})")
    page.goto(course_url)
    page.wait_for_load_state("networkidle")

    unique_assignments = {} 
    unique_attendance_records = {} 
    unique_quizzes = {}

    # Look for assignment links
    assignment_links = page.locator("a[href*='/mod/assign/view.php']").all()
    for link in assignment_links:
        url = link.get_attribute("href")
        if url and url not in unique_assignments:
            text = link.inner_text().strip()
            text = text.replace("\nAssignment", "").strip()
            
            # Deep scrape for due date
            print(f"    Extracting due date for: {text}")
            try:
                new_page = page.context.new_page()
                new_page.goto(url, timeout=15000)
                due_date_locator = new_page.locator(".datesummary, .submissionstatustable td.cell.c1:has-text('202'), .submissionstatustable td:has-text('Due date') + td")
                
                due_date = None
                if due_date_locator.count() > 0:
                    due_date = due_date_locator.first.inner_text().strip()
                    print(f"      Due date found: {due_date}")
                
                unique_assignments[url] = {"text": text, "url": url, "due_date": due_date}
                new_page.close()
            except Exception as e:
                print(f"      Could not get due date: {e}")
                unique_assignments[url] = {"text": text, "url": url, "due_date": None}

    # Look for attendance links
    attendance_links = page.locator("a[href*='/mod/attendance/view.php']").all()
    for link in attendance_links:
        url = link.get_attribute("href")
        if url and url not in unique_attendance_records:
            text = link.inner_text().strip()
            text = text.replace("\nAttendance", "").strip()
            unique_attendance_records[url] = {"text": text, "url": url}

    # Look for quiz links (New)
    quiz_links = page.locator("a[href*='/mod/quiz/view.php']").all()
    for link in quiz_links:
        url = link.get_attribute("href")
        if url and url not in unique_quizzes:
            text = link.inner_text().strip()
            text = text.replace("\nQuiz", "").strip()
            unique_quizzes[url] = {"text": text, "url": url}

    assignments = list(unique_assignments.values())
    attendance_records = list(unique_attendance_records.values())
    quizzes = list(unique_quizzes.values())

    print(f"  Found {len(assignments)} assignments, {len(attendance_records)} attendance links, and {len(quizzes)} quizzes.")
    return {"assignments": assignments, "attendance": attendance_records, "quizzes": quizzes}


def auto_attendance(page, attendance_url):
    """
    Automatically submits attendance for a session.
    """
    print(f"Attempting auto-attendance for: {attendance_url}")
    try:
        page.goto(attendance_url)
        page.wait_for_load_state("networkidle")
        
        # Look for "Submit attendance" or "Ajukan kehadiran"
        submit_link = page.locator("a:has-text('Submit attendance'), a:has-text('Ajukan kehadiran'), a:has-text('Pilih Kehadiran')").first
        
        if submit_link.count() > 0:
            submit_link.click()
            page.wait_for_load_state("networkidle")
            
            # Usually there's a radio button for "Hadir" or "Present"
            hadir_radio = page.locator("label:has-text('Hadir'), label:has-text('Present')").first
            if hadir_radio.count() > 0:
                hadir_radio.click()
                page.click("input[type='submit'], button[type='submit']")
                print("Attendance submitted successfully!")
                return True
            else:
                print("Found submit link but couldn't find 'Hadir' or 'Present' option.")
        else:
            print("No active attendance session found to submit.")
    except Exception as e:
        print(f"Error during auto-attendance: {e}")
    return False


def auto_solve_quiz(page, quiz_url, ai_api_key=None, model_name='gemini-1.5-flash'):
    """
    Automatically solves multiple-choice quizzes using AI.
    """
    print(f"Attempting auto-quiz solver for: {quiz_url} using {model_name}")
    if not ai_api_key:
        print("AI API Key not provided. Skipping quiz solver.")
        return False

    try:
        import google.generativeai as genai
        genai.configure(api_key=ai_api_key)
        model = genai.GenerativeModel(model_name)
        
        page.goto(quiz_url)
        page.wait_for_load_state("networkidle")
        
        # Check if quiz is attemptable
        attempt_btn = page.locator("button:has-text('Attempt quiz now'), button:has-text('Continue the last attempt')").first
        if attempt_btn.count() == 0:
            print("Quiz is not attemptable (already finished or not open).")
            return False
            
        attempt_btn.click()
        page.wait_for_load_state("networkidle")
        
        # Loop through questions
        while True:
            # Extract question text
            question_container = page.locator(".que").first
            if question_container.count() == 0:
                break
                
            q_text = question_container.locator(".qtext").innerText()
            options = question_container.locator(".answer div.r0, .answer div.r1").all()
            
            options_text = []
            for i, opt in enumerate(options):
                options_text.append(f"{chr(65+i)}. {opt.innerText()}")
            
            prompt = f"Question: {q_text}\nOptions:\n" + "\n".join(options_text) + "\n\nSelect the correct option letter (A, B, C, D, or E). Only return the letter."
            
            response = model.generate_content(prompt)
            answer_letter = response.text.strip().upper()
            
            # Find the option to click
            found_answer = False
            for i, opt in enumerate(options):
                if answer_letter == chr(65+i):
                    opt.locator("input").click()
                    found_answer = True
                    break
            
            if not found_answer:
                print(f"AI suggested {answer_letter} but it wasn't found in options. Clicking first option as fallback.")
                options[0].locator("input").click()
            
            # Next page
            next_btn = page.locator("input[value='Next page'], input[value='Finish attempt...'], button:has-text('Next')").first
            if next_btn.count() > 0:
                is_finish = "Finish" in next_btn.get_attribute("value") or "Finish" in next_btn.inner_text()
                next_btn.click()
                page.wait_for_load_state("networkidle")
                if is_finish:
                    # Submit all and finish
                    page.locator("button:has-text('Submit all and finish')").click()
                    # Moodle usually has a confirmation dialog
                    page.locator(".modal-footer button.btn-primary:has-text('Submit all and finish')").click()
                    print("Quiz submitted successfully!")
                    return True
            else:
                break
                
    except Exception as e:
        print(f"Error during auto-quiz solver: {e}")
    return False

def send_discord_notification(webhook_url, message):
    """
    Sends a notification to a Discord webhook, splitting into multiple messages if too long.
    """
    if not webhook_url:
        print("Discord webhook URL not provided. Skipping notification.")
        return

    MAX_MESSAGE_LENGTH = 2000
    
    # Split the message into chunks if it's too long
    message_chunks = []
    current_chunk = ""
    for line in message.splitlines(keepends=True): # keepends=True to preserve newlines for splitting logic
        if len(current_chunk) + len(line) > MAX_MESSAGE_LENGTH:
            message_chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += line
    if current_chunk: # Add the last chunk
        message_chunks.append(current_chunk)

    if not message_chunks:
        print("No content to send to Discord.")
        return

    for i, chunk in enumerate(message_chunks):
        payload = {
            "content": chunk.strip() # Strip to avoid sending empty messages if a chunk is just whitespace
        }
        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors
            print(f"Discord notification part {i+1}/{len(message_chunks)} sent successfully!")
        except requests.exceptions.RequestException as e:
            print(f"Error sending Discord notification part {i+1}/{len(message_chunks)}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Discord API response: {e.response.text}")


def find_new_items(old_data, new_data):
    """
    Compares old and new data to find new assignments, attendance records, and quizzes.
    """
    old_assignments_urls = set()
    old_attendance_urls = set()
    old_quizzes_urls = set()

    for course_data in old_data:
        for assignment in course_data.get("assignments", []):
            old_assignments_urls.add(assignment["url"])
        for attendance in course_data.get("attendance", []):
            old_attendance_urls.add(attendance["url"])
        for quiz in course_data.get("quizzes", []):
            old_quizzes_urls.add(quiz["url"])

    new_assignments = []
    new_attendance = []
    new_quizzes = []

    for course_data in new_data:
        for assignment in course_data.get("assignments", []):
            if assignment["url"] not in old_assignments_urls:
                new_assignments.append(assignment)
        for attendance in course_data.get("attendance", []):
            if attendance["url"] not in old_attendance_urls:
                new_attendance.append(attendance)
        for quiz in course_data.get("quizzes", []):
            if quiz["url"] not in old_quizzes_urls:
                new_quizzes.append(quiz)

    return new_assignments, new_attendance, new_quizzes


def main():
    """
    Main function to run the scraper.
    """
    dotenv_path = os.path.join(os.path.dirname(__file__), 'login.env')
    load_dotenv(dotenv_path=dotenv_path)
    
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        login(page)

        # Navigate to the courses page
        print("Navigating to courses page...")
        page.goto("https://spada.teknokrat.ac.id/my/courses.php")
        page.wait_for_load_state("networkidle")
        print("Courses page loaded.")

        course_list = get_courses(page)
        
        all_course_data = []
        for course in course_list:
            data = scrape_course_data(page, course["title"], course["url"])
            all_course_data.append({"course_title": course["title"], **data})
        
        # Load previous data
        old_course_data = load_data()

        # Find new items
        new_assignments, new_attendance, new_quizzes = find_new_items(old_course_data, all_course_data)

        # Send Discord notifications for new items
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        print(f"Discord webhook URL being used: {discord_webhook_url}")
        notification_message = ""

        if new_assignments:
            notification_message += "**New Assignments:**\n"
            for assign in new_assignments:
                notification_message += f"- [{assign['text']}]({assign['url']})\n"
        
        if new_attendance:
            if notification_message:
                notification_message += "\n"
            notification_message += "**New Attendance Records:**\n"
            for attend in new_attendance:
                notification_message += f"- [{attend['text']}]({attend['url']})\n"

        if new_quizzes:
            if notification_message:
                notification_message += "\n"
            notification_message += "**New Quizzes:**\n"
            for quiz in new_quizzes:
                notification_message += f"- [{quiz['text']}]({quiz['url']})\n"

        if notification_message:
            send_discord_notification(discord_webhook_url, notification_message)
        else:
            print("No new assignments, attendance records, or quizzes found.")

        # Save the new data
        save_data(all_course_data)
        
        browser.close()


if __name__ == "__main__":
    main()
