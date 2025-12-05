# Bug Fix: White Background Flash on Page Loads

## Bug ID
ad-hoc

## Date
2025-12-04

## Description
A white/light gray background was appearing during all page loads, breaking the dark theme consistency. This occurred whenever the ProtectedRoute component was checking authentication state.

## Root Cause
The `ProtectedRoute` component used hardcoded Tailwind gray classes (`bg-gray-50`, `text-gray-600`, `border-blue-600`) instead of theme-aware CSS variables. These classes don't respect the dark mode theme defined in `globals.css`.

## Fix Applied
Replaced hardcoded color classes with theme-aware Tailwind utilities that use CSS variables from the dark theme:

### Files Modified
- `frontend/src/shared/components/ProtectedRoute.tsx:33-38`: Updated loading state styling
  - `bg-gray-50` → `bg-background` (uses dark mode `#0f172a` slate-950)
  - `text-gray-600` → `text-muted-foreground` (uses dark mode `#94a3b8` slate-400)
  - `border-blue-600` → `border-primary` (uses dark mode `#38bdf8` sky-400)

## Verification
1. Navigate to any protected route (e.g., `/research`, `/research/[runId]`)
2. Observe the loading state during authentication check
3. Verify that the background matches the dark theme (`#0f172a`)
4. Verify that the spinner uses the primary accent color (`#38bdf8`)
5. Verify that the "Loading..." text uses muted foreground color

## Prevention
When creating loading states or fallback UI:
- Always use theme-aware Tailwind utilities (e.g., `bg-background`, `text-foreground`)
- Avoid hardcoded color classes (e.g., `bg-gray-50`, `text-blue-600`)
- Test components in both light and dark modes if theme switching is supported
- Reference `frontend/src/app/globals.css` for the current theme variables
