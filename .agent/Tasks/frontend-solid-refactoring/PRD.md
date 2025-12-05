# Frontend SOLID Refactoring - Product Requirements Document

## Overview

This document outlines the refactoring opportunities identified in the frontend codebase that violate SOLID principles. The goal is to improve maintainability, reduce code duplication, and enhance the overall architecture while following established project conventions.

## Status

- [x] Planning
- [x] Architecture
- [x] Implementation
- [x] Testing (build verification passed)
- [x] Documentation Review
- [ ] Complete (pending final approval)

## Summary of Findings

After analyzing the frontend codebase, **14 refactoring items** were identified across **4 priority levels**. The most significant issues relate to:

1. **Single Responsibility Principle (SRP)** - Large hooks mixing multiple concerns
2. **Open/Closed Principle (OCP)** - Duplicate SSE streaming logic across features
3. **Interface Segregation Principle (ISP)** - Large context interfaces
4. **Dependency Inversion Principle (DIP)** - Direct API calls in components (partially addressed by existing `api-client.ts`)

---

## Requirements

### Functional Requirements

Each refactoring must:
- Maintain existing functionality without regressions
- Follow the project's feature-based architecture conventions
- Use existing patterns (kebab-case, hooks pattern, shadcn/ui)
- Not introduce new external dependencies
- Be testable in isolation

### Non-Functional Requirements

- **Maintainability**: Reduce cognitive load when working on features
- **Reusability**: Extract common patterns for cross-feature use
- **Consistency**: Apply same patterns across similar code
- **Performance**: No performance regressions

---

## Refactoring Items

### Priority 1: High Impact (Extract Shared Infrastructure)

#### Item 1.1: Extract SSE Streaming Infrastructure
**Violation**: OCP, SRP
**Location**: Multiple hooks with duplicated SSE streaming logic
**Files Affected**:
- `frontend/src/features/conversation-import/hooks/useConversationImport.ts` (lines 198-345)
- `frontend/src/features/input-pipeline/hooks/useManualIdeaImport.ts` (lines 69-190)
- `frontend/src/features/project-draft/hooks/useChatStreaming.ts` (lines 118-209)
- `frontend/src/features/research/hooks/useResearchRunSSE.ts` (lines 114-231)

**Issue**: Each hook implements its own SSE streaming logic with buffer management, line parsing, and event type handling. This violates OCP because adding a new streaming feature requires writing the same boilerplate.

**Proposed Solution**:
Create `frontend/src/shared/hooks/useSSEStream.ts` - a generic SSE streaming hook that accepts event handlers and manages connection lifecycle. Each feature hook would compose this base hook.

**Success Criteria**:
- [ ] Common SSE logic extracted to shared hook
- [ ] Feature hooks use composition to add business logic
- [ ] Reconnection logic centralized
- [ ] Auto-scroll behavior configurable

---

#### Item 1.2: Create Generic Streaming Import Hook
**Violation**: OCP, SRP
**Location**: Two nearly identical import hooks
**Files Affected**:
- `frontend/src/features/conversation-import/hooks/useConversationImport.ts` (525 lines)
- `frontend/src/features/input-pipeline/hooks/useManualIdeaImport.ts` (210 lines)

**Issue**: Both hooks manage streaming import state (error, streamingContent, currentState, isStreaming) with identical patterns. `useManualIdeaImport` is a simpler version of `useConversationImport`.

**Proposed Solution**:
Create a base streaming import hook that handles common streaming state and lifecycle. Feature-specific hooks extend it with their own event handlers and API endpoints.

**Success Criteria**:
- [ ] Shared streaming import base hook
- [ ] Feature hooks only define unique behavior
- [ ] Reduced code duplication by ~150 lines

---

### Priority 2: Medium-High Impact (Large Hook Refactoring)

#### Item 2.1: Split useProjectDraftState Hook
**Violation**: SRP
**Location**: `frontend/src/features/project-draft/hooks/useProjectDraftState.ts` (257 lines)
**Lines**: Full file

