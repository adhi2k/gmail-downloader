import streamlit as st
from imap_tools import MailBox, AND
from datetime import date
import io
import zipfile
import traceback

st.set_page_config(
    page_title="Gmail Attachment Downloader", 
    page_icon="📧",
    layout="centered"
)

# Custom CSS for a cleaner, modern look
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 50px;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stDownloadButton>button {
        width: 100%;
        background-color: #008CBA;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        height: 50px;
    }
    .stDownloadButton>button:hover {
        background-color: #007399;
    }
</style>
""", unsafe_allow_html=True)

st.title("📧 Gmail Attachment Downloader")
st.markdown("Download all your email attachments in a specific date range directly into a single `.zip` file.")

with st.form("download_form"):
    st.subheader("Credentials")
    email = st.text_input("Gmail Address", placeholder="you@gmail.com")
    password = st.text_input("App Password", type="password", help="Use a 16-digit Google App Password. Standard passwords will not work.")
    
    st.subheader("Filters")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
    with col2:
        end_date = st.date_input("End Date", value=date.today())
        
    extension_filter = st.text_input("File Extension (Optional)", placeholder="e.g. .pdf, .docx, .jpg", help="Only download files with this exact extension.")
    
    submit_button = st.form_submit_button("Fetch Attachments")

if submit_button:
    if not email or not password:
        st.error("Please provide both your Gmail address and your App Password.")
    elif start_date > end_date:
        st.error("Start Date must be before or equal to End Date.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.info("Connecting to Gmail securely...")
            mailbox = MailBox('imap.gmail.com').login(email, password)
            
            gm_search = "has:attachment"
            if extension_filter:
                clean_ext = extension_filter.strip().lstrip('.')
                gm_search += f" filename:{clean_ext}"

            search_criteria = AND(f'X-GM-RAW "{gm_search}"', date_gte=start_date, date_lt=end_date)
            
            status_text.info("Scanning for matching emails (this may take a moment)...")
            uids = mailbox.uids(search_criteria)
            total_emails = len(uids)
            
            if total_emails == 0:
                progress_bar.progress(100)
                status_text.warning("No attachments found matching your criteria in this date range.")
            else:
                memory_file = io.BytesIO()
                with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    messages = mailbox.fetch(search_criteria, reverse=True, bulk=True)
                    
                    for i, msg in enumerate(messages):
                        mail_date = msg.date.strftime('%Y-%m-%d')
                        
                        for att in msg.attachments:
                            filename = att.filename
                            if not filename:
                                continue
                            
                            # Ensure clean paths
                            zip_path = f"{mail_date}/{filename}"
                            zf.writestr(zip_path, att.payload)
                            
                        # Update progress bar and text
                        progress_percent = int(((i + 1) / total_emails) * 100)
                        progress_bar.progress(progress_percent)
                        status_text.info(f"Downloading attachments... {progress_percent}% ({i+1} / {total_emails} emails processed)")
                
                # Logout safely
                try:
                    mailbox.logout()
                except Exception:
                    pass
                
                # Verify the zip file isn't empty
                memory_file.seek(0)
                is_valid_zip = False
                try:
                    with zipfile.ZipFile(memory_file, 'r') as z:
                        if z.namelist():
                            is_valid_zip = True
                except zipfile.BadZipFile:
                    pass
                
                if not is_valid_zip:
                    status_text.warning("Emails were found, but no valid attachments could be extracted.")
                else:
                    status_text.success("✅ Download complete! Click the button below to save your files.")
                    
                    # Present the actual download button to the user
                    st.download_button(
                        label="⬇️ Save Attachments (.zip)",
                        data=memory_file.getvalue(),
                        file_name="gmail_attachments.zip",
                        mime="application/zip"
                    )
                    
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            if "AUTHENTICATIONFAILED" in str(e):
                st.error("Authentication failed. Please check your email and make sure you are using a 16-digit App Password, not your normal account password.")
            else:
                st.error(f"An unexpected error occurred: {e}")
                with st.expander("Show detailed error log"):
                    st.code(traceback.format_exc())
