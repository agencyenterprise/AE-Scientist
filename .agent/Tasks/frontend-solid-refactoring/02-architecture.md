# Architecture Phase

## Agent
feature-architecture-expert

## Timestamp
2025-12-03 18:00

## Input Received
- Context: `.agent/Tasks/frontend-solid-refactoring/00-context.md`
- Planning: `.agent/Tasks/frontend-solid-refactoring/01-planning.md`
- PRD: `.agent/Tasks/frontend-solid-refactoring/PRD.md`
- Reusable Assets: `.agent/Tasks/frontend-solid-refactoring/01a-reusable-assets.md`

## Key Decisions from Planning

From `01-planning.md`:
1. **Start with SSE infrastructure** - Highest impact, unlocks subsequent refactoring
2. **Split hooks using facade pattern** - Maintains backward compatibility
3. **Create generic StringSection** - Clear DRY win with minimal risk
4. **Replace all direct fetch** - Use `apiFetch`/`apiStream` consistently

---

## Reusability (CRITICAL SECTION)

### Assets Being REUSED (Do NOT Recreate)

| Asset | Source Location | Used For |
|-------|-----------------|----------|
| `apiFetch<T>()` | `shared/lib/api-client.ts` | All REST API calls |
| `apiStream()` | `shared/lib/api-client.ts` | All SSE streaming requests |
| `ApiError` | `shared/lib/api-client.ts` | Error handling with status codes |
| `config.apiUrl` | `shared/lib/config.ts` | API base URL |
| `constants.POLL_INTERVAL_MS` | `shared/lib/config.ts` | Polling interval |
| `cn()` | `shared/lib/utils.ts` | Class name merging |
| `useModelSelection()` | `features/project-draft/hooks/useModelSelection.ts` | Model state management |
| `markdownComponents` | `features/project-draft/utils/markdownComponents.ts` | Markdown rendering config |
| `ImportState`, `SSEEvent` types | `features/conversation-import/types/types.ts` | SSE event typing |

### Assets Being CREATED (New)

| Asset | Location | Justification |
|-------|----------|---------------|
| `useSSEStream` | `shared/hooks/use-sse-stream.ts` | Generic SSE streaming - no equivalent exists |
| `useStreamingImport` | `shared/hooks/use-streaming-import.ts` | Base import streaming - consolidates duplicate patterns |
| `useImportFormState` | `features/conversation-import/hooks/use-import-form-state.ts` | Split from useConversationImport (SRP) |
| `useImportConflictResolution` | `features/conversation-import/hooks/use-import-conflict-resolution.ts` | Split from useConversationImport (SRP) |
| `useProjectDraftData` | `features/project-draft/hooks/use-project-draft-data.ts` | Split from useProjectDraftState (SRP) |
| `useProjectDraftEdit` | `features/project-draft/hooks/use-project-draft-edit.ts` | Split from useProjectDraftState (SRP) |
| `StringSection` | `features/project-draft/components/StringSection.tsx` | Generic section component (DRY) |

### Imports Required

```typescript
// From shared/lib (MUST REUSE)
import { apiFetch, apiStream, ApiError } from '@/shared/lib/api-client';
import { config, constants } from '@/shared/lib/config';
import { cn } from '@/shared/lib/utils';

// From existing features (MUST REUSE)
import { useModelSelection } from '@/features/project-draft/hooks/useModelSelection';
import { ImportState, SSEEvent, SSEState, SSEContent } from '@/features/conversation-import/types/types';
import { markdownComponents } from '@/features/project-draft/utils/markdownComponents';
```

---

## Reasoning

### SSE Infrastructure Architecture

**Pattern**: Generic event-driven streaming hook with callback-based event handling.

**Rationale**: After analyzing all 4 streaming hooks (`useConversationImport`, `useManualIdeaImport`, `useChatStreaming`, `useResearchRunSSE`), they share:
- Buffer management and line parsing logic
- AbortController for cancellation
- Error handling with retry capability
- Connection state tracking

