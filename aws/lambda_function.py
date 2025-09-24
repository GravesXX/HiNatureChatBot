# app.py
import json, os, re, time, uuid, html
from datetime import datetime, timezone
from difflib import SequenceMatcher
import urllib.request, urllib.parse

import boto3

# =========================
# Config
# =========================
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
MODEL_ID       = os.getenv("MODEL_ID", "us.meta.llama3-2-1b-instruct-v1:0")
DDB_TABLE      = os.getenv("DDB_TABLE", "HN_Sessions")            # PK: session_id (S)
SNS_TOPIC_ARN  = os.getenv("SNS_TOPIC_ARN", "")                   # optional
BRAND_NAME     = "Hi Nature! Pet"

# Shopify
SHOPIFY_STORE_URL   = os.getenv("SHOPIFY_STORE_URL", "https://yourstore.myshopify.com")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

# If True, FAQs will be paraphrased by brand_tone(); otherwise exact template is returned.
USE_BRAND_TONE_FOR_FAQ = False

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamo  = boto3.client("dynamodb")
sns     = boto3.client("sns")

# =========================
# FAQ BANK (template answers only)
# =========================
FAQS = [
    {
        "q": "What is fresh cooked dog food?",
        "tags": [
            "fresh cooked", "fresh food", "现做", "鲜食", "熟食",
            "生食对比", "what is your food",
            "why feed fresh cooked", "what is fresh cooked food"
        ],
        "a": ("Fresh cooked dog food is gently prepared at low temperatures to retain nutrients "
              "while eliminating harmful bacteria. It’s safer and easier to digest than raw, and "
              "more nutritious than kibble.")
    },
    {
        "q": "Why feed fresh-cooked?",
        "tags": [
            "why feed fresh cooked",
            "benefits of fresh cooked meals for dogs",
            "why not feed kibble",
            "is fresh cooked food healthier than kibble",
            "why do vets recommend fresh cooked diets",
            "is there scientific proof behind fresh cooked food",
            "expert reasons to feed fresh cooked",
            "why nutritionists support fresh cooked diets",
            "为什么吃鲜食", "鲜食的好处"
        ],
        "a": ("Fresh-cooked meals are made from real, human-grade ingredients and gently prepared to preserve nutrients "
              "and taste. Compared with heavily processed kibble, they’re easier to digest and closer to a dog’s natural "
              "diet. Many pet parents see improvements in digestion, energy, coat, and stools. It’s simply balanced "
              "nutrition from real food, made convenient.")
    },
    {
        "q": "Is Hi Nature! food AAFCO compliant and complete?",
        "tags": [
            "is your food AAFCO compliant",
            "is your food complete and balanced",
            "does Hi Nature meet AAFCO standards",
            "do your recipes follow NRC guidelines",
            "is your food nutritionally complete",
            "are recipes formulated to meet standards",
            "nutritionist verified balanced diets",
            "AAFCO", "complete", "营养全面", "均衡", "is it balanced"
        ],
        "a": ("Yes. All recipes are formulated to meet AAFCO nutrient profiles and align with NRC reference values "
              "for maintenance and growth where applicable. We routinely review formulas with veterinarians and "
              "pet-nutrition professionals for safety and nutritional adequacy.")
    },
    {
        "q": "Is Hi Nature! Pet Canadian?",
        "tags": ["Canadian", "加拿大", "本地", "Toronto", "are you canadian", "made in Canada", "本地食材"],
        "a": ("Yes—proudly Canadian. Made fresh in the Toronto area with locally sourced ingredients.")
    },
    {
        "q": "What ingredients do you use—and what does “human-grade” mean?",
        "tags": [
            "what ingredients do you use",
            "what does human grade mean",
            "are your ingredients human grade",
            "where do your ingredients come from",
            "do you use feed grade ingredients",
            "human grade", "人食级", "人用级", "ingredients", "real food"
        ],
        "a": ("We use fresh, human-grade meats and fish, fruits, and vegetables from trusted Canadian farms and suppliers. "
              "We do not use feed-grade inputs, meat meals, artificial colours, flavours, or preservatives.")
    },
    {
        "q": "Do you add vitamins and minerals?",
        "tags": [
            "do you add vitamins and minerals",
            "are vitamins included in your food",
            "what supplements are added",
            "do you add synthetic nutrients",
            "how do you balance micronutrients",
            "nutritionist formulated vitamin blend",
            "有没有加维生素", "有没有矿物质补充"
        ],
        "a": ("Yes. In addition to nutrients from whole foods, we use targeted, food-grade supplements (vitamin/mineral "
              "additions) as needed to ensure the diet is complete and balanced to AAFCO/NRC standards.")
    },
    {
        "q": "Who formulates the recipes?",
        "tags": [
            "who makes your recipes",
            "who develops your food",
            "who designs the formula",
            "who creates the recipes",
            "who prepares your meals",
            "who is behind the formulation",
            "who formulates the recipes",
            "who balances the nutrition",
            "who approves the recipes",
            "who’s responsible for your formulations",
            "who formulates your food vet or nutritionist",
            "are your recipes formulated by a vet",
            "are your meals created by a veterinary nutritionist",
            "who ensures the recipes meet AAFCO/NRC standards",
            "do veterinarians review your food",
            "is your food developed by experts",
            "is there a pet nutritionist behind the recipes",
            "who guarantees the nutritional balance",
            "who checks the recipes for health & safety",
            "are the formulas vet-approved",
            "配方师", "营养师", "veterinarian", "formulate", "who makes recipes"
        ],
        "a": ("Our recipes are developed by a pet-nutrition team and modified and finalized by licensed veterinarians. "
              "We continuously evaluate palatability, digestibility, and nutrient targets.")
    },
    {
        "q": "Are your meals grain-free or hypoallergenic?",
        "tags": [
            "grain free", "过敏", "敏感肠胃", "低致敏", "allergy", "hypoallergenic",
            "sensitive stomach", "novel protein", "duck", "fish", "对谷物过敏"
        ],
        "a": ("We offer both with and without grains. Many recipes support sensitive stomachs and use novel proteins like duck or fish.")
    },
    {
        "q": "Can I feed Hi Nature! to my puppy?",
        "tags": [
            "can puppies eat your food",
            "do you have puppy recipes",
            "for puppy", "puppy", "幼犬", "小狗",
            "is your food good for all life stages", "puppy diet"
        ],
        "a": ("Current recipes are intended for adult and senior dogs. Puppy formulas are in development—join our email list for updates.")
    },
    {
        "q": "Can my puppy or senior dog eat your food?",
        "tags": [
            "can puppies eat your food",
            "can senior dogs eat your meals",
            "is your food good for all life stages",
            "do you have senior formulas",
            "do you have puppy recipes",
            "老年犬能吃吗", "幼犬能吃吗"
        ],
        "a": ("Puppies (0–8 months): we do not recommend using our meals as a full diet at this age. You may use Hi Nature! as a topper "
              "alongside a complete puppy diet; discuss any changes with your veterinarian.\n"
              "Seniors: yes. We offer a Senior Care pack with senior-friendly ingredients and portions.")
    },
    {
        "q": "How do I tailor meals to my dog?",
        "tags": [
            "how do I tailor meals to my dog",
            "can meals be customized for my pet",
            "how do you calculate portions",
            "do you personalize the nutrition plan",
            "how do you adjust food for my dog’s needs",
            "vet guided meal personalization",
            "nutritionist designed feeding plan",
            "怎么定制配餐", "如何计算克数"
        ],
        "a": ("Tell us about your pup’s age, weight, body condition, activity, and sensitivities, and we’ll recommend recipes and daily portions. "
              "Start here: Meal Calculator")
    },
    {
        "q": "My dog has a sensitive stomach—what should I do?",
        "tags": [
            "my dog has a sensitive stomach what should I do",
            "is your food good for sensitive stomach",
            "which recipes help digestion",
            "do you have a sensitive stomach formula",
            "what to feed a dog with tummy issues",
            "expert advice on sensitive stomach feeding",
            "敏感肠胃 怎么办", "消化不良 吃什么"
        ],
        "a": ("Transition gradually (we include step-by-step instructions in your first box). Many sensitive pups do well on our gentler recipes "
              "and steady portions. If your dog has ongoing health issues or a medical history, please check with your vet.")
    },
    {
        "q": "How do I transition my dog to Hi Nature!",
        "tags": ["transition", "换粮", "过渡", "switch food", "how to transition", "7 day transition"],
        "a": ("Use a 7-day transition: 25% new → 50% → 75% → 100%. Our Starter Box makes it easy.")
    },
    {
        "q": "How do I store fresh cooked pet food?",
        "tags": [
            "how do I store fresh cooked pet food",
            "how to keep the food fresh",
            "how do I store the meals",
            "do I refrigerate or freeze",
            "how long can food stay in fridge",
            "store", "storage", "保存", "冷冻", "冷藏", "how to store",
            "how do I keep the food", "the way to keep the food", "the way to store the food",
            "我怎么保存呀", "如何保鲜"
        ],
        "a": ("Place meals in the freezer upon arrival. Keep 1–2 daily packs in the refrigerator so you’re ready for mealtimes. "
              "Our vacuum-sealed packs store up to 6 months frozen and up to 4 days refrigerated once thawed (unopened). Always use clean utensils.")
    },
    {
        "q": "Can I microwave the food?",
        "tags": ["microwave", "微波炉", "加热", "heat food", "can I warm the food", "加热方式"],
        "a": ("You can gently warm to room temperature; avoid overheating to preserve nutrients.")
    },
    {
        "q": "Can I re-freeze meals that aren’t fully frozen on arrival?",
        "tags": [
            "can I refreeze meals",
            "what if meals arrive thawed",
            "is it safe to refreeze your food",
            "can I re-freeze dog food",
            "what to do if food is not fully frozen",
            "能不能二次冷冻", "到货没完全冻住怎么办"
        ],
        "a": ("If packs feel fridge-cold to the touch (like just out of the refrigerator), you can place them back in the freezer. "
              "If they feel warm, do not feed.")
    },
    {
        "q": "How do I dispose of the packaging?",
        "tags": [
            "how do I dispose of packaging",
            "is your packaging recyclable",
            "can I recycle your insulation and packs",
            "what to do with the box and gel packs",
            "is your packaging eco friendly",
            "sustainable packaging disposal",
            "包装如何处理", "是否可回收"
        ],
        "a": ("Cardboard box & paper inserts: recycle curbside.\n"
              "Gel packs: recycle the outer poly bag where facilities accept plastic film. Cut open the pack and place the gel in the household garbage "
              "(it will dehydrate to ~0.5% of its original weight). Do not pour gel down the drain.\n"
              "Multi-layer insulation: place in garbage.\n"
              "Dry-ice bag (if included): allow any remaining dry ice to dissipate in a well-ventilated area away from people and pets; "
              "dispose of the empty bag per local rules.")
    },
    {
        "q": "How can I calculate how much my dog eats?",
        "tags": [
            "how much to feed", "how much food", "calories", "kcal", "grams",
            "喂多少", "克数", "热量", "配餐",
            "meal calculator", "计算", "calculator",
            "how much food does my dog need to eat",
            "how do you calculate portions"
        ],
        "a": ("There’s a ‘Meal Calculator’ section on our website—just follow the steps there to get a tailored daily amount. "
              "You can choose between full meals or toppings across multiple recipes.<br><br>"
              "👉 <a href='https://hinaturepet.com/#quiz-RbHqn8B' target='_blank' rel='noopener'>Try the Meal Calculator here</a>")
    },
    {
        "q": "Where do you deliver and what’s the cost?",
        "tags": [
            "where do you deliver",
            "what areas do you ship to",
            "is delivery available in my city",
            "do you deliver outside Ontario",
            "what is the delivery cost",
            "shipping fees for your dog food",
            "how is food shipped safely",
            "deliver", "delivery", "shipping", "运费", "配送", "where deliver", "delivery areas", "where do you ship"
        ],
        "a": ("We ship to most Ontario and Québec key urban areas.\n"
              "GTA addresses: free shipping.\n"
              "Outside the GTA (ON/QC urban zones): orders under CA$150 ship at a CA$5.99 flat rate; orders CA$150+ ship free. "
              "Availability is confirmed at checkout by postal code.")
    },
    {
        "q": "When will I receive my delivery?",
        "tags": [
            "when will I receive my delivery",
            "how long does shipping take",
            "when will my food arrive",
            "delivery time for orders",
            "how soon will I get my box",
            "expected delivery date",
            "when deliver", "到货", "发货时间", "delivery time", "到货时间",
            "when can i get my dog food", "when can i get my dogfood",
            "when get dog food", "when will my order arrive", "delivery arrive", "什么时候能拿到狗粮"
        ],
        "a": ("Orders placed before Friday at midnight ship the following Tuesday or Wednesday.\n"
              "Delivery usually takes 1–3 business days depending on your location.")
    },
    {
        "q": "What’s in the Starter Box?",
        "tags": [
            "what’s in the starter box",
            "what do I get in the starter box",
            "what comes in the trial box",
            "what meals are included in starter pack",
            "do I get all recipes in starter box",
            "新手礼包 里面有什么"
        ],
        "a": ("You’ll receive 7 fresh cooked meal packs, a Feeding Guide and storage instructions, plus a small mystery gift (toy, accessory, or treat).")
    },
    {
        "q": "What if I’m not home when it’s delivered?",
        "tags": [
            "what if I’m not home for delivery",
            "do I need to be home for delivery",
            "can the food be left at my door",
            "will food stay safe if I’m not home",
            "how long will food stay frozen outside",
            "不在家 怎么办", "是否需要在家收货"
        ],
        "a": ("Our insulated packaging and coolants are designed to keep meals cold through the delivery window. For best results, we recommend retrieving "
              "evening deliveries the same night and placing the meals in your freezer right away. If you expect to be away longer, consider having the "
              "box delivered to a location where someone can receive it on your behalf.")
    },
    {
        "q": "Will my food arrive frozen?",
        "tags": [
            "will my food arrive frozen",
            "is food delivered frozen",
            "do meals stay frozen in transit",
            "how is the food kept frozen",
            "will the box be cold on arrival",
            "到货是冷冻的吗", "运输如何保冷"
        ],
        "a": ("Yes. Every order is shipped with insulation and gel packs to keep the food cold while in transit. Please bring the box inside promptly and "
              "place the packs in the freezer right away. If a pack arrives refrigerator-cold to the touch, it’s safe to feed or re-freeze.")
    },
    {
        "q": "Can I manage or pause my subscription?",
        "tags": [
            "can I manage my subscription",
            "can I pause my plan",
            "can I skip deliveries",
            "how do I change my subscription",
            "how to update my dog’s plan",
            "subscription flexibility options",
            "pause", "skip", "cancel", "订阅", "修改", "manage subscription"
        ],
        "a": ("Yes! Simply log into your account to skip, pause, reschedule, or cancel your subscription anytime.")
    },
    {
        "q": "Can I return meals?",
        "tags": [
            "can I return meals",
            "do you accept returns",
            "what’s your return policy",
            "can I send back unused packs",
            "can I get a refund for meals",
            "能不能退货", "是否支持退款"
        ],
        "a": ("Because our products are frozen and perishable, all sales are final and we can’t accept returns. If something is incorrect or there’s a "
              "delivery issue, email hello@hinaturepet.com with your order number and photos—we’ll help promptly.")
    },
    {
        "q": "Do I have to subscribe?",
        "tags": [
            "do I have to subscribe",
            "can I buy one time",
            "is subscription required",
            "do you offer one time purchase",
            "can I try without a plan",
            "subscription vs one time order",
            "必须订阅吗", "能不能一次性买"
        ],
        "a": ("Not necessarily. Most pet parents choose our flexible subscription for the savings and convenience—it makes sure your dog never runs out. "
              "But if you prefer to order only when needed, you can also make a one-time purchase (8 packs minimum) at the regular price. And if you’re brand "
              "new to Hi Nature, our Starter Box with 40% off is the best way to try us first before deciding on a plan.")
    }
]

