"""
Utility Functions
Common utility functions used across the frontend
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import csv
import io
import base64
from typing import Dict, Any, List, Optional, Union
import hashlib
import uuid
import re

# ===================================================================
# Data Processing Utilities
# ===================================================================

def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency"""
    if currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def format_date(date_input: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:
    """Format date string or datetime object"""
    if isinstance(date_input, str):
        try:
            date_obj = pd.to_datetime(date_input)
            return date_obj.strftime(format_str)
        except:
            return date_input
    elif isinstance(date_input, datetime):
        return date_input.strftime(format_str)
    else:
        return str(date_input)

def format_datetime(datetime_input: Union[str, datetime], format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime string or datetime object"""
    return format_date(datetime_input, format_str)

def calculate_time_ago(timestamp: Union[str, datetime]) -> str:
    """Calculate human-readable time ago"""
    if isinstance(timestamp, str):
        timestamp = pd.to_datetime(timestamp)
    
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def safe_json_parse(json_string: str, default: Any = None) -> Any:
    """Safely parse JSON string"""
    try:
        return json.loads(json_string) if json_string else default
    except (json.JSONDecodeError, TypeError):
        return default

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe downloads"""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return sanitized.strip()

# ===================================================================
# UI Helper Functions
# ===================================================================

def create_metric_card(title: str, value: str, delta: str = None, delta_color: str = "normal"):
    """Create a styled metric card"""
    delta_html = ""
    if delta:
        color = "green" if delta_color == "normal" else "red"
        delta_html = f'<span style="color: {color}; font-size: 12px;">{delta}</span>'
    
    st.markdown(f"""
    <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid #e0e0e0; background: white;">
        <h4 style="margin: 0; color: #666;">{title}</h4>
        <h2 style="margin: 0.5rem 0 0 0;">{value}</h2>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def create_status_badge(status: str) -> str:
    """Create colored status badge HTML"""
    colors = {
        'approved': '#28a745',
        'success': '#28a745',
        'completed': '#28a745',
        'pending': '#ffc107',
        'processing': '#17a2b8',
        'rejected': '#dc3545',
        'failed': '#dc3545',
        'cancelled': '#6c757d',
        'flagged': '#fd7e14'
    }
    
    color = colors.get(status.lower(), '#6c757d')
    return f'<span style="background-color: {color}; color: white; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;">{status.title()}</span>'

def create_progress_bar(value: float, max_value: float = 100, label: str = ""):
    """Create a progress bar"""
    percentage = min((value / max_value) * 100, 100)
    
    st.markdown(f"""
    <div style="margin: 0.5rem 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
            <span>{label}</span>
            <span>{value:.1f}/{max_value}</span>
        </div>
        <div style="width: 100%; background-color: #e0e0e0; border-radius: 0.25rem; height: 0.5rem;">
            <div style="width: {percentage}%; background-color: #007bff; border-radius: 0.25rem; height: 100%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def show_loading_spinner(message: str = "Loading..."):
    """Show loading spinner with message"""
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem;">
        <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
        <p style="margin-top: 1rem;">{message}</p>
    </div>
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    """, unsafe_allow_html=True)

# ===================================================================
# Chart and Visualization Utilities
# ===================================================================

def create_line_chart(data: pd.DataFrame, x: str, y: str, title: str = ""):
    """Create a line chart with Plotly"""
    fig = px.line(data, x=x, y=y, title=title)
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def create_bar_chart(data: pd.DataFrame, x: str, y: str, title: str = ""):
    """Create a bar chart with Plotly"""
    fig = px.bar(data, x=x, y=y, title=title)
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def create_pie_chart(data: pd.DataFrame, values: str, names: str, title: str = ""):
    """Create a pie chart with Plotly"""
    fig = px.pie(data, values=values, names=names, title=title)
    fig.update_layout(
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def create_gauge_chart(value: float, max_value: float = 100, title: str = ""):
    """Create a gauge chart for metrics like risk scores"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        gauge = {
            'axis': {'range': [None, max_value]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, max_value * 0.3], 'color': "lightgray"},
                {'range': [max_value * 0.3, max_value * 0.7], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_value * 0.8
            }
        }
    ))
    fig.update_layout(height=300)
    return fig

# ===================================================================
# Data Export/Import Utilities
# ===================================================================

