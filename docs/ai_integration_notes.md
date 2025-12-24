# AI Integration Notes (QualiAgent)

## Objectives
- Closed-set labeling against the **current codebook** for consistency.
- Open-set **novelty proposals** when no existing code fits, with rationale and draft definition.

## Interfaces
- `ScorerProtocol.extract_events(segments) -> [Event]`
- `ScorerProtocol.label_events(events, codebook) -> [EventLabel]`

## Prompting Strategy (MVP)
- **Event extraction**: concise summary (≤30 chars), reference `segment_id`, prefer segment-level spans; avoid speculative inference.
- **Labeling**: Provide code name + definition context + 2 exemplars per code when available.

## Config & Env
- `OPENAI_API_KEY`, `OPENAI_API_BASE_URL`, `OPENAI_LLM_MODEL`, `OPENAI_EMBED_MODEL`, `CHUNK_TOKENS`.
- Store `prompt_hash`, `engine_name`, `engine_version` in `source_meta`.

## Thresholds (initial, tune later)
- Novelty trigger when `max_similarity < 0.60` or model uncertainty high.
- Cap proposals to **≤2** new categories per transcript in MVP.

## Logging & Provenance
- Persist request/response IDs, timestamps, and prompt hashes.
- Save raw JSON alongside formatted memo/event content.

## Evaluation (post-data)
- Holdout **gold set**; track precision/recall for labels; track acceptance rate of AI proposals in Review Queue.
