#!/usr/bin/env python3
"""
Improved ChatGPT Share URL Parser with Advanced Bot Detection Evasion

This script implements multiple techniques to bypass ChatGPT's bot detection:
- Playwright Stealth mode
- Multiple browser engines
- Human-like behavior simulation
- Randomized delays and actions
- Different user agents and fingerprints
"""

import argparse
import asyncio
import json
import random
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """Represents a single message in a conversation."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ConversationData(BaseModel):
    """Represents extracted conversation data from ChatGPT."""

    url: str = Field(..., description="Original ChatGPT share URL")
    title: str = Field(..., description="Conversation title")
    author: str = Field(..., description="Conversation author")
    import_date: str = Field(..., description="ISO format import timestamp")
    content: List[ConversationMessage] = Field(..., description="List of conversation messages")

    @property
    def message_count(self) -> int:
        """Get the number of messages in the conversation."""
        return len(self.content)


class ParseResult(BaseModel):
    """Result of parsing operation."""

    success: bool = Field(..., description="Whether parsing was successful")
    data: Optional[ConversationData] = Field(
        None, description="Parsed conversation data if successful"
    )
    error: Optional[str] = Field(None, description="Error message if parsing failed")


def validate_chatgpt_url(url: str) -> bool:
    """Validate if the URL is a valid ChatGPT share URL."""
    pattern = r"^https://chatgpt\.com/share/[a-f0-9-]+$"
    return bool(re.match(pattern, url))


def get_random_user_agent() -> str:
    """Get a random realistic user agent."""
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    return random.choice(user_agents)


def get_random_viewport() -> dict[str, int]:
    """Get a random realistic viewport size."""
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1280, "height": 720},
    ]
    return random.choice(viewports)


async def human_delay(min_ms: int, max_ms: int) -> None:
    """Add a human-like random delay."""
    delay_seconds = random.uniform(a=min_ms / 1000, b=max_ms / 1000)
    await asyncio.sleep(delay=delay_seconds)


async def setup_stealth_page(
    browser: Browser, user_agent: str, viewport: dict[str, int]
) -> tuple[BrowserContext, Page]:
    """Setup a stealth browser context and page."""
    context = await browser.new_context(
        user_agent=user_agent,
        viewport=viewport,  # type: ignore
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

    page = await context.new_page()

    # Apply manual stealth techniques
    # 1. Override webdriver property
    await page.add_init_script(
        script="""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """
    )

    # 2. Override plugins array to look realistic
    await page.add_init_script(
        script="""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """
    )

    # 3. Override languages
    await page.add_init_script(
        script="""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """
    )

    # 4. Override WebGL fingerprinting
    await page.add_init_script(
        script="""
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter(parameter);
        };
    """
    )

    return context, page


async def extract_conversation_data_v2(page: Page) -> ParseResult:
    """
    Enhanced conversation data extraction with multiple strategies.
    """
    try:
        print("🔍 Extracting conversation data...")

        # Wait for page to be fully loaded
        await page.wait_for_load_state(state="domcontentloaded", timeout=15000)
        await human_delay(min_ms=1000, max_ms=2000)

        # Try to wait for conversation content
        try:
            await page.wait_for_selector(selector="main", timeout=10000)
        except Exception:
            print("Warning: Main content selector not found, continuing...")

        await human_delay(min_ms=500, max_ms=1000)

        # Extract title
        title = None
        title_selectors = [
            "h1",
            "title",
            "[data-testid*='title']",
            ".text-2xl",
            ".text-3xl",
            ".font-semibold",
            ".conversation-title",
        ]

        for selector in title_selectors:
            try:
                element = await page.query_selector(selector=selector)
                if element:
                    element_text = await element.inner_text()
                    text = element_text.strip() if element_text else ""
                    if text and text.lower() != "chatgpt" and len(text) > 1:
                        title = text
                        print(f"✓ Found title: {title}")
                        break
            except Exception:
                continue

        # Extract messages using multiple strategies
        messages: List[ConversationMessage] = []

        # Strategy 1: Look for conversation containers
        conversation_selectors = [
            "[data-message-author-role]",
            ".conversation-turn",
            ".message",
            "[role='group']",
            ".group",
            ".flex.flex-col",
            "article",
        ]

        for selector in conversation_selectors:
            try:
                elements = await page.query_selector_all(selector=selector)
                print(f"🔍 Trying selector '{selector}': found {len(elements)} elements")

                if elements and len(elements) > 1:  # We expect multiple messages
                    temp_messages = []

                    for element in elements:
                        try:
                            # Determine role
                            role = "user"  # default

                            # Check for role indicators
                            role_attr = await element.get_attribute(name="data-message-author-role")
                            if role_attr:
                                role = "assistant" if role_attr == "assistant" else "user"
                            else:
                                # Check for text patterns or class names
                                element_html_raw = await element.inner_html()
                                element_html = (element_html_raw or "").lower()
                                element_classes = await element.get_attribute(name="class") or ""

                                if (
                                    "assistant" in element_html
                                    or "ai" in element_classes.lower()
                                    or "bot" in element_classes.lower()
                                ):
                                    role = "assistant"
                                elif "user" in element_html or "human" in element_classes.lower():
                                    role = "user"

                            # Extract content
                            inner_text_raw = await element.inner_text()
                            content = inner_text_raw.strip() if inner_text_raw else ""

                            # Filter valid messages
                            if (
                                content
                                and len(content) > 10
                                and not content.lower().startswith("chatgpt")
                            ):
                                temp_messages.append(
                                    ConversationMessage(role=role, content=content)
                                )

                        except Exception as e:
                            print(f"Warning: Error processing element: {e}")
                            continue

                    if len(temp_messages) > len(messages):
                        messages = temp_messages
                        print(f"✓ Found {len(messages)} messages with selector '{selector}'")

                if len(messages) > 2:  # If we have a good set of messages, use them
                    break

            except Exception as e:
                print(f"Warning: Error with selector '{selector}': {e}")
                continue

        # Strategy 2: If no structured messages found, try text parsing
        if not messages:
            print("🔍 Trying text-based parsing...")
            try:
                body_text = await page.inner_text(selector="body")
                print(f"📄 Body text length: {len(body_text)}")

                if body_text and len(body_text) > 100:
                    # Try to identify conversation patterns
                    lines = body_text.split("\n")
                    current_message = ""
                    current_role = "user"

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        # Look for role indicators
                        if any(indicator in line.lower() for indicator in ["user", "you", "human"]):
                            if current_message:
                                messages.append(
                                    ConversationMessage(role=current_role, content=current_message)
                                )
                            current_message = line
                            current_role = "user"
                        elif any(
                            indicator in line.lower()
                            for indicator in ["assistant", "chatgpt", "ai", "bot"]
                        ):
                            if current_message:
                                messages.append(
                                    ConversationMessage(role=current_role, content=current_message)
                                )
                            current_message = line
                            current_role = "assistant"
                        else:
                            current_message += " " + line

                    # Add the last message
                    if current_message:
                        messages.append(
                            ConversationMessage(role=current_role, content=current_message)
                        )

            except Exception as e:
                print(f"Warning: Text parsing failed: {e}")

        # If we still don't have messages, try one more fallback
        if not messages:
            print("🔍 Using fallback content extraction...")
            try:
                # Get all text and create a single assistant message
                all_text = await page.inner_text(selector="body")
                if all_text and len(all_text) > 50:
                    # Clean up the text
                    cleaned_text = all_text.replace("ChatGPT", "").strip()
                    if cleaned_text:
                        messages.append(
                            ConversationMessage(
                                role="assistant",
                                content=(
                                    cleaned_text[:2000] + "..."
                                    if len(cleaned_text) > 2000
                                    else cleaned_text
                                ),
                            )
                        )
            except Exception as e:
                print(f"Warning: Fallback extraction failed: {e}")

        # Build result
        if messages:
            return ParseResult(
                success=True,
                data=ConversationData(
                    url="",  # Will be set by caller
                    title=title or f"Conversation from {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    author="Unknown",
                    import_date=datetime.now().isoformat(),
                    content=messages,
                ),
                error=None,
            )
        else:
            return ParseResult(success=False, data=None, error="No conversation messages found")

    except Exception as e:
        print(f"Error extracting conversation data: {e}")
        traceback.print_exc()
        return ParseResult(
            success=False, data=None, error=f"Failed to extract conversation data: {str(e)}"
        )


async def parse_chatgpt_conversation_v2(url: str, headless: bool, max_retries: int) -> ParseResult:
    """
    Enhanced ChatGPT conversation parser with multiple browser engines and retry logic.
    """
    if not validate_chatgpt_url(url=url):
        return ParseResult(success=False, data=None, error=f"Invalid ChatGPT share URL: {url}")

    print(f"🤖 Parsing ChatGPT conversation from: {url}")

    browsers_to_try = ["chromium", "firefox", "webkit"]

    async with async_playwright() as playwright:
        for attempt in range(max_retries):
            for browser_name in browsers_to_try:
                browser: Browser | None = None
                try:
                    print(f"🔄 Attempt {attempt + 1}/{max_retries} with {browser_name}")

                    if browser_name == "chromium":
                        browser = await playwright.chromium.launch(headless=headless)
                    elif browser_name == "firefox":
                        browser = await playwright.firefox.launch(headless=headless)
                    else:
                        browser = await playwright.webkit.launch(headless=headless)

                    user_agent = get_random_user_agent()
                    viewport = get_random_viewport()
                    _context, page = await setup_stealth_page(
                        browser=browser, user_agent=user_agent, viewport=viewport
                    )

                    print(
                        f"📱 Using {browser_name} with viewport {viewport['width']}x{viewport['height']}"
                    )

                    await human_delay(min_ms=500, max_ms=1500)

                    print("🌐 Navigating to URL...")
                    response = await page.goto(
                        url=url, wait_until="domcontentloaded", timeout=30000
                    )

                    if not response:
                        print("❌ No response received")
                        continue

                    if response.status != 200:
                        print(f"❌ HTTP {response.status}: {response.status_text}")
                        continue

                    print(f"✅ Page loaded successfully (HTTP {response.status})")

                    await human_delay(min_ms=1000, max_ms=3000)

                    try:
                        screenshot_path = (
                            f"backend/playground/debug_screenshot_{browser_name}_{attempt}.png"
                        )
                        await page.screenshot(path=screenshot_path)
                        print(f"📸 Screenshot saved: {screenshot_path}")
                    except Exception:
                        pass

                    result = await extract_conversation_data_v2(page=page)

                    if result.success:
                        print(f"✅ Successfully extracted conversation with {browser_name}")
                        if result.data:
                            result.data.url = url
                        return result
                    else:
                        print(f"❌ Extraction failed with {browser_name}: {result.error}")

                except Exception as e:
                    print(f"❌ Error with {browser_name} (attempt {attempt + 1}): {e}")
                    traceback.print_exc()
                finally:
                    if browser and browser.is_connected():
                        await browser.close()

            if attempt < max_retries - 1:
                delay = random.uniform(a=2, b=5)
                print(f"⏰ Waiting {delay:.1f}s before retry...")
                await asyncio.sleep(delay=delay)

    return ParseResult(
        success=False,
        data=None,
        error=f"Failed to parse conversation after {max_retries} attempts with all browsers",
    )


async def run_cli(args: argparse.Namespace) -> None:
    print("🚀 Enhanced ChatGPT Parser")
    print("=" * 40)

    result = await parse_chatgpt_conversation_v2(
        url=args.url, headless=not args.no_headless, max_retries=args.retries
    )

    if result.success and result.data:
        print("\n✅ Successfully parsed conversation!")
        print(f"Title: {result.data.title}")
        print(f"Author: {result.data.author}")
        print(f"Messages: {result.data.message_count}")
        print(f"Import Date: {result.data.import_date}")

        print("\n📝 Content Preview:")
        for msg in result.data.content[:3]:
            role_emoji = "🤖" if msg.role == "assistant" else "👤"
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"{role_emoji} {msg.role.title()}: {content_preview}")

        if len(result.data.content) > 3:
            remaining = len(result.data.content) - 3
            print(f"... and {remaining} more messages")

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(
                data=json.dumps(
                    obj=result.data.model_dump(),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            print(f"\n💾 Data saved to: {output_path}")
        else:
            print("\n📄 Full JSON output:")
            print(result.data.model_dump_json(indent=2))

    else:
        print(f"\n❌ Failed to parse conversation: {result.error}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enhanced ChatGPT conversation parsing with bot evasion"
    )
    parser.add_argument("url", help="ChatGPT share URL to parse")
    parser.add_argument(
        "--no-headless", action="store_true", help="Run browser in non-headless mode for debugging"
    )
    parser.add_argument("--output", help="Output file to save parsed data (JSON)")
    parser.add_argument(
        "--retries", type=int, default=3, help="Number of retry attempts (default: 3)"
    )

    args = parser.parse_args()
    asyncio.run(main=run_cli(args=args))


if __name__ == "__main__":
    main()
