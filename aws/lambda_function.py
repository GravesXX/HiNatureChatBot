# app.py
import json, os, re, math, time, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

import boto3

# ---------- Config ----------
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
MODEL_ID = os.getenv("MODEL_ID", "us.meta.llama3-2-1b-instruct-v1:0")
DDB_TABLE = os.getenv("DDB_TABLE", "HN_Sessions")            # PK: session_id (S)
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")               # optional; publish if set
BRAND_NAME = "Hi Nature! Pet"

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamo  = boto3.client("dynamodb")
sns     = boto3.client("sns")

# ---------- FAQ bank (template answers) ----------
FAQS = [
    {
        "q": "What is fresh cooked dog food?",
        "tags": ["fresh cooked", "fresh food", "现做", "鲜食", "熟食", "生食对比"],
        "a": ("Fresh cooked dog food is gently prepared at low temperatures to retain nutrients "
              "while eliminating harmful bacteria. It’s safer and easier to digest than raw, and "
              "more nutritious than kibble.")
    },
    {
        "q": "Is Hi Nature! food AAFCO compliant and complete?",
        "tags": ["AAFCO", "complete", "营养全面", "均衡"],
        "a": ("Yes. Every Hi Nature! recipe is AAFCO-compliant and formulated by pet nutritionists "
              "and veterinarians to provide 100% complete and balanced nutrition for adult and senior dogs.")
    },
    {
        "q": "Is Hi Nature! Pet Canadian?",
        "tags": ["Canadian", "加拿大", "本地", "Toronto"],
        "a": ("Yes—proudly Canadian. Made fresh in the Toronto area with locally sourced ingredients.")
    },
    {
        "q": "Do you use human-grade ingredients?",
        "tags": ["human grade", "人食级", "人用级", "ingredients"],
        "a": ("Absolutely. Only fresh, human-grade ingredients—no meat meals, fillers, or artificial preservatives.")
    },
    {
        "q": "Are your meals grain-free or hypoallergenic?",
        "tags": ["grain free", "过敏", "敏感肠胃", "低致敏"],
        "a": ("We offer both with and without grains. Many recipes support sensitive stomachs and use novel proteins like duck or fish.")
    },
    {
        "q": "Who formulates the recipes?",
        "tags": ["配方师", "营养师", "veterinarian", "formulate"],
        "a": ("Meals are developed by certified pet nutritionists and reviewed by veterinarians.")
    },
    {
        "q": "Can I feed Hi Nature! to my puppy?",
        "tags": ["puppy", "幼犬", "小狗"],
        "a": ("Current recipes are intended for adult and senior dogs. Puppy formulas are in development—join our email list for updates.")
    },
    {
        "q": "How do I store fresh cooked pet food?",
        "tags": ["store", "storage", "保存", "冷冻", "冷藏"],
        "a": ("Keep meals frozen up to 6 months. After thawing, refrigerate and use within 4 days. Don’t leave at room temp >2 hours.")
    },
    {
        "q": "Can I microwave the food?",
        "tags": ["microwave", "微波炉", "加热"],
        "a": ("You can gently warm to room temperature; avoid overheating to preserve nutrients.")
    },
    {
        "q": "How do I transition my dog to Hi Nature!",
        "tags": ["transition", "换粮", "过渡"],
        "a": ("Use a 7-day transition: 25% new → 50% → 75% → 100%. Our Starter Box makes it easy.")
    },
    {
        "q": "Where do you deliver and what’s the cost?",
        "tags": ["deliver", "delivery", "shipping", "运费", "配送"],
        "a": ("We ship within Ontario and Québec. GTA: $5.99, free over $100. Most ON & QC: $9.99, free over $150. Final rates shown at checkout.")
    },
    {
        "q": "When will I receive my delivery?",
        "tags": ["when deliver", "到货", "发货时间"],
        "a": ("Orders placed before Friday 23:59 ship the following Tue/Wed; transit 1–3 business days by location.")
    },
    {
        "q": "Can I manage or pause my subscription?",
        "tags": ["pause", "skip", "cancel", "订阅", "修改"],
        "a": ("Yes—log into your account to skip, pause, reschedule, or cancel anytime.")
    },
]

