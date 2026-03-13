"""
EnerVision RAG (Retrieval-Augmented Generation) Chatbot System
Handles document processing, vector storage, and intelligent Q&A
"""

import os
import io
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import streamlit as st

# Document processing
import PyPDF2
from docx import Document
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai  # optional, used only if API key provided

# Configuration
class RAGConfig:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "demo_key")
        self.embedding_model_name = "all-MiniLM-L6-v2"
        self.max_chunk_size = 512
        self.chunk_overlap = 50
        self.similarity_threshold = 0.7
        self.max_context_length = 4000  # words approx, used to build prompt context
        self.gen_ai_model = "text-bison-001"  # placeholder model name

        # Configure Gemini (Google generative AI) if key present
        if self.gemini_api_key != "demo_key":
            try:
                genai.configure(api_key=self.gemini_api_key)
            except Exception:
                # leave configured or not; generation wrappers handle errors
                pass

class DocumentProcessor:
    """Handles document processing and chunking"""

    def __init__(self, config: RAGConfig):
        self.config = config

    def process_document(self, file_content: bytes, filename: str) -> List[Dict[str, str]]:
        """Process document and return chunks"""

        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text = self._extract_pdf_text(file_content)
        elif filename.lower().endswith('.docx'):
            text = self._extract_docx_text(file_content)
        elif filename.lower().endswith('.txt'):
            text = file_content.decode('utf-8')
        else:
            raise ValueError(f"Unsupported file type: {filename}")

        # Clean and chunk text
        cleaned_text = self._clean_text(text)
        chunks = self._chunk_text(cleaned_text, filename)

        return chunks

    def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            text_parts = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n".join(text_parts)
        except Exception as e:
            return f"Error extracting PDF text: {str(e)}"

    def _extract_docx_text(self, file_content: bytes) -> str:
        """Extract text from DOCX"""
        try:
            doc_file = io.BytesIO(file_content)
            doc = Document(doc_file)

            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    text_parts.append(paragraph.text)

            return "\n".join(text_parts)
        except Exception as e:
            return f"Error extracting DOCX text: {str(e)}"

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not isinstance(text, str):
            return ""

        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove special characters but keep punctuation
        import re
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', ' ', text)

        # Normalize spacing
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _chunk_text(self, text: str, source: str) -> List[Dict[str, str]]:
        """Split text into chunks with overlap"""

        chunks = []
        if not text:
            return chunks

        words = text.split()

        if len(words) <= self.config.max_chunk_size:
            # Single chunk
            chunks.append({
                "content": text,
                "source": source,
                "chunk_id": 0,
                "word_count": len(words)
            })
        else:
            # Multiple chunks with overlap
            chunk_id = 0
            start_idx = 0

            while start_idx < len(words):
                end_idx = min(start_idx + self.config.max_chunk_size, len(words))

                chunk_words = words[start_idx:end_idx]
                chunk_text = ' '.join(chunk_words)

                chunks.append({
                    "content": chunk_text,
                    "source": source,
                    "chunk_id": chunk_id,
                    "word_count": len(chunk_words)
                })

                # Move start index with overlap
                if end_idx == len(words):
                    break

                start_idx = end_idx - self.config.chunk_overlap
                chunk_id += 1

        return chunks

