"""
Pesquisa na web feita pela própria app, para quando a pesquisa Google do Gemini não está disponível na chave
(a Google responde «429 RESOURCE_EXHAUSTED» à ferramenta de pesquisa nas contas sem quota para ela).

- Com uma chave da Tavily (tavily.com, plano grátis), pesquisa em toda a web, sem a Wikipédia nem sites de perguntas e
  respostas, fóruns ou trabalhos copiados; os sites mais fiáveis (organismos oficiais, universidades, revistas
  científicas, obras de referência) passam para a frente.
- Sem chave, junta fontes abertas e fiáveis, conforme a pergunta:
  · coisas recentes (lançamentos, notícias, resultados, datas) → Google Notícias (feed RSS público);
  · tempo → Open-Meteo (previsão grátis, sem chave);
  · conhecimento geral → OpenAlex (artigos de revisão, livros e capítulos de editoras académicas, com resumo), em
    inglês e em português. A Wikipédia só entra como último recurso, quando nada mais encontra resultados.
Os resultados vão para a IA, que responde com eles e cita os sites. Não depende do Streamlit (testes_pesquisa.py).
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

AGENTE = "MondegoIA/1.0 (aplicação de estudo para estudantes; https://github.com/)"
TEMPO = 8  # segundos por pedido: um site lento não pode atrasar a resposta toda


LOCAL_PADRAO = "Coimbra"  # perguntas sobre o tempo sem localidade (a app é para estudantes de Coimbra)


class ErroPesquisa(Exception):
    """Erro com mensagem pronta a mostrar."""


# Sites que não entram nas respostas: enciclopédias que qualquer pessoa edita, perguntas e respostas, fóruns e trabalhos
# de alunos copiados (não são fontes que se possam citar num trabalho).
DOMINIOS_EXCLUIDOS = ("wikipedia.org", "wikiwand.com", "wikimedia.org", "wikia.com", "fandom.com", "brainly.", "quora.com",
                      "reddit.com", "answers.yahoo.com", "br.answers.yahoo.com", "studocu.com", "passeidireto.com",
                      "scribd.com", "coursehero.com", "slideshare.net", "monografias.com", "trabalhosfeitos.com")

# Sites mais fiáveis: organismos oficiais, universidades, revistas e editoras científicas, obras de referência.
FIAVEIS_FORTES = (".gov", ".gov.pt", ".edu", ".edu.pt", ".ac.uk", ".europa.eu", "who.int", "un.org", "unesco.org", "oecd.org",
                  "doi.org", "openalex.org", "nature.com", "science.org", "sciencedirect.com", "springer.com", "wiley.com",
                  "cambridge.org", "oup.com", "academic.oup.com", "tandfonline.com", "jstor.org", "ncbi.nlm.nih.gov",
                  "nih.gov", "europepmc.org", "scielo.", "arxiv.org", "plos.org", "frontiersin.org", "mdpi.com",
                  "uc.pt", "ulisboa.pt", "up.pt", "unl.pt", "uminho.pt", "ua.pt", "iscte-iul.pt", "rcaap.pt", "b-on.pt")
FIAVEIS = ("britannica.com", "infopedia.pt", "ciberduvidas.iscte-iul.pt", "priberam.org", "dge.mec.pt", "dgeec.medu.pt",
           "cienciaviva.pt", "ine.pt", "pordata.pt", "bportugal.pt", "diariodarepublica.pt", "dre.pt", "portaldasaude.pt",
           "sns.gov.pt", "dgs.pt", "ipma.pt", "ensina.rtp.pt", "museu", "biblioteca", "khanacademy.org", "nasa.gov",
           "esa.int", "cern.ch", "nationalgeographic.com", "smithsonianmag.com", "bbc.co.uk", "publico.pt", "rtp.pt",
           "expresso.pt", "observador.pt", "lusa.pt", "reuters.com", "apnews.com")


def _anfitriao(url: str) -> str:
    host = urllib.parse.urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _coincide(host: str, dominio: str) -> bool:
    """«uc.pt» apanha «www.uc.pt» e «apps.uc.pt»; «.gov» apanha «nasa.gov»; «museu» apanha qualquer site de museu."""
    if dominio.startswith("."):
        return host.endswith(dominio)
    if "." not in dominio:
        return dominio in host
    return host == dominio or host.endswith("." + dominio) or (dominio.endswith(".") and dominio in host)


def excluido(url: str) -> bool:
    host = _anfitriao(url)
    return any(_coincide(host, d) for d in DOMINIOS_EXCLUIDOS)


def confianca(r: dict) -> int:
    """Quanto se pode confiar no site do resultado: 3 (oficial, universidade, revista científica), 2 (obra de referência,
    imprensa de referência), 1 (outros), 0 (Wikipédia como último recurso), -1 (a evitar: fica de fora)."""
    if r.get("fonte") == "OpenAlex":
        return 3
    if r.get("fonte") == "Wikipédia":  # só chega aqui como último recurso (nada mais encontrou): fica, mas no fim
        return 0
    host = _anfitriao(r.get("url"))
    if excluido(r.get("url")):
        return -1
    if any(_coincide(host, d) for d in FIAVEIS_FORTES):
        return 3
    if any(_coincide(host, d) for d in FIAVEIS):
        return 2
    return 1


def por_confianca(resultados: list) -> list:
    """Tira os sites a evitar e põe os mais fiáveis à frente (mantendo a ordem da pesquisa entre os do mesmo nível)."""
    return sorted((r for r in resultados if confianca(r) >= 0), key=lambda r: -confianca(r))


def _simples(texto: str) -> str:
    """Minúsculas e sem acentos (para comparar palavras)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")


