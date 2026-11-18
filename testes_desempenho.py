"""Testes das otimizações das respostas da IA (py -3.14 testes_desempenho.py). Não precisam de internet."""
import desempenho as dz

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


pedidos = []


def buscar():
    pedidos.append(1)
    return ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3-pro", "gemini-3.6-flash-preview"]


dz.CACHE_MODELOS.clear()
a = dz.modelos_em_cache("chave-1", buscar, agora=1000)
b = dz.modelos_em_cache("chave-1", buscar, agora=2000)
dz.modelos_em_cache("chave-2", buscar, agora=2000)
ok("Lista de modelos: pergunta à Google uma vez por chave e por hora (antes: antes de cada resposta)",
   a == b and len(pedidos) == 2)
dz.modelos_em_cache("chave-1", buscar, agora=1000 + dz.TTL_MODELOS + 1)
ok("Lista de modelos: passada uma hora, volta a perguntar", len(pedidos) == 3)


def falha():
    raise RuntimeError("sem rede")


ok("Lista de modelos: se a Google falhar, usa a última lista conhecida", dz.modelos_em_cache("chave-1", falha, agora=99_999) == a)
ok("A chave nunca fica guardada (só um resumo)", all("chave" not in k for k in dz.CACHE_MODELOS) and len(dz.resumo_chave("x")) == 16)
dz.SEM_PESQUISA_GOOGLE.clear()
dz.marcar_sem_pesquisa_google("k", 1800, agora=100)
ok("Pesquisa Google indisponível: fica memorizado 30 min para todas as sessões (não volta a falhar em cada pergunta)",
   dz.pesquisa_google_indisponivel("k", agora=1000) and not dz.pesquisa_google_indisponivel("k", agora=2000)
   and not dz.pesquisa_google_indisponivel("outra", agora=1000))
ok("Tarefa: perguntas simples vs. complexas (contas, passo a passo, código, comparações, documentos anexados)",
   dz.complexidade("O que é uma matriz?") == "simples" and dz.complexidade("Quem ganhou o Nobel da Física?") == "simples"
   and dz.complexidade("Explica passo a passo a inversa de uma matriz 3x3") == "complexa"
   and dz.complexidade("Resolve x^2 - 4 = 0") == "complexa" and dz.complexidade("Corrige este código Python") == "complexa"
   and dz.complexidade("Resume", anexos=True) == "complexa" and dz.complexidade("e agora?", resposta_anterior="x" * 3000) == "complexa")
modelos = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3-pro", "gemini-3.6-flash-preview", "gemini-3.5-flash-lite-preview"]
ok("Modelo: o mais rápido (flash-lite) para títulos e perguntas simples na velocidade «Rápida»",
   dz.ordenar_modelos(modelos, "Rápida", "simples")[0] == "gemini-3.5-flash-lite"
   and dz.ordenar_modelos(modelos, "Máxima qualidade", "leve")[0] == "gemini-3.5-flash-lite")
ok("Modelo: um flash completo para pedidos complexos (mesmo na «Rápida») e nas outras velocidades; versões de "
   "teste (preview) por último", dz.ordenar_modelos(modelos, "Rápida", "complexa")[0] == "gemini-3.5-flash"
   and dz.ordenar_modelos(modelos, "Equilibrada", "simples")[0] == "gemini-3.5-flash"
   and dz.ordenar_modelos(modelos, "Rápida", "complexa")[-1].endswith("preview"))
ok("Pensar: o mínimo nas perguntas simples (onde o modelo deixa), baixo no normal, médio nas difíceis em «Equilibrada»",
   dz.nivel_pensamento("gemini-3.5-flash-lite", "simples", "Rápida") == ("level", "minimal")
   and dz.nivel_pensamento("gemini-3.8-flash", "simples", "Rápida") == ("level", "low")
   and dz.nivel_pensamento("gemini-3.6-flash", "leve", "Equilibrada") == ("level", "minimal")
   and dz.nivel_pensamento("gemini-3.8-flash", "complexa", "Rápida") == ("level", "low")
   and dz.nivel_pensamento("gemini-3.8-flash", "complexa", "Equilibrada") == ("level", "medium")
   and dz.nivel_pensamento("gemini-3.8-flash", "complexa", "Máxima qualidade") is None
   and dz.nivel_pensamento("gemini-2.5-flash", "simples", "Rápida") == ("budget", 0))
ok("Temperatura: só nos modelos que a usam (os Gemini 3.6+ e 4 ignoram-na)",
   dz.aceita_temperatura("gemini-3.5-flash-lite") and not dz.aceita_temperatura("gemini-3.8-flash")
   and not dz.aceita_temperatura("gemini-4-hydrogen") and not dz.aceita_temperatura("gemini-3.6-flash"))
ok("Modelo: a família rápida do Gemini 4 conta como «flash» (antes ia para o fim da lista)",
   dz.ordenar_modelos(["gemini-3-pro", "gemini-4-hydrogen", "gemini-3.5-flash-lite"], "Rápida", "complexa")[0] == "gemini-4-hydrogen")
docs = {"algebra.pdf": ("A matriz inversa de A é a matriz que multiplicada por A dá a identidade. " * 30
                        + "Determinantes e matrizes. " * 300),
        "historia.pdf": "A Revolução Francesa começou em 1789 com a tomada da Bastilha. " * 400}
texto, n = dz.selecionar_relevante(docs, "O que é a matriz inversa?", 12_000)
ok("Documentos: só os excertos que interessam à pergunta (os de História ficam de fora)",
   n >= 1 and "inversa" in texto and "Bastilha" not in texto and len(texto) <= 12_000 + 200)
vazio, n0 = dz.selecionar_relevante(docs, "Quando sai a nova temporada de Fortnite?", 12_000)
ok("Documentos: pergunta sem nada a ver com os documentos não leva excertos (pedido muito mais pequeno)",
   vazio == "" and n0 == 0)
ok("Documentos: palavras comuns («como», «explica», «sobre») não contam como relevantes",
   dz.termos("Como é que explicas isso sobre a fotossíntese?") == ["explicas", "fotossintese"])
pequeno = {"notas.txt": "Fotossíntese: luz, água e CO2 dão glicose e oxigénio."}
ok("Documentos curtos e relevantes vão inteiros", dz.selecionar_relevante(pequeno, "fotossíntese", 12_000)[0].startswith("=== FICHEIRO"))
conversa = [{"role": "user", "content": "p1"}, {"role": "assistant", "content": "r" * 30_000},
            {"role": "user", "content": "p2"}, {"role": "assistant", "content": "r2"}, {"role": "user", "content": "p3"}]
ctx = dz.contexto_conversa(conversa, orcamento=8000)
ok("Histórico: cabe no orçamento, encurta respostas antigas enormes, começa no aluno e mantém a ordem",
   sum(len(m["content"]) for m in ctx) <= 8100 and ctx[0]["role"] == "user" and ctx[-1]["content"] == "p3"
   and any(m["content"].endswith("[…]") for m in ctx))
ok("Histórico: no máximo 16 mensagens", len(dz.contexto_conversa([{"role": "user", "content": "x"}] * 40)) == 16)
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
