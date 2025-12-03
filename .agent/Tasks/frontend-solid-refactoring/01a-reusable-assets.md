# Reusable Assets Inventory

## Agent
codebase-analyzer

## Timestamp
2025-12-03 17:00

## Feature Requirements Summary
This refactoring focuses on:
1. Extracting shared SSE streaming infrastructure
2. Splitting large hooks (useConversationImport, useProjectDraftState)
3. Creating generic section components
4. Standardizing model selection usage
5. Replacing direct fetch() calls with api-client

---

## MUST REUSE (Existing, Ready to Use)

### Shared API Infrastructure

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| API Fetch Wrapper | `apiFetch<T>()` | `frontend/src/shared/lib/api-client.ts` | `import { apiFetch } from '@/shared/lib/api-client'` |
| SSE Stream Fetch | `apiStream()` | `frontend/src/shared/lib/api-client.ts` | `import { apiStream } from '@/shared/lib/api-client'` |
| API Error Class | `ApiError` | `frontend/src/shared/lib/api-client.ts` | `import { ApiError } from '@/shared/lib/api-client'` |
| API Config | `config.apiUrl` | `frontend/src/shared/lib/config.ts` | `import { config } from '@/shared/lib/config'` |
| Constants | `constants.POLL_INTERVAL_MS` | `frontend/src/shared/lib/config.ts` | `import { constants } from '@/shared/lib/config'` |
| Class Names Utility | `cn()` | `frontend/src/shared/lib/utils.ts` | `import { cn } from '@/shared/lib/utils'` |

**API Client Pattern:**
```typescript
// Regular API call
const data = await apiFetch<LLMDefaultsResponse>('/llm-defaults/idea_generation');

// POST with body
const result = await apiFetch<Response>('/endpoint', {
  method: 'POST',
  body: { key: 'value' }  // Auto JSON.stringify'd
});

// SSE streaming
const response = await apiStream('/conversations/import', {
  method: 'POST',
  headers: { Accept: 'text/event-stream' },
  body: JSON.stringify(body),
});
```

### Model Selection

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Model Selection Hook | `useModelSelection()` | `frontend/src/features/project-draft/hooks/useModelSelection.ts` | `import { useModelSelection } from '@/features/project-draft/hooks/useModelSelection'` |
| Model Selector Data | `useModelSelectorData()` | `frontend/src/features/model-selector/hooks/useModelSelectorData.ts` | `import { useModelSelectorData } from '@/features/model-selector/hooks/useModelSelectorData'` |

**useModelSelection API:**
```typescript
interface ModelSelectionState {
  selectedModel: string;
  selectedProvider: string;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: { supportsImages: boolean; supportsPdfs: boolean };
}

interface ModelSelectionActions {
  handleModelChange: (model: string, provider: string) => void;
  handleModelDefaults: (model: string, provider: string) => void;
  handleModelCapabilities: (capabilities: { supportsImages: boolean; supportsPdfs: boolean }) => void;
}
```

### Context/State Management

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Auth Context | `useAuth()` | `frontend/src/shared/hooks/useAuth.ts` | `import { useAuth } from '@/shared/hooks/useAuth'` |
| Conversation Context | `useConversationContext()` | `frontend/src/features/conversation/context/ConversationContext.tsx` | `import { useConversationContext } from '@/features/conversation/context/ConversationContext'` |

### API Adapters (Anti-corruption Layer)

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Error Response Check | `isErrorResponse()` | `frontend/src/shared/lib/api-adapters.ts` | `import { isErrorResponse } from '@/shared/lib/api-adapters'` |
| Conversation Converters | `convertApiConversation()` | `frontend/src/shared/lib/api-adapters.ts` | `import { convertApiConversation } from '@/shared/lib/api-adapters'` |
| Research Run Converters | `convertApiResearchRun()` | `frontend/src/shared/lib/api-adapters.ts` | `import { convertApiResearchRun } from '@/shared/lib/api-adapters'` |

### UI Components

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Button | `Button` | `frontend/src/shared/components/ui/button.tsx` | `import { Button } from '@/shared/components/ui/button'` |
| Pagination | `Pagination*` | `frontend/src/shared/components/ui/pagination.tsx` | `import { Pagination } from '@/shared/components/ui/pagination'` |
| Avatar | `Avatar*` | `frontend/src/shared/components/ui/avatar.tsx` | `import { Avatar } from '@/shared/components/ui/avatar'` |
| Markdown Renderer | `Markdown` | `frontend/src/shared/components/Markdown.tsx` | `import { Markdown } from '@/shared/components/Markdown'` |
| File Upload | `FileUpload` | `frontend/src/shared/components/FileUpload.tsx` | `import { FileUpload } from '@/shared/components/FileUpload'` |
| Protected Route | `ProtectedRoute` | `frontend/src/shared/components/ProtectedRoute.tsx` | `import { ProtectedRoute } from '@/shared/components/ProtectedRoute'` |