# ---------- Multipliers (from your screenshot) ----------
# Puppy's ranges are wide; we present an average and the range used.
MULTIPLIERS = {
    "puppy_lt_4m": (2.5, 3.0, 2.75),
    "puppy_4_12m": (1.6, 2.0, 1.8),
    "adult_spayed_active": (1.3, 1.4, 1.35),
    "adult_spayed_normal": (1.2, 1.3, 1.25),
    "adult_spayed_low": (1.0, 1.1, 1.05),
    "adult_intact_active": (1.4, 1.5, 1.45),
    "adult_intact_normal": (1.3, 1.3, 1.30),
    "adult_intact_low": (1.2, 1.2, 1.20),
    "senior": (1.0, 1.2, 1.10),
}

# ---------- Utilities ----------
def _resp(code, obj):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type"
        },
        "body": json.dumps(obj, ensure_ascii=False)
    }

def now_epoch():
    return int(time.time())

def sm_ratio(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def best_faq_match(text):
    best = (0.0, None)
    for item in FAQS:
        score = sm_ratio(text, item["q"])
        for tag in item.get("tags", []):
            score = max(score, sm_ratio(text, tag))
        if score > best[0]:
            best = (score, item)
    return best  # (score, item | None)

def normalize(s):
    return re.sub(r"\s+", " ", s or "").strip()

# ---------- DynamoDB (single-item per session: history + state) ----------
def load_session(session_id):
    try:
        r = dynamo.get_item(
            TableName=DDB_TABLE,
            Key={"session_id": {"S": session_id}},
            ConsistentRead=True
        )
        if "Item" not in r:
            return {"history": [], "state": {}}
        item = r["Item"]
        history = json.loads(item.get("history", {"S": "[]"})["S"])
        state = json.loads(item.get("state", {"S": "{}"})["S"])
        return {"history": history, "state": state}
    except Exception:
        return {"history": [], "state": {}}

def save_session(session_id, history, state):
    dynamo.put_item(
        TableName=DDB_TABLE,
        Item={
            "session_id": {"S": session_id},
            "history": {"S": json.dumps(history, ensure_ascii=False)},
            "state": {"S": json.dumps(state, ensure_ascii=False)},
            "updated_at": {"N": str(now_epoch())}
        }
    )

def append_history(state, role, content):
    state["history"].append({"role": role, "content": content, "ts": now_epoch()})

# ---------- Bedrock fallback / paraphrase ----------
def llm_reply(history, user_message):
    # compress last 10 turns
    last = history[-10:]
    conv = []
    for m in last:
        conv.append(f"<|start_header_id|>{m['role']}<|end_header_id|>\n{m['content']}\n<|eot_id|>")
    conv.append(f"<|start_header_id|>user<|end_header_id|>\n{user_message}\n<|eot_id|>")
    sys = (
        "You are a friendly assistant for a pet food store called Hi Nature! Pet. "
        "Keep replies brief, polite, and helpful."
    )
    prompt = "<|begin_of_text|>" \
             f"<|start_header_id|>system<|end_header_id|>\n{sys}\n<|eot_id|>" \
             + "".join(conv) + "<|start_header_id|>assistant<|end_header_id|>\n"
    payload = {"prompt": prompt, "max_gen_len": 400, "temperature": 0.3}
    r = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload),
        accept="application/json",
        contentType="application/json",
    )
    data = json.loads(r["body"].read())
    return (data.get("generation") or "").strip()

def brand_tone(text):
    # optional small pass through LLM to keep brand voice
    try:
        prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"Rewrite the message in the warm, concise tone of a Canadian pet food brand called {BRAND_NAME}. "
            "Keep facts unchanged.\n"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            f"{text}\n"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        )
        payload = {"prompt": prompt, "max_gen_len": 300, "temperature": 0.2}
        r = bedrock.invoke_model(
            modelId=MODEL_ID, body=json.dumps(payload),
            accept="application/json", contentType="application/json",
        )
        data = json.loads(r["body"].read())
        t = (data.get("generation") or "").strip()
        return t or text
    except Exception:
        return text

# ---------- Intent detection ----------
KW_MEAL = ["calorie", "kcal", "how much to feed", "how much food",
           "吃多少", "热量", "计算", "配餐", "克数", "喂多少"]
KW_ORDER = ["order", "订单", "status", "where is my order", "track"]
KW_DELIV = ["deliver", "delivery", "shipping", "物流", "送货", "配送"]

def detect_intent(msg, explicit=None):
    if explicit:
        return explicit
    m = msg.lower()
    if any(k in m for k in KW_ORDER):
        return "order_status"
    if any(k in m for k in KW_DELIV):
        return "delivery"
    if any(k in m for k in KW_MEAL):
        return "meal_calc"
    # try FAQ similarity
    score, item = best_faq_match(m)
    if score >= 0.72:
        return "faq"
    return "fallback"

