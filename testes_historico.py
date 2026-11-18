"""Testes do histórico das conversas (py -3.14 testes_historico.py)."""
from datetime import date

import historico as h

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


hoje = date(2026, 11, 3)
ok("Grupos por data: hoje, ontem, 7 dias, 30 dias e mais antigas (datas inválidas vão para o fim)",
   [h.grupo_da_data(d, hoje) for d in ["2026-11-03T10:00:00", "2026-11-02T23:59:00", "2026-10-28T09:00:00",
                                       "2026-10-10T09:00:00", "2026-01-01T09:00:00", "lixo", None]]
   == ["Hoje", "Ontem", "Últimos 7 dias", "Últimos 30 dias", "Mais antigas", "Mais antigas", "Mais antigas"])

conversas = {
    "a": {"titulo": "Matrizes inversas", "atualizada": "2026-11-03T09:00:00", "mensagens": [
        {"role": "user", "content": "Como se calcula a inversa?"}, {"role": "assistant", "content": "Com o método de Gauss-Jordan."}]},
    "b": {"titulo": "Tempo em Coimbra", "atualizada": "2026-11-02T18:00:00", "mensagens": []},
    "c": {"titulo": "Revolução Francesa", "atualizada": "2026-10-01T18:00:00", "fixada": True, "mensagens": []},
    "d": {"titulo": "Derivadas", "atualizada": "2026-10-30T18:00:00", "mensagens": []},
    "e": {"titulo": "Sem data", "mensagens": []},
    "x": "lixo",
}
grupos, escondidas = h.agrupar(conversas, hoje)
ok("Fixadas primeiro (mesmo antigas); depois os grupos por data, cada um do mais recente para o mais antigo",
   [(g, [cid for cid, _ in itens]) for g, itens in grupos]
   == [("Fixadas", ["c"]), ("Hoje", ["a"]), ("Ontem", ["b"]), ("Últimos 7 dias", ["d"]), ("Mais antigas", ["e"])]
   and escondidas == 0)
grupos, escondidas = h.agrupar(conversas, hoje, limite=2)
ok("Limite: mostra só as mais recentes (as fixadas não contam) e diz quantas ficaram escondidas",
   [(g, [cid for cid, _ in itens]) for g, itens in grupos] == [("Fixadas", ["c"]), ("Hoje", ["a"]), ("Ontem", ["b"])]
   and escondidas == 2)
ok("Pesquisa: no título e nas mensagens, sem ligar a maiúsculas nem acentos; todas as palavras têm de aparecer",
   [cid for cid, _ in h.agrupar(conversas, hoje, "gauss jordan")[0][0][1]] == ["a"]
   and [cid for cid, _ in h.agrupar(conversas, hoje, "REVOLUCAO")[0][0][1]] == ["c"]
   and h.agrupar(conversas, hoje, "gauss coimbra") == ([], 0)
   and h.agrupar(conversas, hoje, "  ")[0][0][0] == "Fixadas")
ok("Pesquisa: os resultados vêm num só grupo «Resultados»", h.agrupar(conversas, hoje, "o")[0][0][0] == "Resultados")
ok("Título provisório: o início da pergunta (como antes)", h.titulo_provisorio("  Olá   mundo ") == "Olá mundo"
   and h.titulo_provisorio("x" * 50) == "x" * 42 + "…" and h.titulo_provisorio("") == "Conversa")
ok("Título da IA: tira aspas, «Título:», asteriscos e ponto final; maiúscula no início",
   h.limpar_titulo('Título: "inversa de uma matriz".') == "Inversa de uma matriz"
   and h.limpar_titulo("**Data da nova temporada de Fortnite**\n") == "Data da nova temporada de Fortnite"
   and h.limpar_titulo("«Previsão do tempo em Coimbra»") == "Previsão do tempo em Coimbra")
ok("Título da IA: recusa respostas que não são um título (vazio, JSON, comprido demais)",
   h.limpar_titulo("") is None and h.limpar_titulo('{"dias": []}') is None
   and h.limpar_titulo("Isto é uma resposta muito comprida que não serve de título nenhum para a conversa") is None)
ok("Pedido do título: curto, na língua da pergunta, sem aspas nem ponto final",
   "3 a 6 palavras" in h.PEDIDO_TITULO and "{pergunta}" in h.PEDIDO_TITULO and "sem aspas" in h.PEDIDO_TITULO)
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
