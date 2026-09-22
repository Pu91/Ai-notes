from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
import uuid
import random
import smtplib
from email.mime.text import MIMEText
from datetime import timedelta
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

app = Flask(__name__)
app.secret_key = "super_secret_ai_notes_key_123" 
# à¦à¦•à¦¬à¦¾à¦° à¦²à¦—à¦‡à¦¨ à¦•à¦°à¦²à§‡ à§©à§¦ à¦¦à¦¿à¦¨ à¦²à¦—à¦‡à¦¨ à¦¥à¦¾à¦•à¦¬à§‡
app.permanent_session_lifetime = timedelta(days=30) 

# Firebase Setup
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# --- à¦²à¦—à¦‡à¦¨ à¦“ à¦°à§‡à¦œà¦¿à¦¸à§à¦Ÿà§à¦°à§‡à¦¶à¦¨ ---l
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_ref = db.collection('users').document(email)
        
        if user_ref.get().exists:
            flash("à¦à¦‡ à¦‡à¦®à§‡à¦‡à¦²à¦Ÿà¦¿ à¦†à¦—à§‡ à¦¥à§‡à¦•à§‡à¦‡ à¦°à§‡à¦œà¦¿à¦¸à§à¦Ÿà¦¾à¦° à¦•à¦°à¦¾ à¦†à¦›à§‡!", "error")
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
                flash("à¦à¦‡ à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿà¦Ÿà¦¿ à¦—à§à¦—à¦² à¦¦à¦¿à§Ÿà§‡ à¦–à§‹à¦²à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ 'Continue with Google' à¦ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨à¥¤", "error")
            elif check_password_hash(user_data['password'], password):
                session.permanent = True
                session['user'] = email
                return redirect(url_for('home'))
            else:
                flash("à¦ªà¦¾à¦¸à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦­à§à¦² à¦¹à§Ÿà§‡à¦›à§‡!", "error")
        else:
            flash("à¦à¦‡ à¦‡à¦®à§‡à¦‡à¦² à¦¦à¦¿à§Ÿà§‡ à¦•à§‹à¦¨à§‹ à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ à¦¨à§‡à¦‡!", "error")
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
            flash("à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦‡à¦®à§‡à¦‡à¦² à¦¦à¦¿à¦¨!", "error")
            return redirect(url_for('forgot_password'))
            
        user_ref = db.collection('users').document(email).get()
        if not user_ref.exists:
            flash("à¦à¦‡ à¦‡à¦®à§‡à¦‡à¦²à¦Ÿà¦¿ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦¸à¦¿à¦¸à§à¦Ÿà§‡à¦®à§‡ à¦¨à§‡à¦‡!", "error")
            return redirect(url_for('forgot_password'))
            
        otp = str(random.randint(1000, 9999))
        session['reset_email'] = email
        session['otp'] = otp
        
        sender_email = "Puspenduhaldar652@gmail.com"  
        sender_password = "tuelxovrkmfeqolr"          

        try:
            msg = MIMEText(f"à¦†à¦ªà¦¨à¦¾à¦° à¦ªà¦¾à¦¸à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦°à¦¿à¦¸à§‡à¦Ÿ à¦•à¦°à¦¾à¦° OTP à¦•à§‹à¦¡ à¦¹à¦²à§‹: {otp}", 'plain', 'utf-8')
            msg['Subject'] = 'AI Notes - Password Reset'
            msg['From'] = f"AI Notes <{sender_email}>"
            msg['To'] = email

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, [email], msg.as_string())
            flash("à¦†à¦ªà¦¨à¦¾à¦° à¦‡à¦®à§‡à¦‡à¦²à§‡ OTP à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à§Ÿà§‡à¦›à§‡! à¦‡à¦¨à¦¬à¦•à§à¦¸ à¦šà§‡à¦• à¦•à¦°à§à¦¨à¥¤", "success")
            return redirect(url_for('verify_otp'))
        except Exception as e:
            flash("à¦‡à¦®à§‡à¦‡à¦² à¦ªà¦¾à¦ à¦¾à¦¤à§‡ à¦¸à¦®à¦¸à§à¦¯à¦¾ à¦¹à¦šà§à¦›à§‡à¥¤ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤", "error")
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
            flash("à¦ªà¦¾à¦¸à¦“à§Ÿà¦¾à¦°à§à¦¡ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦¹à§Ÿà§‡à¦›à§‡! à¦à¦¬à¦¾à¦° à¦²à¦—à¦‡à¦¨ à¦•à¦°à§à¦¨à¥¤", "success")
            return redirect(url_for('login'))
        else:
            flash("OTP à¦­à§à¦² à¦¹à§Ÿà§‡à¦›à§‡!", "error")
            return redirect(url_for('verify_otp'))
    return render_template('verify.html')

