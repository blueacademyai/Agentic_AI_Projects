import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Dict, List, Optional, Any
import warnings
warnings.filterwarnings('ignore')
import ssl
import logging
import tempfile
from email.mime.base import MIMEBase
from email import encoders


# Import your config
from config import settings, FeatureFlags

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnerVisionNotificationSystem:
    def __init__(self):
        # Use settings from config.py instead of direct os.getenv
        self.smtp_host = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        
        # Validate configuration on initialization
        self.config_valid = self.validate_config()
        
        # Email templates
        self.templates = {
            'work_order': self.get_work_order_template(),
            'anomaly_alert': self.get_anomaly_alert_template(),
            'energy_report': self.get_energy_report_template(),
            'optimization_alert': self.get_optimization_template()
        }
    
    def validate_config(self) -> bool:
        """Validate SMTP configuration"""
        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured")
            return False
        
        if not self.smtp_host or not self.smtp_port:
            logger.warning("SMTP host/port not configured")
            return False
        
        return True
    
    def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection without sending email"""
        if not self.config_valid:
            return {
                'success': False,
                'error': 'SMTP credentials not properly configured. Check your environment variables.',
                'details': 'Please set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD in your .env file'
            }
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Test connection
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
            
            return {
                'success': True,
                'message': f'Successfully connected to {self.smtp_host}:{self.smtp_port}'
            }
            
        except smtplib.SMTPAuthenticationError:
            return {
                'success': False,
                'error': 'Authentication failed. Check your username and password/app password.',
                'details': 'For Gmail, use App Password instead of regular password'
            }
        except smtplib.SMTPConnectError:
            return {
                'success': False,
                'error': f'Cannot connect to SMTP server {self.smtp_host}:{self.smtp_port}',
                'details': 'Check your internet connection and firewall settings'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}',
                'details': 'Check all SMTP settings and network connectivity'
            }
    
    def send_email(self, recipient: str, subject: str, content: str,
                   template_type: str = None, attachments: List[str] = None) -> Dict[str, Any]:
        """Send email notification with detailed error reporting"""
        if not self.config_valid:
            return {
                'success': False,
                'error': 'SMTP configuration is invalid',
                'details': 'Missing or invalid SMTP settings'
            }
        
        # Validate email format
        if '@' not in recipient or '.' not in recipient:
            return {
                'success': False,
                'error': 'Invalid email format',
                'details': f'"{recipient}" does not appear to be a valid email address'
            }
        
        try:
            context = ssl.create_default_context()
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = recipient
            msg['Subject'] = subject
            
            if template_type and template_type in self.templates:
                html_content = self.templates[template_type].format(content=content)
                msg.attach(MIMEText(html_content, 'html'))
            else:
                msg.attach(MIMEText(content, 'plain'))
            
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        self.add_attachment(msg, attachment_path)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient}")
            return {
                'success': True,
                'message': f'Email sent successfully to {recipient}'
            }
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication error: {e}")
            return {
                'success': False,
                'error': 'Authentication failed',
                'details': 'Check your username and app password. For Gmail, ensure you are using a 16-character app password.'
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                'success': False,
                'error': 'Email sending failed',
                'details': str(e)
            }
    
    def add_attachment(self, msg: MIMEMultipart, file_path: str):
        """Add attachment to email message"""
        try:
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(file_path)}'
            )
            msg.attach(part)
            
        except Exception as e:
            logger.error(f"Error adding attachment: {e}")
    
    def send_work_order_notification(self, work_order: Dict, recipient: str) -> Dict[str, Any]:
        """Send work order notification"""
        subject = f"⚡ EnerVision Work Order #{work_order['id']} - {work_order['priority']} Priority"
        
        priority_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        
        content = f"""
        A new work order has been created in EnerVision:
        
        📋 WORK ORDER DETAILS:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Work Order ID: {work_order['id']}
        Title: {work_order['title']}
        Priority: {priority_emoji.get(work_order['priority'], '⚪')} {work_order['priority']}
        Branch: {work_order['branch']}
        Category: {work_order['category']}
        Due Date: {work_order['due_date']}
        Estimated Hours: {work_order['estimated_hours']}
        Cost Estimate: ${work_order['cost_estimate']:,.0f}
        Status: {work_order['status']}
        Created: {work_order['created_date']}
        
        📝 DESCRIPTION:
        {work_order['description']}
        
        🔧 SPECIAL INSTRUCTIONS:
        {work_order.get('instructions', 'None specified')}
        
        ⏰ RESPONSE TIME GUIDELINES:
        • High Priority: Immediate attention required (within 2 hours)
        • Medium Priority: Address within 24 hours
        • Low Priority: Address within 72 hours
        
        📞 NEXT STEPS:
        1. Acknowledge receipt of this work order
        2. Assess the situation at {work_order['branch']}
        3. Take appropriate corrective action
        4. Update the work order status when completed
        
        This is an automated notification from EnerVision Energy Management Platform.
        """
        
        return self.send_email(recipient, subject, content, 'work_order')
    
    def send_anomaly_alert(self, anomalies: List[Dict], recipient: str) -> Dict[str, Any]:
        """Send anomaly alert notification"""
        high_priority = [a for a in anomalies if a.get('Severity') == 'High']
        subject = f"🚨 EnerVision Anomaly Alert - {len(high_priority)} High Priority Issues"
        
        content = f"""
        Energy consumption anomalies detected in EnerVision:
        
        📊 ANOMALY SUMMARY:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Total Anomalies: {len(anomalies)}
        🔴 High Priority: {len(high_priority)}
        🟡 Medium Priority: {len([a for a in anomalies if a.get('Severity') == 'Medium'])}
        🟢 Low Priority: {len([a for a in anomalies if a.get('Severity') == 'Low'])}
        
        🚨 HIGH PRIORITY ISSUES:
        """
        
        for i, anomaly in enumerate(high_priority[:5], 1):
            content += f"""
        {i}. {anomaly.get('Type', 'Unknown')} at {anomaly.get('Branch', 'Unknown')} on {anomaly.get('Date', 'Unknown')}
           Value: {anomaly.get('Value', 'N/A')} kWh (Expected: {anomaly.get('Expected', 'N/A')} kWh)
           Deviation: {anomaly.get('Deviation', 'N/A')} standard deviations
        """
        
        content += """
        
        ⚡ IMMEDIATE ACTION REQUIRED:
        • Investigate all high priority anomalies immediately
        • Check equipment status and operational conditions
        • Review branch operations for unusual activities
        
        Please investigate these anomalies to prevent energy waste and ensure optimal performance.
        """
        
        return self.send_email(recipient, subject, content, 'anomaly_alert')
    
    def send_test_email(self, recipient: str) -> Dict[str, Any]:
        """Send a test email to verify configuration"""
        subject = "⚡ EnerVision - Test Email Configuration"
        content = f"""
        🎉 Congratulations! Your EnerVision email configuration is working perfectly!
        
        📧 Test Email Details:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        • Recipient: {recipient}
        • SMTP Host: {self.smtp_host}
        • SMTP Port: {self.smtp_port}
        • From: {self.smtp_username}
        • Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        🔧 System Status:
        • Email Configuration: ✅ Working
        • SMTP Connection: ✅ Successful
        • Authentication: ✅ Verified
        
        📋 Available Notifications:
        • Work Order Alerts
        • Anomaly Detection Alerts
        • Energy Reports
        • Optimization Recommendations
        
        Your EnerVision platform is now ready to send automated notifications!
        
        Best regards,
        EnerVision Energy Management Team ⚡
        """
        
        return self.send_email(recipient, subject, content, 'work_order')
    
    def diagnose_email_issues(self) -> Dict[str, Any]:
        """Diagnose common email configuration issues"""
        issues = []
        
        if not self.smtp_username:
            issues.append("SMTP_USERNAME not set in environment variables")
        
        if not self.smtp_password:
            issues.append("SMTP_PASSWORD not set in environment variables")
        
        if self.smtp_host == 'smtp.gmail.com' and self.smtp_password and len(self.smtp_password) != 16:
            issues.append("Gmail requires 16-character app password, not regular password")
        
        if not self.smtp_host:
            issues.append("SMTP_HOST not configured")
        
        if self.smtp_port not in [587, 465, 25]:
            issues.append(f"Unusual SMTP port {self.smtp_port}. Common ports: 587 (TLS), 465 (SSL), 25 (plain)")
        
        return {
            'issues_found': len(issues) > 0,
            'issues': issues,
            'recommendations': [
                "Set environment variables: SMTP_USERNAME, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT",
                "For Gmail: Use app password, not regular password",
                "Ensure firewall/antivirus isn't blocking SMTP connections",
                "Try different SMTP ports if connection fails",
                "Verify recipient email addresses are valid"
            ]
        }
    
    # Email Templates
    def get_work_order_template(self) -> str:
        """HTML template for work order notifications"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(90deg, #2E8B57 0%, #32CD32 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .priority-high {{ color: #d32f2f; font-weight: bold; }}
                .priority-medium {{ color: #f57c00; font-weight: bold; }}
                .priority-low {{ color: #388e3c; font-weight: bold; }}
                .footer {{ background-color: #e8e8e8; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚡ EnerVision Work Order Notification</h2>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    <p>EnerVision Energy Management Platform | Automated Notification</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def get_anomaly_alert_template(self) -> str:
        """HTML template for anomaly alerts"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #fff3e0; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(90deg, #FF6B6B 0%, #FF8E8E 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #fff3e0; }}
                .alert {{ border-left: 4px solid #ff9800; padding: 10px; margin: 10px 0; background-color: white; }}
                .footer {{ background-color: #e8e8e8; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🚨 EnerVision Anomaly Alert</h2>
                </div>
                <div class="content">
                    <div class="alert">
                        {content}
                    </div>
                </div>
                <div class="footer">
                    <p>EnerVision Energy Management Platform | Automated Alert</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def get_energy_report_template(self) -> str:
        """HTML template for energy reports"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f8f0; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(90deg, #2E8B57 0%, #32CD32 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .report {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .footer {{ background-color: #e8e8e8; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚡ EnerVision Energy Report</h2>
                </div>
                <div class="content">
                    <div class="report">
                        {content}
                    </div>
                </div>
                <div class="footer">
                    <p>EnerVision Energy Management Platform | Generated Report</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def get_optimization_template(self) -> str:
        """HTML template for optimization notifications"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f4ff; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(90deg, #4ECDC4 0%, #45B7D1 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f0f4ff; }}
                .optimization {{ border-left: 4px solid #45B7D1; padding: 10px; margin: 10px 0; background-color: white; }}
                .footer {{ background-color: #e8e8e8; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🤖 EnerVision AI Optimization</h2>
                </div>
                <div class="content">
                    <div class="optimization">
                        {content}
                    </div>
                </div>
                <div class="footer">
                    <p>EnerVision Energy Management Platform | AI Recommendations</p>
                </div>
            </div>
        </body>
        </html>
        """

# Page configuration
st.set_page_config(
    page_title="EnerVision - Smart Branch Energy Management",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #2E8B57 0%, #32CD32 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #2E8B57;
    }
    .alert-high { border-left-color: #FF4B4B; }
    .alert-medium { border-left-color: #FFA500; }
    .alert-low { border-left-color: #32CD32; }
    .stButton > button {
        background: linear-gradient(90deg, #2E8B57 0%, #32CD32 100%);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

class EnerVisionApp:
    def __init__(self):
        self.init_session_state()
        self.notification_system = EnerVisionNotificationSystem()

    def init_session_state(self):
        """Initialize session state variables"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'company_name' not in st.session_state:
            st.session_state.company_name = ""
        if 'user_email' not in st.session_state:
            st.session_state.user_email = ""
        if 'energy_data' not in st.session_state:
            st.session_state.energy_data = None
        if 'anomalies' not in st.session_state:
            st.session_state.anomalies = []
            
    def hash_password(self, password: str) -> str:
        """Hash password for secure storage"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate_user(self, email: str, password: str) -> bool:
        """Authenticate user (simplified for demo)"""
        # In production, this would check against a database
        hashed_password = self.hash_password(password)
        # For demo, accept any email with password "demo123"
        return password == "demo123"
    
    def register_user(self, company_name: str, email: str, password: str, industry: str) -> bool:
        """Register new user (simplified for demo)"""
        # In production, this would save to database
        return True
    
    def login_page(self):
        """Render login/registration page"""
        st.markdown("""
        <div class="main-header">
            <h1>⚡ EnerVision</h1>
            <h3>Smart Branch Energy Management Platform</h3>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            st.subheader("Login to Your Account")
            with st.form("login_form"):
                email = st.text_input("Email Address")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    if self.authenticate_user(email, password):
                        st.session_state.authenticated = True
                        st.session_state.user_email = email
                        st.session_state.company_name = email.split('@')[0].capitalize()
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Use password: demo123")
        
        with tab2:
            st.subheader("Register Your Company")
            with st.form("register_form"):
                company_name = st.text_input("Company Name")
                reg_email = st.text_input("Company Email")
                industry = st.selectbox("Industry", 
                    ["Retail", "Technology", "Manufacturing", "Healthcare", "Other"])
                reg_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                if st.form_submit_button("Register"):
                    if reg_password == confirm_password and len(reg_password) >= 6:
                        if self.register_user(company_name, reg_email, reg_password, industry):
                            st.success("Registration successful! Please login.")
                    else:
                        st.error("Passwords don't match or are too short (min 6 characters)")
    
    def generate_sample_data(self) -> pd.DataFrame:
        """Generate sample energy data for demonstration"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        branches = ['NYC_Branch_001', 'LA_Branch_002', 'CHI_Branch_003', 'MIA_Branch_004', 'SEA_Branch_005']
        
        data = []
        for date in dates:
            for branch in branches:
                # Seasonal and daily patterns
                base_consumption = 100 + 30 * np.sin(2 * np.pi * date.dayofyear / 365)
                daily_pattern = 20 * np.sin(2 * np.pi * date.hour / 24) if hasattr(date, 'hour') else 0
                noise = np.random.normal(0, 10)
                
                energy_total = max(50, base_consumption + daily_pattern + noise)
                hvac_ratio = np.random.uniform(0.4, 0.6)
                lighting_ratio = np.random.uniform(0.2, 0.3)
                
                data.append({
                    'Branch': branch,
                    'Date': date.strftime('%Y-%m-%d'),
                    'EnergyMeter_kWh': round(energy_total, 2),
                    'HVAC_kWh': round(energy_total * hvac_ratio, 2),
                    'Lighting_kWh': round(energy_total * lighting_ratio, 2),
                    'Temperature_C': round(np.random.uniform(18, 26), 1),
                    'Occupancy_Count': np.random.randint(50, 200),
                    'CarbonEmission_tons': round(energy_total * 0.0005, 4),
                    'ESG_Score': round(np.random.uniform(7.0, 9.5), 2)
                })
        
        return pd.DataFrame(data)
    
    def detect_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        """Simple anomaly detection using statistical methods"""
        anomalies = []
        
        for branch in df['Branch'].unique():
            branch_data = df[df['Branch'] == branch].copy()
            
            # Calculate rolling statistics
            branch_data['rolling_mean'] = branch_data['EnergyMeter_kWh'].rolling(window=7).mean()
            branch_data['rolling_std'] = branch_data['EnergyMeter_kWh'].rolling(window=7).std()
            
            # Detect outliers using 2-sigma rule
            threshold = 2
            for idx, row in branch_data.iterrows():
                if pd.notna(row['rolling_mean']) and pd.notna(row['rolling_std']):
                    z_score = abs(row['EnergyMeter_kWh'] - row['rolling_mean']) / row['rolling_std']
                    
                    if z_score > threshold:
                        severity = "High" if z_score > 3 else "Medium" if z_score > 2.5 else "Low"
                        anomalies.append({
                            'Branch': row['Branch'],
                            'Date': row['Date'],
                            'Value': row['EnergyMeter_kWh'],
                            'Expected': row['rolling_mean'],
                            'Deviation': z_score,
                            'Severity': severity,
                            'Type': 'High Consumption' if row['EnergyMeter_kWh'] > row['rolling_mean'] else 'Low Consumption'
                        })
        
        return anomalies
    
    def dashboard_tab(self):
        """Dashboard and Data Management tab"""
        st.header("📊 Dashboard & Data Management")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📁 Data Upload & Management")
            
            # File upload
            uploaded_file = st.file_uploader("Upload Energy Data (JSON)", type="json")
            if uploaded_file:
                try:
                    data = json.load(uploaded_file)
                    df = pd.DataFrame(data)
                    st.session_state.energy_data = df
                    st.success(f"✅ Uploaded {len(df)} records successfully!")
                except Exception as e:
                    st.error(f"❌ Error uploading file: {str(e)}")
            
            # Generate sample data button
            if st.button("🔄 Generate Sample Data"):
                st.session_state.energy_data = self.generate_sample_data()
                st.success("✅ Sample data generated!")
        
        with col2:
            st.subheader("📈 Quick Stats")
            if st.session_state.energy_data is not None:
                df = st.session_state.energy_data
                
                # Summary metrics
                total_branches = df['Branch'].nunique()
                date_range = f"{df['Date'].min()} to {df['Date'].max()}"
                total_consumption = df['EnergyMeter_kWh'].sum()
                avg_esg_score = df['ESG_Score'].mean()
                
                st.metric("🏢 Total Branches", total_branches)
                st.metric("⚡ Total Consumption", f"{total_consumption:,.0f} kWh")
                st.metric("🌱 Avg ESG Score", f"{avg_esg_score:.2f}/10")
                st.metric("📅 Date Range", f"{(pd.to_datetime(df['Date'].max()) - pd.to_datetime(df['Date'].min())).days} days")
        
        # Data filtering and preview
        if st.session_state.energy_data is not None:
            st.subheader("🔍 Data Filtering & Preview")
            df = st.session_state.energy_data
            
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_branches = st.multiselect("Select Branches", 
                    options=df['Branch'].unique(),
                    default=df['Branch'].unique()[:3])
            
            with col2:
                df['Date'] = pd.to_datetime(df['Date'])
                min_date = df['Date'].min().date()
                max_date = df['Date'].max().date()
                date_range = st.date_input("Date Range", 
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date)
            
            # Filter data
            if len(date_range) == 2:
                filtered_df = df[
                    (df['Branch'].isin(selected_branches)) &
                    (df['Date'].dt.date >= date_range[0]) &
                    (df['Date'].dt.date <= date_range[1])
                ]
                
                st.dataframe(filtered_df.head(100), use_container_width=True)
                
                # Export filtered data
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Filtered Data",
                    data=csv,
                    file_name=f"enervision_data_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    def visualization_tab(self):
        """Data Visualization tab"""
        st.header("📈 Data Visualization")
        
        if st.session_state.energy_data is None:
            st.warning("⚠️ Please upload data first in the Dashboard tab.")
            return
        
        df = st.session_state.energy_data.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Time series analysis
        st.subheader("⏰ Energy Consumption Trends")
        
        col1, col2 = st.columns(2)
        with col1:
            chart_type = st.selectbox("Chart Type", ["Line Chart", "Area Chart", "Bar Chart"])
        with col2:
            metric = st.selectbox("Metric", 
                ["EnergyMeter_kWh", "HVAC_kWh", "Lighting_kWh", "CarbonEmission_tons"])
        
        # Aggregate daily data
        daily_data = df.groupby(['Date', 'Branch'])[metric].sum().reset_index()
        
        if chart_type == "Line Chart":
            fig = px.line(daily_data, x='Date', y=metric, color='Branch',
                title=f"{metric} Over Time by Branch")
        elif chart_type == "Area Chart":
            fig = px.area(daily_data, x='Date', y=metric, color='Branch',
                title=f"{metric} Over Time by Branch")
        else:
            # Monthly aggregation for bar chart
            df['Month'] = df['Date'].dt.to_period('M').astype(str)
            monthly_data = df.groupby(['Month', 'Branch'])[metric].sum().reset_index()
            fig = px.bar(monthly_data, x='Month', y=metric, color='Branch',
                title=f"Monthly {metric} by Branch")
        
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Comparative analysis
        st.subheader("🔄 Comparative Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Branch comparison
            branch_summary = df.groupby('Branch').agg({
                'EnergyMeter_kWh': 'mean',
                'HVAC_kWh': 'mean',
                'Lighting_kWh': 'mean',
                'ESG_Score': 'mean'
            }).round(2)
            
            fig_bar = px.bar(
                x=branch_summary.index,
                y=branch_summary['EnergyMeter_kWh'],
                title="Average Energy Consumption by Branch",
                labels={'x': 'Branch', 'y': 'Average kWh'}
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            # Energy breakdown pie chart
            energy_breakdown = df[['HVAC_kWh', 'Lighting_kWh']].sum()
            other_energy = df['EnergyMeter_kWh'].sum() - energy_breakdown.sum()
            
            fig_pie = px.pie(
                values=[energy_breakdown['HVAC_kWh'], energy_breakdown['Lighting_kWh'], other_energy],
                names=['HVAC', 'Lighting', 'Other'],
                title="Energy Consumption Breakdown"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        # Correlation analysis
        st.subheader("🔗 Correlation Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Temperature vs Energy correlation
            df['Temperature_C'] = df['Temperature_C'].fillna(df['Temperature_C'].mean())
            fig_scatter = px.scatter(
                df, x='Temperature_C', y='EnergyMeter_kWh', 
                color='Branch', size='Occupancy_Count',
                title="Energy Consumption vs Temperature",
                trendline="ols"
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        with col2:
            # Occupancy vs Energy correlation
            fig_scatter2 = px.scatter(
                df, x='Occupancy_Count', y='EnergyMeter_kWh',
                color='Branch', size='Temperature_C',
                title="Energy Consumption vs Occupancy",
                trendline="ols"
            )
            st.plotly_chart(fig_scatter2, use_container_width=True)
    
    def anomaly_tab(self):
        """Anomaly Detection & Usage Analysis tab"""
        st.header("🚨 Anomaly Detection & Usage Analysis")
        
        if st.session_state.energy_data is None:
            st.warning("⚠️ Please upload data first in the Dashboard tab.")
            return
        
        df = st.session_state.energy_data.copy()
        
        # Run anomaly detection
        if st.button("🔍 Run Anomaly Detection"):
            with st.spinner("Analyzing data for anomalies..."):
                st.session_state.anomalies = self.detect_anomalies(df)
            st.success(f"✅ Detection complete! Found {len(st.session_state.anomalies)} anomalies.")
        
        if st.session_state.anomalies:
            anomalies_df = pd.DataFrame(st.session_state.anomalies)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div class="metric-card alert-high">
                    <h3 style="color: #FF4B4B; margin: 0;">High Priority</h3>
                    <h2 style="margin: 5px 0;">{}</h2>
                </div>
                """.format(len(anomalies_df[anomalies_df['Severity'] == 'High'])), 
                unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div class="metric-card alert-medium">
                    <h3 style="color: #FFA500; margin: 0;">Medium Priority</h3>
                    <h2 style="margin: 5px 0;">{}</h2>
                </div>
                """.format(len(anomalies_df[anomalies_df['Severity'] == 'Medium'])), 
                unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div class="metric-card alert-low">
                    <h3 style="color: #32CD32; margin: 0;">Low Priority</h3>
                    <h2 style="margin: 5px 0;">{}</h2>
                </div>
                """.format(len(anomalies_df[anomalies_df['Severity'] == 'Low'])), 
                unsafe_allow_html=True)
            
            with col4:
                st.markdown("""
                <div class="metric-card">
                    <h3 style="color: #2E8B57; margin: 0;">Total Anomalies</h3>
                    <h2 style="margin: 5px 0;">{}</h2>
                </div>
                """.format(len(anomalies_df)), 
                unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Filters for anomalies
            col1, col2, col3 = st.columns(3)
            
            with col1:
                severity_filter = st.multiselect("Filter by Severity", 
                    options=['High', 'Medium', 'Low'],
                    default=['High', 'Medium', 'Low'])
            
            with col2:
                branch_filter = st.multiselect("Filter by Branch",
                    options=anomalies_df['Branch'].unique(),
                    default=anomalies_df['Branch'].unique())
            
            with col3:
                type_filter = st.multiselect("Filter by Type",
                    options=anomalies_df['Type'].unique(),
                    default=anomalies_df['Type'].unique())
            
            # Filter anomalies
            filtered_anomalies = anomalies_df[
                (anomalies_df['Severity'].isin(severity_filter)) &
                (anomalies_df['Branch'].isin(branch_filter)) &
                (anomalies_df['Type'].isin(type_filter))
            ]
            
            # Anomalies visualization
            if not filtered_anomalies.empty:
                st.subheader("📊 Anomaly Visualization")
                
                # Timeline of anomalies
                fig_timeline = px.scatter(
                    filtered_anomalies, 
                    x='Date', y='Branch', 
                    color='Severity',
                    size='Deviation',
                    hover_data=['Value', 'Expected', 'Type'],
                    title="Anomaly Timeline by Branch"
                )
                fig_timeline.update_layout(height=400)
                st.plotly_chart(fig_timeline, use_container_width=True)
                
                # Detailed anomaly table
                st.subheader("📋 Detailed Anomaly Report")
                
                # Sort by severity and deviation
                severity_order = {'High': 3, 'Medium': 2, 'Low': 1}
                filtered_anomalies['severity_rank'] = filtered_anomalies['Severity'].map(severity_order)
                filtered_anomalies_sorted = filtered_anomalies.sort_values(
                    ['severity_rank', 'Deviation'], ascending=[False, False]
                ).drop('severity_rank', axis=1)
                
                st.dataframe(
                    filtered_anomalies_sorted,
                    use_container_width=True,
                    column_config={
                        "Date": st.column_config.DateColumn("Date"),
                        "Value": st.column_config.NumberColumn("Actual (kWh)", format="%.2f"),
                        "Expected": st.column_config.NumberColumn("Expected (kWh)", format="%.2f"),
                        "Deviation": st.column_config.NumberColumn("Z-Score", format="%.2f"),
                        "Severity": st.column_config.TextColumn("Severity")
                    }
                )
                
                # Export anomalies
                csv_anomalies = filtered_anomalies_sorted.to_csv(index=False)
                st.download_button(
                    label="📥 Download Anomaly Report",
                    data=csv_anomalies,
                    file_name=f"anomaly_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    def optimization_tab(self):
        """AI-Powered Optimization Recommendations tab"""
        st.header("🤖 AI-Powered Optimization Recommendations")
        
        if st.session_state.energy_data is None:
            st.warning("⚠️ Please upload data first in the Dashboard tab.")
            return
        
        st.info("🚀 This feature uses LangGraph multi-agent system for intelligent recommendations.")
        
        # Simulate AI recommendations (in production, this would use actual LLM)
        if st.button("🧠 Generate AI Recommendations"):
            with st.spinner("AI agents analyzing your data..."):
                # Simulate processing time
                import time
                time.sleep(3)
                
                recommendations = self.generate_mock_recommendations()
                st.session_state.recommendations = recommendations
        
        if 'recommendations' in st.session_state:
            recommendations = st.session_state.recommendations
            
            st.success("✅ Analysis complete! Here are your optimization recommendations:")
            
            # Display recommendations by category
            for category, recs in recommendations.items():
                st.subheader(f"🎯 {category}")
                
                for i, rec in enumerate(recs, 1):
                    with st.expander(f"💡 {rec['title']} - {rec['priority']} Priority"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write("**Description:**")
                            st.write(rec['description'])
                            
                            st.write("**Implementation Steps:**")
                            for step in rec['steps']:
                                st.write(f"• {step}")
                        
                        with col2:
                            st.metric("💰 Est. Savings", rec['savings'])
                            st.metric("⏱️ Implementation", rec['timeline'])
                            st.metric("🌱 ESG Impact", rec['esg_impact'])
                            
                        
    
    def generate_mock_recommendations(self) -> Dict:
        """Generate mock AI recommendations for demonstration"""
        return {
            "Energy Efficiency": [
                {
                    "title": "HVAC System Optimization",
                    "priority": "High",
                    "description": "Your HVAC systems are consuming 15% more energy than industry benchmarks. Implementing smart thermostats and zone-based controls could significantly reduce consumption.",
                    "steps": [
                        "Install smart thermostats in all zones",
                        "Implement occupancy-based temperature control",
                        "Schedule regular maintenance for optimal efficiency",
                        "Add thermal insulation to reduce load"
                    ],
                    "savings": "$2,400/month",
                    "timeline": "2-3 weeks",
                    "esg_impact": "+0.8 ESG Score"
                },
                {
                    "title": "LED Lighting Upgrade",
                    "priority": "Medium",
                    "description": "Branch lighting systems show potential for 30% energy reduction through LED upgrades and smart controls.",
                    "steps": [
                        "Audit current lighting systems",
                        "Replace fluorescent with LED fixtures",
                        "Install motion sensors and daylight controls",
                        "Implement automated lighting schedules"
                    ],
                    "savings": "$1,200/month",
                    "timeline": "1-2 weeks",
                    "esg_impact": "+0.5 ESG Score"
                }
            ],
            "Operational Improvements": [
                {
                    "title": "Peak Demand Management",
                    "priority": "High", 
                    "description": "Analysis shows opportunities to shift 20% of energy usage to off-peak hours, reducing demand charges.",
                    "steps": [
                        "Identify energy-intensive processes",
                        "Reschedule non-critical operations to off-peak hours",
                        "Implement demand response protocols",
                        "Install energy storage systems for peak shaving"
                    ],
                    "savings": "$1,800/month",
                    "timeline": "3-4 weeks",
                    "esg_impact": "+0.6 ESG Score"
                }
            ],
            "Sustainability": [
                {
                    "title": "Solar Panel Installation",
                    "priority": "Medium",
                    "description": "Rooftop analysis indicates potential for 40% renewable energy offset through solar installation.",
                    "steps": [
                        "Conduct detailed site assessment",
                        "Obtain permits and approvals",
                        "Install solar panels and inverters",
                        "Connect to grid with net metering"
                    ],
                    "savings": "$3,500/month",
                    "timeline": "8-12 weeks",
                    "esg_impact": "+1.5 ESG Score"
                }
            ]
        }
    
    def forecasting_tab(self):
        """Energy Forecasting tab"""
        st.header("🔮 Energy Forecasting")
        
        if st.session_state.energy_data is None:
            st.warning("⚠️ Please upload data first in the Dashboard tab.")
            return
        
        df = st.session_state.energy_data.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        
        st.subheader("📈 Predictive Models")
        
        col1, col2 = st.columns(2)
        
        with col1:
            forecast_period = st.selectbox(
                "Forecast Period",
                ["Next 7 days", "Next 30 days", "Next 3 months", "Next 12 months"]
            )
            
        with col2:
            selected_branch = st.selectbox(
                "Select Branch",
                options=df['Branch'].unique()
            )
        
        if st.button("🚀 Generate Forecast"):
            with st.spinner("Generating forecast..."):
                # Simple forecast simulation (in production, use proper ML models)
                forecast_data = self.generate_forecast(df, selected_branch, forecast_period)
                
                # Plot historical and forecast data
                fig = go.Figure()
                
                # Historical data
                branch_data = df[df['Branch'] == selected_branch].sort_values('Date')
                fig.add_trace(go.Scatter(
                    x=branch_data['Date'],
                    y=branch_data['EnergyMeter_kWh'],
                    mode='lines',
                    name='Historical',
                    line=dict(color='blue')
                ))
                
                # Forecast data
                fig.add_trace(go.Scatter(
                    x=forecast_data['Date'],
                    y=forecast_data['Forecast'],
                    mode='lines',
                    name='Forecast',
                    line=dict(color='red', dash='dash')
                ))
                
                # Confidence interval
                fig.add_trace(go.Scatter(
                    x=forecast_data['Date'],
                    y=forecast_data['Upper_CI'],
                    fill=None,
                    mode='lines',
                    line=dict(color='rgba(0,0,0,0)'),
                    name='Upper CI',
                    showlegend=False
                ))
                
                fig.add_trace(go.Scatter(
                    x=forecast_data['Date'],
                    y=forecast_data['Lower_CI'],
                    fill='tonexty',
                    mode='lines',
                    line=dict(color='rgba(0,0,0,0)'),
                    name='Confidence Interval',
                    fillcolor='rgba(255,0,0,0.1)'
                ))
                
                fig.update_layout(
                    title=f'Energy Consumption Forecast - {selected_branch}',
                    xaxis_title='Date',
                    yaxis_title='Energy Consumption (kWh)',
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Forecast summary
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_forecast = forecast_data['Forecast'].mean()
                    st.metric("📊 Avg Predicted Consumption", f"{avg_forecast:.1f} kWh")
                
                with col2:
                    total_forecast = forecast_data['Forecast'].sum()
                    st.metric("⚡ Total Predicted Consumption", f"{total_forecast:.0f} kWh")
                
                with col3:
                    confidence = 85  # Mock confidence level
                    st.metric("🎯 Model Confidence", f"{confidence}%")
                
                # Forecast insights
                st.subheader("🔍 Forecast Insights")
                insights = [
                    "📈 Energy consumption is expected to increase by 5% due to seasonal changes",
                    "⚠️ Peak consumption periods identified on weekdays 2-4 PM",
                    "💡 Optimal time for maintenance: Weekends and early mornings",
                    "🌡️ Temperature correlation suggests 3% increase per degree above 24°C"
                ]
                
                for insight in insights:
                    st.info(insight)
    
    def generate_forecast(self, df: pd.DataFrame, branch: str, period: str) -> pd.DataFrame:
        """Generate forecast data (simplified simulation)"""
        branch_data = df[df['Branch'] == branch].sort_values('Date')
        last_date = pd.to_datetime(branch_data['Date'].max())
        
        # Determine forecast length
        if period == "Next 7 days":
            days = 7
        elif period == "Next 30 days":
            days = 30
        elif period == "Next 3 months":
            days = 90
        else:  # Next 12 months
            days = 365
        
        # Generate future dates
        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days, freq='D')
        
        # Simple trend + seasonal forecast
        historical_mean = branch_data['EnergyMeter_kWh'].mean()
        historical_std = branch_data['EnergyMeter_kWh'].std()
        
        forecast_values = []
        for i, date in enumerate(future_dates):
            # Basic seasonal pattern
            seasonal = 20 * np.sin(2 * np.pi * date.dayofyear / 365)
            trend = historical_mean + seasonal + np.random.normal(0, 5)
            forecast_values.append(max(50, trend))
        
        # Create confidence intervals
        ci_width = historical_std * 0.5
        
        return pd.DataFrame({
            'Date': future_dates,
            'Forecast': forecast_values,
            'Upper_CI': [f + ci_width for f in forecast_values],
            'Lower_CI': [f - ci_width for f in forecast_values]
        })
    
    def reports_tab(self):
        """Report Generation tab"""
        st.header("📋 Report Generation")
        
        if st.session_state.energy_data is None:
            st.warning("⚠️ Please upload data first in the Dashboard tab.")
            return
        
        st.subheader("📄 Generate Custom Reports")
        
        col1, col2 = st.columns(2)
        
        with col1:
            report_type = st.selectbox(
                "Report Type",
                [
                    "Daily Energy Report",
                    "Weekly Energy Summary", 
                    "Monthly ESG Report",
                    "Quarterly Cost Analysis",
                    "Annual Sustainability Report",
                    "Anomaly Summary Report",
                    "Optimization Progress Report"
                ]
            )
            
            report_format = st.selectbox("Output Format", ["PDF", "Excel", "CSV"])
            
        with col2:
            # Date range for report
            df = st.session_state.energy_data.copy()
            df['Date'] = pd.to_datetime(df['Date'])
            
            min_date = df['Date'].min().date()
            max_date = df['Date'].max().date()
            
            report_date_range = st.date_input(
                "Report Date Range",
                value=(max_date - timedelta(days=30), max_date),
                min_value=min_date,
                max_value=max_date
            )
            
            selected_branches_report = st.multiselect(
                "Select Branches",
                options=df['Branch'].unique(),
                default=df['Branch'].unique()[:3],
                key="branches_report"
            )
        
        if st.button("📊 Generate Report"):
            with st.spinner("Generating report..."):
                report_data = self.generate_report_data(df, report_type, report_date_range, selected_branches_report)
                
                st.success("✅ Report generated successfully!")
                
                # Display report preview
                st.subheader("📖 Report Preview")
                
                # Executive Summary
                st.markdown("### Executive Summary")
                st.write(report_data['executive_summary'])
                
                # Key Metrics
                st.markdown("### Key Metrics")
                col1, col2, col3, col4 = st.columns(4)
                
                metrics = report_data['key_metrics']
                with col1:
                    st.metric("Total Consumption", f"{metrics['total_consumption']:,.0f} kWh")
                with col2:
                    st.metric("Average ESG Score", f"{metrics['avg_esg_score']:.2f}")
                with col3:
                    st.metric("Carbon Emissions", f"{metrics['total_emissions']:.2f} tons")
                with col4:
                    st.metric("Cost Estimate", f"${metrics['estimated_cost']:,.0f}")
                
                # Charts
                if 'charts' in report_data:
                    st.markdown("### Energy Consumption Analysis")
                    for chart in report_data['charts']:
                        st.plotly_chart(chart, use_container_width=True)
                
                # Recommendations
                if 'recommendations' in report_data:
                    st.markdown("### Key Recommendations")
                    for rec in report_data['recommendations']:
                        st.write(f"• {rec}")
                
                # Download button
                report_content = self.format_report_for_download(report_data, report_format)
                file_extension = report_format.lower()
                
                st.download_button(
                    label=f"📥 Download {report_format} Report",
                    data=report_content,
                    file_name=f"enervision_report_{datetime.now().strftime('%Y%m%d')}.{file_extension}",
                    mime=f"application/{file_extension}"
                )
    
    def generate_report_data(self, df: pd.DataFrame, report_type: str, date_range, branches: List[str]) -> Dict:
        """Generate report data based on type and parameters"""
        
        # Filter data
        if len(date_range) == 2:
            filtered_df = df[
                (df['Branch'].isin(branches)) &
                (df['Date'].dt.date >= date_range[0]) &
                (df['Date'].dt.date <= date_range[1])
            ]
        else:
            filtered_df = df[df['Branch'].isin(branches)]
        
        # Calculate key metrics
        key_metrics = {
            'total_consumption': filtered_df['EnergyMeter_kWh'].sum(),
            'avg_esg_score': filtered_df['ESG_Score'].mean(),
            'total_emissions': filtered_df['CarbonEmission_tons'].sum(),
            'estimated_cost': filtered_df['EnergyMeter_kWh'].sum() * 0.12  # $0.12 per kWh
        }
        
        # Generate executive summary
        executive_summary = f"""
        This {report_type.lower()} covers {len(branches)} branch(es) from {date_range[0] if len(date_range) == 2 else 'start'} to {date_range[1] if len(date_range) == 2 else 'end'}. 
        Total energy consumption was {key_metrics['total_consumption']:,.0f} kWh, resulting in {key_metrics['total_emissions']:.2f} tons of carbon emissions. 
        The average ESG score across all branches was {key_metrics['avg_esg_score']:.2f}/10, with an estimated energy cost of ${key_metrics['estimated_cost']:,.0f}.
        """
        
        # Generate charts
        charts = []
        
        # Daily consumption trend
        daily_consumption = filtered_df.groupby('Date')['EnergyMeter_kWh'].sum().reset_index()
        fig1 = px.line(daily_consumption, x='Date', y='EnergyMeter_kWh', 
                      title='Daily Energy Consumption Trend')
        charts.append(fig1)
        
        # Branch comparison
        branch_comparison = filtered_df.groupby('Branch')['EnergyMeter_kWh'].sum().reset_index()
        fig2 = px.bar(branch_comparison, x='Branch', y='EnergyMeter_kWh',
                     title='Energy Consumption by Branch')
        charts.append(fig2)
        
        # Recommendations based on report type
        recommendations = [
            "Implement energy monitoring systems for real-time tracking",
            "Consider LED lighting upgrades for 20-30% energy savings",
            "Optimize HVAC schedules based on occupancy patterns", 
            "Investigate renewable energy options for long-term sustainability",
            "Establish energy reduction targets for each branch"
        ]
        
        return {
            'report_type': report_type,
            'executive_summary': executive_summary,
            'key_metrics': key_metrics,
            'charts': charts,
            'recommendations': recommendations,
            'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def format_report_for_download(self, report_data: Dict, format_type: str) -> str:
        """Format report data for download"""
        if format_type == "CSV":
            # Return key metrics as CSV
            metrics = report_data['key_metrics']
            csv_content = "Metric,Value\n"
            csv_content += f"Total Consumption (kWh),{metrics['total_consumption']}\n"
            csv_content += f"Average ESG Score,{metrics['avg_esg_score']:.2f}\n"
            csv_content += f"Total Emissions (tons),{metrics['total_emissions']:.2f}\n"
            csv_content += f"Estimated Cost ($),{metrics['estimated_cost']:.0f}\n"
            return csv_content
        
        elif format_type == "Excel":
            # Mock Excel content (in production, use openpyxl)
            return "Excel format would be generated here using openpyxl library"
        
        else:  # PDF
            # Mock PDF content (in production, use reportlab)
            pdf_content = f"""
            {report_data['report_type']}
            Generated: {report_data['generation_date']}
            
            {report_data['executive_summary']}
            
            Key Metrics:
            - Total Consumption: {report_data['key_metrics']['total_consumption']:,.0f} kWh
            - Average ESG Score: {report_data['key_metrics']['avg_esg_score']:.2f}
            - Total Emissions: {report_data['key_metrics']['total_emissions']:.2f} tons
            - Estimated Cost: ${report_data['key_metrics']['estimated_cost']:,.0f}
            
            Recommendations:
            """ + "\n".join([f"- {rec}" for rec in report_data['recommendations']])
            
            return pdf_content
    
    def communication_tab(self):
        """Enhanced Work Order Management & Communication tab with full SMTP functionality"""
        st.header("📧 Work Order Management & Communication")
        
        # Email Configuration Section
        st.subheader("🔧 Email Configuration & Testing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Email configuration status
            if self.notification_system.config_valid:
                st.success("✅ Email Configuration: Valid")
            else:
                st.error("❌ Email Configuration: Invalid")
                
            if st.button("🧪 Test Email Configuration"):
                with st.spinner("Testing email configuration..."):
                    test_result = self.notification_system.test_connection()
                    if test_result['success']:
                        st.success(f"✅ {test_result['message']}")
                    else:
                        st.error(f"❌ {test_result['error']}")
                        if test_result.get('details'):
                            st.write(f"**Details:** {test_result['details']}")
                        
                        # Show diagnostic information
                        diagnosis = self.notification_system.diagnose_email_issues()
                        if diagnosis['issues_found']:
                            with st.expander("🔍 Diagnostic Details"):
                                st.warning("**Issues Found:**")
                                for issue in diagnosis['issues']:
                                    st.write(f"• {issue}")
                                
                                st.info("**Recommendations:**")
                                for rec in diagnosis['recommendations']:
                                    st.write(f"• {rec}")
        
        with col2:
            test_email = st.text_input(
                "Manager Email Address", 
                placeholder="manager@company.com",
                help="Enter email address for notifications and testing"
            )
            
            col_test, col_validate = st.columns(2)
            
            with col_test:
                if st.button("📧 Send Test Email") and test_email:
                    if '@' not in test_email or '.' not in test_email:
                        st.error("❌ Please enter a valid email address")
                    else:
                        with st.spinner("Sending test email..."):
                            result = self.notification_system.send_test_email(test_email)
                            if result['success']:
                                st.success("✅ Test email sent successfully!")
                            else:
                                st.error(f"❌ Failed to send test email: {result['error']}")
                                if result.get('details'):
                                    st.write(f"**Details:** {result['details']}")
            
            with col_validate:
                if st.button("✅ Validate Email") and test_email:
                    if '@' not in test_email or '.' not in test_email:
                        st.error("❌ Invalid email format")
                    else:
                        st.success("✅ Email format valid")
        
        # Environment Variables Display
        # Environment Variables Display
        with st.expander("🔍 Current SMTP Configuration"):
            st.code(f"""
        Current SMTP Settings:
        SMTP_SERVER: {settings.smtp_server or 'Not set'}
        SMTP_PORT: {settings.smtp_port or 'Not set'}
        SMTP_USERNAME: {settings.smtp_username or 'Not set'}
        SMTP_PASSWORD: {'Set (' + str(len(settings.smtp_password)) + ' chars)' if settings.smtp_password else 'Not set'}
            """)
            
            # Show all loaded environment variables for debugging
            st.write("**Debug - All SMTP Environment Variables:**")
            st.write(f"- SMTP_SERVER from env: {os.getenv('SMTP_SERVER', 'Not found')}")
            st.write(f"- SMTP_PORT from env: {os.getenv('SMTP_PORT', 'Not found')}")  
            st.write(f"- SMTP_USERNAME from env: {os.getenv('SMTP_USERNAME', 'Not found')}")
            st.write(f"- SMTP_PASSWORD from env: {'Found' if os.getenv('SMTP_PASSWORD') else 'Not found'}")
            
            st.info("""
            **Gmail App Password Setup Instructions:**
            
            1. **Enable 2-Factor Authentication:**
            - Go to [Google Account Security](https://myaccount.google.com/security)
            - Click "2-Step Verification" and set it up
            
            2. **Generate App Password:**
            - Return to Google Account Security
            - Click "App passwords" (only visible after 2FA)
            - Select app: **Mail**, device: **Other (custom name)**
            - Enter name: **EnerVision** → Click **Generate**
            - Copy the 16-character password (e.g., abcd efgh ijkl mnop)
            
            3. **Set Environment Variables in .env file:**
            ```
            SMTP_SERVER=smtp.gmail.com
            SMTP_PORT=587
            SMTP_USERNAME=your_email@gmail.com
            SMTP_PASSWORD=abcdefghijklmnop
            ```
            
            4. **Restart your Streamlit application**
            """)

        
        st.divider()
        
        # Work Order Creation Form
        st.subheader("📋 Create Work Order")
        
        with st.form("enhanced_work_order_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                wo_title = st.text_input("Work Order Title", placeholder="e.g., HVAC System Maintenance")
                wo_branch = st.selectbox("Target Branch",
                    options=st.session_state.energy_data['Branch'].unique() if st.session_state.energy_data is not None else ['NYC_Branch_001', 'LA_Branch_002', 'CHI_Branch_003'])
                wo_priority = st.selectbox("Priority Level", ["High", "Medium", "Low"])
                wo_category = st.selectbox("Category", 
                    ["Energy Efficiency", "Maintenance", "Anomaly Resolution", "Optimization", "Emergency", "Safety", "Other"])
            
            with col2:
                wo_assignee = st.text_input("Assign To (Email)", placeholder="technician@company.com")
                wo_due_date = st.date_input("Due Date", value=datetime.now().date() + timedelta(days=7))
                wo_estimated_hours = st.number_input("Estimated Hours", min_value=1, max_value=100, value=4)
                wo_cost_estimate = st.number_input("Cost Estimate ($)", min_value=0, value=500)
            
            wo_description = st.text_area("Work Order Description", 
                height=100,
                placeholder="Detailed description of the work to be performed...")
            wo_instructions = st.text_area("Special Instructions", 
                height=80,
                placeholder="Any special safety requirements, tools needed, etc...")
            
            # Auto-send notification option
            auto_notify = st.checkbox(
                "📧 Auto-send email notification", 
                value=True,
                help="Automatically send notification when work order is created"
            )
            
            if st.form_submit_button("📋 Create Work Order"):
                if wo_title.strip() and wo_description.strip():
                    # Create work order
                    work_order = {
                        'id': f"WO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        'title': wo_title,
                        'branch': wo_branch,
                        'priority': wo_priority,
                        'category': wo_category,
                        'assignee': wo_assignee,
                        'due_date': wo_due_date.strftime('%Y-%m-%d'),
                        'estimated_hours': wo_estimated_hours,
                        'cost_estimate': wo_cost_estimate,
                        'description': wo_description,
                        'instructions': wo_instructions,
                        'status': 'Open',
                        'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'notifications_sent': 0
                    }
                    
                    # Store work order in session state
                    if 'work_orders' not in st.session_state:
                        st.session_state.work_orders = []
                    st.session_state.work_orders.append(work_order)
                    
                    st.success(f"✅ Work Order {work_order['id']} created successfully!")
                    
                    # Send email notification if enabled and email provided
                    if auto_notify and wo_assignee:
                        with st.spinner("Sending notification..."):
                            result = self.notification_system.send_work_order_notification(work_order, wo_assignee)
                            
                            if result['success']:
                                st.success(f"📧 {result['message']}")
                                work_order['notifications_sent'] = 1
                                work_order['last_notification'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                st.warning(f"⚠️ Work order created but notification failed: {result['error']}")
                                if result.get('details'):
                                    st.write(f"Details: {result['details']}")
                    elif auto_notify and not wo_assignee:
                        st.warning("⚠️ Auto-notification enabled but no assignee email provided")
                    
                    st.rerun()
                else:
                    st.error("❌ Please provide both title and description for the work order")
        
        # Work Order Management Section
        if 'work_orders' in st.session_state and st.session_state.work_orders:
            st.divider()
            st.subheader("📊 Work Order Management")
            
            work_orders_df = pd.DataFrame(st.session_state.work_orders)
            
            # Work order summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                open_orders = len(work_orders_df[work_orders_df['status'] == 'Open'])
                st.metric("📋 Open Orders", open_orders)
            
            with col2:
                high_priority = len(work_orders_df[work_orders_df['priority'] == 'High'])
                st.metric("🚨 High Priority", high_priority)
            
            with col3:
                total_cost = work_orders_df['cost_estimate'].sum()
                st.metric("💰 Total Cost Est.", f"${total_cost:,.0f}")
            
            with col4:
                total_hours = work_orders_df['estimated_hours'].sum()
                st.metric("⏱️ Total Hours Est.", f"{total_hours} hrs")
            
            # Individual Work Orders Display
            st.subheader("📋 Active Work Orders")
            
            for i, wo in enumerate(st.session_state.work_orders):
                status_color = {"Open": "🔴", "In Progress": "🟡", "Completed": "🟢"}
                priority_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
                
                with st.expander(f"🎫 Work Order #{wo['id']} - {priority_color.get(wo['priority'], '⚪')} {wo['priority']} Priority - {status_color.get(wo['status'], '⚪')} {wo['status']}"):
                    col_info, col_actions = st.columns([3, 1])
                    
                    with col_info:
                        st.write(f"**Title:** {wo['title']}")
                        st.write(f"**Branch:** {wo['branch']}")
                        st.write(f"**Category:** {wo['category']}")
                        st.write(f"**Assignee:** {wo['assignee']}")
                        st.write(f"**Due Date:** {wo['due_date']}")
                        st.write(f"**Cost Estimate:** ${wo['cost_estimate']:,.0f}")
                        st.write(f"**Description:** {wo['description']}")
                        if wo.get('instructions'):
                            st.write(f"**Instructions:** {wo['instructions']}")
                        st.write(f"**Created:** {wo['created_date']}")
                        
                        if 'notifications_sent' in wo and wo['notifications_sent'] > 0:
                            st.write(f"**Notifications Sent:** {wo['notifications_sent']}")
                            if 'last_notification' in wo:
                                st.write(f"**Last Notification:** {wo['last_notification']}")
                    
                    with col_actions:
                        if wo['status'] != 'Completed':
                            if st.button(f"✅ Complete", key=f"complete_{i}"):
                                st.session_state.work_orders[i]['status'] = 'Completed'
                                st.session_state.work_orders[i]['completed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                st.success("Work order marked as completed!")
                                st.rerun()
                            
                            if st.button(f"🔄 In Progress", key=f"progress_{i}"):
                                st.session_state.work_orders[i]['status'] = 'In Progress'
                                st.info("Work order marked as in progress!")
                                st.rerun()
                        
                        if st.button(f"📧 Send Notification", key=f"notify_{i}"):
                            if not test_email:
                                st.error("❌ Please enter a manager email address above")
                            else:
                                with st.spinner("Sending notification..."):
                                    result = self.notification_system.send_work_order_notification(wo, test_email)
                                    
                                    if result['success']:
                                        st.success(f"✅ {result['message']}")
                                        # Track notification
                                        if 'notifications_sent' not in st.session_state.work_orders[i]:
                                            st.session_state.work_orders[i]['notifications_sent'] = 0
                                        st.session_state.work_orders[i]['notifications_sent'] += 1
                                        st.session_state.work_orders[i]['last_notification'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    else:
                                        st.error(f"❌ {result['error']}")
                                        if result.get('details'):
                                            st.write(f"Details: {result['details']}")
            
            # Bulk Actions Section
            st.subheader("⚡ Bulk Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📧 Notify All Open Orders"):
                    if test_email:
                        open_orders = [wo for wo in st.session_state.work_orders if wo['status'] == 'Open']
                        if open_orders:
                            with st.spinner(f"Sending {len(open_orders)} notifications..."):
                                success_count = 0
                                for wo in open_orders:
                                    result = self.notification_system.send_work_order_notification(wo, test_email)
                                    if result['success']:
                                        success_count += 1
                                
                                if success_count == len(open_orders):
                                    st.success(f"✅ All {success_count} notifications sent!")
                                else:
                                    st.warning(f"⚠️ {success_count}/{len(open_orders)} notifications sent successfully")
                        else:
                            st.info("No open work orders to notify")
                    else:
                        st.error("Please enter a manager email address above")
            
            with col2:
                high_priority = [wo for wo in st.session_state.work_orders if wo['priority'] == 'High' and wo['status'] == 'Open']
                if high_priority and st.button("🚨 Notify High Priority"):
                    if test_email:
                        with st.spinner(f"Sending {len(high_priority)} urgent notifications..."):
                            success_count = 0
                            for wo in high_priority:
                                result = self.notification_system.send_work_order_notification(wo, test_email)
                                if result['success']:
                                    success_count += 1
                            st.success(f"✅ {success_count} urgent notifications sent!")
                    else:
                        st.error("Please enter a manager email address above")
            
            with col3:
                if st.button("📊 Export Work Orders"):
                    df_export = pd.DataFrame(st.session_state.work_orders)
                    csv = df_export.to_csv(index=False)
                    st.download_button(
                        label="💾 Download CSV",
                        data=csv,
                        file_name=f"enervision_work_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            # Work Orders Table
            st.subheader("📊 Work Orders Overview")
            st.dataframe(
                work_orders_df,
                use_container_width=True,
                column_config={
                    "id": "Work Order ID",
                    "title": "Title",
                    "branch": "Branch",
                    "priority": st.column_config.TextColumn("Priority"),
                    "status": st.column_config.TextColumn("Status"),
                    "assignee": "Assignee",
                    "due_date": st.column_config.DateColumn("Due Date"),
                    "cost_estimate": st.column_config.NumberColumn("Cost ($)", format="$%.0f"),
                    "notifications_sent": st.column_config.NumberColumn("Notifications", format="%d")
                }
            )
        
        # Additional Features Section
        st.divider()
        st.subheader("🔔 Anomaly Alert Integration")
        
        if st.session_state.anomalies and test_email:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Detected Anomalies:** {len(st.session_state.anomalies)}")
                high_anomalies = len([a for a in st.session_state.anomalies if a.get('Severity') == 'High'])
                st.write(f"**High Priority Anomalies:** {high_anomalies}")
            
            with col2:
                if st.button("📧 Send Anomaly Alert"):
                    with st.spinner("Sending anomaly alert..."):
                        result = self.notification_system.send_anomaly_alert(st.session_state.anomalies, test_email)
                        
                        if result['success']:
                            st.success(f"✅ {result['message']}")
                        else:
                            st.error(f"❌ {result['error']}")
                            if result.get('details'):
                                st.write(f"Details: {result['details']}")
        else:
            if not st.session_state.anomalies:
                st.info("💡 Run anomaly detection in the Anomalies tab to enable alert notifications")
            if not test_email:
                st.info("💡 Enter a manager email address above to enable anomaly alerts")

    
    def send_work_order_email(self, work_order: Dict) -> Dict[str, Any]:
        """Send work order email notification using enhanced notification system"""
        try:
            if work_order.get('assignee'):
                result = self.notification_system.send_work_order_notification(
                    work_order, 
                    work_order['assignee']
                )
                return result
            else:
                return {
                    'success': False,
                    'error': 'No assignee email specified'
                }
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            return {
                'success': False,
                'error': error_msg
            }

    
    def workflow_diagram_tab(self):
        """LangGraph Workflow Diagram tab"""
        st.header("🔀 EnerVision AI Workflow Architecture")
        
        st.markdown("""
        This diagram shows the **LangGraph Multi-Agent System** workflow used in EnerVision for intelligent energy analysis and optimization.
        """)
        
        # Create workflow diagram using Plotly
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        # Define agent positions
        agents = {
            "Planner": {"x": 1, "y": 5, "color": "#FF6B6B"},
            "Data Retrieval": {"x": 3, "y": 5, "color": "#4ECDC4"},
            "Reasoning": {"x": 5, "y": 5, "color": "#45B7D1"},
            "Compliance": {"x": 3, "y": 3, "color": "#96CEB4"},
            "Forecast": {"x": 5, "y": 3, "color": "#FFEAA7"},
            "Reporter": {"x": 4, "y": 1, "color": "#DDA0DD"}
        }
        
        # Create the workflow diagram
        fig = go.Figure()
        
        # Add agent nodes
        for agent, props in agents.items():
            fig.add_trace(go.Scatter(
                x=[props["x"]],
                y=[props["y"]],
                mode='markers+text',
                marker=dict(
                    size=100,
                    color=props["color"],
                    line=dict(color="white", width=2)
                ),
                text=[agent],
                textposition="middle center",
                textfont=dict(size=12, color="white", family="Arial Black"),
                name=agent,
                showlegend=True
            ))
        
        # Add arrows/connections
        connections = [
            ("Planner", "Data Retrieval"),
            ("Data Retrieval", "Reasoning"),
            ("Reasoning", "Compliance"),
            ("Reasoning", "Forecast"),
            ("Compliance", "Reporter"),
            ("Forecast", "Reporter")
        ]
        
        for start, end in connections:
            start_pos = agents[start]
            end_pos = agents[end]
            
            fig.add_trace(go.Scatter(
                x=[start_pos["x"], end_pos["x"]],
                y=[start_pos["y"], end_pos["y"]],
                mode='lines',
                line=dict(color="gray", width=3, dash="solid"),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            # Add arrow heads
            mid_x = (start_pos["x"] + end_pos["x"]) / 2
            mid_y = (start_pos["y"] + end_pos["y"]) / 2
            
            fig.add_annotation(
                x=end_pos["x"], y=end_pos["y"],
                ax=start_pos["x"], ay=start_pos["y"],
                xref="x", yref="y",
                axref="x", ayref="y",
                arrowhead=2,
                arrowsize=1.5,
                arrowcolor="gray",
                arrowwidth=2
            )
        
        # Update layout
        fig.update_layout(
            title={
                'text': "🤖 EnerVision Multi-Agent Workflow",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 24}
            },
            xaxis=dict(
                range=[0, 6],
                showgrid=False,
                showticklabels=False,
                zeroline=False
            ),
            yaxis=dict(
                range=[0, 6],
                showgrid=False,
                showticklabels=False,
                zeroline=False
            ),
            height=600,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Agent descriptions
        st.subheader("🧠 Agent Responsibilities")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **🎯 Planner Agent**
            - Analyzes user requests and data characteristics
            - Creates comprehensive analysis strategy
            - Identifies priority areas for investigation
            - Coordinates overall workflow execution
            
            **📊 Data Retrieval Agent**
            - Processes and analyzes energy consumption data
            - Calculates key performance metrics
            - Identifies patterns and trends
            - Provides benchmark comparisons
            
            **🧮 Reasoning Agent** 
            - Generates insights from processed data
            - Identifies optimization opportunities
            - Performs pattern recognition and analysis
            - Creates prioritized recommendations
            """)
        
        with col2:
            st.markdown("""
            **✅ Compliance Agent**
            - Ensures ESG compliance and standards
            - Performs regulatory requirement checks
            - Assesses certification readiness
            - Identifies compliance risks and mitigation
            
            **🔮 Forecast Agent**
            - Generates short and long-term predictions
            - Analyzes seasonal consumption patterns
            - Predicts peak demand periods
            - Provides forecast accuracy metrics
            
            **📋 Reporter Agent**
            - Compiles comprehensive analysis reports
            - Creates executive summaries
            - Generates implementation roadmaps
            - Provides monitoring recommendations
            """)
        
        # Workflow execution stats
        st.subheader("📈 Workflow Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("⚡ Avg Execution Time", "45.2 seconds")
        with col2:
            st.metric("🎯 Success Rate", "99.7%")
        with col3:
            st.metric("🤖 Total Agents", "6")
        with col4:
            st.metric("🔄 Parallel Operations", "3")
        
        # Technology stack
        st.subheader("🛠️ Technology Stack")
        
        tech_info = {
            "🧠 LangGraph": "Multi-agent workflow orchestration framework",
            "🤖 Google Gemini-1.5-Flash": "Large language model for intelligent analysis",
            "📊 AgentOps": "Agent performance monitoring and tracing",
            "🔍 LangSmith": "Workflow observability and debugging",
            "⚡ FAISS": "Vector similarity search for document retrieval",
            "🐍 Python": "Core application development language"
        }
        
        for tech, description in tech_info.items():
            st.markdown(f"**{tech}**: {description}")
        
        # Mock tracing information
        st.subheader("🔍 Agent Execution Tracing")
        
        if st.button("🎯 View Latest Execution Trace", key="trace_btn"):
            trace_data = {
                "execution_id": f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_duration": "45.2s",
                "agents_executed": 6,
                "success": True,
                "agent_details": [
                    {"agent": "Planner", "duration": "5.2s", "status": "✅ Success", "tokens": 1250},
                    {"agent": "Data Retrieval", "duration": "12.8s", "status": "✅ Success", "tokens": 2100},
                    {"agent": "Reasoning", "duration": "15.6s", "status": "✅ Success", "tokens": 3200},
                    {"agent": "Compliance", "duration": "8.1s", "status": "✅ Success", "tokens": 1800},
                    {"agent": "Forecast", "duration": "10.3s", "status": "✅ Success", "tokens": 2400},
                    {"agent": "Reporter", "duration": "7.2s", "status": "✅ Success", "tokens": 2800}
                ]
            }
            
            st.json(trace_data)
            st.success("✅ Execution trace displayed. In production, this connects to LangSmith for detailed tracing.")
        
        # Integration status
        st.subheader("🔗 Integration Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **🟢 Active Integrations:**
            - ✅ LangGraph Framework
            - ✅ Multi-Agent Coordination
            - ✅ Google Gemini API (if configured)
            - ✅ Workflow State Management
            """)
        
        with col2:
            st.markdown("""
            **🟡 Optional Integrations:**
            - ⚠️ AgentOps Monitoring (requires API key)
            - ⚠️ LangSmith Tracing (requires API key)  
            - ⚠️ Production Database (PostgreSQL)
            - ⚠️ Redis Caching (for scale)
            """)
        
        # Configuration info
        st.info("""
        💡 **Configuration Note**: 
        AgentOps and LangSmith tracing require valid API keys in your .env file:
        - `AGENTOPS_API_KEY=your_key_here`
        - `LANGSMITH_API_KEY=your_key_here`
        
        The workflow will function without these keys but with limited monitoring capabilities.
        """)
    
    def add_chat_response(self, response: str):
        """Add a response to chat history (legacy method for compatibility)"""
        # This method is kept for backward compatibility but not used in new workflow tab
        pass
    
    def generate_ai_response(self, prompt: str) -> str:
        """Generate AI response (legacy method for compatibility)"""
        # This method is kept for backward compatibility but not used in new workflow tab
        return "This feature has been moved to the AI Workflow tab."
        
        # Display chat history in a container
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
        
        # Quick action buttons
        st.subheader("⚡ Quick Actions")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📊 Data Summary", key="data_summary_btn"):
                self.add_chat_response("Here's a summary of your energy data analysis...")
        
        with col2:
            if st.button("🎯 Optimization Tips", key="optimization_btn"):
                self.add_chat_response("Based on your data, here are my top optimization recommendations...")
        
        with col3:
            if st.button("📋 ESG Compliance", key="esg_btn"):
                self.add_chat_response("Let me check your ESG compliance status...")
        
        with col4:
            if st.button("🚨 Anomaly Insights", key="anomaly_btn"):
                self.add_chat_response("I've detected several anomalies in your energy consumption patterns...")
        
        # Alternative chat input using text_input and button
        st.subheader("💭 Ask Your Question")
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_input = st.text_input(
                "Type your question here...",
                key="chat_input",
                placeholder="Ask me anything about energy management...",
                label_visibility="collapsed"
            )
        
        with col2:
            send_button = st.button("Send 📤", key="send_btn")
        
        # Process user input
        if send_button and user_input.strip():
            # Add user message
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            # Generate AI response
            with st.spinner("Thinking..."):
                response = self.generate_ai_response(user_input)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            
            # Clear input and rerun to show new messages
            st.rerun()
        
        # Clear chat history
        if st.button("🗑️ Clear Chat History", key="clear_chat_btn"):
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Chat history cleared. How can I help you today?"}
            ]
            st.rerun()
    
    def generate_ai_response(self, prompt: str) -> str:
        """Generate AI response (mock implementation)"""
        # In production, this would use Google Gemini API and RAG with FAISS
        
        prompt_lower = prompt.lower()
        
        if 'energy consumption' in prompt_lower or 'usage' in prompt_lower:
            return """Based on your energy data analysis, I can see several key patterns:

📊 **Current Consumption Overview:**
- Total consumption across all branches: ~180,000 kWh/month
- HVAC systems account for ~55% of total usage
- Lighting represents ~25% of consumption
- Peak usage typically occurs between 2-4 PM on weekdays

💡 **Key Insights:**
- NYC Branch shows 15% higher consumption than average
- Temperature correlation suggests HVAC optimization opportunities
- Weekend consumption is 40% lower, indicating good operational controls

Would you like me to dive deeper into any specific aspect?"""
        
        elif 'esg' in prompt_lower or 'sustainability' in prompt_lower:
            return """Here's your ESG performance summary:

🌱 **Current ESG Metrics:**
- Average ESG Score: 8.2/10 across all branches
- Carbon footprint: ~90 tons CO2/month
- Renewable energy: Currently 0% (opportunity for improvement)

📈 **Improvement Opportunities:**
- Solar panel installation could offset 40% of consumption
- LED upgrades could reduce lighting energy by 30%
- Smart HVAC controls could improve efficiency by 20%

🎯 **Compliance Status:**
- Meeting current regulatory requirements
- On track for 2030 carbon reduction targets
- Recommend quarterly ESG reporting implementation

Need specific guidance on any ESG initiative?"""
        
        elif 'anomaly' in prompt_lower or 'unusual' in prompt_lower:
            return """🚨 **Anomaly Analysis Results:**

I've detected 23 anomalies in your recent energy data:

**High Priority (5 cases):**
- NYC Branch: 40% consumption spike on March 15th
- LA Branch: Unusual weekend consumption pattern
- CHI Branch: HVAC system showing irregular patterns

**Medium Priority (12 cases):**
- Various branches showing minor deviations from expected patterns
- Mostly weather-related variations

**Recommended Actions:**
1. Investigate NYC Branch equipment on March 15th
2. Check LA Branch security/cleaning schedules
3. Schedule HVAC maintenance for CHI Branch

Would you like detailed analysis for any specific anomaly?"""
        
        elif 'cost' in prompt_lower or 'savings' in prompt_lower:
            return """💰 **Cost Analysis & Savings Opportunities:**

**Current Monthly Costs:**
- Estimated energy cost: $21,600/month
- Average cost per kWh: $0.12
- Peak demand charges: ~30% of total bill

**Potential Savings:**
- LED lighting upgrade: $1,200/month (5.5% reduction)
- HVAC optimization: $2,400/month (11% reduction)
- Peak demand management: $1,800/month (8% reduction)
- Solar installation: $3,500/month (16% reduction)

**Total Potential Savings: $8,900/month (41% reduction)**

**ROI Timeline:**
- LED upgrades: 18 months payback
- HVAC optimization: 24 months payback
- Solar installation: 7 years payback

Would you like a detailed cost-benefit analysis for any specific initiative?"""
        
        else:
            return f"""I understand you're asking about: "{prompt}"

As your EnerVision AI Assistant, I can help you with:

🔋 **Energy Management:**
- Consumption analysis and trends
- Peak demand optimization
- Equipment efficiency insights

🌱 **ESG & Sustainability:**
- Carbon footprint tracking
- Renewable energy opportunities
- Compliance monitoring

🎯 **Optimization:**
- Cost reduction strategies
- Operational improvements
- Predictive maintenance

📊 **Data Analysis:**
- Anomaly detection insights
- Performance benchmarking
- Custom reporting

Could you be more specific about what aspect you'd like me to focus on?"""
    
    def add_chat_response(self, response: str):
        """Add a response to chat history"""
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()
    
    def run(self):
        """Main application runner"""
        if not st.session_state.authenticated:
            self.login_page()
        else:
            # Main application header
            st.markdown(f"""
            <div class="main-header">
                <h1>⚡ {st.session_state.company_name} - EnerVision Dashboard</h1>
                <p>Powered by EnerVision Smart Branch Energy Management Platform</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Logout button
            col1, col2, col3 = st.columns([6, 1, 1])
            with col3:
                if st.button("🚪 Logout"):
                    st.session_state.authenticated = False
                    st.rerun()
            
            # Main application tabs
            tabs = st.tabs([
                "📊 Dashboard", 
                "📈 Visualization", 
                "🚨 Anomalies", 
                "🤖 AI Optimization",
                "🔮 Forecasting",
                "📋 Reports", 
                "📧 Work Orders",
                "🔀 AI Workflow"
            ])
            
            with tabs[0]:
                self.dashboard_tab()
            
            with tabs[1]:
                self.visualization_tab()
            
            with tabs[2]:
                self.anomaly_tab()
            
            with tabs[3]:
                self.optimization_tab()
            
            with tabs[4]:
                self.forecasting_tab()
            
            with tabs[5]:
                self.reports_tab()
            
            with tabs[6]:
                self.communication_tab()
            
            with tabs[7]:
                self.workflow_diagram_tab()

# Initialize and run the application
if __name__ == "__main__":
    app = EnerVisionApp()
    app.run()