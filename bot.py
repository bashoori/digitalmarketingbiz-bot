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
    if not GOOGLE_SHEET_URL or not GOOGLE_SHEET_URL.startswith("https://script.google.com/macros/"):
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL is missing or invalid. Expect a 401/404 if you POST to a docs URL.")
        return
    try:
        print(f"📤 Sending data to Google Sheet{(' ['+note+']') if note else ''}: {payload}")
        resp = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=20)
        print(f"📊 Google Sheet response code: {resp.status_code}")
        print(f"📄 Google Sheet response text: {resp.text[:500]}")
    except Exception as e:
        print(f"❌ Failed to send to Google Sheet: {e}")

# ========== Email Senders ==========
def send_verification_email(name, recipient_email):
    msg = EmailMessage()
    msg["Subject"] = "Digital Marketing Business — Email Verification"
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    msg.set_content(
        f"Hello {name},\n\n"
        "This is a verification email from Digital Marketing Business.\n"
        "If you received this, your email address is working.\n\n"
        "Thanks,\nDigital Marketing Business Team"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Verification email sent to {recipient_email}")
        return True
    except Exception as e:
        print("Error sending verification email:", e)
        return False

def send_followup_email(name, recipient_email, welcome_link):
    msg = EmailMessage()
    msg["Subject"] = "Welcome to Digital Marketing Business — Start Here!"
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    link = welcome_link or "https://example.com/start"
    msg.set_content(
        f"Hello {name},\n\n"
        "Your email has been verified successfully 🎉\n"
        f"Start your training here: {link}\n\n"
        "• Learn how digital marketing franchises work\n"
        "• Attract your first clients online\n"
        "• Scale with automation\n\n"
        "— Digital Marketing Business Team"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"📨 Follow-up email sent to {recipient_email}")
        return True
    except Exception as e:
        print("❌ Error sending follow-up:", e)
        return False

# ========== Gmail Bounce Checker ==========
def check_bounce_messages(target_email):
    """Look for recent bounce notifications for target_email."""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SMTP_EMAIL, SMTP_PASSWORD)
        mail.select("inbox")
        # Narrow search; adjust SINCE if needed
        result, data = mail.search(None, '(FROM "mailer-daemon@googlemail.com")')
        if result != "OK":
            return False
        # Check the last ~10 messages only
        for num in data[0].split()[-10:]:
            result, msg_data = mail.fetch(num, "(RFC822)")
            if result != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body += part.get_payload(decode=True).decode(errors="ignore")
                        except Exception:
                            continue
            else:
                try:
                    body += msg.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    pass

            body_lower = body.lower()
            if target_email.lower() in body_lower and any(
                p in body_lower for p in [
                    "address not found", "no such user", "user unknown",
                    "does not exist", "550 5.1.1"
                ]
            ):
                print(f"🚨 Bounce detected for {target_email}")
                return True
        return False
    except Exception as e:
        print("Error checking Gmail:", e)
        return False

# ========== Conversation States ==========
ASK_NAME, ASK_EMAIL = range(2)

# ========== Telegram Bot Logic ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 سلام! خوش آمدید به دنیای **دیجیتال مارکتینگ حرفه‌ای**.\n\n"
        "ما یک فرانچایز بیزنس آنلاین در زمینه آموزش دیجیتال مارکتینگ ارائه می‌دهیم که "
        "با آن می‌توانید مهارت‌ها را یاد بگیرید و درآمد آنلاین بسازید. 💼💻\n\n"
        "اگر دوست دارید توضیحات اولیه را برای شما ارسال کنیم، لطفاً نام خود را وارد کنید:"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("خیلی خوب 🌟 حالا لطفاً ایمیل خود را وارد کنید:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = normalize_email(update.message.text)
    name = context.user_data.get("name")

    if not is_valid_email(email_input):
        await update.message.reply_text("❌ ایمیل معتبر نیست. لطفاً مثل example@gmail.com وارد کنید:")
        return ASK_EMAIL

    # Save locally
    leads = load_data()
    lead_record = {
        "name": name,
        "email": email_input,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "status": "Pending",
    }
    leads.append(lead_record)
    save_data(leads)

    # === Notify admin ===
    try:
        if ADMIN_CHAT_ID:
            admin_message = (
                f"📥 *New Lead Registered!*\n"
                f"👤 Name: {name}\n"
                f"📧 Email: {email_input}\n"
                f"🆔 User ID: {update.effective_user.id}\n"
                f"🕒 Status: Pending"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_message,
                parse_mode="Markdown"
            )
            print(f"📬 Notified admin ({ADMIN_CHAT_ID}) about new lead.")
    except Exception as e:
        print(f"⚠️ Failed to notify admin: {e}")


    # Save to Google Sheet (Pending)
    payload = {
        "name": name,
        "email": email_input,
        "username": update.effective_user.username or "",
        "user_id": update.effective_user.id,
        "status": "Pending",
    }
    post_to_sheet(payload, note="create")

    await update.message.reply_text(
        f"📧 در حال بررسی ایمیل ({email_input}) هستم، لطفاً صبر کنید...\n"
        "اگر ایمیل را دریافت نکردید، پوشهٔ *Inbox* یا *Spam* را هم بررسی کنید و روی **Not Spam** بزنید.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )

    # Send verification email
    sent = send_verification_email(name, email_input)
    if not sent:
        await update.message.reply_text("⚠️ ارسال ایمیل ناموفق بود. لطفاً بعداً دوباره امتحان کنید.")
        return ConversationHandler.END

    # Wait then check bounce
    await asyncio.sleep(60)
    bounced = check_bounce_messages(email_input)

    # Update local status
    for lead in leads:
        if lead["email"] == email_input:
            lead["status"] = "Invalid" if bounced else "Verified"
            break
    save_data(leads)

    # Update Google Sheet status
    payload["status"] = "Invalid" if bounced else "Verified"
    post_to_sheet(payload, note="status_update")

    if bounced:
        await update.message.reply_text(
            "❌ متأسفانه ایمیلی که وارد کردید وجود ندارد یا در دسترس نیست.\n"
            "لطفاً ایمیل صحیح خود را دوباره وارد کنید:"
        )
        return ASK_EMAIL

    # Verified: send PDF (if exists)
    await update.message.reply_text("✅ ایمیل شما تأیید شد! در حال ارسال فایل آموزشی هستم...")
    if os.path.exists(PDF_PATH) and os.path.getsize(PDF_PATH) > 0:
        try:
            with open(PDF_PATH, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="Franchise_Intro.pdf",
                    caption="📘 فایل معرفی فرانچایز دیجیتال مارکتینگ 👇",
                )
        except Exception as e:
            print(f"⚠️ Could not send PDF: {e}")
            await update.message.reply_text("⚠️ فایل معرفی در حال حاضر در دسترس نیست.")
    else:
        await update.message.reply_text("⚠️ فایل معرفی در حال حاضر در دسترس نیست.")

    # Follow-up email with training link
    await update.message.reply_text("📬 ارسال ایمیل آموزشی برای شما در حال انجام است...")
    follow_sent = send_followup_email(name, email_input, WELCOME_LINK)
    if follow_sent:
        await update.message.reply_text(
            "✅ ایمیل آموزشی برای شما ارسال شد! 💌  لطفاً پوشهٔ اینباکس (Inbox) یا اسپم (Spam) را بررسی کنید."
        )
    else:
        await update.message.reply_text("⚠️ ارسال ایمیل آموزشی ناموفق بود، اما ثبت شما تکمیل شد.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفت‌وگو لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ========== Main ==========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("🤖 Digital Marketing Business Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    import os
    main()