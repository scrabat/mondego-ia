"""
Constrói no Blender as peças de um modelo do Mondego IA e exporta um GLB com uma malha por peça.

Uso (feito pela app ou pelo servidor Blender, sem janela):
    blender -b --factory-startup -noaudio --python-exit-code 1 --python construir_modelo.py -- entrada.json saida.glb

O que o Blender acrescenta a cada peça:
- caixas, cilindros, cones e extrusões: arestas arredondadas (bisel) com normais «endurecidas» (brilhos realistas);
- formas orgânicas (órgãos, células, rochas): superfície subdividida e lisa, com relevo natural (textura de nuvens);
- tornos (vasos, garrafas, colunas): rebordos arredondados;
- todas: sombreamento suave com arestas vivas onde o ângulo é grande;
- materiais físicos (metal, vidro com transmissão, verniz, tecido com «sheen», emissivo com intensidade).
A cor, a posição, a rotação, a escala e os textos de cada peça continuam a vir do modelo (o visualizador aplica-os).

Segurança: o ficheiro de entrada só tem números, listas e nomes; nada dele é executado como código.
Compatível com o Blender 4.2 a 5.x (testa os nomes das opções antes de as usar).
"""
import json
import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geometria as G  # noqa: E402

LIMITE_PECAS = 400
TIPOS = {"esfera", "caixa", "cilindro", "cone", "toro", "capsula", "tubo", "torno", "organico", "extrusao"}

MATERIAIS = {
    "padrao": {"rough": 0.5},
    "brilhante": {"rough": 0.22, "coat": 0.8, "coat_rough": 0.1},
    "mate": {"rough": 0.93},
    "metal": {"rough": 0.24, "metal": 1.0},
    "vidro": {"rough": 0.02, "trans": 1.0, "ior": 1.45},
    "emissivo": {"rough": 0.4, "emit": 3.0},
    "tecido": {"rough": 0.78, "sheen": 0.8},
}


# ----------------------------------------------------------------------------------------------- utilitários
def argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        raise SystemExit("uso: blender -b --python construir_modelo.py -- entrada.json saida.glb")
    return argv[0], argv[1]


def num(v, defeito, minimo=0.0005, maximo=50.0):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defeito
    if math.isnan(x) or math.isinf(x):
        return defeito
    return max(minimo, min(maximo, x))


def cena_vazia():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for colecao in (bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.cameras, bpy.data.lights):
        for item in list(colecao):
            colecao.remove(item)


def definir(bsdf, valor, *nomes):
    """Os nomes das entradas do Principled BSDF mudaram no Blender 4.0: tenta os novos e os antigos."""
    for nome in nomes:
        s = bsdf.inputs.get(nome)
        if s is not None:
            try:
                s.default_value = valor
                return True
            except (TypeError, ValueError):
                continue
    return False


def material(tipo):
    nome = "mondego_" + tipo
    m = bpy.data.materials.get(nome)
    if m:
        return m
    m = bpy.data.materials.new(nome)
    try:
        m.use_nodes = True  # no Blender 5 os materiais já usam nós e esta opção pode já não existir
    except (AttributeError, TypeError):
        pass
    arvore = getattr(m, "node_tree", None)
    bsdf = next((n for n in arvore.nodes if n.type == "BSDF_PRINCIPLED"), None) if arvore else None
    c = MATERIAIS.get(tipo, MATERIAIS["padrao"])
    if bsdf is not None:
        definir(bsdf, (0.8, 0.8, 0.8, 1.0), "Base Color")
        definir(bsdf, c.get("rough", 0.5), "Roughness")
        definir(bsdf, c.get("metal", 0.0), "Metallic")
        if "coat" in c:
            definir(bsdf, c["coat"], "Coat Weight", "Clearcoat")
            definir(bsdf, c["coat_rough"], "Coat Roughness", "Clearcoat Roughness")
        if "trans" in c:
            definir(bsdf, c["trans"], "Transmission Weight", "Transmission")
            definir(bsdf, c["ior"], "IOR")
        if "sheen" in c:
            definir(bsdf, c["sheen"], "Sheen Weight", "Sheen")
        if "emit" in c:
            definir(bsdf, (1.0, 1.0, 1.0, 1.0), "Emission Color", "Emission")
            definir(bsdf, c["emit"], "Emission Strength")
    return m


