from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import uuid

from ..database import get_db
from ..models import User, ChatSession, ChatMessage, AILog, Transaction, Message
from ..auth import get_current_user
from ..agents.chatbot_agent import ChatbotAgent
from ..utils.rag_service import RAGService
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize chatbot agent and RAG service
chatbot_agent = ChatbotAgent(api_key=os.getenv("GEMINI_API_KEY"))
rag_service = RAGService(api_key=os.getenv("GEMINI_API_KEY"))

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    suggestions: Optional[List[str]] = None
    escalate_to_admin: bool = False
    context: Optional[Dict[str, Any]] = None

class ChatHistoryItem(BaseModel):
    id: int
    sender: str
    content: str
    message_type: str
    created_at: datetime

class ChatSessionInfo(BaseModel):
    session_id: str
    is_active: bool
    created_at: datetime
    message_count: int

@router.post("/", response_model=ChatResponse)
async def chat_with_bot(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat with the AI assistant"""
    try:
        # Get or create chat session
        if chat_request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == chat_request.session_id,
                ChatSession.user_id == current_user.id
            ).first()
        else:
            session = None
        
        if not session:
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                user_id=current_user.id,
                is_active=True
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Save user message
        user_message = ChatMessage(
            session_id=session.session_id,
            sender="user",
            content=chat_request.message,
            message_type="text"
        )
        db.add(user_message)
        
        # Get chat history for context
        chat_history = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.session_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        
        # Prepare context for AI
        context = {
            "user_id": current_user.id,
            "user_email": current_user.email,
            "user_role": current_user.role,
            "session_id": session.session_id,
            "chat_history": [
                {
                    "sender": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in reversed(chat_history[-5:])  # Last 5 messages
            ]
        }
        
        if chat_request.context:
            context.update(chat_request.context)
        
        # Get AI response
        ai_response = await chatbot_agent.process_message(
            message=chat_request.message,
            context=context,
            rag_service=rag_service
        )
        
        # Save AI response
        ai_message = ChatMessage(
            session_id=session.session_id,
            sender="ai",
            content=ai_response["response"],
            message_type=ai_response.get("message_type", "text"),
            ai_context=ai_response.get("context", {})
        )
        db.add(ai_message)
        
        # Log AI operation
        ai_log = AILog(
            agent_name="ChatbotAgent",
            agent_type="chatbot",
            operation="process_message",
            input_data={
                "message": chat_request.message,
                "context": context
            },
            output_data=ai_response,
            execution_time=ai_response.get("execution_time", 0),
            status="success",
            user_id=current_user.id,
            model_used="gemini-1.5-flash"
        )
        db.add(ai_log)
        
        db.commit()
        
        logger.info(f"Chat interaction for user {current_user.email}, session {session.session_id}")
        
        return ChatResponse(
            response=ai_response["response"],
            session_id=session.session_id,
            suggestions=ai_response.get("suggestions", []),
            escalate_to_admin=ai_response.get("escalate_to_admin", False),
            context=ai_response.get("context", {})
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat service temporarily unavailable"
        )

@router.get("/sessions", response_model=List[ChatSessionInfo])
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's chat sessions"""
    try:
        from sqlalchemy import func
        
        sessions = db.query(
            ChatSession,
            func.count(ChatMessage.id).label('message_count')
        ).outerjoin(ChatMessage).filter(
            ChatSession.user_id == current_user.id
        ).group_by(ChatSession.id).order_by(
            ChatSession.created_at.desc()
        ).limit(20).all()
        
        return [
            ChatSessionInfo(
                session_id=chat_session.session_id,
                is_active=chat_session.is_active,
                created_at=chat_session.created_at,
                message_count=message_count or 0
            )
            for chat_session , message_count in sessions
        ]
        
    except Exception as e:
        logger.error(f"Error fetching chat sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch chat sessions"
        )

@router.get("/sessions/{session_id}/history", response_model=List[ChatHistoryItem])
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a session"""
    try:
        # Verify session belongs to user
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
        
        return [
            ChatHistoryItem(
                id=msg.id,
                sender=msg.sender,
                content=msg.content,
                message_type=msg.message_type,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch chat history"
        )

@router.patch("/sessions/{session_id}/end")
async def end_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End a chat session"""
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        session.is_active = False
        session.ended_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Chat session ended"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending chat session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end chat session"
        )

