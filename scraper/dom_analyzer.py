from bs4 import BeautifulSoup
from typing import Dict, List
import hashlib

class DOMAnalyzer:
    def __init__(self):
        pass
    
    def analyze_structure(self, html: str) -> Dict:
        """Analyze DOM structure and create tree representation"""
        soup = BeautifulSoup(html, 'lxml')
        
        return {
            "tree": self._build_dom_tree(soup.body if soup.body else soup),
            "statistics": self._get_dom_statistics(soup),
            "semantic_structure": self._analyze_semantic_structure(soup),
            "content_blocks": self._identify_content_blocks(soup)
        }
    
    def _build_dom_tree(self, element, depth=0, max_depth=5) -> Dict:
        """Build hierarchical DOM tree structure"""
        if depth > max_depth or not element or not hasattr(element, 'name'):
            return {}
        
        node = {
            "tag": element.name if element.name else "text",
            "id": element.get('id', ''),
            "classes": element.get('class', []),
            "text_content": element.get_text()[:100] if element.get_text() else "",
            "children": [],
            "attributes": dict(element.attrs) if hasattr(element, 'attrs') else {},
            "depth": depth,
            "node_id": hashlib.md5(str(element)[:500].encode()).hexdigest()[:8]
        }
        
        # Add children (limit to prevent huge trees)
        if hasattr(element, 'children') and depth < max_depth:
            child_count = 0
            for child in element.children:
                if child_count >= 10:  # Limit children per node
                    break
                if hasattr(child, 'name') and child.name:
                    child_node = self._build_dom_tree(child, depth + 1, max_depth)
                    if child_node:
                        node["children"].append(child_node)
                        child_count += 1
        
        return node
    
    def _get_dom_statistics(self, soup: BeautifulSoup) -> Dict:
        """Get DOM statistics for analysis"""
        all_tags = soup.find_all()
        tag_counts = {}
        
        for tag in all_tags:
            tag_name = tag.name
            tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1
        
        return {
            "total_elements": len(all_tags),
            "tag_distribution": tag_counts,
            "max_depth": self._calculate_max_depth(soup),
            "text_content_ratio": self._calculate_text_ratio(soup)
        }
    
    def _analyze_semantic_structure(self, soup: BeautifulSoup) -> Dict:
        """Analyze semantic HTML structure"""
        semantic_tags = ['header', 'nav', 'main', 'article', 'section', 'aside', 'footer']
        semantic_elements = {}
        
        for tag in semantic_tags:
            elements = soup.find_all(tag)
            semantic_elements[tag] = len(elements)
        
        return {
            "semantic_elements": semantic_elements,
            "has_semantic_structure": sum(semantic_elements.values()) > 0,
            "content_hierarchy": self._analyze_heading_hierarchy(soup)
        }
    
    def _identify_content_blocks(self, soup: BeautifulSoup) -> List[Dict]:
        """Identify main content blocks for LLM processing"""
        content_blocks = []
        
        # Look for common content containers
        selectors = ['article', 'main', '.content', '#content', '.post', '.entry']
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                if elem.get_text(strip=True):
                    content_blocks.append({
                        "selector": selector,
                        "tag": elem.name,
                        "text_length": len(elem.get_text()),
                        "element_id": elem.get('id', ''),
                        "classes": elem.get('class', []),
                        "priority": self._calculate_content_priority(elem)
                    })
        
        return sorted(content_blocks, key=lambda x: x['priority'], reverse=True)[:5]
    
    def _calculate_max_depth(self, soup: BeautifulSoup) -> int:
        """Calculate maximum DOM depth"""
        def get_depth(element, current_depth=0):
            if not hasattr(element, 'children'):
                return current_depth
            
            max_child_depth = current_depth
            for child in element.children:
                if hasattr(child, 'name') and child.name:
                    depth = get_depth(child, current_depth + 1)
                    max_child_depth = max(max_child_depth, depth)
            
            return max_child_depth
        
        return get_depth(soup)
    
    def _calculate_text_ratio(self, soup: BeautifulSoup) -> float:
        """Calculate ratio of text content to HTML tags"""
        text_length = len(soup.get_text())
        html_length = len(str(soup))
        return text_length / html_length if html_length > 0 else 0
    
    def _analyze_heading_hierarchy(self, soup: BeautifulSoup) -> List[Dict]:
        """Analyze heading structure for content organization"""
        headings = []
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                headings.append({
                    "level": i,
                    "text": heading.get_text().strip(),
                    "position": len(headings)
                })
        return headings
    
    def _calculate_content_priority(self, element) -> int:
        """Calculate priority score for content blocks"""
        score = 0
        text_length = len(element.get_text())
        
        # Text length scoring
        score += min(text_length // 100, 10)
        
        # Semantic tag bonus
        if element.name in ['article', 'main']:
            score += 5
        elif element.name in ['section', 'div']:
            score += 2
        
        # Class/ID based scoring
        classes = element.get('class', [])
        element_id = element.get('id', '')
        
        content_indicators = ['content', 'article', 'post', 'main', 'body']
        for indicator in content_indicators:
            if any(indicator in str(c).lower() for c in classes):
                score += 3
            if indicator in element_id.lower():
                score += 3
        
        return score