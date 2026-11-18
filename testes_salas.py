"""Testes das Salas em modo local (SQLite numa pasta temporária). Correr com:  py -3.14 testes_salas.py"""
import sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from salas_backend import BackendLocal, ErroSalas

pasta = Path(tempfile.mkdtemp(prefix="teste_salas_")); db = pasta / "salas.sqlite"
res = []
def ok(n, c): res.append(bool(c)); print(("PASSOU " if c else "FALHOU ") + n)
def erro(f):
    try: f(); return None
    except ErroSalas as e: return str(e)

prof_s, ana_s, rui_s = {}, {}, {}
prof = BackendLocal(db, prof_s); ana = BackendLocal(db, ana_s); rui = BackendLocal(db, rui_s)
ok("Validação do registo (email, palavra-passe curta)", erro(lambda: prof.registar("x", "12345678", "P", "Professor"))
   and erro(lambda: prof.registar("p@uc.pt", "123", "Prof", "Professor")))
prof.registar("prof@uc.pt", "segredo123", "Prof. Sousa", "Professor")
ana.registar("ana@uc.pt", "segredo123", "Ana", "Aluno"); rui.registar("rui@uc.pt", "segredo123", "Rui", "Aluno")
ok("Email repetido é recusado", "Já existe" in (erro(lambda: BackendLocal(db, {}).registar("ana@uc.pt", "segredo123", "Ana2", "Aluno")) or ""))
ok("Entrar com palavra-passe errada falha; certa funciona", erro(lambda: BackendLocal(db, {}).entrar("ana@uc.pt", "errada!!"))
   and BackendLocal(db, {}).entrar("ANA@uc.pt ", "segredo123")["nome"] == "Ana")
sala = prof.criar_sala("Álgebra Linear – T1", chat_ativo=True, cadeira="Álgebra Linear")
ok("Professor cria sala de cadeira com código", sala["tipo"] == "cadeira" and len(sala["codigo"]) == 6 and sala["papel"] == "criador")
grupo = ana.criar_sala("Grupo de estudo", chat_ativo=False, cadeira="X")
ok("Aluno cria grupo de estudo (sem cadeira)", grupo["tipo"] == "grupo_estudo" and grupo["cadeira"] is None)
ok("Quem não é membro não vê a sala", erro(lambda: rui.obter_sala(sala["id"])))
ana.entrar_com_codigo(sala["codigo"].lower()); rui.entrar_com_codigo(" " + sala["codigo"] + " ")
ok("Entrar com código (aceita minúsculas e espaços); código errado falha",
   len(prof.membros(sala["id"])) == 3 and erro(lambda: rui.entrar_com_codigo("ZZZZZZ")))
ok("Entrar duas vezes não duplica", (ana.entrar_com_codigo(sala["codigo"]), len(prof.membros(sala["id"])))[1] == 3)
prof.enviar_ficheiro(sala["id"], "teoria.pdf", b"%PDF", "application/pdf", True, "Matrizes e determinantes")
ana.enviar_ficheiro(sala["id"], "notas.jpg", b"img", "image/jpeg", False, "Apontamentos da Ana")
ok("Sala de cadeira (por omissão): só o criador põe documentos nos materiais", erro(lambda: ana.enviar_ficheiro(sala["id"], "x.pdf", b"", "", True, "")))
ok("Pasta do professor: todos veem; ficheiro da Ana: só ela",
   [f["nome"] for f in rui.ficheiros(sala["id"])] == ["teoria.pdf"]
   and sorted(f["nome"] for f in ana.ficheiros(sala["id"])) == ["notas.jpg", "teoria.pdf"]
   and [f["nome"] for f in prof.ficheiros(sala["id"])] == ["teoria.pdf"])
fid = [f for f in ana.ficheiros(sala["id"]) if f["nome"] == "notas.jpg"][0]["id"]
ok("Só o dono apaga o ficheiro", erro(lambda: rui.apagar_ficheiro(fid)) and (ana.apagar_ficheiro(fid) is None))
prof.atualizar_sala(sala["id"], chat_modo="todos")
ana.enviar_mensagem(sala["id"], "Olá a todos!"); prof.enviar_mensagem(sala["id"], "Bem-vindos.")
ok("Conversa entre membros com histórico", [m["texto"] for m in rui.mensagens(sala["id"])] == ["Olá a todos!", "Bem-vindos."]
   and rui.mensagens(sala["id"])[0]["autor_nome"] == "Ana")
ok("Sem conversa ativa não se escreve", "não tem conversa" in (erro(lambda: ana.enviar_mensagem(grupo["id"], "oi")) or ""))
ok("Só o criador altera a sala", erro(lambda: ana.atualizar_sala(sala["id"], chat_ativo=False))
   and prof.atualizar_sala(sala["id"], nome="Álgebra T1", chat_ativo=False)["chat_ativo"] is False
   and ana.mensagens(sala["id"]) == [])
