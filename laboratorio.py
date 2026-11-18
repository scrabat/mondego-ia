"""
Laboratório do Mondego IA — cálculos de Química, Biologia e Matemática (sem Streamlit, testáveis).

- Química: tabela periódica (118 elementos), massa molar de fórmulas (com parênteses e hidratos), acerto de equações.
- Biologia: transcrição e tradução (código genético padrão), quadrados de Punnett.
- Matemática: avaliação SEGURA de funções escritas pelo aluno (sem eval), raízes, derivadas, integrais e extremos.
"""

from __future__ import annotations

import ast
import itertools
import math
import re
from collections import Counter
from fractions import Fraction

import numpy as np


class ErroLab(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


# =========================================================================== QUÍMICA
_CATEGORIAS = {"al": "Metal alcalino", "at": "Metal alcalino-terroso", "mt": "Metal de transição",
               "pt": "Metal de pós-transição", "sm": "Semimetal", "nm": "Não metal", "ha": "Halogéneo",
               "gn": "Gás nobre", "la": "Lantanídeo", "ac": "Actinídeo"}
CORES_CATEGORIA = {"Metal alcalino": "#F2B8A2", "Metal alcalino-terroso": "#F6D49A", "Metal de transição": "#F3E3A6",
                   "Metal de pós-transição": "#C9DDB8", "Semimetal": "#B9DCCF", "Não metal": "#B8D4EE",
                   "Halogéneo": "#C9C2EA", "Gás nobre": "#E3BEDF", "Lantanídeo": "#F1C9B5", "Actinídeo": "#E7B9B9"}
_DADOS = """1 H Hidrogénio 1.008 nm 1 1|2 He Hélio 4.0026 gn 18 1|3 Li Lítio 6.94 al 1 2|4 Be Berílio 9.0122 at 2 2
|5 B Boro 10.81 sm 13 2|6 C Carbono 12.011 nm 14 2|7 N Azoto 14.007 nm 15 2|8 O Oxigénio 15.999 nm 16 2
|9 F Flúor 18.998 ha 17 2|10 Ne Néon 20.180 gn 18 2|11 Na Sódio 22.990 al 1 3|12 Mg Magnésio 24.305 at 2 3
|13 Al Alumínio 26.982 pt 13 3|14 Si Silício 28.085 sm 14 3|15 P Fósforo 30.974 nm 15 3|16 S Enxofre 32.06 nm 16 3
|17 Cl Cloro 35.45 ha 17 3|18 Ar Árgon 39.948 gn 18 3|19 K Potássio 39.098 al 1 4|20 Ca Cálcio 40.078 at 2 4
|21 Sc Escândio 44.956 mt 3 4|22 Ti Titânio 47.867 mt 4 4|23 V Vanádio 50.942 mt 5 4|24 Cr Crómio 51.996 mt 6 4
|25 Mn Manganês 54.938 mt 7 4|26 Fe Ferro 55.845 mt 8 4|27 Co Cobalto 58.933 mt 9 4|28 Ni Níquel 58.693 mt 10 4
|29 Cu Cobre 63.546 mt 11 4|30 Zn Zinco 65.38 mt 12 4|31 Ga Gálio 69.723 pt 13 4|32 Ge Germânio 72.630 sm 14 4
|33 As Arsénio 74.922 sm 15 4|34 Se Selénio 78.971 nm 16 4|35 Br Bromo 79.904 ha 17 4|36 Kr Crípton 83.798 gn 18 4
|37 Rb Rubídio 85.468 al 1 5|38 Sr Estrôncio 87.62 at 2 5|39 Y Ítrio 88.906 mt 3 5|40 Zr Zircónio 91.224 mt 4 5
|41 Nb Nióbio 92.906 mt 5 5|42 Mo Molibdénio 95.95 mt 6 5|43 Tc Tecnécio 98 mt 7 5|44 Ru Ruténio 101.07 mt 8 5
|45 Rh Ródio 102.91 mt 9 5|46 Pd Paládio 106.42 mt 10 5|47 Ag Prata 107.87 mt 11 5|48 Cd Cádmio 112.41 mt 12 5
|49 In Índio 114.82 pt 13 5|50 Sn Estanho 118.71 pt 14 5|51 Sb Antimónio 121.76 sm 15 5|52 Te Telúrio 127.60 sm 16 5
|53 I Iodo 126.90 ha 17 5|54 Xe Xénon 131.29 gn 18 5|55 Cs Césio 132.91 al 1 6|56 Ba Bário 137.33 at 2 6
|57 La Lantânio 138.91 la 0 6|58 Ce Cério 140.12 la 0 6|59 Pr Praseodímio 140.91 la 0 6|60 Nd Neodímio 144.24 la 0 6
|61 Pm Promécio 145 la 0 6|62 Sm Samário 150.36 la 0 6|63 Eu Európio 151.96 la 0 6|64 Gd Gadolínio 157.25 la 0 6
|65 Tb Térbio 158.93 la 0 6|66 Dy Disprósio 162.50 la 0 6|67 Ho Hólmio 164.93 la 0 6|68 Er Érbio 167.26 la 0 6
|69 Tm Túlio 168.93 la 0 6|70 Yb Itérbio 173.05 la 0 6|71 Lu Lutécio 174.97 la 0 6|72 Hf Háfnio 178.49 mt 4 6
|73 Ta Tântalo 180.95 mt 5 6|74 W Tungsténio 183.84 mt 6 6|75 Re Rénio 186.21 mt 7 6|76 Os Ósmio 190.23 mt 8 6
|77 Ir Irídio 192.22 mt 9 6|78 Pt Platina 195.08 mt 10 6|79 Au Ouro 196.97 mt 11 6|80 Hg Mercúrio 200.59 mt 12 6
|81 Tl Tálio 204.38 pt 13 6|82 Pb Chumbo 207.2 pt 14 6|83 Bi Bismuto 208.98 pt 15 6|84 Po Polónio 209 pt 16 6
|85 At Astato 210 ha 17 6|86 Rn Rádon 222 gn 18 6|87 Fr Frâncio 223 al 1 7|88 Ra Rádio 226 at 2 7
|89 Ac Actínio 227 ac 0 7|90 Th Tório 232.04 ac 0 7|91 Pa Protactínio 231.04 ac 0 7|92 U Urânio 238.03 ac 0 7
|93 Np Neptúnio 237 ac 0 7|94 Pu Plutónio 244 ac 0 7|95 Am Amerício 243 ac 0 7|96 Cm Cúrio 247 ac 0 7
|97 Bk Berquélio 247 ac 0 7|98 Cf Califórnio 251 ac 0 7|99 Es Einsténio 252 ac 0 7|100 Fm Férmio 257 ac 0 7
|101 Md Mendelévio 258 ac 0 7|102 No Nobélio 259 ac 0 7|103 Lr Laurêncio 262 ac 0 7|104 Rf Rutherfórdio 267 mt 4 7
|105 Db Dúbnio 268 mt 5 7|106 Sg Seabórgio 269 mt 6 7|107 Bh Bóhrio 270 mt 7 7|108 Hs Hássio 269 mt 8 7
|109 Mt Meitnério 278 mt 9 7|110 Ds Darmstácio 281 mt 10 7|111 Rg Roentgénio 282 mt 11 7|112 Cn Copernício 285 mt 12 7
|113 Nh Nipónio 286 pt 13 7|114 Fl Fleróvio 289 pt 14 7|115 Mc Moscóvio 290 pt 15 7|116 Lv Livermório 293 pt 16 7
|117 Ts Tenesso 294 ha 17 7|118 Og Oganésson 294 gn 18 7"""

ORBITAIS = ["1s", "2s", "2p", "3s", "3p", "4s", "3d", "4p", "5s", "4d", "5p", "6s", "4f", "5d", "6p", "7s", "5f", "6d", "7p"]
_CAP = {"s": 2, "p": 6, "d": 10, "f": 14}
_EXCECOES = {24: "[Ar] 3d5 4s1", 29: "[Ar] 3d10 4s1", 41: "[Kr] 4d4 5s1", 42: "[Kr] 4d5 5s1", 44: "[Kr] 4d7 5s1",
             45: "[Kr] 4d8 5s1", 46: "[Kr] 4d10", 47: "[Kr] 4d10 5s1", 57: "[Xe] 5d1 6s2", 58: "[Xe] 4f1 5d1 6s2",
             64: "[Xe] 4f7 5d1 6s2", 78: "[Xe] 4f14 5d9 6s1", 79: "[Xe] 4f14 5d10 6s1", 89: "[Rn] 6d1 7s2",
             90: "[Rn] 6d2 7s2", 91: "[Rn] 5f2 6d1 7s2", 92: "[Rn] 5f3 6d1 7s2", 93: "[Rn] 5f4 6d1 7s2",
             96: "[Rn] 5f7 6d1 7s2"}
_GASES = [(86, "Rn"), (54, "Xe"), (36, "Kr"), (18, "Ar"), (10, "Ne"), (2, "He")]


def _configuracao(z: int) -> str:
    if z in _EXCECOES:
        return _EXCECOES[z]
    nucleo, resto = "", z
    inicio = 0
    for zg, simbolo in _GASES:
        if z > zg:
            nucleo, resto = f"[{simbolo}] ", z - zg
            # orbitais já preenchidos pelo gás nobre
            soma, inicio = 0, 0
            while soma < zg:
                soma += _CAP[ORBITAIS[inicio][-1]]
                inicio += 1
            break
    partes = []
    for orb in ORBITAIS[inicio:]:
        if resto <= 0:
            break
        n = min(resto, _CAP[orb[-1]])
        partes.append(f"{orb}{n}")
        resto -= n
    return (nucleo + " ".join(partes)).strip()


ELEMENTOS: list[dict] = []
for _bloco in _DADOS.replace("\n", "").split("|"):
    _z, _s, _n, _m, _c, _g, _p = _bloco.split()
    ELEMENTOS.append({"z": int(_z), "simbolo": _s, "nome": _n, "massa": float(_m), "categoria": _CATEGORIAS[_c],
                      "grupo": int(_g) or None, "periodo": int(_p), "configuracao": _configuracao(int(_z))})
POR_SIMBOLO = {e["simbolo"]: e for e in ELEMENTOS}


def _ler_formula(formula: str) -> Counter:
    """Conta os átomos de uma fórmula: H2O, Ca(OH)2, K4[Fe(CN)6], CuSO4·5H2O."""
    texto = formula.strip().replace(" ", "")
    for sep in ("·", "•", "*", "."):
        if sep in texto:
            total = Counter()
            for parte in texto.split(sep):
                m = re.match(r"^(\d+)(.*)$", parte)
                k, resto = (int(m.group(1)), m.group(2)) if m else (1, parte)
                for el, n in _ler_formula(resto).items():
                    total[el] += n * k
            return total
    texto = re.sub(r"[\^]?\d*[+-]$", "", texto)  # carga no fim (ex.: SO4^2-) é ignorada
    pilha = [Counter()]
    i = 0
    while i < len(texto):
        c = texto[i]
        if c in "([{":
            pilha.append(Counter())
            i += 1
        elif c in ")]}":
            if len(pilha) == 1:
                raise ErroLab("Parênteses a mais na fórmula.")
            grupo = pilha.pop()
            m = re.match(r"\d+", texto[i + 1:])
            k = int(m.group()) if m else 1
            i += 1 + (len(m.group()) if m else 0)
            for el, n in grupo.items():
                pilha[-1][el] += n * k
        else:
            m = re.match(r"([A-Z][a-z]?)(\d*)", texto[i:])
            if not m:
                raise ErroLab(f"Não percebo «{texto[i:]}» na fórmula. Os símbolos começam por maiúscula (ex.: NaCl).")
            el = m.group(1)
            if el not in POR_SIMBOLO:
                raise ErroLab(f"O elemento «{el}» não existe.")
            pilha[-1][el] += int(m.group(2) or 1)
            i += len(m.group())
    if len(pilha) != 1:
        raise ErroLab("Falta fechar parênteses na fórmula.")
    if not pilha[0]:
        raise ErroLab("Escreve uma fórmula química (ex.: H2SO4).")
    return pilha[0]


def massa_molar(formula: str) -> dict:
    contagem = _ler_formula(formula)
    linhas = [{"elemento": el, "nome": POR_SIMBOLO[el]["nome"], "atomos": n, "massa_atomica": POR_SIMBOLO[el]["massa"],
               "contribuicao": round(n * POR_SIMBOLO[el]["massa"], 4)} for el, n in contagem.items()]
    total = sum(l["contribuicao"] for l in linhas)
    for l in linhas:
        l["percentagem"] = round(100 * l["contribuicao"] / total, 2)
    return {"formula": formula.strip(), "massa": round(total, 3), "composicao": linhas}


def acertar_equacao(equacao: str) -> dict:
    """Acerta uma equação química pelo método algébrico (espaço nulo da matriz dos elementos, com frações exatas)."""
    texto = equacao.replace("⟶", "->").replace("→", "->").replace("=>", "->").replace("=", "->")
    if texto.count("->") != 1:
        raise ErroLab("Escreve a equação com uma seta, por exemplo: H2 + O2 -> H2O")
    lados = [[s.strip() for s in lado.split("+") if s.strip()] for lado in texto.split("->")]
    if not lados[0] or not lados[1]:
        raise ErroLab("Faltam reagentes ou produtos.")
    especies = [re.sub(r"^\d+", "", s) for s in lados[0] + lados[1]]
    contagens = [_ler_formula(s) for s in especies]
    elementos = sorted({el for c in contagens for el in c})
    n_r = len(lados[0])
    matriz = [[Fraction(c.get(el, 0) * (1 if j < n_r else -1)) for j, c in enumerate(contagens)] for el in elementos]
    # eliminação de Gauss-Jordan
    linhas, colunas = len(matriz), len(especies)
    pivots, r = [], 0
    for col in range(colunas):
        piv = next((i for i in range(r, linhas) if matriz[i][col] != 0), None)
        if piv is None:
            continue
        matriz[r], matriz[piv] = matriz[piv], matriz[r]
        matriz[r] = [v / matriz[r][col] for v in matriz[r]]
        for i in range(linhas):
            if i != r and matriz[i][col] != 0:
                f = matriz[i][col]
                matriz[i] = [a - f * b for a, b in zip(matriz[i], matriz[r])]
        pivots.append(col)
        r += 1
    livres = [c for c in range(colunas) if c not in pivots]
    if len(livres) != 1:
        raise ErroLab("Esta equação não tem um acerto único (verifica as fórmulas ou se falta alguma espécie).")
    livre = livres[0]
    sol = [Fraction(0)] * colunas
    sol[livre] = Fraction(1)
    for i, col in enumerate(pivots):
        sol[col] = -matriz[i][livre]
    mmc = 1
    for v in sol:
        mmc = mmc * v.denominator // math.gcd(mmc, v.denominator)
    inteiros = [int(v * mmc) for v in sol]
    if any(v <= 0 for v in inteiros):
        inteiros = [-v for v in inteiros]
    if any(v <= 0 for v in inteiros):
        raise ErroLab("Não foi possível acertar esta equação (alguma espécie está do lado errado?).")
    g = 0
    for v in inteiros:
        g = math.gcd(g, v)
    inteiros = [v // g for v in inteiros]

    def lado(ini, fim):
        return " + ".join(f"{c if c > 1 else ''}{s}" for c, s in zip(inteiros[ini:fim], especies[ini:fim]))
    verificacao = {el: (sum(inteiros[j] * contagens[j].get(el, 0) for j in range(n_r)),
                        sum(inteiros[j] * contagens[j].get(el, 0) for j in range(n_r, colunas))) for el in elementos}
    return {"coeficientes": inteiros, "especies": especies, "acertada": f"{lado(0, n_r)} → {lado(n_r, colunas)}",
            "verificacao": verificacao}


# =========================================================================== BIOLOGIA
_BASES = "UCAG"
_AMINO = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODIGO_GENETICO = {a + b + c: _AMINO[16 * i + 4 * j + k]
                   for i, a in enumerate(_BASES) for j, b in enumerate(_BASES) for k, c in enumerate(_BASES)}
AMINOACIDOS = {"A": ("Ala", "Alanina"), "R": ("Arg", "Arginina"), "N": ("Asn", "Asparagina"), "D": ("Asp", "Ácido aspártico"),
               "C": ("Cys", "Cisteína"), "Q": ("Gln", "Glutamina"), "E": ("Glu", "Ácido glutâmico"), "G": ("Gly", "Glicina"),
               "H": ("His", "Histidina"), "I": ("Ile", "Isoleucina"), "L": ("Leu", "Leucina"), "K": ("Lys", "Lisina"),
               "M": ("Met", "Metionina"), "F": ("Phe", "Fenilalanina"), "P": ("Pro", "Prolina"), "S": ("Ser", "Serina"),
               "T": ("Thr", "Treonina"), "W": ("Trp", "Triptofano"), "Y": ("Tyr", "Tirosina"), "V": ("Val", "Valina"),
               "*": ("Stop", "Codão de finalização")}
_COMPLEMENTO = str.maketrans("ATCG", "TAGC")


def expressao_genica(sequencia: str, cadeia: str = "codificante", desde_aug: bool = True) -> dict:
    """DNA → mRNA → proteína. cadeia: 'codificante' (5'→3', igual ao mRNA com T) ou 'molde' (complementar, 3'→5')."""
    seq = re.sub(r"[\s\d\-]", "", sequencia.upper())
    if not seq:
        raise ErroLab("Escreve uma sequência de DNA (A, T, C, G).")
    if re.search(r"[^ATCGU]", seq):
        raise ErroLab("A sequência só pode ter as bases A, T, C e G.")
    seq = seq.replace("U", "T")
    codificante = seq if cadeia == "codificante" else seq.translate(_COMPLEMENTO)
    mrna = codificante.replace("T", "U")
    inicio = mrna.find("AUG") if desde_aug else 0
    if desde_aug and inicio < 0:
        return {"mrna": mrna, "inicio": None, "codoes": [], "proteina": "", "aviso": "Não há codão de iniciação (AUG)."}
    codoes, prot = [], []
    for i in range(inicio, len(mrna) - 2, 3):
        cod = mrna[i:i + 3]
        aa = CODIGO_GENETICO[cod]
        codoes.append({"codao": cod, "aa": aa, "abrev": AMINOACIDOS[aa][0], "nome": AMINOACIDOS[aa][1]})
        if aa == "*":
            break
        prot.append(aa)
    aviso = "" if codoes and codoes[-1]["aa"] == "*" else "Não apareceu codão de finalização (UAA, UAG ou UGA)."
    return {"mrna": mrna, "inicio": inicio, "codoes": codoes, "proteina": "".join(prot),
            "proteina_abrev": "-".join(AMINOACIDOS[a][0] for a in prot), "aviso": aviso}


def _gametas(genotipo: str) -> list[str]:
    g = genotipo.strip()
    if len(g) % 2 or not g.isalpha():
        raise ErroLab("Escreve cada genótipo com pares de letras, por exemplo Aa ou AaBb.")
    pares = [g[i:i + 2] for i in range(0, len(g), 2)]
    for p in pares:
        if p[0].lower() != p[1].lower():
            raise ErroLab(f"O par «{p}» mistura genes diferentes (deve ser AA, Aa ou aa).")
    return ["".join(c) for c in itertools.product(*pares)]


def punnett(pai: str, mae: str) -> dict:
    gp, gm = _gametas(pai), _gametas(mae)
    if len(gp[0]) != len(gm[0]) or {c.lower() for c in pai} != {c.lower() for c in mae}:
        raise ErroLab("Os dois progenitores têm de ter os mesmos genes (ex.: AaBb × AaBb).")

    def ordenar(gametas_a: str, gametas_b: str) -> str:
        return "".join("".join(sorted(par, key=lambda c: (c.lower(), c.islower()))) for par in zip(gametas_a, gametas_b))
    tabela = [[ordenar(a, b) for b in gm] for a in gp]
    genos = Counter(c for linha in tabela for c in linha)
    fenos = Counter(" ".join(("dominante " if any(ch.isupper() for ch in g[i:i + 2]) else "recessivo ") + g[i].upper()
                             for i in range(0, len(g), 2)) for linha in tabela for g in linha)
    total = len(gp) * len(gm)
    return {"gametas_pai": gp, "gametas_mae": gm, "tabela": tabela,
            "genotipos": {g: f"{n}/{total}" for g, n in sorted(genos.items())},
            "fenotipos": {f: f"{n}/{total}" for f, n in sorted(fenos.items(), key=lambda kv: -kv[1])}}


# =========================================================================== MATEMÁTICA (sem eval)
_FUNCOES = {"sin": np.sin, "sen": np.sin, "cos": np.cos, "tan": np.tan, "tg": np.tan, "asin": np.arcsin,
            "arcsen": np.arcsin, "arcsin": np.arcsin, "acos": np.arccos, "arccos": np.arccos, "atan": np.arctan,
            "arctg": np.arctan, "arctan": np.arctan, "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh, "exp": np.exp,
            "log": np.log, "ln": np.log, "log10": np.log10, "log2": np.log2, "sqrt": np.sqrt, "raiz": np.sqrt,
            "abs": np.abs, "floor": np.floor, "ceil": np.ceil, "sign": np.sign, "cbrt": np.cbrt}
_CONSTANTES = {"pi": math.pi, "e": math.e}
_OPERADORES = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide, ast.Pow: np.power,
               ast.Mod: np.mod}


def preparar_expressao(texto: str) -> str:
    t = (texto or "").strip().lower()
    t = re.sub(r"^\s*[a-z]\s*\(\s*[a-z]\s*(,\s*[a-z]\s*)?\)\s*=", "", t)  # tira "f(x) =" do início
    t = re.sub(r"^\s*[yz]\s*=", "", t)
    t = t.strip()
    t = t.replace("^", "**").replace("×", "*").replace("·", "*").replace("÷", "/").replace("−", "-").replace("π", "pi")
    t = t.replace("√", "sqrt")
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)                              # 2,5 → 2.5
    t = re.sub(r"(?<![a-z_\d.])(\d+(?:\.\d+)?)\s*([a-z(])", r"\1*\2", t)  # 2x → 2*x, 3(x+1) → 3*(x+1)
    t = re.sub(r"\)\s*([a-z\d(])", r")*\1", t)                         # (x+1)(x-1) → (x+1)*(x-1)
    t = re.sub(r"(?<![a-z])([xy])\s*(?=\()", r"\1*", t)                # x(x+1) → x*(x+1)
    return t