### SSE Event Types (Reusable)

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Import States Enum | `ImportState` | `frontend/src/features/conversation-import/types/types.ts` | `import { ImportState } from '@/features/conversation-import/types/types'` |
| SSE Event Types | `SSEEvent`, `SSEState`, etc. | `frontend/src/features/conversation-import/types/types.ts` | `import { SSEEvent, SSEState, SSEContent } from '@/features/conversation-import/types/types'` |

---

## CONSIDER REUSING (Existing, May Need Extension)

### Hooks That May Need Generalization

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| Generic SSE Streaming | `useResearchRunSSE` | `frontend/src/features/research/hooks/useResearchRunSSE.ts` | Best pattern with reconnection logic. Extract common SSE logic. |
| File Upload State | `useChatFileUpload` | `frontend/src/features/project-draft/hooks/useChatFileUpload.ts` | Good SRP example. May be reusable for other upload scenarios. |
| Search Hook | `useSearch` | `frontend/src/shared/hooks/useSearch.ts` | Well-structured with caching/debounce. Could be pattern for other data hooks. |

### Common Streaming Patterns Found

All 4 streaming hooks share this pattern that should be extracted:

```typescript
// Pattern in: useResearchRunSSE, useChatStreaming, useConversationImport, useManualIdeaImport

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n");  // or "\n\n" for some
  buffer = lines.pop() || "";

  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const eventData = JSON.parse(line);
      // Handle event by type...
    } catch (e) {
      console.warn("Failed to parse JSON line:", line);
    }
  }
}
```

### Diff Utilities

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| Text Diff Display | `generateStringDiff()` | `frontend/src/features/project-draft/utils/diffUtils.tsx` | Currently feature-specific. Consider moving to shared if needed elsewhere. |
| Diff Components | `DiffContent` interface | `frontend/src/features/project-draft/utils/diffUtils.tsx` | Returns ReactElement[]. Could be useful for other comparison views. |

---

## PATTERNS TO FOLLOW

### 1. Hook Structure Pattern (from useModelSelectorData)
**Location**: `frontend/src/features/model-selector/hooks/useModelSelectorData.ts`

Best example of clean React Query usage:
- Separate interfaces for props, result, and internal types
- JSDoc comments for public API
- Logical grouping: queries, mutations, return value
- Uses `apiFetch` from api-client

```typescript
interface UseXxxProps { ... }
interface UseXxxReturn { ... }

export function useXxx({ prop }: UseXxxProps): UseXxxReturn {
  const queryClient = useQueryClient();
  
  const dataQuery = useQuery({
    queryKey: ["key", prop],
    queryFn: () => apiFetch<Response>(`/endpoint/${prop}`),
  });

  const mutation = useMutation({
    mutationFn: (data) => apiFetch<Response>('/endpoint', { method: 'POST', body: data }),
    onSuccess: (data) => {
      queryClient.setQueryData(["key", prop], data);
    },
  });

  return {
    data: dataQuery.data ?? null,
    isLoading: dataQuery.isLoading,
    mutate: mutation.mutateAsync,
    isMutating: mutation.isPending,
  };
}
```

### 2. Single Responsibility Hook Pattern (from useChatFileUpload)
**Location**: `frontend/src/features/project-draft/hooks/useChatFileUpload.ts`

Excellent example of focused hook:
- ~97 lines, single concern
- Clear state/action separation
- Uses useCallback for all handlers
- Derives state with useMemo

### 3. Context Provider Pattern (from ConversationContext)
**Location**: `frontend/src/features/conversation/context/ConversationContext.tsx`

```typescript
interface ContextValue { ... }

const MyContext = createContext<ContextValue | null>(null);

export function useMyContext() {
  const context = useContext(MyContext);
  if (!context) {
    throw new Error("useMyContext must be used within MyProvider");
  }
  return context;
}

export function MyProvider({ children }: { children: ReactNode }) {
  const value = useMemo(() => ({ ... }), [deps]);
  return <MyContext.Provider value={value}>{children}</MyContext.Provider>;
}
```

### 4. Return Type Organization (from useConversationImport)
**Location**: `frontend/src/features/conversation-import/hooks/useConversationImport.ts`

Good pattern for complex hooks - group returns by category:
```typescript
return {
  state: { url, error, streamingContent, ... },
  model: { selected, provider, ... },
  conflict: { hasConflict, items, ... },
  status: { isIdle, isImporting, canSubmit, ... },
  actions: { setUrl, startImport, reset, ... },
  streamingRef,
};
```

### 5. Component Props Interface Pattern (from Section components)
**Location**: `frontend/src/features/project-draft/components/HypothesisSection.tsx`

```typescript
interface XxxSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}
```

---

## CREATE NEW (Not Found, Need to Build)

### Priority 1: Shared SSE Infrastructure

| What to Create | Suggested Location | Notes |
|----------------|-------------------|-------|
| `useSSEStream` | `frontend/src/shared/hooks/useSSEStream.ts` | Generic SSE hook with buffer management, line parsing, event dispatch, reconnection logic. Based on pattern from `useResearchRunSSE`. |
| `useStreamingImport` | `frontend/src/shared/hooks/useStreamingImport.ts` | Base hook for import streaming (shared by conversation import and manual import) |

