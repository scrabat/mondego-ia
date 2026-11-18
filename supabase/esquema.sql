-- Mondego IA — esquema para o Supabase (Fase 2: Salas, contas e ficheiros partilhados)
-- AINDA NÃO APLICADO. Em Authentication → Providers → Email podes desligar «Confirm email» para testar mais depressa.
-- Corre este ficheiro no SQL Editor do teu projeto Supabase quando o criares.
-- As regras de acesso (Row Level Security) garantem que cada pessoa só vê o que deve (RGPD).

create extension if not exists "pgcrypto";

-- Perfil de cada utilizador (a conta/login é gerida pelo Supabase Auth: auth.users)
create table if not exists perfis (
  id uuid primary key references auth.users(id) on delete cascade,
  nome_completo text not null,
  nivel text check (nivel in ('Ensino secundário', 'Ensino superior')),
  area text,
  instituicao text,
  grau text,
  curso text,
  vinculo text check (vinculo in ('Aluno', 'Professor')),
  departamentos text[] default '{}',
  disciplinas text[] default '{}',
  foto_b64 text,                      -- fotografia do perfil (pequena, em base64)
  criado_em timestamptz default now()
);

create table if not exists salas (
  id uuid primary key default gen_random_uuid(),
  nome text not null check (char_length(nome) between 2 and 80),
  tipo text not null check (tipo in ('grupo_estudo', 'cadeira')),
  cadeira text,
  criador_id uuid not null references perfis(id) on delete cascade,
  codigo text not null unique check (codigo ~ '^[A-Z0-9]{6,10}$'),
  chat_ativo boolean not null default false,
  criada_em timestamptz default now(),
  -- definições da sala (só o criador as muda)
  descricao text not null default '',
  cor text not null default 'terracota',
  aviso text not null default '',
  chat_modo text not null default 'todos' check (chat_modo in ('todos', 'criador', 'desligado')),
  quem_publica text not null default 'todos' check (quem_publica in ('criador', 'todos')),
  ficheiros_privados boolean not null default true,
  assistente_ativo boolean not null default true,
  convites text not null default 'todos' check (convites in ('todos', 'criador')),
  entrada_aberta boolean not null default true
);
-- para projetos criados com a versão anterior deste ficheiro
alter table salas add column if not exists descricao text not null default '';
alter table salas add column if not exists cor text not null default 'terracota';
alter table salas add column if not exists aviso text not null default '';
alter table salas add column if not exists chat_modo text not null default 'todos';
alter table salas add column if not exists quem_publica text not null default 'todos';
alter table salas add column if not exists ficheiros_privados boolean not null default true;
alter table salas add column if not exists assistente_ativo boolean not null default true;
-- Laboratório da sala (opcional): ligado/desligado e as ferramentas escolhidas por quem a criou ("área.ferramenta").
-- Seguro para bases de dados que já existem: as salas antigas ficam sem Laboratório.
alter table salas add column if not exists laboratorio boolean not null default false;
alter table salas add column if not exists ferramentas_lab jsonb not null default '[]'::jsonb;
-- ícone da sala (escolhido por quem a cria; vazio = a app sugere um pelo nome)
alter table salas add column if not exists icone text not null default '';
alter table salas add column if not exists convites text not null default 'todos';
alter table salas add column if not exists entrada_aberta boolean not null default true;
alter table perfis add column if not exists foto_b64 text;

create table if not exists membros (
  sala_id uuid references salas(id) on delete cascade,
  utilizador_id uuid references perfis(id) on delete cascade,
  papel text not null check (papel in ('criador', 'professor', 'aluno')),
  entrou_em timestamptz default now(),
  primary key (sala_id, utilizador_id)
);

create table if not exists ficheiros (
  id uuid primary key default gen_random_uuid(),
  sala_id uuid not null references salas(id) on delete cascade,
  dono_id uuid not null references perfis(id) on delete cascade,
  nome text not null,
  caminho_storage text not null,      -- ficheiro original no Supabase Storage (bucket privado "salas")
  tipo_mime text,
  pasta_fixa boolean not null default false,   -- true = material do professor, visível a todos
  texto_extraido text,                -- texto (ou leitura da fotografia) usado pelo assistente da sala
  enviado_em timestamptz default now()
);

create table if not exists mensagens (
  id bigint generated always as identity primary key,
  sala_id uuid not null references salas(id) on delete cascade,
  autor_id uuid not null references perfis(id) on delete cascade,
  texto text not null check (char_length(texto) between 1 and 4000),
  enviada_em timestamptz default now()
);

-- Funções auxiliares
create or replace function e_membro(p_sala uuid) returns boolean language sql security definer stable as $$
  select exists (select 1 from membros where sala_id = p_sala and utilizador_id = auth.uid());
