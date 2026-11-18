"""
Fórmulas matemáticas "como no papel".

O Streamlit desenha fórmulas LaTeX com o KaTeX quando estão entre $...$ (na linha) ou $$...$$ (em destaque).
As IAs às vezes usam outros delimitadores (\\( \\), \\[ \\]) ou estragam as barras invertidas dentro do JSON
(ex.: "\\frac" passa a ser um carácter de controlo + "rac"). Este módulo corrige as duas coisas.
Não depende do Streamlit, para se poder testar sozinho.
"""

import re

# Instrução comum a todos os pedidos que podem ter fórmulas.
REGRAS_FORMULAS = (
    "Escreve TODAS as fórmulas, variáveis, expressões e unidades matemáticas em LaTeX: entre $...$ quando estão "
    "no meio do texto (ex.: $f(x)=x^2$, $\\alpha$, $\\frac{a}{b}$) e entre $$...$$ numa linha própria quando são "
    "fórmulas importantes ou longas. Nunca uses \\( \\) nem \\[ \\], nunca escrevas fórmulas em texto simples "
    "(como x^2, sqrt(x) ou a/b) e não uses blocos de código para fórmulas."
)
REGRAS_FORMULAS_JSON = REGRAS_FORMULAS + (
    " Como a resposta é JSON, cada barra invertida do LaTeX tem de ser escrita a dobrar (ex.: \"$\\\\frac{1}{2}$\")."
)

# Comandos LaTeX que começam pelas letras que o JSON usa em escapes (\b \f \n \r \t \u).
# Só estes são corrigidos quando aparecem completos — assim "\nOutra linha" continua a ser uma mudança de linha.
_COMANDOS_AMBIGUOS = {
    "b": "bar beta begin big Big bigg binom bmatrix boldsymbol bot bullet bmod boxed",
    "f": "frac forall flat frak",
    "n": "nabla neq neg not notin nu nless ngtr nleq ngeq nmid nparallel nsubseteq nexists",
    "r": "rho right rightarrow Rightarrow rightleftharpoons rangle rceil rfloor rbrace rvert rVert",
    "t": "tau text textbf textit textrm theta times tilde to top triangle tan tanh tfrac thinspace",
    "u": "underline underbrace uparrow Uparrow upsilon union",
}
_AMBIGUOS = {c for grupo in _COMANDOS_AMBIGUOS.values() for c in grupo.split()}


def reparar_json_latex(texto: str) -> str:
    """Dobra as barras invertidas do LaTeX que a IA deixou simples dentro do JSON, antes do json.loads.

    - \\sqrt, \\alpha, \\sum... (letras que não são escapes JSON) dariam erro de JSON;
    - \\frac, \\times, \\theta, \\neq, \\right... seriam lidos como carácter de controlo e estragavam a fórmula.
    As barras já dobradas (\\\\frac) ficam como estão.
    """
    def trocar(m: re.Match) -> str:
        barras, palavra = m.group(1), m.group(2)
        if len(barras) % 2 == 0:  # já estava escapada
            return m.group(0)
        if palavra[0] in "bfnrtu" and palavra not in _AMBIGUOS:
            return m.group(0)  # escape JSON verdadeiro (ex.: \n seguido de texto)
        return barras + "\\" + palavra
    return re.sub(r"(\\+)([A-Za-z]+)", trocar, texto)


_BLOCO_CODIGO = re.compile(r"(```.*?```|`[^`\n]+`)", re.S)


def _normalizar_trecho(t: str) -> str:
    # \[ ... \]  ->  $$ ... $$ numa linha própria
    t = re.sub(r"\\\[(.+?)\\\]", lambda m: "\n\n$$\n" + m.group(1).strip() + "\n$$\n\n", t, flags=re.S)
    # \( ... \)  ->  $ ... $
    t = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", t, flags=re.S)
    # $$ ... $$ no meio de uma frase -> numa linha própria (o KaTeX só o mostra em destaque assim)
    t = re.sub(r"\$\$(.+?)\$\$", lambda m: "\n\n$$\n" + m.group(1).strip() + "\n$$\n\n", t, flags=re.S)
    # $ x $ com espaços colados aos delimitadores não é reconhecido como fórmula. Os pares $...$ são lidos da
    # esquerda para a direita, para nunca tratar o texto ENTRE duas fórmulas como uma fórmula (antes, em
    # "$A$ é a matriz $B$" os espaços à volta de «é a matriz» desapareciam e o texto ficava colado às fórmulas).
    t = re.sub(r"(?<![\$\\])\$(?!\$)([^\$\n]+?)(?<!\\)\$(?!\$)",
               lambda m: "$" + m.group(1).strip() + "$" if m.group(1).strip() else m.group(0), t)
    return re.sub(r"\n{3,}", "\n\n", t)


def normalizar(texto) -> str:
    """Prepara texto (markdown) com fórmulas para o st.markdown mostrar como no papel. Não mexe em código."""
    if not isinstance(texto, str) or not texto:
        return "" if texto is None else str(texto)
    partes = _BLOCO_CODIGO.split(texto)
    return "".join(p if i % 2 else _normalizar_trecho(p) for i, p in enumerate(partes)).strip()


def tem_formula(texto: str) -> bool:
    return bool(re.search(r"\$[^\$]+\$", normalizar(texto)))
