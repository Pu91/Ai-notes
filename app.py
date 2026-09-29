from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
import os
import io
import re
import uuid
import random
import smtplib
import base64
from PIL import Image
import PyPDF2
from email.mime.text import MIMEText
from datetime import timedelta
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

from main_prompt import get_system_instruction, OCR_PROMPT, get_image_notes_prompt

app = Flask(__name__)
app.secret_key = "super_secret_ai_notes_key_123"
app.permanent_session_lifetime = timedelta(days=30)

# Firebase Setup
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Groq Setup
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def encode_image(image_path):
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((1400, 1400))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=88)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

def clean_and_format_response(text):
    if not text or "<img" in text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?m)^#{1,6}\s*(.*?)$', r'<b>\1</b>', text)
    text = re.sub(r'</?u>', '', text)
    text = re.sub(r'(?m)^\s*\*\s+', '• ', text)
    text = re.sub(r'(?m)^\s*-\s+', '• ', text)
    return text

# টোকেন বাঁচানোর জন্য চেক করা: ইউজার কি আগের মেসেজের ওপর ডাউট, পয়েন্ট বা পরের ধাপের প্রশ্ন (5 Marks / বাকি প্রশ্ন) চাইছে?
def needs_previous_context(prompt_text, has_new_image=False):
    if has_new_image:
        return False
    
    q = prompt_text.lower()
    if "mode: doubt solve" in q:
        return True

    clean_user_text = re.sub(r'\[.*?\]\s*', '', q).strip()

    followup_keywords = [
        "নম্বর", "নাম্বার", "নম্বরের", "number", "no", "দাগ", "পয়েন্ট", "পয়েন্ট", "point", "pint", "টপিক", "topic",
        "টপিকের", "বাকি", "baki", "পরের", "porer", "marks", "মার্কস", "প্রশ্নটা", "উত্তরটা", "প্রশ্নগুলো", "উত্তরগুলো",
        "বড়", "বড়", "boro", "ছোট", "choto", "আগের", "ager", "আবার", "abar", "এবার", "ebar",
        "বুঝিয়ে", "বুঝিয়ে", "বোঝাও", "bujhiye", "এটা", "ওটা", "ata", "ota", "এই", "oi", "বলো", "bolo",
        "ব্যাখ্যা", "explain", "detail", "short", "ডাউট", "doubt", "কেন", "কিভাবে",
        "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯", "১০",
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"
    ]
    if any(word in clean_user_text for word in followup_keywords):
        return True

    if len(clean_user_text.split()) <= 12:
        return True

    return False

# টোকেন বাঁচিয়ে শুরুর মূল টপিক/ছবির লেখা এবং শেষের ২টি মেসেজ অক্ষুণ্ণ রেখে হিস্ট্রি আনার ফাংশন
def get_smart_chat_history(user_email, session_id, exclude_msg_id=None):
    history_messages = []
    if not session_id or session_id == "None":
        return history_messages
    try:
        msgs_ref = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').order_by('timestamp').stream()
        raw_list = []
        for m in msgs_ref:
            if exclude_msg_id and m.id == exclude_msg_id:
                break
            raw_list.append(m.to_dict())

        if not raw_list:
            return history_messages

        # চ্যাটের শুরুতে বা আগে কোনো ছবি/সিলেবাস দেওয়া থাকলে সেটির টপিক মনে রাখা (যাতে ৩ নম্বর ধাপে গিয়েও মূল টপিক না ভোলে)
        base_topic_context = ""
        for item in raw_list:
            if item.get('ocr_text'):
                base_topic_context = f"[এই চ্যাটের মূল সিলেবাস/ছবির লেখা:\n{item.get('ocr_text')[:1200]}]\n"
                break
        if not base_topic_context and len(raw_list) > 2:
            first_u_msg = re.sub(r'\[.*?\]\s*', '', raw_list[0].get('user_msg', '')).strip()
            if first_u_msg:
                base_topic_context = f"[এই চ্যাটের মূল আলোচ্য টপিক: {first_u_msg[:500]}]\n"

        # শেষের ২টি মেসেজ নেওয়া হচ্ছে (যাতে ১–৫ নম্বর প্রশ্ন দেওয়ার পর ৬ নম্বর থেকে দেওয়ার সময় আগের প্রশ্নগুলো মনে থাকে)
        recent_items = raw_list[-2:]
        for idx, item in enumerate(recent_items):
            u_msg = re.sub(r'\[.*?\]\s*', '', item.get('user_msg', '')).strip()
            ocr_txt = item.get('ocr_text', '')
            a_msg = item.get('ai_msg', '')

            if ocr_txt:
                u_msg = f"আগের ছবির প্রশ্ন/সিলেবাস:\n{ocr_txt[:1200]}\nইউজারের নির্দেশ: {u_msg}"
            elif idx == 0 and base_topic_context:
                u_msg = f"{base_topic_context}ইউজারের নির্দেশ: {u_msg}"

            if u_msg:
                history_messages.append({"role": "user", "content": u_msg[:1400]})
            if a_msg:
                # ক্লিক বাটনের কোড বাদ দিয়ে এবং লাইন ব্রেক (\n) ঠিক রেখে আগের উত্তরটি মেমোরিতে দেওয়া হচ্ছে
                clean_a_msg = re.sub(r'<div onclick=.*?</div>', '', a_msg, flags=re.DOTALL)
                clean_a_msg = re.sub(r'<br\s*/?>', '\n', clean_a_msg)
                clean_a_msg = re.sub(r'<[^>]+>', '', clean_a_msg)
                clean_a_msg = re.sub(r'\n{3,}', '\n\n', clean_a_msg).strip()
                history_messages.append({"role": "assistant", "content": clean_a_msg[:3200]})
    except Exception:
        pass
    return history_messages