$$;
create or replace function papel_na_sala(p_sala uuid) returns text language sql security definer stable as $$
  select papel from membros where sala_id = p_sala and utilizador_id = auth.uid();
$$;

-- Entrar numa sala com o código (não expõe a lista de salas a quem não é membro)
create or replace function entrar_com_codigo(p_codigo text) returns uuid language plpgsql security definer as $$
declare v_sala uuid;
begin
  select id into v_sala from salas where codigo = upper(regexp_replace(p_codigo, '[^A-Za-z0-9]', '', 'g'));
  if v_sala is null then raise exception 'Código de sala inválido'; end if;
  if not e_membro(v_sala) and not (select entrada_aberta from salas where id = v_sala) then
    raise exception 'Esta sala não está a aceitar novos membros';
  end if;
  insert into membros (sala_id, utilizador_id, papel)
  values (v_sala, auth.uid(),
          case when (select vinculo from perfis where id = auth.uid()) = 'Professor' then 'professor' else 'aluno' end)
  on conflict do nothing;
  return v_sala;
end; $$;

-- Row Level Security
alter table perfis enable row level security;
alter table salas enable row level security;
alter table membros enable row level security;
alter table ficheiros enable row level security;
alter table mensagens enable row level security;

create policy "perfil: o próprio" on perfis for all using (id = auth.uid()) with check (id = auth.uid());
-- os membros de uma sala veem o nome uns dos outros (para a lista de membros, o chat e os ficheiros)
create policy "perfis: colegas de sala veem o nome" on perfis for select using (
  exists (select 1 from membros a join membros b on a.sala_id = b.sala_id
          where a.utilizador_id = auth.uid() and b.utilizador_id = perfis.id));

create policy "salas: membros veem" on salas for select using (e_membro(id) or criador_id = auth.uid());
create policy "salas: criar" on salas for insert with check (
  criador_id = auth.uid() and (
    (tipo = 'grupo_estudo') or
    (tipo = 'cadeira' and (select vinculo from perfis where id = auth.uid()) = 'Professor')));
create policy "salas: criador edita" on salas for update using (criador_id = auth.uid());
create policy "salas: criador apaga" on salas for delete using (criador_id = auth.uid());

create policy "membros: membros veem" on membros for select using (e_membro(sala_id));
create policy "membros: criador junta-se" on membros for insert with check (
  utilizador_id = auth.uid() and exists (select 1 from salas s where s.id = sala_id and s.criador_id = auth.uid()));
create policy "membros: sair ou o criador remove" on membros for delete using (
  utilizador_id = auth.uid() or exists (select 1 from salas s where s.id = sala_id and s.criador_id = auth.uid()));

-- Ficheiros: o dono vê os seus; todos os membros veem os documentos partilhados (pasta_fixa).
-- Partilhar: o criador sempre; os outros só se a sala o permitir (quem_publica = 'todos').
-- Privados: só se a sala os permitir. Apagar: o dono ou o criador da sala.
create policy "ficheiros: ver" on ficheiros for select using (
  dono_id = auth.uid() or (pasta_fixa and e_membro(sala_id)));
create policy "ficheiros: enviar" on ficheiros for insert with check (
  dono_id = auth.uid() and e_membro(sala_id) and (
    (pasta_fixa and (papel_na_sala(sala_id) = 'criador' or (select quem_publica from salas where id = sala_id) = 'todos')) or
    (not pasta_fixa and (select ficheiros_privados from salas where id = sala_id))));
create policy "ficheiros: dono ou criador apaga" on ficheiros for delete using (
  dono_id = auth.uid() or exists (select 1 from salas s where s.id = sala_id and s.criador_id = auth.uid()));

-- Conversa: desligada, todos escrevem, ou só o criador escreve (avisos)
create policy "mensagens: ver" on mensagens for select using (
  e_membro(sala_id) and (select chat_modo from salas where id = sala_id) <> 'desligado');
create policy "mensagens: escrever" on mensagens for insert with check (
  autor_id = auth.uid() and e_membro(sala_id) and (
    (select chat_modo from salas where id = sala_id) = 'todos' or
    ((select chat_modo from salas where id = sala_id) = 'criador' and papel_na_sala(sala_id) = 'criador')));
create policy "mensagens: autor ou criador apaga" on mensagens for delete using (
  autor_id = auth.uid() or exists (select 1 from salas s where s.id = sala_id and s.criador_id = auth.uid()));

