"""Testes da voz do assistente (py -3.14 testes_voz.py). Não usam a internet: o serviço da Google é simulado."""
import base64
import io
import json
import wave

import voz_tts as vt

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


# --------------------------------------------------------------------------------- texto → fala
f = vt.texto_para_fala("## Derivada\n- A **derivada** de $x^2$ é $2x$.\n- Vê [isto](https://x.pt) 😀\n$$\\frac{a}{b}$$")
ok("Fala sem markdown, listas, links nem emojis", "#" not in f and "*" not in f and "http" not in f and "😀" not in f
   and "isto" in f)
ok("Fórmulas passam a palavras (x ao quadrado, a sobre b)", "x ao quadrado" in f and "a sobre b" in f and "$" not in f)
ok("Texto vazio", vt.texto_para_fala("") == "" and vt.texto_para_fala(None) == "")

# --------------------------------------------------------------------------------- WAV
pcm = b"\x00\x01" * 2400
w = vt.para_wav(pcm, "audio/L16;codec=pcm;rate=24000")
with wave.open(io.BytesIO(w)) as ww:
    ok("PCM sem cabeçalho passa a WAV 24 kHz, mono, 16 bits", w[:4] == b"RIFF" and ww.getframerate() == 24000
       and ww.getnchannels() == 1 and ww.getsampwidth() == 2)
ok("WAV completo fica igual", vt.para_wav(w) == w)
ok("Duração do WAV", abs(vt.duracao_wav(w) - 0.1) < 0.01)

# --------------------------------------------------------------------------------- síntese (serviço simulado)
PEDIDOS = []


def falso(respostas):
    def _pedido(metodo, caminho, chave, corpo=None, tempo=45):
        PEDIDOS.append((metodo, caminho, chave, corpo))
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    return _pedido


audio_ok = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000",
                                                                    "data": base64.b64encode(pcm).decode()}}]}}]}
vt._memoria.update(modelo=None, forma=None)
vt._pedido = falso([vt.ErroVoz("404 model not found", 404), audio_ok])
wav, modelo = vt.sintetizar("CHAVE", "Olá, sou o **Mondego**.", "Charon")
ok("Modelo inexistente (404): passa ao seguinte e devolve WAV", wav[:4] == b"RIFF" and modelo == vt.MODELOS_TTS[1])
ok("A chave vai no cabeçalho, nunca no endereço", all("CHAVE" not in p[1] for p in PEDIDOS) and PEDIDOS[0][2] == "CHAVE")
ok("O texto enviado já vem limpo para ser falado", PEDIDOS[-1][3]["contents"][0]["parts"][0]["text"] == "Olá, sou o Mondego.")
ok("Pede só áudio, com a voz escolhida", PEDIDOS[-1][3]["generationConfig"]["responseModalities"] == ["AUDIO"]
   and json.dumps(PEDIDOS[-1][3]["generationConfig"]["speechConfig"]).count("Charon") == 1)

PEDIDOS.clear()
vt._pedido = falso([audio_ok])
vt.sintetizar("CHAVE", "Outra vez.", "Charon")
ok("Lembra-se do modelo que funcionou (começa por ele)", vt.MODELOS_TTS[1] in PEDIDOS[0][1] and len(PEDIDOS) == 1)

PEDIDOS.clear()
vt._memoria.update(modelo=None, forma=None)
vt._pedido = falso([vt.ErroVoz("400 Invalid JSON payload: unknown field voice", 400), audio_ok])
vt.sintetizar("CHAVE", "Teste.", "Orus")
ok("Forma nova da voz recusada (400): tenta a forma antiga (prebuiltVoiceConfig) no mesmo modelo",
   "prebuiltVoiceConfig" in json.dumps(PEDIDOS[1][3]) and PEDIDOS[0][1] == PEDIDOS[1][1] and vt._memoria["forma"] == "antiga")

vt._pedido = falso([vt.ErroVoz("400 API key not valid", 400)])
try:
    vt.sintetizar("MÁ", "Teste.", "Charon")
    ok("Chave inválida dá erro logo (sem tentar todos os modelos)", False)
except vt.ErroVoz as e:
    ok("Chave inválida dá erro logo (sem tentar todos os modelos)", "API key" in str(e))

vt._pedido = falso([vt.ErroVoz("404", 404)] * 8)
try:
    vt.sintetizar("CHAVE", "Teste.", "voice_abc123")
    ok("Sem modelos disponíveis: erro claro", False)
except vt.ErroVoz:
    ok("Sem modelos disponíveis: erro claro", True)

# --------------------------------------------------------------------------------- ouvir: gravação → texto (serviço simulado)
gravacao = vt.para_wav(b"\x10\x00" * 16000, "audio/L16;rate=16000")
inter_ok = {"id": "interactions/x", "status": "completed",
            "steps": [{"id": "s1", "type": "model_output", "content": [{"type": "text", "text": "Explica o teorema de Laplace."}]}]}
texto_ok = {"candidates": [{"content": {"parts": [{"text": "pensamento", "thought": True},
                                                    {"text": "Transcrição: «Explica o teorema de Laplace.»"}]}}]}
