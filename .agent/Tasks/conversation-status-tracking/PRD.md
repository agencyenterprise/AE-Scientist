# Conversation Status Tracking - Product Requirements Document

## Overview

Add the ability to track conversation status via a dedicated database column (Draft | With Research), with automatic status updates when research runs are created, and provide Edit buttons in the Ideation Queue views to navigate directly to the conversation detail page.

## Status

See `task.json` for current implementation status.

**REVISED**: This plan was updated per user request to use a **stored ENUM column** instead of computed status.

## User Story

**As a** User
**I want to** track the status of my conversations with a dedicated status column
**So I can** better handle conversation status and continue from where I left.

## Acceptance Criteria

| ID | Criterion | Status |
|----|-----------|--------|
| AC1 | Create a status column for conversations: Draft \| With Research (when we have launched research) | Pending |
| AC2 | Auto-update status to 'with_research' when a research run is created | Pending |
| AC3 | Have an "Edit" button in the IdeationQueueCard so I can go to the /conversation/[id] page | Pending |
| AC4 | Have an "Edit" button in the InlineIdeaView so I can go to the /conversation/[id] page | Pending |

---

## Technical Decisions

### Architectural Approach: Stored ENUM Column (REVISED)

**Decision:** Status is stored as a dedicated column in the conversations table.

**Justification:**
- User explicitly requested a stored column for better status handling
- Enables direct SQL queries for filtering conversations by status
- Explicit state management - status is always clear
- Flexibility for future status values (easy to extend CHECK constraint)
- Pattern consistent with existing status columns (e.g., `research_pipeline_runs.status`)

**Alternatives Considered:**

| Approach | Pros | Cons | Why Rejected |
|----------|------|------|--------------|
| **Stored ENUM Column** | Explicit, query-friendly, flexible | Requires migration, app-level sync | **SELECTED** (user request) |
| Computed Status | Simple, no migration, always accurate | Cannot query directly, computed at runtime | User wanted stored column |
| Hybrid Cached Status | Best of both worlds | Complex implementation | Over-engineered |

### Status Values

| Status | Condition | Display |
|--------|-----------|---------|
| `draft` | Default state, no research launched | Initial state for all conversations |
| `with_research` | Has at least one research run | Updated when run is created |

### Column Implementation

- **Column Type:** `TEXT` with `CHECK` constraint (not PostgreSQL ENUM)
- **Default Value:** `'draft'`
- **Allowed Values:** `('draft', 'with_research')`
- **Rationale:** TEXT + CHECK is more flexible than ENUM for future additions

### Status Transition Logic

**Trigger Point:** `create_research_pipeline_run()` method in `ResearchPipelineRunsMixin`

**Logic:**
1. When creating a research run, lookup the conversation_id via idea_id
2. Update conversation status to `'with_research'` in the same transaction
3. This ensures atomicity - if run creation fails, status is not updated

### Edit Button Design

**Placement:**
- **IdeationQueueCard**: Footer row, next to existing "Show/Hide Runs" toggle
- **InlineIdeaView**: Header area, after the research runs badge

**Interaction:**
- Uses `router.push(/conversations/${id})` for navigation
- `e.stopPropagation()` prevents card click event bubbling
- Consistent styling with existing buttons in the codebase

**Icon:** Lucide `Pencil` icon (standard edit action icon)

---

## Implementation Plan

### Phase 1: Database Migration (AC1)

**File:** `server/database_migrations/versions/0013_add_conversation_status.py`

**Migration Tasks:**
1. Add `status` column to `conversations` table
2. Set default value to `'draft'`
3. Add CHECK constraint for allowed values
4. Backfill existing conversations:
   - If conversation has research runs -> `'with_research'`
   - Otherwise -> `'draft'`
5. Update `conversation_dashboard_view` to include status column

**Migration Pattern (following 0003_manual_seed_columns.py):**

