# System Overview

Career Copilot is a single-node pilot application composed of:

- a FastAPI backend;
- a Streamlit frontend;
- PostgreSQL persistence;
- local/object storage for uploads;
- deterministic services for documents, applications, interview prep, evidence, and review.

The backend exposes the canonical API contract. The frontend must consume review and diagnostics summaries instead of inferring internal storage shape.

Key principles:

- human review stays in the loop for generated drafts;
- provenance must explain generated output;
- trust data is normalized before it reaches the UI;
- demo flows should be reproducible and deterministic.
