import os
import re
import json
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
import requests

# ==========================================================
# 🔧 Load environment variables
# ==========================================================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
GOOGLE_SHEET_WEBAPP_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
ROOT_URL = os.getenv("ROOT_URL", "https://digitalmarketingbiz-bot.onrender.com")

# ==========================================================
# 🗂 Local storage setup
# ==========================================================
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

# ==========================================================
# 📧 Email validation & Google Sheet posting
# ==========================================================
def is_valid_email(email_str: str) -> bool:
    """Basic regex email validator"""
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email_str) is not None

def post_to_sheet(payload: dict, timeout: int = 15) -> bool:
    """Send lead to Google Sheet via Apps Script WebApp URL."""
    if not GOOGLE_SHEET_WEBAPP_URL:
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL not set")
        return False
    try:
        resp = requests.post(GOOGLE_SHEET_WEBAPP_URL, json=payload, timeout=timeout)
        print(f"📤 Sheet POST: {resp.status_code} - {resp.text[:120]}")
        return resp.status_code == 200
    except Exception as e:
        print("❌ post_to_sheet error:", e)
        return False

# ==========================================================
# 🤖 Telegram Bot Setup
# ==========================================================
ASK_NAME, ASK_EMAIL = range(2)
flask_app = Flask(__name__)

# ------------------------
# Handlers
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! لطفاً نام خود را وارد کنید:")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("خیلی خوب 🌟 حالا لطفاً ایمیل خود را وارد کنید:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = update.message.text.strip().lower()
    name = context.user_data.get("name", "").strip()

    if not is_valid_email(email_input):
        await update.message.reply_text("❌ ایمیل معتبر نیست. لطفاً دوباره وارد کنید:")
        return ASK_EMAIL

    # Save lead info
    lead = {
        "name": name,
        "email": email_input,
        "user_id": update.effective_user.id if update.effective_user else None,
        "username": update.effective_user.username if update.effective_user else None,
        "status": "Validated",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    leads = load_leads()
    leads.append(lead)
    try:
        save_leads(leads)
        print(f"💾 Saved locally: {lead}")
    except Exception as e:
        print("⚠️ Failed to save lead:", e)

    # Post to Google Sheet
    posted = post_to_sheet({
        "name": lead["name"],
        "email": lead["email"],
        "username": lead["username"] or "",
        "user_id": lead["user_id"] or "",
        "status": lead["status"],
    })

    if posted:
        await update.message.reply_text(
            f"✅ ایمیل شما ({email_input}) معتبر است و ثبت شد.\n"
            "ممنون! ممکن است بعداً با شما تماس بگیریم."
        )
    else:
        await update.message.reply_text(
            f"✅ ایمیل شما ({email_input}) معتبر است و در سیستم محلی ذخیره شد.\n"
            "اما ارسال به Google Sheet موفق نبود."
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفت‌وگو لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==========================================================
# 🧩 Build Telegram Application
# ==========================================================
application = Application.builder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
application.add_handler(conv_handler)

# ==========================================================
# 🌐 Flask Routes (Webhook)
# ==========================================================
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        if not application.ready:
            asyncio.run(application.initialize())

        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        asyncio.run(application.process_update(update))

        return "ok", 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "error", 500

@flask_app.route("/")
def index():
    return f"✅ Bot running — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

# ==========================================================
# 🚀 Startup & Webhook setup
# ==========================================================
async def set_webhook():
    webhook_url = f"{ROOT_URL}/{TOKEN}"
    try:
        await application.bot.set_webhook(webhook_url)
        print(f"✅ Webhook set to: {webhook_url}")
    except Exception as e:
        print(f"⚠️ Webhook setup failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Email Validation + Sheet Bot (Render)...")
    asyncio.run(application.initialize())  # Ensure bot is initialized once
    asyncio.run(set_webhook())             # Register webhook
    flask_app.run(host="0.0.0.0", port=PORT)
