"""Preparação para testes dos Laboratórios (História e Biologia): pedido à IA, validação, correção e diagnóstico.
Sem Streamlit (testado em testes_laboratorios.py).

- Escolha múltipla, verdadeiro/falso e associação corrigem-se aqui, sem IA (resultado exato e imediato).
- Resposta curta, desenvolvimento, análise de documentos, interpretação de experiências e de gráficos são corrigidas
  pela IA com critérios (pontos de 0 a 100, o que faltou, como melhorar).
- O diagnóstico junta tudo: nota, temas fortes e fracos e o que estudar a seguir. O próximo teste é adaptativo:
  insiste nos temas fracos e sobe ou desce a dificuldade conforme os resultados anteriores.
"""
from __future__ import annotations

import json
import random
import re
import uuid

TIPOS = {
    "escolha_multipla": "Escolha múltipla",
    "verdadeiro_falso": "Verdadeiro ou falso",
    "associacao": "Associação",
    "resposta_curta": "Resposta curta",
    "desenvolvimento": "Desenvolvimento",
    "documento": "Análise de documento",
    "experiencia": "Interpretação de experiência",
    "grafico": "Análise de gráfico ou tabela",
}
TIPOS_DA_AREA = {
    "historia": ["escolha_multipla", "verdadeiro_falso", "associacao", "desenvolvimento", "documento"],
    "biologia": ["escolha_multipla", "resposta_curta", "desenvolvimento", "associacao", "experiencia", "grafico"],
}
OBJETIVAS = {"escolha_multipla", "verdadeiro_falso", "associacao"}
DIFICULDADES = ["fácil", "média", "difícil"]

_FORMATOS = {
    "escolha_multipla": '{"tipo": "escolha_multipla", "tema": "...", "pergunta": "...", "opcoes": ["A", "B", "C", "D"], '
                        '"correta": 0, "explicacao": "porque é esta e não as outras"}',
    "verdadeiro_falso": '{"tipo": "verdadeiro_falso", "tema": "...", "afirmacao": "...", "verdadeira": true, '
                        '"explicacao": "..."}',
    "associacao": '{"tipo": "associacao", "tema": "...", "instrucao": "Associa cada elemento da coluna A à coluna B", '
                  '"pares": [{"a": "...", "b": "..."}], "explicacao": "..."}',
    "resposta_curta": '{"tipo": "resposta_curta", "tema": "...", "pergunta": "...", "criterios": ["..."], '
                      '"resposta_modelo": "1 a 3 frases"}',
    "desenvolvimento": '{"tipo": "desenvolvimento", "tema": "...", "pergunta": "...", "criterios": ["tópico 1", "..."], '
                       '"resposta_modelo": "..."}',
    "documento": '{"tipo": "documento", "tema": "...", "documento": "excerto real e identificado (autor, data) ou '
                 'descrição fiel de uma fonte histórica conhecida", "fonte": "autor, título, data", "pergunta": "...", '
                 '"criterios": ["..."], "resposta_modelo": "..."}',
    "experiencia": '{"tipo": "experiencia", "tema": "...", "contexto": "descrição da experiência e dos resultados", '
                   '"pergunta": "...", "criterios": ["..."], "resposta_modelo": "..."}',
    "grafico": '{"tipo": "grafico", "tema": "...", "titulo_dados": "...", "colunas": ["x", "y"], '
               '"linhas": [[0, 1.5], [1, 2.0]], "pergunta": "...", "criterios": ["..."], "resposta_modelo": "..."}',
}


def pedido_teste(area: str, tema: str, tipos: list, n: int, nivel: str, dificuldade: str = "média",
                 temas_fracos: list | None = None, fontes: str = "") -> str:
    """Instruções para a IA criar o teste (responde só com JSON)."""
    tipos = [t for t in tipos if t in TIPOS] or TIPOS_DA_AREA.get(area, ["escolha_multipla"])
    n = max(3, min(int(n or 6), 15))
    formatos = "\n".join(f"- {TIPOS[t]}: {_FORMATOS[t]}" for t in tipos)
    area_nome = {"historia": "História", "biologia": "Biologia"}.get(area, area)
    texto = (f"Cria um teste de {area_nome} sobre: {tema}.\nNível do aluno: {nivel}. Dificuldade: {dificuldade}.\n"
             f"{n} perguntas, misturando estes tipos (pelo menos uma de cada, se couber):\n{formatos}\n"
             "Regras: factos corretos e verificáveis (sem datas, nomes ou valores inventados; se uma fonte não for "
             "certa, não a uses). Na escolha múltipla, 4 opções plausíveis e só uma certa (o índice «correta» começa "
             "em 0). Nas associações, 4 a 6 pares. Nas perguntas abertas, 2 a 5 critérios de correção objetivos. "
             "«tema» é um subtema curto (2 a 4 palavras) para o diagnóstico. Português de Portugal.")
    if temas_fracos:
        texto += f"\nO aluno errou antes nestes temas: {', '.join(temas_fracos[:6])}. Inclui perguntas sobre eles."
    if fontes:
        texto += f"\nBaseia as perguntas nestes materiais:\n<fontes>\n{fontes[:30000]}\n</fontes>"
    return texto + '\nResponde só com JSON: {"titulo": "...", "perguntas": [ ... ]}'


