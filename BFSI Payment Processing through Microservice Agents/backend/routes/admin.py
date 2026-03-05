from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from sqlalchemy import text, case, Date, cast
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta

from ..database import get_db
from ..models import User, Transaction, AILog, Message, PolicyDocument
from ..auth import get_current_admin_user
from ..utils.rag_service import RAGService
from ..utils.email_service import send_admin_message
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize RAG service
rag_service = RAGService(api_key=os.getenv("GEMINI_API_KEY"))

# Pydantic models
class AdminMessage(BaseModel):
    user_email: str
    subject: str
    content: str
    message_type: str = "info"
    priority: str = "normal"

class PolicyQuery(BaseModel):
    query: str
    category: Optional[str] = None

class TransactionUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_transactions: int
    total_volume: float
    pending_transactions: int
    failed_transactions: int
    avg_risk_score: float
    ai_operations_today: int

@router.get("/dashboard")
async def get_admin_dashboard(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin dashboard overview"""
    try:
        from sqlalchemy import func, and_
        
        # Get current date for daily stats
        # Get current date for daily stats (use datetime range instead of func.date)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # User statistics
        total_users = db.query(func.count(User.id)).scalar()
        active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
        new_users_today = db.query(func.count(User.id)).filter(
            User.created_at >= today_start,
            User.created_at < today_end
        ).scalar()

        
        # Transaction statistics
        total_transactions = db.query(func.count(Transaction.id)).scalar()
        total_volume = db.query(func.sum(Transaction.amount)).scalar() or 0
        pending_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.status == "pending"
        ).scalar()
        failed_transactions = db.query(func.count(Transaction.id)).filter(
            Transaction.status == "failed"
        ).scalar()
        
        transactions_today = db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= today_start,
            Transaction.created_at < today_end
        ).scalar()

        volume_today = db.query(func.sum(Transaction.amount)).filter(
            Transaction.created_at >= today_start,
            Transaction.created_at < today_end
        ).scalar() or 0

        ai_operations_today = db.query(func.count(AILog.id)).filter(
            AILog.created_at >= today_start,
            AILog.created_at < today_end
        ).scalar()
        
        # Risk analysis
        avg_risk_score = db.query(func.avg(Transaction.risk_score)).scalar() or 0
        high_risk_transactions = db.query(func.count(Transaction.id)).filter(
            and_(Transaction.risk_score >= 7, Transaction.status == "pending")
        ).scalar()
        
        
        # Recent high-risk transactions
        recent_high_risk = db.query(Transaction).filter(
            Transaction.risk_score >= 7
        ).order_by(Transaction.created_at.desc()).limit(5).all()
        
        # System health metrics
        recent_ai_errors = db.query(func.count(AILog.id)).filter(
            and_(
                AILog.status == "error",
                AILog.created_at >= datetime.utcnow() - timedelta(hours=24)
            )
        ).scalar()
        
        return {
            "overview": {
                "total_users": total_users,
                "active_users": active_users,
                "new_users_today": new_users_today,
                "total_transactions": total_transactions,
                "total_volume": float(total_volume),
                "transactions_today": transactions_today,
                "volume_today": float(volume_today),
                "pending_transactions": pending_transactions,
                "failed_transactions": failed_transactions,
                "avg_risk_score": float(avg_risk_score),
                "high_risk_pending": high_risk_transactions,
                "ai_operations_today": ai_operations_today,
                "ai_errors_24h": recent_ai_errors
            },
            "recent_high_risk": [
                {
                    "transaction_id": tx.transaction_id,
                    "amount": tx.amount,
                    "risk_score": tx.risk_score,
                    "status": tx.status,
                    "user_email": tx.user.email,
                    "created_at": tx.created_at.isoformat()
                }
                for tx in recent_high_risk
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching admin dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard data"
        )

@router.get("/transactions")
async def get_all_transactions(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    risk_threshold: Optional[int] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all transactions with filters"""
    try:
        query = db.query(Transaction).join(User)
        
        if status_filter:
            query = query.filter(Transaction.status == status_filter)
            
        if risk_threshold is not None:
            query = query.filter(Transaction.risk_score >= risk_threshold)
        
        transactions = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
        
        return [
            {
                "id": tx.id,
                "transaction_id": tx.transaction_id,
                "amount": tx.amount,
                "currency": tx.currency,
                "description": tx.description,
                "category": tx.category,
                "status": tx.status,
                "risk_score": tx.risk_score,
                "payment_method": tx.payment_method,
                "user": {
                    "id": tx.user.id,
                    "email": tx.user.email,
                    "full_name": tx.user.full_name
                },
                "ai_validation": tx.ai_validation_result,
                "created_at": tx.created_at.isoformat(),
                "processed_at": tx.processed_at.isoformat() if tx.processed_at else None
            }
            for tx in transactions
        ]
        
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transactions"
        )

