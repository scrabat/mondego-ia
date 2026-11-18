"""
Histórico das conversas do Assistente, organizado como no Claude:
- conversas fixadas no topo e as outras agrupadas por data (Hoje, Ontem, Últimos 7 dias, Últimos 30 dias, Mais antigas);
- pesquisa no título e no conteúdo (sem diferença entre maiúsculas e acentos);
- título provisório (o início da pergunta) e título curto feito pela IA depois da primeira resposta.
Não depende do Streamlit (testes_historico.py).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

GRUPOS = ["Fixadas", "Hoje", "Ontem", "Últimos 7 dias", "Últimos 30 dias", "Mais antigas"]
LIMITE = 30  # conversas mostradas na barra lateral antes de «Mostrar todas»

PEDIDO_TITULO = (
    "Dá um título curto a esta conversa: 3 a 6 palavras que digam o tema, na língua da pergunta (em português, "
    "português de Portugal), sem aspas, sem emojis e sem ponto final. Responde só com o título.\n\n"
    "Pergunta do aluno: {pergunta}\n\nInício da resposta: {resposta}"
)


def _simples(texto: str) -> str:
    """Minúsculas e sem acentos (para pesquisar)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def _dia(iso) -> date | None:
    try:
        return datetime.fromisoformat(str(iso)).date()
    except (TypeError, ValueError):
        return None


def grupo_da_data(iso, hoje: date) -> str:
    """Em que grupo fica uma conversa atualizada em `iso` (data ISO)."""
    d = _dia(iso)
    if d is None:
        return "Mais antigas"
    dias = (hoje - d).days
    if dias <= 0:
        return "Hoje"
    if dias == 1:
        return "Ontem"
    if dias < 7:
        return "Últimos 7 dias"
    if dias < 30:
        return "Últimos 30 dias"
    return "Mais antigas"


def corresponde(conversa: dict, consulta: str) -> bool:
    """Todas as palavras da pesquisa aparecem no título ou nas mensagens."""
    palavras = _simples(consulta).split()
    if not palavras:
        return True
    texto = _simples(" ".join([str(conversa.get("titulo") or "")] + [
        str(m.get("content") or "") for m in conversa.get("mensagens") or [] if isinstance(m, dict)]))
    return all(p in texto for p in palavras)


def ordenar(conversas: dict) -> list:
    """[(id, conversa)], da mais recente para a mais antiga."""
    return sorted(((cid, c) for cid, c in (conversas or {}).items() if isinstance(c, dict)),
                  key=lambda kv: str(kv[1].get("atualizada") or kv[1].get("criada") or ""), reverse=True)


def agrupar(conversas: dict, hoje: date, consulta: str = "", limite: int | None = LIMITE) -> tuple[list, int]:
    """Devolve ([(grupo, [(id, conversa), ...]), ...], quantas ficaram escondidas pelo limite).
    Com pesquisa: um só grupo «Resultados». Sem pesquisa: «Fixadas» (sempre todas) e os grupos por data."""
    itens = [(cid, c) for cid, c in ordenar(conversas) if corresponde(c, consulta)]
    if consulta.strip():
        mostrar = itens[:limite] if limite else itens
        return ([("Resultados", mostrar)] if mostrar else []), len(itens) - len(mostrar)
    fixadas = [x for x in itens if x[1].get("fixada")]
    outras = [x for x in itens if not x[1].get("fixada")]
    escondidas = max(0, len(outras) - limite) if limite else 0
    if limite:
        outras = outras[:limite]
    por_grupo: dict = {}
    for cid, c in outras:
        por_grupo.setdefault(grupo_da_data(c.get("atualizada") or c.get("criada"), hoje), []).append((cid, c))
    grupos = [("Fixadas", fixadas)] if fixadas else []
    grupos += [(g, por_grupo[g]) for g in GRUPOS[1:] if g in por_grupo]
    return grupos, escondidas


def titulo_provisorio(texto: str) -> str:
    """O início da pergunta, até à IA dar um título melhor."""
    t = re.sub(r"\s+", " ", texto or "").strip()
    return (t[:42] + "…") if len(t) > 42 else t or "Conversa"


def limpar_titulo(texto: str) -> str | None:
    """Título da IA pronto a mostrar, ou None se não servir (vazio, comprido demais, JSON, várias frases...)."""
    linhas = [l.strip() for l in str(texto or "").splitlines() if l.strip()]
    if not linhas:
        return None
    t = re.sub(r"^(t[ií]tulo|title)\s*:\s*", "", linhas[0], flags=re.IGNORECASE)
    t = t.strip(" \t\"'«»“”‘’*#`").rstrip(".!:;,").strip(" \t\"'«»“”‘’*#`")
    t = re.sub(r"\s+", " ", t)
    if not t or t[0] in "{[<" or len(t) > 60 or len(t.split()) > 10:
        return None
    return t[0].upper() + t[1:]
