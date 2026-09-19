from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
import PyPDF2
import os

app = Flask(__name__)

# ডেটাবেস (Database) সেটআপ
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ডেটাবেস টেবিল তৈরি (যেখানে ইউজারের প্রশ্ন এবং AI এর উত্তর সেভ হবে)
class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_msg = db.Column(db.String(5000))
    ai_msg = db.Column(db.String(5000))

# অ্যাপ চালুর সময় ডেটাবেস ফাইলটি তৈরি করা
with app.app_context():
    db.create_all()

# API Key সেটআপ
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

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
    তুমি একজন অত্যন্ত স্মার্ট, গোছানো এবং বন্ধুসুলভ প্রাইভেট টিউটর। তোমাকে নিচের নিয়মগুলো কঠোরভাবে মেনে চলতে হবে:

    ১. ইউজার যদি শুধু "Hi", "Hello", "কেমন আছো" বা সাধারণ কুশল বিনিময় করে, তবে তুমি কোনো লেকচার দেবে না। শুধু ৩-৫ লাইনের মধ্যে সুন্দর করে উত্তর দিয়ে জিজ্ঞেস করবে, "আমি আজ আপনাকে কীভাবে সাহায্য করতে পারি?"
    ২. যেকোনো পড়াশোনা বা টপিক সংক্রান্ত প্রশ্নের উত্তর সবসময় পয়েন্ট (Bullet points) করে এবং ছোট ছোট প্যারাগ্রাফে খুব সুন্দর করে গুছিয়ে দেবে। দেখতে যেন একদম পরিষ্কার ও প্রফেশনাল লাগে।
    ৩. পয়েন্টের হেডিং বা গুরুত্বপূর্ণ শব্দগুলো বোল্ড (**bold**) করে দেবে। 
    ৪. ইউজার যতটুকু প্রশ্ন করবে, ঠিক ততটুকুই উত্তর দেবে। অকারণে অপ্রাসঙ্গিক বা অতিরিক্ত কথা বলবে না।
    
    ইউজারের প্রশ্ন বা টপিক: {prompt} {context}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": full_prompt}]
        )
        ai_response = response.choices[0].message.content
        
        # ডেটাবেসে চ্যাট সেভ করা
        new_chat = Chat(user_msg=prompt, ai_msg=ai_response)
        db.session.add(new_chat)
        db.session.commit()
        
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
