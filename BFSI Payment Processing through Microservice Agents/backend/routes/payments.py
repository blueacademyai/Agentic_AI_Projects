from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import uuid

from ..database import get_db
from ..models import User, Transaction, AILog
from ..auth import get_current_user
from ..agents.payment_agent import PaymentAgent
from ..utils.email_service import send_payment_notification
from ..utils.serialization import serialize_input

import os

MIN_TRANSACTION_AMOUNT = 0.5  # USD
MAX_RISK_SCORE = 7  # Block transactions above this AI risk score

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize payment agent
payment_agent = PaymentAgent(api_key=os.getenv("GOOGLE_API_KEY"))

# ---------------- Pydantic models ----------------
class RecipientInfo(BaseModel):
    email: str
    name: Optional[str] = None

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid recipient email address")
        return v

class PaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"
    description: Optional[str] = None
    category: str = "payment"
    payment_method: str = "card"
    recipient_info: RecipientInfo
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 100000:  # $100k limit
            raise ValueError('Amount exceeds maximum limit of $100,000')
        return round(v, 2)
    
    @validator('category')
    def validate_category(cls, v):
        valid_categories = ['payment', 'transfer', 'purchase', 'refund']
        if v not in valid_categories:
            raise ValueError(f'Category must be one of {valid_categories}. You provided: "{v}"')
        return v
    
    @validator('payment_method')
    def validate_payment_method(cls, v):
        valid_methods = ['card', 'bank_transfer', 'wallet', 'crypto']
        if v not in valid_methods:
            raise ValueError(f'Payment method must be one of {valid_methods}')
        return v

class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float
    currency: str
    risk_score: int
    ai_validation: Dict[str, Any]
    created_at: datetime
    estimated_completion: Optional[str] = None

class TransactionDetail(BaseModel):
    id: int
    transaction_id: str
    amount: float
    currency: str
    description: Optional[str]
    category: str
    status: str
    risk_score: int
    ai_validation_result: Optional[Dict[str, Any]]
    payment_method: str
    recipient_info: Optional[Dict[str, Any]]
    transaction_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]

class PaymentStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['pending', 'processing', 'success', 'failed', 'cancelled']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of {valid_statuses}')
        return v

# ---------------- Routes ----------------
MIN_TRANSACTION_AMOUNT = 0.5  # USD
MAX_RISK_SCORE = 7  # Block transactions above this AI risk score

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new payment transaction with robust error handling and risk controls"""
    try:
        # --- 1. Prepare validation data ---
        validation_data = {
            "amount": payment_data.amount,
            "currency": payment_data.currency,
            "description": payment_data.description,
            "category": payment_data.category,
            "payment_method": payment_data.payment_method,
            "recipient_info": payment_data.recipient_info or {},
            "metadata": payment_data.metadata or {},
            "user_id": current_user.id,
            "user_role": current_user.role
        }
        safe_validation_data = serialize_input(validation_data)
        logger.info(f"Validation data prepared: {safe_validation_data}")

        # --- 2. AI validation ---
        try:
            ai_validation = await payment_agent.validate_payment(safe_validation_data) or {}
            if not isinstance(ai_validation, dict):
                logger.warning("AI validation returned non-dict, defaulting to safe values")
                ai_validation = {"valid": False, "risk_score": 10}
            logger.info(f"AI validation result: {ai_validation}")
        except Exception as e:
            logger.error(f"AI validation failed: {str(e)}")
            ai_validation = {"valid": False, "risk_score": 10}

        # --- 2a. Additional business rules ---
        # Recipient email check
        if not payment_data.recipient_info or not payment_data.recipient_info.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient email is required"
            )

        # Minimum amount check
        if payment_data.amount < MIN_TRANSACTION_AMOUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction amount must be at least ${MIN_TRANSACTION_AMOUNT}"
            )

        # AI risk score check
        risk_score = ai_validation.get("risk_score", 5)
        if risk_score > MAX_RISK_SCORE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Transaction blocked due to high risk (score: {risk_score})"
            )

        # --- 3. Create Transaction ---
        try:
            transaction = Transaction(
                transaction_id=str(uuid.uuid4()),
                user_id=current_user.id,
                amount=payment_data.amount,
                currency=payment_data.currency,
                description=payment_data.description,
                category=payment_data.category,
                payment_method=payment_data.payment_method,
                recipient_info=payment_data.recipient_info.dict(),
                transaction_metadata=payment_data.metadata,
                status="pending" if ai_validation.get("valid", False) else "failed",
                risk_score=risk_score,
                ai_validation_result=ai_validation
            )
            db.add(transaction)
            db.flush()
            db.commit()
            db.refresh(transaction)
            logger.info(f"Transaction created: {transaction.transaction_id}")
        except Exception as e:
            logger.exception(f"Failed to create transaction: {str(e)}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error while creating transaction: {str(e)}"
            )

        # --- 4. Log AI operation ---
        try:
            ai_log = AILog(
                agent_name="PaymentAgent",
                agent_type="validation",
                operation="validate_payment",
                input_data=safe_validation_data,
                output_data=serialize_input(ai_validation),
                execution_time=ai_validation.get("execution_time", 0),
                status="success",
                user_id=current_user.id,
                transaction_id=transaction.transaction_id,
                model_used="gemini-1.5-flash",
                tokens_used=ai_validation.get("tokens_used", 0),
                cost=ai_validation.get("cost", 0.0)
            )
            db.add(ai_log)
            db.commit()
            logger.info(f"AI log saved for transaction {transaction.transaction_id}")
        except Exception as e:
            logger.error(f"Failed to save AI log: {str(e)}")
            db.rollback()  # non-fatal

        # --- 5. Schedule Email Notification ---
        try:
            recipient_email = transaction.recipient_info.get("email")
            if recipient_email:
                background_tasks.add_task(
                    send_payment_notification,
                    transaction.recipient_info.get("name", current_user.full_name or current_user.email),
                    transaction
                )
                logger.info(f"Payment notification scheduled for {recipient_email}")
            else:
                logger.warning(f"No recipient email found for transaction {transaction.transaction_id}")
        except Exception as e:
            logger.error(f"Failed to schedule payment notification: {str(e)}")
            # non-fatal

        # --- 6. Determine estimated completion ---
        estimated_completion = None
        if ai_validation.get("valid", False):
            if payment_data.payment_method == "card":
                estimated_completion = "2-5 minutes"
            elif payment_data.payment_method == "bank_transfer":
                estimated_completion = "1-3 business days"
            elif payment_data.payment_method == "wallet":
                estimated_completion = "Instant"

        return PaymentResponse(
            transaction_id=transaction.transaction_id,
            status=transaction.status,
            amount=transaction.amount,
            currency=transaction.currency,
            risk_score=transaction.risk_score,
            ai_validation=ai_validation,
            created_at=transaction.created_at,
            estimated_completion=estimated_completion
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unhandled error in create_payment: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed due to server error"
        )


@router.get("/", response_model=List[TransactionDetail])
async def get_user_payments(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history"""
    try:
        query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
        
        if status_filter:
            query = query.filter(Transaction.status == status_filter)
        
        transactions = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
        
        return [
            TransactionDetail(
                id=tx.id,
                transaction_id=tx.transaction_id,
                amount=tx.amount,
                currency=tx.currency,
                description=tx.description,
                category=tx.category,
                status=tx.status,
                risk_score=tx.risk_score,
                ai_validation_result=tx.ai_validation_result,
                payment_method=tx.payment_method,
                recipient_info=tx.recipient_info,
                transaction_metadata=tx.transaction_metadata,
                created_at=tx.created_at,
                updated_at=tx.updated_at,
                processed_at=tx.processed_at
            )
            for tx in transactions
        ]
        
    except Exception as e:
        logger.error(f"Error fetching user payments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payments"
        )

