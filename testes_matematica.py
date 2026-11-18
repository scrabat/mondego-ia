"""Testes das fórmulas (py -3.14 testes_matematica.py)."""
import json

import matematica as mt

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


cru = r'{"p": "Calcula $\frac{1}{2} \times \theta$, $\sqrt{x}$, $x \neq 0$ e $\nabla f$.\nDepois $\\alpha$ e \"aspas\"."}'
d = json.loads(mt.reparar_json_latex(cru))["p"]
ok("JSON: \\frac, \\times, \\theta, \\neq, \\nabla não viram caracteres de controlo", r"\frac{1}{2} \times \theta" in d
   and r"x \neq 0" in d and r"\nabla f" in d and "\f" not in d and "\t" not in d)
ok("JSON: \\sqrt (escape inválido) passa a ser lido", r"\sqrt{x}" in d)
ok("JSON: mudança de linha verdadeira mantém-se", "\nDepois" in d)
ok("JSON: barras já dobradas não mudam", r"$\alpha$" in d and '"aspas"' in d)
ok("JSON válido não é alterado", mt.reparar_json_latex('{"a": "linha\\nseguinte", "b": "\\u00e9"}') == '{"a": "linha\\nseguinte", "b": "\\u00e9"}')
ok("\\( \\) passa a $ $", mt.normalizar(r"A área é \(\pi r^2\).") == r"A área é $\pi r^2$.")
ok("\\[ \\] passa a bloco $$ numa linha própria", "\n$$\nE=mc^2\n$$\n" in mt.normalizar(r"Energia: \[E=mc^2\] fim"))
ok("$$ no meio da frase vai para linha própria", "\n$$\na+b\n$$\n" in mt.normalizar("Soma $$a+b$$ fim"))
ok("$ x $ com espaços colados é corrigido", mt.normalizar("valor $ x+1 $ aqui") == "valor $x+1$ aqui")
ok("O texto entre duas fórmulas mantém os espaços", mt.normalizar("quadrada $A$ é a matriz $A^{-1}$ tal que")
   == "quadrada $A$ é a matriz $A^{-1}$ tal que")
ok("Código não é alterado", mt.normalizar(r"usa `\(x\)` e ```\[y\]```") == r"usa `\(x\)` e ```\[y\]```")
ok("Texto vazio ou None", mt.normalizar(None) == "" and mt.normalizar("") == "")
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
