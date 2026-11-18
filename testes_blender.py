"""Testes do motor Blender sem precisar do Blender (py -3.14 testes_blender.py): geometria das peças e preparação."""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "blender"))
import geometria as G  # noqa: E402

import estudio3d as e3  # noqa: E402
import motor_blender as mb  # noqa: E402

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


def unir(vs, fs, casas=6):
    """Junta vértices repetidos (como o Blender faz) para poder verificar se a malha é fechada."""
    mapa, novos, idx = {}, [], []
    for v in vs:
        k = tuple(round(c, casas) for c in v)
        if k not in mapa:
            mapa[k] = len(novos)
            novos.append(v)
        idx.append(mapa[k])
    faces = []
    for f in fs:
        g = [idx[i] for i in f]
        g = [x for k, x in enumerate(g) if x != g[k - 1]] if len(g) > 2 else g
        if len(set(g)) >= 3:
            faces.append(g)
    return novos, faces


def fechada_e_orientada(vs, fs):
    """Cada aresta aparece duas vezes, uma em cada sentido (malha fechada, com as faces todas para o mesmo lado)."""
    vs, fs = unir(vs, fs)
    arestas = {}
    for f in fs:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            arestas[(a, b)] = arestas.get((a, b), 0) + 1
    return all(n == 1 and arestas.get((b, a)) == 1 for (a, b), n in arestas.items())


def volume(vs, fs):
    """Volume com sinal: positivo quando as faces estão viradas para fora."""
    vol = 0.0
    for f in fs:
        for i in range(1, len(f) - 1):
            a, b, c = vs[f[0]], vs[f[i]], vs[f[i + 1]]
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return vol


