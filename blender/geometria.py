"""
Geometria das peças do formato mondego3d, igual à que o visualizador (Three.js) desenha.

O Blender (construir_modelo.py) usa estas malhas como ponto de partida e melhora-as (biséis, suavização, relevo).
Coordenadas locais da peça, com o eixo Y para cima (como no Three.js). A posição, rotação e escala de cada peça são
aplicadas depois pelo visualizador, por isso aqui só interessa a forma.

Python puro (sem bpy nem numpy): corre dentro do Blender e também nos testes (testes_blender.py).
Cada função devolve (vertices, faces): vertices = [(x, y, z)], faces = [(i, j, k[, l])] com a mesma orientação do Three.js.
"""
from __future__ import annotations

import math

TAU = math.pi * 2


# ----------------------------------------------------------------------------------------- vetores
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _len(a): return math.sqrt(_dot(a, a))


def _norm(a):
    n = _len(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 0 else (0.0, 0.0, 0.0)


def _lerp(a, b, t): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _rodar(v, eixo, ang):
    """Roda v em torno do eixo (unitário) pelo ângulo (fórmula de Rodrigues)."""
    c, s = math.cos(ang), math.sin(ang)
    return _add(_add(_mul(v, c), _mul(_cross(eixo, v), s)), _mul(eixo, _dot(eixo, v) * (1 - c)))


# ----------------------------------------------------------------------------------------- primitivas
def esfera(r=0.5, ws=48, hs=32):
    vs, grelha = [], []
    for iy in range(hs + 1):
        v = iy / hs
        linha = []
        for ix in range(ws + 1):
            u = ix / ws
            linha.append(len(vs))
            vs.append((-r * math.cos(u * TAU) * math.sin(v * math.pi), r * math.cos(v * math.pi),
                       r * math.sin(u * TAU) * math.sin(v * math.pi)))
        grelha.append(linha)
    fs = []
    for iy in range(hs):
        for ix in range(ws):
            a, b, c, d = grelha[iy][ix + 1], grelha[iy][ix], grelha[iy + 1][ix], grelha[iy + 1][ix + 1]
            if iy == 0:
                fs.append((b, c, d))
            elif iy == hs - 1:
                fs.append((a, b, d))
            else:
                fs.append((a, b, c, d))
    return vs, fs


def caixa(w=1.0, h=1.0, d=1.0):
    x, y, z = w / 2, h / 2, d / 2
    vs = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    fs = [(4, 5, 6, 7), (1, 0, 3, 2), (5, 1, 2, 6), (0, 4, 7, 3), (7, 6, 2, 3), (0, 1, 5, 4)]  # frente, trás, dir, esq, cima, baixo
    return vs, fs


def cilindro(rt=0.3, rb=0.3, h=1.0, n=40):
    """CylinderGeometry: eixo Y, centrado. Tampas fechadas (partilham os vértices com o corpo: malha fechada)."""
    vs, fs = [], []
    topo, base = [], []
    for y, r, lista in ((h / 2, rt, topo), (-h / 2, rb, base)):
        if r <= 1e-9:
            lista.append(len(vs))
            vs.append((0.0, y, 0.0))
            continue
        for x in range(n):
            th = x / n * TAU
            lista.append(len(vs))
            vs.append((r * math.sin(th), y, r * math.cos(th)))
    for x in range(n):
        a = topo[x % len(topo)]
        d = topo[(x + 1) % len(topo)]
        b = base[x % len(base)]
        c = base[(x + 1) % len(base)]
        face = [a, b, c, d]
        face = [i for k, i in enumerate(face) if i not in face[:k]]  # cone: tira o vértice repetido
        if len(face) >= 3:
            fs.append(tuple(face))
    if len(topo) > 1:
        fs.append(tuple(topo))                   # normal +Y
    if len(base) > 1:
        fs.append(tuple(reversed(base)))         # normal -Y
    return vs, fs


def toro(R=0.8, r=0.2, rad=24, tub=72, arco=TAU):
    fechado = abs(arco - TAU) < 1e-6
    ncol = tub if fechado else tub + 1
    vs = []
    for j in range(rad):
        v = j / rad * TAU
        for i in range(ncol):
            u = i / tub * arco
            vs.append(((R + r * math.cos(v)) * math.cos(u), (R + r * math.cos(v)) * math.sin(u), r * math.sin(v)))
    fs = []
    for j in range(rad):
        j2 = (j + 1) % rad
        for i in range(tub):
            i2 = (i + 1) % ncol if fechado else i + 1
            a, b, c, d = j2 * ncol + i, j * ncol + i, j * ncol + i2, j2 * ncol + i2
            fs.append((a, b, c, d))
    return vs, fs


def torno(perfil, n=72):
    """LatheGeometry: o perfil [(raio, y)] roda à volta do eixo Y. Os pontos com raio 0 viram um só vértice."""
    pts = [(max(0.0, float(p[0])), float(p[1])) for p in perfil]
    vs, anel = [], []
    for j, (r, y) in enumerate(pts):
        if r <= 1e-9:
            anel.append([len(vs)] * n)
            vs.append((0.0, y, 0.0))
            continue
        linha = []
        for i in range(n):
            phi = i / n * TAU
            linha.append(len(vs))
            vs.append((r * math.sin(phi), y, r * math.cos(phi)))
        anel.append(linha)
    fs = []
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(len(pts) - 1):
            a, b, c, d = anel[j][i], anel[j][i2], anel[j + 1][i2], anel[j + 1][i]
            face = [a, b, c, d]  # mesma orientação do Three.js (a, b, d) + (c, d, b)
            face = [k for idx, k in enumerate(face) if k not in face[:idx]]
            if len(face) >= 3:
                fs.append(tuple(face))
    return vs, fs


def capsula(r=0.3, comprimento=1.0, cap=10, radial=24):
    """CapsuleGeometry do Three.js: um torno com dois quartos de círculo e um segmento reto."""
    meio = comprimento / 2
    perfil = []
    for k in range(2 * cap + 1):          # de baixo (ângulo 270°) até ao equador de baixo (360°)
        a = 1.5 * math.pi + (k / (2 * cap)) * 0.5 * math.pi
        perfil.append((r * math.cos(a), -meio + r * math.sin(a)))
    for k in range(2 * cap + 1):          # do equador de cima (0°) até ao topo (90°)
        a = (k / (2 * cap)) * 0.5 * math.pi
        perfil.append((r * math.cos(a), meio + r * math.sin(a)))
    perfil[0] = (0.0, perfil[0][1])
    perfil[-1] = (0.0, perfil[-1][1])
    return torno(perfil, radial)


# ----------------------------------------------------------------------------------------- tubos (Catmull-Rom)
class CatmullRom:
    """CatmullRomCurve3 do Three.js (tipo «centripetal»), com parametrização por comprimento de arco."""

    def __init__(self, pontos, fechado=False):
        self.p = [tuple(float(c) for c in q) for q in pontos]
        self.fechado = fechado
        self._comp = None

    def ponto(self, t):
        pts, n = self.p, len(self.p)
        p = (n - (0 if self.fechado else 1)) * t
        i = math.floor(p)
        w = p - i
        if self.fechado:
            i += 0 if i > 0 else (math.floor(abs(i) / n) + 1) * n
        elif w == 0 and i == n - 1:
            i, w = n - 2, 1.0
        if self.fechado or i > 0:
            p0 = pts[(i - 1) % n]
        else:
            p0 = _add(_sub(pts[0], pts[1]), pts[0])
        p1, p2 = pts[i % n], pts[(i + 1) % n]
        if self.fechado or i + 2 < n:
            p3 = pts[(i + 2) % n]
        else:
            p3 = _add(_sub(pts[n - 1], pts[n - 2]), pts[n - 1])
        d2 = lambda a, b: _dot(_sub(a, b), _sub(a, b))
        dt0, dt1, dt2 = d2(p0, p1) ** 0.25, d2(p1, p2) ** 0.25, d2(p2, p3) ** 0.25
        if dt1 < 1e-4:
            dt1 = 1.0
        if dt0 < 1e-4:
            dt0 = dt1
        if dt2 < 1e-4:
            dt2 = dt1
        res = []
        for k in range(3):
            x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
            t1 = ((x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1) * dt1
            t2 = ((x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2) * dt1
            c0, c1, c2, c3 = x1, t1, -3 * x1 + 3 * x2 - 2 * t1 - t2, 2 * x1 - 2 * x2 + t1 + t2
            res.append(c0 + c1 * w + c2 * w * w + c3 * w * w * w)
        return tuple(res)

    def comprimentos(self, divisoes=200):
        if self._comp is None:
            comp, soma, ultimo = [0.0], 0.0, self.ponto(0)
            for k in range(1, divisoes + 1):
                atual = self.ponto(k / divisoes)
                soma += _len(_sub(atual, ultimo))
                comp.append(soma)
                ultimo = atual
            self._comp = comp
        return self._comp

    def u_para_t(self, u):
        comp = self.comprimentos()
        n = len(comp)
        alvo = u * comp[-1]
        baixo, alto = 0, n - 1
        while baixo <= alto:
            i = baixo + (alto - baixo) // 2
            dif = comp[i] - alvo
            if dif < 0:
                baixo = i + 1
            elif dif > 0:
                alto = i - 1
            else:
                alto = i
                break
        i = max(0, alto)
        if comp[i] == alvo or i >= n - 1:
            return i / (n - 1)
        frac = (alvo - comp[i]) / (comp[i + 1] - comp[i])
        return (i + frac) / (n - 1)

    def ponto_em(self, u):
        return self.ponto(self.u_para_t(u))

    def tangente_em(self, u):
        t = self.u_para_t(u)
        t1, t2 = max(0.0, t - 0.0001), min(1.0, t + 0.0001)
        return _norm(_sub(self.ponto(t2), self.ponto(t1)))

    def referenciais(self, segmentos):
        """computeFrenetFrames do Three.js: tangentes, normais e binormais (transporte paralelo)."""
        tg = [self.tangente_em(i / segmentos) for i in range(segmentos + 1)]
        t0 = tg[0]
        ax, ay, az = abs(t0[0]), abs(t0[1]), abs(t0[2])
        menor, normal = float("inf"), (1.0, 0.0, 0.0)
        if ax <= menor:
            menor, normal = ax, (1.0, 0.0, 0.0)
        if ay <= menor:
            menor, normal = ay, (0.0, 1.0, 0.0)
        if az <= menor:
            normal = (0.0, 0.0, 1.0)
        vec = _norm(_cross(t0, normal))
        ns = [_cross(t0, vec)]
        bs = [_cross(t0, ns[0])]
        for i in range(1, segmentos + 1):
            n = ns[i - 1]
            vec = _cross(tg[i - 1], tg[i])
            if _len(vec) > 2.220446049250313e-16:
                vec = _norm(vec)
                th = math.acos(max(-1.0, min(1.0, _dot(tg[i - 1], tg[i]))))
                n = _rodar(n, vec, th)
            ns.append(n)
            bs.append(_cross(tg[i], n))
        if self.fechado:
            th = math.acos(max(-1.0, min(1.0, _dot(ns[0], ns[segmentos])))) / segmentos
            if _dot(tg[0], _cross(ns[0], ns[segmentos])) > 0:
                th = -th
            for i in range(1, segmentos + 1):
                ns[i] = _rodar(ns[i], tg[i], th * i)
                bs[i] = _cross(tg[i], ns[i])
        return tg, ns, bs


def tubo(pontos, raio=0.1, fechado=False, raios=None, radial=18):
    curva = CatmullRom(pontos, fechado)
    if raios and len(raios) >= 2:
        segmentos = max(64, len(pontos) * 24)

        def r_em(t):
            x = t * (len(raios) - 1)
            i = min(int(math.floor(x)), len(raios) - 2)
            return raios[i] + (raios[i + 1] - raios[i]) * (x - i)
    else:
        segmentos = max(48, len(pontos) * 20)
        r_em = lambda t: raio
    _tg, ns, bs = curva.referenciais(segmentos)
    vs = []
    nlin = segmentos if fechado else segmentos + 1
    for i in range(nlin):
        t = i / segmentos
        c, r, N, B = curva.ponto_em(t), r_em(t), ns[i], bs[i]
        for j in range(radial):
            a = j / radial * TAU
            s, co = math.sin(a), -math.cos(a)
            vs.append(_add(c, _mul(_add(_mul(N, co), _mul(B, s)), r)))
    fs = []
    for i in range(segmentos if fechado else segmentos):
        i2 = (i + 1) % nlin if fechado else i + 1
        for j in range(radial):
            j2 = (j + 1) % radial
            a, b, c, d = i * radial + j, i2 * radial + j, i2 * radial + j2, i * radial + j2
            fs.append((a, b, c, d))
    if not fechado:  # tampas nas pontas (o Three.js deixa-as abertas; fechado fica melhor no Blender)
        fs.append(tuple(range(radial)))                                   # a ordem dos anéis dá normal -tangente
        ultimo = (nlin - 1) * radial
        fs.append(tuple(reversed(range(ultimo, ultimo + radial))))        # na outra ponta, +tangente
    return vs, fs


# ----------------------------------------------------------------------------------------- orgânico
def ruido(x, y, z):
    """O mesmo ruído do visualizador (soma de senos): formas naturais para órgãos, células, rochas…"""
    return (math.sin(x * 1.7 + math.cos(y * 1.3)) * 0.5 + math.sin(y * 2.1 + math.cos(z * 1.9)) * 0.3 +
            math.sin(z * 2.7 + math.cos(x * 2.3)) * 0.2)


_T = (1 + math.sqrt(5)) / 2
_ICO_V = [(-1, _T, 0), (1, _T, 0), (-1, -_T, 0), (1, -_T, 0), (0, -1, _T), (0, 1, _T), (0, -1, -_T), (0, 1, -_T),
          (_T, 0, -1), (_T, 0, 1), (-_T, 0, -1), (-_T, 0, 1)]
_ICO_F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
          (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
          (8, 6, 7), (9, 8, 1)]


def icosfera(r=0.5, detalhe=5):
    """IcosahedronGeometry(r, detalhe) do Three.js, com os vértices repetidos unidos (malha fechada)."""
    vs, fs, indice = [], [], {}

    def vert(p):
        p = _mul(_norm(p), r)
        chave = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
        if chave not in indice:
            indice[chave] = len(vs)
            vs.append(p)
        return indice[chave]

    cols = detalhe + 1
    for fa, fb, fc in _ICO_F:
        a, b, c = _ICO_V[fa], _ICO_V[fb], _ICO_V[fc]
        v = []
        for i in range(cols + 1):
            aj, bj = _lerp(a, c, i / cols), _lerp(b, c, i / cols)
            linhas = cols - i
            v.append([aj if (j == 0 and i == cols) else _lerp(aj, bj, j / linhas if linhas else 0) for j in range(linhas + 1)])
        for i in range(cols):
            for j in range(2 * (cols - i) - 1):
                k = j // 2
                if j % 2 == 0:
                    tri = (v[i][k + 1], v[i + 1][k], v[i][k])
                else:
                    tri = (v[i][k + 1], v[i + 1][k + 1], v[i + 1][k])
                fs.append(tuple(vert(q) for q in tri))
    return vs, fs


def organico(r=0.5, irregularidade=0.15, frequencia=2.2, semente=1.0, detalhe=5):
    vs, fs = icosfera(r, detalhe)
    novos = []
    for x, y, z in vs:
        n = ruido(x * frequencia + semente, y * frequencia - semente, z * frequencia + semente * 0.7)
        novos.append(_mul((x, y, z), 1 + irregularidade * n))
    return novos, fs


# ----------------------------------------------------------------------------------------- peça → malha
def comprimento_de_ate(d):
    if not d.get("de") or not d.get("ate"):
        return 0.0
    return _len(_sub(d["ate"], d["de"]))


def malha(p, detalhe_organico=5):
    """Peça do modelo → (vertices, faces) ou None (tipos que o Blender não refaz: superfície e extrusão,
    que é feita diretamente no Blender, ver construir_modelo.py)."""
    d = p.get("dims") or {}
    t = p.get("tipo")
    if t == "esfera":
        return esfera(d.get("raio", 0.5))
    if t == "caixa":
        return caixa(d.get("largura", 1), d.get("altura", 1), d.get("profundidade", 1))
    if t == "cilindro":
        return cilindro(d.get("raio_topo", 0.3), d.get("raio_base", 0.3), comprimento_de_ate(d) or d.get("altura", 1))
    if t == "cone":
        return cilindro(0.0, d.get("raio", 0.4), comprimento_de_ate(d) or d.get("altura", 1))
    if t == "toro":
        return toro(d.get("raio", 0.8), d.get("raio_tubo", 0.2), arco=d.get("arco") or TAU)
    if t == "capsula":
        r = d.get("raio", 0.3)
        comp = comprimento_de_ate(d) or d.get("comprimento", 1)
        return capsula(r, max(0.001, comp - (2 * r if d.get("de") else 0)))
    if t == "tubo":
        return tubo(d.get("pontos") or [[0, 0, 0], [0, 1, 0]], d.get("raio", 0.1), bool(d.get("fechado")), d.get("raios"))
    if t == "torno":
        return torno(d.get("perfil") or [[0, -0.5], [0.5, 0], [0, 0.5]])
    if t == "organico":
        return organico(d.get("raio", 0.5), d.get("irregularidade", 0.15), d.get("frequencia", 2.2), d.get("semente", 1.0),
                        detalhe_organico)
    return None


def caixa_limite(vs):
    xs, ys, zs = [v[0] for v in vs], [v[1] for v in vs], [v[2] for v in vs]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
