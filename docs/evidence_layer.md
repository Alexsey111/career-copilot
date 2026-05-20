# Evidence Layer

## Purpose
Reusable candidate evidence for documents, cover letters, interview prep, and future recommendations.

## Source of truth
CandidateAchievement remains the user-confirmed fact source.
EvidenceSnippet is a reusable operational projection.
EvidenceUsage records where a snippet was reused.

## Product boundary
AI cannot create confirmed evidence.
Only user-confirmed or explicitly reviewed facts should become strong evidence.

## Models
EvidenceSnippet
EvidenceUsage

## Services
EvidenceExtractionService
EvidenceStrengthService
EvidenceSelectionService

## Current integrations
Resume generation
Cover letter generation
Interview prep
Question generation
GET /evidence/snippets
GET /evidence/usages
GET /evidence/insights

## Evidence-aware generation
Generation uses ranked evidence signals:
- fact_status
- evidence_strength
- STAR completeness
- skill overlap
- usage penalty

Generated documents store:
- selected_evidence_ids
- evidence_selection_reason

This makes evidence selection inspectable in review workflows.

Document Review Workspace now shows Evidence used:
- `selected_evidence_ids`
- `evidence_selection_reason`
- snippet `fact_status` and `evidence_strength` when available

This connects document approval to reusable evidence provenance.

Interview Prep Workspace shows Supporting evidence per question:
- `recommended_evidence`
- `evidence_links` fallback
- `evidence_id` / `title` / `reason` / `score`
- `fact_status` / `evidence_strength` when available
- STAR preview

## What is deterministic
STAR formatting
Skill tagging
Strength scoring
Evidence selection
Evidence insights counting and recommendations

## Not included yet
Embeddings
Vector search
Autonomous memory
Semantic graph DB
Automatic claims confirmation
Auto-confirmation
Autonomous evidence rewriting
