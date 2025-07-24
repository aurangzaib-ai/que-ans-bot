import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
import requests
import time
import os
from dotenv import load_dotenv

# --- Load API Key ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# --- UI Setup ---
st.set_page_config(page_title="AI PDF Auto-Filler & Q/A", layout="wide")
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #3a0ca3 0%, #9d4edd 50%, #c77dff 100%);
    color: white;
    font-family: 'Segoe UI', sans-serif;
}
h1, h2, h3, label, .stTextInput label, .stTextArea label {
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 AI PDF Auto-Filler with Q/A")
st.caption("Upload scanned PDF → Auto-fill missing values → Ask questions → Download AI-filled PDF")

# --- Functions ---
def pdf_to_text(pdf_file):
    try:
        images = convert_from_bytes(pdf_file.read())
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img) + "\n"
        return text
    except Exception as e:
        st.error(f"❌ PDF processing error: {e}")
        return ""

def groq_fill_missing(text):
    prompt = f"""
You are an expert form assistant. The scanned form text below has missing values like 'N/A', 'nan', or '---'.
Please fill missing values realistically and preserve the original layout.

--- FORM START ---
{text}
--- FORM END ---
"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1500
    }
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"❌ Groq API error: {response.text}"
    except Exception as e:
        return f"❌ Request failed: {e}"

def generate_pdf(text):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "AI-Filled Form")
    y -= 30
    c.setFont("Helvetica", 10)

    for line in text.split("\n"):
        if not line.strip():
            y -= 12
            continue
        while len(line) > 110:
            c.drawString(40, y, line[:110])
            line = line[110:]
            y -= 12
        c.drawString(40, y, line.strip())
        y -= 12
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 10)

    c.save()
    buffer.seek(0)
    return buffer

def groq_answer_question(text, question):
    prompt = f"""
You are reading an AI-filled scanned form.

Form Content:
{text}

Answer the following question:
{question}
"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 600
    }
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"❌ Groq API error: {response.text}"
    except Exception as e:
        return f"❌ Request failed: {e}"

# --- Session State ---
st.session_state.setdefault("ocr_text", "")
st.session_state.setdefault("filled_text", "")
st.session_state.setdefault("qa_history", [])

# --- Upload & OCR ---
uploaded = st.file_uploader("📄 Upload Scanned PDF Form", type=["pdf"])
if uploaded:
    if not st.session_state.ocr_text:
        with st.spinner("🔍 Performing OCR..."):
            st.session_state.ocr_text = pdf_to_text(uploaded)

# --- Show Extracted Text ---
if st.session_state.ocr_text:
    st.subheader("🧾 OCR Extracted Text")
    st.text_area("Scanned Text", st.session_state.ocr_text, height=250)

    if st.button("✨ AI Fill Missing Fields"):
        with st.spinner("🤖 AI is filling the missing fields..."):
            st.session_state.filled_text = groq_fill_missing(st.session_state.ocr_text)

# --- Show AI-Filled Output ---
if st.session_state.filled_text:
    st.subheader("✅ AI-Filled Output")
    st.text_area("AI-Filled Text", st.session_state.filled_text, height=250)

    # PDF Download
    pdf_buffer = generate_pdf(st.session_state.filled_text)
    st.download_button("📥 Download AI-Filled PDF", data=pdf_buffer, file_name="AI_Filled_Form.pdf", mime="application/pdf")

    # Ask Questions
    st.subheader("💬 Ask Questions About the Form")
    question = st.text_input("Enter your question:")
    if question:
        with st.spinner("Answering..."):
            answer = groq_answer_question(st.session_state.filled_text, question)
            st.session_state.qa_history.append({"question": question, "answer": answer})

# --- Q&A History ---
if st.session_state.qa_history:
    st.subheader("📚 Q&A History")
    for item in reversed(st.session_state.qa_history):
        st.markdown(f"**Q:** {item['question']}")
        st.success(f"**A:** {item['answer']}")
