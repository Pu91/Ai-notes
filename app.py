from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai
import PyPDF2
import os

app = Flask(__name__)

# ডেটাবেস সেটআপ
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_msg = db.Column(db.String(5000))
    ai_msg = db.Column(db.String(5000))

with app.app_context():
    db.create_all()

# Gemini API Key সেটআপ
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    prompt = request.form.get('prompt')
    pdf_file = request.files.get('pdf_file')
    
    context = ""
    if pdf_file and pdf_file.filename.endswith('.pdf'):
        reader = PyPDF2.PdfReader(pdf_file)
        pdf_text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])
        if len(pdf_text) > 15000:
            pdf_text = pdf_text[:15000]
        context = f"\n\n[নিচের PDF তথ্যের ওপর ভিত্তি করে উত্তর দাও:\n{pdf_text}]"
        
    full_prompt = f"""
    তুমি একজন বিশ্ববিদ্যালয়ের প্রফেসর এবং অত্যন্ত স্মার্ট টিউটর। তোমাকে নিচের নিয়মগুলো কঠোরভাবে মেনে চলতে হবে:

    ১. কোনোভাবেই উত্তরে '#' বা '*' চিহ্নের মতো কোনো মার্কডাউন (Markdown) ট্যাগ ব্যবহার করা যাবে না। পয়েন্ট করার জন্য শুধুমাত্র ১, ২, ৩... বা ক, খ, গ... এবং স্বাভাবিক প্যারাগ্রাফ ব্যবহার করবে।
    ২. বাংলা শব্দের একাধিক অর্থ থাকতে পারে (যেমন: 'দ্রব্য' দর্শনে এক জিনিস, বিজ্ঞানে অন্য)। ইউজারের প্রশ্নটি ভালো করে বুঝে, সঠিক বিষয়ের ওপর একদম ডিপ, গোছানো এবং প্রফেশনাল নোটস তৈরি করবে। 
    ৩. নোটসগুলো যেন পর পর সুন্দরভাবে সাজানো থাকে— প্রথমে ভূমিকা, তারপর মূল আলোচনা, শেষে উপসংহার।
    ৪. ইউজার যদি শুধু "Hi", "Hello" বলে, তবে কোনো লেকচার না দিয়ে শুধু ৩-৫ লাইনে উত্তর দেবে।
    
    ইউজারের প্রশ্ন বা টপিক: {prompt} {context}
    """
    
    try:
        # এখানে গুগলের সবচেয়ে শক্তিশালী Gemini 1.5 Pro মডেল ব্যবহার করা হয়েছে
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(full_prompt)
        ai_response = response.text
        
        # ডেটাবেসে সেভ করা
        new_chat = Chat(user_msg=prompt, ai_msg=ai_response)
        db.session.add(new_chat)
        db.session.commit()
        
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
