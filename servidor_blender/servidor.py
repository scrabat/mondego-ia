"""
Servidor Blender do Mondego IA — para que TODOS os utilizadores da app online tenham modelos 3D feitos no Blender.

Recebe a forma das peças (JSON, sem código) e devolve o GLB feito pelo Blender (blender/construir_modelo.py).
Corre num computador ou servidor com o Blender instalado (ver o Dockerfile ao lado, que já o instala).

Variáveis de ambiente:
  MONDEGO_TOKEN     chave obrigatória (a app envia-a no cabeçalho Authorization: Bearer ...)
  MONDEGO_BLENDER   caminho do executável do Blender (opcional; senão procura nos sítios habituais)
  MONDEGO_TRABALHOS quantos modelos ao mesmo tempo (por omissão 1)
  PORT              porta (por omissão 8080)

Endereços: GET /saude (sem chave, para verificações do alojamento), GET /estado e POST /construir (com chave).
Na app: Definições → IA → Servidor Blender, ou .streamlit/secrets.toml → [blender] url = "https://...", token = "...".
"""
from __future__ import annotations

import hmac
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import estudio3d as e3  # noqa: E402
import motor_blender as mb  # noqa: E402

TOKEN = os.environ.get("MONDEGO_TOKEN", "")
MAX_PEDIDO = 2_000_000
TRABALHOS = threading.Semaphore(max(1, int(os.environ.get("MONDEGO_TRABALHOS", "1"))))


def modelo_do_pedido(entrada: dict) -> dict:
    """Valida cada peça com as mesmas regras da app (limites de tamanho, tipos conhecidos, números)."""
    partes = []
    for p in (entrada.get("partes") or [])[:e3.MAX_PARTES]:
        if not isinstance(p, dict):
            continue
        try:
            q = e3.normalizar_parte({"id": p.get("id"), "tipo": p.get("tipo"), "dims": p.get("dims"),
                                     "material": {"tipo": p.get("material")}})
        except e3.ErroModelo:
            continue
        q["id"] = e3.slug(p.get("id") or q["id"])
        partes.append(q)
    return {"partes": partes}


class Pedidos(BaseHTTPRequestHandler):
    server_version = "MondegoBlender/1"

    def _autorizado(self) -> bool:
        return bool(TOKEN) and hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {TOKEN}")

    def _responder(self, codigo: int, corpo: bytes, tipo: str = "application/json") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, codigo: int, dados: dict) -> None:
        self._responder(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):  # noqa: N802
        caminho = self.path.split("?")[0].rstrip("/")
        if caminho == "/saude":
            return self._json(200, {"ok": True})
        if caminho != "/estado":
            return self._json(404, {"erro": "não existe"})
        if not self._autorizado():
            return self._json(401, {"erro": "chave inválida"})
        exe = mb.encontrar_blender()
        return self._json(200, {"ok": bool(exe), "blender": mb.nome_blender(exe) if exe else None})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0].rstrip("/") != "/construir":
            return self._json(404, {"erro": "não existe"})
        if not self._autorizado():
            return self._json(401, {"erro": "chave inválida"})
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = 0
        if tamanho <= 0 or tamanho > MAX_PEDIDO:
            return self._json(413, {"erro": "pedido vazio ou demasiado grande"})
        try:
            modelo = modelo_do_pedido(json.loads(self.rfile.read(tamanho).decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"erro": "JSON inválido"})
        if not modelo["partes"]:
            return self._json(400, {"erro": "sem peças válidas"})
        exe = mb.encontrar_blender()
        if not exe:
            return self._json(500, {"erro": "Blender não encontrado no servidor"})
        if not TRABALHOS.acquire(timeout=180):
            return self._json(503, {"erro": "servidor ocupado, tenta daqui a pouco"})
        try:
            glb, _registo = mb.construir_local(modelo, exe)
        except mb.ErroBlender as erro:
            return self._json(500, {"erro": str(erro)[:1500]})
        finally:
            TRABALHOS.release()
        return self._responder(200, glb, "model/gltf-binary")

    def log_message(self, formato, *args):  # registo curto, sem conteúdo dos pedidos
        sys.stderr.write("%s - %s\n" % (self.address_string(), formato % args))


def principal():
    if not TOKEN:
        raise SystemExit("Define a variável MONDEGO_TOKEN (uma chave longa e secreta).")
    porta = int(os.environ.get("PORT", "8080"))
    print(f"Servidor Blender do Mondego IA na porta {porta} · {mb.encontrar_blender() or 'Blender NÃO encontrado'}")
    ThreadingHTTPServer(("0.0.0.0", porta), Pedidos).serve_forever()


if __name__ == "__main__":
    principal()
