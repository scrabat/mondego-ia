"""
Definições do Mondego IA — o que não depende do Streamlit (testado em testes_definicoes.py):
- as categorias da página Definições e o índice para a pesquisa;
- as preferências novas de cada pessoa (valores por omissão e validação);
- o CSS das preferências de aparência e acessibilidade (tamanho do texto, contraste, leitura, foco, movimento);
- as indicações para a IA (tamanho, nível e tom das respostas);
- os avisos (notificações dentro da app): avaliações próximas, tarefas, flashcards, salas e temas a rever;
- as perguntas frequentes.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta

# ---------------------------------------------------------------- categorias (chave, título, ícone, descrição curta)
CATEGORIAS = [
    ("conta", "Conta e perfil", "account_circle", "Nome, fotografia, palavra-passe e sessão"),
    ("academico", "Perfil académico", "school", "Curso, salas, objetivos e como estudas"),
    ("personalizacao", "Personalização", "palette", "Tema, página inicial e animações"),
    ("notificacoes", "Notificações", "notifications", "Avisos de avaliações, tarefas e salas"),
    ("ia", "Inteligência artificial", "auto_awesome", "Respostas, voz e histórico"),
    ("privacidade", "Privacidade e segurança", "shield", "Os teus dados, conversas e sessões"),
    ("acessibilidade", "Acessibilidade", "accessibility_new", "Texto, contraste, movimento e teclado"),
    ("ajuda", "Ajuda e suporte", "help", "Perguntas frequentes, contacto e versão"),
]
TITULOS = {c[0]: c[1] for c in CATEGORIAS}

# ---------------------------------------------------------------- preferências novas (ficam no perfil da conta)
OPCOES = {
    "movimento": ["Normal", "Reduzido"],
    "texto": ["Normal", "Grande", "Muito grande"],
    "pagina_inicial": ["Início", "Assistente", "Salas", "Calendário"],
    "ia_tamanho": ["Curtas", "Equilibradas", "Detalhadas"],
    "ia_nivel": ["Simples", "Normal", "Avançado"],
    "ia_tom": ["Próximo", "Neutro"],
    "voz_velocidade": ["Calma", "Normal", "Rápida"],
}
PADRAO = {
    "movimento": "Normal", "texto": "Normal", "contraste": False, "leitura": False, "foco": False, "intro": True,
    "pagina_inicial": "Início", "ia_tamanho": "Equilibradas", "ia_nivel": "Normal", "ia_tom": "Próximo",
    "voz_velocidade": "Normal", "voz_alta": True, "voz_continua": True,
}
AVISOS_PADRAO = {"ativos": True, "avaliacoes": True, "dias": 7, "tarefas": True, "estudo": True, "cartoes": True,
                 "salas": True, "revisao": True}
DIAS_AVISO = [1, 3, 7, 14]
CHAVES = tuple(PADRAO) + ("avisos",)
VISTA_INICIAL = {"Início": "inicio", "Assistente": "chat", "Salas": "salas", "Calendário": "calendario"}
VELOCIDADE_VOZ = {"Calma": 0.9, "Normal": 1.0, "Rápida": 1.2}
TAMANHO_TEXTO = {"Normal": None, "Grande": "17.5px", "Muito grande": "19.5px"}


def limpar_avisos(valor) -> dict:
    valor = valor if isinstance(valor, dict) else {}
    limpo = dict(AVISOS_PADRAO)
    for k in AVISOS_PADRAO:
        if k == "dias":
            if valor.get("dias") in DIAS_AVISO:
                limpo["dias"] = valor["dias"]
        elif isinstance(valor.get(k), bool):
            limpo[k] = valor[k]
    return limpo


def limpar(valores: dict | None) -> dict:
    """Preferências completas e válidas: o que faltar ou vier estragado fica com o valor por omissão."""
    valores = valores if isinstance(valores, dict) else {}
    limpo = {}
    for k, padrao in PADRAO.items():
        v = valores.get(k, padrao)
        if k == "pagina_inicial" and v == "Cadeiras":  # as cadeiras passaram a ser salas
            v = "Salas"
        if k in OPCOES:
            limpo[k] = v if v in OPCOES[k] else padrao
        else:
            limpo[k] = v if isinstance(v, bool) else padrao
    limpo["avisos"] = limpar_avisos(valores.get("avisos"))
    return limpo


def alteradas(prefs: dict) -> list:
    """Chaves que não estão no valor por omissão (para «Repor»)."""
    limpo = limpar(prefs)
    return [k for k in PADRAO if limpo[k] != PADRAO[k]] + (["avisos"] if limpo["avisos"] != AVISOS_PADRAO else [])


# ---------------------------------------------------------------- pesquisa nas definições
# (categoria, título da opção, palavras por que se pode procurar)
INDICE = [
    ("conta", "Nome e fotografia", "nome foto fotografia avatar perfil dados pessoais"),
    ("conta", "Email e forma de entrar", "email correio google microsoft conta entrar login"),
    ("conta", "Palavra-passe", "palavra-passe password senha segurança mudar alterar"),
    ("conta", "Sessão neste e noutros dispositivos", "sessão terminar sair logout dispositivos sessões ativas"),
    ("conta", "Apagar a conta", "apagar eliminar remover conta dados irreversível"),
    ("academico", "Curso, ano e instituição", "curso ano escolar instituição universidade escola nível ensino"),
    ("academico", "Salas e objetivos", "salas cadeiras disciplinas objetivos nota pretendida dificuldade"),
    ("academico", "Como estudas", "preferências aprendizagem dias estudo ritmo estilo plano exercícios teoria"),
    ("personalizacao", "Tema claro, escuro ou do sistema", "tema claro escuro automático sistema cor aparência modo"),
    ("personalizacao", "Página ao abrir a app", "página inicial abrir começar início assistente"),
    ("personalizacao", "Animações", "animações movimento reduzir animação entrada transições"),
    ("notificacoes", "Avisos no Início", "avisos notificações lembretes ligar desligar"),
    ("notificacoes", "Avaliações próximas", "avaliações testes exames datas antecedência dias"),
    ("notificacoes", "Tarefas e plano de estudo", "tarefas pendentes plano estudo lembrete por fazer"),
    ("notificacoes", "Flashcards e temas a rever", "flashcards cartões rever revisão quizzes temas fracos"),
    ("notificacoes", "Atividade das salas", "salas mensagens novas conversa atividade"),
    ("ia", "Idioma das respostas", "idioma língua português inglês english"),
    ("ia", "Velocidade das respostas", "velocidade rápida equilibrada rigorosa modelo"),
    ("ia", "Tamanho, nível e tom das explicações", "detalhe curtas detalhadas nível simples avançado tom comunicação explicações"),
    ("ia", "De onde vêm as respostas", "web internet pesquisa google fontes documentos só apontamentos wikipédia fiáveis"),
    ("ia", "Voz do assistente", "voz falar alto conversa contínua velocidade reprodução microfone"),
    ("ia", "Histórico de conversas", "histórico conversas apagar limpar"),
    ("privacidade", "Onde ficam os teus dados", "dados guardados onde privacidade rgpd"),
    ("privacidade", "Descarregar ou trazer os dados", "exportar descarregar zip importar transferir portabilidade"),
    ("privacidade", "Estatísticas de utilização", "estatísticas tempo uso foco contar apagar"),
    ("privacidade", "Conversas, voz e transcrições", "conversas voz áudio transcrições microfone permissões"),
    ("privacidade", "Sessões ativas", "sessões dispositivos terminar segurança"),
    ("privacidade", "Apagar os dados", "apagar eliminar dados conta"),
    ("acessibilidade", "Tamanho do texto", "texto letra tamanho grande aumentar fonte"),
    ("acessibilidade", "Contraste alto", "contraste alto visão cores"),
    ("acessibilidade", "Menos movimento", "movimento reduzido animações enjoo"),
    ("acessibilidade", "Leitura confortável", "leitura espaçamento linhas dislexia confortável"),
    ("acessibilidade", "Teclado", "teclado foco tab atalhos navegação"),
    ("ajuda", "Perguntas frequentes", "ajuda faq perguntas frequentes como funciona"),
    ("ajuda", "Contacto e reportar um problema", "contacto suporte reportar problema erro bug email"),
    ("ajuda", "Privacidade e versão", "termos privacidade versão sobre aplicação"),
]


def sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()


def procurar(consulta: str, perguntas: list | None = None) -> list:
    """Opções (e perguntas frequentes) que têm todas as palavras da consulta, sem contar acentos nem maiúsculas.
    Devolve [(categoria, título)], pela ordem das categorias."""
    palavras = [p for p in sem_acentos(consulta).split() if len(p) >= 2]
    if not palavras:
        return []
    achados = []
    for cat, titulo, extra in INDICE:
        alvo = sem_acentos(f"{titulo} {extra} {TITULOS[cat]}")
        if all(p in alvo for p in palavras):
            achados.append((cat, titulo))
    for pergunta, resposta in (perguntas if perguntas is not None else PERGUNTAS):
        if all(p in sem_acentos(pergunta + " " + resposta) for p in palavras):
            achados.append(("ajuda", pergunta))
    return achados


# ---------------------------------------------------------------- CSS das preferências (fora dos laboratórios)
_CONTRASTE_CLARO = "--texto:#0A1216; --suave:#2F3F45; --linha:#7D9096; --linha-forte:#4C6067; --borda-campo:#4C6067;"
_CONTRASTE_ESCURO = "--texto:#FFFFFF; --suave:#D3DEE0; --linha:#6F878E; --linha-forte:#9DB1B7; --borda-campo:#9DB1B7;"


def css_preferencias(prefs: dict, tema: str = "Automático") -> str:
    """Bloco <style> com o que a pessoa escolheu em Personalização e Acessibilidade. Vazio (<style></style>) com tudo
    no valor por omissão. Só entra nas páginas que não são de laboratório."""
    p = limpar(prefs)
    regras = []
    if TAMANHO_TEXTO[p["texto"]]:
        regras.append(f"html {{ font-size:{TAMANHO_TEXTO[p['texto']]} !important; }}")
    if p["contraste"]:
        if tema == "Escuro":
            regras.append(f":root {{{_CONTRASTE_ESCURO}}}")
        elif tema == "Claro":
            regras.append(f":root {{{_CONTRASTE_CLARO}}}")
        else:
            regras.append(f":root {{{_CONTRASTE_CLARO}}}\n@media (prefers-color-scheme: dark) {{ :root {{{_CONTRASTE_ESCURO}}} }}")
        regras.append('[data-testid="stMain"] a { text-decoration:underline; }')
    if p["leitura"]:
        regras.append('[data-testid="stMain"] [data-testid="stMarkdownContainer"] p, [data-testid="stMain"] '
                      '[data-testid="stMarkdownContainer"] li { line-height:1.8; letter-spacing:0.012em; word-spacing:0.05em; }\n'
                      '[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p { margin-bottom:0.9em; }\n'
                      '[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { max-width:68ch; }')
    if p["foco"]:
        regras.append('[data-testid="stApp"] :is(button, a, input, textarea, select, summary, [role="button"], [role="tab"], '
                      '[role="radio"], [role="checkbox"], [role="switch"], [tabindex]):focus-visible { outline:3px solid '
                      'var(--foco, #2AA5B8) !important; outline-offset:2px !important; border-radius:6px; }')
    if p["movimento"] == "Reduzido":
        regras.append("*, *::before, *::after { animation-duration:0.01ms !important; animation-iteration-count:1 !important; "
                      "transition-duration:0.01ms !important; scroll-behavior:auto !important; }")
    return "<style>" + "\n".join(regras) + "</style>"


# ---------------------------------------------------------------- indicações para a IA
def instrucoes_ia(prefs: dict, voz: bool = False) -> str:
    """Frases a juntar às instruções do assistente (conversa, cadeira e voz). Vazio com tudo no valor por omissão."""
    p = limpar(prefs)
    partes = []
    if p["ia_tamanho"] == "Curtas":
        partes.append("respostas curtas e diretas: o essencial em poucas frases, sem introduções" if not voz
                      else "respostas muito curtas: uma a três frases, só o essencial")
    elif p["ia_tamanho"] == "Detalhadas":
        partes.append("explicações completas, passo a passo, com um exemplo sempre que ajude" if not voz
                      else "explicações um pouco mais completas, passo a passo, com um exemplo")
    if p["ia_nivel"] == "Simples":
        partes.append("explica de forma simples, como a quem vê o tema pela primeira vez, e explica qualquer termo técnico")
    elif p["ia_nivel"] == "Avançado":
        partes.append("usa rigor técnico e a notação formal da área: o aluno já domina as bases")
    if p["ia_tom"] == "Neutro":
        partes.append("tom neutro e objetivo, sem expressões coloquiais nem entusiasmo")
    if not partes:
        return ""
    return "\n\nPREFERÊNCIAS DO ALUNO (respeita-as, sem as comentar): " + "; ".join(partes) + "."


# ---------------------------------------------------------------- avisos (notificações dentro da app)
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _data(valor) -> date | None:
    try:
        return valor if isinstance(valor, date) else date.fromisoformat(str(valor or "")[:10])
    except ValueError:
        return None


def quando(dias: int) -> str:
    return "hoje" if dias <= 0 else "amanhã" if dias == 1 else f"daqui a {dias} dias"


def avisos(hoje: date, prefs: dict, proximas: list | None = None, tarefas_hoje: tuple = (0, 0), atrasadas: int = 0,
           cartoes: int = 0, cartoes_cadeira: str | None = None, temas_fracos: list | None = None,
           salas_novas: list | None = None, vistos: dict | None = None) -> list:
    """Lista de avisos úteis para hoje, por ordem de urgência. Cada aviso: {id, tipo, icone, titulo, texto, urgente,
    destino}. «vistos» = {id: dia em que foi dispensado}: um aviso dispensado hoje não volta a aparecer hoje.
    - proximas: [{id, nome, cadeira, data, hora}] (avaliações por vir);
    - tarefas_hoje: (feitas, total) do plano de hoje; atrasadas: tarefas por fazer em dias que já passaram;
    - cartoes: flashcards para rever hoje (e a cadeira com mais);
    - temas_fracos: [(cadeira, tema)] dos últimos quizzes; salas_novas: [(id, nome, n mensagens novas)]."""
    a = limpar_avisos((prefs or {}).get("avisos") if isinstance(prefs, dict) and "avisos" in prefs else prefs)
    if not a["ativos"]:
        return []
    lista = []
    if a["avaliacoes"]:
        for r in proximas or []:
            d = _data(r.get("data"))
            if d is None:
                continue
            dias = (d - hoje).days
            if 0 <= dias <= a["dias"]:
                hora = f" às {r['hora']}" if r.get("hora") else ""
                lista.append({"id": f"av:{r.get('id')}:{d.isoformat()}:{min(dias, 3)}", "tipo": "avaliacoes", "icone": "event",
                              "titulo": f"{r.get('nome', 'Avaliação')} é {quando(dias)}",
                              "texto": f"{r.get('cadeira', '')} · {DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]}{hora}",
                              "urgente": dias <= 1, "ordem": dias, "destino": ("avaliacao", r.get("id"))})
    if a["tarefas"] and atrasadas > 0:
        lista.append({"id": f"tar:{hoje.isoformat()}:{atrasadas}", "tipo": "tarefas", "icone": "event_repeat",
                      "titulo": f"{atrasadas} {'tarefa ficou' if atrasadas == 1 else 'tarefas ficaram'} por fazer",
                      "texto": "Reorganiza o plano: o que falta é espalhado pelos dias até à avaliação.",
                      "urgente": False, "ordem": 20, "destino": ("plano", None)})
    feitas, total = tarefas_hoje
    if a["estudo"] and total and feitas < total:
        falta = total - feitas
        lista.append({"id": f"est:{hoje.isoformat()}:{falta}", "tipo": "estudo", "icone": "checklist",
                      "titulo": (f"{falta} {'tarefa' if falta == 1 else 'tarefas'} no plano de hoje" if feitas == 0
                                 else f"{'Falta' if falta == 1 else 'Faltam'} {falta} {'tarefa' if falta == 1 else 'tarefas'} do plano de hoje"),
                      "texto": "Marca cada tarefa quando a acabares." if feitas == 0 else f"Já fizeste {feitas} de {total}.",
                      "urgente": False, "ordem": 30, "destino": ("plano", None)})
    if a["cartoes"] and cartoes > 0:
        lista.append({"id": f"car:{hoje.isoformat()}", "tipo": "cartoes", "icone": "style",
                      "titulo": f"{cartoes} {'flashcard' if cartoes == 1 else 'flashcards'} para rever hoje",
                      "texto": f"Começa por {cartoes_cadeira}." if cartoes_cadeira else "A revisão espaçada funciona melhor em dia.",
                      "urgente": False, "ordem": 40, "destino": ("cartoes", cartoes_cadeira)})
    if a["revisao"]:
        for cadeira, tema in (temas_fracos or [])[:2]:
            lista.append({"id": f"rev:{cadeira}:{tema}", "tipo": "revisao", "icone": "target",
                          "titulo": f"Rever «{tema}»", "texto": f"Foi onde erraste mais no último quiz de {cadeira}.",
                          "urgente": False, "ordem": 50, "destino": ("cadeira", cadeira)})
    if a["salas"]:
        for sala_id, nome, n in (salas_novas or [])[:3]:
            if n > 0:
                lista.append({"id": f"sala:{sala_id}:{n}", "tipo": "salas", "icone": "forum",
                              "titulo": f"{n} {'mensagem nova' if n == 1 else 'mensagens novas'} em {nome}",
                              "texto": "Abre a sala para ver a conversa.", "urgente": False, "ordem": 45,
                              "destino": ("sala", sala_id)})
    vistos = vistos or {}
    lista = [x for x in lista if vistos.get(x["id"]) != hoje.isoformat()]
    return sorted(lista, key=lambda x: (not x["urgente"], x["ordem"]))


def limpar_vistos(vistos: dict | None, hoje: date) -> dict:
    """Só interessam os avisos dispensados hoje (os de ontem voltam a poder aparecer)."""
    return {k: v for k, v in (vistos or {}).items() if v == hoje.isoformat()}


def mensagens_novas(mensagens: list, desde: str | None, meu_id: str | None) -> int:
    """Mensagens de outras pessoas enviadas depois de «desde» (ISO). Sem «desde» (nunca abriu a sala): nenhuma,
    para não avisar de conversas antigas."""
    if not desde:
        return 0
    return sum(1 for m in mensagens or []
               if str(m.get("enviada_em") or m.get("criada_em") or "") > desde and m.get("autor_id") != meu_id)


# ---------------------------------------------------------------- cronómetro: resumo das sessões de foco
def resumo_foco(foco: list, hoje: date) -> dict:
    """Minutos de hoje e da semana (últimos 7 dias), sessões de hoje, dias seguidos com foco e minutos por cadeira
    nos últimos 7 dias."""
    por_dia: dict = {}
    semana_ini = hoje - timedelta(days=6)
    por_cadeira: dict = {}
    sessoes_hoje = 0
    for f in foco or []:
        d = _data(f.get("data"))
        if d is None:
            continue
        m = int(f.get("minutos") or 0)
        por_dia[d] = por_dia.get(d, 0) + m
        if d == hoje:
            sessoes_hoje += 1
        if semana_ini <= d <= hoje:
            nome = f.get("cadeira") or "Sem sala"
            por_cadeira[nome] = por_cadeira.get(nome, 0) + m
    seguidos, d = 0, hoje
    if not por_dia.get(hoje):  # hoje ainda sem foco: a sequência conta até ontem
        d = hoje - timedelta(days=1)
    while por_dia.get(d):
        seguidos += 1
        d -= timedelta(days=1)
    return {"hoje": por_dia.get(hoje, 0), "sessoes_hoje": sessoes_hoje,
            "semana": sum(m for dia, m in por_dia.items() if semana_ini <= dia <= hoje), "seguidos": seguidos,
            "por_cadeira": dict(sorted(por_cadeira.items(), key=lambda kv: -kv[1]))}


# ---------------------------------------------------------------- palavra-passe
def validar_palavra_passe(nova: str, confirmar: str, atual: str = "") -> str | None:
    """Devolve o problema (texto para mostrar) ou None se a palavra-passe nova serve."""
    if len(nova or "") < 8:
        return "A palavra-passe nova tem de ter pelo menos 8 caracteres."
    if nova != confirmar:
        return "As duas palavras-passe novas não são iguais."
    if atual and nova == atual:
        return "A palavra-passe nova tem de ser diferente da atual."
    return None


# ---------------------------------------------------------------- perguntas frequentes (o que a app faz de facto)
PERGUNTAS = [
    ("Como começo a estudar uma cadeira?",
     "Em Cadeiras, cria a cadeira e junta as tuas fontes (PDF, slides, apontamentos). A partir daí podes conversar sobre a "
     "matéria e pedir resumos, quizzes, flashcards, testes e um plano de preparação."),
    ("Como funciona o plano de estudo?",
     "Marca as avaliações no Calendário e escolhe «Novo plano com IA». A IA lê a matéria e a app diz-te o que estudar em "
     "cada dia, sem horários. Marca as tarefas feitas; o que ficar por fazer pode ser reorganizado pelos dias que faltam."),
    ("Posso falar com o assistente por voz?",
     "Sim. No Início, carrega na esfera e faz a pergunta (no Chrome ou no Edge). O browser pede autorização para usar o "
     "microfone. A resposta aparece escrita e é lida em voz alta; podes pausar ou interromper."),
    ("O que são as Salas?",
     "Espaços para estudar com colegas ou com uma turma: materiais partilhados, conversa e um assistente que responde com "
     "base nos materiais da sala. Entra-se com o código ou o link que o criador partilha."),
    ("Onde ficam guardados os meus dados?",
     "Na tua conta: só tu os vês. Em Definições → Privacidade e segurança podes descarregar tudo num ficheiro .zip, "
     "trazer os dados de outro computador ou apagar a conta."),
    ("O que é enviado à IA?",
     "As tuas perguntas e os excertos dos documentos que interessam à pergunta, só para gerar a resposta. A chave da IA "
     "é de quem gere a app e nunca aparece aos utilizadores."),
    ("Como mudo o tema ou o tamanho do texto?",
     "Em Definições → Personalização escolhes o tema claro, escuro ou o do sistema. Em Definições → Acessibilidade "
     "aumentas o texto, ligas o contraste alto ou reduzes o movimento."),
    ("Como recebo avisos?",
     "Os avisos aparecem no Início: avaliações próximas, tarefas por fazer, flashcards para rever e mensagens novas nas "
     "salas. Escolhe os que queres em Definições → Notificações. Ainda não há avisos por email nem no telemóvel."),
    ("O cronómetro continua a contar se eu mudar de página?",
     "Sim. O tempo fica guardado no browser e continua certo noutras páginas; quando a sessão de foco acaba, os minutos "
     "entram nas tuas estatísticas."),
]