-- Storage: criar um bucket PRIVADO chamado "salas" (Storage → New bucket) e usar caminhos "sala_id/dono_id/nome".
-- Sem estas regras o Supabase recusa o envio e a leitura dos ficheiros das Salas (o bucket privado começa fechado).
drop policy if exists "salas: enviar ficheiros" on storage.objects;
create policy "salas: enviar ficheiros" on storage.objects for insert to authenticated with check (
  bucket_id = 'salas' and (storage.foldername(name))[2] = auth.uid()::text
  and public.e_membro(((storage.foldername(name))[1])::uuid));
drop policy if exists "salas: ver ficheiros" on storage.objects;
create policy "salas: ver ficheiros" on storage.objects for select to authenticated using (
  bucket_id = 'salas' and exists (select 1 from public.ficheiros f where f.caminho_storage = name));
drop policy if exists "salas: o dono apaga" on storage.objects;
create policy "salas: o dono apaga" on storage.objects for delete to authenticated using (
  bucket_id = 'salas' and (storage.foldername(name))[2] = auth.uid()::text);

-- =====================================================================================================
-- 3D Studio (biblioteca de modelos 3D). AINDA NÃO APLICADO/TESTADO. Mesmas regras do modo local (biblioteca3d.py).
-- =====================================================================================================
create table if not exists modelos3d (
  id uuid primary key default gen_random_uuid(),
  dono_id uuid not null references perfis(id) on delete cascade,
  titulo text not null check (char_length(titulo) between 1 and 100),
  descricao text not null default '',
  categoria text not null default 'Outro',
  etiquetas text[] not null default '{}',
  visibilidade text not null default 'privado' check (visibilidade in ('publico', 'privado')),
  permite_remix boolean not null default false,
  licenca text not null default '',
  creditos text not null default '',
  capa_b64 text,
  dados jsonb not null,
  versao_atual int not null default 1,
  origem_id uuid references modelos3d(id) on delete set null,
  origem_titulo text, origem_autor text,
  publicado boolean not null default false,
  criado_em timestamptz default now(), atualizado_em timestamptz default now(), publicado_em timestamptz,
  visualizacoes int not null default 0,
  gostos int not null default 0
);
create table if not exists versoes3d (
  modelo_id uuid references modelos3d(id) on delete cascade, n int not null, dados jsonb not null, nota text,
  anterior int, autor_id uuid references perfis(id), criado_em timestamptz default now(), primary key (modelo_id, n));
create table if not exists gostos3d (modelo_id uuid references modelos3d(id) on delete cascade,
  utilizador_id uuid references perfis(id) on delete cascade, primary key (modelo_id, utilizador_id));
create table if not exists favoritos3d (modelo_id uuid references modelos3d(id) on delete cascade,
  utilizador_id uuid references perfis(id) on delete cascade, primary key (modelo_id, utilizador_id));
create table if not exists partilhas3d (modelo_id uuid references modelos3d(id) on delete cascade,
  utilizador_id uuid references perfis(id) on delete cascade, primary key (modelo_id, utilizador_id));
create table if not exists colecoes3d (id uuid primary key default gen_random_uuid(),
  dono_id uuid not null references perfis(id) on delete cascade, nome text not null, criada_em timestamptz default now());
create table if not exists colecao_itens3d (colecao_id uuid references colecoes3d(id) on delete cascade,
  modelo_id uuid references modelos3d(id) on delete cascade, primary key (colecao_id, modelo_id));
create table if not exists glb3d (id uuid primary key default gen_random_uuid(),
  dono_id uuid not null references perfis(id) on delete cascade, nome text, dados_b64 text not null,
  criado_em timestamptz default now());

create or replace function pode_ver_modelo3d(p uuid) returns boolean language sql security definer stable as $$
  select exists (select 1 from modelos3d m where m.id = p and (
    (m.publicado and m.visibilidade = 'publico') or m.dono_id = auth.uid()
    or exists (select 1 from partilhas3d s where s.modelo_id = m.id and s.utilizador_id = auth.uid())));
$$;
-- contador de gostos sempre certo
create or replace function contar_gostos3d() returns trigger language plpgsql security definer as $$
begin
  update modelos3d set gostos = (select count(*) from gostos3d where modelo_id = coalesce(new.modelo_id, old.modelo_id))
   where id = coalesce(new.modelo_id, old.modelo_id);
  return null;
end; $$;
drop trigger if exists gostos3d_contar on gostos3d;
create trigger gostos3d_contar after insert or delete on gostos3d for each row execute function contar_gostos3d();
create or replace function ver_modelo3d(p_modelo uuid) returns void language sql security definer as $$
  update modelos3d set visualizacoes = visualizacoes + 1 where id = p_modelo and pode_ver_modelo3d(p_modelo);
