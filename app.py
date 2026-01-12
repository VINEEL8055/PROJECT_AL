import streamlit as st
import boto3
import fitz
import json
import tempfile

# =================================================
# 🔐 DIRECT R2 CREDENTIALS (PASTE HERE)
# =================================================
BUCKET_NAME = "al-pdf-store"
INDEX_KEY = "pdf_search_index.json"

import streamlit as st

R2_ENDPOINT = st.secrets["R2_ENDPOINT"]
R2_ACCESS_KEY = st.secrets["R2_ACCESS_KEY"]
R2_SECRET_KEY = st.secrets["R2_SECRET_KEY"]

# ---------------- R2 CLIENT ----------------
s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto"
)

st.set_page_config(page_title="PDF Search & Merge", layout="centered")
st.title("📄 PDF Search & Merge")

# ---------------- UTILITIES ----------------
def load_index():
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=INDEX_KEY)
        return json.loads(obj["Body"].read().decode())
    except:
        return {}

def save_index(index):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=INDEX_KEY,
        Body=json.dumps(index).encode("utf-8"),
        ContentType="application/json"
    )

def update_index_for_pdf(pdf_key, pdf_bytes, index):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = {}
    for i in range(len(doc)):
        pages[i] = doc[i].get_text().lower()
    index[pdf_key] = pages

# ---------------- UPLOAD ----------------
st.header("📤 Upload PDFs")

uploaded_files = st.file_uploader(
    "Upload one or more PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Uploading & indexing PDFs..."):
        index = load_index()

        for file in uploaded_files:
            pdf_bytes = file.read()

            # Upload PDF to R2
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=file.name,
                Body=pdf_bytes
            )

            # Update index immediately
            update_index_for_pdf(file.name, pdf_bytes, index)

        save_index(index)

    st.success("✅ PDFs uploaded and indexed successfully")

# ---------------- SEARCH ----------------
st.header("🔍 Search & Merge")

search_input = st.text_input(
    "Enter search terms (comma-separated)",
    placeholder="CMO12345, INV7789"
)

if st.button("Search & Merge"):
    if not search_input.strip():
        st.warning("Please enter at least one search term.")
    else:
        terms = [t.strip().lower() for t in search_input.split(",") if t.strip()]
        index = load_index()

        merged = fitz.open()
        matches = 0

        with st.spinner("Searching PDFs..."):
            for pdf_key, pages in index.items():
                matched_pages = [
                    int(p) for p, text in pages.items()
                    if any(term in text for term in terms)
                ]

                if not matched_pages:
                    continue

                with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                    s3.download_fileobj(BUCKET_NAME, pdf_key, tmp)
                    tmp.seek(0)
                    doc = fitz.open(stream=tmp.read(), filetype="pdf")

                    for p in matched_pages:
                        merged.insert_pdf(doc, from_page=p, to_page=p)
                        matches += 1

        if matches == 0:
            st.error("❌ No matches found.")
        else:
            out_file = "merged_result.pdf"
            merged.save(out_file)
            merged.close()

            with open(out_file, "rb") as f:
                st.download_button(
                    "⬇️ Download Merged PDF",
                    f,
                    file_name="merged_result.pdf",
                    mime="application/pdf"
                )

            st.success(f"✅ Merged {matches} pages")
