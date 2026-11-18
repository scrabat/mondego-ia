"""
Planos de estudo do Mondego IA — regras que não dependem do Streamlit (testadas em testes_plano.py).

O plano diz O QUE estudar em cada dia — nunca a que horas nem quanto tempo. É uma lista de tarefas:
    {"data": "AAAA-MM-DD", "cadeira": "...", "tipo": "Estudar|Praticar|Rever|Testar|Projeto",
     "temas": "o que fazer, em concreto", "tema": "tema da matéria", "ordem": 3, "final": False}
(«temas» guarda o texto da tarefa porque é com ele que a app identifica as tarefas feitas: data|cadeira|temas.)

A IA lê a matéria e devolve os TEMAS de cada cadeira (dificuldade, importância e as tarefas concretas de cada tema).
A distribuição pelos dias é feita aqui, sempre da mesma maneira:
- cada tema: estudar → praticar (exercícios) → revisões espaçadas (mais revisões nos temas difíceis e importantes);
- as cadeiras são intercaladas e a matéria nova de cada uma é espalhada por igual até à avaliação;
- nos últimos dias antes de cada avaliação: revisão geral e um teste de treino;
- nenhum dia passa o ritmo escolhido (tarefas por dia), a não ser que falte tempo para dar a matéria toda;
- reorganizar volta a espalhar o que ficou por fazer pelos dias que faltam, sem acumular tudo no mesmo dia.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
TIPOS_TAREFA = ["Estudar", "Praticar", "Rever", "Testar", "Projeto"]
TIPOS_SESSAO = TIPOS_TAREFA  # nome antigo
LEGADO_TIPOS = {"Teoria": "Estudar", "Exercícios": "Praticar", "Revisão": "Rever", "Teste": "Testar"}
RITMOS = {"Leve": 3, "Equilibrado": 4, "Intenso": 6}  # máximo de tarefas por dia (todas as cadeiras juntas)
COMECAR = ["Pelos temas mais difíceis", "Pelas bases, do mais fácil ao mais difícil"]
ESTILOS = ["Equilibrado", "Mais teoria", "Mais exercícios", "Muitos testes e exames antigos"]
DIFICULDADES = ["Fácil", "Média", "Difícil"]
IMPORTANCIAS = ["Baixa", "Média", "Alta"]
PREFS_PADRAO = {"folga": [], "ritmo": "Equilibrado", "comecar": COMECAR[0], "estilo": ESTILOS[0]}
# revisões espaçadas: quantos dias depois de estudar o tema (mais e mais cedo nos temas difíceis)
REVISOES = {"Fácil": [4], "Média": [2, 6], "Difícil": [1, 3, 7]}
MAX_TEMAS = 14       # por cadeira
MAX_TEXTO = 140      # caracteres de cada tarefa
SEM_AVALIACAO_DIAS = 14  # cadeira sem avaliação marcada: plano para as próximas duas semanas
CAMPOS_DO_DIA = ("data", "ordem", "hora", "duracao_min")


# ---------------------------------------------------------------- utilitários
def para_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor or "")[:10])
    except ValueError:
        return None


def limpar(texto, maximo: int = MAX_TEXTO) -> str:
    """Uma linha, sem espaços a mais, sem ponto final e no máximo «maximo» caracteres."""
    t = " ".join(str(texto or "").split()).strip(" .;")
    return t if len(t) <= maximo else t[: maximo - 1].rstrip() + "…"


def minuscula(tema: str) -> str:
    """«Limites» → «limites» para ir a meio de uma frase («Estudar limites»); siglas (ADN, PIB) ficam como estão."""
    return tema[:1].lower() + tema[1:] if len(tema) > 1 and tema[1].islower() else tema


def tipo_de(tarefa: dict) -> str:
    t = tarefa.get("tipo")
    return t if t in TIPOS_TAREFA else LEGADO_TIPOS.get(t, "Estudar")


def id_sessao(sessao: dict, cadeira: str | None = None) -> str:
    """O mesmo identificador que o resto da app usa para marcar tarefas feitas: data|cadeira|temas."""
    return f"{str(sessao.get('data', ''))[:10]}|{sessao.get('cadeira') or cadeira}|{sessao.get('temas')}"


def ids_do_plano(dias: list, cadeira: str | None = None) -> set:
    return {id_sessao(s, cadeira) for s in dias}


def ordenar(tarefas: list) -> list:
    """Por dia; dentro do dia pela ordem do plano (planos antigos, sem ordem: pela hora que tinham)."""
    return sorted(tarefas, key=lambda s: (str(s.get("data", "")), s.get("ordem", 10 ** 6),
                                          str(s.get("hora") or "99:99"), str(s.get("cadeira") or "")))


def texto_da_tarefa(tarefa: dict) -> tuple[str, str]:
    """(o que fazer, pormenor opcional). Planos antigos tinham o tema em «temas» e o que fazer em «tarefas»."""
    principal = limpar(tarefa.get("temas") or "Estudar", 300)
    detalhe = limpar(tarefa.get("tarefas") or "", 300)
    return principal, ("" if detalhe.lower() == principal.lower() else detalhe)


def dias_de_estudo(inicio: date, fim_exclusivo: date, folga) -> list:
    """Dias de «inicio» até ao dia antes de «fim_exclusivo», sem os dias da semana de folga."""
    dias, d = [], inicio
    while d < fim_exclusivo:
        if DIAS_SEMANA[d.weekday()] not in (folga or []):
            dias.append(d)
        d += timedelta(days=1)
    return dias


def preferencias(guardadas: dict | None, perfil: dict | None = None) -> dict:
    """Preferências do plano: dias de folga, ritmo (tarefas por dia), por onde começar e estilo.
    Aproveita o que já existia: a folga do perfil (ou do horário antigo, nos dias sem horas) e as horas por dia."""
    guardadas, perfil = guardadas or {}, perfil or {}
    prefs = dict(PREFS_PADRAO)
    folga = guardadas.get("folga")
    if folga is None and isinstance(guardadas.get("horario"), dict):  # preferências antigas, com horário semanal
        folga = [d for d in DIAS_SEMANA if not guardadas["horario"].get(d)]
    if folga is None:
        folga = perfil.get("folga") or []
    prefs["folga"] = [d for d in DIAS_SEMANA if d in folga]
    if guardadas.get("ritmo") in RITMOS:
        prefs["ritmo"] = guardadas["ritmo"]
    else:
        try:
            horas = int(guardadas.get("horas_dia") or perfil.get("horas_dia") or 2)
        except (TypeError, ValueError):
            horas = 2
        prefs["ritmo"] = "Leve" if horas <= 1 else "Intenso" if horas >= 4 else "Equilibrado"
    for k, opcoes in (("comecar", COMECAR), ("estilo", ESTILOS)):
        if guardadas.get(k) in opcoes:
            prefs[k] = guardadas[k]
    if len(prefs["folga"]) == 7:  # pelo menos um dia de estudo
        prefs["folga"] = []
    prefs["por_dia"] = RITMOS[prefs["ritmo"]]
    return prefs


# ---------------------------------------------------------------- temas propostos pela IA
def _nivel(valor, opcoes: list, padrao: str) -> str:
    v = str(valor or "").strip().lower()
    for o in opcoes:
        if v and (v == o.lower() or o.lower().startswith(v[:4])):
            return o
    mapa = {"easy": "Fácil", "facil": "Fácil", "medium": "Média", "media": "Média", "hard": "Difícil",
            "dificil": "Difícil", "low": "Baixa", "high": "Alta"}
    if mapa.get(v) in opcoes:
        return mapa[v]
    if v in ("1", "2", "3"):
        return opcoes[int(v) - 1]
    return padrao


def _chave(nome) -> str:
    """Nome de cadeira para comparar: sem acentos, maiúsculas nem espaços a mais («Introdução à Programação»)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def validar_unidades(resposta, cadeiras_validas, cadeira_fixa: str | None = None) -> dict:
    """{cadeira: [temas]} a partir da resposta da IA. Cada tema: tema, dificuldade, importância e as tarefas
    («estudar», «praticar», «rever»); o que faltar é completado. Tira temas repetidos, cadeiras desconhecidas e lixo."""
    if not isinstance(resposta, dict):
        return {}
    blocos = resposta.get("cadeiras")
    if not isinstance(blocos, list) and isinstance(resposta.get("dias"), list) and not resposta.get("temas"):
        # a IA respondeu no formato antigo (sessões por dia): aproveitam-se os temas, pela ordem em que vinham
        grupos: dict = {}
        for d in resposta["dias"]:
            if isinstance(d, dict) and d.get("temas"):
                grupos.setdefault(cadeira_fixa or str(d.get("cadeira") or "").strip(), []).append(
                    {"tema": d["temas"], "praticar": d.get("tarefas")} if d.get("tarefas") else {"tema": d["temas"]})
        blocos = [{"cadeira": c, "temas": t} for c, t in grupos.items()]
    if not isinstance(blocos, list):
        blocos = [{"cadeira": cadeira_fixa, "temas": resposta.get("temas") or resposta.get("_lista") or []}]
    blocos = [b for b in blocos if isinstance(b, dict)]
    nomes = {_chave(c): c for c in cadeiras_validas}
    if cadeira_fixa:  # plano de uma cadeira: os blocos de outras cadeiras não contam (se a IA trocou o nome, aceita-se)
        certos = [b for b in blocos if _chave(b.get("cadeira")) == _chave(cadeira_fixa)]
        blocos = certos or [b for b in blocos if _chave(b.get("cadeira")) not in nomes]
    unidades: dict = {}
    for b in blocos:
        cadeira = cadeira_fixa or nomes.get(_chave(b.get("cadeira")))
        if cadeira not in cadeiras_validas:
            continue
        lista = unidades.setdefault(cadeira, [])
        vistos = {u["tema"].lower() for u in lista}
        for t in b.get("temas") or []:
            if isinstance(t, str):
                t = {"tema": t}
            if not isinstance(t, dict):
                continue
            tema = limpar(t.get("tema") or t.get("nome"), 80)
            if not tema or tema.lower() in vistos or len(lista) >= MAX_TEMAS:
                continue
            vistos.add(tema.lower())
            lista.append({
                "tema": tema,
                "dificuldade": _nivel(t.get("dificuldade"), DIFICULDADES, "Média"),
                "importancia": _nivel(t.get("importancia") or t.get("importância"), IMPORTANCIAS, "Média"),
                "estudar": limpar(t.get("estudar")) or f"Estudar {minuscula(tema)}",
                "praticar": limpar(t.get("praticar")) or f"Resolver exercícios sobre {minuscula(tema)}",
                "rever": limpar(t.get("rever")) or f"Rever {minuscula(tema)}",
            })
    return {c: l for c, l in unidades.items() if l}