**Proposed useSSEStream API:**
```typescript
interface UseSSEStreamOptions<T> {
  url: string;
  enabled: boolean;
  onEvent: (event: T) => void;
  onComplete?: () => void;
  onError?: (error: string) => void;
  reconnect?: boolean;
  maxReconnectAttempts?: number;
}

interface UseSSEStreamReturn {
  isConnected: boolean;
  connectionError: string | null;
  reconnect: () => void;
  disconnect: () => void;
}
```

### Priority 2: Split Hook Pieces

| What to Create | Suggested Location | Notes |
|----------------|-------------------|-------|
| `useImportFormState` | `frontend/src/features/conversation-import/hooks/useImportFormState.ts` | Form state: url, error, validation |
| `useImportModelState` | `frontend/src/features/conversation-import/hooks/useImportModelState.ts` | Reuses `useModelSelection` internally |
| `useImportStreamingState` | `frontend/src/features/conversation-import/hooks/useImportStreamingState.ts` | Uses shared `useSSEStream` |
| `useImportConflictResolution` | `frontend/src/features/conversation-import/hooks/useImportConflictResolution.ts` | Conflict + model limit states |
| `useProjectDraftData` | `frontend/src/features/project-draft/hooks/useProjectDraftData.ts` | Data loading + polling |
| `useProjectDraftEdit` | `frontend/src/features/project-draft/hooks/useProjectDraftEdit.ts` | Edit mode state |
| `useProjectDraftActions` | `frontend/src/features/project-draft/hooks/useProjectDraftActions.ts` | Save, create project |

### Priority 3: Generic Components

| What to Create | Suggested Location | Notes |
|----------------|-------------------|-------|
| `StringSection` | `frontend/src/features/project-draft/components/StringSection.tsx` | Generic section with title, content, optional diff, optional edit button. Replaces HypothesisSection, AbstractSection, RelatedWorkSection, ExpectedOutcomeSection |

**Proposed StringSection API:**
```typescript
interface StringSectionProps {
  title: string;
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
  variant?: 'default' | 'primary-border' | 'success-box';
  className?: string;
}
```

---

## EXTRACTION CANDIDATES

### Code That Should Be Moved to Shared

| Current Location | Asset | Suggested New Location | Why |
|------------------|-------|------------------------|-----|
| `features/project-draft/hooks/useModelSelection.ts` | `useModelSelection` | `shared/hooks/useModelSelection.ts` | Used by multiple features (ConversationContext, project-draft). Core reusable state pattern. |
| `features/conversation-import/types/types.ts` | `ImportState`, `SSEEvent` types | `shared/types/sse.ts` | SSE types needed by shared useSSEStream hook |
| N/A | Streaming buffer/parsing logic | `shared/lib/sse-utils.ts` | Common across 4 hooks |

### Inconsistencies to Standardize

| Issue | Files | Resolution |
|-------|-------|------------|
| Direct `fetch()` vs `apiStream()` | `useChatStreaming.ts` (line 120), `useResearchRunSSE.ts` (line 128) | Replace with `apiStream()` from api-client |
| Direct `config.apiUrl` fetch vs `apiFetch` | `ProjectDraft.tsx` (line 85-108) | Replace with `apiFetch()` |
| Buffer split pattern varies | `\n` vs `\n\n` | Standardize in shared SSE hook |

---

## Naming Conventions Observed

| Type | Convention | Examples |
|------|------------|----------|
| Hooks | `use{Feature}{Purpose}` | `useModelSelection`, `useChatStreaming`, `useProjectDraftState` |
| Components | PascalCase, descriptive | `HypothesisSection`, `ChatMessageList`, `CreateProjectModal` |
| Utils | camelCase function names | `generateStringDiff`, `isIdeaGenerating`, `validateUrl` |
| Types | PascalCase interfaces | `ModelSelectionState`, `UseXxxReturn`, `SSEEvent` |
| Files | kebab-case | `api-client.ts`, `use-model-selection.ts` (but some use camelCase like `useModelSelection.ts`) |

**Note**: There's inconsistency in hook file naming - some use kebab-case, some use camelCase. The project convention from docs says kebab-case.

---

## For Architect

Key reusability requirements:
1. **DO NOT** create new API fetch wrapper - use `apiFetch`/`apiStream` from `shared/lib/api-client.ts`
2. **DO NOT** create new model selection state - use `useModelSelection` from `project-draft/hooks`
3. **REUSE** `ImportState` and `SSEEvent` types from `conversation-import/types/types.ts`
4. **FOLLOW** hook pattern from `useModelSelectorData` (React Query) and `useChatFileUpload` (SRP)
5. **EXTRACT** SSE streaming logic to `shared/hooks/useSSEStream.ts` as foundation

## For Executor

Before implementing ANY utility/hook/component:
1. Check this inventory first
2. Search the codebase if not listed here: `grep -rn "export function" frontend/src/`
3. Only create new if confirmed nothing exists
4. Use `apiStream()` for all SSE endpoints, `apiFetch()` for all REST endpoints
5. Follow kebab-case for file names per project convention
