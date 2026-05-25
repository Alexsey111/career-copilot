# Trust Flow Diagram

```mermaid
flowchart TD
    V[Vacancy Analysis] --> Q[Document / Interview Generation]
    C[Confirmed Achievements] --> Q
    Q --> X[Evidence Selection]
    X --> P[Provenance Builder]
    P --> F[Confidence Normalization]
    F --> S[Unified Review Summary]
    S --> U[Trust Panel]
    U --> A[Recommended Actions]
    A --> H[Human Review]
    H --> R[Approved / Ready Output]

    G[Gap-risk Inputs] --> Q
    G --> S
```

## Notes

- Gap-risk items remain visible until a human resolves them.
- Confidence levels are deterministic, not ML-scored in this baseline.
- Recommended actions are derived from blockers, warnings, unsupported claims, and low-confidence evidence.
