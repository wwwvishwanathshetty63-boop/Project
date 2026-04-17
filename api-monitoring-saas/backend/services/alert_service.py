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
        
    if to_email.endswith(("@example.com", "@test.com")):
        logger.info(f"Skipping email delivery to test domain: {to_email}")
        return True

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

        if int(Config.SMTP_PORT) == 465:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
                server.send_message(msg)
        else:
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
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; padding: 20px; text-align: center; margin: 0;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; overflow: hidden; text-align: left; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <tr>
                <td style="background: linear-gradient(135deg, #7c3aed, #2563eb); background-color: #2563eb; padding: 24px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 22px;">🚨 API Alert</h1>
                    <div style="display: inline-block; background-color: {badge_color}; color: #ffffff; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: bold; margin-top: 12px;">{badge_text}</div>
                </td>
            </tr>
            <tr>
                <td style="padding: 24px;">
                    <p style="color: #e2e8f0; font-size: 15px; margin-top: 0; margin-bottom: 16px;">An issue has been detected with one of your monitored API endpoints.</p>
                    <table border="0" cellpadding="12" cellspacing="0" width="100%" style="background-color: #0f172a; border-radius: 8px; margin: 0 0 16px 0;">
                        <tr>
                            <td style="border-bottom: 1px solid #334155;">
                                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">API Name</div>
                                <div style="color: #f1f5f9; font-weight: bold; font-size: 15px; padding-top: 4px;">{api_name}</div>
                            </td>
                        </tr>
                        <tr>
                            <td style="border-bottom: 1px solid #334155;">
                                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">URL</div>
                                <div style="color: #38bdf8; font-weight: bold; font-size: 14px; padding-top: 4px; word-break: break-all;"><a href="{api_url}" style="color: #38bdf8; text-decoration: none;">{api_url}</a></div>
                            </td>
                        </tr>
                        <tr>
                            <td style="border-bottom: 1px solid #334155;">
                                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Timestamp</div>
                                <div style="color: #f1f5f9; font-size: 14px; padding-top: 4px;">{timestamp}</div>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Error Details</div>
                                <div style="color: #ef4444; font-weight: bold; font-size: 14px; padding-top: 4px;">{error_details}</div>
                            </td>
                        </tr>
                    </table>
                    <p style="color: #94a3b8; font-size: 13px; margin-bottom: 0;">Please check your dashboard for more details and take appropriate action.</p>
                </td>
            </tr>
            <tr>
                <td style="padding: 16px 24px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #334155;">
                    API Monitor SaaS &bull; Automated Alert Notification
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def send_employee_credentials_email(to_email: str, employee_name: str, password: str) -> bool:
    """Send an official email to the employee with their login credentials (Name, Email, Password)."""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping credentials email.")
        logger.info(f"[DEV] Employee credentials for {employee_name}: Email={to_email}, Password={password}")
        return False

    subject = "📡 API Monitor — Your Employee Account Credentials"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; margin: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; overflow: hidden; border: 1px solid #334155; }}
            .header {{ background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%); padding: 36px 24px; text-align: center; }}
            .header h1 {{ color: #fff; margin: 0 0 6px; font-size: 24px; font-weight: 700; }}
            .header p {{ color: rgba(255,255,255,0.85); margin-top: 8px; font-size: 14px; }}
            .body {{ padding: 36px 32px; }}
            .body p {{ font-size: 15px; line-height: 1.7; color: #cbd5e1; margin-top: 0; }}
            .creds-box {{ background: #0f172a; border: 2px solid #6366f1; border-radius: 12px; padding: 24px; margin: 24px 0; }}
            .cred-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #334155; }}
            .cred-row:last-child {{ border-bottom: none; }}
            .cred-label {{ color: #94a3b8; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
            .cred-value {{ color: #e2e8f0; font-size: 15px; font-weight: 700; font-family: 'Courier New', monospace; }}
            .warning {{ background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 14px 16px; margin-top: 20px; font-size: 13px; color: #fbbf24; }}
            .footer {{ padding: 20px 24px; text-align: center; color: #475569; font-size: 12px; border-top: 1px solid #334155; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📡 API Monitor</h1>
                <p>Official Employee Onboarding</p>
            </div>
            <div class="body">
                <p>Dear <strong>{employee_name}</strong>,</p>
                <p>Welcome to the API Monitoring team! Your employee account has been created. Please find your login credentials below. You will need all three fields to log in to the Employee Portal.</p>

                <div class="creds-box">
                    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #334155;">
                            <td style="padding: 12px 0; color: #94a3b8; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Name</td>
                            <td style="padding: 12px 0; color: #e2e8f0; font-size: 15px; font-weight: 700; text-align: right;">{employee_name}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #334155;">
                            <td style="padding: 12px 0; color: #94a3b8; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Email</td>
                            <td style="padding: 12px 0; color: #38bdf8; font-size: 15px; font-weight: 700; text-align: right;">{to_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; color: #94a3b8; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Password</td>
                            <td style="padding: 12px 0; color: #a78bfa; font-size: 16px; font-weight: 800; font-family: 'Courier New', monospace; text-align: right; letter-spacing: 1px;">{password}</td>
                        </tr>
                    </table>
                </div>

                <div class="warning">
                    ⚠️ <strong>Important:</strong> Please save these credentials securely. You will need your <strong>Name</strong>, <strong>Email</strong>, and <strong>Password</strong> to log in to the Employee Portal. We recommend changing your password after your first login.
                </div>

                <p style="margin-top: 24px; color: #94a3b8; font-size: 13px;">
                    If you did not expect this email, please contact your IT administrator immediately.
                </p>
            </div>
            <div class="footer">
                API Monitor SaaS &bull; Official Employee Credentials — Confidential
            </div>
        </div>
    </body>
    </html>
    """

    return send_alert_email(to_email, subject, body_html)


def send_daily_summary_email(to_email: str, summary_data: dict) -> bool:
    """Send a daily API monitoring summary email to HR/Admin."""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping daily summary email.")
        return False

    subject = "📊 API Monitor — Daily Summary Report"

    total_checks = summary_data.get("total_checks", 0)
    successful = summary_data.get("successful_checks", 0)
    failed = summary_data.get("failed_checks", 0)
    avg_response = summary_data.get("avg_response_time", 0)
    uptime = summary_data.get("uptime_percentage", 100)
    total_apis = summary_data.get("total_apis", 0)
    down_apis = summary_data.get("down_apis", 0)
    incidents = summary_data.get("incidents", [])
    date_str = summary_data.get("date", "Today")

    incidents_html = ""
    if incidents:
        rows = ""
        for inc in incidents[:10]:
            rows += f"""<tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #334155; color: #e2e8f0; font-size: 13px;">{inc.get('name', 'N/A')}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #334155; color: #ef4444; font-size: 13px;">{inc.get('error', 'Failed')}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #334155; color: #94a3b8; font-size: 13px;">{inc.get('time', 'N/A')}</td>
            </tr>"""
        incidents_html = f"""
        <div style="margin-top: 24px;">
            <h3 style="color: #e2e8f0; font-size: 16px; margin-bottom: 12px;">🚨 Incidents</h3>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: #0f172a; border-radius: 8px; overflow: hidden;">
                <tr style="background: #1e293b;"><th style="padding: 10px 12px; text-align: left; color: #94a3b8; font-size: 12px;">API</th><th style="padding: 10px 12px; text-align: left; color: #94a3b8; font-size: 12px;">Error</th><th style="padding: 10px 12px; text-align: left; color: #94a3b8; font-size: 12px;">Time</th></tr>
                {rows}
            </table>
        </div>"""

    uptime_color = "#10b981" if uptime >= 99 else ("#f59e0b" if uptime >= 95 else "#ef4444")

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; overflow: hidden; border: 1px solid #334155;">
            <div style="background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%); padding: 36px 24px; text-align: center;">
                <h1 style="color: #fff; margin: 0 0 6px; font-size: 22px;">📊 Daily Summary Report</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 0; font-size: 14px;">{date_str}</p>
            </div>
            <div style="padding: 32px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
                    <tr>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 33%;">
                            <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Total Checks</div>
                            <div style="color: #e2e8f0; font-size: 28px; font-weight: 800; margin-top: 4px;">{total_checks}</div>
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 33%;">
                            <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Uptime</div>
                            <div style="color: {uptime_color}; font-size: 28px; font-weight: 800; margin-top: 4px;">{uptime}%</div>
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 33%;">
                            <div style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Avg Response</div>
                            <div style="color: #38bdf8; font-size: 28px; font-weight: 800; margin-top: 4px;">{avg_response}ms</div>
                        </td>
                    </tr>
                </table>
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin-top: 16px;">
                    <tr>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 25%;">
                            <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase;">APIs</div>
                            <div style="color: #e2e8f0; font-size: 22px; font-weight: 700;">{total_apis}</div>
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 25%;">
                            <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase;">Success</div>
                            <div style="color: #10b981; font-size: 22px; font-weight: 700;">{successful}</div>
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 25%;">
                            <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase;">Failed</div>
                            <div style="color: #ef4444; font-size: 22px; font-weight: 700;">{failed}</div>
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="padding: 16px; background: #0f172a; border-radius: 8px; text-align: center; width: 25%;">
                            <div style="color: #94a3b8; font-size: 11px; text-transform: uppercase;">Down</div>
                            <div style="color: {'#ef4444' if down_apis > 0 else '#10b981'}; font-size: 22px; font-weight: 700;">{down_apis}</div>
                        </td>
                    </tr>
                </table>
                {incidents_html}
            </div>
            <div style="padding: 16px 24px; text-align: center; color: #475569; font-size: 12px; border-top: 1px solid #334155;">
                API Monitor SaaS &bull; Automated Daily Report
            </div>
        </div>
    </body>
    </html>
    """

    return send_alert_email(to_email, subject, body_html)


def send_otp_email(to_email: str, otp: str, company_name: str = "") -> bool:
    """Send a 6-digit OTP verification email for company registration."""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        # Dev mode: log the OTP so the developer can use it
        logger.warning("SMTP credentials not configured — OTP will be logged for development.")
        logger.info(f"[DEV OTP] Email: {to_email}  OTP: {otp}")
        return False

    subject = "🔐 API Monitor — Email Verification Code"

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #0f172a; color: #e2e8f0; padding: 20px; margin: 0; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #1e293b;
                          border-radius: 16px; overflow: hidden; border: 1px solid #334155; }}
            .header {{ background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%);
                       padding: 36px 24px; text-align: center; }}
            .header h1 {{ color: #fff; margin: 0 0 6px; font-size: 22px; font-weight: 700; }}
            .header p  {{ color: rgba(255,255,255,0.8); margin: 0; font-size: 14px; }}
            .body {{ padding: 36px 32px; text-align: center; }}
            .body p {{ color: #94a3b8; font-size: 15px; line-height: 1.7; margin-top: 0; }}
            .otp-box {{ background: #0f172a; border: 2px solid #7c3aed;
                        border-radius: 12px; padding: 24px 32px; margin: 28px auto;
                        display: inline-block; }}
            .otp {{ font-size: 42px; font-weight: 800; letter-spacing: 12px;
                    color: #a78bfa; font-family: 'Courier New', monospace; }}
            .expiry {{ color: #64748b; font-size: 13px; margin-top: 20px; }}
            .divider {{ border: none; border-top: 1px solid #334155; margin: 28px 0; }}
            .footer {{ padding: 20px 24px; text-align: center; color: #475569;
                       font-size: 12px; border-top: 1px solid #334155; }}
            .icon {{ font-size: 40px; margin-bottom: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="icon">📡</div>
                <h1>API Monitor</h1>
                <p>Email Verification</p>
            </div>
            <div class="body">
                <p>{"Hi <strong>" + company_name + "</strong>,<br>" if company_name else ""}
                   Use the code below to verify your email address and complete your company registration.</p>
                <div class="otp-box">
                    <div class="otp">{otp}</div>
                </div>
                <p class="expiry">⏱ This code expires in <strong>10 minutes</strong>.</p>
                <hr class="divider">
                <p style="font-size: 13px; color: #64748b;">
                    If you did not request this code, you can safely ignore this email.
                    Someone may have entered your email address by mistake.
                </p>
            </div>
            <div class="footer">
                API Monitor SaaS &bull; Secure Company Registration
            </div>
        </div>
    </body>
    </html>
    """

    return send_alert_email(to_email, subject, body_html)

