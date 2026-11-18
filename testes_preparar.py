"""Testes do assistente pedagógico «Preparar com a IA», sem internet nem IA (py -3.14 testes_preparar.py)."""
import io
import json

import preparar as pp

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


# ---------- respostas da IA na conversa
t = pp.interpretar_turno('```json\n{"mensagem": "Olá! Em que disciplina vamos trabalhar?", "opcoes": ["Matemática", '
                         '"Português", "matemática", "  Estudo do Meio  "], "dados": {"ano": "3.º ano", "tema": null, '
                         '"objetivos": ["somar", "subtrair"]}, "falta": ["disciplina", "tema"], "titulo": "Aula", '
                         '"pronto": false}\n```')
ok("Lê o JSON da IA (com cercas), tira opções repetidas e espaços, ignora dados vazios e junta listas",
   t["mensagem"] == "Olá! Em que disciplina vamos trabalhar?" and t["opcoes"] == ["Matemática", "Português", "Estudo do Meio"]
   and t["dados"] == {"ano": "3.º ano", "objetivos": "somar, subtrair"} and t["falta"] == ["disciplina", "tema"]
   and t["pronto"] is False)
t = pp.interpretar_turno('Claro! {"mensagem": "Vou criar a ficha.", "opcoes": ["x"], "dados": {}, "pronto": true} Fim.')
ok("Texto à volta do JSON não estraga; pronto → sem opções nem campos em falta",
   t["pronto"] is True and t["opcoes"] == [] and t["falta"] == [] and t["mensagem"] == "Vou criar a ficha.")
try:
    pp.interpretar_turno("Desculpa, não percebi.")
    ok("Resposta sem JSON → erro (a app mostra o erro e deixa repetir)", False)
except ValueError:
    ok("Resposta sem JSON → erro (a app mostra o erro e deixa repetir)", True)
try:
    pp.interpretar_turno('{"mensagem": "", "pronto": false}')
    ok("Sem mensagem e sem estar pronto → erro", False)
except ValueError:
    ok("Sem mensagem e sem estar pronto → erro", True)
t = pp.interpretar_turno('{"mensagem": "ok", "opcoes": ["a","b","c","d","e","f","g","h"], "dados": {}}')
ok("No máximo 6 respostas rápidas", len(t["opcoes"]) == 6)

# ---------- mensagens para a IA
turnos = [{"papel": "prof", "texto": "Quero criar uma ficha de exercícios."},
          {"papel": "ia", "json": {"mensagem": "Que disciplina?", "dados": {}, "pronto": False}},
          {"papel": "prof", "texto": "Matemática, 3.º ano"}]
m = pp.mensagens_conversa("ficha", turnos, "Perfil: Professor · Ensino básico.")
ok("Conversa → mensagens: contexto e pedido primeiro, a IA com o JSON que deu, o professor com o que escreveu",
   [x["role"] for x in m] == ["user", "assistant", "user"] and "Perfil: Professor" in m[0]["content"]
   and "ficha de exercícios" in m[0]["content"] and json.loads(m[1]["content"])["mensagem"] == "Que disciplina?"
   and m[2]["content"] == "Matemática, 3.º ano")
muitos = [{"papel": "prof", "texto": "Quero planear uma aula."}]
for i in range(pp.MAX_PERGUNTAS):
    muitos += [{"papel": "ia", "json": {"mensagem": f"P{i}?"}}, {"papel": "prof", "texto": f"R{i}"}]
ok("Depois do número máximo de perguntas, a IA é mandada criar com o que tem",
   "pronto" in pp.mensagens_conversa("aula", muitos, "")[-1]["content"])
ok("Sugestão escolhida → a IA sabe o que tem de produzir",
   "grelha de avaliação" in pp.mensagens_conversa("outro", [{"papel": "prof", "texto": "Preciso de uma grelha."}], "",
                                                  "grelha")[0]["content"].lower())
