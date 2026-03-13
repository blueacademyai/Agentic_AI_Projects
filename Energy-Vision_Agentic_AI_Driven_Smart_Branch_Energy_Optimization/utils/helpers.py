# utils/helpers.py
"""
EnerVision Utility Functions and Helpers
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidator:
    """Validates energy data and user inputs"""
    
    @staticmethod
    def validate_energy_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate energy data format and content"""
        errors = []
        
        # Check required columns
        required_columns = [
            'Branch', 'Date', 'EnergyMeter_kWh', 'HVAC_kWh', 
            'Lighting_kWh', 'Temperature_C', 'Occupancy_Count',
            'CarbonEmission_tons', 'ESG_Score'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        
        if errors:
            return False, errors
        
        # Validate data types and ranges
        try:
            df['Date'] = pd.to_datetime(df['Date'])
        except:
            errors.append("Invalid date format in Date column")
        
        # Validate numeric ranges
        if (df['EnergyMeter_kWh'] < 0).any():
            errors.append("Energy consumption cannot be negative")
        
        if (df['ESG_Score'] < 0).any() or (df['ESG_Score'] > 10).any():
            errors.append("ESG Score must be between 0 and 10")
        
        if (df['Temperature_C'] < -50).any() or (df['Temperature_C'] > 60).any():
            errors.append("Temperature values seem unrealistic")
        
        if (df['Occupancy_Count'] < 0).any():
            errors.append("Occupancy count cannot be negative")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_user_input(input_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate user input data"""
        errors = []
        
        # Email validation
        if 'email' in input_data:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            if not re.match(email_pattern, input_data['email']):
                errors.append("Invalid email format")
        
        # Password validation
        if 'password' in input_data:
            password = input_data['password']
            if len(password) < 8:
                errors.append("Password must be at least 8 characters long")
            if not re.search(r'[A-Za-z]', password):
                errors.append("Password must contain at least one letter")
            if not re.search(r'\d', password):
                errors.append("Password must contain at least one digit")
        
        return len(errors) == 0, errors

class SecurityUtils:
    """Security utilities for authentication and encryption"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return SecurityUtils.hash_password(password) == hashed

class FileUtils:
    """File handling utilities"""
    
    @staticmethod
    def ensure_directory_exists(path: str) -> bool:
        """Ensure directory exists, create if not"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {str(e)}")
            return False
    
    @staticmethod
    def get_file_size_mb(file_path: str) -> float:
        """Get file size in MB"""
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except:
            return 0.0
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """Clean filename for safe storage"""
        import re
        # Remove unsafe characters
        cleaned = re.sub(r'[^\w\-_.]', '', filename)
        # Add timestamp to prevent conflicts
        name, ext = os.path.splitext(cleaned)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}{ext}"

class EmailUtils:
    """Email utilities for notifications"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

class DataExporter:
    """Data export utilities"""
    
    @staticmethod
    def export_to_csv(data: pd.DataFrame, filename: str) -> str:
        """Export data to CSV"""
        try:
            FileUtils.ensure_directory_exists("exports")
            file_path = f"exports/{filename}"
            data.to_csv(file_path, index=False)
            return file_path
        except Exception as e:
            logger.error(f"Failed to export CSV: {str(e)}")
            return None
    
    @staticmethod
    def export_to_excel(data: pd.DataFrame, filename: str, sheet_name: str = "Data") -> str:
        """Export data to Excel"""
        try:
            FileUtils.ensure_directory_exists("exports")
            file_path = f"exports/{filename}"
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                data.to_excel(writer, sheet_name=sheet_name, index=False)
            return file_path
        except Exception as e:
            logger.error(f"Failed to export Excel: {str(e)}")
            return None
    
    @staticmethod
    def export_to_json(data: Dict[str, Any], filename: str) -> str:
        """Export data to JSON"""
        try:
            FileUtils.ensure_directory_exists("exports")
            file_path = f"exports/{filename}"
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return file_path
        except Exception as e:
            logger.error(f"Failed to export JSON: {str(e)}")
            return None

class MetricsCalculator:
    """Calculate various energy and ESG metrics"""
    
    @staticmethod
    def calculate_energy_efficiency(consumption_kwh: float, area_sqft: float) -> float:
        """Calculate energy efficiency (kWh per sqft)"""
        if area_sqft <= 0:
            return 0
        return consumption_kwh / area_sqft
    
    @staticmethod
    def calculate_carbon_intensity(emissions_tons: float, consumption_kwh: float) -> float:
        """Calculate carbon intensity (tons CO2 per kWh)"""
        if consumption_kwh <= 0:
            return 0
        return emissions_tons / consumption_kwh
    
    @staticmethod
    def calculate_cost_per_kwh(total_cost: float, consumption_kwh: float) -> float:
        """Calculate cost per kWh"""
        if consumption_kwh <= 0:
            return 0
        return total_cost / consumption_kwh
    
    @staticmethod
    def calculate_savings_percentage(baseline: float, current: float) -> float:
        """Calculate savings percentage"""
        if baseline <= 0:
            return 0
        return ((baseline - current) / baseline) * 100
    
    @staticmethod
    def calculate_esg_weighted_score(
        environmental_score: float, 
        social_score: float, 
        governance_score: float,
        weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)
    ) -> float:
        """Calculate weighted ESG score"""
        e_weight, s_weight, g_weight = weights
        return (
            environmental_score * e_weight + 
            social_score * s_weight + 
            governance_score * g_weight
        )

class PerformanceMonitor:
    """Monitor application performance"""
    
    def __init__(self):
        self.start_time = None
        self.operations = {}
    
    def start_operation(self, operation_name: str):
        """Start timing an operation"""
        self.operations[operation_name] = datetime.now()
    
    def end_operation(self, operation_name: str) -> float:
        """End timing an operation and return duration in seconds"""
        if operation_name not in self.operations:
            return 0
        
        start_time = self.operations[operation_name]
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Operation '{operation_name}' completed in {duration:.2f} seconds")
        return duration
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system performance statistics"""
        import psutil
        
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "network_io": psutil.net_io_counters()._asdict(),
                "timestamp": datetime.now().isoformat()
            }
        except:
            return {"error": "Unable to retrieve system stats"}

# Utility functions for common operations
def format_number(value: float, decimal_places: int = 2) -> str:
    """Format number with commas and decimal places"""
    return f"{value:,.{decimal_places}f}"

def format_percentage(value: float, decimal_places: int = 1) -> str:
    """Format percentage"""
    return f"{value:.{decimal_places}f}%"

def format_currency(value: float) -> str:
    """Format currency"""
    return f"${value:,.2f}"

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def get_date_range_options() -> List[Dict[str, Any]]:
    """Get common date range options"""
    today = datetime.now().date()
    return [
        {"label": "Last 7 days", "start": today - timedelta(days=7), "end": today},
        {"label": "Last 30 days", "start": today - timedelta(days=30), "end": today},
        {"label": "Last 3 months", "start": today - timedelta(days=90), "end": today},
        {"label": "Last 6 months", "start": today - timedelta(days=180), "end": today},
        {"label": "Last year", "start": today - timedelta(days=365), "end": today}
    ]

def calculate_business_days(start_date: datetime, end_date: datetime) -> int:
    """Calculate number of business days between dates"""
    return np.busday_count(start_date.date(), end_date.date())

def get_next_business_day(date: datetime) -> datetime:
    """Get next business day"""
    next_day = date + timedelta(days=1)
    while next_day.weekday() > 4:  # 0-6, where 0 is Monday and 6 is Sunday
        next_day += timedelta(days=1)
    return next_day