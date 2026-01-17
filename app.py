import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse

# --- DATABASE SETUP (Google Sheets) ---
# We replace sqlite3 with a Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)


def get_bookmarks():
    """Read data from Google Sheets"""
    return conn.read(worksheet="bookmarks", ttl=0)  # ttl=0 ensures we get fresh data


# --- HELPER FUNCTIONS ---
def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


# --- APP UI ---
st.set_page_config(page_title="My Cyber Research Bookmarks", layout="wide")
st.title("🔖 Personal Bookmark Manager")

# Sidebar for adding new links
with st.sidebar:
    st.header("Add New Bookmark")
    new_title = st.text_input("Title")
    new_url = st.text_input("URL")
    new_cat = st.selectbox(
        "Category",
        [
            "Offensive Security",
            "Finance",
            "Real Estate",
            "YouTube",
            "Tools",
            "Articles",
            "Documentation",
        ],
    )
    new_tags = st.text_input("Tags (comma-separated)")
    new_notes = st.text_area("Notes (optional)")

    if st.button("💾 Save Bookmark", type="primary"):
        if new_url and new_title:
            if not validate_url(new_url):
                st.error("⚠️ Invalid URL")
            else:
                # 1. Get existing data
                existing_data = get_bookmarks()

                # 2. Create new row
                new_row = pd.DataFrame(
                    [
                        {
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "title": new_title,
                            "url": new_url,
                            "category": new_cat,
                            "tags": new_tags,
                            "notes": new_notes,
                        }
                    ]
                )

                # 3. Combine and Update
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(worksheet="bookmarks", data=updated_df)

                st.success("✅ Saved to Google Sheets!")
                st.rerun()

# --- MAIN VIEW ---
df = get_bookmarks()

# Search and Filter
search_query = st.text_input("🔍 Search bookmarks...")
if search_query:
    df = df[
        df.apply(
            lambda row: search_query.lower() in row.astype(str).str.lower().values,
            axis=1,
        )
    ]

# Display logic remains similar to your original code
if not df.empty:
    for index, row in df.iloc[::-1].iterrows():  # Show newest first
        with st.container():
            st.markdown(f"### [{row['title']}]({row['url']})")
            st.caption(f"📅 {row['date']} | Category: {row['category']}")
            if row["tags"]:
                st.markdown(f"🏷️ `{row['tags']}`")
            st.divider()