# ✅ Moved analytics summary above transaction_id
@router.get("/analytics/summary")
async def get_payment_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment analytics summary for the user"""
    try:
        from sqlalchemy import func
        
        # Get transaction statistics
        stats = db.query(
            func.count(Transaction.id).label('total_transactions'),
            func.sum(Transaction.amount).label('total_amount'),
            func.avg(Transaction.amount).label('average_amount'),
            func.avg(Transaction.risk_score).label('average_risk_score')
        ).filter(Transaction.user_id == current_user.id).first()
        
        # Get status breakdown
        status_breakdown = db.query(
            Transaction.status,
            func.count(Transaction.id).label('count')
        ).filter(Transaction.user_id == current_user.id).group_by(Transaction.status).all()
        
        # Get category breakdown
        category_breakdown = db.query(
            Transaction.category,
            func.count(Transaction.id).label('count'),
            func.sum(Transaction.amount).label('total_amount')
        ).filter(Transaction.user_id == current_user.id).group_by(Transaction.category).all()
        
        return {
            "summary": {
                "total_transactions": stats.total_transactions or 0,
                "total_amount": float(stats.total_amount or 0),
                "average_amount": float(stats.average_amount or 0),
                "average_risk_score": float(stats.average_risk_score or 0)
            },
            "status_breakdown": [
                {"status": item.status, "count": item.count}
                for item in status_breakdown
            ],
            "category_breakdown": [
                {
                    "category": item.category,
                    "count": item.count,
                    "total_amount": float(item.total_amount or 0)
                }
                for item in category_breakdown
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching payment summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment summary"
        )

@router.get("/{transaction_id}", response_model=TransactionDetail)
async def get_payment_details(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific payment details"""
    try:
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == transaction_id,
            Transaction.user_id == current_user.id
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        return TransactionDetail(
            id=transaction.id,
            transaction_id=transaction.transaction_id,
            amount=transaction.amount,
            currency=transaction.currency,
            description=transaction.description,
            category=transaction.category,
            status=transaction.status,
            risk_score=transaction.risk_score,
            ai_validation_result=transaction.ai_validation_result,
            payment_method=transaction.payment_method,
            recipient_info=transaction.recipient_info,
            transaction_metadata=transaction.transaction_metadata,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
            processed_at=transaction.processed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payment details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment details"
        )

@router.patch("/{transaction_id}/status")
async def update_payment_status(
    transaction_id: str,
    status_update: PaymentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update payment status (for user cancellation only)"""
    try:
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == transaction_id,
            Transaction.user_id == current_user.id
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Users can only cancel pending payments
        if status_update.status == "cancelled" and transaction.status == "pending":
            transaction.status = "cancelled"
            transaction.updated_at = datetime.utcnow()
            
            # Add cancellation note to metadata
            if not transaction.transaction_metadata:
                transaction.transaction_metadata = {}
            transaction.transaction_metadata["cancellation_reason"] = status_update.notes or "User cancellation"
            transaction.transaction_metadata["cancelled_at"] = datetime.utcnow().isoformat()
            
            db.commit()
            
            logger.info(f"Payment cancelled by user: {transaction_id}")
            
            return {"message": "Payment cancelled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update payment status"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update payment status"
        )