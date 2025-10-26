# Research Guidelines (QualiAgent)

## Event Definition
- An **event** is a discrete experience, decision point, realization, or interaction described by the participant.

## Coding Principles
- Prefer **segment-level** events; use char spans for precision when necessary.
- One event can have **multiple labels**; avoid forcing fit.
- Summaries should be **neutral** and **concise**; avoid interpretation.

## Codebook Governance
- **Active** vs **Deprecated** statuses.
- Merges retain child history and redirect to the surviving code.
- Every category must have a **definition** and **exemplars**.

## Novelty Policy (MVP)
- Novel proposals require: suggested name, short definition (≤40 words), and 2 representative quotes.
- A human reviewer must **Accept/Revise/Reject**; decisions are logged.

## QA & Reliability
- Sample **double-coding** each sprint to monitor drift.
- Track AI proposal acceptance rates and rationales.

## Documentation
- Update `categories_log.md` on each taxonomy change (who, what, why, when).
