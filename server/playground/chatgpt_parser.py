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
import json
import random
import re
import sys
import time
import traceback
from datetime import datetime
from typing import List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
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


def human_delay(min_ms: int = 100, max_ms: int = 300) -> None:
    """Add a human-like random delay."""
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    time.sleep(delay)


def setup_stealth_page(
    browser: Browser, user_agent: str, viewport: dict[str, int]
) -> tuple[BrowserContext, Page]:
    """Setup a stealth browser context and page."""
    context = browser.new_context(
        user_agent=user_agent,
        viewport=viewport,  # type: ignore
        locale="en-US",
        timezone_id="America/New_York",
        # Simulate a real device
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False,
        # Additional stealth options
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

    # Apply manual stealth techniques
    # 1. Override webdriver property
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """
    )

    # 2. Override plugins array to look realistic
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """
    )

    # 3. Override languages
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """
    )

    # 4. Override WebGL fingerprinting
    page.add_init_script(
        """
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter(parameter);
        };
    """
    )

    return context, page


def extract_conversation_data_v2(page: Page) -> ParseResult:
    """
    Enhanced conversation data extraction with multiple strategies.
    """
    try:
        print("🔍 Extracting conversation data...")

        # Wait for page to be fully loaded
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        human_delay(1000, 2000)

        # Try to wait for conversation content
        try:
            page.wait_for_selector("main", timeout=10000)
        except Exception:
            print("Warning: Main content selector not found, continuing...")

        human_delay(500, 1000)

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
                element = page.query_selector(selector)
                if element:
                    text = element.inner_text().strip()
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
                elements = page.query_selector_all(selector)
                print(f"🔍 Trying selector '{selector}': found {len(elements)} elements")

                if elements and len(elements) > 1:  # We expect multiple messages
                    temp_messages = []

                    for element in elements:
                        try:
                            # Determine role
                            role = "user"  # default

                            # Check for role indicators
                            role_attr = element.get_attribute("data-message-author-role")
                            if role_attr:
                                role = "assistant" if role_attr == "assistant" else "user"
                            else:
                                # Check for text patterns or class names
                                element_html = element.inner_html().lower()
                                element_classes = element.get_attribute("class") or ""

                                if (
                                    "assistant" in element_html
                                    or "ai" in element_classes.lower()
                                    or "bot" in element_classes.lower()
                                ):
                                    role = "assistant"
                                elif "user" in element_html or "human" in element_classes.lower():
                                    role = "user"

                            # Extract content
                            content = element.inner_text().strip()

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
                body_text = page.inner_text("body")
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
                all_text = page.inner_text("body")
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


def parse_chatgpt_conversation_v2(
    url: str, headless: bool = True, max_retries: int = 3
) -> ParseResult:
    """
    Enhanced ChatGPT conversation parser with multiple browser engines and retry logic.
    """
    if not validate_chatgpt_url(url):
        return ParseResult(success=False, data=None, error=f"Invalid ChatGPT share URL: {url}")

    print(f"🤖 Parsing ChatGPT conversation from: {url}")

    browsers_to_try = ["chromium", "firefox", "webkit"]

    for attempt in range(max_retries):
        for browser_name in browsers_to_try:
            try:
                print(f"🔄 Attempt {attempt + 1}/{max_retries} with {browser_name}")

                with sync_playwright() as p:
                    # Get browser
                    if browser_name == "chromium":
                        browser = p.chromium.launch(headless=headless)
                    elif browser_name == "firefox":
                        browser = p.firefox.launch(headless=headless)
                    else:  # webkit
                        browser = p.webkit.launch(headless=headless)

                    # Setup stealth page
                    user_agent = get_random_user_agent()
                    viewport = get_random_viewport()
                    context, page = setup_stealth_page(browser, user_agent, viewport)

                    print(
                        f"📱 Using {browser_name} with viewport {viewport['width']}x{viewport['height']}"
                    )

                    # Random delay before navigation
                    human_delay(500, 1500)

                    # Navigate to URL
                    print("🌐 Navigating to URL...")
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    if not response:
                        print("❌ No response received")
                        browser.close()
                        continue

                    if response.status != 200:
                        print(f"❌ HTTP {response.status}: {response.status_text}")
                        browser.close()
                        continue

                    print(f"✅ Page loaded successfully (HTTP {response.status})")

                    # Random delay after page load
                    human_delay(1000, 3000)

                    # Take screenshot for debugging
                    try:
                        screenshot_path = (
                            f"backend/playground/debug_screenshot_{browser_name}_{attempt}.png"
                        )
                        page.screenshot(path=screenshot_path)
                        print(f"📸 Screenshot saved: {screenshot_path}")
                    except Exception:
                        pass

                    # Extract data
                    result = extract_conversation_data_v2(page)

                    browser.close()

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
                continue

        # Delay between retry attempts
        if attempt < max_retries - 1:
            delay = random.uniform(2, 5)
            print(f"⏰ Waiting {delay:.1f}s before retry...")
            time.sleep(delay)

    return ParseResult(
        success=False,
        data=None,
        error=f"Failed to parse conversation after {max_retries} attempts with all browsers",
    )


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

    print("🚀 Enhanced ChatGPT Parser")
    print("=" * 40)

    # Parse the conversation
    result = parse_chatgpt_conversation_v2(
        args.url, headless=not args.no_headless, max_retries=args.retries
    )

    if result.success and result.data:
        print("\n✅ Successfully parsed conversation!")
        print(f"Title: {result.data.title}")
        print(f"Author: {result.data.author}")
        print(f"Messages: {result.data.message_count}")
        print(f"Import Date: {result.data.import_date}")

        print("\n📝 Content Preview:")
        for i, msg in enumerate(result.data.content[:3]):  # Show first 3 messages
            role_emoji = "🤖" if msg.role == "assistant" else "👤"
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"{role_emoji} {msg.role.title()}: {content_preview}")

        if len(result.data.content) > 3:
            print(f"... and {len(result.data.content) - 3} more messages")

        # Save to file if requested
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result.data.model_dump(), f, indent=2, ensure_ascii=False)
            print(f"\n💾 Data saved to: {args.output}")
        else:
            print("\n📄 Full JSON output:")
            print(result.data.model_dump_json(indent=2))

    else:
        print(f"\n❌ Failed to parse conversation: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
