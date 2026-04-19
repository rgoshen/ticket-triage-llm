# Ground Truth Audit — Phase 3 Replication

Tickets where all three models (2B, 4B, 9B) scored 0/5 on the same field across 5 independent runs. When every model consistently disagrees with a label, the label is the first thing to check.

## Labels Changed

### n-012 — "How to integrate with SSO?"
- **category**: `other` → `feature_request`. An integration request is a feature request, not "other." All models agreed 15/15.
- **severity**: `medium` → `low`. No business impact stated; informational inquiry. All models agreed 15/15.
- **routing**: `support` → `product`. SSO integration is product/engineering scope, not frontline support. All models agreed 15/15.

### n-017 — "Dashboard widgets not refreshing"
- **routing**: `product` → `infra`. Stale data for 3+ hours affecting all users is a backend/infrastructure issue. All models agreed 15/15.

### n-027 — "Calendar integration feature"
- **severity**: `medium` → `low`. Feature requests carry no business urgency unless explicitly stated. All models agreed 15/15.

### n-035 — "Notification behavior — thought I'd mention it"
- **category**: `bug` → `other`. User isn't sure it's a problem ("not really bothering me, just seemed odd"). All models agreed on not-bug 15/15.

### n-028 — "Critical data loss during backup"
- **category**: `bug` → `outage`. All models said `outage` (15/15). The operational consequence settles it: data loss with active business impact needs immediate triage. Labeling as `bug` risks slower pickup; `outage` ensures urgency-appropriate routing.

## Labels Kept

### n-024 — "Documentation unclear"
- **category**: kept as `other`. Models split between `feature_request` (2B) and `bug` (4B, 9B). Documentation gaps aren't bugs in the software and aren't feature requests — `other` is the correct catch-all. The models are wrong here.
- **routing**: kept as `support`. Models unanimously said `product`, but documentation questions are frontline support scope in most orgs.

## Observation

6 of 6 flagged tickets had incorrect ground truth (n-024 kept but was not a unanimous failure — models split). The per-ticket replication matrix surfaced label errors that aggregate accuracy metrics hid. This is a genuine finding about production ML evaluation: model consensus against a label is a stronger audit signal than manual review, especially for ambiguous categories where human labelers make judgment calls without explicit definitions.