# frases que só aparecem em perguntas sobre o tempo (não «calor» ou «chuva ácida», que são matéria)
FRASES_TEMPO = ("vai chover", "chover", "vai estar sol", "vai fazer sol", "previsao do tempo", "previsao meteorologica",
                "meteorolog", "que tempo vai fazer", "que tempo faz", "que tempo vai estar", "tempo amanha", "tempo hoje", "tempo para amanha", "tempo esta semana",
                "tempo no fim de semana", "tempo este fim de semana", "temperatura amanha", "temperatura hoje",
                "chuva amanha", "chuva hoje", "weather", "forecast", "will it rain")


def parece_tempo(texto: str) -> bool:
    t = _simples(texto)
    return any(f in t for f in FRASES_TEMPO)


_MAIUSC = "A-ZÁÂÃÀÉÊÍÓÔÕÚÇ"
_PALAVRA = r"[\wÀ-ÿ'-]+"


def local_da_pergunta(texto: str) -> str:
    """«vai chover amanhã em Coimbra?» → «Coimbra»; «tempo no Porto» → «Porto»; sem localidade → ''."""
    nome = rf"[{_MAIUSC}]{_PALAVRA}(?:\s+(?:de|da|do|das|dos)\s+[{_MAIUSC}]{_PALAVRA}|\s+[{_MAIUSC}]{_PALAVRA})*"
    achados = re.findall(rf"\b(?:em|no|na|para|in|at)\s+({nome})", texto)
    if achados:
        return achados[-1]
    m = re.search(rf"\bem\s+([a-zà-ÿ][\wà-ÿ'-]{{2,}})\s*(?:\?|!|\.|$)", texto.strip())
    return m.group(1).title() if m else ""


def _bruto(url: str, dados: dict | None = None, cabecalhos: dict | None = None) -> bytes:
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    pedido = urllib.request.Request(url, data=corpo, method="POST" if corpo else "GET",
                                    headers={"User-Agent": AGENTE, "Accept": "application/json", **(cabecalhos or {})})
    with urllib.request.urlopen(pedido, timeout=TEMPO) as resposta:
        return resposta.read()


def _pedir(url: str, dados: dict | None = None, cabecalhos: dict | None = None) -> dict:
    return json.loads(_bruto(url, dados, cabecalhos).decode("utf-8"))


def pesquisar_noticias(consulta: str, n: int = 6) -> list:
    """Notícias recentes (Google Notícias, edição portuguesa): título, fonte, data e ligação."""
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": consulta, "hl": "pt-PT", "gl": "PT", "ceid": "PT:pt-150"})
    raiz = ET.fromstring(_bruto(url, cabecalhos={"Accept": "application/rss+xml, application/xml"}))
    resultados = []
    for item in raiz.iter("item"):
        titulo = " ".join((item.findtext("title") or "").split())
        ligacao = (item.findtext("link") or "").strip()
        if not titulo or not ligacao:
            continue
        fonte = " ".join((item.findtext("source") or "").split())
        try:
            data = parsedate_to_datetime(item.findtext("pubDate") or "")
            quando, ordem = data.strftime("%d/%m/%Y"), data.timestamp()
        except (TypeError, ValueError):
            quando, ordem = "", 0
        resultados.append((ordem, {"titulo": titulo, "url": ligacao, "fonte": "Google Notícias",
                                   "texto": f"Notícia{' de ' + quando if quando else ''}{' (' + fonte + ')' if fonte else ''}: {titulo}"}))
        if len(resultados) >= n:
            break
    # as mais recentes primeiro (para «último jogo», «nova temporada»...); as sem data no fim
    return [r for _, r in sorted(resultados, key=lambda x: -x[0])]


TEMPO_WMO = {0: "céu limpo", 1: "pouco nublado", 2: "parcialmente nublado", 3: "nublado", 45: "nevoeiro", 48: "nevoeiro com geada",
             51: "chuvisco fraco", 53: "chuvisco", 55: "chuvisco forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
             66: "chuva gelada", 67: "chuva gelada forte", 71: "neve fraca", 73: "neve", 75: "neve forte", 77: "granizo miúdo",
             80: "aguaceiros fracos", 81: "aguaceiros", 82: "aguaceiros fortes", 85: "aguaceiros de neve",
             86: "aguaceiros de neve fortes", 95: "trovoada", 96: "trovoada com granizo", 99: "trovoada forte com granizo"}


DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _com_dia_semana(dia: str) -> str:
    from datetime import date
    try:
        return f"{dia} ({DIAS_SEMANA[date.fromisoformat(dia).weekday()]})"
    except (TypeError, ValueError):
        return str(dia)


def previsao_tempo(local: str, dias: int = 10) -> list:
    """Previsão diária (Open-Meteo, sem chave) para uma localidade («Coimbra», «Coimbra, Portugal»...)."""
    lugar = None
    antes = local.split(",")[0].strip()
    for nome in dict.fromkeys([local.strip(), antes, antes.split()[0] if antes.split() else ""]):
        if not nome:
            continue
        g = _pedir("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": nome, "count": 1, "language": "pt", "format": "json"}))
        if g.get("results"):
            lugar = g["results"][0]
            break
    if not lugar:
        return []
    f = _pedir("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lugar["latitude"], "longitude": lugar["longitude"], "timezone": "auto", "forecast_days": dias,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max"}))
    d = f.get("daily") or {}
    linhas = []
    for i, dia in enumerate(d.get("time") or []):
        def v(chave):
            lista = d.get(chave) or []
            return lista[i] if i < len(lista) else None
        linhas.append(f"{_com_dia_semana(dia)}: {TEMPO_WMO.get(v('weather_code'), 'tempo variável')}, mínima {v('temperature_2m_min')} °C, "
                      f"máxima {v('temperature_2m_max')} °C, probabilidade de chuva {v('precipitation_probability_max')} %, "
                      f"vento até {v('wind_speed_10m_max')} km/h")
    nome = ", ".join(x for x in [lugar.get("name"), lugar.get("admin1"), lugar.get("country")] if x)
    return [{"titulo": f"Previsão do tempo para {lugar.get('name')} — Open-Meteo",
             "url": f"https://open-meteo.com/en/docs#latitude={lugar['latitude']}&longitude={lugar['longitude']}",
             "texto": f"Previsão diária para {nome}:\n" + "\n".join(linhas), "fonte": "Open-Meteo"}] if linhas else []