# =========================
# Helpers
# =========================
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

def now_epoch(): return int(time.time())
def normalize(s): return re.sub(r"\s+", " ", s or "").strip()
def sm_ratio(a, b): return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def best_faq_match(text):
    best = (0.0, None)
    for item in FAQS:
        score = sm_ratio(text, item["q"])
        for tag in item.get("tags", []):
            score = max(score, sm_ratio(text, tag))
        if score > best[0]:
            best = (score, item)
    return best  # (score, item)

# DynamoDB session state
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
        state   = json.loads(item.get("state",   {"S": "{}"})["S"])
        return {"history": history, "state": state}
    except Exception:
        return {"history": [], "state": {}}

def save_session(session_id, history, state):
    dynamo.put_item(
        TableName=DDB_TABLE,
        Item={
            "session_id": {"S": session_id},
            "history": {"S": json.dumps(history, ensure_ascii=False)},
            "state":   {"S": json.dumps(state, ensure_ascii=False)},
            "updated_at": {"N": str(now_epoch())}
        }
    )

# =========================
# Shopify Helpers
# =========================
def shopify_get(path, params=None):
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{SHOPIFY_STORE_URL}/admin/api/2025-01/{path}{query}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_customer_by_email(email: str):
    data = shopify_get("customers/search.json", {"query": f"email:{email}"})
    return data.get("customers", [])