def compilar(texto: str, variaveis: tuple = ("x",)):
    """Transforma a expressão numa função numpy, verificando cada parte (só números, variáveis, operações e funções
    matemáticas conhecidas). Nunca executa código arbitrário."""
    expr = preparar_expressao(texto)
    if not expr:
        raise ErroLab("Escreve uma função, por exemplo x^2 - 3x + 2.")
    try:
        arvore = ast.parse(expr, mode="eval")
    except SyntaxError as erro:
        raise ErroLab("A expressão tem um erro de escrita (verifica parênteses e operações).") from erro

    def construir(no):
        if isinstance(no, ast.Expression):
            return construir(no.body)
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
            v = float(no.value)
            return lambda amb: v
        if isinstance(no, ast.Name):
            if no.id in variaveis:
                return lambda amb, n=no.id: amb[n]
            if no.id in _CONSTANTES:
                v = _CONSTANTES[no.id]
                return lambda amb: v
            raise ErroLab(f"Não conheço «{no.id}». Usa a variável {' e '.join(variaveis)}.")
        if isinstance(no, ast.BinOp) and type(no.op) in _OPERADORES:
            f, a, b = _OPERADORES[type(no.op)], construir(no.left), construir(no.right)
            return lambda amb: f(a(amb), b(amb))
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
            a = construir(no.operand)
            return (lambda amb: -a(amb)) if isinstance(no.op, ast.USub) else a
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id in _FUNCOES and len(no.args) == 1 \
                and not no.keywords:
            f, a = _FUNCOES[no.func.id], construir(no.args[0])
            return lambda amb: f(a(amb))
        raise ErroLab("A expressão só pode ter números, a variável, + − × ÷ ^ e funções como sin, cos, exp, log, sqrt.")
    calc = construir(arvore)

    def funcao(**valores):
        with np.errstate(all="ignore"):
            r = calc({k: np.asarray(v, dtype=float) for k, v in valores.items()})
            r = np.asarray(r, dtype=float) * np.ones(np.broadcast(*[np.asarray(v) for v in valores.values()]).shape)
        r[~np.isfinite(r)] = np.nan
        return r
    funcao.expressao = expr
    return funcao


