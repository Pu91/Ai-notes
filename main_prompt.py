# main_prompt.py - Subject, Course, Language ebong Mode onujayi 'prompts/' folder theke automatic prompt load korar file

import re
import importlib

# Purono file-gulor fallback (jodi root folder ba prompts folder-e thake)
def _safe_import_rule(module_names, var_name):
    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, var_name):
                return getattr(mod, var_name)
        except ImportError:
            continue
    return ""

BIOLOGY_RULES = _safe_import_rule(["prompts.biology_prompt", "biology_prompt"], "BIOLOGY_RULES")
BIOCHEMISTRY_RULES = _safe_import_rule(["prompts.biochemistry_prompt", "biochemistry_prompt"], "BIOCHEMISTRY_RULES")
GENERAL_RULES = _safe_import_rule(["prompts.general_prompt", "general_prompt"], "GENERAL_RULES")


MAIN_FORMATTING_RULES = """
তুমি একজন অত্যন্ত দক্ষ ও অভিজ্ঞ এআই শিক্ষক এবং নোটস মেকার। উত্তর দেওয়ার সময় নিচের ফরম্যাটিং নিয়মগুলো কঠোরভাবে মেনে চলবে:

১. কোনো অবস্থাতেই সাধারণ লেখার ভেতরে স্টার চিহ্ন (** বা *) কিংবা হ্যাশট্যাগ (### বা ##) কিংবা সাধারণ লেখায় আন্ডারলাইন ট্যাগ (<u>) ব্যবহার করবে না। 
২. প্রতিটি প্যারাগ্রাফের মাঝে ফাঁকা লাইন রাখবে যাতে পড়তে আরামদায়ক হয়।
৩. প্রধান প্রশ্ন বা পয়েন্টগুলো ১., ২., ৩. (বা ইংরেজি হলে 1., 2., 3.) এভাবে নম্বর দিয়ে লিখবে এবং হেডিং শুধুমাত্র বোল্ড করবে (যেমন: <b>১. প্রধান বিষয়:</b> বা <b>1. Main Topic:</b>)।
৪. ভেতরের সাব-পয়েন্টগুলো লেখার সময় গোল বুলেট (•) ব্যবহার করবে এবং পয়েন্টের মূল শব্দটি শুধুমাত্র বোল্ড (<b>) করবে।
৫. ইউজার যদি কোনো কিছুর 'পার্থক্য' (Difference), তুলনা বা ছক চায়, তবে অবশ্যই নিচের মতো স্ক্রলযোগ্য ডিভ-এর ভেতর পরিষ্কার HTML Table তৈরি করে দেবে:
   <div class="table-scroll-box"><table class="ai-table"><thead><tr><th>বিষয় / Topic</th><th>প্রথম বিষয়</th><th>দ্বিতীয় বিষয়</th></tr></thead><tbody><tr><td><b>১. সংজ্ঞা</b></td><td>...</td><td>...</td></tr></tbody></table></div>
৬. যদি ইউজার কোনো ছবি আঁকতে বা ডায়াগ্রাম দিতে বলে, তবে উত্তর শেষ হওয়ার পর একদম শেষে নিচের HTML ট্যাগটি দেবে:
   <img src="https://image.pollinations.ai/prompt/ENGLISH_PROMPT?width=600&height=600&nologo=true" style="width:100%; max-width:350px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.15); cursor:pointer;" onclick="openModal(this.src)">
"""

HONOURS_COURSE_RULE = """
[কোর্স লেভেল: HONOURS (অনার্স)]
• উত্তরটি অবশ্যই অনার্স (Honours) স্ট্যান্ডার্ডের গভীর, তথ্যসমৃদ্ধ ও বিস্তারিত হতে হবে। প্রয়োজনীয় বিজ্ঞানীদের নাম, সাল, বিজ্ঞানসম্মত নাম ও রাসায়নিক সংকেত উল্লেখ করবে।
"""

GENERAL_COURSE_RULE = """
[কোর্স লেভেল: GENERAL / MDC (জেনারেল)]
• উত্তরটি জেনারেল (General) কোর্সের উপযোগী সহজ-সরল ভাষায়, টু-দ্য-পয়েন্ট (To-the-point) এবং সহজে মনে রাখার মতো করে লিখবে।
"""

