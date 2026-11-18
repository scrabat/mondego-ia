"""
Geração 3D realista por um serviço externo (Meshy, text-to-3D) — LIGAÇÃO PREPARADA, AINDA NÃO TESTADA.

O 3D Studio já cria modelos com a IA do Mondego (o Gemini descreve o modelo em peças geométricas reais, editáveis peça a
peça). Para malhas foto-realistas (uma única malha esculpida, como num jogo) é preciso um serviço de geração 3D.
Para ativar:
  1. Criar conta em https://www.meshy.ai e gerar uma chave da API (planos pagos; tem créditos de teste).
  2. Colar a chave em Perfil → Chaves e dados → Chave da IA → «Chave Meshy (geração 3D realista)».
Sem chave, a opção aparece desativada com estas instruções. Nada é simulado.

API usada (documentação Meshy, text-to-3D v2):
  POST https://api.meshy.ai/openapi/v2/text-to-3d   {"mode": "preview", "prompt": ..., "art_style": ...} → {"result": id}
  GET  https://api.meshy.ai/openapi/v2/text-to-3d/{id} → {"status": "PENDING|IN_PROGRESS|SUCCEEDED|FAILED", "progress",
                                                         "model_urls": {"glb": url}, "task_error": {"message"}}
"""

from __future__ import annotations

BASE = "https://api.meshy.ai/openapi/v2/text-to-3d"
ESTILOS = {"Realista": "realistic", "Escultura": "sculpture"}


class ErroGerador(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


class GeradorMeshy:
    def __init__(self, chave: str):
        import httpx

        if not chave:
            raise ErroGerador("Falta a chave Meshy (Perfil → Chaves e dados → Chave da IA).")
        self.http = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {chave}"})

    def _verificar(self, r):
        if r.status_code == 401:
            raise ErroGerador("A chave Meshy foi recusada. Confirma-a em Perfil → Chaves e dados → Chave da IA.")
        if r.status_code == 402:
            raise ErroGerador("A conta Meshy não tem créditos suficientes.")
        if r.status_code == 429:
            raise ErroGerador("O Meshy está a limitar pedidos. Tenta daqui a um minuto.")
        if r.status_code >= 400:
            raise ErroGerador(f"O Meshy recusou o pedido ({r.status_code}): {r.text[:200]}")
        return r.json()

    def iniciar(self, descricao: str, estilo: str = "Realista") -> str:
        dados = self._verificar(self.http.post(BASE, json={
            "mode": "preview", "prompt": descricao.strip()[:600], "art_style": ESTILOS.get(estilo, "realistic"),
            "should_remesh": True}))
        if not dados.get("result"):
            raise ErroGerador("O Meshy não devolveu o identificador da tarefa.")
        return dados["result"]

    def estado(self, tarefa: str) -> dict:
        d = self._verificar(self.http.get(f"{BASE}/{tarefa}"))
        return {"estado": d.get("status", "?"), "progresso": int(d.get("progress") or 0),
                "glb": (d.get("model_urls") or {}).get("glb"), "erro": (d.get("task_error") or {}).get("message", "")}

    def descarregar(self, url: str) -> bytes:
        r = self.http.get(url, follow_redirects=True)
        if r.status_code >= 400 or not r.content:
            raise ErroGerador("Não foi possível descarregar o modelo gerado.")
        return r.content