def objeto(nome, malha_bl):
    ob = bpy.data.objects.new(nome, malha_bl)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def malha_de_listas(nome, vs, fs, recalcular=False):
    me = bpy.data.meshes.new(nome)
    me.from_pydata([tuple(v) for v in vs], [], [tuple(f) for f in fs])
    me.validate(clean_customdata=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)   # pólos, costuras e eixos dos tornos
    if recalcular:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def suavizar(ob, angulo=None):
    """Sombreamento suave; com ângulo, as arestas mais vivas do que isso ficam marcadas (não ficam «derretidas»)."""
    me = ob.data
    try:
        me.shade_smooth()
    except AttributeError:
        for p in me.polygons:
            p.use_smooth = True
    if angulo is not None:
        try:
            me.set_sharp_from_angle(angle=math.radians(angulo))
        except (AttributeError, TypeError):
            try:
                me.use_auto_smooth = True
                me.auto_smooth_angle = math.radians(angulo)
            except AttributeError:
                pass


def bisel(ob, largura, segmentos=3, angulo=35.0):
    md = ob.modifiers.new("Bisel", "BEVEL")
    md.width = largura
    md.segments = segmentos
    md.limit_method = "ANGLE"
    md.angle_limit = math.radians(angulo)
    for atributo, valor in (("use_clamp_overlap", True), ("harden_normals", True), ("profile", 0.5)):
        try:
            setattr(md, atributo, valor)
        except (AttributeError, TypeError):
            pass
    return md


def relevo_organico(ob, raio, irregularidade, nivel):
    sub = ob.modifiers.new("Suavizar", "SUBSURF")
    sub.levels = nivel
    sub.render_levels = nivel
    try:
        tex = bpy.data.textures.new("relevo_" + ob.name, type="CLOUDS")
        tex.noise_scale = max(0.02, raio * 0.3)
        tex.noise_depth = 2
        md = ob.modifiers.new("Relevo", "DISPLACE")
        md.texture = tex
        md.texture_coords = "LOCAL"
        md.mid_level = 0.5
        md.strength = raio * (0.025 + 0.05 * irregularidade)
    except (AttributeError, TypeError, RuntimeError):
        pass  # sem textura de relevo: fica só a superfície lisa


def extrusao(nome, d):
    forma = []
    for q in d.get("forma") or []:
        try:
            ponto = (float(q[0]), float(q[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if not forma or (abs(ponto[0] - forma[-1][0]) + abs(ponto[1] - forma[-1][1])) > 1e-7:
            forma.append(ponto)
    if len(forma) > 3 and abs(forma[0][0] - forma[-1][0]) + abs(forma[0][1] - forma[-1][1]) < 1e-7:
        forma.pop()
    if len(forma) < 3:
        return None
    prof = num(d.get("profundidade"), 0.2)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0.0)) for x, y in forma]
    face = bm.faces.new(vs)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    novos = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=novos, vec=(0.0, 0.0, prof))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    centro = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, prof / 2)   # como o g.center() do visualizador
    bmesh.ops.translate(bm, verts=bm.verts, vec=(-centro[0], -centro[1], -centro[2]))
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    return me


