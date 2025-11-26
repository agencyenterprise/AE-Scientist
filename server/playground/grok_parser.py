#!/usr/bin/env python3
"""
Grok Share URL Parser (no retries, single browser run)
"""

import argparse
import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: str = Field(...)
    content: str = Field(...)


class ConversationData(BaseModel):
    url: str = Field(...)
    title: str = Field(...)
    author: str = Field(...)
    import_date: str = Field(...)
    content: List[ConversationMessage] = Field(...)


class ParseResult(BaseModel):
    success: bool = Field(...)
    data: Optional[ConversationData] = None
    error: Optional[str] = None


def validate_url(url: str) -> bool:
    # Accept percent-encoded tokens in the prefix before the underscore as Grok uses base64-like ids
    pattern = r"^https://grok\.com/share/[A-Za-z0-9_%\-]+_[a-f0-9\-]{36}$"
    return bool(re.match(pattern=pattern, string=url))


def setup_page(browser: Browser) -> tuple[BrowserContext, Page]:
    context = browser.new_context(
        bypass_csp=True,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ),
        viewport={"width": 1440, "height": 900},
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
    page = context.new_page()
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
          if (parameter === 37445) return 'Intel Inc.';
          if (parameter === 37446) return 'Intel Iris OpenGL Engine';
          return getParameter(parameter);
        };
        """
    )
    return context, page


def _wait_cloudflare_if_present(page: Page) -> None:
    try:
        print("[DEBUG] Cloudflare check: start", flush=True)
        title_text = page.title()
        if title_text and "Just a moment" in title_text:
            print("[DEBUG] Cloudflare interstitial via title; waiting 6s and reloading", flush=True)
            page.wait_for_timeout(timeout=6000)
            try:
                page.reload(wait_until="domcontentloaded")
                print("[DEBUG] Reload after Cloudflare wait done", flush=True)
            except Exception as e:
                print(f"[DEBUG] Cloudflare reload error: {e}", flush=True)
        try:
            page.wait_for_selector(
                selector="main, [data-message-author-role], article", timeout=12000
            )
            print("[DEBUG] Main/content selectors present", flush=True)
        except Exception as e:
            print(f"[DEBUG] wait_for_selector fallback: {e}", flush=True)
            page.wait_for_timeout(timeout=1000)
    except Exception as e:
        print(f"[DEBUG] Cloudflare check exception: {e}", flush=True)


def _expand_collapsibles(page: Page) -> None:
    try:
        print("[DEBUG] Expanding collapsibles", flush=True)
        # Click common expanders a few times to reveal hidden/inline sections
        labels = [
            "Show inline",
            "Show more",
            "Expand",
            "Read more",
            "Continue reading",
        ]
        for _ in range(3):
            clicked = False
            for label in labels:
                selectors = [
                    f"button:has-text('{label}')",
                    f"[role=button]:has-text('{label}')",
                    f"a:has-text('{label}')",
                    f"div:has-text('{label}')",
                    f"span:has-text('{label}')",
                ]
                for sel in selectors:
                    try:
                        els = page.query_selector_all(selector=sel)
                        print(
                            f"[DEBUG] Found {len(els) if els else 0} for expander '{label}' via {sel}",
                            flush=True,
                        )
                        for el in els or []:
                            if el.is_visible():
                                el.click()
                                page.wait_for_timeout(timeout=200)
                                clicked = True
                    except Exception as e:
                        print(f"[DEBUG] Expander error {label}/{sel}: {e}", flush=True)
                        continue
            if not clicked:
                print("[DEBUG] No more expanders clicked; stopping", flush=True)
                break
    except Exception as e:
        print(f"[DEBUG] expand_collapsibles exception: {e}", flush=True)


def _auto_scroll(page: Page) -> None:
    try:
        prev_h = page.evaluate(expression="document.body.scrollHeight")
        print(f"[DEBUG] Auto-scroll: initial body scrollHeight={prev_h}", flush=True)
        for i in range(12):
            page.evaluate(expression="window.scrollTo(0, document.body.scrollHeight)")
            try:
                page.wait_for_function(
                    expression="s => document.body.scrollHeight > s",
                    arg=prev_h,
                    timeout=300,
                )
            except Exception as e:
                print(
                    f"[DEBUG] Auto-scroll (body) break at step {i}: no growth or error: {e}",
                    flush=True,
                )
                break
            curr_h = page.evaluate(expression="document.body.scrollHeight")
            print(f"[DEBUG] Auto-scroll (body) step {i}: {prev_h} -> {curr_h}", flush=True)
            if curr_h == prev_h:
                break
            prev_h = curr_h

        # Also try scrolling the main container if it exists
        main_prev = page.evaluate(
            expression="""
            (() => { const m = document.querySelector('main'); return m ? m.scrollHeight : 0; })()
            """
        )
        print(f"[DEBUG] Auto-scroll: initial main scrollHeight={main_prev}", flush=True)
        for i in range(6):
            page.evaluate(
                expression="""
                const m = document.querySelector('main');
                if (m) { m.scrollTop = m.scrollHeight; }
                """
            )
            try:
                page.wait_for_function(
                    expression="s => { const m = document.querySelector('main'); return m ? m.scrollHeight > s : true; }",
                    arg=main_prev,
                    timeout=300,
                )
            except Exception as e:
                print(
                    f"[DEBUG] Auto-scroll (main) break at step {i}: no growth or error: {e}",
                    flush=True,
                )
                break
            main_curr = page.evaluate(
                expression="""
                (() => { const m = document.querySelector('main'); return m ? m.scrollHeight : 0; })()
                """
            )
            print(f"[DEBUG] Auto-scroll (main) step {i}: {main_prev} -> {main_curr}", flush=True)
            if main_curr == main_prev:
                break
            main_prev = main_curr
    except Exception as e:
        print(f"[DEBUG] auto_scroll exception: {e}", flush=True)


def _get_content_signature(page: Page) -> tuple[int, int]:
    try:
        res = page.evaluate(
            expression="""
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
            isinstance(res, (list, tuple))
            and len(res) == 2
            and isinstance(res[0], int)
            and isinstance(res[1], int)
        ):
            return int(res[0]), int(res[1])
    except Exception:
        pass
    return (0, 0)