# ---------- Slot parsing for Meal Calculator ----------
def parse_slots(text):
    t = text.lower()

    # weight
    weight_kg = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(kg|公斤|千克)\b', t)
    if m:
        weight_kg = float(m.group(1))
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(lb|lbs|磅)\b', t)
        if m:
            weight_kg = float(m.group(1)) * 0.453592

    # age → months
    age_months = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(months|month|m|月)\b', t)
    if m:
        age_months = float(m.group(1))
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*(years|year|y|岁|年)\b', t)
        if m:
            age_months = float(m.group(1)) * 12

    # spayed / neutered
    spayed = None
    if re.search(r'(neuter|neutered|spay|spayed|已绝育|绝育)', t):
        spayed = True
    if re.search(r'(未绝育|intact|not neutered|not spayed)', t):
        spayed = False

    # activity: low / normal / active
    activity = None
    if re.search(r'(very\s*active|工作犬|running|sport)', t):
        activity = "active"
    if re.search(r'(active|活跃)', t):
        activity = "active"
    if re.search(r'(sedentary|不活跃|低|少动)', t):
        activity = "low"
    if re.search(r'(normal|一般|适中|moderate)', t):
        activity = "normal" if activity is None else activity

    # gender
    gender = None
    if re.search(r'\b(male|公)\b', t):
        gender = "male"
    if re.search(r'\b(female|母)\b', t):
        gender = "female"

    # body type: lean / ideal / overweight
    body_type = None
    if re.search(r'(lean|偏瘦|太瘦|瘦)', t):
        body_type = "lean"
    if re.search(r'(ideal|正常|标准|适中)', t):
        body_type = "ideal"
    if re.search(r'(overweight|超重|偏胖|胖)', t):
        body_type = "overweight"

    # breed (very rough; after the word breed/品种)
    breed = None
    m = re.search(r'(breed|品种)\s*[:：]?\s*([a-zA-Z\u4e00-\u9fa5\- ]{2,})', t)
    if m:
        breed = m.group(2).strip()

    return {
        "gender": gender,
        "weight_kg": weight_kg,
        "age_months": age_months,
        "spayed": spayed,
        "activity": activity,
        "body_type": body_type,
        "breed": breed
    }

REQUIRED_SLOTS = ["gender", "weight_kg", "age_months", "spayed", "activity", "body_type"]

def missing_slots(slots):
    return [k for k in REQUIRED_SLOTS if slots.get(k) in (None, "", [])]

def multiplier_for(slots):
    age_m = slots["age_months"]
    years = age_m / 12.0
    if age_m < 4 * 12 / 12:  # <4 months
        return MULTIPLIERS["puppy_lt_4m"]
    if age_m < 12:          # 4–12 months
        return MULTIPLIERS["puppy_4_12m"]
    if years >= 7:
        return MULTIPLIERS["senior"]
    spayed = bool(slots["spayed"])
    act = slots["activity"] or "normal"
    key = None
    if spayed:
        if act == "active":
            key = "adult_spayed_active"
        elif act == "low":
            key = "adult_spayed_low"
        else:
            key = "adult_spayed_normal"
    else:
        if act == "active":
            key = "adult_intact_active"
        elif act == "low":
            key = "adult_intact_low"
        else:
            key = "adult_intact_normal"
    return MULTIPLIERS[key]

def rer(weight_kg):
    # Resting Energy Requirement
    return 70.0 * (weight_kg ** 0.75)

def apply_bodytype_adjustment(kcal, body_type):
    if body_type == "lean":
        return kcal * 1.10
    if body_type == "overweight":
        return kcal * 0.90
    return kcal

# ---------- Escalation ----------
def escalate_to_sns(kind, session_id, user_message, contact=None):
    if not SNS_TOPIC_ARN:
        return None
    payload = {
        "type": kind,
        "session_id": session_id,
        "message": user_message,
        "contact": contact,
        "ts": datetime.now(timezone.utc).isoformat()
    }
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"{BRAND_NAME}: {kind} request",
        Message=json.dumps(payload, ensure_ascii=False)
    )
    return payload

# ---------- Handlers ----------
def handle_faq(user_message):
    score, item = best_faq_match(user_message)
    if not item or score < 0.72:
        return None
    text = f"{item['a']}"
    # optional: polish in brand tone
    return brand_tone(text)

