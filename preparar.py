"""
Assistente pedagógico («Preparar com a IA»): uma conversa curta e guiada com o professor para preparar aulas, fichas de
exercícios, testes com critérios e outros recursos, sem escrever prompts nem carregar documentos.

Este módulo tem as regras: o que a IA deve perguntar e como lhe pedir os materiais, como ler as respostas dela, como
guardar as versões e como exportar para Word e PDF. A interface está em app.py (pagina_preparar). Não depende do
Streamlit (testes_preparar.py).

Como funciona a conversa: a cada passo a IA devolve um objeto JSON com a mensagem para o professor, as respostas rápidas
(botões), o que já sabe («dados»), o que ainda falta e se já pode criar («pronto»). Quando está pronta, a app pede o
material completo (em Markdown), mostra-o e guarda-o no perfil, com as versões seguintes (mais fácil, mais difícil,
nova versão, alterações pedidas ou edição à mão).
"""
from __future__ import annotations

import html
import io
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- tipos de material
TIPOS = {
    "aula": {
        "rotulo": "Planear uma aula", "icone": "event_note", "curto": "Plano de aula",
        "descricao": "Objetivos, desenvolvimento com tempos, atividades, recursos, diferenciação e avaliação.",
        "campos": {"disciplina": "Disciplina", "ano": "Ano", "tema": "Tema", "duracao": "Duração"},
        "pedido": "Quero planear uma aula.",
    },
    "ficha": {
        "rotulo": "Criar uma ficha de exercícios", "icone": "assignment", "curto": "Ficha de exercícios",
        "descricao": "Exercícios variados por níveis, espaço para as respostas e as soluções à parte.",
        "campos": {"disciplina": "Disciplina", "ano": "Ano", "tema": "Conteúdo", "dificuldade": "Dificuldade"},
        "pedido": "Quero criar uma ficha de exercícios.",
    },
    "teste": {
        "rotulo": "Fazer um teste com critérios", "icone": "fact_check", "curto": "Teste",
        "descricao": "Perguntas de vários tipos, cotações, critérios de classificação e de correção, soluções.",
        "campos": {"disciplina": "Disciplina", "ano": "Ano", "tema": "Matéria", "duracao": "Duração"},
        "pedido": "Quero fazer um teste com critérios de classificação.",
    },
    "outro": {
        "rotulo": "Outro recurso", "icone": "auto_awesome", "curto": "Recurso",
        "descricao": "Jogos, grelhas, apresentações, planificações, estratégias…",
        "campos": {"objetivo": "Objetivo", "disciplina": "Disciplina", "ano": "Ano", "tema": "Tema"},
        "pedido": "",
    },
}
TIPOS_PRINCIPAIS = ("aula", "ficha", "teste")

# «Em que posso ajudar hoje?»: (id, ícone, pergunta mostrada, tipo, pedido que começa a conversa)
SUGESTOES = [
    ("ideias", "lightbulb", "Precisas de ideias para uma aula?", "aula", "Preciso de ideias para uma aula."),
    ("jogo", "sports_esports", "Queres criar um jogo educativo?", "outro", "Quero criar um jogo educativo para os meus alunos."),
    ("dificuldades", "support", "Tens alunos com dificuldades?", "outro",
     "Tenho alunos com dificuldades e preciso de ajuda para os apoiar."),
    ("niveis", "stairs", "Queres adaptar atividades a diferentes níveis?", "outro",
     "Quero adaptar uma atividade a diferentes níveis dos alunos."),
    ("grelha", "table_chart", "Precisas de criar uma grelha de avaliação?", "outro", "Preciso de criar uma grelha de avaliação."),
    ("apresentacao", "slideshow", "Queres preparar uma apresentação?", "outro", "Quero preparar uma apresentação para uma aula."),
    ("semanal", "calendar_view_week", "Queres organizar a planificação semanal?", "outro",
     "Quero organizar a planificação da semana."),
    ("consolidacao", "task_alt", "Queres criar atividades de consolidação?", "outro", "Quero criar atividades de consolidação."),
    ("motivar", "emoji_objects", "Queres estratégias para motivar os alunos?", "outro",
     "Quero estratégias para motivar os meus alunos."),
]
SUGESTAO = {s[0]: s for s in SUGESTOES}
# Nome curto de cada sugestão (na grelha «Mais ideias»; a pergunta completa fica na dica do botão)
CURTO_SUGESTAO = {"ideias": "Ideias para uma aula", "jogo": "Jogo educativo", "dificuldades": "Alunos com dificuldades",
                  "niveis": "Atividades por níveis", "grelha": "Grelha de avaliação", "apresentacao": "Apresentação",
                  "semanal": "Planificação semanal", "consolidacao": "Atividades de consolidação",
                  "motivar": "Motivar os alunos"}

