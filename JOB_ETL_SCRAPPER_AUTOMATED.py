from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import io
import os
import smtplib
import sqlite3
import time
import matplotlib
import urllib.parse
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

matplotlib.use("Agg")
import matplotlib.pyplot as plt

users_config = {
    "user1": {
        "DB_LINKEDIN": "linkedin_user1.db",
        "DB_NAUKRI": "naukri_user1.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
        "KEYWORDS": [
            "Py",
            "Python",
            "PySpark",
            "SQL",
            "Data Engineer",
            "AWS",
            "Palantir",
            "ETL",
            "Data Warehouse",
            "Data Pipeline",
            "Big Data",
            "Cloud",
            "Foundry",
            "Python Data Engineer",
            "PySpark Data Engineer",
            "AWS Data Engineer",
            "Data Platform Engineer",
            "Big Data Engineer",
            "ETL Developer",
        ],
        "LOCATIONS": [
            "Bangalore",
            "Bengaluru",
            "Bangalore Urban",
            "Bangalore Rural",
            "Remote",
        ],
    },
    "user2": {
        "DB_LINKEDIN": "linkedin_user2.db",
        "DB_NAUKRI": "naukri_user2.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
        "KEYWORDS": [
            "Py",
            "Data Operations Analyst",
            "Financial Data Analyst",
            "Business Intelligence Analyst",
            "Finance Operations Analyst",
            "Revenue Operations Analyst",
            "Accounts Payable Analyst",
            "SQL",
            "Python",
            "Power BI",
            "Tableau",
            "Excel",
            "Advanced Excel",
            "Macros",
            "VBA",
            "VBA Macros",
            "DAX",
            "Power Query",
            "Order to Cash",
            "Procure to Pay",
            "Financial Reconciliation",
            "Billing Operations",
            "Audit Compliance",
            "TAT Optimization",
            "Data Analyst",
            "Data Visualization",
            "Data Reporting",
        ],
        "LOCATIONS": [
            "Bangalore",
            "Bengaluru",
            "Bangalore Urban",
            "Bangalore Rural",
            "Remote",
        ],
    },
}

CHROME_PROFILE = os.path.join(os.getcwd(), "AutomationProfile")


def init_dbs(user_params):
  linkedin_schema = """
    (
        job_id TEXT,
        title TEXT,
        company TEXT,
        location TEXT,
        url TEXT,
        date_scraped DATE,
        PRIMARY KEY(job_id, date_scraped)
    )
    """
  naukri_schema = """
    (
        job_id TEXT,
        title TEXT,
        company TEXT,
        location TEXT,
        salary TEXT,
        experience TEXT,
        url TEXT,
        date_scraped DATE,
        PRIMARY KEY(job_id, date_scraped)
    )
    """
  db_configs = [
      (user_params["DB_LINKEDIN"], linkedin_schema),
      (user_params["DB_NAUKRI"], naukri_schema),
  ]
  for db_path, schema in db_configs:
    with sqlite3.connect(db_path) as conn:
      cursor = conn.cursor()
      cursor.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
      )
      if cursor.fetchone() is None:
        cursor.execute(f"CREATE TABLE jobs {schema}")
        conn.commit()
        continue

      cursor.execute("PRAGMA table_info(jobs)")
      columns = cursor.fetchall()
      pk_columns = [c[1] for c in columns if c[5] > 0]
      if pk_columns == ["job_id", "date_scraped"]:
        continue

      cursor.execute("ALTER TABLE jobs RENAME TO jobs_old")
      cursor.execute(f"CREATE TABLE jobs {schema}")
      if "salary" in [c[1] for c in columns]:
        cursor.execute("""
                    INSERT OR IGNORE INTO jobs
                    (job_id, title, company, location, salary, experience, url, date_scraped)
                    SELECT job_id, title, company, location, salary, experience, url, date_scraped
                    FROM jobs_old
                """)
      else:
        cursor.execute("""
                    INSERT OR IGNORE INTO jobs
                    (job_id, title, company, location, url, date_scraped)
                    SELECT job_id, title, company, location, url, date_scraped
                    FROM jobs_old
                """)
      cursor.execute("DROP TABLE jobs_old")
      conn.commit()