The key differences are:
- Event types and handlers (business logic)
- Line delimiter (`\n` vs `\n\n` vs `data: ` prefix)
- Reconnection behavior (only useResearchRunSSE has it)

**Decision**: Create a generic `useSSEStream` that accepts:
1. A parser function to handle different line formats
2. Event callbacks for type-safe handling
3. Optional reconnection configuration

### Hook Splitting Strategy

**Pattern**: Facade pattern for backward compatibility.

**Rationale**: The existing hooks (`useConversationImport`, `useProjectDraftState`) are used by multiple components. Splitting them directly would:
- Break existing consumers
- Require simultaneous updates to all call sites
- Risk introducing bugs during refactoring

**Decision**:
1. Create focused sub-hooks with single responsibilities
2. Keep the original hook as a facade that composes sub-hooks
3. Original API is preserved - consumers continue working unchanged
4. New components can import sub-hooks directly for better granularity

### StringSection Component Architecture

**Pattern**: Configurable component with variant prop.

**Rationale**: The 4 string section components differ only in:
- Title text
- Border styling (only HypothesisSection has `border-l-4 border-primary`)
- Content text color (`text-foreground` vs `text-foreground/90`)
- Content background (only ExpectedOutcomeSection has green background)

**Decision**: Create `StringSection` with:
- Required `title` and `content` props
- `variant` prop for styling variations
- Optional `onEdit` callback
- Optional `diffContent` for comparison mode

---

## File Structure (New Files)

### Shared Hooks

```
frontend/src/shared/hooks/
  use-sse-stream.ts              # Generic SSE streaming infrastructure
  use-streaming-import.ts        # Base streaming import hook
```

**`use-sse-stream.ts`**
- Purpose: Generic SSE connection management with buffer handling
- Key exports: `useSSEStream`, `SSEStreamOptions`, `SSEStreamReturn`
- Dependencies: `apiStream` from api-client

**`use-streaming-import.ts`**
- Purpose: Base hook for streaming import operations
- Key exports: `useStreamingImport`, `StreamingImportOptions`, `StreamingImportReturn`
- Dependencies: `useSSEStream`

### Conversation Import Feature

```
frontend/src/features/conversation-import/hooks/
  use-import-form-state.ts       # Form state (url, error, validation)
  use-import-conflict-resolution.ts  # Conflict and model limit handling
```

**`use-import-form-state.ts`**
- Purpose: Manage import form URL and validation state
- Key exports: `useImportFormState`, `ImportFormState`, `ImportFormActions`
- Dependencies: `validateUrl`, `getUrlValidationError` from existing utils

**`use-import-conflict-resolution.ts`**
- Purpose: Handle conflict detection and resolution workflows
- Key exports: `useImportConflictResolution`, `ConflictState`, `ConflictActions`
- Dependencies: None (pure state management)

### Project Draft Feature

```
frontend/src/features/project-draft/hooks/
  use-project-draft-data.ts      # Data loading and polling
  use-project-draft-edit.ts      # Edit mode state management

frontend/src/features/project-draft/components/
  StringSection.tsx              # Generic string section component
```

**`use-project-draft-data.ts`**
- Purpose: Load project draft data and handle polling during generation
- Key exports: `useProjectDraftData`, `ProjectDraftDataReturn`
- Dependencies: `apiFetch`, `constants.POLL_INTERVAL_MS`, `isIdeaGenerating`

**`use-project-draft-edit.ts`**
- Purpose: Manage edit mode state and title/description editing
- Key exports: `useProjectDraftEdit`, `ProjectDraftEditReturn`
- Dependencies: None (pure state management)

**`StringSection.tsx`**
- Purpose: Reusable section component for string content
- Key exports: `StringSection`, `StringSectionProps`
- Dependencies: `ReactMarkdown`, `markdownComponents`, `cn`, `Pencil` icon

---

## File Structure (Modified Files)

### Files to Modify