rui.sair_da_sala(sala["id"])
ok("Sair da sala", len(prof.membros(sala["id"])) == 2 and erro(lambda: rui.ficheiros(sala["id"])))
ok("Dados persistem (nova ligação ao ficheiro)", len(BackendLocal(db, dict(prof_s)).minhas_salas()) == 1)
# ---------------------------------------------------------------- definições do criador (salas reformuladas)
s2 = prof.criar_sala("Física I", cadeira="Física", descricao="Aulas práticas", cor="verde", chat_modo="criador",
                     quem_publica="criador", ficheiros_privados=False, convites="criador")
ok("Criar sala com as definições escolhidas (descrição, cor, conversa só do criador, documentos só do criador...)",
   s2["descricao"] == "Aulas práticas" and s2["cor"] == "verde" and s2["chat_modo"] == "criador" and not s2["ficheiros_privados"]
   and s2["e_criador"])
ana.entrar_com_codigo(s2["codigo"])
s2a = ana.obter_sala(s2["id"])
ok("Convites «só eu»: os membros não veem o código da sala", s2a["codigo"] is None and not s2a["e_criador"])
ok("Conversa «só eu escrevo»: os membros leem mas não escrevem; o criador escreve",
   "só quem a criou" in (erro(lambda: ana.enviar_mensagem(s2["id"], "posso?")) or "")
   and prof.enviar_mensagem(s2["id"], "Teste na sexta.") is None and len(ana.mensagens(s2["id"])) == 1)
ok("Sem ficheiros privados nesta sala", "não tem ficheiros privados" in (erro(lambda: ana.enviar_ficheiro(s2["id"], "a.txt", b"a", "", False, "a")) or ""))
ok("Só o criador configura (os membros não)", "Só quem criou" in (erro(lambda: ana.atualizar_sala(s2["id"], quem_publica="todos")) or ""))
prof.atualizar_sala(s2["id"], quem_publica="todos", chat_modo="todos", ficheiros_privados=True, aviso="Teste na sexta!")
f_ana = ana.enviar_ficheiro(s2["id"], "resumo.pdf", b"%PDF", "application/pdf", True, "Resumo da Ana")
ok("O criador abre a partilha a todos: a Ana partilha um documento e todos o veem; aviso fixo guardado",
   [f["nome"] for f in prof.ficheiros(s2["id"])] == ["resumo.pdf"] and ana.obter_sala(s2["id"])["aviso"] == "Teste na sexta!")
ok("O criador modera: apaga documentos e mensagens de outros", prof.ficheiros(s2["id"])[0]["pode_apagar"]
   and prof.apagar_ficheiro(f_ana["id"]) is None and ana.ficheiros(s2["id"]) == []
   and (ana.enviar_mensagem(s2["id"], "oi"), prof.apagar_mensagem(ana.mensagens(s2["id"])[-1]["id"]), len(ana.mensagens(s2["id"])))[2] == 1)
ok("Definições inválidas são recusadas", "desconhecid" in (erro(lambda: prof.atualizar_sala(s2["id"], chat_modo="xpto")) or ""))
codigo_antigo = s2["codigo"]; novo_c = prof.novo_codigo(s2["id"])
ok("Novo código: o antigo deixa de funcionar", novo_c != codigo_antigo and erro(lambda: rui.entrar_com_codigo(codigo_antigo)))
prof.atualizar_sala(s2["id"], entrada_aberta=False)
ok("Sala fechada a novos membros", "não está a aceitar" in (erro(lambda: rui.entrar_com_codigo(novo_c)) or ""))
prof.atualizar_sala(s2["id"], entrada_aberta=True); rui.entrar_com_codigo(novo_c)
prof.remover_membro(s2["id"], rui.atual()["id"])
ok("O criador remove um membro (e não se pode remover a si próprio)", erro(lambda: rui.obter_sala(s2["id"]))
   and erro(lambda: prof.remover_membro(s2["id"], prof.atual()["id"])) and erro(lambda: ana.remover_membro(s2["id"], prof.atual()["id"])))
u = ana.mudar_perfil(nome="Ana Sousa", foto=b"\xff\xd8foto")
ok("Mudar nome e fotografia da conta (os colegas veem nos membros)", u["nome"] == "Ana Sousa"
   and [m for m in prof.membros(s2["id"]) if m["nome"] == "Ana Sousa"][0]["foto"] == b"\xff\xd8foto"
   and ana.mudar_perfil(apagar_foto=True)["foto"] is None)
