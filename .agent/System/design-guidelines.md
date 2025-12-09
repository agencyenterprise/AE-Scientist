# Design Guidelines

This document defines the visual design system for AE-Scientist, including typography, color tokens, motion patterns, backgrounds, and component patterns.

**Related Documentation:**
- [Project Architecture](project_architecture.md) - Overall system architecture
- [Frontend Architecture](frontend_architecture.md) - Frontend structure and patterns
- [Frontend Features SOP](../SOP/frontend_features.md) - Component organization

---

## Typography

### Font Family
```css
body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI',
               Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizelegibility;
}
```

### Font Sizes & Weights
Use Tailwind's default typography scale:
- **Headings**: `text-2xl`, `text-xl`, `text-lg` with `font-semibold` or `font-bold`
- **Body**: `text-sm` or `text-base` with `font-normal` or `font-medium`
- **Small/Meta**: `text-xs` with `font-normal` or `font-medium`

### Best Practices
- Use semantic HTML (`<h1>`, `<p>`, etc.) with Tailwind classes
- Maintain consistent hierarchy: larger sizes = higher importance
- Prefer `font-semibold` for UI elements, `font-bold` for emphasis
- Use `text-foreground` for primary text, `text-muted-foreground` for secondary

---

## Color & Theme

### Color System Overview
AE-Scientist uses CSS variables defined in `globals.css` for theme support. All colors use OKLCH color space for consistent perceptual lightness.

### Light Mode Colors

#### Brand Colors (Teal)
```css
--primary-50:  #f0fdfa;
--primary-100: #ccfbf1;
--primary-300: #5eead4;
--primary-500: #14b8a6;
--primary-600: #0d9488;
--primary-700: #0f766e;
--primary: oklch(20.5% 0 0deg);
--primary-hover: var(--primary-700);
--primary-foreground: oklch(98.5% 0 0deg);
```

#### Semantic Colors
```css
--success: #10b981;           /* Green */
--success-foreground: #fff;
--warning: #f59e0b;           /* Amber */
--warning-foreground: #1f2937;
--danger: #ef4444;            /* Red */
--danger-foreground: #fff;
--destructive: oklch(57.7% 0.245 27.325deg);
```

#### Neutrals
```css
--background: oklch(100% 0 0deg);     /* White */
--foreground: oklch(14.5% 0 0deg);    /* Near black */
--surface: #fff;
--muted: oklch(97% 0 0deg);           /* Light gray */
--muted-foreground: oklch(55.6% 0 0deg);
--border: oklch(92.2% 0 0deg);
--card: oklch(100% 0 0deg);
--card-foreground: oklch(14.5% 0 0deg);
```

#### UI Elements
```css
--input: oklch(92.2% 0 0deg);
--ring: oklch(70.8% 0 0deg);           /* Focus ring */
--radius: 0.625rem;                     /* 10px */
```

### Dark Mode Colors (Slate/Sky Theme)

Dark mode uses `.dark` class (not system preference).

#### Background/Foreground
```css
--background: #0f172a;  /* slate-950 */
--foreground: #f1f5f9;  /* slate-100 */
--surface: #0f172a;     /* slate-950 */
```

#### Cards & Surfaces
```css
--card: #1e293b;              /* slate-800 */
--card-foreground: #f1f5f9;   /* slate-100 */
--popover: #1e293b;           /* slate-800 */
--popover-foreground: #f1f5f9;
```

#### Primary (Sky Blue Accent)
```css
--primary: #38bdf8;             /* sky-400 */
--primary-foreground: #0f172a;  /* slate-950 */
--accent: #0ea5e9;              /* sky-500 */
--accent-foreground: #f8fafc;   /* slate-50 */
```

#### Borders & Inputs
```css
--border: #334155;  /* slate-700 */
--input: #334155;   /* slate-700 */
--ring: #38bdf8;    /* sky-400 focus ring */
```

#### Charts (Sky Palette)
```css
--chart-1: #38bdf8;  /* sky-400 */
--chart-2: #0ea5e9;  /* sky-500 */
--chart-3: #0284c7;  /* sky-600 */
--chart-4: #7dd3fc;  /* sky-300 */
--chart-5: #bae6fd;  /* sky-200 */
```

### Status Colors (Orchestrator)
Defined in `orchestrator/tailwind.config.ts`:
```typescript
status: {
  queued: "#1E3A8A",    /* Blue-900 */
  running: "#2563EB",   /* Blue-600 */
  auto: "#7C3AED",      /* Purple-600 */
  awaiting: "#F59E0B",  /* Amber-500 */
  success: "#10B981",   /* Green-500 */
  failed: "#DC2626",    /* Red-600 */
  canceled: "#6B7280"   /* Gray-500 */
}
```

### Usage Guidelines
- **Always use CSS variables** (`bg-primary`, `text-foreground`) instead of hardcoded colors
- Use `text-muted-foreground` for secondary text
- Use semantic colors (`success`, `warning`, `danger`) for status indicators
- Prefer `border-border` for consistent border colors
- Use `ring-ring` for focus states

---

## Motion & Animation

### Transitions
Use Tailwind's `transition` utilities:
```css
.btn-primary-gradient {
  @apply transition;  /* Default: 150ms ease */
}

.nav-link {
  @apply transition hover:text-foreground;
}
```