# O que cada sugestão deve produzir (vai no pedido do material)
GUIA_SUGESTAO = {
    "ideias": "Várias ideias de aula (3 a 5), cada uma com o título, a ideia em duas frases, como decorre (passos com "
              "tempos), materiais e porque resulta. No fim, recomenda uma.",
    "jogo": "Um jogo educativo pronto a usar: objetivo de aprendizagem, número de alunos e duração, materiais, preparação, "
            "regras passo a passo, exemplos de perguntas/cartões (pelo menos 12), variações para mais fácil e mais difícil, "
            "e como avaliar o que aprenderam.",
    "dificuldades": "Um plano de apoio: dificuldades prováveis e como as identificar, estratégias concretas na aula, "
                    "atividades de apoio graduadas (com exemplos), adaptações de avaliação, envolvimento da família e um "
                    "plano de acompanhamento de 4 semanas (tabela).",
    "niveis": "Uma atividade base e três versões (Nível 1 — apoio, Nível 2 — base, Nível 3 — desafio), com instruções "
              "para os alunos, exemplos, critérios de sucesso de cada nível e soluções.",
    "grelha": "Uma grelha de avaliação (rubrica) em tabela: critérios nas linhas, níveis de desempenho nas colunas (com "
              "descritores observáveis e pontuação), mais as instruções de uso e uma grelha de registo para a turma.",
    "apresentacao": "O guião de uma apresentação, diapositivo a diapositivo (### Diapositivo n — título), com os pontos a "
                    "mostrar, uma sugestão de imagem ou esquema e as notas do professor, e uma pergunta para a turma no fim.",
    "semanal": "Uma planificação semanal em tabela (dia, aula/turma, objetivos, atividades, recursos, trabalho de casa) e, "
               "por baixo, os pontos de atenção da semana.",
    "consolidacao": "Atividades de consolidação variadas (pelo menos 6, do mais simples ao mais exigente), com o tempo de "
                    "cada uma, instruções para os alunos e as soluções numa secção à parte.",
    "motivar": "Estratégias para motivar os alunos: 6 a 8 estratégias concretas, cada uma com o que é, como aplicar "
               "amanhã (passos), um exemplo nesta disciplina e como saber se está a resultar.",
}

ESTRUTURA = {
    "aula": """Estrutura obrigatória do plano de aula:
# (título da aula)
Uma linha com: disciplina · ano/turma · duração.
## Objetivos de aprendizagem (3 a 5, verificáveis, começados por um verbo)
## Conteúdos
## Desenvolvimento da aula — tabela | Momento | Tempo | O professor | Os alunos |, com os tempos a somar a duração
## Atividades de aprendizagem (cada uma com instruções claras e, se tiver exercícios, as soluções)
## Recursos necessários
## Diferenciação pedagógica (apoio a quem tem dificuldades, desafio a quem avança depressa, adaptações se fizer sentido)
## Avaliação das aprendizagens (como saber se os objetivos foram atingidos: instrumentos e critérios de sucesso)""",
    "ficha": """Estrutura obrigatória da ficha de exercícios:
# (título da ficha)
Uma linha com: disciplina · ano · conteúdo.
**Nome:** ______________________ **N.º:** ____ **Turma:** ____ **Data:** ____/____/______
## Instruções (curtas, para os alunos)
## Exercícios — por níveis de dificuldade: ### Nível 1 — (aplicação direta), ### Nível 2 — (compreensão), ### Nível 3 — (desafio).
Numera os exercícios seguidamente (1., 2., 3., …) e varia os tipos (escolha múltipla, verdadeiro/falso, completar,
resposta curta, problemas). Depois de cada exercício de resposta escrita deixa linhas de resposta, cada uma só com
sublinhados: ________________________________________
---
## Soluções e propostas de correção (por número de exercício, com a resolução ou os passos, nunca só o resultado)""",
    "teste": """Estrutura obrigatória do teste:
# (título do teste)
**Escola:** ______________________ **Ano/Turma:** ____ **Data:** ____/____/______ **Duração:** (a duração)
**Nome:** ______________________________ **N.º:** ____ **Classificação:** ________
## Instruções
## Grupo I, ## Grupo II, … — perguntas de tipologias diferentes (escolha múltipla, verdadeiro/falso, associação,
resposta curta, resposta extensa ou problema), numeradas seguidamente (1., 2., …), cada uma com a cotação no fim, entre
parênteses: (10 pontos). As cotações somam exatamente 100 pontos (no ensino superior, 20 valores).
---
## Quadro de cotações — tabela | Pergunta | Cotação | com a linha **Total**
## Critérios de classificação (para cada pergunta de resposta aberta: níveis de desempenho com descritores e pontos)
## Critérios de correção e soluções (para todas as perguntas: resposta esperada e cotações parciais)""",
}

ACOES_RAPIDAS = {
    "mais_facil": ("Mais fácil", "south", "Torna o material mais fácil e mais acessível: linguagem mais simples, mais "
                   "exemplos e passos intermédios, exercícios/atividades menos exigentes. Mantém a estrutura e os objetivos."),
    "mais_dificil": ("Mais difícil", "north", "Torna o material mais desafiante: exercícios/atividades mais exigentes, "
                     "mais raciocínio e aplicação a situações novas. Mantém a estrutura e os objetivos."),
    "nova_versao": ("Nova versão", "autorenew", "Cria uma versão alternativa com os mesmos objetivos, a mesma estrutura e "
                    "o mesmo nível, mas com atividades, exemplos e exercícios diferentes."),
}

