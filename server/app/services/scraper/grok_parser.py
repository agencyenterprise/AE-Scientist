"""
Grok Parser Service.

Scrapes Grok share pages with Playwright to extract title and messages.
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


class GrokParserService:
    """Service for parsing Grok conversations from share URLs."""

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

    def _clean_content(self, text: str) -> str:
        lines = [ln.rstrip("\r") for ln in text.splitlines()]
        terminal_substrings = (
            "sign in to continue conversation",
            "failed to initialize session",
            "making sure you're human",
            "fast",
            "grok 4 heavy",
            "completed",
        )
        filtered: list[str] = []
        for raw in lines:
            low = raw.strip().lower()
            if low in {"skip to content"}:
                continue
            if raw.strip() == "File":
                continue
            if any(marker in low for marker in terminal_substrings):
                continue
            # Drop obvious UI-only lines seen around expandable sections
            if low in {
                "text",
                "collapse",
                "wrap",
                "copy",
                "show inline",
                "show more",
                "expand",
                "read more",
                "continue reading",
            }:
                continue
            filtered.append(raw)
        return "\n".join(filtered).strip()

    async def _auto_scroll(self, page: Page) -> None:
        try:
            # Body-level scroll (reduced passes)
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

            # Scroll main container if present (reduced passes)
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
            max_ms = 3000  # hard cap to avoid long scans
            for _ in range(2):
                clicked = False
                for label in labels:
                    # Restrict search to main; avoid expensive :has-text on the whole document
                    selectors = [
                        f"main button:has-text('{label}')",
                        f"main [role=button]:has-text('{label}')",
                        f"main a:has-text('{label}')",
                    ]
                    for sel in selectors:
                        try:
                            els = await page.query_selector_all(sel)
                            for el in els or []:
                                try:
                                    if await el.is_visible():
                                        await el.click()
                                        clicked = True
                                except Exception:
                                    continue
                        except Exception:
                            continue
                    # time budget guard
                    try:
                        now_ms = await page.evaluate("Date.now()")
                        if isinstance(now_ms, (int, float)) and isinstance(start_ms, (int, float)):
                            if (now_ms - start_ms) > max_ms:
                                return
                    except Exception:
                        pass
                if not clicked:
                    break
                # brief pause to allow DOM to update before next sweep
                await page.wait_for_timeout(150)
        except Exception:
            return

    async def _get_content_signature(self, page: Page) -> tuple[int, int]:
        try:
            res = await page.evaluate(
                """
                (() => {
                  const nodes = Array.from(
                    document.querySelectorAll(
                      '.prose, [class*="prose"], .markdown, [class*="markdown"], .whitespace-pre-wrap, [data-message-content]'
                    )
                  );
                  const text = nodes.map(n => (n.innerText||'').trim()).filter(Boolean);
                  const total = text.reduce((acc, t) => acc + t.length, 0);
                  return [text.length, total];
                })()
                """
            )
            if (
                isinstance(res := res, (list, tuple))
                and len(res) == 2
                and isinstance(res[0], int)
                and isinstance(res[1], int)
            ):
                return int(res[0]), int(res[1])
        except Exception:
            pass
        return (0, 0)

    async def _settle_content(
        self, page: Page, max_wait_ms: int = 2000, step_ms: int = 150
    ) -> None:
        try:
            prev = await self._get_content_signature(page)
            elapsed = 0
            stable = 0
            while elapsed < max_wait_ms:
                await page.wait_for_timeout(step_ms)
                elapsed += step_ms
                curr = await self._get_content_signature(page)
                if curr == prev:
                    stable += 1
                else:
                    stable = 0
                prev = curr
                if stable >= 2:
                    break
        except Exception:
            return

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

    def _extract_messages_from_body_text(self, body_text: str) -> List[ImportedChatMessage]:
        """Fallback: parse conversation from plain body text when DOM selectors fail.

        Recognizes simple role markers like 'You said:' and 'Grok said:' (also
        'Assistant:' and 'ChatGPT said:').
        """
        lines = [line.strip() for line in body_text.splitlines()]
        role_markers = {
            "you said:": "user",
            "user query:": "user",
            "grok said:": "assistant",
            "assistant:": "assistant",
            "chatgpt said:": "assistant",
        }
        terminal_markers = (
            "sign in to continue conversation",
            "failed to initialize session",
            "making sure you're human",
        )

        current_role: str | None = None
        buffer: List[str] = []
        parsed: List[ImportedChatMessage] = []

        def _flush() -> None:
            nonlocal buffer, current_role, parsed
            content = "\n".join([segment for segment in buffer if segment])
            content_stripped = content.strip()
            if current_role and content_stripped:
                parsed.append(ImportedChatMessage(role=current_role, content=content_stripped))
            buffer = []

        trigger_user_starts = (
            "please ",
            "can you",
            "could you",
            "do ",
            "and do ",
        )

        i = 0
        while i < len(lines):
            raw = lines[i]
            low = raw.lower()

            # Switch role when encountering markers (substring match for robustness)
            if any(marker in low for marker in role_markers):
                _flush()
                for marker, role in role_markers.items():
                    if marker in low:
                        current_role = role
                        break
                i += 1
                continue

            # Skip obvious UI noise and keep scanning
            if low in {"sign up", "sign in", "skip to content"} or raw == "File":
                i += 1
                continue

            # Ignore terminal UI/auth markers but do not stop parsing
            if any(marker in low for marker in terminal_markers):
                i += 1
                continue

            # Detect the specific two-line user request block and splice it out
            if low.strip() == "please increase scale":
                j = i + 1
                # advance to next non-empty line
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    next_low = lines[j].strip().lower()
                    if next_low == (
                        "and do anything else to get meaningful real results you can without me having to provide anything more"
                    ):
                        _flush()
                        user_block = raw + "\n\n" + lines[j]
                        parsed.append(ImportedChatMessage(role="user", content=user_block.strip()))
                        i = j + 1
                        continue

            # Heuristic: plain user requests without explicit markers
            if current_role != "user" and any(low.startswith(ts) for ts in trigger_user_starts):
                _flush()
                current_role = "user"

            if current_role is not None:
                buffer.append(raw)
            i += 1

        _flush()

        # Filter noise and ensure minimum messages
        parsed_filtered = self._filter_messages(messages=parsed)
        return parsed_filtered

    async def _extract_conversation_data(self, page: Page, url: str) -> ImportedChat:
        await page.wait_for_load_state("load")
        await page.wait_for_timeout(1500)
        try:
            await page.wait_for_selector("main", timeout=15000)
        except Exception:
            pass

        # Ensure lazy/expandable content is visible
        await self._auto_scroll(page)
        await self._expand_collapsibles(page)
        await self._auto_scroll(page)
        await self._settle_content(page)

        title = "Untitled Conversation"
        try:
            title_tag = await page.query_selector("title")
            if title_tag:
                title_candidate = (await title_tag.inner_text()).strip()
                if title_candidate and title_candidate.lower() not in ["grok"]:
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
                        and low not in ["grok"]
                        and not t.startswith("We use")
                    ):
                        title = t
                        break
            except Exception:
                pass

        message_selectors = [
            # Attribute-based roles (preferred)
            "main [data-message-author-role]",
            "article [data-message-author-role]",
            "[data-message-author-role]",
            # Test IDs commonly used for messages
            'main [data-testid*="message"]',
            'main [data-testid*="Message"]',
            # ARIA roles and semantic containers
            'main [role="article"]',
            "main article",
            "article",
            # Class-based fallbacks for common message/content wrappers
            'main [class*="message"]',
            'main [class*="Message"]',
            'main [class*="whitespace-pre-wrap"]',
            'main [class*="prose"]',
            'main [class*="markdown"]',
        ]

        messages: List[ImportedChatMessage] = []
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

                        # Prefer message content root and aggregate unique child blocks in order
                        content_root = await el.query_selector("[data-message-content]")
                        if not content_root:
                            content_root = el
                        blocks = await content_root.query_selector_all(
                            'p, li, .whitespace-pre-wrap, h1, h2, h3, h4, pre, code, [data-testid*="code" i], [data-testid*="markdown" i]'
                        )
                        texts: list[str] = []
                        seen_norm: set[str] = set()
                        if blocks:
                            for b in blocks:
                                try:
                                    t = (await b.inner_text()).strip()
                                except Exception:
                                    continue
                                t_clean = self._clean_content(t)
                                if not t_clean:
                                    continue
                                norm = " ".join(t_clean.split())
                                if norm in seen_norm:
                                    continue
                                seen_norm.add(norm)
                                texts.append(t_clean)
                            text_md = "\n\n".join(texts).strip()
                        else:
                            text_md = self._clean_content((await el.inner_text()).strip())

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
            try:
                body_text = await page.inner_text("body")
            except Exception:
                body_text = ""
            text_messages = self._extract_messages_from_body_text(body_text=body_text)
            if text_messages and len(text_messages) >= 2:
                messages = text_messages
            else:
                # Treat missing messages as not found to avoid retries for deleted/invalid shares
                raise ChatNotFound("Grok conversation not found")

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
                    raise ChatNotFound("Grok conversation not found")
                raise ValueError(f"Failed to load page: HTTP {status or 'No response'}")
            await page.wait_for_timeout(1000)
            try:
                await page.wait_for_selector("main", timeout=15000)
            except Exception:
                pass
            return await self._extract_conversation_data(page=page, url=url)
        finally:
            await context.close()

    async def parse_conversation(self, url: str) -> ParseResult:
        logger.debug(f"Starting Grok conversation parsing for URL: {url}")
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
            success=False, error="Failed to parse Grok conversation with all browsers"
        )
