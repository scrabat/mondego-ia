"""Desempenho das respostas da IA (sem Streamlit; testado em testes_desempenho.py).

- Lista de modelos em cache (antes: um pedido à Google antes de CADA resposta).
- Memória partilhada de «esta chave não tem pesquisa Google» (antes: cada sessão voltava a falhar em todos os modelos).
- Escolha do modelo pela tarefa: o mais rápido para perguntas simples e títulos, um mais capaz para pedidos complexos.
- Só os excertos dos documentos que interessam à pergunta (antes: ~130 mil caracteres em todas as perguntas).
- Histórico da conversa com um orçamento de caracteres (as mensagens antigas e muito longas são encurtadas).
"""
from __future__ import annotations

import hashlib
import math
import re
import time
import unicodedata

# ---------------------------------------------------------------- caches partilhadas pelo servidor (todas as sessões)
CACHE_MODELOS: dict = {}          # resumo da chave → (quando, lista de modelos)
SEM_PESQUISA_GOOGLE: dict = {}    # resumo da chave → até quando não vale a pena tentar a pesquisa Google
TTL_MODELOS = 3600


def resumo_chave(chave: str) -> str:
    """Identifica a chave sem a guardar (só um resumo de 16 caracteres)."""
    return hashlib.sha256((chave or "").encode()).hexdigest()[:16]


def modelos_em_cache(chave: str, buscar, agora: float | None = None) -> list:
    """Devolve a lista de modelos guardada (até 1 hora); só pergunta à Google quando não há ou expirou.
    Se a Google falhar, usa a última lista conhecida (mesmo antiga) em vez de falhar a resposta."""
    agora = time.time() if agora is None else agora
    r = resumo_chave(chave)
    guardado = CACHE_MODELOS.get(r)
    if guardado and agora - guardado[0] < TTL_MODELOS:
        return list(guardado[1])
    try:
        lista = list(buscar())
    except Exception:  # noqa: BLE001
        if guardado:
            return list(guardado[1])
        raise
    if lista:
        CACHE_MODELOS[r] = (agora, lista)
    return lista


def pesquisa_google_indisponivel(chave: str, agora: float | None = None) -> bool:
    return (time.time() if agora is None else agora) < SEM_PESQUISA_GOOGLE.get(resumo_chave(chave), 0)


def marcar_sem_pesquisa_google(chave: str, segundos: float = 1800, agora: float | None = None) -> None:
    SEM_PESQUISA_GOOGLE[resumo_chave(chave)] = (time.time() if agora is None else agora) + segundos


# ---------------------------------------------------------------- tipo de tarefa (escolha do modelo)
_COMPLEXO = re.compile(
    r"passo a passo|step by step|demonstr|prova que|prove|resolv|resolu|calcul|deriva|integra|equa[cç]|limite d|"
    r"exerc[ií]cio|problema|c[oó]digo|program|algoritmo|fun[cç][aã]o recursiva|debug|erro no|compar|analis|"
    r"ensaio|desenvolv|disserta|porqu[eê] |justifica|critica|avalia|relaciona|explica .{0,40} detalh|"
    r"[=∫∑√^]|\\frac|\\int|\d\s*[x×*/]\s*\d", re.I)


def complexidade(texto: str, anexos: bool = False, resposta_anterior: str = "") -> str:
    """«simples» (resposta direta, factual, curta) ou «complexa» (raciocínio, contas, código, análise, documentos)."""
    t = texto or ""
    if anexos or len(t) > 280 or _COMPLEXO.search(t) or len(resposta_anterior or "") > 2500:
        return "complexa"
    return "simples"


def ordenar_modelos(modelos: list, velocidade: str, tarefa: str = "normal") -> list:
    """Ordem dos modelos do Gemini para a tarefa:
    - «leve» (títulos, classificar a pesquisa): sempre o mais rápido (flash-lite) primeiro;
    - «simples»: o mais rápido na velocidade «Rápida»;
    - «complexa»: um modelo flash completo primeiro mesmo na velocidade «Rápida» (melhor raciocínio);
    - velocidades «Equilibrada» e «Máxima qualidade»: flash completo primeiro.
    Dentro de cada família, a versão mais recente e estável primeiro."""
    rapido = tarefa == "leve" or (velocidade == "Rápida" and tarefa != "complexa")

    def versao(nome: str) -> float:
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", nome)
        return float(m.group(1)) if m else 0.0

    def ordem(m: str):
        instavel = "preview" in m or "exp" in m
        rapido_m = "flash" in m or "hydrogen" in m  # «hydrogen»: a família rápida e equilibrada do Gemini 4
        familia = 0 if ("flash-lite" in m) == rapido and rapido_m else 1 if rapido_m else 2
        return (instavel, familia, -versao(m))

    return sorted(modelos, key=ordem)


