# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-03 14:30

## Input Received
- Context: `.agent/Tasks/frontend-solid-refactoring/00-context.md`
- Project docs consulted:
    - `.agent/README.md` - Documentation index
    - `.agent/System/frontend_architecture.md` - Feature-based architecture, conventions
    - `.agent/System/project_architecture.md` (referenced)

## Files Analyzed

### Hooks (Primary Focus - SRP Violations)

| File | Lines | Issues Found |
|------|-------|--------------|
| `features/conversation-import/hooks/useConversationImport.ts` | 525 | Multiple concerns: form state, model state, streaming state, conflict resolution, model limits |
| `features/project-draft/hooks/useProjectDraftState.ts` | 257 | Multiple concerns: data loading, polling, edit state, modals, scroll behavior |
| `features/project-draft/hooks/useChatStreaming.ts` | 299 | Large hook with SSE streaming, duplicates pattern from other hooks |
| `features/input-pipeline/hooks/useManualIdeaImport.ts` | 210 | Duplicates streaming import pattern from useConversationImport |
| `features/research/hooks/useResearchRunSSE.ts` | 265 | SSE streaming with reconnection logic, similar to other streaming hooks |
| `features/project-draft/hooks/useSectionEdit.ts` | 344 | Well-structured but large; acceptable given complexity |
| `features/model-selector/hooks/useModelSelectorData.ts` | 129 | Good example - clean React Query usage |
| `features/project-draft/hooks/useChatFileUpload.ts` | 97 | Good example - single responsibility |

### Components Analyzed

| File | Lines | Issues Found |
|------|-------|--------------|
| `features/input-pipeline/components/CreateHypothesisForm.tsx` | 280 | Too many concerns: form state, model state, import hooks orchestration |
| `features/project-draft/components/ProjectDraft.tsx` | 265 | Uses direct fetch() instead of api-client; orchestrates multiple hooks |
| `features/project-draft/components/ProjectDraftContent.tsx` | 195 | Good - orchestrates section components cleanly |
| `features/project-draft/components/HypothesisSection.tsx` | 39 | Nearly identical to other section components |
| `features/project-draft/components/AbstractSection.tsx` | 39 | Nearly identical to other section components |
| `features/project-draft/components/ExperimentsSection.tsx` | 122 | Array section - different enough to warrant separate component |
| `features/conversation-import/components/ImportModal.tsx` | 135 | Clean orchestration of import flow |

### Contexts Analyzed

| File | Lines | Issues Found |
|------|-------|--------------|
| `features/conversation/context/ConversationContext.tsx` | 118 | Large interface (18 properties), could be split |
| `shared/contexts/AuthContext.tsx` | 163 | Acceptable - auth is inherently cross-cutting |

### Shared Libraries

| File | Lines | Quality |
|------|-------|---------|
| `shared/lib/api-client.ts` | 154 | Excellent - centralized API abstraction |
| `shared/lib/config.ts` | - | Centralized configuration |
| `shared/lib/api-adapters.ts` | - | Anti-corruption layer for API responses |

---

## Reasoning

### Why This Approach

The analysis focused on **patterns over individual issues**. Instead of cataloging every small problem, I identified **recurring patterns** that cause multiple violations:

1. **SSE Streaming Duplication** - Four hooks implement nearly identical streaming logic. This is the highest-impact refactoring because it affects multiple features and would eliminate ~300 lines of duplicated code.

2. **Large Hooks** - The two largest hooks (`useConversationImport` at 525 lines and `useProjectDraftState` at 257 lines) both violate SRP by mixing multiple concerns. Splitting them creates smaller, more testable units.

3. **Section Components** - The string section components are a clear DRY violation. A generic component would reduce maintenance burden.

4. **Context Size** - While the ConversationContext works, it exposes too much to consumers who only need part of it.

### Pattern Selection

| Pattern | Chosen From | Rationale |
|---------|-------------|-----------|
| Hook composition | `useModelSelectorData` | Clean separation of data fetching and state |
| Facade hooks | Existing project pattern | Maintain backward compatibility while splitting internals |
| Shared hooks in `shared/hooks/` | Project convention | Per `frontend_architecture.md` section 2 |
| Generic components | shadcn/ui pattern | Configurable via props, not branches |

### Dependencies Identified

| Dependency | Why Needed |
|------------|------------|
| `shared/lib/api-client.ts` | Already exists; standardize usage across all hooks |
| `features/project-draft/hooks/useModelSelection.ts` | Already exists; should be reused instead of duplicating |
| React Context | Existing pattern for feature-level state |
| React Query | Existing pattern for server state |

### Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Use facade pattern - keep original interfaces, refactor internals |
| Performance regression from context splitting | Use context selectors or careful memoization |
| Incomplete refactoring | Prioritize by impact; complete high-priority items before moving on |
| Merge conflicts | Refactor during low-activity periods; communicate changes |

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Start with SSE infrastructure | Yes | Highest impact, unlocks subsequent refactoring |
| Split hooks using facade pattern | Yes | Maintains backward compatibility |
| Create generic StringSection | Yes | Clear DRY win with minimal risk |
| Split ConversationContext | Lower priority | Works fine currently, splitting is optimization |
| Move diffUtils to shared | Defer | No clear reuse case yet |
| Replace all direct fetch | Yes | Consistency and error handling |

---

## Specific Violations Found

### Single Responsibility Principle (SRP)

#### useConversationImport.ts
- **Lines 111-143**: State declarations for 5+ distinct concerns
  - Form state: `url`, `error`
  - Model state: `selectedModel`, `selectedProvider`, `currentModel`, `currentProvider`
  - Streaming state: `isStreaming`, `sections`, `currentState`, `summaryProgress`, `isUpdateMode`
  - Conflict state: `hasConflict`, `conflicts`, `selectedConflictId`
  - Model limit state: `hasModelLimitConflict`, `modelLimitMessage`, `modelLimitSuggestion`

#### useProjectDraftState.ts
- **Lines 50-58**: Mix of data state and UI state
- **Lines 171-187**: Data fetching
- **Lines 189-218**: Polling logic
- **Lines 221-230**: Scroll behavior (UI concern)

#### CreateHypothesisForm.tsx
- **Lines 22-31**: Manages both manual form state AND model selection state
- **Lines 60-82**: Duplicates model selection logic that exists in hooks
- **Lines 100-120**: Form submission handles two different import paths

### Open/Closed Principle (OCP)

#### SSE Streaming Logic
Each streaming hook has its own implementation:
- `useConversationImport.ts` lines 198-345: Buffer management, line parsing, event handling
- `useManualIdeaImport.ts` lines 69-190: Same pattern, different events
- `useChatStreaming.ts` lines 118-209: Same pattern
- `useResearchRunSSE.ts` lines 114-231: Same pattern with reconnection

Adding a new streaming feature requires copying this pattern instead of extending a base.

#### Section Components
- `HypothesisSection.tsx`, `AbstractSection.tsx`, `RelatedWorkSection.tsx`, `ExpectedOutcomeSection.tsx`
- All nearly identical with different titles and minor styling
- Adding a new section type requires creating a new component

### Interface Segregation Principle (ISP)

#### ConversationContext (lines 16-40)
```typescript
export interface ConversationContextValue {
  // Model selection (6 properties)
  selectedModel, selectedProvider, currentModel, currentProvider, modelCapabilities,
  handleModelChange, handleModelDefaults, handleModelCapabilities,

  // UI state (6 properties)
  effectiveCapabilities, setEffectiveCapabilities,
  isStreaming, setIsStreaming,
  isReadOnly, setIsReadOnly,

  // Prompt modal (2 properties)
  onOpenPromptModal, setOnOpenPromptModal,
}
```
Components that only need model selection must accept the entire interface.

### Dependency Inversion Principle (DIP)

#### Direct fetch() in ProjectDraft.tsx (lines 85-108)
```typescript
const response = await fetch(
  `${config.apiUrl}/conversations/${conversation.id}/idea/versions/${versionState.comparisonVersion.version_id}/activate`,
  { method: "POST", credentials: "include" }
);
```
Should use `apiFetch` from `shared/lib/api-client.ts` for consistent error handling.

#### Direct fetch() in useChatStreaming.ts (lines 120-137)
Similar issue - uses direct fetch instead of `apiStream`.

---

## Output Summary

- PRD created: `.agent/Tasks/frontend-solid-refactoring/PRD.md`
- Files to create: 6-8 new hooks, 1-2 new components
- Estimated complexity: **Moderate to Complex**
  - High: SSE infrastructure (new pattern, multiple consumers)
  - Medium: Hook splitting (facade pattern, backward compatible)
  - Low: Section component generalization (simple abstraction)

---

## For Next Phase (Architecture)

Key considerations for the architect:

1. **SSE Hook API Design**: The generic `useSSEStream` hook needs a flexible API that works for:
   - Import streaming (content events, state events, conflict events)
   - Chat streaming (content, status, idea_updated events)
   - Research run SSE (initial, stage_progress, log, artifact, run_update events)

2. **Hook Composition Strategy**: Decide between:
   - Composition: `useConversationImport` internally uses `useImportFormState()`, `useImportStreamingState()`, etc.
   - Facade: `useConversationImport` exposes same API but delegates to smaller hooks

3. **Context Splitting Approach**: Consider:
   - Multiple contexts (ModelContext, UIContext)
   - Context selectors (use-context-selector library)
   - Keep single context with better memoization

4. **Type Definitions**: Many hooks use inline types. Consider moving shared types to feature-level type files.

5. **Testing Strategy**: With hooks split, unit testing individual concerns becomes easier. Architecture should support this.

---

## Approval Status

- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
