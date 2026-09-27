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

# ছবিকে পরিষ্কার রেখে অপটিমাইজড Base64 করার ফাংশন
def encode_image(image_path):
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((1400, 1400))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=88)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

# অগোছালো ** বা ### চিহ্ন সরিয়ে পরিষ্কার ও সুন্দর সাজানো টেক্সট তৈরি করার ফাংশন
def clean_and_format_response(text):
    if not text or "<img" in text:
        return text
    # যদি এআই ভুল করেও **বোল্ড** লেখে, সেটিকে HTML <b> ট্যাগে রূপান্তর করবে যাতে ** দেখা না যায়
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # লাইনের শুরুতে থাকা অপ্রয়োজনীয় ### বা ## সরিয়ে বোল্ড করে দেওয়া
    text = re.sub(r'(?m)^#{1,6}\s*(.*?)$', r'<b><u>\1</u></b>', text)
    # যেকোনো ছড়িয়ে ছিটিয়ে থাকা সিঙ্গেল * চিহ্নকে বুলেট পয়েন্ট (•) করে দেওয়া
    text = re.sub(r'(?m)^\s*\*\s+', '• ', text)
    text = re.sub(r'(?m)^\s*-\s+', '• ', text)
    return text

# এআই-এর জন্য মাস্টার ফরম্যাটিং নির্দেশাবলী
SYSTEM_INSTRUCTION = """
তুমি একজন অত্যন্ত দক্ষ ও অভিজ্ঞ এআই শিক্ষক এবং নোটস মেকার। উত্তর দেওয়ার সময় নিচের নিয়মগুলো কঠোরভাবে মেনে চলবে:

১. কোনো অবস্থাতেই লেখার ভেতরে স্টার চিহ্ন (** বা *) কিংবা হ্যাশট্যাগ (### বা ##) ব্যবহার করবে না। 
২. পুরো উত্তরটি একদম পরিষ্কার, সুন্দর ও গোছানো বাংলায় লিখবে। প্রতিটি প্যারাগ্রাফের মাঝে ফাঁকা লাইন রাখবে যাতে পড়তে আরামদায়ক হয়।
৩. প্রধান পয়েন্টগুলো ১., ২., ৩. এভাবে নম্বর দিয়ে লিখবে এবং পয়েন্টের হেডিং বোল্ড করবে (যেমন: <b>১. প্রধান বিষয়:</b>)।
৪. ভেতরের সাব-পয়েন্ট বা বৈশিষ্ট্যগুলো লেখার সময় অবশ্যই গোল বুলেট (• বা ○) ব্যবহার করবে এবং পয়েন্টের মূল শব্দটির নিচে আন্ডারলাইন করে তারপর বিস্তারিত লিখবে। 
   উদাহরণস্বরূপ:
   • <u><b>বৈশিষ্ট্য:</b></u> এখানে খুব সহজ ও সুন্দরভাবে বিস্তারিত ব্যাখ্যা লিখবে।
   • <u><b>গঠন ও কাজ:</b></u> এখানে ওই বিষয়ের গঠন ও কাজ গুছিয়ে লিখবে।
   • <u><b>উদাহরণ:</b></u> উপযুক্ত উদাহরণ দেবে।
৫. ইউজার যদি কোনো কিছুর 'পার্থক্য' (Difference), তুলনা বা ছক চায়, তবে কোনো সাধারণ লেখার বদলে অবশ্যই নিচের মতো পরিষ্কার HTML Table তৈরি করে দেবে:
   <table style="width:100%; border-collapse:collapse; margin:12px 0; font-size:15px;">
     <thead>
       <tr style="background-color:#2563eb; color:#ffffff; text-align:left;">
         <th style="border:1px solid #cbd5e1; padding:8px;">বিষয়</th>
         <th style="border:1px solid #cbd5e1; padding:8px;">প্রথম বিষয়</th>
         <th style="border:1px solid #cbd5e1; padding:8px;">দ্বিতীয় বিষয়</th>
       </tr>
     </thead>
     <tbody>
       <tr>
         <td style="border:1px solid #cbd5e1; padding:8px;"><b>১. সংজ্ঞা</b></td>
         <td style="border:1px solid #cbd5e1; padding:8px;">...</td>
         <td style="border:1px solid #cbd5e1; padding:8px;">...</td>
       </tr>
     </tbody>
   </table>
৬. যদি ইউজার কোনো ছবি আঁকতে বা জেনারেট করতে বলে (যেমন: "একটি বাঘের ছবি দাও", "Generate an image"), শুধুমাত্র তখন কোনো কথা না বলে নিচের HTML ট্যাগটি দেবে:
   <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
"""

