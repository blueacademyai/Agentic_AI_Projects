import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import os
import logging
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Optional
import pickle
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self, api_key: str, policy_dir: str = "backend\policies\bank_policies"):
        """Initialize RAG Service for policy retrieval"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.policy_dir = Path(policy_dir)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Storage for documents and embeddings
        self.documents = []
        self.embeddings = None
        self.index_file = self.policy_dir / "policy_index.pkl"
        
        # Initialize the knowledge base
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize or load the policy knowledge base"""
        try:
            if self.index_file.exists():
                logger.info("Loading existing policy index...")
                self._load_index()
            else:
                logger.info("Creating new policy index...")
                self._create_index()
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {str(e)}")
            self._create_default_policies()
    
    def _create_default_policies(self):
        """Create default policy documents if none exist"""
        default_policies = [
            {
                "title": "Payment Processing Policy",
                "content": """
                Payment Processing Guidelines:
                
                1. Transaction Limits:
                   - Individual transaction limit: $100,000
                   - Daily transaction limit: $500,000
                   - Monthly limit for new accounts: $1,000,000
                
                2. Processing Times:
                   - Card payments: 2-5 minutes
                   - Bank transfers: 1-3 business days
                   - Wire transfers: Same day to 1 business day
                   - International transfers: 2-5 business days
                
                3. Verification Requirements:
                   - All transactions over $10,000 require additional verification
                   - Identity verification required for accounts over $50,000 monthly volume
                   - Business accounts require additional documentation
                
                4. Risk Assessment:
                   - All transactions are screened by AI systems
                   - High-risk transactions (score 7+) require manual review
                   - Suspicious patterns trigger automatic holds
                """,
                "category": "payment_processing"
            },
            {
                "title": "Security and Compliance Policy",
                "content": """
                Security and Compliance Framework:
                
                1. Data Protection:
                   - All data encrypted at rest and in transit
                   - PCI DSS Level 1 compliance
                   - SOC 2 Type II certified
                   - GDPR compliant data handling
                
                2. Authentication:
                   - Multi-factor authentication required for high-value transactions
                   - Session timeouts after 30 minutes of inactivity
                   - Password requirements: minimum 8 characters, mixed case, numbers, symbols
                
                3. Fraud Prevention:
                   - Real-time AI fraud detection
                   - Machine learning models updated daily
                   - Suspicious activity monitoring 24/7
                   - Automatic transaction blocking for high-risk patterns
                
                4. Regulatory Compliance:
                   - BSA/AML compliance program
                   - OFAC sanctions screening
                   - CTR filing for transactions over $10,000
                   - SAR filing for suspicious activities
                """,
                "category": "security_compliance"
            },
            {
                "title": "Customer Support Policy",
                "content": """
                Customer Support Guidelines:
                
                1. Support Channels:
                   - 24/7 AI chatbot support
                   - Live chat: Monday-Friday 8AM-8PM EST
                   - Phone support: Monday-Friday 9AM-6PM EST
                   - Email support: Response within 24 hours
                
                2. Issue Resolution:
                   - Payment issues: 2-4 hours response time
                   - Account access issues: 1-2 hours response time
                   - Technical issues: 4-8 hours response time
                   - Dispute resolution: 5-10 business days
                
                3. Escalation Process:
                   - Level 1: AI chatbot and basic support
                   - Level 2: Specialized support agents
                   - Level 3: Senior specialists and managers
                   - Executive escalation for unresolved issues
                
                4. Customer Rights:
                   - Right to explanation of AI decisions
                   - Right to human review of automated decisions
                   - Right to data portability and deletion
                   - Right to dispute resolution process
                """,
                "category": "customer_support"
            },
            {
                "title": "Fee Structure Policy",
                "content": """
                Fee Structure and Pricing:
                
                1. Transaction Fees:
                   - Domestic card payments: 2.9% + $0.30
                   - International card payments: 3.4% + $0.30
                   - Bank transfers (ACH): $0.50 per transaction
                   - Wire transfers: $25 domestic, $50 international
                   - Wallet transfers: Free for first 10 per month, $0.25 thereafter
                
                2. Account Fees:
                   - Personal accounts: Free
                   - Business accounts: $15/month
                   - Premium accounts: $50/month (includes priority support)
                   - Enterprise accounts: Custom pricing
                
                3. Special Fees:
                   - Failed payment fee: $5.00
                   - Chargeback fee: $15.00
                   - Express processing: $10.00 (1-hour processing)
                   - Currency conversion: 3.5% markup on exchange rate
                
                4. Fee Waivers:
                   - High-volume discounts available
                   - Non-profit organizations: 50% discount
                   - Educational institutions: 25% discount
                   - First 30 days: All fees waived for new accounts
                """,
                "category": "fees_pricing"
            }
        ]
        
        # Create policy directory if it doesn't exist
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        
        # Save default policies as text files
        for policy in default_policies:
            file_path = self.policy_dir / f"{policy['category']}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {policy['title']}\n\n{policy['content']}")
        
        # Now create the index
        self._create_index()
    
    def _load_policy_documents(self) -> List[Dict[str, Any]]:
        """Load policy documents from files"""
        documents = []
        
        if not self.policy_dir.exists():
            return documents
        
        for file_path in self.policy_dir.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Split content into chunks
                chunks = self._split_content(content)
                
                for i, chunk in enumerate(chunks):
                    documents.append({
                        'id': f"{file_path.stem}_{i}",
                        'title': file_path.stem.replace('_', ' ').title(),
                        'content': chunk,
                        'source': str(file_path),
                        'chunk_index': i
                    })
                    
            except Exception as e:
                logger.error(f"Error loading policy document {file_path}: {str(e)}")
        
        return documents
    
    def _split_content(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split content into overlapping chunks"""
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(content):
                # Look for sentence ending
                sentence_end = content.rfind('.', start, end)
                if sentence_end > start + chunk_size // 2:
                    end = sentence_end + 1
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = max(start + chunk_size - overlap, end)
        
        return chunks
    
    def _create_index(self):
        """Create embeddings index for policy documents"""
        try:
            # Load documents
            self.documents = self._load_policy_documents()
            
            if not self.documents:
                logger.warning("No policy documents found")
                return
            
            # Generate embeddings
            contents = [doc['content'] for doc in self.documents]
            logger.info(f"Generating embeddings for {len(contents)} document chunks...")
            
            self.embeddings = self.embedding_model.encode(contents)
            
            # Save index
            index_data = {
                'documents': self.documents,
                'embeddings': self.embeddings
            }
            
            with open(self.index_file, 'wb') as f:
                pickle.dump(index_data, f)
            
            logger.info(f"Policy index created with {len(self.documents)} documents")
            
        except Exception as e:
            logger.error(f"Error creating policy index: {str(e)}")
    
    def _load_index(self):
        """Load existing embeddings index"""
        try:
            with open(self.index_file, 'rb') as f:
                index_data = pickle.load(f)
            
            self.documents = index_data['documents']
            self.embeddings = index_data['embeddings']
            
            logger.info(f"Policy index loaded with {len(self.documents)} documents")
            
        except Exception as e:
            logger.error(f"Error loading policy index: {str(e)}")
            self._create_index()
    
    def _similarity_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Find most similar documents to query"""
        if not self.documents or self.embeddings is None:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_embedding, self.embeddings)[0]

            
            # Get top k similar documents
            top_indices = np.argsort(similarities)[::-1][:k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    results.append({
                        'document': self.documents[idx],
                        'similarity': float(similarities[idx])
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return []
    
    async def get_policy_summary(self, query: str, category: Optional[str] = None) -> str:
        """Get AI-generated policy summary based on query"""
        try:
            # Find relevant documents
            relevant_docs = self._similarity_search(query, k=5)
            
            if not relevant_docs:
                return "I couldn't find specific policy information related to your query. Please contact support for detailed assistance."
            
            # Filter by category if specified
            if category:
                relevant_docs = [
                    doc for doc in relevant_docs 
                    if category.lower() in doc['document'].get('source', '').lower()
                ]
            
            # Prepare context from relevant documents
            context_parts = []
            for doc_result in relevant_docs[:3]:  # Use top 3 most relevant
                doc = doc_result['document']
                context_parts.append(f"From {doc['title']}:\n{doc['content']}")
            
            context = "\n\n".join(context_parts)
            
            # Generate AI summary
            prompt = f"""
            Based on the following policy documents, provide a comprehensive and accurate summary for this query: "{query}"
            
            Policy Documents:
            {context}
            
            Please provide:
            1. A clear, direct answer to the query
            2. Relevant policy details and requirements
            3. Any important limitations or conditions
            4. Actionable next steps if applicable
            
            Keep the response informative but concise (under 300 words).
            If the query cannot be fully answered from the provided policies, clearly state what additional information might be needed.
            """
            
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating policy summary: {str(e)}")
            return f"I encountered an error while retrieving policy information. Please try rephrasing your query or contact support for assistance."
    
    async def get_policy_recommendations(self, user_context: Dict[str, Any]) -> List[str]:
        """Get policy-based recommendations for user"""
        try:
            # Build context query based on user information
            context_parts = []
            
            if user_context.get('transaction_amount'):
                context_parts.append(f"transaction amount ${user_context['transaction_amount']}")
            
            if user_context.get('transaction_type'):
                context_parts.append(f"{user_context['transaction_type']} transaction")
            
            if user_context.get('account_type'):
                context_parts.append(f"{user_context['account_type']} account")
            
            query = f"recommendations for {' '.join(context_parts)}"
            
            # Get relevant policies
            relevant_docs = self._similarity_search(query, k=3)
            
            if not relevant_docs:
                return [
                    "Ensure all transaction details are accurate",
                    "Verify recipient information before submitting",
                    "Keep transaction records for your files"
                ]
            
            # Extract recommendations using AI
            context = "\n".join([doc['document']['content'] for doc in relevant_docs])
            
            prompt = f"""
            Based on these policies and the user context, provide 3-5 specific recommendations:
            
            User Context: {json.dumps(user_context, indent=2)}
            
            Relevant Policies:
            {context}
            
            Provide actionable recommendations as a JSON list of strings.
            Focus on compliance, security, and best practices.
            """
            
            response = await asyncio.to_thread(self.model.generate_content, prompt)

            
            try:
                recommendations = json.loads(response.text)
                return recommendations if isinstance(recommendations, list) else []
            except json.JSONDecodeError:
                # Fallback: extract recommendations from text
                lines = response.text.split('\n')
                recommendations = []
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                        clean_line = line.lstrip('-•0123456789. ').strip()
                        if clean_line:
                            recommendations.append(clean_line)
                
                return recommendations[:5] if recommendations else [
                    "Follow standard security practices",
                    "Verify all transaction details",
                    "Keep records of all transactions"
                ]
            
        except Exception as e:
            logger.error(f"Error generating policy recommendations: {str(e)}")
            return [
                "Review transaction details carefully",
                "Ensure compliance with applicable policies",
                "Contact support for specific guidance"
            ]
    
    async def answer_policy_question(self, question: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Answer specific policy questions with citations"""
        try:
            # Find relevant documents
            relevant_docs = self._similarity_search(question, k=4)
            
            if not relevant_docs:
                return {
                    "answer": "I don't have specific policy information to answer that question. Please contact our support team for detailed assistance.",
                    "confidence": 0.1,
                    "sources": []
                }
            
            # Prepare context
            context = "\n\n".join([
                f"Source: {doc['document']['title']}\n{doc['document']['content']}"
                for doc in relevant_docs
            ])
            
            # Include conversation history if provided
            history_context = ""
            if conversation_history:
                recent_history = conversation_history[-3:]  # Last 3 exchanges
                history_context = "\n".join([
                    f"User: {msg.get('user', '')}\nAssistant: {msg.get('assistant', '')}"
                    for msg in recent_history if msg.get('user') or msg.get('assistant')
                ])

            # Prepare history text separately
            history_text = f"Recent Conversation Context:\n{history_context}\n" if history_context else ""

            # Generate comprehensive answer
            prompt = f"""
            Answer the following policy question based on the provided policy documents:

            Question: {question}

            {history_text}

            Policy Documents:
            {context}

            Please provide:
            1. A direct, accurate answer to the question
            2. Specific policy details and requirements
            3. Any important exceptions or conditions
            4. Practical guidance for compliance

            If the question cannot be fully answered from the provided policies, clearly indicate what information is available and what might require additional clarification.

            Respond in a helpful, professional tone suitable for customer service.
            """

            
            response = self.model.generate_content(prompt)
            
            # Calculate confidence based on document relevance
            avg_similarity = np.mean([doc['similarity'] for doc in relevant_docs])
            confidence = min(avg_similarity * 2, 1.0)  # Scale and cap at 1.0
            
            # Prepare sources
            sources = [
                {
                    "title": doc['document']['title'],
                    "similarity": doc['similarity'],
                    "content_preview": doc['document']['content'][:200] + "..."
                }
                for doc in relevant_docs
            ]
            
            return {
                "answer": response.text,
                "confidence": float(confidence),
                "sources": sources,
                "query": question
            }
            
        except Exception as e:
            logger.error(f"Error answering policy question: {str(e)}")
            return {
                "answer": f"I encountered an error while processing your policy question. Please try again or contact support for assistance.",
                "confidence": 0.0,
                "sources": [],
                "error": str(e)
            }
    
    def update_policy_document(self, title: str, content: str, category: str = "general"):
        """Update or add a policy document"""
        try:
            # Create filename from title
            filename = title.lower().replace(' ', '_') + '.txt'
            file_path = self.policy_dir / filename
            
            # Write document
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n{content}")
            
            # Rebuild index
            self._create_index()
            
            logger.info(f"Policy document updated: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating policy document: {str(e)}")
            return False
    
    def get_available_policies(self) -> List[Dict[str, Any]]:
        """Get list of available policy documents"""
        try:
            policies = []
            
            # Group documents by source file
            policy_groups = {}
            for doc in self.documents:
                source = doc.get('title', 'Unknown')
                if source not in policy_groups:
                    policy_groups[source] = {
                        'title': source,
                        'chunks': 0,
                        'total_content_length': 0
                    }
                
                policy_groups[source]['chunks'] += 1
                policy_groups[source]['total_content_length'] += len(doc['content'])
            
            for title, info in policy_groups.items():
                policies.append({
                    'title': title,
                    'chunks': info['chunks'],
                    'content_length': info['total_content_length'],
                    'last_updated': None  # Could be enhanced with file modification time
                })
            
            return policies
            
        except Exception as e:
            logger.error(f"Error getting available policies: {str(e)}")
            return []
    
    def search_policies(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search policies and return ranked results"""
        try:
            results = self._similarity_search(query, k=limit)
            
            return [
                {
                    'title': result['document']['title'],
                    'content': result['document']['content'],
                    'similarity': result['similarity'],
                    'source': result['document'].get('source', ''),
                    'chunk_index': result['document'].get('chunk_index', 0)
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Error searching policies: {str(e)}")
            return []