| File | Changes | Why |
|------|---------|-----|
| `useConversationImport.ts` | Refactor to use `useSSEStream`, `useImportFormState`, `useImportConflictResolution` | SRP, code reuse |
| `useManualIdeaImport.ts` | Refactor to use `useStreamingImport` | DRY, eliminate duplicate streaming |
| `useChatStreaming.ts` | Replace direct `fetch` with `apiStream`, use `useSSEStream` pattern | DIP, consistency |
| `useResearchRunSSE.ts` | Replace direct `fetch` with `apiStream` | DIP compliance |
| `useProjectDraftState.ts` | Compose `useProjectDraftData` and `useProjectDraftEdit` | SRP |
| `HypothesisSection.tsx` | Replace with `StringSection` usage | DRY |
| `AbstractSection.tsx` | Replace with `StringSection` usage | DRY |
| `RelatedWorkSection.tsx` | Replace with `StringSection` usage | DRY |
| `ExpectedOutcomeSection.tsx` | Replace with `StringSection` usage | DRY |
| `ProjectDraft.tsx` | Replace direct `fetch` with `apiFetch` | DIP compliance |

---

## API Designs

### useSSEStream

```typescript
// frontend/src/shared/hooks/use-sse-stream.ts

/**
 * Parser function type for converting raw SSE lines to events
 * Different SSE endpoints use different formats:
 * - Import: JSON per line, no prefix
 * - Research: "data: " prefix with "\n\n" delimiter
 * - Chat: JSON per line, no prefix
 */
export type SSELineParser<T> = (line: string) => T | null;

export interface SSEStreamOptions<TEvent> {
  /** URL path for the SSE endpoint (will be prefixed with apiUrl) */
  url: string;
  /** HTTP method (default: 'GET') */
  method?: 'GET' | 'POST';
  /** Request body for POST requests */
  body?: object;
  /** Whether the stream should be active */
  enabled: boolean;
  /** Parse raw line into typed event (return null to skip) */
  parseEvent: SSELineParser<TEvent>;
  /** Handle parsed event */
  onEvent: (event: TEvent) => void;
  /** Called when stream completes normally */
  onComplete?: () => void;
  /** Called on error (connection or parsing) */
  onError?: (error: string) => void;
  /** Line delimiter (default: '\n') */
  delimiter?: string;
  /** Enable auto-reconnection on connection loss */
  reconnect?: boolean;
  /** Max reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
}

export interface SSEStreamReturn {
  /** Whether the stream is currently connected */
  isConnected: boolean;
  /** Connection error message, if any */
  connectionError: string | null;
  /** Manually trigger reconnection */
  reconnect: () => void;
  /** Disconnect the stream */
  disconnect: () => void;
}

export function useSSEStream<TEvent>(
  options: SSEStreamOptions<TEvent>
): SSEStreamReturn;
```

**Usage Example (Research Run):**

```typescript
import { useSSEStream } from '@/shared/hooks/use-sse-stream';

function useResearchRunSSE({ runId, conversationId, enabled, onLog, ... }) {
  const parseEvent = useCallback((line: string) => {
    if (!line.startsWith('data: ')) return null;
    return JSON.parse(line.slice(6)) as SSEEvent;
  }, []);

  const handleEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case 'log': onLog(event.data as LogEntry); break;
      // ... other handlers
    }
  }, [onLog]);

  return useSSEStream({
    url: `/conversations/${conversationId}/idea/research-run/${runId}/stream`,
    enabled,
    parseEvent,
    onEvent: handleEvent,
    delimiter: '\n\n',
    reconnect: true,
  });
}
```

### useStreamingImport

