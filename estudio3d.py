"""
3D Studio do Mondego IA — formato dos modelos e edição.

Um modelo é um conjunto de peças geométricas reais (esferas, cilindros, tubos, superfícies de revolução...) com
nome, cor, material, etiqueta e uma explicação. O visualizador (componentes/mondego/visor3d.js, Three.js) desenha-as
em 3D; a IA cria e altera modelos neste formato. Também pode haver um ficheiro GLB/glTF por baixo (modelo aberto
do computador ou gerado por um serviço externo), com ajustes por malha (cor, etiqueta, visibilidade).

Não depende do Streamlit, para se poder testar sozinho.
"""

from __future__ import annotations

import copy
import json
import math
import re
import unicodedata

FORMATO = "mondego3d"
VERSAO_FORMATO = 1
MAX_PARTES = 400
MAX_PONTOS = 96
MAX_GRELHA = 140

TIPOS = ("esfera", "caixa", "cilindro", "cone", "toro", "capsula", "tubo", "torno", "superficie", "organico", "extrusao")
SINONIMOS_TIPO = {
    "sphere": "esfera", "ball": "esfera", "elipsoide": "esfera", "ellipsoid": "esfera",
    "box": "caixa", "cube": "caixa", "cubo": "caixa", "paralelepipedo": "caixa",
    "cylinder": "cilindro", "cone": "cone", "torus": "toro", "anel": "toro", "ring": "toro",
    "capsule": "capsula", "tube": "tubo", "curva": "tubo", "vaso": "tubo", "lathe": "torno", "revolucao": "torno",
    "surface": "superficie", "plane": "caixa", "plano": "caixa", "organic": "organico", "blob": "organico",
    "extrude": "extrusao", "extrusion": "extrusao", "placa": "extrusao",
}
MATERIAIS = ("padrao", "brilhante", "mate", "metal", "vidro", "emissivo", "tecido")
CATEGORIAS = ("Anatomia", "Biologia", "Química", "Física", "Matemática", "Engenharia", "Geografia",
              "História e arte", "Outro")
TIPOS_MODELO = ("Automático", "Anatomia", "Biologia celular", "Molécula", "Máquina ou mecanismo", "Objeto", "Edifício ou monumento",
                "Relevo ou geografia", "Outro")
NIVEIS_DETALHE = {"Simples": (6, 14), "Médio": (14, 35), "Alto": (35, 80), "Muito alto": (80, 160)}
ESTILOS = ("Automático", "Didático (cores distintas)", "Realista", "Esquemático (transparente)", "Low-poly")
COMPLEXIDADES = ("Automático", "Simplificado para estudo", "Fiel à realidade")

_DIMS_PADRAO = {
    "esfera": {"raio": 0.5},
    "caixa": {"largura": 1.0, "altura": 1.0, "profundidade": 1.0},
    "cilindro": {"raio_topo": 0.3, "raio_base": 0.3, "altura": 1.0},
    "cone": {"raio": 0.4, "altura": 1.0},
    "toro": {"raio": 0.8, "raio_tubo": 0.2},
    "capsula": {"raio": 0.3, "comprimento": 1.0},
    "tubo": {"raio": 0.1, "pontos": [[0, 0, 0], [0, 1, 0]]},
    "torno": {"perfil": [[0.0, -0.5], [0.5, 0.0], [0.0, 0.5]]},
    "superficie": {"nx": 2, "ny": 2, "largura": 4.0, "profundidade": 4.0, "alturas": [0, 0, 0, 0]},
    "organico": {"raio": 0.5, "irregularidade": 0.15, "frequencia": 2.2, "semente": 1.0},
    "extrusao": {"forma": [[0, 0], [1, 0], [0.5, 1]], "profundidade": 0.2},
}
_NUM_DIMS = ("raio", "largura", "altura", "profundidade", "raio_topo", "raio_base", "raio_tubo", "comprimento",
             "arco", "frequencia")


