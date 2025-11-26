## Theme Palette

This document defines the current color tokens used across the frontend. Colors are exposed as CSS variables in `src/app/globals.css` and referenced in components via Tailwind arbitrary values, e.g. `bg-[var(--primary)]`, `text-[var(--primary-700)]`, `ring-[var(--ring)]`.

### Brand
- primary: vibrant violet for actions and highlights
  - --primary-50:  #f5f3ff
  - --primary-100: #ede9fe
  - --primary-300: #c4b5fd
  - --primary-500: #8b5cf6
  - --primary-600: #7c3aed
  - --primary-700: #6d28d9
  - --primary:     #7c3aed (alias of 600)
  - --primary-hover: #6d28d9
  - --ring:        #8b5cf6 (focus outlines)

### Semantic
- success
  - --success:       #10b981
  - --success-foreground: #ffffff
- warning
  - --warning:       #f59e0b
  - --warning-foreground: #1f2937
- danger
  - --danger:        #ef4444
  - --danger-foreground: #ffffff

### Neutrals / Surfaces
- --background:         page background
- --foreground:         primary text
- --surface:            card surface
- --muted:              subtle backgrounds
- --muted-foreground:   secondary text
- --border:             borders and dividers

Light mode
- --background: #ffffff
- --foreground: #111827
- --surface:    #ffffff
- --muted:      #f8fafc
- --muted-foreground: #475569
- --border:     #e5e7eb

Dark mode
- --background: #0a0a0a
- --foreground: #e5e7eb
- --surface:    #0f1115
- --muted:      #0f172a
- --muted-foreground: #a1a1aa
- --border:     #27272a

### Usage examples
- Primary button: `bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white`
- Outline button: `border border-[var(--border)] hover:bg-[var(--muted)]`
- Focus ring: `focus:ring-2 focus:ring-[var(--ring)]`
- Emphasis text: `text-[var(--primary-700)]`