BENGALI_LANG_RULE = """
[ভাষা নির্দেশ: BENGALI (বাংলা)]
• পুরো নোটস এবং উত্তর অবশ্যই অত্যন্ত সুন্দর, প্রাঞ্জল ও স্পষ্ট বাংলা ভাষায় লিখবে। জটিল শব্দের পাশে ব্র্যাকেটে ইংরেজি টার্ম দেবে।
"""

ENGLISH_LANG_RULE = """
[LANGUAGE INSTRUCTION: ENGLISH]
• You MUST write the entire notes, headings, explanations, bullet points, and comparison tables strictly in clear, simple, exam-ready academic ENGLISH language. Do NOT write in Bengali anywhere.
"""

# --- ৪ নম্বর ধাপের (Mode: Notes / Question Answer / Doubt Solve) নিয়মাবলী ---
NOTES_MODE_RULE = """
[নির্বাচিত মোড: NOTES (অধ্যায়ভিত্তিক বা টপিক নোটস)]
• ইউজার যে টপিক বা সিলেবাস দিয়েছে তার প্রতিটি অংশ আলাদা করে পরীক্ষার উপযোগী সম্পূর্ণ ও গোছানো স্টাডি নোটস (Study Notes) তৈরি করে দেবে।
"""

QA_MODE_RULE = """
[নির্বাচিত মোড: QUESTION ANSWER (প্রশ্ন-উত্তর)]
• ইউজারের দেওয়া টপিক বা প্রশ্নের জন্য নির্দিষ্ট নিয়ম অনুযায়ী আদর্শ প্রশ্ন ও উত্তর (Question & Answer) তৈরি করে দেবে।
"""

DOUBT_MODE_RULE = """
[নির্বাচিত মোড: DOUBT SOLVE (ডাউট সলভ ও সহজ ব্যাখ্যা)]
• একজন অভিজ্ঞ শিক্ষকের মতো ইউজারের প্রশ্ন বা আগের মেসেজের নির্দিষ্ট নম্বরের পয়েন্ট/টপিকটি খুব সহজ ভাষায় এবং উদাহরণ দিয়ে বিস্তারিত বুঝিয়ে সমাধান করে দেবে।
"""


def load_subject_specific_rules(subject_name, course="general", lang="bengali", full_query=""):
    sub = subject_name.lower().strip().replace(" ", "_").replace(".", "")
    crs = course.lower().strip()
    lng = lang.lower().strip()

    # ১. প্রথমে prompts/ ফোল্ডার এবং রুট ফোল্ডারে ক্রমানুসারে ফাইল খুঁজবে:
    # যেমন: prompts.zoology_general_bengali_prompt -> prompts.zoology_general_english_prompt -> prompts.zoology_prompt
    candidate_modules = [
        f"prompts.{sub}_{crs}_{lng}_prompt",
        f"{sub}_{crs}_{lng}_prompt",
        f"prompts.{sub}_general_{lng}_prompt",
        f"{sub}_general_{lng}_prompt",
        f"prompts.{sub}_{lng}_prompt",
        f"{sub}_{lng}_prompt",
        f"prompts.{sub}_prompt",
        f"{sub}_prompt"
    ]

    for mod_path in candidate_modules:
        try:
            module = importlib.import_module(mod_path)
            # যদি মডিউলের ভেতর ভাষা অনুযায়ী ফাংশন থাকে
            if hasattr(module, "get_zoology_rules_by_lang"):
                return module.get_zoology_rules_by_lang(full_query)
            # অথবা যেকোনো *_RULES বা *_PROMPT ভেরিয়েবল রিটার্ন করবে
            for attr in dir(module):
                if attr.endswith("_RULES") or attr.endswith("_PROMPT"):
                    val = getattr(module, attr)
                    if isinstance(val, str) and val.strip():
                        return val
        except ImportError:
            continue

    # ২. যদি ওই বিষয়ের আলাদা ফাইল না থাকে, তবে ডিফল্ট রুলস ব্যবহার করবে
    if sub in ["zoology", "botany", "physiology", "biology", "environmental_science", "env_science"]:
        return BIOLOGY_RULES
    elif sub in ["biochemistry", "chemistry"]:
        return BIOCHEMISTRY_RULES
    else:
        return f"Subject: {subject_name}\n{GENERAL_RULES}"