def export_dataframe_to_csv(df: pd.DataFrame, filename: str = "export.csv"):
    """Export dataframe to CSV download"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{sanitize_filename(filename)}">Download CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_data_to_json(data: Any, filename: str = "export.json"):
    """Export data to JSON download"""
    json_str = json.dumps(data, indent=2, default=str)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:file/json;base64,{b64}" download="{sanitize_filename(filename)}">Download JSON</a>'
    st.markdown(href, unsafe_allow_html=True)

def create_download_button(data: str, filename: str, mime_type: str = "text/plain", label: str = "Download"):
    """Create a download button for any data"""
    st.download_button(
        label=label,
        data=data,
        file_name=sanitize_filename(filename),
        mime=mime_type
    )

# ===================================================================
# Session State Management
# ===================================================================

def init_session_state(defaults: Dict[str, Any]):
    """Initialize session state with default values"""
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def clear_session_state(keys: List[str] = None):
    """Clear specific keys or all session state"""
    if keys:
        for key in keys:
            if key in st.session_state:
                del st.session_state[key]
    else:
        st.session_state.clear()

def get_session_value(key: str, default: Any = None) -> Any:
    """Safely get session state value with default"""
    return st.session_state.get(key, default)

def set_session_value(key: str, value: Any):
    """Set session state value"""
    st.session_state[key] = value

# ===================================================================
# Notification and Alert Utilities
# ===================================================================

def show_success_message(message: str, duration: int = 5):
    """Show success message with auto-dismiss"""
    success_placeholder = st.empty()
    success_placeholder.success(message)
    # Note: Auto-dismiss would require JavaScript in a real implementation

def show_error_message(message: str, details: str = None):
    """Show error message with optional details"""
    st.error(message)
    if details:
        with st.expander("Error Details"):
            st.code(details)

def show_warning_message(message: str, dismissible: bool = True):
    """Show warning message"""
    st.warning(message)

def show_info_message(message: str):
    """Show info message"""
    st.info(message)

def create_notification_toast(message: str, notification_type: str = "info"):
    """Create a toast notification (placeholder for future implementation)"""
    if notification_type == "success":
        st.success(message)
    elif notification_type == "error":
        st.error(message)
    elif notification_type == "warning":
        st.warning(message)
    else:
        st.info(message)

# ===================================================================
# Form Validation Utilities
# ===================================================================

def validate_required_fields(form_data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """Validate required fields and return list of missing fields"""
    missing_fields = []
    for field in required_fields:
        if not form_data.get(field) or (isinstance(form_data[field], str) and not form_data[field].strip()):
            missing_fields.append(field)
    return missing_fields

def validate_email_format(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) if email else False

def validate_phone_format(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return False
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    # Check if it's between 10-15 digits
    return 10 <= len(digits_only) <= 15

def validate_amount(amount: Union[str, float], min_amount: float = 0.01, max_amount: float = 100000) -> Dict[str, Any]:
    """Validate transaction amount"""
    try:
        amount_float = float(amount) if isinstance(amount, str) else amount
        
        if amount_float < min_amount:
            return {"valid": False, "error": f"Amount must be at least {format_currency(min_amount)}"}
        
        if amount_float > max_amount:
            return {"valid": False, "error": f"Amount cannot exceed {format_currency(max_amount)}"}
        
        return {"valid": True, "amount": amount_float}
    
    except (ValueError, TypeError):
        return {"valid": False, "error": "Please enter a valid amount"}

# ===================================================================
# Data Processing and Analysis
# ===================================================================

def calculate_transaction_stats(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics from transaction data"""
    if not transactions:
        return {
            "total_count": 0,
            "total_amount": 0,
            "average_amount": 0,
            "success_rate": 0,
            "risk_distribution": {}
        }
    
    df = pd.DataFrame(transactions)
    
    total_count = len(df)
    total_amount = df['amount'].sum() if 'amount' in df.columns else 0
    average_amount = df['amount'].mean() if 'amount' in df.columns else 0
    
    # Calculate success rate
    successful = len(df[df['status'] == 'approved']) if 'status' in df.columns else 0
    success_rate = (successful / total_count * 100) if total_count > 0 else 0
    
    # Risk distribution
    risk_distribution = {}
    if 'risk_score' in df.columns:
        risk_counts = df['risk_score'].value_counts().to_dict()
        risk_distribution = {str(k): v for k, v in risk_counts.items()}
    
    return {
        "total_count": total_count,
        "total_amount": float(total_amount),
        "average_amount": float(average_amount),
        "success_rate": float(success_rate),
        "risk_distribution": risk_distribution
    }