def get_ai_response(prompt, base64_image=None, chat_history=None):
    final_prompt = prompt
    combined_context = prompt
    extracted_image_text = ""

    # ১. যদি মেসেজে নতুন ছবি থাকে -> Qwen 3.8 Vision দিয়ে ছবির লেখা পড়ে নেওয়া হবে
    if base64_image:
        try:
            vision_response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                temperature=0.2,
                max_tokens=750
            )
            extracted_image_text = vision_response.choices[0].message.content
            final_prompt = get_image_notes_prompt(extracted_image_text, prompt)
            combined_context = f"{extracted_image_text} {prompt}"
        except Exception as e:
            raise Exception(f"Vision Model Error: {str(e)}")

    system_instruction = get_system_instruction(combined_context)

    messages_payload = [{"role": "system", "content": system_instruction}]
    if chat_history:
        messages_payload.extend(chat_history)
        p_lower = prompt.lower()
        # ইউজার কি ৫ নম্বরের প্রশ্ন বা বাকি থাকা পরের প্রশ্নগুলোর বাটনে ক্লিক করেছে?
        if any(k in p_lower for k in ["5 marks", "৫ নম্বরের", "বাকি থাকা", "৬ নম্বর থেকে"]):
            final_prompt = f"""{final_prompt}

[জরুরি নির্দেশ: ওপরে দেওয়া আগের মেসেজের মূল টপিক/সিলেবাস এবং আগের প্রশ্নোত্তরগুলো দেখো। ইউজার যদি ৫ নম্বরের প্রশ্ন চায় তবে প্রথমে ১ থেকে ৫ নম্বর পর্যন্ত বড় প্রশ্নোত্তর (প্রতিটি ৬-৭ লাইনের ওপরে) দাও এবং আরও বাকি থাকলে নিচে ক্লিক করার আন্ডারলাইন কোডটি দাও। আর যদি ইউজার 'বাকি থাকা পরের ৫ নম্বরের প্রশ্ন (৬ নম্বর থেকে)' চায়, তবে আগের ১-৫ নম্বর প্রশ্নগুলো রিপিট না করে ৬ নম্বর থেকে বাকি সব প্রশ্নোত্তর দাও এবং শেষে ১২ নম্বরের সমাপ্তি নোটটি লিখে দাও।]"""
        else:
            final_prompt = f"""{final_prompt}

[জরুরি নির্দেশ: ইউজার ওপরে দেওয়া তোমার আগের উত্তরের (Previous Assistant Message) পরিপ্রেক্ষিতে এই প্রশ্নটি করেছে। ইউজার যদি '2 number point/pint', '২ নম্বর টপিক' বা কোনো নির্দিষ্ট ক্রমিক নম্বর উল্লেখ করে, তবে তোমার আগের উত্তরের ভেতরে থাকা সেই ক্রমিক নম্বরের পয়েন্ট বা টপিকটিই বিস্তারিতভাবে বুঝিয়ে বলো। ভুলেও সেটিকে '২ নম্বরের প্রশ্ন (2-Mark Question)' ভাববে না!]"""

    messages_payload.append({"role": "user", "content": final_prompt})

    # ২. মূল উত্তর তৈরি করবে OpenAI GPT-OSS-120B মডেল
    text_models = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b"
    ]
    
    last_error = None
    for model_name in text_models:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages_payload,
                "temperature": 0.3
            }
            if "qwen" in model_name:
                kwargs["max_tokens"] = 750

            response = client.chat.completions.create(**kwargs)
            raw_reply = response.choices[0].message.content
            return clean_and_format_response(raw_reply), extracted_image_text
        except Exception as e:
            last_error = e
            continue
            
    raise last_error

