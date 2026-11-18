"""
Repetição espaçada para flashcards (sistema de caixas de Leitner).

Cada cartão tem uma "caixa" de 0 (novo) a 5 (dominado). Quando acertas, sobe de caixa e volta a aparecer
mais tarde; quando erras, volta à caixa 1 e repete no mesmo dia.
"""

from datetime import date, timedelta

INTERVALOS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}  # dias até voltar a aparecer, por caixa
NOMES_CAIXAS = {0: "Novos", 1: "A aprender", 2: "A rever", 3: "Quase", 4: "Sei bem", 5: "Dominados"}


def preparar(cartao: dict) -> dict:
    cartao.setdefault("caixa", 0)
    cartao.setdefault("proxima", None)
    cartao.setdefault("vistas", 0)
    cartao.setdefault("acertos", 0)
    return cartao


def devido(cartao: dict, hoje: date) -> bool:
    preparar(cartao)
    return cartao["proxima"] is None or date.fromisoformat(cartao["proxima"]) <= hoje


def devidos(cartoes: list, hoje: date) -> list:
    """Índices dos cartões para rever hoje (novos primeiro, depois os mais atrasados)."""
    idx = [i for i, c in enumerate(cartoes) if devido(c, hoje)]
    return sorted(idx, key=lambda i: (cartoes[i]["caixa"] != 0, cartoes[i]["proxima"] or ""))


def responder(cartao: dict, resposta: str, hoje: date) -> dict:
    """resposta: 'errei', 'dificil' ou 'sabia'."""
    preparar(cartao)
    if resposta == "errei":
        cartao["caixa"] = 1
        cartao["proxima"] = hoje.isoformat()
    elif resposta == "dificil":
        cartao["caixa"] = max(1, cartao["caixa"])
        cartao["proxima"] = (hoje + timedelta(days=1)).isoformat()
    elif resposta == "sabia":
        cartao["caixa"] = min(5, cartao["caixa"] + 1)
        cartao["proxima"] = (hoje + timedelta(days=INTERVALOS[cartao["caixa"]])).isoformat()
        cartao["acertos"] += 1
    else:
        raise ValueError(f"Resposta desconhecida: {resposta}")
    cartao["vistas"] += 1
    return cartao


def juntar_progresso(novos: list, antigos: list) -> list:
    """Ao gerar cartões novos, mantém o progresso dos cartões com a mesma frente."""
    por_frente = {(c.get("frente") or "").strip().lower(): c for c in antigos or []}
    resultado = []
    for c in novos:
        antigo = por_frente.get((c.get("frente") or "").strip().lower())
        if antigo:
            c.update({k: antigo[k] for k in ("caixa", "proxima", "vistas", "acertos") if k in antigo})
        resultado.append(preparar(c))
    return resultado


def resumo(cartoes: list, hoje: date) -> dict:
    caixas = {k: 0 for k in NOMES_CAIXAS}
    for c in cartoes:
        caixas[preparar(c)["caixa"]] += 1
    return {"caixas": caixas, "para_hoje": len(devidos(cartoes, hoje)),
            "dominados": caixas[4] + caixas[5], "total": len(cartoes)}