def ordenar_unidades(lista: list, comecar: str) -> list:
    """Pelas bases: a ordem da matéria (a da IA). Pelos difíceis: primeiro os difíceis e importantes (sem perder a
    ordem da matéria entre temas do mesmo nível)."""
    if comecar == COMECAR[0]:
        peso = {"Difícil": 0, "Média": 1, "Fácil": 2}
        imp = {"Alta": 0, "Média": 1, "Baixa": 2}
        return sorted(lista, key=lambda u: (peso[u["dificuldade"]], imp[u["importancia"]]))
    return list(lista)


# ---------------------------------------------------------------- distribuição pelos dias
def _tarefa(cadeira: str, tipo: str, texto: str, tema: str = "", final: bool = False) -> dict:
    return {"cadeira": cadeira, "tipo": tipo, "temas": limpar(texto), "tema": tema, "final": final}


def _juntar(estudar: str, praticar: str) -> str:
    """Pouco tempo: «Estudar limites e resolver exercícios sobre limites» numa só tarefa."""
    p = praticar[:1].lower() + praticar[1:] if praticar[1:2].islower() else praticar
    return limpar(f"{estudar}; depois, {p}", 220)


def _texto_revisao(u: dict, j: int) -> str:
    """Cada revisão do mesmo tema pede uma coisa diferente (nada de tarefas repetidas)."""
    t = minuscula(u["tema"])
    return [u["rever"], f"Rever {t} sem consultar os apontamentos", f"Explicar {t} por palavras tuas e confirmar",
            f"Responder a perguntas rápidas sobre {t}"][min(j, 3)]


