#!/usr/bin/env python3
"""
Test script for ChatGPT parser functionality without actual web scraping.
"""

from datetime import datetime

from chatgpt_parser import ConversationData, ConversationMessage, ParseResult, validate_chatgpt_url


def test_url_validation() -> None:
    """Test URL validation function."""
    print("🔍 Testing URL validation...")

    # Valid URLs
    valid_urls = [
        "https://chatgpt.com/share/68239525-2e24-8006-850d-811d36083b8d",
        "https://chatgpt.com/share/abcdef12-3456-7890-abcd-ef1234567890",
    ]

    # Invalid URLs
    invalid_urls = [
        "https://invalid-url.com",
        "https://chatgpt.com/share/invalid",
        "http://chatgpt.com/share/68239525-2e24-8006-850d-811d36083b8d",  # http instead of https
        "https://chatgpt.com/share/",  # missing UUID
        "https://chat.openai.com/share/68239525-2e24-8006-850d-811d36083b8d",  # wrong domain
    ]

    print("✅ Valid URLs:")
    for url in valid_urls:
        result = validate_chatgpt_url(url)
        print(f"  {url}: {'✓' if result else '✗'}")
        assert result, f"Expected {url} to be valid"

    print("\n❌ Invalid URLs:")
    for url in invalid_urls:
        result = validate_chatgpt_url(url)
        print(f"  {url}: {'✓' if result else '✗'}")
        assert not result, f"Expected {url} to be invalid"

    print("✅ URL validation tests passed!\n")


def test_pydantic_models() -> None:
    """Test Pydantic model creation and serialization."""
    print("🏗️  Testing Pydantic models...")

    # Create test messages
    messages = [
        ConversationMessage(role="user", content="Hello, can you help me with Python?"),
        ConversationMessage(
            role="assistant",
            content="Of course! I'd be happy to help you with Python. What specific topic or problem would you like assistance with?",
        ),
        ConversationMessage(
            role="user", content="I need to understand how to use Pydantic models."
        ),
        ConversationMessage(
            role="assistant",
            content="Pydantic is a great library for data validation and settings management. Here's how you can use it...",
        ),
    ]

    # Create conversation data
    conversation = ConversationData(
        url="https://chatgpt.com/share/68239525-2e24-8006-850d-811d36083b8d",
        title="Python and Pydantic Help",
        author="Test User",
        import_date=datetime.now().isoformat(),
        content=messages,
    )

    print(f"✅ Created conversation with {conversation.message_count} messages")
    print(f"Title: {conversation.title}")
    print(f"Author: {conversation.author}")

    # Test successful parse result
    success_result = ParseResult(success=True, data=conversation, error=None)
    print("✅ Successful ParseResult created")
    assert success_result.success is True
    assert success_result.data is not None

    # Test failed parse result
    error_result = ParseResult(success=False, data=None, error="Test error message")
    print("✅ Error ParseResult created")
    assert error_result.success is False
    assert error_result.error == "Test error message"

    # Test JSON serialization
    json_output = conversation.model_dump_json(indent=2)
    print("✅ JSON serialization successful")
    print(f"JSON length: {len(json_output)} characters")

    # Show a preview of the conversation
    print("\n📝 Conversation Preview:")
    for i, msg in enumerate(conversation.content[:2]):
        role_emoji = "🤖" if msg.role == "assistant" else "👤"
        content_preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        print(f"{role_emoji} {msg.role.title()}: {content_preview}")

    print("✅ Pydantic model tests passed!\n")


def test_database_structure() -> None:
    """Test the expected database structure matches our models."""
    print("🗄️  Testing database structure compatibility...")

    # Create a conversation that would be stored in the database
    conversation = ConversationData(
        url="https://chatgpt.com/share/test-id",
        title="Test Conversation",
        author="Test Author",
        import_date=datetime.now().isoformat(),
        content=[
            ConversationMessage(role="user", content="Test message 1"),
            ConversationMessage(role="assistant", content="Test response 1"),
        ],
    )

    # Convert to database format (what we'd store in the content column)
    content_json = [msg.model_dump() for msg in conversation.content]

    print("✅ Database content structure:")
    print(f"  URL: {conversation.url}")
    print(f"  Title: {conversation.title}")
    print(f"  Author: {conversation.author}")
    print(f"  Import Date: {conversation.import_date}")
    print(f"  Content (JSON): {len(content_json)} messages")

    # Verify the content structure matches expected format
    for msg in content_json:
        assert "role" in msg, "Message must have 'role' field"
        assert "content" in msg, "Message must have 'content' field"
        assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"
        assert isinstance(msg["content"], str), "Content must be a string"

    print("✅ Database structure tests passed!\n")


def main() -> int:
    """Run all tests."""
    print("🧪 ChatGPT Parser Test Suite")
    print("=" * 40)

    try:
        test_url_validation()
        test_pydantic_models()
        test_database_structure()

        print("🎉 All tests passed successfully!")
        print("\n📋 Next steps:")
        print("1. Test with a real ChatGPT share URL")
        print("2. Implement database storage")
        print("3. Create backend API endpoints")
        print("4. Build frontend components")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
