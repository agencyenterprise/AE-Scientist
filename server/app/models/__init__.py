"""
Models module for the AE Scientist

This module exports all Pydantic models for data validation and API contracts.
"""

# Auth models
from app.models.auth import AuthStatus, AuthUser, ServiceKey, User, UserSession

# Billing models
from app.models.billing import (
    BillingWalletResponse,
    CheckoutSessionCreateRequest,
    CheckoutSessionCreateResponse,
    CreditTransactionModel,
    FundingOptionListResponse,
    FundingOptionModel,
)
from app.models.chat import ChatMessage, ChatRequest, ChatResponse

# Conversation models
from app.models.conversations import (
    ChatMessageData,
    ConversationResponse,
    ConversationUpdate,
    ImportChatCreateNew,
    ImportChatGPTConversation,
    ImportChatPrompt,
    ImportChatUpdateExisting,
    ImportedChat,
    ImportedChatMessage,
    ManualIdeaSeedRequest,
    ParseErrorResult,
    ParseResult,
    ParseSuccessResult,
    ResearchRunSummary,
)

# Idea models
from app.models.ideas import (
    Idea,
    IdeaCreateRequest,
    IdeaRefinementRequest,
    IdeaRefinementResponse,
    IdeaResponse,
    IdeaVersion,
    IdeaVersionsResponse,
)
from app.models.imported_conversation_summary import ImportedConversationSummaryUpdate

# LLM prompt models
from app.models.llm_prompts import (
    LLMDefault,
    LLMDefaultsResponse,
    LLMDefaultsUpdateRequest,
    LLMDefaultsUpdateResponse,
    LLMModel,
    LLMPromptCreateRequest,
    LLMPromptDeleteRequest,
    LLMPromptDeleteResponse,
    LLMPromptResponse,
    LLMProvidersResponse,
)

# LLM token usage models
from app.models.llm_token_usage import LlmTokenUsage, LLMTokenUsageCost
from app.models.research_pipeline import (
    ArtifactPresignedUrlResponse,
    ArtifactType,
    ChildConversationInfo,
    LlmReviewNotFoundResponse,
    LlmReviewResponse,
    ResearchRunArtifactMetadata,
    ResearchRunCodeExecution,
    ResearchRunDetailsResponse,
    ResearchRunEvent,
    ResearchRunInfo,
    ResearchRunListItem,
    ResearchRunListResponse,
    ResearchRunPaperGenerationProgress,
    ResearchRunStageProgress,
    ResearchRunStageSkipWindow,
    ResearchRunSubstageEvent,
    ResearchRunSubstageSummary,
    RunTreeNode,
    RunTreeResponse,
    TreeVizItem,
)
from app.models.sse import (
    ChatStreamEvent,
    ConversationImportStreamEvent,
    ResearchRunStreamEvent,
    WalletStreamEvent,
)

__all__ = [
    # Conversation models
    "ImportedChatMessage",
    "ImportedChat",
    "ConversationResponse",
    "ConversationUpdate",
    "ResearchRunSummary",
    "ResearchRunInfo",
    "ResearchRunStageProgress",
    "ResearchRunSubstageEvent",
    "ResearchRunSubstageSummary",
    "ResearchRunPaperGenerationProgress",
    "ResearchRunStageSkipWindow",
    "ResearchRunEvent",
    "ResearchRunArtifactMetadata",
    "ArtifactPresignedUrlResponse",
    "ArtifactType",
    "ResearchRunDetailsResponse",
    "ResearchRunCodeExecution",
    "ResearchRunListItem",
    "ChildConversationInfo",
    "ResearchRunListResponse",
    "TreeVizItem",
    "LlmReviewResponse",
    "LlmReviewNotFoundResponse",
    "RunTreeNode",
    "RunTreeResponse",
    "ImportChatGPTConversation",
    "ImportChatPrompt",
    "ImportChatCreateNew",
    "ImportChatUpdateExisting",
    "ManualIdeaSeedRequest",
    "ChatMessageData",
    "ParseSuccessResult",
    "ParseErrorResult",
    "ParseResult",
    # Idea models
    "IdeaVersion",
    "Idea",
    "IdeaCreateRequest",
    "IdeaRefinementRequest",
    "IdeaResponse",
    "IdeaVersionsResponse",
    "IdeaRefinementResponse",
    # LLM prompt models
    "LLMDefault",
    "LLMDefaultsResponse",
    "LLMDefaultsUpdateRequest",
    "LLMDefaultsUpdateResponse",
    "LLMModel",
    "LLMPromptCreateRequest",
    "LLMPromptDeleteRequest",
    "LLMPromptDeleteResponse",
    "LLMPromptResponse",
    "LLMProvidersResponse",
    # Chat models
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    # Auth models
    "User",
    "UserSession",
    "ServiceKey",
    "AuthUser",
    "AuthStatus",
    # Imported conversation summary models
    "ImportedConversationSummaryUpdate",
    # LLM token usage models
    "LlmTokenUsage",
    "LLMTokenUsageCost",
    # Billing models
    "BillingWalletResponse",
    "CreditTransactionModel",
    "FundingOptionModel",
    "FundingOptionListResponse",
    "CheckoutSessionCreateRequest",
    "CheckoutSessionCreateResponse",
    # SSE models
    "ChatStreamEvent",
    "ConversationImportStreamEvent",
    "ResearchRunStreamEvent",
    "WalletStreamEvent",
]
