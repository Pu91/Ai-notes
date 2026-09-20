from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
import uuid
import random
import smtplib
from email.mime.text import MIMEText
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

app = Flask(__name__)
app.secret_key = "super_secret_ai_notes_key_123" 

# Firebase Setup
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Gemini API Key Setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

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
                flash("এই অ্যাকাউন্টটি গুগল দিয়ে খোলা হয়েছে। দয়া করে 'Continue with Google' এ ক্লিক করুন।", "error")
            elif check_password_hash(user_data['password'], password):
                session['user'] = email
                return redirect(url_for('home'))
            else:
                flash("পাসওয়ার্ড ভুল হয়েছে!", "error")
        else:
            flash("এই ইমেইল দিয়ে কোনো অ্যাকাউন্ট নেই!", "error")
            
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
        user_ref = db.collection('users').document(email).get()
        if not user_ref.exists:
            flash("এই ইমেইলটি আমাদের সিস্টেমে নেই!", "error")
            return redirect(url_for('forgot_password'))
            
        otp = str(random.randint(1000, 9999))
        session['reset_email'] = email
        session['otp'] = otp
        
        # --- সত্যিকারের ইমেইল পাঠানোর কোড ---
        sender_email = "আপনার_জিমেইল@gmail.com"  # <--- এখানে আপনার আসল জিমেইলটি দিন
        sender_password = "tuelxovrkmfeqolr"     # <--- আপনার দেওয়া App Password বসানো হয়েছে

        msg = MIMEText(f"আপনার পাসওয়ার্ড রিসেট করার OTP কোড হলো: {otp}")
        msg['Subject'] = 'AI Notes - Password Reset OTP'
        msg['From'] = f"AI Notes <{sender_email}>"
        msg['To'] = email

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [email], msg.as_string())
            flash("আপনার ইমেইলে OTP পাঠানো হয়েছে! ইনবক্স বা স্প্যাম ফোল্ডার চেক করুন।", "success")
            return redirect(url_for('verify_otp'))
        except Exception as e:
            print("Email Error:", e)
            flash("ইমেইল পাঠাতে সার্ভার সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।", "error")
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
            flash("পাসওয়ার্ড সফলভাবে পরিবর্তন হয়েছে! এবার লগইন করুন।", "success")
            return redirect(url_for('login'))
        else:
            flash("OTP ভুল হয়েছে!", "error")
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
        for m in msgs: history.append(m.to_dict())
            
    return render_template('index.html', history=history, sidebar_sessions=sidebar_sessions, current_session=session_id)

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_email = session['user']
    prompt = request.form.get('prompt')
    session_id = request.form.get('session_id')
    
    if not session_id or session_id == "None": session_id = str(uuid.uuid4())
    full_prompt = f"তুমি একজন স্মার্ট টিউটর। পয়েন্ট করে গুছিয়ে উত্তর দেবে।\nইউজারের প্রশ্ন: {prompt}"
    
    try:
        model = genai.GenerativeModel('gemini-3.8-flash')
        ai_response = model.generate_content(full_prompt).text
        
        session_ref = db.collection('users').document(user_email).collection('sessions').document(session_id)
        if not session_ref.get().exists:
            session_ref.set({'title': prompt[:25] + "...", 'created_at': firestore.SERVER_TIMESTAMP})
        
        session_ref.collection('messages').add({'user_msg': prompt, 'ai_msg': ai_response, 'timestamp': firestore.SERVER_TIMESTAMP})
        return jsonify({"response": ai_response, "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
