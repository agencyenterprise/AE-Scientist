# Shared Packages

This directory contains packages that are shared between `server` and `research_pipeline`.

## Why Shared Packages?

Both `server` and `research_pipeline` need certain functionality, but they have very different dependency profiles:

- **server**: Lightweight web service with FastAPI, minimal ML dependencies
- **research_pipeline**: Heavy ML workload with PyTorch, transformers, scikit-learn, etc.

Extracting shared code into standalone packages allows us to:

1. Avoid duplicating code between projects
2. Keep each project's dependencies minimal
3. Test shared functionality independently
4. Deploy server without pulling in heavy ML dependencies

## Packages

### ae-paper-review

Standalone paper review functionality for AI-generated research papers.

**Features:**
- LLM-based paper review with ensemble scoring and reflection
- VLM-based figure/table review and duplicate detection
- PDF text extraction and processing
- Few-shot examples for calibrated reviews

**Usage:**
```python
from ae_paper_review import perform_review, load_paper

# Load paper from PDF
paper_text = load_paper("paper.pdf")

# Perform review
result = perform_review(
    paper_text,
    model="anthropic:claude-sonnet-4-20250514",
    temperature=0.1,
    event_callback=lambda e: print(f"Progress: {e.progress:.0%}"),
    num_reflections=2,
    num_fs_examples=1,
    num_reviews_ensemble=3,
)

print(f"Decision: {result.review.decision}")
print(f"Overall Score: {result.review.overall}")
```

**Key design decisions:**
- Stateless: All content passed as parameters, no file I/O within the package
- Token usage returned with results (not tracked via callbacks)
- Lightweight dependencies: No torch, transformers, or heavy ML libs

## Installation

Packages are installed as editable dependencies via each project's Makefile:

```bash
# From server/ or research_pipeline/
make install
```

This runs `uv pip install -e ../packages/ae-paper-review` after `uv sync`.
