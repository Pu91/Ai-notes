from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import PyPDF2
import os

app = Flask(__name__)

# API Key সেটআপ (লোকাল টেস্ট বা হোস্টিংয়ের সময় Environment Variable থেকে নেবে)
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
    তুমি একজন শিক্ষক। তুমি ক্লাসরুমে বেঞ্চে বসে থাকা স্টুডেন্টদের সামনে দাঁড়িয়ে খুব সহজ, সুন্দর ও সাবলীল ভাষায় পড়া বোঝাচ্ছো। 
    পয়েন্ট করে এবং বাস্তব উদাহরণ দিয়ে বিষয়টি বুঝিয়ে দেবে।
    
    ইউজারের প্রশ্ন বা টপিক: {prompt} {context}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": full_prompt}]
        )
        return jsonify({"response": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
