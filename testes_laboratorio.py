"""Testes do Laboratório (py -3.14 testes_laboratorio.py)."""
import math

import numpy as np

import laboratorio as lab

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


def erro(f, *a):
    try:
        f(*a)
        return False
    except lab.ErroLab:
        return True


# ---------------------------------------------------------------- química
ok("Tabela periódica com 118 elementos, símbolos únicos", len(lab.ELEMENTOS) == 118 and len(lab.POR_SIMBOLO) == 118
   and [e["z"] for e in lab.ELEMENTOS] == list(range(1, 119)))
ok("Grupos e períodos coerentes (gases nobres no grupo 18)", all(e["grupo"] == 18 for e in lab.ELEMENTOS if e["categoria"] == "Gás nobre")
   and lab.POR_SIMBOLO["Fe"]["grupo"] == 8 and lab.POR_SIMBOLO["Fe"]["periodo"] == 4)
ok("Massas crescentes (com as exceções conhecidas Ar/K, Co/Ni, Te/I, Th/Pa, U/Np...)",
   sum(a["massa"] > b["massa"] for a, b in zip(lab.ELEMENTOS, lab.ELEMENTOS[1:])) <= 8)
ok("Configurações eletrónicas", lab.POR_SIMBOLO["O"]["configuracao"] == "[He] 2s2 2p4"
   and lab.POR_SIMBOLO["Fe"]["configuracao"] == "[Ar] 4s2 3d6" and lab.POR_SIMBOLO["Cu"]["configuracao"] == "[Ar] 3d10 4s1"
   and lab.POR_SIMBOLO["H"]["configuracao"] == "1s1" and lab.POR_SIMBOLO["Br"]["configuracao"] == "[Ar] 4s2 3d10 4p5")
ok("Massa molar da água ≈ 18,015", abs(lab.massa_molar("H2O")["massa"] - 18.015) < 0.002)
ok("Massa molar com parênteses: Ca(OH)2 ≈ 74,09", abs(lab.massa_molar("Ca(OH)2")["massa"] - 74.092) < 0.01)
ok("Hidratos: CuSO4·5H2O ≈ 249,68", abs(lab.massa_molar("CuSO4·5H2O")["massa"] - 249.68) < 0.02)
ok("Parênteses retos: K4[Fe(CN)6] ≈ 368,35", abs(lab.massa_molar("K4[Fe(CN)6]")["massa"] - 368.35) < 0.02)
ok("Percentagens somam 100", abs(sum(l["percentagem"] for l in lab.massa_molar("C6H12O6")["composicao"]) - 100) < 0.05)
ok("Fórmulas inválidas dão mensagem clara", erro(lab.massa_molar, "Xx2") and erro(lab.massa_molar, "h2o") and erro(lab.massa_molar, "Ca(OH2"))
r = lab.acertar_equacao("H2 + O2 -> H2O")
ok("Acertar H2 + O2 → H2O (2, 1, 2)", r["coeficientes"] == [2, 1, 2] and r["acertada"] == "2H2 + O2 → 2H2O")
ok("Combustão do propano (1, 5, 3, 4)", lab.acertar_equacao("C3H8 + O2 → CO2 + H2O")["coeficientes"] == [1, 5, 3, 4])
r = lab.acertar_equacao("KMnO4 + HCl = KCl + MnCl2 + H2O + Cl2")
ok("Equação redox difícil (2, 16, 2, 2, 8, 5)", r["coeficientes"] == [2, 16, 2, 2, 8, 5]
   and all(a == b for a, b in r["verificacao"].values()))
ok("Fotossíntese (6, 6, 1, 6)", lab.acertar_equacao("CO2 + H2O -> C6H12O6 + O2")["coeficientes"] == [6, 6, 1, 6])
ok("Equação impossível ou sem seta dá erro", erro(lab.acertar_equacao, "H2 + O2") and erro(lab.acertar_equacao, "NaCl -> KBr"))

# ---------------------------------------------------------------- biologia
ok("Código genético: 64 codões, 3 de finalização", len(lab.CODIGO_GENETICO) == 64
   and sorted(c for c, a in lab.CODIGO_GENETICO.items() if a == "*") == ["UAA", "UAG", "UGA"])
