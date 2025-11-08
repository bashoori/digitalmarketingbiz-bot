import os
import re
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from authorize_gmail import send_welcome_email
from dotenv import load_dotenv

# ========== Load environment variables ==========
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ========== States ==========
ASK_NAME, ASK_EMAIL = range(2)

# ========== Helper functions ==========
def is_valid_email(email_str: str) -> bool:
    """Check if email matches a valid pattern."""
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email_str) is not None

# ========== Handlers ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! لطفاً نام خود را وارد کنید:")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text("خیلی هم عالی 🌟 حالا لطفاً ایمیل خود را وارد کنید:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = update.message.text.strip()
    name = context.user_data.get("name")

    # === validate email ===
    if not is_valid_email(email_input):
        await update.message.reply_text("❌ ایمیل معتبر نیست. لطفاً دوباره وارد کنید:")
        return ASK_EMAIL

    await update.message.reply_text(
        f"✅ ایمیل شما ({email_input}) معتبر است.\n"
        "در حال ارسال ایمیل خوش‌آمدگویی هستم..."
    )

    try:
        sent = send_welcome_email(name, email_input)
        await asyncio.sleep(2)

        if sent:
            await update.message.reply_text(
                "📬 ایمیل خوش‌آمدگویی برای شما ارسال شد!\n"
                "اگر در Inbox نبود، لطفاً پوشه‌ی Spam را هم بررسی کنید."
            )
        else:
            await update.message.reply_text(
                "⚠️ مشکلی در ارسال ایمیل پیش آمد. لطفاً بعداً امتحان کنید."
            )

    except Exception as e:
        print(f"❌ Email sending error: {e}")
        await update.message.reply_text(
            "⚠️ مشکلی در ارسال ایمیل پیش آمد. لطفاً بعداً امتحان کنید."
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفت‌وگو لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ========== Main ==========
def main():
    """Start the Telegram bot."""
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

    print("🤖 Bot is running and waiting for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
