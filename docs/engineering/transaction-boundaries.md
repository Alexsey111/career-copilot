# docs\engineering\transaction-boundaries.md

# Transaction Boundary Rules

## Goal

Keep transaction lifecycle predictable and centralized.

This project uses route-level transaction ownership.

---

# Rules

## Repositories

Repositories must NEVER:

- call `session.commit()`
- call `session.rollback()`

Repositories are CRUD/data-access only.

Allowed:

- `session.add(...)`
- `session.flush()`
- `session.refresh(...)`
- queries

---

## Services

Services must NEVER:

- call `session.commit()`
- call `session.rollback()`

Services contain business logic only.

Services MAY:

- create/update multiple entities
- call repositories
- use `session.flush()` when IDs or DB validation are needed

---

## AI Use Cases

AI orchestration/use-case layers must NEVER:

- commit transactions
- rollback transactions

They may orchestrate services and repositories.

---

## Route Layer

Routes own transaction lifecycle.

Pattern:

```python
try:
    result = await service.execute(...)
    await session.commit()
    return result
except Exception:
    await session.rollback()
    raise
```

---

# Why

This prevents:

- partial writes
- inconsistent multi-step flows
- broken orchestration chains
- nested transaction ownership conflicts

---

# Preferred Transaction Flow

Route
→ Service
→ Repository
→ flush()
→ return
→ commit() at route boundary