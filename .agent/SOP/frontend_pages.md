# SOP: Frontend Pages (Next.js App Router)

## Related Documentation
- [Frontend Architecture](../System/frontend_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating new pages using Next.js App Router in the frontend. Use this procedure when you need to:
- Add new routes/pages
- Create layouts for route groups
- Implement dynamic routes
- Add protected pages

---

## Prerequisites

- Node.js environment set up
- Understanding of the page's purpose and data requirements
- Knowledge of whether the page needs authentication

---

## Step-by-Step Procedure

### 1. Determine Route Structure

Decide where your page fits in the routing structure:

```
frontend/src/app/
├── layout.tsx              # Root layout (AuthProvider)
├── login/
│   └── page.tsx           # /login (public)
├── (dashboard)/            # Grouped routes (authenticated)
│   ├── layout.tsx         # Dashboard layout (sidebar, context)
│   ├── page.tsx           # / (dashboard home)
│   ├── conversations/
│   │   └── [id]/
│   │       └── page.tsx   # /conversations/:id
│   └── my-feature/
│       └── page.tsx       # /my-feature (NEW)
```

### 2. Create the Page File

For a simple page at `/my-feature`:

```typescript
// frontend/src/app/(dashboard)/my-feature/page.tsx
"use client"

import { useEffect, useState } from "react"
import { useDashboard } from "../DashboardContext"
import { MyFeatureComponent } from "@/components/MyFeature"

export default function MyFeaturePage() {
  const { user } = useDashboard()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch("/api/my-feature", {
          credentials: "include"
        })
        const result = await response.json()
        setData(result)
      } catch (error) {
        console.error("Failed to fetch data:", error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return <div className="flex justify-center p-8">Loading...</div>
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">My Feature</h1>
      <MyFeatureComponent data={data} />
    </div>
  )
}
```

### 3. For Dynamic Routes

Create a folder with bracket notation:

```typescript
// frontend/src/app/(dashboard)/my-feature/[id]/page.tsx
"use client"

import { useParams } from "next/navigation"

export default function MyFeatureDetailPage() {
  const params = useParams()
  const id = params.id as string

  return (
    <div className="container mx-auto p-4">
      <h1>Feature Detail: {id}</h1>
      {/* Component implementation */}
    </div>
  )
}
```

### 4. Create a Layout (Optional)

If your feature needs a specific layout:

```typescript
// frontend/src/app/(dashboard)/my-feature/layout.tsx
"use client"

import { ReactNode } from "react"

interface LayoutProps {
  children: ReactNode
}

export default function MyFeatureLayout({ children }: LayoutProps) {
  return (
    <div className="flex">
      <aside className="w-64 border-r">
        {/* Sidebar navigation */}
      </aside>
      <main className="flex-1">
        {children}
      </main>
    </div>
  )
}
```

### 5. Add Route Protection

For authenticated routes, ensure you're inside `(dashboard)` group which uses `ProtectedRoute`:

```typescript
// frontend/src/app/(dashboard)/layout.tsx (already exists)
import { ProtectedRoute } from "@/shared/components/ProtectedRoute"
import { Header } from "@/shared/components/Header"

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="flex flex-col h-screen">
        <Header />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </ProtectedRoute>
  )
}
```

### 6. Add Navigation Link (if needed)

Update the sidebar or navigation component:

```typescript
// In your navigation component
<Link href="/my-feature" className="nav-link">
  My Feature
</Link>
```

---

## Route Group Patterns

### Public Routes (outside dashboard)

```
src/app/
├── login/page.tsx       # /login
├── signup/page.tsx      # /signup
└── public/page.tsx      # /public
```

### Protected Routes (inside dashboard group)

```
src/app/(dashboard)/
├── page.tsx                    # / (dashboard home with CreateHypothesisForm)
├── conversations/
│   ├── page.tsx               # /conversations (list view)
│   └── [id]/
│       └── page.tsx           # /conversations/:id (detail view)
```

### Nested Dynamic Routes

```
src/app/(dashboard)/
└── projects/
    ├── page.tsx           # /projects
    └── [projectId]/
        ├── page.tsx       # /projects/:projectId
        └── tasks/
            └── [taskId]/
                └── page.tsx  # /projects/:projectId/tasks/:taskId
```

---

## Key Files

| File | Purpose |
|------|---------|
| `src/app/layout.tsx` | Root layout with AuthProvider & QueryProvider |
| `src/app/(dashboard)/layout.tsx` | Dashboard layout with Header |
| `src/shared/contexts/AuthContext.tsx` | Authentication state |
| `src/shared/components/ProtectedRoute.tsx` | Route protection component |

---

## Common Patterns

### Using Dashboard Context

```typescript
"use client"

import { useDashboard } from "../DashboardContext"

export default function MyPage() {
  const {
    conversations,
    selectedConversation,
    setSelectedConversation,
    refreshConversations
  } = useDashboard()

  // Use context values
}
```

### Using Auth Context

```typescript
"use client"

import { useAuth } from "@/shared/hooks/useAuth"

export default function MyPage() {
  const { user, isAuthenticated, logout } = useAuth()

  if (!isAuthenticated) {
    return <div>Please log in</div>
  }

  return <div>Welcome, {user?.name}</div>
}
```

### Loading States

```typescript
"use client"

import { Suspense } from "react"

export default function MyPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <MyFeatureContent />
    </Suspense>
  )
}

function LoadingSpinner() {
  return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin h-8 w-8 border-4 border-blue-500 rounded-full border-t-transparent" />
    </div>
  )
}
```

---

## Common Pitfalls

- **Always add `"use client"`**: Required for components using hooks, state, or effects
- **Don't forget the parentheses**: Route groups use `(groupName)` syntax
- **Check authentication**: Put protected pages inside `(dashboard)` group
- **Use correct file names**: `page.tsx` for pages, `layout.tsx` for layouts
- **Handle loading states**: Show loading UI while fetching data
- **Never run `npm run dev`**: As per project rules, do not start the dev server manually

---

## Verification

1. Check the route exists by navigating to it in the browser

2. Verify the page renders correctly

3. Check authentication works:
   - Logout and try accessing the page
   - Should redirect to login

4. Verify context access:
   - Console log context values to ensure they're available

5. Test dynamic routes:
   - Navigate to `/my-feature/123`
   - Verify the ID is correctly extracted