s = pp.sistema_conversa("teste")
ok("Instruções da conversa: uma pergunta de cada vez, só JSON, campos essenciais do tipo",
   "UMA pergunta" in s and "JSON" in s and "«duracao»" in s and "«tema»" in s)
p = pp.pedido_material("ficha", {"disciplina": "Matemática", "ano": "3.º ano", "tema": "Multiplicação"}, "Quero uma ficha.")
ok("Pedido do material: dados recolhidos e estrutura obrigatória (níveis, espaço para respostas, soluções à parte)",
   "- Disciplina: Matemática" in p[0]["content"] and "Nível 1" in p[0]["content"] and "Soluções" in p[0]["content"]
   and "________" in p[0]["content"])
ok("Teste: cotações a somar 100 pontos, critérios de classificação e de correção",
   all(x in pp.pedido_material("teste", {}, "")[0]["content"]
       for x in ("100 pontos", "Critérios de classificação", "Critérios de correção", "Quadro de cotações")))
ok("Aula: objetivos, desenvolvimento, atividades, recursos, diferenciação e avaliação",
   all(x in pp.pedido_material("aula", {}, "")[0]["content"] for x in (
       "Objetivos de aprendizagem", "Desenvolvimento da aula", "Atividades de aprendizagem", "Recursos",
       "Diferenciação pedagógica", "Avaliação das aprendizagens")))
ok("Revisão: devolve o material completo com a alteração pedida",
   "COMPLETO" in pp.pedido_revisao("# A", "mais fácil")[0]["content"] and "<material>" in pp.pedido_revisao("# A", "x")[0]["content"])
ok("Material: tira a cerca ```markdown e lê o título", pp.limpar_material("```markdown\n# Ficha de **multiplicação**\ntexto\n```")
   == "# Ficha de **multiplicação**\ntexto" and pp.titulo_do_material("# Ficha de **multiplicação**\nx") == "Ficha de multiplicação")
ok("Progresso: os campos essenciais com o que já se sabe",
   pp.progresso("aula", {"dados": {"disciplina": "Ciências"}}) == [("Disciplina", "Ciências"), ("Ano", None), ("Tema", None),
                                                                 ("Duração", None)])

# ---------- modelo do professor (teste da escola, ficha antiga…)
modelo = {"nome": "teste_escola.docx", "texto": "AGRUPAMENTO DE ESCOLAS X\nGrupo I (40 pontos)\n1. Escolhe a opção correta… (8 pontos)"}
m = pp.mensagens_conversa("teste", [{"papel": "prof", "texto": "Quero um teste."}], "", "", modelo)
ok("Modelo anexado: vai no contexto da conversa (a IA tira dele o que puder e pergunta como o usar)",
   "teste_escola.docx" in m[0]["content"] and "Grupo I (40 pontos)" in m[0]["content"]
   and "Seguir este formato" in pp.sistema_conversa("teste"))
p = pp.pedido_material("teste", {"disciplina": "História", "uso_modelo": "Seguir este formato"}, "Quero um teste.", modelo=modelo)
ok("Seguir o formato: o pedido leva o modelo e manda copiar a estrutura com conteúdo novo",
   "<modelo>" in p[0]["content"] and "Grupo I (40 pontos)" in p[0]["content"] and "ESTRUTURA" in p[0]["content"])
ok("Escolhas do professor reconhecidas: formato, a partir deste, adaptar (ou ainda nada)",
   pp.uso_do_modelo({"uso_modelo": "formato"}) == "formato" and pp.uso_do_modelo({"uso_modelo": "Fazer um novo a partir deste"}) == "base"
   and pp.uso_do_modelo({"uso_modelo": "Adaptar este"}) == "adaptar" and pp.uso_do_modelo({}) == "")