def _dias_finais(dias: list, com_avaliacao: bool) -> tuple[list, list]:
    """(dias para a matéria, dias para a revisão geral e o teste de treino)."""
    if not com_avaliacao or len(dias) < 2:
        return dias, []
    n = 1 if len(dias) <= 4 else 2
    return (dias[:-n] or dias), dias[-n:]


def _agendar(cadeiras: dict, cap: int, revisoes: list | None = None, ocupados: dict | None = None) -> tuple[list, dict]:
    """O coração do plano. cadeiras = {nome: {"conteudo": [dias], "seq": [tarefas por ordem], "finais": [(dia, tarefa)],
    "ordem": n}}. A matéria de cada cadeira é espalhada por igual pelos seus dias (alvo acumulado), os dias que passam
    do ritmo adiam tarefas das cadeiras com mais dias pela frente, e o espaço que sobra leva as revisões espaçadas
    (revisoes = [{"cadeira", "tema", "tarefa", "depois": dias após estudar o tema, "ja_estudado", "tipo"}]).
    ocupados = {dia: n}: tarefas que já lá estão (feitas) e contam para o ritmo desse dia."""
    ocupados = ocupados or {}
    pendentes_rev = list(revisoes or [])
    estado = {c: {"i": 0, "pos": {d: k for k, d in enumerate(p["conteudo"])}} for c, p in cadeiras.items()}
    todos = sorted({d for p in cadeiras.values() for d in p["conteudo"]} |
                   {d for p in cadeiras.values() for d, _ in p["finais"]})
    dia_estudado: dict = {}   # (cadeira, tema) -> dia em que o tema foi estudado
    candidatas: list = []     # revisões à espera de um dia com espaço
    resultado, cheios, cortadas, ordem = [], [], 0, 0
    peso_tipo = {t: i for i, t in enumerate(TIPOS_TAREFA)}
    precisa = [math.ceil(len(p["seq"]) / len(p["conteudo"])) for p in cadeiras.values() if p["conteudo"]]
    total_fixo = sum(len(p["seq"]) + len(p["finais"]) for p in cadeiras.values())
    limite_dia = max([cap, math.ceil(total_fixo / len(todos)) if todos else cap] + precisa)

    def fim_revisoes(c):  # as revisões podem ir até à véspera da avaliação (também nos dias da revisão geral)
        p = cadeiras[c]
        return max([d for d, _ in p["finais"]] + p["conteudo"][-1:], default=None)

    dias_da = {c: set(p["conteudo"]) | {d for d, _ in p["finais"]} for c, p in cadeiras.items()}

    for dia in todos:
        do_dia: list = [t for p in cadeiras.values() for d, t in p["finais"] if d == dia]
        escolhidas: dict = {}
        for c, p in cadeiras.items():
            e = estado[c]
            if dia not in e["pos"] or e["i"] >= len(p["seq"]):
                continue
            k, n, total = e["pos"][dia] + 1, len(p["conteudo"]), len(p["seq"])
            quota = max(0, math.ceil(total * k / n) - e["i"])
            escolhidas[c] = p["seq"][e["i"]: e["i"] + quota]
            e["i"] += len(escolhidas[c])
        # dia acima do ritmo: adia uma tarefa de cada vez da cadeira com mais folga nos dias que lhe faltam;
        # se nenhuma tiver folga, o dia fica mais cheio (é melhor do que acumular tudo no último dia)
        def depois(x):  # (dias que faltam à cadeira depois de hoje, tarefas por dia que teria de fazer nesses dias)
            n = len(cadeiras[x]["conteudo"]) - estado[x]["pos"][dia] - 1
            return n, (len(cadeiras[x]["seq"]) - estado[x]["i"] + 1) / n if n else math.inf
        while len(do_dia) + sum(len(v) for v in escolhidas.values()) + ocupados.get(dia, 0) > limite_dia:
            adiaveis = [c for c, v in escolhidas.items() if v and depois(c)[0] > 0 and depois(c)[1] <= limite_dia]
            if not adiaveis:
                break
            c = min(adiaveis, key=lambda x: (depois(x)[1], -cadeiras[x].get("ordem", 0)))
            escolhidas[c].pop()
            estado[c]["i"] -= 1
        for c in escolhidas:
            do_dia.extend(escolhidas[c])
        # revisões espaçadas: ficam à espera do dia certo e entram quando há espaço
        for r in list(pendentes_rev):
            base = (todos[0] - timedelta(days=1)) if r.get("ja_estudado") else dia_estudado.get((r["cadeira"], r["tema"]))
            if base is not None:
                ate = fim_revisoes(r["cadeira"])
                cedo = base + timedelta(days=r["depois"])
                if ate and cedo > ate:  # não há tantos dias: a revisão fica para o último dia antes da revisão geral
                    cedo = max(base + timedelta(days=1), ate)
                candidatas.append({**r, "cedo": cedo, "ate": ate})
                pendentes_rev.remove(r)
        livres = cap - len(do_dia) - ocupados.get(dia, 0)
        if len(do_dia) and len(do_dia) + ocupados.get(dia, 0) > cap:
            cheios.append(dia.isoformat())
        temas_hoje = {(t["cadeira"], t.get("tema")) for t in do_dia if t.get("tema")}
        for r in sorted(candidatas, key=lambda x: (x["ate"] or dia, x["cedo"])):
            if livres <= 0:
                break
            if (r["cedo"] <= dia <= (r["ate"] or dia) and dia in dias_da[r["cadeira"]]
                    and (r["cadeira"], r["tema"]) not in temas_hoje):
                do_dia.append(_tarefa(r["cadeira"], r.get("tipo", "Rever"), r["tarefa"], r["tema"]))
                temas_hoje.add((r["cadeira"], r["tema"]))
                candidatas.remove(r)
                livres -= 1
        for t in do_dia:
            if t.get("tipo") == "Estudar" and t.get("tema"):
                dia_estudado.setdefault((t["cadeira"], t["tema"]), dia)
        antes = len(candidatas)
        candidatas = [r for r in candidatas if (r["ate"] or dia) > dia]
        cortadas += antes - len(candidatas)
        # dentro do dia: cadeira a cadeira (a da avaliação mais próxima primeiro); em cada uma estudar → praticar → rever
        vistos = set()
        for t in sorted(do_dia, key=lambda x: (cadeiras[x["cadeira"]].get("ordem", 0), peso_tipo.get(x.get("tipo"), 9))):
            chave = (t["cadeira"], t["temas"].lower())
            if chave in vistos:  # a mesma tarefa duas vezes no mesmo dia: só uma
                continue
            vistos.add(chave)
            ordem += 1
            resultado.append({**t, "data": dia.isoformat(), "ordem": ordem})
    cortadas += len(candidatas) + len(pendentes_rev)
    return resultado, {"cheios": sorted(set(cheios)), "revisoes_cortadas": cortadas}


