"""Testes dos módulos do Mondego IA que não dependem do Streamlit.
Correr com:  py -3.14 testes_modulos.py   (não mexe nos teus dados)"""
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import academico as ac
import identidade as idt
import repeticao as rs
import salas as sl

resultados = []
def ok(nome, cond):
    resultados.append(bool(cond)); print(("PASSOU " if cond else "FALHOU ") + nome)

# ---------- repetição espaçada
hoje = date(2026, 11, 2)
c = rs.preparar({"frente": "O que é uma matriz?", "verso": "Tabela de números"})
ok("Cartão novo está para rever hoje", rs.devido(c, hoje))
rs.responder(c, "sabia", hoje)
ok("Sabia: sobe para a caixa 1 e volta amanhã", c["caixa"] == 1 and c["proxima"] == "2026-11-03" and not rs.devido(c, hoje))
rs.responder(c, "sabia", hoje + timedelta(days=1))
ok("Sabia outra vez: caixa 2, volta 3 dias depois", c["caixa"] == 2 and c["proxima"] == "2026-11-06")
rs.responder(c, "errei", hoje + timedelta(days=4))
ok("Errei: volta à caixa 1 e repete no mesmo dia", c["caixa"] == 1 and c["proxima"] == "2026-11-06")
rs.responder(c, "dificil", hoje)
ok("Difícil: fica e volta amanhã", c["caixa"] == 1 and c["proxima"] == "2026-11-03" and c["vistas"] == 4 and c["acertos"] == 2)
for _ in range(10):
    rs.responder(c, "sabia", hoje)
ok("Caixa máxima é 5 (30 dias)", c["caixa"] == 5 and c["proxima"] == "2026-12-02")
novos = rs.juntar_progresso([{"frente": "o que é uma MATRIZ?", "verso": "x"}, {"frente": "Determinante", "verso": "y"}], [c])
ok("Gerar cartões novos mantém o progresso das frentes iguais", novos[0]["caixa"] == 5 and novos[1]["caixa"] == 0)
lista = [rs.preparar({"frente": str(i)}) for i in range(3)]
rs.responder(lista[1], "sabia", hoje)
r = rs.resumo(lista, hoje)
ok("Resumo: 2 para hoje, 1 na caixa 1", r["para_hoje"] == 2 and r["caixas"][1] == 1 and r["total"] == 3)

# ---------- salas (regras de acesso)
def _lanca(f):
    try:
        f()
        return False
    except ValueError:
        return True

membros = [sl.Membro("s1", "prof", "professor"), sl.Membro("s1", "ana", "aluno"), sl.Membro("s1", "rui", "aluno")]
f_prof = sl.Ficheiro("f1", "s1", "prof", "teoria.pdf", pasta_fixa=True)
f_ana = sl.Ficheiro("f2", "s1", "ana", "apontamentos.jpg")
f_ana_fixa = sl.Ficheiro("f3", "s1", "ana", "tentativa.pdf", pasta_fixa=True)
ok("Pasta fixa do professor: todos os membros veem", all(sl.pode_ver_ficheiro(f_prof, u, membros) for u in ("prof", "ana", "rui")))
ok("Ficheiro de aluno: só o dono vê", sl.pode_ver_ficheiro(f_ana, "ana", membros) and not sl.pode_ver_ficheiro(f_ana, "rui", membros)
   and not sl.pode_ver_ficheiro(f_ana, "prof", membros))
ok("Documento partilhado por um membro (quando a sala o permite): todos os membros veem", sl.pode_ver_ficheiro(f_ana_fixa, "rui", membros))
sala_cad = {"id": "s1", "criador_id": "prof", **sl.definicoes_padrao("cadeira")}
sala_grupo = {"id": "s1", "criador_id": "ana", **sl.definicoes_padrao("grupo_estudo")}
ok("Sala de cadeira: só o criador partilha; grupo de estudo: todos partilham", sl.pode_partilhar(sala_cad, "prof")
   and not sl.pode_partilhar(sala_cad, "ana") and sl.pode_partilhar(sala_grupo, "rui"))
ok("Só o criador configura, modera e remove membros (não a si próprio)", sl.pode_configurar(sala_cad, "prof")
   and not sl.pode_configurar(sala_cad, "ana") and sl.pode_apagar_ficheiro(sala_cad, "ana", "prof")
   and not sl.pode_apagar_ficheiro(sala_cad, "prof", "ana") and sl.pode_remover_membro(sala_cad, "ana", "prof")
   and not sl.pode_remover_membro(sala_cad, "prof", "prof"))
