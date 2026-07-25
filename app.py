import streamlit as st
import pandas as pd
from pypdf import PdfReader
import re

# --- UI Configuration & Blue Theme ---
st.set_page_config(page_title="Document Matcher", page_icon="📘", layout="centered")

st.markdown("""
    <style>
    /* Make the main button blue */
    .stButton>button {
        background-color: #0066cc;
        color: white;
        border-radius: 5px;
        width: 100%;
        border: none;
    }
    .stButton>button:hover {
        background-color: #004c99;
        color: white;
    }
    /* Add a subtle blue tint to the background */
    .stApp {
        background-color: #f4f8fc;
    }
    </style>
""", unsafe_allow_html=True)


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
st.title("📘 Document Matcher")
st.write("Drag and drop your Master Spreadsheet and the PDF report below to generate a comparison.")

col1, col2 = st.columns(2)
with col1:
    excel_file = st.file_uploader("1. Master Spreadsheet", type=["xlsx", "csv"])
with col2:
    pdf_file = st.file_uploader("2. PDF Document", type=["pdf"])

if excel_file and pdf_file:
    if st.button("Run Comparison"):
        with st.spinner("Processing documents..."):
            try:
                # --- STEP 1: Process Spreadsheet ---
                if excel_file.name.endswith('.csv'):
                    df = pd.read_csv(excel_file)
                else:
                    df = pd.read_excel(excel_file, engine='calamine')
                    
                df.columns = df.columns.str.strip().str.lower()
                fn_col = next((col for col in df.columns if col in ['first name', 'firstname', 'first_name', 'first']), None)
                ln_col = next((col for col in df.columns if col in ['last name', 'lastname', 'last_name', 'last']), None)

                if not (fn_col and ln_col):
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

                # --- STEP 2: Process PDF ---
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

                # --- STEP 3: Generate Report ---
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
                
                st.success("Comparison complete!")
                
                # Show a preview on screen
                st.text_area("Report Preview", report_text, height=300)
                
                # Create a download button for the text file
                st.download_button(
                    label="⬇️ Download Results as Text File",
                    data=report_text,
                    file_name="comparison_results.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"An error occurred: {e}")