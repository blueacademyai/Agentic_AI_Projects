# pages/user_dashboard.py
"""
User Dashboard - Main interface for regular users with Professional UI
"""

import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
import time

def load_professional_css():
    """Load professional UI styles for user dashboard"""
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');
    
    /* Professional Color Palette */
    :root {
        --primary-blue: #2563eb;
        --primary-blue-dark: #1d4ed8;
        --primary-blue-light: #3b82f6;
        --secondary-purple: #7c3aed;
        --accent-green: #059669;
        --accent-orange: #d97706;
        --accent-red: #dc2626;
        --gray-50: #f9fafb;
        --gray-100: #f3f4f6;
        --gray-200: #e5e7eb;
        --gray-300: #d1d5db;
        --gray-500: #6b7280;
        --gray-600: #4b5563;
        --gray-700: #374151;
        --gray-800: #1f2937;
        --gray-900: #111827;
        --white: #ffffff;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        --radius-md: 8px;
        --radius-lg: 12px;
        --radius-xl: 16px;
        --radius-2xl: 20px;
    }
    
    /* Global Styling */
    .main {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: linear-gradient(135deg, var(--gray-50) 0%, var(--white) 100%);
    }
    
    /* Professional Headers */
    .dashboard-header {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-purple) 100%);
        padding: 2rem;
        border-radius: var(--radius-2xl);
        color: var(--white);
        margin-bottom: 2rem;
        box-shadow: var(--shadow-xl);
        position: relative;
        overflow: hidden;
    }
    
    .dashboard-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        pointer-events: none;
    }
    
    .dashboard-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        position: relative;
        z-index: 1;
    }
    
    .dashboard-header p {
        font-size: 1.125rem;
        opacity: 0.9;
        position: relative;
        z-index: 1;
    }
    
    /* Enhanced Metric Cards */
    [data-testid="metric-container"] {
        background: linear-gradient(145deg, var(--white), var(--gray-50));
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-xl);
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    [data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }
    
    [data-testid="metric-container"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--primary-blue), var(--secondary-purple));
    }
    
    /* Professional Buttons */
    .stButton > button {
        border-radius: var(--radius-lg);
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        padding: 0.875rem 1.5rem;
        border: 1px solid var(--gray-300);
        background: linear-gradient(145deg, var(--white), var(--gray-50));
        color: var(--gray-700);
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(145deg, var(--primary-blue), var(--primary-blue-dark));
        color: var(--white);
        border-color: var(--primary-blue);
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(145deg, var(--primary-blue), var(--primary-blue-dark));
        color: var(--white);
        border-color: var(--primary-blue);
        box-shadow: var(--shadow-md);
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(145deg, var(--primary-blue-dark), var(--gray-800));
        box-shadow: var(--shadow-lg);
    }
    
    .stButton > button[kind="secondary"] {
        background: linear-gradient(145deg, var(--gray-100), var(--gray-200));
        color: var(--gray-600);
        border-color: var(--gray-300);
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: linear-gradient(145deg, var(--gray-600), var(--gray-700));
        color: var(--white);
    }
    
    /* Transaction Cards */
    .transaction-card {
        background: var(--white);
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .transaction-card:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--primary-blue);
    }
    
    /* Enhanced Forms */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input {
        border-radius: var(--radius-lg);
        border: 2px solid var(--gray-200);
        font-family: 'Inter', sans-serif;
        padding: 0.75rem 1rem;
        background: var(--white);
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--primary-blue);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1), var(--shadow-md);
        outline: none;
    }
    
    /* Enhanced Alerts */
    .stAlert {
        border-radius: var(--radius-lg);
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        box-shadow: var(--shadow-md);
        border: none;
        margin: 1rem 0;
        padding: 1rem 1.25rem;
    }
    
    .stSuccess {
        background: linear-gradient(145deg, #d1fae5, #a7f3d0);
        color: #065f46;
        border-left: 4px solid var(--accent-green);
    }
    
    .stError {
        background: linear-gradient(145deg, #fee2e2, #fecaca);
        color: #991b1b;
        border-left: 4px solid var(--accent-red);
    }
    
    .stWarning {
        background: linear-gradient(145deg, #fef3c7, #fde68a);
        color: #92400e;
        border-left: 4px solid var(--accent-orange);
    }
    
    .stInfo {
        background: linear-gradient(145deg, #dbeafe, #bfdbfe);
        color: #1e40af;
        border-left: 4px solid var(--primary-blue);
    }
    
    /* Section Headers */
    .section-header {
        background: linear-gradient(135deg, var(--gray-50), var(--white));
        border-left: 4px solid var(--primary-blue);
        padding: 1rem 1.5rem;
        border-radius: var(--radius-lg);
        margin: 1.5rem 0 1rem 0;
        box-shadow: var(--shadow-sm);
    }
    
    .section-header h3 {
        color: var(--gray-800);
        font-weight: 600;
        margin: 0;
    }
    
    /* Status Badges */
    .status-badge {
        padding: 0.375rem 0.75rem;
        border-radius: var(--radius-md);
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Quick Actions Panel */
    .quick-actions-panel {
        background: linear-gradient(145deg, var(--white), var(--gray-50));
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-xl);
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
    }
    
    /* Insights Panel */
    .insights-panel {
        background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
        border: 1px solid #bae6fd;
        border-radius: var(--radius-lg);
        padding: 1.25rem;
        margin: 1rem 0;
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        background: var(--white);
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-lg);
        padding: 0.75rem 1rem;
        font-weight: 500;
    }
    
    /* Chat Interface */
    .chat-message-user {
        background: linear-gradient(145deg, #dbeafe, #bfdbfe);
        color: #1e40af;
        padding: 1rem 1.25rem;
        border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
        margin: 0.5rem 0 0.5rem auto;
        max-width: 70%;
        box-shadow: var(--shadow-sm);
        font-weight: 500;
    }
    
    .chat-message-assistant {
        background: linear-gradient(145deg, var(--white), var(--gray-50));
        color: var(--gray-800);
        padding: 1rem 1.25rem;
        border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px;
        margin: 0.5rem auto 0.5rem 0;
        max-width: 70%;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--gray-200);
    }
    
    /* Form Enhancements */
    .stForm {
        background: var(--white);
        border: 1px solid var(--gray-200);
        border-radius: var(--radius-xl);
        padding: 2rem;
        box-shadow: var(--shadow-md);
    }
    
    /* Download Button */
    .stDownloadButton > button {
        background: linear-gradient(145deg, var(--accent-green), #047857);
        color: var(--white);
        border: none;
        border-radius: var(--radius-lg);
        font-weight: 500;
    }
    
    /* Dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--gray-300), transparent);
        margin: 2rem 0;
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .dashboard-header h1 {
            font-size: 2rem;
        }
        
        .dashboard-header {
            padding: 1.5rem;
        }
        
        [data-testid="metric-container"] {
            padding: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# Import utility functions (keeping existing logic)
def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency"""
    return f"${amount:,.2f}"

def create_status_badge(status: str) -> str:
    """Create colored status badge HTML with professional styling"""
    colors = {
        'completed': 'background: linear-gradient(145deg, #059669, #047857); color: white;',
        'pending': 'background: linear-gradient(145deg, #d97706, #b45309); color: white;',
        'failed': 'background: linear-gradient(145deg, #dc2626, #b91c1c); color: white;',
        'flagged': 'background: linear-gradient(145deg, #ea580c, #c2410c); color: white;'
    }
    style = colors.get(status.lower(), 'background: linear-gradient(145deg, #6b7280, #4b5563); color: white;')
    return f'<span class="status-badge" style="{style}">{status.title()}</span>'

def make_api_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None):
    """Make API request to backend (keeping existing logic)"""
    api_base = "http://localhost:8000/api"
    headers = {"Content-Type": "application/json"}
    
    if st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    
    url = f"{api_base}{endpoint}"
    
    try:
        if method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            response = requests.get(url, headers=headers, timeout=10)
        
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def render_user_dashboard(current_page: str, db_manager, config_manager):
    """Render user dashboard based on current page with professional UI"""
    
    # Load professional CSS
    load_professional_css()
    
    if current_page == 'dashboard':
        render_dashboard_overview()
    elif current_page == 'payment':
        render_payment_form()
    elif current_page == 'history':
        render_transaction_history()
    elif current_page == 'chatbot':
        render_chatbot_interface()
    elif current_page == 'profile':
        render_user_profile()
    elif current_page == 'settings':
        render_user_settings()
    else:
        render_dashboard_overview()

def render_dashboard_overview():
    """Render main dashboard overview with professional styling"""
    
    # Professional header
    st.markdown("""
    <div class="dashboard-header">
        <h1>🏠 Dashboard</h1>
        <p>Welcome to your AI-powered payment dashboard</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick stats (keeping existing logic)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Account Balance", "$2,450.00", "+5.2%")
    
    with col2:
        st.metric("This Month", "$1,234.56", "-2.1%")
    
    with col3:
        st.metric("Transactions", "23", "+12")
    
    with col4:
        st.metric("Avg. Risk Score", "2.3/10", "-0.5")
    
    st.markdown("---")
    
    # Recent transactions with professional styling
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <div class="section-header">
            <h3>💳 Recent Transactions</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch recent transactions (keeping existing logic)
        response = make_api_request("/payments?limit=5")

        if response and response.status_code == 200:
            try:
                transactions = response.json() or []
            except Exception:
                transactions = []
            
            if isinstance(transactions, dict) and "transactions" in transactions:
                transactions = transactions["transactions"]
            
            if transactions:
                df = pd.DataFrame(transactions)

                display_data = []
                for _, row in df.iterrows():
                    recipient_info = row.get("recipient_info") if isinstance(row.get("recipient_info"), dict) else {}
                    recipient = recipient_info.get("email", "N/A")

                    display_data.append({
                        "ID": str(row.get("transaction_id", ""))[:12] + "...",
                        "Amount": format_currency(row.get("amount", 0.0)),
                        "Recipient": recipient[:20] + "..." if len(recipient) > 20 else recipient,
                        "Status": row.get("status", "unknown"),
                        "Date": pd.to_datetime(row.get("created_at", datetime.now())).strftime("%m/%d %H:%M")
                    })

                # Display as professional cards
                for transaction in display_data:
                    st.markdown(f"""
                    <div class="transaction-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>{transaction['ID']}</strong><br>
                                <span style="color: #6b7280; font-size: 0.875rem;">{transaction['Recipient']}</span>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-weight: 600; color: #1f2937;">{transaction['Amount']}</div>
                                <div style="font-size: 0.75rem; color: #6b7280;">{transaction['Date']}</div>
                            </div>
                            <div>
                                {create_status_badge(transaction['Status'])}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No recent transactions found.")
        else:
            st.error("Unable to load transactions. Please try again later.")
    
    with col2:
        st.markdown("""
        <div class="quick-actions-panel">
            <h3 style="margin-top: 0; color: #374151;">📊 Quick Actions</h3>
        """, unsafe_allow_html=True)
        
        if st.button("💰 Send Payment", type="primary", use_container_width=True):
            st.session_state.current_page = 'payment'
            st.rerun()
        
        if st.button("📜 View History", type="secondary", use_container_width=True):
            st.session_state.current_page = 'history'
            st.rerun()
        
        if st.button("💬 AI Assistant", type="secondary", use_container_width=True):
            st.session_state.current_page = 'chatbot'
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Account insights with professional styling
        st.markdown("""
        <div class="insights-panel">
            <h4 style="margin-top: 0; color: #1e40af;">📈 Account Insights</h4>
            <div style="margin: 0.75rem 0;">
                <div style="background: rgba(16, 185, 129, 0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem; border-left: 3px solid #10b981;">
                    <small style="color: #065f46;">Your spending is 15% lower this month compared to last month.</small>
                </div>
                <div style="background: rgba(59, 130, 246, 0.1); padding: 0.75rem; border-radius: 8px; border-left: 3px solid #3b82f6;">
                    <small style="color: #1e40af;">All transactions this week have low risk scores!</small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_payment_form():
    """Render payment submission form with professional styling"""
    
    st.markdown("""
    <div class="dashboard-header">
        <h1>💳 New Payment</h1>
        <p>Send secure payments with AI-powered validation</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("payment_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input("Amount ($)", min_value=0.01, max_value=100000.00, value=0.01, step=0.01)
            recipient = st.text_input("Recipient Email", placeholder="recipient@example.com")
            payment_type = st.selectbox("Payment Type", ["transfer", "payment", "bill_pay", "donation"])
        
        with col2:
            # Map friendly category names to backend values (keeping existing logic)
            CATEGORY_MAP = {
                "Utilities": "payment",
                "Groceries": "purchase",
                "Entertainment": "purchase",
                "Healthcare": "payment",
                "Shopping": "purchase",
                "Transfer": "transfer",
                "Other": "refund"
            }

            selected_category = st.selectbox("Category", list(CATEGORY_MAP.keys()))
            category = CATEGORY_MAP[selected_category]
            description = st.text_area("Description (Optional)", placeholder="What is this payment for?")
            priority = st.selectbox("Priority", ["normal", "urgent", "scheduled"])

        # Advanced options with professional styling
        with st.expander("🔧 Advanced Options"):
            send_notification = st.checkbox("Send email notification to recipient", value=True)
            request_confirmation = st.checkbox("Request confirmation before processing", value=False)
            metadata = st.text_area("Additional Notes", placeholder="Any additional information...")
        
        submit_button = st.form_submit_button("💸 Send Payment", type="primary")

        if submit_button:
            # Validation (keeping existing logic)
            if amount <= 0:
                st.error("Please enter a valid amount")
            elif not recipient:
                st.error("Please enter a recipient email")
            else:
                # Prepare payment data (keeping existing logic)
                PAYMENT_METHOD_MAP = {
                    "transfer": "bank_transfer",
                    "payment": "card",
                    "bill_pay": "wallet",
                    "donation": "crypto"
                }

                payment_method = PAYMENT_METHOD_MAP.get(payment_type, "card")

                payment_data = {
                    "amount": amount,
                    "payment_method": payment_method,
                    "category": category,
                    "description": description,
                    "recipient_info": {
                        "email": recipient,
                        "name": ""
                    },
                    "metadata": {
                        "priority": priority,
                        "send_notification": send_notification,
                        "request_confirmation": request_confirmation,
                        "notes": metadata
                    }
                }
                
                with st.spinner("Processing payment..."):
                    response = make_api_request("/payments", "POST", payment_data)
                    
                    if response and response.status_code == 200:
                        result = response.json()
                        st.success(f"Payment submitted successfully!")
                        st.info(f"Transaction ID: {result['transaction_id']}")
                        st.info(f"Status: {result['status']}")
                        
                        # Show risk assessment (keeping existing logic)
                        if 'risk_score' in result:
                            risk_score = result['risk_score']
                            if risk_score < 30:
                                st.success(f"✅ Low Risk Score: {risk_score}/100")
                            elif risk_score < 70:
                                st.warning(f"⚠️ Medium Risk Score: {risk_score}/100")
                            else:
                                st.error(f"🚨 High Risk Score: {risk_score}/100")
                        
                        # Auto-refresh to dashboard after success
                        time.sleep(2)
                        st.session_state.current_page = 'dashboard'
                        st.rerun()
                    
                    else:
                        st.error("Payment failed. Please try again or contact support.")

def render_transaction_history():
    """Render transaction history page with professional styling"""
    
    st.markdown("""
    <div class="dashboard-header">
        <h1>📜 Transaction History</h1>
        <p>View and manage your payment history</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filters (keeping existing logic)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.selectbox("Status", ["All", "completed", "pending", "failed", "flagged"])
    
    with col2:
        date_range = st.selectbox("Date Range", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"])
    
    with col3:
        amount_min = st.number_input("Min Amount", min_value=0.0, value=0.0)
    
    with col4:
        amount_max = st.number_input("Max Amount", min_value=0.0, value=10000.0)
    
    # Fetch transactions (keeping existing logic)
    response = make_api_request("/payments?limit=5")
    
    if response and response.status_code == 200:
        transactions = response.json()
        
        if transactions:
            df = pd.DataFrame(transactions)
            
            # Apply filters (keeping existing logic)
            if status_filter != "All":
                df = df[df['status'] == status_filter]
            
            df = df[(df['amount'] >= amount_min) & (df['amount'] <= amount_max)]
            
            # Date filtering (keeping existing logic)
            if date_range != "All time":
                df['created_at'] = pd.to_datetime(df['created_at'])
                days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
                cutoff_date = datetime.now() - timedelta(days=days_map[date_range])
                df = df[df['created_at'] >= cutoff_date]
            
            if not df.empty:
                # Summary statistics (keeping existing logic)
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Transactions", len(df))
                with col2:
                    st.metric("Total Amount", format_currency(df['amount'].sum()))
                with col3:
                    st.metric("Average Amount", format_currency(df['amount'].mean()))
                with col4:
                    avg_risk = df['risk_score'].mean() if 'risk_score' in df.columns else 0
                    st.metric("Avg Risk Score", f"{avg_risk:.1f}/10")
                
                st.markdown("---")
                
                # Display transactions (keeping existing logic)
                for _, row in df.iterrows():
                    recipient = row.get('recipient_info', {}).get('email', 'N/A')
                    risk_score = row.get('risk_score', 'N/A')

                    with st.expander(f"{row['transaction_id']} - {format_currency(row['amount'])} - {row['status'].title()}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Amount:** {format_currency(row['amount'])}")
                            st.write(f"**Recipient:** {recipient}")
                            payment_type = row.get('payment_type') or row.get('payment_method', 'N/A')
                            st.write(f"**Type:** {payment_type}")
                            st.write(f"**Category:** {row.get('category', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Status:** {row['status']}")
                            st.write(f"**Risk Score:** {risk_score}/10")
                            st.write(f"**Created:** {pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')}")
                            if row.get('description'):
                                st.write(f"**Description:** {row['description']}")

                # Download option (keeping existing logic)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv,
                    file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            else:
                st.info("No transactions found matching your filters.")
        
        else:
            st.info("No transactions found.")
    
    else:
        st.error("Unable to load transaction history.")

def render_chatbot_interface():
    """Render AI chatbot interface with professional styling"""
    
    st.markdown("""
    <div class="dashboard-header">
        <h1>💬 AI Banking Assistant</h1>
        <p>Get help with payments, policies, and banking questions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize chat state (keeping existing logic)
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Hello! I'm your AI banking assistant. How can I help you today?", "id": str(uuid.uuid4())}
        ]
    if 'chat_session_id' not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())

    # Fetch quick suggestions from backend (keeping existing logic)
    suggestions = []
    response = make_api_request("/chatbot/suggestions")
    if response and response.status_code == 200:
        suggestions = response.json().get("quick_suggestions", [])

    # Chat container with professional styling
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="chat-message-user">
                    {msg['content']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-message-assistant">
                    {msg['content']}
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='clear:both; margin: 2rem 0;'></div>", unsafe_allow_html=True)

    # Chat input form (keeping existing logic)
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask me anything about payments, policies, or banking...", key="user_input")
        send_button = st.form_submit_button("Send", type="primary")
        clear_button = st.form_submit_button("Clear Chat", type="secondary")

        if send_button and user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input, "id": str(uuid.uuid4())})
            
            typing_msg = st.empty()
            typing_msg.markdown("🤖 AI is typing...")

            response = make_api_request("/chatbot/", "POST", {
                "message": user_input,
                "session_id": st.session_state.chat_session_id
            })
            typing_msg.empty()

            if response and response.status_code == 200:
                ai_response = response.json().get("response", "Sorry, I couldn't process your request.")
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response, "id": str(uuid.uuid4())})
            else:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "I'm experiencing technical difficulties. Please try again later.",
                    "id": str(uuid.uuid4())
                })
            st.rerun()

        if clear_button:
            st.session_state.chat_history = [
                {"role": "assistant", "content": "Hello! I'm your AI banking assistant. How can I help you today?", "id": str(uuid.uuid4())}
            ]
            st.session_state.chat_session_id = str(uuid.uuid4())
            st.rerun()

    # Quick suggestion buttons with professional styling
    if suggestions:
        st.markdown("""
        <div class="section-header">
            <h3>Quick Questions</h3>
        </div>
        """, unsafe_allow_html=True)
        
        for suggestion in suggestions:
            if st.button(suggestion, key=f"suggestion_{suggestion}"):
                st.session_state.chat_history.append({"role": "user", "content": suggestion, "id": str(uuid.uuid4())})
                st.rerun()

def submit_chat_feedback(msg_id: str, rating: int):
    """Submit feedback for a specific AI message (keeping existing logic)"""
    if 'chat_session_id' not in st.session_state:
        return
    
    make_api_request("/chatbot/feedback", "POST", {
        "session_id": st.session_state.chat_session_id,
        "rating": rating,
        "feedback": f"Feedback for message {msg_id}"
    })

def render_user_profile():
    """Render user profile management with professional styling"""
    
    st.markdown("""
    <div class="dashboard-header">
        <h1>👤 User Profile</h1>
        <p>Manage your account information and security settings</p>
    </div>
    """, unsafe_allow_html=True)
    
    user_data = st.session_state.user_data
    
    # Profile information with professional styling
    with st.form("profile_form"):
        st.markdown("""
        <div class="section-header">
            <h3>Personal Information</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name", value=user_data.get('full_name', ''))
            email = st.text_input("Email Address", value=user_data.get('email', ''), disabled=True)
        
        with col2:
            phone = st.text_input("Phone Number", value=user_data.get('phone', ''))
        
        st.markdown("""
        <div class="section-header" style="margin-top: 2rem;">
            <h3>Security</h3>
        </div>
        """, unsafe_allow_html=True)
        
        change_password = st.checkbox("Change Password")
        
        if change_password:
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
        
        update_button = st.form_submit_button("Update Profile", type="primary")
        
        if update_button:
            st.success("Profile updated successfully!")

def render_user_settings():
    """Render user settings and preferences with professional styling"""
    
    st.markdown("""
    <div class="dashboard-header">
        <h1>⚙️ Settings</h1>
        <p>Customize your preferences and privacy settings</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Notification preferences (keeping existing logic)
    st.markdown("""
    <div class="section-header">
        <h3>📧 Notification Preferences</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        email_notifications = st.checkbox("Email notifications", value=True)
        transaction_alerts = st.checkbox("Transaction alerts", value=True)
        security_alerts = st.checkbox("Security alerts", value=True)
    
    with col2:
        policy_updates = st.checkbox("Policy updates", value=False)
        marketing_messages = st.checkbox("Marketing messages", value=False)
        mobile_notifications = st.checkbox("Mobile notifications", value=True)
    
    # Display preferences (keeping existing logic)
    st.markdown("""
    <div class="section-header">
        <h3>🎨 Display Preferences</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        theme = st.selectbox("Theme", ["Light", "Dark", "Auto"])
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP"])
    
    with col2:
        language = st.selectbox("Language", ["English", "Spanish", "French"])
        timezone = st.selectbox("Timezone", ["UTC-5 (EST)", "UTC-8 (PST)", "UTC (GMT)"])
    
    # Privacy settings (keeping existing logic)
    st.markdown("""
    <div class="section-header">
        <h3>🔒 Privacy Settings</h3>
    </div>
    """, unsafe_allow_html=True)
    
    data_sharing = st.checkbox("Allow data sharing for improved AI assistance", value=False)
    analytics = st.checkbox("Share anonymous usage analytics", value=True)
    
    # Save settings
    if st.button("💾 Save Settings", type="primary"):
        st.success("Settings saved successfully!")
    
    # Danger zone with professional styling
    st.markdown("---")
    st.markdown("""
    <div style="background: linear-gradient(145deg, #fef2f2, #fee2e2); border: 1px solid #fecaca; border-radius: 12px; padding: 1.5rem; margin: 2rem 0;">
        <h3 style="color: #991b1b; margin-top: 0;">⚠️ Danger Zone</h3>
        <p style="color: #7f1d1d; margin-bottom: 1rem;">These actions are irreversible. Please proceed with caution.</p>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Delete All Data", type="secondary"):
            st.warning("This action cannot be undone!")
    
    with col2:
        if st.button("🚪 Delete Account", type="secondary"):
            st.error("Account deletion requires email confirmation.")
    
    st.markdown("</div>", unsafe_allow_html=True)