def distribuir(unidades: dict, limites: dict, hoje: date, prefs: dict, estudados: dict | None = None,
               ocupados: dict | None = None) -> tuple[list, dict]:
    """Plano novo. unidades = {cadeira: [temas]} (validar_unidades); limites = {cadeira: data da avaliação ou None};
    estudados = {cadeira: {temas já estudados}} — não voltam a ser dados, só revistos;
    ocupados = {dia: n} tarefas feitas que já estão nesse dia (contam para o ritmo).
    Devolve (tarefas ordenadas, informação: dias acima do ritmo, cadeiras sem dias, revisões que não couberam)."""
    prefs = preferencias(prefs)
    estudados = {c: {t.lower() for t in v} for c, v in (estudados or {}).items()}
    estilo = prefs["estilo"]
    cadeiras, revisoes, sem_dias = {}, [], []
    por_data = sorted(unidades, key=lambda c: (limites.get(c) or date.max, c))
    for ordem_c, c in enumerate(por_data):
        lista = unidades.get(c) or []
        if not lista:
            continue
        fim = limites.get(c) or hoje + timedelta(days=SEM_AVALIACAO_DIAS)
        dias = dias_de_estudo(hoje, fim, prefs["folga"])
        if not dias:
            sem_dias.append(c)
            continue
        conteudo, finais_d = _dias_finais(dias, bool(limites.get(c)))
        seq = []
        ordem_u = ordenar_unidades(lista, prefs["comecar"])
        novos = [u for u in ordem_u if u["tema"].lower() not in estudados.get(c, set())]
        apertado = 2 * len(novos) > len(conteudo) * prefs["por_dia"] / 2   # a matéria ocupa mais de metade do ritmo
        longo = len(conteudo) >= 21
        for k, u in enumerate(ordem_u, start=1):
            tema = u["tema"]
            ja = tema.lower() in estudados.get(c, set())
            if not ja and apertado:
                seq.append(_tarefa(c, "Estudar", "", tema) | {"temas": _juntar(u["estudar"], u["praticar"])})
            elif not ja:
                seq.append(_tarefa(c, "Estudar", u["estudar"], tema))
                if not (estilo == "Mais teoria" and u["dificuldade"] == "Fácil"):
                    seq.append(_tarefa(c, "Praticar", u["praticar"], tema))
            if estilo == ESTILOS[3] and k % 3 == 0 and k < len(ordem_u):
                seq.append(_tarefa(c, "Testar", "Fazer um mini-teste sobre " +
                                   ", ".join(minuscula(x["tema"]) for x in ordem_u[k - 3:k])))
            intervalos = [2] if ja else list(REVISOES[u["dificuldade"]])
            if u["importancia"] == "Alta" and not ja and len(intervalos) < 3:
                intervalos.append(intervalos[-1] + 4)
            if longo and not ja:  # muitas semanas até à avaliação: mais uma revisão, mais tarde
                intervalos.append(intervalos[-1] + 10)
            for j, depois in enumerate(intervalos):
                revisoes.append({"cadeira": c, "tema": tema, "depois": depois, "ja_estudado": ja,
                                 "tarefa": _texto_revisao(u, j)})
            if not ja and (u["dificuldade"] == "Difícil" or (estilo == "Mais exercícios" and u["dificuldade"] != "Fácil")):
                revisoes.append({"cadeira": c, "tema": tema, "depois": 1, "tipo": "Praticar",
                                 "tarefa": f"Refazer os exercícios de {minuscula(tema)} que correram pior"})
        finais = []
        if finais_d:
            finais.append((finais_d[0], _tarefa(c, "Rever", f"Revisão geral de {c}: resumir os temas principais",
                                                final=True)))
            finais.append((finais_d[-1], _tarefa(c, "Testar", f"Fazer um teste de treino de {c} e corrigir os erros",
                                                 final=True)))
        cadeiras[c] = {"conteudo": conteudo, "seq": seq, "finais": finais, "ordem": ordem_c}
    tarefas, info = _agendar(cadeiras, prefs["por_dia"], revisoes, ocupados)
    info.update(sem_dias=sem_dias, total=len(tarefas))
    return ordenar(tarefas), info