p = pp.pedido_material("ficha", {"uso_modelo": "base"}, "", modelo={"nome": "x", "texto": "A" * (pp.MAX_MODELO + 50)})
ok("Modelo muito grande: vai cortado (e a IA sabe que foi cortado); sem modelo, nada muda",
   "foi cortado" in p[0]["content"] and "CONTEÚDO" in p[0]["content"]
   and "<modelo>" not in pp.pedido_material("ficha", {}, "")[0]["content"])
ok("O material guarda o modelo que usou", pp.novo_material("teste", "T", {}, "# T", [], "", modelo)["modelo"]["nome"] == "teste_escola.docx"
   and pp.novo_material("teste", "T", {}, "# T", [])["modelo"] is None)

# ---------- o que a IA está a fazer
ok("Estado na conversa: primeira pergunta, a ler a resposta, a ler o modelo",
   pp.estado_turno([{"papel": "prof", "texto": "Quero planear uma aula."}])[0] == "A preparar a primeira pergunta"
   and pp.estado_turno([{"papel": "prof", "texto": "x"}, {"papel": "ia"}, {"papel": "prof", "texto": "3.º ano"}])
   == ("A ler a tua resposta", "«3.º ano» · a ver o que ainda falta")
   and pp.estado_turno([{"papel": "prof", "texto": "x"}, {"papel": "prof", "texto": "Anexei um modelo: «t.docx»."}],
                       {"nome": "t.docx"})[0] == "A ler o modelo")
ok("Estado antes de escrever: o tipo de material, os dados e o modelo",
   pp.estado_material("aula", {"disciplina": "Matemática", "ano": "3.º ano", "uso_modelo": "formato"}, {"nome": "m.docx"})
   == ("A pensar no plano de aula", "Matemática · 3.º ano · no formato de «m.docx»"))
texto_meio = "# Plano\nlinha\n## Objetivos de aprendizagem\n- a\n## **Conteúdos**\n- b\n### Desenvolvimento da aula\n"
ok("Estado a escrever: a secção em curso e as que já estão feitas",
   pp.secoes_escritas(texto_meio) == ["Objetivos de aprendizagem", "Conteúdos", "Desenvolvimento da aula"]
   and pp.estado_escrita(texto_meio) == ("A escrever: Desenvolvimento da aula",
                                         "Já escrevi: Objetivos de aprendizagem · Conteúdos")
   and pp.estado_escrita("# Ficha\nNome:")[0] == "A escrever o título e o cabeçalho"
   and pp.estado_escrita("## A\n", "Mais difícil") == ("A escrever: A", "Mais difícil · A primeira secção"))

# ---------- guardar versões
mat = pp.novo_material("ficha", "Ficha", {"ano": "3.º"}, "# Ficha A\nx", turnos)
for n in range(pp.MAX_VERSOES + 3):
    pp.juntar_versao(mat, f"# Ficha v{n}\ny", "Mais difícil")
ok("Versões: guarda as mais recentes (no máximo 12) e o título acompanha a última",
   len(mat["versoes"]) == pp.MAX_VERSOES and mat["versoes"][-1]["conteudo"].startswith(f"# Ficha v{pp.MAX_VERSOES + 2}")
   and mat["titulo"] == f"Ficha v{pp.MAX_VERSOES + 2}" and mat["conversa"] == turnos)
a, b = dict(mat, id="a", atualizado_em="2026-01-01"), dict(mat, id="b", atualizado_em="2026-05-01")
ok("Lista dos materiais: os mais recentes primeiro; procurar por id", [x["id"] for x in pp.lista_ordenada([a, b, {}])] == ["b", "a"]
   and pp.procurar([a, b], "a") is a and pp.procurar([a], "z") is None)

