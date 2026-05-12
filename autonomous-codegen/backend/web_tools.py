"""
Web access tools - search and fetch
"""
import httpx
import asyncio
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


async def web_search(query: str, num_results: int = 5) -> dict:
    """Search the web using DuckDuckGo"""
    try:
        from duckduckgo_search import DDGS

        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=num_results,
                    safesearch='off'
                ))
            return results

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _search)

        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")
            })

        return {
            "success": True,
            "query": query,
            "results": formatted
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


async def web_fetch(url: str, extract_text: bool = True) -> dict:
    """Fetch content from a URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AutonomousCodeGen/1.0)"
        }

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            raw_content = response.text

        if extract_text and "html" in content_type:
            try:
                import trafilatura
                text = trafilatura.extract(raw_content)
                if text:
                    # Limit size
                    content = text[:8000]
                else:
                    content = _basic_html_extract(raw_content)[:8000]
            except Exception:
                content = _basic_html_extract(raw_content)[:8000]
        else:
            content = raw_content[:8000]

        return {
            "success": True,
            "url": url,
            "content": content,
            "content_type": content_type
        }
    except httpx.TimeoutException:
        return {"success": False, "error": "Request timed out", "url": url}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}", "url": url}
    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return {"success": False, "error": str(e), "url": url}


def _basic_html_extract(html: str) -> str:
    """Basic HTML text extraction fallback"""
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    # Remove tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Clean whitespace
    html = re.sub(r'\s+', ' ', html)
    return html.strip()
