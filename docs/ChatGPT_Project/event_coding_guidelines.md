# 🧩 QualiAgent Event Coding Guidelines

## 🎯 Purpose
These guidelines define how to extract and label “events” from qualitative interview transcripts for the QualiAgent project.  
They serve as the methodological foundation for both human and AI coders.

---

## 🧠 Core Concept: “Event”
An **event** refers to any **concrete action, reflection, or situation** that the participant describes or reflects upon.

Each event unit should be summarized as:

```yaml
[Event Type] + [Brief Description of Content]
```

Example:
> “我会觉得研一上学期，它会让我建立对咨询师的一个能力的认识。”  
> → Event: `Project Value — Building counselor competency framework during first semester`

## 🧩 Coding Principles

1. **Focus on Meaning Units**
   - Each segment should express a self-contained idea or reflection.
   - Avoid splitting an event across multiple codes unless necessary.

2. **Event Typology**
   - Each event belongs to one or more **event categories**.
   - Example major categories:
     - `Project Value`
     - `Self-Reflection`
     - `Interpersonal Experience`
     - `Learning Process`
     - `Emotional Response`
     - `Difficulties / Challenges`
     - `Future Orientation`

3. **Descriptive Summary**
   - Use concise, neutral phrasing.
   - Capture *what happened* and *why it matters* in 10–20 words.

4. **Consistency with Prior Codes**
   - When new transcripts continue previous ones, reuse existing categories.
   - If new content doesn’t fit any existing category, propose a new one but justify it briefly.

5. **Clarity and Traceability**
   - Every event code should link to:
     - Transcript ID
     - Speaker role (interviewer/interviewee)
     - Segment index or timestamp (if available)

---

## 🧰 Coding Output Example

| ID   | Transcript   | Segment | Event Type    | Summary                                     | Notes                          |
| ---- | ------------ | ------- | ------------- | ------------------------------------------- | ------------------------------ |
| 8    | #6 Interview | Line 42 | Project Value | Building counselor competency framework     | Same type as earlier segment 7 |
| 9    | #6 Interview | Line 43 | Project Value | Constructing counselor knowledge system     | Follows logically from 8       |
| 10   | #6 Interview | Line 44 | Project Value | Identifying counselor development direction | New sub-event                  |

---

## 🧩 Extension Rules

- New event categories must be **hierarchically compatible** with existing ones.
- When ambiguity arises, prefer **interpretive consistency** over granularity.
- Document every change to the event category system in the `categories_log.md`.

---

## ✅ Output Schema (for system-level integration)

```json
{
  "id": "auto",
  "transcript_id": "Interview_06",
  "segment_index": 44,
  "speaker": "interviewee",
  "event_type": "Project Value",
  "summary": "Identifying counselor development direction",
  "created_by": "AI or Human",
  "timestamp": "2025-10-26T22:00:00"
}
```

## 📘 Note

This document should evolve as QualiAgent matures.

All updates must maintain conceptual coherence and traceability.