# Modelo do professor (teste da escola, ficha antiga, grelha…): como usá-lo
USOS_MODELO = {
    "formato": ("Seguir este formato",
                "Segue a ESTRUTURA do documento de referência: o mesmo cabeçalho, a mesma organização (grupos, secções, "
                "numeração), os mesmos tipos de pergunta, o mesmo sistema de cotações e o mesmo estilo de instruções, mas "
                "com conteúdo NOVO sobre o tema pedido. Onde a estrutura do documento for diferente da estrutura acima, "
                "manda a do documento (mantém sempre as soluções e os critérios)."),
    "base": ("Fazer um novo a partir deste",
             "Cria um material NOVO a partir do CONTEÚDO do documento de referência: a mesma matéria e o mesmo nível, com "
             "exercícios e perguntas diferentes (não copies os do documento)."),
    "adaptar": ("Adaptar este",
                "ADAPTA o documento de referência ao que o professor pediu: mantém o que serve, muda o resto (nível, "
                "duração, tipos de pergunta…) e acrescenta o que faltar (soluções, critérios)."),
}
MAX_MODELO = 15000  # caracteres do modelo que vão para a IA

MAX_VERSOES = 12
MAX_PERGUNTAS = 4  # depois disto a IA cria com o que tem (nunca um questionário longo)


# ---------------------------------------------------------------- pedidos à IA
def contexto_professor(resumo_academico: str = "", turmas: list | None = None, disciplinas: list | None = None) -> str:
    """O que a app já sabe sobre quem ensina (para a IA não perguntar o que já se sabe)."""
    partes = []
    if resumo_academico:
        partes.append(f"Perfil: {resumo_academico}.")
    turmas = [t for t in (turmas or []) if t]
    if turmas:
        partes.append("Turmas na app: " + "; ".join(turmas[:8]) + ".")
    disciplinas = [d for d in (disciplinas or []) if d]
    if disciplinas:
        partes.append("Disciplinas/cadeiras na app: " + ", ".join(disciplinas[:10]) + ".")
    return " ".join(partes) or "Sem informação de perfil."


def sistema_conversa(tipo: str) -> str:
    t = TIPOS.get(tipo, TIPOS["outro"])
    campos = ", ".join(f"«{k}» ({v.lower()})" for k, v in t["campos"].items())
    return f"""És o assistente pedagógico do Mondego IA: ajudas professores portugueses a preparar materiais (aulas, fichas,
testes, grelhas, jogos, apresentações, planificações…). Escreves em português de Portugal (AO90), tratas o professor por
tu, és caloroso e direto, e usas a terminologia do sistema educativo português (ex.: «3.º ano», «10.º ano», «ensino
superior», Aprendizagens Essenciais).

COMO CONDUZES A CONVERSA
- Fazes UMA pergunta de cada vez, curta (até duas frases), e adaptas a seguinte ao que o professor respondeu.
- Nunca perguntas o que já sabes pelo contexto do professor ou pelas respostas anteriores. Se puderes deduzir com
  segurança (ex.: só tem uma disciplina), assumes e dizes numa frase que assumiste.
- Para cada pergunta dás entre 3 e 6 respostas rápidas em «opcoes»: curtas (até 5 palavras), concretas e adequadas ao
  contexto (ex.: anos do nível de ensino do professor; durações de 45, 50 ou 90 minutos). Quando o professor pode não
  saber, inclui a opção «Sugere-me tu».
- Se o professor não souber o que quer ou disser «sugere-me tu», propões 2 ou 3 alternativas concretas como opções (ou
  escolhes a melhor e dizes qual).
- Não fazes questionários: no máximo {MAX_PERGUNTAS} perguntas no total. Os detalhes secundários (dificuldade, número de
  exercícios, abordagem) escolhes tu com bom senso e dizes o que escolheste.
- Para este material o essencial é: {campos}.
- Se o professor anexou um documento de referência (um «modelo»: teste da escola, ficha antiga, grelha…), tira dele
  tudo o que puderes (disciplina, ano, tema, duração, tipos de pergunta, cotações) em vez de perguntar. Se ele ainda não
  disse como o quer usar, pergunta-o com as opções «Seguir este formato», «Fazer um novo a partir deste» e «Adaptar
  este», e guarda a escolha em dados.uso_modelo («formato», «base» ou «adaptar»).
- Logo que tenhas o essencial, ou se o professor pedir para avançar («cria já», «tanto faz»), marcas "pronto": true e
  em «mensagem» dizes numa frase o que vais criar (sem fazer mais perguntas).

RESPONDES SÓ COM UM OBJETO JSON, sem mais nada:
{{"mensagem": "texto para o professor", "opcoes": ["…"], "dados": {{"disciplina": "…"}}, "falta": ["…"],
  "titulo": "título curto do material", "pronto": false}}
- «dados»: tudo o que já sabes até agora (acumulado), com as chaves acima e outras úteis (ex.: «abordagem», «n_exercicios»).
- «falta»: as chaves essenciais que ainda faltam.
- «opcoes»: lista vazia quando "pronto" é true."""


