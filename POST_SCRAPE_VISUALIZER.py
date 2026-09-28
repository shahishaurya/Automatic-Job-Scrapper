import io
import os
import smtplib
import socket
import sqlite3
import subprocess
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
USERS_CONFIG = {
    "user1": {
        "DB_LINKEDIN": "linkedin_user1.db",
        "DB_NAUKRI": "naukri_user1.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
    },
    "user2": {
        "DB_LINKEDIN": "linkedin_user2.db",
        "DB_NAUKRI": "naukri_user2.db",
        "GMAIL_USER": "user@gmail.com",
        "GMAIL_PASS": "enter gmail passkey",
    }
}

# -----------------------------------------------------------------------------
# Option 2: Generate 14-Day In-Memory Trend Chart
# -----------------------------------------------------------------------------
def generate_trend_chart_bytes(db_li, db_nk, user_name):
    """Queries SQLite databases and generates an in-memory 14-day trend image buffer."""
    try:
        with sqlite3.connect(db_li) as conn_l, sqlite3.connect(db_nk) as conn_n:
            df_l = pd.read_sql(
                """
                SELECT date_scraped, COUNT(*) as cnt 
                FROM jobs 
                GROUP BY date_scraped 
                ORDER BY date_scraped DESC LIMIT 14
                """, conn_l
            )
            df_n = pd.read_sql(
                """
                SELECT date_scraped, COUNT(*) as cnt 
                FROM jobs 
                GROUP BY date_scraped 
                ORDER BY date_scraped DESC LIMIT 14
                """, conn_n
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
                markersize=4,
                linewidth=2.2,
                color="#0a66c2",
                label="LinkedIn Inflow"
            )
        if not df_n.empty:
            ax.plot(
                df_n["date_scraped"].dt.strftime("%d %b"),
                df_n["cnt"],
                marker="s",
                markersize=4,
                linewidth=2.2,
                color="#0284c7",
                label="Naukri Inflow"
            )

        ax.set_title(f"14-Day Job Inflow Dynamics — {user_name}", fontsize=11, fontweight="bold", color="#0f172a", pad=12)
        ax.tick_params(axis="x", rotation=30, labelsize=8, colors="#475569")
        ax.tick_params(axis="y", labelsize=8, colors="#475569")
        ax.grid(True, linestyle="--", alpha=0.5, color="#cbd5e1")
        
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#cbd5e1")

        ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=8, loc="upper left")
        fig.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"Error creating trend chart for {user_name}: {e}")
        return None

