import logging
import time
from typing import Tuple
from typing import Dict, Any, Optional, List

from ..utils.rag_service import RAGService

logger = logging.getLogger(__name__)

class PolicyAgent:
    def __init__(self, api_key: str, rag_service: Optional[RAGService] = None):
        """
        Initialize Policy Agent
        - Handles policy, compliance, and rules-based queries
        - Uses RAG for retrieving relevant policies
        """
        self.rag_service = rag_service or RAGService(api_key=api_key)

        # Default known policies (can be expanded or fetched from DB)
        self.default_policies = {
            "transaction_limits": "Daily transaction limits: $100,000 per transfer, $500,000 total per day. Higher limits are available for verified business accounts.",
            "processing_times": "Card payments: 2-5 minutes, Bank transfers: 1-3 business days, Wallet transfers: Instant, Wire transfers: Same day to 1 business day.",
            "security_measures": "We use bank-level security: encryption, AI fraud detection, MFA, PCI DSS compliance, and 24/7 monitoring.",
            "fees": "Most payments are free. Wire transfers and international payments may incur small fees depending on the bank and method."
        }

    async def handle_policy_question(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a user’s policy-related question
        Returns a structured response with optional escalation if no answer is found
        """
        start_time = time.time()
        try:
            # Try to fetch policy answer using RAG
            rag_answer = await self.rag_service.get_policy_summary(query)

            if rag_answer:
                response_text = f"Here’s what I found in our policy documents: {rag_answer}"
                source = "rag"
            else:
                # Fallback: check default policies
                response_text, source = self._fallback_policy(query)

            return {
                "response": response_text,
                "message_type": "policy_response",
                "escalate_to_admin": False if response_text else True,
                "context": {"policy_query": query},
                "execution_time": time.time() - start_time,
                "source": source
            }

        except Exception as e:
            logger.error(f"PolicyAgent error: {str(e)}")
            return {
                "response": "I couldn’t retrieve the policy information right now. Please try again later or contact support.",
                "message_type": "error",
                "escalate_to_admin": True,
                "context": {"policy_query": query},
                "execution_time": time.time() - start_time,
                "error": str(e)
            }

    def _fallback_policy(self, query: str) -> Tuple[str, str]:
        """
        Match query with known default policies using simple keyword search
        """
        query_lower = query.lower()
        if "limit" in query_lower or "maximum" in query_lower:
            return self.default_policies["transaction_limits"], "default"
        elif "time" in query_lower or "processing" in query_lower:
            return self.default_policies["processing_times"], "default"
        elif "security" in query_lower or "safe" in query_lower:
            return self.default_policies["security_measures"], "default"
        elif "fee" in query_lower or "charge" in query_lower:
            return self.default_policies["fees"], "default"
        else:
            return "", "none"
