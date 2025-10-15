import streamlit as st
import os
from PyPDF2 import PdfReader
from docx import Document
import pandas as pd
from gtts import gTTS
import tempfile
import json
import random
import string
import time
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv

# --- Load OpenAI API key ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Create sessions folder ---
os.makedirs('sessions', exist_ok=True)

# --- Unique user ID ---
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
user_file = f'sessions/{st.session_state["user_id"]}.json'

# --- Load chat history ---

if os.path.exists(user_file):
    with open(user_file, 'r') as f:
        try:
            chat_history = json.load(f)
        except:
            chat_history = []
else:
    chat_history = []

# --- Sidebar ---
st.sidebar.title("💬 Chat History")
# --- New Chat Button ---
if st.sidebar.button("➕ New Chat"):
    chat_history = []
    st.session_state['user_id'] = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    user_file = f'sessions/{st.session_state["user_id"]}.json'
    with open(user_file, 'w') as f:
        json.dump(chat_history, f)
    st.session_state['file_text'] = ""
    st.rerun()




# --- Load previous chat sessions ---
session_files = sorted(os.listdir("sessions"), reverse=True)

for filename in session_files:
    filepath = os.path.join("sessions", filename)
    try:
        with open(filepath, "r") as f:
            chats = json.load(f)
        if not chats:
            continue  # skip empty chat
        last_msg = next((c.get("message", "") for c in reversed(chats) if c.get("message")), "")
        if not last_msg:
            continue
        preview = last_msg[:50].replace("\n", " ") + "..."
        if st.sidebar.button(preview, key=filename):
            with open(filepath, "r") as f:
                chat_history = json.load(f)
            st.session_state['user_id'] = filename.replace(".json", "")
            st.rerun()
    except Exception:
        continue



# --- Initialize states ---
st.session_state.setdefault('show_uploader', False)
st.session_state.setdefault('file_text', "")
st.session_state.setdefault('thinking', False)

# --- Title ---
st.title("💬 Company Chatbot (Powered by OpenAI 🤖)")

# --- CSS (UI same as before) ---
st.markdown("""
<style>
.main { padding-bottom: 110px !important; }
.chat-input {
    position: fixed; bottom: 0; left: 0; width: 100%;
    background-color: #fafafa; border-top: 1px solid #ddd;
    padding: 12px 6%; z-index: 999;
}
.stChatMessage { margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# --- Chat Container ---
chat_container = st.container()
with chat_container:
    for chat in chat_history:
        role = chat.get("role", "user").lower()
        message = chat.get("message", "")
        with st.chat_message(role):
            st.markdown(message, unsafe_allow_html=True)

# --- Thinking message ---
if st.session_state['thinking']:
    st.markdown("<p style='text-align:center; color:gray;'>🤖 Thinking... Please wait</p>", unsafe_allow_html=True)

# --- Input Bar ---
st.markdown('<div class="chat-input">', unsafe_allow_html=True)
with st.form(key='chat_form', clear_on_submit=True):
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])
    with col1:
        user_input = st.text_input("Type your message", key='msg_input', label_visibility="collapsed")
    with col2:
        if st.form_submit_button("📎"):
            st.session_state['show_uploader'] = True
    with col3:
        if st.form_submit_button("🎙"):
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                st.info("🎙 Speak now...")
                audio = recognizer.listen(source, timeout=5)
            try:
                user_input = recognizer.recognize_google(audio)
                st.success(f"You said: {user_input}")
            except Exception as e:
                st.error(f"Speech not recognized: {e}")
    with col4:
        submit_button = st.form_submit_button("Send")
st.markdown('</div>', unsafe_allow_html=True)

# --- File Uploader ---
uploaded_file = st.file_uploader("Choose a file", type=['txt', 'pdf', 'docx', 'csv']) if st.session_state['show_uploader'] else None

# --- File Text Extraction ---
def extract_text_from_file(file):
    try:
        if file.type == 'application/pdf':
            pdf = PdfReader(file)
            return ''.join([page.extract_text() or "" for page in pdf.pages])
        elif file.type == 'text/plain':
            return file.getvalue().decode('utf-8')
        elif file.type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            doc = Document(file)
            return '\n'.join([p.text for p in doc.paragraphs])
        elif file.type == 'text/csv':
            df = pd.read_csv(file)
            return df.to_csv(index=False)
    except Exception as e:
        st.error(f"⚠ File reading error: {e}")
    return ""

# --- Main Chat Logic ---
if submit_button and user_input:
    st.session_state['thinking'] = True
    st.rerun()

if st.session_state['thinking'] and 'msg_input' in st.session_state:
    user_input = st.session_state['msg_input']
    if user_input:
        if uploaded_file is not None:
            text = extract_text_from_file(uploaded_file)
            if text:
                st.session_state['file_text'] = text

        context = st.session_state['file_text']
        prompt = f"User message: {user_input}\n\nFile content (if any): {context}"

        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that can analyze documents, answer questions, and summarize content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            bot_reply = completion.choices[0].message.content.strip()
        except Exception as e:
            bot_reply = f"⚠ API Error: {e}"

        chat_history.append({'role': 'User', 'message': user_input})
        chat_history.append({'role': 'Bot', 'message': bot_reply})
        with open(user_file, 'w') as f:
            json.dump(chat_history, f, indent=4)

        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("bot"):
                st.markdown(bot_reply, unsafe_allow_html=True)

        try:
            tts = gTTS(bot_reply, lang='en')
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(temp_file.name)
            time.sleep(1)
            st.audio(temp_file.name, format='audio/mp3')
        except Exception as e:
            st.error(f"🎙 Voice error: {e}")

        st.session_state['thinking'] = False