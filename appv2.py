import streamlit as st
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib

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


# ==============================================================================
# LOGO & HEADER
# ==============================================================================
LOGO_PATH = "static/SipanLabsLogo-main.jpg"
try:
    st.logo(LOGO_PATH, size="large", link="https://github.com/eliox01")
except Exception as e:
    st.sidebar.warning(f"Logo not found: {e}")


def get_bookmarks():
    """
    Read data from Google Sheets

    Returns:
        pd.DataFrame: DataFrame containing all bookmarks with columns:
                     date, title, url, category, tags, notes
    """
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
    """
    Save a new bookmark to Google Sheets

    Args:
        new_row_data (dict): Dictionary containing bookmark data with keys:
                            date, title, url, category, tags, notes

    Returns:
        tuple: (success: bool, message: str)
    """
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


def delete_bookmark(row_index):
    """
    Delete a bookmark from Google Sheets

    Args:
        row_index (int): The row number to delete (1-indexed, accounting for header)

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        sheet = init_gsheets_connection()
        if sheet is None:
            return False, "Failed to connect to Google Sheets"

        worksheet = sheet.worksheet("main")

        # Google Sheets rows are 1-indexed, and we need to account for the header row
        # row_index from our DataFrame needs +2 (1 for header, 1 for 0-indexed to 1-indexed)
        sheet_row_number = row_index + 2

        # Delete the row
        worksheet.delete_rows(sheet_row_number)

        return True, "Bookmark deleted successfully!"

    except Exception as e:
        return False, f"Error deleting: {str(e)}"


def find_duplicates(df):
    """
    Find duplicate bookmarks based on URL

    Args:
        df (pd.DataFrame): DataFrame containing bookmarks

    Returns:
        pd.DataFrame: DataFrame containing only duplicate entries
    """
    if df.empty:
        return pd.DataFrame()

    # Find duplicates based on URL (case-insensitive)
    df["url_lower"] = df["url"].str.lower().str.strip()
    duplicates = df[df.duplicated(subset=["url_lower"], keep=False)]
    duplicates = duplicates.drop(columns=["url_lower"])

    return duplicates.sort_values("url")


def validate_url(url):
    """
    Basic URL validation

    Args:
        url (str): URL string to validate

    Returns:
        bool: True if valid URL, False otherwise
    """
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

        # Show duplicate count
        duplicates = find_duplicates(df_stats)
        if not duplicates.empty:
            st.metric("🔄 Duplicate URLs", len(duplicates))
    except:
        st.metric("Total Bookmarks", "0")

# --- MAIN VIEW: TABS FOR DIFFERENT VIEWS ---
st.session_state["current_context"] = "main"

# Create tabs for different views
tab1, tab2 = st.tabs(["📚 All Bookmarks", "🔄 Manage Duplicates"])

df = get_bookmarks()

# TAB 1: ALL BOOKMARKS
with tab1:
    st.subheader("📚 Your Research Feed")

    # Search functionality
    search_query = st.text_input(
        "🔍 Search bookmarks...", placeholder="Search by title, tags, or notes..."
    )

    if not df.empty and len(df) > 0:
        # Reverse to show newest first
        display_df = df.iloc[::-1].copy()
        # Add index for deletion tracking
        display_df["original_index"] = range(len(df) - 1, -1, -1)

        if search_query:
            # Simple string matching across all columns
            mask = display_df.apply(
                lambda row: row.astype(str)
                .str.contains(search_query, case=False)
                .any(),
                axis=1,
            )
            display_df = display_df[mask]

        if len(display_df) == 0:
            st.info(f"No bookmarks match '{search_query}'")
        else:
            for index, row in display_df.iterrows():
                with st.container():
                    col1, col2 = st.columns([5, 1])

                    with col1:
                        st.markdown(f"### [{row['title']}]({row['url']})")
                        st.markdown(f"**`{row['category']}`** 📅 {row['date']}")
                        if pd.notna(row["tags"]) and row["tags"]:
                            st.caption(f"🏷️ {row['tags']}")
                        if pd.notna(row["notes"]) and row["notes"]:
                            with st.expander("View Notes"):
                                st.write(row["notes"])

                    with col2:
                        # Delete button for each bookmark
                        if st.button("🗑️ Delete", key=f"delete_{row['original_index']}"):
                            with st.spinner("Deleting..."):
                                success, message = delete_bookmark(
                                    row["original_index"]
                                )
                                if success:
                                    st.success(message)
                                    st.cache_resource.clear()
                                    st.rerun()
                                else:
                                    st.error(message)

                    st.divider()
    else:
        st.info("📝 No bookmarks found. Add one in the sidebar to get started!")
        st.markdown("---")
        st.markdown("### Quick Start:")
        st.markdown("1. Fill out the form in the sidebar")
        st.markdown("2. Click 'Save Bookmark'")
        st.markdown("3. Your bookmark will appear here!")

# TAB 2: DUPLICATES MANAGEMENT
with tab2:
    st.subheader("🔄 Duplicate Bookmarks")
    st.markdown("These bookmarks have the same URL. Keep one and delete the others.")

    duplicates = find_duplicates(df)

    if duplicates.empty:
        st.success("✅ No duplicate bookmarks found!")
        st.balloons()
    else:
        st.warning(f"Found {len(duplicates)} duplicate bookmark entries")

        # Group by URL to show duplicates together
        for url in duplicates["url"].unique():
            url_dupes = df[
                df["url"].str.lower().str.strip() == url.lower().strip()
            ].copy()
            url_dupes["original_index"] = url_dupes.index

            st.markdown(f"### 🔗 URL: `{url}`")
            st.caption(f"Found {len(url_dupes)} copies of this bookmark")

            for idx, row in url_dupes.iterrows():
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])

                    with col1:
                        st.markdown(f"**{row['title']}**")
                        st.caption(f"📅 {row['date']} | Category: {row['category']}")
                        if pd.notna(row["tags"]) and row["tags"]:
                            st.caption(f"🏷️ {row['tags']}")

                    with col2:
                        st.caption(f"Row {idx + 2}")  # +2 for header and 0-index

                    with col3:
                        if st.button("🗑️ Delete", key=f"dup_delete_{idx}"):
                            with st.spinner("Deleting..."):
                                success, message = delete_bookmark(idx)
                                if success:
                                    st.success(message)
                                    st.cache_resource.clear()
                                    st.rerun()
                                else:
                                    st.error(message)

                st.markdown("---")

            st.divider()
