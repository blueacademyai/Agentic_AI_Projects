import google.generativeai as genai
from langsmith import traceable
import json
import logging
import time
from typing import Dict, Any, List
import asyncio
import re
logger = logging.getLogger(__name__)

class PaymentAgent:
    def __init__(self, api_key: str):
        """Initialize Payment Validation Agent"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.fraud_patterns = self._load_fraud_patterns()
        
    def _load_fraud_patterns(self) -> List[Dict[str, Any]]:
        """Load known fraud patterns"""
        return [
            {
                "pattern": "round_amount_high_value",
                "description": "Round amounts over $1000",
                "risk_score": 6
            },
            {
                "pattern": "unusual_time",
                "description": "Transaction outside business hours",
                "risk_score": 3
            },
            {
                "pattern": "rapid_transactions",
                "description": "Multiple transactions in short time",
                "risk_score": 7
            },
            {
                "pattern": "high_risk_country",
                "description": "Transaction to high-risk country",
                "risk_score": 8
            },
            {
                "pattern": "suspicious_metadata",
                "description": "Missing or suspicious transaction metadata",
                "risk_score": 5
            }
        ]
    
    @traceable
    async def validate_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment using AI and rule-based checks"""
        start_time = time.time()
        
        try:
            # Perform rule-based validation first
            rule_based_result = await self._rule_based_validation(payment_data)
            
            # Perform AI-based validation
            ai_result = await self._ai_validation(payment_data)
            
            # Combine results
            final_result = self._combine_validations(rule_based_result, ai_result, payment_data)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            final_result["execution_time"] = execution_time
            
            logger.info(f"Payment validation completed: {final_result['valid']}, Risk: {final_result['risk_score']}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Payment validation error: {str(e)}")
            return {
                "valid": False,
                "risk_score": 10,
                "issues": [f"Validation error: {str(e)}"],
                "suggestions": ["Please try again or contact support"],
                "execution_time": time.time() - start_time,
                "error": True
            }
    
    async def _rule_based_validation(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform rule-based validation checks"""
        issues = []
        risk_score = 0
        suggestions = []
        
        amount = payment_data.get("amount", 0)
        currency = payment_data.get("currency", "USD")
        description = payment_data.get("description", "")
        category = payment_data.get("category", "")
        payment_method = payment_data.get("payment_method", "")
        recipient_info = payment_data.get("recipient_info", {})
        metadata = payment_data.get("metadata", {})
        
        # Amount validation
        if amount <= 0:
            issues.append("Invalid amount")
            risk_score += 10
        elif amount > 100000:
            issues.append("Amount exceeds daily limit")
            risk_score += 8
        elif amount > 10000:
            risk_score += 3  # Higher amounts are riskier
        
        # Round amount detection
        if amount > 1000 and amount == int(amount):
            risk_score += 2
            suggestions.append("Round amounts over $1000 are flagged for review")
        
        # Description validation
        if not description or len(description.strip()) < 3:
            issues.append("Missing or insufficient transaction description")
            risk_score += 3
            suggestions.append("Please provide a clear description of the transaction")
        
        # Suspicious keywords in description
        suspicious_keywords = ["test", "testing", "urgent", "immediate", "asap", "emergency"]
        if any(keyword in description.lower() for keyword in suspicious_keywords):
            risk_score += 2
            suggestions.append("Transaction description contains flagged keywords")
        
        # Payment method validation
        high_risk_methods = ["crypto", "wire_transfer"]
        if payment_method in high_risk_methods:
            risk_score += 4
            suggestions.append(f"{payment_method} transactions require additional verification")
        
        # Recipient validation
        if category in ["transfer", "payment"]:
            if not recipient_info:
                if amount > 100:  # Require recipient info only for larger transactions
                    issues.append("Missing recipient information")
                    risk_score += 3
                    suggestions.append("Please provide recipient details")
                else:
                    # Small transactions allowed without recipient info, but add slight risk
                    risk_score += 1

        
        # Metadata validation
        required_fields = ["ip_address", "device_id"]
        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            risk_score += len(missing_fields)
        
        return {
            "method": "rule_based",
            "issues": issues,
            "risk_score": min(risk_score, 10),
            "suggestions": suggestions,
            "valid": len(issues) == 0 and risk_score < 8
        }
    
    async def _ai_validation(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform AI-based validation using Gemini"""
        try:
            prompt = f"""
            Analyze this payment transaction for potential fraud or compliance issues:

            Transaction Details:
            - Amount: ${payment_data.get('amount', 0)} {payment_data.get('currency', 'USD')}
            - Description: {payment_data.get('description', 'N/A')}
            - Category: {payment_data.get('category', 'N/A')}
            - Payment Method: {payment_data.get('payment_method', 'N/A')}
            - Recipient: {json.dumps(payment_data.get('recipient_info', {}))}
            - Metadata: {json.dumps(payment_data.get('metadata', {}))}

            Please analyze for:
            1. Fraud indicators
            2. Compliance issues
            3. Money laundering patterns
            4. Unusual transaction characteristics
            5. Risk assessment

            Return ONLY valid JSON (no extra text) with:
            - "risk_score": integer 1-10
            - "fraud_indicators": list of strings
            - "compliance_issues": list of strings
            - "recommendations": list of strings
            - "confidence": float (0-1)
            - "reasoning": string
            """

            response = await self.model.generate_content_async(prompt)

            ai_text = ""
            if response.candidates:
                parts = response.candidates[0].content.parts
                if parts and hasattr(parts[0], "text"):
                    ai_text = parts[0].text.strip()

            # ✅ Clean Gemini output
            ai_text = ai_text.strip("`")  # remove stray backticks
            if ai_text.startswith("json"):
                ai_text = ai_text[4:].strip()

            # ✅ Extract first JSON block
            match = re.search(r"\{.*\}", ai_text, re.DOTALL)
            if match:
                ai_text = match.group(0)

            try:
                result = json.loads(ai_text)
            except json.JSONDecodeError:
                logger.warning(f"AI returned invalid JSON: {ai_text[:200]}...")
                raise

            # ✅ Ensure structure
            required_fields = ["risk_score", "fraud_indicators", "compliance_issues", "recommendations"]
            for field in required_fields:
                result.setdefault(field, [] if field != "risk_score" else 5)

            result["risk_score"] = max(1, min(10, int(result.get("risk_score", 5))))

            return {
                "method": "ai_based",
                "risk_score": result["risk_score"],
                "fraud_indicators": result.get("fraud_indicators", []),
                "compliance_issues": result.get("compliance_issues", []),
                "recommendations": result.get("recommendations", []),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", "AI analysis completed"),
                "valid": result["risk_score"] < 7
            }

        except Exception as e:
            logger.error(f"AI validation error: {str(e)}")
            return {
                "method": "ai_based",
                "risk_score": 6,
                "fraud_indicators": [],
                "compliance_issues": [],
                "recommendations": ["AI validation temporarily unavailable"],
                "confidence": 0.3,
                "reasoning": f"AI validation failed: {str(e)}",
                "valid": True,
                "error": str(e)
            }

    
    def _combine_validations(self, rule_result: Dict[str, Any], ai_result: Dict[str, Any], payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Combine rule-based and AI validation results"""
        
        # Calculate weighted risk score (60% AI, 40% rules)
        combined_risk = int(
            (ai_result["risk_score"] * 0.6) + (rule_result["risk_score"] * 0.4)
        )
        
        # Combine issues and suggestions
        all_issues = rule_result["issues"] + ai_result.get("fraud_indicators", []) + ai_result.get("compliance_issues", [])
        all_suggestions = (
            rule_result["suggestions"] + 
            ai_result.get("recommendations", [])
        )
        
        # ✅ Ignore missing recipient name for small payments
        ignoreable_issues = {"Missing recipient information", "Lack of recipient name"}
        amount = payment_data.get("amount", 0)

        filtered_issues = [
            issue for issue in all_issues
            if not (amount <= 100 and issue in ignoreable_issues)
        ]

        # Final validation decision
        is_valid = (
            rule_result["valid"] and 
            ai_result["valid"] and 
            combined_risk < 8 and
            len(all_issues) == 0
        )
        
        # Generate transaction recommendations
        recommendations = self._generate_recommendations(combined_risk, all_issues)
        
        return {
            "valid": is_valid,
            "risk_score": combined_risk,
            "issues": list(set(all_issues)),  # Remove duplicates
            "suggestions": list(set(all_suggestions)),
            "recommendations": recommendations,
            "validation_details": {
                "rule_based": {
                    "risk_score": rule_result["risk_score"],
                    "issues": rule_result["issues"]
                },
                "ai_based": {
                    "risk_score": ai_result["risk_score"],
                    "confidence": ai_result.get("confidence", 0.7),
                    "reasoning": ai_result.get("reasoning", "")
                }
            },
            "next_steps": self._get_next_steps(is_valid, combined_risk),
            "estimated_processing_time": self._estimate_processing_time(combined_risk, is_valid)
        }
    
    def _generate_recommendations(self, risk_score: int, issues: List[str]) -> List[str]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []
        
        if risk_score >= 8:
            recommendations.append("Transaction requires manual review")
            recommendations.append("Additional identity verification may be needed")
        elif risk_score >= 6:
            recommendations.append("Transaction will be monitored")
            recommendations.append("Consider providing additional transaction details")
        elif risk_score >= 4:
            recommendations.append("Transaction appears normal with minor flags")
        else:
            recommendations.append("Transaction passes all automated checks")
        
        if issues:
            recommendations.append("Please address the identified issues before resubmitting")
        
        return recommendations
    
    def _get_next_steps(self, is_valid: bool, risk_score: int) -> List[str]:
        """Get next steps for the transaction"""
        if not is_valid:
            return [
                "Transaction blocked",
                "Please review and correct the identified issues",
                "Contact support if you need assistance"
            ]
        elif risk_score >= 7:
            return [
                "Transaction queued for manual review",
                "You will receive an email update within 2-4 hours",
                "No further action required at this time"
            ]
        elif risk_score >= 5:
            return [
                "Transaction processing with enhanced monitoring",
                "Expected completion in 5-10 minutes",
                "You will receive confirmation once processed"
            ]
        else:
            return [
                "Transaction approved for immediate processing",
                "Expected completion in 2-5 minutes",
                "Confirmation will be sent shortly"
            ]
    
    def _estimate_processing_time(self, risk_score: int, is_valid: bool) -> str:
        """Estimate processing time based on risk score"""
        if not is_valid:
            return "Blocked - requires correction"
        elif risk_score >= 8:
            return "2-24 hours (manual review)"
        elif risk_score >= 6:
            return "30 minutes - 2 hours (enhanced checks)"
        elif risk_score >= 4:
            return "5-15 minutes (automated processing)"
        else:
            return "2-5 minutes (fast track)"
    
    async def get_transaction_insights(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI insights about transaction patterns"""
        try:
            prompt = f"""
            Analyze this transaction data and provide insights:
            {json.dumps(transaction_data, indent=2)}
            
            Please provide:
            1. Transaction category insights
            2. Amount pattern analysis
            3. Timing analysis
            4. Risk factors summary
            5. Improvement suggestions
            
            Return structured JSON response.
            """

            # ✅ Async call
            response = await self.model.generate_content_async(prompt)

            # ✅ Extract AI text safely
            ai_text = ""
            if response.candidates:
                parts = response.candidates[0].content.parts
                if parts and hasattr(parts[0], "text"):
                    ai_text = parts[0].text

            try:
                return json.loads(ai_text)
            except json.JSONDecodeError:
                return {
                    "insights": ai_text,
                    "structured": False
                }

        except Exception as e:
            logger.error(f"Transaction insights error: {str(e)}")
            return {
                "error": str(e),
                "insights": "Unable to generate insights at this time"
            }

    
    def validate_payment_sync(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous version of validate_payment for compatibility"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.validate_payment(payment_data))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Sync payment validation error: {str(e)}")
            return {
                "valid": False,
                "risk_score": 10,
                "issues": [f"Validation error: {str(e)}"],
                "suggestions": ["Please try again or contact support"],
                "execution_time": 0,
                "error": True
            }
    
    def get_fraud_patterns(self) -> List[Dict[str, Any]]:
        """Get current fraud patterns for admin review"""
        return self.fraud_patterns
    
    def update_fraud_patterns(self, new_patterns: List[Dict[str, Any]]) -> bool:
        """Update fraud patterns (admin function)"""
        try:
            self.fraud_patterns = new_patterns
            logger.info(f"Updated fraud patterns: {len(new_patterns)} patterns loaded")
            return True
        except Exception as e:
            logger.error(f"Error updating fraud patterns: {str(e)}")
            return False
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics for monitoring"""
        return {
            "total_patterns": len(self.fraud_patterns),
            "high_risk_patterns": len([p for p in self.fraud_patterns if p.get("risk_score", 0) >= 7]),
            "medium_risk_patterns": len([p for p in self.fraud_patterns if 4 <= p.get("risk_score", 0) < 7]),
            "low_risk_patterns": len([p for p in self.fraud_patterns if p.get("risk_score", 0) < 4])
        }