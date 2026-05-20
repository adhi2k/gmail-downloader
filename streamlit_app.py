import streamlit as st
from imap_tools import MailBox, AND
from datetime import date
import io
import zipfile
import traceback
import os
from PIL import Image
import pandas as pd
import json

st.set_page_config(
    page_title="Swiss Army Knife", 
    page_icon="🛠️",
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

def render_gmail_downloader():
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

def render_file_converter():
    st.title("🔄 Universal File Converter")
    st.markdown("Convert your files seamlessly right in your browser.")
    
    uploaded_file = st.file_uploader("Upload a file to convert", type=['png', 'jpg', 'jpeg', 'webp', 'pdf'])
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext == 'jpeg': file_ext = 'jpg'
        
        st.write(f"**Uploaded File:** {uploaded_file.name}")
        
        # Determine conversion options based on file type
        if file_ext in ['png', 'jpg', 'webp']:
            # For images
            target_format = st.selectbox("Convert to:", ['PNG', 'JPG', 'WEBP', 'PDF'])
            
            with st.spinner("Preparing file..."):
                try:
                    img = Image.open(uploaded_file)
                    
                    # Convert to RGB if saving to JPG or PDF to avoid alpha channel errors
                    if target_format in ['JPG', 'PDF'] and img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                        
                    output_file = io.BytesIO()
                    
                    if target_format == 'PDF':
                        img.save(output_file, format='PDF', resolution=100.0)
                        mime_type = "application/pdf"
                        download_name = f"{uploaded_file.name.rsplit('.', 1)[0]}.pdf"
                    else:
                        img.save(output_file, format=target_format)
                        mime_type = f"image/{target_format.lower()}"
                        download_name = f"{uploaded_file.name.rsplit('.', 1)[0]}.{target_format.lower()}"
                        
                    st.success("✅ Ready for download!")
                    st.download_button(
                        label=f"⬇️ Download {target_format} file",
                        data=output_file.getvalue(),
                        file_name=download_name,
                        mime=mime_type
                    )
                except Exception as e:
                    st.error(f"Error converting image: {e}")
                        
        elif file_ext == 'pdf':
            # For PDFs
            target_format = st.selectbox("Convert to:", ['DOCX', 'PNG (ZIP)', 'JPG (ZIP)'])
            
            with st.spinner("Preparing file... this may take a while depending on file size."):
                try:
                    import fitz  # PyMuPDF
                    
                    if target_format == 'DOCX':
                        from pdf2docx import Converter
                        import tempfile
                        
                        # pdf2docx requires physical files
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(uploaded_file.getvalue())
                            tmp_pdf_path = tmp_pdf.name
                            
                        tmp_docx_path = tmp_pdf_path + ".docx"
                        
                        cv = Converter(tmp_pdf_path)
                        cv.convert(tmp_docx_path)
                        cv.close()
                        
                        with open(tmp_docx_path, "rb") as f:
                            docx_bytes = f.read()
                            
                        st.success("✅ Ready for download!")
                        st.download_button(
                            label="⬇️ Download DOCX file",
                            data=docx_bytes,
                            file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        
                        # Cleanup temp files
                        try:
                            os.unlink(tmp_pdf_path)
                            os.unlink(tmp_docx_path)
                        except:
                            pass
                            
                    elif target_format in ['PNG (ZIP)', 'JPG (ZIP)']:
                        img_format = target_format.split(' ')[0]
                        doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
                        
                        memory_file = io.BytesIO()
                        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for page_num in range(len(doc)):
                                page = doc.load_page(page_num)
                                pix = page.get_pixmap(dpi=150)
                                img_bytes = pix.tobytes(img_format.lower())
                                zf.writestr(f"page_{page_num + 1}.{img_format.lower()}", img_bytes)
                                
                        doc.close()
                        st.success("✅ Ready for download!")
                        st.download_button(
                            label=f"⬇️ Download {img_format}s (.zip)",
                            data=memory_file.getvalue(),
                            file_name=f"{uploaded_file.name.rsplit('.', 1)[0]}_{img_format.lower()}s.zip",
                            mime="application/zip"
                        )
                except Exception as e:
                    st.error(f"Error converting PDF: {e}")
                    with st.expander("Show detailed error log"):
                        st.code(traceback.format_exc())


CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"last_serial": 1, "company_ifsc": "", "company_acc_no": "924020049602165", "employee_sheet_url": ""}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def render_bank_upload_form():
    st.title("🏦 Automated Bank Upload Generator")

    config = load_config()

    tab1, tab2 = st.tabs(["🚀 Upload", "⚙️ Settings"])

    # --- TAB 2: Settings ---
    with tab2:
        st.subheader("Company Details")
        company_ifsc = st.text_input("Company IFSC Code", value=config.get("company_ifsc", ""))
        company_acc = st.text_input("Company Bank Account No", value=config.get("company_acc_no", "924020049602165"))
        
        st.subheader("Google Sheets Database")
        st.markdown("Paste your Google Sheet link containing **all Employee & Vendor bank details**.")
        emp_url = st.text_input("Database Sheet URL", value=config.get("employee_sheet_url", ""))
        
        st.subheader("Serial Number Tracking")
        last_serial = st.number_input("Last Used Serial Number", min_value=0, value=config.get("last_serial", 1))
        
        if st.button("Save Settings"):
            config["company_ifsc"] = company_ifsc.strip().upper()
            config["company_acc_no"] = company_acc.strip()
            config["employee_sheet_url"] = emp_url.strip()
            config["last_serial"] = last_serial
            save_config(config)
            st.success("Settings saved!")

    # --- Helper: Convert any Google Sheets URL to CSV export ---
    def convert_gsheet_url(raw_url):
        import re
        if "/edit" in raw_url:
            m = re.search(r'spreadsheets/d/([a-zA-Z0-9-_]+)', raw_url)
            if m:
                sid = m.group(1)
                gm = re.search(r'gid=([0-9]+)', raw_url)
                gid = gm.group(1) if gm else "0"
                return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
        elif "/pubhtml" in raw_url:
            raw_url = raw_url.replace("/pubhtml", "/pub")
            if "?" in raw_url:
                raw_url = raw_url.replace("?", "?output=csv&")
            else:
                raw_url = raw_url + "?output=csv"
        return raw_url

    def load_gsheet_df(url):
        url = convert_gsheet_url(url)
        df_raw = pd.read_csv(url, dtype=str, names=range(50), header=None, engine='python')
        headers = df_raw.iloc[0]
        df = df_raw[1:].copy()
        df.columns = headers
        mask = [pd.notna(c) and str(c).strip().lower() not in ['nan', 'none', '<na>', ''] for c in df.columns]
        df = df.loc[:, mask]
        df = df.loc[:, ~df.columns.duplicated()]
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # --- Load database silently from Google Sheets ---
    df_db = pd.DataFrame()

    if config.get("employee_sheet_url"):
        try:
            df_db = load_gsheet_df(config["employee_sheet_url"])
        except:
            pass

    # --- Column detection ---
    def find_col_in(df, keywords):
        cols_lower = df.columns.str.lower()
        for i, c in enumerate(cols_lower):
            if all(k in c for k in keywords):
                return df.columns[i]
        return None

    db_code_col = find_col_in(df_db, ['code']) if not df_db.empty else None
    db_name_col = find_col_in(df_db, ['name']) if not df_db.empty else None
    db_acc_col = find_col_in(df_db, ['acc']) if not df_db.empty else None
    db_ifsc_col = find_col_in(df_db, ['ifsc']) if not df_db.empty else None

    # --- Build combined name list for manual add popup ---
    all_entries = []
    if not df_db.empty and db_name_col and db_acc_col and db_ifsc_col:
        for _, r in df_db.iterrows():
            code = str(r[db_code_col]).replace('.0', '').strip() if (db_code_col and pd.notna(r[db_code_col])) else ""
            name = str(r[db_name_col]).strip()
            acc = str(r[db_acc_col]).replace('.0', '').strip()
            ifsc = str(r[db_ifsc_col]).strip()
            if name.upper() != 'NAN' and name:
                label = f"{name} ({code})" if (code and code.upper() != 'NAN') else name
                all_entries.append({"label": label, "name": name, "acc": acc, "ifsc": ifsc})

    # Initialize manual rows in session state
    if 'manual_rows' not in st.session_state:
        st.session_state.manual_rows = []

    @st.dialog("➕ Add Manual Transaction")
    def add_manual_row():
        if not all_entries:
            st.warning("No database loaded. Please load database link in Settings first.")
            return
        
        labels = [e["label"] for e in all_entries]
        selected = st.selectbox("Search Employee / Vendor", options=labels, index=None, placeholder="Type to search...")
        
        if selected:
            entry = all_entries[labels.index(selected)]
            st.markdown(f"**Account No:** `{entry['acc']}`")
            st.markdown(f"**IFSC Code:** `{entry['ifsc']}`")
            
            amount = st.number_input("Enter Amount (₹)", min_value=1.0, step=1000.0, format="%.2f")
            
            if st.button("✅ Add to Batch", use_container_width=True):
                company_ifsc = config.get("company_ifsc", "").strip().upper()
                company_acc = config.get("company_acc_no", "924020049602165")
                e_ifsc = entry["ifsc"].upper()
                
                if len(e_ifsc) >= 4 and len(company_ifsc) >= 4 and e_ifsc[:4] == company_ifsc[:4]:
                    t_type = "I"
                else:
                    t_type = "N" if amount < 2000000 else "R"
                
                st.session_state.manual_rows.append({
                    "Col1": t_type,
                    "Col2": amount,
                    "Col3": date.today().strftime("%d-%m-%Y"),
                    "Col4": entry["name"],
                    "Col5": entry["acc"],
                    "Col6": "",
                    "Col7": "",
                    "Col8": company_acc,
                    "Col9": 0,  # serial assigned at generate time
                    "Col10": entry["ifsc"],
                    "Col11": "10"
                })
                st.success(f"Added {entry['name']} — ₹{amount:,.2f}")
                st.rerun()

    # --- TAB 1: Upload ---
    with tab1:
        st.info(f"Next Serial No: **{config.get('last_serial', 0) + 1}**  |  "
                f"Database loaded: **{len(df_db)}** entries")
        
        col_upload, col_manual = st.columns([3, 1])
        with col_upload:
            salary_file = st.file_uploader("Upload Payment Sheet (Employee Code / Vendor Name + Amount)", type=["csv", "xlsx"], key="salary")
        with col_manual:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add Manual", use_container_width=True):
                add_manual_row()

        # Show manually added rows preview if any
        if st.session_state.manual_rows:
            st.markdown(f"**Manually added entries: {len(st.session_state.manual_rows)}**")
            manual_preview = pd.DataFrame(st.session_state.manual_rows)[["Col4", "Col2", "Col5", "Col10"]]
            manual_preview.columns = ["Name", "Amount", "Account No", "IFSC"]
            st.dataframe(manual_preview, use_container_width=True)
            if st.button("🗑️ Clear Manual Entries"):
                st.session_state.manual_rows = []
                st.rerun()

        if salary_file or st.session_state.manual_rows:
            transactions = []
            current_serial = config.get("last_serial", 0) + 1
            today_str = date.today().strftime("%d-%m-%Y")
            company_ifsc = config.get("company_ifsc", "").strip().upper()
            company_acc = config.get("company_acc_no", "924020049602165")
            errors = []
            
            # 1. Process file if uploaded
            if salary_file:
                if salary_file.name.endswith('.csv'):
                    df_sal = pd.read_csv(salary_file, dtype=str)
                else:
                    df_sal = pd.read_excel(salary_file, dtype=str)
                    
                df_sal.columns = [str(c).strip() for c in df_sal.columns]
                sal_cols = df_sal.columns.str.lower()
                
                def find_sal_col(keywords):
                    for i, c in enumerate(sal_cols):
                        if all(k in c for k in keywords):
                            return df_sal.columns[i]
                    return None
                
                sal_id_col = find_sal_col(['code']) or find_sal_col(['name']) or (df_sal.columns[0] if len(df_sal.columns) >= 1 else None)
                sal_amt_col = find_sal_col(['salary']) or find_sal_col(['amount']) or (df_sal.columns[1] if len(df_sal.columns) >= 2 else None)
                
                if not sal_id_col or not sal_amt_col:
                    st.error("Payment sheet needs at least 2 columns: an identifier (Code/Name) and an Amount.")
                else:
                    for idx, row in df_sal.iterrows():
                        identifier = str(row[sal_id_col]).replace('.0', '').strip()
                        if identifier.upper() == 'NAN' or not identifier:
                            continue
                            
                        amt_str = str(row[sal_amt_col]).replace(',', '').strip()
                        try:
                            amt = float(amt_str)
                        except ValueError:
                            continue 
                        
                        matched = False
                        match_name = ""
                        match_acc = ""
                        match_ifsc = ""
                        
                        if not df_db.empty and db_acc_col and db_ifsc_col:
                            # Try Employee Code match first
                            if db_code_col:
                                db_codes = df_db[db_code_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
                                code_match = df_db[db_codes == identifier.upper()]
                                if not code_match.empty:
                                    data = code_match.iloc[0]
                                    match_name = str(data[db_name_col]).strip() if db_name_col else identifier
                                    match_acc = str(data[db_acc_col]).replace('.0', '').strip()
                                    match_ifsc = str(data[db_ifsc_col]).strip().upper()
                                    matched = True
                            
                            # Fallback: match by Name (for vendors in the same sheet)
                            if not matched and db_name_col:
                                db_names = df_db[db_name_col].astype(str).str.strip().str.upper()
                                name_match = df_db[db_names == identifier.upper()]
                                if not name_match.empty:
                                    data = name_match.iloc[0]
                                    match_name = str(data[db_name_col]).strip()
                                    match_acc = str(data[db_acc_col]).replace('.0', '').strip()
                                    match_ifsc = str(data[db_ifsc_col]).strip().upper()
                                    matched = True
                        
                        if not matched:
                            errors.append(f"'{identifier}'")
                            continue
                        
                        if len(match_ifsc) >= 4 and len(company_ifsc) >= 4 and match_ifsc[:4] == company_ifsc[:4]:
                            t_type = "I"
                        else:
                            t_type = "N" if amt < 2000000 else "R"
                                
                        transactions.append({
                            "Col1": t_type, "Col2": amt, "Col3": today_str,
                            "Col4": match_name, "Col5": match_acc,
                            "Col6": "", "Col7": "", "Col8": company_acc,
                            "Col9": current_serial, "Col10": match_ifsc, "Col11": "10"
                        })
                        current_serial += 1

            # 2. Append manual rows
            for mr in st.session_state.manual_rows:
                mr_copy = mr.copy()
                mr_copy["Col9"] = current_serial
                transactions.append(mr_copy)
                current_serial += 1

            if errors:
                st.warning(f"⚠️ Not found in database: {', '.join(errors)}")
                    
            if transactions:
                st.success(f"✅ {len(transactions)} transactions generated")
                df_trans = pd.DataFrame(transactions)
                
                import io
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_trans.to_excel(writer, index=False, header=False, sheet_name='BankUpload')
                    worksheet = writer.sheets['BankUpload']
                    for row_cells in worksheet.iter_rows():
                        for cell in row_cells:
                            cell.number_format = '@'
                excel_data = excel_buffer.getvalue()
                
                st.download_button("⬇️ Download Bank Upload Excel", data=excel_data, 
                                   file_name=f"bank_upload_{date.today()}.xlsx", 
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                                   key="dl_btn")
                
                # Auto-update serial number
                config["last_serial"] = current_serial - 1
                save_config(config)
            else:
                if not errors:
                    st.warning("No valid entries found in the uploaded sheet or manual list.")

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Gmail Attachment Downloader", "File Converter", "Bank Upload Generator"])

if page == "Gmail Attachment Downloader":
    render_gmail_downloader()
elif page == "File Converter":
    render_file_converter()
elif page == "Bank Upload Generator":
    render_bank_upload_form()