@router.post("/escalate")
async def escalate_to_admin(
    session_id: str,
    reason: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Escalate chat to admin"""
    try:
        # Verify session exists
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        # Create escalation message
        escalation_message = Message(
            user_id=current_user.id,
            sender="system",
            sender_name="Chat System",
            subject="Chat Escalation Request",
            content=f"User has requested admin assistance.\n\nSession ID: {session_id}\nReason: {reason}\n\nPlease review the chat history and provide assistance.",
            message_type="alert",
            priority="high"
        )
        
        db.add(escalation_message)
        
        # Add escalation note to chat
        escalation_chat = ChatMessage(
            session_id=session_id,
            sender="system",
            content="Your request has been escalated to our support team. An admin will review your chat and get back to you soon.",
            message_type="escalation"
        )
        db.add(escalation_chat)
        
        db.commit()
        
        logger.info(f"Chat escalated to admin for user {current_user.email}, session {session_id}")
        
        return {"message": "Chat escalated to admin successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error escalating chat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate chat"
        )

@router.get("/suggestions")
async def get_chat_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get suggested chat topics/questions"""
    try:
        from sqlalchemy import func, desc

        # Get user's recent transactions for personalized suggestions
        recent_transactions = db.query(Transaction).filter(
            Transaction.user_id == current_user.id
        ).order_by(Transaction.created_at.desc()).limit(3).all()
        
        # Base suggestions
        suggestions = [
            "How do I make a payment?",
            "What are the transaction limits?",
            "How can I check my payment history?",
            "What security measures are in place?",
            "How do I cancel a pending payment?"
        ]
        
        # Add personalized suggestions based on user activity
        if recent_transactions:
            if any(tx.status == "pending" for tx in recent_transactions):
                suggestions.insert(0, "Check status of my pending payments")
            
            if any(tx.risk_score > 6 for tx in recent_transactions):
                suggestions.insert(0, "Why was my payment flagged for review?")
        
        # Get common questions from chat history
        common_keywords = db.query(
            func.count(ChatMessage.id).label("count"),
            ChatMessage.content
        ).filter(
            ChatMessage.sender == "user"
        ).group_by(ChatMessage.content).order_by(desc(text("count"))).limit(3).all()
        
        # Merge top common keywords into quick suggestions
        for _, content in common_keywords:
            if content not in suggestions:
                suggestions.append(content)
        
        return {
            "quick_suggestions": suggestions[:5],
            "categories": [
                {
                    "name": "Payments",
                    "suggestions": [
                        "How to make a payment",
                        "Payment methods available",
                        "Transaction fees"
                    ]
                },
                {
                    "name": "Account",
                    "suggestions": [
                        "Update account information",
                        "Security settings",
                        "Transaction history"
                    ]
                },
                {
                    "name": "Support",
                    "suggestions": [
                        "Contact support",
                        "Report an issue",
                        "Account security concerns"
                    ]
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching suggestions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch suggestions"
        )


@router.post("/feedback")
async def submit_chat_feedback(
    session_id: str,
    rating: int,
    feedback: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback for a chat session"""
    try:
        # Verify session exists
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        # Validate rating
        if not 1 <= rating <= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 5"
            )
        
        # Add feedback as a system message
        feedback_message = ChatMessage(
            session_id=session_id,
            sender="system",
            content=f"User feedback: Rating {rating}/5" + (f" - {feedback}" if feedback else ""),
            message_type="feedback"
        )
        db.add(feedback_message)
        db.commit()
        
        logger.info(f"Chat feedback submitted for session {session_id}: {rating}/5")
        
        return {"message": "Feedback submitted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )