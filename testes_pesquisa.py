"""Testes da pesquisa na web feita pela app, sem internet (py -3.14 testes_pesquisa.py)."""
import io
import json
import urllib.parse

import pesquisa_web as pw

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


PEDIDOS = []


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def falso_urlopen(pedido, timeout=None):
    url = pedido.full_url
    PEDIDOS.append((url, pedido.get_method(), dict(pedido.header_items()), pedido.data))
    if "news.google.com" in url:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
        if q == "sem notícias":
            return Resposta(b"<rss><channel></channel></rss>")
        if q == "ordem":
            return Resposta(("<rss><channel><item><title>Antiga - A</title><link>https://a</link><pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate></item>"
                             "<item><title>Recente - B</title><link>https://b</link><pubDate>Sun, 01 Nov 2026 10:00:00 GMT</pubDate></item>"
                             "</channel></rss>").encode("utf-8"))
        return Resposta(("<?xml version='1.0'?><rss version='2.0'><channel><title>Google Notícias</title>"
                         "<item><title>Fortnite: nova temporada chega a 5 de dezembro - Eurogamer</title>"
                         "<link>https://news.google.com/rss/articles/abc</link><pubDate>Sat, 31 Oct 2026 10:00:00 GMT</pubDate>"
                         "<source url='https://eurogamer.pt'>Eurogamer</source></item>"
                         "<item><title></title><link>https://x</link></item>"
                         "<item><title>Epic confirma data</title><link>https://news.google.com/rss/articles/def</link>"
                         "<pubDate>data estranha</pubDate></item></channel></rss>").encode("utf-8"))
    if "geocoding-api.open-meteo.com" in url:
        nome = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["name"][0]
        if nome.startswith("Atlântida"):
            return Resposta(b"{}")
        return Resposta(json.dumps({"results": [{"name": "Coimbra", "admin1": "Distrito de Coimbra", "country": "Portugal",
                                                 "latitude": 40.2, "longitude": -8.4}]}).encode())
    if "api.open-meteo.com" in url:
        return Resposta(json.dumps({"daily": {"time": ["2026-11-01", "2026-11-02"], "weather_code": [45, 61],
                                              "temperature_2m_max": [26.5, 18.0], "temperature_2m_min": [9.8, 11.2],
                                              "precipitation_probability_max": [0, 80], "wind_speed_10m_max": [10, 30]}}).encode())
    if "tavily" in url:
        if FALHAR_TAVILY["sim"]:
            raise OSError("sem ligação")
        return Resposta(json.dumps({"results": [{"title": "Tempo em Coimbra", "url": "https://tempo.pt/coimbra",
                                                 "content": "Amanhã:   sol,   20 °C."}, {"title": "sem url"}]}).encode())
    if "api.openalex.org" in url:
        busca = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["search"][0].lower()
        if "photosynthesis" not in busca and "fotossíntese" not in busca:
            return Resposta(b'{"results": []}')
        return Resposta(json.dumps({"results": [
            {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1042/abc", "display_name": "Photosynthesis:  light reactions",
             "publication_year": 2018, "primary_location": {"source": {"display_name": "Essays in Biochemistry"},
                                                            "landing_page_url": "https://portlandpress.com/x"},
             "abstract_inverted_index": {"converts": [1], "Photosynthesis": [0], "light": [2], "energy.": [3]}},
            {"id": "https://openalex.org/W2", "display_name": "Photosynthesis without abstract", "abstract_inverted_index": None},
            {"id": "https://openalex.org/W3", "display_name": "Tomato prices in 1990", "primary_location": {},
             "abstract_inverted_index": {"Prices": [0], "rose.": [1]}}]}).encode())
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    lingua = urllib.parse.urlparse(url).netloc.split(".")[0]
    if q.get("list") == ["search"]:
        if lingua == "pt" and q["srsearch"] in (["nada"], ["sem notícias"]):
            return Resposta(json.dumps({"query": {"search": []}}).encode())
        if lingua == "en":
            return Resposta(json.dumps({"query": {"search": [{"title": "Carnation Revolution"}]}}).encode())
        return Resposta(json.dumps({"query": {"search": [{"title": "Revolução dos Cravos"}, {"title": "Salgueiro Maia"},
                                                         {"title": "Ensaios da Anitta"}]}}).encode())
    if lingua == "en":
        return Resposta(json.dumps({"query": {"pages": {"1": {"title": "Carnation Revolution", "extract": "Military coup of 25 April 1974.",
                                                              "fullurl": "https://en.wikipedia.org/wiki/Carnation_Revolution"}}}}).encode())
    return Resposta(json.dumps({"query": {"pages": {
        "4": {"title": "Ensaios da Anitta", "fullurl": "https://pt.wikipedia.org/wiki/Ensaios", "extract": "Digressão da cantora em 2023."},
        "2": {"title": "Salgueiro Maia", "fullurl": f"https://{lingua}.wikipedia.org/wiki/Salgueiro_Maia",
              "extract": "Capitão de Abril, uma das figuras da Revolução dos Cravos."},
        "1": {"title": "Revolução dos Cravos", "fullurl": f"https://{lingua}.wikipedia.org/wiki/Revolu%C3%A7%C3%A3o_dos_Cravos",
              "extract": "Golpe   de 25 de Abril de 1974."},
        "3": {"title": "Sem texto", "extract": ""}}}}).encode())


pw.urllib.request.urlopen = falso_urlopen
FALHAR_TAVILY = {"sim": False}

r = pw.pesquisar_wikipedia("Revolução dos Cravos", "pt")
ok("Wikipédia: resultados pela ordem da pesquisa, com título, ligação e resumo (sem páginas vazias nem sem nada a ver)",
   [x["titulo"] for x in r] == ["Revolução dos Cravos — Wikipédia", "Salgueiro Maia — Wikipédia"]
   and r[0]["url"].startswith("https://pt.wikipedia.org/wiki/") and r[0]["texto"] == "Golpe de 25 de Abril de 1974.")
ok("Wikipédia: identifica-se com um User-Agent (regra da Wikimedia)", all("User-agent" in h or "User-Agent" in h
                                                                          for _, _, h, _ in PEDIDOS))
PEDIDOS.clear()
r, motor = pw.pesquisar({"pt": "sem notícias", "en": "Carnation Revolution"})
ok("Último recurso (sem obras académicas nem notícias): Wikipédia, primeiro em português e depois em inglês",
   motor == "Wikipédia" and r and r[0]["url"].startswith("https://en.wikipedia.org"))
PEDIDOS.clear()
r, motor = pw.pesquisar({"pt": "fotossíntese", "en": "photosynthesis light reactions", "tipo": "geral"})
ok("Conhecimento geral: obras académicas (OpenAlex) com resumo, revista e ano, e nada da Wikipédia",
   motor == "OpenAlex" and r[0] == {"titulo": "Photosynthesis: light reactions — Essays in Biochemistry (2018)",
                                    "url": "https://doi.org/10.1042/abc", "texto": "Photosynthesis converts light energy.",
                                    "fonte": "OpenAlex", "revista": "Essays in Biochemistry"}
   and not any("wikipedia" in u for u, *_ in PEDIDOS) and not any(x["fonte"] == "Wikipédia" for x in r))
ok("OpenAlex: sem resumo ou sem nada a ver com a pesquisa ficam de fora; pede textos de síntese em inglês",
   all("Tomato" not in x["titulo"] and "without abstract" not in x["titulo"] for x in r)
   and any("type%3Areview%7Cbook%7Cbook-chapter" in u for u, *_ in PEDIDOS if "openalex" in u))
PEDIDOS.clear()
r, motor = pw.pesquisar("tempo amanhã Coimbra", chave_tavily="tvly-segredo")
url, metodo, cab, corpo = PEDIDOS[0]
ok("Tavily (com chave): pesquisa em toda a web; a chave vai no cabeçalho, nunca no endereço",
   motor == "Tavily" and r == [{"titulo": "Tempo em Coimbra", "url": "https://tempo.pt/coimbra", "texto": "Amanhã: sol, 20 °C.",
                                "fonte": "Tavily"}]
   and metodo == "POST" and "tvly-segredo" not in url and cab.get("Authorization") == "Bearer tvly-segredo"
   and json.loads(corpo)["query"] == "tempo amanhã Coimbra")
r = pw.pesquisar_noticias("nova temporada Fortnite")
ok("Notícias (Google Notícias, sem chave): título, data, fonte e ligação; itens sem título ficam de fora",
   [x["titulo"] for x in r] == ["Fortnite: nova temporada chega a 5 de dezembro - Eurogamer", "Epic confirma data"]
   and r[0]["texto"] == "Notícia de 31/10/2026 (Eurogamer): Fortnite: nova temporada chega a 5 de dezembro - Eurogamer"
   and r[1]["texto"] == "Notícia: Epic confirma data" and r[0]["url"].startswith("https://news.google.com/"))
ok("Notícias: as mais recentes primeiro", [x["titulo"] for x in pw.pesquisar_noticias("ordem")] == ["Recente - B", "Antiga - A"])
ok("Preparar: tipo desconhecido conta como «geral», o tempo reconhece-se pela pergunta e ganha a localidade",
   pw.preparar({"pt": "x", "tipo": "??"})["tipo"] == "geral"
   and pw.preparar({"pt": "x", "tipo": "atual", "pergunta": "vai chover no Porto?"}) | {} == {"pt": "x", "tipo": "tempo",
                                                                                          "pergunta": "vai chover no Porto?", "local": "Porto"}
   and pw.preparar("texto")["tipo"] == "geral")
r, motor = pw.pesquisar({"pt": "nova temporada Fortnite", "en": "new Fortnite season", "tipo": "atual"})
ok("Pergunta sobre algo recente: notícias primeiro; páginas da Wikipédia sem nada a ver ficam de fora",
   motor == "Google Notícias" and r[0]["fonte"] == "Google Notícias" and not any(x["fonte"] == "Wikipédia" for x in r))
ok("Relevância: fica a página com as palavras no título ou várias no resumo",
   pw.relevante({"titulo": "Fortnite", "texto": ""}, "nova temporada Fortnite")
   and pw.relevante({"titulo": "Epic Games", "texto": "A nova temporada do Fortnite..."}, "temporada Fortnite")
   and not pw.relevante({"titulo": "Ensaios da Anitta", "texto": "Digressão com tempo de palco"}, "previsão tempo Coimbra amanhã"))
ok("Perguntas sobre o tempo reconhecem-se sem a IA (e a matéria não conta como tempo)",
   pw.parece_tempo("vai chover amanhã em Coimbra?") and pw.parece_tempo("weather in London tomorrow")
   and not pw.parece_tempo("O que é o calor específico?") and not pw.parece_tempo("chuva ácida")
   and not pw.parece_tempo("Que tempo verbal é este?"))
ok("Localidade tirada da pergunta", pw.local_da_pergunta("vai chover amanhã em Coimbra?") == "Coimbra"
   and pw.local_da_pergunta("previsão do tempo para Vila Nova de Gaia") == "Vila Nova de Gaia"
   and pw.local_da_pergunta("vai chover em lisboa?") == "Lisboa" and pw.local_da_pergunta("vai chover amanhã?") == "")
r = pw.previsao_tempo("Coimbra")
ok("Tempo (Open-Meteo, sem chave): previsão de 10 dias, com o dia da semana, o céu, temperaturas, chuva e vento",
   len(r) == 1 and "Previsão diária para Coimbra, Distrito de Coimbra, Portugal" in r[0]["texto"]
   and "2026-11-02 (segunda-feira): chuva fraca, mínima 11.2 °C, máxima 18.0 °C, probabilidade de chuva 80 %, vento até 30 km/h"
   in r[0]["texto"] and "2026-11-01 (domingo): nevoeiro" in r[0]["texto"]
   and "forecast_days=10" in [u for u, *_ in PEDIDOS if "api.open-meteo" in u][-1])
