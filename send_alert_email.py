import env_loader
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")
EMAIL_FROM = os.environ.get("EMAIL_FROM")

def send_alert():
    print(f"Sending expiration alert to {TO_EMAIL}...")
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = TO_EMAIL
    msg['Subject'] = "⚠️ URGENT: WhatsApp Automation Session Expired"
    
    body = """Hi Satya,

The WhatsApp automated reporting session has expired.

Please log into the automation server and run:
    node setup_whatsapp_session.js

Scan the QR code to re-authenticate so that the automated WhatsApp reports can resume sending.

Thanks,
Automations Central
"""
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Alert email sent successfully!")
        sys.exit(0)
    except Exception as err:
        print(f"Failed to send email: {err}")
        sys.exit(1)

if __name__ == "__main__":
    send_alert()
