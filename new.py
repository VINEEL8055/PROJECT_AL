import streamlit as st
import pdfplumber
from pypdf import PdfReader, PdfWriter
import io
import re

st.set_page_config(page_title="PDF Page Extractor", page_icon="📄", layout="centered")

# --- Styling ---
st.markdown("""
<style>
    .stApp { max-width: 800px; margin: 0 auto; }
    .match-card {
        background: #f0f7ff;
        border-left: 4px solid #1a73e8;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        font-size: 14px;
    }
    .match-card strong { color: #1a73e8; }
    .stat-box {
        background: #e8f5e9;
        padding: 10px 16px;
        border-radius: 8px;
        text-align: center;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF Page Extractor")
st.markdown("Upload a PDF, enter numbers to search for — get a new PDF with only the matching pages.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])

# --- Search Input ---
search_input = st.text_input(
    "Enter numbers to search (comma-separated)",
    placeholder="e.g. 12345, 67890, 11223"
)

# --- Options ---
col1, col2 = st.columns(2)
with col1:
    match_mode = st.selectbox(
        "Match mode",
        ["Exact match", "Contains (partial match)"],
        help="Exact: matches the number as a standalone value. Contains: finds the number anywhere in the text."
    )
with col2:
    show_preview = st.checkbox("Show matched text preview", value=True)


def search_pages(pdf_file, search_terms, exact=True):
    """Search PDF pages for given terms and return matching page numbers with context."""
    matches = {}  # {page_num: [matched_terms]}
    previews = {}  # {page_num: snippet}

    with pdfplumber.open(pdf_file) as pdf:
        total_pages = len(pdf.pages)
        progress = st.progress(0, text="Scanning pages...")

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            page_num = i + 1

            for term in search_terms:
                term = term.strip()
                if not term:
                    continue

                if exact:
                    # Match as a standalone number (word boundary)
                    pattern = r'(?<!\d)' + re.escape(term) + r'(?!\d)'
                    found = re.search(pattern, text)
                else:
                    found = term in text

                if found:
                    if page_num not in matches:
                        matches[page_num] = []
                        # Grab a snippet around the match
                        if isinstance(found, re.Match):
                            start = max(0, found.start() - 60)
                            end = min(len(text), found.end() + 60)
                            previews[page_num] = "..." + text[start:end].replace("\n", " ") + "..."
                        else:
                            idx = text.find(term)
                            start = max(0, idx - 60)
                            end = min(len(text), idx + len(term) + 60)
                            previews[page_num] = "..." + text[start:end].replace("\n", " ") + "..."

                    if term not in matches[page_num]:
                        matches[page_num].append(term)

            progress.progress((i + 1) / total_pages, text=f"Scanning page {i + 1} of {total_pages}...")

        progress.empty()

    return matches, previews, total_pages


def extract_pages(pdf_file, page_numbers):
    """Extract specific pages from PDF and return as bytes."""
    reader = PdfReader(pdf_file)
    writer = PdfWriter()

    for pg in sorted(page_numbers):
        writer.add_page(reader.pages[pg - 1])  # 0-indexed

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


# --- Main Logic ---
if st.button("🔍 Search & Extract", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("Please upload a PDF file.")
    elif not search_input.strip():
        st.error("Please enter at least one number to search.")
    else:
        search_terms = [t.strip() for t in search_input.split(",") if t.strip()]
        exact = match_mode == "Exact match"

        # Reset file pointer
        uploaded_file.seek(0)
        matches, previews, total_pages = search_pages(uploaded_file, search_terms, exact)

        if not matches:
            st.warning(f"No pages found containing: {', '.join(search_terms)}")
            st.info("💡 Try switching to 'Contains (partial match)' mode if exact match isn't working.")
        else:
            # Stats
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f'<div class="stat-box">📄 Total Pages<br>{total_pages}</div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="stat-box">✅ Matched<br>{len(matches)}</div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="stat-box">🔢 Terms Found<br>{len(set(t for terms in matches.values() for t in terms))}/{len(search_terms)}</div>', unsafe_allow_html=True)

            # Show matches
            st.markdown("### Matched Pages")
            for pg in sorted(matches.keys()):
                terms_str = ", ".join(matches[pg])
                preview_html = ""
                if show_preview and pg in previews:
                    preview_html = f"<br><small style='color:#666'>{previews[pg]}</small>"
                st.markdown(
                    f'<div class="match-card"><strong>Page {pg}</strong> — found: {terms_str}{preview_html}</div>',
                    unsafe_allow_html=True
                )

            # Check for terms not found
            found_terms = set(t for terms in matches.values() for t in terms)
            missing = [t for t in search_terms if t not in found_terms]
            if missing:
                st.warning(f"⚠️ Not found in any page: {', '.join(missing)}")

            # Extract and provide download
            uploaded_file.seek(0)
            extracted_pdf = extract_pages(uploaded_file, matches.keys())

            st.markdown("---")
            st.download_button(
                label=f"⬇️ Download Extracted PDF ({len(matches)} pages)",
                data=extracted_pdf,
                file_name="extracted_pages.pdf",
                mime="application/pdf",
                use_container_width=True
            )