def bloco_modelo(modelo: dict | None, limite: int = MAX_MODELO) -> str:
    """O documento de referência do professor, para ir no pedido à IA."""
    if not modelo or not str(modelo.get("texto") or "").strip():
        return ""
    texto = str(modelo["texto"]).strip()
    corte = "\n[… o resto do documento foi cortado]" if len(texto) > limite else ""
    return (f"\n\nDOCUMENTO DE REFERÊNCIA anexado pelo professor («{modelo.get('nome') or 'modelo'}»):\n<modelo>\n"
            f"{texto[:limite]}{corte}\n</modelo>")


def uso_do_modelo(dados: dict | None) -> str:
    """«formato», «base» ou «adaptar» (o que o professor escolheu), ou "" se ainda não disse."""
    v = str((dados or {}).get("uso_modelo") or "").lower()
    if any(x in v for x in ("formato", "estrutura", "seguir")):
        return "formato"
    if any(x in v for x in ("adapt",)):
        return "adaptar"
    if any(x in v for x in ("base", "novo", "nova", "partir")):
        return "base"
    return ""


def primeira_mensagem(tipo: str, pedido: str, contexto: str, sugestao: str = "", modelo: dict | None = None) -> str:
    t = TIPOS.get(tipo, TIPOS["outro"])
    extra = f"\nO que se pretende produzir: {GUIA_SUGESTAO[sugestao]}" if sugestao in GUIA_SUGESTAO else ""
    extra += bloco_modelo(modelo, 6000)
    return (f"Contexto do professor: {contexto}\n\nTipo de material: {t['rotulo'] if tipo != 'outro' else 'recurso pedagógico'}."
            f"{extra}\n\nPedido do professor: {pedido.strip() or t['pedido']}\n\n"
            "Começa a conversa: cumprimenta numa frase curta e faz a primeira pergunta (ou, se já tiveres o essencial, "
            "marca pronto).")


def mensagens_conversa(tipo: str, turnos: list, contexto: str, sugestao: str = "", modelo: dict | None = None) -> list:
    """Converte a conversa guardada nas mensagens para a IA. turnos: [{"papel": "prof"|"ia", ...}], o primeiro é o
    pedido do professor; os turnos da IA vão como o JSON que ela devolveu (assim mantém o que já sabia)."""
    if not turnos:
        raise ValueError("Conversa vazia.")
    mensagens = [{"role": "user", "content": primeira_mensagem(tipo, turnos[0].get("texto", ""), contexto, sugestao, modelo)}]
    for t in turnos[1:]:
        if t.get("papel") == "ia":
            mensagens.append({"role": "assistant", "content": json.dumps(t.get("json") or {}, ensure_ascii=False)})
        else:
            mensagens.append({"role": "user", "content": str(t.get("texto") or "").strip() or "Continua."})
    if mensagens[-1]["role"] == "assistant":  # a IA fala sempre depois do professor
        mensagens.append({"role": "user", "content": "Continua."})
    perguntas = sum(1 for t in turnos if t.get("papel") == "ia")
    if perguntas >= MAX_PERGUNTAS:
        mensagens[-1]["content"] += ("\n\n(Já fizeste as perguntas todas: marca \"pronto\": true e cria com o que sabes, "
                                     "escolhendo tu o que faltar.)")
    return mensagens


def _sem_cercas(texto: str) -> str:
    return re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", str(texto or "").strip())


def interpretar_turno(texto: str) -> dict:
    """Lê a resposta da IA na conversa e devolve-a sempre no mesmo formato. Rebenta (ValueError) se não houver nada que
    se possa mostrar ao professor."""
    t = _sem_cercas(texto)
    try:
        dados = json.loads(t)
    except json.JSONDecodeError:
        inicio, fim = t.find("{"), t.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise ValueError("A IA não respondeu no formato esperado.")
        dados = json.loads(t[inicio:fim + 1])
    if isinstance(dados, list):
        dados = next((x for x in dados if isinstance(x, dict)), {})
    if not isinstance(dados, dict):
        raise ValueError("A IA não respondeu no formato esperado.")
    mensagem = " ".join(str(dados.get("mensagem") or "").split()) if "\n" not in str(dados.get("mensagem") or "") \
        else str(dados.get("mensagem")).strip()
    pronto = dados.get("pronto") in (True, "true", "sim", 1)
    opcoes = []
    for o in dados.get("opcoes") or []:
        o = " ".join(str(o).split())[:60]
        if o and o.lower() not in (x.lower() for x in opcoes):
            opcoes.append(o)
    recolhidos = {}
    for k, v in (dados.get("dados") or {}).items() if isinstance(dados.get("dados"), dict) else []:
        if isinstance(v, (list, tuple)):
            v = ", ".join(str(x) for x in v if str(x).strip())
        v = " ".join(str(v if v is not None else "").split())
        if v and v.lower() not in ("?", "—", "-", "null", "none", "desconhecido"):
            recolhidos[str(k).strip()[:40]] = v[:200]
    falta = [str(x).strip() for x in (dados.get("falta") or []) if str(x).strip()] if isinstance(dados.get("falta"), list) else []
    if not mensagem and not pronto:
        raise ValueError("A IA não fez nenhuma pergunta.")
    return {"mensagem": mensagem, "opcoes": [] if pronto else opcoes[:6], "dados": recolhidos,
            "falta": [] if pronto else falta, "titulo": " ".join(str(dados.get("titulo") or "").split())[:90],
            "pronto": pronto}


