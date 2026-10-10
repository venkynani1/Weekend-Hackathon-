create or replace function public.bootstrap_first_organization_admin()
returns trigger
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  target_organization_id uuid;
begin
  -- Serialize concurrent sign-ups so only one account can win the bootstrap.
  perform pg_advisory_xact_lock(hashtextextended('talentguard:first-admin', 0));

  if not exists (select 1 from public.organization_members) then
    select id
      into target_organization_id
      from public.organizations
     where slug = 'talentguard-demo';

    if target_organization_id is not null then
      insert into public.organization_members (organization_id, user_id, role)
      values (target_organization_id, new.id, 'org_admin')
      on conflict (organization_id, user_id) do nothing;
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.bootstrap_first_organization_admin() from public;

drop trigger if exists bootstrap_first_organization_admin on auth.users;
create trigger bootstrap_first_organization_admin
  after insert on auth.users
  for each row execute function public.bootstrap_first_organization_admin();

comment on function public.bootstrap_first_organization_admin() is
  'Hackathon bootstrap: grants the first Auth user org_admin access to TalentGuard Demo.';
