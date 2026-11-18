"""
Motor Blender do 3D Studio: o Blender refaz as peças dos modelos com mais qualidade (arestas arredondadas, superfícies
suaves, relevo orgânico, materiais físicos) e devolve um ficheiro GLB que o visualizador usa no lugar das peças simples.

Onde corre o Blender (por esta ordem):
1. num servidor Blender (para todos os utilizadores da app online): endereço e chave em .streamlit/secrets.toml
   ([blender] url / token) ou em Perfil → Chaves e dados → Chave da IA;
2. no próprio computador onde corre a app, se o Blender estiver instalado (é encontrado sozinho).

O Blender só recebe a FORMA das peças (tipo, dimensões, material) em JSON e corre sempre o mesmo script
(blender/construir_modelo.py): nunca executa código vindo da IA nem dos utilizadores.
Não depende do Streamlit (testado em testes_blender.py; o servidor está em servidor_blender/servidor.py).
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import estudio3d as e3

PASTA = Path(__file__).resolve().parent
SCRIPT = PASTA / "blender" / "construir_modelo.py"
TEMPO_MAXIMO = 300  # segundos
_cache_exe: dict = {}


class ErroBlender(Exception):
    """Erro com mensagem pronta a mostrar."""


# ------------------------------------------------------------------------------------------- encontrar o Blender
def _versao_do_caminho(caminho: str) -> tuple:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", caminho)
    return tuple(int(x or 0) for x in m.groups()) if m else (0, 0, 0)


def encontrar_blender(caminho: str | None = None) -> str | None:
    """Executável do Blender: o indicado, a variável MONDEGO_BLENDER, o que estiver no PATH ou os sítios habituais
    de instalação (Windows, macOS, Linux). Escolhe a versão mais recente."""
    for c in (caminho, os.environ.get("MONDEGO_BLENDER")):
        if c and Path(c).is_file():
            return str(Path(c))
    chave = "auto"
    if chave in _cache_exe and (_cache_exe[chave] is None or Path(_cache_exe[chave]).is_file()):
        return _cache_exe[chave]
    candidatos = []
    no_path = shutil.which("blender")
    if no_path:
        candidatos.append(no_path)
    sistema = platform.system()
    if sistema == "Windows":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                     os.path.expandvars(r"%LOCALAPPDATA%\Programs")):
            if base:
                candidatos += glob.glob(os.path.join(base, "Blender Foundation", "Blender*", "blender.exe"))
        candidatos += glob.glob(os.path.expandvars(r"%ProgramFiles%\Steam\steamapps\common\Blender\blender.exe"))
    elif sistema == "Darwin":
        candidatos += glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender")
    else:
        candidatos += glob.glob("/opt/blender*/blender") + glob.glob("/usr/local/blender*/blender") + ["/usr/bin/blender"]
    existentes = [c for c in candidatos if c and Path(c).is_file()]
    existentes.sort(key=_versao_do_caminho, reverse=True)
    _cache_exe[chave] = existentes[0] if existentes else None
    return _cache_exe[chave]


def nome_blender(exe: str) -> str:
    v = _versao_do_caminho(str(Path(exe).parent))
    return f"Blender {v[0]}.{v[1]}" if v[0] else "Blender"


# ------------------------------------------------------------------------------------------- preparação
def preparar(modelo: dict) -> dict:
    """Só a forma das peças visíveis vai para o Blender (sem textos, posições nem cores)."""
    partes = []
    for p in modelo.get("partes", []):
        if not p.get("visivel", True) or p.get("tipo") == "superficie":
            continue
        partes.append({"id": p["id"], "tipo": p["tipo"], "dims": p.get("dims") or {},
                       "material": (p.get("material") or {}).get("tipo", "padrao")})
    return {"formato": "mondego3d-blender", "versao": 1, "partes": partes}


def hashes(modelo: dict) -> dict:
    return {p["id"]: e3.hash_geometria(p) for p in modelo.get("partes", [])
            if p.get("visivel", True) and p.get("tipo") != "superficie"}


def pecas_atualizadas(modelo: dict) -> list:
    """Peças cuja forma ainda é a que o Blender fez (as outras aparecem como peças simples até se refazer)."""
    b = modelo.get("blender") or {}
    feitas = b.get("hashes") or {}
    if not b.get("id"):
        return []
    return [p["id"] for p in modelo.get("partes", []) if feitas.get(p["id"]) and feitas[p["id"]] == e3.hash_geometria(p)]


def por_refazer(modelo: dict) -> list:
    feitas = set(pecas_atualizadas(modelo))
    return [i for i in hashes(modelo) if i not in feitas]


# ------------------------------------------------------------------------------------------- executar
def construir_local(modelo: dict, exe: str, tempo: int = TEMPO_MAXIMO) -> tuple[bytes, str]:
    """Corre o Blender neste computador, sem janela. Devolve (GLB, registo do Blender)."""
    if not SCRIPT.is_file():
        raise ErroBlender("Falta o ficheiro blender/construir_modelo.py.")
    entrada = preparar(modelo)
    if not entrada["partes"]:
        raise ErroBlender("O modelo não tem peças que o Blender possa melhorar.")
    with tempfile.TemporaryDirectory(prefix="mondego_blender_") as pasta:
        f_in, f_out = Path(pasta) / "entrada.json", Path(pasta) / "saida.glb"
        f_in.write_text(json.dumps(entrada), encoding="utf-8")
        cmd = [exe, "-b", "--factory-startup", "-noaudio", "--python-exit-code", "1", "--python", str(SCRIPT),
               "--", str(f_in), str(f_out)]
        extra = {"creationflags": 0x08000000} if platform.system() == "Windows" else {}  # sem janela de consola
        inicio = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=tempo, **extra)
        except subprocess.TimeoutExpired:
            raise ErroBlender(f"O Blender demorou mais de {tempo} s. Tenta um modelo com menos peças.") from None
        except OSError as erro:
            raise ErroBlender(f"Não foi possível abrir o Blender ({erro}).") from None
        registo = (r.stdout or "") + "\n" + (r.stderr or "")
        if r.returncode != 0 or not f_out.is_file() or f_out.stat().st_size < 20:
            ultimas = "\n".join(l for l in registo.splitlines() if l.strip())[-1500:]
            raise ErroBlender("O Blender não conseguiu construir o modelo.\n" + ultimas)
        dados = f_out.read_bytes()
        return dados, registo + f"\n[tempo total: {time.time() - inicio:.1f} s]"


def construir_servidor(modelo: dict, url: str, token: str, tempo: int = TEMPO_MAXIMO) -> bytes:
    """Pede o modelo a um servidor Blender (servidor_blender/servidor.py). A chave vai no cabeçalho."""
    if not url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise ErroBlender("O endereço do servidor Blender tem de começar por https://")
    pedido = urllib.request.Request(url.rstrip("/") + "/construir", data=json.dumps(preparar(modelo)).encode("utf-8"),
                                    method="POST", headers={"Authorization": f"Bearer {token}",
                                                            "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo) as r:
            dados = r.read()
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:500]
        raise ErroBlender(f"O servidor Blender respondeu {erro.code}: {detalhe}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroBlender(f"Sem ligação ao servidor Blender ({getattr(erro, 'reason', erro)}).") from None
    if dados[:4] != b"glTF":
        raise ErroBlender("O servidor Blender não devolveu um ficheiro GLB.")
    return dados


def estado_servidor(url: str, token: str) -> dict:
    pedido = urllib.request.Request(url.rstrip("/") + "/estado", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as erro:  # noqa: BLE001
        raise ErroBlender(f"O servidor Blender não respondeu ({erro}).") from None


def construir(modelo: dict, servidor: dict | None = None, caminho_local: str | None = None) -> tuple[bytes, str]:
    """Usa o servidor (se configurado) ou o Blender deste computador. Devolve (GLB, nome do motor)."""
    if servidor and servidor.get("url") and servidor.get("token"):
        return construir_servidor(modelo, servidor["url"], servidor["token"]), "Servidor Blender"
    exe = encontrar_blender(caminho_local)
    if not exe:
        raise ErroBlender("Não encontrei o Blender. Instala-o (blender.org, grátis) ou liga um servidor Blender.")
    dados, _ = construir_local(modelo, exe)
    return dados, nome_blender(exe)