```typescript
// frontend/src/shared/hooks/use-streaming-import.ts

import type { ImportState, SSEEvent } from '@/features/conversation-import/types/types';

export interface StreamingImportOptions {
  /** Called when import starts */
  onStart?: () => void;
  /** Called when import ends (success or error) */
  onEnd?: () => void;
  /** Called on successful completion with conversation ID */
  onSuccess?: (conversationId: number) => void;
  /** Called on error */
  onError?: (error: string) => void;
}

export interface StreamingImportState {
  /** Accumulated content organized by section */
  sections: Record<string, string>;
  /** Current import state/phase */
  currentState: ImportState | '';
  /** Summary progress percentage (0-100) */
  summaryProgress: number | null;
  /** Whether this is an update to existing conversation */
  isUpdateMode: boolean;
  /** Whether currently streaming */
  isStreaming: boolean;
}

export interface StreamingImportActions {
  /** Start the streaming import */
  startStream: (params: {
    url: string;
    model: string;
    provider: string;
    duplicateResolution: 'prompt' | 'update_existing' | 'create_new';
    targetConversationId?: number;
    acceptSummarization?: boolean;
  }) => Promise<void>;
  /** Reset all streaming state */
  reset: () => void;
}

export interface StreamingImportReturn {
  state: StreamingImportState;
  actions: StreamingImportActions;
  /** Ref for auto-scrolling textarea */
  streamingRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useStreamingImport(
  options?: StreamingImportOptions
): StreamingImportReturn;
```

**Usage Example (Conversation Import):**

```typescript
import { useStreamingImport } from '@/shared/hooks/use-streaming-import';

function useConversationImport(options) {
  const formState = useImportFormState();
  const conflictState = useImportConflictResolution();
  const modelState = useModelSelection();

  const streaming = useStreamingImport({
    onSuccess: options.onSuccess,
    onError: options.onError,
  });

  const startImport = async () => {
    if (!formState.validate()) return;

    await streaming.actions.startStream({
      url: formState.url,
      model: modelState.currentModel,
      provider: modelState.currentProvider,
      duplicateResolution: 'prompt',
    });
  };

  // ... compose return value from sub-hooks
}
```

### useImportFormState

```typescript
// frontend/src/features/conversation-import/hooks/use-import-form-state.ts

export interface ImportFormState {
  url: string;
  error: string;
}

export interface ImportFormActions {
  setUrl: (url: string) => void;
  setError: (error: string) => void;
  validate: () => boolean;
  reset: () => void;
}

export interface UseImportFormStateReturn {
  state: ImportFormState;
  actions: ImportFormActions;
}

export function useImportFormState(): UseImportFormStateReturn;
```

### useImportConflictResolution

```typescript
// frontend/src/features/conversation-import/hooks/use-import-conflict-resolution.ts

import type { ConflictItem } from '../types/types';

export interface ConflictState {
  hasConflict: boolean;
  items: ConflictItem[];
  selectedId: number | null;
}

export interface ModelLimitState {
  hasConflict: boolean;
  message: string;
  suggestion: string;
}

export interface ConflictActions {
  setConflict: (items: ConflictItem[]) => void;
  selectConflict: (id: number) => void;
  clearConflict: () => void;
  setModelLimit: (message: string, suggestion: string) => void;
  clearModelLimit: () => void;
  reset: () => void;
}

export interface UseImportConflictResolutionReturn {
  conflict: ConflictState;
  modelLimit: ModelLimitState;
  actions: ConflictActions;
}

export function useImportConflictResolution(): UseImportConflictResolutionReturn;
```

### useProjectDraftData

```typescript
// frontend/src/features/project-draft/hooks/use-project-draft-data.ts

import type { Idea, ConversationDetail } from '@/types';

export interface UseProjectDraftDataOptions {
  conversation: ConversationDetail;
}

export interface UseProjectDraftDataReturn {
  projectDraft: Idea | null;
  setProjectDraft: (draft: Idea) => void;
  isLoading: boolean;
  isUpdating: boolean;
  updateProjectDraft: (ideaData: {
    title: string;
    short_hypothesis: string;
    related_work: string;
    abstract: string;
    experiments: string[];
    expected_outcome: string;
    risk_factors_and_limitations: string[];
  }) => Promise<void>;
}

export function useProjectDraftData(
  options: UseProjectDraftDataOptions
): UseProjectDraftDataReturn;
```

### useProjectDraftEdit

