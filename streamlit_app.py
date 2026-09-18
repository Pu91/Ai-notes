import streamlit as st
import google.generativeai as genai
import PyPDF2

# Gemini API Key সেটআপ (এটি আমরা হোস্টিংয়ের সময় সিক্রেট হিসেবে যুক্ত করব)
# আপনার যদি লোকাল পিসিতে টেস্ট করতে হয়, তবে st.secrets এর জায়গায় সরাসরি আপনার API key দিতে পারেন।
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# ওয়েবসাইটের ডিজাইন
st.set_page_config(page_title="AI Notes Generator", page_icon="📚")
st.title("📚 AI Notes Generator")
st.write("আপনার সিলেবাসের PDF আপলোড করুন এবং মুহূর্তেই বিস্তারিত নোটস পেয়ে যান!")

# ইনপুট নেওয়ার অপশন
uploaded_file = st.file_uploader("সিলেবাসের PDF আপলোড করুন", type=["pdf"])
topic_text = st.text_area("অথবা, সিলেবাসের টপিকগুলো এখানে টাইপ করুন:")

if st.button("নোটস তৈরি করুন"):
    syllabus_content = ""
    
    if uploaded_file is not None:
        with st.spinner("PDF পড়া হচ্ছে..."):
            syllabus_content = extract_text_from_pdf(uploaded_file)
    elif topic_text:
        syllabus_content = topic_text
        
    if syllabus_content:
        with st.spinner("আপনার জন্য এআই নোটস তৈরি করছে..."):
            # এআই-কে দেওয়া নির্দেশ (Prompt)
            prompt = f"""
            নিচের সিলেবাস বা টপিকগুলোর ওপর একটি বিস্তারিত ও গোছানো নোটস তৈরি করো। 
            নোটসগুলো এমনভাবে লিখবে যেন মনে হয় একজন শিক্ষক ক্লাসরুমে বেঞ্চে বসে থাকা স্টুডেন্টদের সামনে দাঁড়িয়ে খুব সহজ ও সুন্দর ভাষায় সবকিছু বুঝিয়ে বলছেন। 
            পয়েন্ট করে এবং বাস্তব উদাহরণ দিয়ে বিষয়টি বুঝিয়ে দেবে।
            
            সিলেবাস:
            {syllabus_content}
            """
            
            try:
                # Gemini 1.5 Flash মডেল ব্যবহার করা হচ্ছে যা খুব ফাস্ট
                model = genai.GenerativeModel("gemini_pro")
                response = model.generate_content(prompt)
                
                st.success("নোটস তৈরি সম্পন্ন!")
                st.subheader("আপনার জেনারেটেড নোটস:")
                st.write(response.text)
            except Exception as e:
                st.error(f"কোনো একটি সমস্যা হয়েছে: {e}")
    else:
        st.warning("দয়া করে PDF আপলোড করুন অথবা টপিক লিখুন।")