v = ana.mudar_vinculo("Professor")
turma_t = ana.criar_sala("Turma de teste")
ok("Aluno ou professor escolhido na primeira entrada passa para a conta (e decide o tipo de sala que cria)",
   v["vinculo"] == "Professor" and turma_t["tipo"] == "cadeira"
   and ana.mudar_vinculo("Aluno")["vinculo"] == "Aluno" and erro(lambda: ana.mudar_vinculo("Diretor")))
ana.apagar_sala(turma_t["id"])
prof.apagar_sala(s2["id"])
prof.apagar_sala(sala["id"])
ok("Apagar sala apaga membros, ficheiros e mensagens", ana.minhas_salas()[0]["id"] == grupo["id"] and len(ana.minhas_salas()) == 1)
shutil.rmtree(pasta, ignore_errors=True)
# entrada com conta externa (Google/Facebook): liga à conta local com o mesmo email
import tempfile as _tf
_b = BackendLocal(Path(_tf.mkdtemp()) / "x.sqlite", {})
_u = _b.entrar_externo("Ana@Gmail.com", "Ana Sousa", "Aluno")
_b.sair()
_u2 = _b.entrar_externo("ana@gmail.com", "Outro Nome")
ok("Conta externa: cria a conta local uma vez e volta a usá-la (sem palavra-passe conhecida)", _u["id"] == _u2["id"]
   and _u2["nome"] == "Ana Sousa" and _u["email"] == "ana@gmail.com")
try:
    _b.entrar("ana@gmail.com", "")
    ok("A conta criada por Google não aceita palavra-passe vazia", False)
except ErroSalas:
    ok("A conta criada por Google não aceita palavra-passe vazia", True)
ok("Existe: diz se já há conta com o email (sem ligar a maiúsculas nem espaços)",
   _b.existe(" ANA@gmail.com ") and not _b.existe("outra@gmail.com") and not _b.existe(""))
_b.entrar_externo("ana@gmail.com", "Ana Sousa"); _b.apagar_conta()
ok("Apagar a conta: a conta desaparece e a sessão termina", not _b.existe("ana@gmail.com") and _b.atual() is None)
# ---------------------------------------------------------------- Laboratório da sala
import salas as _sl
pasta = Path(tempfile.mkdtemp(prefix="teste_salas_lab_"))
_db_lab = pasta / "lab.sqlite"
_p = BackendLocal(_db_lab, {}); _p.registar("prof.lab@uc.pt", "segredo123", "Prof. Lab", "Professor")
_a = BackendLocal(_db_lab, {}); _a.registar("ana.lab@uc.pt", "segredo123", "Ana Lab", "Aluno")
s_sem = _p.criar_sala("Sem laboratório")
ok("Laboratório: por omissão a sala não tem Laboratório", s_sem["laboratorio"] is False and s_sem["ferramentas_lab"] == [])
s_lab = _p.criar_sala("História 12.º A", laboratorio=True,
                      ferramentas_lab=["historia.cronologia", "biologia.genetica", "historia.explicar", "historia.explicar"])
ok("Laboratório: guarda só as ferramentas escolhidas, sem repetidas e pela ordem do catálogo",
   s_lab["laboratorio"] is True and s_lab["ferramentas_lab"] == ["historia.explicar", "historia.cronologia", "biologia.genetica"])
ok("Laboratório: as ferramentas têm de existir na app e tem de haver pelo menos uma",
   "desconhecida" in (erro(lambda: _p.criar_sala("X1", laboratorio=True, ferramentas_lab=["historia.inventada"])) or "")
   and "pelo menos uma" in (erro(lambda: _p.criar_sala("X2", laboratorio=True, ferramentas_lab=[])) or ""))
_a.entrar_com_codigo(s_lab["codigo"])
ok("Laboratório: as definições ficam guardadas e os membros veem as mesmas ferramentas (também depois de reabrir)",
   BackendLocal(_db_lab, {"uid": _a.sessao["uid"]}).obter_sala(s_lab["id"])["ferramentas_lab"]
   == ["historia.explicar", "historia.cronologia", "biologia.genetica"])
ok("Laboratório: só quem criou a sala o muda", "Só quem criou" in (erro(lambda: _a.atualizar_sala(s_lab["id"], laboratorio=False)) or ""))
_p.atualizar_sala(s_lab["id"], laboratorio=False)
ok("Laboratório: desligar deixa a sala sem Laboratório (as escolhas ficam para se voltar a ligar)",
   _p.obter_sala(s_lab["id"])["laboratorio"] is False and _p.obter_sala(s_lab["id"])["ferramentas_lab"])