class ErroModelo(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


# ------------------------------------------------------------------ utilitários
def _num(v, defeito=0.0, minimo=-50.0, maximo=50.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float(defeito)
    if math.isnan(x) or math.isinf(x):
        return float(defeito)
    return max(minimo, min(maximo, x))


def _vec3(v, defeito, minimo=-50.0, maximo=50.0) -> list:
    if isinstance(v, (int, float)):
        v = [v, v, v]
    if not isinstance(v, (list, tuple)) or len(v) < 3:
        return list(defeito)
    return [round(_num(v[i], defeito[i], minimo, maximo), 4) for i in range(3)]


def _texto(v, maximo: int) -> str:
    return " ".join(str(v or "").split())[:maximo]


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t[:40] or "parte"


_CORES_NOMES = {"vermelho": "#C0392B", "azul": "#2E6DB4", "verde": "#3E8E5A", "amarelo": "#E2B33C",
                "laranja": "#E07B39", "roxo": "#7D4FA8", "rosa": "#E58FA8", "branco": "#F4F1EA", "preto": "#222222",
                "cinzento": "#8C8C8C", "castanho": "#7A5230", "bege": "#D9C7A7", "dourado": "#C9A23F",
                "red": "#C0392B", "blue": "#2E6DB4", "green": "#3E8E5A", "yellow": "#E2B33C", "white": "#F4F1EA",
                "black": "#222222", "gray": "#8C8C8C", "grey": "#8C8C8C", "orange": "#E07B39", "purple": "#7D4FA8",
                "pink": "#E58FA8", "brown": "#7A5230"}


def cor_valida(v, defeito: str = "#C9C2B4") -> str:
    s = str(v or "").strip().lower()
    if s in _CORES_NOMES:
        return _CORES_NOMES[s]
    if re.fullmatch(r"#[0-9a-f]{6}", s):
        return s.upper()
    if re.fullmatch(r"#[0-9a-f]{3}", s):
        return ("#" + "".join(c * 2 for c in s[1:])).upper()
    return defeito


# ------------------------------------------------------------------ normalização (validação) das peças e do modelo
def normalizar_parte(p: dict, ids_usados: set | None = None) -> dict:
    """Devolve uma peça válida (com valores por omissão e limites), ou levanta ErroModelo se não der para usar."""
    if not isinstance(p, dict):
        raise ErroModelo("Peça inválida.")
    tipo = str(p.get("tipo") or "").strip().lower()
    tipo = unicodedata.normalize("NFKD", tipo).encode("ascii", "ignore").decode()
    tipo = SINONIMOS_TIPO.get(tipo, tipo)
    if tipo not in TIPOS:
        raise ErroModelo(f"Tipo de peça desconhecido: {p.get('tipo')!r}.")
    nome = _texto(p.get("nome") or p.get("id") or tipo, 80)
    ident = slug(p.get("id") or nome)
    if ids_usados is not None:
        base, n = ident, 2
        while ident in ids_usados:
            ident = f"{base}_{n}"
            n += 1
        ids_usados.add(ident)
    dims_in = p.get("dims") if isinstance(p.get("dims"), dict) else {}
    dims = copy.deepcopy(_DIMS_PADRAO[tipo])
    for k in _NUM_DIMS:
        if k in dims_in:
            dims[k] = round(_num(dims_in[k], dims.get(k, 1.0), 0.001, 50.0), 4)
    for k in ("de", "ate"):  # cilindros, cones e cápsulas orientados entre dois pontos
        if k in dims_in and tipo in ("cilindro", "cone", "capsula"):
            dims[k] = _vec3(dims_in[k], [0, 0, 0])
    if tipo == "tubo":
        pts = [_vec3(q, [0, 0, 0]) for q in (dims_in.get("pontos") or []) if isinstance(q, (list, tuple))][:MAX_PONTOS]
        if len(pts) < 2:
            pts = dims["pontos"]
        dims["pontos"] = pts
        dims["fechado"] = bool(dims_in.get("fechado", False))
        raios = dims_in.get("raios")
        if isinstance(raios, list) and len(raios) >= 2:  # espessura variável ao longo do tubo
            dims["raios"] = [round(_num(r, 0.1, 0.001, 20), 4) for r in raios[:MAX_PONTOS]]
    if tipo == "torno":
        perfil = []
        for q in (dims_in.get("perfil") or [])[:MAX_PONTOS]:
            if isinstance(q, (list, tuple)) and len(q) >= 2:
                perfil.append([round(_num(q[0], 0, 0, 50), 4), round(_num(q[1], 0), 4)])
        dims["perfil"] = perfil if len(perfil) >= 2 else dims["perfil"]
    if tipo == "superficie":
        nx = int(_num(dims_in.get("nx"), 2, 2, MAX_GRELHA))
        ny = int(_num(dims_in.get("ny"), 2, 2, MAX_GRELHA))
        alturas = dims_in.get("alturas") or []
        if not isinstance(alturas, list) or len(alturas) != nx * ny:
            raise ErroModelo("A superfície precisa de nx × ny alturas.")
        dims.update(nx=nx, ny=ny, alturas=[round(_num(a, 0, -50, 50), 4) for a in alturas])
        dims["cores_por_altura"] = bool(dims_in.get("cores_por_altura", True))
    if tipo == "organico":
        dims["irregularidade"] = round(_num(dims_in.get("irregularidade", 0.15), 0.15, 0.0, 0.6), 3)
        dims["semente"] = round(_num(dims_in.get("semente", 1.0), 1.0, -100, 100), 3)
    if tipo == "extrusao":
        forma = [[round(_num(q[0], 0), 4), round(_num(q[1], 0), 4)] for q in (dims_in.get("forma") or [])[:MAX_PONTOS]
                 if isinstance(q, (list, tuple)) and len(q) >= 2]
        dims["forma"] = forma if len(forma) >= 3 else dims["forma"]
    material_in = p.get("material") if isinstance(p.get("material"), dict) else {"tipo": p.get("material")}
    mat_tipo = str(material_in.get("tipo") or "padrao").lower()
    material = {"tipo": mat_tipo if mat_tipo in MATERIAIS else "padrao",
                "opacidade": round(_num(material_in.get("opacidade", 1.0), 1.0, 0.05, 1.0), 3)}
    return {
        "id": ident, "nome": nome, "tipo": tipo, "dims": dims,
        "posicao": _vec3(p.get("posicao"), [0, 0, 0]),
        "rotacao": _vec3(p.get("rotacao"), [0, 0, 0], -360, 360),
        "escala": _vec3(p.get("escala", 1), [1, 1, 1], 0.01, 50),
        "cor": cor_valida(p.get("cor")),
        "material": material,
        "etiqueta": _texto(p.get("etiqueta"), 60),
        "descricao": _texto(p.get("descricao"), 500),
        "funcao": _texto(p.get("funcao"), 400),
        "curiosidade": _texto(p.get("curiosidade"), 400),
        "grupo": _texto(p.get("grupo"), 60),
        "visivel": bool(p.get("visivel", True)),
    }


def _cena(c) -> dict:
    c = c if isinstance(c, dict) else {}
    corte = c.get("corte") if isinstance(c.get("corte"), dict) else {}
    eixo = str(corte.get("eixo", "y")).lower()
    return {
        "corte": {"ativo": bool(corte.get("ativo", False)), "eixo": eixo if eixo in ("x", "y", "z") else "y",
                  "posicao": round(_num(corte.get("posicao", 0.0), 0.0), 3), "inverter": bool(corte.get("inverter", False))},
        "explodir": round(_num(c.get("explodir", 0.0), 0.0, 0.0, 1.0), 3),
        "etiquetas": bool(c.get("etiquetas", True)),
        "rodar": bool(c.get("rodar", False)),
    }


def _ajustes_glb(a) -> dict:
    """Ajustes por malha de um GLB: cor, etiqueta, descrição, visibilidade e escala."""
    saida = {}
    if not isinstance(a, dict):
        return saida
    for chave, v in list(a.items())[:MAX_PARTES]:
        if not isinstance(v, dict):
            continue
        aj = {}
        if "cor" in v:
            aj["cor"] = cor_valida(v["cor"])
        if "etiqueta" in v:
            aj["etiqueta"] = _texto(v["etiqueta"], 60)
        if "descricao" in v:
            aj["descricao"] = _texto(v["descricao"], 500)
        if "visivel" in v:
            aj["visivel"] = bool(v["visivel"])
        if "escala" in v:
            aj["escala"] = round(_num(v["escala"], 1, 0.05, 10), 3)
        if "material" in v and isinstance(v["material"], dict):
            aj["material"] = {"tipo": v["material"].get("tipo") if v["material"].get("tipo") in MATERIAIS else "padrao",
                              "opacidade": round(_num(v["material"].get("opacidade", 1), 1, 0.05, 1), 3)}
        saida[str(chave)[:120]] = aj
    return saida


def hash_geometria(p: dict) -> str:
    """Impressão digital da FORMA de uma peça (tipo, dimensões e tipo de material). Cor, posição, rotação, escala e
    textos não contam: o visualizador aplica-os por cima da malha feita pelo Blender, sem a refazer."""
    import hashlib

    forma = {"tipo": p.get("tipo"), "dims": p.get("dims"), "material": (p.get("material") or {}).get("tipo")}
    return hashlib.sha1(json.dumps(forma, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def _blender(b) -> dict | None:
    """Resultado do motor Blender: o GLB com as peças melhoradas e a forma de cada peça nessa altura."""
    if not isinstance(b, dict) or not re.fullmatch(r"[0-9a-zA-Z_-]{1,64}", str(b.get("id") or "")):
        return None
    hashes = b.get("hashes") if isinstance(b.get("hashes"), dict) else {}
    return {"id": str(b["id"]), "motor": _texto(b.get("motor"), 60), "em": _texto(b.get("em"), 30),
            "hashes": {str(k)[:60]: str(v)[:16] for k, v in list(hashes.items())[:MAX_PARTES]}}


def normalizar_modelo(m: dict) -> dict:
    """Valida um modelo vindo da IA, de um ficheiro ou da base de dados. Ignora peças inválidas (não rebenta)."""
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except json.JSONDecodeError as erro:
            raise ErroModelo("O ficheiro do modelo não é JSON válido.") from erro
    if not isinstance(m, dict):
        raise ErroModelo("Modelo inválido.")
    ids: set = set()
    partes = []
    for p in (m.get("partes") or m.get("parts") or [])[:MAX_PARTES]:
        try:
            partes.append(normalizar_parte(p, ids))
        except ErroModelo:
            continue
    glb = m.get("glb") if isinstance(m.get("glb"), dict) else None
    if glb:
        glb = {"id": _texto(glb.get("id"), 64), "nome": _texto(glb.get("nome"), 120)}
        if not glb["id"]:
            glb = None
    if not partes and not glb:
        raise ErroModelo("O modelo não tem nenhuma peça válida.")
    return {
        "formato": FORMATO, "versao": VERSAO_FORMATO,
        "titulo": _texto(m.get("titulo") or "Modelo 3D", 100),
        "descricao": _texto(m.get("descricao"), 1000),
        "partes": partes,
        "cena": _cena(m.get("cena")),
        "glb": glb,
        "ajustes_glb": _ajustes_glb(m.get("ajustes_glb")),
        "blender": _blender(m.get("blender")),
    }


def tamanho_json(m: dict) -> int:
    return len(json.dumps(m, ensure_ascii=False, separators=(",", ":")))


# ------------------------------------------------------------------ edição (pela IA ou pelos controlos)
CAMPOS_ALTERAVEIS = ("nome", "tipo", "dims", "posicao", "rotacao", "escala", "cor", "material", "etiqueta",
                     "descricao", "funcao", "curiosidade", "grupo", "visivel")


def aplicar_operacoes(modelo: dict, operacoes: list, apenas: str | None = None) -> tuple[dict, list]:
    """Aplica operações a uma CÓPIA do modelo e devolve (novo_modelo, relatório). Só muda o que é pedido.

    Operações: {"op":"adicionar","parte":{...}}, {"op":"alterar","id":"...","campos":{...}},
    {"op":"remover","id":"..."}, {"op":"cena","campos":{...}}, {"op":"titulo","titulo":"..."}.
    Com `apenas` (peça selecionada), alterar/remover só atuam nessa peça (as adições são permitidas)."""
    novo = copy.deepcopy(modelo)
    relatorio = []
    ids = {p["id"] for p in novo["partes"]}
    por_id = {p["id"]: p for p in novo["partes"]}
    glb_ids = set(novo.get("ajustes_glb", {})) | set(novo.get("_malhas_glb", []))
    for op in operacoes if isinstance(operacoes, list) else []:
        if not isinstance(op, dict):
            continue
        tipo = str(op.get("op") or "").lower()
        alvo = str(op.get("id") or "")
        if tipo in ("alterar", "remover") and apenas and alvo != apenas:
            relatorio.append(f"Ignorado: «{alvo}» não é a peça selecionada.")
            continue
        if tipo == "adicionar":
            if len(novo["partes"]) >= MAX_PARTES:
                relatorio.append("Limite de peças atingido.")
                continue
            try:
                parte = normalizar_parte(op.get("parte") or {}, ids)
            except ErroModelo as erro:
                relatorio.append(f"Peça não adicionada: {erro}")
                continue
            novo["partes"].append(parte)
            por_id[parte["id"]] = parte
            relatorio.append(f"Adicionado: {parte['nome']}")
        elif tipo == "alterar":
            campos = op.get("campos") if isinstance(op.get("campos"), dict) else {}
            if alvo in por_id:
                atual = por_id[alvo]
                mistura = copy.deepcopy(atual)
                for k, v in campos.items():
                    if k not in CAMPOS_ALTERAVEIS:
                        continue
                    if k in ("dims", "material") and isinstance(v, dict):
                        mistura[k] = {**mistura.get(k, {}), **v}
                    else:
                        mistura[k] = v
                mistura["id"] = alvo
                try:
                    nova = normalizar_parte(mistura)
                except ErroModelo as erro:
                    relatorio.append(f"Não alterado ({alvo}): {erro}")
                    continue
                nova["id"] = alvo
                novo["partes"][novo["partes"].index(atual)] = nova
                por_id[alvo] = nova
                relatorio.append(f"Alterado: {nova['nome']}")
            elif alvo in glb_ids or alvo.startswith("glb:"):
                aj = novo.setdefault("ajustes_glb", {}).get(alvo, {})
                aj.update({k: v for k, v in campos.items() if k in ("cor", "etiqueta", "descricao", "visivel", "escala", "material")})
                novo["ajustes_glb"][alvo] = aj
                novo["ajustes_glb"] = _ajustes_glb(novo["ajustes_glb"])
                relatorio.append(f"Alterado: {alvo.removeprefix('glb:')}")
            else:
                relatorio.append(f"Peça não encontrada: «{alvo}».")
        elif tipo == "remover":
            if alvo in por_id:
                novo["partes"] = [p for p in novo["partes"] if p["id"] != alvo]
                relatorio.append(f"Removido: {por_id.pop(alvo)['nome']}")
            elif alvo in glb_ids or alvo.startswith("glb:"):
                novo.setdefault("ajustes_glb", {}).setdefault(alvo, {})["visivel"] = False
                relatorio.append(f"Escondido: {alvo.removeprefix('glb:')}")
            else:
                relatorio.append(f"Peça não encontrada: «{alvo}».")
        elif tipo == "cena":
            campos = op.get("campos") if isinstance(op.get("campos"), dict) else {}
            cena = novo.get("cena", {})
            for k, v in campos.items():
                if k == "corte" and isinstance(v, dict):
                    cena["corte"] = {**cena.get("corte", {}), **v}
                elif k in ("explodir", "etiquetas", "rodar"):
                    cena[k] = v
            novo["cena"] = _cena(cena)
            relatorio.append("Vista alterada")
        elif tipo == "titulo":
            novo["titulo"] = _texto(op.get("titulo"), 100) or novo["titulo"]
    novo.pop("_malhas_glb", None)
    if not novo["partes"] and not novo.get("glb"):
        raise ErroModelo("Essa alteração deixava o modelo sem nenhuma peça.")
    return normalizar_modelo(novo), relatorio


def resumo_para_ia(modelo: dict, malhas_glb: list | None = None) -> str:
    """Modelo compacto (sem alturas de superfícies) para enviar à IA quando se pede uma alteração."""
    m = copy.deepcopy(modelo)
    m.pop("blender", None)  # o resultado do Blender não interessa à IA
    for p in m["partes"]:
        if p["tipo"] == "superficie":
            p["dims"] = {k: v for k, v in p["dims"].items() if k != "alturas"}
    if malhas_glb:
        m["malhas_do_ficheiro_glb"] = malhas_glb[:150]
    return json.dumps(m, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ instruções para a IA
ESQUEMA = (
    "Formato (JSON): {\"titulo\": \"...\", \"descricao\": \"...\", \"partes\": [PEÇA, ...], "
    "\"cena\": {\"etiquetas\": true}}. "
    "PEÇA = {\"id\": \"identificador_curto\", \"nome\": \"nome em português\", \"tipo\": TIPO, \"dims\": {...}, "
    "\"posicao\": [x, y, z], \"rotacao\": [graus_x, graus_y, graus_z], \"escala\": [sx, sy, sz], \"cor\": \"#RRGGBB\", "
    "\"material\": {\"tipo\": \"padrao|brilhante|mate|metal|vidro|emissivo|tecido\", \"opacidade\": 0.05-1} (tecido = órgãos e "
    "tecidos vivos), \"etiqueta\": \"texto curto (ou vazio)\", \"descricao\": \"o que é esta peça (1-2 frases exatas)\", "
    "\"funcao\": \"para que serve / como funciona (1 frase)\", \"curiosidade\": \"um facto interessante e verdadeiro (1 frase)\", "
    "\"grupo\": \"sistema ou conjunto a que pertence (ex.: Câmaras, Vasos, Válvulas)\"}. "
    "TIPOS e dims: esfera {raio} (usa escala para elipsoides e formas orgânicas); caixa {largura, altura, profundidade}; "
    "cilindro {raio_topo, raio_base, altura} ou {raio_topo, raio_base, de:[x,y,z], ate:[x,y,z]} para o ligar entre dois "
    "pontos; cone {raio, altura} (também aceita de/ate); toro {raio, raio_tubo, arco (radianos, opcional)}; "
    "capsula {raio, comprimento} (também aceita de/ate); tubo {raio, pontos:[[x,y,z], ...]} (curva suave, ideal para "
    "vasos sanguíneos, nervos, fios, ADN); torno {perfil:[[raio, y], ...]} (sólido de revolução em torno do eixo Y, "
    "ideal para vasos, garrafas, colunas, órgãos ocos); tubo também aceita raios:[r1, r2, ...] (espessura variável ao longo "
    "da curva, para vasos que afunilam, raízes, ramos); organico {raio, irregularidade 0-0.5, frequencia, semente} (forma "
    "natural irregular: órgãos, células, rochas, nuvens; combina com escala); extrusao {forma:[[x,y], ...], profundidade} "
    "(perfil 2D extrudido: ossos planos, folhas, engrenagens, letras). "
    "Formas: combina várias peças para cada estrutura complexa (ex.: um órgão = esferas com escala diferente em cada "
    "eixo + tubos para vasos com 4 a 8 pontos de curva + torno para cavidades); usa rotação para inclinar peças como na "
    "realidade; evita modelos feitos só de esferas. "
    "Regras: eixo Y para cima; o modelo inteiro cabe numa caixa de -3 a 3 em cada eixo, centrado na origem; as peças "
    "tocam-se ou sobrepõem-se ligeiramente (sem peças a flutuar soltas); proporções e posições anatómicas/reais "
    "corretas; ids únicos em minúsculas sem espaços."
)
SISTEMA_3D = (
    "És um modelador 3D e professor. Constróis modelos 3D educativos a partir de peças geométricas, com proporções e "
    "posições corretas, nomes em português de Portugal e explicações curtas e exatas. Respondes só com JSON válido."
)


def pedido_gerar(descricao: str, tipo: str, detalhe: str, complexidade: str, estilo: str, incluir: str,
                 etiquetas: bool) -> str:
    minimo, maximo = NIVEIS_DETALHE.get(detalhe, NIVEIS_DETALHE["Alto"])
    estilo_txt = {
        "Didático (cores distintas)": "cores distintas e saturadas para cada estrutura (como num atlas escolar)",
        "Realista": "cores e materiais realistas (tons naturais, brilho onde faz sentido)",
        "Esquemático (transparente)": "peças exteriores com material vidro e opacidade 0.25-0.4 para se ver o interior",
        "Low-poly": "formas simples e cores planas (material mate)",
    }.get(estilo, estilo)
    return (
        f"PEDIDO DO UTILIZADOR (segue-o à letra): {descricao.strip()}\n"
        "Faz EXATAMENTE o que é pedido: o mesmo objeto, as partes, cores, tamanhos, posições e estilo que o utilizador "
        "indicar. Não o troques por outra coisa, não o simplifiques nem o reinterpretes. O que não for dito decides tu, "
        "de forma realista e coerente com o pedido.\n"
        + (f"Tipo de modelo: {tipo}. " if tipo and tipo != "Automático" else "")
        + f"Nível de detalhe: {detalhe} — usa OBRIGATORIAMENTE entre {minimo} e {maximo} peças (divide as estruturas em "
        "partes reconhecíveis e junta os detalhes que as tornam fiéis à realidade; conta as peças antes de responder). "
        + (f"Complexidade: {complexidade}. " if complexidade and complexidade != "Automático" else "")
        + (f"Estilo visual: {estilo_txt}. " if estilo and estilo != "Automático" else
           "Estilo visual: o que o pedido indicar; se não indicar, cores realistas e bem distintas entre estruturas. ")
        + (f"Inclui obrigatoriamente: {incluir.strip()}. " if incluir.strip() else "")
        + ("Põe etiqueta nas estruturas principais. " if etiquetas else "Deixa as etiquetas vazias. ")
        + "\n" + ESQUEMA + "\nResponde só com o JSON do modelo."
    )


def pedido_rever(descricao: str, modelo: dict) -> str:
    """Segunda passagem: a IA compara o modelo com o pedido e corrige só o que falta ou está errado."""
    return (
        f"Pedido original do utilizador: {descricao.strip()}\n\nModelo 3D criado:\n{resumo_para_ia(modelo)}\n\n"
        "Verifica com rigor se o modelo cumpre o pedido À LETRA: estão lá TODAS as estruturas/partes pedidas? As cores, "
        "tamanhos, posições e o estilo pedidos foram respeitados? As proporções e posições relativas estão corretas? "
        "Há peças soltas a flutuar ou que não fazem sentido? Faltam descrições, funções ou curiosidades?\n"
        "Corrige só o necessário (mantém tudo o que já está certo). Responde só com JSON: {\"resumo\": \"o que corrigiste "
        "(ou 'nada a corrigir')\", \"operacoes\": [OPERAÇÃO, ...]} com as operações adicionar/alterar/remover descritas "
        "abaixo; lista vazia se estiver tudo certo.\n"
        "OPERAÇÕES: {\"op\":\"adicionar\",\"parte\":PEÇA}; {\"op\":\"alterar\",\"id\":\"id_existente\",\"campos\":{...}}; "
        "{\"op\":\"remover\",\"id\":\"id_existente\"}.\n" + ESQUEMA
    )


def pedido_editar(modelo: dict, instrucao: str, selecionada: str | None = None, malhas_glb: list | None = None) -> str:
    alvo = (f"O utilizador selecionou a peça «{selecionada}»: altera SÓ essa peça (podes acrescentar detalhes "
            "ligados a ela). " if selecionada else "")
    return (
        f"Modelo atual:\n{resumo_para_ia(modelo, malhas_glb)}\n\n"
        f"Pedido do utilizador: {instrucao.strip()}\n{alvo}"
        "Faz EXATAMENTE o que foi pedido (sem reinterpretar), alterando o modelo existente com o mínimo de mudanças: não "
        "recries o modelo e não mexas no que não foi pedido. "
        "Responde só com JSON: {\"resumo\": \"o que mudaste, numa frase\", \"operacoes\": [OPERAÇÃO, ...]}. "
        "OPERAÇÕES: {\"op\":\"adicionar\",\"parte\":PEÇA}; {\"op\":\"alterar\",\"id\":\"id_existente\",\"campos\":{só os "
        "campos que mudam}}; {\"op\":\"remover\",\"id\":\"id_existente\"}; {\"op\":\"cena\",\"campos\":{\"corte\":{\"ativo\":"
        "true,\"eixo\":\"x|y|z\",\"posicao\":0,\"inverter\":false}, \"explodir\": 0-1, \"etiquetas\": true}}; "
        "{\"op\":\"titulo\",\"titulo\":\"...\"}. "
        "Dicas: 'corte transversal' = op cena com corte; 'separar partes' = cena explodir 0.5-0.8; 'aumentar' = alterar "
        "escala; 'simplificar para estudo' = remover peças pequenas/secundárias; 'mais realista' = cores e materiais "
        "naturais e peças de detalhe; para malhas de um ficheiro GLB usa o id \"glb:NOME\" e só os campos cor, etiqueta, "
        "descricao, visivel, escala e material.\n" + ESQUEMA
    )


# ------------------------------------------------------------------ moléculas (dados reais do PubChem, formato SDF)
CORES_CPK = {"H": "#F4F4F4", "C": "#3A3A3A", "N": "#3050F8", "O": "#E03A2F", "F": "#90E050", "Cl": "#1FF01F",
             "Br": "#A62929", "I": "#940094", "S": "#E6C63A", "P": "#FF8000", "Na": "#AB5CF2", "K": "#8F40D4",
             "Mg": "#8AFF00", "Ca": "#3DFF00", "Fe": "#E06633", "Cu": "#C88033", "Zn": "#7D80B0", "B": "#FFB5B5",
             "Si": "#F0C8A0", "Li": "#CC80FF", "Al": "#BFA6A6"}
RAIO_ATOMO = {"H": 0.25, "C": 0.38, "N": 0.37, "O": 0.36, "F": 0.34, "Cl": 0.45, "Br": 0.5, "I": 0.55, "S": 0.46,
              "P": 0.46}


def molecula_de_sdf(sdf: str, nome: str) -> dict:
    """Converte um ficheiro SDF/MOL (V2000) num modelo de bolas e varetas com as coordenadas reais."""
    linhas = sdf.splitlines()
    if len(linhas) < 4:
        raise ErroModelo("Ficheiro da molécula vazio.")
    try:
        n_at, n_lig = int(linhas[3][0:3]), int(linhas[3][3:6])
    except ValueError as erro:
        raise ErroModelo("Formato SDF não reconhecido.") from erro
    if not 0 < n_at <= 300:
        raise ErroModelo("Molécula demasiado grande para o visualizador (máx. 300 átomos).")
    atomos = []
    for ln in linhas[4:4 + n_at]:
        partes = ln.split()
        atomos.append(([float(partes[0]), float(partes[1]), float(partes[2])], partes[3]))
    cx = sum(a[0][0] for a in atomos) / n_at
    cy = sum(a[0][1] for a in atomos) / n_at
    cz = sum(a[0][2] for a in atomos) / n_at
    extensao = max(max(abs(a[0][0] - cx), abs(a[0][1] - cy), abs(a[0][2] - cz)) for a in atomos) or 1
    k = min(1.0, 3.0 / extensao)  # cabe na caixa de -3 a 3
    pos = [[round((a[0][0] - cx) * k, 4), round((a[0][1] - cy) * k, 4), round((a[0][2] - cz) * k, 4)] for a in atomos]
    partes = []
    contagem: dict = {}
    for i, (p, el) in enumerate(zip(pos, (a[1] for a in atomos))):
        contagem[el] = contagem.get(el, 0) + 1
        partes.append({"id": f"{el.lower()}{contagem[el]}", "nome": f"{el}{contagem[el]}", "tipo": "esfera",
                       "dims": {"raio": RAIO_ATOMO.get(el, 0.42) * max(k, 0.5)}, "posicao": p,
                       "cor": CORES_CPK.get(el, "#E77FC7"), "material": {"tipo": "brilhante"}, "grupo": f"Átomos de {el}",
                       "descricao": f"Átomo de {el}."})
    for ln in linhas[4 + n_at:4 + n_at + n_lig]:
        try:
            a, b, ordem = int(ln[0:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])
        except ValueError:
            continue
        if not (0 <= a < n_at and 0 <= b < n_at):
            continue
        pa, pb = pos[a], pos[b]
        d = [pb[i] - pa[i] for i in range(3)]
        comp = math.sqrt(sum(x * x for x in d)) or 1
        # vetor perpendicular para desenhar ligações duplas/triplas lado a lado
        aux = [0, 0, 1] if abs(d[2]) < 0.9 * comp else [0, 1, 0]
        perp = [d[1] * aux[2] - d[2] * aux[1], d[2] * aux[0] - d[0] * aux[2], d[0] * aux[1] - d[1] * aux[0]]
        n = math.sqrt(sum(x * x for x in perp)) or 1
        perp = [x / n * 0.07 for x in perp]
        desvios = {1: [0], 2: [-1, 1], 3: [-1.6, 0, 1.6]}.get(ordem, [0])
        for j, s in enumerate(desvios):
            o = [perp[i] * s for i in range(3)]
            partes.append({"id": f"lig_{a + 1}_{b + 1}_{j}", "nome": f"Ligação {atomos[a][1]}–{atomos[b][1]}",
                           "tipo": "cilindro", "dims": {"raio_topo": 0.05, "raio_base": 0.05,
                                                         "de": [pa[i] + o[i] for i in range(3)],
                                                         "ate": [pb[i] + o[i] for i in range(3)]},
                           "cor": "#B8B2A6", "material": {"tipo": "brilhante"}, "grupo": "Ligações",
                           "descricao": {1: "Ligação simples.", 2: "Ligação dupla.", 3: "Ligação tripla."}.get(ordem, "Ligação.")})
    formula = "".join(f"{el}{n if n > 1 else ''}" for el, n in sorted(contagem.items(), key=lambda kv: (kv[0] != "C", kv[0] != "H", kv[0])))
    return normalizar_modelo({"titulo": nome, "descricao": f"Estrutura 3D de {nome} ({formula}), dados do PubChem.",
                              "partes": partes, "cena": {"etiquetas": False}})


# ------------------------------------------------------------------ superfícies z = f(x, y)
def modelo_superficie(titulo: str, alturas: list, nx: int, ny: int, largura: float = 6.0, profundidade: float = 6.0) -> dict:
    """Gráfico 3D: uma superfície com cores pela altura (alturas já em unidades do visualizador, linha a linha)."""
    return normalizar_modelo({"titulo": titulo, "partes": [{
        "id": "superficie", "nome": titulo, "tipo": "superficie", "cor": "#2AA5B8", "material": {"tipo": "padrao"},
        "dims": {"nx": nx, "ny": ny, "largura": largura, "profundidade": profundidade, "alturas": alturas,
                 "cores_por_altura": True}}], "cena": {"etiquetas": False}})
