"""
Adaptive algorithm protocol (ask-tell interface).

The adaptive algorithm protocol defines a two-phase optimizer API loop between 
the search algorithm and the evaluator. This is the handshake between the search 
algorithm and your evaluator. A worker repeatedly asks for a batch (possibly size 1) 
of parameter candidates, runs the simulation/evaluation, and then tells the algorithm 
the observed results. The algorithm may return fewer than n candidates if it is 
nearing completion; it may also return an empty list when awaiting results. The loop 
terminates when finished() becomes True.

Typical control flow:
    while not algo.finished():
        batch = algo.ask(n)
        if not batch:
            # no proposals right now (e.g., pending results) — continue loop
            continue
        results = evaluate(batch)  # run sims, aggregate replicates, compute loss
        algo.tell(results)

What the algorithm guarantees:
- ask(n) returns up to n unique proposals, each with a stable param_id.
  Proposals are leased atomically so the same trial won't go to two workers.
  It can return fewer than n or even [] (that just means "nothing to hand out right now").
- finished() flips to True when no more proposals will be produced.
  After that, ask() returns [], but late results for already-leased trials are still accepted.

What you send back:
- Call tell([...]) with results for any previously asked trials, in any order.
  Re-sending the exact same result is a no-op; sending a different result for a finished trial is rejected.
  Each result carries: param_id, a terminal state {COMPLETED|FAILED|TIMEOUT},
  and (for COMPLETED) the objective value(s). Extras like diagnostics/artifacts are optional.

Internal model (for intuition):
- Trials move through: PENDING → LEASED → {COMPLETED | FAILED | TIMEOUT}.
  Each trial ends in exactly one terminal state. Terminal writes are idempotent.

Coordination & "don't shoot yourself in the foot":
- To run multiple workers, back this with a coordinator (e.g., a transactional DB/service)
  that gives you atomic leases and durable writes. In-memory storage is fine for a single process only.
- Leases may have a TTL so crashed workers don't hold trials forever; expired leases can be reclaimed.
- If ask() returns [], back off briefly (don't busy-loop).

Reproducibility:
- Proposals should include a base RNG seed; derive replicate seeds deterministically
  (e.g., hash of {trial_id, replicate_index}) and record minimal provenance in results.

Future-friendly:
- You can add optional progress/pruning/heartbeat hooks later without changing this core contract.
"""

from typing import Protocol, runtime_checkable
from .types import UniqueParameterSet, TrialResult


@runtime_checkable
class AdaptiveAlgorithm(Protocol):
    """Protocol for optimization algorithms."""
    
    def ask(self, n: int) -> list[UniqueParameterSet]:
        """Request n parameter sets to evaluate."""
        ...
    
    def tell(self, results: list[TrialResult]) -> None:
        """Report evaluation results back to algorithm."""
        ...
    
    def finished(self) -> bool:
        """Check if optimization is complete."""
        ...


__all__ = ["AdaptiveAlgorithm"]