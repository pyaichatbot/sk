# ============================================================================
# microservices/agents/rag-agent/rag_agent.py
# ============================================================================
"""
RAG Agent implementation for microservice
Adapted from monolithic structure with microservice-specific modifications
"""

import os
import asyncio
from typing import AsyncIterator, List, Dict, Any, Optional
from pathlib import Path
import hashlib
from datetime import datetime

# Add shared modules to path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel import Kernel

from shared.models import AgentCapabilities, AgentResponse
from shared.infrastructure.observability.logging import get_logger
from shared.infrastructure.ai_services.service_factory import AIServiceFactory
from shared.infrastructure.storage.document_store import DocumentStore
from shared.config.settings import MicroserviceSettings

logger = get_logger(__name__)

class RAGAgent:
    """Retrieval-Augmented Generation agent for document-based Q&A"""
    
    def __init__(self, settings: MicroserviceSettings, document_store: Optional[DocumentStore] = None):
        self.settings = settings
        self.agent_id = "rag-agent-001"
        self.capabilities = AgentCapabilities(
            agent_name="RAGAgent",
            capabilities=["document_processing", "vector_search", "contextual_generation", "multi_format_support", "semantic_retrieval"],
            input_formats=["text", "pdf", "docx", "txt", "json", "xml", "csv"],
            output_formats=["text", "json"],
            max_input_size=50000,
            rate_limit=50,
            timeout=60
        )
        
        self.instructions = """
        You are a specialized RAG (Retrieval-Augmented Generation) agent that combines 
        document retrieval with language generation.
        
        Your capabilities include:
        1. Processing documents in multiple formats (PDF, Word, TXT, JSON, XML, CSV)
        2. Creating and managing vector embeddings for semantic search
        3. Retrieving relevant context from document collections
        4. Generating accurate answers based on retrieved context
        5. Providing source citations and confidence scores
        
        Always:
        - Base answers on the retrieved context
        - Cite specific sources and page numbers when available
        - Indicate confidence levels in your responses
        - Acknowledge when information is not available in the documents
        - Respect document access permissions and privacy settings
        """
        
        self.name = "RAGAgent"
        self.description = "Retrieval-Augmented Generation agent for document-based question answering"
        
        # Initialize document store and services
        self.document_store = document_store or DocumentStore()
        self.kernel: Optional[Kernel] = None
        self._agent: Optional[ChatCompletionAgent] = None
        self._initialized = False
        
        # RAG specific settings
        self.max_context_length = 4000
        self.similarity_threshold = 0.7
        self.max_retrieved_docs = 5
        
        # Performance metrics
        self._metrics = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "average_response_time": 0.0
        }
        
        self.logger = get_logger(f"agent.{self.name}")
        self._start_time = datetime.utcnow()
        
        self.logger.info(
            "RAG Agent initialized",
            agent_name=self.name,
            agent_id=self.agent_id,
            capabilities=self.capabilities.capabilities
        )
    
    async def initialize(self):
        """Initialize the agent with kernel and services"""
        if self._initialized:
            return
        
        try:
            # Create kernel
            self.kernel = await AIServiceFactory.create_kernel()
            
            # Create ChatCompletion agent
            self._agent = ChatCompletionAgent(
                kernel=self.kernel,
                name=self.name,
                instructions=self.instructions,
                description=self.description
            )
            
            self._initialized = True
            
            self.logger.info(
                "RAG Agent initialization complete",
                agent_name=self.name
            )
            
        except Exception as e:
            self.logger.error(f"RAG Agent initialization failed: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup agent resources"""
        try:
            if self._agent:
                # Cleanup agent if needed
                pass
            if self.kernel:
                # Cleanup kernel if needed
                pass
            self.logger.info("RAG Agent cleanup completed")
        except Exception as e:
            self.logger.error(f"RAG Agent cleanup failed: {e}")
    
    async def invoke(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        include_sources: bool = True,
        max_context_docs: Optional[int] = None,
        **kwargs
    ) -> AgentResponse:
        """Invoke RAG agent with document retrieval"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Retrieve relevant documents
            max_docs = max_context_docs or self.max_retrieved_docs
            relevant_docs = await self.document_store.search_documents(
                query=message,
                max_results=max_docs,
                similarity_threshold=self.similarity_threshold
            )
            
            # Build context from retrieved documents
            context = self._build_context(relevant_docs)
            
            # Create enhanced prompt with context
            enhanced_prompt = self._create_rag_prompt(message, context, relevant_docs)
            
            # Get response from LLM
            user_message = ChatMessageContent(role=AuthorRole.USER, content=enhanced_prompt)
            responses = await self._agent.invoke(user_message, thread)
            
            if responses:
                result = responses[-1].content
                
                # Add source information if requested
                if include_sources and relevant_docs:
                    sources = self._format_sources(relevant_docs)
                    result = f"{result}\n\n**Sources:**\n{sources}"
                
                # Update metrics
                self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
                
                # Create audit entry
                audit_entry = {
                    "timestamp": start_time.isoformat(),
                    "action": "rag_query",
                    "user_id": user_id,
                    "session_id": session_id,
                    "query_hash": hash(message),
                    "docs_retrieved": len(relevant_docs),
                    "agent_name": self.name,
                    "agent_id": self.agent_id
                }
                
                response = AgentResponse(
                    content=result,
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    metadata={
                        "thread_id": getattr(thread, 'id', None),
                        "docs_retrieved": len(relevant_docs),
                        "context_length": len(context),
                        **kwargs
                    },
                    audit_trail=[audit_entry]
                )
                
                self.logger.info(
                    "RAG query completed",
                    docs_retrieved=len(relevant_docs),
                    context_length=len(context),
                    response_time_ms=response.metadata["response_time_ms"]
                )
                
                return response
            else:
                return AgentResponse(
                    content="No response generated from RAG query.",
                    agent_id=self.agent_id,
                    agent_name=self.name,
                    success=False,
                    metadata={"warning": "No response generated"}
                )
                
        except Exception as e:
            # Update metrics
            self._update_metrics(False, (datetime.utcnow() - start_time).total_seconds())
            
            self.logger.error(f"RAG execution failed: {e}")
            
            return AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__,
                metadata={"error_type": type(e).__name__}
            )
    
    async def invoke_stream(
        self,
        message: str,
        thread: Optional[ChatHistoryAgentThread] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[AgentResponse]:
        """Execute streaming RAG query"""
        from datetime import datetime
        start_time = datetime.utcnow()
        
        try:
            await self.initialize()
            
            # Create or use existing thread
            if thread is None:
                thread = ChatHistoryAgentThread()
            
            # Validate request
            await self._validate_request(message, user_id)
            
            # Retrieve context (same as non-streaming)
            relevant_docs = await self.document_store.search_documents(
                query=message,
                max_results=self.max_retrieved_docs,
                similarity_threshold=self.similarity_threshold
            )
            
            context = self._build_context(relevant_docs)
            enhanced_prompt = self._create_rag_prompt(message, context, relevant_docs)
            
            # Stream response
            user_message = ChatMessageContent(role=AuthorRole.USER, content=enhanced_prompt)
            
            async for response in self._agent.invoke_stream(user_message, thread):
                if hasattr(response, 'content') and response.content:
                    yield AgentResponse(
                        content=response.content,
                        agent_id=self.agent_id,
                        agent_name=self.name,
                        metadata={
                            "streaming": True,
                            "thread_id": getattr(thread, 'id', None),
                            "docs_retrieved": len(relevant_docs)
                        }
                    )
            
            # Update metrics
            self._update_metrics(True, (datetime.utcnow() - start_time).total_seconds())
            
        except Exception as e:
            self.logger.error(f"Streaming RAG execution failed: {e}")
            yield AgentResponse(
                content="",
                agent_id=self.agent_id,
                agent_name=self.name,
                success=False,
                error=str(e),
                error_code=type(e).__name__
            )
    
    async def add_document(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a document to the RAG system"""
        try:
            await self.initialize()
            
            # Process document
            doc_id = await self.document_store.add_document(
                file_path=file_path,
                document_id=document_id,
                metadata=metadata or {}
            )
            
            self.logger.info(
                "Document added to RAG system",
                document_id=doc_id,
                file_path=file_path
            )
            
            return doc_id
            
        except Exception as e:
            self.logger.error(f"Failed to add document: {e}, file_path={file_path}")
            raise
    
    async def add_documents_batch(
        self,
        file_paths: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """Add multiple documents to the RAG system"""
        doc_ids = []
        
        for i, file_path in enumerate(file_paths):
            try:
                metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
                doc_id = await self.add_document(file_path, metadata=metadata)
                doc_ids.append(doc_id)
            except Exception as e:
                self.logger.error(f"Failed to add document in batch: {e}, file_path={file_path}")
                doc_ids.append(None)
        
        return doc_ids
    
    async def get_document_summary(self, document_id: str) -> str:
        """Get summary of a specific document"""
        try:
            doc_info = await self.document_store.get_document(document_id)
            if not doc_info:
                return "Document not found."
            
            content = doc_info.get('content', '')
            if len(content) > 2000:
                # Summarize if content is long
                summary_prompt = f"Please provide a concise summary of the following document:\n\n{content[:2000]}..."
                response = await self.invoke(summary_prompt, include_sources=False)
                return response.content
            else:
                return content
                
        except Exception as e:
            self.logger.error(f"Failed to get document summary: {e}, document_id={document_id}")
            return f"Error retrieving document summary: {str(e)}"
    
    async def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents in the RAG system"""
        try:
            return await self.document_store.list_documents()
        except Exception as e:
            self.logger.error(f"Failed to list documents: {e}")
            return []
    
    async def remove_document(self, document_id: str) -> bool:
        """Remove a document from the RAG system"""
        try:
            success = await self.document_store.remove_document(document_id)
            if success:
                self.logger.info("Document removed from RAG system", document_id=document_id)
            return success
        except Exception as e:
            self.logger.error(f"Failed to remove document: {e}, document_id={document_id}")
            return False
    
    def update_settings(
        self,
        max_context_length: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        max_retrieved_docs: Optional[int] = None
    ):
        """Update RAG agent settings"""
        if max_context_length is not None:
            self.max_context_length = max_context_length
        
        if similarity_threshold is not None:
            self.similarity_threshold = max(0.0, min(1.0, similarity_threshold))
        
        if max_retrieved_docs is not None:
            self.max_retrieved_docs = max(1, max_retrieved_docs)
        
        self.logger.info(
            "RAG settings updated",
            max_context_length=self.max_context_length,
            similarity_threshold=self.similarity_threshold,
            max_retrieved_docs=self.max_retrieved_docs
        )
    
    def _build_context(self, documents: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved documents"""
        context_parts = []
        total_length = 0
        
        for doc in documents:
            content = doc.get('content', '')
            source = doc.get('source', 'Unknown')
            score = doc.get('similarity_score', 0.0)
            
            # Add document with metadata
            doc_text = f"[Source: {source} | Relevance: {score:.2f}]\n{content}\n"
            
            # Check if adding this document would exceed context limit
            if total_length + len(doc_text) > self.max_context_length:
                # Truncate if needed
                remaining_space = self.max_context_length - total_length
                if remaining_space > 100:  # Only add if meaningful space remains
                    doc_text = doc_text[:remaining_space] + "...\n"
                    context_parts.append(doc_text)
                break
            
            context_parts.append(doc_text)
            total_length += len(doc_text)
        
        return "\n---\n".join(context_parts)
    
    def _create_rag_prompt(
        self,
        query: str,
        context: str,
        documents: List[Dict[str, Any]]
    ) -> str:
        """Create enhanced prompt with retrieved context"""
        prompt = f"""
You are answering a question based on the provided context from relevant documents.

**Instructions:**
1. Answer the question using ONLY the information provided in the context below
2. If the context doesn't contain enough information, clearly state this
3. Cite specific sources when making claims
4. Provide confidence levels for your answers
5. Be precise and factual

**Context from Retrieved Documents:**
{context}

**User Question:** {query}

**Your Answer:**
"""
        return prompt
    
    def _format_sources(self, documents: List[Dict[str, Any]]) -> str:
        """Format source citations"""
        sources = []
        
        for i, doc in enumerate(documents, 1):
            source = doc.get('source', 'Unknown')
            score = doc.get('similarity_score', 0.0)
            page = doc.get('page_number', '')
            
            source_line = f"{i}. {source}"
            if page:
                source_line += f" (Page {page})"
            source_line += f" - Relevance: {score:.2f}"
            
            sources.append(source_line)
        
        return "\n".join(sources)
    
    async def _validate_request(self, message: str, user_id: Optional[str]):
        """Validate request against governance policies"""
        # Input validation
        if not message or len(message.strip()) == 0:
            raise ValueError("Message cannot be empty")
        
        if len(message) > 10000:  # Max message length
            raise ValueError("Message too long")
        
        # Rate limiting check (implement based on user_id)
        if user_id:
            await self._check_rate_limit(user_id)
        
        # Content filtering
        await self._filter_content(message)
    
    async def _check_rate_limit(self, user_id: str):
        """Check rate limiting for user"""
        # Implementation depends on rate limiting strategy
        # This could use Redis or in-memory store
        pass
    
    async def _filter_content(self, message: str):
        """Filter content for inappropriate content"""
        # Implement content filtering logic
        # Could use external services or internal rules
        pass
    
    def _update_metrics(self, success: bool, response_time: float):
        """Update performance metrics"""
        from datetime import datetime
        
        self._metrics["requests_total"] += 1
        
        if success:
            self._metrics["requests_successful"] += 1
        else:
            self._metrics["requests_failed"] += 1
        
        # Update average response time
        total_requests = self._metrics["requests_total"]
        current_avg = self._metrics["average_response_time"]
        self._metrics["average_response_time"] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        from datetime import datetime
        
        return {
            **self._metrics,
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "uptime": (datetime.utcnow() - self._start_time).total_seconds()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get agent health status"""
        success_rate = 0
        if self._metrics["requests_total"] > 0:
            success_rate = self._metrics["requests_successful"] / self._metrics["requests_total"]
        
        status = "healthy"
        if success_rate < 0.95:
            status = "degraded"
        if success_rate < 0.8:
            status = "unhealthy"
        
        return {
            "status": status,
            "success_rate": success_rate,
            "average_response_time": self._metrics["average_response_time"],
            "total_requests": self._metrics["requests_total"],
            "initialized": self._initialized
        }
