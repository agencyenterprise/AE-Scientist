"""
Claude Parser Service.

Scrapes Claude share pages with Playwright to extract title and messages.
"""

import logging
import random
from datetime import datetime
from typing import Dict, List

import html2text
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.models import (
    ImportedChat,
    ImportedChatMessage,
    ParseErrorResult,
    ParseResult,
    ParseSuccessResult,
)
from app.services.scraper.errors import ChatNotFound

logger = logging.getLogger(__name__)


class ClaudeParserService:
    """Service for parsing Claude conversations from share URLs."""

    def __init__(self) -> None:
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

        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.body_width = 0
        self.html_converter.protect_links = True
        self.html_converter.single_line_break = True

    def _get_random_config(self) -> Dict:
        return {
            "user_agent": random.choice(self.user_agents),
            "viewport": random.choice(self.viewports),
        }

    async def _apply_stealth_overrides(self, page: Page) -> None:
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
          if (parameter === 37445) { return 'Intel Inc.'; }
          if (parameter === 37446) { return 'Intel Iris OpenGL Engine'; }
          return getParameter.call(this, parameter);
        };
        """
        await page.add_init_script(stealth_js)

    async def _auto_scroll(self, page: Page) -> None:
        try:
            prev_h = await page.evaluate("document.body.scrollHeight")
            for _ in range(6):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                try:
                    await page.wait_for_function(
                        "s => document.body.scrollHeight > s", arg=prev_h, timeout=250
                    )
                except Exception:
                    break
                curr_h = await page.evaluate("document.body.scrollHeight")
                if curr_h == prev_h:
                    break
                prev_h = curr_h

            main_prev = await page.evaluate(
                "(() => { const m = document.querySelector('main'); return m ? m.scrollHeight : 0; })()"
            )
            for _ in range(3):
                await page.evaluate(
                    "(() => { const m = document.querySelector('main'); if (m) { m.scrollTop = m.scrollHeight; } })()"
                )
                try:
                    await page.wait_for_function(
                        "s => { const m = document.querySelector('main'); return m ? m.scrollHeight > s : true; }",
                        arg=main_prev,
                        timeout=250,
                    )
                except Exception:
                    break
                main_curr = await page.evaluate(
                    "(() => { const m = document.querySelector('main'); return m ? m.scrollHeight : 0; })()"
                )
                if main_curr == main_prev:
                    break
                main_prev = main_curr
        except Exception:
            return

    async def _expand_collapsibles(self, page: Page) -> None:
        try:
            labels = [
                "Show inline",
                "Show more",
                "Expand",
                "Read more",
                "Continue reading",
            ]
            start_ms = await page.evaluate("Date.now()")
            max_ms = 3000
            for _ in range(2):
                clicked = False
                for label in labels:
                    selectors = [
                        f"main button:has-text('{label}')",
                        f"main [role=button]:has-text('{label}')",
                        f"main a:has-text('{label}')",
                    ]
                    for sel in selectors:
                        try:
                            for el in await page.query_selector_all(sel):
                                try:
                                    if await el.is_visible():
                                        await el.click()
                                        clicked = True
                                except Exception:
                                    continue
                        except Exception:
                            continue
                    try:
                        now_ms = await page.evaluate("Date.now()")
                        if isinstance(now_ms, (int, float)) and isinstance(start_ms, (int, float)):
                            if (now_ms - start_ms) > max_ms:
                                return
                    except Exception:
                        pass
                if not clicked:
                    break
                await page.wait_for_timeout(150)
        except Exception:
            return

    async def _is_cloudflare_interstitial(self, page: Page) -> bool:
        """Detect common Cloudflare interstitial markers quickly."""
        try:
            title_text = await page.title()
            if title_text and "Just a moment" in title_text:
                return True
        except Exception:
            pass
        try:
            body_text = await page.inner_text("body")
            if body_text and (
                "Verify you are human" in body_text
                or "Performance & security by Cloudflare" in body_text
            ):
                return True
        except Exception:
            pass
        return False

    def _is_noise_text(self, text: str) -> bool:
        if not text:
            return True
        normalized = "\n".join(line.strip() for line in text.splitlines()).strip().lower()
        noise_exact = {
            "log in",
            "sign up",
            "cookie preferences",
            "share",
            "copy link",
            "new chat",
            "get the app",
            "upgrade",
        }
        if normalized in noise_exact:
            return True
        # Common cookie/privacy and banner text
        cookie_noise_substrings = (
            "we use cookies",
            "cookie settings",
            "customize cookie settings",
            "reject all cookies",
            "accept all cookies",
            "start your own conversation",
            "this is a copy of a chat",
            "performance & security by cloudflare",
            "verify you are human",
        )
        if any(s in normalized for s in cookie_noise_substrings):
            return True
        if len(normalized) <= 2:
            return True
        header_noise_prefixes = (
            "log in",
            "sign up",
            "sign in",
            "cookie",
            "search",
        )
        if (
            any(normalized.startswith(pfx) for pfx in header_noise_prefixes)
            and len(normalized) <= 30
        ):
            return True
        letters = [c for c in normalized if c.isalpha()]
        if len(letters) < 3:
            return True
        return False

    def _filter_messages(self, messages: List[ImportedChatMessage]) -> List[ImportedChatMessage]:
        filtered: List[ImportedChatMessage] = []
        for msg in messages:
            content_norm = (msg.content or "").strip()
            if not content_norm:
                continue
            if self._is_noise_text(text=content_norm):
                continue
            filtered.append(msg)
        return filtered

    async def _extract_conversation_data(self, page: Page, url: str) -> ImportedChat:
        await page.wait_for_load_state("load")
        await page.wait_for_timeout(600)
        # Try to ensure main is present but don't wait long
        try:
            await page.wait_for_selector("main", timeout=3000)
        except Exception:
            pass

        title = "Untitled Conversation"
        try:
            title_tag = await page.query_selector("title")
            if title_tag:
                title_candidate = (await title_tag.inner_text()).strip()
                if title_candidate and title_candidate.lower() not in ["claude", "anthropic"]:
                    title = title_candidate
        except Exception:
            pass

        if title == "Untitled Conversation":
            try:
                h1s = await page.query_selector_all("h1")
                for h in h1s:
                    t = (await h.inner_text()).strip()
                    low = t.lower()
                    if (
                        t
                        and len(t) > 3
                        and "cookie" not in low
                        and low not in ["claude", "anthropic"]
                        and not t.startswith("We use")
                    ):
                        title = t
                        break
            except Exception:
                pass

        # Ensure lazy/expandable content is visible (same fixes as Grok)
        await self._auto_scroll(page)
        await self._expand_collapsibles(page)
        await self._auto_scroll(page)

        # Preferred DOM-based extraction: explicit containers for user and assistant
        messages: List[ImportedChatMessage] = []
        try:
            dom_nodes = await page.query_selector_all(
                '[data-testid="user-message"], .font-claude-response'
            )
            if dom_nodes and len(dom_nodes) >= 2:
                for node in dom_nodes:
                    try:
                        data_testid = await node.get_attribute("data-testid")
                        role = "user" if data_testid == "user-message" else "assistant"
                        content_root = await node.query_selector("[data-message-content]")
                        if content_root:
                            html = (await content_root.inner_html()).strip()
                            text_md = self.html_converter.handle(html)
                        else:
                            # fallback to node HTML/text
                            html = (await node.inner_html()).strip()
                            text_md = (
                                self.html_converter.handle(html)
                                if html
                                else (await node.inner_text()).strip()
                            )
                        text_norm = (text_md or "").strip()
                        if text_norm:
                            messages.append(ImportedChatMessage(role=role, content=text_norm))
                    except Exception:
                        continue
                messages = self._filter_messages(messages=messages)
        except Exception:
            messages = []

        # Fallback structured selectors if DOM-first did not produce enough
        if not messages or len(messages) < 2:
            message_selectors = [
                "main [data-message-author-role]",
                "article [data-message-author-role]",
                "[data-message-author-role]",
                "main article",
                "article",
                "main [data-testid*=message]",
            ]

            messages = []
            for selector in message_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if not elements or len(elements) < 2:
                        continue
                    temp: List[ImportedChatMessage] = []
                    for idx, el in enumerate(elements):
                        try:
                            role_attr = await el.get_attribute("data-message-author-role")
                            role = (
                                "user"
                                if role_attr == "user"
                                else (
                                    "assistant"
                                    if role_attr
                                    else ("user" if (idx % 2 == 0) else "assistant")
                                )
                            )

                            content_div = await el.query_selector(
                                '.prose, [class*="prose"], .markdown, [class*="markdown"], .whitespace-pre-wrap, [data-message-content]'
                            )
                            if content_div:
                                html = (await content_div.inner_html()).strip()
                                text_md = self.html_converter.handle(html)
                            else:
                                text_md = (await el.inner_text()).strip()

                            if text_md and len(text_md) > 2:
                                temp.append(ImportedChatMessage(role=role, content=text_md))
                        except Exception:
                            continue

                    temp = self._filter_messages(messages=temp)
                    if temp and len(temp) >= 2:
                        messages = temp
                        break
                except Exception:
                    continue

        if not messages:
            raise ChatNotFound("Claude conversation not found")

        return ImportedChat(
            url=url,
            title=title,
            import_date=datetime.now().isoformat(),
            content=messages,
        )

    async def _try_with_browser(
        self, browser: Browser, url: str, _browser_name: str
    ) -> ImportedChat:
        config = self._get_random_config()
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
            response = await page.goto(url, wait_until="load", timeout=45000)
            if not response or response.status != 200:
                status = response.status if response else None
                if status == 404:
                    raise ChatNotFound("Claude conversation not found")
                raise ValueError(f"Failed to load page: HTTP {status or 'No response'}")
            # Fast-fail if Cloudflare interstitial is shown immediately; treat as not found for this provider
            try:
                if await self._is_cloudflare_interstitial(page):
                    raise ChatNotFound("Claude conversation not found")
            except ChatNotFound:
                raise
            except Exception:
                pass
            # Basic Cloudflare interstitial handling: loop a few times waiting and reloading
            try:
                title_text = await page.title()
                attempts = 0
                while attempts < 4 and title_text and "Just a moment" in title_text:
                    attempts += 1
                    await page.wait_for_timeout(7000)
                    try:
                        await page.reload(wait_until="domcontentloaded")
                    except Exception:
                        pass
                    try:
                        title_text = await page.title()
                    except Exception:
                        title_text = ""
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            try:
                await page.wait_for_selector("main", timeout=3000)
            except Exception:
                pass
            return await self._extract_conversation_data(page=page, url=url)
        finally:
            await context.close()

    async def parse_conversation(self, url: str) -> ParseResult:
        logger.debug(f"Starting Claude conversation parsing for URL: {url}")
        browsers = ["firefox", "chromium", "webkit"]
        async with async_playwright() as p:
            for browser_name in browsers:
                browser = await getattr(p, browser_name).launch(headless=True)
                try:
                    for attempt in range(1, 3):
                        try:
                            data = await self._try_with_browser(
                                browser=browser, url=url, _browser_name=browser_name
                            )
                            return ParseSuccessResult(success=True, data=data)
                        except ChatNotFound as e:
                            raise e
                        except Exception as e:
                            logger.debug(f"Attempt {attempt} failed with {browser_name}: {e}")
                            if attempt == 2:
                                break
                            continue
                except ChatNotFound:
                    raise
                except Exception as e:
                    logger.debug(f"Browser {browser_name} failed completely: {e}")
                finally:
                    await browser.close()
        return ParseErrorResult(
            success=False, error="Failed to parse Claude conversation with all browsers"
        )