class VectorStore:
    """FAISS-based vector store for document embeddings"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.embedding_model = SentenceTransformer(config.embedding_model_name)
        self.index: Optional[faiss.Index] = None
        self.documents: List[str] = []
        self.document_metadata: List[Dict[str, Any]] = []

    def add_documents(self, chunks: List[Dict[str, str]]) -> bool:
        """Add document chunks to vector store"""

        try:
            if not chunks:
                return False

            # Generate embeddings
            texts = [chunk["content"] for chunk in chunks]
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

            # Initialize or update FAISS index
            if self.index is None:
                # Create new index
                dimension = embeddings.shape[1]
                # Using Inner Product (IP) and later normalize => cosine similarity
                self.index = faiss.IndexFlatIP(dimension)

            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)

            # Add to index
            self.index.add(embeddings.astype('float32'))

            # Store documents and metadata
            self.documents.extend(texts)
            self.document_metadata.extend(chunks)

            return True

        except Exception as e:
            st.error(f"Error adding documents to vector store: {str(e)}")
            return False

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents"""

        if self.index is None or len(self.documents) == 0:
            return []

        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query], convert_to_numpy=True, show_progress_bar=False)
            faiss.normalize_L2(query_embedding)

            # Search
            scores, indices = self.index.search(query_embedding.astype('float32'), top_k)

            # Prepare results
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.documents) and float(score) > self.config.similarity_threshold:
                    results.append({
                        "content": self.documents[idx],
                        "metadata": self.document_metadata[idx],
                        "similarity_score": float(score),
                        "source": self.document_metadata[idx].get("source", "Unknown")
                    })

            return results

        except Exception as e:
            st.error(f"Error searching vector store: {str(e)}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""

        sources = {}
        for metadata in self.document_metadata:
            source = metadata.get("source", "Unknown")
            sources[source] = sources.get(source, 0) + 1

        return {
            "total_documents": len(self.documents),
            "total_sources": len(sources),
            "sources_breakdown": sources,
            "index_size": int(self.index.ntotal) if self.index else 0
        }

class EnerVisionRAG:
    """Main RAG system for EnerVision"""

    def __init__(self):
        self.config = RAGConfig()
        self.document_processor = DocumentProcessor(self.config)
        self.vector_store = VectorStore(self.config)

    def add_file(self, uploaded_file: io.BytesIO, filename: str) -> bool:
        """Process an uploaded file and index its chunks"""
        try:
            content = uploaded_file.read()
            chunks = self.document_processor.process_document(content, filename)
            if not chunks:
                st.warning(f"No text extracted from {filename}.")
                return False
            return self.vector_store.add_documents(chunks)
        except Exception as e:
            st.error(f"Failed to add file {filename}: {str(e)}")
            return False

    def _build_context(self, results: List[Dict[str, Any]]) -> str:
        """Build an answer context by concatenating retrieved chunks up to max_context_length"""
        if not results:
            return ""

        context_parts = []
        total_words = 0
        for r in results:
            content = r.get("content", "")
            words = content.split()
            if total_words + len(words) > self.config.max_context_length:
                # truncate to remaining words
                remaining = max(0, self.config.max_context_length - total_words)
                if remaining <= 0:
                    break
                context_parts.append(' '.join(words[:remaining]))
                total_words += remaining
                break
            else:
                context_parts.append(content)
                total_words += len(words)

        return "\n\n".join(context_parts)

    def generate_answer(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """Search, assemble context, and generate final answer (uses Gemini if configured)"""
        # Step 1: retrieve relevant chunks
        results = self.vector_store.search(question, top_k=top_k)

        # Step 2: build context from retrieved docs
        context = self._build_context(results)

        # Step 3: craft a prompt for generation
        prompt = (
            "You are an expert assistant. Use the context below (do not hallucinate). "
            "Answer the user's question concisely and cite the source filename and chunk_id when relevant.\n\n"
            "CONTEXT:\n"
            f"{context}\n\n"
            "QUESTION:\n"
            f"{question}\n\n"
            "Answer:"
        )

        # Step 4: if Gemini configured, attempt to call it; otherwise return synthesized answer from context
        if self.config.gemini_api_key != "demo_key":
            try:
                # NOTE: actual genai API usage may differ depending on package version.
                # We attempt a generic call; any errors fall back to a local composed answer.
                response = genai.generate(
                    model=self.config.gen_ai_model,
                    prompt=prompt,
                    max_output_tokens=512,
                )
                # response may be a dict-like, handle gracefully
                gen_text = ""
                if isinstance(response, dict):
                    # Try a common key
                    gen_text = response.get("candidates", [{}])[0].get("content", "")
                    if not gen_text:
                        gen_text = response.get("content", "") or str(response)
                else:
                    gen_text = str(response)
                return {
                    "answer": gen_text.strip(),
                    "retrieved": results,
                    "used_model": "gemini"  # best-effort label
                }
            except Exception as e:
                # If generation fails, fallback to context-based response
                st.warning(f"Generative model call failed: {str(e)}. Returning extracted context summary.")
                synthesized = self._synthesize_answer_from_context(context, question, results)
                return {
                    "answer": synthesized,
                    "retrieved": results,
                    "used_model": "fallback"
                }
        else:
            # No API key: synthesize directly
            synthesized = self._synthesize_answer_from_context(context, question, results)
            return {
                "answer": synthesized,
                "retrieved": results,
                "used_model": "local_synthesis"
            }

    def _synthesize_answer_from_context(self, context: str, question: str, results: List[Dict[str, Any]]) -> str:
        """Basic deterministic answer builder using retrieved context (no LLM)"""
        if not context:
            return "I couldn't find relevant information in the indexed documents."

        # Simple heuristic: return context + list of sources and short summary
        top_sources = []
        for r in results:
            md = r.get("metadata", {})
            src = md.get("source", "Unknown")
            cid = md.get("chunk_id", "?")
            top_sources.append(f"{src} (chunk {cid})")

        summary = (
            f"Found {len(results)} relevant passages. Sources: {', '.join(top_sources)}.\n\n"
            f"Context excerpts:\n{context[:2000]}...\n\n"
            "Please ask a follow-up if you want a focused summary of a particular aspect."
        )
        return summary
