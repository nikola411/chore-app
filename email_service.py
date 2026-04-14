import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _build_html(user_name: str, chores: list[dict], app_url: str) -> str:
    chore_rows = ""
    for c in chores:
        desc = f'<p style="color:#666;margin:4px 0 0 0;font-size:14px;">{c["description"]}</p>' if c.get("description") else ""
        chore_rows += f"""
        <div style="background:white;padding:14px 16px;border-radius:8px;
                    border-left:4px solid #667eea;margin:10px 0;">
            <h3 style="margin:0;color:#333;font-size:16px;">{c["name"]}</h3>
            {desc}
        </div>"""

    plural = "chores" if len(chores) > 1 else "chore"
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                  padding:20px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;margin:0;">ChoreBoard</h1>
      </div>
      <div style="background:#f8f9fa;padding:24px;border-radius:0 0 12px 12px;
                  border:1px solid #dee2e6;">
        <h2 style="color:#333;margin-top:0;">Hi {user_name}!</h2>
        <p style="color:#555;font-size:15px;">
          You have {len(chores)} {plural} due today:
        </p>
        {chore_rows}
        <br>
        <a href="{app_url}"
           style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                  color:white;padding:12px 24px;text-decoration:none;
                  border-radius:6px;font-weight:bold;">
          Open Dashboard
        </a>
        <p style="color:#aaa;font-size:12px;margin-top:24px;">
          You received this because you are a member of ChoreBoard.
        </p>
      </div>
    </body>
    </html>"""


def send_reminders(user_email: str, user_name: str, chores: list[dict], app_url: str) -> None:
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    email_from = os.environ.get('EMAIL_FROM', smtp_user) or smtp_user

    if not smtp_user or not smtp_password:
        print(f"[email] SMTP not configured — skipping reminder for {user_email}")
        return

    plural = "chores" if len(chores) > 1 else "chore"
    subject = f"Reminder: {len(chores)} {plural} due today"
    if len(chores) == 1:
        subject = f"Reminder: \"{chores[0]['name']}\" is due today"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email_from
    msg['To'] = user_email
    msg.attach(MIMEText(_build_html(user_name, chores, app_url), 'html'))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(email_from, user_email, msg.as_string())

    print(f"[email] Sent reminder to {user_email} ({len(chores)} chore(s))")