**Issue**: This hook manages multiple concerns:
1. Loading/polling project draft data (lines 171-218)
2. Edit mode state management (lines 88-108)
3. Modal state (isCreateModalOpen, lines 146-152)
4. Project creation logic (lines 154-168)
5. Scroll behavior (lines 221-230)

**Proposed Solution**:
Split into focused hooks:
- `useProjectDraftData` - Data fetching and polling
- `useProjectDraftEdit` - Edit mode state
- `useProjectDraftActions` - Save, create project actions
- Keep `useProjectDraftState` as a facade that composes these hooks

**Success Criteria**:
- [ ] Each hook has single responsibility
- [ ] Hooks can be used independently
- [ ] Original API preserved via facade

---

#### Item 2.2: Split useConversationImport Hook
**Violation**: SRP
**Location**: `frontend/src/features/conversation-import/hooks/useConversationImport.ts` (525 lines)
**Lines**: Full file

**Issue**: This hook manages too many concerns:
1. Form state (url, error) - lines 111-113
2. Model selection state - lines 115-118
3. Streaming state - lines 121-125
4. Conflict resolution state - lines 135-137
5. Model limit conflict state - lines 140-143
6. Auto-scroll effect - lines 148-152

**Proposed Solution**:
Split into focused hooks:
- `useImportFormState` - Form state management
- `useImportModelState` - Model selection state
- `useImportStreamingState` - Streaming state (uses shared SSE hook from Item 1.1)
- `useImportConflictResolution` - Conflict handling
- `useConversationImport` - Facade that composes all hooks

**Success Criteria**:
- [ ] Each sub-hook is <100 lines
- [ ] State is properly encapsulated
- [ ] Conflict resolution logic is isolated

---

### Priority 3: Medium Impact (Component Patterns)

#### Item 3.1: Create Generic Section Component
**Violation**: OCP, DRY
**Location**: `frontend/src/features/project-draft/components/`
**Files Affected**:
- `HypothesisSection.tsx` (39 lines)
- `AbstractSection.tsx` (39 lines)
- `RelatedWorkSection.tsx` (similar)
- `ExpectedOutcomeSection.tsx` (similar)

**Issue**: These four components are nearly identical, differing only in:
1. Section title
2. Border styling (hypothesis has `border-l-4 border-primary`)
3. Text color (`text-foreground` vs `text-foreground/90`)

**Proposed Solution**:
Create a generic `StringSection` component that accepts configuration props. Feature-specific components become thin wrappers or are replaced entirely.

```typescript
interface StringSectionProps {
  title: string;
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
  variant?: 'default' | 'primary-border';
}
```

**Success Criteria**:
- [ ] Single configurable StringSection component
- [ ] Existing section components use StringSection
- [ ] No visual regression

---

#### Item 3.2: Extract Modal Base Component
**Violation**: SRP, OCP
**Location**: Multiple modal implementations
**Files Affected**:
- `frontend/src/features/conversation-import/components/ImportModal.tsx`
- `frontend/src/features/project-draft/components/SectionEditModal.tsx`
- `frontend/src/features/project-draft/components/ArraySectionEditModal.tsx`
- `frontend/src/features/project-draft/components/CreateProjectModal.tsx`
- `frontend/src/features/conversation/components/DeleteConfirmModal.tsx`

**Issue**: Each modal implements its own backdrop, escape key handling, and base styling. While each has unique content, the modal shell is duplicated.

**Proposed Solution**:
- The project already uses shadcn/ui. Ensure all modals use the `Dialog` component from shadcn/ui consistently
- Create a `BaseModal` wrapper component if Dialog doesn't meet all needs

**Success Criteria**:
- [ ] All modals use consistent base component
- [ ] Escape key handling centralized
- [ ] Backdrop styling unified

---

#### Item 3.3: Refactor CreateHypothesisForm Component
**Violation**: SRP
**Location**: `frontend/src/features/input-pipeline/components/CreateHypothesisForm.tsx` (280 lines)

**Issue**: This component manages:
1. Manual form state (title, idea) - lines 22-24
2. Model selection state (duplicated from hooks) - lines 27-30
3. Two different import hooks - lines 33-53
4. Form submission logic - lines 100-120
5. Multiple UI states (importing, conflict, model limit) - lines 153-226