def handle_meal(user_message, session_state):
    # slot filling
    slots = session_state.get("meal_slots", {})
    slots.update({k: v for k, v in parse_slots(user_message).items() if v is not None})
    session_state["meal_slots"] = slots

    todo = missing_slots(slots)
    if todo:
        # ask for all missing at once (your requirement: ask wholly)
        questions = []
        if "gender" in todo:      questions.append("gender (male/female)")
        if "weight_kg" in todo:   questions.append("weight in kg (or lb)")
        if "age_months" in todo:  questions.append("age (months or years)")
        if "spayed" in todo:      questions.append("spayed/neutered? (yes/no)")
        if "activity" in todo:    questions.append("activity (low / normal / active)")
        if "body_type" in todo:   questions.append("body type (lean / ideal / overweight)")
        prompt = ("To calculate calories, please provide ALL of these:\n"
                  "- " + "\n- ".join(questions) +
                  "\n(You can send them in one sentence, any order. Example: "
                  "'female, 12 kg, 3 years, spayed, normal activity, ideal body')")
        return {"need_more": True, "reply": prompt, "slots": slots}

    # we have all required slots—compute
    low, high, mid = multiplier_for(slots)
    base = rer(slots["weight_kg"])
    kcal_mid = apply_bodytype_adjustment(base * mid, slots["body_type"])
    kcal_low = apply_bodytype_adjustment(base * low, slots["body_type"])
    kcal_high = apply_bodytype_adjustment(base * high, slots["body_type"])

    years = slots["age_months"] / 12.0
    spay_txt = "spayed/neutered" if slots["spayed"] else "intact"
    msg = (
        f"Here’s a starting point for daily energy needs:\n"
        f"- Weight: {slots['weight_kg']:.1f} kg, Age: {years:.1f} years, {spay_txt}, "
        f"activity: {slots['activity']}, body type: {slots['body_type']}.\n"
        f"- RER = 70 × kg^0.75 = {base:.0f} kcal/day.\n"
        f"- Multiplier range {low}–{high} → {kcal_low:.0f}–{kcal_high:.0f} kcal/day.\n"
        f"- Practical target: ~{kcal_mid:.0f} kcal/day (adjust 5–10% after 1–2 weeks based on body condition).\n"
        f"If you tell me the recipe’s kcal per gram, I can convert to grams/day."
    )
    return {"need_more": False, "reply": brand_tone(msg), "slots": slots}

def handle_escalation(kind, session_id, user_message, state):
    # Publish to SNS and mark state for humans
    ticket = escalate_to_sns(kind, session_id, user_message, contact=state.get("contact"))
    if ticket:
        return (f"I’ve sent your {kind.replace('_', ' ')} request to our team. "
                "We’ll follow up shortly. If you’d like, reply with your email/phone to speed things up.")
    else:
        return ("I can flag this for a human, but SNS isn’t configured. "
                "Please contact support, or set SNS_TOPIC_ARN in the backend.")

# ---------- Lambda entry ----------
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        session_id = (body.get("session_id") or "").strip() or str(uuid.uuid4())
        user_message = normalize(body.get("message"))
        explicit_intent = body.get("intent")  # optional override from frontend

        if not user_message:
            return _resp(400, {"error": "message required"})

        # load session
        session = load_session(session_id)
        history = session["history"]
        state = session["state"]
        if "meal_slots" not in state:
            state["meal_slots"] = {}

        # append user message
        history.append({"role": "user", "content": user_message, "ts": now_epoch()})

        # route
        intent = detect_intent(user_message, explicit=explicit_intent)
        reply_payload = {}
        reply_text = None

        if intent == "faq":
            reply_text = handle_faq(user_message)
            if reply_text is None:
                intent = "fallback"  # safety
        if intent == "meal_calc":
            out = handle_meal(user_message, state)
            reply_payload["meal"] = out
            reply_text = out["reply"]
        if intent == "order_status":
            reply_text = handle_escalation("order_status", session_id, user_message, state)
        if intent == "delivery":
            reply_text = handle_escalation("delivery", session_id, user_message, state)
        if intent == "fallback":
            reply_text = llm_reply(history, user_message)

        # append assistant message
        history.append({"role": "assistant", "content": reply_text, "ts": now_epoch(), "intent": intent})

        # save session
        save_session(session_id, history, state)

        # response
        result = {
            "reply": reply_text,
            "intent": intent,
            "session_id": session_id,
            "state": state,          # client can keep a local mirror if desired
            "meta": reply_payload
        }
        return _resp(200, result)

    except Exception as e:
        return _resp(502, {"error": str(e)})