### Custom Animations
```css
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

### Best Practices
- Use `transition` for hover states
- Keep animations subtle (150-300ms)
- Use `hover:opacity-90` for button hover states
- Animate opacity, transform, and colors only (avoid layout shifts)

---

## Backgrounds

### Solid Backgrounds
```css
@apply bg-background;     /* Page background */
@apply bg-card;           /* Card/container background */
@apply bg-muted;          /* Subtle background */
```

### Gradient Backgrounds

#### Primary Gradient Button (Orchestrator Style)
```css
.btn-primary-gradient {
  background: linear-gradient(to right, #0ea5e9, #3b82f6, #22d3ee);
  box-shadow: 0 18px 40px -18px rgb(56 189 248 / 65%);
}

.btn-primary-gradient:hover {
  background: linear-gradient(to right, #38bdf8, #60a5fa, #67e8f9);
}
```

#### Scrollbar Gradient (Dark Mode)
```css
background: linear-gradient(180deg,
  rgb(56 189 248 / 60%),
  rgb(29 78 216 / 60%)
);
```

### Glass/Blur Effects
```css
.toolbar-glass {
  @apply border-b border-border bg-card/70 backdrop-blur;
  @apply supports-[backdrop-filter]:bg-card/60;
}
```

### Best Practices
- Use gradients sparingly (primary CTA buttons only)
- Prefer solid backgrounds for readability
- Use `backdrop-blur` with opacity for glass effects
- Maintain 60-70% opacity for glass surfaces

---

## Component Patterns

### Buttons

#### Primary Gradient Button
```tsx
<button className="btn-primary-gradient">
  Submit
</button>
```

Classes: `.btn-primary-gradient`
- Gradient background (sky-blue shades)
- Rounded-full
- Shadow on hover
- White text

#### Secondary Button
```tsx
<button className="btn-secondary">
  Cancel
</button>
```

Classes: `.btn-secondary`
- Card background with border
- Hover: muted background
- Medium font weight

#### Danger Button
```tsx
<button className="btn-danger">
  Delete
</button>
```

Classes: `.btn-danger`
- Red destructive background
- White text
- Opacity hover effect

#### Filter Buttons
```tsx
<button className="btn-filter btn-filter-inactive">
  Inactive
</button>
<button className="btn-filter btn-filter-active">
  Active
</button>
```

### Inputs

#### Standard Input Field
```tsx
<input className="input-field" placeholder="Enter text..." />
```

Classes: `.input-field`
- Rounded-xl borders
- Card background
- Primary ring on focus
- Placeholder: muted-foreground

### Cards & Containers

#### Card Container
```tsx
<div className="card-container">
  {/* Content */}
</div>
```

Classes: `.card-container`
- Rounded-2xl
- Border with card background
- Padding: p-5

### Navigation

#### Toolbar/Header
```tsx
<header className="toolbar-glass">
  {/* Nav items */}
</header>
```

Classes: `.toolbar-glass`
- Glass effect with backdrop blur
- Border bottom

#### Nav Links
```tsx
<a className="nav-link">Home</a>
```

Classes: `.nav-link`
- Muted foreground
- Hover: foreground

### View Tabs

```tsx
<div className="view-tabs">
  <button className="view-tab view-tab-inactive">List</button>
  <button className="view-tab view-tab-active">Grid</button>
</div>
```

Classes:
- `.view-tabs` - Container with muted background
- `.view-tab` - Base tab styles
- `.view-tab-active` - Primary color with border
- `.view-tab-inactive` - Muted with hover effect

### Scrollbars (Dark Mode)

Custom scrollbar with sky-blue gradient:
```tsx
<div className="custom-scrollbar overflow-auto">
  {/* Content */}
</div>
```

Classes: `.custom-scrollbar`
- Thin scrollbar (6px)
- Sky-blue gradient thumb
- Slate track background

---

## Accessibility

### Focus States
- Always use `ring-ring` for focus indicators
- Maintain visible focus rings (don't remove outline)
- Use `focus:ring-2` and `focus:ring-offset-2`

### Color Contrast
- Foreground/background meet WCAG AA standards
- Muted text uses 55.6% lightness (accessible)
- Button text uses high contrast colors

### Dark Mode
- Dark mode requires explicit `.dark` class
- Not activated by system preference
- All colors meet contrast requirements in both modes

### Text Selection
```css
::selection {
  background: var(--ring);
  color: var(--primary-foreground);
}
```

### Best Practices
- Test keyboard navigation on all interactive elements
- Ensure sufficient color contrast (use muted-foreground, not arbitrary grays)
- Provide hover and focus states for all clickable elements
- Use semantic HTML (`<button>`, `<nav>`, etc.)
- Test with screen readers when possible

---

## Quick Reference

### Common Patterns
```tsx
// Card with content
<div className="card-container">
  <h2 className="text-xl font-semibold mb-4">Title</h2>
  <p className="text-sm text-muted-foreground">Description</p>
</div>

// Primary action button
<button className="btn-primary-gradient">
  Create Experiment
</button>

// Form input
<input
  type="text"
  className="input-field"
  placeholder="Experiment name..."
/>

// Status badge
<span className="px-2 py-1 text-xs rounded-full bg-status-success text-white">
  Success
</span>
```

### Color Variables to Use
- `bg-background` / `text-foreground` - Main page colors
- `bg-card` / `text-card-foreground` - Card/container colors
- `bg-muted` / `text-muted-foreground` - Subtle/secondary content
- `bg-primary` / `text-primary-foreground` - Brand accent
- `border-border` - All borders
- `ring-ring` - Focus rings

### Border Radius
- `rounded-md` - Small elements (4px)
- `rounded-lg` - Medium elements (8px)
- `rounded-xl` - Large elements (12px)
- `rounded-2xl` - Cards (16px)
- `rounded-full` - Pills/circles

---

## Notes

- This project uses Tailwind CSS v4 with the new `@import "tailwindcss"` syntax
- All design tokens are defined in `frontend/src/app/globals.css`
- Orchestrator has additional status colors in `orchestrator/tailwind.config.ts`
- Use the `tw-animate-css` plugin for animations
- Dark mode is class-based (`.dark`), not media-query based
