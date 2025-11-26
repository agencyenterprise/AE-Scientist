#!/usr/bin/env python3
"""
Playground script to test the metacognition service integration for long context handling.

This script demonstrates:
1. Starting the metacognition service
2. Making calls to the /manage_conversation endpoint
3. Handling conversation summarization for long contexts

Requirements:
- The metacognition service needs to be running (we'll start it in this script)
- Environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, OPEN_ROUTER_API_KEY
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from backend/.env
env_path = Path(__file__).parent.parent / ".env"
print("env_path", env_path)
load_dotenv(dotenv_path=env_path)

# Constants
METACOGNITION_API_URL = os.environ["METACOGNITION_API_URL"]
METACOGNITION_AUTH_TOKEN = os.environ["METACOGNITION_AUTH_TOKEN"]
print("METACOGNITION_AUTH_TOKEN", METACOGNITION_AUTH_TOKEN)


# NOTE: On-disk summary fallback removed. Consumers should rely on the API's
# latest_summary field and poll until it is populated.


class MetacognitionService:
    """Client for the metacognition service API."""

    def __init__(
        self, base_url: str = METACOGNITION_API_URL, auth_token: str = METACOGNITION_AUTH_TOKEN
    ):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def health_check(self) -> bool:
        """Check if the service is running."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Health check failed: {e}")
            return False

    def manage_conversation(
        self,
        summary_id: Optional[int],
        index_of_first_new_message: int,
        new_messages: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Manage a conversation using the metacognition service.

        Args:
            summary_id: Existing conversation ID or None for new conversation
            index_of_first_new_message: Index of the first new message to add
            new_messages: List of new messages to add to the conversation

        Returns:
            Tuple of (success, response_data)
        """
        payload = {
            "summary_id": summary_id,
            "index_of_first_new_message": index_of_first_new_message,
            "new_messages": new_messages,
        }

        try:
            response = requests.post(
                f"{self.base_url}/manage_conversation",
                json=payload,
                headers=self.headers,
                timeout=120,  # Longer timeout for LLM processing
            )

            response_data = response.json()
            # Print the full response payload from the summarizer service
            try:
                logger.info(
                    "↩️ manage_conversation response:\n%s", json.dumps(response_data, indent=2)
                )
            except Exception:
                logger.info("↩️ manage_conversation response (raw): %s", str(response_data))
            success = response.status_code == 200 and response_data.get("status") == "success"

            if not success:
                logger.error(f"Conversation management failed: {response_data}")

            return success, response_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return False, {"error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode failed: {e}")
            return False, {"error": "Invalid JSON response"}

    def wait_for_processing(
        self,
        summary_id: int,
        index_of_first_new_message: int,
        max_wait_seconds: int,
        check_interval_seconds: int,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Wait for background processing to complete by polling the conversation status.

        Args:
            summary_id: The conversation ID to check
            index_of_first_new_message: The index of the first new message to add
            max_wait_seconds: Maximum time to wait for processing
            check_interval_seconds: How often to check the status

        Returns:
            Tuple of (success, final_response)
        """
        import time

        logger.info(f"⏳ Waiting for background processing of conversation {summary_id}...")
        logger.info(f"Max wait: {max_wait_seconds}s, Check interval: {check_interval_seconds}s")

        start_time = time.time()

        while (time.time() - start_time) < max_wait_seconds:
            # Check current conversation status
            success, response = self.manage_conversation(
                summary_id=summary_id,
                index_of_first_new_message=index_of_first_new_message,
                new_messages=[],  # Empty list just to check status
            )

            if success:
                latest_processed_message_idx = response.get("latest_processed_message_idx")
                summary = response.get("latest_summary", "")

                logger.info(
                    f"📊 Status check: processed_idx={latest_processed_message_idx}, summary_length={len(summary) if summary else 0}"
                )

                # Check if processing is complete (processed_idx is not None and summary exists)
                if (
                    latest_processed_message_idx is not None
                    and latest_processed_message_idx > index_of_first_new_message
                    and summary
                ):
                    logger.info(
                        f"✅ Processing complete! Processed {latest_processed_message_idx + 1} messages"
                    )
                    return True, response

            else:
                logger.error(f"Status check failed: {response}")

            # Wait before next check
            time.sleep(check_interval_seconds)

        logger.warning(f"⏰ Timeout after {max_wait_seconds}s - processing may still be ongoing")

        # Return final status even if timeout
        success, response = self.manage_conversation(
            summary_id=summary_id, index_of_first_new_message=0, new_messages=[]
        )
        return success, response

    def upload_document(
        self,
        content: str,
        description: str,
        document_type: str,
        is_new_document: bool,
        document_id: int,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Upload an external document for processing.

        Note: Binary files (PDF/images) must be converted to text before upload.
        """
        payload = {
            "content": content,
            "description": description,
            "document_type": document_type,
            "document_id": None if is_new_document else document_id,
        }

        try:
            response = requests.post(
                f"{self.base_url}/upload_document",
                json=payload,
                headers=self.headers,
                timeout=120,
            )
            response_data = response.json()
            success = response.status_code == 200 and response_data.get("status") == "success"
            if not success:
                logger.error(f"Document upload failed: {response_data}")
            return success, response_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Upload request failed: {e}")
            return False, {"error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Upload JSON decode failed: {e}")
            return False, {"error": "Invalid JSON response"}

    def add_document_to_conversation(
        self,
        conversation_id: int,
        document_id: int,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Link a document to a conversation so the worker processes it into the summary.
        """
        payload = {
            "conversation_id": conversation_id,
            "document_id": document_id,
        }

        try:
            response = requests.post(
                f"{self.base_url}/add_document_to_conversation",
                json=payload,
                headers=self.headers,
                timeout=60,
            )
            response_data = response.json()
            success = response.status_code == 200 and response_data.get("status") == "success"
            if not success:
                logger.error(f"Add document to conversation failed: {response_data}")
            return success, response_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Link request failed: {e}")
            return False, {"error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Link JSON decode failed: {e}")
            return False, {"error": "Invalid JSON response"}


def create_sample_long_conversation() -> List[Dict[str, Any]]:
    """Create a sample long conversation for testing."""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant discussing software architecture patterns.",
        },
        {
            "role": "user",
            "content": "I'm working on a large-scale web application and need advice on microservices architecture. Can you help me understand the key patterns?",
        },
        {
            "role": "assistant",
            "content": "Absolutely! Microservices architecture involves several key patterns. Let me start with the fundamental ones: 1) Service Decomposition - breaking your monolith into business capability-aligned services, 2) API Gateway pattern for unified client access, 3) Database per Service to ensure loose coupling, 4) Saga pattern for distributed transactions, and 5) Circuit Breaker for fault tolerance. Which of these would you like me to elaborate on first?",
        },
        {
            "role": "user",
            "content": "Let's dive deep into the API Gateway pattern. I'm particularly interested in authentication, rate limiting, and request routing strategies.",
        },
        {
            "role": "assistant",
            "content": "Great choice! The API Gateway is crucial for microservices. For authentication, you typically implement JWT token validation at the gateway level, often with OAuth 2.0/OIDC integration. The gateway acts as a security perimeter, validating tokens before routing requests to backend services. For rate limiting, implement token bucket or sliding window algorithms - I recommend per-client rate limits with different tiers (free, premium, enterprise). Request routing can be path-based (/api/users/* → user-service), header-based (version routing), or even weighted routing for A/B testing. Popular tools include Kong, Istio Gateway, or cloud-native solutions like AWS API Gateway.",
        },
        {
            "role": "user",
            "content": "That's very helpful. Now I'm thinking about data consistency patterns. In a distributed system with multiple services, how do you handle transactions that span multiple services? The Saga pattern you mentioned sounds interesting.",
        },
        {
            "role": "assistant",
            "content": "Excellent question! The Saga pattern is indeed the go-to solution for distributed transactions. There are two main approaches: 1) Choreography-based sagas where each service knows what to do next and publishes events (more decoupled but harder to track), and 2) Orchestration-based sagas with a central coordinator (easier to monitor but creates a single point of failure). For example, in an e-commerce order saga: Reserve inventory → Process payment → Create shipping → Update order status. If payment fails, you'd compensate by releasing inventory. Key considerations: idempotency of operations, compensation logic design, and handling partial failures. Tools like Temporal, Zeebe, or cloud services like AWS Step Functions can help orchestrate these complex workflows.",
        },
    ]

    # # Add more messages to make it longer
    # for i in range(10):
    #     messages.extend(
    #         [
    #             {
    #                 "role": "user",
    #                 "content": f"Follow-up question {i + 1}: Can you elaborate more on the implementation details of the points you just made? I'm particularly interested in real-world examples and potential pitfalls.",
    #             },
    #             {
    #                 "role": "assistant",
    #                 "content": f"Certainly! For implementation detail {i + 1}, let me provide concrete examples... [This would be a very long detailed response in a real scenario, covering multiple aspects of microservices architecture, deployment strategies, monitoring, observability, security considerations, performance optimization, and operational best practices. The response would include code examples, architectural diagrams explanations, and references to industry standards and tools.]",
    #             },
    #         ]
    #     )

    return messages