**Proposed Solution**:
Split into smaller components:
- `CreateHypothesisFormFields` - Form inputs
- `CreateHypothesisActions` - Submit button + model selector
- `CreateHypothesisContainer` - State orchestration
- Use existing import hooks more directly without duplicating model state

**Success Criteria**:
- [ ] Main component <100 lines
- [ ] Clear separation of UI and state
- [ ] No duplicated model state

---

### Priority 4: Lower Impact (Context Improvements)

#### Item 4.1: Split ConversationContext Interface
**Violation**: ISP
**Location**: `frontend/src/features/conversation/context/ConversationContext.tsx` (118 lines)

**Issue**: The `ConversationContextValue` interface (lines 16-40) exposes 18 properties to all consumers. Components that only need model selection must accept the entire context interface.

**Proposed Solution**:
Create separate contexts or use context selectors:
- `ModelSelectionContext` - Model state and actions
- `ConversationUIContext` - UI state (isStreaming, isReadOnly, capabilities)
- Or use a selector pattern with `use-context-selector` library

**Success Criteria**:
- [ ] Contexts are properly segmented
- [ ] Components only subscribe to needed state
- [ ] No unnecessary re-renders

---

#### Item 4.2: Create Model Selection Hook Factory
**Violation**: DIP, DRY
**Location**: Model selection logic duplicated in multiple places
**Files Affected**:
- `frontend/src/features/conversation/context/ConversationContext.tsx` (lines 56-67)
- `frontend/src/features/input-pipeline/components/CreateHypothesisForm.tsx` (lines 27-30, 60-82)
- `frontend/src/features/conversation-import/hooks/useConversationImport.ts` (lines 173-195)

**Issue**: Model selection state (selectedModel, selectedProvider, currentModel, currentProvider) is managed in multiple places with identical logic.

**Proposed Solution**:
The project already has `useModelSelection` hook at `frontend/src/features/project-draft/hooks/useModelSelection.ts`. Ensure this hook is used consistently across all features instead of duplicating the logic.

**Success Criteria**:
- [ ] Single source of truth for model selection logic
- [ ] All features use the same hook
- [ ] No duplicated model state management

---

### Priority 5: Code Quality Improvements

#### Item 5.1: Standardize Direct fetch() Calls
**Violation**: DIP
**Location**: Multiple components using direct fetch instead of api-client
**Files Affected**:
- `frontend/src/features/project-draft/components/ProjectDraft.tsx` (lines 85-108)
- `frontend/src/features/project-draft/hooks/useChatStreaming.ts` (lines 120-137)

**Issue**: Some components use direct `fetch()` calls instead of the centralized `apiFetch` or `apiStream` functions from `shared/lib/api-client.ts`.

**Proposed Solution**:
Replace direct fetch calls with api-client functions. This ensures consistent error handling, credential inclusion, and 401 redirect behavior.

**Success Criteria**:
- [ ] All API calls use api-client functions
- [ ] No direct fetch() calls to API endpoints
- [ ] Consistent error handling

---

#### Item 5.2: Extract Diff Utils to Shared Module
**Violation**: Potential for reuse
**Location**: `frontend/src/features/project-draft/utils/diffUtils.tsx`

**Issue**: Diff visualization utilities are only in project-draft feature but could be useful elsewhere (e.g., comparing conversation versions, research results).

**Proposed Solution**:
Move to `frontend/src/shared/lib/diffUtils.ts` if there's clear reuse potential. Otherwise, leave in place but document for future reference.

**Success Criteria**:
- [ ] Assess reuse potential
- [ ] Move if beneficial, document if not

---

## Technical Decisions

Based on project documentation:
- **Pattern**: Feature-based architecture with hooks for state management
- **SOPs**: Follow `frontend_features.md` and `frontend_api_hooks.md`
- **Dependencies**: Use existing shared utilities, React Context, React Query

## Reusability Analysis