# --- à¦šà§à¦¯à¦¾à¦Ÿ à¦à¦¬à¦‚ à¦¹à§‹à¦®à¦ªà§‡à¦œ ---
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
    
    # --- à¦‡à¦®à§‡à¦œ à¦œà§‡à¦¨à¦¾à¦°à§‡à¦¶à¦¨ à¦¸à¦¾à¦ªà§‹à¦°à§à¦Ÿ à¦¸à¦¹ à¦à¦†à¦‡ à¦ªà§à¦°à¦®à§à¦ªà¦Ÿ ---
    system_instruction = f"""
    à¦¤à§à¦®à¦¿ à¦à¦•à¦œà¦¨ à¦¸à§à¦®à¦¾à¦°à§à¦Ÿ à¦à¦†à¦‡à¥¤ 
    à§§. à¦¸à¦¾à¦§à¦¾à¦°à¦£ à¦ªà§à¦°à¦¶à§à¦¨à§‡à¦° à¦‰à¦¤à§à¦¤à¦° à¦ªà§Ÿà§‡à¦¨à§à¦Ÿ à¦•à¦°à§‡ à¦—à§à¦›à¦¿à§Ÿà§‡ à¦¬à¦¾à¦‚à¦²à¦¾à§Ÿ à¦¦à§‡à¦¬à§‡à¥¤
    à§¨. à¦•à¦¿à¦¨à§à¦¤à§ à¦¯à¦¦à¦¿ à¦‡à¦‰à¦œà¦¾à¦° à¦•à§‹à¦¨à§‹ à¦›à¦¬à¦¿ à¦¤à§ˆà¦°à¦¿ à¦•à¦°à¦¤à§‡ à¦¬à¦¾ à¦†à¦à¦•à¦¤à§‡ à¦¬à¦²à§‡ (à¦¯à§‡à¦®à¦¨: "à¦à¦•à¦Ÿà¦¿ à¦•à§à¦•à§à¦°à§‡à¦° à¦›à¦¬à¦¿ à¦¦à¦¾à¦“", "Generate an image", "create a picture"), 
    à¦¤à¦¾à¦¹à¦²à§‡ à¦¤à§à¦®à¦¿ à¦•à§‹à¦¨à§‹ à¦¬à§à¦¯à¦¾à¦–à§à¦¯à¦¾à¦®à§‚à¦²à¦• à¦•à¦¥à¦¾ à¦¨à¦¾ à¦¬à¦²à§‡ à¦¶à§à¦§à§ à¦¨à¦¿à¦šà§‡à¦° HTML à¦Ÿà§à¦¯à¦¾à¦—à¦Ÿà¦¿ à¦‰à¦¤à§à¦¤à¦° à¦¹à¦¿à¦¸à§‡à¦¬à§‡ à¦¦à§‡à¦¬à§‡:
    <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
    
    * ENGLISH_PROMPT à¦à¦° à¦œà¦¾à§Ÿà¦—à¦¾à§Ÿ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦šà¦¾à¦“à§Ÿà¦¾ à¦›à¦¬à¦¿à¦Ÿà¦¿à¦° à¦à¦•à¦Ÿà¦¿ à¦¸à§à¦¨à§à¦¦à¦° à¦“ à¦¬à¦¿à¦¸à§à¦¤à¦¾à¦°à¦¿à¦¤ à¦‡à¦‚à¦°à§‡à¦œà¦¿ à¦¡à§‡à¦¸à¦•à§à¦°à¦¿à¦ªà¦¶à¦¨ à¦²à¦¿à¦–à¦¬à§‡ à¦à¦¬à¦‚ à¦¶à¦¬à§à¦¦à§‡à¦° à¦®à¦¾à¦à¦–à¦¾à¦¨à§‡à¦° à¦¸à§à¦ªà§‡à¦¸à§‡à¦° à¦¬à¦¦à¦²à§‡ %20 à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¬à§‡à¥¤
    
    à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦ªà§à¦°à¦¶à§à¦¨: {prompt}
    """
    
    gemini_input = [system_instruction]
    
    # à¦›à¦¬à¦¿ à¦†à¦ªà¦²à§‹à¦¡à§‡à¦° à¦²à¦œà¦¿à¦•
    if file:
        os.makedirs('static/uploads', exist_ok=True)
        filename = str(uuid.uuid4()) + "_" + file.filename.replace(" ", "_")
        filepath = os.path.join('static/uploads', filename)
        file.save(filepath)
        img_url = '/' + filepath
        
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            img = Image.open(filepath)
            gemini_input.append(img)
            
    try:
        model = genai.GenerativeModel('gemini-3.6-flash')
        ai_response = model.generate_content(gemini_input).text
        
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

# --- à¦šà§à¦¯à¦¾à¦Ÿ à¦à¦¡à¦¿à¦Ÿ à¦°à§à¦Ÿ ---
@app.route('/edit_chat', methods=['POST'])
def edit_chat():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_email = session['user']
    prompt = request.form.get('prompt')
    session_id = request.form.get('session_id')
    msg_id = request.form.get('msg_id')
    
    system_instruction = f"""
    à¦¤à§à¦®à¦¿ à¦à¦•à¦œà¦¨ à¦¸à§à¦®à¦¾à¦°à§à¦Ÿ à¦à¦†à¦‡à¥¤ 
    à§§. à¦¸à¦¾à¦§à¦¾à¦°à¦£ à¦ªà§à¦°à¦¶à§à¦¨à§‡à¦° à¦‰à¦¤à§à¦¤à¦° à¦ªà§Ÿà§‡à¦¨à§à¦Ÿ à¦•à¦°à§‡ à¦—à§à¦›à¦¿à§Ÿà§‡ à¦¬à¦¾à¦‚à¦²à¦¾à§Ÿ à¦¦à§‡à¦¬à§‡à¥¤
    à§¨. à¦•à¦¿à¦¨à§à¦¤à§ à¦¯à¦¦à¦¿ à¦‡à¦‰à¦œà¦¾à¦° à¦•à§‹à¦¨à§‹ à¦›à¦¬à¦¿ à¦¤à§ˆà¦°à¦¿ à¦•à¦°à¦¤à§‡ à¦¬à¦¾ à¦†à¦à¦•à¦¤à§‡ à¦¬à¦²à§‡ (à¦¯à§‡à¦®à¦¨: "à¦à¦•à¦Ÿà¦¿ à¦•à§à¦•à§à¦°à§‡à¦° à¦›à¦¬à¦¿ à¦¦à¦¾à¦“", "Generate an image", "create a picture"), 
    à¦¤à¦¾à¦¹à¦²à§‡ à¦¤à§à¦®à¦¿ à¦•à§‹à¦¨à§‹ à¦¬à§à¦¯à¦¾à¦–à§à¦¯à¦¾à¦®à§‚à¦²à¦• à¦•à¦¥à¦¾ à¦¨à¦¾ à¦¬à¦²à§‡ à¦¶à§à¦§à§ à¦¨à¦¿à¦šà§‡à¦° HTML à¦Ÿà§à¦¯à¦¾à¦—à¦Ÿà¦¿ à¦‰à¦¤à§à¦¤à¦° à¦¹à¦¿à¦¸à§‡à¦¬à§‡ à¦¦à§‡à¦¬à§‡:
    <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
    
    * ENGLISH_PROMPT à¦à¦° à¦œà¦¾à§Ÿà¦—à¦¾à§Ÿ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦šà¦¾à¦“à§Ÿà¦¾ à¦›à¦¬à¦¿à¦Ÿà¦¿à¦° à¦à¦•à¦Ÿà¦¿ à¦¸à§à¦¨à§à¦¦à¦° à¦“ à¦¬à¦¿à¦¸à§à¦¤à¦¾à¦°à¦¿à¦¤ à¦‡à¦‚à¦°à§‡à¦œà¦¿ à¦¡à§‡à¦¸à¦•à§à¦°à¦¿à¦ªà¦¶à¦¨ à¦²à¦¿à¦–à¦¬à§‡ à¦à¦¬à¦‚ à¦¶à¦¬à§à¦¦à§‡à¦° à¦®à¦¾à¦à¦–à¦¾à¦¨à§‡à¦° à¦¸à§à¦ªà§‡à¦¸à§‡à¦° à¦¬à¦¦à¦²à§‡ %20 à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¬à§‡à¥¤
    
    à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦ªà§à¦°à¦¶à§à¦¨: {prompt}
    """
    gemini_input = [system_instruction]
    
    try:
        model = genai.GenerativeModel('gemini-3.6-flash')
        ai_response = model.generate_content(gemini_input).text
        
        # à¦¡à§‡à¦Ÿà¦¾à¦¬à§‡à¦¸à§‡ à¦†à¦—à§‡à¦° à¦®à§‡à¦¸à§‡à¦œ à¦†à¦ªà¦¡à§‡à¦Ÿ à¦•à¦°à§‡ à¦¦à§‡à¦“à§Ÿà¦¾
        db.collection('users').document(user_email).collection('sessions').document(session_id).collection('messages').document(msg_id).update({
            'user_msg': prompt,
            'ai_msg': ai_response
        })
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
