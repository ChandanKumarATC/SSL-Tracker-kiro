import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_FROM_EMAIL, ALERT_TO_EMAIL

logger = logging.getLogger(__name__)


def send_email(subject: str, body_html: str, to_email: str = None) -> bool:
    """
    Send an HTML email via SMTP.
    Returns True on success, False on failure.
    """
    recipient = to_email or ALERT_TO_EMAIL
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ALERT_FROM_EMAIL
    msg["To"] = recipient
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(ALERT_FROM_EMAIL, recipient, msg.as_string())
        logger.info("Email sent to %s: %s", recipient, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD.")
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending email: %s", e)
    except Exception as e:
        logger.error("Unexpected error sending email: %s", e)

    return False


def send_ssl_alert(domain_name: str, expiry_date: datetime, days_left: int) -> bool:
    """Send SSL certificate expiry alert."""
    subject = f"⚠️ SSL Certificate Expiring Soon: {domain_name}"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #e67e22;">SSL Certificate Expiry Alert</h2>
        <p>The SSL certificate for <strong>{domain_name}</strong> is expiring soon.</p>
        <table style="border-collapse: collapse; width: 400px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Domain</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{domain_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Expiry Date</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{expiry_date.strftime('%Y-%m-%d') if expiry_date else 'Unknown'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Days Remaining</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; color: #e67e22;"><strong>{days_left} days</strong></td>
            </tr>
        </table>
        <p style="margin-top: 20px;">Please renew your SSL certificate as soon as possible.</p>
        <hr/>
        <small style="color: #999;">Domain & SSL Expiry Tracker</small>
    </body></html>
    """
    return send_email(subject, body)


def send_domain_alert(domain_name: str, expiry_date: datetime, days_left: int) -> bool:
    """Send domain registration expiry alert."""
    subject = f"⚠️ Domain Expiring Soon: {domain_name}"
    body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #c0392b;">Domain Expiry Alert</h2>
        <p>The domain registration for <strong>{domain_name}</strong> is expiring soon.</p>
        <table style="border-collapse: collapse; width: 400px;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Domain</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{domain_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Expiry Date</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{expiry_date.strftime('%Y-%m-%d') if expiry_date else 'Unknown'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Days Remaining</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; color: #c0392b;"><strong>{days_left} days</strong></td>
            </tr>
        </table>
        <p style="margin-top: 20px;">Please renew your domain registration to avoid service interruption.</p>
        <hr/>
        <small style="color: #999;">Domain & SSL Expiry Tracker</small>
    </body></html>
    """
    return send_email(subject, body)
