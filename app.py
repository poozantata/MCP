from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional
import asyncio
from main import WebScrapingOrchestrator

app = FastAPI(
    title="Advanced Web Scraper for LLM",
    description="Scrape, analyze, and store web content optimized for LLM consumption",
    version="1.0.0"
)

# Global orchestrator instance
orchestrator = WebScrapingOrchestrator()

# Pydantic models
class URLRequest(BaseModel):
    url: HttpUrl
    
class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class BatchURLRequest(BaseModel):
    urls: List[HttpUrl]

# Response models
class ScrapingResponse(BaseModel):
    success: bool
    url: str
    title: Optional[str] = None
    summary: Optional[Dict] = None
    llm_ready_data: Optional[Dict] = None
    error: Optional[str] = None

class SearchResponse(BaseModel):
    results: List[Dict]
    total_found: int

@app.post("/scrape", response_model=ScrapingResponse)
async def scrape_url(request: URLRequest):
    """Scrape a single URL and store data optimized for LLM consumption"""
    try:
        result = await orchestrator.process_url(str(request.url))
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return ScrapingResponse(**result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/scrape-batch")
async def scrape_batch_urls(request: BatchURLRequest, background_tasks: BackgroundTasks):
    """Scrape multiple URLs in the background"""
    async def process_batch():
        results = []
        for url in request.urls:
            try:
                result = await orchestrator.process_url(str(url))
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "url": str(url)})
        return results
    
    # Add to background tasks
    background_tasks.add_task(process_batch)
    
    return {
        "message": f"Started processing {len(request.urls)} URLs in background",
        "urls": [str(url) for url in request.urls]
    }

@app.get("/page/{url:path}")
async def get_page_data(url: str):
    """Get processed page data optimized for LLM consumption"""
    try:
        # Decode URL
        import urllib.parse
        decoded_url = urllib.parse.unquote(url)
        
        page_data = orchestrator.get_page_for_llm(decoded_url)
        
        if not page_data:
            raise HTTPException(status_code=404, detail="Page not found")
        
        return page_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search_content(request: SearchRequest):
    """Search stored content for LLM context"""
    try:
        results = orchestrator.search_for_llm(request.query, request.limit)
        
        return SearchResponse(
            results=results,
            total_found=len(results)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/llm-ready/{url:path}")
async def get_llm_ready_content(url: str):
    """Get content specifically formatted for LLM consumption"""
    try:
        import urllib.parse
        decoded_url = urllib.parse.unquote(url)
        
        page_data = orchestrator.get_page_for_llm(decoded_url)
        
        if not page_data:
            raise HTTPException(status_code=404, detail="Page not found")
        
        # Format for LLM
        llm_content = {
            "instruction": "Use this content for generating summaries, notes, or mind maps",
            "content": {
                "title": page_data["title"],
                "main_content": page_data["content"],
                "structure": {
                    "headings": page_data["headings"],
                    "content_type": page_data["study_metadata"]["content_type"],
                    "complexity": page_data["study_metadata"]["complexity_score"],
                    "reading_time": page_data["study_metadata"]["reading_time"]
                },
                "context": {
                    "related_pages": page_data["relationships"]["related_pages"],
                    "key_topics": page_data["study_metadata"]["key_topics"]
                }
            },
            "suggestions": {
                "study_approach": _get_study_approach(page_data["study_metadata"]),
                "focus_areas": page_data["headings"][:3],
                "difficulty_level": _assess_difficulty(page_data["study_metadata"])
            }
        }
        
        return llm_content
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM formatting failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Web scraper API is running"}

@app.get("/stats")
async def get_statistics():
    """Get scraping statistics"""
    try:
        # Get basic stats from MongoDB
        mongo_stats = orchestrator.mongo_storage.collection.estimated_document_count()
        
        return {
            "total_pages_scraped": mongo_stats,
            "database_status": "connected",
            "features": [
                "Dynamic content scraping with Playwright",
                "DOM structure analysis",
                "MongoDB storage for content",
                "Neo4j for relationships",
                "LLM-optimized data extraction"
            ]
        }
    
    except Exception as e:
        return {"error": f"Stats retrieval failed: {str(e)}"}

def _get_study_approach(metadata: Dict) -> str:
    """Suggest study approach based on content analysis"""
    content_type = metadata.get("content_type", "general")
    complexity = metadata.get("complexity_score", 0)
    
    if content_type == "tutorial":
        return "hands-on practice with step-by-step approach"
    elif content_type == "documentation":
        return "reference-based learning with examples"
    elif content_type == "research":
        return "analytical reading with note-taking"
    elif complexity > 5:
        return "detailed study with concept mapping"
    else:
        return "general reading with summary creation"

def _assess_difficulty(metadata: Dict) -> str:
    """Assess content difficulty for LLM processing hints"""
    complexity = metadata.get("complexity_score", 0)
    reading_time = metadata.get("reading_time", 0)
    
    if complexity < 2 and reading_time < 5:
        return "beginner"
    elif complexity < 5 and reading_time < 15:
        return "intermediate"
    else:
        return "advanced"

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    orchestrator.close_connections()

# Run the API
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)