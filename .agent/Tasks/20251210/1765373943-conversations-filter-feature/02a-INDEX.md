# Next.js 15 Guidance Index: Conversations Filter Feature

## Quick Navigation

### For Different Learning Styles

**Visual Learner?** → Start with `02a-ARCHITECTURE-DIAGRAM.md`
- Component hierarchy
- Data flow diagrams
- Sequence diagrams
- File dependency tree

**Code-First Learner?** → Start with `02a-nextjs-15-quick-reference.md`
- 8 complete, ready-to-copy code files
- Implementation checklist
- File structure
- Common issues with solutions

**Conceptual Learner?** → Start with `02a-nextjs-15-guidance.md`
- Why each decision was made
- Best practices
- Do's and Don'ts
- Documentation links

**Question-Driven?** → Start with `02a-nextjs-15-qa.md`
- Your 4 specific questions answered
- Detailed explanations
- Comparison tables
- Approach recommendations

---

## Document Overview

### 1. 02a-IMPLEMENTATION-SUMMARY.md
**Read Time**: 5 minutes | **Audience**: Everyone (start here!)

**What**: High-level overview of all guidance documents

**Contains**:
- Version validation ✓
- Document descriptions
- Your 4 questions answered (summary)
- Architecture decision matrix
- Implementation steps in order
- File checklist
- Key patterns used
- Best practices applied
- Common issues & resolutions
- Approval status

**Best For**: Getting oriented, understanding the big picture

---

### 2. 02a-ARCHITECTURE-DIAGRAM.md
**Read Time**: 10 minutes | **Audience**: Architects, visual learners

**What**: Visual diagrams of the system architecture

**Contains**:
- Component hierarchy and data flow
- Data flow diagram
- State management architecture
- Context flow diagram
- File structure with dependencies
- React 19 + Next.js 15 component boundaries
- API integration flow
- State updates sequence diagram
- Performance optimization points
- Comparison: right vs wrong approach
- Testing flow
- Next.js version differences
- Summary architecture

**Best For**: Understanding how everything connects

---

### 3. 02a-nextjs-15-guidance.md
**Read Time**: 30 minutes | **Audience**: Everyone (comprehensive reference)

**What**: Complete technical guidance with explanations

**Contains**:
- Project analysis
- Version-specific guidance (15.4.8 with React 19)
- Architecture overview
- Section 1: Filter state management in layout
  - The pattern (with code)
  - Why it works
  - Next.js 15 App Router behavior
- Section 2: Context typing with callbacks
  - Complete type definition pattern
  - Why each part matters
  - React 19 improvements
- Section 3: React 19 event handlers
  - Type inference improvements
  - Callback dependencies
  - Patterns for simple toggles
  - When to use useCallback
- Section 4: URL query params
  - Approach 1: Read-only (simplest)
  - Approach 2: Read on mount (recommended)
  - Approach 3: Sync with URL (complex)
  - Approach 4: Server Component params (advanced)
  - Recommendation for your project
- Data fetching patterns
- Do's and Don'ts
- File structure recommendation
- Integration patterns
- Key reminders

**Best For**: Deep understanding, reference during coding

---

### 4. 02a-nextjs-15-quick-reference.md
**Read Time**: 5-15 minutes | **Audience**: Developers implementing

**What**: Copy-paste ready code snippets

**Contains**:
- Section 1: DashboardContext definition
- Section 2: Conversations layout with state
- Section 3: Filter toggle button component
- Section 4: Updated IdeationQueueHeader
- Section 5: Conversations page (Server Component)
- Section 6: ConversationsList component
- Section 7: API hook with TanStack Query
- Section 8: API function
- Implementation checklist
- Common issues & solutions
- React 19 + Next.js 15 key reminders
- Files to create/update
- Next.js 15 specific features used

**Best For**: Actually implementing the code

---

### 5. 02a-nextjs-15-qa.md
**Read Time**: 20 minutes | **Audience**: Specific questions

**What**: Detailed answers to your 4 questions

**Contains**:
- Q1: Filter state management in layout
  - Why the pattern works
  - Next.js 15 layout behavior
  - Comparison with Pages Router
- Q2: Context typing with callbacks
  - Complete interface pattern
  - Why each part matters
  - Type safety in React 19
  - Usage examples
  - TypeScript improvements
- Q3: React 19 event handlers
  - Type inference changes
  - Callback dependency strictness
  - When to use useCallback
  - Complete patterns
  - Event handler best practices
  - What not to do in React 19
  - What to do in React 19
- Q4: URL query params
  - Approach 1: No URL sync
  - Approach 2: Read from URL (recommended)
  - Approach 3: Sync with URL
  - Approach 4: Server Component
  - Which approach to choose
  - Summary table

**Best For**: Understanding "why" behind decisions

---

## Implementation Workflow

### Step 1: Understand the Architecture
**Time**: 10 minutes
**Files**: `02a-IMPLEMENTATION-SUMMARY.md` + `02a-ARCHITECTURE-DIAGRAM.md`

Read the overview and look at the diagrams to understand how everything fits together.

### Step 2: Reference the Code
**Time**: 5 minutes
**File**: `02a-nextjs-15-quick-reference.md`

Copy the exact code snippets you need for each file.

### Step 3: Understand the Decisions
**Time**: 15 minutes
**File**: `02a-nextjs-15-qa.md`

Read the Q&A to understand why each decision was made.

### Step 4: Deep Dive (If Needed)
**Time**: 30 minutes
**File**: `02a-nextjs-15-guidance.md`

