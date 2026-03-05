from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
import uvicorn
import os
import logging
from datetime import datetime

# Import local modules
from .database import get_db, engine
from .models import Base
from .routes import auth, payments, admin, chatbot

# Create all database tables (if not exists)
Base.metadata.create_all(bind=engine)

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="AI Payment Processing System",
    description="Secure payment processing system with AI-powered validation and assistance",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware (security)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # In production, replace with actual domains
)

# -------------------------------
# Exception handlers
# -------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# -------------------------------
# Middleware for request logging
# -------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    process_time = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"Response: {response.status_code} - Processing time: {process_time:.3f}s")
    
    return response

# -------------------------------
# Include routers
# -------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"])
app.include_router(chatbot.router, prefix="/api/chatbot", tags=["Chatbot"])

# -------------------------------
# Root & status endpoints
# -------------------------------
@app.get("/")
async def root():
    return {
        "message": "AI Payment Processing System API",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/status")
async def api_status():
    return {
        "api_version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "authentication": "/api/auth",
            "payments": "/api/payments",
            "admin": "/api/admin",
            "chatbot": "/api/chatbot"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# -------------------------------
# Startup & shutdown events
# -------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Payment Processing System...")
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/bank_policies", exist_ok=True)
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Payment Processing System...")
    logger.info("Application shutdown complete")

# -------------------------------
# Run server (development)
# -------------------------------
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="debug" if debug else "info"
    )
