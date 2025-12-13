---
name: adr-design-strategy
description: UX strategy guidance using AE design principles
allowed-tools: Read, Write, Grep, Glob
---

# Design Strategy Skill

Guide UX decisions with AE's 5 design principles and design system tokens.

## When to Use

- Frontend feature implementation
- UI/UX planning decisions
- Dashboard/interface design
- AI/agentic system interfaces
- Any user-facing work

---

## The 5 Design Principles

### 1. Ship to Learn, Then Iterate

**The job is not to make perfect things. It's to make things real.**

- Share work early (even rough AI-generated concepts)
- Use AI tools daily to generate variations
- Deploy working prototypes people can actually use
- Frame shares as hypotheses: "Here's V1, testing if [assumption]. What breaks?"

**When to apply:**
- Client wants perfection before launch
- Timeline is tight or unclear
- Need to validate assumptions

---

### 2. Design Systems That Increase Agency

**Every interface should make users more capable, not just more informed.**

- Design AI outputs that show reasoning, not just results
- Give users control points: knobs, sliders, overrides
- Ensure interfaces work for diverse audiences

**For AI/agentic systems:**
- Show confidence levels
- Explain reasoning
- Surface data sources
- Let users override/adjust/reject

**When to apply:**
- AI feature feels like a black box
- Building any AI-powered interface
- Users need control over automated decisions

---

### 3. Spend Craft Where It Compounds

**AI gets you to 7/10. Taste decides where to push to 9.**

- Ask: "If this is the only thing someone sees, does it need to be great?"
- If yes → apply craft. If no → ship it.
- Motion should guide, not decorate

**High craft moments:**
- First impressions / hero sections
- Core interactions (the main thing users do)
- Trust moments (error states, AI reasoning)
- Explaining complexity

**When to apply:**
- Unsure where to spend craft vs ship fast
- Resource constraints require prioritization

---

### 4. Steelman User Needs, Then Commit

**Advocate fiercely for the user, then move forward decisively.**

- Articulate the strongest version of user needs
- Use AI to simulate scenarios, validate with real humans
- When research isn't feasible, ship hypothesis-driven v1
- Communicate tradeoffs: "We're assuming X because Y"

**When to apply:**
- Unclear if you understand user needs
- High-stakes interfaces (healthcare, finance, safety)
- Conflicting stakeholder requirements

---

### 5. Translate Complexity, Don't Just Simplify It

**Clarity isn't about dumbing down. It's about opening up.**

- Find visual/interactive approaches that preserve meaning
- Use progressive disclosure: simple first, deeper on demand
- Test with outsiders - if they don't get it, rethink

**Translation techniques:**
- Metaphors that shift perspective
- Interactive systems to experience complexity
- Layered interfaces (summary → detail)

**When to apply:**
- Complex work feels inaccessible
- Explaining AI alignment or technical concepts
- Research needs to reach non-experts

---

## The 5 Essential Questions

Before UX recommendations, gather context:

### Q1: What's the job to be done?

Format: "When I [situation], I want to [motivation], so I can [outcome]"

Quick options:
- Monitor/analyze data to spot issues
- Make a decision with confidence
- Understand something complex
- Complete a task efficiently
- Explore/discover possibilities

### Q2: Who's the user and how often?

| Type | Optimize For |
|------|--------------|
| Expert / Daily | Speed |
| Regular / Weekly | Balance clarity + efficiency |
| Occasional / Monthly | Clarity |
| First-time / One-time | Maximum guidance |

### Q3: What's complex about the system?

- Nothing - straightforward UI
- Lots of data (need hierarchy/filtering)
- AI/agent system (need transparency, reasoning, control)
- Technical complexity (need translation/metaphor)

### Q4: What's your riskiest assumption?

The one thing most likely to be wrong.
How will you test it in <3 days?

### Q5: Where does craft matter?

Mark ONE as "high craft":
- First impression / hero section
- Core interaction (the main thing they do)
- Explaining complexity
- Trust moment (error states, AI reasoning)

Everything else = ship fast.

---

## Design Guidelines

### Typography

**Font Stack:**
```css
--font-sans: 'Geist Sans', ui-sans-serif, system-ui, sans-serif;
--font-mono: 'Geist Mono', ui-monospace, monospace;
```

**Type Scale:**

| Token | Size | Usage |
|-------|------|-------|
| `text-xs` | 12px | Captions, metadata |
| `text-sm` | 14px | Secondary text, labels |
| `text-base` | 16px | Body text (default) |
| `text-lg` | 18px | Emphasized body |
| `text-xl` | 20px | Card titles |
| `text-2xl` | 24px | Page headings |
| `text-3xl` | 30px | Hero subheadings |
| `text-4xl` | 36px | Hero headings |

### Color & Theme

**Use OKLCH color space.** Always use semantic tokens, never hardcode.

```css
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --radius: 1rem;
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
}
```

### Motion & Animation

| Duration | Usage |
|----------|-------|
| 150ms | Quick interactions (hover, active) |
| 200ms | Standard transitions (modals, tooltips) |
| 300ms | Emphasis transitions (cards) |
| **Max: 500ms** | Never exceed for UI |

**Required:** Always support reduced motion:
```tsx
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
```

### Accessibility (WCAG 2.1 AA)

- Normal text: **4.5:1 contrast**
- Large text: **3:1 contrast**
- UI components: **3:1 contrast**
- Focus indicators: 2px minimum, visible
- Keyboard navigation: All interactive elements

---

## AI/Agentic Patterns

For any AI-powered interface:

### Transparency
- Show confidence levels: `<Badge>{confidence}% confident</Badge>`
- Explain reasoning: "Show AI reasoning" button
- Surface data sources

### Control
- User can override suggestions
- User can adjust parameters
- User can reject recommendations

### Agency
- AI augments, doesn't replace
- Clear handoff points
- User remains decision-maker

### Example Component Patterns

```tsx
// Confidence indicator
<Badge>{Math.round(confidence * 100)}% confident</Badge>

// Reasoning toggle
<Button onClick={() => setShowReasoning(!showReasoning)}>
  Show AI reasoning
</Button>

// User control
<Slider
  value={[aiConfidence]}
  onValueChange={setAiConfidence}
  min={0}
  max={100}
/>
```

---

## Output Format

When applying this skill, produce:

```markdown
# UX Strategy: {Feature Name}

## User Context
- **JTBD:** "{When I..., I want to..., so I can...}"
- **User type:** {type}, {frequency}
- **Complexity:** {level}
- **Riskiest assumption:** {assumption}
- **Craft moment:** {element}

## Principles Applied
- **Primary:** Principle #{n} - {why}
- **Secondary:** Principle #{n} - {why}

## Recommended Approach: {Name}

### Layout
{ASCII diagram}

### Craft vs Ship Fast
**High Craft:** {elements}
**Ship Fast:** {elements}

## Design Checklist
- [ ] {Requirement} → Principle #{n}
- [ ] {Requirement} → Principle #{n}
```

---

## Anti-Patterns

- Don't design for them - guide their thinking
- Don't give vague advice like "make it intuitive"
- Don't skip AI patterns for AI interfaces
- Don't over-engineer simple UIs
- Don't forget to propose validation plans
