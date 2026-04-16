# JobRadar — Pipeline Tracker (TODO)

Transform JobRadar from a triage tool into a full job search CRM.

---

## New Status Pipeline

Replace the binary `approved / bypassed` with a full pipeline enum:

```
shortlisted → research_first → apply_later → applied → interviewing → offer | bypassed
```

Update `StatusUpdate` Pydantic model in `api/routes_jobs.py` to accept the new values.
Update Firestore `jobs_raw` documents to use the expanded status field.

---

## Firestore Schema Additions

Add to `jobs_raw` documents:

| Field | Type | Description |
|-------|------|-------------|
| `stage` | string | Current pipeline stage |
| `next_action` | string | What needs to happen next |
| `next_action_date` | ISO string | When to follow up |
| `notes` | string | Free-text notes per job |
| `outreach_sent` | boolean | Whether outreach draft was sent |
| `applied_at` | ISO string | When the application was submitted |

---

## UI Changes

### Job Cards (left panel)

- Replace Pursue / Bypass buttons with a **stage selector** — pill buttons or a small dropdown showing current stage
- Add a color-coded stage badge next to the recommendation badge
- Show `next_action_date` inline if set (e.g. "Follow up Apr 20")
- Highlight overdue next actions in amber/red

### Job Detail / Chat Panel (right panel)

Add a **Follow-up bar** above the chat messages:

- Stage selector (advance through pipeline with one tap)
- Next action field + date picker
- Notes textarea (auto-saved on blur)
- Outreach "Draft → Sent" toggle

### New View: Follow-up Dashboard

A third panel / tab alongside the job list:

- Jobs with a `next_action_date` set, sorted ascending
- Overdue actions highlighted
- Quick-advance buttons (no need to open full card)
- Filter: All | Overdue | This Week | Applied | Interviewing

---

## API Changes

### `POST /jobs/{job_id}/status`

Expand accepted status values:

```python
Literal["shortlisted", "research_first", "apply_later", "applied",
        "interviewing", "offer", "bypassed", "scored"]
```

### New endpoint: `PATCH /jobs/{job_id}/followup`

```json
{
  "next_action": "Follow up with recruiter",
  "next_action_date": "2026-04-22T00:00:00",
  "notes": "Strong fit, need to prep system design",
  "outreach_sent": true
}
```

---

## AI Advisor Enhancements

Once stage + notes are in context, the Advisor system prompt can include them:

- **Applied stage** → advisor shifts to interview prep mode
- **Interviewing stage** → advisor knows which round, can drill into likely questions
- **Follow-up prompts** the advisor should handle well:
  - "Draft a follow-up email — it's been 5 days since I applied"
  - "What should I prepare for the phone screen tomorrow?"
  - "How are my active applications looking?" (summary across all in-flight jobs)

Pass `stage`, `notes`, `applied_at`, and `next_action` into the job context block in `api/routes_jobs.py`.

---

## Header Stats Bar

Add stage counts to the stats bar:

```
[◎ 0 pursue]  [◑ 7 review]  |  [✓ 2 pursuing]  [→ 3 applied]  [◈ 1 interviewing]
```

---

## Implementation Order

1. Expand status enum in backend + Firestore
2. Add `followup` fields to schema
3. New `PATCH /jobs/{job_id}/followup` endpoint
4. Update job cards with stage selector + next action display
5. Follow-up bar in chat panel
6. Follow-up dashboard view
7. Pass new fields into Advisor system prompt
8. Update header stats bar