def perto(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ---------------------------------------------------------------------------- primitivas iguais às do Three.js
vs, fs = G.caixa(2, 1, 0.5)
ok("Caixa: dimensões, fechada e virada para fora", G.caixa_limite(vs) == ((-1, -0.5, -0.25), (1, 0.5, 0.25))
   and fechada_e_orientada(vs, fs) and abs(volume(vs, fs) - 1.0) < 1e-9)
vs, fs = G.esfera(0.5)
ok("Esfera: raio 0,5, fechada, volume ≈ 4/3·π·r³", perto(G.caixa_limite(vs)[1], (0.5, 0.5, 0.5), 0.01)
   and fechada_e_orientada(vs, fs) and abs(volume(*unir(vs, fs)) - 4 / 3 * math.pi * 0.125) < 0.01)
vs, fs = G.cilindro(0.3, 0.5, 2.0)
lim = G.caixa_limite(vs)
ok("Cilindro: eixo Y, altura 2, raio de baixo 0,5, fechado e para fora", perto(lim[0], (-0.5, -1, -0.5), 0.01)
   and perto(lim[1], (0.5, 1, 0.5), 0.01) and fechada_e_orientada(vs, fs) and volume(vs, fs) > 0)
vs, fs = G.cilindro(0.0, 0.4, 1.0)
ok("Cone: ponta em cima, base em baixo, fechado e para fora", fechada_e_orientada(vs, fs) and volume(vs, fs) > 0
   and perto(G.caixa_limite(vs)[1], (0.4, 0.5, 0.4), 0.01))
vs, fs = G.toro(0.8, 0.2)
ok("Toro: no plano XY (eixo Z, como no Three.js), fechado e para fora", perto(G.caixa_limite(vs)[1], (1.0, 1.0, 0.2), 0.01)
   and fechada_e_orientada(vs, fs) and volume(vs, fs) > 0)
vs, fs = G.capsula(0.3, 1.0)
lim = G.caixa_limite(vs)
ok("Cápsula: comprimento total = comprimento + 2·raio, fechada e para fora", perto(lim[1], (0.3, 0.8, 0.3), 0.01)
   and fechada_e_orientada(vs, fs) and volume(*unir(vs, fs)) > 0)
vs, fs = G.torno([[0, -0.5], [0.4, -0.3], [0.5, 0.2], [0, 0.5]])
ok("Torno (perfil a rodar à volta de Y): fechado e para fora", fechada_e_orientada(vs, fs) and volume(*unir(vs, fs)) > 0)
vs, fs = G.icosfera(1.0, 5)
ok("Icosfera do Three.js (detalhe 5): 720 triângulos, 362 vértices, raio 1", len(fs) == 720 and len(vs) == 362
   and all(abs(math.sqrt(x * x + y * y + z * z) - 1) < 1e-9 for x, y, z in vs) and fechada_e_orientada(vs, fs)
   and volume(vs, fs) > 0)
vs, fs = G.organico(0.5, 0.2, 2.2, 3.0)
ok("Orgânico: forma irregular (ruído igual ao do visualizador), fechada e para fora",
   fechada_e_orientada(vs, fs) and volume(vs, fs) > 0
   and max(math.dist(v, (0, 0, 0)) for v in vs) - min(math.dist(v, (0, 0, 0)) for v in vs) > 0.05)

# ---------------------------------------------------------------------------- tubos (Catmull-Rom)
c = G.CatmullRom([[0, 0, 0], [1, 1, 0], [2, 0, 0], [3, 1, 0]])
ok("Curva passa pelos pontos dados", perto(c.ponto(0), (0, 0, 0), 1e-9) and perto(c.ponto(1 / 3), (1, 1, 0), 1e-9)
   and perto(c.ponto(1), (3, 1, 0), 1e-9))
ok("Parametrização por comprimento de arco (pontos igualmente espaçados)",
   abs(math.dist(c.ponto_em(0.1), c.ponto_em(0.2)) - math.dist(c.ponto_em(0.7), c.ponto_em(0.8))) < 0.01)
vs, fs = G.tubo([[0, 0, 0], [0, 1, 0.5], [0, 2, 0]], 0.1)
ok("Tubo aberto: tampas nas pontas → malha fechada e virada para fora", fechada_e_orientada(vs, fs) and volume(vs, fs) > 0)
vs, fs = G.tubo([[1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0]], 0.1, fechado=True)
ok("Tubo fechado (anel): fechado e para fora", fechada_e_orientada(vs, fs) and volume(vs, fs) > 0)
vs, fs = G.tubo([[0, 0, 0], [0, 2, 0]], raios=[0.4, 0.1])
lim = G.caixa_limite(vs)
ok("Tubo com espessura variável (afunila)", perto(lim[1], (0.4, 2, 0.4), 0.02))

# ---------------------------------------------------------------------------- peças do formato
p = e3.normalizar_parte({"tipo": "cilindro", "nome": "osso", "dims": {"raio_topo": 0.1, "raio_base": 0.1, "de": [0, 0, 0], "ate": [0, 0, 3]}})
vs, _ = G.malha(p)
ok("Cilindro entre dois pontos: comprimento = distância (o visualizador orienta-o)", perto(G.caixa_limite(vs)[1], (0.1, 1.5, 0.1), 0.01))
ok("Superfície e extrusão não são feitas pela geometria (superfície fica no visualizador; extrusão no Blender)",
   G.malha({"tipo": "superficie", "dims": {}}) is None and G.malha({"tipo": "extrusao", "dims": {}}) is None)

# ---------------------------------------------------------------------------- preparação e estado (sem Blender)
modelo = e3.normalizar_modelo({"titulo": "Teste", "partes": [
    {"tipo": "caixa", "nome": "Base", "dims": {"largura": 2}, "cor": "#ff0000"},
    {"tipo": "esfera", "nome": "Bola", "posicao": [0, 1, 0], "visivel": False},
    {"tipo": "superficie", "nome": "Relevo", "dims": {"nx": 2, "ny": 2, "alturas": [0, 1, 0, 1]}}]})
entrada = mb.preparar(modelo)
ok("Preparar: só vai para o Blender a forma das peças visíveis (sem textos nem posições)",
   [x["id"] for x in entrada["partes"]] == ["base"] and "descricao" not in entrada["partes"][0]
   and "posicao" not in entrada["partes"][0] and entrada["partes"][0]["material"] == "padrao")
h = e3.hash_geometria(modelo["partes"][0])
m2 = json.loads(json.dumps(modelo))
m2["partes"][0]["cor"] = "#00ff00"
m2["partes"][0]["posicao"] = [1, 2, 3]
ok("Mudar a cor ou a posição não obriga a refazer no Blender (a forma é a mesma)", e3.hash_geometria(m2["partes"][0]) == h)
m2["partes"][0]["dims"]["largura"] = 3
ok("Mudar as dimensões obriga a refazer essa peça", e3.hash_geometria(m2["partes"][0]) != h)
modelo["blender"] = {"id": "abc123", "hashes": {"base": h, "bola": "x"}, "motor": "Blender 5.2"}
norm = e3.normalizar_modelo(modelo)
ok("O modelo guarda o resultado do Blender (id do GLB e a forma de cada peça)", norm["blender"]["id"] == "abc123"
   and norm["blender"]["hashes"]["base"] == h)
ok("Peças atualizadas no Blender: só as que não mudaram de forma", mb.pecas_atualizadas(norm) == ["base"])
ok("Sem resultado do Blender: nenhuma peça", mb.pecas_atualizadas(e3.normalizar_modelo({"partes": [{"tipo": "esfera"}]})) == [])
ok("Procura o Blender instalado (caminho indicado que não existe → nada)", mb.encontrar_blender("/nao/existe/blender") in (None, mb.encontrar_blender()))
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