def get_system_instruction(query_text=""):
    q = query_text.lower()

    # Course নির্ধারণ (honours / general)
    is_honours = "course: honours" in q
    course_name = "honours" if is_honours else "general"
    course_instruction = HONOURS_COURSE_RULE if is_honours else GENERAL_COURSE_RULE

    # Language নির্ধারণ (english / bengali)
    is_english = "language: english" in q
    lang_name = "english" if is_english else "bengali"
    lang_instruction = ENGLISH_LANG_RULE if is_english else BENGALI_LANG_RULE

    # Mode চেক করা (Notes / Question Answer / Doubt Solve)
    if "mode: question answer" in q:
        mode_instruction = QA_MODE_RULE
    elif "mode: doubt solve" in q:
        mode_instruction = DOUBT_MODE_RULE
    else:
        mode_instruction = NOTES_MODE_RULE

    # Subject খুঁজে বের করে prompts/ ফোল্ডার থেকে সঠিক ফাইল লোড করা
    match = re.search(r'subject:\s*([a-zA-Z\.\s]+?)\s*➔', query_text, re.IGNORECASE)
    if match:
        selected_subject = match.group(1).strip()
        subject_rules = load_subject_specific_rules(selected_subject, course=course_name, lang=lang_name, full_query=query_text)
    else:
        if any(w in q for w in ["zoology", "protozoa", "chordata", "phylum", "paramecium", "euglena", "amoeba"]):
            subject_rules = load_subject_specific_rules("zoology", course=course_name, lang=lang_name, full_query=query_text)
        elif any(w in q for w in ["biochemistry", "amino", "protein", "lipid", "enzyme"]):
            subject_rules = BIOCHEMISTRY_RULES
        elif any(w in q for w in ["botany", "physiology"]):
            subject_rules = BIOLOGY_RULES
        else:
            subject_rules = GENERAL_RULES

    return f"{MAIN_FORMATTING_RULES}\n\n{lang_instruction}\n\n{course_instruction}\n\n{mode_instruction}\n\n{subject_rules}"


OCR_PROMPT = "Read this image carefully and transcribe all the text, unit names, syllabus topics, headings, and questions completely and accurately."

def get_image_notes_prompt(extracted_text, user_prompt):
    if "language: english" in user_prompt.lower():
        return f"""The user has uploaded an image of a syllabus or question paper. Below is the exact text extracted from the image:

--- TEXT INSIDE THE IMAGE ---
{extracted_text}
-----------------------------

User's Selected Subject, Course, Language, Mode & Instruction: "{user_prompt}"

IMPORTANT INSTRUCTION: Never say "I cannot see the image directly" because the full text of the image is provided above. Strictly follow the user's selected Subject, Course (Honours/General), Language (English), and Mode (Notes / Question Answer / Doubt Solve) rules to generate complete unit/topic headings and detailed exam-ready solutions in English."""

    return f"""ইউজার একটি সিলেবাস বা প্রশ্নপত্রের ছবি আপলোড করেছে। ছবিটির ভেতরে নিচের লেখাগুলো রয়েছে:

--- ছবির ভেতরের লেখা ---
{extracted_text}
-------------------------

ইউজারের নির্বাচিত বিষয়, কোর্স, ভাষা, মোড ও নির্দেশ: "{user_prompt}"

বিশেষ নির্দেশ: তুমি কখনোই বলবে না যে "আমি সরাসরি ছবিটি দেখতে পাচ্ছি না"—কারণ ছবির সব লেখা ওপরে দেওয়া হয়েছে। ইউজারের নির্বাচিত Subject, Course (Honours/General), Language (Bengali) এবং Mode (Notes / Question Answer / Doubt Solve) অনুযায়ী ওপরের লেখাগুলোর প্রতিটি টপিক বা প্রশ্নের জন্য নিয়ম মেনে বড় হেডিং, বিস্তারিত নোটস বা ধাপে ধাপে প্রশ্নোত্তর তৈরি করে দাও।"""
