"""Laboratório de Biologia: processos passo a passo, divisão celular desenhada fase a fase, exercícios de genética com
resolução, simulação de osmose, Hardy-Weinberg e as instruções para a IA (sem Streamlit; testado em
testes_laboratorios.py). Os processos descritos aqui foram escritos para o ensino secundário/superior e não dependem da
IA; a IA explica mais a fundo, analisa experiências e dados e faz glossários e testes.
"""
from __future__ import annotations

import random
import re
from fractions import Fraction
from itertools import product

SECOES = {
    "explicar": ("Explicar", ":material/school:"),
    "processos": ("Processos", ":material/route:"),
    "genetica": ("Genética", ":material/genetics:"),
    "experiencias": ("Experiências", ":material/biotech:"),
    "dados": ("Gráficos e dados", ":material/monitoring:"),
    "testes": ("Testes", ":material/quiz:"),
    "glossario": ("Glossário", ":material/menu_book:"),
    "simulacoes": ("Simulações", ":material/play_circle:"),
}

RIGOR = ("Rigor científico: termos corretos (português de Portugal, terminologia do ensino em Portugal), sem inventar "
         "valores, nomes de estruturas ou resultados; se algo depender do organismo ou do manual (ex.: número de ATP), "
         "di-lo. Fórmulas químicas e equações em LaTeX ($...$).")


def sistema(nivel: str) -> str:
    return ("És um professor de Biologia, rigoroso e claro, que ajuda o aluno a compreender processos, visualizá-los e "
            f"resolver exercícios. Adaptas a profundidade e o vocabulário ao nível: {nivel}. " + RIGOR)


def pedido_explicacao(conceito: str) -> str:
    return (f"Explica o conceito biológico: {conceito}\nUsa estas secções (### título), curtas:\n### Definição\n"
            "### Como funciona\n### Componentes\n(estruturas/moléculas envolvidas e a função de cada uma)\n"
            "### Processos envolvidos\n(etapas numeradas)\n### Exemplos\n### Relações com outros conceitos\n"
            "### Erros comuns\n### Para memorizar\n(3 a 6 pontos)")


