
import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
from langfuse import Langfuse
import time
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import PyPDF2
import docx
from typing import List, Dict
import hashlib

# Page config
st.set_page_config(page_title="ATM Network Monitoring System", page_icon="🏧", layout="wide")

# Langfuse Configuration
LANGFUSE_SECRET_KEY = "sk-lf-9c581f87-42b7-4d0e-9480-40581d9c1554"
LANGFUSE_PUBLIC_KEY = "pk-lf-aaabf4e4-7b96-49e1-a2fa-dd7035c81745"
LANGFUSE_HOST = "https://us.cloud.langfuse.com"

# Gemini API Key (add your key here)
GEMINI_API_KEY = "AIzaSyAkFycAp3L9xMyZ3_dbmL4LrqTOX-FdW_8"  # Replace with your actual key

# ===========================
# RAG Setup
# ===========================
@st.cache_resource
def initialize_rag_components():
    """Initialize RAG components"""
    try:
        # Initialize embedding model
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Initialize Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")

        return embedding_model, gemini_model
    except Exception as e:
        st.error(f"Failed to initialize RAG components: {e}")
        return None, None

def extract_text_from_file(uploaded_file):
    """Extract text from uploaded files"""
    text = ""
    try:
        if uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(uploaded_file)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

        elif uploaded_file.type == "text/csv" or uploaded_file.name.endswith('.csv'):
            # Read CSV and convert to readable text format
            csv_content = pd.read_csv(uploaded_file)
            text = f"CSV File: {uploaded_file.name}\n"
            text += f"Columns: {', '.join(csv_content.columns)}\n"
            text += f"Number of rows: {len(csv_content)}\n\n"
            text += "Data Summary:\n"
            text += csv_content.describe(include='all').to_string() + "\n\n"
            text += "Sample Data (first 10 rows):\n"
            text += csv_content.head(10).to_string() + "\n\n"

            # Convert each row to a readable format
            text += "Detailed Data:\n"
            for idx, row in csv_content.iterrows():
                if idx < 100:  # Limit to first 100 rows to avoid token limits
                    row_text = f"Row {idx + 1}: "
                    row_text += ", ".join([f"{col}: {val}" for col, val in row.items()])
                    text += row_text + "\n"
                else:
                    text += f"... and {len(csv_content) - 100} more rows\n"
                    break

        elif uploaded_file.type == "text/plain":
            text = str(uploaded_file.read(), "utf-8")

        else:
            st.error(f"Unsupported file type: {uploaded_file.type}")
            return None

    except Exception as e:
        st.error(f"Error extracting text from {uploaded_file.name}: {e}")
        return None

    return text.strip()
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into chunks with overlap"""
    if not text:
        return []

    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())

    return chunks

def build_vector_store(documents: List[Dict], embedding_model):
    """Build FAISS vector store from documents"""
    if not documents:
        return None, []

    all_chunks = []
    chunk_metadata = []

    for doc in documents:
        chunks = chunk_text(doc['content'])
        for chunk in chunks:
            all_chunks.append(chunk)
            chunk_metadata.append({
                'filename': doc['filename'],
                'chunk_text': chunk
            })

    if not all_chunks:
        return None, []

    # Create embeddings
    embeddings = embedding_model.encode(all_chunks)

    # Build FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))

    return index, chunk_metadata

def retrieve_relevant_chunks(query: str, index, chunk_metadata: List[Dict], embedding_model, k: int = 3):
    """Retrieve relevant chunks for a query"""
    if not index or not chunk_metadata:
        return []

    # Encode query
    query_embedding = embedding_model.encode([query])

    # Search
    scores, indices = index.search(query_embedding.astype('float32'), k)

    relevant_chunks = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunk_metadata):
            chunk_info = chunk_metadata[idx].copy()
            chunk_info['score'] = float(scores[0][i])
            relevant_chunks.append(chunk_info)

    return relevant_chunks

def generate_rag_response(query: str, relevant_chunks: List[Dict], gemini_model) -> str:
    """Generate response using RAG"""
    if not relevant_chunks:
        return None

    # Prepare context from relevant chunks
    context = "\n\n".join([f"From {chunk['filename']}:\n{chunk['chunk_text']}" for chunk in relevant_chunks])

    prompt = f"""You are an ATM Network Monitoring Assistant. Use the following context from uploaded documents to answer the user's question. If the context doesn't contain relevant information, say so.

Context from uploaded documents:
{context}

User Question: {query}

Instructions:
1. Answer based primarily on the provided context
2. Be specific and cite which document the information comes from
3. If the context doesn't contain relevant information, clearly state that
4. Maintain the helpful tone of an ATM monitoring assistant

