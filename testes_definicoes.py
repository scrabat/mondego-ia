"""Testes das Definições (py -3.14 testes_definicoes.py): preferências, pesquisa, CSS de acessibilidade, indicações para
a IA, avisos, resumo do cronómetro, palavra-passe e sessões noutros dispositivos. Não precisam de internet."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "supabase"))
import servidor_falso as falso  # noqa: E402

SRV = falso.Servidor()
sys.modules["httpx"] = falso.modulo_httpx(SRV)
import definicoes as dfs  # noqa: E402
import inicio_sessao as isess  # noqa: E402
import salas_backend as sb  # noqa: E402

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


# ---------------------------------------------------------------- preferências
ok("Preferências: sem nada guardado ficam os valores por omissão (avisos ligados, 7 dias de antecedência)",
   dfs.limpar(None) == {**dfs.PADRAO, "avisos": dfs.AVISOS_PADRAO} and dfs.alteradas({}) == [])
sujo = dfs.limpar({"texto": "Gigante", "contraste": "sim", "movimento": "Reduzido", "ia_tamanho": "Curtas", "voz_alta": False,
                   "avisos": {"dias": 5, "salas": False, "ativos": "x"}, "lixo": 1})
ok("Preferências: valores estragados voltam ao normal, os válidos ficam e o que não existe sai",
   sujo["texto"] == "Normal" and sujo["contraste"] is False and sujo["movimento"] == "Reduzido" and sujo["ia_tamanho"] == "Curtas"
   and sujo["voz_alta"] is False and sujo["avisos"]["dias"] == 7 and sujo["avisos"]["salas"] is False
   and sujo["avisos"]["ativos"] is True and "lixo" not in sujo)
ok("Preferências: «alteradas» diz o que não está por omissão",
   set(dfs.alteradas(sujo)) == {"movimento", "ia_tamanho", "voz_alta", "avisos"})
ok("Há oito categorias, com título, ícone e descrição, e todas as opções do índice pertencem a uma delas",
   len(dfs.CATEGORIAS) == 8 and all(len(c) == 4 and all(c) for c in dfs.CATEGORIAS)
   and {i[0] for i in dfs.INDICE} == set(dfs.TITULOS))

# ---------------------------------------------------------------- pesquisa
ok("Pesquisa: encontra pela palavra, sem contar acentos nem maiúsculas",
   ("conta", "Palavra-passe") in dfs.procurar("PASSWORD") and ("acessibilidade", "Contraste alto") in dfs.procurar("contraste")
   and ("notificacoes", "Avaliações próximas") in dfs.procurar("avaliacoes"))
ok("Pesquisa: várias palavras têm de aparecer todas; sem resultados devolve vazio; uma letra não conta",
   dfs.procurar("tema escuro")[0] == ("personalizacao", "Tema claro, escuro ou do sistema")
   and dfs.procurar("xyzzy") == [] and dfs.procurar("a") == [])
ok("Pesquisa: também procura nas perguntas frequentes",
   any(c == "ajuda" and "cronómetro" in t for c, t in dfs.procurar("cronometro")))

# ---------------------------------------------------------------- CSS
ok("CSS: com tudo por omissão não muda nada", dfs.css_preferencias({}) == "<style></style>")
css = dfs.css_preferencias({"texto": "Grande", "contraste": True, "leitura": True, "foco": True, "movimento": "Reduzido"}, "Escuro")
ok("CSS: texto maior, contraste do tema escuro, leitura, foco do teclado e menos movimento",
   "font-size:17.5px" in css and "--texto:#FFFFFF" in css and "line-height:1.8" in css and ":focus-visible" in css
   and "animation-duration:0.01ms" in css and css.startswith("<style>") and css.endswith("</style>"))
auto = dfs.css_preferencias({"contraste": True}, "Automático")
ok("CSS: no tema automático o contraste segue o sistema (claro e escuro)",
   "--texto:#0A1216" in auto and "prefers-color-scheme: dark" in auto and "--texto:#FFFFFF" in auto
   and "--texto:#FFFFFF" not in dfs.css_preferencias({"contraste": True}, "Claro"))

# ---------------------------------------------------------------- IA
ok("IA: por omissão não acrescenta nada às instruções", dfs.instrucoes_ia({}) == "" and dfs.instrucoes_ia(None, voz=True) == "")
txt = dfs.instrucoes_ia({"ia_tamanho": "Curtas", "ia_nivel": "Simples", "ia_tom": "Neutro"})
ok("IA: tamanho, nível e tom viram indicações claras (na voz, respostas ainda mais curtas)",
   "PREFERÊNCIAS DO ALUNO" in txt and "curtas e diretas" in txt and "forma simples" in txt and "tom neutro" in txt
   and "uma a três frases" in dfs.instrucoes_ia({"ia_tamanho": "Curtas"}, voz=True)
   and "rigor técnico" in dfs.instrucoes_ia({"ia_nivel": "Avançado"}))

# ---------------------------------------------------------------- avisos
hoje = date(2026, 11, 12)
prox = [{"id": "a1", "nome": "Teste 1", "cadeira": "Álgebra", "data": "2026-11-13", "hora": "10:00"},
        {"id": "a2", "nome": "Exame", "cadeira": "Análise", "data": "2026-11-18", "hora": None},
        {"id": "a3", "nome": "Projeto", "cadeira": "Programação", "data": "2026-12-20"}]
lista = dfs.avisos(hoje, {}, prox, tarefas_hoje=(1, 4), atrasadas=2, cartoes=12, cartoes_cadeira="Álgebra",
                   temas_fracos=[("Álgebra", "Determinantes")], salas_novas=[("s1", "Grupo de Álgebra", 3)])
ok("Avisos: avaliações dentro da antecedência (7 dias), a de amanhã primeiro e marcada como urgente",
   [x["tipo"] for x in lista][:2] == ["avaliacoes", "avaliacoes"] and lista[0]["titulo"] == "Teste 1 é amanhã"
   and lista[0]["urgente"] and "sexta-feira, 13 de novembro às 10:00" in lista[0]["texto"]
   and not any("Projeto" in x["titulo"] for x in lista))
ok("Avisos: tarefas por fazer, plano de hoje, flashcards, salas e temas a rever, cada um com destino",
   {x["tipo"] for x in lista} == {"avaliacoes", "tarefas", "estudo", "cartoes", "salas", "revisao"}
   and next(x for x in lista if x["tipo"] == "tarefas")["titulo"] == "2 tarefas ficaram por fazer"
   and next(x for x in lista if x["tipo"] == "estudo")["titulo"] == "Faltam 3 tarefas do plano de hoje"
   and next(x for x in lista if x["tipo"] == "salas")["destino"] == ("sala", "s1")
   and next(x for x in lista if x["tipo"] == "cartoes")["destino"] == ("cartoes", "Álgebra"))
so_av = dfs.avisos(hoje, {"avisos": {"tarefas": False, "estudo": False, "cartoes": False, "salas": False, "revisao": False,
                                     "dias": 1}}, prox, (0, 4), 2, 12, "Álgebra", [("Álgebra", "X")], [("s1", "G", 3)])
ok("Avisos: cada tipo desliga-se nas Definições e a antecedência é respeitada",
   [x["tipo"] for x in so_av] == ["avaliacoes"] and len(so_av) == 1)
ok("Avisos: desligados de todo não aparece nada", dfs.avisos(hoje, {"avisos": {"ativos": False}}, prox, (0, 4), 2, 12) == [])
visto = {lista[0]["id"]: hoje.isoformat(), lista[1]["id"]: (hoje - timedelta(days=1)).isoformat()}
depois = dfs.avisos(hoje, {}, prox, (1, 4), 2, 12, "Álgebra", [("Álgebra", "Determinantes")], [("s1", "Grupo de Álgebra", 3)], visto)
ok("Avisos: o que foi dispensado hoje não volta hoje; o dispensado ontem volta",
   lista[0]["id"] not in [x["id"] for x in depois] and lista[1]["id"] in [x["id"] for x in depois]
   and dfs.limpar_vistos(visto, hoje) == {lista[0]["id"]: hoje.isoformat()})
ok("Avisos: plano de hoje todo feito ou sem tarefas não gera lembrete",
   not any(x["tipo"] == "estudo" for x in dfs.avisos(hoje, {}, [], (4, 4))) and dfs.avisos(hoje, {}, [], (0, 0)) == [])
msgs = [{"autor_id": "eu", "enviada_em": "2026-11-12T10:00:00"}, {"autor_id": "rui", "enviada_em": "2026-11-12T11:00:00"},
        {"autor_id": "rui", "enviada_em": "2026-11-10T09:00:00"}]
ok("Salas: só contam mensagens de outras pessoas depois da última visita (sem visita, nenhuma)",
   dfs.mensagens_novas(msgs, "2026-11-11T00:00:00", "eu") == 1 and dfs.mensagens_novas(msgs, None, "eu") == 0)

# ---------------------------------------------------------------- cronómetro
foco = [{"data": "2026-11-12", "minutos": 25, "cadeira": "Álgebra"}, {"data": "2026-11-12", "minutos": 50, "cadeira": None},
        {"data": "2026-11-11", "minutos": 30, "cadeira": "Álgebra"}, {"data": "2026-11-10", "minutos": 10, "cadeira": "Física"},
        {"data": "2026-11-01", "minutos": 99, "cadeira": "Física"}, {"data": "lixo", "minutos": 5}]
rf = dfs.resumo_foco(foco, hoje)
ok("Cronómetro: minutos e sessões de hoje, semana, dias seguidos e minutos por cadeira",
   rf == {"hoje": 75, "sessoes_hoje": 2, "semana": 115, "seguidos": 3,
          "por_cadeira": {"Álgebra": 55, "Sem sala": 50, "Física": 10}})
ok("Cronómetro: sem foco hoje, a sequência conta até ontem; sem dados, tudo a zero",
   dfs.resumo_foco(foco[2:], hoje)["seguidos"] == 2 and dfs.resumo_foco([], hoje)["semana"] == 0)

# ---------------------------------------------------------------- palavra-passe (conta neste computador)
ok("Palavra-passe: pelo menos 8 caracteres, as duas iguais e diferente da atual",
   dfs.validar_palavra_passe("curta", "curta") and dfs.validar_palavra_passe("comprida-1", "comprida-2")
   and dfs.validar_palavra_passe("igual-igual", "igual-igual", "igual-igual")
   and dfs.validar_palavra_passe("nova-palavra", "nova-palavra", "antiga-palavra") is None)
pasta = Path(tempfile.mkdtemp())
local = sb.BackendLocal(pasta / "salas.sqlite", {})
local.registar("ana@mondego.local", "primeira-palavra", "Ana Teste", "Aluno")
try:
    local.mudar_palavra_passe("errada", "segunda-palavra")
    recusou = False
except sb.ErroSalas as e:
    recusou = "atual" in str(e)
try:
    local.mudar_palavra_passe("primeira-palavra", "curta")
    curta = False
except sb.ErroSalas:
    curta = True
local.mudar_palavra_passe("primeira-palavra", "segunda-palavra")
outro = sb.BackendLocal(pasta / "salas.sqlite", {})
try:
    outro.entrar("ana@mondego.local", "primeira-palavra")
    antiga = True
except sb.ErroSalas:
    antiga = False
ok("Conta local: recusa a atual errada e a nova curta; depois de mudar só entra a nova",
   recusou and curta and not antiga and outro.entrar("ana@mondego.local", "segunda-palavra")["email"] == "ana@mondego.local")

# ---------------------------------------------------------------- palavra-passe (Supabase simulado)
nuvem = sb.BackendSupabase(SRV.url, SRV.chave, {})
nuvem.registar("rita@uc.pt", "segredo-da-rita", "Rita Nuvem", "Aluno")
try:
    nuvem.mudar_palavra_passe("nao-e-esta", "nova-da-rita-1")
    recusou_n = False
except sb.ErroSalas as e:
    recusou_n = "atual" in str(e)
nuvem.mudar_palavra_passe("segredo-da-rita", "nova-da-rita-1")
uid_r = nuvem.sessao["uid"]
ok("Supabase (simulado): confirma a atual, muda com PUT /auth/v1/user e a sessão continua aberta",
   recusou_n and SRV.utilizadores[uid_r]["password"] == "nova-da-rita-1" and nuvem.atual()["email"] == "rita@uc.pt"
   and any(m == "PUT" and c.startswith("/auth/v1/user") for m, c in SRV.pedidos)
   and sb.BackendSupabase(SRV.url, SRV.chave, {}).entrar("rita@uc.pt", "nova-da-rita-1")["email"] == "rita@uc.pt")
ok("Supabase (simulado): a mudança usa a sessão acabada de criar (serve quando o projeto pede um início de sessão "
   "recente) e essa sessão temporária termina logo; a da pessoa continua válida",
   nuvem.sessao["access_token"] in SRV.acessos
   and sum(1 for t, u in SRV.acessos.items() if u[0] == uid_r and t != nuvem.sessao["access_token"]) == 1  # só a do «entrar» acima
   and any(m == "POST" and c.startswith("/auth/v1/logout") for m, c in SRV.pedidos))

# ---------------------------------------------------------------- sessões noutros dispositivos
lembradas = isess.SessoesLembradas(pasta / "sessoes.sqlite")
t1 = lembradas.criar({"backend": "local", "uid": "u1"})
t2 = lembradas.criar({"backend": "local", "uid": "u1"})
t3 = lembradas.criar({"backend": "local", "uid": "u2"})
ok("Sessões: conta os dispositivos desta conta e termina os outros sem tocar no atual nem nas outras contas",
   lembradas.contar("u1") == 2 and lembradas.contar("") == 0 and lembradas.apagar_outras("u1", t1) == 1
   and lembradas.contar("u1") == 1 and lembradas.obter(t1) and lembradas.obter(t2) is None and lembradas.obter(t3))

ok("Página inicial «Cadeiras» (de antes) passa a «Salas» (as cadeiras passaram a ser salas)",
   dfs.limpar({"pagina_inicial": "Cadeiras"})["pagina_inicial"] == "Salas" and dfs.VISTA_INICIAL["Salas"] == "salas"
   and "Cadeiras" not in dfs.OPCOES["pagina_inicial"])
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
raise SystemExit(0 if all(res) else 1)
