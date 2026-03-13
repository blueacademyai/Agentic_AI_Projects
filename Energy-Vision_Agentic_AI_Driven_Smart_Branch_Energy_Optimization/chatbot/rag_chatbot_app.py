import streamlit as st
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai
import uuid
from datetime import datetime
import io
import PyPDF2
import docx
from typing import List, Tuple, Dict, Any
import time
import os
st.set_page_config(
        page_title="EnerVision Chatbot",
        page_icon="🌱",
        layout="wide"
    )
# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system environment variables

# Try to import Langfuse with fallback
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    st.warning("Langfuse not available. Install with: pip install langfuse")

# Initialize Langfuse
@st.cache_resource
def init_langfuse():
    if LANGFUSE_AVAILABLE:
        try:
            langfuse_client = Langfuse(
                secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            )
            
            # Test the connection - use the correct method based on SDK version
            try:
                # Try newer SDK method first
                test_trace = langfuse_client.trace(name="connection_test")
                print(f"Langfuse connection successful (v2+ API). Test trace ID: {test_trace.id}")
            except AttributeError:
                # Fall back to older SDK method
                try:
                    test_trace = langfuse_client.create_trace(name="connection_test")
                    print(f"Langfuse connection successful (v1 API). Test trace ID: {test_trace.id}")
                except Exception as e:
                    print(f"Both trace methods failed: {e}")
                    return None
            
            return langfuse_client
        except Exception as e:
            st.warning(f"Langfuse initialization failed: {e}")
            print(f"Langfuse error details: {e}")
            return None
    return None

# Initialize models
@st.cache_resource
def load_models():
    # Load sentence transformer model
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return embedding_model

def initialize_gemini(api_key):
    """Initialize Gemini model with provided API key"""
    if not api_key:
        return None, "No API key provided"
    
    try:
        genai.configure(api_key=api_key)
        
        # First, try to list available models
        try:
            available_models = []
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    available_models.append(model.name)
            
            if available_models:
                print(f"Available models: {available_models}")
        except Exception as list_error:
            print(f"Could not list models: {list_error}")
            available_models = []
        
        # Try different model names (without 'models/' prefix first, then with)
        model_names = [
            'gemini-1.5-pro-latest',
            'gemini-1.5-pro',
            'gemini-1.5-flash-latest', 
            'gemini-1.5-flash',
            'gemini-pro',
            'gemini-1.0-pro',
            'models/gemini-1.5-pro-latest',
            'models/gemini-1.5-pro',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-pro',
            'models/gemini-1.0-pro'
        ]
        
        # If we found available models, try those first
        if available_models:
            # Remove 'models/' prefix for testing
            test_models = [m.replace('models/', '') for m in available_models]
            model_names = test_models + model_names
        
        last_error = None
        for model_name in model_names:
            try:
                print(f"Trying model: {model_name}")
                gemini_model = genai.GenerativeModel(model_name)
                # Test the API key with a simple request
                test_response = gemini_model.generate_content("Hello")
                return gemini_model, f"API key is valid! Using model: {model_name}"
            except Exception as model_error:
                last_error = str(model_error)
                print(f"Failed with {model_name}: {model_error}")
                continue
        
        # If all failed, provide detailed error message
        error_msg = f"No available Gemini models found.\n"
        if available_models:
            error_msg += f"Detected models: {', '.join(available_models[:3])}\n"
        error_msg += f"Last error: {last_error}"
        
        return None, error_msg
    except Exception as e:
        return None, f"API key error: {str(e)}"

