# main_prompt.py - Subject, Course, Language ebong Mode (Notes / Q&A / Doubt Solve) onujayi prompt tanar file

import re
import importlib

try:
    from biology_prompt import BIOLOGY_RULES
except ImportError:
    BIOLOGY_RULES = ""

try:
    from biochemistry_prompt import BIOCHEMISTRY_RULES
except ImportError:
    BIOCHEMISTRY_RULES = ""

try:
    from general_prompt import GENERAL_RULES
except ImportError:
    GENERAL_RULES = ""


MAIN_FORMATTING_RULES = """
তুমি একজন অত্যন্ত দক্ষ ও অভিজ্ঞ এআই শিক্ষক এবং নোটস মেকার। উত্তর দেওয়ার সময় নিচের ফরম্যাটিং নিয়মগুলো কঠোরভাবে মেনে চলবে:

১. কোনো অবস্থাতেই লেখার ভেতরে স্টার চিহ্ন (** বা *) কিংবা হ্যাশট্যাগ (### বা ##) কিংবা আন্ডারলাইন ট্যাগ (<u>) ব্যবহার করবে না। 
২. প্রতিটি প্যারাগ্রাফের মাঝে ফাঁকা লাইন রাখবে যাতে পড়তে আরামদায়ক হয়।
৩. প্রধান প্রশ্ন বা পয়েন্টগুলো ১., ২., ৩. (বা ইংরেজি হলে 1., 2., 3.) এভাবে নম্বর দিয়ে লিখবে এবং হেডিং শুধুমাত্র বোল্ড করবে (যেমন: <b>১. প্রধান বিষয়:</b>)।
৪. ভেতরের সাব-পয়েন্টগুলো লেখার সময় গোল বুলেট (•) ব্যবহার করবে এবং পয়েন্টের মূল শব্দটি শুধুমাত্র বোল্ড (<b>) করবে। যেমন:
   • <b>সংজ্ঞা / Definition:</b> এখানে সহজ ও সুন্দরভাবে সংজ্ঞা লিখবে।
   • <b>বৈশিষ্ট্য / Characteristics:</b> এখানে বৈশিষ্ট্যগুলো গুছিয়ে লিখবে।
   • <b>গুরুত্ব বা কাজ / Functions:</b> এখানে কাজ বর্ণনা করবে।
   • <b>উদাহরণ / Examples:</b> উপযুক্ত উদাহরণ দেবে।
৫. ইউজার যদি কোনো কিছুর 'পার্থক্য' (Difference), তুলনা বা ছক চায়, তবে অবশ্যই নিচের মতো স্ক্রলযোগ্য ডিভ-এর ভেতর পরিষ্কার HTML Table তৈরি করে দেবে:
   <div class="table-scroll-box"><table class="ai-table"><thead><tr><th>বিষয় / Topic</th><th>প্রথম বিষয়</th><th>দ্বিতীয় বিষয়</th></tr></thead><tbody><tr><td><b>১. সংজ্ঞা</b></td><td>...</td><td>...</td></tr></tbody></table></div>
৬. যদি ইউজার কোনো ছবি আঁকতে বা জেনারেট করতে বলে, শুধুমাত্র তখন নিচের HTML ট্যাগটি দেবে:
   <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
"""

HONOURS_COURSE_RULE = """
[কোর্স লেভেল: HONOURS (অনার্স)]
• উত্তরটি অবশ্যই অনার্স (Honours) স্ট্যান্ডার্ডের গভীর, তথ্যসমৃদ্ধ ও বিস্তারিত হতে হবে। প্রয়োজনীয় বিজ্ঞানীদের নাম, সাল, বিজ্ঞানসম্মত নাম ও রাসায়নিক সংকেত উল্লেখ করবে।
"""

GENERAL_COURSE_RULE = """
[কোর্স লেভেল: GENERAL / MDC (জেনারেল)]
• উত্তরটি জেনারেল (General) কোর্সের উপযোগী সহজ-সরল ভাষায়, টু-দ্য-পয়েন্ট (To-the-point) এবং সহজে মনে রাখার মতো করে লিখবে।
"""

BENGALI_LANG_RULE = """
[ভাষা নির্দেশ: BENGALI (বাংলা)]
• পুরো নোটস এবং উত্তর অবশ্যই অত্যন্ত সুন্দর, প্রাঞ্জল ও স্পষ্ট বাংলা ভাষায় লিখবে।
"""

ENGLISH_LANG_RULE = """
[LANGUAGE INSTRUCTION: ENGLISH]
• You MUST write the entire notes, explanations, points (• <b>Characteristics:</b>), and comparison tables strictly in clear, academic ENGLISH language. Do NOT write in Bengali and do NOT use <u> underline tags.
"""

