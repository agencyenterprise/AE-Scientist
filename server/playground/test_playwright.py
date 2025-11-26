#!/usr/bin/env python3
"""
Simple test to verify Playwright is working correctly.
"""

from playwright.sync_api import sync_playwright


def test_simple_page() -> bool:
    """Test Playwright with a simple page."""
    print("🧪 Testing Playwright with a simple page...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            print("📱 Navigating to httpbin.org...")
            response = page.goto("https://httpbin.org/get", timeout=30000)

            if response and response.status == 200:
                print(f"✅ Successfully loaded page. Status: {response.status}")

                # Get page content
                content = page.content()
                print(f"📄 Page content length: {len(content)} characters")

                # Try to get some text
                body_text = page.inner_text("body")
                print(f"📝 Body text preview: {body_text[:200]}...")

                browser.close()
                return True
            else:
                print(
                    f"❌ Failed to load page. Status: {response.status if response else 'No response'}"
                )
                browser.close()
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def test_chatgpt_access() -> bool:
    """Test if we can at least access ChatGPT domain."""
    print("\n🤖 Testing ChatGPT domain access...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("🌐 Navigating to ChatGPT main page...")
            response = page.goto("https://chatgpt.com", timeout=30000)

            if response and response.status == 200:
                print(f"✅ Successfully loaded ChatGPT. Status: {response.status}")

                title = page.title()
                print(f"📋 Page title: {title}")

                browser.close()
                return True
            else:
                print(
                    f"❌ Failed to load ChatGPT. Status: {response.status if response else 'No response'}"
                )
                browser.close()
                return False

        except Exception as e:
            print(f"❌ Error accessing ChatGPT: {e}")
            return False


if __name__ == "__main__":
    print("🔧 Playwright Debugging Test")
    print("=" * 40)

    # Test basic Playwright functionality
    basic_works = test_simple_page()

    # Test ChatGPT domain access
    chatgpt_works = test_chatgpt_access()

    print("\n📊 Results:")
    print(f"Basic Playwright: {'✅ Working' if basic_works else '❌ Failed'}")
    print(f"ChatGPT Access: {'✅ Working' if chatgpt_works else '❌ Failed'}")

    if basic_works and not chatgpt_works:
        print(
            "\n💡 Recommendation: ChatGPT might have bot protection. Consider alternative approaches."
        )
    elif not basic_works:
        print("\n💡 Recommendation: Check Playwright installation and system requirements.")
    else:
        print("\n💡 The issue might be specific to ChatGPT share pages.")
