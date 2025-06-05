from pymongo import MongoClient
from typing import Dict, List, Optional
import datetime
from config.settings import settings

class MongoStorage:
    def __init__(self):
        self.client = MongoClient(settings.database.mongo_uri)
        self.db = self.client[settings.database.mongo_db]
        self.collection = self.db.scraped_pages
        self._create_indexes()
    
    def _create_indexes(self):
        """Create indexes for better query performance"""
        self.collection.create_index("url", unique=True)
        self.collection.create_index("domain")
        self.collection.create_index("timestamp")
        self.collection.create_index("content.metadata.title")
    
    def store_page_data(self, url: str, extracted_data: Dict, dom_structure: Dict) -> str:
        """Store complete page data optimized for LLM consumption"""
        document = {
            "url": url,
            "domain": extracted_data["metadata"]["domain"],
            "timestamp": datetime.datetime.utcnow(),
            "title": extracted_data["metadata"]["title"],
            "description": extracted_data["metadata"]["description"],
            
            # LLM-optimized content structure
            "content": {
                "text_summary": extracted_data["text_summary"],
                "content_blocks": extracted_data["content"],
                "headings": extracted_data["metadata"]["headings"],
                "structure_info": extracted_data["structure"]
            },
            
            # Relationship data
            "relationships": {
                "internal_links": [link for link in extracted_data["links"] if link["internal"]],
                "external_links": [link for link in extracted_data["links"] if not link["internal"]],
                "images": extracted_data["images"]
            },
            
            # DOM analysis for advanced processing
            "dom_analysis": {
                "tree_structure": dom_structure["tree"],
                "statistics": dom_structure["statistics"],
                "semantic_structure": dom_structure["semantic_structure"],
                "content_blocks": dom_structure["content_blocks"]
            },
            
            # Study-friendly metadata
            "study_metadata": {
                "reading_time": self._estimate_reading_time(extracted_data["text_summary"]),
                "complexity_score": self._calculate_complexity_score(extracted_data),
                "content_type": self._identify_content_type(extracted_data),
                "key_topics": self._extract_key_topics(extracted_data)
            }
        }
        
        # Upsert document
        result = self.collection.replace_one(
            {"url": url}, 
            document, 
            upsert=True
        )
        
        return str(result.upserted_id or result.matched_count)
    
    def get_page_data(self, url: str) -> Optional[Dict]:
        """Retrieve page data by URL"""
        return self.collection.find_one({"url": url})
    
    def get_pages_by_domain(self, domain: str) -> List[Dict]:
        """Get all pages from a specific domain"""
        return list(self.collection.find({"domain": domain}))
    
    def search_pages(self, query: str, limit: int = 10) -> List[Dict]:
        """Search pages by content for LLM queries"""
        search_filter = {
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"content.text_summary": {"$regex": query, "$options": "i"}}
            ]
        }
        
        return list(self.collection.find(search_filter).limit(limit))
    
    def _estimate_reading_time(self, text: str) -> int:
        """Estimate reading time in minutes (250 words per minute)"""
        word_count = len(text.split())
        return max(1, word_count // 250)
    
    def _calculate_complexity_score(self, data: Dict) -> float:
        """Calculate content complexity for LLM processing hints"""
        score = 0.0
        
        # Text length factor
        text_length = len(data["text_summary"])
        score += min(text_length / 1000, 5.0)
        
        # Structure complexity
        content_blocks = len(data["content"])
        score += min(content_blocks / 10, 3.0)
        
        # Link density
        total_links = len(data["links"])
        score += min(total_links / 20, 2.0)
        
        return round(score, 2)
    
    def _identify_content_type(self, data: Dict) -> str:
        """Identify content type for LLM processing strategy"""
        title = data["metadata"]["title"].lower()
        text = data["text_summary"].lower()
        
        if any(word in title or word in text for word in ["tutorial", "guide", "how to"]):
            return "tutorial"
        elif any(word in title or word in text for word in ["news", "article", "report"]):
            return "article"
        elif any(word in title or word in text for word in ["documentation", "docs", "reference"]):
            return "documentation"
        elif any(word in title or word in text for word in ["blog", "post", "opinion"]):
            return "blog_post"
        else:
            return "general"
    
    def _extract_key_topics(self, data: Dict) -> List[str]:
        """Extract key topics for study organization"""
        # Simple keyword extraction from headings and title
        topics = set()
        
        # From title
        title_words = data["metadata"]["title"].split()
        topics.update([word.lower() for word in title_words if len(word) > 3])
        
        # From headings
        for heading in data["metadata"]["headings"]:
            heading_words = heading["text"].split()
            topics.update([word.lower() for word in heading_words if len(word) > 3])
        
        return list(topics)[:10]  # Limit to top 10 topics