# -----------------------------------------------------------------------------
# Process & Email Dispatch
# -----------------------------------------------------------------------------
def process_user_report(user_name, params):
    today = datetime.now().date()
    db_li = params["DB_LINKEDIN"]
    db_nk = params["DB_NAUKRI"]

    if not os.path.exists(db_li) or not os.path.exists(db_nk):
        print(f"[SKIP] Missing database for {user_name}")
        return

    with sqlite3.connect(db_li) as conn_l, sqlite3.connect(db_nk) as conn_n:
        df_l_today = pd.read_sql(f"SELECT * FROM jobs WHERE date_scraped='{today}' ORDER BY company, title", conn_l)
        df_n_today = pd.read_sql(f"SELECT * FROM jobs WHERE date_scraped='{today}' ORDER BY company, title", conn_n)
        total_li = pd.read_sql("SELECT COUNT(*) cnt FROM jobs", conn_l)["cnt"][0]
        total_nk = pd.read_sql("SELECT COUNT(*) cnt FROM jobs", conn_n)["cnt"][0]

    # Generate Export CSVs
    li_csv = f"Job_Report_LinkedIn_{user_name}_{today}.csv"
    nk_csv = f"Job_Report_Naukri_{user_name}_{today}.csv"
    df_l_today.to_csv(li_csv, index=False, encoding="utf-8-sig")
    df_n_today.to_csv(nk_csv, index=False, encoding="utf-8-sig")

    # Top 10 Opportunities Preview
    preview_df = pd.concat([
        df_l_today[["title", "company", "location", "url"]].assign(Source="LinkedIn"),
        df_n_today[["title", "company", "location", "url"]].assign(Source="Naukri")
    ]).head(10)

    preview_rows = ""
    for _, r in preview_df.iterrows():
        badge_bg = "#0a66c2" if r["Source"] == "LinkedIn" else "#0284c7"
        preview_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px 14px; font-weight: 600; color: #1e293b;">{r['title']}</td>
            <td style="padding: 10px 14px; color: #475569;">{r['company']}</td>
            <td style="padding: 10px 14px; color: #475569;">{r['location']}</td>
            <td style="padding: 10px 14px;"><span style="background: {badge_bg}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{r['Source']}</span></td>
            <td style="padding: 10px 14px;"><a href="{r['url']}" style="background-color: #0284c7; color: white; padding: 5px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: 500;">Apply</a></td>
        </tr>
        """

    # Responsive HTML Template with In-Email CID Chart
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; padding: 20px; margin: 0;">
        <div style="max-width: 780px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            <div style="background: linear-gradient(135deg, #0f172a, #0369a1); padding: 26px; color: #ffffff;">
                <h2 style="margin: 0; font-size: 22px;">Daily Job Intelligence Report</h2>
                <p style="margin: 6px 0 0 0; opacity: 0.85; font-size: 14px;">Candidate: <strong>{user_name}</strong> | Date: {today}</p>
            </div>

            <!-- KPI Badges -->
            <div style="display: flex; gap: 12px; padding: 18px 24px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                    <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">New Today</span>
                    <div style="font-size: 22px; font-weight: 700; color: #16a34a; margin-top: 4px;">+{len(df_l_today) + len(df_n_today)}</div>
                </div>
                <div style="flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                    <span style="font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase;">Total Historical</span>
                    <div style="font-size: 22px; font-weight: 700; color: #334155; margin-top: 4px;">{total_li + total_nk:,}</div>
                </div>
            </div>

            <div style="padding: 24px;">
                <h3 style="margin-top: 0; color: #0f172a; font-size: 16px;">14-Day Inflow Trends</h3>
                <div style="text-align: center; margin-bottom: 24px;">
                    <img src="cid:trend_chart" style="width: 100%; max-width: 730px; border-radius: 8px; border: 1px solid #e2e8f0;" alt="Trend Chart" />
                </div>

                <h3 style="color: #0f172a; font-size: 16px;">Top Opportunities Today</h3>
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
                    <thead>
                        <tr style="background: #f8fafc; color: #475569; border-bottom: 2px solid #e2e8f0;">
                            <th style="padding: 10px 14px;">Role</th>
                            <th style="padding: 10px 14px;">Company</th>
                            <th style="padding: 10px 14px;">Location</th>
                            <th style="padding: 10px 14px;">Platform</th>
                            <th style="padding: 10px 14px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {preview_rows}
                    </tbody>
                </table>
                <p style="font-size: 12px; color: #64748b; margin-top: 20px;">Daily CSV extracts are attached. You can also view real-time metrics on the local Streamlit dashboard (<code>localhost:8501</code>).</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = f"Job Intelligence Daily Digest - {user_name} ({today})"
    msg_root["From"] = params["GMAIL_USER"]
    msg_root["To"] = params["GMAIL_USER"]

    msg_alt = MIMEMultipart("alternative")
    msg_root.attach(msg_alt)
    msg_alt.attach(MIMEText(html_content, "html"))

    # Attach in-memory chart
    chart_bytes = generate_trend_chart_bytes(db_li, db_nk, user_name)
    if chart_bytes:
        img_part = MIMEImage(chart_bytes, "png")
        img_part.add_header("Content-ID", "<trend_chart>")
        img_part.add_header("Content-Disposition", "inline", filename="trend.png")
        msg_root.attach(img_part)

    # Attach CSVs
    for path in [li_csv, nk_csv]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                attachment = MIMEApplication(f.read(), Name=os.path.basename(path))
                attachment["Content-Disposition"] = f'attachment; filename="{os.path.basename(path)}"'
                msg_root.attach(attachment)

    # Send Email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(params["GMAIL_USER"], params["GMAIL_PASS"])
        smtp.send_message(msg_root)
    print(f"Digest email with trend chart dispatched to {user_name}")

# -----------------------------------------------------------------------------
# Option 3: Launch or Ensure Streamlit Server is Running
# -----------------------------------------------------------------------------
def ensure_dashboard_running():
    """Checks if Streamlit dashboard is already active on port 8501; launches it if not."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = sock.connect_ex(("localhost", 8501)) == 0
    sock.close()

    if not is_open:
        print("Launching Streamlit Dashboard server on port 8501...")
        subprocess.Popen(
            ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.headless=true"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
    else:
        print("Streamlit Dashboard server is already online at http://localhost:8501")

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting Post-Scrape Visualizer & Reporting Engine [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]...")
    for user, config in USERS_CONFIG.items():
        process_user_report(user, config)
    ensure_dashboard_running()
    print("Post-scrape routines completed successfully.")