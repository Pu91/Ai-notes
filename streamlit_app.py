import streamlit as st
from openai import OpenAI
import PyPDF2

# Groq API Setup
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=st.secrets["GROQ_API_KEY"],
)

st.set_page_config(page_title="AI Notes Assistant", page_icon="🤖", layout="centered")

# ==========================================
# মোবাইল ফ্রেন্ডলি ডিজাইন এবং CSS
# ==========================================
custom_css = """
<style>
    /* ডিফল্ট হেডার ও ফুটার লুকানো */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* মোবাইলে ডানে-বামে স্লাইড হওয়া বন্ধ করা এবং মার্জিন ঠিক করা */
    * {
        overflow-wrap: break-word !important;
        word-wrap: break-word !important;
    }
    .stMarkdown p, .stMarkdown li {
        white-space: normal !important;
    }
    .stMarkdown pre {
        white-space: pre-wrap !important;
        overflow-x: hidden !important;
    }
    /* চ্যাট মেসেজের চারপাশের মার্জিন ও প্যাডিং */
    .stChatMessage {
        padding: 15px !important;
        border-radius: 10px !important;
        margin-bottom: 10px !important;
    }
    /* স্ক্রিনের সাইডের মার্জিন */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 6rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# ==========================================
# টপ হেডার (টাইটেল এবং New Chat)
# ==========================================
col1, col2 = st.columns([7, 3])
with col1:
    st.markdown("### 🤖 AI Notes")
with col2:
    if st.button("📝 New Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# সাইডবার (শুধুমাত্র হিস্ট্রি এবং আপগ্রেড)
# ==========================================
with st.sidebar:
    st.subheader("🕒 Chat History")
    st.button("📝 Unit 6 & 7 Notes", use_container_width=True)
    st.button("📝 Bengali Syllabus", use_container_width=True)
    st.button("📝 English Grammar", use_container_width=True)
    st.write("---")
    st.markdown("### 🚀 [Upgrade to Plus](#)")

# ==========================================
# মূল চ্যাট ইন্টারফেস
# ==========================================
# আগের চ্যাট মেসেজগুলো দেখানো
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# ইনপুট এবং অ্যাটাচমেন্ট (চ্যাট বক্সের উপরে)
# ==========================================
# ফাইল আপলোডের জন্য পপওভার (ক্লিক করলে বক্স খুলবে)
with st.popover("📎 PDF আপলোড"):
    uploaded_file = st.file_uploader("সিলেবাস নির্বাচন করুন", type=["pdf"])
    if uploaded_file:
        st.success("ফাইল যুক্ত হয়েছে! এবার নিচে প্রশ্ন লিখুন।")

# ইউজারের ইনপুট বক্স
if prompt := st.chat_input("আপনার সিলেবাসের টপিক বা প্রশ্ন লিখুন..."):
    
    # ইউজারের মেসেজ সেভ করা
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # PDF প্রসেসিং
        context = ""
        if uploaded_file is not None:
            pdf_text = extract_text_from_pdf(uploaded_file)
            if len(pdf_text) > 15000:
                pdf_text = pdf_text[:15000]
                st.warning("⚠️ PDF-টি অনেক বড় হওয়ায় প্রথম অংশের ওপর ভিত্তি করে উত্তর দেওয়া হচ্ছে।")
            context = f"\n\n[নিচের PDF তথ্যের ওপর ভিত্তি করে উত্তর দাও:\n{pdf_text}]"
            
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
                
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"কোনো একটি সমস্যা হয়েছে: {e}")
