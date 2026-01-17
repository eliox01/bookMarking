import streamlit as st
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- APP CONFIG ---
st.set_page_config(page_title="My Cyber Research Bookmarks", layout="wide")


# --- DATABASE CONNECTION ---
@st.cache_resource
def init_gsheets_connection():
    """Initialize Google Sheets connection using gspread directly"""
    try:
        # Define the scope
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]

        # Get credentials from Streamlit secrets
        creds_dict = {
            "type": st.secrets["connections"]["gsheets"]["service_account"]["type"],
            "project_id": st.secrets["connections"]["gsheets"]["service_account"][
                "project_id"
            ],
            "private_key_id": st.secrets["connections"]["gsheets"]["service_account"][
                "private_key_id"
            ],
            "private_key": st.secrets["connections"]["gsheets"]["service_account"][
                "private_key"
            ],
            "client_email": st.secrets["connections"]["gsheets"]["service_account"][
                "client_email"
            ],
            "client_id": st.secrets["connections"]["gsheets"]["service_account"][
                "client_id"
            ],
            "auth_uri": st.secrets["connections"]["gsheets"]["service_account"][
                "auth_uri"
            ],
            "token_uri": st.secrets["connections"]["gsheets"]["service_account"][
                "token_uri"
            ],
            "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"][
                "service_account"
            ]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["connections"]["gsheets"][
                "service_account"
            ]["client_x509_cert_url"],
        }

        # Create credentials
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, scope
        )

        # Authorize and connect
        client = gspread.authorize(credentials)

        # Open the spreadsheet
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_key(spreadsheet_id)

        return sheet

    except Exception as e:
        st.error(f"Connection initialization failed: {e}")
        return None


def get_bookmarks():
    """Read data from Google Sheets"""
    try:
        sheet = init_gsheets_connection()
        if sheet is None:
            return pd.DataFrame(
                columns=["date", "title", "url", "category", "tags", "notes"]
            )

        # Get the 'main' worksheet
        worksheet = sheet.worksheet("main")

        # Get all values
        data = worksheet.get_all_records()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Ensure all required columns exist
        required_columns = ["date", "title", "url", "category", "tags", "notes"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = ""

        return df

    except Exception as e:
        error_msg = str(e)

        # Only show detailed errors in main area
        if "sidebar" not in st.session_state.get("current_context", ""):
            with st.expander("🔍 Connection Error Details", expanded=True):
                st.error(f"**Error**: {error_msg}")

                if "permission" in error_msg.lower() or "403" in error_msg:
                    st.warning("🔒 **Permission Issue**")
                    st.markdown(
                        """
                    Share your Google Sheet with:
                    ```
                    bookmark@n8n-credentials-482321.iam.gserviceaccount.com
                    ```
                    Grant **Editor** access!
                    """
                    )
                elif (
                    "not found" in error_msg.lower() or "worksheet" in error_msg.lower()
                ):
                    st.warning("📝 **Worksheet Issue**")
                    st.markdown(
                        "Make sure your sheet has a tab named exactly: `main` (lowercase)"
                    )
                else:
                    st.info("💡 **Checklist**:")
                    st.markdown(
                        """
                    1. Share sheet with service account (Editor access)
                    2. Tab name is exactly 'main'
                    3. First row has headers: date, title, url, category, tags, notes
                    """
                    )

        return pd.DataFrame(
            columns=["date", "title", "url", "category", "tags", "notes"]
        )


def save_bookmark(new_row_data):
    """Save a new bookmark to Google Sheets"""
    try:
        sheet = init_gsheets_connection()
        if sheet is None:
            return False, "Failed to connect to Google Sheets"

        worksheet = sheet.worksheet("main")

        # Append the new row
        worksheet.append_row(
            [
                new_row_data["date"],
                new_row_data["title"],
                new_row_data["url"],
                new_row_data["category"],
                new_row_data["tags"],
                new_row_data["notes"],
            ]
        )

        return True, "Bookmark saved successfully!"

    except Exception as e:
        return False, f"Error saving: {str(e)}"


def validate_url(url):
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


# --- UI TITLE ---
st.title("🔖 Personal Bookmark Manager")

# --- SIDEBAR: ADD NEW BOOKMARK ---
with st.sidebar:
    st.session_state["current_context"] = "sidebar"
    st.header("Add New Bookmark")

    new_title = st.text_input("Title", placeholder="e.g., Sliver C2 Documentation")
    new_url = st.text_input("URL", placeholder="https://...")
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
    new_tags = st.text_input(
        "Tags (comma-separated)", placeholder="c2, redteam, golang"
    )
    new_notes = st.text_area("Notes (optional)")

    if st.button("💾 Save Bookmark", type="primary"):
        if new_url and new_title:
            if not validate_url(new_url):
                st.error("⚠️ Please enter a valid URL (include http/https)")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    new_row_data = {
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "title": new_title,
                        "url": new_url,
                        "category": new_cat,
                        "tags": new_tags,
                        "notes": new_notes,
                    }

                    success, message = save_bookmark(new_row_data)

                    if success:
                        st.success("✅ " + message)
                        st.balloons()
                        # Clear cache and reload
                        st.cache_resource.clear()
                        st.rerun()
                    else:
                        st.error("❌ " + message)
        else:
            st.error("⚠️ Title and URL are required!")

    st.divider()

    # Get stats
    try:
        df_stats = get_bookmarks()
        st.metric("Total Bookmarks", len(df_stats))
    except:
        st.metric("Total Bookmarks", "0")

# --- MAIN VIEW: RESEARCH FEED ---
st.session_state["current_context"] = "main"
st.subheader("📚 Your Research Feed")

df = get_bookmarks()

# Search functionality
search_query = st.text_input(
    "🔍 Search bookmarks...", placeholder="Search by title, tags, or notes..."
)

if not df.empty and len(df) > 0:
    # Reverse to show newest first
    display_df = df.iloc[::-1].copy()

    if search_query:
        # Simple string matching across all columns
        mask = display_df.apply(
            lambda row: row.astype(str).str.contains(search_query, case=False).any(),
            axis=1,
        )
        display_df = display_df[mask]

    if len(display_df) == 0:
        st.info(f"No bookmarks match '{search_query}'")
    else:
        for index, row in display_df.iterrows():
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### [{row['title']}]({row['url']})")
                    st.markdown(f"**`{row['category']}`** 📅 {row['date']}")
                    if pd.notna(row["tags"]) and row["tags"]:
                        st.caption(f"🏷️ {row['tags']}")
                    if pd.notna(row["notes"]) and row["notes"]:
                        with st.expander("View Notes"):
                            st.write(row["notes"])
                st.divider()
else:
    st.info("📝 No bookmarks found. Add one in the sidebar to get started!")
    st.markdown("---")
    st.markdown("### Quick Start:")
    st.markdown("1. Fill out the form in the sidebar")
    st.markdown("2. Click 'Save Bookmark'")
    st.markdown("3. Your bookmark will appear here!")