def get_shared_driver():
  lock_file = os.path.join(CHROME_PROFILE, "SingletonLock")
  if os.path.exists(lock_file):
    try:
      os.remove(lock_file)
    except Exception:
      pass

  options = webdriver.ChromeOptions()
  options.add_argument(f"--user-data-dir={CHROME_PROFILE}")
  options.add_argument("--profile-directory=Default")
  options.add_argument("--headless=new")
  options.add_argument("--disable-gpu")
  options.add_argument("--no-sandbox")
  options.add_argument("--disable-dev-shm-usage")
  options.add_argument("--blink-settings=imagesEnabled=false")
  options.add_argument("--disable-blink-features=AutomationControlled")
  options.add_experimental_option("excludeSwitches", ["enable-automation"])
  options.add_argument(
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

  driver = webdriver.Chrome(
      service=Service(ChromeDriverManager().install()), options=options
  )
  driver.execute_cdp_cmd(
      "Page.addScriptToEvaluateOnNewDocument",
      {
          "source": (
              "Object.defineProperty(navigator, 'webdriver', {get: () =>"
              " undefined})"
          )
      },
  )
  return driver


def scrape_linkedin(driver, user_params):
  print(f"\n[2] Starting LinkedIn Scrape...")
  wait = WebDriverWait(driver, 8)  # Reduced from 15s/20s to speed up execution

  new_count = 0
  duplicate_count = 0
  skipped_count = 0
  scanned_count = 0
  today = datetime.now().date()

  try:
    with sqlite3.connect(user_params["DB_LINKEDIN"]) as conn:
      for kw in user_params["KEYWORDS"]:
        for loc in user_params["LOCATIONS"]:
          url = (
              "https://www.linkedin.com/jobs/search/"
              f"?keywords={kw.replace(' ', '%20')}"
              f"&location={loc.replace(' ', '%20')}"
              "&f_TPR=r604800"
          )
          driver.get(url)

          # Check for presence of job cards OR zero-result banners
          try:
            wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "h3.base-search-card__title, .base-card__title,"
                    " .jobs-search-no-results-banner, .no-results-headline",
                ))
            )
          except Exception:
            print(f"[TIMEOUT/EMPTY] {kw} | {loc}")
            continue

          time.sleep(1)
          driver.execute_script("window.scrollBy(0, 1200)")

          cards = driver.find_elements(
              By.CSS_SELECTOR, ".job-search-card, .base-card, .base-search-card"
          )
          if not cards:
            continue

          print(f"Scanning {len(cards)} cards: '{kw}' in '{loc}'...")

          batch_rows = []
          for card in cards:
            scanned_count += 1
            title, company = "", ""
            for sel in [
                "h3.base-search-card__title",
                ".base-card__title",
                "h3",
            ]:
              try:
                title = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                if title:
                  break
              except Exception:
                pass

            for sel in [
                ".base-search-card__subtitle",
                ".job-search-card__subtitle",
                "h4",
            ]:
              try:
                company = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                if company:
                  break
              except Exception:
                pass

            try:
              link = card.find_element(By.TAG_NAME, "a")
              full_url = link.get_attribute("href").split("?")[0]
              job_id = full_url.split("/")[-1].split("-")[-1]
            except Exception:
              skipped_count += 1
              continue

            try:
              card_loc = card.find_element(
                  By.CSS_SELECTOR,
                  ".job-search-card__location, .base-search-card__metadata",
              ).text.strip()
            except Exception:
              card_loc = loc

            if not title or not company or not job_id:
              skipped_count += 1
              continue

            batch_rows.append(
                (job_id, title, company, card_loc, full_url, today)
            )

          for row in batch_rows:
            cursor = conn.execute(
                """
                            INSERT OR IGNORE INTO jobs
                            (job_id, title, company, location, url, date_scraped)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                row,
            )
            if cursor.rowcount == 1:
              new_count += 1
            else:
              duplicate_count += 1
          conn.commit()

  except Exception as e:
    print(f"LinkedIn Critical Error: {e}")

  return {
    "new": new_count,
    "duplicate": duplicate_count,
    "scanned": scanned_count,
    "skipped": skipped_count,
  }


# def scrape_naukri(driver, user_params):
#   print(f"\n[3] Starting Naukri Scrape...")
#   new_count = 0
#   duplicate_count = 0
#   skipped_count = 0
#   scanned_count = 0
#   today = datetime.now().date()

#   try:
#     with sqlite3.connect(user_params["DB_NAUKRI"]) as conn:
#       for kw in user_params["KEYWORDS"]:
#         for loc in user_params["LOCATIONS"]:
#           kw_url = kw.lower().replace(" ", "-")
#           loc_url = loc.lower().replace(" ", "-")
#           url = f"https://www.naukri.com/{kw_url}-jobs-in-{loc_url}"

#           driver.get(url)
#           time.sleep(2.5)

#           jobs = driver.find_elements(By.CLASS_NAME, "srp-jobtuple-wrapper")
#           if not jobs:
#             continue

#           print(f"Scanning {len(jobs)} jobs: '{kw}' in '{loc}'...")

#           batch_rows = []
#           for job in jobs:
#             scanned_count += 1
#             try:
#               title_el = job.find_element(By.CSS_SELECTOR, "a.title")
#               title = title_el.text.strip()
#               link = title_el.get_attribute("href")
#               company = job.find_element(
#                   By.CSS_SELECTOR, ".comp-name"
#               ).text.strip()

#               meta = job.find_elements(
#                   By.CSS_SELECTOR, "span.ni-job-tuple-icon + span"
#               )
#               experience = meta[0].text.strip() if len(meta) > 0 else "N/A"
#               salary = meta[1].text.strip() if len(meta) > 1 else "N/A"
#               location = meta[2].text.strip() if len(meta) > 2 else loc

#               job_id = f"nk_{abs(hash(link))}"
#               batch_rows.append((
#                   job_id,
#                   title,
#                   company,
#                   location,
#                   salary,
#                   experience,
#                   link,
#                   today,
#               ))
#             except Exception:
#               skipped_count += 1

#           for row in batch_rows:
#             cursor = conn.execute(
#                 """
#                             INSERT OR IGNORE INTO jobs
#                             (job_id, title, company, location, salary, experience, url, date_scraped)
#                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#                             """,
#                 row,
#             )
#             if cursor.rowcount == 1:
#               new_count += 1
#             else:
#               duplicate_count += 1
#           conn.commit()

#   except Exception as e:
#     print(f"Naukri Critical Error: {e}")

#   return {
#     "new": new_count,
#     "duplicate": duplicate_count,
#     "scanned": scanned_count,
#     "skipped": skipped_count,
#   }

def scrape_naukri(driver, user_params):
  print(f"\n[3] Starting Naukri Scrape...")
  new_count = 0
  duplicate_count = 0
  skipped_count = 0
  scanned_count = 0
  today = datetime.now().date()

  wait = WebDriverWait(driver, 10)

  try:
    with sqlite3.connect(user_params["DB_NAUKRI"]) as conn:
      for kw in user_params["KEYWORDS"]:
        for loc in user_params["LOCATIONS"]:
          # Clean URL formatting using query parameters
          encoded_kw = urllib.parse.quote(kw)
          # Map multi-word location variants to standard city names recognized by Naukri
          loc_clean = loc
          if "Bangalore" in loc or "Bengaluru" in loc:
            loc_clean = "Bangalore/Bengaluru"

          encoded_loc = urllib.parse.quote(loc_clean)
          kw_slug = (
              kw.lower()
              .replace(" ", "-")
              .replace("/", "-")
              .replace("&", "and")
          )

          url = f"https://www.naukri.com/{kw_slug}-jobs?k={encoded_kw}&l={encoded_loc}"
          driver.get(url)

          # Wait for job tuples or zero-results container to render
          try:
            wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    ".srp-jobtuple-wrapper, .cust-job-tuple, [data-job-id],"
                    " .no-result-container",
                ))
            )
          except Exception:
            print(f"[NAUKRI TIMEOUT/EMPTY] {kw} | {loc}")
            continue

          # Scroll to trigger lazy loading of cards
          driver.execute_script("window.scrollBy(0, 1000);")
          time.sleep(1.5)

          # Match both legacy and modern Naukri card selectors
          jobs = driver.find_elements(
              By.CSS_SELECTOR,
              ".srp-jobtuple-wrapper, .cust-job-tuple, [data-job-id]",
          )
          if not jobs:
            continue

          print(f"Scanning {len(jobs)} jobs: '{kw}' in '{loc}'...")

          batch_rows = []
          for job in jobs:
            scanned_count += 1
            try:
              title_el = None
              for sel in ["a.title", ".title a", "a[class*='title']"]:
                try:
                  title_el = job.find_element(By.CSS_SELECTOR, sel)
                  if title_el:
                    break
                except Exception:
                  pass

              if not title_el:
                skipped_count += 1
                continue

              title = title_el.text.strip()
              link = title_el.get_attribute("href")
              if not link:
                skipped_count += 1
                continue

              # Company Name
              company = "N/A"
              for sel in [
                  ".comp-name",
                  "a.comp-name",
                  ".comp-name-link",
                  "a[class*='comp-name']",
              ]:
                try:
                  company = job.find_element(By.CSS_SELECTOR, sel).text.strip()
                  if company:
                    break
                except Exception:
                  pass

              # Experience, Salary, Location metadata
              meta = job.find_elements(
                  By.CSS_SELECTOR,
                  "span.ni-job-tuple-icon + span, .exp-wrap span,"
                  " .sal-wrap span, .loc-wrap span",
              )
              experience = (
                  meta[0].text.strip()
                  if len(meta) > 0 and meta[0].text.strip()
                  else "N/A"
              )
              salary = (
                  meta[1].text.strip()
                  if len(meta) > 1 and meta[1].text.strip()
                  else "Not Disclosed"
              )
              location = (
                  meta[2].text.strip()
                  if len(meta) > 2 and meta[2].text.strip()
                  else loc
              )

              job_id = f"nk_{abs(hash(link))}"
              batch_rows.append((
                  job_id,
                  title,
                  company,
                  location,
                  salary,
                  experience,
                  link,
                  today,
              ))
            except Exception:
              skipped_count += 1

          for row in batch_rows:
            cursor = conn.execute(
                """
                            INSERT OR IGNORE INTO jobs
                            (job_id, title, company, location, salary, experience, url, date_scraped)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                row,
            )
            if cursor.rowcount == 1:
              new_count += 1
            else:
              duplicate_count += 1
          conn.commit()

  except Exception as e:
    print(f"Naukri Critical Error: {e}")

  print(
      f"Naukri Summary   -> Scanned: {scanned_count} | New: {new_count} |"
      f" Dup: {duplicate_count}"
  )
  return {
      "new": new_count,
      "duplicate": duplicate_count,
      "scanned": scanned_count,
      "skipped": skipped_count,
  }

def generate_email_chart(db_li, db_nk):
  """Generates a styled 14-day posting trend image buffer for email embedding."""
  try:
    with sqlite3.connect(db_li) as conn_l, sqlite3.connect(db_nk) as conn_n:
      df_l = pd.read_sql(
          "SELECT date_scraped, COUNT(*) as cnt FROM jobs GROUP BY date_scraped"
          " ORDER BY date_scraped DESC LIMIT 14",
          conn_l,
      )
      df_n = pd.read_sql(
          "SELECT date_scraped, COUNT(*) as cnt FROM jobs GROUP BY date_scraped"
          " ORDER BY date_scraped DESC LIMIT 14",
          conn_n,
      )

    df_l["date_scraped"] = pd.to_datetime(df_l["date_scraped"])
    df_n["date_scraped"] = pd.to_datetime(df_n["date_scraped"])
    df_l = df_l.sort_values("date_scraped")
    df_n = df_n.sort_values("date_scraped")

    fig, ax = plt.subplots(figsize=(7.5, 3), dpi=160)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafbfc")

    if not df_l.empty:
      ax.plot(
          df_l["date_scraped"].dt.strftime("%d %b"),
          df_l["cnt"],
          marker="o",
          linewidth=2.2,
          color="#0a66c2",
          label="LinkedIn",
      )
    if not df_n.empty:
      ax.plot(
          df_n["date_scraped"].dt.strftime("%d %b"),
          df_n["cnt"],
          marker="s",
          linewidth=2.2,
          color="#0284c7",
          label="Naukri",
      )

    ax.set_title(
        "Job Inflow Trend (Last 14 Days)",
        fontsize=11,
        fontweight="bold",
        color="#0f172a",
        pad=10,
    )
    ax.tick_params(axis="x", rotation=30, labelsize=8, colors="#475569")
    ax.tick_params(axis="y", labelsize=8, colors="#475569")
    ax.grid(True, linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=8)

    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
  except Exception as e:
    print(f"Chart generation error: {e}")
    return None


def generate_report_and_mail(
    user_name, user_params, linkedin_stats, naukri_stats
):
  print(f"\n[4] Generating CSV Reports & HTML Email for {user_name}...")
  today = datetime.now().date()

  try:
    with (
        sqlite3.connect(user_params["DB_LINKEDIN"]) as conn_l,
        sqlite3.connect(user_params["DB_NAUKRI"]) as conn_n,
    ):
      df_l = pd.read_sql(
          f"SELECT * FROM jobs WHERE date_scraped='{today}' ORDER BY company,"
          " title",
          conn_l,
      )
      df_n = pd.read_sql(
          f"SELECT * FROM jobs WHERE date_scraped='{today}' ORDER BY company,"
          " title",
          conn_n,
      )
      total_li = pd.read_sql("SELECT COUNT(*) cnt FROM jobs", conn_l)["cnt"][0]
      total_nk = pd.read_sql("SELECT COUNT(*) cnt FROM jobs", conn_n)["cnt"][0]

    summary_df = pd.DataFrame([
        {
            "Source": "LinkedIn",
            "Scanned": linkedin_stats["scanned"],
            "New": linkedin_stats["new"],
            "Duplicate": linkedin_stats["duplicate"],
            "Skipped": linkedin_stats["skipped"],
            "Today Total": len(df_l),
            "Historical Total": total_li,
        },
        {
            "Source": "Naukri",
            "Scanned": naukri_stats["scanned"],
            "New": naukri_stats["new"],
            "Duplicate": naukri_stats["duplicate"],
            "Skipped": naukri_stats["skipped"],
            "Today Total": len(df_n),
            "Historical Total": total_nk,
        },
    ])

    summary_csv = f"Job_Summary_{user_name}_{today}.csv"
    li_csv = f"Job_Report_LinkedIn_{user_name}_{today}.csv"
    nk_csv = f"Job_Report_Naukri_{user_name}_{today}.csv"

    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    df_l.to_csv(li_csv, index=False, encoding="utf-8-sig")
    df_n.to_csv(nk_csv, index=False, encoding="utf-8-sig")

    combined_today = pd.concat([
        df_l[["title", "company", "location", "url"]].assign(Source="LinkedIn"),
        df_n[["title", "company", "location", "url"]].assign(Source="Naukri"),
    ]).head(10)

    preview_rows = ""
    for _, r in combined_today.iterrows():
      badge_color = "#0a66c2" if r["Source"] == "LinkedIn" else "#0284c7"
      preview_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 14px; font-weight: 600; color: #1e293b;">{r['title']}</td>
                <td style="padding: 10px 14px; color: #475569;">{r['company']}</td>
                <td style="padding: 10px 14px; color: #475569;">{r['location']}</td>
                <td style="padding: 10px 14px;"><span style="background: {badge_color}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{r['Source']}</span></td>
                <td style="padding: 10px 14px;"><a href="{r['url']}" style="background-color: #0284c7; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; display: inline-block;">Apply</a></td>
            </tr>
            """

    # HTML Body with embedded CID chart
    html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; padding: 20px; margin: 0;">
            <div style="max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                <div style="background: linear-gradient(135deg, #0f172a, #0284c7); padding: 26px; color: #ffffff;">
                    <h1 style="margin: 0; font-size: 22px;">Daily Job Intelligence Report</h1>
                    <p style="margin: 6px 0 0 0; opacity: 0.85; font-size: 14px;">Candidate: <strong>{user_name}</strong> | Date: {today}</p>
                </div>

                <!-- KPI Metric Badges -->
                <div style="display: flex; gap: 12px; padding: 18px 24px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                        <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">New Today</span>
                        <div style="font-size: 22px; font-weight: 700; color: #16a34a; margin-top: 4px;">+{linkedin_stats['new'] + naukri_stats['new']}</div>
                    </div>
                    <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                        <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Cards Scanned</span>
                        <div style="font-size: 22px; font-weight: 700; color: #0284c7; margin-top: 4px;">{linkedin_stats['scanned'] + naukri_stats['scanned']}</div>
                    </div>
                    <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                        <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Total In Repository</span>
                        <div style="font-size: 22px; font-weight: 700; color: #334155; margin-top: 4px;">{total_li + total_nk:,}</div>
                    </div>
                </div>

                <div style="padding: 24px;">
                    <!-- Option 2: Embedded Visualization Trend Chart -->
                    <h3 style="margin-top: 0; color: #0f172a; font-size: 16px;">14-Day Inflow Trends</h3>
                    <div style="text-align: center; margin-bottom: 24px;">
                        <img src="cid:trend_chart" style="width: 100%; max-width: 750px; border-radius: 8px; border: 1px solid #e2e8f0;" alt="Hiring Inflow Chart" />
                    </div>

                    <!-- Option 1: Source Breakdown Table -->
                    <h3 style="color: #0f172a; font-size: 16px;">Execution Summary</h3>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; margin-bottom: 24px;">
                        <thead>
                            <tr style="background: #f8fafc; color: #475569; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 10px;">Platform</th>
                                <th style="padding: 10px;">Scanned</th>
                                <th style="padding: 10px;">New</th>
                                <th style="padding: 10px;">Duplicates</th>
                                <th style="padding: 10px;">Skipped</th>
                                <th style="padding: 10px;">Today Total</th>
                                <th style="padding: 10px;">Historical Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="border-bottom: 1px solid #e2e8f0;">
                                <td style="padding: 10px; font-weight: 600;">LinkedIn</td>
                                <td style="padding: 10px;">{linkedin_stats['scanned']}</td>
                                <td style="padding: 10px; color: #16a34a; font-weight: 700;">+{linkedin_stats['new']}</td>
                                <td style="padding: 10px;">{linkedin_stats['duplicate']}</td>
                                <td style="padding: 10px;">{linkedin_stats['skipped']}</td>
                                <td style="padding: 10px;">{len(df_l)}</td>
                                <td style="padding: 10px;">{total_li:,}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #e2e8f0;">
                                <td style="padding: 10px; font-weight: 600;">Naukri</td>
                                <td style="padding: 10px;">{naukri_stats['scanned']}</td>
                                <td style="padding: 10px; color: #16a34a; font-weight: 700;">+{naukri_stats['new']}</td>
                                <td style="padding: 10px;">{naukri_stats['duplicate']}</td>
                                <td style="padding: 10px;">{naukri_stats['skipped']}</td>
                                <td style="padding: 10px;">{len(df_n)}</td>
                                <td style="padding: 10px;">{total_nk:,}</td>
                            </tr>
                        </tbody>
                    </table>

                    <h3 style="color: #0f172a; font-size: 16px;">Top 10 New Postings</h3>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
                        <thead>
                            <tr style="background: #f8fafc; color: #475569; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 10px 14px;">Role</th>
                                <th style="padding: 10px 14px;">Company</th>
                                <th style="padding: 10px 14px;">Location</th>
                                <th style="padding: 10px 14px;">Source</th>
                                <th style="padding: 10px 14px;">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {preview_rows}
                        </tbody>
                    </table>
                    <p style="font-size: 12px; color: #64748b; margin-top: 18px;">Detailed CSV data files are attached below.</p>
                </div>
            </div>
        </body>
        </html>
        """

    # Build MIME Structure with Related Image & Attachments
    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = (
        f"Job Intelligence Daily Digest - {user_name} ({today})"
    )
    msg_root["From"] = user_params["GMAIL_USER"]
    msg_root["To"] = user_params["GMAIL_USER"]

    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)
    msg_alt.attach(MIMEText(html_body, "html"))

    # Generate & Attach Inline Chart Image
    chart_png = generate_email_chart(
        user_params["DB_LINKEDIN"], user_params["DB_NAUKRI"]
    )
    if chart_png:
      img = MIMEImage(chart_png, "png")
      img.add_header("Content-ID", "<trend_chart>")
      img.add_header("Content-Disposition", "inline", filename="trend.png")
      msg_root.attach(img)

    # Attach CSV Files
    for filepath in [summary_csv, li_csv, nk_csv]:
      if os.path.exists(filepath):
        with open(filepath, "rb") as f:
          part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
          part["Content-Disposition"] = (
              f'attachment; filename="{os.path.basename(filepath)}"'
          )
          msg_root.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
      smtp.login(user_params["GMAIL_USER"], user_params["GMAIL_PASS"])
      smtp.send_message(msg_root)

    print(f"Report & Email dispatched successfully for {user_name}.")

  except Exception as e:
    print(f"Error in reporting/email for {user_name}: {e}")


def run_full_job_intelligence_suite():
  start_time = datetime.now()
  today = start_time.date()  # Bug fix

  print("\n" + "=" * 80)
  print("JOB INTELLIGENCE AUTOMATION PIPELINE")
  print(f"Pipeline Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
  print("=" * 80)

  overall_summary = []

  for idx, (name, params) in enumerate(users_config.items(), start=1):
    print(f"\n>>> Running Candidate {idx}/{len(users_config)}: {name} <<<")
    driver = None
    user_start = datetime.now()

    try:
      init_dbs(params)
      driver = get_shared_driver()

      li_stats = scrape_linkedin(driver, params)
      nk_stats = scrape_naukri(driver, params)

      generate_report_and_mail(name, params, li_stats, nk_stats)

      runtime = datetime.now() - user_start
      overall_summary.append({
          "User": name,
          "LI New": li_stats["new"],
          "LI Dup": li_stats["duplicate"],
          "LI Scan": li_stats["scanned"],
          "NK New": nk_stats["new"],
          "NK Dup": nk_stats["duplicate"],
          "NK Scan": nk_stats["scanned"],
          "Status": "SUCCESS",
          "Duration": str(runtime).split(".")[0],
      })
    except Exception as e:
      print(f"Failed execution for user {name}: {e}")
      overall_summary.append({
          "User": name,
          "LI New": 0,
          "LI Dup": 0,
          "LI Scan": 0,
          "NK New": 0,
          "NK Dup": 0,
          "NK Scan": 0,
          "Status": "FAILED",
          "Duration": "-",
      })
    finally:
      if driver:
        try:
          driver.quit()
        except Exception:
          pass
      time.sleep(3)

  end_time = datetime.now()
  summary_df = pd.DataFrame(overall_summary)
  pipeline_report_csv = f"Pipeline_Summary_{today}.csv"
  summary_df.to_csv(pipeline_report_csv, index=False, encoding="utf-8-sig")

  print("\n" + "=" * 80)
  print("FINAL PIPELINE SUMMARY")
  print("=" * 80)
  print(summary_df.to_string(index=False))
  print(f"\nPipeline log saved to: {pipeline_report_csv}")
  print(f"Total Duration: {end_time - start_time}")


if __name__ == "__main__":
  run_full_job_intelligence_suite()