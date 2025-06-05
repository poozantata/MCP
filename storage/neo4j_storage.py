from neo4j import GraphDatabase
from typing import Dict, List
from urllib.parse import urlparse
from config.settings import settings

class Neo4jStorage:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.database.neo4j_uri,
            auth=(settings.database.neo4j_user, settings.database.neo4j_password)
        )
        self._create_constraints()
    
    def _create_constraints(self):
        """Create constraints and indexes for better performance"""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT page_url IF NOT EXISTS FOR (p:Page) REQUIRE p.url IS UNIQUE")
                session.run("CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE")
                session.run("CREATE INDEX page_title IF NOT EXISTS FOR (p:Page) ON (p.title)")
            except Exception as e:
                pass  # Constraints might already exist
    
    def store_relationships(self, url: str, extracted_data: Dict, dom_structure: Dict):
        """Store page relationships and structure in Neo4j"""
        with self.driver.session() as session:
            # Create main page node
            self._create_page_node(session, url, extracted_data)
            
            # Create domain relationships
            self._create_domain_relationships(session, url, extracted_data)
            
            # Create content relationships
            self._create_content_relationships(session, url, extracted_data)
            
            # Create link relationships
            self._create_link_relationships(session, url, extracted_data["links"])
            
            # Create DOM structure relationships
            self._create_dom_relationships(session, url, dom_structure)
    
    def _create_page_node(self, session, url: str, data: Dict):
        """Create or update page node with LLM-friendly properties"""
        query = """
        MERGE (p:Page {url: $url})
        SET p.title = $title,
            p.description = $description,
            p.domain = $domain,
            p.content_type = $content_type,
            p.complexity_score = $complexity_score,
            p.reading_time = $reading_time,
            p.word_count = $word_count,
            p.last_scraped = datetime()
        """
        
        session.run(query, {
            "url": url,
            "title": data["metadata"]["title"],
            "description": data["metadata"]["description"],
            "domain": data["metadata"]["domain"],
            "content_type": self._identify_content_type(data),
            "complexity_score": self._calculate_complexity_score(data),
            "reading_time": len(data["text_summary"].split()) // 250,
            "word_count": len(data["text_summary"].split())
        })
    
    def _create_domain_relationships(self, session, url: str, data: Dict):
        """Create domain nodes and relationships"""
        domain = data["metadata"]["domain"]
        
        # Create domain node
        session.run("""
        MERGE (d:Domain {name: $domain})
        SET d.last_updated = datetime()
        """, {"domain": domain})
        
        # Link page to domain
        session.run("""
        MATCH (p:Page {url: $url})
        MATCH (d:Domain {name: $domain})
        MERGE (p)-[:BELONGS_TO]->(d)
        """, {"url": url, "domain": domain})
    
    def _create_content_relationships(self, session, url: str, data: Dict):
        """Create content structure relationships for LLM understanding"""
        # Create topic nodes from headings
        for i, heading in enumerate(data["metadata"]["headings"]):
            session.run("""
            MATCH (p:Page {url: $url})
            MERGE (h:Heading {text: $text, level: $level, page_url: $url})
            SET h.position = $position
            MERGE (p)-[:HAS_HEADING]->(h)
            """, {
                "url": url,
                "text": heading["text"],
                "level": heading["level"],
                "position": i
            })
        
        # Create content block relationships
        for i, block in enumerate(data["content"][:10]):  # Limit for performance
            session.run("""
            MATCH (p:Page {url: $url})
            MERGE (c:ContentBlock {text: $text, page_url: $url, position: $position})
            SET c.tag = $tag,
                c.length = $length
            MERGE (p)-[:HAS_CONTENT]->(c)
            """, {
                "url": url,
                "text": block["text"][:500],  # Truncate for storage
                "tag": block["tag"],
                "length": len(block["text"]),
                "position": i
            })
    
    def _create_link_relationships(self, session, url: str, links: List[Dict]):
        """Create link relationships for navigation understanding"""
        for link in links[:20]:  # Limit for performance
            target_url = link["url"]
            link_text = link["text"]
            is_internal = link["internal"]
            
            # Create target page node (minimal)
            session.run("""
            MERGE (target:Page {url: $target_url})
            SET target.discovered_via = $source_url
            """, {"target_url": target_url, "source_url": url})
            
            # Create relationship
            relationship_type = "LINKS_TO_INTERNAL" if is_internal else "LINKS_TO_EXTERNAL"
            session.run(f"""
            MATCH (source:Page {{url: $source_url}})
            MATCH (target:Page {{url: $target_url}})
            MERGE (source)-[r:{relationship_type}]->(target)
            SET r.link_text = $link_text,
                r.is_internal = $is_internal
            """, {
                "source_url": url,
                "target_url": target_url,
                "link_text": link_text,
                "is_internal": is_internal
            })
    
    def _create_dom_relationships(self, session, url: str, dom_structure: Dict):
        """Create DOM structure relationships for content hierarchy"""
        # Create semantic structure nodes
        semantic_elements = dom_structure["semantic_structure"]["semantic_elements"]
        for tag, count in semantic_elements.items():
            if count > 0:
                session.run("""
                MATCH (p:Page {url: $url})
                MERGE (s:SemanticElement {tag: $tag, page_url: $url})
                SET s.count = $count
                MERGE (p)-[:HAS_SEMANTIC_ELEMENT]->(s)
                """, {"url": url, "tag": tag, "count": count})
    
    def get_page_relationships(self, url: str) -> Dict:
        """Get all relationships for a page for LLM context"""
        with self.driver.session() as session:
            result = session.run("""
            MATCH (p:Page {url: $url})
            OPTIONAL MATCH (p)-[:LINKS_TO_INTERNAL]->(internal:Page)
            OPTIONAL MATCH (p)-[:LINKS_TO_EXTERNAL]->(external:Page)
            OPTIONAL MATCH (p)-[:HAS_HEADING]->(h:Heading)
            RETURN p, collect(DISTINCT internal.url) as internal_links,
                   collect(DISTINCT external.url) as external_links,
                   collect(DISTINCT {text: h.text, level: h.level}) as headings
            """, {"url": url})
            
            record = result.single()
            if record:
                return {
                    "page": dict(record["p"]),
                    "internal_links": record["internal_links"],
                    "external_links": record["external_links"],
                    "headings": record["headings"]
                }
            return {}
    
    def get_related_pages(self, url: str, limit: int = 5) -> List[Dict]:
        """Find related pages for LLM context and study suggestions"""
        with self.driver.session() as session:
            result = session.run("""
            MATCH (p:Page {url: $url})
            MATCH (p)-[:BELONGS_TO]->(d:Domain)
            MATCH (related:Page)-[:BELONGS_TO]->(d)
            WHERE related.url <> $url
            RETURN related.url as url, related.title as title, 
                   related.content_type as content_type,
                   related.complexity_score as complexity_score
            ORDER BY related.complexity_score DESC
            LIMIT $limit
            """, {"url": url, "limit": limit})
            
            return [dict(record) for record in result]
    
    def _identify_content_type(self, data: Dict) -> str:
        """Identify content type for graph relationships"""
        title = data["metadata"]["title"].lower()
        if "tutorial" in title or "guide" in title:
            return "tutorial"
        elif "documentation" in title or "docs" in title:
            return "documentation"
        elif "blog" in title or "article" in title:
            return "article"
        return "general"
    
    def _calculate_complexity_score(self, data: Dict) -> float:
        """Calculate complexity score for relationship weighting"""
        text_length = len(data["text_summary"])
        content_blocks = len(data["content"])
        return min(text_length / 1000 + content_blocks / 10, 10.0)
    
    def close(self):
        """Close database connection"""
        self.driver.close()