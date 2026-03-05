import google.generativeai as genai
from langsmith import traceable
import json
import logging
import time
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)

class ChatbotAgent:
    def __init__(self, api_key: str):
        """Initialize Chatbot Agent"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.conversation_context = {}
        self.faq_database = self._load_faq_database()
        
    def _load_faq_database(self) -> List[Dict[str, str]]:
        """Load FAQ database"""
        return [
            {
                "question": "How do I make a payment?",
                "answer": "To make a payment, go to the Payments section, enter the amount and recipient details, select your payment method, and click Submit. Your payment will be validated and processed.",
                "keywords": ["payment", "make", "send", "transfer"]
            },
            {
                "question": "What are the transaction limits?",
                "answer": "Daily transaction limits are: Individual transactions up to $100,000, Daily total up to $500,000. Higher limits available for verified business accounts.",
                "keywords": ["limit", "maximum", "daily", "transaction"]
            },
            {
                "question": "How long do payments take?",
                "answer": "Processing times vary by method: Card payments: 2-5 minutes, Bank transfers: 1-3 business days, Wallet transfers: Instant, Wire transfers: Same day to 1 business day.",
                "keywords": ["time", "processing", "how long", "duration"]
            },
            {
                "question": "Why was my payment flagged?",
                "answer": "Payments may be flagged for various reasons including: High amounts, Unusual patterns, Missing information, Security checks. Our AI system reviews all transactions for safety.",
                "keywords": ["flagged", "blocked", "review", "risk", "security"]
            },
            {
                "question": "How do I cancel a payment?",
                "answer": "You can cancel pending payments from your transaction history. Go to Payments > History, find the transaction, and click Cancel if available. Processed payments cannot be cancelled.",
                "keywords": ["cancel", "stop", "reverse", "undo"]
            },
            {
                "question": "Is my payment secure?",
                "answer": "Yes, we use bank-level security including: End-to-end encryption, AI fraud detection, Multi-factor authentication, PCI DSS compliance, 24/7 monitoring.",
                "keywords": ["secure", "safety", "protection", "encryption"]
            },
            {
                "question": "What payment methods are supported?",
                "answer": "We support: Credit/Debit cards, Bank transfers, Digital wallets, Wire transfers, ACH transfers. Cryptocurrency support coming soon.",
                "keywords": ["methods", "card", "bank", "wallet", "wire"]
            },
            {
                "question": "How do I contact support?",
                "answer": "You can contact our support team: 24/7 chat support, Email: support@paymentsystem.com, Phone: 1-800-PAY-HELP, or escalate this chat to an admin.",
                "keywords": ["support", "help", "contact", "assistance"]
            }
        ]
    
    @traceable
    async def process_message(self, message: str, context: Dict[str, Any], rag_service=None) -> Dict[str, Any]:
        """Process user message and generate response"""
        start_time = time.time()
        
        try:
            # Analyze user intent
            intent = await self._analyze_intent(message, context)
            
            # Check for FAQ match first
            faq_response = self._check_faq_match(message)
            if faq_response:
                return {
                    "response": faq_response,
                    "message_type": "faq",
                    "suggestions": self._get_related_suggestions(message),
                    "escalate_to_admin": False,
                    "execution_time": time.time() - start_time,
                    "source": "faq"
                }
            
            # Handle specific intents
            if intent["type"] == "payment_status":
                response = await self._handle_payment_status(message, context)
            elif intent["type"] == "payment_help":
                response = await self._handle_payment_help(message, context, rag_service)
            elif intent["type"] == "account_inquiry":
                response = await self._handle_account_inquiry(message, context)
            elif intent["type"] == "technical_support":
                response = await self._handle_technical_support(message, context)
            elif intent["type"] == "policy_question":
                response = await self._handle_policy_question(message, context, rag_service)
            else:
                response = await self._handle_general_inquiry(message, context, rag_service)
            
            # Add common response elements
            response.update({
                "execution_time": time.time() - start_time,
                "intent": intent,
                "suggestions": self._get_contextual_suggestions(intent, context)
            })
            
            logger.info(f"Chatbot processed message, intent: {intent['type']}")
            
            return response
            
        except Exception as e:
            logger.error(f"Chatbot processing error: {str(e)}")
            return {
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again or contact support for immediate assistance.",
                "message_type": "error",
                "escalate_to_admin": True,
                "execution_time": time.time() - start_time,
                "error": str(e)
            }
    
    async def _analyze_intent(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user intent using AI"""
        try:
            prompt = f"""
            Analyze the user's intent from this message:
            Message: "{message}"
            
            Previous context: {json.dumps(context.get("chat_history", [])[-3:], indent=2)}
            
            Classify the intent into one of these categories:
            - payment_status: Asking about transaction status
            - payment_help: Need help making a payment
            - account_inquiry: Questions about account or settings
            - technical_support: Technical issues or bugs
            - policy_question: Questions about policies, fees, or procedures
            - general_inquiry: General questions or conversation
            
            Return JSON with:
            - "type": intent category
            - "confidence": float 0-1
            - "entities": extracted entities (amounts, dates, transaction IDs, etc.)
            - "urgency": "low", "medium", or "high"
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                result = json.loads(response.text)
                return {
                    "type": result.get("type", "general_inquiry"),
                    "confidence": float(result.get("confidence", 0.7)),
                    "entities": result.get("entities", {}),
                    "urgency": result.get("urgency", "medium")
                }
            except json.JSONDecodeError:
                # Fallback to keyword-based classification
                return self._classify_intent_keywords(message)
                
        except Exception as e:
            logger.error(f"Intent analysis error: {str(e)}")
            return self._classify_intent_keywords(message)
    
    def _classify_intent_keywords(self, message: str) -> Dict[str, Any]:
        """Fallback keyword-based intent classification"""
        message_lower = message.lower()
        
        # Payment status keywords
        if any(word in message_lower for word in ["status", "pending", "failed", "cancelled", "complete"]):
            return {"type": "payment_status", "confidence": 0.8, "entities": {}, "urgency": "medium"}
        
        # Payment help keywords
        if any(word in message_lower for word in ["how to pay", "make payment", "send money", "transfer"]):
            return {"type": "payment_help", "confidence": 0.7, "entities": {}, "urgency": "medium"}
        
        # Account inquiry keywords
        if any(word in message_lower for word in ["account", "profile", "settings", "update"]):
            return {"type": "account_inquiry", "confidence": 0.7, "entities": {}, "urgency": "low"}
        
        # Technical support keywords
        if any(word in message_lower for word in ["error", "bug", "not working", "broken", "issue"]):
            return {"type": "technical_support", "confidence": 0.8, "entities": {}, "urgency": "high"}
        
        # Policy question keywords
        if any(word in message_lower for word in ["policy", "fee", "limit", "rule", "regulation"]):
            return {"type": "policy_question", "confidence": 0.7, "entities": {}, "urgency": "low"}
        
        return {"type": "general_inquiry", "confidence": 0.5, "entities": {}, "urgency": "low"}
    
    def _check_faq_match(self, message: str) -> Optional[str]:
        """Check if message matches FAQ"""
        message_lower = message.lower()
        
        for faq in self.faq_database:
            if any(keyword in message_lower for keyword in faq["keywords"]):
                # Check if it's a close match
                similarity_score = self._calculate_similarity(message_lower, faq["question"].lower())
                if similarity_score > 0.3:
                    return faq["answer"]
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0
    
    async def _handle_payment_status(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment status inquiries"""
        user_id = context.get("user_id")
        
        # Extract transaction ID if mentioned
        transaction_id_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', message)
        
        if transaction_id_match:
            transaction_id = transaction_id_match.group()
            response = f"I can help you check the status of transaction {transaction_id}. Let me look that up for you. You can also check your transaction history in the Payments section of your dashboard."
        else:
            response = "I can help you check your payment status. You can view all your transactions in the Payments > History section. If you have a specific transaction ID, please share it with me for detailed status information."
        
        return {
            "response": response,
            "message_type": "status_inquiry",
            "escalate_to_admin": False,
            "context": {"requires_transaction_lookup": True}
        }
    
    async def _handle_payment_help(self, message: str, context: Dict[str, Any], rag_service=None) -> Dict[str, Any]:
        """Handle payment assistance requests"""
        try:
            prompt = f"""
            The user needs help with making a payment. Their message: "{message}"
            
            Provide helpful, step-by-step guidance for making payments. Include:
            1. Clear instructions
            2. Important security reminders
            3. What information they'll need
            4. Expected processing times
            5. Common issues to avoid
            
            Keep the response friendly, helpful, and under 200 words.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "response": response.text,
                "message_type": "payment_assistance",
                "escalate_to_admin": False,
                "context": {"providing_payment_help": True}
            }
            
        except Exception as e:
            logger.error(f"Payment help error: {str(e)}")
            return {
                "response": "I'd be happy to help you make a payment. Go to the Payments section, enter the recipient details and amount, choose your payment method, and submit. If you need more specific help, I can connect you with a support agent.",
                "message_type": "payment_assistance",
                "escalate_to_admin": True
            }
    
    async def _handle_account_inquiry(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle account-related questions"""
        user_email = context.get("user_email", "")
        
        return {
            "response": f"I can help with account-related questions. Your account ({user_email}) settings can be updated in the profile section. What specific account information do you need help with? I can assist with profile updates, security settings, or notification preferences.",
            "message_type": "account_help",
            "escalate_to_admin": False,
            "context": {"account_assistance": True}
        }
    
    async def _handle_technical_support(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle technical support requests"""
        return {
            "response": "I understand you're experiencing a technical issue. I'll connect you with our technical support team who can provide specialized assistance. In the meantime, try refreshing the page or clearing your browser cache. Is this an urgent issue that's preventing you from making payments?",
            "message_type": "technical_support",
            "escalate_to_admin": True,
            "context": {"technical_issue": True}
        }
    
    async def _handle_policy_question(self, message: str, context: Dict[str, Any], rag_service=None) -> Dict[str, Any]:
        """Handle policy and procedure questions"""
        if rag_service:
            try:
                policy_summary = await rag_service.get_policy_summary(message)
                return {
                    "response": f"Based on our policies: {policy_summary}",
                    "message_type": "policy_response",
                    "escalate_to_admin": False,
                    "context": {"policy_query": message}
                }
            except Exception as e:
                logger.error(f"RAG service error: {str(e)}")
        
        return {
            "response": "I can help with policy questions. Common topics include transaction limits ($100K per transaction, $500K daily), processing times (2-5 minutes for cards, 1-3 days for bank transfers), and security measures. What specific policy information do you need?",
            "message_type": "policy_response",
            "escalate_to_admin": False
        }
    
    async def _handle_general_inquiry(self, message: str, context: Dict[str, Any], rag_service=None) -> Dict[str, Any]:
        """Handle general conversations and inquiries"""
        try:
            prompt = f"""
            You are a helpful payment system assistant. The user said: "{message}"
            
            Respond in a friendly, professional manner. If it's a general greeting or conversation, respond appropriately. If it's a question about payments, banking, or financial services, provide helpful information.
            
            Keep responses under 150 words and always offer to help with specific payment-related tasks.
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                "response": response.text,
                "message_type": "general",
                "escalate_to_admin": False,
                "context": {"general_conversation": True}
            }
            
        except Exception as e:
            logger.error(f"General inquiry error: {str(e)}")
            return {
                "response": "Hello! I'm here to help you with payments and account questions. How can I assist you today?",
                "message_type": "general",
                "escalate_to_admin": False
            }
    
    def _get_related_suggestions(self, message: str) -> List[str]:
        """Get suggestions related to the current message"""
        message_lower = message.lower()
        suggestions = []
        
        if "payment" in message_lower:
            suggestions = [
                "Check payment status",
                "View payment history",
                "Payment methods available",
                "Transaction limits"
            ]
        elif "account" in message_lower:
            suggestions = [
                "Update profile information",
                "Security settings",
                "Notification preferences",
                "Account verification"
            ]
        elif "help" in message_lower or "support" in message_lower:
            suggestions = [
                "Contact human support",
                "Common issues",
                "User guide",
                "FAQ section"
            ]
        else:
            suggestions = [
                "Make a payment",
                "Check transaction history",
                "Account settings",
                "Contact support"
            ]
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def _get_contextual_suggestions(self, intent: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Get contextual suggestions based on intent and context"""
        intent_type = intent.get("type", "general_inquiry")
        
        suggestions_map = {
            "payment_status": [
                "View all transactions",
                "Download transaction receipt",
                "Contact support about payment"
            ],
            "payment_help": [
                "Start making a payment",
                "Check payment methods",
                "View transaction limits"
            ],
            "account_inquiry": [
                "Update profile",
                "Security settings",
                "View account summary"
            ],
            "technical_support": [
                "Report a bug",
                "Contact technical support",
                "System status"
            ],
            "policy_question": [
                "View all policies",
                "Transaction fees",
                "Security policies"
            ],
            "general_inquiry": [
                "Make a payment",
                "View transaction history",
                "Contact support"
            ]
        }
        
        return suggestions_map.get(intent_type, suggestions_map["general_inquiry"])
    
    def get_conversation_summary(self, chat_history: List[Dict[str, Any]]) -> str:
        """Generate a summary of the conversation"""
        if not chat_history:
            return "No conversation history"
        
        try:
            history_text = "\n".join([
                f"{msg['sender']}: {msg['content']}" 
                for msg in chat_history[-10:]  # Last 10 messages
            ])
            
            prompt = f"""
            Summarize this chat conversation:
            {history_text}
            
            Provide a brief summary of:
            1. Main topics discussed
            2. Issues raised
            3. Solutions provided
            4. Any unresolved matters
            
            Keep summary under 100 words.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Conversation summary error: {str(e)}")
            return "Unable to generate conversation summary"