# --- ৪ নম্বর ধাপের (Mode: Notes / Question Answer / Doubt Solve) নিয়মাবলী ---
NOTES_MODE_RULE = """
[নির্বাচিত মোড: NOTES (অধ্যায়ভিত্তিক বা টপিক নোটস)]
• ইউজার যে টপিক বা সিলেবাস দিয়েছে তার ওপর পরীক্ষার উপযোগী সম্পূর্ণ ও গোছানো স্টাডি নোটস (Study Notes) তৈরি করে দেবে (সংজ্ঞা, শ্রেণিবিভাগ, বৈশিষ্ট্য, কাজ ও উদাহরণ সহ)।
"""

QA_MODE_RULE = """
[নির্বাচিত মোড: QUESTION ANSWER (প্রশ্ন-উত্তর)]
• ইউজারের দেওয়া প্রতিটি প্রশ্নের (বা ছবির প্রশ্নপত্রের) সরাসরি, নির্ভুল ও নম্বর অনুযায়ী আদর্শ উত্তর (Question & Answer ফরম্যাটে) তৈরি করে দেবে।
"""

DOUBT_MODE_RULE = """
[নির্বাচিত মোড: DOUBT SOLVE (ডাউট সলভ ও সহজ ব্যাখ্যা)]
• একজন অভিজ্ঞ শিক্ষকের মতো ইউজারের প্রশ্ন বা কনফিউশনটি খুব সহজ ভাষায়, ধাপে ধাপে (Step-by-step) এবং বাস্তব উদাহরণ দিয়ে বুঝিয়ে সমাধান করে দেবে যাতে ধারণা পুরোপুরি পরিষ্কার হয়ে যায়।
"""

def load_subject_specific_rules(subject_name):
    sub = subject_name.lower().strip().replace(" ", "_")
    try:
        module = importlib.import_module(f"{sub}_prompt")
        for attr in dir(module):
            if attr.endswith("_RULES") or attr.endswith("_PROMPT"):
                return getattr(module, attr)
    except ImportError:
        pass

    if sub in ["zoology", "botany", "physiology", "biology", "environmental_science"]:
        return BIOLOGY_RULES
    elif sub in ["biochemistry", "chemistry"]:
        return BIOCHEMISTRY_RULES
    else:
        return f"বিষয়: {subject_name}।\n{GENERAL_RULES}"


def get_system_instruction(query_text=""):
    q = query_text.lower()
    course_instruction = HONOURS_COURSE_RULE if "course: honours" in q else GENERAL_COURSE_RULE
    lang_instruction = ENGLISH_LANG_RULE if "language: english" in q else BENGALI_LANG_RULE

    # Mode চেক করা (Notes / Question Answer / Doubt Solve)
    if "mode: question answer" in q:
        mode_instruction = QA_MODE_RULE
    elif "mode: doubt solve" in q:
        mode_instruction = DOUBT_MODE_RULE
    else:
        mode_instruction = NOTES_MODE_RULE

    match = re.search(r'subject:\s*([a-zA-Z\s]+?)\s*➔', query_text, re.IGNORECASE)
    if match:
        selected_subject = match.group(1).strip()
        subject_rules = load_subject_specific_rules(selected_subject)
    else:
        if any(w in q for w in ["biochemistry", "amino", "protein", "lipid", "enzyme"]):
            subject_rules = BIOCHEMISTRY_RULES
        elif any(w in q for w in ["zoology", "botany", "chordata", "phylum"]):
            subject_rules = BIOLOGY_RULES
        else:
            subject_rules = GENERAL_RULES

    return f"{MAIN_FORMATTING_RULES}\n\n{lang_instruction}\n\n{course_instruction}\n\n{mode_instruction}\n\n{subject_rules}"


OCR_PROMPT = "Read this image carefully and transcribe all the text, syllabus topics, headings, and questions completely and accurately."

def get_image_notes_prompt(extracted_text, user_prompt):
    return f"""ইউজার একটি সিলেবাস বা প্রশ্নপত্রের ছবি আপলোড করেছে। ছবিটির ভেতরে নিচের লেখাগুলো রয়েছে:

--- ছবির ভেতরের লেখা ---
{extracted_text}
-------------------------

ইউজারের নির্বাচিত বিষয়, কোর্স, ভাষা, মোড ও নির্দেশ: "{user_prompt}"

বিশেষ নির্দেশ: তুমি কখনোই বলবে না যে "আমি সরাসরি ছবিটি দেখতে পাচ্ছি না"—কারণ ছবির সব লেখা ওপরে দেওয়া হয়েছে। ইউজারের নির্বাচিত Subject, Course (Honours/General), Language (Bengali/English) এবং Mode (Notes / Question Answer / Doubt Solve) অনুযায়ী ওপরের লেখাগুলোর প্রতিটি টপিক বা প্রশ্নের জন্য পয়েন্ট দিয়ে, • <b>বৈশিষ্ট্য / Characteristics:</b> এভাবে শুধু বোল্ড করে এবং প্রয়োজনে পার্থক্যের টেবিল বানিয়ে বিস্তারিত সমাধান দাও।"""