g = lab.expressao_genica("TTATGGCCAAATGA")
ok("Transcrição e tradução desde AUG até ao stop", g["mrna"] == "UUAUGGCCAAAUGA" and g["proteina"] == "MAK"
   and g["proteina_abrev"] == "Met-Ala-Lys" and g["codoes"][-1]["aa"] == "*" and not g["aviso"])
g2 = lab.expressao_genica("TACCGGTTTACT", cadeia="molde")
ok("Cadeia molde: usa o complemento", g2["mrna"] == "AUGGCCAAAUGA" and g2["proteina"] == "MAK")
ok("Sequência inválida dá erro", erro(lab.expressao_genica, "ATGXYZ"))
p = lab.punnett("Aa", "Aa")
ok("Punnett Aa × Aa: 1 AA : 2 Aa : 1 aa e 3:1", p["genotipos"] == {"AA": "1/4", "Aa": "2/4", "aa": "1/4"}
   and p["fenotipos"] == {"dominante A": "3/4", "recessivo A": "1/4"})
p2 = lab.punnett("AaBb", "AaBb")
ok("Di-híbrido AaBb × AaBb: 9:3:3:1", sorted(p2["fenotipos"].values(), key=lambda v: -int(v.split("/")[0])) == ["9/16", "3/16", "3/16", "1/16"]
   and len(p2["tabela"]) == 4)
ok("Genótipos inválidos dão erro", erro(lab.punnett, "Ab", "Aa") and erro(lab.punnett, "Aa", "AaBb"))

# ---------------------------------------------------------------- matemática
f = lab.compilar("x^2 - 3x + 2")
ok("Escrita natural: x^2 - 3x + 2", float(f(x=np.array([4.0]))[0]) == 6.0)
ok("Raízes de x² − 3x + 2: 1 e 2", lab.raizes(f, -5, 5) == [1.0, 2.0])
ok("Derivada em x=3 vale 3", abs(lab.derivada(f, 3) - 3) < 1e-6)
ok("Integral de 0 a 3 vale 1,5", abs(lab.integral(f, 0, 3) - 1.5) < 1e-9)
ok("Mínimo em x = 1,5", lab.extremos(f, -5, 5)[0]["tipo"] == "mínimo" and abs(lab.extremos(f, -5, 5)[0]["x"] - 1.5) < 0.01)
ok("Funções em português e notação: 2sen(x) + raiz(4), f(x)=, vírgula decimal",
   abs(float(lab.compilar("f(x) = 2sen(x) + raiz(4) + 0,5")(x=np.array([math.pi / 2]))[0]) - 4.5) < 1e-9)
ok("Multiplicação implícita: (x+1)(x-1) e x(x+1)", float(lab.compilar("(x+1)(x-1)")(x=np.array([3.0]))[0]) == 8.0
   and float(lab.compilar("x(x+1)")(x=np.array([2.0]))[0]) == 6.0)
ok("log10 não é confundido com multiplicação", float(lab.compilar("log10(100)")(x=np.array([0.0]))[0]) == 2.0)
ok("Fora do domínio fica vazio (sem erro)", np.isnan(lab.compilar("sqrt(x)")(x=np.array([-1.0]))[0]))
ok("tan(x): as assíntotas não ganham raízes falsas", all(abs(math.sin(r)) < 1e-4 for r in lab.raizes(lab.compilar("tan(x)"), -4, 4)))
x, y = lab.amostrar(lab.compilar("1/x"), -2, 2)
ok("1/x: a linha vertical na assíntota é cortada", np.isnan(y).any())
seguro = all(erro(lab.compilar, e) for e in ("__import__('os')", "x.__class__", "open('a')", "[1,2]", "lambda: 1", "y + 1"))
ok("Segurança: código que não é matemática é recusado", seguro)
alt, info = lab.grelha_superficie("x^2 - y^2", n=21)
ok("Superfície z = x² − y² (grelha e escala)", len(alt) == 441 and abs(info["zmax"] - 9) < 1e-9 and max(alt) <= 2.5 + 1e-9)
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
