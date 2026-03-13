# app_langgraph_complete.py - Enhanced ATM Predictive Maintenance with LangGraph Multi-Agent System
# ==========================================================
# Enhanced with Google Gemini AI and Five Specialized Agents:
# 1. MonitoringAgent - Real-time system monitoring and data analysis
# 2. AnalyticsAgent - Advanced data analytics and visualization
# 3. ActionsAgent - Decision making and response coordination
# 4. MaintenanceAgent - Work order management and technician coordination
# 5. SettingsAgent - System configuration and optimization
# ==========================================================

import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import uuid
from typing import Dict, List, Any, Optional, TypedDict
import asyncio

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import io

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# LangGraph imports
from langgraph.graph import StateGraph, END
from langchain.schema import BaseMessage, HumanMessage, AIMessage

# Google Gemini
try:
    import google.generativeai as genai
    GEMINI_OK = True
except ImportError:
    GEMINI_OK = False
    st.error("Google Generative AI not installed. Please install: pip install google-generativeai")

# Twilio (mandatory)
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_OK = True
except ImportError:
    st.error("Twilio not installed. Please install: pip install twilio")
    st.stop()
    TWILIO_OK = False


# Configure Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    # st.error("Twilio configuration missing. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables.")
    twilio_client = None
else:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        st.error(f"Failed to initialize Twilio client: {str(e)}")
        twilio_client = None

def send_sms_alert(phone_number: str, message: str) -> bool:
    """Send SMS alert to technician"""
    if not twilio_client:
        return False
    
    try:
        message_obj = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        return True
    except Exception as e:
        st.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False


# Environment setup
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

except ImportError:
    pass

# Configure Gemini
if GEMINI_OK:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        # Initialize the model
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    else:
        st.warning("GEMINI_API_KEY not found in environment variables")
        gemini_model = None
else:
    gemini_model = None

async def get_gemini_insights(data_summary: str, alerts: List[Dict], metrics: Dict) -> str:
    """Get AI insights from Gemini based on system data"""
    if not gemini_model:
        return "Gemini AI not available"
    
    try:
        prompt = f"""
        As an ATM maintenance expert, analyze this system data and provide actionable insights:
        
        Current Metrics: {metrics}
        Active Alerts: {len(alerts)} alerts
        Data Summary: {data_summary}
        
        Please provide:
        1. Root cause analysis for any issues
        2. Predictive maintenance recommendations
        3. Risk assessment (1-10 scale)
        4. Immediate actions needed
        
        Be concise and focus on actionable recommendations.
        """
        
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error getting Gemini insights: {str(e)}"

# ===========================
# ENHANCED STATE DEFINITION
# ===========================
# ===========================
# ENHANCED STATE DEFINITION
# ===========================
class ATMState(TypedDict):
    """Enhanced state shared between all agents"""
    # Raw data
    sensor_data: Optional[pd.DataFrame]
    uploaded_data: Optional[pd.DataFrame]
    latest_metrics: Optional[Dict[str, Any]]
    
    # Analysis results
    risk_assessment: Optional[Dict[str, Any]]
    analytics_results: Optional[Dict[str, Any]]
    alerts: List[Dict[str, Any]]  # Changed to list of dictionaries for better alert handling
    system_health_score: float
    
    # Actions and responses
    recommended_actions: List[Dict[str, Any]]
    automated_responses: List[Dict[str, Any]]
    
    # Maintenance info
    work_orders: List[Dict[str, Any]]
    maintenance_schedule: List[Dict[str, Any]]
    technician_assignments: Dict[str, str]
    
    # Settings and configuration
    system_settings: Dict[str, Any]
    optimization_recommendations: List[Dict[str, Any]]
    
    # Communication
    messages: List[BaseMessage]
    notifications_sent: List[Dict[str, Any]]
    
    # Configuration
    location: Dict[str, str]
    thresholds: Dict[str, float]
    
    # Agent coordination
    current_agent: str
    agent_outputs: Dict[str, Any]
    should_escalate: bool

# ===========================
# ENHANCED AGENT CLASSES


# ===========================
# ENHANCED AGENT CLASSES
# ===========================