def _texto(v, limite: int = 2000) -> str:
    return " ".join(str(v or "").split())[:limite]


def validar_teste(dados: dict, tipos_pedidos: list | None = None) -> dict:
    """Limpa o teste da IA: deita fora perguntas mal formadas e dá um id a cada uma. Erro se não sobrar nenhuma."""
    lista = dados.get("perguntas") if isinstance(dados, dict) else None
    if lista is None and isinstance(dados, dict):
        lista = dados.get("_lista")
    perguntas = []
    for p in lista or []:
        if not isinstance(p, dict):
            continue
        tipo = p.get("tipo")
        if tipo not in TIPOS or (tipos_pedidos and tipo not in tipos_pedidos):
            continue
        q = {"id": uuid.uuid4().hex[:8], "tipo": tipo, "tema": _texto(p.get("tema") or "Geral", 60),
             "explicacao": _texto(p.get("explicacao"), 1200)}
        if tipo == "escolha_multipla":
            opcoes = [_texto(o, 300) for o in (p.get("opcoes") or []) if _texto(o)]
            try:
                correta = int(p.get("correta"))
            except (TypeError, ValueError):
                continue
            if len(opcoes) < 3 or not 0 <= correta < len(opcoes) or not _texto(p.get("pergunta")):
                continue
            q.update(pergunta=_texto(p["pergunta"]), opcoes=opcoes[:5], correta=correta)
        elif tipo == "verdadeiro_falso":
            if not _texto(p.get("afirmacao")) or not isinstance(p.get("verdadeira"), bool):
                continue
            q.update(afirmacao=_texto(p["afirmacao"]), verdadeira=p["verdadeira"])
        elif tipo == "associacao":
            pares = [{"a": _texto(x.get("a"), 200), "b": _texto(x.get("b"), 200)} for x in (p.get("pares") or [])
                     if isinstance(x, dict) and _texto(x.get("a")) and _texto(x.get("b"))]
            if len(pares) < 3 or len({x["b"] for x in pares}) != len(pares):
                continue
            q.update(instrucao=_texto(p.get("instrucao") or "Associa cada elemento da coluna A à coluna B."), pares=pares[:6])
        else:
            if not _texto(p.get("pergunta")):
                continue
            q.update(pergunta=_texto(p["pergunta"]), criterios=[_texto(c, 300) for c in (p.get("criterios") or []) if _texto(c)][:6],
                     resposta_modelo=_texto(p.get("resposta_modelo"), 3000))
            if tipo == "documento":
                if not _texto(p.get("documento")):
                    continue
                q.update(documento=_texto(p["documento"], 4000), fonte=_texto(p.get("fonte"), 300))
            elif tipo == "experiencia":
                if not _texto(p.get("contexto")):
                    continue
                q["contexto"] = _texto(p["contexto"], 3000)
            elif tipo == "grafico":
                colunas = [_texto(c, 60) for c in (p.get("colunas") or [])][:6]
                linhas = [l for l in (p.get("linhas") or []) if isinstance(l, list) and len(l) == len(colunas)][:40]
                if len(colunas) < 2 or len(linhas) < 2:
                    continue
                q.update(titulo_dados=_texto(p.get("titulo_dados"), 200), colunas=colunas, linhas=linhas)
        perguntas.append(q)
    if not perguntas:
        raise ValueError("O teste veio sem perguntas válidas.")
    return {"titulo": _texto((dados or {}).get("titulo") or "Teste", 120), "perguntas": perguntas}


def opcoes_associacao(pergunta: dict, semente: str = "") -> list:
    """A coluna B baralhada (sempre igual para o mesmo teste, para não mudar a cada clique)."""
    b = [x["b"] for x in pergunta["pares"]]
    random.Random(pergunta["id"] + semente).shuffle(b)
    return b


def corrigir_objetiva(pergunta: dict, resposta) -> dict:
    """Correção exata das perguntas objetivas. Devolve {"pontos": 0..100, "certa": bool, "feedback": "..."}."""
    tipo = pergunta["tipo"]
    if tipo == "escolha_multipla":
        certa = resposta == pergunta["correta"]
        certo_txt = pergunta["opcoes"][pergunta["correta"]]
        fb = "Certo." if certa else f"A resposta certa é «{certo_txt}»."
        return {"pontos": 100 if certa else 0, "certa": certa, "feedback": (fb + " " + pergunta.get("explicacao", "")).strip()}
    if tipo == "verdadeiro_falso":
        certa = resposta is not None and bool(resposta) == pergunta["verdadeira"]
        fb = "Certo." if certa else f"A afirmação é {'verdadeira' if pergunta['verdadeira'] else 'falsa'}."
        return {"pontos": 100 if certa else 0, "certa": certa, "feedback": (fb + " " + pergunta.get("explicacao", "")).strip()}
    if tipo == "associacao":
        resposta = resposta or {}
        acertos = sum(1 for x in pergunta["pares"] if resposta.get(x["a"]) == x["b"])
        total = len(pergunta["pares"])
        erradas = [f"{x['a']} → {x['b']}" for x in pergunta["pares"] if resposta.get(x["a"]) != x["b"]]
        fb = f"{acertos} de {total} associações certas." + (" Certas: " + "; ".join(erradas) + "." if erradas else "")
        return {"pontos": round(100 * acertos / total), "certa": acertos == total, "feedback": fb}
    raise ValueError("Esta pergunta corrige-se com a IA.")


