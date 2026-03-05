"""
Main Streamlit Application
AI-Powered Payment Processing System Frontend
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
import asyncio
import logging
from typing import Dict, Any, Optional
import sqlite3
from pathlib import Path
import textwrap

# Configure page
st.set_page_config(
    page_title="AI Payment System",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
def load_custom_css():
    st.markdown("""
    <style>
    /* Import modern fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global styling */
    .main {
        padding-top: 2rem;
    }
    
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Modern sidebar styling */
    .css-1d391kg {
        background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 100%);
        border-right: 1px solid #e2e8f0;
    }
    
    /* Navigation buttons styling */
    .stButton > button {
        width: 100%;
        height: 3.5rem; /* increase height */
        border-radius: 8px;
        border: none;
        background: linear-gradient(145deg, #ffffff, #f1f5f9);
        box-shadow: 2px 2px 5px #d1d5db, -2px -2px 5px #ffffff;
        color: #374151;
        font-size:1.1rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
        margin-bottom: 0.5rem;
        padding: 0.5rem 1rem;
    }
    
    .stButton > button:hover {
        background: linear-gradient(145deg, #3b82f6, #1d4ed8);
        color: white;
        box-shadow: 4px 4px 10px #d1d5db, -4px -4px 10px #ffffff;
        transform: translateY(-1px);
    }
    
    .stButton > button:active {
        transform: translateY(1px);
        box-shadow: 1px 1px 3px #d1d5db;
    }
    
    /* Primary button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(145deg, #3b82f6, #1d4ed8);
        color: white;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(145deg, #1d4ed8, #1e40af);
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    .main-header p {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Status indicators */
    .status-online {
        color: #10b981;
        font-weight: 600;
    }
    
    .status-offline {
        color: #ef4444;
        font-weight: 600;
    }
    
    /* Form styling */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #e5e7eb;
        font-family: 'Inter', sans-serif;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* Success/Error messages */
    .stAlert {
        border-radius: 10px;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar section headers */
    .sidebar-section {
        background: rgba(59, 130, 246, 0.1);
        padding: 0.75rem;
        border-radius: 8px;
        margin: 1rem 0 0.5rem 0;
        font-weight: 600;
        color: #1e40af;
        font-family: 'Inter', sans-serif;
    }
    
    /* Clean dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #e5e7eb, transparent);
        margin: 1.5rem 0;
    }
    
    /* Metrics styling */
    [data-testid="metric-container"] {
        background: linear-gradient(145deg, #ffffff, #f8fafc);
        border: 1px solid #e5e7eb;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* Tabs container spacing */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.75rem; /* space between tabs */
        justify-content: center; /* center align */
        margin-bottom: 1.5rem;
    }

    /* Tab default style */
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 2rem;
        border-radius: 8px;
        background: #f1f5f9;
        color: #374151;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 1rem;
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
        cursor: pointer;
    }

    /* Hover effect */
    .stTabs [data-baseweb="tab"]:hover {
        background: linear-gradient(145deg, #3b82f6, #1d4ed8);
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }

    /* Active tab (selected) */
    .stTabs [aria-selected="true"] {
        background: linear-gradient(145deg, #3b82f6, #1d4ed8);
        color: white !important;
        border: none;
        box-shadow: 0 6px 12px rgba(59,130,246,0.25);
    }

    /* Banking Summary Styles */
    .summary-container {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem 0;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    
    .summary-title {
        color: #1e40af;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
        text-align: center;
        font-family: 'Inter', sans-serif;
    }
    
    .comparison-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        margin-top: 1.5rem;
    }
    
    .comparison-section {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        border-left: 4px solid #3b82f6;
    }
    
    .section-title {
        color: #374151;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1rem;
        font-family: 'Inter', sans-serif;
    }
    
    .feature-list {
        color: #4b5563;
        line-height: 1.6;
        font-family: 'Inter', sans-serif;
    }
    
    .feature-list li {
        margin-bottom: 0.5rem;
    }
    
    .highlight-box {
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
        text-align: center;
        font-weight: 600;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .main-header {
            padding: 1.5rem;
        }
        
        .comparison-grid {
            grid-template-columns: 1fr;
            gap: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api")

class DatabaseManager:
    """Database manager for frontend operations"""
    
    def __init__(self, db_path: str = "../data/payment_system.db"):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure DB path exists; don't overwrite backend schema if present."""
        db_path_obj = Path(self.db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # If backend tables already exist, do nothing
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        if {'users', 'transactions'} <= existing:
            conn.close()
            return
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                recipient TEXT,
                payment_type TEXT,
                category TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending',
                risk_score REAL DEFAULT 0.0,
                payment_method TEXT DEFAULT 'card',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                email_notifications BOOLEAN DEFAULT 1,
                sms_notifications BOOLEAN DEFAULT 0,
                in_app_notifications BOOLEAN DEFAULT 1,
                transaction_alerts BOOLEAN DEFAULT 1,
                security_alerts BOOLEAN DEFAULT 1,
                policy_updates BOOLEAN DEFAULT 0,
                marketing_messages BOOLEAN DEFAULT 0,
                quiet_hours_start TEXT,
                quiet_hours_end TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS in_app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'info',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

class ConfigManager:
    """Configuration manager for application settings"""
    
    def __init__(self):
        self.config = {
            'api_base_url': API_BASE,
            'gemini_api_key': os.getenv('GEMINI_API_KEY'),
            'langsmith_api_key': os.getenv('LANGSMITH_API_KEY'),
            'app_name': 'AI Payment System',
            'app_version': '1.0.0',
            'max_transaction_amount': 100000,
            'default_currency': 'USD'
        }
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)

# Initialize managers
@st.cache_resource
def get_database_manager():
    return DatabaseManager()

@st.cache_resource
def get_config_manager():
    return ConfigManager()

# Initialize session state
def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'user_data' not in st.session_state:
        st.session_state.user_data = {}
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'dashboard'
    
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'

# Authentication functions
def make_api_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None, auth: bool = False):
    """Make API request to backend"""
    headers = {"Content-Type": "application/json"}
    
    if auth and st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        
        return response
    
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def render_login_form():
    """Render login/signup form"""
    
    # Main header for login page
    st.markdown("""
    <div class="main-header">
        <h1>🏦 AI Payment System</h1>
        <p>Secure, Intelligent, and Lightning Fast Payment Processing</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.markdown("#### Sign In to Your Account")
        
        with st.form("login_form"):
            email = st.text_input("Email Address", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            remember_me = st.checkbox("Remember me")
            
            col1, col2 = st.columns(2)
            
            with col1:
                login_btn = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            with col2:
                if st.form_submit_button("Forgot Password?", type="secondary", use_container_width=True):
                    st.info("Password reset functionality coming soon!")
            
            if login_btn:
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    with st.spinner("Signing in..."):
                        response = make_api_request("/auth/login", "POST", {
                            "email": email,
                            "password": password
                        })
                        
                        if response and response.status_code == 200:
                            data = response.json()
                            st.session_state.authenticated = True
                            st.session_state.access_token = data["access_token"]
                            st.session_state.user_data = data["user"]
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid credentials. Please try again.")
    
    with tab2:
        st.markdown("#### Create New Account")
        
        with st.form("signup_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                full_name = st.text_input("Full Name", placeholder="John Doe")
                email = st.text_input("Email Address", placeholder="john@example.com")
            
            with col2:
                phone = st.text_input("Phone Number", placeholder="+1234567890")
                role = st.selectbox("Account Type", ["user", "admin"], help="Select user for personal account")
            
            password = st.text_input("Password", type="password", help="Minimum 8 characters")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            terms_accepted = st.checkbox("I agree to the Terms of Service and Privacy Policy")
            
            signup_btn = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            
            if signup_btn:
                if not all([full_name, email, password, confirm_password]):
                    st.error("Please fill in all required fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif not terms_accepted:
                    st.error("Please accept the Terms of Service")
                else:
                    with st.spinner("Creating account..."):
                        response = make_api_request("/auth/signup", "POST", {
                            "email": email,
                            "password": password,
                            "full_name": full_name,
                            "phone": phone,
                            "role": role
                        })
                        
                        if response and response.status_code == 201:
                            st.success("Account created successfully! Please check your email for verification.")
                            st.info("You can now sign in with your credentials.")
                        else:
                            error_msg = "Registration failed"
                            if response:
                                try:
                                    error_data = response.json()
                                    error_msg = error_data.get("detail", error_msg)
                                except:
                                    pass
                            st.error(error_msg)

def render_sidebar():
    """Render clean sidebar without title"""
    
    with st.sidebar:
        # User info section (no title, just content)
        user_data = st.session_state.user_data
        
        st.markdown("""
        <div class="sidebar-section">
            👤 Account
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Name:** {user_data.get('full_name', 'N/A')}")
        st.write(f"**Role:** {user_data.get('role', 'user').title()}")
        st.write(f"**Email:** {user_data.get('email', 'N/A')}")
        
        # Navigation
        st.markdown("""
        <div class="sidebar-section">
            🧭 Navigation
        </div>
        """, unsafe_allow_html=True)
        
        if user_data.get('role') == 'admin':
            # Admin navigation
            nav_options = {
                'dashboard': '🏠 Dashboard',
                'admin_transactions': '💳 All Transactions',
                'admin_users': '👥 Users',
                'admin_analytics': '📊 Analytics',
                'admin_ai_logs': '🤖 AI Logs',
                'admin_policies': '📋 Policies',
                'admin_settings': '⚙️ System Settings'
            }
        else:
            # User navigation
            nav_options = {
                'dashboard': '🏠 Dashboard',
                'payment': '💳 New Payment',
                'history': '📜 History',
                'chatbot': '💬 AI Assistant',
                'profile': '👤 Profile',
                'settings': '⚙️ Settings'
            }
        
        for key, label in nav_options.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.current_page = key
                st.rerun()
        
        # Quick actions
        st.markdown("""
        <div class="sidebar-section">
            ⚡ Quick Actions
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("💰 Quick Pay", type="secondary", use_container_width=True):
            st.session_state.current_page = 'payment'
            st.rerun()
        
        if st.button("📊 Reports", type="secondary", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()
        
        # Settings
        st.markdown("""
        <div class="sidebar-section">
            ⚙️ Settings
        </div>
        """, unsafe_allow_html=True)
        
        # Theme selector
        theme = st.selectbox("Theme", ["light", "dark"], key="theme_selector")
        if theme != st.session_state.theme:
            st.session_state.theme = theme
        
        # System status
        st.markdown("""
        <div class="sidebar-section">
            📊 System Status
        </div>
        """, unsafe_allow_html=True)
        
        # Check API health
        try:
            health_response = make_api_request("/health")
            if health_response and health_response.status_code == 200:
                st.markdown('<span class="status-online">🟢 Online</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-offline">🔴 Offline</span>', unsafe_allow_html=True)
        except:
            st.markdown('<span class="status-offline">🔴 Connection Error</span>', unsafe_allow_html=True)
        
        # Help and support
        st.markdown("""
        <div class="sidebar-section">
            🆘 Support
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("💬 Chat Support", use_container_width=True):
            st.session_state.current_page = 'chatbot'
            st.rerun()
        
        st.markdown("📧 support@aibanking.com")
        st.markdown("📞 1-800-AI-BANK")
        
        # Logout
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            # Clear session state
            st.session_state.authenticated = False
            st.session_state.access_token = None
            st.session_state.user_data = {}
            st.session_state.current_page = 'dashboard'
            st.success("Logged out successfully!")
            st.rerun()

def render_main_header():
    """Render the main page header with title"""
    current_page = st.session_state.current_page
    user_data = st.session_state.user_data
    
    page_titles = {
        'dashboard': 'Dashboard Overview',
        'payment': 'Send Payment',
        'history': 'Transaction History',
        'chatbot': 'AI Assistant',
        'profile': 'My Profile',
        'settings': 'Settings',
        'admin_transactions': 'Transaction Management',
        'admin_users': 'User Management',
        'admin_analytics': 'Analytics & Reports',
        'admin_ai_logs': 'AI Operations',
        'admin_policies': 'Policy Management',
        'admin_settings': 'System Settings'
    }
    
    page_title = page_titles.get(current_page, 'AI Payment System')
    
    st.markdown(f"""
    <div class="main-header">
        <h1>🏦 AI Payment System</h1>
        <p>{page_title} - Welcome back, {user_data.get('full_name', 'User')}!</p>
    </div>
    """, unsafe_allow_html=True)

def render_banking_summary():
    """Render a modern, user-friendly banking system summary using Streamlit components"""
    
    st.markdown("### 🏦 Traditional Banking vs AI-Powered Payment Processing")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏛️ Traditional Banking")
        st.markdown("""
        - Checking & savings accounts  
        - Debit & credit cards  
        - Online & mobile banking  
        - Loans, mortgages, and investments  
        - Secure transactions & account protection  
        - Branch network & ATMs for in-person services  
        - Customer support via phone, email, and chat
        """)
        st.markdown("**Customer Benefits:**")
        st.markdown("""
        - Trusted financial institution  
        - Safe storage of funds  
        - Access to a wide range of products  
        - Convenient account access & bill payment
        """)

    with col2:
        st.subheader("🤖 AI-Powered Banking (This System)")
        st.markdown("""
        - Smart payments with AI risk assessment  
        - Real-time account insights & alerts  
        - Integrated AI assistant for support  
        - Automated compliance monitoring  
        - Modern, responsive interface  
        - Faster and smarter transaction processing
        """)
        st.markdown("**Customer Benefits:**")
        st.markdown("""
        - Predictive fraud prevention  
        - 24/7 AI customer support  
        - Intelligent financial recommendations  
        - Enhanced convenience & efficiency
        """)

    st.info(
        "💡 Both systems provide secure account management and transactions, "
        "but AI-powered banking adds intelligent insights, faster processing, "
        "and personalized support for a smarter banking experience!"
    )


def render_notifications():
    """Render notifications"""
    
    if st.session_state.notifications:
        for i, notification in enumerate(st.session_state.notifications):
            if notification['type'] == 'success':
                st.success(notification['message'])
            elif notification['type'] == 'error':
                st.error(notification['message'])
            elif notification['type'] == 'warning':
                st.warning(notification['message'])
            else:
                st.info(notification['message'])
        
        # Clear notifications after displaying
        st.session_state.notifications = []

def main():
    """Main application function"""
    
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Get managers
    db_manager = get_database_manager()
    config_manager = get_config_manager()
    
    # Check authentication
    if not st.session_state.authenticated:
        render_login_form()
        return
    
    # Render main header (title is here now)
    render_main_header()
    
    
    # Render sidebar (clean, no title)
    render_sidebar()
    
    # Render notifications
    render_notifications()
    
    # Main content area
    current_page = st.session_state.current_page
    user_role = st.session_state.user_data.get('role', 'user')
    
    try:
        if user_role == 'admin':
            # Admin interface
            try:
                from pages.admin_dashboard import (
                    render_admin_dashboard,
                    render_admin_transactions,
                    render_admin_users,
                    render_admin_analytics,
                    render_admin_ai_logs,
                    render_admin_policies,
                    render_admin_settings
                )

                # Route admin pages
                if current_page == 'dashboard':
                    render_admin_dashboard(db_manager, config_manager)
                elif current_page == 'admin_transactions':
                    render_admin_transactions(db_manager, config_manager)
                elif current_page == 'admin_users':
                    render_admin_users(db_manager, config_manager)
                elif current_page == 'admin_analytics':
                    render_admin_analytics(db_manager, config_manager)
                elif current_page == 'admin_ai_logs':
                    render_admin_ai_logs(db_manager, config_manager)
                elif current_page == 'admin_policies':
                    render_admin_policies(db_manager, config_manager)
                elif current_page == 'admin_settings':
                    render_admin_settings(db_manager, config_manager)
                else:
                    render_admin_dashboard(db_manager, config_manager)

            except ImportError:
                # Fallback admin interface
                st.markdown("### 👨‍💼 Admin Dashboard")
                st.info("Admin features are loading. Some functionality may be limited.")

                # Show basic admin stats
                stats = get_basic_admin_stats(db_manager)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Users", stats.get('users', 0))
                with col2:
                    st.metric("Total Transactions", stats.get('transactions', 0))
                with col3:
                    st.metric("System Status", "Online")

        else:
            # User interface
            try:
                from pages.user_dashboard import render_user_dashboard
                render_user_dashboard(current_page, db_manager, config_manager)
            except ImportError:
                # Fallback user interface
                if current_page == 'dashboard':
                    render_default_user_dashboard(db_manager, config_manager)
                elif current_page == 'payment':
                    render_default_payment_form()
                elif current_page == 'history':
                    render_default_transaction_history(db_manager)
                else:
                    st.info(f"The {current_page} page is currently being developed.")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.error(f"Application error: {str(e)}")
    
    # Render banking summary on dashboard pages
    if st.session_state.current_page == 'dashboard':
        render_banking_summary()

def render_default_user_dashboard(db_manager, config_manager):
    """Fallback user dashboard"""
    st.markdown("### 📊 Your Dashboard")
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Account Balance",
            value="$12,345.67",
            delta="$234.50"
        )
    
    with col2:
        st.metric(
            label="This Month",
            value="$2,543.21",
            delta="-$123.45"
        )
    
    with col3:
        st.metric(
            label="Transactions",
            value="47",
            delta="12"
        )
    
    with col4:
        st.metric(
            label="Security Score",
            value="98%",
            delta="2%"
        )
    
    # Recent activity
    st.markdown("### 📈 Recent Activity")
    st.info("Connect to view your recent transactions and AI insights.")


def render_default_payment_form():
    """Fallback payment form"""
    st.markdown("### 💳 Send Payment")
    
    with st.form("payment_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            recipient = st.text_input("Recipient", placeholder="Enter email or phone")
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
        
        with col2:
            payment_method = st.selectbox("Payment Method", ["Credit Card", "Bank Account", "Digital Wallet"])
            category = st.selectbox("Category", ["Personal", "Business", "Bills", "Other"])
        
        description = st.text_area("Description (Optional)", placeholder="What's this payment for?")
        
        if st.form_submit_button("Send Payment", type="primary", use_container_width=True):
            if recipient and amount > 0:
                st.success(f"Payment of ${amount:.2f} to {recipient} initiated successfully!")
                st.info("This is a demo - no actual payment was processed.")
            else:
                st.error("Please fill in required fields.")


def render_default_transaction_history(db_manager):
    """Fallback transaction history"""
    st.markdown("### 📜 Transaction History")
    
    # Sample data for demo
    import pandas as pd
    from datetime import datetime, timedelta
    
    sample_data = {
        'Date': [
            datetime.now() - timedelta(days=1),
            datetime.now() - timedelta(days=3),
            datetime.now() - timedelta(days=7),
            datetime.now() - timedelta(days=10),
            datetime.now() - timedelta(days=15)
        ],
        'Recipient': ['Coffee Shop', 'John Doe', 'Utility Company', 'Amazon', 'Restaurant'],
        'Amount': [-4.50, -250.00, -89.32, -156.78, -42.50],
        'Status': ['Completed', 'Completed', 'Completed', 'Completed', 'Completed'],
        'Category': ['Food', 'Personal', 'Bills', 'Shopping', 'Food']
    }
    
    df = pd.DataFrame(sample_data)
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    st.dataframe(df, use_container_width=True)
    
    st.info("This is sample data. Connect to your account to view actual transactions.")


def get_basic_admin_stats(db_manager):
    """Fallback function for basic admin stats"""
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = cursor.fetchone()[0]

        conn.close()

        return {
            'users': user_count,
            'transactions': transaction_count
        }
    except Exception:
        return {'users': 0, 'transactions': 0}


if __name__ == "__main__":
    main()