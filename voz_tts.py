"""
Voz do assistente Mondego: transforma a resposta em fala com as vozes da Google (modelos TTS do Gemini).

- Usa a API REST diretamente (não depende da versão instalada do pacote google-genai).
- A chave vai sempre no cabeçalho «x-goog-api-key», nunca no endereço.
- Tenta primeiro os modelos TTS atuais e depois os anteriores; lembra-se do que funcionou.
- Devolve sempre um ficheiro WAV completo (24 kHz, mono, 16 bits), pronto a tocar no browser.
- Também ouve: transcreve a gravação do microfone (transcrever) com o modelo de transcrição da Google, com as palavras
  prováveis (cadeiras, avaliações...) e, se esse modelo não der, com um modelo de texto que ouve o áudio com o contexto.
Não depende do Streamlit (é testado em testes_voz.py).
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELOS_TTS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
               "gemini-2.5-flash-preview-tts"]

# O Mondego fala sempre com a voz masculina «Charon» da Google (calma e clara, de explicador).
VOZ_POR_OMISSAO = "Charon"
VOZ_BROWSER = "browser"  # só quando a voz da Google não está disponível (sem chave do Gemini ou falha do serviço)

_memoria = {"modelo": None, "forma": None}


class ErroVoz(Exception):
    def __init__(self, mensagem: str, codigo: int | None = None):
        super().__init__(mensagem)
        self.codigo = codigo


def _pedido(metodo: str, caminho: str, chave: str, corpo: dict | None = None, tempo: int = 45) -> dict:
    if not chave:
        raise ErroVoz("Falta a chave do Gemini.", 401)
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(BASE + caminho, data=dados, method=metodo,
                                    headers={"x-goog-api-key": chave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo) as resposta:
            return json.loads(resposta.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as erro:
        try:
            detalhe = json.loads(erro.read().decode("utf-8", "replace")).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detalhe = ""
        raise ErroVoz(f"{erro.code} {detalhe}".strip()[:400], erro.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroVoz(f"Sem ligação ao serviço de voz ({getattr(erro, 'reason', erro)}).") from None


# --------------------------------------------------------------------------------------------- texto → fala
_LATEX = [(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1 sobre \2"), (r"\\sqrt\{([^{}]*)\}", r"raiz quadrada de \1"),
          (r"\^\{?2\}?", " ao quadrado"), (r"\^\{?3\}?", " ao cubo"), (r"\^\{([^{}]*)\}", r" elevado a \1"),
          (r"\^(-?\w+)", r" elevado a \1"), (r"_\{([^{}]*)\}", r" \1"), (r"\\cdot|\\times", " vezes "),
          (r"\\pi", " pi "), (r"\\infty", " infinito "), (r"\\to|\\rightarrow", " tende para "),
          (r"\\int", " integral de "), (r"\\sum", " soma de "), (r"\\lim", " limite "), (r"\\le(q)?", " menor ou igual a "),
          (r"\\ge(q)?", " maior ou igual a "), (r"\\neq", " diferente de "), (r"\\approx", " aproximadamente "),
          (r"\\Delta", " delta "), (r"\\alpha", " alfa "), (r"\\beta", " beta "), (r"\\theta", " teta "),
          (r"\\lambda", " lambda "), (r"\\mu", " miú "), (r"\\sigma", " sigma "), (r"\\omega", " ómega ")]


def texto_para_fala(texto: str) -> str:
    """Limpa o texto para ser lido em voz alta: sem markdown, links, emojis nem LaTeX (passa a palavras)."""
    t = str(texto or "")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)            # [texto](link) → texto
    t = re.sub(r"https?://\S+", "", t)

    def formula(m):
        f = m.group(1)
        for padrao, troca in _LATEX:
            f = re.sub(padrao, troca, f)
        return re.sub(r"[{}\\$]", " ", f).replace("=", " igual a ").replace("+", " mais ").replace(" - ", " menos ")

    t = re.sub(r"\$\$([^$]+)\$\$", formula, t)
    t = re.sub(r"\$([^$]+)\$", formula, t)
    t = re.sub(r"\\\((.+?)\\\)", formula, t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)        # títulos
    t = re.sub(r"^\s*[-*•]\s+", "", t, flags=re.M)             # itens de lista
    t = re.sub(r"[*_`>|#]", "", t)
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", "", t)  # emojis
    t = re.sub(r"\s*\n\s*", ". ", t.strip())
    t = re.sub(r"\.\s*\.", ".", t)
    return re.sub(r"\s{2,}", " ", t).strip()


# --------------------------------------------------------------------------------------------- áudio
def para_wav(dados: bytes, mime: str = "") -> bytes:
    """Os modelos novos devolvem um WAV completo; os antigos devolvem PCM 16 bits sem cabeçalho."""
    if dados[:4] == b"RIFF":
        return dados
    m = re.search(r"rate=(\d+)", mime or "")
    taxa = int(m.group(1)) if m else 24000
    saida = io.BytesIO()
    with wave.open(saida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(dados)
    return saida.getvalue()


def duracao_wav(wav: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        return 0.0


def _formas(voz: str) -> list:
    """Duas maneiras de indicar a voz: a nova («voice») e a antiga («prebuiltVoiceConfig»)."""
    formas = [{"voiceConfig": {"voice": voz}}]
    if not voz.startswith("voice_") and "/" not in voz:
        formas.append({"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}})
    if _memoria["forma"] == "antiga":
        formas.reverse()
    return formas


def sintetizar(chave: str, texto: str, voz: str = VOZ_POR_OMISSAO, modelos: list | None = None) -> tuple[bytes, str]:
    """Texto → (WAV, modelo usado). Lança ErroVoz se nenhum modelo funcionar."""
    texto = texto_para_fala(texto)[:3000]
    if not texto:
        raise ErroVoz("Não há texto para dizer.")
    lista = list(modelos or MODELOS_TTS)
    if _memoria["modelo"] in lista:
        lista.remove(_memoria["modelo"])
        lista.insert(0, _memoria["modelo"])
    ultimo = None
    for modelo in lista:
        formas = _formas(voz)
        for i, forma in enumerate(formas):
            corpo = {"contents": [{"role": "user", "parts": [{"text": texto}]}],
                     "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": forma}}
            try:
                r = _pedido("POST", f"/models/{urllib.parse.quote(modelo)}:generateContent", chave, corpo)
            except ErroVoz as erro:
                ultimo = erro
                if erro.codigo == 401 or "api key" in str(erro).lower():
                    raise                                   # chave inválida: não vale a pena tentar mais
                if erro.codigo == 400 and i < len(formas) - 1:
                    continue                                # forma de indicar a voz não aceite: tenta a outra
                break                                       # 404 (modelo inexistente), 429 (limite)...: próximo modelo
            try:
                parte = next(p for p in r["candidates"][0]["content"]["parts"] if "inlineData" in p or "inline_data" in p)
                dados = parte.get("inlineData") or parte.get("inline_data")
                wav = para_wav(base64.b64decode(dados["data"]), dados.get("mimeType") or dados.get("mime_type") or "")
            except (KeyError, IndexError, StopIteration, TypeError, ValueError):
                ultimo = ErroVoz("O serviço de voz respondeu sem áudio.")
                continue
            _memoria["modelo"] = modelo
            _memoria["forma"] = "nova" if "voice" in forma["voiceConfig"] else "antiga"
            return wav, modelo
    raise ultimo or ErroVoz("Nenhum modelo de voz disponível.")


# --------------------------------------------------------------------------------------------- fala → texto (ouvir)
MODELOS_TRANSCRICAO = ["gemini-3.5-transcribe"]
_memoria_ouvir = {"modelo": None}


def e_wav(dados: bytes) -> bool:
    return isinstance(dados, (bytes, bytearray)) and len(dados) > 44 and dados[:4] == b"RIFF" and dados[8:12] == b"WAVE"


def limpar_transcricao(texto: str) -> str:
    """Tira o que não foi dito: «Transcrição:», marcas como [ruído] ou (silêncio), aspas à volta e espaços a mais."""
    t = re.sub(r"^\s*(transcri[çc][aã]o|transcript(ion)?)\s*:\s*", "", str(texto or ""), flags=re.I)
    t = re.sub(r"\[[^\]\n]{1,40}\]|<[^>\n]{1,40}>|\((sil[eê]ncio|ru[ií]do|inaud[ií]vel|m[uú]sica|risos?|silence|noise|"
               r"inaudible|music|laughs?)\)", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip().strip('"\'«»“”').strip()
    return t[:1500]


def _texto_da_interacao(r: dict) -> str:
    """Resposta das Interactions: o texto está nos passos «model_output» (steps[].content[].text)."""
    partes = []
    for passo in r.get("steps") or []:
        if isinstance(passo, dict) and passo.get("type", "model_output") == "model_output":
            partes += [c.get("text", "") for c in passo.get("content") or []
                       if isinstance(c, dict) and c.get("type", "text") == "text"]
    if not partes:  # outra forma possível da resposta
        partes = [c.get("text", "") for c in r.get("outputs") or [] if isinstance(c, dict)]
    return " ".join(p.strip() for p in partes if isinstance(p, str) and p.strip())


def _texto_do_conteudo(r: dict) -> str:
    """Resposta do generateContent: as partes de texto do primeiro candidato (sem os pensamentos)."""
    try:
        partes = r["candidates"][0]["content"].get("parts") or []
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""
    return " ".join(p["text"].strip() for p in partes if isinstance(p, dict) and isinstance(p.get("text"), str)
                    and not p.get("thought"))


def _ouvir_com_transcricao(chave: str, modelo: str, b64: str, lingua: str, vocabulario: list, tempo: int) -> str:
    """Modelo de transcrição (Interactions): modo «smart» (tira hesitações e pontua), na língua da app e com as palavras
    prováveis. Se o pedido completo for recusado (400), tenta só com a língua. Não fica guardado na Google (store)."""
    config = {"mode": "smart", "language_codes": [lingua]}
    if vocabulario:
        config["custom_vocabulary"] = vocabulario[:100]
    corpos = [{"model": modelo, "input": [{"type": "audio", "data": b64, "mime_type": "audio/wav"}],
               "generation_config": {"transcription_config": config}, "store": False},
              {"model": modelo, "input": [{"type": "audio", "data": b64, "mime_type": "audio/wav"}],
               "generation_config": {"transcription_config": {"language_codes": [lingua]}}}]
    for i, corpo in enumerate(corpos):
        try:
            return _texto_da_interacao(_pedido("POST", "/interactions", chave, corpo, tempo))
        except ErroVoz as erro:
            if erro.codigo == 400 and i == 0 and "api key" not in str(erro).lower():
                continue
            raise
    return ""


def _ouvir_com_modelo_de_texto(chave: str, modelo: str, b64: str, lingua: str, vocabulario: list, contexto: str,
                               rascunho: str, tempo: int) -> str:
    """Um modelo normal ouve o áudio e escreve o que foi dito, com a conversa recente para perceber palavras ambíguas."""
    ingles = lingua.lower().startswith("en")
    if ingles:
        pedido = ("Transcribe word for word what the person says in this audio (English). They are a student talking to "
                  "a study assistant. Do NOT answer or comment: return only the spoken words, with punctuation. If "
                  "there is no intelligible speech, return an empty line.")
        if vocabulario:
            pedido += "\nWords that may come up (spell them like this): " + ", ".join(vocabulario[:60]) + "."
        if contexto:
            pedido += "\nConversation so far (to resolve ambiguous words):\n" + contexto[-1500:]
        if rascunho:
            pedido += "\nThe browser's speech recognition heard (it may be wrong): «" + rascunho[:500] + "»"
    else:
        pedido = ("Transcreve palavra a palavra o que a pessoa diz neste áudio (português de Portugal). É um estudante a "
                  "falar com um assistente de estudo. NÃO respondas nem comentes: devolve só as palavras ditas, com "
                  "pontuação e a ortografia de Portugal. Se não houver fala percetível, devolve uma linha vazia.")
        if vocabulario:
            pedido += "\nPalavras que podem aparecer (escreve-as assim): " + ", ".join(vocabulario[:60]) + "."
        if contexto:
            pedido += "\nConversa até agora (para perceber palavras ambíguas):\n" + contexto[-1500:]
        if rascunho:
            pedido += "\nO reconhecimento de voz do browser ouviu (pode estar errado): «" + rascunho[:500] + "»"
    base = {"contents": [{"role": "user", "parts": [{"text": pedido}, {"inlineData": {"mimeType": "audio/wav", "data": b64}}]}]}
    pensar = {"thinkingBudget": 0} if modelo.startswith("gemini-2") else {"thinkingLevel": "low"}
    corpos = [{**base, "generationConfig": {"temperature": 0, "thinkingConfig": pensar}},
              {**base, "generationConfig": {"temperature": 0}}]
    caminho = f"/models/{urllib.parse.quote(modelo)}:generateContent"
    for i, corpo in enumerate(corpos):
        try:
            return _texto_do_conteudo(_pedido("POST", caminho, chave, corpo, tempo))
        except ErroVoz as erro:
            if erro.codigo == 400 and i == 0 and "api key" not in str(erro).lower():
                continue                                    # a opção de pensar menos não é aceite: sem ela
            raise
    return ""


def transcrever(chave: str, wav: bytes, lingua: str = "pt-PT", vocabulario: list | None = None, contexto: str = "",
                rascunho: str = "", modelos_texto: list | None = None, limite: float = 20.0) -> tuple[str, str]:
    """Gravação (WAV) → (texto dito, modelo usado). Primeiro o modelo de transcrição da Google; se não existir ou falhar,
    um modelo de texto que ouve o áudio. Lança ErroVoz se nenhum der (a app usa então o que o browser ouviu)."""
    if not e_wav(wav):
        raise ErroVoz("A gravação não é um WAV.")
    b64 = base64.b64encode(bytes(wav)).decode("ascii")
    vocabulario = [str(v).strip()[:60] for v in (vocabulario or []) if str(v).strip()]
    tentativas = [("transcricao", m) for m in MODELOS_TRANSCRICAO] + [("texto", m) for m in (modelos_texto or [])[:3]]
    if _memoria_ouvir["modelo"] in [m for _, m in tentativas]:
        tentativas.sort(key=lambda x: x[1] != _memoria_ouvir["modelo"])  # o que funcionou da última vez primeiro
    inicio, ultimo = time.monotonic(), None
    for tipo, modelo in tentativas:
        resta = limite - (time.monotonic() - inicio)
        if resta < 3:
            break                                           # já se esperou demais: fica o que o browser ouviu
        try:
            if tipo == "transcricao":
                texto = _ouvir_com_transcricao(chave, modelo, b64, lingua, vocabulario, int(min(15, resta)))
            else:
                texto = _ouvir_com_modelo_de_texto(chave, modelo, b64, lingua, vocabulario, contexto, rascunho,
                                                   int(min(15, resta)))
        except ErroVoz as erro:
            ultimo = erro
            if erro.codigo == 401 or "api key" in str(erro).lower():
                raise                                       # chave inválida: não vale a pena tentar mais
            continue                                        # 403/404 (modelo sem acesso), 429 (limite), sem ligação...
        texto = limpar_transcricao(texto)
        if not texto and rascunho.strip():                  # não ouviu nada mas o browser ouviu: pede outra opinião
            ultimo = ErroVoz("A transcrição veio vazia.")
            continue
        _memoria_ouvir["modelo"] = modelo
        return texto, modelo
    raise ultimo or ErroVoz("Não foi possível transcrever a gravação.")