def pedido_correcao(perguntas: list, respostas: dict, nivel: str) -> str:
    """Instruções para a IA corrigir as perguntas abertas (JSON com pontos, feedback e o que faltou)."""
    itens = []
    for p in perguntas:
        bloco = {"id": p["id"], "tipo": TIPOS[p["tipo"]], "pergunta": p["pergunta"], "criterios": p.get("criterios", []),
                 "resposta_modelo": p.get("resposta_modelo", ""), "resposta_do_aluno": _texto(respostas.get(p["id"]), 4000)}
        for extra in ("documento", "contexto", "titulo_dados"):
            if p.get(extra):
                bloco[extra] = p[extra]
        itens.append(bloco)
    return ("Corrige as respostas deste aluno (nível: " + nivel + ") com rigor e justiça, pelos critérios. Para cada "
            "pergunta dá pontos de 0 a 100, um comentário curto e direto (o que está certo e o que está errado) e a lista "
            "do que faltou. Resposta vazia = 0. Não inventes factos. Português de Portugal.\n"
            + json.dumps(itens, ensure_ascii=False)
            + '\nResponde só com JSON: {"correcoes": [{"id": "...", "pontos": 0, "feedback": "...", "faltou": ["..."]}], '
              '"melhorar": ["2 a 4 conselhos concretos para estudar"]}')


def validar_correcao(dados: dict, ids: list) -> tuple[dict, list]:
    """{id: {"pontos", "certa", "feedback", "faltou"}} e a lista de conselhos. Perguntas sem correção ficam com 0."""
    saida = {}
    for c in (dados or {}).get("correcoes") or []:
        if not isinstance(c, dict) or c.get("id") not in ids:
            continue
        try:
            pontos = max(0, min(100, round(float(c.get("pontos")))))
        except (TypeError, ValueError):
            pontos = 0
        saida[c["id"]] = {"pontos": pontos, "certa": pontos >= 75, "feedback": _texto(c.get("feedback"), 1200),
                          "faltou": [_texto(x, 200) for x in (c.get("faltou") or []) if _texto(x)][:6]}
    for i in ids:
        saida.setdefault(i, {"pontos": 0, "certa": False, "feedback": "Não foi possível corrigir esta resposta.",
                             "faltou": []})
    conselhos = [_texto(x, 300) for x in ((dados or {}).get("melhorar") or []) if _texto(x)][:5]
    return saida, conselhos


def diagnostico(perguntas: list, correcoes: dict) -> dict:
    """Nota final e desempenho por tema (fortes ≥ 75 %, fracos < 50 %)."""
    por_tema = {}
    for p in perguntas:
        c = correcoes.get(p["id"]) or {"pontos": 0}
        por_tema.setdefault(p["tema"], []).append(c["pontos"])
    medias = {t: round(sum(v) / len(v)) for t, v in por_tema.items()}
    nota = round(sum(c["pontos"] for c in (correcoes.get(p["id"]) or {"pontos": 0} for p in perguntas)) / max(1, len(perguntas)))
    return {"nota": nota, "por_tema": medias, "fortes": sorted([t for t, m in medias.items() if m >= 75]),
            "fracos": sorted([t for t, m in medias.items() if m < 50], key=lambda t: medias[t])}


def adaptar(historico: list) -> tuple[str, list]:
    """Dificuldade e temas fracos para o próximo teste, pelos últimos resultados (adaptativo)."""
    recentes = [h for h in (historico or []) if isinstance(h, dict) and "nota" in h][-3:]
    if not recentes:
        return "média", []
    media = sum(h["nota"] for h in recentes) / len(recentes)
    dificuldade = "difícil" if media >= 80 else "fácil" if media < 45 else "média"
    fracos = []
    for h in reversed(recentes):
        for t in h.get("fracos") or []:
            if t not in fracos:
                fracos.append(t)
    return dificuldade, fracos[:6]


def resposta_numerica(texto: str) -> float | None:
    """«1/4», «25%», «0,25», «3:1» (razão → fração do primeiro) → número entre 0 e 1 (ou None)."""
    t = (texto or "").strip().replace(",", ".").replace(" ", "")
    try:
        if t.endswith("%"):
            return float(t[:-1]) / 100
        m = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", t)
        if m:
            return float(m.group(1)) / float(m.group(2))
        m = re.fullmatch(r"(\d+):(\d+)", t)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return a / (a + b) if a + b else None
        return float(t)
    except (ValueError, ZeroDivisionError):
        return None
