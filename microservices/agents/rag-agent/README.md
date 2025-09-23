# RAG Agent Service

## Overview
The RAG (Retrieval-Augmented Generation) Agent Service provides document-based question answering capabilities. It processes documents, creates vector embeddings, and retrieves relevant context for generating accurate responses.

## Responsibilities
- **Document Processing**: Handle multiple document formats (PDF, Word, TXT, JSON, XML, CSV)
- **Vector Embeddings**: Create and manage vector embeddings for semantic search
- **Context Retrieval**: Retrieve relevant document context based on queries
- **Response Generation**: Generate answers using retrieved context
- **Source Citation**: Provide source references and confidence scores
- **Document Management**: Upload, search, list, and remove documents

## Architecture
```
Orchestration Service → RAG Agent Service → Vector Database
                        ↓
                    Document Store
                        ↓
                    Embedding Service
```

## Features
- **Multi-format Support**: PDF, Word, TXT, JSON, XML, CSV
- **Semantic Search**: Vector-based similarity search
- **Context Management**: Configurable context length and retrieval parameters
- **Source Tracking**: Document source and page number tracking
- **Confidence Scoring**: Response confidence and relevance scoring
- **Batch Processing**: Support for bulk document operations

## Configuration
- **Port**: 8002 (configurable)
- **Vector Database**: Milvus integration
- **Document Storage**: File system or object storage
- **Embedding Model**: Configurable embedding service
- **Context Length**: Configurable maximum context length
- **Similarity Threshold**: Configurable similarity threshold

## Dependencies
- Vector Database (Milvus)
- Document Storage (File system/S3)
- Embedding Service
- Redis (for caching)
- PostgreSQL (for metadata)

## API Endpoints
- `POST /documents/upload` - Upload document
- `POST /documents/search` - Search documents
- `GET /documents` - List documents
- `DELETE /documents/{id}` - Remove document
- `POST /query` - Process RAG query
- `GET /health` - Health check