def group_transactions_by_period(transactions: List[Dict[str, Any]], period: str = "day") -> pd.DataFrame:
    """Group transactions by time period"""
    if not transactions:
        return pd.DataFrame()
    
    df = pd.DataFrame(transactions)
    
    if 'created_at' not in df.columns:
        return df
    
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    if period == "day":
        df['period'] = df['created_at'].dt.date
    elif period == "week":
        df['period'] = df['created_at'].dt.to_period('W')
    elif period == "month":
        df['period'] = df['created_at'].dt.to_period('M')
    elif period == "year":
        df['period'] = df['created_at'].dt.to_period('Y')
    else:
        df['period'] = df['created_at'].dt.date
    
    grouped = df.groupby('period').agg({
        'amount': ['sum', 'count', 'mean'],
        'risk_score': 'mean'
    }).round(2)
    
    grouped.columns = ['total_amount', 'transaction_count', 'avg_amount', 'avg_risk_score']
    grouped = grouped.reset_index()
    
    return grouped

def detect_anomalies(data: List[float], threshold: float = 2.0) -> List[bool]:
    """Detect anomalies in numeric data using z-score"""
    if not data or len(data) < 2:
        return [False] * len(data)
    
    df = pd.Series(data)
    mean = df.mean()
    std = df.std()
    
    if std == 0:
        return [False] * len(data)
    
    z_scores = abs((df - mean) / std)
    return (z_scores > threshold).tolist()

# ===================================================================
# Security and Privacy Utilities
# ===================================================================

def mask_sensitive_data(data: str, mask_char: str = "*", show_last: int = 4) -> str:
    """Mask sensitive data like email or phone numbers"""
    if not data or len(data) <= show_last:
        return data
    
    masked_length = len(data) - show_last
    return mask_char * masked_length + data[-show_last:]

def hash_data(data: str) -> str:
    """Create hash of sensitive data for logging/tracking"""
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def generate_session_id() -> str:
    """Generate unique session ID"""
    return str(uuid.uuid4())

# ===================================================================
# Configuration and Settings
# ===================================================================

def load_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Load and validate configuration"""
    default_config = {
        "app_name": "AI Payment System",
        "version": "1.0.0",
        "api_timeout": 30,
        "max_file_size": 10 * 1024 * 1024,  # 10MB
        "supported_currencies": ["USD", "EUR", "GBP"],
        "max_transaction_amount": 100000,
        "session_timeout": 3600  # 1 hour
    }
    
    # Merge with provided config
    config = {**default_config, **config_dict}
    return config

def get_app_info() -> Dict[str, str]:
    """Get application information"""
    return {
        "name": "AI Payment Processing System",
        "version": "1.0.0",
        "description": "Secure payment processing with AI-powered validation",
        "author": "AI Payment Team",
        "license": "MIT"
    }

# ===================================================================
# Error Handling and Logging
# ===================================================================

def log_error(error: Exception, context: str = ""):
    """Log error for debugging"""
    error_msg = f"Error in {context}: {str(error)}"
    # In a real implementation, this would use proper logging
    print(f"[ERROR] {error_msg}")

def handle_api_error(response_status: int, response_text: str = "") -> str:
    """Handle API error responses"""
    error_messages = {
        400: "Bad request - please check your input",
        401: "Unauthorized - please log in again",
        403: "Forbidden - you don't have permission for this action",
        404: "Not found - the requested resource doesn't exist",
        429: "Too many requests - please try again later",
        500: "Server error - please try again later",
        502: "Service unavailable - please try again later",
        503: "Service unavailable - please try again later"
    }
    
    if response_status in error_messages:
        return error_messages[response_status]
    elif 400 <= response_status < 500:
        return f"Client error ({response_status}): {response_text}"
    elif 500 <= response_status < 600:
        return f"Server error ({response_status}): Please try again later"
    else:
        return f"Unexpected error ({response_status}): {response_text}"

# ===================================================================
# Testing and Debug Utilities
# ===================================================================

def generate_sample_transaction_data(count: int = 50) -> List[Dict[str, Any]]:
    """Generate sample transaction data for testing"""
    import random
    from datetime import datetime, timedelta
    
    statuses = ['approved', 'pending', 'rejected', 'flagged']
    categories = ['utilities', 'groceries', 'entertainment', 'healthcare', 'transfer']
    
    transactions = []
    for i in range(count):
        transactions.append({
            'transaction_id': f"tx_{uuid.uuid4().hex[:12]}",
            'amount': round(random.uniform(10, 5000), 2),
            'status': random.choice(statuses),
            'category': random.choice(categories),
            'risk_score': random.randint(1, 10),
            'created_at': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
            'user_email': f"user{i}@example.com",
            'recipient': f"recipient{i}@example.com"
        })
    
    return transactions

def debug_session_state():
    """Debug function to display session state"""
    st.write("Current Session State:")
    st.json(dict(st.session_state))

# ===================================================================
# Performance Utilities
# ===================================================================

def cache_data(func):
    """Simple decorator to cache function results"""
    return st.cache_data(func)

def measure_execution_time(func):
    """Decorator to measure function execution time"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        print(f"Function {func.__name__} took {execution_time:.3f} seconds")
        return result
    return wrapper