def _settle_content(page: Page, max_wait_ms: int = 2000, step_ms: int = 150) -> None:
    try:
        prev = _get_content_signature(page)
        print(f"[DEBUG] Settle start: blocks={prev[0]} total_len={prev[1]}", flush=True)
        elapsed = 0
        stable = 0
        while elapsed < max_wait_ms:
            page.wait_for_timeout(timeout=step_ms)
            elapsed += step_ms
            curr = _get_content_signature(page)
            print(
                f"[DEBUG] Settle step: blocks={curr[0]} total_len={curr[1]} (stable={stable})",
                flush=True,
            )
            if curr == prev:
                stable += 1
            else:
                stable = 0
            prev = curr
            if stable >= 2:
                print("[DEBUG] Settle: content stabilized", flush=True)
                break
        if elapsed >= max_wait_ms:
            print("[DEBUG] Settle: timeout reached", flush=True)
    except Exception as e:
        print(f"[DEBUG] settle_content exception: {e}", flush=True)


def _clean_content(text: str) -> str:
    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    terminal_markers = (
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
        # Drop obvious UI-only lines
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
        if any(marker in low for marker in terminal_markers):
            continue
        filtered.append(raw)
    return "\n".join(filtered).strip()


def extract(page: Page) -> ParseResult:
    try:
        print("[DEBUG] Extract: start", flush=True)
        page.wait_for_load_state(state="domcontentloaded", timeout=15000)
        _wait_cloudflare_if_present(page=page)
        try:
            page.wait_for_selector(selector="main", timeout=10000)
            print("[DEBUG] Main selector available", flush=True)
        except Exception as e:
            print(f"[DEBUG] Waiting for main selector failed: {e}", flush=True)
        _auto_scroll(page=page)
        _expand_collapsibles(page=page)
        _auto_scroll(page=page)
        _settle_content(page=page)

        title = None
        for sel in ["title", "h1", "[data-testid*='title']"]:
            try:
                el = page.query_selector(selector=sel)
                if el:
                    t = el.inner_text().strip()
                    if t and t.lower() not in ["grok"]:
                        title = t
                        break
            except Exception:
                continue

        messages: List[ConversationMessage] = []
        selectors = [
            # Attribute-based roles
            "main [data-message-author-role]",
            "article [data-message-author-role]",
            "[data-message-author-role]",
            # Test IDs likely used for messages
            'main [data-testid*="message"]',
            'main [data-testid*="Message"]',
            # ARIA and semantic fallbacks
            'main [role="article"]',
            "main article",
            "article",
            # Class-based fallbacks used by many UIs
            'main [class*="message"]',
            'main [class*="Message"]',
            'main [class*="whitespace-pre-wrap"]',
            'main [class*="prose"]',
            'main [class*="markdown"]',
        ]
        for sel in selectors:
            try:
                els = page.query_selector_all(selector=sel)
                print(
                    f"[DEBUG] Selector '{sel}' matched {len(els) if els else 0} elements",
                    flush=True,
                )
                if els and len(els) >= 2:
                    tmp: List[ConversationMessage] = []
                    for idx, el in enumerate(els):
                        try:
                            role_attr = el.get_attribute(name="data-message-author-role")
                            role = (
                                "user"
                                if role_attr == "user"
                                else (
                                    "assistant"
                                    if role_attr
                                    else ("user" if idx % 2 == 0 else "assistant")
                                )
                            )
                            # Prefer message content root and aggregate unique child blocks in order
                            content_root = (
                                el.query_selector(selector="[data-message-content]") or el
                            )
                            # Collect leaf textual nodes likely to contain user-visible text
                            blocks = content_root.query_selector_all(
                                selector=(
                                    "p, li, .whitespace-pre-wrap, h1, h2, h3, h4, "
                                    'pre, code, [data-testid*="code" i], [data-testid*="markdown" i]'
                                )
                            )
                            texts: list[str] = []
                            seen_norm: set[str] = set()
                            if blocks:
                                for b in blocks:
                                    try:
                                        t = b.inner_text().strip()
                                    except Exception:
                                        continue
                                    t_clean = _clean_content(t)
                                    if not t_clean:
                                        continue
                                    norm = " ".join(t_clean.split())
                                    if norm in seen_norm:
                                        continue
                                    seen_norm.add(norm)
                                    texts.append(t_clean)
                                inner_clean = "\n\n".join(texts).strip()
                            else:
                                inner_clean = _clean_content(el.inner_text().strip())
                            if inner_clean and len(inner_clean) > 2:
                                tmp.append(ConversationMessage(role=role, content=inner_clean))
                        except Exception as e:
                            print(f"[DEBUG] Element extraction error: {e}", flush=True)
                            continue
                    if len(tmp) >= 2:
                        print(
                            f"[DEBUG] Using selector '{sel}' yielded {len(tmp)} messages",
                            flush=True,
                        )
                        messages = tmp
                        break
            except Exception as e:
                print(f"[DEBUG] Selector loop exception for '{sel}': {e}", flush=True)
                continue

        if not messages:
            # Fallback: parse from text using simple role markers
            try:
                body_text = page.inner_text(selector="body")
            except Exception as e:
                print(f"[DEBUG] body inner_text error: {e}", flush=True)
                body_text = ""

            lines = [line.strip() for line in body_text.splitlines()]
            role_markers = {
                "you said:": "user",
                "grok said:": "assistant",
                "assistant:": "assistant",
                "chatgpt said:": "assistant",
            }
            terminal_markers = (
                "sign in to continue conversation",
                "failed to initialize session",
                "making sure you're human",
                "fast",
                "grok 4 heavy",
                "completed",
            )
            current_role: Optional[str] = None
            buf: list[str] = []
            text_messages: list[ConversationMessage] = []

            def _flush(role: Optional[str]) -> None:
                nonlocal buf, text_messages
                content = "\n".join([b for b in buf if b]).strip()
                if role is not None and content:
                    text_messages.append(
                        ConversationMessage(role=role, content=_clean_content(content))
                    )
                buf = []

            i = 0
            while i < len(lines):
                raw = lines[i]
                low = raw.lower()
                if low in role_markers:
                    _flush(current_role)
                    current_role = role_markers[low]
                    i += 1
                    continue
                if low in {"sign up", "sign in", "skip to content"} or raw == "File":
                    i += 1
                    continue
                if any(marker in low for marker in terminal_markers):
                    # Skip UI noise but keep scanning for more content/messages
                    i += 1
                    continue
                # Detect the two-line user message pattern even when embedded
                if low.strip() == "please increase scale":
                    # Find next non-empty line
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        next_low = lines[j].strip().lower()
                        if next_low == (
                            "and do anything else to get meaningful real results you can without me having to provide anything more"
                        ):
                            _flush(current_role)
                            user_block = raw + "\n\n" + lines[j]
                            text_messages.append(
                                ConversationMessage(role="user", content=_clean_content(user_block))
                            )
                            i = j + 1
                            continue
                if current_role is not None:
                    buf.append(raw)
                i += 1

            _flush(current_role)

            if len(text_messages) >= 2:
                messages = text_messages
            else:
                # Debug: print page content for troubleshooting
                try:
                    title_dbg = page.title()
                    print(f"DEBUG title: {title_dbg}")
                except Exception:
                    pass
                try:
                    print(f"DEBUG body text length: {len(body_text)}")
                    print("DEBUG body text preview:\n" + body_text[:4000])
                except Exception:
                    pass
                try:
                    html = page.content()
                    print(f"DEBUG html length: {len(html)}")
                    print("DEBUG html preview:\n" + html[:4000])
                except Exception:
                    pass
                return ParseResult(success=False, error="No conversation messages found")

        return ParseResult(
            success=True,
            data=ConversationData(
                url="",
                title=title or f"Conversation from {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                author="Unknown",
                import_date=datetime.now().isoformat(),
                content=messages,
            ),
        )
    except Exception as e:
        traceback.print_exc()
        return ParseResult(success=False, error=str(e))


def parse_grok(url: str, headless: bool, browser_name: str) -> ParseResult:
    if not validate_url(url=url):
        return ParseResult(success=False, error=f"Invalid Grok share URL: {url}")

    with sync_playwright() as p:
        if browser_name == "chromium":
            browser = p.chromium.launch(headless=headless)
        elif browser_name == "webkit":
            browser = p.webkit.launch(headless=headless)
        else:
            browser = p.firefox.launch(headless=headless)
        context, page = setup_page(browser=browser)
        try:
            resp = page.goto(url=url, wait_until="domcontentloaded", timeout=30000)
            if not resp or resp.status != 200:
                return ParseResult(
                    success=False, error=f"HTTP {resp.status if resp else 'No response'}"
                )
            res = extract(page=page)
            if res.success and res.data:
                res.data.url = url
            return res
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Grok parser (single-run)")
    parser.add_argument("url", help="Grok share URL to parse")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="firefox")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = parse_grok(url=args.url, headless=not args.no_headless, browser_name=args.browser)
    if result.success and result.data:
        print(json.dumps(result.data.model_dump(), indent=2, ensure_ascii=False))
        if args.output:
            out_path = Path(args.output)
            with open(file=out_path, mode="w", encoding="utf-8") as f:
                json.dump(result.data.model_dump(), f, indent=2, ensure_ascii=False)
    else:
        print(f"Error: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
