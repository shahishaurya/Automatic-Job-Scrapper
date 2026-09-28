import os
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Job Intelligence Hub", page_icon="💼", layout="wide")

USER_KEYWORDS = {
    "user1": [
        "PySpark", "Python", "SQL", "Data Engineer", "AWS", "Palantir",
        "ETL", "Data Warehouse", "Data Pipeline", "Big Data", "Cloud", "Foundry"
    ],
    "user2": [
        "Data Analyst", "Power BI", "Tableau", "Excel", "SQL", "VBA",
        "Macros", "DAX", "Power Query", "Order to Cash", "Procure to Pay",
        "Billing", "Reconciliation", "Financial Data Analyst"
    ]
}

@st.cache_data(ttl=180)
def load_data(user_name):
    u = user_name.lower()
    frames = []
    if os.path.exists(f"linkedin_{u}.db"):
        with sqlite3.connect(f"linkedin_{u}.db") as conn:
            df_li = pd.read_sql("SELECT job_id, title, company, location, url, date_scraped FROM jobs", conn)
            df_li["Source"] = "LinkedIn"
            df_li["salary"] = "Not Disclosed"
            df_li["experience"] = "N/A"
            frames.append(df_li)
    if os.path.exists(f"naukri_{u}.db"):
        with sqlite3.connect(f"naukri_{u}.db") as conn:
            df_nk = pd.read_sql("SELECT job_id, title, company, location, salary, experience, url, date_scraped FROM jobs", conn)
            df_nk["Source"] = "Naukri"
            frames.append(df_nk)
            
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["date_scraped"] = pd.to_datetime(df["date_scraped"]).dt.date
    df["salary"] = df["salary"].fillna("Not Disclosed").replace("", "Not Disclosed")
    df["company"] = df["company"].fillna("Unknown")
    df["title"] = df["title"].fillna("Untitled")
    return df

st.sidebar.title("💼 Dashboard Filters")
user_select = st.sidebar.selectbox("Candidate Profile", ["Shaurya", "Kshma"])
raw_df = load_data(user_select)

if raw_df.empty:
    st.warning(f"No databases found for {user_select}.")
    st.stop()

min_d, max_d = raw_df["date_scraped"].min(), raw_df["date_scraped"].max()
date_range = st.sidebar.slider("Scraped Date Range", min_value=min_d, max_value=max_d, value=(min_d, max_d))
selected_tags = st.sidebar.multiselect("Filter by Skill Keywords", options=USER_KEYWORDS.get(user_select, []), default=[])
sources = st.sidebar.multiselect("Platforms", options=["LinkedIn", "Naukri"], default=["LinkedIn", "Naukri"])
only_disclosed_salary = st.sidebar.checkbox("Show Disclosed Salary Only", value=False)

# Filtering
filtered = raw_df[
    (raw_df["date_scraped"] >= date_range[0]) & 
    (raw_df["date_scraped"] <= date_range[1]) & 
    (raw_df["Source"].isin(sources))
]
if selected_tags:
    pattern = "|".join(selected_tags)
    filtered = filtered[filtered["title"].str.contains(pattern, case=False, na=False)]
if only_disclosed_salary:
    filtered = filtered[~filtered["salary"].str.contains("Not Disclosed|N/A", case=False)]

# Main View
st.title(f"💼 Job Intelligence Hub — {user_select}")
st.caption(f"Active window: {date_range[0]} to {date_range[1]} | Sources: {', '.join(sources)}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Matching Jobs", f"{len(filtered):,}")
m2.metric("Latest Inflow", f"{(filtered['date_scraped'] == max_d).sum():,}")
m3.metric("Hiring Companies", f"{filtered['company'].nunique():,}")
m4.metric("Bengaluru Matches", f"{filtered['location'].str.contains('Bangalore|Bengaluru', case=False, na=False).sum():,}")

# Charts
v1, v2 = st.columns([6, 4])
with v1:
    daily = filtered.groupby(["date_scraped", "Source"]).size().reset_index(name="Volume")
    fig_line = px.line(daily, x="date_scraped", y="Volume", color="Source", title="Posting Inflow Dynamics", markers=True, color_discrete_map={"LinkedIn": "#0a66c2", "Naukri": "#0284c7"})
    fig_line.update_layout(height=340, margin=dict(l=10, r=10, t=35, b=10), xaxis_title="", yaxis_title="Openings")
    st.plotly_chart(fig_line, use_container_width=True)

with v2:
    top_c = filtered["company"].value_counts().head(10).reset_index()
    top_c.columns = ["Company", "Openings"]
    fig_bar = px.bar(top_c, x="Openings", y="Company", orientation="h", title="Top 10 Hiring Companies", color="Openings", color_continuous_scale="Blues")
    fig_bar.update_layout(height=340, margin=dict(l=10, r=10, t=35, b=10), yaxis=dict(autorange="reversed"), coloraxis_showscale=False, xaxis_title="Postings", yaxis_title="")
    st.plotly_chart(fig_bar, use_container_width=True)

# Table
st.subheader("📋 Interactive Job Feed")
search_term = st.text_input("Search Roles or Companies", placeholder="Type keyword (e.g. PySpark, Palantir, Accenture)...")
table_df = filtered
if search_term:
    table_df = table_df[
        table_df["title"].str.contains(search_term, case=False, na=False) |
        table_df["company"].str.contains(search_term, case=False, na=False) |
        table_df["location"].str.contains(search_term, case=False, na=False)
    ]

st.dataframe(
    table_df[["date_scraped", "title", "company", "location", "salary", "experience", "Source", "url"]].sort_values("date_scraped", ascending=False),
    column_config={
        "url": st.column_config.LinkColumn("Action", display_text="Apply"),
        "date_scraped": st.column_config.DateColumn("Scraped Date"),
        "title": "Role Title",
        "company": "Company",
        "location": "Location",
        "salary": "Compensation",
        "experience": "Exp",
        "Source": "Source"
    },
    hide_index=True,
    use_container_width=True,
    height=450
)