def reorganizar(tarefas: list, feitas: set, hoje: date, limites: dict, prefs: dict,
                cadeira: str | None = None) -> tuple[list, dict]:
    """Volta a distribuir o que está por fazer (o que ficou para trás e o que vem) pelos dias que faltam até cada
    avaliação, pela mesma ordem, sem passar o ritmo diário e com a revisão geral e o teste de treino no fim.
    As tarefas feitas não mudam. Tarefas de avaliações que já passaram saem do plano."""
    prefs = preferencias(prefs)
    feitas_l, por_fazer = [], {}
    for t in ordenar(tarefas):
        c = t.get("cadeira") or cadeira
        if id_sessao(t, cadeira) in feitas:
            feitas_l.append(t)
        else:
            por_fazer.setdefault(c, []).append(t)
    cadeiras, retiradas, sem_dias, cortadas, revisoes = {}, 0, [], 0, []
    for ordem_c, c in enumerate(sorted(por_fazer, key=lambda x: (limites.get(x) or date.max, str(x)))):
        lista = por_fazer[c]
        limite = limites.get(c)
        if limite and limite <= hoje:
            retiradas += len(lista)
            continue
        ultima = max((para_data(t.get("data")) or hoje) for t in lista)
        fim = limite or max(hoje + timedelta(days=7), ultima + timedelta(days=1))
        dias = dias_de_estudo(hoje, fim, prefs["folga"])
        if not dias:
            sem_dias.append(c)
            retiradas += len(lista)
            continue
        finais_t = [t for t in lista if t.get("final")]
        conteudo, finais_d = _dias_finais(dias, bool(limite and finais_t))
        sem_dia = [{**{k: v for k, v in t.items() if k not in CAMPOS_DO_DIA}, "cadeira": t.get("cadeira") or c,
                    "tipo": tipo_de(t)} for t in lista]
        finais = [(finais_d[0] if tipo_de(t) == "Rever" else finais_d[-1], t) for t in sem_dia if t.get("final") and finais_d]
        # a matéria por fazer é espalhada por igual; as revisões e os «refazer exercícios» preenchem o espaço que sobra
        # (a seguir ao estudo do tema, se ainda não foi estudado), até à véspera da avaliação
        seq = [t for t in sem_dia if not (t.get("final") and finais_d) and not _e_revisao_extra(t)]
        por_estudar = {t.get("tema") for t in seq if tipo_de(t) == "Estudar" and t.get("tema")}
        estudo_original = {t.get("tema"): para_data(t.get("data")) for t in tarefas
                           if (t.get("cadeira") or cadeira) == c and tipo_de(t) == "Estudar" and t.get("tema")}
        for t in lista:
            if t.get("final") or not _e_revisao_extra(t):
                continue
            d0 = para_data(t.get("data")) or hoje
            if t["tema"] in por_estudar:
                base0 = estudo_original.get(t["tema"])
                revisoes.append({"cadeira": c, "tema": t["tema"], "tarefa": t["temas"], "tipo": tipo_de(t),
                                 "depois": max(1, (d0 - base0).days) if base0 else 2, "ja_estudado": False})
            else:
                revisoes.append({"cadeira": c, "tema": t["tema"], "tarefa": t["temas"], "tipo": tipo_de(t),
                                 "depois": max(1, (d0 - hoje).days + 1), "ja_estudado": True})
        cadeiras[c] = {"conteudo": conteudo, "seq": seq, "finais": finais, "ordem": ordem_c}
    ocupados: dict = {}
    for t in feitas_l:  # o que já está feito num dia (hoje ou depois) conta para o ritmo desse dia
        d = para_data(t.get("data"))
        if d and d >= hoje:
            ocupados[d] = ocupados.get(d, 0) + 1
    novas, info = _agendar(cadeiras, prefs["por_dia"], revisoes, ocupados)
    base = max([int(t.get("ordem") or 0) for t in feitas_l] + [0])
    for t in novas:
        t["ordem"] += base
    antes = {id_sessao(t, cadeira) for t in tarefas}
    info["revisoes_cortadas"] += cortadas
    info.update(retiradas=retiradas, sem_dias=sem_dias,
                movidas=sum(1 for t in novas if id_sessao(t, cadeira) not in antes))
    return ordenar(feitas_l + novas), info


