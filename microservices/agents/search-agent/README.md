# Search Agent Service

## Overview
The Search Agent Service provides internet search capabilities for real-time information retrieval. It integrates with search engines and provides content extraction and validation.

## Responsibilities
- **Web Search**: Perform internet searches using search engines
- **Content Extraction**: Extract and parse content from web pages
- **Result Validation**: Validate and filter search results
- **Source Verification**: Verify source reliability and authenticity
- **Rate Limiting**: Respect search engine rate limits
- **Content Filtering**: Filter inappropriate or unreliable content

## Architecture
```
Orchestration Service → Search Agent Service → Search Engines
                        ↓
                    Content Extractor
                        ↓
                    Result Validator
```

## Features
- **Multi-engine Support**: Google Custom Search, Bing, etc.
- **Content Extraction**: HTML parsing and text extraction
- **URL Validation**: Validate and check URL accessibility
- **Result Filtering**: Filter by relevance, date, source
- **Caching**: Cache search results for performance
- **Rate Limiting**: Respect API rate limits

## Configuration
- **Port**: 8003 (configurable)
- **Search API**: Google Custom Search API
- **Rate Limits**: Configurable request limits
- **Cache TTL**: Configurable cache expiration
- **Content Limits**: Configurable content extraction limits
- **Filtering Rules**: Configurable content filtering

## Dependencies
- Search Engine APIs (Google Custom Search)
- HTTP Client (aiohttp)
- Content Parser (BeautifulSoup)
- Redis (for caching)
- Rate Limiting Service

## API Endpoints
- `POST /search` - Perform web search
- `POST /extract` - Extract content from URL
- `POST /validate` - Validate URLs
- `GET /engines` - List available search engines
- `GET /health` - Health check