Reference specific sections for deeper understanding.

---

## Finding What You Need

### "I want to see the code"
→ `02a-nextjs-15-quick-reference.md` - Sections 1-8

### "How do I implement the layout state?"
→ `02a-nextjs-15-qa.md` - Q1
→ `02a-nextjs-15-quick-reference.md` - Section 2

### "How should I type the context?"
→ `02a-nextjs-15-qa.md` - Q2
→ `02a-nextjs-15-quick-reference.md` - Section 1

### "What about React 19 event handlers?"
→ `02a-nextjs-15-qa.md` - Q3
→ `02a-nextjs-15-guidance.md` - Section 3

### "Should I use URL query params?"
→ `02a-nextjs-15-qa.md` - Q4
→ `02a-nextjs-15-guidance.md` - Section 4

### "Why does the state persist on navigation?"
→ `02a-ARCHITECTURE-DIAGRAM.md` - State Persistence section
→ `02a-nextjs-15-qa.md` - Q1

### "Show me the component hierarchy"
→ `02a-ARCHITECTURE-DIAGRAM.md` - Component Hierarchy
→ `02a-ARCHITECTURE-DIAGRAM.md` - File Structure

### "What API calls should I make?"
→ `02a-nextjs-15-quick-reference.md` - Section 8
→ `02a-ARCHITECTURE-DIAGRAM.md` - API Integration Flow

### "I'm getting errors, what's wrong?"
→ `02a-nextjs-15-quick-reference.md` - Common Issues & Solutions
→ `02a-nextjs-15-guidance.md` - Do's and Don'ts

### "How do I test this?"
→ `02a-ARCHITECTURE-DIAGRAM.md` - Testing Flow section

---

## Document Map

```
Your Questions
└── "How to implement conversations filter"
    │
    ├─ Understanding Phase (10 min)
    │  ├── 02a-IMPLEMENTATION-SUMMARY.md (read first!)
    │  └── 02a-ARCHITECTURE-DIAGRAM.md (visual overview)
    │
    ├─ Implementation Phase (15 min)
    │  ├── 02a-nextjs-15-quick-reference.md (copy code from here)
    │  ├── Checklist in same file
    │  └── Common issues section
    │
    ├─ Understanding Phase (15 min)
    │  └── 02a-nextjs-15-qa.md (why decisions)
    │
    └─ Reference Phase (as needed)
       └── 02a-nextjs-15-guidance.md (deep dive)
```

---

## Version Information

| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.8 | App Router (default) |
| react | 19.1.2 | Latest React |
| typescript | ^5 | Strict type checking |
| @tanstack/react-query | ^5.90.10 | For data fetching |
| zustand | ^5.0.8 | For state (if needed) |

**All guidance is specific to Next.js 15.4.8 with React 19.1.2**

---

## Key Takeaways

### 1. Architecture Decision
**Use layout with `'use client'` to manage filter state**
- Ensures state persists on navigation (App Router feature)
- Provides state to all child pages via context
- Clean separation of concerns

### 2. Type Safety
**Create explicit TypeScript interfaces**
- ConversationFilters for filter shape
- DashboardContextType for context shape
- Custom hook for safe access

### 3. React 19
**Key changes**
- Type inference is better
- Dependency checking is stricter
- Inline arrow functions work well
- useCallback when passing handlers as props

### 4. URL Query Params
**Use Approach 2: Read on mount**
- Simple implementation
- Bookmarkable URLs
- State-driven updates
- Easy to extend later

### 5. Performance
**Use memoization strategically**
- useMemo for context value
- useCallback for callbacks
- TanStack Query for data fetching
- App Router preserves layout state for free

---

## FAQ

**Q: Which document should I read first?**
A: `02a-IMPLEMENTATION-SUMMARY.md` - It's the quickest overview

**Q: Where's the code?**
A: `02a-nextjs-15-quick-reference.md` - Sections 1-8 with copy-paste snippets

**Q: Why is there a layout with state?**
A: `02a-nextjs-15-qa.md` - Q1 explains App Router behavior

**Q: What about TypeScript types?**
A: `02a-nextjs-15-quick-reference.md` - Section 1 or `02a-nextjs-15-qa.md` - Q2

**Q: Are there diagrams?**
A: `02a-ARCHITECTURE-DIAGRAM.md` - Multiple diagrams and flows

**Q: What if I get errors?**
A: `02a-nextjs-15-quick-reference.md` - Common issues section

**Q: Should I use URL query params?**
A: `02a-nextjs-15-qa.md` - Q4 has recommendations

**Q: What about performance?**
A: `02a-ARCHITECTURE-DIAGRAM.md` - Performance optimization section

**Q: Is this different from Next.js 14?**
A: `02a-ARCHITECTURE-DIAGRAM.md` - Version comparison section

---

## Next Steps

1. **Read**: `02a-IMPLEMENTATION-SUMMARY.md` (5 min)
2. **Visualize**: `02a-ARCHITECTURE-DIAGRAM.md` (10 min)
3. **Implement**: `02a-nextjs-15-quick-reference.md` (15 min)
4. **Understand**: `02a-nextjs-15-qa.md` (optional, 20 min)
5. **Reference**: `02a-nextjs-15-guidance.md` (as needed)

---

## Document Creation Info

**Agent**: nextjs-15-expert
**Date**: 2025-12-10
**Project**: AE-Scientist Conversations Filter Feature
**Feature ID**: 1765373943-conversations-filter-feature
**Status**: Ready for Implementation

All documents created and cross-referenced for easy navigation.
