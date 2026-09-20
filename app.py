from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
import uuid
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
# লগইন সেশন মনে রাখার জন্য একটি সিক্রেট কী (এটি পরিবর্তন করবেন না)
app.secret_key = "super_secret_ai_notes_key_123" 

# Firebase ডেটাবেস কানেকশন
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Gemini API Key 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# --- লগইন ও রেজিস্ট্রেশন সিস্টেম ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_ref = db.collection('users').document(email)
        if user_ref.get().exists:
            return "এই ইমেইলটি আগে থেকেই আছে! <a href='/login'>লগইন করুন</a>"
        
        hashed_pw = generate_password_hash(password)
        user_ref.set({'email': email, 'password': hashed_pw})
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
            if check_password_hash(user_data['password'], password):
                session['user'] = email
                return redirect(url_for('home'))
        return "ইমেইল বা পাসওয়ার্ড ভুল! <a href='/login'>আবার চেষ্টা করুন</a>"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- হোম পেজ এবং চ্যাট ---
@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_email = session['user']
    session_id = request.args.get('session_id')
    
    # ইউজারের আগের সব চ্যাটের লিস্ট (সাইডবারের জন্য)
    sessions_ref = db.collection('users').document(user_email).collection('sessions').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    sidebar_sessions = []
    for s in sessions_ref:
        sd = s.to_dict()
        sd['id'] = s.id
        sidebar_sessions.append(sd)
        
    # বর্তমান চ্যাটের মেসেজ লোড করা
    history = []
    if session_id:
        msgs = db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').order_by('timestamp').stream()
        for m in msgs:
            history.append(m.to_dict())
            
    return render_template('index.html', history=history, sidebar_sessions=sidebar_sessions, current_session=session_id)

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_email = session['user']
    prompt = request.form.get('prompt')
    session_id = request.form.get('session_id')
    
    # নতুন চ্যাট হলে নতুন আইডি তৈরি করা
    if not session_id or session_id == "None":
        session_id = str(uuid.uuid4())
        
    full_prompt = f"তুমি একজন বিশ্ববিদ্যালয়ের প্রফেসর... [নিময়গুলো মেনে চলবে]\nইউজারের প্রশ্ন: {prompt}"
    
    try:
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content(full_prompt)
        ai_response = response.text
        
        # ডেটাবেসে সেশন (সাইডবারের টাইটেল) তৈরি করা
        session_ref = db.collection('users').document(user_email).collection('sessions').document(session_id)
        if not session_ref.get().exists:
            title = prompt[:25] + "..." if len(prompt) > 25 else prompt
            session_ref.set({'title': title, 'created_at': firestore.SERVER_TIMESTAMP})
        
        # চ্যাটের মেসেজ সেভ করা
        session_ref.collection('messages').add({
            'user_msg': prompt,
            'ai_msg': ai_response,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"response": ai_response, "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