# ---------- Markdown → blocos → Word e PDF (HTML)
MD = """# Ficha de multiplicação
Matemática · 3.º ano
**Nome:** __________ **N.º:** ____

## Instruções
Lê com *atenção*.

### Nível 1 — Aplicação direta
1. Calcula 3 × 4.
________________________________
2. Completa:
   - 2 × 5 = ___
   - 6 × 2 = ___

| Pergunta | Cotação |
|---|---|
| 1 | 10 pontos |
| **Total** | **100 pontos** |

---
## Soluções
1. 12 (`3 × 4`)
"""
bs = pp.blocos(MD)
tipos = [b[0] for b in bs]
ok("Markdown em blocos: títulos, linhas, listas numeradas e com recuo, linhas de resposta, tabela, separador",
   tipos == ["h", "p", "h", "p", "h", "lista", "resposta", "lista", "tabela", "regra", "h", "lista"]
   and bs[1] == ("p", ["Matemática · 3.º ano", "**Nome:** __________ **N.º:** ____"])
   and bs[7][2] == [(0, "2.", "Completa:"), (1, "•", "2 × 5 = ___"), (1, "•", "6 × 2 = ___")]
   and bs[8][1] == ["Pergunta", "Cotação"] and bs[8][2][1] == ["**Total**", "**100 pontos**"])
ok("Negrito, itálico e código dentro do texto; os sublinhados das respostas não viram itálico nem negrito",
   pp.pedacos("**Nome:** __________ __negrito__") == [("Nome:", True, False, False), (" __________ ", False, False, False),
                                                      ("negrito", True, False, False)]
   and pp.pedacos("**Nome:** ____ e *atenção* `x`") == [("Nome:", True, False, False), (" ____ e ", False, False, False),
                                                    ("atenção", False, True, False), (" ", False, False, False),
                                                    ("x", False, False, True)])
h = pp.para_html("Ficha", MD)
ok("HTML para o PDF: sem título repetido, tabela, separador e texto escapado",
   h.count("<h1>") == 1 and "<table>" in h and "<th><b>Total</b></th>" not in h and "<td><b>Total</b></td>" in h
   and "<hr/>" in h and "<i>atenção</i>" in h and "<script" not in pp.para_html("x", "<script>alert(1)</script>"))
from docx import Document  # noqa: E402

dados_docx = pp.para_docx("Ficha", MD)
d = Document(io.BytesIO(dados_docx))
textos = [p.text for p in d.paragraphs]
ok("Word: abre, tem o título, as instruções, os exercícios, a tabela e as soluções numa página à parte",
   dados_docx[:2] == b"PK" and textos[0] == "Ficha de multiplicação" and "Lê com atenção." in textos
   and any(t.startswith("1.\tCalcula 3 × 4.") for t in textos) and len(d.tables) == 1
   and d.tables[0].rows[2].cells[1].text == "100 pontos" and 'w:br w:type="page"' in d.element.xml
   and any(r.bold for p in d.paragraphs if "Nome:" in p.text for r in p.runs))
ok("Nome do ficheiro sem acentos nem espaços", pp.nome_ficheiro("Ficha de Multiplicação — 3.º ano", "docx")
   == "ficha_de_multiplicacao_3_ano.docx")
ok("Tipos e sugestões: três materiais principais e as nove sugestões da área «Em que posso ajudar hoje?»",
   pp.TIPOS_PRINCIPAIS == ("aula", "ficha", "teste") and len(pp.SUGESTOES) == 9
   and all(s[3] in pp.TIPOS for s in pp.SUGESTOES) and all(s[0] in pp.GUIA_SUGESTAO for s in pp.SUGESTOES)
   and all(len(pp.CURTO_SUGESTAO[s[0]]) <= 28 for s in pp.SUGESTOES))
try:
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        import fitz  # noqa: F401

    pdf = pp.para_pdf("Ficha", MD)
    ok("PDF: cria um PDF A4 com o texto", pdf[:5] == b"%PDF-" and b"%%EOF" in pdf[-1024:])
except ImportError:
    print("(PyMuPDF não está instalado aqui: o teste do PDF fica por fazer)")

print(f"\nResumo: {sum(res)} de {len(res)} passaram")