```typescript
// frontend/src/features/project-draft/hooks/use-project-draft-edit.ts

import type { Idea } from '@/types';

export interface UseProjectDraftEditReturn {
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editTitle: string;
  setEditTitle: (title: string) => void;
  editDescription: string;
  setEditDescription: (description: string) => void;
  handleEdit: (projectDraft: Idea | null) => void;
  handleSave: () => { title: string; ideaData: object } | null;
  handleCancelEdit: () => void;
  handleKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
}

export function useProjectDraftEdit(): UseProjectDraftEditReturn;
```

### StringSection

```typescript
// frontend/src/features/project-draft/components/StringSection.tsx

import type { ReactElement } from 'react';

export type StringSectionVariant =
  | 'default'           // No border, text-foreground/90
  | 'primary-border'    // border-l-4 border-primary, text-foreground
  | 'success-box';      // Green background box

export interface StringSectionProps {
  /** Section title (displayed as uppercase label) */
  title: string;
  /** Section content (rendered as Markdown) */
  content: string;
  /** Diff content for comparison mode (overrides content) */
  diffContent?: ReactElement[] | null;
  /** Edit button click handler */
  onEdit?: () => void;
  /** Visual variant */
  variant?: StringSectionVariant;
  /** Additional CSS classes */
  className?: string;
}

export function StringSection(props: StringSectionProps): ReactElement;
```

**Usage Example:**

```typescript
import { StringSection } from './StringSection';

// Replaces HypothesisSection
<StringSection
  title="Hypothesis"
  content={hypothesis}
  variant="primary-border"
  onEdit={handleEditHypothesis}
/>

// Replaces AbstractSection
<StringSection
  title="Abstract"
  content={abstract}
  onEdit={handleEditAbstract}
/>

// Replaces ExpectedOutcomeSection
<StringSection
  title="Expected Outcome"
  content={expectedOutcome}
  variant="success-box"
  onEdit={handleEditOutcome}
/>
```

---

## Dependency Graph

```
                                    +-----------------+
                                    |  api-client.ts  |
                                    | (apiFetch,      |
                                    |  apiStream)     |
                                    +--------+--------+
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
           +--------v--------+      +--------v--------+      +--------v--------+
           | use-sse-stream  |      | useProjectDraft |      | useChatStreaming|
           |     (new)       |      |     Data (new)  |      |   (modified)    |
           +--------+--------+      +-----------------+      +-----------------+
                    |
           +--------v--------+
           | useStreaming    |
           |   Import (new)  |
           +--------+--------+
                    |
    +---------------+---------------+
    |                               |
+---v----+                   +------v------+
|useConv |                   |useManual    |
|Import  |                   |IdeaImport   |
|(facade)|                   |(simplified) |
+---+----+                   +-------------+
    |
    +---uses--->+--------------------+
                | useImportFormState |
                +--------------------+
    +---uses--->+------------------------+
                | useImportConflict      |
                | Resolution             |
                +------------------------+
    +---uses--->+--------------------+
                | useModelSelection  |
                | (existing, reused) |
                +--------------------+


  +-------------------+           +-------------------+
  | useProjectDraft   |--uses---->| useProjectDraft   |
  |     State         |           |     Data (new)    |
  |   (facade)        |           +-------------------+
  +-------------------+
           |
           +------uses-------->+-------------------+
                               | useProjectDraft   |
                               |     Edit (new)    |
                               +-------------------+


  +-------------------+
  |   StringSection   |<---replaces---+  HypothesisSection
  |      (new)        |               +  AbstractSection
  +-------------------+               +  RelatedWorkSection
           |                          +  ExpectedOutcomeSection
           v
  +-------------------+
  | markdownComponents|
  |    (existing)     |
  +-------------------+
```

---

## Implementation Order

### Phase 1: Shared Infrastructure (Highest Impact)

1. **Create `use-sse-stream.ts`** - Generic SSE streaming hook
   - This is the foundation for all streaming refactoring
   - Test with `useResearchRunSSE` first (simplest consumer)

2. **Modify `useResearchRunSSE.ts`** - First consumer of `useSSEStream`
   - Replace direct fetch with apiStream
   - Validates the generic hook works

3. **Create `use-streaming-import.ts`** - Base import streaming hook
   - Built on top of `useSSEStream`
   - Handles import-specific event types

