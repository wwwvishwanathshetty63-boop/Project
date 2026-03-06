import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.config import Config

logger = logging.getLogger(__name__)


def send_alert_email(to_email: str, subject: str, body_html: str) -> bool:
    """Send an alert email via SMTP."""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping email alert.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{Config.SMTP_FROM_NAME} <{Config.SMTP_FROM_EMAIL or Config.SMTP_USERNAME}>"
        msg["To"] = to_email

        # Plain text fallback
        plain_text = body_html.replace("<br>", "\n").replace("</p>", "\n")
        import re

        plain_text = re.sub(r"<[^>]+>", "", plain_text)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Alert email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send alert email to {to_email}: {e}")
        return False


def build_alert_html(
    api_name: str,
    api_url: str,
    timestamp: str,
    error_details: str,
    alert_type: str = "failure",
) -> str:
    """Build HTML email body for an alert notification."""

    if alert_type == "consecutive_failures":
        badge_color = "#dc2626"
        badge_text = "CRITICAL — 3 Consecutive Failures"
    elif alert_type == "timeout":
        badge_color = "#f59e0b"
        badge_text = "TIMEOUT"
    else:
        badge_color = "#ef4444"
        badge_text = "FAILURE"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #7c3aed, #2563eb); padding: 24px; text-align: center; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 22px; }}
            .badge {{ display: inline-block; background: {badge_color}; color: #fff; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-top: 12px; }}
            .body {{ padding: 24px; }}
            .detail {{ background: #0f172a; border-radius: 8px; padding: 16px; margin: 12px 0; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #334155; }}
            .detail-row:last-child {{ border-bottom: none; }}
            .label {{ color: #94a3b8; font-size: 13px; }}
            .value {{ color: #f1f5f9; font-weight: 600; font-size: 14px; }}
            .footer {{ padding: 16px 24px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #334155; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚨 API Alert</h1>
                <div class="badge">{badge_text}</div>
            </div>
            <div class="body">
                <p>An issue has been detected with one of your monitored API endpoints.</p>
                <div class="detail">
                    <div class="detail-row">
                        <span class="label">API Name</span>
                        <span class="value">{api_name}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">URL</span>
                        <span class="value">{api_url}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Timestamp</span>
                        <span class="value">{timestamp}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Error Details</span>
                        <span class="value">{error_details}</span>
                    </div>
                </div>
                <p style="color: #94a3b8; font-size: 13px;">Please check your dashboard for more details and take appropriate action.</p>
            </div>
            <div class="footer">
                API Monitor SaaS &bull; Automated Alert Notification
            </div>
        </div>
    </body>
    </html>
    """


def send_invitation_email(to_email: str, employee_name: str, token: str) -> bool:
    """Send an employee invitation email with a verification link."""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping invitation email.")
        logger.info(f"[DEV] Invitation link for {employee_name}: http://localhost:5000/verify-employee.html?token={token}")
        return False

    subject = "📡 API Monitor — You've Been Invited!"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #6366f1, #06b6d4); padding: 32px; text-align: center; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 24px; }}
            .header p {{ color: rgba(255,255,255,0.85); margin-top: 8px; font-size: 14px; }}
            .body {{ padding: 32px; }}
            .body p {{ font-size: 15px; line-height: 1.7; color: #cbd5e1; }}
            .cta {{ display: inline-block; background: linear-gradient(135deg, #6366f1, #06b6d4); color: #fff; padding: 14px 36px; border-radius: 8px; font-size: 16px; font-weight: 600; text-decoration: none; margin: 24px 0; }}
            .note {{ background: #0f172a; border-radius: 8px; padding: 16px; margin-top: 20px; font-size: 13px; color: #94a3b8; }}
            .footer {{ padding: 16px 24px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #334155; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📡 API Monitor</h1>
                <p>Employee Invitation</p>
            </div>
            <div class="body">
                <p>Hi <strong>{employee_name}</strong>,</p>
                <p>You've been invited to join the API Monitor dashboard as an employee. Click the button below to verify your account and get your login credentials.</p>
                <div style="text-align: center;">
                    <a href="http://localhost:5000/verify-employee.html?token={token}" class="cta">✅ Verify & Get Credentials</a>
                </div>
                <div class="note">
                    <strong>⚠️ Important:</strong> This link can only be used once. After verification, you'll receive a unique Employee ID and password to log in.
                </div>
            </div>
            <div class="footer">
                API Monitor SaaS &bull; Secure Employee Onboarding
            </div>
        </div>
    </body>
    </html>
    """

    return send_alert_email(to_email, subject, body_html)