# ----------------------------------------------------------------------------------------------- peças
def construir_peca(p, nivel_organico):
    tipo = p.get("tipo")
    nome = str(p.get("id") or "peca")[:60]
    d = p.get("dims") or {}
    if tipo == "extrusao":
        me = extrusao(nome, d)
        if me is None:
            return None
        ob = objeto(nome, me)
        suavizar(ob, 35)
        prof = num(d.get("profundidade"), 0.2)
        bisel(ob, min(0.05, prof / 3), 3, 35)
    else:
        geo = G.malha(p, detalhe_organico=4 if nivel_organico >= 2 else 5)
        if geo is None:
            return None
        vs, fs = geo
        ob = objeto(nome, malha_de_listas(nome, vs, fs, recalcular=(tipo == "caixa")))
        if tipo == "caixa":
            menor = min(num(d.get("largura"), 1), num(d.get("altura"), 1), num(d.get("profundidade"), 1))
            suavizar(ob, 35)
            bisel(ob, min(0.12, menor * 0.07), 4, 35)
        elif tipo in ("cilindro", "cone"):
            raios = [num(d.get(k), 0.3) for k in ("raio_topo", "raio_base", "raio") if d.get(k)]
            menor = min(raios + [num(d.get("altura"), 1.0)]) if raios else 0.3
            suavizar(ob, 35)
            bisel(ob, min(0.08, menor * 0.12), 3, 35)
        elif tipo == "torno":
            alturas = [float(q[1]) for q in d.get("perfil") or [[0, 0]]]
            raios = [float(q[0]) for q in d.get("perfil") or [[0, 0]]]
            tam = max(max(alturas) - min(alturas), max(raios), 0.05)
            suavizar(ob, 40)
            bisel(ob, tam * 0.015, 2, 40)
        elif tipo == "organico":
            suavizar(ob)
            relevo_organico(ob, num(d.get("raio"), 0.5), num(d.get("irregularidade"), 0.15, 0.0, 0.6), nivel_organico)
        else:  # esfera, cápsula, toro, tubo: já são lisas
            suavizar(ob, 60 if tipo == "tubo" else None)
    ob.data.materials.append(material(str(p.get("material") or "padrao")))
    return ob


def exportar(caminho):
    op = bpy.ops.export_scene.gltf
    try:
        aceites = set(op.get_rna_type().properties.keys())
    except Exception:  # noqa: BLE001
        aceites = set()
    pedidas = dict(export_format="GLB", export_apply=True, export_yup=False, use_selection=False,
                   export_materials="EXPORT", export_cameras=False, export_lights=False, export_extras=False,
                   export_texcoords=False, export_normals=True, export_animations=False, export_skins=False,
                   export_morph=False, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                   export_draco_position_quantization=14, export_draco_normal_quantization=10)
    kw = {k: v for k, v in pedidas.items() if not aceites or k in aceites}
    try:
        op(filepath=caminho, **kw)
    except Exception as erro:  # noqa: BLE001 — sem compressão Draco nesta instalação: exporta sem ela
        if not kw.pop("export_draco_mesh_compression_enable", None):
            raise
        print("Aviso: exportação sem Draco:", erro)
        for k in [k for k in kw if k.startswith("export_draco")]:
            kw.pop(k)
        op(filepath=caminho, **kw)


def principal():
    entrada, saida = argumentos()
    with open(entrada, encoding="utf-8") as f:
        dados = json.load(f)
    partes = [p for p in (dados.get("partes") or [])[:LIMITE_PECAS] if isinstance(p, dict) and p.get("tipo") in TIPOS]
    cena_vazia()
    organicas = sum(1 for p in partes if p["tipo"] == "organico")
    nivel = 2 if organicas <= 30 else 1   # menos subdivisão quando há muitas formas orgânicas (ficheiro mais leve)
    feitas, falhadas = [], []
    for p in partes:
        try:
            ob = construir_peca(p, nivel)
            (feitas if ob else falhadas).append(p.get("id"))
        except Exception as erro:  # noqa: BLE001 — uma peça estranha não estraga o resto do modelo
            falhadas.append(p.get("id"))
            print("Peça ignorada:", p.get("id"), erro)
    if not feitas:
        raise SystemExit("Nenhuma peça foi construída.")
    exportar(saida)
    print("MONDEGO_OK " + json.dumps({"feitas": len(feitas), "falhadas": falhadas, "blender": bpy.app.version_string}))


principal()