@router.patch("/transactions/{transaction_id}/status")
async def update_transaction_status(
    transaction_id: str,
    update_data: TransactionUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update transaction status (admin only)"""
    try:
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == transaction_id
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Update transaction
        old_status = transaction.status
        transaction.status = update_data.status
        transaction.updated_at = datetime.utcnow()
        
        if update_data.status in ["success", "failed"]:
            transaction.processed_at = datetime.utcnow()
        
        # Add admin notes to metadata
        if not transaction.transaction_metadata:
            transaction.transaction_metadata = {}
        
        transaction.transaction_metadata["admin_update"] = {
            "updated_by": current_admin.email,
            "old_status": old_status,
            "new_status": update_data.status,
            "notes": update_data.notes,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        db.commit()
        
        logger.info(f"Transaction {transaction_id} updated by admin {current_admin.email}: {old_status} -> {update_data.status}")
        
        return {"message": "Transaction updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update transaction"
        )

@router.get("/ai-logs")
async def get_ai_logs(
    skip: int = 0,
    limit: int = 50,
    agent_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get AI operation logs"""
    try:
        query = db.query(AILog)
        
        if agent_filter:
            query = query.filter(AILog.agent_name == agent_filter)
            
        if status_filter:
            query = query.filter(AILog.status == status_filter)
        
        logs = query.order_by(AILog.created_at.desc()).offset(skip).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "session_id": log.session_id,
                "agent_name": log.agent_name,
                "agent_type": log.agent_type,
                "operation": log.operation,
                "status": log.status,
                "execution_time": log.execution_time,
                "error_message": log.error_message,
                "model_used": log.model_used,
                "tokens_used": log.tokens_used,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
        
    except Exception as e:
        logger.error(f"Error fetching AI logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch AI logs"
        )

@router.post("/policy-summary")
async def get_policy_summary(
    query_data: PolicyQuery,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get AI-generated policy summary"""
    try:
        # Get policy summary using RAG
        summary = await rag_service.get_policy_summary(
            query_data.query,
            category=query_data.category
        )
        
        # Log AI operation
        ai_log = AILog(
            agent_name="PolicyAgent",
            agent_type="policy",
            operation="summarize_policy",
            input_data={"query": query_data.query, "category": query_data.category},
            output_data={"summary": summary},
            execution_time=0.5,  # Approximate time
            status="success",
            user_id=current_admin.id,
            model_used="gemini-1.5-flash"
        )
        db.add(ai_log)
        db.commit()
        
        return {"summary": summary, "query": query_data.query}
        
    except Exception as e:
        logger.error(f"Error generating policy summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate policy summary"
        )

@router.post("/send-message")
async def send_message_to_user(
    message_data: AdminMessage,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Send message/notification to user"""
    try:
        # Find target user
        user = db.query(User).filter(User.email == message_data.user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create message record
        message = Message(
            user_id=user.id,
            sender="admin",
            sender_name=current_admin.full_name or current_admin.email,
            subject=message_data.subject,
            content=message_data.content,
            message_type=message_data.message_type,
            priority=message_data.priority
        )
        
        db.add(message)
        db.commit()
        
        # Send email notification
        background_tasks.add_task(
            send_admin_message,
            user.email,
            user.full_name or user.email,
            message_data.subject,
            message_data.content,
            current_admin.full_name or current_admin.email
        )
        
        logger.info(f"Admin message sent from {current_admin.email} to {user.email}")
        
        return {"message": "Message sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending admin message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )

@router.get("/users")
async def get_all_users(
    skip: int = 0,
    limit: int = 50,
    role_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all users with filtering"""
    try:
        query = db.query(User)
        
        if role_filter:
            query = query.filter(User.role == role_filter)
            
        if status_filter == "active":
            query = query.filter(User.is_active == True)
        elif status_filter == "inactive":
            query = query.filter(User.is_active == False)
        
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        
        # Get transaction count for each user
        user_data = []
        for user in users:
            tx_count = db.query(Transaction).filter(Transaction.user_id == user.id).count()
            total_volume = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user.id
            ).scalar() or 0
            
            user_data.append({
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "transaction_count": tx_count,
                "total_volume": float(total_volume),
                "created_at": user.created_at.isoformat(),
                "last_updated": user.updated_at.isoformat()
            })
        
        return user_data
        
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )

@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    is_active: bool,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user active status"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent admin from deactivating themselves
        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify own account status"
            )
        
        user.is_active = is_active
        user.updated_at = datetime.utcnow()
        db.commit()
        
        action = "activated" if is_active else "deactivated"
        logger.info(f"User {user.email} {action} by admin {current_admin.email}")
        
        return {"message": f"User {action} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )

@router.get("/analytics/overview")
async def get_analytics_overview(
    days: int = 30,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics overview"""
    try:
        from sqlalchemy import func, and_
        
        # Date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Transaction trends
        # Transaction trends (portable across DBs)
        daily_stats = db.query(
            cast(Transaction.created_at, Date).label('date'),
            func.count(Transaction.id).label('transaction_count'),
            func.sum(Transaction.amount).label('total_volume'),
            func.avg(Transaction.risk_score).label('avg_risk_score')
        ).filter(
            Transaction.created_at >= start_date
        ).group_by(
            cast(Transaction.created_at, Date)
        ).order_by('date').all()
        
        # Status distribution
        status_dist = db.query(
            Transaction.status,
            func.count(Transaction.id).label('count'),
            func.sum(Transaction.amount).label('volume')
        ).filter(
            Transaction.created_at >= start_date
        ).group_by(Transaction.status).all()
        
        # Risk score distribution
        risk_dist = db.query(
            case(
                (Transaction.risk_score <= 3, 'Low'),
                (Transaction.risk_score <= 6, 'Medium'),
                (Transaction.risk_score <= 8, 'High'),
                else_='Critical'
            ).label('risk_level'),
            func.count(Transaction.id).label('count')
        ).filter(
            Transaction.created_at >= start_date
        ).group_by('risk_level').all()
        
        # AI performance metrics
        ai_stats = db.query(
            AILog.agent_name,
            func.count(AILog.id).label('operations'),
            func.avg(AILog.execution_time).label('avg_execution_time'),
            func.sum(AILog.tokens_used).label('total_tokens')
        ).filter(
            AILog.created_at >= start_date
        ).group_by(AILog.agent_name).all()
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "daily_trends": [
                {
                    "date": stat.date.isoformat(),
                    "transaction_count": stat.transaction_count,
                    "total_volume": float(stat.total_volume or 0),
                    "avg_risk_score": float(stat.avg_risk_score or 0)
                }
                for stat in daily_stats
            ],
            "status_distribution": [
                {
                    "status": stat.status,
                    "count": stat.count,
                    "volume": float(stat.volume or 0)
                }
                for stat in status_dist
            ],
            "risk_distribution": [
                {
                    "risk_level": stat.risk_level,
                    "count": stat.count
                }
                for stat in risk_dist
            ],
            "ai_performance": [
                {
                    "agent": stat.agent_name,
                    "operations": stat.operations,
                    "avg_execution_time": float(stat.avg_execution_time or 0),
                    "total_tokens": stat.total_tokens or 0
                }
                for stat in ai_stats
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch analytics"
        )

@router.get("/system/health")
async def get_system_health(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get system health metrics"""
    try:
        from sqlalchemy import func
        
        # Database health
        db_connection_test = db.execute(text("SELECT 1")).fetchone()
        
        # Recent error rates
        last_24h = datetime.utcnow() - timedelta(hours=24)
        
        total_ai_ops = db.query(func.count(AILog.id)).filter(
            AILog.created_at >= last_24h
        ).scalar() or 0
        
        failed_ai_ops = db.query(func.count(AILog.id)).filter(
            and_(AILog.created_at >= last_24h, AILog.status == "error")
        ).scalar() or 0
        
        error_rate = (failed_ai_ops / total_ai_ops * 100) if total_ai_ops > 0 else 0
        
        # Transaction processing health
        pending_too_long = db.query(func.count(Transaction.id)).filter(
            and_(
                Transaction.status == "pending",
                Transaction.created_at < datetime.utcnow() - timedelta(hours=1)
            )
        ).scalar() or 0
        
        # System performance metrics
        avg_ai_response_time = db.query(func.avg(AILog.execution_time)).filter(
            AILog.created_at >= last_24h
        ).scalar() or 0
        
        return {
            "database": {
                "status": "healthy" if db_connection_test else "unhealthy",
                "connection": "ok"
            },
            "ai_services": {
                "error_rate": round(error_rate, 2),
                "total_operations_24h": total_ai_ops,
                "failed_operations_24h": failed_ai_ops,
                "avg_response_time": float(avg_ai_response_time)
            },
            "transaction_processing": {
                "pending_too_long": pending_too_long,
                "status": "healthy" if pending_too_long < 10 else "warning"
            },
            "overall_status": "healthy" if error_rate < 5 and pending_too_long < 10 else "warning"
        }
        
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check system health"
        )