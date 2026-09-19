from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Firebase ডেটাবেস কানেকশন (Render-এর Secret File থেকে)
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Gemini API Key সেটআপ (Render Environment Variable থেকে)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    # Firebase থেকে পুরনো চ্যাটগুলো লোড করা
    history = []
    try:
        chats_ref = db.collection('chats').order_by('timestamp')
        docs = chats_ref.stream()
        for doc in docs:
            history.append(doc.to_dict())
    except Exception as e:
        print("Firebase Error:", e)
        
    return render_template('index.html', history=history)

@app.route('/chat', methods=['POST'])
def chat():
    prompt = request.form.get('prompt')
    
    full_prompt = f"""
    তুমি একজন বিশ্ববিদ্যালয়ের প্রফেসর এবং অত্যন্ত স্মার্ট টিউটর। কোনোভাবেই উত্তরে '#' বা '*' চিহ্নের মতো কোনো মার্কডাউন (Markdown) ট্যাগ ব্যবহার করা যাবে না। পয়েন্ট করার জন্য শুধুমাত্র ১, ২, ৩... বা ক, খ, গ... এবং স্বাভাবিক প্যারাগ্রাফ ব্যবহার করবে।
    বাংলা শব্দের একাধিক অর্থ থাকতে পারে। ইউজারের প্রশ্নটি ভালো করে বুঝে, সঠিক বিষয়ের ওপর একদম ডিপ, গোছানো এবং প্রফেশনাল নোটস তৈরি করবে। 
    ইউজার যদি শুধু "Hi", "Hello" বলে, তবে কোনো লেকচার না দিয়ে শুধু ৩-৫ লাইনে উত্তর দেবে।
    
    ইউজারের প্রশ্ন: {prompt}
    """
    
    try:
        # লেটেস্ট Gemini 3.8 Flash মডেল
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content(full_prompt)
        ai_response = response.text
        
        # Firebase-এ নতুন চ্যাট সেভ করা
        db.collection('chats').add({
            'user_msg': prompt,
            'ai_msg': ai_response,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
