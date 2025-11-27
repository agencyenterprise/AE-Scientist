# aigraph

Graph implementation based on [Sakana][1]

## About

Scientific research automation using LangGraph agents.

## Development

### Requirements

- **pdflatex**: Required for LaTeX document compilation

```bash
sudo apt-get install texlive
# or
brew install basictex
```

### Setup

```bash
uv sync
```

### LangGraph Core Concepts

- **Context**: Passes runtime dependencies (database connections)
- **State**: Holds graph data relevant to execution
- **Config**: Configures LangChain/LangGraph (e.g., `thread_id`)
- **Checkpointer**: Persists state at each super-step

**Use Cases**:
- Human-in-the-loop: Pause for intervention at nodes
- Memory: Retain conversation history across sessions
- Time travel: Revert to previous execution states
- Fault tolerance: Resume from last checkpoint

**Example**:

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

# Define state
class State(TypedDict):
    messages: list[str]

# Node with context access
def process(state: State, context):
    db = context["db"]  # Access runtime dependency
    # Use db connection here
    return {"messages": state["messages"] + ["done"]}

# Build graph
graph = StateGraph(State)
graph.add_node("process", process)
graph.set_entry_point("process")
graph.set_finish_point("process")

# Compile with checkpointer
app = graph.compile(checkpointer=MemorySaver())

# Invoke with config and context
result = app.invoke(
    {"messages": ["start"]},
    config={"configurable": {"thread_id": "1"}},
    context={"db": db_connection}
)
```

## Running Scripts

Execute individual agents:

- `uv run -m aigraph.scripts.run_baseline` - Define metrics, run baseline
- `uv run -m aigraph.scripts.run_tuning` - Hyperparameter optimization
- `uv run -m aigraph.scripts.run_ablation` - Ablation studies
- `uv run -m aigraph.scripts.run_plotting` - Generate plots and analysis
- `uv run -m aigraph.scripts.run_writeup` - Generate LaTeX document
- `uv run -m aigraph.scripts.run_pipeline` - Execute complete pipeline

## Complete Pipeline (run_pipeline)

Main orchestrator with parallel experiments and review loop:

```mermaid
graph TD
    START([START]) --> node_ideas
    node_ideas -->|Fan Out| node_experiment
    node_experiment --> node_review
    node_review -->|Retry| node_experiment
    node_review -->|Done| END([END])
```

### Experiment Sub-Graph

Sequential stages within each experiment:

```mermaid
graph TD
    START([START]) --> node_setup
    node_setup --> node_research
    node_research --> node_baseline
    node_baseline --> node_tuning
    node_tuning --> node_ablation
    node_ablation --> node_plotting
    node_plotting --> node_writeup
    node_writeup --> node_judge
    node_judge --> END([END])
```

## Agent Architectures

### 1. Baseline Agent

Defines metrics and runs baseline experiment.

```mermaid
graph TD
    START([START]) --> node_baseline_define_metrics
    node_baseline_define_metrics --> node_baseline_code_experiment
    node_baseline_code_experiment --> node_baseline_exec_experiment
    node_baseline_exec_experiment --> node_baseline_parse_experiment_output
    node_baseline_parse_experiment_output -->|Has Bug| node_baseline_code_experiment
    node_baseline_parse_experiment_output -->|No Bug| node_baseline_code_metrics_parser
    node_baseline_code_metrics_parser --> node_baseline_exec_metrics_parser
    node_baseline_exec_metrics_parser --> node_baseline_parse_metrics_output
    node_baseline_parse_metrics_output -->|Has Bug| node_baseline_code_metrics_parser
    node_baseline_parse_metrics_output -->|No Bug| END([END])
```

### 2. Tuning Agent

Proposes and tests hyperparameters.

```mermaid
graph TD
    START([START]) --> node_tuning_propose_hyperparam
    node_tuning_propose_hyperparam --> node_tuning_code_tuning
    node_tuning_code_tuning --> node_tuning_exec_tuning
    node_tuning_exec_tuning --> node_tuning_parse_tuning_output
    node_tuning_parse_tuning_output -->|Has Bug| node_tuning_code_tuning
    node_tuning_parse_tuning_output -->|No Bug| node_tuning_code_metrics_parser
    node_tuning_code_metrics_parser --> node_tuning_exec_metrics_parser
    node_tuning_exec_metrics_parser --> node_tuning_parse_metrics_output
    node_tuning_parse_metrics_output -->|Has Bug| node_tuning_code_metrics_parser
    node_tuning_parse_metrics_output -->|No Bug| END([END])
```

### 3. Ablation Agent

Proposes and runs ablation studies.

```mermaid
graph TD
    START([START]) --> node_ablation_propose_ablation
    node_ablation_propose_ablation --> node_ablation_code_ablation
    node_ablation_code_ablation --> node_ablation_exec_ablation
    node_ablation_exec_ablation --> node_ablation_parse_ablation_output
    node_ablation_parse_ablation_output -->|Has Bug| node_ablation_code_ablation
    node_ablation_parse_ablation_output -->|No Bug| node_ablation_code_metrics_parser
    node_ablation_code_metrics_parser --> node_ablation_exec_metrics_parser
    node_ablation_exec_metrics_parser --> node_ablation_parse_metrics_output
    node_ablation_parse_metrics_output -->|Has Bug| node_ablation_code_metrics_parser
    node_ablation_parse_metrics_output -->|No Bug| END([END])
```

### 4. Plotting Agent

Generates and analyzes visualization plots.

```mermaid
graph TD
    START([START]) --> node_plotting_code_plotting
    node_plotting_code_plotting --> node_plotting_exec_plotting
    node_plotting_exec_plotting --> node_plotting_parse_plotting_output
    node_plotting_parse_plotting_output -->|Has Bug| node_plotting_code_plotting
    node_plotting_parse_plotting_output -->|No Bug, Fan Out| node_plotting_analyze_single_plot
    node_plotting_analyze_single_plot --> END([END])
```

### 5. Writeup Agent

Generates and compiles LaTeX document.

```mermaid
graph TD
    START([START]) --> node_writeup_setup_writeup
    node_writeup_setup_writeup --> node_writeup_generate_writeup
    node_writeup_generate_writeup --> node_compile_writeup
    node_compile_writeup --> node_parse_compile_output
    node_parse_compile_output -->|Has Bug| node_writeup_generate_writeup
    node_parse_compile_output -->|No Bug| END([END])
```

[1]: https://github.com/SakanaAI/AI-Scientist