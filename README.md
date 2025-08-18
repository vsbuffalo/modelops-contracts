# ModelOps Contracts

Stable interface between ModelOps (infrastructure) and Calabaria (science).

## Installation

```bash
pip install modelops-contracts

# For development:
pip install modelops-contracts[dev]
```

## Usage

```python
from modelops_contracts import (
    UniqueParameterSet,
    TrialResult,
    TrialStatus,
    AlgorithmAdapter,
    CONTRACTS_VERSION,
)

# Create parameter set with stable ID
params = UniqueParameterSet.from_dict({"learning_rate": 0.01, "batch_size": 32})

# Report results  
result = TrialResult(
    param_id=params.param_id,
    loss=0.234,
    status=TrialStatus.OK,
    diagnostics={"val_accuracy": 0.95}
)
```

## Dependency Rules

- **ModelOps**: May import from modelops_contracts only
- **Calabaria**: May import from modelops_contracts only  
- **Contracts**: Zero heavy dependencies (no NumPy, Polars, Optuna, etc.)

## Contract Guarantees

- param_id is stable: same params → same ID
- loss is always finite for OK status
- diagnostics < 64KB when serialized
- Seeds are uint64 range
- All types are immutable (frozen dataclasses)

## Version

Current version: 0.1.0
