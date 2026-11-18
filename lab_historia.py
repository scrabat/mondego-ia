"""Laboratório de História e Geografia: um assistente de aprendizagem histórica (sem Streamlit; testado em
testes_laboratorios.py). Aqui ficam as instruções para a IA, a validação do que ela devolve e as regras de rigor.

Rigor: a IA não pode inventar datas, nomes nem acontecimentos. Cada facto vem com o grau de certeza («confirmado»,
«aproximado» ou «incerto»); interpretações de historiadores ficam separadas dos factos; quando há fontes da web
(Wikipédia, notícias, Tavily ou a pesquisa Google), a IA cita-as com [n] e a app mostra a lista.
"""
from __future__ import annotations

import re

SECOES = {
    "explicar": ("Explicar", ":material/school:"),
    "documentos": ("Documentos", ":material/description:"),
    "cronologia": ("Cronologia", ":material/timeline:"),
    "comparar": ("Comparar", ":material/compare_arrows:"),
    "testes": ("Testes", ":material/quiz:"),
    "resumos": ("Resumos", ":material/summarize:"),
    "mapa": ("Mapas", ":material/map:"),
}
CERTEZAS = {"confirmado": "Confirmado", "aproximado": "Data aproximada", "incerto": "Incerto / discutido"}
ORGANIZACAO_RESUMO = {"tema": "Por tema", "periodo": "Por período", "acontecimento": "Por acontecimento",
                      "capitulo": "Por capítulo (dos teus materiais)", "objetivo": "Por objetivo de estudo"}

RIGOR = ("Rigor histórico (obrigatório): não inventes datas, nomes, números, citações nem acontecimentos. Se não "
         "tiveres a certeza de uma data, escreve «c.» ou o século e diz que é aproximada; se um facto for discutido "
         "pelos historiadores, di-lo. Separa sempre os factos das interpretações historiográficas. Se te derem "
         "resultados da web ou materiais, usa-os e cita-os com [n] ou [nome do ficheiro]; não cites fontes que não te "
         "deram. Português de Portugal; datas por extenso (ex.: 25 de abril de 1974), sem LaTeX.")


def sistema(nivel: str) -> str:
    return ("És um professor de História e Geografia, rigoroso e claro, que ajuda o aluno a compreender, relacionar e "
            f"memorizar. Adaptas a profundidade e o vocabulário ao nível: {nivel}. " + RIGOR)


def pedido_explicacao(tema: str) -> str:
    return (f"Explica: {tema}\n\nUsa exatamente estas secções (### título), curtas e bem organizadas:\n"
            "### Em poucas palavras\n(2 frases)\n### Contexto histórico\n### Causas\n(lista: causas profundas e "
            "imediatas, cada uma com uma frase)\n### Desenvolvimento\n### Principais acontecimentos\n(tabela com as "
            "colunas Data | Acontecimento | Porque importa; só datas que tens a certeza)\n### Consequências\n(curto e "
            "médio/longo prazo)\n### Personagens importantes\n(nome — papel, uma linha cada)\n### Importância histórica"
            "\n### Factos e interpretações\n(o que é facto assente e o que é interpretação ou debate entre historiadores)"
            "\n### Para memorizar\n(3 a 6 pontos curtos)\nSe o tema não for histórico ou geográfico, responde só à "
            "pergunta, sem estas secções.")


def pedido_documento(documento: str, origem: str = "") -> str:
    return (("Origem indicada pelo aluno: " + origem + "\n") if origem else "") + (
        "Analisa este documento histórico como num exercício de análise de fontes:\n<documento>\n"
        f"{documento[:20000]}\n</documento>\n"
        'Responde só com JSON: {"natureza": "tipo de fonte (primária/secundária; carta, lei, discurso, cartaz, '
        'imagem, gráfico...)", "autor": {"valor": "...", "certeza": "confirmado|aproximado|incerto"}, '
        '"data": {"valor": "...", "certeza": "confirmado|aproximado|incerto"}, "contexto": "contexto histórico", '
        '"assunto": "...", "intencao": "intenção do autor", "publico_alvo": "...", "mensagem": "ideias principais", '
        '"relacao": ["ligação a acontecimentos ou processos históricos"], "factos": ["o que o documento afirma ou '
        'mostra e se pode confirmar"], "interpretacoes": ["leituras possíveis / interpretações"], '
        '"nao_confirmado": ["o que não se consegue confirmar só com este documento"], '
        '"perguntas_para_pensar": ["2 a 3 perguntas de análise"]}. Se o autor ou a data não estiverem no documento '
        'nem forem conhecidos, escreve "desconhecido" com certeza "incerto". ' + RIGOR)


def _txt(v, n: int = 1500) -> str:
    return " ".join(str(v or "").split())[:n]


