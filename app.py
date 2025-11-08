import os
import re
import json
import requests
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ========== ENV CONFIG ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEET_WEBAPP_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
ROOT_URL = os.getenv("ROOT_URL", "https://digitalmarketingbiz-bot.onrender.com")
PORT = int(os.getenv("PORT", "10000"))

# ========== STORAGE ==========
LEADS_FILE = "leads.json"
def load_leads():
    if not os.path.exists(LEADS_FILE):
        return []
    try:
        with open(LEADS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_leads(leads):
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

# ========== HELPERS ==========
def normalize_email(raw: str) -> str:
    if not raw:
        return ""
    return raw.replace("\u200c", "").replace("\u200f", "").strip().lower()

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
def is_valid_email(email: str) -> bool:
    return EMAIL_RE.match(email.strip()) if email else False

def post_to_sheet(payload: dict, timeout: int = 10) -> bool:
    if not GOOGLE_SHEET_WEBAPP_URL:
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL not set")
        return False
    try:
        r = requests.post(GOOGLE_SHEET_WEBAPP_URL, json=payload, timeout=timeout)
        print(f"📤 POST Sheet → {r.status_code}: {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print("❌ post_to_sheet error:", e)
        return False

# ========== MENU ==========
MAIN_MENU = ReplyKeyboardMarkup(
    [["🏁 شروع", "📘 درباره ما"], ["📝 ثبت‌نام", "📅 رزرو جلسه"]],
    resize_keyboard=True,
)

# ========== STATES ==========
ASK_NAME, ASK_EMAIL = range(2)

# ========== TELEGRAM HANDLERS ==========
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! به ربات دیجیتال مارکتینگ خوش آمدید.\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=MAIN_MENU,
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 *درباره ما:*\n"
        "ما آموزش و راه‌اندازی بیزنس آنلاین، اتوماسیون و دیژیتال مارکتینگ را "
        "برای همه ساده کرده‌ایم. با ما یاد بگیرید چطور برند خودتان را بسازید و درآمد آنلاین کسب کنید.",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )

# === Registration ===
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 لطفاً نام کامل خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("خوب 🌟 حالا لطفاً ایمیل خود را وارد کنید:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = normalize_email(update.message.text)
    name = context.user_data.get("name", "")

    if not is_valid_email(email):
        await update.message.reply_text("❌ ایمیل معتبر نیست. دوباره وارد کنید:")
        return ASK_EMAIL

    lead = {
        "name": name,
        "email": email,
        "user_id": update.effective_user.id if update.effective_user else None,
        "username": update.effective_user.username if update.effective_user else None,
        "status": "Validated",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    leads = load_leads()
    leads.append(lead)
    save_leads(leads)

    posted = post_to_sheet(lead)
    text = f"✅ {name}، ثبت‌نام شما انجام شد!" if posted else "✅ ثبت‌نام انجام شد (ذخیره محلی موفق)."

    await update.message.reply_text(text, reply_markup=MAIN_MENU)
    return ConversationHandler.END

# === Appointment ===
async def appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 برای رزرو جلسه لطفاً وارد این لینک شوید:\n\n"
        "https://calendly.com/your-link\n\n"
        "یا از منوی زیر گزینه دیگری انتخاب کنید.",
        reply_markup=MAIN_MENU,
    )

# === Cancel ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لغو شد.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# ========== APP ==========
application = Application.builder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^(📝 ثبت‌نام|ثبت نام)$"), start_registration)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler("start", show_menu))
application.add_handler(MessageHandler(filters.Regex("^(🏁 شروع)$"), show_menu))
application.add_handler(MessageHandler(filters.Regex("^(📘 درباره ما)$"), about))
application.add_handler(MessageHandler(filters.Regex("^(📅 رزرو جلسه)$"), appointment))

# ========== FLASK & WEBHOOK ==========
flask_app = Flask(__name__)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        # ✅ Thread-safe async call (prevents "Task destroyed" warnings)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e:
        print("❌ Webhook error:", e)
    return "ok"

@flask_app.route("/", methods=["GET"])
def index():
    return f"✅ Bot running — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

def set_webhook():
    try:
        loop.run_until_complete(application.initialize())
        webhook_url = f"{ROOT_URL.rstrip('/')}/{TELEGRAM_TOKEN}"
        loop.run_until_complete(application.bot.set_webhook(webhook_url))
        print(f"✅ Webhook set to {webhook_url}")
        print("✅ Bot started successfully — ready to receive messages.")
    except Exception as e:
        print("⚠️ Webhook setup failed:", e)

set_webhook()

if __name__ == "__main__":
    print("🚀 Starting Digital Marketing Bot with menu...")
    flask_app.run(host="0.0.0.0", port=PORT)
