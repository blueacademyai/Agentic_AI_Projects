import os
import smtplib
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from jinja2 import Template
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv   # <-- add this

# Load .env automatically
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class EmailService:
    def __init__(self):
        """Initialize Email Service"""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_username = os.getenv("EMAIL_USERNAME")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.email_username)
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Email templates
        self.templates = {
            "verification": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Welcome to AI Payment System</h1>
                </div>
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2>Hello {{name}},</h2>
                    <p>Thank you for registering with our AI-powered payment system. Please verify your email address to complete your account setup.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{verification_link}}" style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify Email Address</a>
                    </div>
                    <p><strong>Security Note:</strong> This link will expire in 24 hours for your security.</p>
                    <p>If you didn't create this account, please ignore this email.</p>
                </div>
                <div style="background: #333; color: white; padding: 20px; text-align: center; font-size: 12px;">
                    <p>AI Payment System | Secure • Fast • Intelligent</p>
                </div>
            </body>
            </html>
            """,
            
            "welcome": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Welcome to AI Payment System!</h1>
                </div>
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2>Hello {{name}},</h2>
                    <p>Your email has been verified successfully! You now have full access to our AI-powered payment system.</p>
                    
                    <h3>🚀 Getting Started:</h3>
                    <ul style="line-height: 1.8;">
                        <li>Make secure payments with AI validation</li>
                        <li>Chat with our AI assistant for help</li>
                        <li>Monitor transactions in real-time</li>
                        <li>Access 24/7 customer support</li>
                    </ul>
                    
                    <div style="background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="margin-top: 0;">🛡️ Security Features:</h4>
                        <p>Your payments are protected by advanced AI fraud detection, end-to-end encryption, and real-time monitoring.</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{dashboard_link}}" style="background: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Access Dashboard</a>
                    </div>
                </div>
                <div style="background: #333; color: white; padding: 20px; text-align: center; font-size: 12px;">
                    <p>AI Payment System | Secure • Fast • Intelligent</p>
                </div>
            </body>
            </html>
            """,
            
            "payment_notification": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Payment {{status_title}}</h1>
                </div>
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2>Hello {{name}},</h2>
                    <p>Your payment has been {{status_message}}.</p>
                    
                    <div style="background: white; padding: 20px; border-radius: 5px; border-left: 4px solid {{status_color}};">
                        <h3 style="margin-top: 0;">Transaction Details:</h3>
                        <p><strong>Transaction ID:</strong> {{transaction_id}}</p>
                        <p><strong>Amount:</strong> ${{amount}} {{currency}}</p>
                        <p><strong>Status:</strong> {{status}}</p>
                        <p><strong>Date:</strong> {{date}}</p>
                        {% if description %}
                        <p><strong>Description:</strong> {{description}}</p>
                        {% endif %}
                    </div>
                    
                    {% if status == 'success' %}
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #4CAF50;"><strong>✅ Payment Completed Successfully</strong></p>
                    </div>
                    {% elif status == 'pending' %}
                    <div style="background: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #FF9800;"><strong>⏳ Payment Processing</strong></p>
                        <p style="margin: 10px 0 0 0;">Expected completion: {{estimated_time}}</p>
                    </div>
                    {% elif status == 'failed' %}
                    <div style="background: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0; color: #f44336;"><strong>❌ Payment Failed</strong></p>
                        <p style="margin: 10px 0 0 0;">Please contact support if you need assistance.</p>
                    </div>
                    {% endif %}
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{transaction_link}}" style="background: #2196F3; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">View Transaction</a>
                    </div>
                </div>
                <div style="background: #333; color: white; padding: 20px; text-align: center; font-size: 12px;">
                    <p>AI Payment System | Secure • Fast • Intelligent</p>
                </div>
            </body>
            </html>
            """,
            
            "admin_message": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #9C27B0 0%, #673AB7 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Message from Support Team</h1>
                </div>
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2>Hello {{name}},</h2>
                    <p>You have received a message from our support team:</p>
                    
                    <div style="background: white; padding: 20px; border-radius: 5px; border-left: 4px solid #9C27B0;">
                        <h3 style="margin-top: 0;">{{subject}}</h3>
                        <div style="line-height: 1.6;">{{content}}</div>
                        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
                        <p style="margin: 0; color: #666; font-size: 12px;">From: {{sender_name}}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{reply_link}}" style="background: #9C27B0; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reply</a>
                    </div>
                </div>
                <div style="background: #333; color: white; padding: 20px; text-align: center; font-size: 12px;">
                    <p>AI Payment System | Secure • Fast • Intelligent</p>
                </div>
            </body>
            </html>
            """
        }
    
    def _send_email_sync(self, to_email: str, subject: str, html_content: str, 
                        attachments: Optional[List[Dict]] = None) -> bool:
        """Send email synchronously"""
        try:
            if not self.email_username or not self.email_password:
                logger.error("Email credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    with open(attachment['path'], 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {attachment["filename"]}'
                        )
                        msg.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_username, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_email(self, to_email: str, subject: str, html_content: str,
                        attachments: Optional[List[Dict]] = None) -> bool:
        """Send email asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self._send_email_sync, 
            to_email, 
            subject, 
            html_content, 
            attachments
        )
    
    def render_template(self, template_name: str, **kwargs) -> str:
        """Render email template with provided data"""
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
        
        template = Template(self.templates[template_name])
        return template.render(**kwargs)

# Initialize global email service
email_service = EmailService()

# Convenience functions
async def send_verification_email(email: str, name: str, verification_token: str):
    """Send email verification email"""
    verification_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:8501')}/verify?token={verification_token}"
    
    html_content = email_service.render_template(
        'verification',
        name=name,
        verification_link=verification_link
    )
    
    return await email_service.send_email(
        to_email=email,
        subject="Verify Your Email - AI Payment System",
        html_content=html_content
    )

async def send_welcome_email(email: str, name: str):
    """Send welcome email after verification"""
    dashboard_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:8501')}/dashboard"
    
    html_content = email_service.render_template(
        'welcome',
        name=name,
        dashboard_link=dashboard_link
    )
    
    return await email_service.send_email(
        to_email=email,
        subject="Welcome to AI Payment System!",
        html_content=html_content
    )

async def send_payment_notification(name: str, transaction):
    """Send payment notification email to the recipient"""
    from datetime import datetime

    # Determine status details
    status_details = {
        'success': {
            'title': 'Completed',
            'message': 'processed successfully',
            'color': '#4CAF50'
        },
        'pending': {
            'title': 'Processing',
            'message': 'received and is being processed',
            'color': '#FF9800'
        },
        'failed': {
            'title': 'Failed',
            'message': 'could not be processed',
            'color': '#f44336'
        }
    }

    status_info = status_details.get(transaction.status, status_details['pending'])
    transaction_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:8501')}/transaction/{transaction.transaction_id}"

    html_content = email_service.render_template(
        'payment_notification',
        name=name,
        transaction_id=transaction.transaction_id,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        status_title=status_info['title'],
        status_message=status_info['message'],
        status_color=status_info['color'],
        description=transaction.description,
        date=transaction.created_at.strftime("%B %d, %Y at %I:%M %p"),
        estimated_time="2-5 minutes" if transaction.status == 'pending' else None,
        transaction_link=transaction_link
    )
    # ✅ Extract recipient email from transaction.recipient_info
    recipient_email = None
    if transaction.recipient_info and isinstance(transaction.recipient_info, dict):
        recipient_email = transaction.recipient_info.get("email")

    if not recipient_email:
        logger.error(f"Missing recipient email for transaction {transaction.transaction_id}")
        return False

    return await email_service.send_email(
        to_email=recipient_email,   # ✅ always send to recipient
        subject=f"Payment {status_info['title']} - ${transaction.amount}",
        html_content=html_content
    )


async def send_admin_message(user_email: str, name: str, subject: str, content: str, sender_name: str):
    """Send admin message to a user"""
    reply_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:8501')}/messages"

    html_content = email_service.render_template(
        'admin_message',
        name=name,
        subject=subject,
        content=content.replace('\n', '<br>'),
        sender_name=sender_name,
        reply_link=reply_link
    )

    return await email_service.send_email(
        to_email=user_email,   # ✅ goes to the user
        subject=f"Message from Support: {subject}",
        html_content=html_content
    )


async def send_security_alert(email: str, name: str, alert_type: str, details: Dict[str, Any]):
    """Send security alert email"""
    alerts = {
        'login_attempt': {
            'title': 'New Login Detected',
            'message': f"A new login was detected from {details.get('location', 'Unknown location')} at {details.get('time', 'Unknown time')}."
        },
        'password_change': {
            'title': 'Password Changed',
            'message': f"Your password was changed on {details.get('time', 'Unknown time')}."
        },
        'suspicious_activity': {
            'title': 'Suspicious Activity Detected',
            'message': f"Suspicious activity was detected on your account: {details.get('description', 'Unknown activity')}."
        }
    }
    
    alert_info = alerts.get(alert_type, alerts['suspicious_activity'])
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #f44336; padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">🔒 Security Alert</h1>
        </div>
        <div style="padding: 30px; background: #f9f9f9;">
            <h2>Hello {name},</h2>
            <div style="background: #ffebee; padding: 20px; border-radius: 5px; border-left: 4px solid #f44336;">
                <h3 style="margin-top: 0; color: #f44336;">{alert_info['title']}</h3>
                <p>{alert_info['message']}</p>
            </div>
            <p>If this was not you, please contact our support team immediately and consider changing your password.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{os.getenv('FRONTEND_URL', 'http://localhost:8501')}/security" style="background: #f44336; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Review Security Settings</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return await email_service.send_email(
        to_email=email,
        subject=f"Security Alert: {alert_info['title']}",
        html_content=html_content
    )

# ---- Safe Sync wrappers for BackgroundTasks ----
def _run_async_task(coro):
    """Run async task safely from sync context (like BackgroundTasks)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop → safe to use asyncio.run
        return asyncio.run(coro)
    else:
        # Already inside an event loop → schedule the task
        return loop.create_task(coro)

def send_verification_email_sync(email: str, name: str, verification_token: str):
    return _run_async_task(send_verification_email(email, name, verification_token))

def send_welcome_email_sync(email: str, name: str):
    return _run_async_task(send_welcome_email(email, name))

def send_payment_notification_sync(name: str, transaction):
    return _run_async_task(send_payment_notification(name, transaction))

def send_admin_message_sync(email: str, name: str, subject: str, content: str, sender_name: str):
    return _run_async_task(send_admin_message(email, name, subject, content, sender_name))

def send_security_alert_sync(email: str, name: str, alert_type: str, details: Dict[str, Any]):
    return _run_async_task(send_security_alert(email, name, alert_type, details))
