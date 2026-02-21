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
    Navigates to a course page and extracts assignments and attendance.
    """
    print(f"Scraping data for course: {course_title} ({course_url})")
    page.goto(course_url)
    page.wait_for_load_state("networkidle")

    unique_assignments = {} # Use dict to store unique assignments by URL
    unique_attendance_records = {} # Use dict to store unique attendance records by URL

    # Look for assignment links
    assignment_links = page.locator("a[href*='/mod/assign/view.php']").all()
    for link in assignment_links:
        url = link.get_attribute("href")
        if url and url not in unique_assignments:
            text = link.inner_text().strip()
            text = text.replace("\nAssignment", "").replace("\nAssignment", "").strip() # Clean up text
            unique_assignments[url] = {"text": text, "url": url}

    # Look for attendance links
    attendance_links = page.locator("a[href*='/mod/attendance/view.php']").all()
    for link in attendance_links:
        url = link.get_attribute("href")
        if url and url not in unique_attendance_records:
            text = link.inner_text().strip()
            text = text.replace("\nAttendance", "").replace("\nAttendance", "").strip() # Clean up text
            unique_attendance_records[url] = {"text": text, "url": url}

    assignments = list(unique_assignments.values())
    attendance_records = list(unique_attendance_records.values())

    print(f"  Found {len(assignments)} assignments and {len(attendance_records)} attendance links.")
    return {"assignments": assignments, "attendance": attendance_records}

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
    Compares old and new data to find new assignments and attendance records.
    """
    old_assignments_urls = set()
    old_attendance_urls = set()

    for course_data in old_data:
        for assignment in course_data.get("assignments", []):
            old_assignments_urls.add(assignment["url"])
        for attendance in course_data.get("attendance", []):
            old_attendance_urls.add(attendance["url"])

    new_assignments = []
    new_attendance = []

    for course_data in new_data:
        for assignment in course_data.get("assignments", []):
            if assignment["url"] not in old_assignments_urls:
                new_assignments.append(assignment)
        for attendance in course_data.get("attendance", []):
            if attendance["url"] not in old_attendance_urls:
                new_attendance.append(attendance)

    return new_assignments, new_attendance


def main():
    """
    Main function to run the scraper.
    """
    dotenv_path = os.path.join(os.path.dirname(__file__), 'login.env')
    load_dotenv(dotenv_path=dotenv_path)
    
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

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

        # Find new assignments and attendance
        new_assignments, new_attendance = find_new_items(old_course_data, all_course_data)

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

        if notification_message:
            send_discord_notification(discord_webhook_url, notification_message)
        else:
            print("No new assignments or attendance records found.")

        # Save the new data
        save_data(all_course_data)
        
        browser.close()


if __name__ == "__main__":
    main()