# ---------------------------------------------------------------- processos (conteúdo verificado, sem IA)
PROCESSOS = {
    "mitose": {
        "nome": "Mitose", "onde": "Núcleo das células eucarióticas (células somáticas)", "ciclo": False,
        "resumo": "Divisão do núcleo que origina dois núcleos com o mesmo número de cromossomas e a mesma informação "
                  "genética da célula-mãe. Com a citocinese, formam-se duas células-filhas iguais.",
        "etapas": [
            ("Interfase (antes da mitose)", "G1: a célula cresce. S: o DNA replica-se (cada cromossoma passa a ter dois "
             "cromatídios). G2: preparação para a divisão."),
            ("Prófase", "Os cromossomas condensam-se e ficam visíveis (dois cromatídios unidos pelo centrómero); forma-se "
             "o fuso acromático; o nucléolo desaparece."),
            ("Prometáfase", "O invólucro nuclear desagrega-se e os microtúbulos do fuso ligam-se aos cinetócoros dos "
             "centrómeros."),
            ("Metáfase", "Os cromossomas alinham-se no plano equatorial (placa metafásica), presos ao fuso."),
            ("Anáfase", "Os cromatídios-irmãos separam-se e migram para polos opostos: cada um passa a ser um cromossoma."),
            ("Telófase", "Os cromossomas descondensam-se, reorganizam-se os invólucros nucleares e os nucléolos."),
            ("Citocinese", "Divisão do citoplasma: por estrangulamento (células animais) ou formação da placa celular "
             "(células vegetais). Resultado: 2 células com o mesmo número de cromossomas (2n → 2n)."),
        ],
        "conceitos": ["cromatídio", "centrómero", "fuso acromático", "placa metafásica", "citocinese", "ciclo celular"],
    },
    "meiose": {
        "nome": "Meiose", "onde": "Células que originam gâmetas (ou esporos)", "ciclo": False,
        "resumo": "Duas divisões seguidas depois de uma só replicação do DNA: uma célula diploide (2n) origina quatro "
                  "células haploides (n), geneticamente diferentes.",
        "etapas": [
            ("Interfase", "O DNA replica-se: cada cromossoma fica com dois cromatídios."),
            ("Prófase I", "Os cromossomas homólogos emparelham (sinapse) e formam bivalentes (tétradas); nos quiasmas "
             "pode haver crossing-over (troca de segmentos entre cromatídios de homólogos)."),
            ("Metáfase I", "Os bivalentes alinham-se no plano equatorial; a orientação de cada par é aleatória "
             "(segregação independente)."),
            ("Anáfase I", "Separam-se os cromossomas homólogos (cada um ainda com dois cromatídios) para polos opostos."),
            ("Telófase I e citocinese", "Formam-se duas células haploides (n), com cromossomas de dois cromatídios. É a "
             "divisão reducional."),
            ("Prófase II e Metáfase II", "Sem nova replicação do DNA; os cromossomas alinham-se no plano equatorial de "
             "cada célula."),
            ("Anáfase II", "Separam-se os cromatídios-irmãos (divisão equacional)."),
            ("Telófase II e citocinese", "Formam-se quatro células haploides (n), geneticamente diferentes entre si "
             "(crossing-over e segregação independente)."),
        ],
        "conceitos": ["cromossomas homólogos", "bivalente", "crossing-over", "quiasma", "haploide", "diploide",
                      "segregação independente"],
    },
    "fotossintese": {
        "nome": "Fotossíntese", "onde": "Cloroplastos (tilacoides e estroma)", "ciclo": False,
        "resumo": "Conversão de energia luminosa em energia química: $6\\,CO_2 + 6\\,H_2O \\xrightarrow{luz} "
                  "C_6H_{12}O_6 + 6\\,O_2$.",
        "etapas": [
            ("Absorção da luz (tilacoides)", "Os pigmentos (clorofilas e carotenoides) dos fotossistemas II e I captam a "
             "energia luminosa e excitam eletrões."),
            ("Fotólise da água", "A água é decomposta: $2\\,H_2O \\rightarrow 4\\,H^+ + 4\\,e^- + O_2$. O oxigénio "
             "libertado vem da água."),
            ("Cadeia transportadora de eletrões", "Os eletrões passam pelos transportadores; é bombeado H⁺ para o lúmen "
             "do tilacoide e o NADP⁺ é reduzido a NADPH."),
            ("Fotofosforilação", "A ATP sintase usa o gradiente de H⁺ para produzir ATP."),
            ("Fixação do CO₂ (ciclo de Calvin, estroma)", "A RuBisCO junta o CO₂ à ribulose-1,5-bisfosfato (RuBP)."),
            ("Redução", "Com o ATP e o NADPH da fase fotoquímica forma-se gliceraldeído-3-fosfato (G3P), que origina "
             "glicose e outros compostos orgânicos."),
            ("Regeneração da RuBP", "Parte do G3P regenera a RuBP, com gasto de ATP, e o ciclo continua."),
        ],
        "conceitos": ["clorofila", "fotossistema", "fotólise", "ATP sintase", "NADPH", "ciclo de Calvin", "RuBisCO"],
    },
    "respiracao": {
        "nome": "Respiração celular aeróbia", "onde": "Citoplasma (hialoplasma) e mitocôndrias", "ciclo": False,
        "resumo": "Oxidação completa da glicose com produção de ATP: $C_6H_{12}O_6 + 6\\,O_2 \\rightarrow 6\\,CO_2 + "
                  "6\\,H_2O$ + energia.",
        "etapas": [
            ("Glicólise (hialoplasma)", "Uma glicose origina 2 piruvatos; saldo de 2 ATP e 2 NADH. Não precisa de O₂."),
            ("Formação de acetil-CoA (matriz)", "Cada piruvato é oxidado e descarboxilado: forma-se acetil-CoA, CO₂ e "
             "NADH."),
            ("Ciclo de Krebs (matriz)", "O acetil-CoA é oxidado: liberta CO₂ e forma NADH, FADH₂ e ATP (ou GTP)."),
            ("Cadeia transportadora de eletrões (membrana interna)", "O NADH e o FADH₂ cedem eletrões; a energia bombeia "
             "H⁺; o O₂ é o aceitador final e forma-se água."),
            ("Fosforilação oxidativa", "A ATP sintase usa o gradiente de H⁺ para produzir a maior parte do ATP (cerca "
             "de 30 a 32 por glicose; alguns manuais indicam 36 a 38)."),
        ],
        "conceitos": ["glicólise", "piruvato", "acetil-CoA", "ciclo de Krebs", "NADH", "FADH₂", "fosforilação oxidativa"],
    },
    "sintese_proteica": {
        "nome": "Síntese proteica", "onde": "Núcleo (transcrição) e ribossomas (tradução)", "ciclo": False,
        "resumo": "A informação de um gene (DNA) é copiada para mRNA e traduzida numa sequência de aminoácidos.",
        "etapas": [
            ("Transcrição", "A RNA polimerase lê a cadeia molde do DNA e sintetiza pré-mRNA no sentido 5'→3' "
             "(complementar: A→U, T→A, C→G, G→C)."),
            ("Processamento (eucariotas)", "Removem-se os intrões (splicing) e acrescentam-se o cap 5' e a cauda poli-A; o "
             "mRNA maduro sai pelos poros nucleares."),
            ("Iniciação da tradução", "O ribossoma liga-se ao mRNA e começa no codão de iniciação AUG, com o tRNA que "
             "transporta a metionina."),
            ("Alongamento", "Cada codão é emparelhado com o anticodão de um tRNA; formam-se ligações peptídicas entre os "
             "aminoácidos e o ribossoma avança."),
            ("Terminação", "Num codão de finalização (UAA, UAG ou UGA) o polipéptido é libertado."),
            ("Dobragem e modificação", "A cadeia dobra-se (estrutura 3D) e pode ser modificada (ex.: no complexo de "
             "Golgi)."),
        ],
        "conceitos": ["gene", "mRNA", "tRNA", "codão", "anticodão", "ribossoma", "ligação peptídica"],
    },
    "replicacao": {
        "nome": "Replicação do DNA", "onde": "Núcleo (eucariotas), na fase S da interfase", "ciclo": False,
        "resumo": "Cópia semiconservativa do DNA: cada nova molécula tem uma cadeia antiga e uma nova.",
        "etapas": [
            ("Origem de replicação", "A replicação começa em pontos específicos (origens); formam-se forquilhas."),
            ("Abertura da dupla hélice", "A helicase quebra as pontes de hidrogénio entre as bases; proteínas "
             "estabilizadoras mantêm as cadeias separadas e a topoisomerase alivia a tensão."),
            ("Primers", "A primase sintetiza pequenos iniciadores de RNA."),
            ("Síntese das novas cadeias", "A DNA polimerase junta nucleótidos complementares (A–T, C–G), sempre no "
             "sentido 5'→3': cadeia contínua e cadeia descontínua (fragmentos de Okazaki)."),
            ("Ligação e revisão", "Os primers são substituídos por DNA, a DNA ligase une os fragmentos e as polimerases "
             "corrigem erros (revisão)."),
        ],
        "conceitos": ["semiconservativa", "helicase", "DNA polimerase", "fragmentos de Okazaki", "DNA ligase"],
    },
    "transcricao_traducao": {
        "nome": "Transcrição e tradução (código genético)", "onde": "Núcleo e citoplasma", "ciclo": False,
        "resumo": "Como uma sequência de bases se torna uma sequência de aminoácidos. Experimenta na ferramenta "
                  "«Do DNA à proteína» (separador Genética).",
        "etapas": [
            ("Cadeia molde → mRNA", "Cada base da cadeia molde dá a base complementar no mRNA (A→U, T→A, C→G, G→C)."),
            ("Leitura em codões", "O mRNA é lido de 3 em 3 bases (codões), a partir do AUG, sem sobreposição."),
            ("Código genético", "64 codões: 61 codificam aminoácidos e 3 são de finalização. É redundante (vários codões "
             "para o mesmo aminoácido) e quase universal."),
            ("Anticodões", "Cada tRNA tem um anticodão complementar do codão e transporta o aminoácido correspondente."),
            ("Mutações", "Uma substituição pode não mudar o aminoácido (silenciosa), mudá-lo ou criar um codão de "
             "finalização; inserções e deleções mudam a grelha de leitura."),
        ],
        "conceitos": ["codão", "anticodão", "grelha de leitura", "redundância do código", "mutação"],
    },
    "transporte_membrana": {
        "nome": "Transporte através da membrana", "onde": "Membrana plasmática (modelo de mosaico fluido)", "ciclo": False,
        "resumo": "Como as substâncias entram e saem da célula, com ou sem gasto de energia.",
        "etapas": [
            ("Difusão simples", "A favor do gradiente de concentração, sem gasto de energia, através da bicamada "
             "fosfolipídica (O₂, CO₂, moléculas pequenas e apolares)."),
            ("Osmose", "Movimento de água através da membrana, do meio hipotónico para o hipertónico (também por "
             "aquaporinas). Vê a simulação em «Simulações»."),
            ("Difusão facilitada", "A favor do gradiente, sem ATP, com proteínas de canal ou transportadoras (ex.: glicose "
             "pelos transportadores GLUT)."),
            ("Transporte ativo", "Contra o gradiente, com gasto de ATP (ex.: bomba Na⁺/K⁺: 3 Na⁺ para fora e 2 K⁺ para "
             "dentro)."),
            ("Endocitose e exocitose", "Entrada (fagocitose, pinocitose, endocitose mediada por recetores) ou saída "
             "(exocitose) de partículas grandes em vesículas."),
        ],
        "conceitos": ["gradiente de concentração", "meio hipotónico", "meio hipertónico", "aquaporina", "bomba Na⁺/K⁺"],
    },
    "circulacao": {
        "nome": "Circulação sanguínea (ser humano)", "onde": "Coração e vasos sanguíneos", "ciclo": True,
        "resumo": "Circulação dupla (pulmonar e sistémica) e completa (o sangue venoso e o arterial não se misturam).",
        "etapas": [
            ("Aurícula direita", "Recebe o sangue venoso (pobre em O₂) do corpo, pelas veias cavas."),
            ("Ventrículo direito", "Passa pela válvula tricúspide e é bombeado para as artérias pulmonares."),
            ("Pulmões (hematose)", "Nos capilares dos alvéolos o sangue liberta CO₂ e recebe O₂."),
            ("Aurícula esquerda", "O sangue arterial (rico em O₂) chega pelas veias pulmonares."),
            ("Ventrículo esquerdo", "Passa pela válvula mitral (bicúspide) e é bombeado com força para a aorta."),
            ("Tecidos do corpo", "Nos capilares há trocas: os tecidos recebem O₂ e nutrientes e entregam CO₂ e "
             "resíduos; o sangue volta pelas veias até às veias cavas."),
        ],
        "conceitos": ["circulação dupla", "circulação completa", "hematose", "válvulas", "sístole", "diástole"],
    },
    "sistemas": {
        "nome": "Sistemas do organismo humano", "onde": "Organismo inteiro (homeostasia)", "ciclo": False,
        "resumo": "Os sistemas trabalham em conjunto para manter o equilíbrio interno (homeostasia).",
        "etapas": [
            ("Digestivo", "Digestão mecânica e química dos alimentos e absorção dos nutrientes (sobretudo no intestino "
             "delgado)."),
            ("Respiratório", "Ventilação pulmonar e trocas gasosas nos alvéolos (hematose)."),
            ("Circulatório", "Transporta O₂, nutrientes, hormonas e resíduos entre os órgãos."),
            ("Urinário (excretor)", "Os rins filtram o sangue, regulam a água e os sais e eliminam ureia na urina."),
            ("Nervoso", "Recebe estímulos, integra a informação e dá respostas rápidas (neurónios e sinapses)."),
            ("Endócrino", "Hormonas libertadas no sangue: regulação mais lenta e duradoura (ex.: insulina e glicemia)."),
            ("Imunitário", "Defesa não específica (barreiras, inflamação, fagocitose) e específica (linfócitos B e T, "
             "anticorpos)."),
        ],
        "conceitos": ["homeostasia", "hormona", "sinapse", "hematose", "imunidade"],
    },
}