class DocumentProcessor:
    def __init__(self):
        pass
    
    def extract_text_from_pdf(self, file) -> str:
        """Extract text from PDF file"""
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    def extract_text_from_docx(self, file) -> str:
        """Extract text from DOCX file"""
        doc = docx.Document(file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    
    def extract_text_from_txt(self, file) -> str:
        """Extract text from TXT file"""
        return str(file.read(), "utf-8")
    
    def process_document(self, uploaded_file) -> str:
        """Process uploaded document and extract text"""
        if uploaded_file.type == "application/pdf":
            return self.extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self.extract_text_from_docx(uploaded_file)
        elif uploaded_file.type == "text/plain":
            return self.extract_text_from_txt(uploaded_file)
        else:
            st.error("Unsupported file type!")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into chunks with overlap"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
        
        return chunks

class RAGChatbot:
    def __init__(self, embedding_model, gemini_model, langfuse_client):
        self.embedding_model = embedding_model
        self.gemini_model = gemini_model
        self.langfuse = langfuse_client
        self.doc_processor = DocumentProcessor()
        self.document_chunks = []
        self.chunk_embeddings = None
        self.current_trace = None
        self.project_id = None
        
    def set_project_id(self, project_id: str):
        """Set the Langfuse project ID"""
        self.project_id = project_id
        
    def create_trace(self, name: str, user_id: str = None):
        """Create a new Langfuse trace with proper error handling for different SDK versions"""
        if not self.langfuse:
            print("Langfuse client not available")
            return None
            
        try:
            # Try the newer SDK method first
            if hasattr(self.langfuse, 'trace'):
                trace_data = {
                    "name": name,
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "project": self.project_id or "default",
                    }
                }
                
                if user_id:
                    trace_data["user_id"] = user_id
                    trace_data["metadata"]["user_id"] = user_id
                    
                trace = self.langfuse.trace(**trace_data)
            
            # Fall back to older SDK method
            elif hasattr(self.langfuse, 'create_trace'):
                trace_data = {
                    "name": name,
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "project": self.project_id or "default",
                    }
                }
                
                if user_id:
                    trace_data["user_id"] = user_id
                    trace_data["metadata"]["user_id"] = user_id
                    
                trace = self.langfuse.create_trace(**trace_data)
            
            else:
                print("No supported trace creation method found")
                return None
                
            self.current_trace = trace
            print(f"Created trace with ID: {trace.id}")
            return trace
            
        except Exception as e:
            print(f"Failed to create trace: {e}")
            print(f"Available Langfuse methods: {[method for method in dir(self.langfuse) if not method.startswith('_')]}")
            import traceback
            traceback.print_exc()
            return None
        
    def log_span(self, name: str, input_data: dict = None, output_data: dict = None, metadata: dict = None):
        """Log a span to the current trace with SDK version compatibility"""
        if not self.current_trace:
            print("No current trace available for span logging")
            return None
            
        try:
            span_data = {"name": name}
            
            if input_data:
                span_data["input"] = input_data
            if output_data:
                span_data["output"] = output_data  
            if metadata:
                span_data["metadata"] = metadata
            
            # Try newer SDK method
            if hasattr(self.current_trace, 'span'):
                span = self.current_trace.span(**span_data)
            # Fall back to older SDK method
            elif hasattr(self.current_trace, 'create_span'):
                span = self.current_trace.create_span(**span_data)
            else:
                print("No supported span creation method found")
                return None
                
            print(f"Created span: {name}")
            return span
        except Exception as e:
            print(f"Failed to log span {name}: {e}")
            return None
        
    def log_generation(self, name: str, input_data: dict, output_data: dict, metadata: dict = None, model: str = None):
        """Log a generation to the current trace with SDK version compatibility"""
        if not self.current_trace:
            print("No current trace available for generation logging")
            return None
            
        try:
            generation_data = {
                "name": name,
                "input": input_data,
                "output": output_data,
            }
            
            if metadata:
                generation_data["metadata"] = metadata
            if model:
                generation_data["model"] = model
            
            # Try newer SDK method
            if hasattr(self.current_trace, 'generation'):
                generation = self.current_trace.generation(**generation_data)
            # Fall back to older SDK method
            elif hasattr(self.current_trace, 'create_generation'):
                generation = self.current_trace.create_generation(**generation_data)
            else:
                print("No supported generation creation method found")
                return None
                
            print(f"Created generation: {name}")
            return generation
        except Exception as e:
            print(f"Failed to log generation {name}: {e}")
            return None
        
    def get_trace_url(self):
        """Get the Langfuse trace URL with improved error handling"""
        if not self.current_trace:
            print("No current trace available")
            return None
            
        if not self.langfuse:
            print("Langfuse client not available")
            return None
            
        if not self.project_id:
            print("Project ID not set")
            return None
            
        try:
            # Ensure the trace is flushed first
            self.langfuse.flush()
            
            # Wait a bit for processing
            time.sleep(0.5)
            
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            host = host.rstrip('/')
            trace_url = f"{host}/project/{self.project_id}/traces/{self.current_trace.id}"
            print(f"Generated trace URL: {trace_url}")
            return trace_url
        except Exception as e:
            print(f"Failed to generate trace URL: {e}")
            return None
        
    def embed_documents(self, chunks: List[str]) -> np.ndarray:
        """Create embeddings for document chunks"""
        start_time = time.time()
        
        # Log embedding process - simplified approach
        if self.langfuse and self.current_trace:
            try:
                span = self.current_trace.span(
                    name="document_embedding",
                    input={"num_chunks": len(chunks)},
                    metadata={"model": "all-MiniLM-L6-v2", "start_time": start_time}
                )
            except Exception as e:
                print(f"Failed to create embedding span: {e}")
                span = None
        else:
            span = None
        
        embeddings = self.embedding_model.encode(chunks)
        processing_time = time.time() - start_time
        
        # Update span with output if available
        if span:
            try:
                span.update(
                    output={"embedding_shape": list(embeddings.shape), "processing_time": processing_time}
                )
            except Exception as e:
                print(f"Failed to update embedding span: {e}")
        
        return embeddings
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """Get embedding for user query"""
        start_time = time.time()
        
        if self.langfuse and self.current_trace:
            try:
                span = self.current_trace.span(
                    name="query_embedding",
                    input={"query": query},
                    metadata={"model": "all-MiniLM-L6-v2"}
                )
            except Exception as e:
                print(f"Failed to create query embedding span: {e}")
                span = None
        else:
            span = None
        
        embedding = self.embedding_model.encode([query])
        processing_time = time.time() - start_time
        
        if span:
            try:
                span.update(
                    output={"embedding_shape": list(embedding.shape), "processing_time": processing_time}
                )
            except Exception as e:
                print(f"Failed to update query embedding span: {e}")
        
        return embedding
    
    def calculate_similarity_scores(self, query_embedding: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between query and document chunks"""
        if self.chunk_embeddings is None:
            return np.array([])
        
        start_time = time.time()
        if self.langfuse and self.current_trace:
            try:
                span = self.current_trace.span(
                    name="similarity_calculation",
                    input={"query_embedding_shape": list(query_embedding.shape)},
                    metadata={"num_chunks": len(self.document_chunks)}
                )
            except Exception as e:
                print(f"Failed to create similarity span: {e}")
                span = None
        else:
            span = None
        
        similarities = cosine_similarity(query_embedding, self.chunk_embeddings)[0]
        processing_time = time.time() - start_time
        
        if span:
            try:
                span.update(
                    output={
                        "max_similarity": float(np.max(similarities)),
                        "mean_similarity": float(np.mean(similarities)),
                        "processing_time": processing_time
                    }
                )
            except Exception as e:
                print(f"Failed to update similarity span: {e}")
        
        return similarities
    
    def get_top_k_chunks(self, similarities: np.ndarray, k: int = 3) -> List[Tuple[str, float]]:
        """Get top k most similar chunks"""
        top_indices = np.argsort(similarities)[-k:][::-1]
        return [(self.document_chunks[i], similarities[i]) for i in top_indices]
    
    def generate_rag_response(self, query: str, top_chunks: List[Tuple[str, float]], response_mode: str = "combined") -> str:
        """Generate response using RAG approach"""
        if not self.gemini_model:
            return "Gemini API is not configured. Please set up your GEMINI_API_KEY."
        
        start_time = time.time()
        
        if response_mode == "individual":
            # Generate individual responses for each chunk
            responses = []
            for i, (chunk, score) in enumerate(top_chunks):
                prompt = f"""
                Based on the following context from the policy document, please answer the user's question.
                
                Context:
                {chunk}
                
                Question: {query}
                
                Please provide a focused answer based on this specific context. If this context doesn't contain relevant information, say so briefly.
                """
                
                try:
                    response = self.gemini_model.generate_content(prompt)
                    answer = response.text
                    responses.append(f"**Response {i+1}** (Similarity: {score:.3f}):\n{answer}")
                except Exception as e:
                    responses.append(f"**Response {i+1}** (Similarity: {score:.3f}):\nError: {str(e)}")
            
            final_response = "\n\n---\n\n".join(responses)
        
        # Log generation - simplified approach
        if self.langfuse and self.current_trace:
            try:
                generation = self.current_trace.generation(
                    name="rag_generation",
                    input={
                        "query": query, 
                        "num_chunks": len(top_chunks), 
                        "response_mode": response_mode,
                        "prompt_length": len(prompt) if response_mode == "combined" else "multiple_prompts"
                    },
                    output={
                        "response": final_response[:500] + "..." if len(final_response) > 500 else final_response,
                        "response_length": len(final_response),
                        "processing_time": processing_time
                    },
                    metadata={"approach": "RAG"},
                    model="gemini-1.5-flash"
                )
                print(f"Created RAG generation log")
            except Exception as e:
                print(f"Failed to log RAG generation: {e}")
        
        return final_response
    
    def generate_gemini_response(self, query: str) -> str:
        """Generate response using Gemini directly"""
        if not self.gemini_model:
            return "Gemini API is not configured. Please set up your GEMINI_API_KEY."
        
        start_time = time.time()
        prompt = f"""
        Please answer the following question using your general knowledge:
        
        Question: {query}
        
        Please provide a helpful and comprehensive answer.
        """
        
        try:
            response = self.gemini_model.generate_content(prompt)
            answer = response.text
            processing_time = time.time() - start_time
            
            # Log generation - simplified approach  
            if self.langfuse and self.current_trace:
                try:
                    generation = self.current_trace.generation(
                        name="gemini_direct_generation",
                        input={"query": query, "prompt": prompt},
                        output={
                            "response": answer[:500] + "..." if len(answer) > 500 else answer,
                            "response_length": len(answer),
                            "processing_time": processing_time
                        },
                        metadata={"approach": "Direct"},
                        model="gemini-1.5-flash"
                    )
                    print(f"Created Gemini direct generation log")
                except Exception as e:
                    print(f"Failed to log Gemini generation: {e}")
            
            return answer
        except Exception as e:
            error_msg = f"Error generating Gemini response: {str(e)}"
            
            # Log error
            if self.langfuse and self.current_trace:
                try:
                    generation = self.current_trace.generation(
                        name="gemini_direct_generation_error",
                        input={"query": query},
                        output={"error": error_msg},
                        metadata={"approach": "Direct"},
                        model="gemini-1.5-flash"
                    )
                except Exception as log_e:
                    print(f"Failed to log Gemini error: {log_e}")
                    
            return error_msg
    
    def process_query(self, query: str, similarity_threshold: float = 0.5, top_k: int = 3, response_mode: str = "combined", user_id: str = None) -> Dict[str, Any]:
        """Process user query and decide response strategy"""
        # Create new trace for this query
        trace_name = f"rag_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        trace = self.create_trace(trace_name, user_id)
        trace_id = trace.id if trace else str(uuid.uuid4())
        
        # Log query processing start - simplified approach
        if self.langfuse and self.current_trace:
            try:
                span = self.current_trace.span(
                    name="query_processing",
                    input={
                        "query": query,
                        "threshold": similarity_threshold,
                        "top_k": top_k,
                        "response_mode": response_mode
                    },
                    metadata={"trace_id": trace_id}
                )
                print(f"Created query processing span")
            except Exception as e:
                print(f"Failed to log query processing start: {e}")
        
        if not self.document_chunks:
            response = "Please upload a policy document first."
            result = {
                "response": response,
                "similarity_score": 0.0,
                "approach": "No Document",
                "top_chunks": [],
                "trace_id": trace_id,
                "trace_url": None
            }
            
            # Log completion
            if self.langfuse and self.current_trace:
                try:
                    span = self.current_trace.span(
                        name="query_processing_complete",
                        input={"query": query},
                        output=result,
                        metadata={"trace_id": trace_id}
                    )
                except Exception as e:
                    print(f"Failed to log query processing complete: {e}")
            
            # Flush and get URL
            if self.langfuse:
                self.langfuse.flush()
                trace_url = self.get_trace_url()
                result["trace_url"] = trace_url
            
            return result
        
        # Get query embedding and calculate similarities
        query_embedding = self.get_query_embedding(query)
        similarities = self.calculate_similarity_scores(query_embedding)
        max_similarity = np.max(similarities) if len(similarities) > 0 else 0.0
        
        # Decide approach based on similarity threshold
        if max_similarity >= similarity_threshold:
            # Use RAG approach
            top_chunks = self.get_top_k_chunks(similarities, top_k)
            response = self.generate_rag_response(query, top_chunks, response_mode)
            approach = f"RAG ({response_mode})"
        else:
            # Use Gemini directly
            response = self.generate_gemini_response(query)
            top_chunks = []
            approach = "Gemini Direct"
        
        result = {
            "response": response,
            "similarity_score": float(max_similarity),
            "approach": approach,
            "top_chunks": top_chunks,
            "trace_id": trace_id,
            "trace_url": None
        }
        
        # Log final result
        if self.langfuse and self.current_trace:
            try:
                span = self.current_trace.span(
                    name="query_processing_complete",
                    input={"query": query},
                    output={
                        "approach": approach,
                        "similarity_score": float(max_similarity),
                        "response_length": len(response)
                    },
                    metadata={"trace_id": trace_id}
                )
                print(f"Created query processing complete span")
            except Exception as e:
                print(f"Failed to log query processing complete: {e}")
        
        # Ensure trace is flushed and get URL
        if self.langfuse:
            try:
                self.langfuse.flush()
                # Wait a moment for processing
                time.sleep(1)
                trace_url = self.get_trace_url()
                result["trace_url"] = trace_url
                print(f"Final trace URL: {trace_url}")
            except Exception as e:
                print(f"Error flushing or getting trace URL: {e}")
        
        return result

def main():
    
    
    st.title("⚡ EnerVision")

    # Initialize components
    langfuse_client = init_langfuse()
    embedding_model = load_models()
    
    # Initialize session state
    if 'chatbot' not in st.session_state:
        st.session_state.chatbot = RAGChatbot(embedding_model, None, langfuse_client)
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'gemini_api_key' not in st.session_state:
        st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if 'gemini_status' not in st.session_state:
        st.session_state.gemini_status = ""
    if 'trace_links' not in st.session_state:
        st.session_state.trace_links = []
    if 'langfuse_project_id' not in st.session_state:
        st.session_state.langfuse_project_id = ""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    # Sidebar configuration
    with st.sidebar:
        st.header("🔑 API Configuration")
        
        # Gemini API Key Input
        api_key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.gemini_api_key,
            type="password",
            help="Get your API key from Google AI Studio"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Test API Key", type="primary"):
                if api_key_input:
                    st.session_state.gemini_api_key = api_key_input
                    with st.spinner("Testing API key..."):
                        gemini_model, status = initialize_gemini(api_key_input)
                        st.session_state.gemini_status = status
                        st.session_state.chatbot.gemini_model = gemini_model
                else:
                    st.session_state.gemini_status = "Please enter an API key"
        
        with col2:
            if st.button("Get API Key"):
                st.markdown("[🔗 Get API Key](https://makersuite.google.com/app/apikey)")
        
        # Display API status
        if st.session_state.gemini_status:
            if "valid" in st.session_state.gemini_status:
                st.success(st.session_state.gemini_status)
            else:
                st.error(st.session_state.gemini_status)
        
        st.divider()
        
        st.header("📄 Document Upload")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Upload Policy Document",
            type=['pdf', 'docx', 'txt'],
            help="Upload a policy document to enable RAG functionality"
        )
        
        st.divider()
        
        st.header("⚙️ Parameters")
        
        # Parameters
        similarity_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.05,
            help="Threshold for determining whether to use RAG or Gemini direct"
        )
        
        top_k = st.slider(
            "Top K Chunks",
            min_value=1,
            max_value=10,
            value=3,
            help="Number of top similar chunks to use for RAG"
        )
        
        # Response mode selection
        response_mode = st.selectbox(
            "Response Mode",
            options=["individual"],
            index=0,
            help="Combined: Single response using all chunks. Individual: Separate response for each chunk."
        )
        
        st.divider()
        
        st.header("📊 Setup Status")
        
        # Show current configuration status
        col_status1, col_status2 = st.columns(2)
        with col_status1:
            if st.session_state.chatbot.gemini_model:
                st.success("Gemini")
            else:
                st.error("Gemini")
                
        with col_status2:
            if langfuse_client:
                st.success("Langfuse")
            else:
                st.warning("Langfuse")
        
        # Langfuse configuration
        with st.expander("🔍 Langfuse Configuration"):
            st.markdown("Configure Langfuse for trace links:")
            
            langfuse_secret = st.text_input("Langfuse Secret Key", type="password", key="lf_secret")
            langfuse_public = st.text_input("Langfuse Public Key", key="lf_public")
            langfuse_host = st.text_input("Langfuse Host", value="https://cloud.langfuse.com", key="lf_host")
            project_id_input = st.text_input(
                "Project ID", 
                value=st.session_state.langfuse_project_id,
                help="Found in your Langfuse project URL: /project/YOUR_PROJECT_ID/traces", 
                key="lf_project"
            )
            
            if st.button("Update Langfuse Config"):
                if langfuse_secret and langfuse_public:
                    # Update environment variables
                    os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret
                    os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public
                    os.environ["LANGFUSE_HOST"] = langfuse_host
                    
                    try:
                        # Store project ID
                        st.session_state.langfuse_project_id = project_id_input
                        
                        # Clear cache and reinitialize
                        init_langfuse.clear()
                        new_langfuse = init_langfuse()
                        if new_langfuse:
                            st.session_state.chatbot.langfuse = new_langfuse
                            st.session_state.chatbot.set_project_id(project_id_input)
                            st.success("Langfuse updated!")
                            # Test the connection
                            try:
                                test_trace = new_langfuse.trace(name="config_test")
                                st.success(f"Langfuse connection verified! Test trace: {test_trace.id[:8]}...")
                                new_langfuse.flush()
                            except Exception as e:
                                st.error(f"Langfuse connection test failed: {e}")
                        else:
                            st.error("Failed to initialize Langfuse client")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Langfuse error: {e}")
                        st.session_state.langfuse_project_id = project_id_input
                else:
                    st.warning("Please fill in Secret and Public keys")
            
            # Show current project ID and user ID
            if st.session_state.langfuse_project_id:
                st.info(f"Current Project ID: {st.session_state.langfuse_project_id}")
            st.info(f"User ID: {st.session_state.user_id}")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()
    
    # Set project ID if configured
    if st.session_state.langfuse_project_id:
        st.session_state.chatbot.set_project_id(st.session_state.langfuse_project_id)
    
    # Process uploaded document
    if uploaded_file is not None:
        if 'current_file' not in st.session_state or st.session_state.current_file != uploaded_file.name:
            st.session_state.current_file = uploaded_file.name
            
            with st.spinner("Processing document..."):
                # Extract text
                text = st.session_state.chatbot.doc_processor.process_document(uploaded_file)
                
                if text:
                    # Chunk text
                    chunks = st.session_state.chatbot.doc_processor.chunk_text(text)
                    st.session_state.chatbot.document_chunks = chunks
                    
                    # Create embeddings
                    st.session_state.chatbot.chunk_embeddings = st.session_state.chatbot.embed_documents(chunks)
                    
                    st.success(f"Document processed! Created {len(chunks)} chunks.")
                else:
                    st.error("Failed to extract text from document.")
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        
        # Chat input using form for better UX
        with st.form("chat_form", clear_on_submit=True):
            query = st.text_input(
                "Ask a question about the policy document:", 
                placeholder="e.g., What is the refund policy?",
                disabled=not st.session_state.chatbot.gemini_model
            )
            submit_button = st.form_submit_button(
                "Send", 
                disabled=not st.session_state.chatbot.gemini_model,
                type="primary"
            )
        
        # Show warning if Gemini is not configured
        if not st.session_state.chatbot.gemini_model:
            st.warning("Please configure your Gemini API key in the sidebar to start chatting!")
        
        if submit_button and query and st.session_state.chatbot.gemini_model:
            with st.spinner("Processing query..."):
                # Process query with Langfuse tracing
                result = st.session_state.chatbot.process_query(
                    query=query,
                    similarity_threshold=similarity_threshold,
                    top_k=top_k,
                    response_mode=response_mode,
                    user_id=st.session_state.user_id
                )
                
                # Add to chat history
                st.session_state.chat_history.append({
                    "query": query,
                    "response": result["response"],
                    "similarity_score": result["similarity_score"],
                    "approach": result["approach"],
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "trace_id": result.get("trace_id", str(uuid.uuid4())),
                    "trace_url": result.get("trace_url", None),
                    "top_chunks": result.get("top_chunks", []),
                    "response_mode": response_mode
                })
                
                # Rerun to refresh the interface
                st.rerun()
        
        # Display chat history
        if st.session_state.chat_history:
            st.subheader("Chat History")
            
            for i, chat in enumerate(reversed(st.session_state.chat_history)):
                with st.expander(f"[{chat['timestamp']}] Query: {chat['query'][:50]}..."):
                    st.markdown(f"**Query:** {chat['query']}")
                    st.markdown(f"**Response:** {chat['response']}")

                    col_score, col_approach = st.columns(2)
                    with col_score:
                        st.metric("Similarity Score", f"{chat['similarity_score']:.3f}")
                    with col_approach:
                        st.metric("Approach Used", chat['approach'])

                    # Trace link with better handling
                    trace_col1, trace_col2 = st.columns([2, 1])
                    with trace_col1:
                        if chat.get('trace_url'):
                            st.markdown(f"[🔗 View Langfuse Trace]({chat['trace_url']})")
                        else:
                            if langfuse_client and st.session_state.langfuse_project_id and chat.get('trace_id'):
                                manual_url = f"https://cloud.langfuse.com/project/{st.session_state.langfuse_project_id}/traces/{chat['trace_id']}"
                                st.markdown(f"[🔗 Manual Trace Link]({manual_url})")
                            elif not langfuse_client:
                                st.markdown("🔗 Langfuse not configured")
                            elif not st.session_state.langfuse_project_id:
                                st.markdown("🔗 Configure Project ID for trace links")
                            else:
                                st.markdown("🔗 Trace ID not available")

                    with trace_col2:
                        if chat.get('trace_id'):
                            st.code(f"ID: {chat['trace_id'][:8]}...", language=None)

    
    with col2:
        
        
        
        # Document status
        
            
        
        # Trace monitoring section
        
        
        # Performance indicators
        if st.session_state.chat_history:
            st.subheader("🎯 Performance Indicators")
            recent_similarities = [chat['similarity_score'] for chat in st.session_state.chat_history[-5:]]
            
            if recent_similarities:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(8, 3))
                ax.plot(recent_similarities, marker='o', linewidth=2, markersize=6)
                ax.axhline(y=similarity_threshold, color='r', linestyle='--', alpha=0.7, label='Threshold')
                ax.set_ylabel('Similarity Score')
                ax.set_xlabel('Recent Queries')
                ax.set_title('Recent Query Similarity Scores')
                ax.legend()
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                



if __name__ == "__main__":
    main()