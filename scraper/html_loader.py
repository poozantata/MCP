import asyncio
from playwright.async_api import async_playwright
from typing import Dict, Optional
import time
from config.settings import settings

class HTMLLoader:
    def __init__(self):
        self.browser = None
        self.context = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.scraping.headless
        )
        self.context = await self.browser.new_context(
            user_agent=settings.scraping.user_agent
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def load_page(self, url: str) -> Dict[str, str]:
        """Load HTML content from URL handling both static and dynamic sites"""
        for attempt in range(settings.scraping.max_retries):
            try:
                page = await self.context.new_page()
                await page.goto(url, timeout=settings.scraping.timeout)
                
                # Wait for body to load
                await page.wait_for_selector(
                    settings.scraping.wait_for_selector, 
                    timeout=10000
                )
                
                # Additional wait for dynamic content
                await page.wait_for_timeout(2000)
                
                html_content = await page.content()
                title = await page.title()
                url_final = page.url
                
                await page.close()
                
                return {
                    "html": html_content,
                    "title": title,
                    "url": url_final,
                    "timestamp": int(time.time())
                }
                
            except Exception as e:
                if attempt == settings.scraping.max_retries - 1:
                    raise Exception(f"Failed to load {url}: {str(e)}")
                await asyncio.sleep(settings.scraping.delay_between_requests)
        
        return None