ok("Quem não é membro não vê nada", not sl.pode_ver_ficheiro(f_prof, "estranho", membros))
ok("Assistente do Rui só usa o que ele pode ver", [f.id for f in sl.ficheiros_para_assistente([f_prof, f_ana], "rui", membros)] == ["f1"])
sala_sem_chat = {**sala_cad, "chat_modo": "desligado"}
sala_com_chat = {**sala_cad, "chat_modo": "todos"}
sala_avisos = {**sala_cad, "chat_modo": "criador"}
ok("Conversa só quando ativa e só para membros; em modo avisos só o criador escreve",
   not sl.pode_escrever_no_chat(sala_sem_chat, "ana", membros) and sl.pode_escrever_no_chat(sala_com_chat, "ana", membros)
   and not sl.pode_escrever_no_chat(sala_com_chat, "x", membros) and not sl.pode_escrever_no_chat(sala_avisos, "ana", membros)
   and sl.pode_escrever_no_chat(sala_avisos, "prof", membros))
ok("Definições validadas (valores desconhecidos recusados, nome com tamanho certo)",
   sl.validar_definicoes({"chat_modo": "criador", "xpto": 1}, sala_cad)["chat_modo"] == "criador"
   and all(_lanca(lambda c=c: sl.validar_definicoes(c, sala_cad)) for c in ({"chat_modo": "x"}, {"nome": "a"}, {"cor": "fúcsia"})))
cod = sl.gerar_codigo()
ok("Código de 6 caracteres sem 0/O/1/I", len(cod) == 6 and not set(cod) & set("0O1I"))
ok("Código normalizado e link de convite", sl.normalizar_codigo(" abc-234 ") == "ABC234"
   and sl.link_convite("https://mondego.app/", "abc 234") == "https://mondego.app/?sala=ABC234")
ok("Aluno cria grupo de estudo; professor cria sala de cadeira",
   sl.tipo_de_sala_permitido("Aluno") == "grupo_estudo" and sl.tipo_de_sala_permitido("Professor") == "cadeira")
ok("Convites: com «só eu», só o criador vê o código", not sl.pode_ver_convite({**sala_cad, "convites": "criador"}, "ana")
   and sl.pode_ver_convite({**sala_cad, "convites": "criador"}, "prof") and sl.pode_ver_convite(sala_cad, "ana"))

# ---------- listas académicas
ok("UC tem 50 licenciaturas (catálogo oficial) e 4 mestrados integrados",
   len(ac.CURSOS_UC["Licenciatura"]) == 50 and len(set(ac.CURSOS_UC["Licenciatura"])) == 50 and len(ac.CURSOS_UC["Mestrado integrado"]) == 4)
ok("UC é a primeira instituição", ac.INSTITUICOES[0] == ac.UC)
ok("Mestrado/doutoramento e outras instituições: curso escrito livremente", ac.cursos_de(ac.UC, "Mestrado") == []
   and ac.cursos_de("Universidade do Porto", "Licenciatura") == [])
ok("Descrição do perfil (professor UC)", "professor" in ac.descricao_perfil(
   {"vinculo": "Professor", "nivel": "Ensino superior", "departamentos": ["Departamento de Matemática (FCTUC)"],
    "instituicao": ac.UC, "grau": "Doutoramento"}).lower())

# ---------- identidade
claro, escuro, auto = idt.css_tema("Claro"), idt.css_tema("Escuro"), idt.css_tema("Automático")
ok("Tema claro usa a torre azul-escura; escuro usa a torre clara",
   "--logo-torre:#16324F" in claro and "--logo-torre:#F4F1EA" in escuro and "#F4F1EA" not in claro)
ok("Automático segue o sistema (prefers-color-scheme)", "prefers-color-scheme: dark" in auto and "prefers-color-scheme" not in claro)
ok("Logótipo e indicador usam as variáveis do tema", "var(--logo-torre)" in idt.logo_html() and "mi-estado" in idt.pensar_html()
   and "var(--logo-onda1)" in escuro and ".mi-orbe" in escuro and "@property --mi-ang" in escuro)
ok("Indicador: globo na pesquisa, faísca a pensar, folhas a ler (escolhido pelo texto ou pedido)",
   "mi-estado-web" in idt.pensar_html("A pesquisar na web") and "mi-estado-pensar" in idt.pensar_html("A pensar")
   and "mi-estado-ler" in idt.pensar_html("A ler 3 fontes", tipo="ler") and "mi-estado-web" in idt.pensar_html("Searching the web"))
h = idt.pensar_html("A ler 6 fontes", tipo="ler", fontes=["Eurogamer.pt", "Omelete", "Eurogamer.pt", "", "SIC", "Público", "<b>x</b>"])
ok("Indicador: os sites aparecem em etiquetas (sem repetidos, no máximo 4 e «+N»), com o texto escapado",
   h.count('class="mi-fonte"') == 4 and "+1" in h and "<b>x</b>" not in h and h.count("Eurogamer.pt") == 1)
ok("Indicador: o passo em curso aparece por baixo do título", 'class="mi-estado-detalhe">«Fortnite» · notícias recentes<'
   in idt.pensar_html("A pesquisar na web", "«Fortnite» · notícias recentes"))

print(f"\nResumo: {sum(resultados)} de {len(resultados)} passaram")