class MLPredictor:
    """Machine Learning predictor for ATM failures"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            'temperature_c', 'network_latency_ms', 'packet_loss_pct', 
            'vibration_g', 'cash_level_pct', 'uptime_hours', 'last_maint_days'
        ]
    
    def prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare features for ML model"""
        features = []
        for col in self.feature_names:
            if col in df.columns:
                features.append(df[col].values)
            else:
                # Default values for missing columns
                default_values = {
                    'temperature_c': 35.0,
                    'network_latency_ms': 80.0,
                    'packet_loss_pct': 1.0,
                    'vibration_g': 0.02,
                    'cash_level_pct': 50.0,
                    'uptime_hours': 24.0,
                    'last_maint_days': 15.0
                }
                features.append(np.full(len(df), default_values[col]))
        
        return np.column_stack(features)
    
    def create_failure_labels(self, df: pd.DataFrame) -> np.ndarray:
        """Create failure labels based on system conditions"""
        # Create synthetic failure labels based on multiple conditions
        failure_conditions = (
            (df['temperature_c'] > 42) |
            (df['network_latency_ms'] > 300) |
            (df['vibration_g'] > 0.25) |
            (df['cash_level_pct'] < 10) |
            (df['last_maint_days'] > 30)
        )
        
        # Add some randomness to make it more realistic
        random_failures = np.random.random(len(df)) < 0.02  # 2% random failure rate
        
        return (failure_conditions | random_failures).astype(int)
    
    def train_model(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Train the ML model on historical data"""
        try:
            if len(df) < 100:
                return {"status": "error", "message": "Insufficient data for training"}
            
            # Prepare features and labels
            X = self.prepare_features(df)
            y = self.create_failure_labels(df)
            
            # Handle class imbalance
            from collections import Counter
            class_counts = Counter(y)
            
            if len(class_counts) < 2:
                return {"status": "error", "message": "Insufficient failure examples"}
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train Random Forest with balanced class weights
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced',
                min_samples_split=5,
                min_samples_leaf=2
            )
            
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            # Calculate feature importance
            feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
            
            # Calculate training metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score
            y_pred = self.model.predict(X_scaled)
            
            metrics = {
                "accuracy": accuracy_score(y, y_pred),
                "precision": precision_score(y, y_pred, zero_division=0),
                "recall": recall_score(y, y_pred, zero_division=0),
                "failure_rate": np.mean(y) * 100
            }
            
            return {
                "status": "success",
                "metrics": metrics,
                "feature_importance": feature_importance,
                "training_samples": len(df),
                "failure_examples": int(np.sum(y))
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def predict_failure_probability(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Predict failure probability for current data"""
        if not self.is_trained:
            return {"status": "error", "message": "Model not trained"}
        
        try:
            # Prepare features for prediction
            X = self.prepare_features(df.tail(1))  # Use latest data point
            X_scaled = self.scaler.transform(X)
            
            # Get prediction and probability
            prediction = self.model.predict(X_scaled)[0]
            probability = self.model.predict_proba(X_scaled)[0]
            
            # Get feature contributions (simplified)
            feature_values = dict(zip(self.feature_names, X[0]))
            
            return {
                "status": "success",
                "will_fail": bool(prediction),
                "failure_probability": float(probability[1]) if len(probability) > 1 else 0.0,
                "confidence": float(max(probability)),
                "feature_values": feature_values,
                "risk_level": self._assess_risk_level(probability[1] if len(probability) > 1 else 0.0)
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _assess_risk_level(self, probability: float) -> str:
        """Assess risk level based on failure probability"""
        if probability > 0.7:
            return "CRITICAL"
        elif probability > 0.4:
            return "HIGH"
        elif probability > 0.2:
            return "MEDIUM"
        else:
            return "LOW"

    def get_top_risk_factors(self, n_factors: int = 3) -> List[Dict[str, Any]]:
        """Get top risk factors based on feature importance"""
        if not self.is_trained:
            return []
        
        # Sort features by importance
        importance_sorted = sorted(
            zip(self.feature_names, self.model.feature_importances_),
            key=lambda x: x[1],
            reverse=True
        )
        
        risk_factors = []
        for feature, importance in importance_sorted[:n_factors]:
            risk_factors.append({
                "factor": feature.replace('_', ' ').title(),
                "importance_score": float(importance),
                "impact_level": "High" if importance > 0.15 else "Medium" if importance > 0.08 else "Low"
            })
        
        return risk_factors

class MonitoringAgent:
    """Enhanced monitoring agent with comprehensive data collection and alert generation"""
    
    def __init__(self):
        self.name = "MonitoringAgent"
class MonitoringAgent:
    """Enhanced monitoring agent with comprehensive data collection and alert generation"""
    
    def __init__(self):
        self.name = "MonitoringAgent"
    
    async def process(self, state: ATMState) -> ATMState:
        """Process monitoring tasks with ML predictions and Gemini insights"""
        try:
            # Use uploaded data if available, otherwise generate synthetic data
            if state["uploaded_data"] is not None:
                sensor_data = state["uploaded_data"].copy()
            else:
                sensor_data = self._load_sensor_data(
                    state["location"]["city"], 
                    state["location"]["branch"]
                )
            
            # Calculate comprehensive metrics
            latest_metrics = self._calculate_enhanced_metrics(sensor_data)
            
            # Generate alerts based on thresholds
            alerts = self._generate_alerts(latest_metrics, state["thresholds"])
            
            # ML Prediction
            ml_predictor = MLPredictor()
            training_result = ml_predictor.train_model(sensor_data)
            
            ml_prediction = {"status": "not_available"}
            if training_result["status"] == "success":
                ml_prediction = ml_predictor.predict_failure_probability(sensor_data)
            
            # Generate health score with ML insights
            health_score = self._calculate_advanced_health_score(latest_metrics, alerts, ml_prediction)
            
            # Get Gemini AI insights
            gemini_insights = ""
            if gemini_model:
                data_summary = f"Temperature: {latest_metrics.get('temperature_c', 0):.1f}°C, Network: {latest_metrics.get('network_latency_ms', 0):.0f}ms, Cash: {latest_metrics.get('cash_level_pct', 0):.0f}%"
                gemini_insights = await get_gemini_insights(data_summary, alerts, latest_metrics)
            
            # Real-time anomaly detection
            anomalies = self._detect_anomalies(sensor_data)
            
            # Update state with ML and AI insights
            state["sensor_data"] = sensor_data
            state["latest_metrics"] = latest_metrics
            state["alerts"] = alerts
            state["system_health_score"] = health_score
            state["agent_outputs"][self.name] = {
                "status": "completed",
                "health_score": health_score,
                "data_points": len(sensor_data),
                "anomalies_detected": len(anomalies),
                "alerts_generated": len(alerts),
                "ml_prediction": ml_prediction,
                "ml_training": training_result,
                "gemini_insights": gemini_insights[:200] + "..." if len(gemini_insights) > 200 else gemini_insights,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add ML insights to messages
            if ml_prediction["status"] == "success":
                risk_level = ml_prediction["risk_level"]
                failure_prob = ml_prediction["failure_probability"] * 100
                state["messages"].append(
                    AIMessage(content=f"ML Analysis: {risk_level} risk ({failure_prob:.1f}% failure probability). {gemini_insights[:100]}...")
                )
            else:
                state["messages"].append(
                    AIMessage(content=f"Monitoring complete. Health: {health_score}%. Alerts: {len(alerts)}, Anomalies: {len(anomalies)}")
                )
            
            return state
            
        except Exception as e:
            state["messages"].append(
                AIMessage(content=f"Monitoring agent error: {str(e)}")
            )
            return state


    def _generate_alerts(self, metrics: Dict[str, Any], thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics and thresholds"""
        alerts = []
        
        if not metrics:
            return alerts
        
        current_time = datetime.now()
        
        # Temperature alerts
        temp_value = metrics.get("temperature_c", 0)
        if temp_value >= thresholds.get("temp_critical", 42):
            alerts.append({
                "id": f"ALERT-TEMP-CRIT-{uuid.uuid4().hex[:8]}",
                "type": "TEMPERATURE",
                "severity": "CRITICAL",
                "title": "Critical Temperature Alert",
                "message": f"Temperature at {temp_value:.1f}°C exceeds critical threshold of {thresholds['temp_critical']}°C",
                "value": temp_value,
                "threshold": thresholds["temp_critical"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": True
            })
        elif temp_value >= thresholds.get("temp_warning", 40):
            alerts.append({
                "id": f"ALERT-TEMP-WARN-{uuid.uuid4().hex[:8]}",
                "type": "TEMPERATURE",
                "severity": "WARNING",
                "title": "Temperature Warning",
                "message": f"Temperature at {temp_value:.1f}°C exceeds warning threshold of {thresholds['temp_warning']}°C",
                "value": temp_value,
                "threshold": thresholds["temp_warning"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": False
            })
        
        # Network alerts
        network_value = metrics.get("network_latency_ms", 0)
        if network_value >= thresholds.get("network_critical", 250):
            alerts.append({
                "id": f"ALERT-NET-CRIT-{uuid.uuid4().hex[:8]}",
                "type": "NETWORK",
                "severity": "CRITICAL",
                "title": "Critical Network Alert",
                "message": f"Network latency at {network_value:.0f}ms exceeds critical threshold of {thresholds['network_critical']}ms",
                "value": network_value,
                "threshold": thresholds["network_critical"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": True
            })
        elif network_value >= thresholds.get("network_warning", 120):
            alerts.append({
                "id": f"ALERT-NET-WARN-{uuid.uuid4().hex[:8]}",
                "type": "NETWORK",
                "severity": "WARNING",
                "title": "Network Performance Warning",
                "message": f"Network latency at {network_value:.0f}ms exceeds warning threshold of {thresholds['network_warning']}ms",
                "value": network_value,
                "threshold": thresholds["network_warning"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": False
            })
        
        # Cash level alerts
        cash_value = metrics.get("cash_level_pct", 100)
        if cash_value <= thresholds.get("cash_critical", 15):
            alerts.append({
                "id": f"ALERT-CASH-CRIT-{uuid.uuid4().hex[:8]}",
                "type": "CASH",
                "severity": "CRITICAL",
                "title": "Critical Cash Level Alert",
                "message": f"Cash level at {cash_value:.0f}% is below critical threshold of {thresholds['cash_critical']}%",
                "value": cash_value,
                "threshold": thresholds["cash_critical"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": True
            })
        elif cash_value <= thresholds.get("cash_warning", 30):
            alerts.append({
                "id": f"ALERT-CASH-WARN-{uuid.uuid4().hex[:8]}",
                "type": "CASH",
                "severity": "WARNING",
                "title": "Low Cash Level Warning",
                "message": f"Cash level at {cash_value:.0f}% is below warning threshold of {thresholds['cash_warning']}%",
                "value": cash_value,
                "threshold": thresholds["cash_warning"],
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": False
            })
        
        # Vibration alerts
        vibration_value = metrics.get("vibration_g", 0)
        if vibration_value >= 0.3:
            alerts.append({
                "id": f"ALERT-VIB-CRIT-{uuid.uuid4().hex[:8]}",
                "type": "MECHANICAL",
                "severity": "CRITICAL",
                "title": "Critical Vibration Alert",
                "message": f"Vibration level at {vibration_value:.2f}g indicates potential mechanical failure",
                "value": vibration_value,
                "threshold": 0.3,
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": True
            })
        elif vibration_value >= 0.15:
            alerts.append({
                "id": f"ALERT-VIB-WARN-{uuid.uuid4().hex[:8]}",
                "type": "MECHANICAL",
                "severity": "WARNING",
                "title": "Vibration Warning",
                "message": f"Elevated vibration level at {vibration_value:.2f}g detected",
                "value": vibration_value,
                "threshold": 0.15,
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": False
            })
        
        # Dispenser jam alerts
        jam_count = metrics.get("dispenser_jams_24h", 0)
        if jam_count >= 5:
            alerts.append({
                "id": f"ALERT-JAM-CRIT-{uuid.uuid4().hex[:8]}",
                "type": "DISPENSER",
                "severity": "CRITICAL",
                "title": "Critical Dispenser Alert",
                "message": f"High dispenser jam count: {jam_count} jams in last 24 hours",
                "value": jam_count,
                "threshold": 5,
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": True
            })
        elif jam_count >= 3:
            alerts.append({
                "id": f"ALERT-JAM-WARN-{uuid.uuid4().hex[:8]}",
                "type": "DISPENSER",
                "severity": "WARNING",
                "title": "Dispenser Performance Warning",
                "message": f"Increased dispenser jams: {jam_count} jams in last 24 hours",
                "value": jam_count,
                "threshold": 3,
                "timestamp": current_time.isoformat(),
                "requires_immediate_action": False
            })
        
        return alerts
    
    def _load_sensor_data(self, city: str, branch: str) -> pd.DataFrame:
        """Generate enhanced synthetic IoT data"""
        return make_enhanced_synthetic_data(city, branch, n_minutes=2880)  # 2 days of data
    
    def _calculate_enhanced_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive metrics from sensor data"""
        if len(df) == 0:
            return {}
        
        latest = df.iloc[-1]
        last_24h = df.tail(1440) if len(df) >= 1440 else df  # Last 24 hours
        
        return {
            # Current values
            "temperature_c": float(latest["temperature_c"]),
            "network_latency_ms": float(latest["network_latency_ms"]),
            "packet_loss_pct": float(latest["packet_loss_pct"]),
            "vibration_g": float(latest["vibration_g"]),
            "cash_level_pct": float(latest["cash_level_pct"]),
            "dispenser_jams_24h": int(latest["dispenser_jams_last_24h"]),
            "door_events": int(latest["door_open_events"]),
            "uptime_hours": float(latest["uptime_hours"]),
            "last_maint_days": float(latest["last_maint_days"]),
            
            # Trends and averages
            "temp_avg_24h": float(last_24h["temperature_c"].mean()),
            "temp_max_24h": float(last_24h["temperature_c"].max()),
            "network_avg_24h": float(last_24h["network_latency_ms"].mean()),
            "network_max_24h": float(last_24h["network_latency_ms"].max()),
            "vibration_avg_24h": float(last_24h["vibration_g"].mean()),
            "vibration_max_24h": float(last_24h["vibration_g"].max()),
            
            # Performance indicators
            "availability_24h": float((last_24h["uptime_hours"] > 0).sum() / len(last_24h) * 100),
            "error_rate_24h": float(last_24h["dispenser_jams_last_24h"].sum()),
            "transaction_success_rate": float(100 - last_24h["packet_loss_pct"].mean()),
        }
    
    def _calculate_advanced_health_score(self, metrics: Dict[str, Any], alerts: List[Dict[str, Any]], ml_prediction: Dict[str, Any] = None) -> float:
        """Advanced health score calculation with ML integration"""
        if not metrics:
            return 0.0
            
        base_score = 100
        weights = {
            "temperature": 0.20,
            "network": 0.18,
            "mechanical": 0.18,
            "operational": 0.12,
            "maintenance": 0.08,
            "alerts": 0.10,
            "ml_risk": 0.14  # New ML-based risk factor
        }
        
        # Temperature score
        temp_penalty = 0
        if metrics["temperature_c"] > 45:
            temp_penalty = 40
        elif metrics["temperature_c"] > 42:
            temp_penalty = 25
        elif metrics["temperature_c"] > 40:
            temp_penalty = 15
        
        # Network score
        network_penalty = 0
        if metrics["network_latency_ms"] > 300:
            network_penalty = 35
        elif metrics["network_latency_ms"] > 250:
            network_penalty = 25
        elif metrics["network_latency_ms"] > 120:
            network_penalty = 10
        
        # Mechanical score
        mechanical_penalty = min(metrics["vibration_g"] * 100, 30) + min(metrics["dispenser_jams_24h"] * 10, 25)
        
        # Operational score
        operational_penalty = max(0, (30 - metrics["cash_level_pct"]) * 2)
        
        # Maintenance score
        maintenance_penalty = max(0, (metrics["last_maint_days"] - 21) * 2)
        
        # Alert penalty - enhanced to consider alert severity
        alert_penalty = 0
        for alert in alerts:
            if alert["severity"] == "CRITICAL":
                alert_penalty += 15
            elif alert["severity"] == "WARNING":
                alert_penalty += 8
        
        # NEW: ML-based risk penalty
        ml_penalty = 0
        if ml_prediction and ml_prediction["status"] == "success":
            failure_prob = ml_prediction["failure_probability"]
            ml_penalty = failure_prob * 50  # Scale 0-1 probability to 0-50 penalty
        
        # Calculate weighted score
        total_penalty = (
            temp_penalty * weights["temperature"] +
            network_penalty * weights["network"] +
            mechanical_penalty * weights["mechanical"] +
            operational_penalty * weights["operational"] +
            maintenance_penalty * weights["maintenance"] +
            alert_penalty * weights["alerts"] +
            ml_penalty * weights["ml_risk"]
        )
        
        return max(0, base_score - total_penalty)
    
    def _detect_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect anomalies in sensor data"""
        anomalies = []
        
        if len(df) < 10:
            return anomalies
        
        # Temperature anomalies
        temp_mean = df["temperature_c"].mean()
        temp_std = df["temperature_c"].std()
        temp_threshold = temp_mean + 2 * temp_std
        
        recent_temp = df.tail(60)["temperature_c"]  # Last hour
        if (recent_temp > temp_threshold).any():
            anomalies.append({
                "type": "temperature_spike",
                "severity": "high",
                "description": "Temperature spike detected in last hour"
            })
        
        # Network anomalies
        recent_latency = df.tail(60)["network_latency_ms"]
        if (recent_latency > 400).any():
            anomalies.append({
                "type": "network_degradation",
                "severity": "medium",
                "description": "Severe network latency spikes detected"
            })
        
        return anomalies

class AnalyticsAgent:
    """New analytics agent for advanced data analysis and visualization"""
    
    def __init__(self):
        self.name = "AnalyticsAgent"
    
    async def process(self, state: ATMState) -> ATMState:
        """Process analytics tasks"""
        try:
            if state["sensor_data"] is None:
                state["messages"].append(AIMessage(content="No data available for analytics"))
                return state
            
            # Perform comprehensive analytics
            analytics_results = self._perform_analytics(state["sensor_data"])
            
            # Generate predictive insights
            predictive_insights = self._generate_predictive_insights(state["sensor_data"])
            
            # Create visualization data
            viz_data = self._prepare_visualization_data(state["sensor_data"])
            
            # Update state
            state["analytics_results"] = {
                **analytics_results,
                "predictive_insights": predictive_insights,
                "visualization_data": viz_data
            }
            
            state["agent_outputs"][self.name] = {
                "status": "completed",
                "trends_analyzed": len(analytics_results.get("trends", {})),
                "insights_generated": len(predictive_insights),
                "timestamp": datetime.now().isoformat()
            }
            
            state["messages"].append(
                AIMessage(content=f"Analytics complete. Generated {len(predictive_insights)} insights")
            )
            
            return state
            
        except Exception as e:
            state["messages"].append(AIMessage(content=f"Analytics agent error: {str(e)}"))
            return state
    
    def _perform_analytics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive data analytics"""
        results = {}
        
        # Trend analysis
        trends = {}
        for col in ["temperature_c", "network_latency_ms", "vibration_g"]:
            if col in df.columns:
                recent_data = df.tail(720)[col]  # Last 12 hours
                if len(recent_data) > 1:
                    slope = np.polyfit(range(len(recent_data)), recent_data, 1)[0]
                    trends[col] = {
                        "slope": float(slope),
                        "direction": "increasing" if slope > 0 else "decreasing",
                        "magnitude": abs(float(slope))
                    }
        
        results["trends"] = trends
        
        # Performance metrics
        if len(df) > 0:
            results["performance"] = {
                "avg_uptime": float(df["uptime_hours"].mean()),
                "max_temp_recorded": float(df["temperature_c"].max()),
                "network_reliability": float(100 - df["packet_loss_pct"].mean()),
                "mechanical_stability": float(1 / (df["vibration_g"].mean() + 0.001))
            }
        
        return results
    
    def _generate_predictive_insights(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate predictive insights using ML"""
        insights = []
        
        if len(df) < 100:
            return insights
        
        try:
            # Prepare features for prediction
            features = ["temperature_c", "network_latency_ms", "vibration_g", "cash_level_pct"]
            available_features = [f for f in features if f in df.columns]
            
            if len(available_features) > 0:
                # Simple trend prediction
                for feature in available_features:
                    recent_values = df.tail(60)[feature].values
                    if len(recent_values) > 10:
                        # Linear regression prediction
                        x = np.arange(len(recent_values))
                        coeffs = np.polyfit(x, recent_values, 1)
                        predicted_next = coeffs[0] * len(recent_values) + coeffs[1]
                        current_value = recent_values[-1]
                        
                        change_pct = ((predicted_next - current_value) / current_value) * 100 if current_value != 0 else 0
                        
                        insights.append({
                            "metric": feature,
                            "current_value": float(current_value),
                            "predicted_value": float(predicted_next),
                            "change_percentage": float(change_pct),
                            "confidence": 0.75,
                            "timeframe": "next_hour"
                        })
        
        except Exception:
            pass
        
        return insights
    
    def _prepare_visualization_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Prepare data for visualizations"""
        viz_data = {}
        
        # Temperature trend data
        if "temperature_c" in df.columns:
            temp_data = df.tail(1440)  # Last 24 hours
            viz_data["temperature_trend"] = {
                "timestamps": temp_data["timestamp"].dt.strftime("%H:%M").tolist() if "timestamp" in temp_data.columns else list(range(len(temp_data))),
                "values": temp_data["temperature_c"].tolist(),
                "threshold_warning": 40,
                "threshold_critical": 42
            }
        
        # Network performance data
        if "network_latency_ms" in df.columns:
            network_data = df.tail(1440)
            viz_data["network_performance"] = {
                "timestamps": network_data["timestamp"].dt.strftime("%H:%M").tolist() if "timestamp" in network_data.columns else list(range(len(network_data))),
                "latency": network_data["network_latency_ms"].tolist(),
                "packet_loss": network_data["packet_loss_pct"].tolist() if "packet_loss_pct" in network_data.columns else []
            }
        
        # System health over time
        health_scores = []
        window_size = 60  # 1 hour windows
        for i in range(0, len(df), window_size):
            window = df.iloc[i:i+window_size]
            if len(window) > 0:
                # Simplified health calculation for historical data
                temp_score = max(0, 100 - max(0, window["temperature_c"].mean() - 35) * 5)
                network_score = max(0, 100 - max(0, window["network_latency_ms"].mean() - 80) / 5)
                overall_score = (temp_score + network_score) / 2
                health_scores.append(overall_score)
        
        viz_data["health_trend"] = {
            "timestamps": [f"{i}h" for i in range(len(health_scores))],
            "scores": health_scores
        }
        
        return viz_data

class ActionsAgent:
    """New actions agent for decision making and response coordination"""
    
    def __init__(self):
        self.name = "ActionsAgent"
    
    async def process(self, state: ATMState) -> ATMState:
        """Process actions and responses"""
        try:
            # Generate recommended actions
            actions = self._generate_recommended_actions(
                state["latest_metrics"],
                state["alerts"],
                state["analytics_results"],
                state["thresholds"]
            )
            
            # Determine automated responses
            automated_responses = self._determine_automated_responses(
                state["latest_metrics"],
                state["system_health_score"],
                state["thresholds"]
            )
            
            # Priority assessment
            priority_actions = self._assess_action_priorities(actions)
            
            # Update state
            state["recommended_actions"] = actions
            state["automated_responses"] = automated_responses
            
            state["agent_outputs"][self.name] = {
                "status": "completed",
                "actions_recommended": len(actions),
                "automated_responses": len(automated_responses),
                "high_priority_actions": len([a for a in actions if a.get("priority") == "HIGH"]),
                "timestamp": datetime.now().isoformat()
            }
            
            state["messages"].append(
                AIMessage(content=f"Actions analysis complete. {len(actions)} recommendations, {len(automated_responses)} automated responses")
            )
            
            return state
            
        except Exception as e:
            state["messages"].append(AIMessage(content=f"Actions agent error: {str(e)}"))
            return state
    
    def _generate_recommended_actions(self, metrics: Optional[Dict[str, Any]], 
                                    alerts: List[Dict[str, Any]], 
                                    analytics: Optional[Dict[str, Any]],
                                    thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate recommended actions based on current state using dynamic thresholds"""
        actions = []
        
        if not metrics:
            return actions
        
        # Use dynamic thresholds from sidebar
        temp_warning = thresholds.get("temp_warning", 40)
        temp_critical = thresholds.get("temp_critical", 42)
        network_warning = thresholds.get("network_warning", 120)
        network_critical = thresholds.get("network_critical", 250)
        cash_warning = thresholds.get("cash_warning", 30)
        cash_critical = thresholds.get("cash_critical", 15)
        
        # Temperature-based actions
        if metrics["temperature_c"] > temp_critical:
            actions.append({
                "id": f"ACT-TEMP-{uuid.uuid4().hex[:8]}",
                "type": "IMMEDIATE",
                "priority": "CRITICAL",
                "title": "Emergency Cooling System Check",
                "description": f"Temperature at {metrics['temperature_c']:.1f}°C exceeds critical threshold of {temp_critical}°C",
                "estimated_time": "1-2 hours",
                "required_skills": ["HVAC", "Electrical"],
                "risk_if_delayed": "System failure, potential fire hazard"
            })
        elif metrics["temperature_c"] > temp_warning:
            actions.append({
                "id": f"ACT-TEMP-{uuid.uuid4().hex[:8]}",
                "type": "PREVENTIVE",
                "priority": "HIGH",
                "title": "Cooling System Maintenance",
                "description": f"Temperature at {metrics['temperature_c']:.1f}°C exceeds warning threshold of {temp_warning}°C",
                "estimated_time": "2-3 hours",
                "required_skills": ["HVAC"],
                "risk_if_delayed": "Potential overheating"
            })
        
        # Network-based actions
        if metrics["network_latency_ms"] > network_critical:
            actions.append({
                "id": f"ACT-NET-{uuid.uuid4().hex[:8]}",
                "type": "IMMEDIATE",
                "priority": "CRITICAL",
                "title": "Critical Network Infrastructure Check",
                "description": f"Network latency at {metrics['network_latency_ms']:.0f}ms exceeds critical threshold of {network_critical}ms",
                "estimated_time": "1-2 hours",
                "required_skills": ["Network", "IT"],
                "risk_if_delayed": "Complete network failure, ATM offline"
            })
        elif metrics["network_latency_ms"] > network_warning:
            actions.append({
                "id": f"ACT-NET-{uuid.uuid4().hex[:8]}",
                "type": "CORRECTIVE",
                "priority": "HIGH",
                "title": "Network Performance Optimization",
                "description": f"Network latency at {metrics['network_latency_ms']:.0f}ms exceeds warning threshold of {network_warning}ms",
                "estimated_time": "1-2 hours",
                "required_skills": ["Network", "IT"],
                "risk_if_delayed": "Transaction failures, customer complaints"
            })
        
        # Cash management actions
        if metrics["cash_level_pct"] < cash_critical:
            actions.append({
                "id": f"ACT-CASH-{uuid.uuid4().hex[:8]}",
                "type": "IMMEDIATE",
                "priority": "CRITICAL",
                "title": "Emergency Cash Replenishment",
                "description": f"Critical cash level at {metrics['cash_level_pct']:.0f}% (below {cash_critical}% threshold)",
                "estimated_time": "30 minutes",
                "required_skills": ["Cash Management"],
                "risk_if_delayed": "ATM out of service"
            })
        elif metrics["cash_level_pct"] < cash_warning:
            actions.append({
                "id": f"ACT-CASH-{uuid.uuid4().hex[:8]}",
                "type": "PREVENTIVE",
                "priority": "HIGH",
                "title": "Scheduled Cash Replenishment",
                "description": f"Cash level at {metrics['cash_level_pct']:.0f}% (below {cash_warning}% warning threshold)",
                "estimated_time": "30 minutes",
                "required_skills": ["Cash Management"],
                "risk_if_delayed": "Potential service disruption"
            })
        
        # Generate actions based on alerts
        for alert in alerts:
            if alert["requires_immediate_action"]:
                action_id = f"ACT-{alert['type']}-{uuid.uuid4().hex[:8]}"
                actions.append({
                    "id": action_id,
                    "type": "IMMEDIATE" if alert["severity"] == "CRITICAL" else "CORRECTIVE",
                    "priority": alert["severity"],
                    "title": f"Address {alert['title']}",
                    "description": alert["message"],
                    "estimated_time": "1-2 hours",
                    "required_skills": self._get_skills_for_alert_type(alert["type"]),
                    "risk_if_delayed": "System degradation or failure",
                    "related_alert_id": alert["id"]
                })
        
        return actions
    
    def _get_skills_for_alert_type(self, alert_type: str) -> List[str]:
        """Get required skills based on alert type"""
        skill_mapping = {
            "TEMPERATURE": ["HVAC", "Electrical"],
            "NETWORK": ["Network", "IT"],
            "CASH": ["Cash Management"],
            "MECHANICAL": ["Mechanical", "Electrical"],
            "DISPENSER": ["Mechanical", "Cash Management"]
        }
        return skill_mapping.get(alert_type, ["General"])
    
    def _determine_automated_responses(self, metrics: Optional[Dict[str, Any]], 
                                     health_score: float,
                                     thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
        """Determine automated responses using dynamic thresholds"""
        responses = []
        
        if not metrics:
            return responses
        
        # Use dynamic thresholds
        temp_warning = thresholds.get("temp_warning", 40)
        network_warning = thresholds.get("network_warning", 120)
        
        # Automatic cooling adjustment
        if metrics["temperature_c"] > temp_warning:
            responses.append({
                "action": "increase_fan_speed",
                "description": "Automatically increased cooling fan speed",
                "triggered_by": f"Temperature: {metrics['temperature_c']:.1f}°C (threshold: {temp_warning}°C)",
                "expected_effect": "Reduce temperature by 2-3°C"
            })
        
        # Network optimization
        if metrics["network_latency_ms"] > network_warning:
            responses.append({
                "action": "switch_network_route",
                "description": "Switched to backup network route",
                "triggered_by": f"High latency: {metrics['network_latency_ms']:.0f}ms (threshold: {network_warning}ms)",
                "expected_effect": "Reduce latency by 30-50%"
            })
        
        # System resource optimization
        if health_score < 70:
            responses.append({
                "action": "optimize_system_resources",
                "description": "Optimized system resource allocation",
                "triggered_by": f"Low health score: {health_score:.0f}%",
                "expected_effect": "Improve overall performance"
            })
        
        return responses
    
    def _assess_action_priorities(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Assess and sort actions by priority"""
        priority_order = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
        return sorted(actions, key=lambda x: priority_order.get(x.get("priority", "LOW"), 0), reverse=True)

class MaintenanceAgent:
    """Enhanced maintenance agent"""
    
    def __init__(self):
        self.name = "MaintenanceAgent"
    
    async def process(self, state: ATMState) -> ATMState:
        """Enhanced maintenance processing"""
        try:
            # Generate comprehensive work orders
            work_orders = self._generate_enhanced_work_orders(
                state["recommended_actions"],
                state["alerts"],
                state["location"]
            )
            
            # Create detailed maintenance schedule
            schedule = self._create_detailed_schedule(
                state["latest_metrics"],
                state["analytics_results"]
            )
            
            # Smart technician assignment
            assignments = self._smart_technician_assignment(
                work_orders,
                state["location"]["city"]
            )
            
            # Send SMS notifications
            notifications = self._send_technician_notifications(work_orders, assignments, state["location"])

            # Update state
            state["work_orders"] = work_orders
            state["maintenance_schedule"] = schedule
            state["technician_assignments"] = assignments
            state["notifications_sent"] = notifications

            state["agent_outputs"][self.name] = {
                "status": "completed",
                "work_orders_created": len(work_orders),
                "maintenance_items": len(schedule),
                "technicians_assigned": len(set(assignments.values())),
                "sms_notifications_sent": len([n for n in notifications if n["message_sent"]]),
                "timestamp": datetime.now().isoformat()
            }

            state["messages"].append(
                AIMessage(content=f"Maintenance coordination complete. {len(work_orders)} work orders created, {len([n for n in notifications if n['message_sent']])} SMS notifications sent")
            )

            return state
            
        except Exception as e:
            state["messages"].append(AIMessage(content=f"Maintenance agent error: {str(e)}"))
            return state
        
    def _generate_enhanced_work_orders(self, actions: List[Dict[str, Any]], 
                                     alerts: List[Dict[str, Any]], 
                                     location: Dict[str, str]) -> List[Dict[str, Any]]:
        """Generate enhanced work orders from recommended actions"""
        work_orders = []
        
        for action in actions:
            work_orders.append({
                "id": f"WO-{action['id'].split('-')[-1]}",
                "title": action["title"],
                "description": action["description"],
                "priority": action["priority"],
                "type": action["type"],
                "location": f"{location['city']}-{location['branch']}",
                "estimated_time": action["estimated_time"],
                "required_skills": action.get("required_skills", []),
                "risk_if_delayed": action.get("risk_if_delayed", "Unknown"),
                "created": datetime.now().isoformat(),
                "status": "PENDING",
                "parts_required": self._estimate_parts_needed(action),
                "related_alert_id": action.get("related_alert_id", None)
            })
        
        return work_orders
    
    def _create_detailed_schedule(self, metrics: Optional[Dict[str, Any]], 
                                analytics: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create detailed maintenance schedule"""
        schedule = []
        base_date = datetime.now()
        
        if not metrics:
            return schedule
        
        # Predictive maintenance based on analytics
        if analytics and "predictive_insights" in analytics:
            for insight in analytics["predictive_insights"]:
                if insight["change_percentage"] > 10:  # Significant change predicted
                    schedule.append({
                        "task": f"Preventive check for {insight['metric']}",
                        "due_date": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
                        "priority": "MEDIUM",
                        "type": "PREDICTIVE",
                        "estimated_time": "1 hour",
                        "reason": f"Predicted change: {insight['change_percentage']:.1f}%"
                    })
        
        # Standard preventive maintenance
        schedule.append({
            "task": "Comprehensive System Check",
            "due_date": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),
            "priority": "NORMAL",
            "type": "PREVENTIVE",
            "estimated_time": "3 hours",
            "reason": "Weekly preventive maintenance"
        })
        
        return schedule
    
    def _smart_technician_assignment(self, work_orders: List[Dict[str, Any]], 
                                   city: str) -> Dict[str, str]:
        """Smart technician assignment based on skills and availability"""
        # Enhanced technician database
        # Enhanced technician database with verified phone numbers
        technicians = {
            "Mumbai": {
                "+919000011111": {"name": "Rajesh Kumar", "skills": ["HVAC", "Electrical", "Mechanical"]},
                "+919000011112": {"name": "Amit Shah", "skills": ["Network", "IT", "Software"]},
                "+919000011113": {"name": "Priya Sharma", "skills": ["Cash Management", "Security", "Mechanical"]}
            },
            "Delhi": {
                "+919000022221": {"name": "Suresh Gupta", "skills": ["HVAC", "Mechanical", "Electrical"]},
                "+919000022222": {"name": "Neha Singh", "skills": ["Network", "IT", "Electronics"]},
                "+919000022223": {"name": "Vikram Joshi", "skills": ["Cash Management", "Security"]}
            },
            "Bengaluru": {
                "+919000033331": {"name": "Karthik Reddy", "skills": ["IT", "Network", "Software"]},
                "+919000033332": {"name": "Lakshmi Iyer", "skills": ["HVAC", "Electrical", "Mechanical"]},
                "+919000033333": {"name": "Ravi Prasad", "skills": ["Cash Management", "Security", "Mechanical"]}
            }
        }
        
        city_techs = technicians.get(city, {"+91 90000 00000": ["General"]})
        assignments = {}
        
        for wo in work_orders:
            required_skills = wo.get("required_skills", [])
            
            # Find best match technician
            best_tech = None
            max_matches = 0
            
            for tech, skills in city_techs.items():
                matches = len(set(required_skills) & set(skills))
                if matches > max_matches:
                    max_matches = matches
                    best_tech = tech
            
            assignments[wo["id"]] = best_tech or list(city_techs.keys())[0]
        
        return assignments
    
    def _estimate_parts_needed(self, action: Dict[str, Any]) -> List[str]:
        """Estimate parts needed based on action type"""
        parts_map = {
            "HVAC": ["air_filter", "cooling_fan", "temperature_sensor"],
            "Network": ["network_cable", "router", "network_card"],
            "Mechanical": ["belt", "motor", "sensor"],
            "Cash Management": ["cash_cassette", "dispenser_parts"]
        }
        
        required_skills = action.get("required_skills", [])
        parts = []
        
        for skill in required_skills:
            if skill in parts_map:
                parts.extend(parts_map[skill])
        
        return list(set(parts))  # Remove duplicates
def _send_technician_notifications(self, work_orders: List[Dict[str, Any]], 
                                     assignments: Dict[str, str],
                                     location: Dict[str, str]) -> List[Dict[str, Any]]:
        """Send SMS notifications to assigned technicians"""
        notifications = []
        
        for wo in work_orders:
            assigned_phone = assignments.get(wo["id"])
            if assigned_phone and twilio_client:
                # Get technician name
                city_techs = technicians.get(location["city"], {})
                tech_info = city_techs.get(assigned_phone, {})
                tech_name = tech_info.get("name", "Technician")
                
                # Create message
                priority_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "📋", "LOW": "📝"}
                emoji = priority_emoji.get(wo["priority"], "📝")
                
                message = f"""
{emoji} ATM Maintenance Alert
Work Order: {wo["id"]}
Priority: {wo["priority"]}
Location: {wo["location"]}
Task: {wo["title"]}
Est. Time: {wo["estimated_time"]}
Please respond within 30 minutes.
"""
                
                # Send SMS
                sms_sent = send_sms_alert(assigned_phone, message.strip())
                
                notifications.append({
                    "work_order_id": wo["id"],
                    "technician_phone": assigned_phone,
                    "technician_name": tech_name,
                    "message_sent": sms_sent,
                    "timestamp": datetime.now().isoformat(),
                    "message": message.strip()
                })
        
        return notifications

class SettingsAgent:
    """New settings agent for system configuration and optimization"""
    
    def __init__(self):
        self.name = "SettingsAgent"
    
    async def process(self, state: ATMState) -> ATMState:
        """Process settings and configuration optimization"""
        try:
            # Analyze current configuration
            config_analysis = self._analyze_current_configuration(
                state["latest_metrics"],
                state["system_health_score"]
            )
            
            # Generate optimization recommendations
            optimizations = self._generate_optimization_recommendations(
                config_analysis,
                state["analytics_results"]
            )
            
            # Update system settings
            updated_settings = self._update_system_settings(
                state["system_settings"],
                optimizations
            )
            
            # Update state
            state["system_settings"] = updated_settings
            state["optimization_recommendations"] = optimizations
            
            state["agent_outputs"][self.name] = {
                "status": "completed",
                "optimizations_identified": len(optimizations),
                "settings_updated": len(updated_settings),
                "performance_gain_expected": config_analysis.get("potential_improvement", 0),
                "timestamp": datetime.now().isoformat()
            }
            
            state["messages"].append(
                AIMessage(content=f"Settings optimization complete. {len(optimizations)} recommendations generated")
            )
            
            return state
            
        except Exception as e:
            state["messages"].append(AIMessage(content=f"Settings agent error: {str(e)}"))
            return state
    
    def _analyze_current_configuration(self, metrics: Optional[Dict[str, Any]], 
                                     health_score: float) -> Dict[str, Any]:
        """Analyze current system configuration"""
        analysis = {
            "overall_efficiency": health_score,
            "bottlenecks": [],
            "optimization_opportunities": [],
            "potential_improvement": 0
        }
        
        if not metrics:
            return analysis
        
        # Identify bottlenecks
        if metrics["temperature_c"] > 38:
            analysis["bottlenecks"].append("thermal_management")
            analysis["potential_improvement"] += 10
        
        if metrics["network_latency_ms"] > 150:
            analysis["bottlenecks"].append("network_configuration")
            analysis["potential_improvement"] += 15
        
        if metrics.get("availability_24h", 100) < 95:
            analysis["bottlenecks"].append("system_stability")
            analysis["potential_improvement"] += 20
        
        return analysis
    
    def _generate_optimization_recommendations(self, config_analysis: Dict[str, Any], 
                                             analytics: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate optimization recommendations"""
        recommendations = []
        
        bottlenecks = config_analysis.get("bottlenecks", [])
        
        if "thermal_management" in bottlenecks:
            recommendations.append({
                "category": "thermal",
                "title": "Optimize Cooling Schedule",
                "description": "Implement smart cooling based on usage patterns",
                "expected_benefit": "10-15% temperature reduction",
                "implementation_effort": "Medium",
                "estimated_savings": "$500/month"
            })
        
        if "network_configuration" in bottlenecks:
            recommendations.append({
                "category": "network",
                "title": "Network QoS Configuration",
                "description": "Prioritize transaction traffic for better performance",
                "expected_benefit": "30-40% latency reduction",
                "implementation_effort": "Low",
                "estimated_savings": "$200/month"
            })
        
        # Analytics-based recommendations
        if analytics and "trends" in analytics:
            trends = analytics["trends"]
            for metric, trend_data in trends.items():
                if trend_data["direction"] == "increasing" and trend_data["magnitude"] > 0.1:
                    recommendations.append({
                        "category": "predictive",
                        "title": f"Proactive {metric} Management",
                        "description": f"Address increasing {metric} trend before issues occur",
                        "expected_benefit": "Prevent 80% of related failures",
                        "implementation_effort": "Low",
                        "estimated_savings": "$1000/incident"
                    })
        
        return recommendations
    
    def _update_system_settings(self, current_settings: Dict[str, Any], 
                               optimizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update system settings based on optimizations"""
        # Default settings
        settings = current_settings or {
            "temperature_thresholds": {"warning": 40, "critical": 42},
            "network_thresholds": {"warning": 120, "critical": 250},
            "maintenance_intervals": {"preventive": 21, "inspection": 7},
            "alert_settings": {"enabled": True, "severity_filter": "medium"},
            "auto_responses": {"enabled": True, "temperature": True, "network": True}
        }
        
        # Apply optimizations
        for opt in optimizations:
            if opt["category"] == "thermal":
                settings["temperature_thresholds"]["warning"] = 38
                settings["auto_responses"]["cooling_boost"] = True
            elif opt["category"] == "network":
                settings["network_thresholds"]["warning"] = 100
                settings["auto_responses"]["network_failover"] = True
        
        settings["last_updated"] = datetime.now().isoformat()
        settings["optimization_version"] = "1.2"
        
        return settings

# ===========================
# ENHANCED UTILITY FUNCTIONS
# ===========================
def make_enhanced_synthetic_data(city: str, branch: str, n_minutes: int = 2880):
    """Generate enhanced synthetic IoT sensor data with realistic patterns and more likely alerts"""
    now = datetime.now()
    idx = pd.date_range(end=now, periods=n_minutes, freq="T")
    
    # More realistic temperature patterns with daily cycles and increased chance of alerts
    hour_cycle = np.sin(2 * np.pi * np.arange(n_minutes) / (24 * 60)) * 3  # Daily temperature cycle
    base_temp = np.random.normal(38, 2.0, size=n_minutes) + hour_cycle  # Increased base temp and variance
    
    # Temperature spikes and failures - increased probability for demo
    spike_prob = 0.01  # 1% chance per minute (increased from 0.5%)
    spikes = (np.random.rand(n_minutes) < spike_prob) * np.random.uniform(3, 8, size=n_minutes)
    temperature_c = np.clip(base_temp + spikes, 25, 60)
    
    # Enhanced network metrics with congestion patterns - more likely to exceed thresholds
    base_latency = 80 + np.sin(2 * np.pi * np.arange(n_minutes) / (12 * 60)) * 30  # Higher base latency
    congestion = (np.random.rand(n_minutes) < 0.05) * np.random.uniform(80, 300, size=n_minutes)  # Increased congestion
    network_latency_ms = np.clip(base_latency + congestion + np.random.normal(0, 20, size=n_minutes), 20, 1000)
    
    # Packet loss correlated with high latency
    packet_loss_pct = np.clip(
        (network_latency_ms - 60) / 80 + np.random.exponential(0.3, size=n_minutes), 
        0, 15
    )
    
    # Enhanced vibration with equipment wear patterns - higher chance of alerts
    wear_factor = np.linspace(0.05, 0.12, n_minutes)  # Increased wear factor
    vibration_spikes = (np.random.rand(n_minutes) < 0.005) * np.random.uniform(0.2, 0.5)  # Increased probability
    vibration_g = np.clip(wear_factor + np.random.normal(0, 0.02, size=n_minutes) + vibration_spikes, 0, 2)
    
    # Enhanced cash level with realistic usage patterns - more likely to trigger low cash alerts
    usage_intensity = 1.5 + 0.8 * np.sin(2 * np.pi * np.arange(n_minutes) / (24 * 60))  # Increased usage
    cash_usage = np.cumsum(np.random.exponential(0.15, size=n_minutes) * usage_intensity)  # Faster depletion
    refills = (np.random.rand(n_minutes) < 0.008) * 70  # Less frequent, smaller refills
    cash_level_pct = np.clip(100 - (cash_usage - np.cumsum(refills)) * 0.8, 0, 100)  # Faster depletion
    
    # Other metrics with higher failure rates
    door_open_events = (np.random.rand(n_minutes) < 0.002).astype(int)  # Increased rate
    dispenser_jam = (np.random.rand(n_minutes) < 0.003).astype(int)  # Increased jam rate
    jams_cum = pd.Series(dispenser_jam).rolling(1440, min_periods=1).sum().values
    
    uptime_minutes = np.cumsum(1 - (np.random.rand(n_minutes) < 0.0002).astype(int))  # Slightly more downtimes
    uptime_hours = uptime_minutes / 60.0
    
    last_maint_days = np.clip(np.random.normal(20, 10, size=n_minutes), 0, 90)  # Longer since maintenance
    
    df = pd.DataFrame({
        "timestamp": idx,
        "city": city,
        "branch": branch,
        "atm_id": f"{city[:3].upper()}-{branch}-{str(uuid.uuid4())[:8]}",
        "temperature_c": temperature_c,
        "network_latency_ms": network_latency_ms,
        "packet_loss_pct": packet_loss_pct,
        "vibration_g": vibration_g,
        "door_open_events": door_open_events,
        "dispenser_jams_last_24h": jams_cum.astype(int),
        "cash_level_pct": cash_level_pct,
        "uptime_hours": uptime_hours,
        "last_maint_days": last_maint_days,
    })
    
    # Enhanced failure prediction with higher risk scores
    risk_score = (
        (df["temperature_c"] > 38).astype(int) * 2 +  # Lower threshold
        (df["packet_loss_pct"] > 2).astype(int) +     # Lower threshold
        (df["vibration_g"] > 0.1).astype(int) * 2 +   # Lower threshold
        (df["dispenser_jams_last_24h"] > 1).astype(int) * 2 +  # Lower threshold
        (df["last_maint_days"] > 15).astype(int) +     # Lower threshold
        (df["network_latency_ms"] > 120).astype(int)   # Lower threshold
    )
    df["will_fail_24h"] = (risk_score + (np.random.rand(len(df)) < 0.03).astype(int) > 2).astype(int)  # Lower threshold for failure
    
    return df

def load_csv_data(uploaded_file) -> Optional[pd.DataFrame]:
    """Load and validate uploaded CSV data"""
    try:
        # Read CSV
        df = pd.read_csv(uploaded_file)
        
        # Required columns for ATM data
        required_cols = ["temperature_c", "network_latency_ms", "cash_level_pct"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            return None
        
        # Add timestamp if not present
        if "timestamp" not in df.columns:
            df["timestamp"] = pd.date_range(end=datetime.now(), periods=len(df), freq="T")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Fill missing optional columns with defaults
        optional_cols = {
            "packet_loss_pct": 1.0,
            "vibration_g": 0.02,
            "door_open_events": 0,
            "dispenser_jams_last_24h": 0,
            "uptime_hours": 24.0,
            "last_maint_days": 15.0
        }
        
        for col, default_val in optional_cols.items():
            if col not in df.columns:
                df[col] = default_val
        
        # Data validation
        if len(df) < 10:
            st.error("Insufficient data points (minimum 10 required)")
            return None
        
        st.success(f"Successfully loaded {len(df)} data points from CSV")
        return df
        
    except Exception as e:
        st.error(f"Error loading CSV: {str(e)}")
        return None

# ===========================
# ENHANCED WORKFLOW CREATION
# ===========================
def create_enhanced_atm_workflow() -> StateGraph:
    """Create enhanced LangGraph workflow with 5 agents"""
    
    workflow = StateGraph(ATMState)
    
    # Initialize all agents
    monitoring_agent = MonitoringAgent()
    analytics_agent = AnalyticsAgent()
    actions_agent = ActionsAgent()
    maintenance_agent = MaintenanceAgent()
    settings_agent = SettingsAgent()
    
    # Define agent processing functions
    async def run_monitoring(state: ATMState) -> ATMState:
        state["current_agent"] = "MonitoringAgent"
        return await monitoring_agent.process(state)
    
    async def run_analytics(state: ATMState) -> ATMState:
        state["current_agent"] = "AnalyticsAgent"
        return await analytics_agent.process(state)
    
    async def run_actions(state: ATMState) -> ATMState:
        state["current_agent"] = "ActionsAgent"
        return await actions_agent.process(state)
    
    async def run_maintenance(state: ATMState) -> ATMState:
        state["current_agent"] = "MaintenanceAgent"
        return await maintenance_agent.process(state)
    
    async def run_settings(state: ATMState) -> ATMState:
        state["current_agent"] = "SettingsAgent"
        return await settings_agent.process(state)
    
    # Add nodes to workflow
    workflow.add_node("monitoring", run_monitoring)
    workflow.add_node("analytics", run_analytics)
    workflow.add_node("actions", run_actions)
    workflow.add_node("maintenance", run_maintenance)
    workflow.add_node("settings", run_settings)
    
    # Define workflow edges - sequential processing
    workflow.set_entry_point("monitoring")
    workflow.add_edge("monitoring", "analytics")
    workflow.add_edge("analytics", "actions")
    workflow.add_edge("actions", "maintenance")
    workflow.add_edge("maintenance", "settings")
    workflow.add_edge("settings", END)
    
    return workflow

# ===========================
# STREAMLIT APP CONFIGURATION
# ===========================
st.set_page_config(
    page_title="Enhanced ATM Multi-Agent System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS
def load_mobile_first_css(css_file: str = "styles.css"):
    """Load mobile-first card design CSS from external file"""
    css_path = Path(css_file)
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"CSS file not found: {css_file}")

load_mobile_first_css()

# ===========================
# CONSTANTS AND DEFAULTS
# ===========================
INDIA_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Ahmedabad", "Chennai",
    "Kolkata", "Pune", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur",
]

DEFAULT_BRANCHES = {
    "Mumbai": ["Fort-01", "Andheri-07", "Bandra-02"],
    "Delhi": ["Connaught-03", "Saket-04", "Dwarka-01"],
    "Bengaluru": ["MG-Road-05", "ElectronicCity-02", "Whitefield-06"],
    "Hyderabad": ["Gachibowli-01", "Hitech-05", "Banjara-02"],
    "Ahmedabad": ["Navrangpura-09", "Maninagar-03"],
    "Chennai": ["T-Nagar-01", "Velachery-02"],
    "Kolkata": ["SaltLake-01", "ParkStreet-02"],
    "Pune": ["Kothrud-01", "Hinjewadi-02"],
    "Jaipur": ["MI-Road-01", "Vaishali-02"],
    "Surat": ["Adajan-01", "Vesu-02"],
    "Lucknow": ["Hazratganj-01", "GomtiNagar-02"],
    "Kanpur": ["SwaroopNagar-01", "Kakadeo-02"],
    "Nagpur": ["Dhantoli-01", "Sitabuldi-02"],
}

# Default system settings
DEFAULT_SETTINGS = {
    "temperature_thresholds": {"warning": 40, "critical": 42},
    "network_thresholds": {"warning": 120, "critical": 250},
    "cash_thresholds": {"warning": 30, "critical": 15},
    "vibration_thresholds": {"warning": 0.15, "critical": 0.3},
    "maintenance_intervals": {"preventive": 21, "inspection": 7},
    "alert_settings": {"enabled": True, "severity_filter": "medium"},
    "auto_responses": {"enabled": True, "temperature": True, "network": True}
}

# ===========================
# SESSION STATE INITIALIZATION
# ===========================
if 'workflow_results' not in st.session_state:
    st.session_state.workflow_results = None
if 'uploaded_data' not in st.session_state:
    st.session_state.uploaded_data = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "Monitor"

# ===========================
# ENHANCED SIDEBAR
# ===========================
with st.sidebar:
    st.markdown("### 🤖 Enhanced ATM Control Center")
    
    # Location Selection
    st.markdown("#### 📍 Location")
    city = st.selectbox("City", INDIA_CITIES, index=2)
    branches = DEFAULT_BRANCHES.get(city, ["Main-01"])
    branch = st.selectbox("Branch", branches)
    
    st.markdown("---")
    
    # CSV Upload Component
    st.markdown("#### 📊 Data Source")
    data_source = st.radio("Select Data Source", ["Synthetic Data", "Upload CSV"])
    
    uploaded_file = None
    if data_source == "Upload CSV":
        uploaded_file = st.file_uploader(
            "Upload ATM Sensor Data",
            type=['csv'],
            help="CSV should contain: temperature_c, network_latency_ms, cash_level_pct columns"
        )
        
        if uploaded_file:
            st.session_state.uploaded_data = load_csv_data(uploaded_file)
            if st.session_state.uploaded_data is not None:
                st.success(f"Loaded {len(st.session_state.uploaded_data)} records")
        else:
            st.session_state.uploaded_data = None
    
    st.markdown("---")
    
    # Agent Configuration
    st.markdown("#### 🤖 Agent Configuration")
    agents_config = {
        "monitoring": st.checkbox("Monitoring Agent", value=True, help="Data collection and health monitoring"),
        "analytics": st.checkbox("Analytics Agent", value=True, help="Advanced analytics and predictions"),
        "actions": st.checkbox("Actions Agent", value=True, help="Decision making and response coordination"),
        "maintenance": st.checkbox("Maintenance Agent", value=True, help="Work order and scheduling management"),
        "settings": st.checkbox("Settings Agent", value=True, help="System optimization and configuration")
    }
    
    st.markdown("---")
    
    # Threshold Configuration
    st.markdown("#### ⚠️ Alert Thresholds")
    
    temp_warning = st.slider("Temperature Warning (°C)", 35.0, 45.0, 40.0, 0.5)
    temp_critical = st.slider("Temperature Critical (°C)", 40.0, 50.0, 42.0, 0.5)
    
    network_warning = st.slider("Network Warning (ms)", 50, 200, 120, 10)
    network_critical = st.slider("Network Critical (ms)", 200, 500, 250, 25)
    
    cash_warning = st.slider("Cash Warning (%)", 10, 50, 30, 5)
    cash_critical = st.slider("Cash Critical (%)", 5, 30, 15, 5)
    
    st.markdown("---")
    
    # System Settings
    st.markdown("#### 🔧 System Settings")
    auto_responses = st.checkbox("Enable Auto Responses", value=True)
    notification_level = st.selectbox("Notification Level", ["Critical Only", "High & Critical", "All Alerts"], index=1)
    
    # Gemini Configuration
    st.markdown("#### 🧠 AI Configuration")
    gemini_enabled = st.checkbox("Enable Gemini AI", value=GEMINI_OK and bool(GEMINI_API_KEY))
    
    if gemini_enabled and not (GEMINI_OK and GEMINI_API_KEY):
        st.error("Gemini API key required")
        gemini_enabled = False
    
    st.markdown("#### 📱 SMS Alerts")
    twilio_enabled = st.checkbox("Enable SMS Notifications", value=bool(twilio_client))

    if twilio_enabled and not twilio_client:
        st.error("Twilio not configured properly")
    elif twilio_enabled:
        st.success("SMS notifications enabled")
        st.info(f"From: {TWILIO_PHONE_NUMBER}")


# ===========================
# MAIN INTERFACE WITH TABS
# ===========================
st.markdown(f"""
<div class="main-header">
    <h1>🤖 Enhanced ATM Multi-Agent System</h1>
    <p>{city} • {branch} • {len([k for k, v in agents_config.items() if v])} Agents Active</p>
</div>
""", unsafe_allow_html=True)

# Tab Navigation
# Tab Navigation
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Monitor", "📈 Analytics", "⚡ Actions", "🔧 Maintenance", "⚙️ Settings", "🤖 ML & AI"])

with tab1:  # Monitor Tab
    st.markdown("### 📊 System Monitoring & AI Analysis")
    
    # Execute Diagnostics Section
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.button("🔍 Execute System Diagnostics", type="primary", use_container_width=True):
            if not any(agents_config.values()):
                st.error("At least one agent must be enabled")
            else:
                # Initialize enhanced state
                initial_state = ATMState(
                    sensor_data=None,
                    uploaded_data=st.session_state.uploaded_data,
                    latest_metrics=None,
                    risk_assessment=None,
                    analytics_results=None,
                    alerts=[],
                    system_health_score=0.0,
                    recommended_actions=[],
                    automated_responses=[],
                    work_orders=[],
                    maintenance_schedule=[],
                    technician_assignments={},
                    system_settings=DEFAULT_SETTINGS.copy(),
                    optimization_recommendations=[],
                    messages=[HumanMessage(content="Starting enhanced ATM analysis workflow")],
                    notifications_sent=[],
                    location={"city": city, "branch": branch},
                    thresholds={
                        "temp_warning": temp_warning, "temp_critical": temp_critical,
                        "network_warning": network_warning, "network_critical": network_critical,
                        "cash_warning": cash_warning, "cash_critical": cash_critical
                    },
                    current_agent="",
                    agent_outputs={},
                    should_escalate=False
                )
                
                # Create progress tracking
                with st.container():
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                try:
                    # Run workflow with enabled agents
                    result = initial_state.copy()
                    step = 0
                    total_steps = sum(agents_config.values())
                    
                    # Run each agent based on configuration
                    if agents_config["monitoring"]:
                        step += 1
                        status_text.markdown(f"🔴 Monitoring Agent Active ({step}/{total_steps})")
                        progress_bar.progress(step / total_steps * 0.8)
                        monitoring_agent = MonitoringAgent()
                        result = asyncio.run(monitoring_agent.process(result))
                        time.sleep(0.8)
                    
                    if agents_config["analytics"]:
                        step += 1
                        status_text.markdown(f"🔵 Analytics Agent Processing ({step}/{total_steps})")
                        progress_bar.progress(step / total_steps * 0.8)
                        analytics_agent = AnalyticsAgent()
                        result = asyncio.run(analytics_agent.process(result))
                        time.sleep(0.8)
                    
                    if agents_config["actions"]:
                        step += 1
                        status_text.markdown(f"🟡 Actions Agent Analyzing ({step}/{total_steps})")
                        progress_bar.progress(step / total_steps * 0.8)
                        actions_agent = ActionsAgent()
                        result = asyncio.run(actions_agent.process(result))
                        time.sleep(0.8)
                    
                    if agents_config["maintenance"]:
                        step += 1
                        status_text.markdown(f"🟢 Maintenance Agent Coordinating ({step}/{total_steps})")
                        progress_bar.progress(step / total_steps * 0.8)
                        maintenance_agent = MaintenanceAgent()
                        result = asyncio.run(maintenance_agent.process(result))
                        time.sleep(0.8)
                    
                    if agents_config["settings"]:
                        step += 1
                        status_text.markdown(f"🟣 Settings Agent Optimizing ({step}/{total_steps})")
                        progress_bar.progress(step / total_steps * 0.8)
                        settings_agent = SettingsAgent()
                        result = asyncio.run(settings_agent.process(result))
                        time.sleep(0.8)
                    
                    progress_bar.progress(1.0)
                    status_text.markdown("✅ All diagnostic agents executed successfully!")
                    
                    st.session_state.workflow_results = result
                    time.sleep(1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"System diagnostic failed: {str(e)}")
    
    with col2:
        if st.session_state.workflow_results:
            health_score = st.session_state.workflow_results["system_health_score"]
            st.metric(
                "System Health", 
                f"{health_score:.0f}%", 
                delta=f"{health_score - 75:.0f}%" if health_score != 75 else None,
                help="Overall system health score based on all metrics"
            )
        else:
            st.info("Run diagnostics to see system health")

    # Display results only if workflow has been executed
    if st.session_state.workflow_results:
        results = st.session_state.workflow_results
        monitoring_output = results.get("agent_outputs", {}).get("MonitoringAgent", {})
        ml_prediction = monitoring_output.get("ml_prediction", {})
        ml_training = monitoring_output.get("ml_training", {})
        gemini_insights = monitoring_output.get("gemini_insights", "")
        
        # Critical Status Banner
        if ml_prediction.get("status") == "success":
            failure_prob = ml_prediction["failure_probability"]
            risk_level = ml_prediction["risk_level"]
            
            if risk_level == "CRITICAL":
                st.error(f"🚨 CRITICAL ALERT: Risk Level {failure_prob:.1%} - Immediate Action Required!")

        # AI Prediction Section
        if ml_prediction.get("status") == "success":
            st.markdown("#### 🔮 AI Failure Prediction")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                failure_prob = ml_prediction["failure_probability"]
                prob_status = "🔴 Critical" if failure_prob >= 0.7 else "⚠️ Warning" if failure_prob >= 0.3 else "✅ Normal"
                
                with st.container():
                    st.markdown(f"**🔮 Failure Probability**")
                    st.markdown(f"### {failure_prob * 100:.1f}%")
                    st.markdown(f"**Status:** {prob_status}")
                    st.markdown(f"**Will fail in 24h:** {'Yes' if ml_prediction.get('will_fail') else 'No'}")
                    if failure_prob >= 0.7:
                        st.markdown("**Action:** 🚨 Immediate maintenance required")
                    elif failure_prob >= 0.3:
                        st.markdown("**Action:** ⚠️ Schedule maintenance soon")
                    else:
                        st.markdown("**Action:** ✅ Routine monitoring")
            
            with col2:
                risk_level = ml_prediction["risk_level"]
                risk_icons = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
                
                with st.container():
                    st.markdown(f"**⚠️ Risk Level**")
                    st.markdown(f"### {risk_icons.get(risk_level, '⚪')} {risk_level}")
                    st.markdown(f"**Confidence:** {ml_prediction.get('confidence', 0) * 100:.1f}%")
                    st.markdown("**Model accuracy:** High")
                    st.markdown("**Prediction reliability:** Excellent")
            
            with col3:
                confidence = ml_prediction.get("confidence", 0)
                conf_status = "✅ Normal" if confidence >= 0.8 else "⚠️ Fair"
                
                with st.container():
                    st.markdown(f"**🎯 AI Confidence**")
                    st.markdown(f"### {confidence * 100:.1f}%")
                    st.markdown(f"**Status:** {conf_status}")
                    st.markdown(f"**Data quality:** {'High' if confidence >= 0.8 else 'Moderate'}")
                    st.markdown(f"**Prediction:** {'Reliable' if confidence >= 0.8 else 'Fair'}")

        # Current System Metrics Section
        if ml_prediction.get("status") == "success" and "feature_values" in ml_prediction:
            st.markdown("#### 📊 Current System Metrics")
            
            feature_values = ml_prediction["feature_values"]
            
            # Create columns for metrics
            metrics_per_row = min(len(feature_values), 4)
            cols = st.columns(metrics_per_row)
            
            for idx, (feature, value) in enumerate(feature_values.items()):
                with cols[idx % metrics_per_row]:
                    display_name = feature.replace('_', ' ').title()
                    
                    # Determine status and details based on feature type
                    if 'temperature' in feature:
                        status = "🔴 Critical" if value > 42 else "⚠️ Warning" if value > 40 else "✅ Normal"
                        unit = "°C"
                        icon = "🌡️"
                        optimal = "20-35°C"
                        cooling_status = "Check required" if value > 40 else "Operating normally"
                    elif 'latency' in feature:
                        status = "🔴 Critical" if value > 250 else "⚠️ Warning" if value > 120 else "✅ Normal"
                        unit = "ms"
                        icon = "🌐"
                        optimal = "<120ms"
                        cooling_status = "Unstable" if value > 120 else "Stable"
                    elif 'cash' in feature and 'level' in feature:
                        status = "🔴 Critical" if value < 15 else "⚠️ Warning" if value < 30 else "✅ Normal"
                        unit = "%"
                        icon = "💰"
                        optimal = ">30%"
                        est_hours = int(value / 25 * 4) if value > 0 else 0
                        cooling_status = f"~{est_hours} hours remaining"
                    elif 'vibration' in feature:
                        status = "🔴 Critical" if value > 0.3 else "⚠️ Warning" if value > 0.15 else "✅ Normal"
                        unit = "g"
                        icon = "📳"
                        optimal = "<0.15g"
                        cooling_status = "Check mounts" if value > 0.15 else "Stable"
                    else:
                        status = "✅ Normal"
                        unit = ""
                        icon = "📊"
                        optimal = "Normal range"
                        cooling_status = "Operating"
                    
                    with st.container():
                        st.markdown(f"**{icon} {display_name}**")
                        if 'temperature' in feature or 'latency' in feature:
                            st.markdown(f"### {value:.1f}{unit}")
                        else:
                            st.markdown(f"### {value:.2f}{unit}")
                        st.markdown(f"**Status:** {status}")
                        st.markdown(f"**Optimal:** {optimal}")
                        st.markdown(f"**Info:** {cooling_status}")

        # AI Insights Section (keeping only this)
        if gemini_insights and gemini_insights != "Gemini AI not available":
            st.markdown("#### 🧠 AI Expert Analysis")
            with st.container():
                st.info("🤖 **Gemini AI Insights:**")
                st.markdown(gemini_insights)

    else:
        # Welcome message when no results available
        st.info("🚀 **Ready for System Analysis**\n\nClick 'Execute System Diagnostics' to see ML predictions, AI insights, and system metrics")        
with tab2:  # Analytics Tab
    st.markdown("### 📈 Advanced Analytics Dashboard")
    
    if st.session_state.workflow_results and st.session_state.workflow_results.get("sensor_data") is not None:
        sensor_data = st.session_state.workflow_results["sensor_data"]
        analytics_results = st.session_state.workflow_results.get("analytics_results", {})
        
        # Time frame selection
        time_frame = st.selectbox(
            "Select Time Frame",
            ["Last 2 Hours", "Last 6 Hours", "Last 12 Hours", "Last 24 Hours", "Last 3 Days", "Last Week"],
            index=3  # Default to Last 24 Hours
        )
        
        # Map time frame to data points
        time_mapping = {
            "Last 2 Hours": 120,
            "Last 6 Hours": 360,
            "Last 12 Hours": 720,
            "Last 24 Hours": 1440,
            "Last 3 Days": 4320,
            "Last Week": 10080
        }
        
        data_points = time_mapping[time_frame]
        filtered_data = sensor_data.tail(min(data_points, len(sensor_data))).copy()
        
        # Create proper timestamps for display if they don't exist
        if "timestamp" not in filtered_data.columns:
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=len(filtered_data))
            filtered_data["timestamp"] = pd.date_range(start=start_time, end=end_time, periods=len(filtered_data))
        else:
            filtered_data["timestamp"] = pd.to_datetime(filtered_data["timestamp"])
        
        # Temperature Trends
        st.markdown(f"#### 🌡️ Temperature Trends - {time_frame}")
        
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(
            x=filtered_data["timestamp"],
            y=filtered_data["temperature_c"],
            mode='lines',
            name='Temperature',
            line=dict(color='#4fc3f7', width=2)
        ))
        
        # Add threshold lines using sidebar values
        fig_temp.add_hline(
            y=temp_warning,
            line_dash="dash",
            line_color="orange",
            annotation_text="Warning Threshold",
            annotation_position="top right"
        )
        fig_temp.add_hline(
            y=temp_critical,
            line_dash="dash",
            line_color="red",
            annotation_text="Critical Threshold",
            annotation_position="top right"
        )

        fig_temp.update_layout(
            title=f"ATM Internal Temperature Over Time",
            xaxis_title="timestamp",
            yaxis_title="temperature_c",
            template="plotly_dark",
            height=400,
            plot_bgcolor='rgba(45, 55, 72, 1)',
            paper_bgcolor='rgba(45, 55, 72, 1)',
            font=dict(color='white')
        )

        st.plotly_chart(fig_temp, use_container_width=True)

        # Network Performance Analytics
        st.markdown(f"#### 🌐 Network Performance - {time_frame}")
        
        fig_network = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Network Latency', 'Packet Loss %'),
            vertical_spacing=0.15,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )

        # Network Latency Plot
        fig_network.add_trace(
            go.Scatter(
                x=filtered_data["timestamp"],
                y=filtered_data["network_latency_ms"],
                mode='lines',
                name='Network Latency',
                line=dict(color='#4fc3f7', width=2)
            ),
            row=1, col=1
        )

        # Packet Loss Plot
        fig_network.add_trace(
            go.Scatter(
                x=filtered_data["timestamp"],
                y=filtered_data["packet_loss_pct"],
                mode='lines',
                name='Packet Loss',
                line=dict(color='#ff9800', width=2)
            ),
            row=2, col=1
        )

        # Update layout for network chart
        fig_network.update_layout(
            title="🌐 Network Performance",
            template="plotly_dark",
            height=500,
            plot_bgcolor='rgba(45, 55, 72, 1)',
            paper_bgcolor='rgba(45, 55, 72, 1)',
            font=dict(color='white'),
            showlegend=False
        )

        # Update y-axis labels
        fig_network.update_yaxes(title_text="network_latency_ms", row=1, col=1)
        fig_network.update_yaxes(title_text="packet_loss_pct", row=2, col=1)
        fig_network.update_xaxes(title_text="timestamp", row=2, col=1)

        st.plotly_chart(fig_network, use_container_width=True)

        # Cash Level Trends
        st.markdown(f"#### 💰 Cash Level Monitor - {time_frame}")
        
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Scatter(
            x=filtered_data["timestamp"],
            y=filtered_data["cash_level_pct"],
            mode='lines',
            name='Cash Level',
            line=dict(color='#10b981', width=2),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.1)'
        ))
        
        # Add cash threshold lines
        fig_cash.add_hline(
            y=cash_warning,
            line_dash="dash",
            line_color="orange",
            annotation_text="Warning Threshold",
            annotation_position="top right"
        )
        fig_cash.add_hline(
            y=cash_critical,
            line_dash="dash",
            line_color="red",
            annotation_text="Critical Threshold",
            annotation_position="top right"
        )

        fig_cash.update_layout(
            title=f"Cash Level Monitor",
            xaxis_title="timestamp",
            yaxis_title="cash_level_pct",
            template="plotly_dark",
            height=400,
            yaxis=dict(range=[0, 100]),
            plot_bgcolor='rgba(45, 55, 72, 1)',
            paper_bgcolor='rgba(45, 55, 72, 1)',
            font=dict(color='white')
        )

        st.plotly_chart(fig_cash, use_container_width=True)

        # Vibration Analysis
        st.markdown(f"#### ⚡ Vibration Analysis - {time_frame}")
        
        fig_vibration = go.Figure()
        fig_vibration.add_trace(go.Scatter(
            x=filtered_data["timestamp"],
            y=filtered_data["vibration_g"],
            mode='lines',
            name='Vibration Level',
            line=dict(color='#e91e63', width=2)
        ))
        
        # Add vibration threshold lines
        fig_vibration.add_hline(
            y=0.15,
            line_dash="dash",
            line_color="orange",
            annotation_text="Warning Threshold",
            annotation_position="top right"
        )
        fig_vibration.add_hline(
            y=0.3,
            line_dash="dash",
            line_color="red",
            annotation_text="Critical Threshold",
            annotation_position="top right"
        )

        fig_vibration.update_layout(
            title=f"Mechanical Vibration Levels",
            xaxis_title="timestamp",
            yaxis_title="vibration_g",
            template="plotly_dark",
            height=400,
            plot_bgcolor='rgba(45, 55, 72, 1)',
            paper_bgcolor='rgba(45, 55, 72, 1)',
            font=dict(color='white')
        )

        st.plotly_chart(fig_vibration, use_container_width=True)

        # System Health Over Time
        st.markdown(f"#### 📊 System Health Score - {time_frame}")
        
        # Calculate health scores for the filtered timeframe
        health_scores = []
        timestamps_for_health = []
        window_size = max(1, len(filtered_data) // 50)  # More granular windows
        
        for i in range(0, len(filtered_data), window_size):
            window = filtered_data.iloc[i:i+window_size]
            if len(window) > 0:
                # Health calculation based on multiple factors
                temp_score = max(0, 100 - max(0, window["temperature_c"].mean() - 35) * 5)
                network_score = max(0, 100 - max(0, window["network_latency_ms"].mean() - 80) / 5)
                cash_score = min(100, window["cash_level_pct"].mean())
                vibration_score = max(0, 100 - window["vibration_g"].mean() * 200)
                
                overall_score = (temp_score + network_score + cash_score + vibration_score) / 4
                health_scores.append(overall_score)
                timestamps_for_health.append(window["timestamp"].iloc[len(window)//2])

        if health_scores:
            fig_health = go.Figure()
            fig_health.add_trace(go.Scatter(
                x=timestamps_for_health,
                y=health_scores,
                mode='lines+markers',
                name='Health Score',
                line=dict(color='#10b981', width=3),
                marker=dict(size=6)
            ))

            fig_health.add_hline(
                y=70,
                line_dash="dash",
                line_color="orange",
                annotation_text="Action Required",
                annotation_position="top right"
            )
            fig_health.add_hline(
                y=50,
                line_dash="dash",
                line_color="red",
                annotation_text="Critical",
                annotation_position="top right"
            )

            fig_health.update_layout(
                title=f"System Health Score Trend",
                xaxis_title="timestamp",
                yaxis_title="Health Score (%)",
                template="plotly_dark",
                height=400,
                yaxis=dict(range=[0, 100]),
                plot_bgcolor='rgba(45, 55, 72, 1)',
                paper_bgcolor='rgba(45, 55, 72, 1)',
                font=dict(color='white')
            )

            st.plotly_chart(fig_health, use_container_width=True)
        
        # Predictive Insights (keep existing code)
        st.markdown("#### 🔮 Predictive Insights")
        if "predictive_insights" in analytics_results:
            insights = analytics_results["predictive_insights"]
            
            if insights:
                insight_cols = st.columns(min(len(insights), 3))
                
                for i, insight in enumerate(insights[:3]):
                    with insight_cols[i % 3]:
                        change_color = "🔴" if insight["change_percentage"] > 0 else "🟢"
                        confidence_bar = "▓" * int(insight["confidence"] * 10)
                        
                        st.markdown(f"""
                        <div class="insight-card">
                            <h4>{insight['metric'].replace('_', ' ').title()}</h4>
                            <div class="insight-values">
                                <div class="current">Current: {insight['current_value']:.2f}</div>
                                <div class="predicted">Predicted: {insight['predicted_value']:.2f}</div>
                            </div>
                            <div class="change-indicator">
                                {change_color} {insight['change_percentage']:+.1f}% change
                            </div>
                            <div class="confidence">
                                Confidence: {confidence_bar} ({insight['confidence']:.0%})
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No significant trends detected for prediction")
        
        # Performance Metrics Summary
        st.markdown("#### 📋 Current Performance Metrics")
        
        if len(filtered_data) > 0:
            latest_data = filtered_data.iloc[-1]
            
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.metric("Temperature", f"{latest_data['temperature_c']:.1f}°C", 
                         delta=f"{latest_data['temperature_c'] - temp_warning:+.1f}" if latest_data['temperature_c'] > temp_warning else None)
            
            with metric_cols[1]:
                st.metric("Network Latency", f"{latest_data['network_latency_ms']:.0f}ms",
                         delta=f"{latest_data['network_latency_ms'] - network_warning:+.0f}" if latest_data['network_latency_ms'] > network_warning else None)
            
            with metric_cols[2]:
                st.metric("Cash Level", f"{latest_data['cash_level_pct']:.0f}%",
                         delta=f"{latest_data['cash_level_pct'] - cash_critical:.0f}" if latest_data['cash_level_pct'] < cash_warning else None)
            
            with metric_cols[3]:
                st.metric("Vibration", f"{latest_data['vibration_g']:.3f}g",
                         delta="High" if latest_data['vibration_g'] > 0.15 else None)
    
    else:
        st.info("Run system diagnostics to see detailed analytics")

with tab3:  # Actions Tab
    st.markdown("### ⚡ Actions & Responses")
    
    # Check if workflow has been run and has results
    if st.session_state.workflow_results:
        results = st.session_state.workflow_results
        actions = results.get("recommended_actions", [])
        automated_responses = results.get("automated_responses", [])
        alerts = results.get("alerts", [])
        health_score = results.get("system_health_score", 0)
        
        # Quick Actions Section
        st.markdown("#### ⚡ Quick Actions")
        
        quick_action_cols = st.columns(4)
        with quick_action_cols[0]:
            if st.button("🚨 Emergency Alert", use_container_width=True, type="primary"):
                st.error("Emergency alert sent to all technicians!")
        
        with quick_action_cols[1]:
            if st.button("📊 Status Report", use_container_width=True):
                st.success("Status report generated and sent!")
        
        with quick_action_cols[2]:
            if st.button("🔄 System Restart", use_container_width=True):
                st.warning("System restart initiated...")
        
        with quick_action_cols[3]:
            if st.button("🔒 Lock ATM", use_container_width=True):
                st.info("ATM locked for maintenance")
        
        st.markdown("---")
        
        # Emergency Actions Section (when critical alerts exist)
        critical_actions = [a for a in actions if a.get("priority") == "CRITICAL"]
        if critical_actions:
            st.markdown("#### 🚨 Emergency Actions")
            
            emergency_cols = st.columns(2)
            with emergency_cols[0]:
                st.button("🚨 Emergency Alert", key="emergency_alert", use_container_width=True, type="primary")
            with emergency_cols[1]:
                st.button("📊 Status Report", key="status_report", use_container_width=True)
            
            emergency_cols2 = st.columns(2)
            with emergency_cols2[0]:
                st.button("🔄 System Restart", key="system_restart", use_container_width=True)
            with emergency_cols2[1]:
                st.button("🔒 Lock ATM", key="lock_atm", use_container_width=True)
        
        # Communication Section
        st.markdown("#### 📞 Communication")
        
        # Custom message to technician
        custom_message = st.text_area(
            "Send custom message to technician",
            value=f"Issue at {results['location']['city']}-{results['location']['branch']}: [describe the problem]",
            height=100
        )
        
        if st.button("📤 Send Message", use_container_width=True, type="primary"):
            st.success("Message sent to assigned technician!")
        
        # Recent Actions Section
        st.markdown("#### 📋 Recent Actions")
        
        # Generate some recent actions for demo
        recent_actions = [
            {"icon": "📊", "action": "Status report sent", "time": "2 minutes ago", "color": "#10b981"},
            {"icon": "🔄", "action": "Data refreshed", "time": "5 minutes ago", "color": "#3b82f6"},
            {"icon": "⚠️", "action": "Alert acknowledged", "time": "12 minutes ago", "color": "#f59e0b"},
            {"icon": "🔧", "action": "Maintenance scheduled", "time": "1 hour ago", "color": "#6b7280"}
        ]
        
        for action in recent_actions:
            st.markdown(f"""
            <div style="display: flex; align-items: center; padding: 12px; 
                       background: rgba(45, 55, 72, 0.8); border-radius: 8px; 
                       margin: 8px 0; border-left: 3px solid {action['color']};">
                <div style="font-size: 1.2em; margin-right: 12px;">{action['icon']}</div>
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: white;">{action['action']}</div>
                    <div style="font-size: 0.8em; color: #9ca3af;">{action['time']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Quick Status Section (similar to image 3)
        st.markdown("#### 📊 Quick Status")
        
        # Calculate metrics
        total_actions = len(actions)
        critical_count = len([a for a in actions if a.get("priority") == "CRITICAL"])
        high_count = len([a for a in actions if a.get("priority") == "HIGH"])
        auto_count = len(automated_responses)
        
        # Determine risk level based on ML prediction or health score
        ml_output = results.get("agent_outputs", {}).get("MonitoringAgent", {})
        ml_prediction = ml_output.get("ml_prediction", {})
        
        if ml_prediction.get("status") == "success":
            risk_percentage = ml_prediction.get("failure_probability", 0) * 100
            risk_level = ml_prediction.get("risk_level", "LOW")
        else:
            risk_percentage = max(0, (100 - health_score) / 2)  # Convert health to risk
            risk_level = "CRITICAL" if health_score < 50 else "HIGH" if health_score < 70 else "NORMAL"
        
        # Status cards matching the design in image 3
        status_cols = st.columns(3)
        
        with status_cols[0]:
            # Current Risk Card
            risk_color = "NORMAL" if risk_level in ["LOW", "NORMAL"] else "WARNING" if risk_level == "HIGH" else "CRITICAL"
            risk_bg_color = "#10b981" if risk_color == "NORMAL" else "#f59e0b" if risk_color == "WARNING" else "#ef4444"
            
            st.markdown(f"""
            <div style="background: rgba(75, 85, 99, 0.9); padding: 20px; border-radius: 15px; 
                       box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); margin: 10px 0;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    <div style="font-size: 2em;">🎯</div>
                    <div style="background: {risk_bg_color}; padding: 4px 12px; border-radius: 15px; 
                               font-size: 0.8em; font-weight: bold; color: white;">
                        {risk_color}
                    </div>
                </div>
                <div style="color: #9ca3af; font-size: 0.9em; margin-bottom: 8px; font-weight: 500;">
                    CURRENT RISK
                </div>
                <div style="color: #60a5fa; font-size: 2.2em; font-weight: bold; margin-bottom: 15px;">
                    {risk_percentage:.1f}%
                </div>
                <div style="color: #d1d5db; font-size: 0.85em; line-height: 1.4;">
                    <div>Priority: {risk_level}</div>
                    <div>Confidence: {'High' if ml_prediction.get('confidence', 0.8) > 0.7 else 'Medium'}</div>
                    <div>Last update: Just now</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with status_cols[1]:
            # Active Alerts Card
            alert_count = len(alerts)
            high_priority_alerts = len([a for a in alerts if a.get("severity") == "CRITICAL"])
            alert_status = "WARNING" if alert_count > 0 else "NORMAL"
            alert_bg_color = "#f59e0b" if alert_count > 0 else "#10b981"
            
            st.markdown(f"""
            <div style="background: rgba(75, 85, 99, 0.9); padding: 20px; border-radius: 15px; 
                       box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); margin: 10px 0;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    <div style="font-size: 2em;">🚨</div>
                    <div style="background: {alert_bg_color}; padding: 4px 12px; border-radius: 15px; 
                               font-size: 0.8em; font-weight: bold; color: white;">
                        {alert_status}
                    </div>
                </div>
                <div style="color: #9ca3af; font-size: 0.9em; margin-bottom: 8px; font-weight: 500;">
                    ACTIVE ALERTS
                </div>
                <div style="color: #60a5fa; font-size: 2.2em; font-weight: bold; margin-bottom: 15px;">
                    {alert_count} alerts
                </div>
                <div style="color: #d1d5db; font-size: 0.85em; line-height: 1.4;">
                    <div>Total alerts: {alert_count}</div>
                    <div>High priority: {high_priority_alerts}</div>
                    <div>Status: {'Needs attention' if alert_count > 0 else 'All clear'}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with status_cols[2]:
            # System Health Card
            health_status = "GOOD" if health_score >= 80 else "WARNING" if health_score >= 60 else "CRITICAL"
            health_bg_color = "#10b981" if health_score >= 80 else "#f59e0b" if health_score >= 60 else "#ef4444"
            
            st.markdown(f"""
            <div style="background: rgba(75, 85, 99, 0.9); padding: 20px; border-radius: 15px; 
                       box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); margin: 10px 0;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    <div style="font-size: 2em;">🔧</div>
                    <div style="background: {health_bg_color}; padding: 4px 12px; border-radius: 15px; 
                               font-size: 0.8em; font-weight: bold; color: white;">
                        {health_status}
                    </div>
                </div>
                <div style="color: #9ca3af; font-size: 0.9em; margin-bottom: 8px; font-weight: 500;">
                    SYSTEM HEALTH
                </div>
                <div style="color: #60a5fa; font-size: 2.2em; font-weight: bold; margin-bottom: 15px;">
                    {health_score:.0f}%
                </div>
                <div style="color: #d1d5db; font-size: 0.85em; line-height: 1.4;">
                    <div>Overall health: {health_score:.0f}%</div>
                    <div>Performance: {'Good' if health_score >= 75 else 'Fair' if health_score >= 50 else 'Poor'}</div>
                    <div>Uptime: 24.0hrs</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Detailed Actions Section (existing functionality)
        if actions:
            st.markdown("#### 📋 Detailed Action Items")
            
            priority_filter = st.selectbox("Filter by Priority", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
            filtered_actions = actions if priority_filter == "All" else [a for a in actions if a.get("priority") == priority_filter]
            
            for action in filtered_actions:
                priority_color = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠", 
                    "MEDIUM": "🟡",
                    "LOW": "🟢"
                }.get(action.get("priority", "LOW"), "⚪")
                
                with st.expander(f"{priority_color} {action['title']} - {action.get('priority', 'LOW')} Priority"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Description:** {action['description']}")
                        st.markdown(f"**Type:** {action.get('type', 'Unknown')}")
                        st.markdown(f"**Risk if delayed:** {action.get('risk_if_delayed', 'Not specified')}")
                        
                        if action.get("required_skills"):
                            skills_badges = " ".join([f"`{skill}`" for skill in action["required_skills"]])
                            st.markdown(f"**Required Skills:** {skills_badges}")
                    
                    with col2:
                        st.markdown(f"**⏱️ Estimated Time:** {action.get('estimated_time', 'Unknown')}")
                        st.markdown(f"**🆔 Action ID:** {action.get('id', 'Unknown')}")
                        
                        if st.button(f"Mark as Completed", key=f"complete_{action.get('id', 'unknown')}"):
                            st.success("Action marked as completed!")
        
        # Automated Responses
        if automated_responses:
            st.markdown("#### 🤖 Automated Responses")
            for i, response in enumerate(automated_responses):
                st.markdown(f"""
                <div style="background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; 
                           padding: 15px; border-radius: 8px; margin: 10px 0;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                        <span style="font-size: 1.2em;">🔄</span>
                        <span style="font-weight: bold; color: #3b82f6;">{response['action'].replace('_', ' ').title()}</span>
                    </div>
                    <div style="margin-bottom: 8px; color: #e5e7eb;">{response['description']}</div>
                    <div style="font-size: 0.9em; color: #9ca3af;">
                        <div><strong>Triggered by:</strong> {response['triggered_by']}</div>
                        <div><strong>Expected effect:</strong> {response['expected_effect']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
    else:
        st.info("Run system diagnostics to see actions and responses")

with tab4:  # Maintenance Tab
    st.markdown("## 🛠️ Maintenance Management")
    
    # Check if workflow has been run and has results
    if st.session_state.workflow_results:
        results = st.session_state.workflow_results
        
        # Work Order Creation Section
        st.markdown("### 📋 Work Orders")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 Create Work Order", use_container_width=True):
                wo_id = f"WO-{str(uuid.uuid4())[:8].upper()}"
                st.success(f"✅ Work Order {wo_id} created!")
                st.json({
                    "id": wo_id,
                    "location": "Bengaluru-MG-Road-05",
                    "priority": "HIGH",
                    "alerts": len(results.get("work_orders", [])),
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M")
                })

        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        with col3:
            if st.button("📞 Call Support", use_container_width=True):
                st.info("☎️ Calling ATM Support: 1800-XXX-XXXX")
        
        # Work Orders Table (if exists)
        work_orders = results.get("work_orders", [])
        
        if work_orders:
            # Status filter
            status_filter = st.selectbox("Filter by Status", ["All", "PENDING", "IN_PROGRESS", "COMPLETED"])
            
            # Work orders table
            wo_data = []
            for wo in work_orders:
                wo_data.append({
                    "ID": wo["id"],
                    "Title": wo["title"],
                    "Priority": wo["priority"],
                    "Type": wo["type"],
                    "Status": wo["status"],
                    "Estimated Time": wo["estimated_time"],
                    "Location": wo["location"]
                })
            
            wo_df = pd.DataFrame(wo_data)
            if status_filter != "All":
                wo_df = wo_df[wo_df["Status"] == status_filter]
            
            st.dataframe(wo_df, use_container_width=True)
        
        # Maintenance Schedule
        st.markdown("### 📅 Maintenance Schedule")
        
        # Use schedule from results if available, otherwise use default
        schedule = results.get("maintenance_schedule", [])
        
        if not schedule:  # Fallback to default maintenance items
            schedule = [
                {
                    "task": "Cash Dispenser Cleaning",
                    "due_date": "2025-08-28",
                    "priority": "HIGH",
                    "estimated_time": "2 hours",
                    "technician": "Rajesh Kumar",
                    "status": "Scheduled"
                },
                {
                    "task": "Network Equipment Check",
                    "due_date": "2025-08-30", 
                    "priority": "MEDIUM",
                    "estimated_time": "1 hour",
                    "technician": "Priya Sharma",
                    "status": "Pending"
                },
                {
                    "task": "Cooling System Service",
                    "due_date": "2025-09-02",
                    "priority": "NORMAL",
                    "estimated_time": "3 hours", 
                    "technician": "Mohammed Ali",
                    "status": "Planned"
                },
                {
                    "task": "Security Camera Maintenance",
                    "due_date": "2025-09-05",
                    "priority": "NORMAL",
                    "estimated_time": "1.5 hours",
                    "technician": "Anil Reddy",
                    "status": "Planned"
                }
            ]
        
        for item in schedule:
            priority = item.get("priority", "NORMAL")
            priority_class = "schedule-urgent" if priority == "HIGH" else "schedule-medium" if priority == "MEDIUM" else "schedule-normal"
            priority_color = "#ef4444" if priority == "HIGH" else "#f59e0b" if priority == "MEDIUM" else "#10b981"
            
            st.markdown(f"""
            <div class="schedule-item {priority_class}" style="background: rgba(45, 55, 72, 0.8); padding: 1rem; margin: 0.5rem 0; 
                        border-radius: 8px; border-left: 4px solid {priority_color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h4 style="color: #e2e8f0; margin: 0; font-size: 1rem;">{item['task']}</h4>
                    <span style="background: {priority_color}; color: white; padding: 0.2rem 0.5rem; 
                                 border-radius: 6px; font-size: 0.7rem; font-weight: 600;">
                        {priority}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.8rem; color: #a0aec0;">
                    <div><strong>Due:</strong> {item['due_date']}</div>
                    <div><strong>Time:</strong> {item['estimated_time']}</div>
                    <div><strong>Technician:</strong> {item.get('technician', 'Not Assigned')}</div>
                    <div><strong>Status:</strong> {item.get('status', 'Scheduled')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Maintenance History
        st.markdown("### 📜 Recent Maintenance History")
        
        history_items = [
            ("✅", "Preventive Maintenance", "2025-08-20", "Completed", "success"),
            ("🔧", "Dispenser Jam Fix", "2025-08-18", "Completed", "success"),
            ("⚠️", "Temperature Alert Fix", "2025-08-15", "Completed", "warning"),
            ("🌐", "Network Issue Resolution", "2025-08-12", "Completed", "success"),
        ]
        
        for icon, task, date, status, level in history_items:
            color = "#10b981" if level == "success" else "#f59e0b" if level == "warning" else "#63b3ed"
            st.markdown(f"""
            <div style="background: rgba(45, 55, 72, 0.8); padding: 1rem; margin: 0.5rem 0; 
                        border-radius: 8px; border-left: 4px solid {color}; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <span style="font-size: 1.5rem;">{icon}</span>
                    <div>
                        <div style="color: #e2e8f0; font-weight: 600;">{task}</div>
                        <div style="color: #a0aec0; font-size: 0.8rem;">{date}</div>
                    </div>
                </div>
                <span style="background: {color}; color: white; padding: 0.3rem 0.6rem; 
                             border-radius: 6px; font-size: 0.7rem; font-weight: 600;">{status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Parts & Inventory
        st.markdown("### 📦 Parts & Inventory Status")
        
        inventory_items = [
            ("💳", "Dispenser Parts", "8", "In Stock", "NORMAL"),
            ("🌡️", "Cooling Filters", "3", "Low Stock", "WARNING"), 
            ("🔌", "Network Cables", "12", "In Stock", "NORMAL"),
            ("🔧", "General Tools", "15", "Available", "NORMAL")
        ]
        
        # Create inventory cards in columns
        inv_cols = st.columns(len(inventory_items))
        
        for i, (icon, item, quantity, status, level) in enumerate(inventory_items):
            with inv_cols[i]:
                color = "#10b981" if level == "NORMAL" else "#f59e0b" if level == "WARNING" else "#ef4444"
                status_text = level
                reorder_text = "⚠️ Reached" if level == "WARNING" else "✅ Normal"
                
                st.markdown(f"""
                <div style="
                    background: rgba(45, 55, 72, 0.8);
                    padding: 1.5rem;
                    border-radius: 12px;
                    text-align: center;
                    height: 200px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                ">
                    <div>
                        <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
                        <span style="
                            background: {color};
                            color: white;
                            padding: 0.25rem 0.5rem;
                            border-radius: 16px;
                            font-size: 0.65rem;
                            font-weight: bold;
                            margin-bottom: 0.75rem;
                            display: inline-block;
                        ">{status_text}</span>
                        <h4 style="color: #a0aec0; margin: 0.5rem 0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">{item}</h4>
                        <h2 style="color: #4299e1; margin: 0.5rem 0; font-size: 1.75rem; font-weight: bold;">{quantity} units</h2>
                    </div>
                    <div style="font-size: 0.7rem; color: #a0aec0; line-height: 1.4;">
                        <div>Status: {status}</div>
                        <div>Last updated: Today</div>
                        <div>Reorder level: {reorder_text}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Technician Assignments
        assignments = results.get("technician_assignments", {})
        
        if assignments:
            st.markdown("### 👨‍🔧 Technician Assignments")
            tech_summary = {}
            for wo_id, tech_phone in assignments.items():
                if tech_phone not in tech_summary:
                    tech_summary[tech_phone] = []
                tech_summary[tech_phone].append(wo_id)
            
            for tech, work_orders_assigned in tech_summary.items():
                with st.expander(f"Technician: {tech} ({len(work_orders_assigned)} work orders)"):
                    st.write("Assigned Work Orders:")
                    for wo_id in work_orders_assigned:
                        st.write(f"- {wo_id}")
        
        # SMS Notifications
        notifications = results.get("notifications_sent", [])

        if notifications:
            st.markdown("### 📱 SMS Notifications")
            notif_data = []
            for notif in notifications:
                status_icon = "✅" if notif["message_sent"] else "❌"
                notif_data.append({
                    "Status": status_icon,
                    "Work Order": notif["work_order_id"],
                    "Technician": notif["technician_name"],
                    "Phone": notif["technician_phone"],
                    "Sent": notif["timestamp"][:19].replace("T", " ")
                })
            
            notif_df = pd.DataFrame(notif_data)
            st.dataframe(notif_df, use_container_width=True)
            
            # Show message preview
            with st.expander("📋 View SMS Messages"):
                for notif in notifications:
                    st.markdown(f"**To: {notif['technician_name']} ({notif['technician_phone']})**")
                    st.code(notif["message"], language="text")
                    st.markdown("---")

        # Maintenance Metrics
        if work_orders or schedule:
            st.markdown("### 📊 Maintenance Metrics")
            metrics_cols = st.columns(4)
            
            # with metrics_cols[0]:
            #     st.metric("Total Work Orders", len(work_orders))
            # with metrics_cols[1]:
            #     pending_count = len([wo for wo in work_orders if wo["status"] == "PENDING"])
            #     st.metric("Pending", pending_count)
            # with metrics_cols[2]:
            #     critical_wo = len([wo for wo in work_orders if wo["priority"] == "CRITICAL"])
            #     st.metric("Critical WOs", critical_wo)
            # with metrics_cols[3]:
            #     scheduled_items = len(schedule)
            #     st.metric("Scheduled Items", scheduled_items)
    
    else:
        # Enhanced empty state matching reference structure
        st.markdown("### 📋 Work Orders")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 Create Work Order", use_container_width=True):
                wo_id = f"WO-{str(uuid.uuid4())[:8].upper()}"
                st.success(f"✅ Work Order {wo_id} created!")

        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        with col3:
            if st.button("📞 Call Support", use_container_width=True):
                st.info("☎️ Calling ATM Support: 1800-XXX-XXXX")
        
        # Show message about running analysis
        st.markdown("""
        <div style="
            background: rgba(74, 158, 255, 0.1);
            border: 1px solid #4299e1;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
            margin: 1rem 0;
        ">
            <h4 style="color: #4299e1; margin-bottom: 0.5rem;">Maintenance analysis not yet performed</h4>
            <p style="color: #a0aec0; margin: 0;">Run the multi-agent analysis to see maintenance information</p>
        </div>
        """, unsafe_allow_html=True)
        
        # System Status Cards
        st.markdown("### ⚙️ System Status")
        
        status_cols = st.columns(3)
        
        with status_cols[0]:
            st.markdown("""
            <div style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; border-radius: 8px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.1);">
                <h4 style="color: #e2e8f0; margin-bottom: 1rem;">⚙️ System Status</h4>
                <div style="background: #10b981; color: white; padding: 0.5rem 1rem; border-radius: 20px; display: inline-block; margin-bottom: 0.5rem; font-size: 0.8rem;">
                    Multi-Agent System: Active
                </div>
                <div style="background: rgba(74, 158, 255, 0.3); color: #4299e1; padding: 0.5rem 1rem; border-radius: 20px; display: inline-block; font-size: 0.8rem;">
                    Active Agents: 5/5
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with status_cols[1]:
            st.markdown("""
            <div style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; border-radius: 8px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.1);">
                <h4 style="color: #e2e8f0; margin-bottom: 1rem;">📊 Data Source</h4>
                <div style="background: rgba(74, 158, 255, 0.3); color: #4299e1; padding: 0.5rem 1rem; border-radius: 20px; display: inline-block; font-size: 0.8rem;">
                    Using: Synthetic Data
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with status_cols[2]:
            st.markdown("""
            <div style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; border-radius: 8px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.1);">
                <h4 style="color: #e2e8f0; margin-bottom: 1rem;">📍 Location</h4>
                <div style="background: rgba(74, 158, 255, 0.3); color: #4299e1; padding: 0.5rem 1rem; border-radius: 20px; display: inline-block; font-size: 0.8rem;">
                    📍 Bengaluru - MG-Road-05
                </div>
            </div>
            """, unsafe_allow_html=True)
 
with tab5:  # Settings Tab
    st.markdown("## ⚙️ Settings & Configuration")
    
    # Check if workflow has been run and has results
    if st.session_state.workflow_results and st.session_state.workflow_results.get("system_settings"):
        results = st.session_state.workflow_results
        settings = results["system_settings"]
        
        # Current Settings Display
        st.markdown("### 🔧 Current System Configuration")
        
        settings_col1, settings_col2 = st.columns(2)
        
        with settings_col1:
            st.markdown("##### Temperature Thresholds")
            temp_settings = settings.get("temperature_thresholds", {})
            st.write(f"Warning: {temp_settings.get('warning', 40)}°C")
            st.write(f"Critical: {temp_settings.get('critical', 42)}°C")
            
            st.markdown("##### Network Thresholds")
            network_settings = settings.get("network_thresholds", {})
            st.write(f"Warning: {network_settings.get('warning', 120)}ms")
            st.write(f"Critical: {network_settings.get('critical', 250)}ms")
        
        with settings_col2:
            st.markdown("##### Maintenance Intervals")
            maint_settings = settings.get("maintenance_intervals", {})
            st.write(f"Preventive: {maint_settings.get('preventive', 21)} days")
            st.write(f"Inspection: {maint_settings.get('inspection', 7)} days")
            
            st.markdown("##### Auto Responses")
            auto_settings = settings.get("auto_responses", {})
            st.write(f"Enabled: {'Yes' if auto_settings.get('enabled') else 'No'}")
            st.write(f"Temperature Control: {'Yes' if auto_settings.get('temperature') else 'No'}")
            st.write(f"Network Failover: {'Yes' if auto_settings.get('network') else 'No'}")
        
        # Optimization Recommendations
        st.markdown("### 🚀 Optimization Recommendations")
        optimizations = results.get("optimization_recommendations", [])
        
        if optimizations:
            for opt in optimizations:
                category_icons = {
                    "thermal": "🌡️",
                    "network": "🌐",
                    "predictive": "🔮",
                    "general": "⚙️"
                }
                
                icon = category_icons.get(opt["category"], "⚙️")
                
                with st.expander(f"{icon} {opt['title']} - {opt['category'].title()}"):
                    st.markdown(f"**Description:** {opt['description']}")
                    st.markdown(f"**Expected Benefit:** {opt['expected_benefit']}")
                    st.markdown(f"**Implementation Effort:** {opt['implementation_effort']}")
                    
                    if "estimated_savings" in opt:
                        st.markdown(f"**Estimated Savings:** {opt['estimated_savings']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Apply Optimization", key=f"apply_{opt['category']}"):
                            st.success("Optimization applied successfully!")
                    with col2:
                        if st.button(f"Schedule Later", key=f"schedule_{opt['category']}"):
                            st.info("Optimization scheduled for next maintenance window")
        else:
            st.success("✅ System is optimally configured")
        
        st.markdown("---")
    
    # Alert Thresholds Section
    st.markdown("### 🚨 Alert Thresholds")
    
    st.markdown("""
    <div class="settings-section" style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
        <div class="settings-title" style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">
            <span>📲</span>
            Alert Preferences
        </div>
    """, unsafe_allow_html=True)
    
    enable_sms = st.checkbox("Enable SMS Notifications", value=True)
    enable_email = st.checkbox("Enable Email Notifications", value=True)
    enable_push = st.checkbox("Enable Push Notifications", value=True)
    
    notification_frequency = st.selectbox("Alert Frequency", 
                                        ["Immediate", "Every 5 minutes", "Every 15 minutes", "Hourly"])
    
    quiet_hours_start = st.time_input("Quiet Hours Start", value=datetime.strptime("22:00", "%H:%M").time())
    quiet_hours_end = st.time_input("Quiet Hours End", value=datetime.strptime("06:00", "%H:%M").time())
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Technician Management
    st.markdown("### 👨‍🔧 Technician Management")
    
    st.markdown("""
    <div class="settings-section" style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
        <div class="settings-title" style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">
            <span>👥</span>
            Contact Information
        </div>
    """, unsafe_allow_html=True)
    
    # Get technician info from workflow results if available
    technician_number = "+91 90000 12345"  # Default value
    if st.session_state.workflow_results:
        assignments = st.session_state.workflow_results.get("technician_assignments", {})
        if assignments:
            technician_number = list(assignments.values())[0]
    
    primary_tech = st.text_input("Primary Technician", value=technician_number)
    backup_tech = st.text_input("Backup Technician", value="+91 90000 99999")
    supervisor = st.text_input("Supervisor", value="+91 90000 88888")
    
    escalation_time = st.selectbox("Escalation Time (if no response)", 
                                 ["15 minutes", "30 minutes", "1 hour", "2 hours"])
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # System Configuration
    st.markdown("### ⚙️ System Configuration")
    
    st.markdown("""
    <div class="settings-section" style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
        <div class="settings-title" style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">
            <span>🔄</span>
            Data & Monitoring
        </div>
    """, unsafe_allow_html=True)
    
    data_refresh_rate = st.selectbox("Data Refresh Rate", 
                                   ["Real-time", "Every 30 seconds", "Every minute", "Every 5 minutes"])
    
    data_retention = st.selectbox("Data Retention Period", 
                                ["7 days", "30 days", "90 days", "1 year"])
    
    enable_predictive = st.checkbox("Enable Predictive Analytics", value=True)
    model_sensitivity = st.slider("Model Sensitivity", 0.1, 1.0, 0.75, 0.05)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Security Settings
    st.markdown("### 🔐 Security Settings")
    
    st.markdown("""
    <div class="settings-section" style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
        <div class="settings-title" style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">
            <span>🛡️</span>
            Access Control
        </div>
    """, unsafe_allow_html=True)
    
    enable_2fa = st.checkbox("Enable Two-Factor Authentication", value=True)
    session_timeout = st.selectbox("Session Timeout", ["15 minutes", "30 minutes", "1 hour", "4 hours"])
    
    auto_lock_suspicious = st.checkbox("Auto-lock on Suspicious Activity", value=True)
    max_failed_attempts = st.number_input("Max Failed Login Attempts", min_value=3, max_value=10, value=5)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Maintenance Settings
    st.markdown("### 🛠️ Maintenance Configuration")
    
    st.markdown("""
    <div class="settings-section" style="background: rgba(45, 55, 72, 0.8); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1);">
        <div class="settings-title" style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; color: #e2e8f0; font-weight: 600; font-size: 1.1rem;">
            <span>📅</span>
            Scheduling
        </div>
    """, unsafe_allow_html=True)
    
    preventive_interval = st.selectbox("Preventive Maintenance Interval", 
                                     ["Weekly", "Bi-weekly", "Monthly", "Quarterly"])
    
    maintenance_window = st.selectbox("Preferred Maintenance Window", 
                                    ["Night (10 PM - 6 AM)", "Early Morning (6 AM - 10 AM)", 
                                     "Business Hours", "Flexible"])
    
    auto_schedule = st.checkbox("Auto-schedule based on risk predictions", value=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Advanced Settings Form (if workflow results exist)
    if st.session_state.workflow_results and st.session_state.workflow_results.get("system_settings"):
        st.markdown("### 🔧 Advanced System Settings")
        
        with st.form("advanced_settings_form"):
            st.markdown("##### Update System Thresholds")
            
            col1, col2 = st.columns(2)
            
            with col1:
                temp_settings = settings.get("temperature_thresholds", {})
                new_temp_warning = st.number_input("Temperature Warning (°C)", 
                                                  min_value=30.0, max_value=50.0, 
                                                  value=float(temp_settings.get('warning', 40)), 
                                                  step=0.5)
                new_temp_critical = st.number_input("Temperature Critical (°C)", 
                                                   min_value=35.0, max_value=55.0, 
                                                   value=float(temp_settings.get('critical', 42)), 
                                                   step=0.5)
            
            with col2:
                network_settings = settings.get("network_thresholds", {})
                new_network_warning = st.number_input("Network Warning (ms)", 
                                                     min_value=50, max_value=300, 
                                                     value=int(network_settings.get('warning', 120)), 
                                                     step=10)
                new_network_critical = st.number_input("Network Critical (ms)", 
                                                      min_value=100, max_value=500, 
                                                      value=int(network_settings.get('critical', 250)), 
                                                      step=25)
            
            st.markdown("##### Auto Response Settings")
            auto_settings = settings.get("auto_responses", {})
            enable_auto = st.checkbox("Enable Automatic Responses", 
                                     value=auto_settings.get('enabled', True))
            enable_temp_control = st.checkbox("Auto Temperature Control", 
                                             value=auto_settings.get('temperature', True))
            enable_network_failover = st.checkbox("Auto Network Failover", 
                                                 value=auto_settings.get('network', True))
            
            if st.form_submit_button("Update Advanced Settings", type="secondary"):
                # Update settings in session state
                st.session_state.workflow_results["system_settings"].update({
                    "temperature_thresholds": {"warning": new_temp_warning, "critical": new_temp_critical},
                    "network_thresholds": {"warning": new_network_warning, "critical": new_network_critical},
                    "auto_responses": {
                        "enabled": enable_auto,
                        "temperature": enable_temp_control,
                        "network": enable_network_failover
                    },
                    "last_updated": datetime.now().isoformat()
                })
                
                st.success("Advanced settings updated successfully!")
                st.rerun()
    
    # Save All Settings Button
    if st.button("💾 Save All Settings", use_container_width=True, type="primary"):
        # Prepare settings data
        settings_data = {
            "notifications": {"sms": enable_sms, "email": enable_email, "push": enable_push, "frequency": notification_frequency},
            "quiet_hours": {"start": str(quiet_hours_start), "end": str(quiet_hours_end)},
            "technicians": {"primary": primary_tech, "backup": backup_tech, "supervisor": supervisor},
            "escalation": {"time": escalation_time},
            "system": {"refresh_rate": data_refresh_rate, "retention": data_retention, "predictive": enable_predictive, "sensitivity": model_sensitivity},
            "security": {"2fa": enable_2fa, "timeout": session_timeout, "auto_lock": auto_lock_suspicious, "max_attempts": max_failed_attempts},
            "maintenance": {"interval": preventive_interval, "window": maintenance_window, "auto_schedule": auto_schedule},
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "location": "Bengaluru-MG-Road-05"
        }
        
        st.success("✅ Settings saved successfully!")
        # st.json(settings_data)

    # Export/Import Settings
    st.markdown("### 🔧 Settings Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📤 Export Settings", use_container_width=True):
            settings_json = {
                "exported_at": datetime.now().isoformat(),
                "location": "Bengaluru-MG-Road-05",
                "settings": "Configuration data would be exported here"
            }
            st.download_button(
                label="💾 Download Settings File",
                data=json.dumps(settings_json, indent=2),
                file_name=f"atm_settings_bengaluru_mg_road_05_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    with col2:
        uploaded_settings = st.file_uploader("📥 Import Settings", type=["json"])
        if uploaded_settings is not None:
            if st.button("📥 Import Settings", use_container_width=True):
                st.success("✅ Settings imported successfully!")
                st.info("📋 Settings have been applied to the system")
    
    # System Performance Impact (if workflow results exist)
    if st.session_state.workflow_results and st.session_state.workflow_results.get("system_settings"):
        st.markdown("### 📈 Performance Impact Analysis")
        
        results = st.session_state.workflow_results
        optimizations = results.get("optimization_recommendations", [])
        
        if results.get("agent_outputs", {}).get("SettingsAgent"):
            settings_output = results["agent_outputs"]["SettingsAgent"]
            perf_gain = settings_output.get("performance_gain_expected", 0)
            
            impact_cols = st.columns(3)
            with impact_cols[0]:
                st.metric("Expected Performance Gain", f"{perf_gain}%")
            with impact_cols[1]:
                st.metric("Optimizations Available", len(optimizations))
            with impact_cols[2]:
                settings_updated = settings_output.get("settings_updated", 0)
                st.metric("Settings Updated", settings_updated)
        else:
            st.info("Run the multi-agent analysis to see performance impact analysis")

with tab6:  # ML & AI Tab
    st.markdown("### 🤖 ML Predictions & AI Insights")
    
    if st.session_state.workflow_results:
        results = st.session_state.workflow_results
        monitoring_output = results.get("agent_outputs", {}).get("MonitoringAgent", {})
        
        # ML Prediction Results
        ml_prediction = monitoring_output.get("ml_prediction", {})
        if ml_prediction.get("status") == "success":
            st.markdown("#### 🔮 Failure Prediction")
            
            pred_cols = st.columns(4)
            with pred_cols[0]:
                failure_prob = ml_prediction["failure_probability"] * 100
                st.metric("Failure Probability", f"{failure_prob:.1f}%")
            
            with pred_cols[1]:
                risk_level = ml_prediction["risk_level"]
                risk_color = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
                st.metric("Risk Level", f"{risk_color.get(risk_level, '⚪')} {risk_level}")
            
            with pred_cols[2]:
                confidence = ml_prediction["confidence"] * 100
                st.metric("Confidence", f"{confidence:.1f}%")
            
            with pred_cols[3]:
                will_fail = "Yes" if ml_prediction["will_fail"] else "No"
                st.metric("Will Fail (24h)", will_fail)
            
            # Feature Values
            st.markdown("#### 📊 Current System Values")
            feature_values = ml_prediction.get("feature_values", {})
            
            if feature_values:
                feature_cols = st.columns(3)
                for i, (feature, value) in enumerate(feature_values.items()):
                    with feature_cols[i % 3]:
                        display_name = feature.replace('_', ' ').title()
                        if 'temperature' in feature:
                            st.metric(display_name, f"{value:.1f}°C")
                        elif 'latency' in feature:
                            st.metric(display_name, f"{value:.0f}ms")
                        elif 'pct' in feature or 'level' in feature:
                            st.metric(display_name, f"{value:.0f}%")
                        else:
                            st.metric(display_name, f"{value:.2f}")
        
        # ML Training Results
        ml_training = monitoring_output.get("ml_training", {})
        if ml_training.get("status") == "success":
            st.markdown("#### 🎯 Model Performance")
            
            train_cols = st.columns(4)
            metrics = ml_training.get("metrics", {})
            
            with train_cols[0]:
                accuracy = metrics.get("accuracy", 0) * 100
                st.metric("Accuracy", f"{accuracy:.1f}%")
            
            with train_cols[1]:
                precision = metrics.get("precision", 0) * 100
                st.metric("Precision", f"{precision:.1f}%")
            
            with train_cols[2]:
                recall = metrics.get("recall", 0) * 100
                st.metric("Recall", f"{recall:.1f}%")
            
            with train_cols[3]:
                failure_rate = metrics.get("failure_rate", 0)
                st.metric("Failure Rate", f"{failure_rate:.1f}%")
            
            # Feature Importance
            feature_importance = ml_training.get("feature_importance", {})
            if feature_importance:
                st.markdown("#### 🎯 Risk Factor Analysis")
                
                # Create feature importance chart
                features = list(feature_importance.keys())
                importances = list(feature_importance.values())
                
                fig_importance = px.bar(
                    x=[f.replace('_', ' ').title() for f in features],
                    y=importances,
                    title="Feature Importance in Failure Prediction",
                    labels={'x': 'Features', 'y': 'Importance Score'}
                )
                fig_importance.update_layout(template="plotly_dark")
                st.plotly_chart(fig_importance, use_container_width=True)
        
        # Gemini AI Insights
        gemini_insights = monitoring_output.get("gemini_insights", "")
        if gemini_insights and gemini_insights != "Gemini AI not available":
            st.markdown("#### 🧠 AI Expert Analysis")
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e40af, #3b82f6); 
                       padding: 20px; border-radius: 10px; margin: 10px 0; 
                       color: white; border-left: 4px solid #60a5fa;">
                <h4 style="margin: 0 0 10px 0; color: #dbeafe;">🤖 Gemini AI Insights</h4>
                <p style="margin: 0; line-height: 1.6;">{gemini_insights}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Run the multi-agent analysis to see ML predictions and AI insights")

# ===========================
# FOOTER AND ADDITIONAL INFO
# ===========================
st.markdown("---")

# Display system information
info_cols = st.columns(3)

with info_cols[0]:
    st.markdown("#### 🤖 System Status")
    if st.session_state.workflow_results:
        st.success("Multi-Agent System: Active")
        agent_count = len([k for k, v in agents_config.items() if v])
        st.info(f"Active Agents: {agent_count}/5")
    else:
        st.warning("System: Idle")

with info_cols[1]:
    st.markdown("#### 📊 Data Source")
    if st.session_state.uploaded_data is not None:
        st.success(f"CSV Data: {len(st.session_state.uploaded_data)} records")
    else:
        st.info("Using: Synthetic Data")

with info_cols[2]:
    st.markdown("#### 🏢 Location")
    st.info(f"📍 {city} - {branch}")

# Add timestamp
st.markdown(f"<div style='text-align: center; color: #6b7280; font-size: 0.8rem; margin-top: 2rem;'>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)