VOC = ["Álgebra Linear", "Laplace", "Mondego"]
PEDIDOS.clear(); vt._memoria_ouvir["modelo"] = None
vt._pedido = falso([inter_ok])
txt, m = vt.transcrever("CHAVE", gravacao, "pt-PT", VOC, rascunho="explica o teorema de la place")
c = PEDIDOS[0][3]
ok("Ouvir: usa o modelo de transcrição da Google (Interactions), com o áudio WAV inline", PEDIDOS[0][1] == "/interactions"
   and c["model"] == vt.MODELOS_TRANSCRICAO[0] and c["input"][0]["type"] == "audio" and c["input"][0]["mime_type"] == "audio/wav"
   and base64.b64decode(c["input"][0]["data"]) == gravacao and txt == "Explica o teorema de Laplace." and m == vt.MODELOS_TRANSCRICAO[0])
tc = c["generation_config"]["transcription_config"]
ok("Ouvir: modo «smart», português de Portugal e as palavras prováveis (cadeiras...); não fica guardado na Google",
   tc["mode"] == "smart" and tc["language_codes"] == ["pt-PT"] and tc["custom_vocabulary"] == VOC and c["store"] is False)
ok("Ouvir: a chave vai no cabeçalho, nunca no endereço", all("CHAVE" not in p[1] for p in PEDIDOS) and PEDIDOS[0][2] == "CHAVE")

PEDIDOS.clear(); vt._memoria_ouvir["modelo"] = None
vt._pedido = falso([vt.ErroVoz("400 unknown field custom_vocabulary", 400), inter_ok])
txt, m = vt.transcrever("CHAVE", gravacao, "en-GB", VOC)
ok("Ouvir: pedido completo recusado (400): repete só com a língua", txt.startswith("Explica") and len(PEDIDOS) == 2
   and PEDIDOS[1][3]["generation_config"]["transcription_config"] == {"language_codes": ["en-GB"]})

PEDIDOS.clear(); vt._memoria_ouvir["modelo"] = None
vt._pedido = falso([vt.ErroVoz("404 model not found", 404), texto_ok])
txt, m = vt.transcrever("CHAVE", gravacao, "pt-PT", VOC, contexto="Aluno: o que é um determinante?",
                        rascunho="explica o teorema de la place", modelos_texto=["gemini-x-lite", "gemini-y"])
pedido = PEDIDOS[1][3]["contents"][0]["parts"]
ok("Ouvir: sem o modelo de transcrição (404), um modelo de texto ouve o áudio com a conversa e o que o browser ouviu",
   PEDIDOS[1][1] == "/models/gemini-x-lite:generateContent" and pedido[1]["inlineData"]["mimeType"] == "audio/wav"
   and "NÃO respondas" in pedido[0]["text"] and "determinante" in pedido[0]["text"] and "la place" in pedido[0]["text"]
   and "Laplace" in pedido[0]["text"] and m == "gemini-x-lite")
ok("Ouvir: tira «Transcrição:», as aspas e os pensamentos do modelo", txt == "Explica o teorema de Laplace.")
PEDIDOS.clear()
vt._pedido = falso([texto_ok])
vt.transcrever("CHAVE", gravacao, modelos_texto=["gemini-x-lite"])
ok("Ouvir: lembra-se do modelo que funcionou (começa por ele)", PEDIDOS[0][1] == "/models/gemini-x-lite:generateContent")

PEDIDOS.clear(); vt._memoria_ouvir["modelo"] = None
vt._pedido = falso([{"steps": [{"type": "model_output", "content": [{"type": "text", "text": " "}]}]}, texto_ok])
txt, m = vt.transcrever("CHAVE", gravacao, rascunho="explica", modelos_texto=["gemini-x-lite"])
ok("Ouvir: transcrição vazia mas o browser ouviu algo → pede outra opinião ao modelo de texto", m == "gemini-x-lite" and txt)
vt._pedido = falso([{"steps": []}])
vt._memoria_ouvir["modelo"] = None
ok("Ouvir: silêncio (nada ouvido por ninguém) → texto vazio, sem erro", vt.transcrever("CHAVE", gravacao)[0] == "")

vt._pedido = falso([vt.ErroVoz("400 API key not valid", 400)])
try:
    vt.transcrever("MÁ", gravacao, modelos_texto=["gemini-x-lite"]); ok("Ouvir: chave inválida dá erro logo", False)
except vt.ErroVoz as e:
    ok("Ouvir: chave inválida dá erro logo", "API key" in str(e))
vt._pedido = falso([vt.ErroVoz("Sem ligação", None)] * 4)
try:
    vt.transcrever("CHAVE", gravacao, modelos_texto=["gemini-x-lite"]); ok("Ouvir: sem ligação → erro (a app usa o browser)", False)
except vt.ErroVoz:
    ok("Ouvir: sem ligação → erro (a app usa o browser)", True)
try:
    vt.transcrever("CHAVE", b"isto nao e audio"); ok("Ouvir: recusa o que não é WAV", False)
except vt.ErroVoz:
    ok("Ouvir: recusa o que não é WAV", True)
ok("Ouvir: limpa marcas que não foram ditas", vt.limpar_transcricao("[ruído] Qual é a matéria (silêncio) do teste?")
   == "Qual é a matéria do teste?")

ok("A voz do Mondego é sempre a Charon (masculina)", vt.VOZ_POR_OMISSAO == "Charon")
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