def _e_revisao_extra(t: dict) -> bool:
    return not t.get("final") and tipo_de(t) in ("Rever", "Praticar") and bool(t.get("tema")) and (
        tipo_de(t) == "Rever" or str(t.get("temas", "")).startswith("Refazer"))


def adiar(tarefas: list, ident: str, hoje: date, folga, cadeira: str | None = None, limite: date | None = None) -> str | None:
    """Passa uma tarefa por fazer para o próximo dia de estudo depois de hoje (e antes de «limite», o dia da avaliação).
    Devolve o novo identificador, ou None se não houver um dia livre antes da avaliação."""
    for t in tarefas:
        if id_sessao(t, cadeira) == ident:
            dia = max(hoje, para_data(t.get("data")) or hoje) + timedelta(days=1)
            for _ in range(7):
                if DIAS_SEMANA[dia.weekday()] not in (folga or []):
                    break
                dia += timedelta(days=1)
            if limite and dia >= limite:
                return None
            t["data"] = dia.isoformat()
            t["ordem"] = 10 ** 5 + int(t.get("ordem") or 0)  # vai para o fim desse dia
            return id_sessao(t, cadeira)
    return None


def ocupados(tarefas: list, feitas: set, hoje: date, cadeira: str | None = None) -> dict:
    """{dia: n}: tarefas feitas de hoje em diante (num plano refeito continuam lá e contam para o ritmo)."""
    res: dict = {}
    for t in tarefas:
        d = para_data(t.get("data"))
        if d and d >= hoje and id_sessao(t, cadeira) in feitas:
            res[d] = res.get(d, 0) + 1
    return res


