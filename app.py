from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
import os
import uuid
import random
import smtplib
import base64
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

# ছবিকে এআই-এর পড়ার উপযোগী (Base64) করার ফাংশন
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_ai_response(system_instruction, prompt, image_path=None):
    # যদি ইউজার ছবি আপলোড করে তবে Vision Model কাজ করবে
    if image_path and os.path.exists(image_path):
        base64_image = encode_image(image_path)
        vision_models = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview"
        ]
        last_error = None
        for model_name in vision_models:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"{system_instruction}\n\nইউজারের নির্দেশ: {prompt}"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}",
                                    },
                                },
                            ],
                        }
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                continue
        raise last_error

    # যদি শুধু টেক্সট মেসেজ হয় তবে সাধারণ Text Model কাজ করবে
    else:
        text_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "llama3-70b-8192"
        ]
        last_error = None
        for model_name in text_models:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
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
    saved_filepath = None
    
    system_instruction = """
    তুমি একজন স্মার্ট এআই। 
    ১. সাধারণ প্রশ্নের উত্তর এবং ছবির ভেতরের লেখা বা প্রশ্নের উত্তর পয়েন্ট করে গুছিয়ে বাংলায় দেবে।
    ২. কিন্তু যদি ইউজার কোনো ছবি তৈরি করতে বা আঁকতে বলে (যেমন: "একটি কুকুরের ছবি দাও", "Generate an image", "create a picture"), 
    তাহলে তুমি কোনো ব্যাখ্যামূলক কথা না বলে শুধু নিচের HTML ট্যাগটি উত্তর হিসেবে দেবে:
    <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
    
    * ENGLISH_PROMPT এর জায়গায় ইউজারের চাওয়া ছবিটির একটি সুন্দর ও বিস্তারিত ইংরেজি ডেসক্রিপশন লিখবে এবং শব্দের মাঝখানের স্পেসের বদলে %20 ব্যবহার করবে।
    """
    
    # ছবি আপলোডের লজিক
    if file:
        os.makedirs('static/uploads', exist_ok=True)
        filename = str(uuid.uuid4()) + "_" + file.filename.replace(" ", "_")
        saved_filepath = os.path.join('static/uploads', filename)
        file.save(saved_filepath)
        img_url = '/' + saved_filepath
        
        if not prompt:
            prompt = "এই ছবিতে যা লেখা আছে তা পড়ে বাংলায় নোটস বা উত্তর তৈরি করে দাও।"

    try:
        # ছবি থাকলে ছবি ও টেক্সট একসাথে যাবে, না থাকলে শুধু টেক্সট যাবে
        ai_response = get_ai_response(system_instruction, prompt, image_path=saved_filepath)
        
        session_ref = db.collection('users').document(user_email).collection('sessions').document(session_id)
        if not session_ref.get().exists:
            title = prompt[:25] + "..." if prompt else "Image Upload..."
            session_ref.set({'title': title, 'created_at': firestore.SERVER_TIMESTAMP})
        
        chat_data = {
            'user_msg': prompt,
            'ai_msg': ai_response,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        if img_url:
            chat_data['img_url'] = img_url
            
        update_time, doc_ref = session_ref.collection('messages').add(chat_data)
        
        return jsonify({"response": ai_response, "session_id": session_id, "img_url": img_url, "msg_id": doc_ref.id})
    except Exception as e:
        return jsonify({"error": str(e)})

# --- চ্যাট এডিট রুট (Fixed 404 temp-id Error & Added Image Support) ---
@app.route('/edit_chat', methods=['POST'])
def edit_chat():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_email = session['user']
    prompt = request.form.get('prompt')
    session_id = request.form.get('session_id')
    msg_id = request.form.get('msg_id')
    
    system_instruction = """
    তুমি একজন স্মার্ট এআই। 
    ১. সাধারণ প্রশ্নের উত্তর এবং ছবির ভেতরের লেখা বা প্রশ্নের উত্তর পয়েন্ট করে গুছিয়ে বাংলায় দেবে।
    ২. কিন্তু যদি ইউজার কোনো ছবি তৈরি করতে বা আঁকতে বলে (যেমন: "একটি কুকুরের ছবি দাও", "Generate an image", "create a picture"), 
    তাহলে তুমি কোনো ব্যাখ্যামূলক কথা না বলে শুধু নিচের HTML ট্যাগটি উত্তর হিসেবে দেবে:
    <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
    
    * ENGLISH_PROMPT এর জায়গায় ইউজারের চাওয়া ছবিটির একটি সুন্দর ও বিস্তারিত ইংরেজি ডেসক্রিপশন লিখবে এবং শব্দের মাঝখানের স্পেসের বদলে %20 ব্যবহার করবে।
    """
    
    try:
        saved_filepath = None
        doc_ref = None
        
        # আগের মেসেজে কোনো ছবি ছিল কি না তা চেক করা হচ্ছে
        if session_id and session_id != "None" and msg_id and not str(msg_id).startswith('temp-'):
            doc_ref = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').document(msg_id)
            doc_snap = doc_ref.get()
            if doc_snap.exists:
                img_url = doc_snap.to_dict().get('img_url')
                if img_url:
                    potential_path = img_url.lstrip('/')
                    if os.path.exists(potential_path):
                        saved_filepath = potential_path

        # এআই থেকে নতুন উত্তর নেওয়া (ছবি থাকলে ছবি সহ)
        ai_response = get_ai_response(system_instruction, prompt, image_path=saved_filepath)
        
        # যদি মেসেজটি ডেটাবেসে আগে থেকেই থাকে তবে আপডেট করবে, আর temp- হলে নতুন করে সেভ করবে (ফলে 404 এরর আসবে না)
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
