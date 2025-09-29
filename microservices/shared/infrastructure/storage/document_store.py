# Document Store and Memory Management Implementation

# ============================================================================
# src/infrastructure/storage/document_store.py
# ============================================================================
import os
import hashlib
import asyncio
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import json
import mimetypes
from dataclasses import dataclass, asdict
from uuid import uuid4

# Document processing libraries
import PyPDF2
import docx
import pandas as pd
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# Vector database (using a simple in-memory implementation for demo)
# In production, use Pinecone, Weaviate, or similar
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from shared.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

@dataclass
class DocumentMetadata:
    """Document metadata structure"""
    document_id: str
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    created_at: datetime
    updated_at: datetime
    content_hash: str
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None
    tags: List[str] = None
    custom_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.custom_metadata is None:
            self.custom_metadata = {}

@dataclass
class DocumentChunk:
    """Document chunk for vector storage"""
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class DocumentProcessor:
    """Document processing utilities"""
    
    SUPPORTED_FORMATS = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.csv': 'text/csv',
        '.html': 'text/html',
        '.htm': 'text/html'
    }
    
    @classmethod
    async def process_document(
        cls,
        file_path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> tuple[str, List[DocumentChunk], DocumentMetadata]:
        """Process document and create chunks"""
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file type
        file_ext = file_path.suffix.lower()
        if file_ext not in cls.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        # Extract text content
        content = await cls._extract_text(file_path)
        
        # Create document metadata
        file_stats = file_path.stat()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        metadata = DocumentMetadata(
            document_id=str(uuid4()),
            file_path=str(file_path),
            file_name=file_path.name,
            file_type=file_ext,
            file_size=file_stats.st_size,
            created_at=datetime.fromtimestamp(file_stats.st_ctime),
            updated_at=datetime.fromtimestamp(file_stats.st_mtime),
            content_hash=content_hash,
            word_count=len(content.split())
        )
        
        # Create chunks
        chunks = cls._create_chunks(
            content=content,
            document_id=metadata.document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        logger.info(
            "Document processed",
            file_path=str(file_path),
            content_length=len(content),
            chunks_created=len(chunks),
            document_id=metadata.document_id
        )
        
        return content, chunks, metadata
    
    @classmethod
    async def _extract_text(cls, file_path: Path) -> str:
        """Extract text from different file formats"""
        file_ext = file_path.suffix.lower()
        
        try:
            if file_ext == '.pdf':
                return await cls._extract_pdf_text(file_path)
            elif file_ext == '.docx':
                return await cls._extract_docx_text(file_path)
            elif file_ext == '.txt':
                return await cls._extract_txt_text(file_path)
            elif file_ext == '.json':
                return await cls._extract_json_text(file_path)
            elif file_ext == '.xml':
                return await cls._extract_xml_text(file_path)
            elif file_ext == '.csv':
                return await cls._extract_csv_text(file_path)
            elif file_ext in ['.html', '.htm']:
                return await cls._extract_html_text(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
        
        except Exception as e:
            logger.error(f"Text extraction failed for file {file_path}: {str(e)}")
            raise
    
    @classmethod
    async def _extract_pdf_text(cls, file_path: Path) -> str:
        """Extract text from PDF"""
        text_parts = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(f"[Page {page_num + 1}]\n{text}\n")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num + 1}", error=e)
        
        return "\n".join(text_parts)
    
    @classmethod
    async def _extract_docx_text(cls, file_path: Path) -> str:
        """Extract text from DOCX"""
        doc = docx.Document(file_path)
        text_parts = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return "\n".join(text_parts)
    
    @classmethod
    async def _extract_txt_text(cls, file_path: Path) -> str:
        """Extract text from TXT"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    
    @classmethod
    async def _extract_json_text(cls, file_path: Path) -> str:
        """Extract text from JSON"""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        def extract_values(obj, path=""):
            """Recursively extract all string values from JSON"""
            text_parts = []
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    text_parts.extend(extract_values(value, current_path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]" if path else f"[{i}]"
                    text_parts.extend(extract_values(item, current_path))
            elif isinstance(obj, str):
                text_parts.append(f"{path}: {obj}")
            else:
                text_parts.append(f"{path}: {str(obj)}")
            
            return text_parts
        
        return "\n".join(extract_values(data))
    
    @classmethod
    async def _extract_xml_text(cls, file_path: Path) -> str:
        """Extract text from XML"""
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        def extract_xml_text(element, path=""):
            text_parts = []
            current_path = f"{path}.{element.tag}" if path else element.tag
            
            if element.text and element.text.strip():
                text_parts.append(f"{current_path}: {element.text.strip()}")
            
            for child in element:
                text_parts.extend(extract_xml_text(child, current_path))
            
            return text_parts
        
        return "\n".join(extract_xml_text(root))
    
    @classmethod
    async def _extract_csv_text(cls, file_path: Path) -> str:
        """Extract text from CSV"""
        df = pd.read_csv(file_path)
        
        # Convert DataFrame to readable text
        text_parts = [f"CSV File: {file_path.name}"]
        text_parts.append(f"Columns: {', '.join(df.columns.tolist())}")
        text_parts.append(f"Rows: {len(df)}")
        text_parts.append("\nData:")
        
        # Add column descriptions
        for col in df.columns:
            non_null_count = df[col].notna().sum()
            data_type = str(df[col].dtype)
            text_parts.append(f"- {col}: {non_null_count} non-null values, type: {data_type}")
        
        # Add sample data
        text_parts.append("\nSample Data:")
        sample_size = min(10, len(df))
        for _, row in df.head(sample_size).iterrows():
            row_text = " | ".join([f"{col}: {val}" for col, val in row.items()])
            text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    @classmethod
    async def _extract_html_text(cls, file_path: Path) -> str:
        """Extract text from HTML"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            html_content = file.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        
        # Extract text
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return ' '.join(chunk for chunk in chunks if chunk)
    
    @classmethod
    def _create_chunks(
        cls,
        content: str,
        document_id: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[DocumentChunk]:
        """Create text chunks with overlap"""
        chunks = []
        
        if len(content) <= chunk_size:
            # Single chunk
            chunks.append(DocumentChunk(
                chunk_id=str(uuid4()),
                document_id=document_id,
                content=content,
                chunk_index=0,
                start_char=0,
                end_char=len(content)
            ))
            return chunks
        
        # Multiple chunks with overlap
        start = 0
        chunk_index = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            
            # Adjust end to word boundary if possible
            if end < len(content):
                # Find the last space within the chunk
                last_space = content.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_content = content[start:end].strip()
            
            if chunk_content:
                chunks.append(DocumentChunk(
                    chunk_id=str(uuid4()),
                    document_id=document_id,
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end
                ))
                
                chunk_index += 1
            
            # Move start position with overlap
            if end >= len(content):
                break
                
            start = max(start + chunk_size - chunk_overlap, start + 1)
        
        return chunks

class VectorStore:
    """Simple vector store implementation"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.document_vectors = None
        self.chunk_index = {}
        self.is_fitted = False
    
    async def add_chunks(self, chunks: List[DocumentChunk]):
        """Add chunks to vector store"""
        logger.info("Adding chunks to vector store", chunk_count=len(chunks))
        
        # Extract texts for vectorization
        texts = [chunk.content for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        
        # Create or update vectorizer
        if not self.is_fitted:
            self.document_vectors = self.vectorizer.fit_transform(texts)
            self.is_fitted = True
        else:
            # Transform new texts with existing vectorizer
            new_vectors = self.vectorizer.transform(texts)
            
            # Combine with existing vectors
            if self.document_vectors is not None:
                from scipy.sparse import vstack
                self.document_vectors = vstack([self.document_vectors, new_vectors])
            else:
                self.document_vectors = new_vectors
        
        # Update chunk index
        start_idx = len(self.chunk_index)
        for i, (chunk_id, chunk) in enumerate(zip(chunk_ids, chunks)):
            self.chunk_index[start_idx + i] = {
                'chunk_id': chunk_id,
                'chunk': chunk
            }
        
        logger.info("Chunks added to vector store", total_chunks=len(self.chunk_index))
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        similarity_threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks"""
        if not self.is_fitted or self.document_vectors is None:
            return []
        
        # Vectorize query
        query_vector = self.vectorizer.transform([query])
        
        # Calculate similarities
        similarities = cosine_similarity(query_vector, self.document_vectors).flatten()
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][:max_results]
        
        results = []
        for idx in top_indices:
            similarity_score = similarities[idx]
            
            if similarity_score >= similarity_threshold:
                chunk_info = self.chunk_index[idx]
                chunk = chunk_info['chunk']
                
                results.append({
                    'chunk_id': chunk.chunk_id,
                    'document_id': chunk.document_id,
                    'content': chunk.content,
                    'similarity_score': float(similarity_score),
                    'chunk_index': chunk.chunk_index,
                    'page_number': chunk.page_number,
                    'metadata': chunk.metadata
                })
        
        logger.info("Vector search completed", query_length=len(query), results_count=len(results))
        
        return results
    
    async def remove_document_chunks(self, document_id: str):
        """Remove all chunks for a document"""
        # Find indices to remove
        indices_to_remove = []
        for idx, chunk_info in self.chunk_index.items():
            if chunk_info['chunk'].document_id == document_id:
                indices_to_remove.append(idx)
        
        if not indices_to_remove:
            return
        
        # Remove from index
        for idx in indices_to_remove:
            del self.chunk_index[idx]
        
        # Rebuild vectors without removed chunks
        if self.chunk_index:
            remaining_chunks = [info['chunk'] for info in self.chunk_index.values()]
            texts = [chunk.content for chunk in remaining_chunks]
            
            self.document_vectors = self.vectorizer.fit_transform(texts)
            
            # Rebuild index with new indices
            new_index = {}
            for i, (old_idx, chunk_info) in enumerate(self.chunk_index.items()):
                new_index[i] = chunk_info
            
            self.chunk_index = new_index
        else:
            # No chunks left
            self.document_vectors = None
            self.is_fitted = False
        
        logger.info("Document chunks removed from vector store", document_id=document_id)

class DocumentStore:
    """Enterprise document store with vector search capabilities"""
    
    def __init__(self):
        self.documents: Dict[str, DocumentMetadata] = {}
        self.document_contents: Dict[str, str] = {}
        self.chunks: Dict[str, List[DocumentChunk]] = {}
        self.vector_store = VectorStore()
        
        # In production, replace with actual database connections
        self.initialized = False
        
        logger.info("Document store initialized")
    
    async def initialize(self):
        """Initialize document store"""
        if not self.initialized:
            # Initialize connections to databases
            # PostgreSQL for metadata, Vector DB for embeddings
            self.initialized = True
            logger.info("Document store initialization completed")
    
    async def add_document(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add document to store"""
        await self.initialize()
        
        logger.info("Adding document to store", file_path=file_path)
        
        try:
            # Process document
            content, chunks, doc_metadata = await DocumentProcessor.process_document(file_path)
            
            # Use provided document_id or generated one
            if document_id:
                doc_metadata.document_id = document_id
            
            # Add custom metadata
            if metadata:
                doc_metadata.custom_metadata.update(metadata)
            
            # Store document
            self.documents[doc_metadata.document_id] = doc_metadata
            self.document_contents[doc_metadata.document_id] = content
            self.chunks[doc_metadata.document_id] = chunks
            
            # Add to vector store
            await self.vector_store.add_chunks(chunks)
            
            logger.info(
                "Document added successfully",
                document_id=doc_metadata.document_id,
                chunks_count=len(chunks)
            )
            
            return doc_metadata.document_id
            
        except Exception as e:
            logger.error(f"Failed to add document for file {file_path}: {str(e)}")
            raise
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        if document_id not in self.documents:
            return None
        
        metadata = self.documents[document_id]
        content = self.document_contents.get(document_id, "")
        
        return {
            "metadata": asdict(metadata),
            "content": content,
            "chunk_count": len(self.chunks.get(document_id, []))
        }
    
    async def search_documents(
        self,
        query: str,
        max_results: int = 5,
        similarity_threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Search documents using vector similarity"""
        logger.info("Searching documents", query=query, max_results=max_results)
        
        try:
            results = await self.vector_store.search(
                query=query,
                max_results=max_results,
                similarity_threshold=similarity_threshold
            )
            
            # Enhance results with document metadata
            enhanced_results = []
            for result in results:
                document_id = result['document_id']
                if document_id in self.documents:
                    doc_metadata = self.documents[document_id]
                    result.update({
                        'source': doc_metadata.file_name,
                        'file_path': doc_metadata.file_path,
                        'file_type': doc_metadata.file_type,
                        'created_at': doc_metadata.created_at.isoformat()
                    })
                
                enhanced_results.append(result)
            
            logger.info("Document search completed", results_found=len(enhanced_results))
            
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Document search failed for query '{query}': {str(e)}")
            raise
    
    async def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents"""
        document_list = []
        
        for doc_id, metadata in self.documents.items():
            doc_info = asdict(metadata)
            doc_info['chunk_count'] = len(self.chunks.get(doc_id, []))
            document_list.append(doc_info)
        
        return document_list
    
    async def remove_document(self, document_id: str) -> bool:
        """Remove document from store"""
        if document_id not in self.documents:
            return False
        
        try:
            # Remove from vector store
            await self.vector_store.remove_document_chunks(document_id)
            
            # Remove from local storage
            del self.documents[document_id]
            
            if document_id in self.document_contents:
                del self.document_contents[document_id]
            
            if document_id in self.chunks:
                del self.chunks[document_id]
            
            logger.info("Document removed", document_id=document_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove document {document_id}: {str(e)}")
            return False
    
    async def get_document_stats(self) -> Dict[str, Any]:
        """Get document store statistics"""
        total_documents = len(self.documents)
        total_chunks = sum(len(chunks) for chunks in self.chunks.values())
        
        # File type distribution
        file_types = {}
        total_size = 0
        
        for metadata in self.documents.values():
            file_type = metadata.file_type
            file_types[file_type] = file_types.get(file_type, 0) + 1
            total_size += metadata.file_size
        
        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "file_types": file_types,
            "supported_formats": list(DocumentProcessor.SUPPORTED_FORMATS.keys())
        }