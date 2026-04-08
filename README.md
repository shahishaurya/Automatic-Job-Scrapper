🚀 Multi-User Job Intelligence Suite (ETL)

A robust, automated job-scraping and reporting engine. This system performs a full ETL (Extract, Transform, Load) cycle: it extracts live job data from LinkedIn and Naukri, transforms it into structured SQLite databases, and delivers a daily Excel summary to multiple users via email.

🌟 Key Features
Dual-Platform Scraper: Native support for LinkedIn and Naukri.com using Selenium Stealth.

Multi-User Architecture: Parallel configuration for different users with unique keywords and locations.

Automated Database Management: SQLite-driven storage to prevent duplicate entries and maintain history.

Email Automation: SMTP-integrated reporting that sends custom Excel attachments once scraping is complete.

Task Scheduling Ready: Built to run autonomously on Windows or Cloud environments.

🛠 Tech Stack
Language: Python 3.x

Automation: Selenium WebDriver, WebDriver-Manager

Data Analysis: Pandas, OpenPyXL

Database: SQLite3

Communication: Smtplib (Gmail SSL), MIME

📦 Installation & Setup
1. Clone the Repository
Bash
git clone https://github.com/your-username/job-intelligence-suite.git
cd job-intelligence-suite
2. Install Dependencies
Bash
pip install pandas selenium webdriver-manager openpyxl
3. Configure Gmail Credentials
For security, do not use your primary password.

Go to your Google Account settings.

Enable 2-Step Verification.

Search for App Passwords.

Generate a password for "Mail" and "Windows Computer". Use this 16-character code in your users_config.

⚙️ Automation on Windows
To make this truly "hands-free," you can schedule it to run every morning.

Step 1: Create a Batch File (run_pipeline.bat)
Create a file named run_pipeline.bat in your project folder and paste the following:

Code snippet
@echo off
cd /d "C:\Path\To\Your\Project\Folder"
python your_script_name.py
pause
Step 2: Schedule with Windows Task Scheduler
Open Task Scheduler and click Create Basic Task.

Trigger: Daily (e.g., 9:00 AM).

Action: Start a Program.

Program/script: Browse and select your run_pipeline.bat.

Start in: Paste the path to your project folder (crucial for locating the database files).

📊 Database Schema
The system maintains two localized databases per user:

LinkedIn Table: job_id, title, company, location, url, date_scraped

Naukri Table: Adds salary and experience fields for deeper insights.

🛡 Disclaimer
This tool is for educational and personal use only. Please ensure you comply with the Terms of Service of LinkedIn and Naukri when using automated scrapers.

📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