def amostrar(f, a: float, b: float, n: int = 800):
    if not a < b:
        raise ErroLab("O início do intervalo tem de ser menor do que o fim.")
    x = np.linspace(a, b, n)
    y = f(x=x)
    # corta as "linhas verticais" nas assíntotas (ex.: tan x, 1/x)
    salto = np.abs(np.diff(y))
    limite = 50 * (np.nanmedian(salto) + 1e-9) if np.isfinite(salto).any() else np.inf
    y[1:][salto > max(limite, 1e3 * (b - a) / n)] = np.nan
    return x, y


def raizes(f, a: float, b: float, n: int = 4000) -> list[float]:
    x = np.linspace(a, b, n)
    y = f(x=x)
    encontradas = []
    for i in range(n - 1):
        y0, y1 = y[i], y[i + 1]
        if np.isnan(y0) or np.isnan(y1):
            continue
        if y0 == 0:
            encontradas.append(x[i])
        elif y0 * y1 < 0:
            lo, hi = x[i], x[i + 1]
            for _ in range(60):
                m = (lo + hi) / 2
                fm = float(f(x=np.array([m]))[0])
                if np.isnan(fm):
                    break
                if (float(f(x=np.array([lo]))[0]) < 0) == (fm < 0):
                    lo = m
                else:
                    hi = m
            r = (lo + hi) / 2
            if abs(float(f(x=np.array([r]))[0])) < 1e-6 * max(1.0, np.nanmax(np.abs(y))):  # não é uma assíntota
                encontradas.append(r)
    unicas = []
    for r in encontradas:
        if not unicas or abs(r - unicas[-1]) > (b - a) / n * 2:
            unicas.append(r)
    return [round(float(r), 6) + 0.0 for r in unicas]


