alter table public.projects
  drop constraint if exists projects_optional_instruction_check;

alter table public.projects
  add constraint projects_optional_instruction_check
  check (optional_instruction is null or char_length(optional_instruction) <= 450);