$$;
create or replace function partilhar_modelo3d(p_modelo uuid, p_email text) returns text language plpgsql security definer as $$
declare v_uid uuid; v_nome text;
begin
  if not exists (select 1 from modelos3d where id = p_modelo and dono_id = auth.uid()) then
    raise exception 'Só o dono pode partilhar este modelo'; end if;
  select u.id, p.nome_completo into v_uid, v_nome from auth.users u join perfis p on p.id = u.id where lower(u.email) = lower(p_email);
  if v_uid is null then raise exception 'Não há nenhuma conta com esse email'; end if;
  insert into partilhas3d values (p_modelo, v_uid) on conflict do nothing;
  return v_nome;
end; $$;

alter table modelos3d enable row level security;
alter table versoes3d enable row level security;
alter table gostos3d enable row level security;
alter table favoritos3d enable row level security;
alter table partilhas3d enable row level security;
alter table colecoes3d enable row level security;
alter table colecao_itens3d enable row level security;
alter table glb3d enable row level security;

create policy "modelos3d: ver" on modelos3d for select using (pode_ver_modelo3d(id));
create policy "modelos3d: criar" on modelos3d for insert with check (dono_id = auth.uid());
create policy "modelos3d: dono altera" on modelos3d for update using (dono_id = auth.uid());
create policy "modelos3d: dono apaga" on modelos3d for delete using (dono_id = auth.uid());
create policy "versoes3d: dono" on versoes3d for all using (exists (select 1 from modelos3d m where m.id = modelo_id and m.dono_id = auth.uid()))
  with check (exists (select 1 from modelos3d m where m.id = modelo_id and m.dono_id = auth.uid()));
create policy "gostos3d: ver" on gostos3d for select using (pode_ver_modelo3d(modelo_id));
create policy "gostos3d: o próprio" on gostos3d for insert with check (utilizador_id = auth.uid() and pode_ver_modelo3d(modelo_id));
create policy "gostos3d: retirar" on gostos3d for delete using (utilizador_id = auth.uid());
create policy "favoritos3d: o próprio" on favoritos3d for all using (utilizador_id = auth.uid()) with check (utilizador_id = auth.uid());
create policy "partilhas3d: dono e convidado veem" on partilhas3d for select using (utilizador_id = auth.uid()
  or exists (select 1 from modelos3d m where m.id = modelo_id and m.dono_id = auth.uid()));
create policy "partilhas3d: dono retira" on partilhas3d for delete using (exists (select 1 from modelos3d m where m.id = modelo_id and m.dono_id = auth.uid()));
create policy "colecoes3d: dono" on colecoes3d for all using (dono_id = auth.uid()) with check (dono_id = auth.uid());
create policy "colecao_itens3d: dono" on colecao_itens3d for all
  using (exists (select 1 from colecoes3d c where c.id = colecao_id and c.dono_id = auth.uid()))
  with check (exists (select 1 from colecoes3d c where c.id = colecao_id and c.dono_id = auth.uid()) and pode_ver_modelo3d(modelo_id));
create policy "glb3d: dono ou quem vê o modelo" on glb3d for select using (dono_id = auth.uid()
  or exists (select 1 from modelos3d m where (m.dados->'glb'->>'id' = glb3d.id::text
                                             or m.dados->'blender'->>'id' = glb3d.id::text) and pode_ver_modelo3d(m.id)));
create policy "glb3d: dono envia" on glb3d for insert with check (dono_id = auth.uid());

-- ======================================================================================================
-- Fase 3: dados de estudo de cada pessoa (para publicar a app sem perder nada quando o servidor reinicia)
-- Perfil, cadeiras (com o texto das fontes), avaliações e conversas, guardados como JSON por conta.
-- Cada pessoa só lê e escreve os seus (RLS). Pode correr-se outra vez sem estragar nada.
-- ======================================================================================================
create table if not exists dados_utilizador (
  uid uuid not null references auth.users(id) on delete cascade,
  chave text not null check (char_length(chave) between 1 and 300),   -- ex.: perfil.json, dados/algebra.json
  valor jsonb not null,
  atualizado timestamptz not null default now(),
  primary key (uid, chave)
);
alter table dados_utilizador enable row level security;
drop policy if exists "dados: só o próprio" on dados_utilizador;
create policy "dados: só o próprio" on dados_utilizador for all
  using (uid = auth.uid()) with check (uid = auth.uid());

-- Apagar a minha conta (RGPD): apaga a conta e, em cascata, os dados, o perfil e as salas que criou.
create or replace function apagar_a_minha_conta() returns void
language sql security definer set search_path = public as $$
  delete from auth.users where id = auth.uid();
$$;
revoke all on function apagar_a_minha_conta() from public, anon;
grant execute on function apagar_a_minha_conta() to authenticated;
