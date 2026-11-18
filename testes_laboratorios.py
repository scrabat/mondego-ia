"""Testes dos Laboratórios de História e Biologia e dos testes com correção (py -3.14 testes_laboratorios.py).
Não precisam de internet nem da IA: verificam as regras, as validações, a correção e os exercícios de genética."""
import json
import re
import xml.dom.minidom
from fractions import Fraction

import exercicios as ex
import lab_biologia as lb
import lab_historia as lh

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


# ---------------------------------------------------------------- testes: pedido, validação e correção
pedido = ex.pedido_teste("historia", "Estado Novo", ["escolha_multipla", "documento"], 6, "Ensino secundário", "difícil",
                         ["Censura"], "texto do manual")
ok("Pedido do teste: tipos pedidos com o formato, nível, dificuldade, temas fracos, materiais e só JSON",
   "Escolha múltipla" in pedido and "Análise de documento" in pedido and "Dificuldade: difícil" in pedido
   and "Censura" in pedido and "<fontes>" in pedido and "só com JSON" in pedido)
bruto = {"titulo": "T", "perguntas": [
    {"tipo": "escolha_multipla", "tema": "A", "pergunta": "P?", "opcoes": ["a", "b", "c", "d"], "correta": 2},
    {"tipo": "escolha_multipla", "tema": "A", "pergunta": "P?", "opcoes": ["a", "b"], "correta": 0},
    {"tipo": "escolha_multipla", "tema": "A", "pergunta": "P?", "opcoes": ["a", "b", "c"], "correta": 7},
    {"tipo": "verdadeiro_falso", "tema": "B", "afirmacao": "X", "verdadeira": "sim"},
    {"tipo": "verdadeiro_falso", "tema": "B", "afirmacao": "X", "verdadeira": False},
    {"tipo": "associacao", "tema": "C", "pares": [{"a": "1", "b": "x"}, {"a": "2", "b": "x"}, {"a": "3", "b": "z"}]},
    {"tipo": "associacao", "tema": "C", "pares": [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}, {"a": "3", "b": "z"}]},
    {"tipo": "grafico", "tema": "D", "colunas": ["t", "v"], "linhas": [[0, 1], [1, 2]], "pergunta": "Tendência?"},
    {"tipo": "documento", "tema": "E", "pergunta": "?"},
    {"tipo": "inventado", "pergunta": "?"}, "lixo"]}
t = ex.validar_teste(bruto)
ok("Validação: deita fora perguntas mal formadas (2 opções, índice fora, V/F sem verdadeiro/falso, pares repetidos, "
   "documento sem texto, tipos inventados)", [q["tipo"] for q in t["perguntas"]] == ["escolha_multipla", "verdadeiro_falso",
                                                                                  "associacao", "grafico"]
   and all(len(q["id"]) == 8 for q in t["perguntas"]))
try:
    ex.validar_teste({"perguntas": []})
    ok("Validação: teste sem perguntas válidas dá erro", False)
except ValueError:
    ok("Validação: teste sem perguntas válidas dá erro", True)
em, vf, asc = t["perguntas"][:3]
ok("Correção exata: escolha múltipla, verdadeiro/falso e associação (pontos parciais)",
   ex.corrigir_objetiva(em, 2)["pontos"] == 100 and ex.corrigir_objetiva(em, 0)["pontos"] == 0
   and "«c»" in ex.corrigir_objetiva(em, 1)["feedback"] and ex.corrigir_objetiva(vf, False)["certa"]
   and not ex.corrigir_objetiva(vf, None)["certa"]
   and ex.corrigir_objetiva(asc, {"1": "x", "2": "y", "3": "x"})["pontos"] == 67)
ok("Associação: a coluna B vem baralhada mas sempre igual para o mesmo teste",
   ex.opcoes_associacao(asc) == ex.opcoes_associacao(asc) and sorted(ex.opcoes_associacao(asc)) == ["x", "y", "z"])
aberta = {"id": "abc12345", "tipo": "desenvolvimento", "tema": "T", "pergunta": "Explica", "criterios": ["c1"],
          "resposta_modelo": "m"}
pc = ex.pedido_correcao([aberta], {"abc12345": "a minha resposta"}, "secundário")
ok("Pedido de correção: critérios, resposta modelo e resposta do aluno; resposta vazia vale 0",
   "a minha resposta" in pc and "c1" in pc and "Resposta vazia = 0" in pc)
corr, conselhos = ex.validar_correcao({"correcoes": [{"id": "abc12345", "pontos": "130", "feedback": "f"},
                                                     {"id": "outro", "pontos": 50}], "melhorar": ["estuda"]},
                                      ["abc12345", "zzz"])
ok("Correção da IA: pontos limitados a 0–100, perguntas sem correção ficam com 0, ids estranhos ignorados",
   corr["abc12345"]["pontos"] == 100 and corr["zzz"]["pontos"] == 0 and "outro" not in corr and conselhos == ["estuda"])