def _lista(v, n: int = 10, m: int = 400) -> list:
    if isinstance(v, str):
        v = [v]
    return [_txt(x, m) for x in (v or []) if _txt(x)][:n]


def _certeza(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in CERTEZAS else "incerto"


def validar_documento(d: dict) -> dict:
    if not isinstance(d, dict) or not _txt(d.get("assunto") or d.get("mensagem")):
        raise ValueError("A análise veio vazia.")

    def campo(x):
        if isinstance(x, dict):
            return {"valor": _txt(x.get("valor"), 200) or "desconhecido", "certeza": _certeza(x.get("certeza"))}
        return {"valor": _txt(x, 200) or "desconhecido", "certeza": "incerto"}
    return {"natureza": _txt(d.get("natureza"), 300), "autor": campo(d.get("autor")), "data": campo(d.get("data")),
            "contexto": _txt(d.get("contexto")), "assunto": _txt(d.get("assunto"), 600),
            "intencao": _txt(d.get("intencao"), 800), "publico_alvo": _txt(d.get("publico_alvo"), 300),
            "mensagem": _txt(d.get("mensagem")), "relacao": _lista(d.get("relacao")), "factos": _lista(d.get("factos")),
            "interpretacoes": _lista(d.get("interpretacoes")), "nao_confirmado": _lista(d.get("nao_confirmado")),
            "perguntas_para_pensar": _lista(d.get("perguntas_para_pensar"), 4)}


def pedido_cronologia(tema: str) -> str:
    return (f"Cria uma cronologia sobre: {tema}. Entre 6 e 16 acontecimentos importantes, por ordem. "
            'Responde só com JSON: {"titulo": "...", "eventos": [{"data": "ex.: 14 de julho de 1789", "ano": 1789, '
            '"titulo": "curto", "descricao": "o que aconteceu (1-2 frases)", "contexto": "1 frase", '
            '"importancia": "porque importa (1 frase)", "relacoes": ["títulos de outros eventos desta lista que causou '
            'ou com que se relaciona"], "categoria": "Política|Economia|Sociedade|Cultura|Guerra|Ciência|Religião", '
            '"certeza": "confirmado|aproximado|incerto"}]}. «ano» é um número (negativo antes de Cristo). ' + RIGOR)


def _ano(v) -> float | None:
    """Ano de um número ou de uma data em texto («5 de outubro de 1910» → 1910; «44 a.C.» → -44)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        texto = str(v or "")
        anos = re.findall(r"\d{3,4}", texto) or re.findall(r"\d{1,4}", texto)
        if not anos:
            return None
        ano = float(anos[-1])
        return -ano if re.search(r"a\.?\s?C\.?|antes de cristo|\bAC\b", texto, re.I) else ano


def validar_cronologia(d: dict) -> dict:
    eventos = []
    for e in (d or {}).get("eventos") or (d or {}).get("_lista") or []:
        if not isinstance(e, dict) or not _txt(e.get("titulo")):
            continue
        ano = _ano(e.get("ano")) if e.get("ano") is not None else _ano(e.get("data"))
        if ano is None:
            continue
        eventos.append({"data": _txt(e.get("data") or int(ano), 80), "ano": ano, "titulo": _txt(e["titulo"], 120),
                        "descricao": _txt(e.get("descricao"), 600), "contexto": _txt(e.get("contexto"), 500),
                        "importancia": _txt(e.get("importancia"), 500), "relacoes": _lista(e.get("relacoes"), 6, 120),
                        "categoria": _txt(e.get("categoria") or "Geral", 30), "certeza": _certeza(e.get("certeza"))})
    if len(eventos) < 2:
        raise ValueError("A cronologia veio vazia.")
    eventos.sort(key=lambda e: e["ano"])
    titulos = {e["titulo"] for e in eventos}
    for e in eventos:  # só ligações a eventos que existem nesta cronologia
        e["relacoes"] = [r for r in e["relacoes"] if r in titulos and r != e["titulo"]]
    return {"titulo": _txt((d or {}).get("titulo") or "Cronologia", 120), "eventos": eventos[:20]}


def dot_relacoes(cronologia: dict, cor: str = "#B7841A") -> str | None:
    """Esquema das relações de causa/ligação entre acontecimentos (Graphviz), só se houver relações."""
    import textwrap

    ligacoes = [(e["titulo"], r) for e in cronologia["eventos"] for r in e.get("relacoes") or []]
    if not ligacoes:
        return None
    ids = {e["titulo"]: f"e{i}" for i, e in enumerate(cronologia["eventos"])}

    def q(t: str) -> str:
        return '"' + "\\n".join(textwrap.wrap(t.replace('"', "'").replace("\\", "/"), 22)) + '"'
    usados = {a for a, _ in ligacoes} | {b for _, b in ligacoes}
    linhas = ['digraph G {', 'graph [bgcolor="transparent", rankdir=LR, pad=0.3, nodesep=0.3, ranksep=0.5];',
              'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#DCE3E1", '
              'fillcolor="#FFFFFF", fontcolor="#16232B", margin="0.15,0.08"];',
              f'edge [color="{cor}", penwidth=1.3, arrowsize=0.7];']
    for e in cronologia["eventos"]:
        if e["titulo"] in usados:
            linhas.append(f'{ids[e["titulo"]]} [label={q(e["data"] + " · " + e["titulo"])}];')
    for a, b in ligacoes:  # «a relaciona-se com b»: seta do mais antigo para o mais recente
        x, y = sorted([a, b], key=lambda t: next(ev["ano"] for ev in cronologia["eventos"] if ev["titulo"] == t))
        linhas.append(f"{ids[x]} -> {ids[y]};")
    return "\n".join(dict.fromkeys(linhas)) + "\n}"


def pedido_comparacao(itens: list, criterios: list | None = None) -> str:
    crit = (f"Usa estes critérios: {', '.join(criterios)}. " if criterios else
            "Escolhe 6 a 9 critérios adequados (ex.: datas e duração, contexto, causas, objetivos, protagonistas, "
            "organização política, economia, sociedade, cultura, consequências). ")
    return (f"Compara: {' | '.join(itens)}. " + crit +
            'Responde só com JSON: {"titulo": "...", "itens": ["nomes curtos, pela ordem dada"], "criterios": '
            '[{"criterio": "...", "valores": {"<item>": "1-2 frases"}}], "semelhancas": ["..."], "diferencas": '
            '["..."], "conclusao": "2-3 frases", "debates": ["pontos discutidos pelos historiadores (se houver)"]}. '
            + RIGOR)


def validar_comparacao(d: dict, itens_pedidos: list) -> dict:
    itens = _lista((d or {}).get("itens"), 6, 80) or [_txt(i, 80) for i in itens_pedidos]
    criterios = []
    for c in (d or {}).get("criterios") or []:
        if not isinstance(c, dict) or not _txt(c.get("criterio")) or not isinstance(c.get("valores"), dict):
            continue
        valores = {k: _txt(v, 500) for k, v in c["valores"].items()}
        # aceita chaves com pequenas diferenças (maiúsculas/espaços) e alinha pelos itens
        normal = {re.sub(r"\W+", "", k.lower()): v for k, v in valores.items()}
        linha = {i: valores.get(i) or normal.get(re.sub(r"\W+", "", i.lower())) or "—" for i in itens}
        criterios.append({"criterio": _txt(c["criterio"], 80), "valores": linha})
    if len(itens) < 2 or len(criterios) < 2:
        raise ValueError("A comparação veio incompleta.")
    return {"titulo": _txt((d or {}).get("titulo") or " vs ".join(itens), 120), "itens": itens, "criterios": criterios,
            "semelhancas": _lista((d or {}).get("semelhancas")), "diferencas": _lista((d or {}).get("diferencas")),
            "conclusao": _txt((d or {}).get("conclusao"), 800), "debates": _lista((d or {}).get("debates"), 5)}


def tabela_comparacao(comp: dict) -> list:
    """Linhas para st.dataframe / tabela: [{"Critério": ..., item1: ..., item2: ...}]."""
    return [{"Critério": c["criterio"], **c["valores"]} for c in comp["criterios"]]


def pedido_resumo(tema: str, organizacao: str, objetivo: str = "") -> str:
    como = {"tema": "organizado por temas/subtemas", "periodo": "organizado por períodos cronológicos",
            "acontecimento": "organizado por acontecimentos (cada um: data, o quê, causas, consequências)",
            "capitulo": "organizado pelos capítulos/secções dos materiais dados",
            "objetivo": f"organizado para este objetivo de estudo: {objetivo or 'preparar o teste'}"}.get(organizacao, "")
    return (f"Faz um resumo de estudo sobre: {tema}, {como}.\nInclui: uma tabela «Datas-chave» (Data | Acontecimento), "
            "os conceitos importantes em **negrito** com definição curta, as personagens (nome — papel), e uma secção "
            "### Causas e consequências com setas (ex.: Causa → Acontecimento → Consequência). Termina com "
            "### Para memorizar (5 a 8 pontos). Curto e organizado, para rever antes de um teste. " + RIGOR)


def consultas_fontes(tema: str) -> dict:
    """Pesquisa para fundamentar a resposta (Wikipédia/web), no formato de pesquisa_web.pesquisar."""
    tema = _txt(tema, 120)
    return {"pt": tema, "en": tema, "tipo": "geral", "local": "", "pergunta": tema}


def bloco_fontes(resultados: list) -> str:
    linhas = []
    for i, r in enumerate(resultados or [], 1):
        linhas.append(f"[{i}] {r.get('titulo', '')} ({r.get('url', '')}): {_txt(r.get('texto'), 1500)}")
    return "\n".join(linhas)