def dot_processo(processo: dict, cor: str = "#3E8E5A") -> str:
    """Esquema do processo: etapas numeradas ligadas por setas (fechado em ciclo quando é um ciclo)."""
    import textwrap

    def q(t: str, largura: int = 26) -> str:
        return '"' + "\\n".join(textwrap.wrap(str(t).replace('"', "'").replace("\\", "/"), largura)) + '"'
    etapas = processo["etapas"]
    linhas = ['digraph G {', f'graph [bgcolor="transparent", rankdir={"LR" if len(etapas) <= 5 else "TB"}, pad=0.25, '
              'nodesep=0.3, ranksep=0.4];',
              'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#DCE3E1", '
              'fillcolor="#FFFFFF", fontcolor="#16232B", margin="0.18,0.1"];',
              f'edge [color="{cor}", penwidth=1.4, arrowsize=0.8];']
    for i, etapa in enumerate(etapas):
        titulo = etapa[0] if isinstance(etapa, (list, tuple)) else etapa.get("titulo", "")
        linhas.append(f'p{i} [label={q(f"{i + 1}. {titulo}")}' + (f', color="{cor}", penwidth=1.6' if i == 0 else "") + "];")
    for i in range(len(etapas) - 1):
        linhas.append(f"p{i} -> p{i + 1};")
    if processo.get("ciclo") and len(etapas) > 2:
        linhas.append(f'p{len(etapas) - 1} -> p0 [style=dashed];')
    return "\n".join(linhas + ["}"])


def pedido_processo(nome: str) -> str:
    return (f"Descreve o processo biológico «{nome}» em etapas para estudar. Responde só com JSON: "
            '{"nome": "...", "onde": "onde acontece", "resumo": "2 frases", "ciclo": false, '
            '"etapas": [{"titulo": "curto", "descricao": "1-2 frases"}], "conceitos": ["..."]}. 4 a 10 etapas, pela '
            "ordem certa. " + RIGOR)


def validar_processo(d: dict) -> dict:
    etapas = [(" ".join(str(e.get("titulo", "")).split())[:80], " ".join(str(e.get("descricao", "")).split())[:500])
              for e in (d or {}).get("etapas") or [] if isinstance(e, dict) and e.get("titulo")]
    if len(etapas) < 2:
        raise ValueError("O processo veio sem etapas.")
    return {"nome": str((d or {}).get("nome") or "Processo")[:80], "onde": str((d or {}).get("onde") or "")[:200],
            "resumo": str((d or {}).get("resumo") or "")[:600], "ciclo": bool((d or {}).get("ciclo")),
            "etapas": etapas[:12], "conceitos": [str(c)[:60] for c in (d or {}).get("conceitos") or []][:10]}


# ---------------------------------------------------------------- divisão celular desenhada fase a fase (SVG)
FASES = {
    "mitose": ["Interfase", "Prófase", "Metáfase", "Anáfase", "Telófase e citocinese"],
    "meiose": ["Interfase", "Prófase I", "Metáfase I", "Anáfase I", "Telófase I", "Metáfase II", "Anáfase II",
               "Telófase II"],
}
_COR = {"m": "#C2410C", "p": "#2563EB"}  # origem materna (laranja) e paterna (azul)
# 2n = 4: par 1 (longo) e par 2 (curto), um homólogo materno e um paterno
_CROMOSSOMAS = [("m", 46), ("p", 46), ("m", 28), ("p", 28)]