# ===================================================================
# Accessibility Utilities
# ===================================================================

def create_accessible_table(df: pd.DataFrame, caption: str = ""):
    """Create accessible table with proper headers"""
    if caption:
        st.caption(caption)
    st.dataframe(df, use_container_width=True)

def create_screen_reader_text(text: str):
    """Create hidden text for screen readers"""
    st.markdown(f'<span style="position: absolute; left: -9999px;">{text}</span>', unsafe_allow_html=True)

# ===================================================================
# Theme and Styling Utilities
# ===================================================================

def apply_custom_css():
    """Apply custom CSS styles"""
    st.markdown("""
    <style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    
    .metric-card {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .status-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: bold;
    }
    
    .error-message {
        color: #dc3545;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 0.75rem;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    
    .success-message {
        color: #155724;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 0.75rem;
        border-radius: 0.25rem;
        margin: 1rem 0;
    }
    
    .chat-message-user {
        background-color: #0066cc;
        color: white;
        padding: 10px 15px;
        border-radius: 18px 18px 5px 18px;
        margin: 10px 0;
        max-width: 70%;
        float: right;
        clear: both;
    }
    
    .chat-message-bot {
        background-color: #f0f2f6;
        color: #333;
        padding: 10px 15px;
        border-radius: 18px 18px 18px 5px;
        margin: 10px 0;
        max-width: 70%;
        float: left;
        clear: both;
    }
    
    .sidebar-nav-button {
        width: 100%;
        margin-bottom: 5px;
        text-align: left;
        background: transparent;
        border: none;
        padding: 10px;
        border-radius: 5px;
        cursor: pointer;
    }
    
    .sidebar-nav-button:hover {
        background-color: #f0f2f6;
    }
    
    .transaction-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .risk-indicator-low {
        color: #28a745;
        font-weight: bold;
    }
    
    .risk-indicator-medium {
        color: #ffc107;
        font-weight: bold;
    }
    
    .risk-indicator-high {
        color: #dc3545;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def get_theme_colors() -> Dict[str, str]:
    """Get theme color palette"""
    return {
        "primary": "#1f77b4",
        "secondary": "#ff7f0e",
        "success": "#2ca02c",
        "warning": "#d62728",
        "info": "#17becf",
        "light": "#f8f9fa",
        "dark": "#343a40"
    }

# ===================================================================
# API Integration Utilities
# ===================================================================

def make_authenticated_request(url: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Make authenticated API request"""
    import requests
    
    headers = {"Content-Type": "application/json"}
    
    # Add authentication token if available
    if st.session_state.get('access_token'):
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            return {"success": False, "error": "Unsupported HTTP method"}
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False, 
                "error": handle_api_error(response.status_code, response.text)
            }
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}

# ===================================================================
# File Processing Utilities
# ===================================================================

def process_uploaded_file(uploaded_file) -> Dict[str, Any]:
    """Process uploaded file and return data"""
    if uploaded_file is None:
        return {"success": False, "error": "No file uploaded"}
    
    try:
        # Check file size
        if uploaded_file.size > 10 * 1024 * 1024:  # 10MB
            return {"success": False, "error": "File too large (max 10MB)"}
        
        # Process based on file type
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            return {"success": True, "data": df.to_dict('records'), "type": "csv"}
        
        elif uploaded_file.name.endswith('.json'):
            data = json.loads(uploaded_file.read().decode('utf-8'))
            return {"success": True, "data": data, "type": "json"}
        
        elif uploaded_file.name.endswith('.txt'):
            content = uploaded_file.read().decode('utf-8')
            return {"success": True, "data": content, "type": "text"}
        
        else:
            return {"success": False, "error": "Unsupported file type"}
    
    except Exception as e:
        return {"success": False, "error": f"Error processing file: {str(e)}"}

# ===================================================================
# Internationalization Utilities
# ===================================================================

def get_localized_text(key: str, language: str = "en") -> str:
    """Get localized text for internationalization"""
    # This would typically load from language files
    # For now, return English text
    translations = {
        "en": {
            "welcome": "Welcome",
            "login": "Login",
            "logout": "Logout",
            "dashboard": "Dashboard",
            "payments": "Payments",
            "transactions": "Transactions",
            "settings": "Settings",
            "profile": "Profile"
        }
    }
    
    return translations.get(language, {}).get(key, key)

def format_currency_localized(amount: float, currency: str = "USD", locale: str = "en_US") -> str:
    """Format currency based on locale"""
    # Basic implementation - would use proper locale libraries in production
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "EUR":
        return f"€{amount:,.2f}"
    elif currency == "GBP":
        return f"£{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"