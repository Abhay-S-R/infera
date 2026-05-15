"""
ASCENT URL Scraper Tool — extracts text content from web pages.
Used by the Scout agent to get full article content from search result URLs.

Dev 2 owns this file.
"""
import httpx
from bs4 import BeautifulSoup


async def scrape_url(url: str, max_chars: int = 5000) -> str:
    """
    Scrape text content from a URL.

    Args:
        url: The URL to scrape
        max_chars: Maximum characters to return (prevents context blowup)

    Returns:
        Extracted text content, truncated to max_chars
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()

        # Extract text from article or main content, fall back to body
        content_element = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_="content")
            or soup.find("body")
        )

        if content_element is None:
            return ""

        text = content_element.get_text(separator="\n", strip=True)

        # Clean up: collapse multiple newlines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        return clean_text[:max_chars]

    except httpx.HTTPStatusError as e:
        print(f"[url_scraper] HTTP error for {url}: {e.response.status_code}")
        return ""

    except Exception as e:
        print(f"[url_scraper] Error scraping {url}: {e}")
        return ""