def progresso(tipo: str, turno: dict | None) -> list:
    """Os campos essenciais, por ordem, com o valor já recolhido (ou None): para o indicador discreto da conversa."""
    dados = (turno or {}).get("dados") or {}
    return [(rotulo, dados.get(chave)) for chave, rotulo in TIPOS.get(tipo, TIPOS["outro"])["campos"].items()]


SISTEMA_MATERIAL = (
    "És um professor experiente e especialista em didática, a preparar materiais para professores portugueses. "
    "Escreves em português de Portugal (AO90) e usas a terminologia do sistema educativo português. Os materiais são "
    "completos, rigorosos, prontos a usar na aula e adequados ao ano e à duração indicados: nada de «exemplo», "
    "«preencher» ou partes por fazer. Formato: Markdown simples (# título, ## secções, ### subsecções, listas, "
    "**negrito**, tabelas Markdown). Não uses LaTeX nem $: escreve as fórmulas em texto com símbolos (x², √, π, ×, ÷, "
    "≤, ≥, frações como 3/4). Não uses HTML nem emojis. Começa diretamente pelo título, sem introduções nem comentários "
    "sobre o que fizeste."
)


def _linhas_dados(dados: dict) -> str:
    nomes = {k: v for t in TIPOS.values() for k, v in t["campos"].items()}
    return "\n".join(f"- {nomes.get(k, k.replace('_', ' ').capitalize())}: {v}" for k, v in dados.items()) or "- (sem dados)"


def pedido_material(tipo: str, dados: dict, pedido: str, sugestao: str = "", conversa: str = "",
                    modelo: dict | None = None) -> list:
    """Mensagens para a IA criar o material completo."""
    t = TIPOS.get(tipo, TIPOS["outro"])
    estrutura = ESTRUTURA.get(tipo) or (
        "O que produzir: " + GUIA_SUGESTAO.get(sugestao, "o recurso pedido, com a estrutura mais útil para o professor")
        + "\nEstrutura: # título; uma linha com disciplina · ano; secções ## claras; tabelas quando organizam melhor; "
          "se houver exercícios, as soluções numa secção ## Soluções no fim, depois de uma linha ---.")
    texto = (f"Cria: {t['rotulo'] if tipo != 'outro' else 'recurso pedagógico'}\n\nDados recolhidos na conversa:\n"
             f"{_linhas_dados(dados)}\n\nPedido inicial do professor: {pedido.strip() or t['pedido']}\n\n{estrutura}")
    if modelo and str(modelo.get("texto") or "").strip():
        uso = uso_do_modelo(dados)
        texto += bloco_modelo(modelo) + "\n" + (USOS_MODELO[uso][1] if uso else
                                                 "Usa o documento de referência como modelo de formato e de nível.")
    if conversa:
        texto += f"\n\nConversa com o professor (para respeitares o que ele disse):\n{conversa}"
    return [{"role": "user", "content": texto}]


def pedido_revisao(material: str, instrucao: str) -> list:
    return [{"role": "user", "content":
             f"Este é o material atual:\n<material>\n{material.strip()}\n</material>\n\n"
             f"Faz esta alteração e devolve o material COMPLETO revisto (com o mesmo formato e todas as secções, incluindo "
             f"as soluções e os critérios, se existirem): {instrucao.strip()}"}]


def resumo_conversa(turnos: list) -> str:
    linhas = []
    for t in turnos:
        if t.get("papel") == "ia":
            msg = (t.get("json") or {}).get("mensagem", "")
            if msg:
                linhas.append(f"Assistente: {msg}")
        elif str(t.get("texto") or "").strip():
            linhas.append(f"Professor: {t['texto'].strip()}")
    return "\n".join(linhas)[-3000:]


