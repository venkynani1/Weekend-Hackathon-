alter table public.employee_snapshots
  alter column attrition drop not null;

comment on column public.employee_snapshots.attrition is
  'Observed historical outcome when known. Null for current workforce snapshots awaiting a future outcome window.';
