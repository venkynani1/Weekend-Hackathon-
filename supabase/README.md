# Supabase migrations

The migration creates the multi-tenant foundation and preserves all 35 source
columns in `public.employee_snapshots`. The model identifier and constant
columns remain in the source-of-truth table even though they are excluded from
model training.

The initial dataset is loaded as one immutable snapshot. Future ingestion runs
append new dated snapshots and must never overwrite earlier dates.

The migration sequence is:

1. Apply `migrations/202610100001_talentguard_foundation.sql`.
2. Create an `ingestion_runs` row for the synthetic seed.
3. Insert the 1,470 CSV rows in bounded, idempotent batches.
4. Verify the row count, distinct employee count, attrition count, null count,
   constants, and expected EDA rates.
5. Apply `202610100002_operational_workflow.sql` for model versions, scoring
   runs, risk scores, interventions, audit events, grants, and RLS.
6. Apply `202610100003_operational_snapshots.sql` so current snapshots may have
   a null future outcome.
7. Apply `202610100004_advisor_indexes.sql` and rerun security/performance
   advisors.

RLS grants authenticated users read access only when they have a matching
`organization_members` row. For the hackathon bootstrap, the first Auth user is
automatically assigned `org_admin` access to `talentguard-demo`; later users must
be assigned explicitly. Data ingestion uses a trusted server-side role;
there are intentionally no browser write policies on employee snapshots.

The `private.is_organization_member` function is outside the exposed Data API
schema. Authenticated users can write only intervention cases for organizations
they belong to; a private trigger records immutable audit events.
