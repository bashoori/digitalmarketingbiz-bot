import os
import json
import re
import smtplib
import imaplib
import email
import asyncio
import requests
from email.message import EmailMessage
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv

# ========== Load environment variables ==========
load_dotenv()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TOKEN = os.getenv("TELEGRAM_TOKEN")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
WELCOME_LINK = os.getenv("WELCOME_LINK")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # optional for Render webhook

DATA_FILE = "leads.json"
PDF_PATH = "docs/franchise_intro.pdf"

# ========== Helper Functions ==========
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def normalize_email(raw: str) -> str:
    return raw.replace("\u200c", "").replace("\u200f", "").strip().lower()

def is_valid_email(email_str: str) -> bool:
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email_str) is not None

def post_to_sheet(payload: dict, note: str = "") -> None:
    """Best-effort POST to Google Apps Script Web App with logs."""
    if not GOOGLE_SHEET_URL:
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL not set")
        return
    try:
        print(f"📤 Sending to Google Sheet: {payload}")
        resp = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=20)
        print(f"📊 Response {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print("❌ Failed to send to Google Sheet:", e)

# ========== Email Senders ==========
def send_email(subject, body, recipient):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Email error:", e)
        return False

def send_verification_email(name, email):
    return send_email(
        "Digital Marketing Business — Email Verification",
        f"Hello {name},\n\n"
        "This is a verification email from Digital Marketing Business.\n"
        "If you received this, your email is working.\n\n"
        "Thanks,\nDigital Marketing Team",
        email,
    )

def send_followup_email(name, email, link):
    link = link or "https://example.com/start"
    return send_email(
        "Welcome to Digital Marketing Business!",
        f"Hi {name},\n\n"
        f"Your email has been verified successfully! 🎉\n"
        f"Start your training here: {link}\n\n"
        "— Digital Marketing Business Team",
        email,
    )

# ========== Telegram Conversation ==========
ASK_NAME, ASK_EMAIL = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Digital Marketing Business*!\n\n"
        "Please enter your full name:",
        parse_mode="Markdown",
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Great! Now please enter your email address:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = normalize_email(update.message.text)
    name = context.user_data.get("name")

    if not is_valid_email(email_input):
        await update.message.reply_text("❌ Invalid email. Try again:")
        return ASK_EMAIL

    leads = load_data()
    record = {"name": name, "email": email_input, "status": "Pending"}
    leads.append(record)
    save_data(leads)
    post_to_sheet(record, note="create")

    await update.message.reply_text(f"📧 Sending verification email to {email_input}...")
    sent = send_verification_email(name, email_input)
    if not sent:
        await update.message.reply_text("⚠️ Email sending failed. Try later.")
        return ConversationHandler.END

    await asyncio.sleep(15)
    record["status"] = "Verified"
    save_data(leads)
    post_to_sheet(record, note="update")

    await update.message.reply_text("✅ Email verified! Sending materials...")
    if os.path.exists(PDF_PATH):
        with open(PDF_PATH, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="Franchise_Intro.pdf",
                caption="📘 Franchise Introduction PDF",
            )

    send_followup_email(name, email_input, WELCOME_LINK)
    await update.message.reply_text("📨 Follow-up email sent. Check your inbox!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Conversation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ========== Main ==========
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)

    print("🤖 Bot is running...")

    # Detect if running on Render or local
    if os.getenv("RENDER") or os.getenv("PORT"):
        port = int(os.environ.get("PORT", 8080))
        url = WEBHOOK_URL or f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
        app.run_webhook(listen="0.0.0.0", port=port, url_path=TOKEN, webhook_url=url)
        print(f"🌐 Running webhook at {url}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