```python
def upgrade() -> None:
    # Add status column with default
    op.add_column(
        "conversations",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="draft"
        )
    )

    # Add CHECK constraint
    op.execute("""
        ALTER TABLE conversations
        ADD CONSTRAINT conversations_status_check
        CHECK (status IN ('draft', 'with_research'))
    """)

    # Backfill existing conversations that have research runs
    op.execute("""
        UPDATE conversations c
        SET status = 'with_research'
        WHERE EXISTS (
            SELECT 1 FROM ideas i
            JOIN research_pipeline_runs r ON r.idea_id = i.id
            WHERE i.conversation_id = c.id
        )
    """)

    # Update dashboard view to include status
    op.execute("""
        CREATE OR REPLACE VIEW conversation_dashboard_view AS
        SELECT
            c.id,
            c.url,
            c.title,
            c.import_date,
            c.created_at,
            c.updated_at,
            c.status,
            c.imported_by_user_id AS user_id,
            u.name AS user_name,
            u.email AS user_email,
            iv.title AS idea_title,
            iv.abstract AS idea_abstract,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'user'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_user_message_content,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'assistant'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_assistant_message_content,
            c.manual_title,
            c.manual_hypothesis
        FROM conversations c
        LEFT JOIN users u ON c.imported_by_user_id = u.id
        LEFT JOIN ideas i ON i.conversation_id = c.id
        LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
    """)
```

### Phase 2: Backend Model Updates (AC1)

**File:** `server/app/models/conversations.py`

**Changes:**
1. Add `status` field to `ConversationResponse` model:

```python
class ConversationResponse(BaseModel):
    # ... existing fields ...
    status: str = Field(
        default="draft",
        description="Conversation status: 'draft' or 'with_research'"
    )
```

**File:** `server/app/services/database/conversations.py`

**Changes:**
1. Add `status` field to `FullConversation` NamedTuple
2. Add `status` field to `DashboardConversation` NamedTuple
3. Update `get_conversation_by_id()` to select status column
4. Update `list_conversations()` to select status column
5. Add `update_conversation_status()` method:

```python
def update_conversation_status(self, conversation_id: int, status: str) -> bool:
    """Update a conversation's status. Returns True if updated."""
    if status not in ('draft', 'with_research'):
        raise ValueError(f"Invalid status: {status}")
    now = datetime.now()
    with self._get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE conversations SET status = %s, updated_at = %s WHERE id = %s",
                (status, now, conversation_id),
            )
            conn.commit()
            return bool(cursor.rowcount > 0)
```

### Phase 3: API Updates (AC1)

**File:** `server/app/api/conversations.py`

**Changes:**
1. Update `convert_db_to_api_response()` to include status field:

```python
def convert_db_to_api_response(
    db_conversation: DBFullConversation,
    research_runs: Optional[List[ResearchRunSummary]] = None,
) -> ConversationResponse:
    return ConversationResponse(
        # ... existing fields ...
        status=db_conversation.status,
        research_runs=research_runs or [],
    )
```

### Phase 4: Auto-Update Logic (AC2)

**File:** `server/app/services/database/research_pipeline_runs.py`

**Changes:**
1. Modify `create_research_pipeline_run()` to update conversation status:

```python
def create_research_pipeline_run(
    self,
    *,
    run_id: str,
    idea_id: int,
    idea_version_id: int,
    status: str,
    start_deadline_at: Optional[datetime],
    cost: float,
) -> int:
    # ... existing validation ...
    now = datetime.now(timezone.utc)
    deadline = start_deadline_at
    with self._get_connection() as conn:
        with conn.cursor() as cursor:
            # Insert the run
            cursor.execute(
                """
                INSERT INTO research_pipeline_runs (...)
                VALUES (...)
                RETURNING id
                """,
                (...)
            )
            new_id_row = cursor.fetchone()
            # ... existing event insertion ...

            # Update conversation status to 'with_research'
            cursor.execute(
                """
                UPDATE conversations c
                SET status = 'with_research', updated_at = %s
                FROM ideas i
                WHERE i.id = %s AND i.conversation_id = c.id
                """,
                (now, idea_id)
            )

            conn.commit()
            return int(new_id)
```

### Phase 5: Edit Button in IdeationQueueCard (AC3)

**File:** `frontend/src/features/conversation/components/IdeationQueueCard.tsx`

**Changes:**
1. Import `Pencil` icon from lucide-react
2. Add `handleEditClick` function with `stopPropagation`
3. Add Edit button in footer next to expand toggle

```tsx
import { Clock, ChevronDown, ChevronUp, Pencil } from "lucide-react";

// Add handler
const handleEditClick = (e: React.MouseEvent) => {
  e.stopPropagation();
  router.push(`/conversations/${id}`);
};

// In footer div, before the expand toggle button:
<button
  onClick={handleEditClick}
  type="button"
  aria-label="Edit conversation"
  className={cn(
    "inline-flex items-center gap-1 rounded px-2 py-1",
    "text-[10px] uppercase tracking-wide text-slate-400",
    "transition-colors hover:bg-slate-800 hover:text-slate-300"
  )}
>
  <Pencil className="h-3 w-3" />
  Edit
</button>
```