perg = [{"id": "1", "tema": "A"}, {"id": "2", "tema": "A"}, {"id": "3", "tema": "B"}, {"id": "4", "tema": "C"}]
d = ex.diagnostico(perg, {"1": {"pontos": 100}, "2": {"pontos": 80}, "3": {"pontos": 20}, "4": {"pontos": 60}})
ok("Diagnóstico: nota, temas fortes (≥ 75 %) e fracos (< 50 %)", d["nota"] == 65 and d["fortes"] == ["A"]
   and d["fracos"] == ["B"] and d["por_tema"]["C"] == 60)
ok("Adaptativo: sobe a dificuldade com boas notas, desce com más e insiste nos temas fracos",
   ex.adaptar([{"nota": 90, "fracos": []}, {"nota": 85, "fracos": ["X"]}]) == ("difícil", ["X"])
   and ex.adaptar([{"nota": 30, "fracos": ["Y"]}])[0] == "fácil" and ex.adaptar([]) == ("média", []))
ok("Respostas numéricas: frações, percentagens, decimais com vírgula e razões",
   ex.resposta_numerica("1/4") == 0.25 and ex.resposta_numerica("25 %") == 0.25 and ex.resposta_numerica("0,25") == 0.25
   and ex.resposta_numerica("3:1") == 0.75 and ex.resposta_numerica("abc") is None and ex.resposta_numerica("1/0") is None)

# ---------------------------------------------------------------- História
ok("Rigor: as instruções proíbem inventar e pedem certezas, separação factos/interpretações e citação das fontes",
   all(x in lh.RIGOR for x in ["não inventes", "aproximada", "interpretações", "[n]"])
   and "### Factos e interpretações" in lh.pedido_explicacao("25 de Abril") and "Ensino superior" in lh.sistema("Ensino superior"))
doc = lh.validar_documento({"natureza": "carta", "autor": {"valor": "D. Pedro IV", "certeza": "confirmadissimo"},
                            "data": "1826", "assunto": "Carta Constitucional", "factos": "um facto", "relacao": None})
ok("Documento: certezas inválidas passam a «incerto», campos em texto viram listas", doc["autor"]["certeza"] == "incerto"
   and doc["data"] == {"valor": "1826", "certeza": "incerto"} and doc["factos"] == ["um facto"] and doc["relacao"] == [])
cr = lh.validar_cronologia({"titulo": "T", "eventos": [
    {"titulo": "B", "data": "1910", "ano": "1910", "relacoes": ["A", "Z"], "certeza": "confirmado"},
    {"titulo": "A", "data": "5 de outubro de 1908", "relacoes": ["B"]}, {"titulo": "sem ano", "data": "?"},
    {"titulo": "Antes de Cristo", "ano": -44}, {"titulo": "Júlio César", "data": "15 de março de 44 a.C."}]})
ok("Cronologia: ordena (também antes de Cristo), tira o ano da data, descarta eventos sem data e relações inexistentes",
   [e["titulo"] for e in cr["eventos"]] == ["Antes de Cristo", "Júlio César", "A", "B"] and cr["eventos"][3]["relacoes"] == ["A"]
   and cr["eventos"][2]["ano"] == 1908 and cr["eventos"][1]["ano"] == -44 and cr["eventos"][2]["certeza"] == "incerto")
dot = lh.dot_relacoes(cr)
ok("Cronologia: esquema das relações (da mais antiga para a mais recente) só quando há relações",
   dot and "->" in dot and lh.dot_relacoes({"eventos": [{"titulo": "x", "data": "1", "ano": 1, "relacoes": []}]}) is None)
cmp_ = lh.validar_comparacao({"itens": ["Monarquia", "República"], "criterios": [
    {"criterio": "Chefe de Estado", "valores": {"monarquia": "Rei", "República ": "Presidente"}},
    {"criterio": "Eleição", "valores": {"Monarquia": "Hereditário"}}, {"sem": "criterio"}]}, ["Monarquia", "República"])
ok("Comparação: alinha os valores pelos itens (maiúsculas e espaços) e marca o que falta com «—»",
   lh.tabela_comparacao(cmp_) == [{"Critério": "Chefe de Estado", "Monarquia": "Rei", "República": "Presidente"},
                                  {"Critério": "Eleição", "Monarquia": "Hereditário", "República": "—"}])
try:
    lh.validar_comparacao({"itens": ["A", "B"], "criterios": [{"criterio": "x", "valores": {}}]}, ["A", "B"])
    ok("Comparação com menos de 2 critérios dá erro", False)
except ValueError:
    ok("Comparação com menos de 2 critérios dá erro", True)
ok("Resumo: tabela de datas-chave, causas e consequências e «Para memorizar», pela organização pedida",
   all(x in lh.pedido_resumo("República", "periodo") for x in ["Datas-chave", "Causas e consequências", "períodos"])
   and "teste de sexta" in lh.pedido_resumo("X", "objetivo", "teste de sexta"))

# ---------------------------------------------------------------- Biologia
ok("Processos: os 10 processos pedidos, cada um com etapas, onde acontece e conceitos",
   {"mitose", "meiose", "fotossintese", "respiracao", "sintese_proteica", "replicacao", "transcricao_traducao",
    "transporte_membrana", "circulacao", "sistemas"} <= set(lb.PROCESSOS)
   and all(len(p["etapas"]) >= 5 and p["onde"] and p["conceitos"] for p in lb.PROCESSOS.values()))