def estudados(tarefas: list, feitas: set, cadeira: str | None = None) -> dict:
    """{cadeira: {temas}}: os temas cuja tarefa «Estudar» já está feita (num plano novo não voltam a ser dados)."""
    res: dict = {}
    for t in tarefas:
        if t.get("tema") and tipo_de(t) == "Estudar" and id_sessao(t, cadeira) in feitas:
            res.setdefault(t.get("cadeira") or cadeira, set()).add(t["tema"])
    return res


def fundir(antigas: list, novas: list, feitas: set, hoje: date, cadeira: str | None = None) -> list:
    """Plano refeito sem perder trabalho: ficam as tarefas feitas; as por fazer (as que ficaram para trás e as que
    vinham) dão lugar ao plano novo, que já volta a incluir essa matéria."""
    mantidas = [t for t in antigas if id_sessao(t, cadeira) in feitas]
    vistos = {id_sessao(t, cadeira) for t in mantidas}
    base = max([int(t.get("ordem") or 0) for t in mantidas] + [0])
    novas_ok = [{**t, "ordem": int(t.get("ordem") or 0) + base} for t in novas
                if (para_data(t.get("data")) or date.min) >= hoje and id_sessao(t, cadeira) not in vistos]
    return ordenar(mantidas + novas_ok)