def get_ai_response(prompt, base64_image=None):
    final_prompt = prompt

    # ১. যদি মেসেজে ছবি থাকে -> Qwen 3.8 Vision দিয়ে ছবির সব লেখা ও প্রশ্ন নিখুঁতভাবে পড়ে নেওয়া হবে
    if base64_image:
        try:
            vision_response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Read this image carefully and transcribe all the text, syllabus topics, headings, and questions completely and accurately."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.2,
                max_tokens=750  # ১০০০ টোকেন লিমিটের নিচে রাখা হয়েছে যাতে 429 এরর না আসে
            )
            extracted_image_text = vision_response.choices[0].message.content
            
            # এখানে টেক্সট মডেলকে স্পষ্ট বলে দেওয়া হচ্ছে যাতে সে কখনোই না বলে যে সে ছবি দেখতে পাচ্ছে না
            final_prompt = f"""ইউজার একটি সিলেবাস বা প্রশ্নপত্রের ছবি আপলোড করেছে। ছবিটির ভেতরে নিচের লেখাগুলো রয়েছে:

--- ছবির ভেতরের লেখা ---
{extracted_image_text}
-------------------------

ইউজারের নির্দেশ: "{prompt}"

বিশেষ নির্দেশ: তুমি কখনোই বলবে না যে "আমি সরাসরি ছবিটি দেখতে পাচ্ছি না" বা "টেক্সটটি লিখে দিন"—কারণ ছবির সব লেখা ওপরে তোমাকে দেওয়া হয়েছে। ওপরের লেখাগুলোর প্রতিটি টপিক বা প্রশ্নের জন্য ১, ২ করে পয়েন্ট দিয়ে, • <u><b>বৈশিষ্ট্য:</b></u> এভাবে আন্ডারলাইন করে এবং প্রয়োজনে পার্থক্যের টেবিল বানিয়ে অত্যন্ত সুন্দর ও বিস্তারিত বাংলা নোটস তৈরি করে দাও।"""
        except Exception as e:
            raise Exception(f"Vision Model Error: {str(e)}")

    # ২. মূল উত্তর ও গোছানো বাংলা নোটস তৈরি করবে OpenAI GPT-OSS-120B মডেল
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
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": final_prompt}
                ],
                "temperature": 0.4
            }
            if "qwen" in model_name:
                kwargs["max_tokens"] = 750

            response = client.chat.completions.create(**kwargs)
            raw_reply = response.choices[0].message.content
            return clean_and_format_response(raw_reply)
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
    
    if not session_id or session_id == "None": session_id = str(uuid.uuid4())
    
    img_url = None
    base64_image = None
    
    # ফাইল এবং ছবি আপলোডের লজিক
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
            prompt = "এই ছবিতে যা লেখা বা প্রশ্ন আছে তার বিস্তারিত নোটস এবং উত্তর বাংলায় তৈরি করে দাও।"

    try:
        ai_response = get_ai_response(prompt, base64_image=base64_image)
        
        session_ref = db.collection('users').document(user_email).collection('sessions').document(session_id)
        if not session_ref.get().exists:
            title = prompt[:25] + "..." if prompt else "Image Notes..."
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

        # যদি আগের কোনো পুরনো মেসেজে (যেখানে ছবি সেভ হয়নি) ইউজার পেন্সিল আইকন চাপে, তবে সেশনের শেষ ছবিটি খুঁজে নেবে
        if not base64_image and session_id and session_id != "None":
            recent_msgs = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(5).stream()
            for m in recent_msgs:
                m_data = m.to_dict()
                if m_data.get('img_b64'):
                    base64_image = m_data.get('img_b64')
                    break
                elif m_data.get('img_url'):
                    potential_path = m_data.get('img_url').lstrip('/')
                    if os.path.exists(potential_path):
                        base64_image = encode_image(potential_path)
                        break

        ai_response = get_ai_response(prompt, base64_image=base64_image)
        
        if doc_ref and doc_ref.get().exists:
            doc_ref.update({
                'user_msg': prompt,
                'ai_msg': ai_response
            })
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