def derivada(f, x0: float, h: float = 1e-5) -> float:
    v = (f(x=np.array([x0 + h]))[0] - f(x=np.array([x0 - h]))[0]) / (2 * h)
    return float(v)


def integral(f, a: float, b: float, n: int = 20000) -> float:
    if n % 2:
        n += 1
    x = np.linspace(a, b, n + 1)
    y = f(x=x)
    if np.isnan(y).any():
        raise ErroLab("A função não está definida em todo o intervalo, por isso o integral não é calculado.")
    h = (b - a) / n
    return float(h / 3 * (y[0] + y[-1] + 4 * y[1:-1:2].sum() + 2 * y[2:-1:2].sum()))


def extremos(f, a: float, b: float, n: int = 4000) -> list[dict]:
    x = np.linspace(a, b, n)
    y = f(x=x)
    saida = []
    for i in range(1, n - 1):
        if np.isnan(y[i - 1:i + 2]).any():
            continue
        if y[i] > y[i - 1] and y[i] >= y[i + 1]:
            saida.append({"tipo": "máximo", "x": round(float(x[i]), 4), "y": round(float(y[i]), 4)})
        elif y[i] < y[i - 1] and y[i] <= y[i + 1]:
            saida.append({"tipo": "mínimo", "x": round(float(x[i]), 4), "y": round(float(y[i]), 4)})
    return saida[:20]


def grelha_superficie(texto: str, intervalo: float = 3.0, n: int = 60, altura_max: float = 2.5) -> tuple[list, dict]:
    """z = f(x, y) numa grelha n × n, já escalada para o visualizador 3D. Devolve (alturas, info)."""
    f = compilar(texto, ("x", "y"))
    v = np.linspace(-intervalo, intervalo, n)
    xx, yy = np.meshgrid(v, v)
    zz = f(x=xx, y=yy)
    if np.isnan(zz).all():
        raise ErroLab("A função não tem valores reais neste intervalo.")
    zmin, zmax = float(np.nanmin(zz)), float(np.nanmax(zz))
    escala = altura_max / max(abs(zmin), abs(zmax), 1e-9)
    alturas = np.nan_to_num(zz * escala, nan=0.0)
    return [round(float(a), 4) for a in alturas.ravel()], {"zmin": zmin, "zmax": zmax, "escala": escala}
