#!/usr/bin/env python3
"""
Claude Share URL Parser (no retries, single browser run)
"""

import argparse
import json
import re
import sys
import traceback
import urllib.error
import urllib.request
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
    return bool(re.match(r"^https://claude\.ai/share/[a-f0-9\-]{36}$", url))


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
        title_text = page.title()
        if title_text and "Just a moment" in title_text:
            page.wait_for_timeout(timeout=6000)
            try:
                page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
        # Wait for any likely content container to appear
        try:
            page.wait_for_selector(
                selector="main, [data-message-author-role], article", timeout=12000
            )
        except Exception:
            page.wait_for_timeout(timeout=1000)
    except Exception:
        pass


def _is_cloudflare_interstitial(page: Page) -> bool:
    try:
        title_text = page.title()
        if title_text and "Just a moment" in title_text:
            return True
        try:
            body_text = page.inner_text(selector="body")
            if body_text and (
                "Verify you are human" in body_text
                or "Performance & security by Cloudflare" in body_text
            ):
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _resolve_cloudflare_if_needed(
    page: Page, context: BrowserContext, max_attempts: int, wait_ms_between: int
) -> None:
    try:
        attempt = 0
        while attempt < max_attempts and _is_cloudflare_interstitial(page=page):
            attempt += 1
            try:
                page.wait_for_timeout(timeout=wait_ms_between)
            except Exception:
                pass
            try:
                page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
            try:
                cookies = context.cookies()
                if any(c.get("name") == "cf_clearance" for c in cookies):
                    break
            except Exception:
                pass
    except Exception:
        pass


def _auto_scroll(page: Page) -> None:
    try:
        prev_h = page.evaluate(expression="document.body.scrollHeight")
        for _ in range(8):
            page.evaluate(expression="window.scrollTo(0, document.body.scrollHeight)")
            try:
                page.wait_for_function(
                    expression="s => document.body.scrollHeight > s",
                    arg=prev_h,
                    timeout=300,
                )
            except Exception:
                break
            curr_h = page.evaluate(expression="document.body.scrollHeight")
            if curr_h == prev_h:
                break
            prev_h = curr_h
    except Exception:
        pass


def _expand_collapsibles(page: Page) -> None:
    try:
        labels = [
            "Show inline",
            "Show more",
            "Expand",
            "Read more",
            "Continue reading",
        ]
        for _ in range(2):
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
                        for el in page.query_selector_all(selector=sel) or []:
                            if el.is_visible():
                                el.click()
                                page.wait_for_timeout(timeout=150)
                                clicked = True
                    except Exception:
                        continue
            if not clicked:
                break
    except Exception:
        pass


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


def _settle_content(page: Page, max_wait_ms: int, step_ms: int) -> None:
    try:
        prev = _get_content_signature(page=page)
        elapsed = 0
        stable = 0
        while elapsed < max_wait_ms:
            page.wait_for_timeout(timeout=step_ms)
            elapsed += step_ms
            curr = _get_content_signature(page=page)
            if curr == prev:
                stable += 1
            else:
                stable = 0
            prev = curr
            if stable >= 2:
                break
    except Exception:
        pass


def _clean_content(text: str) -> str:
    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    terminal_markers = (
        "sign in to continue conversation",
        "failed to initialize session",
        "making sure you're human",
        "cookie settings",
        "customize cookie settings",
        "reject all cookies",
        "accept all cookies",
    )
    filtered: list[str] = []
    for raw in lines:
        low = raw.strip().lower()
        if low in {"text", "copy", "expand", "show more", "show inline"}:
            continue
        if any(marker in low for marker in terminal_markers):
            continue
        filtered.append(raw)
    return "\n".join(filtered).strip()