# ---------------------------------------------------------------- quanto o modelo «pensa» antes de responder
# Pensar mais dá respostas melhores nas perguntas difíceis, mas atrasa o início da resposta. Os modelos Gemini 3 pensam
# sempre; o nível escolhe-se com thinking_level («minimal» só existe em alguns: 3.5 Flash-Lite, 3.6 Flash, 3 Flash).
def versao(nome: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", nome or "")
    return float(m.group(1)) if m else 0.0


def aceita_minimo(modelo: str) -> bool:
    m = (modelo or "").lower()
    if "pro" in m or "carbon" in m or "hydrogen" in m:
        return False
    return "flash-lite" in m or (("flash" in m) and versao(m) < 3.8 and versao(m) >= 3)


def nivel_pensamento(modelo: str, tarefa: str, velocidade: str):
    """("level", nível) ou ("budget", tokens) para o pedido; None = o que o modelo faz por omissão.
    - «Máxima qualidade»: o modelo decide (pensa o que precisar);
    - títulos, classificações e perguntas simples: o mínimo possível (resposta quase imediata);
    - perguntas complexas na velocidade «Equilibrada»: médio (melhor raciocínio);
    - o resto: baixo (rápido, mas ainda pensa um pouco)."""
    if velocidade == "Máxima qualidade":
        return None
    if (modelo or "").startswith("gemini-2"):
        return ("budget", 0 if velocidade == "Rápida" and tarefa != "complexa" else 1024)
    if tarefa in ("leve", "simples"):
        return ("level", "minimal" if aceita_minimo(modelo) else "low")
    if tarefa == "complexa" and velocidade == "Equilibrada":
        return ("level", "medium")
    return ("level", "low")


def aceita_temperatura(modelo: str) -> bool:
    """Os modelos Gemini 4 e Gemini 3.6+ ignoram a temperatura (a Google pede para não a enviar)."""
    m = (modelo or "").lower()
    return not ("hydrogen" in m or "carbon" in m or versao(m) >= 3.6 or versao(m) >= 4)


# ---------------------------------------------------------------- excertos relevantes dos documentos
_PARAGENS = set("""
como para isso esta este estes estas qual quais sobre porque quando onde mais menos muito muita muitos muitas pode podes
fazer explica explicar explicame quero queria entre tambem ainda depois antes entao cada outro outra outros outras seja
sera pelo pela pelos pelas numa nuns umas aqui isto aquilo tudo todos todas nada algo alguem tens tenho fala diga dizer
qualquer coisa coisas exemplo exemplos passo resumo resume resumir ajuda ajudar preciso favor podia poderia sabes saber
what which with from that this have about explain please could would should there their they them then than when where
also into your sera serao estao esta tem temos sao foram fosse forem dela dele delas deles nesta neste nessa
nesse essa esse essas esses minha minhas meus teus tuas nosso nossa vosso vossa ainda agora hoje ontem amanha
quem quanto quanta quantos quantas porque assim sempre nunca talvez sobre ganha ganhou
""".split())


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def termos(texto: str) -> list:
    """Palavras com significado (4+ letras, sem acentos, sem palavras comuns)."""
    return [p for p in re.findall(r"[a-z0-9]{4,}", _sem_acentos(texto or "")) if p not in _PARAGENS]


def selecionar_relevante(ficheiros: dict, consulta: str, limite: int, bloco: int = 3000) -> tuple[str, int]:
    """Excertos que interessam à pergunta, por relevância (palavras raras valem mais: tf·idf). Sem nenhum excerto
    relevante devolve ("", 0): a IA não recebe páginas de documentos que nada têm a ver com a pergunta.
    Devolve (texto, número de excertos)."""
    completo = "\n\n".join(f"=== FICHEIRO: {n} ===\n{t}" for n, t in ficheiros.items() if t)
    pedidos = set(termos(consulta))
    if not completo or not pedidos:
        return "", 0
    blocos = [(nome, i, texto[i:i + bloco]) for nome, texto in ficheiros.items() if texto
              for i in range(0, len(texto), bloco)]
    normais = [_sem_acentos(b[2]) for b in blocos]
    df = {t: sum(1 for b in normais if t in b) for t in pedidos}
    n = len(blocos)
    pesos = {t: math.log((n + 1) / (df[t] + 0.5)) for t in pedidos if df[t]}
    if not pesos:
        return "", 0
    # Cobertura: que parte (pesada pela raridade) das palavras da pergunta aparece no excerto. As palavras que não
    # existem nos documentos contam como as mais raras: «Quem ganhou o Nobel da Física?» não é sobre apontamentos de
    # programação só por terem a palavra «quem».
    peso_max = math.log((n + 1) / 0.5)
    total = sum(pesos.get(t, peso_max) for t in pedidos)
    minimo = 0.5 if len(pedidos) <= 3 else 0.3
    pontuados = []
    for (nome, i, texto), normal in zip(blocos, normais):
        presentes = [t for t in pesos if t in normal]
        if not presentes or sum(pesos[t] for t in presentes) / total < minimo:
            continue
        pontos = sum(pesos[t] * (1 + math.log(normal.count(t))) for t in presentes)
        pontuados.append((pontos, nome, i, texto))
    if not pontuados:
        return "", 0
    if len(completo) <= limite and len(pontuados) >= max(1, n // 2):  # documentos curtos e quase todos relevantes
        return completo, n
    n_max = max(1, limite // (bloco + 60))
    escolhidos = sorted(pontuados, key=lambda b: b[0], reverse=True)[:n_max]
    escolhidos.sort(key=lambda b: (b[1], b[2]))
    return "\n\n".join(f"=== EXCERTO DE: {nome} ===\n{texto}" for _, nome, _, texto in escolhidos), len(escolhidos)


# ---------------------------------------------------------------- histórico da conversa enviado à IA
def contexto_conversa(mensagens: list, max_mensagens: int = 16, orcamento: int = 24_000, por_mensagem: int = 6000) -> list:
    """As mensagens mais recentes que cabem no orçamento; as longas e antigas ficam encurtadas (a mais recente fica
    sempre inteira até ao limite). Começa sempre numa mensagem do aluno."""
    escolhidas, total = [], 0
    for k, m in enumerate(reversed(list(mensagens or [])[-max_mensagens:])):
        texto = str(m.get("content") or "")
        restante = orcamento - total
        if restante <= 300:
            break
        limite = restante if k == 0 else min(restante, por_mensagem)
        if len(texto) > limite:
            texto = texto[:limite] + "\n[…]"
        escolhidas.append({"role": m.get("role"), "content": texto})
        total += len(texto)
    escolhidas.reverse()
    while escolhidas and escolhidas[0]["role"] != "user":
        escolhidas.pop(0)
    return escolhidas