def get_orders_by_customer(customer_id: str):
    return shopify_get("orders.json", {"customer_id": customer_id, "status": "any"}).get("orders", [])

def summarize_order(order):
    number = order["order_number"]
    created = datetime.fromisoformat(order["created_at"].replace("Z","+00:00")).strftime("%b %d")
    status = order.get("fulfillment_status") or "unfulfilled"
    reply = f"Your order #{number} placed on {created} is {status}."
    if order.get("fulfillments"):
        f = order["fulfillments"][0]
        tracking = f.get("tracking_number")
        company  = f.get("tracking_company")
        if tracking and company:
            reply += f" Tracking: {company} {tracking}."
    return reply


# =========================
# LLM helpers (fallback + brand tone)
# =========================
def _clean_brand_text(t: str) -> str:
    """Strip prefaces like 'Here is the rewritten message...', code fences, quotes."""
    if not t: return t
    s = t.strip()
    s = re.sub(r"^```(?:\w+)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    s = re.sub(r"^(here('?|’)?s|this is|rewrit\w+|polish\w+|in the warm.*tone).*?:\s*",
               "", s, flags=re.IGNORECASE)
    s = s.strip().strip('“”"\'').strip()
    return html.unescape(s)

def brand_tone(text):
    """Rewrite in brand tone, output only the sentence; sanitize any meta."""
    try:
        sys = (
            f"You are a style rewriter for a Canadian pet food brand called {BRAND_NAME}. "
            "Rewrite the user's message in a warm, concise, friendly tone. "
            "Keep all facts unchanged. "
            "IMPORTANT: Output ONLY the rewritten message with no preface, no explanations, no quotes, no markdown."
        )
        prompt = (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n" + sys + "\n<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n" + text + "\n<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )
        payload = {"prompt": prompt, "max_gen_len": 280, "temperature": 0.15}
        r = bedrock.invoke_model(
            modelId=MODEL_ID, body=json.dumps(payload),
            accept="application/json", contentType="application/json",
        )
        data = json.loads(r["body"].read())
        raw  = (data.get("generation") or "").strip()
        return _clean_brand_text(raw) or text
    except Exception:
        return text

def llm_reply(history, user_message):
    last = history[-10:]
    conv = []
    for m in last:
        conv.append(f"<|start_header_id|>{m['role']}<|end_header_id|>\n{m['content']}\n<|eot_id|>")
    conv.append(f"<|start_header_id|>user<|end_header_id|>\n{user_message}\n<|eot_id|>")
    sys = ("You are a friendly assistant for a pet food store called Hi Nature! Pet. "
           "Keep replies brief, polite, and helpful.")
    prompt = ("<|begin_of_text|>"
              f"<|start_header_id|>system<|end_header_id|>\n{sys}\n<|eot_id|>"
              + "".join(conv) +
              "<|start_header_id|>assistant<|end_header_id|>\n")
    payload = {"prompt": prompt, "max_gen_len": 400, "temperature": 0.3}
    r = bedrock.invoke_model(
        modelId=MODEL_ID, body=json.dumps(payload),
        accept="application/json", contentType="application/json",
    )
    data = json.loads(r["body"].read())
    return (data.get("generation") or "").strip()

# =========================
# Intent detection
# =========================
KW_ORDER = ["order", "订单", "status", "where is my order", "track", "tracking"]
KW_DELIV = ["deliver", "delivery", "shipping", "物流", "送货", "配送", "arrive", "到货"]

def detect_intent(msg, explicit=None):
    if explicit: return explicit
    m = msg.lower()
    if any(k in m for k in KW_ORDER): return "order_status"
    if any(k in m for k in KW_DELIV): return "faq"  # delivery timing is an FAQ
    score, _ = best_faq_match(m)
    if score >= 0.70: return "faq"
    return "fallback"

# =========================
# Escalation via SNS
# =========================
def escalate_to_sns(kind, session_id, user_message, contact=None):
    if not SNS_TOPIC_ARN: return None
    payload = {
        "type": kind, "session_id": session_id, "message": user_message,
        "contact": contact, "ts": datetime.now(timezone.utc).isoformat()
    }
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"{BRAND_NAME}: {kind} request",
        Message=json.dumps(payload, ensure_ascii=False)
    )
    return payload

# =========================
# Handlers
# =========================
def handle_faq(user_message):
    score, item = best_faq_match(user_message)
    if not item or score < 0.70:
        # If user text smells like delivery but similarity is low, force delivery FAQ.
        if any(k in user_message.lower() for k in ["when", "arrive", "到货", "发货"]):
            for it in FAQS:
                if "When will I receive my delivery?" in it["q"]:
                    item = it; break
        if not item: return None
    text = item["a"]
    return brand_tone(text) if USE_BRAND_TONE_FOR_FAQ else text

def handle_escalation(kind, session_id, user_message, state):
    ticket = escalate_to_sns(kind, session_id, user_message, contact=state.get("contact"))
    if ticket:
        return (f"I’ve sent your {kind.replace('_', ' ')} request to our team. "
                "We’ll follow up shortly. You can reply with your email/phone to speed things up.")
    else:
        return ("I can flag this for a human, but SNS isn’t configured. "
                "Please contact support, or set SNS_TOPIC_ARN in the backend.")
    
def handle_order_status(session_id, user_message, state):
    # Step 1. Extract email
    email = state.get("contact")
    if not email:
        match = re.search(r"[\w\.-]+@[\w\.-]+", user_message)
        if match:
            email = match.group(0)
            state["contact"] = email
        else:
            return "Can you please provide the email you used for your order?"

    # Step 2. Fetch customer
    try:
        customers = get_customer_by_email(email)
    except Exception as e:
        return "Sorry, I wasn’t able to reach our order system. Please try again later."

    if not customers:
        return f"We couldn’t find any customer with {email}. You may not have an account with us yet."

    # Step 3. Fetch orders
    try:
        customer_id = customers[0]["id"]
        orders = get_orders_by_customer(customer_id)
    except Exception:
        return "Sorry, I wasn’t able to retrieve your orders. Please try again later."

    if not orders:
        return f"We found your profile but no orders linked to {email}."

    # Step 4. Return latest order summary
    latest = orders[0]
    return summarize_order(latest)


# =========================a
# Lambda entry
# =========================
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        session_id      = (body.get("session_id") or "").strip() or str(uuid.uuid4())
        user_message    = normalize(body.get("message"))
        explicit_intent = body.get("intent")

        if not user_message:
            return _resp(400, {"error": "message required"})

        session = load_session(session_id)
        history = session["history"]
        state   = session["state"]

        # record user
        history.append({"role": "user", "content": user_message, "ts": now_epoch()})

        # ---- intent handling ----
        # if we're already inside an order_status flow, STAY there
        prev_intent = history[-2]["intent"] if len(history) >= 2 else None
        if prev_intent == "order_status" and "resolved" not in state:
            intent = "order_status"
        else:
            intent = detect_intent(user_message, explicit=explicit_intent)

        reply_payload = {}
        reply_text = None

        if intent == "faq":
            reply_text = handle_faq(user_message) or \
                         "For deliveries: orders before Friday 23:59 ship Tue/Wed; transit 1–3 business days."
        elif intent == "order_status":
            reply_text = handle_order_status(session_id, user_message, state)
            # mark resolved so we don’t loop forever
            if "order #" in reply_text.lower():
                state["resolved"] = True
        elif intent == "delivery":
            reply_text = handle_escalation("delivery", session_id, user_message, state)
        else:
            reply_text = llm_reply(history, user_message)

        # record assistant
        history.append({"role": "assistant", "content": reply_text, "ts": now_epoch(), "intent": intent})

        # persist
        save_session(session_id, history, state)

        return _resp(200, {
            "reply": reply_text,
            "intent": intent,
            "session_id": session_id,
            "state": state,
            "meta": reply_payload
        })

    except Exception as e:
        return _resp(502, {"error": str(e)})
