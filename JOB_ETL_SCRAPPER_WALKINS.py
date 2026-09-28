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
import urllib.parse
import matplotlib
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

matplotlib.use("Agg")
import matplotlib.pyplot as plt

users_walkin_config = {
    "user1": {
        "DB_LINKEDIN": "linkedin_user1.db",
        "DB_NAUKRI": "naukri_user1.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
        "DOMAINS": [
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
        "WALKIN_MODIFIERS": [
            "Walkin",
            "Walk-in",
            "Hiring Drive",
            "Walk in Drive",
            "Interview Drive",
        ],
        "LOCATION": "Bengaluru",
    },
    "user2": {
        "DB_LINKEDIN": "linkedin_user2.db",
        "DB_NAUKRI": "naukri_user2.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
        "DOMAINS": [
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
        "WALKIN_MODIFIERS": [
            "Walkin",
            "Walk-in",
            "Hiring Drive",
            "Walk in Drive",
            "Interview Drive",
        ],
        "LOCATION": "Bengaluru",
    },
}

CHROME_PROFILE_WALKIN = os.path.join(os.getcwd(), "AutomationProfile_Walkins")


def init_walkin_dbs(user_params):
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
      conn.execute("PRAGMA journal_mode = WAL;")
      cursor = conn.cursor()
      cursor.execute(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
      )
      if cursor.fetchone() is None:
        cursor.execute(f"CREATE TABLE jobs {schema}")
        conn.commit()


def get_walkin_driver():
  lock_file = os.path.join(CHROME_PROFILE_WALKIN, "SingletonLock")
  if os.path.exists(lock_file):
    try:
      os.remove(lock_file)
    except Exception:
      pass

  options = webdriver.ChromeOptions()
  options.add_argument(f"--user-data-dir={CHROME_PROFILE_WALKIN}")
  options.add_argument("--profile-directory=Default")
  options.add_argument("--headless=new")
  options.add_argument("--disable-gpu")
  options.add_argument("--no-sandbox")
  options.add_argument("--disable-dev-shm-usage")
  options.add_argument("--remote-debugging-pipe")
  options.add_argument("--blink-settings=imagesEnabled=false")
  options.add_argument("--disable-blink-features=AutomationControlled")
  options.add_experimental_option("excludeSwitches", ["enable-automation"])
  options.add_argument(
      "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
  )

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


def is_walkin_relevant(text):
  triggers = [
      "walk-in",
      "walk in",
      "walkin",
      "hiring drive",
      "recruitment drive",
      "interview drive",
      "walk-ins",
      "walkins",
      "f2f",
      "face to face",
      "virtual drive",
  ]
  text_lower = text.lower()
  return any(t in text_lower for t in triggers)


def scrape_linkedin_walkins(driver, user_params):
  print(f"\n[1] Starting LinkedIn Walkin Scrape for Bangalore...")
  wait = WebDriverWait(driver, 8)
  new_count = 0
  duplicate_count = 0
  scanned_count = 0
  today = datetime.now().date()

  search_queries = []
  for domain in user_params["DOMAINS"]:
    search_queries.append(f"Walk-in {domain}")
    search_queries.append(f"{domain} hiring drive")

  try:
    with sqlite3.connect(user_params["DB_LINKEDIN"]) as conn:
      for query in search_queries:
        encoded_kw = urllib.parse.quote(query)
        encoded_loc = urllib.parse.quote(user_params["LOCATION"])
        url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={encoded_kw}&location={encoded_loc}&f_TPR=r604800"
        )
        driver.get(url)

        try:
          wait.until(
              EC.presence_of_element_located((
                  By.CSS_SELECTOR,
                  "h3.base-search-card__title, .base-card__title,"
                  " .jobs-search-no-results-banner, .no-results-headline",
              ))
          )
        except Exception:
          print(f"[TIMEOUT/EMPTY] {query}")
          continue

        time.sleep(1)
        driver.execute_script("window.scrollBy(0, 1000)")

        cards = driver.find_elements(
            By.CSS_SELECTOR, ".job-search-card, .base-card, .base-search-card"
        )
        if not cards:
          continue

        print(f"Scanning {len(cards)} cards: '{query}' in Bangalore...")
        batch = []
        for card in cards:
          scanned_count += 1
          title = ""
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

          company = "N/A"
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
            continue

          try:
            card_loc = card.find_element(
                By.CSS_SELECTOR,
                ".job-search-card__location, .base-search-card__metadata",
            ).text.strip()
          except Exception:
            card_loc = "Bangalore"

          # Restrict to genuine walkin/drive titles
          if not is_walkin_relevant(title):
            continue

          batch.append((job_id, title, company, card_loc, full_url, today))

        for row in batch:
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
    print(f"LinkedIn Walkins Error: {e}")

  return {
      "scanned": scanned_count,
      "new": new_count,
      "duplicate": duplicate_count,
  }


def scrape_naukri_walkins(driver, user_params):
  print(f"\n[2] Starting Naukri Walkin Scrape for Bangalore...")
  wait = WebDriverWait(driver, 8)
  new_count = 0
  duplicate_count = 0
  scanned_count = 0
  today = datetime.now().date()

  search_queries = []
  for domain in user_params["DOMAINS"]:
    search_queries.append(f"walkin {domain}")
    search_queries.append(f"{domain} drive")

  try:
    with sqlite3.connect(user_params["DB_NAUKRI"]) as conn:
      for query in search_queries:
        encoded_kw = urllib.parse.quote(query)
        url = (
            "https://www.naukri.com/walk-in-jobs-in-bengaluru"
            f"?k={encoded_kw}&l=Bangalore%2FBengaluru"
        )
        driver.get(url)

        try:
          wait.until(
              EC.presence_of_element_located((
                  By.CSS_SELECTOR,
                  ".srp-jobtuple-wrapper, .cust-job-tuple, [data-job-id],"
                  " .no-result-container",
              ))
          )
        except Exception:
          print(f"[TIMEOUT/EMPTY] {query}")
          continue

        time.sleep(1.5)
        driver.execute_script("window.scrollBy(0, 1000);")

        jobs = driver.find_elements(
            By.CSS_SELECTOR,
            ".srp-jobtuple-wrapper, .cust-job-tuple, [data-job-id]",
        )
        if not jobs:
          continue

        print(f"Scanning {len(jobs)} postings: '{query}' in Bangalore...")
        batch = []
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
              continue

            title = title_el.text.strip()
            link = title_el.get_attribute("href")
            if not link:
              continue

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

            meta = job.find_elements(
                By.CSS_SELECTOR,
                "span.ni-job-tuple-icon + span, .exp-wrap span, .sal-wrap"
                " span, .loc-wrap span",
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
                else "Bangalore"
            )

            job_id = f"nk_wk_{abs(hash(link))}"
            batch.append((
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
            continue

        for row in batch:
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
    print(f"Naukri Walkins Error: {e}")

  return {
      "scanned": scanned_count,
      "new": new_count,
      "duplicate": duplicate_count,
  }


def generate_walkin_chart(db_li, db_nk, user_name):
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

    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=160)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")

    if not df_l.empty:
      ax.plot(
          df_l["date_scraped"].dt.strftime("%d %b"),
          df_l["cnt"],
          marker="o",
          linewidth=2.2,
          color="#0a66c2",
          label="LinkedIn Walkins",
      )
    if not df_n.empty:
      ax.plot(
          df_n["date_scraped"].dt.strftime("%d %b"),
          df_n["cnt"],
          marker="s",
          linewidth=2.2,
          color="#0284c7",
          label="Naukri Walkins",
      )

    ax.set_title(
        f"Bangalore Walk-in Hiring Trends (Last 14 Days) — {user_name}",
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
    ax.legend(
        frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=8
    )

    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
  except Exception as e:
    print(f"Chart creation error: {e}")
    return None


def generate_walkin_report_and_mail(
    user_name, user_params, li_stats, nk_stats
):
  today = datetime.now().date()
  db_li = user_params["DB_LINKEDIN"]
  db_nk = user_params["DB_NAUKRI"]

  with sqlite3.connect(db_li) as conn_l, sqlite3.connect(db_nk) as conn_n:
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

  li_csv = f"Walkin_LinkedIn_{user_name}_{today}.csv"
  nk_csv = f"Walkin_Naukri_{user_name}_{today}.csv"
  df_l.to_csv(li_csv, index=False, encoding="utf-8-sig")
  df_n.to_csv(nk_csv, index=False, encoding="utf-8-sig")

  combined_walkins = pd.concat([
      df_l[["title", "company", "location", "url"]].assign(Source="LinkedIn"),
      df_n[["title", "company", "location", "url"]].assign(Source="Naukri"),
  ])

  preview_rows = ""
  for _, r in combined_walkins.head(15).iterrows():
    badge_bg = "#0a66c2" if r["Source"] == "LinkedIn" else "#0284c7"
    preview_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px 14px; font-weight: 600; color: #1e293b;">{r['title']}</td>
            <td style="padding: 10px 14px; color: #475569;">{r['company']}</td>
            <td style="padding: 10px 14px; color: #475569;">{r['location']}</td>
            <td style="padding: 10px 14px;"><span style="background: {badge_bg}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{r['Source']}</span></td>
            <td style="padding: 10px 14px;"><a href="{r['url']}" style="background-color: #0284c7; color: white; padding: 5px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold;">View Drive</a></td>
        </tr>
        """

  html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f1f5f9; padding: 20px; margin: 0;">
        <div style="max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            <div style="background: linear-gradient(135deg, #047857, #0284c7); padding: 26px; color: #ffffff;">
                <h1 style="margin: 0; font-size: 22px;">📍 Bangalore Walk-in Drives Digest</h1>
                <p style="margin: 6px 0 0 0; opacity: 0.85; font-size: 14px;">Candidate: <strong>{user_name}</strong> | Date: {today}</p>
            </div>

            <div style="display: flex; gap: 12px; padding: 18px 24px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                    <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Drives Found Today</span>
                    <div style="font-size: 22px; font-weight: 700; color: #16a34a; margin-top: 4px;">+{len(df_l) + len(df_n)}</div>
                </div>
                <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                    <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Active Drives</span>
                    <div style="font-size: 22px; font-weight: 700; color: #0284c7; margin-top: 4px;">{total_li + total_nk:,}</div>
                </div>
            </div>

            <div style="padding: 24px;">
                <h3 style="margin-top: 0; color: #0f172a; font-size: 16px;">Bangalore Walk-in Frequency</h3>
                <div style="text-align: center; margin-bottom: 24px;">
                    <img src="cid:trend_chart" style="width: 100%; max-width: 750px; border-radius: 8px; border: 1px solid #e2e8f0;" alt="Walk-in Chart" />
                </div>

                <h3 style="color: #0f172a; font-size: 16px;">Top Immediate Walk-ins (Bangalore)</h3>
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
                    <thead>
                        <tr style="background: #f8fafc; color: #475569; border-bottom: 2px solid #e2e8f0;">
                            <th style="padding: 10px 14px;">Drive Title</th>
                            <th style="padding: 10px 14px;">Company</th>
                            <th style="padding: 10px 14px;">Location</th>
                            <th style="padding: 10px 14px;">Source</th>
                            <th style="padding: 10px 14px;">Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        {preview_rows if preview_rows else "<tr><td colspan='5' style='padding: 20px; text-align: center; color: #64748b;'>No new walk-in drives found today.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

  msg_root = MIMEMultipart("related")
  msg_root["Subject"] = (
      f"📍 Bangalore Walk-in Drives Digest - {user_name} ({today})"
  )
  msg_root["From"] = user_params["GMAIL_USER"]
  msg_root["To"] = user_params["GMAIL_USER"]

  msg_alt = MIMEMultipart("alternative")
  msg_root.attach(msg_alt)
  msg_alt.attach(MIMEText(html_content, "html"))

  chart_bytes = generate_walkin_chart(db_li, db_nk, user_name)
  if chart_bytes:
    img = MIMEImage(chart_bytes, "png")
    img.add_header("Content-ID", "<trend_chart>")
    img.add_header("Content-Disposition", "inline", filename="trend.png")
    msg_root.attach(img)

  for fpath in [li_csv, nk_csv]:
    if os.path.exists(fpath):
      with open(fpath, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(fpath))
        part["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(fpath)}"'
        )
        msg_root.attach(part)

  with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(user_params["GMAIL_USER"], user_params["GMAIL_PASS"])
    smtp.send_message(msg_root)
  print(f"Walk-in digest email dispatched to {user_name}.")


def run_walkin_pipeline():
  start_time = datetime.now()
  print("\n" + "=" * 80)
  print("BANGALORE WALK-IN DRIVES AUTOMATION PIPELINE")
  print(f"Pipeline Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
  print("=" * 80)

  for name, params in users_walkin_config.items():
    print(f"\n>>> Running Walk-in Tracker for: {name} <<<")
    init_walkin_dbs(params)
    driver = None
    try:
      driver = get_walkin_driver()
      li_stats = scrape_linkedin_walkins(driver, params)
      nk_stats = scrape_naukri_walkins(driver, params)
      generate_walkin_report_and_mail(name, params, li_stats, nk_stats)
    except Exception as e:
      print(f"Walkin run error for {name}: {e}")
    finally:
      if driver:
        try:
          driver.quit()
        except Exception:
          pass
      time.sleep(2)

  print(
      f"\nWalk-in Pipeline Completed in {datetime.now() - start_time} seconds."
  )


if __name__ == "__main__":
  run_walkin_pipeline()