### Phase 2: Hook Splitting (Medium Impact)

4. **Create `use-import-form-state.ts`** - Form state split
5. **Create `use-import-conflict-resolution.ts`** - Conflict state split
6. **Modify `useConversationImport.ts`** - Compose sub-hooks (facade)
   - Keep original API unchanged
   - Internal implementation uses new hooks

7. **Create `use-project-draft-data.ts`** - Data loading split
8. **Create `use-project-draft-edit.ts`** - Edit state split
9. **Modify `useProjectDraftState.ts`** - Compose sub-hooks (facade)

### Phase 3: Component Patterns (Lower Risk)

10. **Create `StringSection.tsx`** - Generic section component
11. **Modify `HypothesisSection.tsx`** - Use StringSection
12. **Modify `AbstractSection.tsx`** - Use StringSection
13. **Modify `RelatedWorkSection.tsx`** - Use StringSection
14. **Modify `ExpectedOutcomeSection.tsx`** - Use StringSection

### Phase 4: Direct Fetch Cleanup (Straightforward)

15. **Modify `useChatStreaming.ts`** - Replace direct fetch with apiStream
16. **Modify `ProjectDraft.tsx`** - Replace direct fetch with apiFetch
17. **Modify `useManualIdeaImport.ts`** - Use `useStreamingImport`

---

## Rationale

### Why Generic SSE Hook First?

1. **Highest code duplication** - 4 hooks with ~150 lines each of identical streaming logic
2. **Foundation for future features** - Any new streaming feature can reuse this
3. **Testable in isolation** - Can test with existing useResearchRunSSE before touching more complex hooks

### Why Facade Pattern for Hook Splitting?

1. **Zero breaking changes** - Existing consumers continue working
2. **Incremental adoption** - New components can use focused hooks
3. **Reversible** - If issues arise, can revert to original implementation
4. **Testing** - Can test sub-hooks independently

### Why StringSection Variants (Not Separate Components)?

1. **Single source of truth** - Styling changes only need one update
2. **Consistent behavior** - Edit button, markdown rendering all unified
3. **Type safety** - TypeScript ensures valid variant names
4. **Extensibility** - Easy to add new variants without new files

### Trade-offs Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| EventEmitter pattern for SSE | Familiar pattern | Adds complexity, less React-idiomatic | Rejected |
| Callback-based SSE | Simple, flexible, React-friendly | Requires careful memoization | **Accepted** |
| Context splitting for ConversationContext | Better ISP | Complex migration, risk of bugs | Deferred (lower priority) |
| Complete hook replacement | Cleaner code | Breaking changes, risky | Rejected in favor of facade |

---

## For Next Phase (Implementation)

### Guidance for the Executor

1. **File naming**: Use kebab-case (`use-sse-stream.ts`, not `useSSEStream.ts`)
2. **Testing approach**: Create unit tests for each new hook before integration
3. **Type exports**: Export interfaces alongside implementations
4. **Error handling**: Use existing `ApiError` pattern from api-client

### Critical Considerations

1. **useSSEStream must handle**:
   - AbortController cleanup on unmount
   - Reconnection timeout cleanup
   - Buffer management for partial lines

2. **Facade hooks must preserve**:
   - Exact return type shape
   - All callback signatures
   - Ref types

3. **StringSection must preserve**:
   - Exact visual appearance of each variant
   - Accessibility (aria-labels)
   - Edit button behavior

### Recommended Testing Strategy

```
Phase 1:
- [ ] Unit test useSSEStream with mock Response
- [ ] Integration test with useResearchRunSSE
- [ ] E2E test research run streaming still works

Phase 2:
- [ ] Unit test each split hook independently
- [ ] Integration test facades match original behavior
- [ ] E2E test import flow unchanged

Phase 3:
- [ ] Visual regression test for each section variant
- [ ] Accessibility audit for StringSection
```

---

## Approval Status

- [ ] Pending approval
- [x] Approved - proceed to Implementation
- [ ] Modified - see feedback below

### Feedback
{User feedback will be added here}
