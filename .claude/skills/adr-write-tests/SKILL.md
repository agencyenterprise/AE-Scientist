---
description: Testing patterns and templates for this project
tools: Read, Write, Bash, Glob, Grep
---

# ADR Write Tests Skill

## When to Use
- Adding tests for new features
- Increasing coverage for existing code
- TDD workflow (test first)

## Test Framework Detection

```bash
# Check package.json for test framework
grep -E "jest|vitest|mocha|pytest" package.json 2>/dev/null

# Find existing tests for patterns
find . -name "*.test.*" -o -name "*.spec.*" | head -5
```

## Process

### Step 1: Find Test Patterns
```bash
# Look at existing tests
cat $(find . -name "*.test.ts" | head -1)
```

### Step 2: Identify What to Test

| Type | Focus |
|------|-------|
| Unit | Single function/component in isolation |
| Integration | Multiple units working together |
| E2E | Full user flows |

### Step 3: Write Tests

Follow existing patterns. Typical structure:

```typescript
describe('ComponentName', () => {
  // Setup
  beforeEach(() => {
    // Reset state
  });

  describe('feature group', () => {
    it('should do expected behavior', () => {
      // Arrange
      // Act
      // Assert
    });

    it('should handle edge case', () => {
      // Test edge cases
    });
  });
});
```

### Step 4: Run and Verify
```bash
npm test -- --watch
```

## Test Templates

### React Component Test
```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComponentName } from './ComponentName';

describe('ComponentName', () => {
  it('renders correctly', () => {
    render(<ComponentName />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('handles click', async () => {
    const onClick = vi.fn();
    render(<ComponentName onClick={onClick} />);
    
    await userEvent.click(screen.getByRole('button'));
    
    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

### Hook Test
```typescript
import { renderHook, act } from '@testing-library/react';
import { useCustomHook } from './useCustomHook';

describe('useCustomHook', () => {
  it('returns initial state', () => {
    const { result } = renderHook(() => useCustomHook());
    expect(result.current.value).toBe(initial);
  });

  it('updates state', () => {
    const { result } = renderHook(() => useCustomHook());
    
    act(() => {
      result.current.update(newValue);
    });
    
    expect(result.current.value).toBe(newValue);
  });
});
```

### API/Service Test
```typescript
import { fetchData } from './api';

describe('fetchData', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('returns data on success', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'test' }),
    });

    const result = await fetchData();
    
    expect(result).toEqual({ data: 'test' });
  });

  it('throws on error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });

    await expect(fetchData()).rejects.toThrow();
  });
});
```

## Coverage Goals

| Type | Target |
|------|--------|
| Statements | 80% |
| Branches | 75% |
| Functions | 80% |
| Lines | 80% |

```bash
npm test -- --coverage
```

## Anti-Patterns

- ❌ Testing implementation details
- ❌ Brittle tests tied to UI structure
- ❌ Missing edge cases
- ❌ No error case testing

- ✅ Test behavior, not implementation
- ✅ Use accessible queries (getByRole, getByLabelText)
- ✅ Cover happy path + edge cases + errors
- ✅ Keep tests focused and readable
