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
from modelops_contracts import SimTask, UniqueParameterSet

# Create a simulation task using factory method
task = SimTask.from_components(
    import_path="covid.models.SEIR",
    scenario="baseline",
    bundle_ref="sha256:abc123def456789...",
    params={"R0": 2.5, "incubation_days": 5},
    seed=42,
    outputs=["infections", "deaths"]
)

# Or create directly with constructor
task = SimTask(
    entrypoint="covid.models.SEIR/baseline",  # Note: no @digest suffix
    bundle_ref="sha256:abc123def456789...",
    params=UniqueParameterSet.from_dict({"R0": 2.5}),
    seed=42
)
```

### Working with Results

```python
from modelops_contracts import TrialResult, TrialStatus, UniqueParameterSet

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

### Hexagonal Architecture Ports

The contracts now include port definitions for clean hexagonal architecture:

```python
from modelops_contracts import (
    Future,
    SimulationServicePort,
    ExecutionEnvironment,
    BundleRepository,
    CAS,
    WireFunction
)

# Implement the ExecutionEnvironment port
class MyExecutionEnv:
    def run(self, task: SimTask) -> SimReturn:
        # Execute simulation
        pass
    
    def health_check(self) -> dict:
        return {"status": "healthy"}
    
    def shutdown(self) -> None:
        # Clean up resources (critical for WorkerPlugin lifecycle)
        pass
```

## Key Contracts

### Core Types

- **SimTask**: Specification for simulation tasks
  - Use `SimTask.from_components()` factory for programmatic creation
  - Entrypoint format: `"module.Class/scenario"` (no digest suffix)
  
- **UniqueParameterSet**: Parameters with stable content-based ID

- **SimReturn**: Results from completed simulation with outputs

- **TableArtifact**: Extracted table output (Arrow IPC format)

### Protocols (Ports)

- **SimulationService**: Primary port for submitting simulations
  - `submit()`, `gather()`, `submit_batch()`

- **ExecutionEnvironment**: Port for executing simulations
  - `run()`, `health_check()`, `shutdown()`

- **BundleRepository**: Port for fetching simulation bundles
  - `ensure_local()`, `exists()`

- **CAS**: Content-addressable storage for large artifacts
  - `put()`, `get()`, `exists()`

- **WireFunction**: Low-level execution contract for isolated workers

- **AdaptiveAlgorithm**: Ask-tell interface for optimization
  - `ask()`, `tell()`, `finished()`

## Contract Guarantees

- **Stable IDs**: Same parameters always produce the same `param_id`
- **Finite losses**: Loss must be finite for `TrialStatus.COMPLETED`
- **Size limits**: Diagnostics must be < 64KB when JSON-serialized
- **Seed range**: Seeds are validated to be within uint64 range (0 to 2^64-1)
- **Immutability**: All contract types are frozen dataclasses with deeply immutable fields
- **Entrypoint format**: Simple `"module.Class/scenario"` format without digest

## Dependency Rules

- **ModelOps**: May import from modelops_contracts only
- **Calabaria**: May import from modelops_contracts only  
- **Contracts**: Zero heavy dependencies (no NumPy, Polars, Optuna, etc.)

## Version

Current version: 0.3.0

### Breaking changes from 0.2.0:
- Entrypoint format simplified (removed `@digest12` suffix)
- Removed `SimTask.from_entrypoint()` factory method
- Added ports module for hexagonal architecture
- Cleaned up exports (removed internal types)

### Breaking changes from 0.1.0:
- SimTask shape changed (scenario now embedded in entrypoint)
- Two-root provenance model (sim_root vs task_id)
- TrialStatus.OK renamed to TrialStatus.COMPLETED

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