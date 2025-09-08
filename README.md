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

## Calabaria Architecture Overview

This section provides ModelOps developers with a high-level understanding of how Calabaria (the science framework) structures its calibration workflow and computes losses from simulation models.

### Conceptual Flow

```
Parameters → Model.simulate() → SimOutput → Target.evaluate() → Loss
     ↓                              ↓              ↓                ↓
  (from ask)                  (DataFrames)   (alignment +      (to tell)
                                            evaluation)
```

### Core Components

#### 1. **BaseModel** - Simulation Engine

The `BaseModel` abstract class defines the simulation contract:

```python
class BaseModel(ModelInterface, ABC):
    """Defines how simulations are run"""
    
    @abstractmethod
    def parameters(self) -> ParameterSet:
        """Define parameter space with bounds and transformations"""
        return ParameterSet.from_dict({
            "beta": {"lower": 1e-5, "upper": 1.0, "transform": "log"},
            "gamma": {"lower": 1e-5, "upper": 1.0, "transform": "log"}
        })
        
    @abstractmethod  
    def simulate(self, param_set: ParameterSet, seed: int) -> RawSimOutput:
        """Run simulation with given parameters and seed"""
        # Returns either a DataFrame or dict of DataFrames
        return {"infected": infected_df, "deaths": deaths_df}
```

**Key Points:**
- Models define their parameter space with bounds and optional transformations
- `simulate()` produces DataFrames (using Polars for performance)
- Output can be a single DataFrame or dict of named outputs
- Models can have extractors via `@model_output` decorator for complex outputs

#### 2. **Target** - Observation-Simulation Link

Targets connect model outputs to observed data:

```python
@dataclass
class Target:
    model_output: str              # Key to extract from SimOutput dict
    data: pl.DataFrame             # Observed/empirical data
    alignment: AlignmentStrategy   # How to join obs vs sim (time matching)
    evaluation: EvaluationStrategy # How to compute loss metric
    weight: float = 1.0           # Importance in multi-objective optimization
    
    def evaluate(self, replicated_sim_outputs: Sequence[SimOutput]) -> TargetEvaluation:
        # 1. Extract named output: simdata = outputs[self.model_output]
        # 2. Align observed vs simulated data
        # 3. Compute loss via evaluation strategy
        return TargetEvaluation(loss=0.234, weighted_loss=0.234 * self.weight)
```

#### 3. **Evaluation Strategies** - Loss Computation

Evaluation strategies define how to compute scalar loss from aligned data:

```python
class EvaluationStrategy(Protocol):
    def evaluate(self, aligned: AlignedData) -> TargetEvaluation:
        """Compute loss from aligned observed/simulated data"""
        # AlignedData.df has columns: [timestep, observed, simulated, replicate_id]
        pass

# Example: Mean Squared Error across replicates
class MeanOfPerReplicateMSE:
    def evaluate(self, aligned: AlignedData) -> TargetEvaluation:
        per_rep_mse = aligned.df.group_by("replicate_id").agg(
            mse=((col("observed") - col("simulated"))**2).mean()
        )
        return TargetEvaluation(
            name="infected_mse",
            loss=per_rep_mse["mse"].mean(),
            weight=1.0,
            weighted_loss=per_rep_mse["mse"].mean()
        )
```

**Available Strategies:**
- MSE, MAE, RMSE (pointwise losses)
- Negative log-likelihood (NLL) for stochastic models
- Custom strategies via Protocol implementation

#### 4. **CalibrationTask** - Orchestrator

The `CalibrationTask` ties everything together:

```python
@dataclass
class CalibrationTask:
    model: ModelInterface      # The simulation model
    targets: Targets          # Collection of Target objects
    replicates: int = 10      # Number of stochastic replicates
    
    def evaluate(self, param_set: ParameterSet) -> EvaluationResult:
        """Main entry point for parameter evaluation"""
        
        # 1. Run simulations with different seeds
        seeds = [self.seed_source.seed(i) for i in range(self.replicates)]
        outputs = [self.model.simulate(param_set, seed) for seed in seeds]
        
        # 2. Each target evaluates against all replicates
        target_results = []
        for target in self.targets:
            result = target.evaluate(outputs)  # alignment + evaluation
            target_results.append(result)
            
        # 3. Aggregate weighted losses
        total_loss = sum(t.weighted_loss for t in target_results)
        
        return EvaluationResult(
            param_set=param_set,
            total_loss=total_loss,
            target_results=target_results,
            seeds=seeds
        )
```

### Integration with ModelOps Contracts

The ModelOps ask-tell interface connects to Calabaria through adapters:

```python
# ModelOps side (ask-tell loop)
while not algo.finished():
    proposals = algo.ask(n=4)  # Get UniqueParameterSet proposals
    
    # Convert to Calabaria format and evaluate
    results = []
    for proposal in proposals:
        # Convert UniqueParameterSet → ParameterSet
        calabaria_params = ParameterSet.from_dict(proposal.parameters)
        
        # Run Calabaria evaluation
        eval_result = calibration_task.evaluate(calabaria_params)
        
        # Convert back to TrialResult
        results.append(TrialResult(
            param_id=proposal.param_id,
            loss=eval_result.total_loss,
            status=TrialStatus.OK,
            diagnostics=eval_result.per_target_loss()
        ))
    
    algo.tell(results)
```

### Key Design Patterns

1. **Dataframe-Centric**: All data manipulation uses Polars DataFrames for performance
2. **Separation of Concerns**: Models simulate, targets define comparisons, evaluators compute metrics
3. **Composable**: Mix and match alignment strategies, evaluation metrics, and dispatchers
4. **Multi-Objective**: Targets can have different weights for weighted sum optimization
5. **Stochastic Support**: Built-in replicate handling with deterministic seeding
6. **Type-Safe**: Extensive use of type hints and Pydantic models throughout

### Data Flow Summary

1. **Parameters In**: ModelOps provides parameter sets via ask()
2. **Simulation**: Calabaria runs model.simulate() with those parameters
3. **Alignment**: Targets align simulation outputs with observed data
4. **Evaluation**: Loss metrics computed from aligned data
5. **Results Out**: Total loss returned to ModelOps via tell()

This architecture allows ModelOps to focus on optimization algorithms and infrastructure while Calabaria handles the scientific computing aspects of model calibration
