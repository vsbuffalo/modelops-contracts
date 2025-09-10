# ModelOps Contracts

Stable interface between ModelOps (infrastructure) and Calabaria (science).

## Installation

```bash
pip install modelops-contracts

# For development:
pip install modelops-contracts[dev]
```

## Usage

### Creating Simulation Tasks

```python
from modelops_contracts import (
    SimTask,
    UniqueParameterSet,
    TrialResult,
    TrialStatus,
    CONTRACTS_VERSION,
)

# Create a simulation task
task = SimTask.from_components(
    import_path="covid.models.SEIR",
    scenario="baseline",
    bundle_ref="sha256:abc123def456789...",
    params={"R0": 2.5, "incubation_days": 5},
    seed=42,
    outputs=["infections", "deaths"]
)

# Or create from a pre-formatted entrypoint
task = SimTask.from_entrypoint(
    entrypoint="covid.models.SEIR/baseline@abc123def456",
    bundle_ref="sha256:abc123def456789...",
    params={"R0": 2.5},
    seed=42
)
```

### Working with Results

```python
# Create parameter set with stable ID
params = UniqueParameterSet.from_dict({"learning_rate": 0.01, "batch_size": 32})

# Report results  
result = TrialResult(
    param_id=params.param_id,
    loss=0.234,
    status=TrialStatus.COMPLETED,
    diagnostics={"val_accuracy": 0.95}
)
```

## Dependency Rules

- **ModelOps**: May import from modelops_contracts only
- **Calabaria**: May import from modelops_contracts only  
- **Contracts**: Zero heavy dependencies (no NumPy, Polars, Optuna, etc.)

## Contract Guarantees

- **Stable IDs**: Same parameters always produce the same `param_id`
- **Finite losses**: Loss must be finite for `TrialStatus.COMPLETED`
- **Size limits**: Diagnostics must be < 64KB when JSON-serialized
- **Seed range**: Seeds are validated to be within uint64 range (0 to 2^64-1)
- **Immutability**: All contract types are frozen dataclasses with deeply immutable fields
- **Entrypoint validation**: Bundle references and entrypoint digests are validated to match

## Version

Current version: 0.2.0

Breaking changes from 0.1.0:
- SimTask shape changed (scenario now embedded in entrypoint)
- Two-root provenance model (sim_root vs task_id)
- TrialStatus.OK renamed to TrialStatus.COMPLETED

## Key Contracts

### SimTask
Core specification for simulation tasks. Use factory methods for creation:
- `SimTask.from_components()`: Build from individual parts (preferred)
- `SimTask.from_entrypoint()`: Use pre-formatted entrypoint string

### SimulationService Protocol
Implemented by execution backends (Dask, Ray, local). Provides:
- `submit(task)`: Submit single task
- `submit_batch(tasks)`: Submit multiple tasks
- `gather(futures)`: Collect results

### Adaptive Algorithms
Ask-tell interface for optimization:
- `ask(n)`: Request n parameter sets to evaluate
- `tell(results)`: Report evaluation results

## Development

### Testing

```bash
uv run pytest tests/
```

### Type Checking

```bash
uv run mypy src/
```

## License

MIT