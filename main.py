import asyncio
from typing import Dict, Optional,List
from scraper.html_loader import HTMLLoader
from scraper.data_extractor import DataExtractor
from scraper.dom_analyzer import DOMAnalyzer
from storage.mongo_storage import MongoStorage
# from storage.neo4j_storage import Neo4jStorage
from config.settings import settings

class WebScrapingOrchestrator:
    def __init__(self):
        self.data_extractor = DataExtractor()
        self.dom_analyzer = DOMAnalyzer()
        self.mongo_storage = MongoStorage()
        self.neo4j_storage = Neo4jStorage()
    
    async def process_url(self, url: str) -> Dict:
        """Complete pipeline to process a URL for LLM consumption"""
        try:
            print(f"Processing URL: {url}")
            
            # Step 1: Load HTML content
            async with HTMLLoader() as loader:
                html_data = await loader.load_page(url)
            
            if not html_data:
                return {"error": "Failed to load page"}
            
            print("✓ HTML loaded successfully")
            
            # Step 2: Extract structured data
            extracted_data = self.data_extractor.extract_structured_data(
                html_data["html"], 
                html_data["url"]
            )
            
            print("✓ Data extracted successfully")
            
            # Step 3: Analyze DOM structure
            dom_structure = self.dom_analyzer.analyze_structure(html_data["html"])
            
            print("✓ DOM structure analyzed")
            
            # Step 4: Store in MongoDB
            mongo_id = self.mongo_storage.store_page_data(
                html_data["url"], 
                extracted_data, 
                dom_structure
            )
            
            print("✓ Data stored in MongoDB")
            
            # Step 5: Store relationships in Neo4j
            # self.neo4j_storage.store_relationships(
            #     html_data["url"], 
            #     extracted_data, 
            #     dom_structure
            # )
            
            # print("✓ Relationships stored in Neo4j")
            
            # Return LLM-ready summary
            return {
                "success": True,
                "url": html_data["url"],
                "title": html_data["title"],
                "mongo_id": mongo_id,
                "summary": {
                    "content_blocks": len(extracted_data["content"]),
                    "text_length": len(extracted_data["text_summary"]),
                    "links_found": len(extracted_data["links"]),
                    "images_found": len(extracted_data["images"]),
                    "dom_depth": dom_structure["statistics"]["max_depth"],
                    "content_type": self._identify_content_type(extracted_data)
                },
                "llm_ready_data": {
                    "text_summary": extracted_data["text_summary"],
                    "key_headings": [h["text"] for h in extracted_data["metadata"]["headings"][:5]],
                    "main_topics": self._extract_main_topics(extracted_data),
                    "study_hints": self._generate_study_hints(extracted_data, dom_structure)
                }
            }
            
        except Exception as e:
            print(f"✗ Error processing {url}: {str(e)}")
            return {"error": str(e), "url": url}
    
    def get_page_for_llm(self, url: str) -> Optional[Dict]:
        """Retrieve page data optimized for LLM consumption"""
        # Get from MongoDB
        mongo_data = self.mongo_storage.get_page_data(url)
        if not mongo_data:
            return None
        
        # Get relationships from Neo4j
        neo4j_data = self.neo4j_storage.get_page_relationships(url)
        
        # Combine for LLM
        return {
            "content": mongo_data["content"]["text_summary"],
            "title": mongo_data["title"],
            "headings": [h["text"] for h in mongo_data["content"]["headings"]],
            "structure": mongo_data["study_metadata"],
            "relationships": {
                "related_pages": neo4j_data.get("internal_links", [])[:5],
                "external_references": neo4j_data.get("external_links", [])[:3]
            },
            "study_metadata": mongo_data["study_metadata"]
        }
    
    def search_for_llm(self, query: str, limit: int = 5) -> List[Dict]:
        """Search content for LLM context"""
        results = self.mongo_storage.search_pages(query, limit)
        
        llm_ready_results = []
        for result in results:
            llm_ready_results.append({
                "url": result["url"],
                "title": result["title"],
                "summary": result["content"]["text_summary"][:500],
                "content_type": result["study_metadata"]["content_type"],
                "complexity": result["study_metadata"]["complexity_score"],
                "key_topics": result["study_metadata"]["key_topics"][:5]
            })
        
        return llm_ready_results
    
    def _identify_content_type(self, data: Dict) -> str:
        """Identify content type for processing hints"""
        title = data["metadata"]["title"].lower()
        text = data["text_summary"].lower()
        
        if any(word in title for word in ["tutorial", "guide", "how to"]):
            return "tutorial"
        elif any(word in title for word in ["documentation", "docs", "api"]):
            return "documentation"
        elif any(word in title for word in ["blog", "article", "news"]):
            return "article"
        elif any(word in text for word in ["research", "study", "analysis"]):
            return "research"
        return "general"
    
    def _extract_main_topics(self, data: Dict) -> List[str]:
        """Extract main topics for LLM understanding"""
        topics = set()
        
        # From title
        title_words = [word for word in data["metadata"]["title"].split() if len(word) > 3]
        topics.update(title_words[:3])
        
        # From headings
        for heading in data["metadata"]["headings"][:3]:
            heading_words = [word for word in heading["text"].split() if len(word) > 3]
            topics.update(heading_words[:2])
        
        return list(topics)[:5]
    
    def _generate_study_hints(self, extracted_data: Dict, dom_structure: Dict) -> Dict:
        """Generate study hints for LLM processing"""
        return {
            "difficulty_level": "beginner" if len(extracted_data["text_summary"]) < 2000 else "intermediate",
            "estimated_study_time": f"{len(extracted_data['text_summary'].split()) // 250} minutes",
            "content_structure": "well_structured" if len(extracted_data["metadata"]["headings"]) > 3 else "basic",
            "has_examples": "code" in extracted_data["text_summary"].lower(),
            "interactive_elements": dom_structure["statistics"]["tag_distribution"].get("form", 0) > 0
        }
    
    def close_connections(self):
        """Close all database connections"""
        self.neo4j_storage.close()

# Main execution function
async def main():
    orchestrator = WebScrapingOrchestrator()
    
    # Example usage
    test_url = "https://en.wikipedia.org/wiki/Virat_Kohli"
    result = await orchestrator.process_url(test_url)
    print(f"Processing result: {result}")
    
    # Clean up
    orchestrator.close_connections()

if __name__ == "__main__":
    asyncio.run(main())
