import streamlit as st
import pandas as pd
from pypdf import PdfReader
import re

# --- UI Configuration & Pastel Theme ---
st.set_page_config(page_title="Document Matcher", page_icon="📘", layout="centered")

st.markdown("""
    <style>
    /* 1. Override Streamlit's hidden root variables to completely disable Dark Mode clashes */
    :root {
        --text-color: #2c3e50 !important;
        --background-color: #eaf2f8 !important;
        --secondary-background-color: #ffffff !important;
    }

    /* 2. Force Pastel Blue Background */
    .stApp, .main, [data-testid="stHeader"] {
        background-color: #eaf2f8 !important; 
    }
    
    /* 3. Force Dark Slate Text Everywhere (Highly visible, softer than pure black) */
    html, body, [class*="css"], .stApp, .stApp *, h1, h2, h3, h4, h5, h6, p, span, div, label, li {
        color: #2c3e50 !important;
    }
    
    /* 4. Pastel Blue Buttons */
    .stButton>button, .stDownloadButton>button {
        background-color: #cce3f3 !important;
        color: #2c3e50 !important; /* Dark text on pastel button */
        border-radius: 8px !important;
        width: 100% !important;
        border: 2px solid #a4c9e3 !important;
        padding: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        background-color: #b5d5ec !important;
        transform: translateY(-1px);
    }
    /* Ensure emojis inside buttons stay visible */
    .stButton>button *, .stDownloadButton>button * {
        color: #2c3e50 !important; 
    }
    
    /* 5. File Uploader Drop Zones (Crisp white cards, pastel borders) */
    [data-testid="stFileUploadDropzone"] {
        background-color: #ffffff !important;
        border-radius: 12px !important;
        border: 2px dashed #a4c9e3 !important;
        padding: 20px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    }
    
    /* 6. Expanders (Dropdowns) */
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #a4c9e3 !important;
        border-radius: 8px !important;
    }
    
    /* 7. Text Area (The Report Preview Box) */
    .stTextArea textarea {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border: 1px solid #a4c9e3 !important;
        border-radius: 8px !important;
    }
    
    /* 8. Loading/Status Box */
    [data-testid="stStatusWidget"] {
        background-color: #ffffff !important;
        border: 1px solid #a4c9e3 !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)


# --- INSTRUCTIONS TEXT ---
CARETRACKER_INSTRUCTIONS = """Instructions for getting the Caretracker PDF with patient names.

1. Find the reports section on the left-hand side of the screen
2. Locate the "Financial Reports" category
3. Click on the "Other reports" line
4. Select "Global - Charges by provider and service date"
5. Select the right date frame 
6. Create the report
7. Find it in the "Published reports"
"""


# --- HELPER FUNCTIONS ---
def get_core_names(first_raw, last_raw):
    def clean(text):
        t = str(text).lower()
        t = re.sub(r'\d+', '', t)
        t = re.sub(r'[^\w\s]', '', t)
        t = re.sub(r'\b(jr|sr|i|ii|iii|iv|v|md|phd|dds)\b', '', t)
        return t.strip()
        
    c_first = clean(first_raw)
    c_last = clean(last_raw)
    core_f = c_first.split()[0] if c_first else ""
    core_l = c_last.split()[-1] if c_last else ""
    return core_f, core_l

EXCLUSIONS = [
    "first name last name", "coast", "norwalk", 
    "vista la mirada", "29th for college hospital", "wellness day"
]

# --- MAIN APP UI ---
# Title Area
st.markdown("<h1 style='text-align: center;'>📘 Master Document Matcher</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; margin-bottom: 2rem;'>Securely compare your master spreadsheet against daily PDF reports.</p>", unsafe_allow_html=True)

# Upload Area
st.markdown("### Step 1: Upload Documents")
col1, col2 = st.columns(2)
with col1:
    excel_file = st.file_uploader("📊 Master Spreadsheet (Excel/CSV)", type=["xlsx", "csv"])
with col2:
    pdf_file = st.file_uploader("📄 PDF Report", type=["pdf"])
    
    # Hidden instructions download
    with st.expander("ℹ️ How to get the Caretracker PDF"):
        st.write("Download the step-by-step instructions for generating the correct PDF from Caretracker.")
        st.download_button(
            label="⬇️ Download Instructions",
            data=CARETRACKER_INSTRUCTIONS,
            file_name="Caretracker_Instructions.txt",
            mime="text/plain",
            use_container_width=True
        )

st.markdown("<br>", unsafe_allow_html=True) 

# Processing Area
if excel_file and pdf_file:
    if st.button("🚀 Run Comparison Match", use_container_width=True):
        with st.status("Analyzing documents...", expanded=True) as status:
            try:
                st.write("Reading spreadsheet data...")
                # --- PROCESS SPREADSHEET ---
                if excel_file.name.endswith('.csv'):
                    df = pd.read_csv(excel_file)
                else:
                    df = pd.read_excel(excel_file, engine='calamine')
                    
                df.columns = df.columns.str.strip().str.lower()
                fn_col = next((col for col in df.columns if col in ['first name', 'firstname', 'first_name', 'first']), None)
                ln_col = next((col for col in df.columns if col in ['last name', 'lastname', 'last_name', 'last']), None)

                if not (fn_col and ln_col):
                    status.update(label="Error processing spreadsheet", state="error", expanded=True)
                    st.error("Could not find 'First Name' and 'Last Name' columns.")
                    st.stop()
                    
                result_df = df[[fn_col, ln_col]].dropna(how='all')
                spreadsheet_persons = {}
                
                for _, row in result_df.iterrows():
                    raw_first = str(row[fn_col]).strip()
                    raw_last = str(row[ln_col]).strip()
                    if raw_first == 'nan' and raw_last == 'nan': continue
                        
                    original_full = f"{raw_first} {raw_last}"
                    if any(ex in original_full.lower() for ex in EXCLUSIONS): continue
                        
                    core_f, core_l = get_core_names(raw_first, raw_last)
                    display_name = f"{raw_first.title()} {raw_last.title()}"
                    
                    if core_f and core_l:
                        spreadsheet_persons[display_name] = {'core_first': core_f, 'core_last': core_l}

                st.write("Scanning PDF text for matches...")
                # --- PROCESS PDF ---
                reader = PdfReader(pdf_file)
                pdf_text = "".join(page.extract_text() or "" for page in reader.pages)
                pdf_text_flat = re.sub(r'\s+', ' ', pdf_text).lower()

                in_both = []
                only_in_spreadsheet = []

                for display_name, p in spreadsheet_persons.items():
                    core_f, core_l = p['core_first'], p['core_last']
                    
                    pattern1 = r"\b" + re.escape(core_f) + r"\b(?:\W+\w+){0,5}\W+" + re.escape(core_l) + r"\b"
                    pattern2 = r"\b" + re.escape(core_l) + r"\b(?:\W+\w+){0,5}\W+" + re.escape(core_f) + r"\b"
                    
                    if re.search(pattern1, pdf_text_flat) or re.search(pattern2, pdf_text_flat):
                        in_both.append(display_name)
                    else:
                        only_in_spreadsheet.append(display_name)
                        
                in_both.sort()
                only_in_spreadsheet.sort()

                # --- GENERATE REPORT ---
                report_lines = [
                    "=" * 50, "COMPARISON RESULTS REPORT (FUZZY MATCHING)", "=" * 50 + "\n",
                    f"1. IN BOTH FILES ({len(in_both)} found):", "-" * 30
                ]
                report_lines.extend([f"  • {name}" for name in in_both] if in_both else ["  (None)"])
                
                report_lines.extend([
                    f"\n2. ONLY IN SPREADSHEET / MISSING FROM PDF ({len(only_in_spreadsheet)} found):", "-" * 30
                ])
                report_lines.extend([f"  • {name}" for name in only_in_spreadsheet] if only_in_spreadsheet else ["  (None)"])
                
                report_text = "\n".join(report_lines)
                
                status.update(label="Comparison Complete!", state="complete", expanded=False)
                
                # --- DISPLAY DASHBOARD RESULTS ---
                st.markdown("### Step 2: Results")
                
                met1, met2, met3 = st.columns(3)
                met1.metric(label="Total in Spreadsheet", value=len(spreadsheet_persons))
                met2.metric(label="✅ Found in PDF", value=len(in_both))
                met3.metric(label="⚠️ Missing from PDF", value=len(only_in_spreadsheet))
                
                with st.expander("Preview Full Text Report"):
                    st.text_area("", report_text, height=300, label_visibility="collapsed")
                
                st.download_button(
                    label="⬇️ Download Results as Text File",
                    data=report_text,
                    file_name="comparison_results.txt",
                    mime="text/plain",
                    use_container_width=True
                )

            except Exception as e:
                status.update(label="An error occurred", state="error", expanded=True)
                st.error(f"Error details: {e}")