Answer:"""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating RAG response: {str(e)}"

# Initialize Langfuse client
@st.cache_resource
def initialize_langfuse():
    try:
        langfuse = Langfuse(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST
        )
        return langfuse
    except Exception as e:
        st.error(f"Failed to initialize Langfuse: {e}")
        return None

# Initialize session state for RAG
def initialize_rag_session_state():
    """Initialize RAG-related session state"""
    if 'documents' not in st.session_state:
        st.session_state.documents = []
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = None
    if 'chunk_metadata' not in st.session_state:
        st.session_state.chunk_metadata = []
    if 'rag_enabled' not in st.session_state:
        st.session_state.rag_enabled = False

# ===========================
# Load CSV Data
# ===========================
@st.cache_data
def load_csv_data():
    # Your actual CSV data
    csv_data = """timestamp,temperature_c,network_latency_ms,cash_level_pct,city,branch,source_mode,auto_notify,technician_number,max_findings,risk_high_threshold,risk_med_threshold,generate_plan
2025-09-01 00:00:00,37.11,297.71,78.76,Hyderabad,Secunderabad,simulated,True,+919346632848,2,0.8,0.5,False
2025-09-01 00:10:00,36.92,151.6,22.87,Kolkata,Salt Lake,manual,True,+918405249101,7,0.8,0.5,False
2025-09-01 00:20:00,40.28,243.84,37.24,Bengaluru,Electronic City,sensor,True,+918052556285,6,0.8,0.5,False
2025-09-01 00:30:00,35.7,264.23,12.05,Kolkata,Howrah,manual,False,+918048234549,2,0.8,0.5,False
2025-09-01 00:40:00,47.36,86.4,69.67,Pune,Shivajinagar,simulated,True,+917351035056,8,0.8,0.5,True
2025-09-01 00:50:00,29.8,165.37,28.56,Pune,Hinjewadi,sensor,True,+918016825982,9,0.8,0.5,True
2025-09-01 01:00:00,34.09,104.37,76.25,Delhi,Dwarka,manual,True,+919928643652,4,0.8,0.5,False
2025-09-01 01:10:00,32.11,258.3,56.11,Kolkata,Howrah,simulated,True,+919105381923,8,0.8,0.5,True
2025-09-01 01:20:00,35.91,180.98,51.9,Mumbai,Branch-02,manual,False,+917413878885,0,0.8,0.5,True
2025-09-01 01:30:00,30.99,272.93,74.62,Ahmedabad,Navrangpura,manual,True,+919735298679,7,0.8,0.5,True
2025-09-01 01:40:00,25.13,152.98,43.54,Chennai,T Nagar,sensor,True,+918672573069,6,0.8,0.5,True
2025-09-01 01:50:00,44.74,267.24,7.44,Kolkata,Park Street,simulated,False,+919216571186,6,0.8,0.5,False
2025-09-01 02:00:00,37.29,300.0,83.3,Chennai,T Nagar,manual,False,+918633974088,0,0.8,0.5,True
2025-09-01 02:10:00,25.88,84.48,54.8,Pune,Hinjewadi,manual,True,+918638851880,10,0.8,0.5,True
2025-09-01 02:20:00,40.51,295.47,57.01,Bengaluru,Electronic City,sensor,True,+919543366396,10,0.8,0.5,False
2025-09-01 02:30:00,42.96,217.67,45.86,Chennai,T Nagar,manual,True,+919228473674,1,0.8,0.5,False
2025-09-01 02:40:00,44.73,171.31,16.94,Mumbai,Branch-01,simulated,False,+919075053208,9,0.8,0.5,False
2025-09-01 02:50:00,44.46,147.27,58.84,Mumbai,Branch-01,sensor,True,+918861479095,10,0.8,0.5,True
2025-09-01 03:00:00,32.31,216.13,60.85,Ahmedabad,Satellite,manual,True,+918991258000,6,0.8,0.5,False
2025-09-01 03:10:00,39.82,147.47,53.46,Mumbai,Branch-03,simulated,True,+917588996434,4,0.8,0.5,False
2025-09-01 03:20:00,26.96,237.35,7.87,Mumbai,Branch-03,manual,False,+918731262316,3,0.8,0.5,True
2025-09-01 03:30:00,41.99,161.69,52.67,Ahmedabad,Navrangpura,simulated,False,+917832242337,2,0.8,0.5,False
2025-09-01 03:40:00,47.79,186.69,79.89,Pune,Shivajinagar,simulated,False,+919411393054,6,0.8,0.5,False
2025-09-01 03:50:00,26.73,140.65,13.13,Chennai,Velachery,sensor,True,+918778597721,0,0.8,0.5,True
2025-09-01 04:00:00,28.35,175.43,46.65,Delhi,Connaught,sensor,True,+917030055245,9,0.8,0.5,True
2025-09-01 04:10:00,25.25,203.08,23.21,Bengaluru,Whitefield,simulated,True,+917900954249,4,0.8,0.5,True
2025-09-01 04:20:00,40.1,275.76,7.46,Pune,Shivajinagar,manual,True,+917241419979,10,0.8,0.5,True
2025-09-01 04:30:00,29.67,205.93,98.41,Chennai,Adyar,sensor,True,+918823822801,1,0.8,0.5,True
2025-09-01 04:40:00,39.09,132.23,96.26,Bengaluru,Electronic City,manual,False,+919789855320,0,0.8,0.5,True
2025-09-01 04:50:00,45.76,244.21,60.88,Pune,Hinjewadi,simulated,False,+918958331712,3,0.8,0.5,True
2025-09-01 05:00:00,38.81,156.67,32.5,Bengaluru,Electronic City,manual,False,+918421819439,1,0.8,0.5,False
2025-09-01 05:10:00,47.87,275.58,82.27,Pune,Kothrud,simulated,True,+919693708815,0,0.8,0.5,False
2025-09-01 05:20:00,45.79,120.26,90.94,Chennai,Velachery,sensor,False,+918880961754,9,0.8,0.5,True
2025-09-01 05:30:00,29.9,93.78,81.57,Mumbai,Branch-01,manual,False,+918218836487,4,0.8,0.5,True
2025-09-01 05:40:00,43.71,99.09,54.67,Delhi,Connaught,sensor,True,+919955411596,10,0.8,0.5,False
2025-09-01 05:50:00,34.31,134.7,82.7,Hyderabad,Banjara Hills,sensor,False,+919694413570,7,0.8,0.5,True
2025-09-01 06:00:00,38.35,105.66,74.63,Mumbai,Branch-01,simulated,True,+917716553168,6,0.8,0.5,True
2025-09-01 06:10:00,47.68,102.27,14.21,Bengaluru,Whitefield,simulated,True,+919154301284,4,0.8,0.5,False
2025-09-01 06:20:00,38.7,239.15,62.62,Ahmedabad,Satellite,sensor,False,+919318215840,2,0.8,0.5,True
2025-09-01 06:30:00,46.39,188.04,54.42,Bengaluru,Whitefield,manual,True,+919397001676,2,0.8,0.5,True
2025-09-01 06:40:00,30.48,106.6,30.42,Ahmedabad,Navrangpura,manual,False,+918638760568,2,0.8,0.5,False
2025-09-01 06:50:00,36.74,91.67,51.44,Hyderabad,Gachibowli,manual,True,+917529221125,10,0.8,0.5,False
2025-09-01 07:00:00,27.65,161.94,59.07,Bengaluru,Whitefield,simulated,True,+918348010523,4,0.8,0.5,False
2025-09-01 07:10:00,30.06,283.12,15.84,Chennai,T Nagar,simulated,False,+917093518072,9,0.8,0.5,False
2025-09-01 07:20:00,26.93,259.25,35.65,Pune,Hinjewadi,simulated,False,+917391402882,2,0.8,0.5,True
2025-09-01 07:30:00,32.18,137.43,26.83,Chennai,T Nagar,sensor,False,+918929377001,2,0.8,0.5,True
2025-09-01 07:40:00,31.7,278.35,92.37,Pune,Hinjewadi,sensor,True,+919445718975,0,0.8,0.5,True
2025-09-01 07:50:00,34.95,130.77,37.08,Delhi,Karol Bagh,simulated,False,+919540232620,10,0.8,0.5,False
2025-09-01 08:00:00,42.61,225.82,13.71,Mumbai,Branch-02,simulated,False,+919742743648,8,0.8,0.5,True
2025-09-01 08:10:00,37.48,97.11,28.88,Kolkata,Howrah,manual,True,+918164019334,7,0.8,0.5,True"""

    # Create DataFrame from the CSV string
    df = pd.read_csv(io.StringIO(csv_data))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# Load the data
df = load_csv_data()

# ===========================
# Thresholds
# ===========================
thresholds = {
    "temp_warning": 40.0,
    "temp_critical": 45.0,
    "network_warning": 150,
    "network_critical": 250,
    "cash_warning": 20,
    "cash_critical": 10
}

# ===========================
# Helper Functions
# ===========================
def get_latest_data_by_location():
    """Get the latest record for each unique city-branch combination"""
    return df.groupby(['city', 'branch']).tail(1).reset_index(drop=True)

def extract_location_from_query(query):
    """Extract city and branch from query"""
    query_lower = query.lower()

    # Get actual data from CSV
    cities = df['city'].unique()
    branches = df['branch'].unique()

    found_city = None
    found_branch = None

    # Check for city names (exact and variations)
    city_mapping = {
        'mumbai': 'Mumbai',
        'bengaluru': 'Bengaluru', 'bangalore': 'Bengaluru',
        'hyderabad': 'Hyderabad',
        'pune': 'Pune',
        'delhi': 'Delhi',
        'chennai': 'Chennai', 'madras': 'Chennai',
        'kolkata': 'Kolkata', 'calcutta': 'Kolkata',
        'ahmedabad': 'Ahmedabad'
    }

    for key, city in city_mapping.items():
        if key in query_lower and city in cities:
            found_city = city
            break

    # Check for branch names
    branch_mapping = {
        'secunderabad': 'Secunderabad',
        'salt lake': 'Salt Lake',
        'electronic city': 'Electronic City', 'electronic': 'Electronic City',
        'howrah': 'Howrah',
        'shivajinagar': 'Shivajinagar',
        'hinjewadi': 'Hinjewadi',
        'dwarka': 'Dwarka',
        'branch-02': 'Branch-02', 'branch 02': 'Branch-02', 'branch 2': 'Branch-02',
        'navrangpura': 'Navrangpura',
        't nagar': 'T Nagar', 'tnagar': 'T Nagar',
        'park street': 'Park Street',
        'branch-01': 'Branch-01', 'branch 01': 'Branch-01', 'branch 1': 'Branch-01',
        'satellite': 'Satellite',
        'branch-03': 'Branch-03', 'branch 03': 'Branch-03', 'branch 3': 'Branch-03',
        'velachery': 'Velachery',
        'connaught': 'Connaught',
        'whitefield': 'Whitefield',
        'adyar': 'Adyar',
        'kothrud': 'Kothrud',
        'banjara hills': 'Banjara Hills', 'banjara': 'Banjara Hills',
        'gachibowli': 'Gachibowli',
        'karol bagh': 'Karol Bagh',
        'mg road': 'MG Road'
    }

    for key, branch in branch_mapping.items():
        if key in query_lower and branch in branches:
            found_branch = branch
            break

    return found_city, found_branch

def check_alerts(row):
    """Generate alert messages for a data row"""
    alerts = []
    location = f"{row['city']} {row['branch']}"

    # Temperature alerts
    if row['temperature_c'] >= thresholds['temp_critical']:
        alerts.append(f"🔥 CRITICAL: Temperature {row['temperature_c']:.1f}°C at {location}")
    elif row['temperature_c'] >= thresholds['temp_warning']:
        alerts.append(f"⚠️ WARNING: Temperature {row['temperature_c']:.1f}°C at {location}")

    # Network alerts
    if row['network_latency_ms'] >= thresholds['network_critical']:
        alerts.append(f"🌐 CRITICAL: Network {row['network_latency_ms']:.1f}ms at {location}")
    elif row['network_latency_ms'] >= thresholds['network_warning']:
        alerts.append(f"⚠️ WARNING: Network {row['network_latency_ms']:.1f}ms at {location}")

    # Cash alerts
    if row['cash_level_pct'] <= thresholds['cash_critical']:
        alerts.append(f"💸 CRITICAL: Cash {row['cash_level_pct']:.1f}% at {location}")
    elif row['cash_level_pct'] <= thresholds['cash_warning']:
        alerts.append(f"⚠️ WARNING: Cash {row['cash_level_pct']:.1f}% at {location}")

    return alerts

def get_response(user_query, langfuse):
    """Process user query and return appropriate response with Langfuse tracking"""
    start_time = time.time()

    with langfuse.start_as_current_span(name="atm-chatbot-conversation", input={"user_message": user_query}) as span:
        with langfuse.start_as_current_generation(
            name="atm-query-processor",
            model="custom-atm-agent",
            input={"prompt": user_query}
        ) as generation:
            try:
                # First, try RAG if enabled and documents are available
                rag_response = None
                if st.session_state.rag_enabled and st.session_state.vector_store is not None:
                    embedding_model, gemini_model = initialize_rag_components()
                    if embedding_model and gemini_model:
                        relevant_chunks = retrieve_relevant_chunks(
                            user_query,
                            st.session_state.vector_store,
                            st.session_state.chunk_metadata,
                            embedding_model,
                            k=3
                        )
                        if relevant_chunks:
                            rag_response = generate_rag_response(user_query, relevant_chunks, gemini_model)

                # If no RAG response or RAG didn't find relevant info, use original ATM logic
                if not rag_response or "doesn't contain relevant information" in rag_response:
                    atm_response = process_query(user_query)

                    # Combine responses if both exist
                    if rag_response and "doesn't contain relevant information" not in rag_response:
                        response = f"**From uploaded documents:**\n{rag_response}\n\n**From ATM system:**\n{atm_response}"
                    else:
                        response = atm_response
                else:
                    response = rag_response

                processing_time = time.time() - start_time

                generation.update(output=response)
                span.update_trace(output={"response": response, "processing_time": processing_time, "rag_used": bool(rag_response)})

                return response, span.trace_id
            except Exception as e:
                error_msg = f"I encountered an error: {str(e)}\n\nPlease try rephrasing your question or type 'show data' to see available locations."
                generation.update(output=error_msg)
                span.update_trace(output={"error": error_msg})
                return error_msg, span.trace_id

def process_query(query):
    """Process user query and return appropriate response"""
    query_lower = query.lower()

    # Show available data command
    if any(cmd in query_lower for cmd in ['show data', 'available data', 'list locations']):
        return show_available_locations()

    # Extract location info
    city, branch = extract_location_from_query(query)

    # Determine query type
    if any(word in query_lower for word in ['temperature', 'temp', 'hot', 'degrees']):
        return handle_temperature_query(query_lower, city, branch)
    elif any(word in query_lower for word in ['network', 'latency', 'connection', 'ms']):
        return handle_network_query(query_lower, city, branch)
    elif any(word in query_lower for word in ['cash', 'money', 'level', 'percent', '%']):
        return handle_cash_query(query_lower, city, branch)
    elif any(word in query_lower for word in ['alert', 'critical', 'warning', 'problem']):
        return handle_alert_query(query_lower, city, branch)
    elif any(word in query_lower for word in ['status', 'metrics', 'latest', 'overview']):
        return handle_status_query(city, branch)
    else:
        return handle_general_query(query_lower, city, branch)

def show_available_locations():
    """Show all available cities and branches"""
    latest_data = get_latest_data_by_location()
    locations_by_city = {}

    for _, row in latest_data.iterrows():
        city = row['city']
        branch = row['branch']
        if city not in locations_by_city:
            locations_by_city[city] = []
        locations_by_city[city].append(branch)

    response = "📋 **Available Locations:**\n\n"
    for city in sorted(locations_by_city.keys()):
        response += f"🏙️ **{city}:**\n"
        for branch in sorted(locations_by_city[city]):
            response += f"  • {branch}\n"
        response += "\n"

    return response

def handle_temperature_query(query, city, branch):
    """Handle temperature-related queries"""
    latest_data = get_latest_data_by_location()

    if city and branch:
        # Specific location
        location_data = latest_data[(latest_data['city'] == city) & (latest_data['branch'] == branch)]
        if location_data.empty:
            return f"No data found for {city} {branch}"

        row = location_data.iloc[0]
        temp = row['temperature_c']
        alerts = [alert for alert in check_alerts(row) if 'Temperature' in alert]

        response = f"🌡️ Temperature at {city} {branch}: **{temp:.1f}°C**"
        if alerts:
            response += "\n\n" + "\n".join(alerts)
        return response

    elif city:
        # All branches in a city
        city_data = latest_data[latest_data['city'] == city]
        if city_data.empty:
            return f"No data found for {city}"

        response = f"🌡️ **Temperature in {city}:**\n"
        for _, row in city_data.iterrows():
            temp = row['temperature_c']
            response += f"• {row['branch']}: {temp:.1f}°C\n"
        return response

    else:
        # System-wide temperature queries
        if 'above' in query or 'over' in query:
            # Extract threshold
            import re
            match = re.search(r'(\d+\.?\d*)', query)
            if match:
                threshold = float(match.group(1))
                high_temp = latest_data[latest_data['temperature_c'] > threshold]
                if not high_temp.empty:
                    response = f"🌡️ **Locations with temperature above {threshold}°C:**\n"
                    for _, row in high_temp.iterrows():
                        response += f"• {row['city']} {row['branch']}: {row['temperature_c']:.1f}°C\n"
                    return response

        if 'critical' in query:
            critical_temp = latest_data[latest_data['temperature_c'] >= thresholds['temp_critical']]
            if not critical_temp.empty:
                response = "🔥 **Critical Temperature Alerts:**\n"
                for _, row in critical_temp.iterrows():
                    response += f"• {row['city']} {row['branch']}: {row['temperature_c']:.1f}°C\n"
                return response
            else:
                return "✅ No critical temperature alerts"

        # Default: show high temperatures
        high_temp = latest_data[latest_data['temperature_c'] >= thresholds['temp_warning']]
        if not high_temp.empty:
            response = f"🌡️ **Locations with temperature ≥ {thresholds['temp_warning']}°C:**\n"
            for _, row in high_temp.iterrows():
                response += f"• {row['city']} {row['branch']}: {row['temperature_c']:.1f}°C\n"
            return response
        else:
            return "✅ All temperatures are normal"

def handle_network_query(query, city, branch):
    """Handle network-related queries"""
    latest_data = get_latest_data_by_location()

    if city and branch:
        location_data = latest_data[(latest_data['city'] == city) & (latest_data['branch'] == branch)]
        if location_data.empty:
            return f"No data found for {city} {branch}"

        row = location_data.iloc[0]
        latency = row['network_latency_ms']
        alerts = [alert for alert in check_alerts(row) if 'Network' in alert]

        response = f"🌐 Network latency at {city} {branch}: **{latency:.1f}ms**"
        if alerts:
            response += "\n\n" + "\n".join(alerts)
        return response

    elif city:
        city_data = latest_data[latest_data['city'] == city]
        if city_data.empty:
            return f"No data found for {city}"

        response = f"🌐 **Network latency in {city}:**\n"
        for _, row in city_data.iterrows():
            latency = row['network_latency_ms']
            response += f"• {row['branch']}: {latency:.1f}ms\n"
        return response

    else:
        if 'above' in query:
            import re
            match = re.search(r'(\d+\.?\d*)', query)
            if match:
                threshold = float(match.group(1))
                high_latency = latest_data[latest_data['network_latency_ms'] > threshold]
                if not high_latency.empty:
                    response = f"🌐 **Locations with network latency above {threshold}ms:**\n"
                    for _, row in high_latency.iterrows():
                        response += f"• {row['city']} {row['branch']}: {row['network_latency_ms']:.1f}ms\n"
                    return response

        if 'critical' in query:
            critical_network = latest_data[latest_data['network_latency_ms'] >= thresholds['network_critical']]
            if not critical_network.empty:
                response = "🌐 **Critical Network Alerts:**\n"
                for _, row in critical_network.iterrows():
                    response += f"• {row['city']} {row['branch']}: {row['network_latency_ms']:.1f}ms\n"
                return response
            else:
                return "✅ No critical network alerts"

        high_latency = latest_data[latest_data['network_latency_ms'] >= thresholds['network_warning']]
        if not high_latency.empty:
            response = f"🌐 **High network latency locations (≥ {thresholds['network_warning']}ms):**\n"
            for _, row in high_latency.iterrows():
                response += f"• {row['city']} {row['branch']}: {row['network_latency_ms']:.1f}ms\n"
            return response
        else:
            return "✅ All network latencies are normal"

def handle_cash_query(query, city, branch):
    """Handle cash-related queries"""
    latest_data = get_latest_data_by_location()

    if city and branch:
        location_data = latest_data[(latest_data['city'] == city) & (latest_data['branch'] == branch)]
        if location_data.empty:
            return f"No data found for {city} {branch}"

        row = location_data.iloc[0]
        cash = row['cash_level_pct']
        alerts = [alert for alert in check_alerts(row) if 'Cash' in alert]

        response = f"💸 Cash level at {city} {branch}: **{cash:.1f}%**"
        if alerts:
            response += "\n\n" + "\n".join(alerts)
        return response

    elif city:
        city_data = latest_data[latest_data['city'] == city]
        if city_data.empty:
            return f"No data found for {city}"

        response = f"💸 **Cash levels in {city}:**\n"
        for _, row in city_data.iterrows():
            cash = row['cash_level_pct']
            response += f"• {row['branch']}: {cash:.1f}%\n"
        return response

    else:
        if 'below' in query:
            import re
            match = re.search(r'(\d+\.?\d*)', query)
            if match:
                threshold = float(match.group(1))
                low_cash = latest_data[latest_data['cash_level_pct'] < threshold]
                if not low_cash.empty:
                    response = f"💸 **Locations with cash below {threshold}%:**\n"
                    for _, row in low_cash.iterrows():
                        response += f"• {row['city']} {row['branch']}: {row['cash_level_pct']:.1f}%\n"
                    return response
                else:
                    return f"✅ No locations found with cash below {threshold}%"

        if 'critical' in query:
            critical_cash = latest_data[latest_data['cash_level_pct'] <= thresholds['cash_critical']]
            if not critical_cash.empty:
                response = "💸 **Critical Cash Alerts:**\n"
                for _, row in critical_cash.iterrows():
                    response += f"• {row['city']} {row['branch']}: {row['cash_level_pct']:.1f}%\n"
                return response
            else:
                return "✅ No critical cash alerts"

        low_cash = latest_data[latest_data['cash_level_pct'] <= thresholds['cash_warning']]
        if not low_cash.empty:
            response = f"💸 **Low cash locations (≤ {thresholds['cash_warning']}%):**\n"
            for _, row in low_cash.iterrows():
                response += f"• {row['city']} {row['branch']}: {row['cash_level_pct']:.1f}%\n"
            return response
        else:
            return "✅ All cash levels are adequate"

def handle_alert_query(query, city, branch):
    """Handle alert queries"""
    latest_data = get_latest_data_by_location()

    if city:
        data_subset = latest_data[latest_data['city'] == city]
    else:
        data_subset = latest_data

    all_alerts = []
    for _, row in data_subset.iterrows():
        alerts = check_alerts(row)
        all_alerts.extend(alerts)

    if 'critical' in query:
        critical_alerts = [alert for alert in all_alerts if 'CRITICAL' in alert]
        if critical_alerts:
            return "🔥 **Critical Alerts:**\n" + "\n".join(critical_alerts)
        else:
            return "✅ No critical alerts found"

    if all_alerts:
        return "🚨 **All Active Alerts:**\n" + "\n".join(all_alerts)
    else:
        return "✅ No alerts - all systems normal"

def handle_status_query(city, branch):
    """Handle status/metrics queries"""
    latest_data = get_latest_data_by_location()

    if city and branch:
        location_data = latest_data[(latest_data['city'] == city) & (latest_data['branch'] == branch)]
        if location_data.empty:
            return f"No data found for {city} {branch}"

        row = location_data.iloc[0]
        alerts = check_alerts(row)

        response = f"📊 **Status for {city} {branch}:**\n\n"
        response += f"🌡️ Temperature: {row['temperature_c']:.1f}°C\n"
        response += f"🌐 Network: {row['network_latency_ms']:.1f}ms\n"
        response += f"💸 Cash: {row['cash_level_pct']:.1f}%\n"

        if alerts:
            response += "\n🚨 **Alerts:**\n" + "\n".join(alerts)
        else:
            response += "\n✅ **All systems normal**"

        return response

    elif city:
        city_data = latest_data[latest_data['city'] == city]
        if city_data.empty:
            return f"No data found for {city}"

        response = f"📊 **Status for all {city} branches:**\n\n"
        for _, row in city_data.iterrows():
            alerts = check_alerts(row)
            status_icon = "🔴" if any("CRITICAL" in alert for alert in alerts) else "🟡" if alerts else "🟢"
            response += f"{status_icon} **{row['branch']}:** T:{row['temperature_c']:.1f}°C, N:{row['network_latency_ms']:.1f}ms, C:{row['cash_level_pct']:.1f}%\n"

        return response

    else:
        # System overview
        total_locations = len(latest_data)
        all_alerts = []
        for _, row in latest_data.iterrows():
            alerts = check_alerts(row)
            all_alerts.extend(alerts)

        critical_count = len([alert for alert in all_alerts if 'CRITICAL' in alert])
        warning_count = len([alert for alert in all_alerts if 'WARNING' in alert])

        response = "📊 **System Overview:**\n\n"
        response += f"🏢 Total Locations: {total_locations}\n"
        response += f"🔥 Critical Alerts: {critical_count}\n"
        response += f"⚠️ Warnings: {warning_count}\n\n"

        if all_alerts:
            response += "🚨 **Recent Alerts:**\n" + "\n".join(all_alerts[:10])
        else:
            response += "✅ **All systems normal**"

        return response

def handle_general_query(query, city, branch):
    """Handle general queries or provide status"""
    if city or branch:
        return handle_status_query(city, branch)
    else:
        return handle_status_query(None, None)

# ===========================
# Streamlit Interface
# ===========================
st.title("🏧 ATM Network Monitoring System")
st.markdown("*Monitor ATM performance across India - Real-time temperature, network, and cash level tracking*")

# Initialize RAG session state
initialize_rag_session_state()

# Initialize components
try:
    langfuse = initialize_langfuse()
    embedding_model, gemini_model = initialize_rag_components()

    if langfuse:
        st.success("✅ Connected to Langfuse for tracking")
        langfuse_url = "https://us.cloud.langfuse.com/project/cmfl7c9bc02tpad079bvnyyzf/traces"
        st.markdown(f"📊 [View Langfuse Traces]({langfuse_url})")
    else:
        st.warning("⚠️ Langfuse tracking disabled")

    if embedding_model and gemini_model:
        st.success("✅ RAG components initialized")
    else:
        st.warning("⚠️ RAG components not available - document search disabled")

except Exception as e:
    st.error(f"❌ Initialization failed: {e}")
    langfuse = None
    embedding_model = None
    gemini_model = None

# Document Upload Section
st.sidebar.header("📄 Document Upload")
uploaded_files = st.sidebar.file_uploader(
    "Upload documents for RAG",
    type=['pdf', 'docx', 'txt', 'csv'],
    accept_multiple_files=True,
    help="Upload PDF, Word, text, or CSV files to enable document-based responses"
)

if uploaded_files:
    if st.sidebar.button("Process Documents"):
        with st.spinner("Processing documents..."):
            documents = []
            for file in uploaded_files:
                text = extract_text_from_file(file)
                if text:
                    documents.append({
                        'filename': file.name,
                        'content': text
                    })

            if documents and embedding_model:
                # Build vector store
                vector_store, chunk_metadata = build_vector_store(documents, embedding_model)

                if vector_store:
                    st.session_state.documents = documents
                    st.session_state.vector_store = vector_store
                    st.session_state.chunk_metadata = chunk_metadata
                    st.session_state.rag_enabled = True
                    st.sidebar.success(f"✅ Processed {len(documents)} documents with {len(chunk_metadata)} chunks")
                else:
                    st.sidebar.error("❌ Failed to build vector store")
            else:
                st.sidebar.error("❌ No valid documents processed")

# RAG Status
if st.session_state.rag_enabled:
    st.sidebar.success(f"📚 RAG Enabled: {len(st.session_state.documents)} documents loaded")
    if st.sidebar.button("Clear Documents"):
        st.session_state.documents = []
        st.session_state.vector_store = None
        st.session_state.chunk_metadata = []
        st.session_state.rag_enabled = False
        st.sidebar.success("Documents cleared")
        st.rerun()
else:
    st.sidebar.info("📚 RAG Disabled: No documents loaded")

# Get latest data for dashboard
latest_data = get_latest_data_by_location()

# Dashboard metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_locations = len(latest_data)
    st.metric("Active Locations", total_locations)

with col2:
    all_alerts = []
    for _, row in latest_data.iterrows():
        all_alerts.extend(check_alerts(row))
    critical_alerts = len([alert for alert in all_alerts if 'CRITICAL' in alert])
    st.metric("Critical Alerts", critical_alerts)

with col3:
    warning_alerts = len([alert for alert in all_alerts if 'WARNING' in alert])
    st.metric("Warnings", warning_alerts)

with col4:
    cities_count = len(latest_data['city'].unique())
    st.metric("Cities", cities_count)

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": """Hello! I'm your ATM Network Monitoring Assistant with RAG capabilities. I can help you with:

**ATM System Queries:**
- "Temperature at Delhi Connaught"
- "Show temperatures above 45°C"
- "Critical temperature alerts"
- "Network latency in Hyderabad"
- "Cash below 15%"
- "Status of all Pune branches"

**Document-Based Queries (when documents are uploaded):**
- Ask questions about uploaded documents
- Get answers from your documentation
- Combined responses from both ATM data and documents

**Quick Commands:**
- Type "show data" to see all ATM locations
- Upload documents in the sidebar for RAG functionality

🔹 Upload documents (PDF, Word, TXT) in the sidebar to enable document-based responses!"""}
    ]

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if user_query := st.chat_input("Ask about any ATM location or system status..."):
    # Add user message
    st.session_state.chat_history.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Process query with Langfuse tracking
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            if langfuse:
                reply, trace_id = get_response(user_query, langfuse)
            else:
                # Fallback without Langfuse
                try:
                    reply = process_query(user_query)
                    trace_id = None
                except Exception as e:
                    reply = f"I encountered an error: {str(e)}\n\nPlease try rephrasing your question or type 'show data' to see available locations."
                    trace_id = None

        st.markdown(reply)
        if trace_id:
            trace_url = f"https://us.cloud.langfuse.com/project/cmfl7c9bc02tpad079bvnyyzf/traces/{trace_id}"
            st.markdown(f"[→ View Trace]({trace_url})")

    # Add response to chat history
    st.session_state.chat_history.append({"role": "assistant", "content": reply})

# Sidebar with system info
with st.sidebar:
    st.header("🌐 System Coverage")

    # Group locations by city
    locations_by_city = {}
    for _, row in latest_data.iterrows():
        city = row['city']
        branch = row['branch']
        if city not in locations_by_city:
            locations_by_city[city] = []
        locations_by_city[city].append((branch, row))

    # Display each city and its branches with status
    for city in sorted(locations_by_city.keys()):
        st.subheader(f"🏢 {city}")
        for branch, row in locations_by_city[city]:
            alerts = check_alerts(row)
            if any('CRITICAL' in alert for alert in alerts):
                status = "🔴"
            elif alerts:
                status = "🟡"
            else:
                status = "🟢"
            st.write(f"{status} {branch}")

    st.header("💡 Quick Commands")
    st.markdown("""
    **Try these:**
    - show data
    - temperature in Delhi
    - cash below 15%
    - network issues
    - status of Pune branches
    - critical alerts
    """)

    st.header("📊 Quick Stats")
    high_temp = len(latest_data[latest_data['temperature_c'] >= thresholds['temp_warning']])
    high_network = len(latest_data[latest_data['network_latency_ms'] >= thresholds['network_warning']])
    low_cash = len(latest_data[latest_data['cash_level_pct'] <= thresholds['cash_warning']])

    st.metric("High Temperature", high_temp)
    st.metric("High Network Latency", high_network)
    st.metric("Low Cash", low_cash)

    # Langfuse tracking info
    st.header("📊 Tracking & RAG Info")
    st.markdown("**Agent:** custom-atm-agent")
    st.markdown("**Tracking:** Langfuse enabled" if langfuse else "**Tracking:** Disabled")
    st.markdown(f"**Messages:** {len(st.session_state.chat_history)}")
    st.markdown(f"**RAG Status:** {'Enabled' if st.session_state.rag_enabled else 'Disabled'}")
    if st.session_state.rag_enabled:
        st.markdown(f"**Documents:** {len(st.session_state.documents)}")
        st.markdown(f"**Chunks:** {len(st.session_state.chunk_metadata)}")

    # Document list
    if st.session_state.documents:
        st.subheader("📁 Loaded Documents")
        for doc in st.session_state.documents:
            st.write(f"📄 {doc['filename']}")

    # Langfuse dashboard link
    if langfuse:
        st.markdown("---")
        st.markdown("### 🔗 Langfuse Dashboard")
        langfuse_traces_url = "https://us.cloud.langfuse.com/project/cmfl7c9bc02tpad079bvnyyzf/traces"
        st.markdown(f"[View All Traces]({langfuse_traces_url})")

    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = [st.session_state.chat_history[0]]  # Keep initial message
        st.rerun()