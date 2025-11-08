# app.py
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

# ==================== Config ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEET_WEBAPP_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
ROOT_URL = os.getenv("ROOT_URL", "https://digitalmarketingbiz-bot.onrender.com")
PORT = int(os.getenv("PORT", "10000"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Missing TELEGRAM_TOKEN environment variable")

# ==================== Local backup file ====================
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

# ==================== Helpers ====================
def normalize_email(raw: str) -> str:
    if not raw:
        return ""
    return raw.replace("\u200c", "").replace("\u200f", "").strip().lower()

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def is_valid_email(email_str: str) -> bool:
    if not email_str:
        return False
    return EMAIL_RE.match(email_str.strip()) is not None

def post_to_sheet(payload: dict, timeout: int = 10) -> bool:
    if not GOOGLE_SHEET_WEBAPP_URL:
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL not set")
        return False
    try:
        resp = requests.post(GOOGLE_SHEET_WEBAPP_URL, json=payload, timeout=timeout)
        print(f"📤 POST Sheet → {resp.status_code}: {resp.text[:200]}")
        return resp.status_code == 200
    except Exception as e:
        print("❌ post_to_sheet error:", e)
        return False

# ==================== Telegram Conversation States ====================
ASK_NAME, ASK_EMAIL = range(2)

# ==================== Telegram Handlers ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    intro = (
        "👋 سلام! خوش آمدید به *Digital Marketing Business Bot*.\n\n"
        "ما در اینجا به شما آموزش می‌دهیم چگونه کسب‌وکار دیجیتال خود را راه‌اندازی کنید "
        "و با ابزارهای مارکتینگ آنلاین رشد کنید.\n\n"
        "برای ادامه یکی از گزینه‌های زیر را انتخاب کنید 👇"
    )
    keyboard = ReplyKeyboardMarkup(
        [["📘 درباره ما", "📝 ثبت نام"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(intro, reply_markup=keyboard, parse_mode="Markdown")

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌐 *درباره ما:*\n\n"
        "ما آموزش دیجیتال مارکتینگ و راه‌اندازی بیزنس آنلاین را ساده و قابل‌فهم کرده‌ایم. "
        "با ما یاد می‌گیرید چگونه مشتری جذب کنید، محتوای حرفه‌ای بسازید و از ابزارهای اتوماسیون استفاده کنید."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عالی 🌟 لطفاً نام کامل خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text("خیلی خوب ✅ حالا لطفاً ایمیل خود را وارد کنید (مثلاً example@gmail.com):")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = normalize_email(update.message.text)
    name = context.user_data.get("name", "").strip()

    if not is_valid_email(email):
        await update.message.reply_text("❌ ایمیل معتبر نیست. لطفاً دوباره وارد کنید:")
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
    print("💾 Saved locally:", lead)

    posted = post_to_sheet({
        "name": lead["name"],
        "email": lead["email"],
        "username": lead["username"] or "",
        "user_id": lead["user_id"] or "",
        "status": lead["status"],
    })

    if posted:
        msg = f"✅ ایمیل شما ({email}) معتبر است و ثبت شد. ممنون از شما!"
    else:
        msg = f"✅ ایمیل شما ({email}) معتبر است، ولی ارسال به Google Sheet انجام نشد."

    await update.message.reply_text(msg)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفت‌وگو لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==================== Telegram App ====================
application = Application.builder().token(TELEGRAM_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(r"^(📝 ثبت نام|ثبت نام)$"), start_registration)
    ],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(MessageHandler(filters.Regex(r"^(📘 درباره ما|درباره ما)$"), about))
application.add_handler(CommandHandler("cancel", cancel))

# ==================== Flask + Webhook ====================
flask_app = Flask(__name__)

# persistent loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        loop.create_task(application.process_update(update))
    except Exception as e:
        print("❌ Webhook error:", e)
    return "ok"

@flask_app.route("/", methods=["GET"])
def index():
    return f"✅ Bot running — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

# ==================== Webhook setup ====================
def set_webhook():
    webhook_url = f"{ROOT_URL.rstrip('/')}/{TELEGRAM_TOKEN}"
    try:
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.bot.set_webhook(webhook_url))
        print(f"✅ Webhook set to: {webhook_url}")
    except Exception as e:
        print("⚠️ Webhook setup failed:", e)

set_webhook()

# ==================== Entry ====================
if __name__ == "__main__":
    print("🚀 Starting Digital Marketing Bot...")
    flask_app.run(host="0.0.0.0", port=PORT)