def pesquisar_tavily(consulta: str, chave: str, n: int = 5) -> list:
    """Pesquisa em toda a web. A chave vai no cabeçalho (nunca no endereço)."""
    r = _pedir("https://api.tavily.com/search", {"query": consulta, "max_results": n + 2, "search_depth": "basic",
                                                 "exclude_domains": list(DOMINIOS_EXCLUIDOS)},
               {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    return por_confianca([{"titulo": (x.get("title") or x.get("url") or "").strip(), "url": x["url"],
                           "texto": " ".join(str(x.get("content") or "").split())[:1500], "fonte": "Tavily"}
                          for x in r.get("results") or [] if isinstance(x, dict) and x.get("url")])[:n]


PARAGEM = {"quando", "qual", "quais", "quem", "como", "onde", "porque", "sobre", "amanha", "hoje", "esta", "este", "isso",
           "isto", "para", "pela", "pelo", "numa", "num", "mais", "menos", "data", "what", "when", "which", "with",
           "from", "that", "this", "does", "will", "nova", "novo", "date", "release"}


def relevante(pagina: dict, consulta: str) -> bool:
    """A Wikipédia procura no texto todo e devolve páginas sem nada a ver («Ensaios da Anitta» para o tempo em Coimbra).
    Fica só o que tem as palavras da pesquisa no título ou várias no resumo."""
    chaves = [w for w in re.findall(r"\w+", _simples(consulta)) if len(w) >= 4 and w not in PARAGEM]
    if not chaves:
        return True
    titulo, texto = _simples(pagina.get("titulo", "")), _simples(pagina.get("texto", ""))
    if any(w in titulo for w in chaves):
        return True
    return sum(w in texto for w in chaves) >= max(2, (len(chaves) + 1) // 2)


def _resumo_openalex(indice: dict | None) -> str:
    """O OpenAlex guarda o resumo como {palavra: [posições]}: volta a pô-lo por ordem."""
    if not isinstance(indice, dict):
        return ""
    posicoes = [(p, palavra) for palavra, lista in indice.items() for p in (lista or []) if isinstance(p, int)]
    return " ".join(palavra for _, palavra in sorted(posicoes))


def pesquisar_openalex(consulta: str, n: int = 4, tipos: str = "") -> list:
    """Artigos, revisões, livros e capítulos de editoras académicas (OpenAlex: catálogo aberto da investigação científica,
    sem chave). Só obras com resumo e não retiradas. tipos: ex. «review|book|book-chapter» para textos de síntese."""
    filtro = "has_abstract:true,is_retracted:false" + (f",type:{tipos}" if tipos else "")
    r = _pedir("https://api.openalex.org/works?" + urllib.parse.urlencode({
        "search": consulta, "per-page": n + 2, "filter": filtro,
        "select": "id,doi,display_name,publication_year,primary_location,abstract_inverted_index,cited_by_count"}))
    resultados = []
    for x in r.get("results") or []:
        if not isinstance(x, dict) or not x.get("display_name"):
            continue
        local = x.get("primary_location") or {}
        revista = " ".join(str((local.get("source") or {}).get("display_name") or "").split())
        url = x.get("doi") or local.get("landing_page_url") or x.get("id") or ""
        texto = " ".join(_resumo_openalex(x.get("abstract_inverted_index")).split())
        if not url or not texto:
            continue
        ano = x.get("publication_year")
        titulo = " ".join(str(x["display_name"]).split())
        pagina = {"titulo": titulo + (f" — {revista}" if revista else "") + (f" ({ano})" if ano else ""), "url": url,
                  "texto": texto[:1500], "fonte": "OpenAlex", "revista": revista or "artigo científico"}
        if relevante({"titulo": titulo, "texto": texto}, consulta):
            resultados.append(pagina)
    return resultados[:n]


def pesquisar_wikipedia(consulta: str, idioma: str = "pt", n: int = 3) -> list:
    base = f"https://{idioma}.wikipedia.org/w/api.php?"
    r = _pedir(base + urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": consulta, "srlimit": n,
                                              "format": "json", "utf8": 1}))
    titulos = [x["title"] for x in (r.get("query") or {}).get("search") or [] if x.get("title")]
    if not titulos:
        return []
    r2 = _pedir(base + urllib.parse.urlencode({"action": "query", "prop": "extracts|info", "inprop": "url", "exintro": 1,
                                               "explaintext": 1, "exchars": 1500, "redirects": 1, "format": "json",
                                               "titles": "|".join(titulos)}))
    ordem = {t: i for i, t in enumerate(titulos)}
    paginas = []
    for p in ((r2.get("query") or {}).get("pages") or {}).values():
        texto = " ".join(str(p.get("extract") or "").split())
        if texto:
            url = p.get("fullurl") or f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ', '_'))}"
            paginas.append((ordem.get(p.get("title"), 99), {"titulo": f"{p['title']} — Wikipédia", "url": url,
                                                             "texto": texto[:1500], "fonte": "Wikipédia"}))
    return [p for _, p in sorted(paginas, key=lambda x: x[0]) if relevante(p, consulta)]


def preparar(consultas: dict | str) -> dict:
    """Completa as consultas: o tipo final (o tempo reconhece-se mesmo sem a IA) e a localidade."""
    if isinstance(consultas, str):
        consultas = {"pt": consultas, "en": consultas}
    consultas = dict(consultas)
    pergunta = consultas.get("pergunta") or consultas.get("pt") or consultas.get("en") or ""
    tipo = consultas.get("tipo") if consultas.get("tipo") in ("atual", "tempo", "geral") else "geral"
    if tipo != "tempo" and parece_tempo(pergunta):
        tipo = "tempo"
    if tipo == "tempo" and not consultas.get("local"):
        consultas["local"] = local_da_pergunta(pergunta) or LOCAL_PADRAO
    consultas["tipo"] = tipo
    return consultas


def pesquisar(consultas: dict | str, chave_tavily: str | None = None) -> tuple[list, str]:
    """consultas: texto ou {"pt", "en", "tipo": "atual" | "tempo" | "geral", "local", "pergunta"}.
    Devolve (resultados, motores usados). Nunca rebenta: sem nada, ([], "")."""
    consultas = preparar(consultas)
    principal = consultas.get("pt") or consultas.get("en") or ""
    tipo = consultas["tipo"]
    if chave_tavily and principal:
        try:
            resultados = pesquisar_tavily(principal, chave_tavily)
            if resultados:
                return resultados, "Tavily"
        except Exception:  # noqa: BLE001 — sem a Tavily, usa as fontes abertas
            pass
    resultados, motores, vistos = [], [], set()

    def juntar(lista, motor):
        novos = [r for r in lista if r["url"] not in vistos]
        for r in novos:
            vistos.add(r["url"])
            resultados.append(r)
        if novos and motor not in motores:
            motores.append(motor)

    if tipo == "tempo" and consultas.get("local"):
        try:
            juntar(previsao_tempo(consultas["local"]), "Open-Meteo")
        except Exception:  # noqa: BLE001
            pass
    if tipo == "atual" and principal:
        try:
            juntar(pesquisar_noticias(principal), "Google Notícias")
        except Exception:  # noqa: BLE001
            pass
    if tipo == "tempo" and not resultados and principal:  # sem previsão: notícias (a Wikipédia não tem o tempo)
        try:
            juntar(pesquisar_noticias(principal), "Google Notícias")
        except Exception:  # noqa: BLE001
            pass
    if tipo == "geral":  # conhecimento: textos de síntese de editoras académicas primeiro (em inglês há muito mais)
        from concurrent.futures import ThreadPoolExecutor

        pedidos = [(consultas.get(idioma) or principal, n, tipos)
                   for idioma, tipos, n in (("en", "review|book|book-chapter", 3), ("pt", "", 3))]
        pedidos = [p for p in pedidos if p[0]]
        if pedidos:  # as duas pesquisas ao mesmo tempo (antes uma depois da outra)
            with ThreadPoolExecutor(max_workers=len(pedidos)) as executor:
                futuros = [executor.submit(pesquisar_openalex, *p) for p in pedidos]
                for futuro in futuros:  # pela ordem (inglês primeiro), para o resultado ser sempre o mesmo
                    try:
                        juntar(futuro.result(), "OpenAlex")
                    except Exception:  # noqa: BLE001
                        continue
    if not resultados and principal and tipo == "geral":  # sem obras académicas: notícias
        try:
            juntar(pesquisar_noticias(principal), "Google Notícias")
        except Exception:  # noqa: BLE001
            pass
    if not resultados and tipo != "tempo":  # último recurso (e só quando nada mais encontrou): a Wikipédia
        for idioma in ("pt", "en"):
            consulta = consultas.get(idioma) or principal
            if not consulta or resultados:
                continue
            try:
                juntar(pesquisar_wikipedia(consulta, idioma), "Wikipédia")
            except Exception:  # noqa: BLE001
                continue
    return por_confianca(resultados)[:8] if tipo != "tempo" else resultados[:8], " e ".join(motores)


def nome_da_fonte(r: dict) -> str:
    """Nome curto do site para mostrar enquanto a IA lê («Eurogamer.pt», «Wikipédia», «tempo.pt»)."""
    titulo = r.get("titulo") or ""
    if r.get("fonte") == "Google Notícias" and " - " in titulo:
        return titulo.rsplit(" - ", 1)[1].strip()
    if r.get("fonte") in ("Wikipédia", "Open-Meteo"):
        return r["fonte"]
    if r.get("fonte") == "OpenAlex":
        return r.get("revista") or "artigo científico"
    host = urllib.parse.urlparse(r.get("url") or "").netloc
    return (host[4:] if host.startswith("www.") else host) or r.get("fonte") or ""


def bloco_para_ia(resultados: list) -> str:
    return "\n\n".join(f"[{i + 1}] {r['titulo']} — {r['url']}\n{r['texto']}" for i, r in enumerate(resultados))
