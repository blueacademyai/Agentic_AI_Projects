from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # user, admin
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    messages = relationship("Message", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    description = Column(Text)
    category = Column(String)  # transfer, payment, purchase
    transaction_metadata = Column(JSON)  # Additional transaction data
    status = Column(String, default="pending")  # pending, processing, success, failed, cancelled
    risk_score = Column(Integer, default=0)  # 0-10 risk assessment
    ai_validation_result = Column(JSON)  # AI agent validation results
    payment_method = Column(String)  # card, bank_transfer, wallet
    recipient_info = Column(JSON)  # Recipient details if applicable
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    @property
    def recipient_email(self):
        if self.recipient_info and isinstance(self.recipient_info, dict):
            return self.recipient_info.get("email")
        return None
    # Relationships
    user = relationship("User", back_populates="transactions")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender = Column(String, nullable=False)  # admin, system, ai_agent, user
    sender_name = Column(String)  # Display name of sender
    subject = Column(String)
    content = Column(Text, nullable=False)
    message_type = Column(String, default="info")  # info, warning, alert, notification
    is_read = Column(Boolean, default=False)
    priority = Column(String, default="normal")  # low, normal, high, urgent
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="messages")

class AILog(Base):
    __tablename__ = "ai_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String, nullable=False)
    agent_type = Column(String)  # validation, policy, messaging, chatbot
    operation = Column(String)  # validate_payment, summarize_policy, send_message, chat
    input_data = Column(JSON)
    output_data = Column(JSON)
    execution_time = Column(Float)  # Time in seconds
    status = Column(String, default="success")  # success, error, timeout
    error_message = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    transaction_id = Column(String, nullable=True)
    model_used = Column(String)  # gemini-1.5-flash, etc.
    tokens_used = Column(Integer)
    cost = Column(Float)  # API cost if applicable
    created_at = Column(DateTime, default=datetime.utcnow)

class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String)  # payment, security, compliance, general
    version = Column(String, default="1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String)  # Admin who created/updated

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat_messages = relationship("ChatMessage", back_populates="session")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False)
    sender = Column(String, nullable=False)  # user, ai, admin
    content = Column(Text, nullable=False)
    message_type = Column(String, default="text")  # text, suggestion, escalation
    ai_context = Column(JSON)  # Context data for AI responses
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="chat_messages")

class SystemConfig(Base):
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # ai, email, security, general
    is_encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)