# --- লগইন ও রেজিস্ট্রেশন ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_ref = db.collection('users').document(email)
        
        if user_ref.get().exists:
            flash("এই ইমেইলটি আগে থেকেই রেজিস্টার করা আছে!", "error")
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password)
        user_ref.set({'email': email, 'password': hashed_pw, 'auth_provider': 'email'})
        session.permanent = True
        session['user'] = email
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_ref = db.collection('users').document(email).get()
        
        if user_ref.exists:
            user_data = user_ref.to_dict()
            if user_data.get('auth_provider') == 'google':
                flash("এই অ্যাকাউন্টটি গুগল দিয়ে খোলা হয়েছে। দয়া করে 'Continue with Google' এ ক্লিক করুন।", "error")
            elif check_password_hash(user_data['password'], password):
                session.permanent = True
                session['user'] = email
                return redirect(url_for('home'))
            else:
                flash("পাসওয়ার্ড ভুল হয়েছে!", "error")
        else:
            flash("এই ইমেইল দিয়ে কোনো অ্যাকাউন্ট নেই!", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/google-login', methods=['POST'])
def google_login():
    token = request.json.get('token')
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        email = decoded_token.get('email')
        user_ref = db.collection('users').document(email)
        if not user_ref.get().exists:
            user_ref.set({'email': email, 'auth_provider': 'google'})
        session.permanent = True
        session['user'] = email
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 401

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- Forgot Password (OTP Flow) ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("দয়া করে ইমেইল দিন!", "error")
            return redirect(url_for('forgot_password'))
            
        user_ref = db.collection('users').document(email).get()
        if not user_ref.exists:
            flash("এই ইমেইলটি আমাদের সিস্টেমে নেই!", "error")
            return redirect(url_for('forgot_password'))
            
        otp = str(random.randint(1000, 9999))
        session['reset_email'] = email
        session['otp'] = otp
        
        sender_email = "Puspenduhaldar652@gmail.com"
        sender_password = "tuelxovrkmfeqolr"

        try:
            msg = MIMEText(f"আপনার পাসওয়ার্ড রিসেট করার OTP কোড হলো: {otp}", 'plain', 'utf-8')
            msg['Subject'] = 'AI Notes - Password Reset'
            msg['From'] = f"AI Notes <{sender_email}>"
            msg['To'] = email

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [email], msg.as_string())
            flash("আপনার ইমেইলে OTP পাঠানো হয়েছে! ইনবক্স চেক করুন।", "success")
            return redirect(url_for('verify_otp'))
        except Exception as e:
            flash("ইমেইল পাঠাতে সমস্যা হচ্ছে। দয়া করে আবার চেষ্টা করুন।", "error")
            return redirect(url_for('forgot_password'))
    return render_template('forgot.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        if user_otp == session.get('otp'):
            email = session.get('reset_email')
            hashed_pw = generate_password_hash(new_password)
            db.collection('users').document(email).update({'password': hashed_pw})
            flash("পাসওয়ার্ড সফলভাবে পরিবর্তন হয়েছে! এবার লগইন করুন।", "success")
            return redirect(url_for('login'))
        else:
            flash("OTP ভুল হয়েছে!", "error")
            return redirect(url_for('verify_otp'))
    return render_template('verify.html')

# --- চ্যাট এবং হোমপেজ ---
@app.route('/')
def home():
    if 'user' not in session: return redirect(url_for('login'))
    user_email = session['user']
    session_id = request.args.get('session_id')
    
    sessions_ref = db.collection('users').document(user_email).collection('sessions').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    sidebar_sessions = [{'id': s.id, **s.to_dict()} for s in sessions_ref]
        
    history = []
    if session_id:
        msgs = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').order_by('timestamp').stream()
        for m in msgs: 
            data = m.to_dict()
            data['id'] = m.id 
            history.append(data)
            
    return render_template('index.html', history=history, sidebar_sessions=sidebar_sessions, current_session=session_id, user_email=user_email)

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_email = session['user']
    prompt = request.form.get('prompt') or ""
    session_id = request.form.get('session_id')
    file = request.files.get('file')
    
    is_new_session = False
    if not session_id or session_id == "None":
        session_id = str(uuid.uuid4())
        is_new_session = True
    
    img_url = None
    base64_image = None
    
    if file:
        os.makedirs('static/uploads', exist_ok=True)
        filename = str(uuid.uuid4()) + "_" + file.filename.replace(" ", "_")
        filepath = os.path.join('static/uploads', filename)
        file.save(filepath)
        
        if filename.lower().endswith('.pdf'):
            try:
                reader = PyPDF2.PdfReader(filepath)
                pdf_text = ""
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""
                prompt = f"{prompt}\n\n[PDF Content]:\n{pdf_text[:4000]}"
            except Exception:
                pass
        else:
            img_url = '/' + filepath
            base64_image = encode_image(filepath)
        
        if not prompt:
            prompt = "এই ছবিতে যা লেখা বা প্রশ্ন আছে তার বিস্তারিত নোটস এবং উত্তর বাংলায় তৈরি করে দাও।"

    try:
        chat_history = []
        if not is_new_session and needs_previous_context(prompt, has_new_image=(base64_image is not None)):
            chat_history = get_smart_chat_history(user_email, session_id)

        ai_response, extracted_ocr_text = get_ai_response(prompt, base64_image=base64_image, chat_history=chat_history)
        
        session_ref = db.collection('users').document(user_email).collection('sessions').document(session_id)
        if not session_ref.get().exists:
            clean_title = re.sub(r'\[.*?\]\s*', '', prompt).strip()
            title = (clean_title[:25] + "...") if clean_title else "Image Notes..."
            session_ref.set({'title': title, 'created_at': firestore.SERVER_TIMESTAMP})
        
        chat_data = {
            'user_msg': prompt,
            'ai_msg': ai_response,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        if img_url:
            chat_data['img_url'] = img_url
        if base64_image:
            chat_data['img_b64'] = base64_image
        if extracted_ocr_text:
            chat_data['ocr_text'] = extracted_ocr_text
            
        update_time, doc_ref = session_ref.collection('messages').add(chat_data)
        
        return jsonify({"response": ai_response, "session_id": session_id, "img_url": img_url, "msg_id": doc_ref.id})
    except Exception as e:
        return jsonify({"error": str(e)})

# --- চ্যাট এডিট রুট ---
@app.route('/edit_chat', methods=['POST'])
def edit_chat():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_email = session['user']
    prompt = request.form.get('prompt')
    session_id = request.form.get('session_id')
    msg_id = request.form.get('msg_id')
    
    try:
        base64_image = None
        doc_ref = None
        
        if session_id and session_id != "None" and msg_id and not str(msg_id).startswith('temp-'):
            doc_ref = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').document(msg_id)
            doc_snap = doc_ref.get()
            if doc_snap.exists:
                doc_data = doc_snap.to_dict()
                base64_image = doc_data.get('img_b64')
                if not base64_image and doc_data.get('img_url'):
                    potential_path = doc_data.get('img_url').lstrip('/')
                    if os.path.exists(potential_path):
                        base64_image = encode_image(potential_path)

        chat_history = []
        if needs_previous_context(prompt, has_new_image=(base64_image is not None)):
            chat_history = get_smart_chat_history(user_email, session_id, exclude_msg_id=msg_id)

        ai_response, extracted_ocr_text = get_ai_response(prompt, base64_image=base64_image, chat_history=chat_history)
        
        if doc_ref and doc_ref.get().exists:
            update_payload = {
                'user_msg': prompt,
                'ai_msg': ai_response
            }
            if extracted_ocr_text:
                update_payload['ocr_text'] = extracted_ocr_text
            doc_ref.update(update_payload)
        elif session_id and session_id != "None":
            db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').add({
                'user_msg': prompt,
                'ai_msg': ai_response,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