ok("Processos: esquema com setas por ordem; a circulação fecha o ciclo", "p0 -> p1" in lb.dot_processo(lb.PROCESSOS["mitose"])
   and "style=dashed" in lb.dot_processo(lb.PROCESSOS["circulacao"]) and "style=dashed" not in lb.dot_processo(lb.PROCESSOS["mitose"]))
svgs_ok = True
for tipo, fases in lb.FASES.items():
    for i, nome in enumerate(fases):
        s = lb.svg_divisao(tipo, i)
        try:
            xml.dom.minidom.parseString(s)
        except Exception:  # noqa: BLE001
            svgs_ok = False
        svgs_ok = svgs_ok and f'aria-label="{nome}"' in s and (tipo, nome) in lb.DESCRICAO_FASES
ok("Divisão celular: cada fase da mitose e da meiose é um SVG válido, acessível e com descrição", svgs_ok)
ok("Divisão celular: a telófase II mostra 4 células e a telófase da mitose 2", lb.svg_divisao("meiose", 7).count("<ellipse") == 4
   and lb.svg_divisao("mitose", 4).count("<ellipse") == 2)
# exercícios de genética: confirmar a resposta com uma contagem independente
certos = True
for semente in range(60):
    for tipo in lb.TIPOS_GENETICA:
        e = lb.exercicio_genetica(tipo, semente)
        certos = certos and 0 <= e["valor"] <= 1 and Fraction(e["resposta"]) == Fraction(e["valor"]).limit_denominator(64)
        certos = certos and lb.verificar_resposta(e, e["resposta"]) and not lb.verificar_resposta(e, "2") is True
ok("Genética: 300 exercícios gerados (5 tipos) com resposta entre 0 e 1 e verificação certa", certos)
e = lb.exercicio_genetica("monoibridismo", 3)
gametas_ok = True
for semente in range(40):
    e2 = lb.exercicio_genetica("monoibridismo", semente)
    m = re.search(r"indivíduo (\w\w) com um indivíduo (\w\w)\. .* ser (com .*|heterozigótico \(Aa\))\?", e2["enunciado"])
    pai, mae, alvo = m.group(1), m.group(2), m.group(3)
    filhos = ["".join(sorted(a + b)) for a in pai for b in mae]
    esperado = Fraction(sum(f == "aa" for f in filhos) if "rugosas" in alvo or "verdes" in alvo or "brancas" in alvo
                        or "anão" in alvo or "castanho" in alvo else sum(f == "Aa" for f in filhos) if "heterozig" in alvo
                        else sum(f != "aa" for f in filhos), 4)
    gametas_ok = gametas_ok and Fraction(e2["resposta"]) == esperado
ok("Genética: as probabilidades de monoibridismo batem certo com uma contagem feita à parte", gametas_ok)
x = lb.exercicio_genetica("ligado_x", 5)
ok("Genética: hereditariedade ligada ao X e grupos sanguíneos com quadro de Punnett na resolução",
   "Quadro de Punnett" in "".join(x["passos"]) and "Xᵃ" in x["enunciado"]
   and "| **" in lb.exercicio_genetica("grupos_sanguineos", 2)["passos"][1])
hw = lb.hardy_weinberg(0.04)
ok("Hardy-Weinberg: q² = 0,04 → q = 0,2, p = 0,8, 2pq = 0,32", abs(hw["q"] - 0.2) < 1e-9 and abs(hw["Aa"] - 0.32) < 1e-9)
est = lb.estatisticas(["x", "y", "nome"], [[1, 2, "a"], [2, 4, "b"], [3, 6.5, "c"]])
ok("Dados: mínimo, máximo, média e tendência (declive) calculados pela app", est["y"]["min"] == 2 and est["y"]["max"] == 6.5
   and abs(est["y"]["declive_vs_x"] - 2.25) < 1e-9 and "nome" not in est)
gl = lb.juntar_glossario([{"conceito": "Mitose", "definicao": "velha"}], lb.validar_glossario(
    {"entradas": [{"conceito": "mitose ", "definicao": "nova"}, {"conceito": "ADN", "definicao": "ácido"}, {"conceito": ""}]}))
ok("Glossário: entradas válidas, sem repetidos (a nova substitui) e por ordem alfabética",
   [g["conceito"] for g in gl] == ["ADN", "mitose"] and gl[1]["definicao"] == "nova")
exp = lb.validar_experiencia({"problema": "P", "variaveis": {"controladas": "temperatura"}, "erros": None})
ok("Experiências: campos em falta ficam vazios (a IA não inventa), listas normalizadas",
   exp["variaveis"]["controladas"] == ["temperatura"] and exp["erros"] == [] and exp["hipotese"] == "")
ok("Osmose: simulação sem pedidos à internet nem funções proibidas", not any(x in lb.SIMULACAO_OSMOSE for x in
                                                                          ["fetch(", "XMLHttpRequest", "eval(", "alert(", "localStorage"]))
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