def _cromatidio(x: float, y: float, comp: float, cor: str, ponta: str | None = None) -> str:
    """Um cromatídio vertical centrado em (x, y). «ponta»: cor do segmento trocado no crossing-over."""
    s = f'<rect x="{x - 3:.1f}" y="{y - comp / 2:.1f}" width="6" height="{comp:.1f}" rx="3" fill="{cor}"/>'
    if ponta:
        s += f'<rect x="{x - 3:.1f}" y="{y + comp / 2 - comp * 0.3:.1f}" width="6" height="{comp * 0.3:.1f}" rx="3" fill="{ponta}"/>'
    return s


def _cromossoma(x: float, y: float, comp: float, cor: str, duplicado: bool = True, pontas=(None, None)) -> str:
    if not duplicado:
        return _cromatidio(x, y, comp, cor, pontas[0])
    return (_cromatidio(x - 3.5, y, comp, cor, pontas[0]) + _cromatidio(x + 3.5, y, comp, cor, pontas[1])
            + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#16232B" opacity="0.55"/>')


def _celula(cx: float, cy: float, rx: float, ry: float, nucleo: str = "") -> str:
    s = (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#E8F4F1" stroke="#7FB8AE" stroke-width="2"/>')
    if nucleo == "inteiro":
        s += f'<circle cx="{cx}" cy="{cy}" r="{min(rx, ry) * 0.55}" fill="#F7FBFA" stroke="#9BB8B2" stroke-width="1.5"/>'
    elif nucleo == "a_desaparecer":
        s += (f'<circle cx="{cx}" cy="{cy}" r="{min(rx, ry) * 0.6}" fill="none" stroke="#9BB8B2" stroke-width="1.5" '
              'stroke-dasharray="5 5"/>')
    return s


def _fuso(cx: float, cy: float, rx: float, alvos: list) -> str:
    """Polos e microtúbulos: cada polo liga-se aos alvos do seu lado (os do meio ligam-se aos dois)."""
    s = ""
    for lado, px in ((-1, cx - rx * 0.86), (1, cx + rx * 0.86)):
        s += f'<circle cx="{px:.1f}" cy="{cy}" r="4" fill="#7C8C91"/>'
        for (ax, ay) in alvos:
            if abs(ax - cx) > 15 and (ax - cx) * lado < 0:
                continue  # não cruza a célula: este alvo pertence ao outro polo
            s += f'<line x1="{px:.1f}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#9AA9AD" stroke-width="0.9"/>'
    return s


def svg_divisao(tipo: str, fase: int) -> str:
    """Desenho da fase da mitose ou da meiose numa célula com 2n = 4 (dois pares de homólogos)."""
    fases = FASES[tipo]
    fase = max(0, min(fase, len(fases) - 1))
    nome = fases[fase]
    W, H, cx, cy = 560, 260, 280, 130
    corpo = ""
    if nome == "Interfase":
        corpo += _celula(cx, cy, 170, 105, "inteiro")
        for i, (o, comp) in enumerate(_CROMOSSOMAS):  # cromatina descondensada (fios)
            x0 = cx - 40 + i * 24
            corpo += (f'<path d="M{x0},{cy - 30} q12,15 0,30 q-12,15 0,30" fill="none" stroke="{_COR[o]}" '
                      'stroke-width="2.2" opacity="0.75"/>')
        corpo += f'<circle cx="{cx + 22}" cy="{cy - 18}" r="9" fill="#9BB8B2"/>'
    elif nome == "Prófase":
        corpo += _celula(cx, cy, 170, 105, "a_desaparecer")
        for i, (o, comp) in enumerate(_CROMOSSOMAS):
            corpo += _cromossoma(cx - 45 + i * 30, cy + (-15 if i % 2 else 12), comp, _COR[o])
        corpo += _fuso(cx, cy, 170, [])
    elif nome == "Prófase I":  # homólogos emparelhados (bivalentes) com crossing-over
        corpo += _celula(cx, cy, 170, 105, "a_desaparecer")
        for par, (xc, comp) in enumerate([(cx - 30, 46), (cx + 35, 28)]):
            corpo += _cromossoma(xc - 9, cy, comp, _COR["m"], pontas=(None, _COR["p"]))
            corpo += _cromossoma(xc + 9, cy, comp, _COR["p"], pontas=(_COR["m"], None))
        corpo += f'<text x="{cx - 30}" y="{cy + 50}" font-size="11" text-anchor="middle" fill="#5A6B70">quiasma</text>'
    elif nome == "Metáfase":
        corpo += _celula(cx, cy, 170, 105)
        ys = [cy - 66, cy - 22, cy + 22, cy + 66]
        corpo += _fuso(cx, cy, 170, [(cx, y) for y in ys])
        for (o, comp), y in zip(_CROMOSSOMAS, ys):
            corpo += f'<g transform="rotate(90 {cx} {y})">{_cromossoma(cx, y, comp * 0.8, _COR[o])}</g>'
        corpo += f'<line x1="{cx}" y1="{cy - 100}" x2="{cx}" y2="{cy + 100}" stroke="#C8932F" stroke-dasharray="4 4"/>'
    elif nome == "Metáfase I":  # bivalentes no plano equatorial: um homólogo de cada lado
        corpo += _celula(cx, cy, 170, 105)
        ys = [cy - 35, cy + 35]
        corpo += _fuso(cx, cy, 170, [(cx - 12, y) for y in ys] + [(cx + 12, y) for y in ys])
        for (comp, y, esq) in [(46, ys[0], "m"), (28, ys[1], "p")]:  # orientação aleatória dos pares
            dirr = "p" if esq == "m" else "m"
            corpo += _cromossoma(cx - 12, y, comp, _COR[esq], pontas=(None, _COR[dirr]))
            corpo += _cromossoma(cx + 12, y, comp, _COR[dirr], pontas=(_COR[esq], None))
        corpo += f'<line x1="{cx}" y1="{cy - 100}" x2="{cx}" y2="{cy + 100}" stroke="#C8932F" stroke-dasharray="4 4"/>'
    elif nome == "Anáfase":  # cromatídios-irmãos para polos opostos
        corpo += _celula(cx, cy, 185, 100)
        ys = [cy - 54, cy - 18, cy + 18, cy + 54]
        corpo += _fuso(cx, cy, 185, [(cx - 95, y) for y in ys] + [(cx + 95, y) for y in ys])
        for (o, comp), y in zip(_CROMOSSOMAS, ys):
            for x in (cx - 95, cx + 95):
                corpo += f'<g transform="rotate(90 {x} {y})">{_cromossoma(x, y, comp * 0.75, _COR[o], False)}</g>'
    elif nome == "Anáfase I":  # homólogos (ainda com 2 cromatídios) para polos opostos
        corpo += _celula(cx, cy, 185, 100)
        ys = [cy - 35, cy + 35]
        corpo += _fuso(cx, cy, 185, [(cx - 95, y) for y in ys] + [(cx + 95, y) for y in ys])
        corpo += _cromossoma(cx - 95, ys[0], 46, _COR["m"], pontas=(None, _COR["p"]))
        corpo += _cromossoma(cx + 95, ys[0], 46, _COR["p"], pontas=(_COR["m"], None))
        corpo += _cromossoma(cx - 95, ys[1], 28, _COR["p"], pontas=(None, _COR["m"]))
        corpo += _cromossoma(cx + 95, ys[1], 28, _COR["m"], pontas=(_COR["p"], None))
    elif nome in ("Telófase e citocinese", "Telófase I"):
        for k, x in enumerate((cx - 120, cx + 120)):
            corpo += _celula(x, cy, 105, 90, "inteiro")
            if nome == "Telófase e citocinese":  # 2n = 4 em cada célula, cromossomas simples
                for i, (o, comp) in enumerate(_CROMOSSOMAS):
                    corpo += _cromossoma(x - 27 + i * 18, cy, comp * 0.8, _COR[o], False)
            else:  # n = 2, cromossomas com 2 cromatídios
                longo, curto = ("m", "p") if k == 0 else ("p", "m")
                corpo += _cromossoma(x - 14, cy, 40, _COR[longo], pontas=(None, _COR["p" if longo == "m" else "m"]))
                corpo += _cromossoma(x + 16, cy, 26, _COR[curto], pontas=(None, _COR["p" if curto == "m" else "m"]))
    elif nome in ("Metáfase II", "Anáfase II"):
        for k, x in enumerate((cx - 135, cx + 135)):
            corpo += _celula(x, cy, 120, 95)
            longo, curto = ("m", "p") if k == 0 else ("p", "m")
            outro = {"m": "p", "p": "m"}
            ys = [cy - 30, cy + 30]
            if nome == "Metáfase II":
                corpo += _fuso(x, cy, 120, [(x, y) for y in ys])
                corpo += f'<g transform="rotate(90 {x} {ys[0]})">{_cromossoma(x, ys[0], 40, _COR[longo], pontas=(None, _COR[outro[longo]]))}</g>'
                corpo += f'<g transform="rotate(90 {x} {ys[1]})">{_cromossoma(x, ys[1], 26, _COR[curto], pontas=(None, _COR[outro[curto]]))}</g>'
            else:
                corpo += _fuso(x, cy, 120, [(x - 62, y) for y in ys] + [(x + 62, y) for y in ys])
                for (cor_c, comp, y) in [(longo, 40, ys[0]), (curto, 26, ys[1])]:
                    corpo += f'<g transform="rotate(90 {x - 62} {y})">{_cromatidio(x - 62, y, comp, _COR[cor_c])}</g>'
                    corpo += (f'<g transform="rotate(90 {x + 62} {y})">'
                              f'{_cromatidio(x + 62, y, comp, _COR[cor_c], _COR[outro[cor_c]])}</g>')
    else:  # Telófase II: 4 células haploides diferentes
        combos = [("m", "p", False), ("m", "p", True), ("p", "m", False), ("p", "m", True)]
        for i, (longo, curto, recomb) in enumerate(combos):
            x = 75 + i * 137
            corpo += _celula(x, cy, 62, 62, "inteiro")
            outro = {"m": "p", "p": "m"}
            corpo += _cromatidio(x - 10, cy, 36, _COR[longo], _COR[outro[longo]] if recomb else None)
            corpo += _cromatidio(x + 12, cy, 22, _COR[curto], _COR[outro[curto]] if not recomb else None)
    legenda = ('<rect x="14" y="232" width="12" height="12" rx="3" fill="#C2410C"/><text x="31" y="242" font-size="12" '
               'fill="#5A6B70">origem materna</text><rect x="140" y="232" width="12" height="12" rx="3" fill="#2563EB"/>'
               '<text x="157" y="242" font-size="12" fill="#5A6B70">origem paterna</text>')
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{nome}" '
            f'style="width:100%;max-width:640px;height:auto;font-family:Inter,sans-serif">{corpo}{legenda}</svg>')


DESCRICAO_FASES = {
    ("mitose", "Interfase"): "O DNA está descondensado (cromatina) e replica-se na fase S. Núcleo e nucléolo visíveis.",
    ("mitose", "Prófase"): "Cromossomas condensados, cada um com 2 cromatídios; o invólucro nuclear desagrega-se; forma-se o fuso.",
    ("mitose", "Metáfase"): "Os 4 cromossomas alinham-se no plano equatorial, ligados ao fuso pelos cinetócoros.",
    ("mitose", "Anáfase"): "Os cromatídios-irmãos separam-se: cada polo recebe uma cópia de cada cromossoma.",
    ("mitose", "Telófase e citocinese"): "Duas células com 2n = 4, iguais entre si e à célula-mãe.",
    ("meiose", "Interfase"): "Replicação do DNA antes da meiose.",
    ("meiose", "Prófase I"): "Os homólogos emparelham (bivalentes) e trocam segmentos (crossing-over, nas pontas de outra cor).",
    ("meiose", "Metáfase I"): "Os bivalentes alinham-se no equador; cada par orienta-se ao acaso (segregação independente).",
    ("meiose", "Anáfase I"): "Separam-se os homólogos (não os cromatídios): é a divisão reducional.",
    ("meiose", "Telófase I"): "Duas células haploides (n = 2), cada cromossoma ainda com 2 cromatídios.",
    ("meiose", "Metáfase II"): "Em cada célula, os cromossomas alinham-se no equador (sem nova replicação).",
    ("meiose", "Anáfase II"): "Separam-se os cromatídios-irmãos, como na mitose.",
    ("meiose", "Telófase II"): "Quatro células haploides (n = 2), todas geneticamente diferentes.",
}


# ---------------------------------------------------------------- genética: exercícios gerados e resolvidos (sem IA)
TIPOS_GENETICA = {"monoibridismo": "Monoibridismo", "cruzamento_teste": "Cruzamento-teste",
                  "diibridismo": "Diibridismo", "ligado_x": "Hereditariedade ligada ao X",
                  "grupos_sanguineos": "Grupos sanguíneos (sistema AB0)"}


def _gametas(genotipo: str) -> list:
    pares = [genotipo[i:i + 2] for i in range(0, len(genotipo), 2)]
    return ["".join(c) for c in product(*pares)]


def _filho(g1: str, g2: str) -> str:
    return "".join("".join(sorted(a + b, key=lambda c: (c.lower(), c.islower()))) for a, b in zip(g1, g2))


def _fenotipo(genotipo: str, carateres: list) -> str:
    return ", ".join(carateres[i][0] if any(c.isupper() for c in genotipo[2 * i:2 * i + 2]) else carateres[i][1]
                     for i in range(len(genotipo) // 2))


def _tabela(g_pai: list, g_mae: list, celula) -> str:
    cab = "| | " + " | ".join(g_mae) + " |\n|---|" + "---|" * len(g_mae) + "\n"
    return cab + "\n".join(f"| **{gp}** | " + " | ".join(celula(gp, gm) for gm in g_mae) + " |" for gp in g_pai)


CARATERES = [  # (dominante, recessivo) — exemplos clássicos
    ("sementes amarelas", "sementes verdes"), ("sementes lisas", "sementes rugosas"), ("flores púrpura", "flores brancas"),
    ("caule alto", "caule anão"), ("pelo preto", "pelo castanho")]


def exercicio_genetica(tipo: str, semente: int) -> dict:
    """Exercício com enunciado, resposta exata (fração) e resolução passo a passo."""
    r = random.Random(semente)
    if tipo in ("monoibridismo", "cruzamento_teste"):
        dom, rec = r.choice(CARATERES)
        if tipo == "cruzamento_teste":
            pai, mae = r.choice(["Aa", "AA"]), "aa"
        else:
            pai, mae = r.choice([("Aa", "Aa"), ("Aa", "aa"), ("AA", "Aa"), ("Aa", "Aa")])
        alvo = r.choice(["rec", "dom", "het"])
        gp, gm = _gametas(pai), _gametas(mae)
        filhos = [_filho(a, b) for a in gp for b in gm]
        conta = {"rec": sum(f == "aa" for f in filhos), "dom": sum(f != "aa" for f in filhos),
                 "het": sum(f == "Aa" for f in filhos)}[alvo]
        resposta = Fraction(conta, len(filhos))
        pede = {"rec": f"com {rec}", "dom": f"com {dom}", "het": "heterozigótico (Aa)"}[alvo]
        enunciado = (f"Numa espécie, o alelo A ({dom}) é dominante sobre o alelo a ({rec}). Cruza-se um indivíduo {pai} "
                     f"com um indivíduo {mae}. Qual é a probabilidade de um descendente ser {pede}?")
        passos = [f"Gâmetas do progenitor {pai}: {', '.join(sorted(set(gp)))}. Gâmetas do progenitor {mae}: "
                  f"{', '.join(sorted(set(gm)))}.", "Quadro de Punnett:\n\n" + _tabela(gp, gm, _filho),
                  f"Casos favoráveis: {conta} em {len(filhos)} → {resposta} ({float(resposta):.0%})."]
    elif tipo == "diibridismo":
        (d1, r1), (d2, r2) = r.sample(CARATERES, 2)
        pai, mae = r.choice([("AaBb", "AaBb"), ("AaBb", "aabb"), ("AaBb", "Aabb")])
        alvo = r.choice(["dd", "rr", "dr"])
        gp, gm = _gametas(pai), _gametas(mae)
        filhos = [_filho(a, b) for a in gp for b in gm]
        car = [(d1, r1), (d2, r2)]
        fenos = [_fenotipo(f, car) for f in filhos]
        quer = {"dd": f"{d1}, {d2}", "rr": f"{r1}, {r2}", "dr": f"{d1}, {r2}"}[alvo]
        conta = sum(f == quer for f in fenos)
        resposta = Fraction(conta, len(filhos))
        enunciado = (f"A ({d1}) domina a ({r1}) e B ({d2}) domina b ({r2}); os genes estão em cromossomas diferentes. "
                     f"Cruza-se {pai} × {mae}. Qual é a probabilidade de um descendente ter {quer}?")
        contagem = {}
        for f in fenos:
            contagem[f] = contagem.get(f, 0) + 1
        passos = [f"Gâmetas de {pai}: {', '.join(gp)}; gâmetas de {mae}: {', '.join(sorted(set(gm)))} "
                  "(segregação independente).", "Quadro de Punnett:\n\n" + _tabela(gp, sorted(set(gm)), _filho),
                  "Proporções fenotípicas: " + "; ".join(f"{f}: {n}/{len(filhos)}" for f, n in contagem.items()) + ".",
                  f"{quer}: {conta}/{len(filhos)} = {resposta} ({float(resposta):.1%})."]
    elif tipo == "ligado_x":
        doenca = r.choice(["daltonismo", "hemofilia A"])
        mae = r.choice(["XᴬXᵃ", "XᴬXᴬ", "XᵃXᵃ"])
        pai = r.choice(["XᴬY", "XᵃY"])
        if mae == "XᴬXᴬ" and pai == "XᴬY":
            mae = "XᴬXᵃ"
        alvo = r.choice(["rapaz_afetado", "filha_portadora", "descendente_afetado"])
        gm = [mae[:2], mae[2:]]
        gp = [pai[:2], "Y"]
        filhos = [(a, b) for a in gp for b in gm]

        def gen(a, b):
            return b + a if a == "Y" else "".join(sorted([a, b], key=lambda x: x != "Xᴬ"))
        genos = [gen(a, b) for a, b in filhos]
        afetado = [("Y" in g and "Xᵃ" in g) or g == "XᵃXᵃ" for g in genos]
        if alvo == "rapaz_afetado":
            rapazes = [a for g, a in zip(genos, afetado) if "Y" in g]
            resposta = Fraction(sum(rapazes), len(rapazes))
            pede = f"um filho rapaz (sabendo que é rapaz) ter {doenca}"
        elif alvo == "filha_portadora":
            filhas = [g for g in genos if "Y" not in g]
            resposta = Fraction(sum(g == "XᴬXᵃ" for g in filhas), len(filhas))
            pede = f"uma filha (sabendo que é rapariga) ser portadora"
        else:
            resposta = Fraction(sum(afetado), len(genos))
            pede = f"um descendente qualquer ter {doenca}"
        enunciado = (f"O {doenca} deve-se a um alelo recessivo (Xᵃ) no cromossoma X. Uma mulher {mae} tem filhos com um "
                     f"homem {pai}. Qual é a probabilidade de {pede}?")
        passos = [f"Gâmetas da mulher: {', '.join(gm)}; gâmetas do homem: {', '.join(gp)}.",
                  "Quadro de Punnett:\n\n" + _tabela(gp, gm, gen),
                  "Os rapazes recebem o X da mãe e o Y do pai; um só Xᵃ basta para o rapaz ser afetado.",
                  f"Resposta: {resposta} ({float(resposta):.0%})."]
    elif tipo == "grupos_sanguineos":
        opcoes = {"IᴬIᴬ": "A", "Iᴬi": "A", "IᴮIᴮ": "B", "Iᴮi": "B", "IᴬIᴮ": "AB", "ii": "0"}
        pai, mae = r.choice([("Iᴬi", "Iᴮi"), ("IᴬIᴮ", "ii"), ("Iᴬi", "Iᴬi"), ("IᴬIᴮ", "Iᴮi"), ("Iᴮi", "ii")])
        alvo = r.choice(["0", "AB", "A", "B"])

        def partes(g):
            return [g[:2], g[2:]] if g != "ii" else ["i", "i"]
        gp, gm = partes(pai), partes(mae)

        def gen(a, b):
            ordem = {"Iᴬ": 0, "Iᴮ": 1, "i": 2}
            return "".join(sorted([a, b], key=lambda x: ordem[x]))
        grupos = [opcoes[gen(a, b)] for a in gp for b in gm]
        resposta = Fraction(grupos.count(alvo), len(grupos))
        enunciado = (f"No sistema AB0, Iᴬ e Iᴮ são codominantes e ambos dominam i. Um pai {pai} e uma mãe {mae} têm um "
                     f"filho. Qual é a probabilidade de ele ser do grupo {alvo}?")
        passos = [f"Gâmetas do pai: {', '.join(gp)}; da mãe: {', '.join(gm)}.",
                  "Quadro de Punnett:\n\n" + _tabela(gp, gm, gen),
                  "Grupos: " + ", ".join(grupos) + f" → grupo {alvo}: {grupos.count(alvo)}/4.",
                  f"Resposta: {resposta} ({float(resposta):.0%})."]
    else:
        raise ValueError("Tipo de exercício desconhecido.")
    return {"tipo": tipo, "semente": semente, "enunciado": enunciado, "resposta": str(resposta),
            "valor": float(resposta), "passos": passos}


def verificar_resposta(exercicio: dict, texto: str) -> bool | None:
    """True/False, ou None se a resposta não for um número (ex.: «1/4», «25 %», «0,25»)."""
    from exercicios import resposta_numerica

    v = resposta_numerica(texto)
    return None if v is None else abs(v - exercicio["valor"]) < 0.006


def hardy_weinberg(q2: float) -> dict:
    """A partir da frequência do fenótipo recessivo (q²): p, q, p², 2pq, q² (população em equilíbrio)."""
    if not 0 <= q2 <= 1:
        raise ValueError("A frequência tem de estar entre 0 e 1.")
    q = q2 ** 0.5
    p = 1 - q
    return {"p": p, "q": q, "AA": p * p, "Aa": 2 * p * q, "aa": q2}


# ---------------------------------------------------------------- IA: experiências, dados, glossário
def pedido_experiencia(texto: str) -> str:
    return ("Ajuda o aluno a interpretar esta experiência/atividade laboratorial:\n<experiencia>\n" + texto[:15000] +
            "\n</experiencia>\nResponde só com JSON: {\"problema\": \"problema científico (pergunta)\", \"hipotese\": "
            "\"...\", \"variaveis\": {\"independente\": \"...\", \"dependente\": \"...\", \"controladas\": [\"...\"]}, "
            "\"controlo\": \"grupo/ensaio de controlo e para que serve\", \"procedimento\": [\"passos resumidos\"], "
            "\"resultados\": \"o que os dados mostram (com os valores dados)\", \"conclusoes\": [\"...\"], "
            "\"erros\": [\"possíveis erros experimentais / limitações\"], \"melhorias\": [\"...\"], "
            "\"falta_informacao\": [\"o que não está no texto e não se pode concluir\"]}. Se algo não estiver no texto, "
            "diz que não está; não inventes valores. " + RIGOR)


def validar_experiencia(d: dict) -> dict:
    def t(v, n=800):
        return " ".join(str(v or "").split())[:n]

    def lista(v):
        return [t(x, 300) for x in ([v] if isinstance(v, str) else v or []) if t(x)][:8]
    if not isinstance(d, dict) or not t(d.get("problema") or d.get("resultados")):
        raise ValueError("A análise veio vazia.")
    var = d.get("variaveis") if isinstance(d.get("variaveis"), dict) else {}
    return {"problema": t(d.get("problema")), "hipotese": t(d.get("hipotese")),
            "variaveis": {"independente": t(var.get("independente"), 300), "dependente": t(var.get("dependente"), 300),
                          "controladas": lista(var.get("controladas"))},
            "controlo": t(d.get("controlo")), "procedimento": lista(d.get("procedimento")), "resultados": t(d.get("resultados"), 1200),
            "conclusoes": lista(d.get("conclusoes")), "erros": lista(d.get("erros")), "melhorias": lista(d.get("melhorias")),
            "falta_informacao": lista(d.get("falta_informacao"))}


def estatisticas(colunas: list, linhas: list) -> dict:
    """Resumo numérico de uma tabela (para a IA interpretar com números reais): por coluna numérica: mínimo, máximo,
    média; e a tendência (declive da reta de regressão) de cada coluna em função da primeira."""
    import statistics as st_

    num = {}
    for j, c in enumerate(colunas):
        valores = []
        for l in linhas:
            try:
                valores.append(float(str(l[j]).replace(",", ".")))
            except (TypeError, ValueError, IndexError):
                pass
        if len(valores) >= 2:
            num[c] = valores
    saida = {c: {"n": len(v), "min": min(v), "max": max(v), "media": round(st_.fmean(v), 4)} for c, v in num.items()}
    x_nome = colunas[0] if colunas and colunas[0] in num else None
    if x_nome:
        xs = num[x_nome]
        for c, ys in num.items():
            if c == x_nome or len(ys) != len(xs) or len(set(xs)) < 2:
                continue
            mx, my = st_.fmean(xs), st_.fmean(ys)
            declive = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
            saida[c]["declive_vs_" + x_nome] = round(declive, 4)
    return saida


def pedido_dados(descricao: str, colunas: list, linhas: list, est: dict) -> str:
    amostra = "\n".join([" | ".join(map(str, colunas))] + [" | ".join(map(str, l)) for l in linhas[:60]])
    return ("Interpreta estes dados de Biologia para o aluno. Contexto: " + (descricao or "(não indicado)") +
            f"\nDados:\n{amostra}\nResumo calculado pela app (valores exatos): {est}\nExplica: o que está a ser "
            "medido, a tendência principal (com os números), o significado biológico, limitações (ex.: poucos dados, "
            "correlação ≠ causa) e 2 perguntas para o aluno pensar. Usa ### títulos curtos. Não inventes valores. " + RIGOR)


def pedido_glossario(tema: str, n: int = 10) -> str:
    return (f"Cria um glossário de Biologia sobre: {tema}. {max(4, min(n, 20))} conceitos essenciais. Responde só com "
            'JSON: {"entradas": [{"conceito": "...", "definicao": "1-2 frases rigorosas", "exemplo": "...", '
            '"relacionados": ["outros conceitos"]}]}. ' + RIGOR)


def validar_glossario(d: dict) -> list:
    saida = []
    for e in (d or {}).get("entradas") or (d or {}).get("_lista") or []:
        if isinstance(e, dict) and str(e.get("conceito") or "").strip() and str(e.get("definicao") or "").strip():
            saida.append({"conceito": " ".join(str(e["conceito"]).split())[:80],
                          "definicao": " ".join(str(e["definicao"]).split())[:600],
                          "exemplo": " ".join(str(e.get("exemplo") or "").split())[:400],
                          "relacionados": [" ".join(str(x).split())[:60] for x in (e.get("relacionados") or [])][:6]})
    if not saida:
        raise ValueError("O glossário veio vazio.")
    return saida


def juntar_glossario(atual: list, novas: list) -> list:
    """Junta entradas novas ao glossário (a mais recente substitui a antiga do mesmo conceito), por ordem alfabética."""
    por_conceito = {re.sub(r"\s+", " ", e["conceito"].strip().lower()): e for e in atual or []}
    for e in novas:
        por_conceito[re.sub(r"\s+", " ", e["conceito"].strip().lower())] = e
    return sorted(por_conceito.values(), key=lambda e: e["conceito"].lower())


# ---------------------------------------------------------------- simulação de osmose (HTML do componente «simulacao»)
SIMULACAO_OSMOSE = """<div id="o" style="width:100%">
<div style="display:flex;flex-wrap:wrap;gap:12px 22px;align-items:center;margin-bottom:8px;font-size:13px;color:var(--texto)">
<label>Soluto à esquerda <input id="e" type="range" min="0" max="60" value="15"> <b id="ve"></b></label>
<label>Soluto à direita <input id="d" type="range" min="0" max="60" value="45"> <b id="vd"></b></label>
<button id="r" style="border:1px solid var(--linha);background:var(--cartao);border-radius:8px;padding:4px 12px;cursor:pointer">Repor</button>
</div><canvas id="c" style="width:100%;height:330px;display:block"></canvas>
<div id="t" style="font-size:13px;color:var(--suave);margin-top:6px"></div></div>
<script>
(function(){
const c=document.getElementById('c'),x=c.getContext('2d'),E=document.getElementById('e'),D=document.getElementById('d');
let vE=50,vD=50,parts=[],agua=[];
function cor(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#17798A';}
function repor(){vE=50;vD=50;criar();}
function criar(){parts=[];const ne=+E.value,nd=+D.value;
 for(let i=0;i<ne;i++)parts.push({l:0,u:Math.random(),v:Math.random()});
 for(let i=0;i<nd;i++)parts.push({l:1,u:Math.random(),v:Math.random()});
 agua=[];for(let i=0;i<70;i++)agua.push({l:i%2,u:Math.random(),v:Math.random(),du:(Math.random()-.5)*.01,dv:(Math.random()-.5)*.01});}
function passo(){const ne=+E.value,nd=+D.value;
 const ce=ne/vE,cd=nd/vD;              // concentração = soluto / volume
 const fluxo=0.9*(cd-ce);             // a água vai para onde há mais soluto (meio hipertónico)
 if(Math.abs(fluxo)>1e-4){const dv=Math.max(-vE+12,Math.min(vD-12,fluxo));vE-=dv;vD+=dv;
   const lado=fluxo>0?0:1;const a=agua.find(w=>w.l===lado&&Math.random()<.5);if(a&&Math.random()<Math.min(1,Math.abs(fluxo)*3)){a.l=1-lado;a.u=lado===0?0.02:0.98;}}
 return {ce,cd,fluxo};}
function desenha(){const r=c.getBoundingClientRect(),dpr=devicePixelRatio||1;c.width=r.width*dpr;c.height=330*dpr;x.setTransform(dpr,0,0,dpr,0,0);
 const W=r.width,H=330,meio=W/2,base=H-30,alt=230;const s=passo();
 x.clearRect(0,0,W,H);
 const hE=alt*vE/100,hD=alt*vD/100;
 x.fillStyle=cor('--bolha');x.fillRect(20,base-hE,meio-24,hE);x.fillRect(meio+4,base-hD,W-meio-24,hD);
 x.strokeStyle=cor('--linha');x.lineWidth=2;x.strokeRect(20,base-alt*1.2,W-40,alt*1.2);
 x.setLineDash([6,5]);x.strokeStyle=cor('--acento');x.beginPath();x.moveTo(meio,base-alt*1.2);x.lineTo(meio,base);x.stroke();x.setLineDash([]);
 for(const a of agua){a.u+=a.du;a.v+=a.dv;if(a.u<0||a.u>1)a.du*=-1;if(a.v<0||a.v>1)a.dv*=-1;a.u=Math.min(1,Math.max(0,a.u));a.v=Math.min(1,Math.max(0,a.v));
  const x0=a.l?meio+8:24,w=meio-36,h=a.l?hD:hE;x.fillStyle=cor('--acento2')||'#5FA8D3';x.beginPath();x.arc(x0+a.u*w,base-6-a.v*(h-12),2.4,0,7);x.fill();}
 for(const p of parts){const x0=p.l?meio+10:26,w=meio-40,h=p.l?hD:hE;x.fillStyle=cor('--acento3')||'#C8932F';x.beginPath();x.arc(x0+p.u*w,base-8-p.v*(h-16),5,0,7);x.fill();}
 x.fillStyle=cor('--texto');x.font='13px Inter, sans-serif';
 x.fillText('Concentração: '+s.ce.toFixed(2),28,24);x.fillText('Concentração: '+s.cd.toFixed(2),meio+12,24);
 const ton=(a,b)=>Math.abs(a-b)<0.02?'isotónico':(a>b?'hipertónico':'hipotónico');
 x.fillStyle=cor('--suave');x.fillText(ton(s.ce,s.cd),28,42);x.fillText(ton(s.cd,s.ce),meio+12,42);
 if(Math.abs(s.fluxo)>0.004){x.fillStyle=cor('--acento');x.font='bold 15px Inter, sans-serif';x.fillText(s.fluxo>0?'água →':'← água',meio-28,base-alt*1.2-6);}
 document.getElementById('ve').textContent=E.value;document.getElementById('vd').textContent=D.value;
 document.getElementById('t').textContent=Math.abs(s.fluxo)>0.004?('A água atravessa a membrana semipermeável para o lado '+(s.fluxo>0?'direito':'esquerdo')+' (mais soluto), até as concentrações se igualarem. O soluto (círculos grandes) não atravessa.'):'Equilíbrio: as concentrações são iguais (meios isotónicos); a água continua a passar, mas sem fluxo efetivo.';
 requestAnimationFrame(desenha);}
E.oninput=D.oninput=criar;document.getElementById('r').onclick=repor;criar();desenha();})();
</script>"""