### Phase 6: Edit Button in InlineIdeaView (AC4)

**File:** `frontend/src/features/conversation/components/InlineIdeaView.tsx`

**Changes:**
1. Import `useRouter` from next/navigation
2. Import `Pencil` icon from lucide-react
3. Add Edit button in header metadata row

```tsx
import { useRouter } from "next/navigation";
import { Eye, FlaskConical, Pencil } from "lucide-react";

// Inside component:
const router = useRouter();

// In the flex row after badges:
<button
  onClick={() => router.push(`/conversations/${conversationId}`)}
  className="inline-flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
>
  <Pencil className="h-3.5 w-3.5" />
  Edit
</button>
```

---

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `server/database_migrations/versions/0013_add_conversation_status.py` | Create | Migration to add status column |
| `server/app/models/conversations.py` | Modify | Add status field to ConversationResponse |
| `server/app/api/conversations.py` | Modify | Include status in API response |
| `server/app/services/database/conversations.py` | Modify | Add status to NamedTuples, add update_conversation_status() |
| `server/app/services/database/research_pipeline_runs.py` | Modify | Auto-update conversation status on run creation |
| `frontend/src/features/conversation/components/IdeationQueueCard.tsx` | Modify | Add Edit button with navigation |
| `frontend/src/features/conversation/components/InlineIdeaView.tsx` | Modify | Add Edit button with navigation |

---

## Reusability Analysis

### Existing Assets to REUSE

| Asset | Location | Purpose |
|-------|----------|---------|
| Migration pattern | `0003_manual_seed_columns.py` | Pattern for adding column + refreshing view |
| `cn()` utility | `@/shared/lib/utils` | Conditional CSS classes |
| `Pencil` icon | `lucide-react` | Edit button icon |
| `useRouter` | `next/navigation` | Client-side navigation |
| Button patterns | Existing components | Consistent styling |

### Similar Features to Reference

| Feature | File | What to Learn |
|---------|------|---------------|
| Expand/Collapse button | `IdeationQueueCard.tsx` | Button styling, stopPropagation pattern |
| Research runs badge | `InlineIdeaView.tsx` | Badge styling in header |
| Status column pattern | `research_pipeline_runs.py` | TEXT + CHECK constraint pattern |

---

## Testing Strategy

### Manual Testing

1. **Migration:**
   - Run migration on test database
   - Verify existing conversations get correct status
   - Verify new conversations default to 'draft'

2. **Auto-Update:**
   - Create a new conversation (status = 'draft')
   - Launch research run
   - Verify status changed to 'with_research'

3. **API Response:**
   - GET /conversations/{id} returns status field
   - GET /conversations returns status in list items

4. **IdeationQueueCard Edit Button:**
   - Click Edit button - should navigate to /conversations/{id}
   - Click card area - should NOT navigate (existing behavior preserved)
   - Verify stopPropagation works correctly

5. **InlineIdeaView Edit Button:**
   - Click Edit button - should navigate to /conversations/{id}
   - Verify button is visible and properly styled

### Edge Cases

- Conversation with failed research run (should still show "with_research")
- Multiple research runs for same conversation
- Concurrent run creation (transaction safety)
- Migration on empty database
- Migration with conversations that have no ideas

---

## Dependencies

- **Alembic**: For database migration
- **PostgreSQL**: TEXT column with CHECK constraint
- **lucide-react**: Pencil icon (already in project)
- **next/navigation**: useRouter (already in project)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration fails on production | Low | High | Test migration on staging first, include rollback |
| Status becomes stale | Low | Medium | Application-level update in same transaction |
| Edit button interferes with card click | Low | Medium | stopPropagation pattern already proven |
| Performance impact from status update | Very Low | Low | Simple UPDATE in same transaction |

---

## Related Documentation

- `.agent/System/server_architecture.md` - Database patterns
- `.agent/System/frontend_architecture.md` - Component patterns
- `.agent/SOP/server_database_migrations.md` - Migration procedures
- `server/database_migrations/versions/0003_manual_seed_columns.py` - Reference migration
