# Task Context: Ideation Queue Enhancement

## Agent
feature-orchestrator (initial handoff)

## Timestamp
2025-12-05

## Original Request

Rename "Conversations" page to "Ideation Queue" (Flavio's original naming).

### User Requirements
Feature parity and fields matching Flavio's UI:
- Each idea row/card should show:
  - Hypothesis title (truncated but readable)
  - Short snippet/abstract OR first N characters of the hypothesis
  - Status badge (e.g. Pending launch, In research, Completed, Failed)
  - Created date and last updated date
- List supports basic sorting and/or filtering by status
- Layout is responsive and doesn't cut off all useful context like the current version

## Initial Analysis

### Current State
The "Conversations" page (`/conversations`) currently displays a simple table with:
- ID (truncated)
- Title
- User
- Imported date
- Updated date
- View action

It lacks:
- Hypothesis/abstract preview
- Status badges
- Sorting/filtering controls
- Responsive card layout

### Key Files Identified
- `/frontend/src/app/(dashboard)/conversations/page.tsx` - Main page
- `/frontend/src/features/conversation/components/ConversationsBoardHeader.tsx` - Header
- `/frontend/src/features/conversation/components/ConversationsBoardTable.tsx` - Table view
- `/frontend/src/features/conversation/hooks/useConversationsFilter.ts` - Search filter
- `/frontend/src/shared/lib/api-adapters.ts` - Conversation type definition

### Technical Constraints
- Next.js 15.4.8 with App Router
- Feature-based architecture in `frontend/src/features/`
- Uses Tailwind CSS v4 (requires explicit class names, not dynamic)
- shadcn/ui component library
- React Query for server state

### Status Integration Challenge
The current `Conversation` type does not include research run status. Options:
1. **Option A**: Derive status from existing fields (ideaTitle presence, etc.) - Limited
2. **Option B**: Backend enhancement to include latest research status per conversation - Ideal
3. **Option C**: Join with research runs data on frontend - Possible but less efficient

For initial implementation, we can use a simplified status derivation:
- "Pending launch" = Has idea but no research run associated
- "In research" = Active research run
- "Completed" = Research run completed
- "Failed" = Research run failed
- "No idea yet" = No ideaTitle/ideaAbstract

## Questions for Planner

1. Should we rename the route from `/conversations` to `/ideation-queue`?
2. Should sidebar navigation be updated accordingly?
3. How should we handle the status badge when no research runs exist? (Derive from idea fields?)
4. Should we add status filtering to the API or filter client-side?

## Handoff to Planner
The feature-planner should:
1. Create comprehensive PRD with implementation phases
2. Decide on status derivation strategy
3. Plan the component architecture changes
4. Identify reusable components from research feature