def create_sample_document_content() -> str:
    """Create sample external document content (simulated extracted text)."""
    return (
        "Microservices Architecture in Practice\n\n"
        "This document provides practical guidance on implementing an API Gateway, applying the Saga pattern for "
        "distributed transactions, and designing fault-tolerant systems with circuit breakers. It includes tradeoffs "
        "between PostgreSQL and MongoDB for transactional systems, including ACID guarantees, reporting needs, and "
        "schema evolution.\n\n"
        "Key Takeaways:\n"
        "- Use PostgreSQL for e-commerce transactions and analytics.\n"
        "- Implement choreography-based sagas for decoupling; consider orchestration when observability and centralized "
        "control are required.\n"
        "- API Gateways should enforce auth, rate limiting, and request routing.\n"
    )


def test_conversation_summarization() -> bool:
    """Test the conversation summarization functionality."""
    logger.info("=== Testing Conversation Summarization ===")
    latest_processed_message_idx = 0

    # Create a sample long conversation
    messages = create_sample_long_conversation()
    logger.info(f"Created sample conversation with {len(messages)} messages")

    # Initialize the client
    client = MetacognitionService()

    logger.info("Creating new conversation...")
    success, response = client.manage_conversation(
        summary_id=None, index_of_first_new_message=0, new_messages=messages
    )

    if not success:
        logger.error(f"❌ Failed to create conversation: {response}")
        return False

    summary_id = response["summary_id"]

    logger.info("💡 Summary is processing in the background. Waiting for completion...")
    # Wait for background processing to complete
    waited, final_response = client.wait_for_processing(
        summary_id=summary_id,
        index_of_first_new_message=latest_processed_message_idx,
        max_wait_seconds=600,
        check_interval_seconds=5,
    )
    if waited:
        final_summary = final_response.get("latest_summary", "")
        latest_processed_message_idx = final_response.get("latest_processed_message_idx", 0)
        assert isinstance(
            latest_processed_message_idx, int
        ), f"Expected int latest_processed_message_idx, got {type(latest_processed_message_idx)}"
        if final_summary:
            logger.info("🎉 Background processing completed!")
            logger.info("Final summary (full):")
            logger.info(final_summary)
        else:
            logger.warning("⚠️  Processing completed but summary is still empty")
            logger.info(
                "If this persists, ensure the worker is running for the metacognition service."
            )
    else:
        logger.error(f"❌ Failed to get final processing status: {final_response}")

    # Proceed to document upload and linking regardless
    logger.info("Uploading external document and linking to conversation...")
    document_content = create_sample_document_content()
    upload_success, upload_resp = client.upload_document(
        content=document_content,
        description="External architecture article",
        document_type="article",
        is_new_document=True,
        document_id=0,
    )
    if not upload_success:
        logger.error(f"❌ Document upload failed: {upload_resp}")
        return False

    new_doc_id = upload_resp.get("document_id")
    assert isinstance(new_doc_id, int), f"Expected int document_id, got {type(new_doc_id)}"
    logger.info(f"✅ Document uploaded with ID: {new_doc_id}")

    link_success, link_resp = client.add_document_to_conversation(
        conversation_id=summary_id,
        document_id=new_doc_id,
    )
    if not link_success:
        logger.error(f"❌ Failed to link document: {link_resp}")
        return False

    # Adding new message after the document is linked, so that we get a new processed message idx
    success, response = client.manage_conversation(
        summary_id=summary_id,
        index_of_first_new_message=latest_processed_message_idx + 1,
        new_messages=[
            {
                "role": "user",
                "content": "Can you elaborate more on the implementation details of the points you just made? I'm particularly interested in real-world examples and potential pitfalls.",
            }
        ],
    )

    if not success:
        logger.error(f"❌ Failed to create conversation: {response}")
        return False

    logger.info("🔄 Waiting for summary update from external document...")
    waited_success, after_doc_resp = client.wait_for_processing(
        summary_id=summary_id,
        index_of_first_new_message=latest_processed_message_idx,
        max_wait_seconds=600,
        check_interval_seconds=5,
    )
    if not waited_success:
        logger.error(f"❌ Failed while waiting for document processing: {after_doc_resp}")
        return False

    updated_summary = after_doc_resp.get("latest_summary", "")
    if updated_summary:
        logger.info("📄 Updated summary (post-document, full):")
        logger.info(updated_summary)
        return True
    else:
        logger.info("📄 Updated summary (post-document): [EMPTY]")
        logger.info(
            "If no update appears, confirm the worker is running and has access to the uploaded document."
        )
        return False


def main() -> None:
    """Main function to test the metacognition service."""
    logger.info("Starting Metacognition Service Test")
    logger.info("=" * 50)

    # Check if .env file exists (for API base URL and auth token)
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        logger.error(f"❌ .env file not found at {env_path}")
        logger.error(
            "Please create backend/.env with METACOGNITION_API_URL and METACOGNITION_AUTH_TOKEN."
        )
        return

    try:
        # Connect to an already running service
        client = MetacognitionService()
        logger.info(f"Connecting to service at: {client.base_url}")
        if not client.health_check():
            logger.error("❌ Metacognition service is not reachable.")
            logger.error(
                "Please start it manually in another terminal (listening on localhost:8888) and try again."
            )
            return

        # Run the tests
        logger.info("\n" + "=" * 50)
        success = test_conversation_summarization()

        if success:
            logger.info("\n✅ All tests passed! The metacognition service is working correctly.")
            logger.info(
                "You can now integrate this service into your main application to handle long contexts."
            )
        else:
            logger.error("\n❌ Some tests failed. Check the logs above for details.")

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
    finally:
        logger.info("Test completed.")


if __name__ == "__main__":
    main()