# ---------------------------------------------------------------- resumo para o ecrã
def por_dia(tarefas: list) -> dict:
    grupos: dict = {}
    for t in ordenar(tarefas):
        grupos.setdefault(str(t.get("data", ""))[:10], []).append(t)
    return grupos


def resumo(dias: list, feitas: set, cadeira: str | None = None, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    feitas_t = [s for s in dias if id_sessao(s, cadeira) in feitas]
    por_cadeira: dict = {}
    for s in dias:
        nome = s.get("cadeira") or cadeira or "—"
        por_cadeira[nome] = por_cadeira.get(nome, 0) + 1
    por_fazer = [s for s in ordenar(dias)
                 if id_sessao(s, cadeira) not in feitas and (para_data(s.get("data")) or hoje) >= hoje]
    datas = [para_data(s.get("data")) for s in dias if para_data(s.get("data"))]
    return {"total": len(dias), "feitas": len(feitas_t), "por_cadeira": por_cadeira,
            "proxima": por_fazer[0] if por_fazer else None, "inicio": min(datas) if datas else None,
            "fim": max(datas) if datas else None,
            "atrasadas": sum(1 for s in dias
                             if id_sessao(s, cadeira) not in feitas and (para_data(s.get("data")) or hoje) < hoje)}


def hora_valida(valor) -> str | None:
    """(Só para as avaliações.) «9:00», «9h30» → «09:00»."""
    m = re.fullmatch(r"\s*(\d{1,2})[:h](\d{2})\s*", str(valor or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"