### Existing Assets to REUSE
- [x] `shared/lib/api-client.ts` - Centralized fetch wrapper
- [x] `features/project-draft/hooks/useModelSelection.ts` - Model selection hook
- [x] `shared/components/ui/` - shadcn/ui components

### Similar Features to Reference
- `useModelSelectorData`: Well-structured React Query hook pattern
- `useChatFileUpload`: Good example of focused, single-responsibility hook

### Needs Codebase Analysis
- [x] No - Analysis complete

---

## Implementation Plan

### Phase 1: Shared Infrastructure (Items 1.1, 1.2)
- [ ] Create useSSEStream shared hook
- [ ] Create streaming import base hook
- [ ] Update existing hooks to use new infrastructure
- [ ] Test streaming functionality

### Phase 2: Hook Refactoring (Items 2.1, 2.2)
- [ ] Split useProjectDraftState
- [ ] Split useConversationImport
- [ ] Ensure backward compatibility
- [ ] Update consumers

### Phase 3: Component Patterns (Items 3.1, 3.2, 3.3)
- [ ] Create StringSection generic component
- [ ] Standardize modal components
- [ ] Refactor CreateHypothesisForm
- [ ] Visual regression testing

### Phase 4: Context and Quality (Items 4.1, 4.2, 5.1, 5.2)
- [ ] Split ConversationContext
- [ ] Standardize model selection usage
- [ ] Replace direct fetch calls
- [ ] Review diff utils location

---

## File Structure (Proposed New Files)

```
frontend/src/shared/
  hooks/
    use-sse-stream.ts            # NEW: Generic SSE streaming
    use-streaming-import.ts      # NEW: Base streaming import

frontend/src/features/project-draft/
  components/
    StringSection.tsx            # NEW: Generic string section
  hooks/
    use-project-draft-data.ts    # NEW: Split from useProjectDraftState
    use-project-draft-edit.ts    # NEW: Split from useProjectDraftState

frontend/src/features/conversation-import/
  hooks/
    use-import-form-state.ts        # NEW: Split from useConversationImport
    use-import-conflict-resolution.ts # NEW: Split from useConversationImport
```

---

## Related Documentation
- `.agent/System/frontend_architecture.md`
- `.agent/SOP/frontend_features.md`
- `.agent/SOP/frontend_api_hooks.md`
- `.agent/Tasks/frontend-solid-refactoring/02-architecture.md` - Detailed architecture

---

## Progress Log

### 2025-12-03
- Created initial PRD
- Analyzed frontend codebase
- Identified 14 refactoring items across 5 priority levels
- Completed architecture phase with detailed API designs

### 2025-12-03 (Implementation)
- Created shared SSE infrastructure:
  - `shared/hooks/use-sse-stream.ts` - Generic SSE streaming hook
  - `shared/hooks/use-streaming-import.ts` - Base import streaming hook
- Split useConversationImport (525 -> ~350 lines):
  - `use-import-form-state.ts` - URL input and validation
  - `use-import-conflict-resolution.ts` - Conflict handling
  - Maintained backward compatible facade API
- Split useProjectDraftState (257 -> ~170 lines):
  - `use-project-draft-data.ts` - Data loading and polling
  - `use-project-draft-edit.ts` - Edit mode state
  - Maintained backward compatible facade API
- Created StringSection component:
  - Variants: default, primary-border, success-box
  - Updated HypothesisSection, AbstractSection, RelatedWorkSection, ExpectedOutcomeSection
- Replaced direct fetch() with apiFetch in ProjectDraft.tsx
- Build verification: PASS

### 2025-12-03 (Documentation Review)
- Created review breadcrumb: `.agent/Tasks/frontend-solid-refactoring/04-review.md`
- Updated documentation with new patterns:
  - `.agent/System/frontend_architecture.md` - Added Shared Hooks section
  - `.agent/SOP/frontend_features.md` - Added Hook Splitting Pattern and Generic Component Pattern
  - `.agent/SOP/frontend_api_hooks.md` - Updated Streaming Hook Pattern with useSSEStream
- Identified remaining technical debt for future consideration
