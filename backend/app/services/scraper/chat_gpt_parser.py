"""
ChatGPT Scraper for the AE Scientist

This module contains the ChatGPT conversation scraper using Playwright
for parsing and extracting content from ChatGPT share URLs.
"""

import logging
import random
from datetime import datetime
from typing import Dict, List

import html2text
from app.models import (
    ImportedChat,
    ImportedChatMessage,
    ParseErrorResult,
    ParseResult,
    ParseSuccessResult,
)
from app.services.scraper.errors import ChatNotFound
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


class ChatGPTParserService:
    """Service for parsing ChatGPT conversations from share URLs."""

    def __init__(self) -> None:
        """Initialize the parser service."""
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        self.viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1440, "height": 900},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1280, "height": 720},
        ]

        # Configure HTML to Markdown converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.body_width = 0  # Disable line wrapping
        self.html_converter.protect_links = True
        self.html_converter.single_line_break = True

    def _get_random_config(self) -> Dict:
        """Get random browser configuration for stealth."""
        return {
            "user_agent": random.choice(self.user_agents),
            "viewport": random.choice(self.viewports),
        }

    async def _apply_stealth_overrides(self, page: Page) -> None:
        """Apply stealth overrides to avoid bot detection."""
        stealth_js = """
        // Override webdriver detection
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Override WebGL
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter(parameter);
        };
        """
        await page.add_init_script(stealth_js)

    def _is_noise_text(self, text: str) -> bool:
        """Return True if the text is clearly UI noise and not a chat message."""
        if not text:
            return True

        normalized = "\n".join(line.strip() for line in text.splitlines()).strip().lower()

        # Obvious UI phrases often present on ChatGPT pages
        noise_exact = {
            "log in",
            "sign up",
            "sign up for free",
            "chatgpt can make mistakes. check important info. see cookie preferences.",
            "chatgpt can make mistakes. check important info.",
            "cookie preferences",
            "attach\nsearch\nstudy",
            "attach\nsearch",
            "search",
            "study",
            "copy link",
            "share",
            "new chat",
            "get the app",
            "upgrade",
        }

        if normalized in noise_exact:
            return True

        # Short, mostly navigation-y items
        if len(normalized) <= 2:
            return True

        # Lines that are just a couple of words commonly seen in headers
        header_noise_prefixes = (
            "log in",
            "sign up",
            "sign in",
            "openai",
            "cookie",
            "attach",
            "search",
            "study",
        )
        if any(normalized.startswith(pfx) for pfx in header_noise_prefixes):
            # Very short or purely UI text
            if len(normalized) <= 30:
                return True

        # Excessively blank-ish content
        letters = [c for c in normalized if c.isalpha()]
        if len(letters) < 3:
            return True

        return False

    def _filter_messages(self, messages: List[ImportedChatMessage]) -> List[ImportedChatMessage]:
        """Filter out messages that are clearly UI noise or empty."""
        filtered: List[ImportedChatMessage] = []
        for msg in messages:
            content_norm = (msg.content or "").strip()
            if not content_norm:
                continue
            if self._is_noise_text(content_norm):
                continue
            filtered.append(msg)
        return filtered

    async def _extract_conversation_data(self, page: Page, url: str) -> ImportedChat:
        """Extract conversation data from the ChatGPT page."""
        try:
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("load")
            # Give the app time to hydrate
            await page.wait_for_timeout(1500)
            # Wait for main content and likely message containers
            try:
                await page.wait_for_selector("main", timeout=15000)
            except Exception:
                pass
            try:
                await page.wait_for_selector(
                    "[data-message-author-role], main article", timeout=15000
                )
            except Exception:
                # Best effort; proceed with extraction attempts
                pass

            title = "Untitled Conversation"
            logger.debug(f"Starting title extraction for URL: {url}")

            # Try title tag first - most reliable
            try:
                title_tag = await page.query_selector("title")
                if title_tag:
                    title_tag_text = (await title_tag.inner_text()).strip()
                    logger.debug(f"Title tag content: '{title_tag_text}'")
                    if title_tag_text and title_tag_text.lower() not in ["chatgpt", "openai"]:
                        title = title_tag_text
                        logger.debug(f"Using title from title tag: '{title}'")
                    else:
                        logger.debug("Title tag content is generic, falling back to H1 elements")
            except Exception as e:
                logger.debug(f"Error getting title tag: {e}")

            # Only fall back to H1 elements if title tag didn't work
            if title == "Untitled Conversation":
                logger.debug("Falling back to H1 element extraction")
                try:
                    all_h1_elements = await page.query_selector_all("h1")
                    logger.debug(f"Found {len(all_h1_elements)} h1 elements on page")

                    for i, h1_elem in enumerate(all_h1_elements):
                        h1_text = (await h1_elem.inner_text()).strip()
                        logger.debug(f"H1 element {i}: '{h1_text}'")

                        # Skip obvious UI elements and use the first meaningful content H1
                        if (
                            h1_text
                            and len(h1_text) > 3
                            and "cookie" not in h1_text.lower()
                            and h1_text.lower() not in ["chatgpt", "openai"]
                            and not h1_text.startswith("We use")
                        ):
                            title = h1_text
                            logger.debug(f"Using H1 title: '{title}'")
                            break

                except Exception as e:
                    logger.debug(f"Error getting H1 elements: {e}")

            logger.debug(f"Final title selected: '{title}'")

            # Extract messages (prefer narrow, conversation-scoped selectors first)
            message_selectors = [
                "main [data-message-author-role]",
                "article [data-message-author-role]",
                "[data-message-author-role]",
                # As a guarded fallback, treat each article as a message container
                "main article",
                "article",
            ]

            messages = []
            for selector in message_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) >= 2:
                        temp_messages: List[ImportedChatMessage] = []
                        for element in elements:
                            try:
                                # Get role from data attribute or infer from structure
                                role_attr = await element.get_attribute("data-message-author-role")

                                if role_attr:
                                    role = "user" if role_attr == "user" else "assistant"
                                else:
                                    # Try to infer role from content or structure
                                    content_text = await element.inner_text()
                                    if not content_text or not content_text.strip():
                                        continue

                                    # Simple heuristic: alternate between user and assistant
                                    role = "user" if len(temp_messages) % 2 == 0 else "assistant"

                                # Extract clean content (avoid ChatGPT layout divs)
                                content_text = (await element.inner_text()).strip()

                                if content_text and len(content_text) > 10:
                                    # Look for the innermost content div to avoid layout wrappers
                                    content_div = await element.query_selector(
                                        '.whitespace-pre-wrap, [class*="whitespace-pre-wrap"], .prose, [class*="prose"], .markdown, [class*="markdown"], [data-message-content]'
                                    )

                                    if content_div:
                                        # Extract clean HTML from the content div and convert to markdown
                                        content_html = (await content_div.inner_html()).strip()
                                        markdown_content = self.html_converter.handle(content_html)
                                    else:
                                        # Fallback: use text content directly as markdown
                                        markdown_content = content_text

                                    temp_messages.append(
                                        ImportedChatMessage(
                                            role=role,
                                            content=markdown_content,
                                        )
                                    )

                            except Exception:
                                continue

                        # Filter out obvious UI noise
                        temp_messages = self._filter_messages(messages=temp_messages)

                        if temp_messages and len(temp_messages) >= 2:
                            messages = temp_messages
                            break

                except Exception:
                    continue

            if not messages:
                raise ValueError("No conversation messages found")

            return ImportedChat(
                url=url,
                title=title,
                import_date=datetime.now().isoformat(),
                content=messages,
            )

        except Exception as e:
            raise ValueError(f"Failed to extract conversation data: {str(e)}")

    async def _try_with_browser(
        self, browser: Browser, url: str, browser_name: str
    ) -> ImportedChat:
        """Try to parse the conversation with a specific browser."""
        logger.debug(f"Trying to parse with browser: {browser_name}")
        config = self._get_random_config()
        logger.debug(f"Using user agent: {config['user_agent'][:50]}...")
        logger.debug(f"Using viewport: {config['viewport']}")

        context: BrowserContext = await browser.new_context(
            user_agent=config["user_agent"],
            viewport=config["viewport"],
            locale="en-US",
            timezone_id="America/New_York",
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            },
        )

        try:
            page = await context.new_page()
            await self._apply_stealth_overrides(page=page)

            logger.debug(f"Navigating to URL: {url}")
            response = await page.goto(url, wait_until="load", timeout=45000)

            if not response or response.status != 200:
                status = response.status if response else None
                logger.debug(f"Page load failed: HTTP {status}")

                # For 404 errors, don't retry - the conversation no longer exists
                if status == 404:
                    raise ChatNotFound(
                        "ChatGPT conversation not found. The shared conversation may have been deleted or the link is invalid."
                    )

                raise ValueError(f"Failed to load page: HTTP {status or 'No response'}")

            logger.debug(f"Page loaded successfully with {browser_name}, status: {response.status}")

            # Allow hydration and wait for conversation elements
            await page.wait_for_timeout(1000)
            try:
                await page.wait_for_selector(
                    "[data-message-author-role], main article", timeout=15000
                )
            except Exception:
                logger.debug(
                    "Conversation elements did not appear within timeout; continuing anyway"
                )

            # Take a debug screenshot
            # await page.screenshot(path=f"debug_screenshot_{browser_name}.png")
            # logger.debug(f"Screenshot saved: debug_screenshot_{browser_name}.png")

            return await self._extract_conversation_data(page=page, url=url)

        finally:
            await context.close()

    async def parse_conversation(self, url: str, max_retries: int = 3) -> ParseResult:
        """
        Parse a ChatGPT conversation from a share URL.

        Args:
            url: The ChatGPT share URL to parse
            max_retries: Maximum number of retry attempts per browser

        Returns:
            ParseResult with success status and data or error
        """
        logger.debug(f"Starting conversation parsing for URL: {url}")
        browsers = [
            "firefox",
            "chromium",
            "webkit",
        ]  # Firefox first since it handles ChatGPT better

        async with async_playwright() as playwright:
            for browser_name in browsers:
                logger.debug(f"Trying browser: {browser_name}")
                browser = await getattr(playwright, browser_name).launch(headless=True)

                try:
                    for attempt in range(1, max_retries + 1):
                        try:
                            logger.debug(f"Attempt {attempt}/{max_retries} with {browser_name}")
                            conversation_data = await self._try_with_browser(
                                browser=browser, url=url, browser_name=browser_name
                            )
                            logger.debug(
                                f"Successfully parsed with {browser_name} on attempt {attempt}"
                            )
                            return ParseSuccessResult(success=True, data=conversation_data)

                        except ChatNotFound as e:
                            # 404 errors should bubble up immediately - don't retry
                            logger.debug("404 error detected - conversation no longer exists")
                            raise e
                        except Exception as e:
                            logger.debug(f"Attempt {attempt} failed with {browser_name}: {e}")

                            if attempt == max_retries:
                                # Last attempt with this browser failed
                                logger.debug(f"All attempts failed with {browser_name}")
                                break
                            continue

                except ChatNotFound as e:
                    # 404 errors should bubble up immediately - don't try other browsers
                    logger.debug("404 error detected - conversation no longer exists")
                    raise e
                except Exception as e:
                    logger.debug(f"Browser {browser_name} failed completely: {e}")
                    continue

                finally:
                    await browser.close()

        logger.debug("All browsers failed")
        return ParseErrorResult(
            success=False, error="Failed to parse conversation with all browsers"
        )
