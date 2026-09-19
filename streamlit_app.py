import streamlit as st
from openai import OpenAI
import PyPDF2

# Groq API Setup
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=st.secrets["GROQ_API_KEY"],
)

# ওয়েবসাইটের পেজ কনফিগারেশন
st.set_page_config(page_title="AI Notes Assistant", page_icon="🤖", layout="wide")

# চ্যাট হিস্ট্রি সেভ রাখার জন্য Session State তৈরি
if "messages" not in st.session_state:
    st.session_state.messages = []

def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# ==========================================
# স্লাইড নেভবার / সাইডবার ডিজাইন (ChatGPT স্টাইল)
# ==========================================
with st.sidebar:
    # New Chat বাটন
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
        
    st.write("---")
    
    # PDF আপলোড অপশন সাইডবারে রাখা হলো যাতে মূল চ্যাট স্ক্রিন পরিষ্কার থাকে
    st.subheader("📚 সিলেবাস আপলোড")
    uploaded_file = st.file_uploader("PDF ফাইল দিন (ঐচ্ছিক)", type=["pdf"])
    
    st.write("---")
    
    # চ্যাট হিস্ট্রি (আপাতত ডেমো লিস্ট, পরবর্তীতে ডাটাবেস যুক্ত করলে এগুলো কাজ করবে)
    st.subheader("🕒 Chat History")
    st.button("📝 Unit 6 & 7 Notes", use_container_width=True)
    st.button("📝 Bengali Syllabus", use_container_width=True)
    st.button("📝 English Grammar", use_container_width=True)
    
    st.write("---")
    
    # আপগ্রেড বাটন
    st.markdown("### 🚀 [Upgrade to Plus](#)")
    st.caption("Get access to advanced features")

# ==========================================
# মূল চ্যাট ইন্টারফেস 
# ==========================================
st.title("🤖 AI Notes Assistant")

# আগের চ্যাট মেসেজগুলো স্ক্রিনে দেখানোর জন্য
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ইউজারের ইনপুট নেওয়ার জন্য চ্যাট বক্স
if prompt = st.chat_input("আপনার সিলেবাসের টপিক বা প্রশ্ন লিখুন..."):
    
    # ইউজারের মেসেজ স্ক্রিনে দেখানো এবং সেভ করা
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # এআই-এর রিপ্লাই তৈরি করা
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # PDF থেকে টেক্সট নেওয়া (যদি আপলোড করা থাকে)
        context = ""
        if uploaded_file is not None:
            pdf_text = extract_text_from_pdf(uploaded_file)
            # টোকেন লিমিট এড়াতে সাইজ কন্ট্রোল
            if len(pdf_text) > 15000:
                pdf_text = pdf_text[:15000]
            context = f"\n\n[নিচের PDF তথ্যের ওপর ভিত্তি করে উত্তর দাও:\n{pdf_text}]"
            
        # এআই-কে নির্দেশ দেওয়া (Teacher Persona)
        full_prompt = f"""
        তুমি একজন শিক্ষক। তুমি ক্লাসরুমে বেঞ্চে বসে থাকা স্টুডেন্টদের সামনে দাঁড়িয়ে খুব সহজ, সুন্দর ও সাবলীল ভাষায় পড়া বোঝাচ্ছো। 
        পয়েন্ট করে এবং বাস্তব উদাহরণ দিয়ে বিষয়টি বুঝিয়ে দেবে।
        
        ইউজারের প্রশ্ন বা টপিক: {prompt} {context}
        """
        
        try:
            with st.spinner("নোটস তৈরি হচ্ছে..."):
                response = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "user", "content": full_prompt}
                    ]
                )
                full_response = response.choices[0].message.content
                
            # এআই-এর মেসেজ স্ক্রিনে দেখানো এবং সেভ করা
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"কোনো একটি সমস্যা হয়েছে: {e}")
