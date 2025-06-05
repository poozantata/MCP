from bs4 import BeautifulSoup, Comment
from typing import Dict, List, Optional
import re
from urllib.parse import urljoin, urlparse
from config.settings import settings

class DataExtractor:
    def __init__(self):
        self.config = settings.extraction
    
    def extract_structured_data(self, html: str, url: str) -> Dict:
        """Extract structured data from HTML for LLM consumption"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove unwanted elements
        self._clean_html(soup)
        
        return {
            "content": self._extract_content(soup),
            "metadata": self._extract_metadata(soup, url),
            "structure": self._extract_structure(soup),
            "links": self._extract_links(soup, url),
            "images": self._extract_images(soup, url),
            "text_summary": self._extract_text_summary(soup)
        }
    
    def _clean_html(self, soup: BeautifulSoup):
        """Remove unwanted elements for cleaner extraction"""
        for selector in self.config.ignore_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Remove comments and scripts
        for element in soup(text=lambda text: isinstance(text, Comment)):
            element.extract()
    
    def _extract_content(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract main content blocks"""
        content_blocks = []
        
        for selector in self.config.content_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if len(text) >= self.config.min_text_length:
                    content_blocks.append({
                        "tag": elem.name,
                        "text": text,
                        "html": str(elem),
                        "attributes": dict(elem.attrs) if elem.attrs else {}
                    })
        
        return content_blocks
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract page metadata"""
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        
        return {
            "title": title.get_text().strip() if title else "",
            "description": meta_desc.get('content', '') if meta_desc else "",
            "url": url,
            "domain": urlparse(url).netloc,
            "headings": self._extract_headings(soup)
        }
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract heading hierarchy for structure"""
        headings = []
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                headings.append({
                    "level": i,
                    "text": heading.get_text().strip(),
                    "id": heading.get('id', '')
                })
        return headings
    
    def _extract_structure(self, soup: BeautifulSoup) -> Dict:
        """Extract DOM structure for relationships"""
        return {
            "sections": len(soup.find_all(['section', 'article', 'div'])),
            "paragraphs": len(soup.find_all('p')),
            "lists": len(soup.find_all(['ul', 'ol'])),
            "tables": len(soup.find_all('table')),
            "forms": len(soup.find_all('form'))
        }
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all links for relationship mapping"""
        links = []
        for link in soup.find_all('a', href=True):
            href = urljoin(base_url, link['href'])
            links.append({
                "url": href,
                "text": link.get_text().strip(),
                "internal": urlparse(href).netloc == urlparse(base_url).netloc
            })
        return links[:50]  # Limit for performance
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract images with context"""
        images = []
        for img in soup.find_all('img', src=True):
            images.append({
                "src": urljoin(base_url, img['src']),
                "alt": img.get('alt', ''),
                "caption": img.get('title', '')
            })
        return images[:20]  # Limit for performance
    
    def _extract_text_summary(self, soup: BeautifulSoup) -> str:
        """Extract clean text for LLM processing"""
        text = soup.get_text()
        # Clean whitespace and normalize
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:5000]  # Limit for token efficiency