def _preflight_http_status(url: str, timeout_seconds: float) -> int | None:
    try:
        req = urllib.request.Request(url=url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # nosec B310
            return int(resp.getcode())
    except urllib.error.HTTPError as e:
        try:
            return int(e.code)
        except Exception:
            return None
    except Exception:
        return None


def _parse_messages_from_body_text(body_text: str) -> List[ConversationMessage]:
    # Split into paragraphs separated by blank lines
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", body_text) if p.strip()]
    noise_markers = [
        "shared by",
        "this is a copy of a chat",
        "report",
        "start your own conversation",
        "cookie settings",
        "customize cookie settings",
        "reject all cookies",
        "accept all cookies",
        "verify you are human",
        "needs to review the security of your connection",
        "performance & security by cloudflare",
        "claude.ai",
    ]

    content_blocks: list[str] = []
    for p in paragraphs:
        if len(p.strip()) < 3:
            continue
        if p.strip() in {"N", "C"}:  # avatar initials or similar UI crumbs
            continue
        low = p.lower()
        if any(marker in low for marker in noise_markers):
            continue
        cleaned = _clean_content(text=p)
        if cleaned and len(cleaned) > 2:
            content_blocks.append(cleaned)

    messages: List[ConversationMessage] = []
    for idx, block in enumerate(content_blocks):
        role = "user" if idx % 2 == 0 else "assistant"
        messages.append(ConversationMessage(role=role, content=block))
        if len(messages) >= 20:
            break
    return messages


def _extract_messages_by_dom(page: Page) -> List[ConversationMessage]:
    try:
        data = page.evaluate(
            expression=r"""
            (() => {
              const root = document.querySelector('main') || document.body;

              const isUser = (el) => el.matches('[data-testid="user-message"]');
              const isAssistant = (el) => el.matches('.font-claude-response');

              function closestMessageContainer(el) {
                let cur = el;
                while (cur) {
                  if (cur.matches && (isUser(cur) || isAssistant(cur) || cur.matches('article'))) return cur;
                  cur = cur.parentElement;
                }
                return el;
              }

              const rawCandidates = Array.from(
                root.querySelectorAll('[data-testid="user-message"], .font-claude-response')
              );
              const seen = new Set();
              const turns = [];

              const noise = [
                'we use cookies',
                'cookie settings',
                'customize cookie settings',
                'reject all cookies',
                'accept all cookies',
                'start your own conversation',
                'shared by',
                'this is a copy of a chat',
              ];

              const getText = (container) => {
                const contentRoot = container.querySelector('[data-message-content]') || container;
                const blocks = Array.from(contentRoot.querySelectorAll('p, li, .whitespace-pre-wrap, pre, code'));
                const out = [];
                const seenNorm = new Set();
                for (const b of blocks) {
                  const t = (b.innerText || '').trim();
                  if (!t) continue;
                  const clean = t.replace(/\s+/g, ' ').trim();
                  if (!clean) continue;
                  const norm = clean.toLowerCase();
                  if (noise.some(n => norm.includes(n))) continue;
                  if (seenNorm.has(clean)) continue;
                  seenNorm.add(clean);
                  out.push(clean);
                }
                const joined = out.join('\n\n').trim();
                if (joined) return joined;
                // Fallback to container text if no block extraction
                const fallback = (contentRoot.innerText || '').trim();
                const fbClean = fallback.replace(/\s+/g, ' ').trim();
                if (fbClean && !noise.some(n => fbClean.toLowerCase().includes(n))) return fbClean;
                return '';
              };

              for (const el of rawCandidates) {
                const container = closestMessageContainer(el);
                if (!container) continue;
                if (seen.has(container)) continue;
                seen.add(container);
                const role = isUser(container) ? 'user' : (isAssistant(container) ? 'assistant' : '');
                if (!role) continue;
                const text = getText(container);
                if (!text) continue;
                turns.push({ role, content: text });
              }

              // Keep relative DOM order. querySelectorAll preserves it; our set preserves first seen.
              return turns;
            })()
            """
        )
        messages: List[ConversationMessage] = []
        for item in data or []:
            role = item.get("role", "")
            content = item.get("content", "").strip()
            if role in ("user", "assistant") and content:
                messages.append(ConversationMessage(role=role, content=content))
        return messages
    except Exception:
        return []


def extract(page: Page) -> ParseResult:
    try:
        page.wait_for_load_state(state="domcontentloaded", timeout=15000)
        _wait_cloudflare_if_present(page=page)
        try:
            page.wait_for_selector(selector="main", timeout=10000)
        except Exception:
            pass

        # Try to reveal dynamic/hidden content
        try:
            _auto_scroll(page=page)
            _expand_collapsibles(page=page)
            _auto_scroll(page=page)
            _settle_content(page=page, max_wait_ms=1800, step_ms=150)
        except Exception:
            pass

        # title
        title = None
        for sel in ["title", "h1", "[data-testid*='title']"]:
            try:
                el = page.query_selector(selector=sel)
                if el:
                    t = el.inner_text().strip()
                    if t and t.lower() not in ["claude", "anthropic"]:
                        title = t
                        break
            except Exception:
                continue

        # messages via DOM-based extraction first (preferred)
        dom_messages: List[ConversationMessage] = _extract_messages_by_dom(page=page)
        if len(dom_messages) >= 2:
            return ParseResult(
                success=True,
                data=ConversationData(
                    url="",
                    title=title or f"Conversation from {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    author="Unknown",
                    import_date=datetime.now().isoformat(),
                    content=dom_messages,
                ),
            )

        # fallback structured selectors if DOM extraction yielded insufficient results
        messages: List[ConversationMessage] = []
        selectors = [
            # Attribute-based roles
            "main [data-message-author-role]",
            "article [data-message-author-role]",
            "[data-message-author-role]",
            # Likely test ids / semantic containers
            'main [data-testid*="message"]',
            'main [data-testid*="Message"]',
            # ARIA and general article fallbacks
            'main [role="article"]',
            "main article",
            "article",
            # Class-based fallbacks used by many UIs
            'main [class*="message" i]',
            'main [class*="whitespace-pre-wrap" i]',
            'main [class*="prose" i]',
            'main [class*="markdown" i]',
        ]
        for sel in selectors:
            try:
                els = page.query_selector_all(selector=sel)
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
                            content_root = (
                                el.query_selector(selector="[data-message-content]") or el
                            )
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
                                    t_clean = _clean_content(text=t)
                                    if not t_clean:
                                        continue
                                    norm = " ".join(t_clean.split())
                                    if norm in seen_norm:
                                        continue
                                    seen_norm.add(norm)
                                    texts.append(t_clean)
                                inner_clean = "\n\n".join(texts).strip()
                            else:
                                inner_clean = _clean_content(text=el.inner_text().strip())
                            if inner_clean and len(inner_clean) > 2:
                                tmp.append(ConversationMessage(role=role, content=inner_clean))
                        except Exception:
                            continue
                    if len(tmp) >= 2:
                        # Post-filter to drop obvious noise like cookie/privacy blocks
                        messages = tmp
                        noise_substrings = (
                            "we use cookies",
                            "cookie settings",
                            "customize cookie settings",
                            "reject all cookies",
                            "accept all cookies",
                            "start your own conversation",
                            "shared by",
                            "this is a copy of a chat",
                        )
                        messages = [
                            m
                            for m in messages
                            if not any(substr in m.content.lower() for substr in noise_substrings)
                        ]
                        if len(messages) < 2:
                            # If over-filtered, keep original tmp to not lose data
                            messages = tmp
                        break
            except Exception:
                continue

        if not messages:
            # Fallback: parse from text when structured selectors fail
            try:
                body_text = page.inner_text(selector="body")
            except Exception:
                body_text = ""

            text_messages = _parse_messages_from_body_text(body_text=body_text)

            if len(text_messages) >= 2:
                messages = text_messages
            else:
                # Debug: print what we actually got from the page
                try:
                    title_dbg = page.title()
                    print(f"DEBUG title: {title_dbg}")
                except Exception:
                    pass
                try:
                    preview = body_text[:4000]
                    print(f"DEBUG body text length: {len(body_text)}")
                    print("DEBUG body text preview:\n" + preview)
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


def _maybe_add_cookies(context: BrowserContext, cookie_file: str) -> None:
    try:
        path = Path(cookie_file)
        if not cookie_file or not path.exists():
            return
        with open(file=path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            context.add_cookies(cookies=data)
    except Exception:
        pass


def parse_claude(
    url: str,
    headless: bool,
    browser_name: str,
    user_data_dir: str,
    cookie_file: str,
    max_challenge_attempts: int,
    challenge_wait_ms: int,
) -> ParseResult:
    if not validate_url(url):
        return ParseResult(success=False, error=f"Invalid Claude share URL: {url}")

    with sync_playwright() as p:
        # Preflight: HEAD request to avoid expensive browser if page is 404
        status = _preflight_http_status(url=url, timeout_seconds=5.0)
        if status == 404:
            return ParseResult(success=False, error="HTTP 404: Conversation not found")

        persistent = bool(user_data_dir.strip())
        if persistent:
            if browser_name == "chromium":
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            elif browser_name == "webkit":
                context = p.webkit.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            else:
                context = p.firefox.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            _maybe_add_cookies(context=context, cookie_file=cookie_file)
            page = context.new_page()
            browser = None
        else:
            if browser_name == "chromium":
                browser = p.chromium.launch(headless=headless)
            elif browser_name == "webkit":
                browser = p.webkit.launch(headless=headless)
            else:
                browser = p.firefox.launch(headless=headless)
            context, page = setup_page(browser)
            _maybe_add_cookies(context=context, cookie_file=cookie_file)
        try:
            resp = page.goto(url=url, wait_until="domcontentloaded", timeout=30000)
            if not resp or resp.status != 200:
                return ParseResult(
                    success=False, error=f"HTTP {resp.status if resp else 'No response'}"
                )
            # If Cloudflare interstitial is detected immediately, do not spend time retrying
            if _is_cloudflare_interstitial(page=page):
                status2 = _preflight_http_status(url=url, timeout_seconds=5.0)
                if status2 == 404:
                    return ParseResult(success=False, error="HTTP 404: Conversation not found")
                return ParseResult(
                    success=False,
                    error="Access blocked by Cloudflare; unable to verify conversation",
                )
            _resolve_cloudflare_if_needed(
                page=page,
                context=context,
                max_attempts=max_challenge_attempts,
                wait_ms_between=challenge_wait_ms,
            )
            res = extract(page)
            if res.success and res.data:
                res.data.url = url
            return res
        finally:
            try:
                if persistent:
                    context.close()
                else:
                    if browser is not None:
                        browser.close()
            except Exception:
                pass


def debug_print_dom(
    url: str,
    headless: bool,
    browser_name: str,
    user_data_dir: str,
    cookie_file: str,
    max_challenge_attempts: int,
    challenge_wait_ms: int,
) -> None:
    with sync_playwright() as p:
        persistent = bool(user_data_dir.strip())
        if persistent:
            if browser_name == "chromium":
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            elif browser_name == "webkit":
                context = p.webkit.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            else:
                context = p.firefox.launch_persistent_context(
                    user_data_dir=user_data_dir, headless=headless
                )
            _maybe_add_cookies(context=context, cookie_file=cookie_file)
            page = context.new_page()
            browser = None
        else:
            if browser_name == "chromium":
                browser = p.chromium.launch(headless=headless)
            elif browser_name == "webkit":
                browser = p.webkit.launch(headless=headless)
            else:
                browser = p.firefox.launch(headless=headless)
            context, page = setup_page(browser)
            _maybe_add_cookies(context=context, cookie_file=cookie_file)
        try:
            resp = page.goto(url=url, wait_until="domcontentloaded", timeout=30000)
            if not resp or resp.status != 200:
                print(f"DEBUG: HTTP {resp.status if resp else 'No response'}")
                return
            _resolve_cloudflare_if_needed(
                page=page,
                context=context,
                max_attempts=max_challenge_attempts,
                wait_ms_between=challenge_wait_ms,
            )
            _wait_cloudflare_if_present(page=page)
            try:
                page.wait_for_selector(selector="main", timeout=10000)
            except Exception:
                pass
            _auto_scroll(page=page)
            _expand_collapsibles(page=page)
            _auto_scroll(page=page)
            _settle_content(page=page, max_wait_ms=1200, step_ms=150)

            outline = page.evaluate(
                expression=r"""
                (() => {
                  const root = document.querySelector('main') || document.body;
                  const nodes = [];
                  const MAX_ARTICLES = 20;
                  const arts = Array.from(root.querySelectorAll('article')).slice(0, MAX_ARTICLES);
                  const pick = (el) => {
                    const attrs = {};
                    for (const a of el.attributes) {
                      if (a.name.startsWith('data-') || a.name === 'role' || a.name.startsWith('aria-')) {
                        attrs[a.name] = a.value;
                      }
                    }
                    const cls = (el.className || '').toString().trim();
                    const classes = cls.split(/\s+/).filter(Boolean).slice(0, 6).join(' ');
                    const text = (el.innerText || '').trim().replace(/\s+/g, ' ');
                    return {
                      tag: el.tagName.toLowerCase(),
                      id: el.id || '',
                      classes,
                      attrs,
                      textPreview: text.slice(0, 140)
                    };
                  };
                  const describe = (el, depth=0, maxDepth=2) => {
                    const info = pick(el);
                    info.depth = depth;
                    nodes.push(info);
                    if (depth >= maxDepth) return;
                    const children = Array.from(el.children).slice(0, 8);
                    for (const c of children) describe(c, depth+1, maxDepth);
                  };
                  describe(root, 0, 1);
                  for (let i = 0; i < arts.length; i++) {
                    const a = arts[i];
                    const info = pick(a);
                    info.isArticle = true;
                    info.index = i;
                    nodes.push(info);
                    const content = a.querySelector('[data-message-content]') || a;
                    const blocks = Array.from(content.querySelectorAll('p, li, .whitespace-pre-wrap, pre, code')).slice(0, 10);
                    for (const b of blocks) {
                      const bi = pick(b);
                      bi.block = true;
                      bi.articleIndex = i;
                      nodes.push(bi);
                    }
                  }
                  return nodes;
                })()
                """
            )
            print("DOM OUTLINE (first main subtree and articles):")
            for n in outline:
                depth = n.get("depth", 0)
                indent = "  " * int(depth)
                prefix = (
                    "[ARTICLE %s] " % n["index"]
                    if "index" in n
                    else ("[BLOCK of %s] " % n["articleIndex"] if "articleIndex" in n else "")
                )
                attrs = n.get("attrs", {})
                data_role = attrs.get("data-message-author-role", "")
                data_testid = attrs.get("data-testid", "")
                role = attrs.get("role", "")
                print(
                    f"{indent}{prefix}{n['tag']}#{n['id']} .{n['classes']} data-role={data_role} data-testid={data_testid} role={role} :: {n['textPreview']}"
                )

            # Focused candidates likely to be conversation turns
            candidates = page.evaluate(
                expression=r"""
                (() => {
                  const pick = (el) => {
                    const attrs = {};
                    for (const a of el.attributes) {
                      if (a.name.startsWith('data-') || a.name === 'role' || a.name.startsWith('aria-')) {
                        attrs[a.name] = a.value;
                      }
                    }
                    const cls = (el.className || '').toString().trim();
                    const classes = cls.split(/\s+/).filter(Boolean).slice(0, 8).join(' ');
                    const text = (el.innerText || '').trim().replace(/\s+/g, ' ');
                    return {
                      tag: el.tagName.toLowerCase(),
                      id: el.id || '',
                      classes,
                      attrs,
                      textPreview: text.slice(0, 160)
                    };
                  };

                  const root = document.querySelector('main') || document.body;
                  const sel = [
                    '[data-message-author-role]',
                    '[data-message-content]',
                    '[data-testid*="message" i]'
                  ].join(',');
                  const found = Array.from(root.querySelectorAll(sel));

                  // Also search for specific sample texts to locate the exact containers
                  const sampleUser = 'this is a simple chat to test the share functionality';
                  const sampleAssistantStarts = "Hello! I'm here and ready to chat";
                  const textNodes = [];
                  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
                  while (walker.nextNode()) {
                    const el = walker.currentNode;
                    const t = (el.innerText||'').trim();
                    if (!t) continue;
                    const low = t.toLowerCase();
                    if (low.includes(sampleUser)) textNodes.push(el);
                    if (t.startsWith(sampleAssistantStarts)) textNodes.push(el);
                  }

                  function closestMessageContainer(el) {
                    let cur = el;
                    while (cur) {
                      if (cur.matches && (cur.matches('[data-message-author-role]') || cur.matches('article'))) return cur;
                      cur = cur.parentElement;
                    }
                    return el;
                  }

                  const results = [];
                  for (const el of found) {
                    const c = closestMessageContainer(el);
                    const obj = pick(c);
                    obj.hint = 'candidate';
                    results.push(obj);
                  }
                  for (const el of textNodes) {
                    const c = closestMessageContainer(el);
                    const obj = pick(c);
                    obj.hint = 'text-located';
                    results.push(obj);
                  }
                  return results;
                })()
                """
            )
            print("\nMESSAGE CANDIDATES:")
            seen = set()
            for c in candidates:
                key = (c.get("tag", ""), c.get("id", ""), c.get("classes", ""))
                if key in seen:
                    continue
                seen.add(key)
                attrs = c.get("attrs", {})
                data_role = attrs.get("data-message-author-role", "")
                data_testid = attrs.get("data-testid", "")
                role = attrs.get("role", "")
                print(
                    f"[{c.get('hint', '')}] {c['tag']}#{c['id']} .{c['classes']} data-role={data_role} data-testid={data_testid} role={role} :: {c['textPreview']}"
                )
        finally:
            try:
                if persistent:
                    context.close()
                else:
                    browser.close()  # type: ignore[union-attr]
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude parser (single-run)")
    parser.add_argument("url", help="Claude share URL to parse")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="firefox")
    parser.add_argument("--output")
    parser.add_argument("--debug-dom", action="store_true")
    parser.add_argument(
        "--user-data-dir", default="", help="Persistent user data dir to retain cookies"
    )
    parser.add_argument("--cookie-file", default="", help="Path to JSON cookies to import")
    parser.add_argument("--challenge-attempts", type=int, default=5)
    parser.add_argument("--challenge-wait-ms", type=int, default=8000)
    args = parser.parse_args()

    if args.debug_dom:
        debug_print_dom(
            url=args.url,
            headless=not args.no_headless,
            browser_name=args.browser,
            user_data_dir=args.user_data_dir,
            cookie_file=args.cookie_file,
            max_challenge_attempts=args.challenge_attempts,
            challenge_wait_ms=args.challenge_wait_ms,
        )
        sys.exit(0)

    result = parse_claude(
        url=args.url,
        headless=not args.no_headless,
        browser_name=args.browser,
        user_data_dir=args.user_data_dir,
        cookie_file=args.cookie_file,
        max_challenge_attempts=args.challenge_attempts,
        challenge_wait_ms=args.challenge_wait_ms,
    )
    if result.success and result.data:
        print(json.dumps(result.data.model_dump(), indent=2))
        if args.output:
            out_path = Path(args.output)
            with open(file=out_path, mode="w", encoding="utf-8") as f:
                json.dump(result.data.model_dump(), f, indent=2, ensure_ascii=False)
    else:
        print(f"Error: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
