# Architecture Diagram

```mermaid
flowchart LR
    U[Candidate / Operator] --> S[Streamlit Frontend]
    S -->|review-summary| B[FastAPI Backend]
    B --> D[(PostgreSQL)]
    B --> F[(File Storage)]
    B --> A[Document + Interview Services]
    A --> P[Provenance + Confidence Normalization]
    P --> R[Unified Review Summary]
    R --> S

    subgraph Trust Layer
        P
        R
    end

    subgraph Core Domains
        A
        D
        F
    end
```

## Reading Guide

- The frontend reads the unified review payload.
- The backend keeps provenance and confidence normalization inside the trust layer.
- The UI should not reconstruct internal state from storage fields.