def limpar_material(texto: str) -> str:
    """Tira cercas de código à volta e espaços a mais (às vezes a IA põe o Markdown dentro de ```markdown)."""
    t = str(texto or "").strip()
    t = re.sub(r"^```(?:markdown|md)?\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


def titulo_do_material(texto: str, alternativo: str = "Material") -> str:
    m = re.search(r"^#\s+(.+)$", texto or "", flags=re.M)
    return re.sub(r"[*_`]", "", m.group(1)).strip()[:90] if m else (alternativo or "Material")[:90]


# ---------------------------------------------------------------- o que a IA está a fazer (o estado mostrado ao professor)
NOME_EM_CURSO = {"aula": "no plano de aula", "ficha": "na ficha de exercícios", "teste": "no teste", "outro": "no recurso"}


def _curto(texto: str, n: int = 48) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def estado_turno(turnos: list, modelo: dict | None = None) -> tuple[str, str]:
    """(título, detalhe) enquanto a IA lê a última coisa que o professor disse."""
    ultimo = next((t for t in reversed(turnos or []) if t.get("papel") == "prof"), {})
    texto = str(ultimo.get("texto") or "")
    if modelo and modelo.get("nome") and "Anexei um modelo" in texto:
        return "A ler o modelo", f"«{_curto(modelo['nome'], 40)}»: estrutura, nível e tipos de pergunta"
    if sum(1 for t in turnos or [] if t.get("papel") == "prof") <= 1:
        return "A preparar a primeira pergunta", _curto(texto) or "A ver o que preciso de saber"
    return "A ler a tua resposta", f"«{_curto(texto, 40)}» · a ver o que ainda falta"


def estado_material(tipo: str, dados: dict | None, modelo: dict | None = None) -> tuple[str, str]:
    """(título, detalhe) antes de começar a escrever o material."""
    partes = [_curto(v, 30) for k, v in (dados or {}).items() if k not in ("uso_modelo",) and v][:3]
    if modelo and modelo.get("nome"):
        uso = uso_do_modelo(dados)
        partes.append({"formato": "no formato de", "base": "a partir de", "adaptar": "a adaptar"}.get(uso, "com o modelo")
                      + f" «{_curto(modelo['nome'], 28)}»")
    return f"A pensar {NOME_EM_CURSO.get(tipo, 'no material')}", " · ".join(partes)


def secoes_escritas(texto: str) -> list:
    """Os títulos (## e ###) já escritos, pela ordem, sem a formatação."""
    return [re.sub(r"[*_`]", "", m.group(2)).strip() for m in re.finditer(r"^(#{2,3})\s+(.+?)\s*#*\s*$", texto or "", re.M)]


def estado_escrita(texto: str, a_rever: str = "") -> tuple[str, str]:
    """(título, detalhe) enquanto o material vai chegando: a secção que está a ser escrita e as que já estão."""
    secoes = secoes_escritas(texto)
    prefixo = f"{a_rever} · " if a_rever else ""
    if not secoes:
        return "A escrever o título e o cabeçalho", prefixo.rstrip(" ·")
    feitas = secoes[:-1]
    detalhe = (f"Já escrevi: {' · '.join(_curto(x, 26) for x in feitas[-3:])}" if feitas else "A primeira secção")
    if len(feitas) > 3:
        detalhe = f"{len(feitas)} secções feitas · " + detalhe
    return f"A escrever: {_curto(secoes[-1], 44)}", prefixo + detalhe


# ---------------------------------------------------------------- guardar (no perfil da conta)
def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def novo_material(tipo: str, titulo: str, dados: dict, conteudo: str, turnos: list, sugestao: str = "",
                  modelo: dict | None = None) -> dict:
    momento = agora()
    return {"id": uuid.uuid4().hex[:12], "tipo": tipo if tipo in TIPOS else "outro", "sugestao": sugestao,
            "modelo": {"nome": modelo.get("nome", ""), "texto": str(modelo.get("texto") or "")[:MAX_MODELO]} if modelo else None,
            "titulo": titulo or "Material", "dados": dict(dados or {}), "conversa": list(turnos or []),
            "versoes": [{"conteudo": conteudo, "criado_em": momento, "nota": "Criado com a IA"}],
            "criado_em": momento, "atualizado_em": momento}


def juntar_versao(material: dict, conteudo: str, nota: str) -> dict:
    material.setdefault("versoes", []).append({"conteudo": conteudo, "criado_em": agora(), "nota": nota})
    material["versoes"] = material["versoes"][-MAX_VERSOES:]
    material["atualizado_em"] = agora()
    material["titulo"] = titulo_do_material(conteudo, material.get("titulo"))
    return material


def lista_ordenada(materiais: list) -> list:
    return sorted((m for m in materiais or [] if isinstance(m, dict) and m.get("versoes")),
                  key=lambda m: m.get("atualizado_em") or "", reverse=True)


def procurar(materiais: list, ident: str) -> dict | None:
    return next((m for m in materiais or [] if isinstance(m, dict) and m.get("id") == ident), None)


# ---------------------------------------------------------------- Markdown → blocos (para o Word e o PDF)
_ITEM = re.compile(r"^(\s*)([-*+•]|\d+[.)])\s+(.*)$")
_LINHA_RESPOSTA = re.compile(r"^[_\s]{6,}$")
_REGRA = re.compile(r"^(?:-\s*){3,}$|^(?:\*\s*){3,}$")


def _celulas(linha: str) -> list:
    s = linha.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def blocos(md: str) -> list:
    """Blocos do Markdown que a IA escreve: ("h", nível, texto), ("p", [linhas]), ("lista", ordenada, [(nível, marca,
    texto)]), ("tabela", cabeçalho, linhas), ("regra",), ("resposta", texto), ("citacao", texto)."""
    linhas = str(md or "").replace("\r", "").split("\n")
    out, para, i = [], [], 0

    def fecha():
        if para:
            out.append(("p", list(para)))
            para.clear()

    while i < len(linhas):
        bruta = linhas[i]
        s = bruta.strip()
        if not s:
            fecha()
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
        if m:
            fecha()
            out.append(("h", len(m.group(1)), m.group(2)))
            i += 1
            continue
        if _LINHA_RESPOSTA.match(s) and "_" in s:
            fecha()
            out.append(("resposta", s))
            i += 1
            continue
        if _REGRA.match(s):
            fecha()
            out.append(("regra",))
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(linhas) and re.match(r"^\|?\s*:?-{2,}", linhas[i + 1].strip()):
            fecha()
            cab = _celulas(s)
            i += 2
            corpo = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                corpo.append(_celulas(linhas[i]))
                i += 1
            n = len(cab)
            out.append(("tabela", cab, [(c + [""] * n)[:n] for c in corpo]))
            continue
        m = _ITEM.match(bruta)
        if m:
            fecha()
            itens = []
            ordenada = bool(re.match(r"\d", m.group(2)))
            while i < len(linhas):
                m2 = _ITEM.match(linhas[i])
                if m2:
                    nivel = 1 if len(m2.group(1).replace("\t", "    ")) >= 2 else 0
                    marca = m2.group(2) if re.match(r"\d", m2.group(2)) else "•"
                    itens.append([nivel, marca, m2.group(3).strip()])
                    i += 1
                elif linhas[i].strip() and linhas[i].startswith(("  ", "\t")) and itens:
                    itens[-1][2] += " " + linhas[i].strip()  # continuação do item anterior
                    i += 1
                else:
                    break
            out.append(("lista", ordenada, [tuple(x) for x in itens]))
            continue
        if s.startswith(">"):
            fecha()
            out.append(("citacao", s.lstrip("> ").strip()))
            i += 1
            continue
        para.append(s)
        i += 1
    fecha()
    return out


_EM_LINHA = re.compile(r"\*\*(.+?)\*\*|__(?=[^\s_])(.+?)(?<=[^\s_])__|(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?!\*)"
                       r"|(?<![\w_])_(?=[^\s_])([^_]+?)(?<=\S)_(?![\w_])|`([^`]+)`")


def pedacos(texto: str) -> list:
    """Texto com **negrito**, *itálico* e `código` → [(texto, negrito, itálico, código)]."""
    out, pos = [], 0
    for m in _EM_LINHA.finditer(texto or ""):
        if m.start() > pos:
            out.append((texto[pos:m.start()], False, False, False))
        if m.group(1) is not None or m.group(2) is not None:
            out.append((m.group(1) if m.group(1) is not None else m.group(2), True, False, False))
        elif m.group(3) is not None or m.group(4) is not None:
            out.append((m.group(3) if m.group(3) is not None else m.group(4), False, True, False))
        else:
            out.append((m.group(5), False, False, True))
        pos = m.end()
    if pos < len(texto or ""):
        out.append((texto[pos:], False, False, False))
    return [p for p in out if p[0]]


def _html_em_linha(texto: str) -> str:
    partes = []
    for t, b, it, cod in pedacos(texto):
        t = html.escape(t)
        if cod:
            t = f"<code>{t}</code>"
        if it:
            t = f"<i>{t}</i>"
        if b:
            t = f"<b>{t}</b>"
        partes.append(t)
    return "".join(partes)


def para_html(titulo: str, md: str) -> str:
    """HTML simples (para o PDF)."""
    bs = blocos(md)
    corpo = [] if bs and bs[0][0] == "h" and bs[0][1] == 1 else [f"<h1>{html.escape(titulo)}</h1>"]
    for b in bs:
        if b[0] == "h":
            n = min(b[1], 4)
            corpo.append(f"<h{n}>{_html_em_linha(b[2])}</h{n}>")
        elif b[0] == "p":
            corpo.append("<p>" + "<br/>".join(_html_em_linha(x) for x in b[1]) + "</p>")
        elif b[0] == "resposta":
            corpo.append('<p class="resposta">' + "_" * 70 + "</p>")
        elif b[0] == "regra":
            corpo.append("<hr/>")
        elif b[0] == "citacao":
            corpo.append(f"<p class='citacao'><i>{_html_em_linha(b[1])}</i></p>")
        elif b[0] == "lista":
            linhas = []
            for nivel, marca, texto in b[2]:
                recuo = 14 + 18 * nivel
                linhas.append(f"<p class='item' style='margin-left:{recuo}pt'>{html.escape(marca)}&#160;&#160;"
                              f"{_html_em_linha(texto)}</p>")
            corpo.append("".join(linhas))
        elif b[0] == "tabela":
            cab = "".join(f"<th>{_html_em_linha(c)}</th>" for c in b[1])
            linhas = "".join("<tr>" + "".join(f"<td>{_html_em_linha(c)}</td>" for c in r) + "</tr>" for r in b[2])
            corpo.append(f"<table><tr>{cab}</tr>{linhas}</table>")
    return "<html><body>" + "\n".join(corpo) + "</body></html>"


CSS_PDF = """
body { font-family: corpo, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #14222A; }
h1 { font-size: 18pt; margin: 0 0 8pt 0; color: #0F4C61; }
h2 { font-size: 13.5pt; margin: 14pt 0 5pt 0; color: #0F4C61; }
h3 { font-size: 11.5pt; margin: 10pt 0 4pt 0; }
h4 { font-size: 10.5pt; margin: 8pt 0 3pt 0; }
p { margin: 0 0 6pt 0; }
p.item { margin-top: 0; margin-bottom: 3pt; }
p.resposta { color: #8A989C; margin: 2pt 0 8pt 0; }
p.citacao { margin-left: 12pt; color: #3D4F56; }
table { border-collapse: collapse; margin: 4pt 0 10pt 0; width: 100%; }
th, td { border: 0.6pt solid #9AA8AC; padding: 3pt 5pt; vertical-align: top; font-size: 9.5pt; }
th { background-color: #E0F0F2; font-weight: bold; }
hr { margin: 12pt 0; }
code { font-family: monospace; }
"""

# Letras com os símbolos de Matemática e Ciências (√, π, ≤, ×…): Arial no Windows, DejaVu no Linux.
PASTAS_LETRA = [
    (Path("C:/Windows/Fonts"), ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
    (Path("/usr/share/fonts/truetype/dejavu"), ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf",
                                                "DejaVuSans-BoldOblique.ttf")),
    (Path("/Library/Fonts"), ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf")),
]


def _letra_pdf():
    """(pasta, css @font-face) da primeira letra que existir neste computador, ou (None, "")."""
    for pasta, (normal, negrito, italico, ambos) in PASTAS_LETRA:
        try:
            if (pasta / normal).exists():
                faces = [(normal, "normal", "normal"), (negrito, "bold", "normal"), (italico, "normal", "italic"),
                         (ambos, "bold", "italic")]
                css = "".join(f"@font-face {{ font-family: corpo; src: url({f}); font-weight: {w}; font-style: {s}; }}\n"
                              for f, w, s in faces if (pasta / f).exists())
                return pasta, css
        except OSError:
            continue
    return None, ""


def para_pdf(titulo: str, md: str) -> bytes:
    """PDF A4 do material (PyMuPDF, que a app já usa para ler PDFs)."""
    try:
        import pymupdf as fitz  # PyMuPDF (o nome novo; a app já o usa para ler PDFs)
    except ImportError:
        import fitz

    pasta, faces = _letra_pdf()
    arquivo = fitz.Archive(str(pasta)) if pasta else None
    historia = fitz.Story(html=para_html(titulo, md), user_css=faces + CSS_PDF, archive=arquivo)
    saida = io.BytesIO()
    escritor = fitz.DocumentWriter(saida)
    pagina = fitz.paper_rect("a4")
    area = pagina + (54, 54, -54, -60)
    mais = True
    while mais:
        dispositivo = escritor.begin_page(pagina)
        mais, _ = historia.place(area)
        historia.draw(dispositivo)
        escritor.end_page()
    escritor.close()
    return saida.getvalue()


def para_docx(titulo: str, md: str) -> bytes:
    """Documento Word do material, com títulos, listas, tabelas e as soluções numa página à parte."""
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.shared import Pt, RGBColor

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for nome, tamanho in (("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        try:
            doc.styles[nome].font.size = Pt(tamanho)
            doc.styles[nome].font.color.rgb = RGBColor(0x0F, 0x4C, 0x61)
        except KeyError:
            pass

    def escrever(paragrafo, texto):
        for t, b, it, cod in pedacos(texto):
            run = paragrafo.add_run(t)
            run.bold, run.italic = b or None, it or None
            if cod:
                run.font.name = "Consolas"

    bs = blocos(md)
    if not (bs and bs[0][0] == "h" and bs[0][1] == 1):
        doc.add_heading(titulo, level=0)
    for b in bs:
        if b[0] == "h":
            p = doc.add_heading("", level=0 if b[1] == 1 else min(b[1] - 1, 3))
            escrever(p, b[2])
        elif b[0] == "p":
            p = doc.add_paragraph()
            for n, linha in enumerate(b[1]):
                if n:
                    p.add_run().add_break()
                escrever(p, linha)
        elif b[0] == "resposta":
            doc.add_paragraph("_" * 78)
        elif b[0] == "regra":  # antes das soluções / critérios: página nova (para imprimir a ficha sem as respostas)
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif b[0] == "citacao":
            p = doc.add_paragraph()
            escrever(p, b[1])
            for r in p.runs:
                r.italic = True
        elif b[0] == "lista":
            for nivel, marca, texto in b[2]:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18 + 18 * nivel)
                p.paragraph_format.first_line_indent = Pt(-14)
                p.paragraph_format.space_after = Pt(2)
                p.add_run(f"{marca}\t" if marca != "•" else "•\t")
                escrever(p, texto)
        elif b[0] == "tabela":
            tabela = doc.add_table(rows=1 + len(b[2]), cols=len(b[1]))
            try:
                tabela.style = "Table Grid"
            except (KeyError, ValueError):
                pass
            for c, texto in enumerate(b[1]):
                celula = tabela.rows[0].cells[c]
                celula.paragraphs[0].text = ""
                escrever(celula.paragraphs[0], texto)
                for r in celula.paragraphs[0].runs:
                    r.bold = True
            for li, linha in enumerate(b[2], start=1):
                for c, texto in enumerate(linha):
                    escrever(tabela.rows[li].cells[c].paragraphs[0], texto)
            doc.add_paragraph()
    saida = io.BytesIO()
    doc.save(saida)
    return saida.getvalue()


def nome_ficheiro(titulo: str, extensao: str) -> str:
    import unicodedata

    base = "".join(c for c in unicodedata.normalize("NFD", titulo or "material") if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()[:60] or "material"
    return f"{base}.{extensao}"