r, motor = pw.pesquisar({"pt": "tempo amanhã Coimbra", "tipo": "tempo", "local": "Coimbra"})
ok("Pergunta sobre o tempo: usa a previsão (sem ir à Wikipédia)", motor == "Open-Meteo" and len(r) == 1)
r, motor = pw.pesquisar({"pt": "tempo amanhã", "tipo": "tempo", "local": "Atlântida"})
ok("Localidade desconhecida: não inventa, procura nas notícias (nunca na Wikipédia)", r and motor == "Google Notícias")
PEDIDOS.clear()
r, motor = pw.pesquisar({"pt": "vai chover amanhã em Coimbra?", "en": "vai chover amanhã em Coimbra?", "tipo": "atual"})
geo = [u for u, *_ in PEDIDOS if "geocoding" in u]
ok("Mesmo se a IA classificar mal (ou falhar), a pergunta do tempo vai à previsão da cidade certa",
   motor == "Open-Meteo" and geo and "name=Coimbra" in geo[0])
PEDIDOS.clear()
r, motor = pw.pesquisar({"pt": "vai chover amanhã?", "tipo": "tempo"})
ok("Tempo sem localidade: usa Coimbra (e a IA vê o nome do sítio)", motor == "Open-Meteo" and "name=Coimbra" in PEDIDOS[0][0]
   and "Coimbra" in r[0]["texto"])
PEDIDOS.clear()
pw.previsao_tempo("Atlântida, Oceano")
ok("Localidade com vírgula: experimenta também só o nome antes da vírgula",
   [urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["name"][0] for u, *_ in PEDIDOS if "geocoding" in u]
   == ["Atlântida, Oceano", "Atlântida"])
ok("Tavily: pede para deixar de fora a Wikipédia e os sites de perguntas e respostas",
   all(d in json.loads(corpo)["exclude_domains"] for d in ("wikipedia.org", "brainly.", "studocu.com")))
ok("Fiabilidade: sites a evitar saem; oficiais, universidades e revistas primeiro, depois obras de referência",
   [x["url"] for x in pw.por_confianca([
       {"url": "https://blog.exemplo.com/a", "fonte": "Tavily"}, {"url": "https://pt.wikipedia.org/wiki/X", "fonte": "Tavily"},
       {"url": "https://www.infopedia.pt/x", "fonte": "Tavily"}, {"url": "https://www.uc.pt/fctuc/x", "fonte": "Tavily"},
       {"url": "https://brainly.com.br/tarefa/1", "fonte": "Tavily"}, {"url": "https://www.sns.gov.pt/x", "fonte": "Tavily"}])]
   == ["https://www.uc.pt/fctuc/x", "https://www.sns.gov.pt/x", "https://www.infopedia.pt/x", "https://blog.exemplo.com/a"])
FALHAR_TAVILY["sim"] = True
r, motor = pw.pesquisar({"pt": "fotossíntese", "en": "photosynthesis"}, chave_tavily="tvly-segredo")
ok("Se a Tavily falhar, usa as fontes abertas fiáveis (obras académicas), não a Wikipédia", motor == "OpenAlex" and r)


def sempre_falha(pedido, timeout=None):
    raise OSError("sem internet")


pw.urllib.request.urlopen = sempre_falha
ok("Sem internet não rebenta: devolve uma lista vazia", pw.pesquisar("qualquer coisa") == ([], ""))
ok("Nome curto de cada fonte (para mostrar enquanto a IA lê)",
   pw.nome_da_fonte({"titulo": "Fortnite: nova temporada - Eurogamer.pt", "fonte": "Google Notícias", "url": "https://news.google.com/x"})
   == "Eurogamer.pt" and pw.nome_da_fonte({"titulo": "X — Wikipédia", "fonte": "Wikipédia", "url": "https://pt.wikipedia.org/wiki/X"})
   == "Wikipédia" and pw.nome_da_fonte({"titulo": "Tempo", "fonte": "Tavily", "url": "https://www.tempo.pt/coimbra"}) == "tempo.pt"
   and pw.nome_da_fonte({"titulo": "X", "fonte": "OpenAlex", "revista": "Nature", "url": "https://doi.org/1"}) == "Nature")
bloco = pw.bloco_para_ia([{"titulo": "A", "url": "https://a.pt", "texto": "texto A"}, {"titulo": "B", "url": "https://b.pt", "texto": "texto B"}])
ok("Bloco para a IA: resultados numerados com ligação (para citar [n])", bloco == "[1] A — https://a.pt\ntexto A\n\n[2] B — https://b.pt\ntexto B")
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
