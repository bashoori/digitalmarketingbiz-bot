import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

def send_welcome_email(name, to_email):
    subject = "Welcome to Digital Marketing Business 🎉"
    body = f"""
    Hello {name},

    Welcome aboard! 🌟
    We're excited to have you join our Digital Marketing Business community.

    If you don't see this email in your Inbox, please check your Spam folder and mark it as 'Not Spam' to stay connected.

    — Digital Marketing Business Team
    """

    msg = MIMEText(body)
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        # Connect to Gmail SMTP server (SSL)
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Sent email to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