ok("Laboratório: catálogo por área com as ferramentas reais da app (História, Biologia, Química, Física, Matemática, "
   "Programação)", list(_sl.ferramentas_por_area(_sl.FERRAMENTAS_LAB)) == ["historia", "biologia", "quimica", "fisica",
                                                                          "matematica", "programacao"]
   and _sl.nome_ferramenta("quimica.tabela") == "Tabela periódica")
import sqlite3 as _sq3
_antiga = pasta / "antiga.sqlite"
_c = _sq3.connect(_antiga); _c.executescript("""
create table utilizadores (id text primary key, email text unique not null, nome text not null, vinculo text not null,
  sal blob not null, hash blob not null, criado_em text);
create table salas (id text primary key, nome text not null, tipo text not null, cadeira text, criador_id text not null,
  codigo text unique not null, chat_ativo integer not null default 0, criada_em text);
insert into utilizadores values ('u1', 'velho@uc.pt', 'Velho', 'Aluno', x'00', x'00', '2026-01-01');
insert into salas values ('s1', 'Sala antiga', 'grupo_estudo', null, 'u1', 'ABCDEF', 1, '2026-01-01');
create table membros (sala_id text, utilizador_id text, papel text not null, entrou_em text, primary key (sala_id, utilizador_id));
insert into membros values ('s1', 'u1', 'criador', '2026-01-01');
"""); _c.commit(); _c.close()
_v = BackendLocal(_antiga, {"uid": "u1"}).obter_sala("s1")
ok("Migração: salas de versões antigas abrem sem Laboratório e com a conversa como estava",
   _v["laboratorio"] is False and _v["ferramentas_lab"] == [] and _v["chat_modo"] == "todos")
ok("Migração: salas antigas ganham a coluna do ícone (vazio: a app sugere um pelo nome)",
   _v.get("icone", "") == "" and _sl.icone_da_sala(_v) == "groups")
# ---------------------------------------------------------------- ícone da sala
ok("Ícone: sugerido pelo nome, sem contar acentos (Álgebra → funções, Química → frasco, Programação → código, "
   "estudos → escola; a matéria ganha às palavras genéricas)",
   _sl.icone_sugerido("Grupo de Álgebra") == "matematica" and _sl.icone_sugerido("Laboratório de Química") == "quimica"
   and _sl.icone_sugerido("Programação I") == "programacao" and _sl.icone_sugerido("estudos") == "estudo"
   and _sl.icone_sugerido("Revisões de Física") == "fisica" and _sl.icone_sugerido("Amigos") == "grupo"
   and _sl.icone_sugerido("Turma 2", cadeira="Física Geral", tipo="cadeira") == "fisica"
   and _sl.icone_sugerido("Turma 2", tipo="cadeira") == "leitura")
try:
    _sl.validar_definicoes({"icone": "foguetao"}, _sl.definicoes_padrao("grupo_estudo")); _rec = ""
except _sl.ErroDefinicoes as _e:
    _rec = str(_e)
ok("Ícone: só os do catálogo; vazio quer dizer «automático»", "desconhecido" in _rec
   and _sl.validar_definicoes({"icone": ""}, _sl.definicoes_padrao("grupo_estudo"))["icone"] == "")
_si = _p.criar_sala("Sala com ícone", icone="musica")
ok("Ícone: escolhido ao criar fica guardado e mostra-se", _p.obter_sala(_si["id"])["icone"] == "musica"
   and _sl.icone_da_sala(_p.obter_sala(_si["id"])) == "music_note")
_p.atualizar_sala(_si["id"], icone="")
ok("Ícone: mudar para «automático» volta ao sugerido pelo nome", _p.obter_sala(_si["id"])["icone"] == ""
   and _sl.icone_da_sala(_p.obter_sala(_si["id"])) == "menu_book")  # sala de professor (tipo cadeira): livro
# Supabase com o esquema antigo (sem a coluna «icone»): a sala é guardada na mesma, sem o ícone
import salas_backend as _sbk
class _SemColuna(_sbk.BackendSupabase):
    def __init__(s): s.enviados = []
    def _pedido(s, metodo, caminho, **kw):
        s.enviados.append(dict(kw.get("json") or {}))
        if "icone" in (kw.get("json") or {}):
            raise ErroSalas("O servidor recusou o pedido: Could not find the 'icone' column of 'salas' in the schema cache")
        return [{"id": "x"}]
_f = _SemColuna()
_f._com_icone("PATCH", "/rest/v1/salas?id=eq.x", {"nome": "A", "icone": "musica"})
_f._com_icone("PATCH", "/rest/v1/salas?id=eq.x", {"nome": "B", "icone": "musica"})
ok("Supabase sem a coluna «icone» (esquema antigo): volta a enviar sem ela e não volta a tentar",
   [("icone" in e) for e in _f.enviados] == [True, False, False])
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
shutil.rmtree(pasta, ignore_errors=True)
