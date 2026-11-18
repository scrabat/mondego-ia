"""
Mondego IA (antes «Estuda Comigo») — versão 5
Assistente de estudo com uma interface de chat simples e limpa.
Os alunos carregam as sabentas e apontamentos e a IA usa-os como fonte para
conversar, resumir, criar slides, quizzes, testes, flashcards e planos de estudo.

IA por defeito: Google Gemini (plano gratuito). Também suporta Claude (pago).
Os dados ficam na pasta "dados" e no ficheiro "perfil.json", ao lado deste ficheiro.

Executar:  py -3.14 -m streamlit run app.py
"""

import base64
import csv
import io
import itertools
import random
import zipfile
from contextlib import contextmanager, nullcontext
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
import streamlit as st
from docx import Document
from pptx import Presentation
from pptx.util import Pt

import academico as ac
import avaliacoes as av
import estudio3d as e3
import identidade as idt
import laboratorio as lab
import matematica as mt
import repeticao as rs
import voz_tts as vt
import salas as _salas_mod
import salas_backend as _salas_backend_mod
import motor_blender as mb
import plano_estudo as pe
import pesquisa_web as pw
import historico as hc
import inicio_sessao as isess
import desempenho as dz
import exercicios as ex
import lab_historia as lh
import lab_biologia as lb
import definicoes as dfs


def _recarregar_se_mudou(*modulos) -> None:
    """O Streamlit só recarrega o app.py quando muda; os outros ficheiros ficavam com a versão antiga em memória
    até se reiniciar a app (ex.: um tema ou animação nova em identidade.py dava erro). Assim recarregam sozinhos."""
    import importlib
    for mod in modulos:
        try:
            alterado = Path(mod.__file__).stat().st_mtime
        except OSError:
            continue
        if getattr(mod, "_carregado_em", None) != alterado:  # reload altera o próprio módulo (idt, mt... continuam válidos)
            importlib.reload(mod)._carregado_em = alterado


_recarregar_se_mudou(idt, mt, rs, ac, e3, lab, vt, mb, pe, pw, hc, isess, dz, ex, lh, lb, _salas_mod, _salas_backend_mod, dfs)

# =============================================================== constantes
PASTA = Path(__file__).parent
PASTA_DADOS = PASTA / "dados"
FICHEIRO_CONFIG = PASTA / "config.json"
FICHEIRO_PERFIL = PASTA / "perfil.json"
FICHEIRO_AVALIACOES = PASTA / "avaliacoes.json"   # fonte única de todas as provas (ver avaliacoes.py)
PASTA_BACKUP = PASTA / "backup"
ICONE_PNG = PASTA / "icone.png"
ICONE_SVG = idt.simbolo_svg()   # torre + rio; as cores seguem o tema ativo
TIPOS_IMAGEM = ["png", "jpg", "jpeg", "webp"]
TIPOS_FICHEIRO = ["pdf", "pptx", "docx", "txt", "md"] + TIPOS_IMAGEM
MODELO_CLAUDE = "claude-sonnet-4-5"
TAMANHO_BLOCO = 3_000
TIPOS = av.TIPOS
DIFICULDADES = ["Fácil", "Média", "Difícil"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Velocidade: quanto texto se envia em cada pedido e quanto a IA "pensa" antes de responder.
VELOCIDADES = {
    "Rápida": {"caracteres": 120_000, "descricao": "Respostas em poucos segundos"},
    "Equilibrada": {"caracteres": 220_000, "descricao": "Um pouco mais lenta, mais completa"},
    "Máxima qualidade": {"caracteres": 300_000, "descricao": "A mais lenta, pensa mais"},
}

# ---------------------------------------------------------------- instruções da IA
# Os prompts originais ficam como estavam; acrescentam-se blocos partilhados com o estilo de resposta (direto,
# proporcional, honesto, formatação só quando ajuda), o uso do contexto do aluno e o guia da app.
FORMATO_EXATO = (" Quando um pedido disser «Responde só com JSON» (ou indicar outro formato exato), segues esse formato "
                 "à letra e as regras de estilo não se aplicam. Nunca inventas citações, páginas, slides, sites, datas ou números.")
EXCECAO_NUMEROS = (" Exceção: datas, horas, preços, temperaturas e outros números do dia a dia (notícias, tempo, lançamentos) "
                   "escrevem-se em texto normal, sem LaTeX (ex.: 2 de novembro, 23 °C, 0 %).")
ESTILO_RESPOSTA = """

COMO RESPONDES
- Começa pela resposta: a primeira frase responde à pergunta; o resto aprofunda, passo a passo e com exemplos.
- Sem preâmbulos nem enchimento: não elogies a pergunta, não a repitas, não anuncies o que vais fazer («Vou explicar…») e \
não acabes com «Espero ter ajudado», «Se precisares de mais alguma coisa, diz!» nem com um resumo do que acabaste de dizer.
- O tamanho acompanha a pergunta: pergunta simples (definição, facto, sim/não) → uma a três frases; explicação de matéria → \
o essencial primeiro, depois o desenvolvimento e um exemplo, e paras quando a dúvida está resolvida; tarefa complexa \
(exercício com várias alíneas, resumo de um capítulo, plano) → completa e organizada por partes.
- Vai ao objetivo real: se pede para resolver, resolves com todos os passos; se mostra uma tentativa, verificas primeiro e \
apontas o erro exato; se diz que não percebe, explicas a intuição antes do formalismo; se está a preparar uma avaliação, \
focas-te no que costuma sair.
- Se o pedido for ambíguo, respondes à interpretação mais provável e, só se for mesmo preciso, fazes no fim uma única pergunta.

TOM E HONESTIDADE
- Caloroso, calmo e respeitoso, sem bajulação: elogias só trabalho concreto, quando é merecido. Tratas o aluno por tu.
- Se o aluno estiver errado, dizes-lho com clareza e simpatia e mostras porquê. Se te enganares, reconheces e corriges, \
sem pedidos de desculpa exagerados.
- Dizes quando não tens a certeza e porquê, e distingues o que vem dos documentos, da web e do teu conhecimento geral.
- Se o aluno mostrar stress ou ansiedade com as avaliações, respondes com calor e de forma prática (um próximo passo \
concreto), sem dramatizar.
- Sem emojis, a não ser que o aluno os use.

FORMATAÇÃO
- Por defeito, prosa corrida em parágrafos curtos (conversas e explicações simples).
- Listas numeradas para passos ou ordem; listas com marcas para três ou mais itens paralelos; nada de listas para o que \
cabe numa frase.
- Títulos só em respostas longas com várias partes distintas; nunca numa resposta de um ou dois parágrafos.
- Negrito com moderação: termos-chave e o resultado final de um exercício.
- Tabelas só para comparar várias coisas em vários critérios; blocos de código só para código de programação, com a \
linguagem indicada.
- Deixa uma linha em branco antes de cada lista e depois de cada título."""
USO_DO_ALUNO = """

O CONTEXTO DO ALUNO
O bloco <aluno></aluno> traz a data de hoje, o nome, o perfil académico, as cadeiras com as próximas avaliações e as \
sessões de estudo do dia. Usa-o só quando muda a resposta (por exemplo, para dar prioridade à matéria do próximo exame \
quando o aluno pede ajuda para estudar). Não comeces as respostas com «Olá, [nome]!», usa o nome raramente e não \
acrescentes lembretes de avaliações nem ofertas de ajuda que ele não pediu."""
GUIA_APP = """

QUEM ÉS E A APLICAÇÃO
És o Assistente do Mondego IA (não és outro produto). Se te perguntarem que modelo de IA usas, dizes que funcionas com o \
modelo de IA escolhido por quem gere a app (Gemini ou Claude), sem inventar versões. Nunca fales de chaves de API.
Quando o aluno perguntar como fazer algo na app, indicas o caminho exato e nunca inventas funcionalidades nem botões:
- Início: próxima avaliação, foco de hoje, plano de hoje, flashcards para rever e cronómetro de estudo.
- Assistente: esta conversa («Nova conversa» na barra lateral); em «Mais» liga e desliga «Pesquisar na web». Em cada \
resposta há «Copiar» e «Gerar outra resposta»; cada pergunta pode ser editada.
- Cadeiras: em cada cadeira, a Conversa com os documentos e as ferramentas Resumo, Guia, Mapa, Quiz, Flashcards, Teste, \
Slides, Plano e Progresso.
- Calendário: avaliações e o plano de estudo com IA (criar, mudar ou apagar).
- Salas: estudar com colegas (materiais, assistente da sala, conversa). Quem cria a sala pode ativar o Laboratório \
(Criar sala → «Ativar Laboratório nesta sala»): História (explicar, analisar documentos, cronologias, comparar, testes, \
resumos, mapas), Biologia (processos, genética, experiências, gráficos e dados, testes, glossário, simulações), Química, \
Física, Matemática e Programação. Não há uma página «Laboratório» fora das salas.
- Perfil: o perfil académico, as estatísticas e os teus dados (descarregar ou apagar a conta).
- Definições: velocidade das respostas, cor da aplicação e assistente (idioma e pesquisa na web).
Sugeres uma funcionalidade só quando serve o objetivo do aluno, numa frase e sem insistir (por exemplo, os Flashcards da \
cadeira para memorizar definições).

CONVERSAS NOVAS
Numa conversa nova, respondes logo ao pedido, sem te apresentares. Se o aluno só cumprimentar ou perguntar o que sabes \
fazer, respondes em duas ou três frases: explicas matéria com os documentos dele, resolves e corriges exercícios, ajudas a \
preparar avaliações e pesquisas na web quando essa opção está ligada; depois convida-lo a fazer a primeira pergunta."""
ESTILO_EN = (" Start with the answer, then go deeper; no preambles, no praise of the question and no generic closings "
             "(«Hope this helps», «Let me know if…»). Match the length to the question: one to three sentences for simple "
             "questions, organised parts for complex tasks. Prose by default; numbered lists for steps and bullets for three "
             "or more parallel items; headings only in long answers; bold sparingly; tables only for multi-criteria "
             "comparisons; code blocks only for programming code. Be warm, calm and honest, without flattery: correct "
             "mistakes clearly and kindly, say when you are unsure, and never invent citations, pages, websites, dates or "
             "numbers. Use the <aluno> block only when it changes the answer and don't greet the student by name in every "
             "answer. No emojis unless the student uses them. You are the Mondego IA Assistant; if asked which AI model you "
             "use, say it runs on the model chosen by whoever runs the app (Gemini or Claude). When asked for JSON or "
             "another exact format, follow it exactly.")

SISTEMA = (
    "És um tutor para estudantes universitários portugueses. "
    "Respondes sempre em português de Portugal (não uses português do Brasil). "
    "Usas APENAS a informação das fontes fornecidas entre <fontes></fontes>. "
    "Se algo não estiver nas fontes, dizes claramente que não está nos documentos. "
    "Sempre que possível indicas a origem, por exemplo (ficheiro.pdf, p. 3) ou (aula2.pptx, slide 5). "
    "Explicas de forma clara, com exemplos, como um bom explicador. " + mt.REGRAS_FORMULAS + FORMATO_EXATO
)
SISTEMA_CHAT = (
    "És um tutor simpático e paciente para estudantes universitários portugueses. "
    "Respondes sempre em português de Portugal (não uses português do Brasil). "
    "Dás prioridade à informação das fontes entre <fontes></fontes> e indicas a origem (ficheiro, página ou slide). "
    "Se a resposta não estiver nas fontes, podes usar o teu conhecimento geral, mas avisas: "
    "'(isto não vem dos teus documentos)'. Vais direto ao assunto, explicas passo a passo e com exemplos. "
    "Usa títulos e listas só quando ajudam. " + mt.REGRAS_FORMULAS + EXCECAO_NUMEROS + FORMATO_EXATO
    + ESTILO_RESPOSTA + USO_DO_ALUNO + GUIA_APP
)
# Com a pesquisa na web ligada, a base é outra: sem a regra «(isto não vem dos teus documentos)», que fazia a IA
# responder a perguntas da web (lançamentos, tempo, notícias) como se só pudesse usar os documentos.
SISTEMA_CHAT_WEB = (
    "És um tutor e assistente simpático para estudantes portugueses. "
    "Respondes sempre em português de Portugal (não uses português do Brasil). "
    "Vais direto ao assunto, explicas passo a passo e com exemplos. Usa títulos e listas só quando ajudam. "
    + mt.REGRAS_FORMULAS + EXCECAO_NUMEROS + FORMATO_EXATO + ESTILO_RESPOSTA + USO_DO_ALUNO + GUIA_APP
)

st.set_page_config(page_title=idt.NOME_APP, page_icon=str(ICONE_PNG) if ICONE_PNG.exists() else None,
                   layout="wide", initial_sidebar_state="auto")

# Telemóvel (ecrãs estreitos): o menu lateral é como o do Claude — desliza da esquerda e ocupa quase o ecrã, a página
# fica encostada à direita (esbatida, com cantos redondos) e tocar nela fecha o menu; linhas grandes, com ícone, as
# conversas recentes com o balão e «Nova conversa» numa pílula fixa no fundo. O botão do menu é redondo.
ESTILO_TELEMOVEL = """
<style>
@media (max-width: 640px) {
  [data-testid="stSidebar"][data-collapsed="false"] { width:86vw !important; min-width:86vw !important; max-width:86vw !important;
    box-shadow:none !important; }
  [data-testid="stSidebar"][data-collapsed="false"] [data-testid="stSidebarContent"] { background:var(--fundo) !important; }
  [data-testid="stMain"], [data-testid="stBottom"] { transition:transform .3s cubic-bezier(.2,.7,.2,1), border-radius .3s ease; }
  .stApp:has([data-testid="stSidebar"][data-collapsed="false"]) :is([data-testid="stMain"], [data-testid="stBottom"]) {
    transform:translateX(86vw); border-radius:28px; overflow:hidden; }
  .stApp:has([data-testid="stSidebar"][data-collapsed="false"]) [data-testid="stMain"]::after { content:""; position:absolute;
    inset:0; background:color-mix(in srgb, var(--fundo) 45%, transparent); pointer-events:none; z-index:50; }
  /* linhas do menu: grandes, para o dedo */
  [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-bottom:6rem !important; }
  [data-testid="stSidebar"] .stButton button { min-height:2.85rem !important; padding:0.45rem 0.75rem !important; gap:0.85rem !important;
    border-radius:12px !important; }
  [data-testid="stSidebar"] .stButton button p { font-size:1.06rem !important; }
  [data-testid="stSidebar"] .stButton button [data-testid="stIconMaterial"] { font-size:1.4rem !important; }
  .ec-secao { text-transform:none !important; letter-spacing:0 !important; font-size:0.95rem !important; font-weight:500 !important;
    margin:1.3rem 0 0.35rem 0.75rem !important; }
  [data-testid="stSidebar"] [class*="st-key-conv_"]:not(.st-key-conv_pesquisa):not(.st-key-conv_mais) button:not(:has([data-testid="stIconMaterial"]))::before {
    content:"chat_bubble"; font-family:'Material Symbols Rounded'; font-size:1.35rem; line-height:1; color:var(--suave);
    font-variation-settings:'FILL' 0; }
  /* «Nova conversa»: pílula escura fixa no fundo do menu, como «Nova sessão» no Claude */
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral { position:fixed !important; left:0 !important; right:auto !important;
    box-sizing:border-box !important; padding-right:calc(14vw + 1rem) !important; display:flex !important; justify-content:flex-end;
    bottom:calc(1.1rem + env(safe-area-inset-bottom)) !important; margin:0 !important; z-index:6; pointer-events:none; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton { pointer-events:auto; }
  [data-testid="stSidebar"][data-collapsed="true"] .st-key-nova_conversa_lateral { display:none !important; }
  [data-testid="stSidebar"][data-collapsed="false"]::after { content:""; position:fixed; left:0; bottom:0; width:86vw; height:6.5rem;
    background:linear-gradient(to bottom, transparent, var(--fundo) 55%); pointer-events:none; z-index:5; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton,
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton button[kind] { width:max-content !important; max-width:80vw; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton button[kind] { background:var(--texto) !important;
    border:none !important; border-radius:999px !important; padding:0.8rem 1.45rem !important; min-height:3.2rem !important;
    box-shadow:0 8px 24px rgba(0,0,0,.2) !important; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton button[kind] * { color:var(--fundo) !important; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral .stButton button[kind] p { font-weight:600 !important; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral button [data-testid="stIconMaterial"] { font-size:0 !important; }
  [data-testid="stSidebar"] .st-key-nova_conversa_lateral button [data-testid="stIconMaterial"]::before { content:"add"; font-size:1.4rem; }
  /* botão do menu: redondo, como no Claude */
  [data-testid="stExpandSidebarButton"] { border-radius:999px !important; width:2.9rem !important; height:2.9rem !important;
    box-shadow:0 2px 10px rgba(0,0,0,.08) !important; }
  /* conversa nova: a saudação ao meio, a caixa no fundo */
  .ec-saudacao.tlm { margin-top:24vh !important; font-size:1.85rem !important; }
  .ec-saudacao.tlm svg { height:42px !important; }
  [data-testid="stBottom"] .st-key-compositor { margin-bottom:0.2rem; }
}
</style>
"""


def e_telemovel() -> bool:
    """Telemóvel (pelo navegador do pedido). No telemóvel a app abre na conversa nova, com a caixa de escrever no fundo
    e o menu fechado, como no Claude; no computador fica tudo como está."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:  # noqa: BLE001
        return False
    return bool(re.search(r"iPhone|iPod|Android.+Mobile|Windows Phone|Mobile Safari", ua))


# =============================================================== estilo
ESTILO = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
/* as variáveis de cor (--fundo, --texto, --acento...) vêm de identidade.css_tema(): identidade «Mondego» (rio, tinta, papel) */
.stApp { background:var(--fundo); }
body, .stMarkdown p, .stMarkdown li, .stCaption, label p, input, textarea,
.stButton button p, .stDownloadButton button p { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family:'Material Symbols Rounded' !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, [data-testid="stMetricValue"],
.ec-titulo, .ec-saudacao, .ec-marca { font-family:'Inter', system-ui, sans-serif !important; color:var(--texto); }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { font-weight:650 !important; letter-spacing:-0.02em; }
/* escala de títulos (igual em todas as páginas) */
.stMarkdown h1 { font-size:var(--t-2xl) !important; } .stMarkdown h2 { font-size:var(--t-xl) !important; }
.stMarkdown h3 { font-size:var(--t-lg) !important; margin-top:1.1rem !important; } .stMarkdown h4 { font-size:var(--t-md) !important; }
.stMarkdown p, .stMarkdown li { line-height:1.6; }
::selection { background:color-mix(in srgb, var(--acento) 24%, transparent); }
.block-container { max-width:1100px; padding-top:1.4rem !important; padding-bottom:7rem; }
@media (min-width: 900px) { .block-container { padding-left:3rem !important; padding-right:3rem !important; } }
header[data-testid="stHeader"] { background:transparent; }
*:focus-visible { outline:2px solid var(--acento) !important; outline-offset:2px; }
/* nas caixas de escrita o foco já se vê na borda da caixa (anel do acento): sem segundo contorno por dentro */
.stApp :is(input, textarea):focus-visible { outline:none !important; }
/* sem regra de «reduzir movimento»: as animações da app mexem-se sempre (pedido do utilizador) */

/* ---------- barra lateral (recolhe-se no botão « do topo) ---------- */
[data-testid="stSidebar"] { background:var(--lateral); border-right:1px solid var(--linha); }
[data-testid="stSidebarUserContent"] { padding-top:0.4rem; }
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(> .stButton),
[data-testid="stSidebar"] .stButton { width:100% !important; max-width:100% !important; }
[data-testid="stSidebar"] .stButton button { justify-content:flex-start; text-align:left; width:100%;
        border-radius:var(--r-sm) !important; padding:0.3rem 0.62rem !important; min-height:2.05rem !important; gap:0.1rem;
        transition:background 0.12s ease; box-shadow:none !important; }
[data-testid="stSidebar"] .stButton button > div { min-width:0; flex:1 1 auto; justify-content:flex-start; }
/* nomes compridos (ex.: «introdução a programação») cortam com «…» em vez de empurrar o ícone para fora do sítio */
[data-testid="stSidebar"] .stButton button > div > span { justify-content:flex-start !important; min-width:0; max-width:100%; }
[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"] { min-width:0; overflow:hidden; }
[data-testid="stSidebar"] .stButton button [data-testid="stIconMaterial"] { flex:none; }
[data-testid="stSidebar"] .stButton button::after { flex:none; margin-left:0.4rem; font-size:0.72rem; font-weight:500;
        line-height:1.5; border-radius:999px; }
[data-testid="stSidebar"] .stButton button p { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:0.9rem; }
[data-testid="stSidebar"] .stButton button[kind="tertiary"] { color:var(--texto); font-weight:400; }
[data-testid="stSidebar"] .stButton button[kind="tertiary"]:hover { background:var(--bolha); }
[data-testid="stSidebar"] .stButton button[kind="secondary"] { background:var(--bolha) !important; border:none; font-weight:600; }
[data-testid="stSidebar"] .stButton button[kind="secondary"] p { color:var(--texto) !important; }
[data-testid="stSidebar"] .stButton button[kind="tertiary"] p { color:color-mix(in srgb, var(--texto) 88%, var(--suave)); }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:0.12rem; }
.st-key-nova_conversa_lateral button { background:var(--acento-claro) !important; border:none !important; font-weight:600 !important; }
.st-key-nova_conversa_lateral button * { color:var(--acento-esc) !important; }
.st-key-nova_conversa_lateral { margin:0.15rem 0 0.4rem 0; }
.st-key-conv_pesquisa input { font-size:0.88rem !important; }
.st-key-lateral_conta { margin-top:0.6rem; padding-top:0.55rem; border-top:1px solid var(--linha); }
.ec-marca { display:flex; align-items:center; gap:0.55rem; font-size:1.3rem; font-weight:650; margin:0 0 0.9rem 0.2rem; }
.ec-marca svg { width:30px; height:30px; flex-shrink:0; }
.ec-secao { display:block; font-size:0.72rem; line-height:1.3; color:var(--suave); margin:1rem 0 0.4rem 0.65rem; font-weight:600;
        letter-spacing:0.05em; text-transform:uppercase; }
/* o Streamlit puxa o elemento seguinte 1rem para cima (margem negativa); nos títulos de secção isso tapava o título */
[data-testid="stMarkdownContainer"]:has(> .ec-secao) { margin-bottom:0 !important; }

/* ---------- conversa ---------- */
.ec-saudacao { display:flex; align-items:center; justify-content:center; gap:0.85rem; margin:19vh 0 1.6rem 0;
        font-size:2.3rem; font-weight:600; letter-spacing:-0.03em; text-align:center; line-height:1.15; }
.ec-saudacao svg { height:54px; width:auto; flex-shrink:0; }
[data-testid="stChatInput"] { border-radius:22px !important; border:1px solid var(--borda-campo) !important;
        background:var(--cartao) !important; box-shadow:0 6px 24px var(--sombra); transition:border-color .15s, box-shadow .15s; }
[data-testid="stChatInput"]:focus-within { border-color:var(--acento) !important;
        box-shadow:0 0 0 3px color-mix(in srgb, var(--acento) 18%, transparent), 0 6px 24px var(--sombra); }
[data-testid="stChatInput"] textarea { font-size:1rem; line-height:1.5; }
[data-testid="stBottom"] > div { background:var(--fundo); }
[data-testid="stBottomBlockContainer"] { max-width:780px; padding-bottom:1.1rem; }
[data-testid="stChatMessage"] { background:transparent; padding:0.35rem 0; gap:0.75rem; animation:mi-entrar .22s ease-out; }
@keyframes mi-entrar { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background:var(--bolha); border-radius:18px; padding:0.6rem 1rem; margin-left:auto;
        width:fit-content; max-width:85%; }
[data-testid="stChatMessageAvatarUser"] { display:none; }
[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarUser"])) .stMarkdown :is(p, li) {
        font-size:1rem; line-height:1.72; color:var(--texto); }
[data-testid="stChatMessage"] .stMarkdown table { border-collapse:collapse; margin:0.6rem 0; font-size:0.93rem; }
[data-testid="stChatMessage"] .stMarkdown :is(th, td) { border:1px solid var(--linha); padding:0.4rem 0.7rem; }
[data-testid="stChatMessage"] .stMarkdown th { background:var(--bolha); font-weight:600; }
[data-testid="stChatMessage"] .stMarkdown blockquote { border-left:3px solid var(--acento); padding-left:0.9rem; color:var(--suave); }
[data-testid="stChatMessage"] pre { border-radius:12px !important; }
/* ações por baixo de cada mensagem (copiar, gerar outra, editar): discretas até se passar por cima */
.mi-acoes { display:flex; gap:0.2rem; margin-top:0.1rem; }
.mi-copiar { display:inline-flex; align-items:center; gap:0.3rem; cursor:pointer; user-select:none; color:var(--suave);
        font-size:0.8rem; padding:0.2rem 0.5rem; border-radius:8px; border:1px solid transparent; }
.mi-copiar:hover, .mi-copiar:focus-visible { background:var(--bolha); color:var(--texto); }
.mi-copiar .material-symbols-rounded { font-size:17px; }
.mi-copiar.ok { color:var(--acento); }
div[class*="st-key-msgacao_"] button { min-height:1.9rem !important; padding:0.15rem 0.5rem !important; color:var(--suave) !important; }
div[class*="st-key-msgacao_"] button:hover { background:var(--bolha) !important; color:var(--texto) !important; }
div[class*="st-key-msgacoes_"] { gap:0.2rem !important; }
/* mensagem do utilizador: o lápis de editar fica fora da bolha (à esquerda) e aparece ao passar o rato */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { position:relative; overflow:visible; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) :is([data-testid="stLayoutWrapper"], div.stVerticalBlock):has(> div[class*="st-key-msgacao_editar_"], > [data-testid="stElementContainer"] div[class*="st-key-msgacao_editar_"]),
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stLayoutWrapper"]:has(> div[class*="st-key-msgacoes_"] div[class*="st-key-msgacao_editar_"]) {
        position:absolute !important; right:calc(100% + 0.3rem); top:50%; transform:translateY(-50%); width:auto !important;
        margin:0 !important; opacity:0; transition:opacity var(--rapido) var(--curva); }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]):is(:hover, :focus-within) [data-testid="stLayoutWrapper"]:has(div[class*="st-key-msgacao_editar_"]) {
        opacity:1; }
@media (hover:none) {
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stLayoutWrapper"]:has(div[class*="st-key-msgacao_editar_"]) { opacity:1; }
}
.st-key-chips [data-testid="stButtonGroup"] button, .st-key-chips button {
        border-radius:999px !important; background:var(--cartao); border:1px solid var(--linha); }
.st-key-compositor [data-testid="stChatInput"] { min-height:3.6rem; }
.ec-pergunta-titulo { font-size:1.45rem; font-weight:600; color:var(--texto); margin:0.2rem 0 0.6rem; }
.ec-contexto { display:inline-block; background:var(--acento-claro); color:var(--acento-esc); border-radius:999px;
        padding:0.15rem 0.75rem; font-size:0.8rem; font-weight:500; }
.ec-titulo-conversa { font-family:'Inter', sans-serif; font-weight:600; color:var(--texto); font-size:1rem;
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ec-titulo-conversa .ec-fixa { font-size:1rem; color:var(--suave); vertical-align:-0.15em; margin-left:0.25rem; }
.mi-vazio { text-align:center; padding:2.2rem 1rem; color:var(--suave); }
.mi-vazio b { display:block; color:var(--texto); font-size:1.05rem; margin-bottom:0.3rem; }

/* ---------- cartões, botões, separadores ---------- */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; }
[data-testid="stForm"] { border-radius:16px; border:1px solid var(--linha); background:var(--cartao); }
[data-testid="stForm"]:has([class*="st-key-avl1_"]) { border:none !important; background:transparent !important; padding:0;
        border-radius:0; }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button { border-radius:10px; font-weight:500;
        transition:background .12s ease, border-color .12s ease; }
[data-testid="stMetric"] { background:var(--fundo); border-radius:12px; padding:0.5rem 0.75rem; }
[data-testid="stMetricValue"] { font-size:1.5rem; font-weight:650; }
[data-testid="stMetricDelta"] { white-space:normal; }
[data-testid="stAlert"] { border-radius:12px; }
[data-testid="stExpander"] details { border-radius:12px; background:var(--cartao); }
[data-testid="stSegmentedControl"] { overflow-x:auto; }

/* ---------- cabeçalhos de página: título, descrição e ações à direita (igual em todas as páginas) ---------- */
.pg-cab { margin:0.1rem 0 0.35rem; }
.pg-cab [data-testid="stHeaderActionElements"] { display:none !important; }
.ec-titulo { font-size:var(--t-2xl); font-weight:650; letter-spacing:-0.028em; line-height:1.15; margin:0 !important;
        overflow-wrap:anywhere; color:var(--texto); }
.ec-subtitulo { color:var(--suave) !important; margin:0.3rem 0 0 0 !important; font-size:var(--t-base); line-height:1.5; }
.ec-etiquetas { display:flex; flex-wrap:wrap; gap:0.35rem; margin-top:0.55rem; }
/* títulos de secção dentro das páginas */
.mi-sec { display:flex; align-items:baseline; justify-content:space-between; gap:0.8rem; margin:0.4rem 0 0.1rem; }
.mi-sec b { font-size:var(--t-md); font-weight:600; color:var(--texto); letter-spacing:-0.01em; }
.mi-sec span { font-size:var(--t-sm); color:var(--suave); }
[data-testid="stMarkdownContainer"]:has(> .mi-sec, > .pg-cab, > .ec-cab, > .mi-avs, > .mi-avatar-g) { margin-bottom:0 !important; }

/* ---------- números do dia (Início, Cadeiras, Cadeira, Perfil) ---------- */
.mi-dia { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:var(--e-3); margin:0.2rem 0 0.4rem; }
.mi-dia-c { background:var(--cartao); border:1px solid var(--linha); border-radius:var(--r-lg); padding:0.85rem 1rem; min-width:0;
  box-shadow:var(--sombra-1); }
.mi-dia-c.urgente { border-color:color-mix(in srgb, var(--acento) 55%, var(--linha)); background:var(--acento-claro); }
.mi-dia-c .r { font-size:var(--t-xs); font-weight:600; text-transform:uppercase; letter-spacing:0.05em; color:var(--suave); }
.mi-dia-c .v { font-size:1.6rem; font-weight:650; color:var(--texto); line-height:1.2; margin:0.2rem 0 0.1rem;
  letter-spacing:-0.02em; font-variant-numeric:tabular-nums; }
.mi-dia-c .s { font-size:var(--t-sm); color:var(--suave); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[data-testid="stMarkdownContainer"]:has(> .mi-dia) { margin-bottom:0 !important; container-type:inline-size; }
/* os números passam a 2 por linha quando o espaço da página é estreito (com ou sem a barra lateral aberta) */
@container (max-width: 700px) { .mi-dia { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
@media (max-width: 900px) { .mi-dia { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
/* ---------- lista de itens com ponto de cor, texto e etiqueta (ex.: próximas avaliações) ---------- */
.mi-avs { background:var(--cartao); border:1px solid var(--linha); border-radius:var(--r-lg); padding:0.9rem 1rem 0.6rem;
  box-shadow:var(--sombra-1); }
.mi-avs .mi-sec { margin:0 0 0.35rem; }
.mi-av { display:flex; align-items:center; gap:0.7rem; padding:0.55rem 0; border-top:1px solid var(--linha); min-width:0; }
.mi-avs .mi-sec + .mi-av { border-top:none; }
.mi-av > i { width:9px; height:9px; border-radius:50%; flex:none; }
.mi-av-c { flex:1; min-width:0; display:flex; flex-direction:column; }
.mi-av-c b { font-weight:600; color:var(--texto); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mi-av.primeira .mi-av-c b { font-size:var(--t-md); }
.mi-av-c span { font-size:var(--t-sm); color:var(--suave); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mi-av em { font-style:normal; flex:none; }
.mi-av-mais { padding:0.3rem 0 0.2rem; }

/* ---------- páginas com listas de cartões (Cadeiras, Salas) e estados vazios ---------- */
/* O Streamlit dá -1rem de margem em baixo a cada bloco de Markdown (para compensar o último parágrafo). Os nossos blocos
   não acabam em parágrafo: sem isto, o elemento seguinte subia por cima do texto (ex.: a caixa da «Nova cadeira»). */
[data-testid="stMarkdownContainer"]:has(.cd-topo, .cd-desc, .sr-topo, .cv-lista, .pg-cab, .sa-ola, .pg-vazio, .pg-rodape,
  .pg-contagem) { margin-bottom:0 !important; }
.pg-vazio .material-symbols-rounded, .cd-ico .material-symbols-rounded, .cd-tag .material-symbols-rounded,
.cv-vazio .material-symbols-rounded { font-weight:400; font-style:normal; line-height:1; letter-spacing:normal;
  text-transform:none; white-space:nowrap; direction:ltr; font-feature-settings:'liga'; -webkit-font-smoothing:antialiased;
  display:inline-block; }
.pg-cab h1 { font-size:var(--t-2xl) !important; font-weight:650 !important; letter-spacing:-0.028em; margin:0 !important;
  padding:0 !important; color:var(--texto); line-height:1.15 !important; }
.pg-cab p { color:var(--suave) !important; margin:0.3rem 0 0 !important; font-size:var(--t-base); line-height:1.5; }
div[class*="st-key-pg_acoes"] { justify-content:flex-end; }
div[class*="st-key-pg_acoes"] button { white-space:nowrap; }
div[class*="st-key-pg_busca"] input { font-size:0.95rem !important; }
.pg-contagem { color:var(--suave); font-size:0.85rem; margin:0.2rem 0 0.4rem; }
.pg-rodape { display:flex; align-items:center; gap:0.55rem; color:var(--suave); font-size:0.82rem; margin-top:2.2rem;
  padding-top:0.9rem; border-top:1px solid var(--linha); }
.pg-rodape .sl-avatar { width:24px; height:24px; flex-basis:24px; font-size:0.7rem; }
.pg-rodape b { color:var(--texto); font-weight:600; }
/* ---- cartões ---- */
div.stVerticalBlock[class*="st-key-card_"] { position:relative; background:var(--cartao) !important;
  border:1px solid var(--linha) !important; border-radius:var(--r-lg) !important; padding:1.05rem 1.1rem 0.95rem !important;
  transition:border-color .15s ease, box-shadow .15s ease, transform .15s ease; min-height:8.6rem; gap:0.35rem !important; }
div.stVerticalBlock[class*="st-key-card_"]:hover { border-color:color-mix(in srgb, var(--acento) 45%, var(--linha)) !important;
  box-shadow:var(--sombra-2); transform:translateY(-1px); }
div.stVerticalBlock[class*="st-key-card_"]:has([class*="st-key-sobre_"] button:focus-visible) {
  outline:2px solid var(--acento); outline-offset:2px; }
:is([data-testid="stLayoutWrapper"]:has(> div[class*="st-key-sobre_"]), div.stVerticalBlock[class*="st-key-sobre_"]) {
  position:absolute !important; inset:0; z-index:1; margin:0 !important; }
div[class*="st-key-sobre_"] :is([data-testid="stElementContainer"], .stButton, button) { width:100% !important;
  height:100% !important; max-width:none !important; }
div[class*="st-key-sobre_"] button { opacity:0; cursor:pointer; border:none !important; }
:is([data-testid="stLayoutWrapper"]:has(> div[class*="st-key-acima_"]), div[class*="st-key-acima_"]) { position:relative; z-index:2; }
div[class*="st-key-acima_"] button { border-radius:999px !important; min-height:1.9rem !important; padding:0.1rem 0.75rem !important;
  font-size:0.82rem !important; }
.cd-topo { display:flex; align-items:center; gap:0.7rem; min-width:0; }
.cd-ico { width:38px; height:38px; border-radius:11px; flex:none; display:grid; place-items:center; font-weight:650;
  font-size:1.02rem; }
.cd-ico .material-symbols-rounded { font-size:21px; }
.cd-nome { font-weight:620; font-size:1.02rem; color:var(--texto); line-height:1.25; min-width:0; overflow:hidden;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow-wrap:anywhere; }
.cd-desc { color:var(--suave); font-size:0.88rem; line-height:1.45; min-height:2.55em; overflow:hidden;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; margin-top:0.15rem; }
.cd-meta { color:var(--suave); font-size:0.8rem; margin-top:0.35rem; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; }
.cd-meta .pt + .pt::before { content:"·"; margin:0 0.45rem; color:var(--suave); opacity:.6; }
.cd-tags { display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.45rem; }
.cd-tag { display:inline-flex; align-items:center; gap:0.2rem; font-size:0.74rem; font-weight:600; border-radius:999px;
  padding:0.05rem 0.55rem; background:var(--bolha); color:var(--texto); }
.cd-tag.lab { background:color-mix(in srgb, var(--destaque) 20%, var(--cartao)); }
.cd-tag.urg { background:var(--acento-claro); color:var(--acento-esc); }
.cd-tag .material-symbols-rounded { font-size:14px; }
.cd-linha { display:flex; align-items:center; gap:0.45rem; font-size:0.86rem; color:var(--texto); min-width:0; margin-top:0.5rem; }
.cd-linha i { width:8px; height:8px; border-radius:50%; flex:none; }
.cd-linha span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.cd-linha .cd-tag { margin-left:auto; flex:none; }
.cd-linha.vazio { color:var(--suave); }
.cd-barra { height:4px; border-radius:99px; background:var(--bolha); overflow:hidden; margin-top:0.65rem; }
.cd-barra div { height:100%; border-radius:99px; }
div.stVerticalBlock[class*="st-key-card_nova"] { border:1.5px dashed var(--linha) !important; background:transparent !important; }
div.stVerticalBlock[class*="st-key-card_nova"]:hover { transform:none; box-shadow:none; }
.st-key-card_nova [data-testid="stForm"] { border:none !important; background:transparent !important; padding:0 !important; }
.pg-vazio { text-align:center; padding:3.2rem 1rem 1.4rem; }
.pg-vazio .material-symbols-rounded { font-size:40px; color:var(--acento); background:var(--acento-claro); border-radius:var(--r-lg);
  padding:0.6rem; }
.pg-vazio b { display:block; font-size:1.2rem; color:var(--texto); margin:0.9rem 0 0.35rem; font-weight:650; }
.pg-vazio p { color:var(--suave) !important; max-width:520px; margin:0 auto !important; line-height:1.55; }
div[class*="st-key-pg_vazio_acoes"] { justify-content:center; }


.ec-etiqueta { background:var(--acento-claro); color:var(--acento-esc); border-radius:999px;
        padding:0.12rem 0.65rem; font-size:0.8rem; font-weight:500; white-space:nowrap; }
.ec-doc { font-size:0.88rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:0.12rem 0; }
.ec-meta { color:var(--suave); font-size:0.85rem; }
.mi-avatar-g { width:72px; height:72px; border-radius:50%; background:var(--primario); color:#fff; display:grid; place-items:center;
        font-size:1.9rem; font-weight:600; box-shadow:0 0 0 4px var(--acento-claro); }
/* pequenas classes partilhadas (em vez de estilos soltos no HTML) */
.mi-ligado { color:var(--logo-relogio); }
.mi-logo-centro { display:flex; justify-content:center; margin:4vh 0 0.6rem; }
.mi-logo-lateral { margin:0 0 0.9rem 0.15rem; }
.mi-encolhe { min-width:0; }
.mi-proximos { margin-top:0.4rem; }
.cd-linha.vazio i { background:var(--linha); }
.cd-ico.neutro { background:var(--bolha); color:var(--suave); }
/* ícone da sala: o símbolo escolhido (ou sugerido pelo nome), cheio, num quadrado com a cor da sala */
.mi-sala-ico, .cad-ico.mi-sala-ico { background:linear-gradient(150deg, color-mix(in srgb, var(--c) 30%, var(--cartao)),
  color-mix(in srgb, var(--c) 13%, var(--cartao))); color:var(--c);
  box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--c) 32%, transparent); }
.mi-sala-ico .material-symbols-rounded { font-variation-settings:'FILL' 1, 'wght' 500; }
.cd-ico.mi-sala-ico { width:44px; height:44px; border-radius:13px; }
/* escolhas grandes («Sou aluno»/«Sou professor», «Só para mim»/«Com colegas»): o cartão inteiro escolhe */
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] { display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] > div { position:relative; margin:0 !important; padding:0.95rem 1.05rem 1.05rem;
  border:1px solid var(--linha); border-radius:16px; background:var(--fundo);
  transition:border-color .15s ease, background-color .15s ease, box-shadow .15s ease; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] > div:hover { border-color:color-mix(in srgb, var(--acento) 55%, var(--linha)); }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] > div:has(input:checked) { border-color:var(--acento);
  background:color-mix(in srgb, var(--acento) 8%, var(--fundo)); box-shadow:0 0 0 1px var(--acento); }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] > div:has(input:focus-visible) { outline:2px solid var(--acento); outline-offset:2px; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [data-testid="stRadioOption"] { margin:0 !important; position:static !important; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [data-testid="stRadioOption"]::after { content:""; position:absolute; inset:0; border-radius:16px; cursor:pointer; z-index:1; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [data-testid="stRadioOption"] p { font-size:1.02rem; font-weight:600; color:var(--texto); }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [data-testid="stRadioCaption"] { padding-left:1.75rem; }
:is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [data-testid="stRadioCaption"] p { font-size:0.86rem !important; line-height:1.45; color:var(--suave) !important;
  margin:0.15rem 0 0 !important; }
@media (max-width:640px) { :is(div.st-key-ob_vinculo, div.st-key-cs_tipo, div.st-key-ob_onde) [role="radiogroup"] { grid-template-columns:1fr; } }
div.st-key-ob_onde, div.st-key-ob_onde [data-testid="stRadio"] { width:100% !important; }
div.st-key-ob_onde [role="radiogroup"] { grid-template-columns:1fr; gap:0.5rem; width:100%; }
div.st-key-ob_onde [role="radiogroup"] > div { padding:0.7rem 0.95rem 0.75rem; }
div.st-key-ob_onde [data-testid="stRadioOption"] p { font-size:0.97rem; }
div.st-key-ob_onde [data-testid="stRadioCaption"] p { font-size:0.82rem !important; }
/* cor da sala: cada opção com a sua bolinha */
[class*="st-key-corsala_"] [data-testid="stButtonGroup"] button::before { content:""; width:0.8rem; height:0.8rem; flex:none;
  border-radius:50%; background:var(--c, var(--suave)); box-shadow:inset 0 0 0 1px rgba(0,0,0,0.14); margin-right:0.4rem; }
/* a sala como vai ficar (ao criar e nas definições) */
.cs-previa { display:flex; align-items:center; gap:0.75rem; padding:0.7rem 0.8rem; border-radius:14px; background:var(--fundo);
  border:1px dashed var(--linha); margin-top:0.2rem; }
.cs-previa .mi-sala-ico { width:44px; height:44px; border-radius:13px; display:grid; place-items:center; flex:none; }
.cs-previa .mi-sala-ico .material-symbols-rounded { font-size:25px; }
.cs-previa b { display:block; color:var(--texto); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cs-previa span { color:var(--suave); font-size:0.82rem; }

/* na barra lateral (computador), o ícone de cada sala também vem cheio e na cor dela, num quadradinho */
@media (min-width:641px) {
  [data-testid=stSidebar] [class*="st-key-navsala_"] button [data-testid=stIconMaterial] {
    --t:color-mix(in srgb, var(--c, var(--acento)) 17%, transparent);
    color:color-mix(in srgb, var(--c, var(--acento)) 82%, var(--texto)) !important; background:var(--t); border-radius:5px;
    box-shadow:0 0 0 3px var(--t), 0 0 0 4px color-mix(in srgb, var(--c, var(--acento)) 26%, transparent);
    margin:0 7px 0 2px; font-variation-settings:'FILL' 1, 'wght' 500; }
}
.cd-ico.mi-sala-ico .material-symbols-rounded { font-size:25px; }
.sr-ico.mi-sala-ico .material-symbols-rounded { font-size:30px; }
/* cartão da sala: o papel numa etiqueta e os números com o seu ícone (em vez de texto separado por pontos) */
.cd-meta.sala { display:flex; align-items:center; gap:0.35rem 0.8rem; flex-wrap:wrap; white-space:normal; margin-top:0.55rem; }
.cd-papel { font-size:0.74rem; font-weight:600; padding:0.08rem 0.55rem; border-radius:999px; background:var(--bolha); color:var(--texto); }
.cd-num { display:inline-flex; align-items:center; gap:0.25rem; }
.cd-num .material-symbols-rounded { font-size:15px; opacity:.8; }
.sem-margem { margin:0 !important; }
/* lista de contagens (perfil → «Criado com IA»): ícone, nome e número à direita, com o tamanho de letra dos cartões */
[data-testid="stMarkdownContainer"]:has(> .mi-contas) { margin-bottom:0 !important; }
.mi-contas > div { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0; border-top:1px solid var(--linha);
        font-size:var(--t-sm); color:var(--texto); }
.mi-contas > div:first-child { border-top:none; }
.mi-contas .material-symbols-rounded { font-size:1.15rem; color:var(--suave); }
.mi-contas b { margin-left:auto; font-variant-numeric:tabular-nums; }
/* perfil: o cabeçalho é igual ao das outras páginas, com a fotografia à esquerda */
.st-key-perfil_topo img { border-radius:50%; box-shadow:0 0 0 1px var(--linha); }
.pf-cab { margin:0 !important; }

/* barra lateral: «Adicionar cadeira» e «Definições» com o mesmo aspeto dos outros itens (texto à esquerda, sem caixa) */
.stApp [data-testid="stSidebar"] [data-testid="stPopoverButton"] { justify-content:flex-start !important; border-color:transparent !important;
        background:transparent !important; min-height:2.05rem !important; padding:0.3rem 0.62rem !important;
        border-radius:var(--r-sm) !important; box-shadow:none !important; font-weight:400; }
.stApp [data-testid="stSidebar"] [data-testid="stPopoverButton"]:is(:hover, [aria-expanded="true"]) { background:var(--bolha) !important;
        border-color:transparent !important; }
.stApp [data-testid="stSidebar"] [data-testid="stPopoverButton"] > div { width:100%; justify-content:space-between; }
.stApp [data-testid="stSidebar"] [data-testid="stPopoverButton"] > div > div:first-child { flex:1 1 auto; justify-content:flex-start; }
.stApp [data-testid="stSidebar"] [data-testid="stPopoverButton"] p { font-size:0.9rem; font-weight:400; }
/* caixa de conversa: o botão de anexar sem caixa à volta (só o de enviar tem fundo) e com o ícone do clipe */
.stApp [data-testid="stChatInput"] button:not([data-testid="stChatInputSubmitButton"]) { border:none !important;
        background:transparent !important; box-shadow:none !important; }
.stApp [data-testid="stChatInputFileUploadButton"] button svg { display:none; }
.stApp [data-testid="stChatInputFileUploadButton"] button::before { content:"attach_file"; font-family:'Material Symbols Rounded';
        font-size:1.3rem; line-height:1; color:var(--suave); transform:rotate(45deg); }
.stApp [data-testid="stChatInputFileUploadButton"] button:hover::before { color:var(--texto); }

/* botão do menu (abrir a barra lateral) bem visível, sobretudo no telemóvel */
[data-testid="stExpandSidebarButton"] { background:var(--cartao) !important; border:1px solid var(--linha) !important;
        border-radius:var(--r-md) !important; width:2.5rem !important; height:2.5rem !important; box-shadow:var(--sombra-1);
        display:grid !important; place-items:center; }
[data-testid="stExpandSidebarButton"]:hover { border-color:var(--acento) !important; }
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] { font-size:0 !important; line-height:1; }
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]::before { content:"menu"; font-size:1.35rem; }

/* Ecrãs médios (tablet) e barra lateral aberta num ecrã estreito: a zona principal fica estreita, por isso as colunas
   passam a ficar umas por baixo das outras, como no telemóvel (antes ficavam espremidas e cortavam o texto). */
/* (as grelhas de 7 colunas — os dias do calendário — e as linhas de botões que têm regra própria ficam como estão) */
@media (min-width: 641px) and (max-width: 820px) {
  [data-testid="stMain"] [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))):not(:is(.st-key-cal_nav, .st-key-cad_topo, [class*="st-key-ag_linha_"]) *) > [data-testid="stColumn"] {
    min-width:calc(100% - 1.5rem) !important; }
}
@media (min-width: 821px) and (max-width: 1100px) {
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) [data-testid="stMain"] [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(7))):not(:is(.st-key-cal_nav, .st-key-cad_topo, [class*="st-key-ag_linha_"]) *) > [data-testid="stColumn"] {
    min-width:calc(100% - 1.5rem) !important; }
}
/* cadeira: no ecrã estreito o nome ocupa a linha toda e «Fontes», «Avaliações» e «Mais» ficam juntos na linha de baixo */
@media (max-width: 1100px) {
  .st-key-cad_topo [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
  .st-key-cad_topo [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:first-child) {
    min-width:0 !important; flex:1 1 0 !important; }
}
@media (max-width: 820px) {
  .st-key-cad_topo [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { min-width:100% !important; }
  .st-key-cad_topo [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:first-child) { flex:1 1 auto !important;
    width:auto !important; }
  .st-key-cad_topo [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex:0 0 auto !important; }
  .st-key-cad_topo [data-testid="stColumn"]:last-child [data-testid="stPopoverButton"] [data-testid="stMarkdownContainer"] { display:none; }
}
/* calendário: as setas e «Hoje» ficam sempre juntos na mesma linha */
.st-key-cal_nav [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; }
.st-key-cal_nav [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:0 !important; }
@media (min-width: 821px) and (max-width: 1100px) {
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) .st-key-cad_topo [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
    min-width:100% !important; }
}
@media (max-width: 640px) {
  .block-container { padding-left:1rem !important; padding-right:1rem !important; padding-top:0.9rem !important; }
  [data-testid="stDialog"] [role="dialog"] { width:calc(100vw - 1.2rem) !important; max-width:calc(100vw - 1.2rem) !important; }
  .ec-saudacao { font-size:1.7rem; margin-top:9vh; } .ec-saudacao svg { height:40px; }
  .ec-titulo, .pg-cab h1, .cad-nome { font-size:var(--t-xl) !important; }
  .mi-dia { grid-template-columns:repeat(2, minmax(0, 1fr)); gap:var(--e-2); } .mi-dia-c { padding:0.7rem 0.8rem; }
  .mi-dia-c .v { font-size:1.3rem; }
  div[class*="st-key-pg_acoes"] { justify-content:flex-start; flex-wrap:wrap; }
  div.stVerticalBlock[class*="st-key-card_"] { min-height:0; }
  [data-testid="stPopoverBody"] { max-width:calc(100vw - 1.5rem) !important; }
  /* «Nova avaliação» / «Editar avaliação»: campos compactos, dois por linha (Sala | Tipo, Data | Hora) */
  [role="dialog"]:has([class*="st-key-avl1_"]) h2 { font-size:1.2rem !important; }
  [data-testid="stForm"]:has([class*="st-key-avl1_"]) [data-testid="stVerticalBlock"] { gap:0.7rem !important; }
  :is([class*="st-key-avl1_"], [class*="st-key-avl2_"]) [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important;
    gap:0.6rem !important; }
  :is([class*="st-key-avl1_"], [class*="st-key-avl2_"]) [data-testid="stColumn"] { min-width:0 !important; width:auto !important;
    flex:1 1 0 !important; }
  [class*="st-key-avl1_"] [data-testid="stColumn"]:first-child { flex-grow:1.5 !important; }
  [data-testid="stForm"]:has([class*="st-key-avl1_"]) [data-testid="stWidgetLabel"] { min-height:0; margin-bottom:0.2rem; }
  [data-testid="stForm"]:has([class*="st-key-avl1_"]) [data-testid="stWidgetLabel"] p { font-size:0.8rem; font-weight:600;
    color:var(--suave); }
  [data-testid="stForm"]:has([class*="st-key-avl1_"]) textarea { height:4.4rem !important; min-height:4.4rem !important; }
  /* janela do dia (tocar num dia do calendário): data mais pequena, cada avaliação numa linha com «Abrir» à direita */
  .st-key-dia_janela { gap:0.75rem !important; }
  [role="dialog"]:has(.st-key-dia_janela) :is(h2, h2 *) { font-size:0.75rem !important; text-transform:uppercase;
    letter-spacing:0.08em; color:var(--suave) !important; }
  .st-key-dia_janela h3 { font-size:1.2rem !important; line-height:1.3 !important; padding:0 !important; margin:0 !important; }
  .st-key-dia_janela h5 { font-size:0.75rem !important; text-transform:uppercase; letter-spacing:0.06em; color:var(--suave);
    padding:0.35rem 0 0 !important; margin:0 !important; }
  .st-key-dia_janela [data-testid="stMarkdownContainer"]:has(h3, h5) { margin-bottom:0 !important; }
  [class*="st-key-diaev_"] { background:var(--cartao); border:1px solid var(--linha); border-radius:12px; padding:0.45rem 0.5rem 0.45rem 0.75rem; }
  [class*="st-key-diaev_"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; gap:0.5rem !important; }
  [class*="st-key-diaev_"] [data-testid="stColumn"] { min-width:0 !important; width:auto !important; flex:1 1 0 !important; }
  [class*="st-key-diaev_"] [data-testid="stColumn"]:last-child { flex:0 0 auto !important; }
  [class*="st-key-diaev_"] p { font-size:0.92rem; }
  [class*="st-key-diaev_"] button { min-height:2.1rem !important; padding:0 0.8rem !important; border-radius:999px; }
  .st-key-dia_janela [data-testid="stCheckbox"] p { font-size:0.92rem; line-height:1.4; }
  .st-key-dia_janela [data-testid="stElementContainer"]:has(button[kind="primary"]),
  .st-key-dia_janela button[kind="primary"] { width:100% !important; }
  [data-testid="stDataFrame"], .stMarkdown table { max-width:100%; overflow-x:auto; display:block; }
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { max-width:92%; }
  /* a caixa de escrever fixa no fundo com a mesma margem dos dois lados */
  [data-testid="stBottomBlockContainer"] { padding-left:1rem !important; padding-right:1rem !important; }
}
</style>
"""
st.markdown(ESTILO + ESTILO_TELEMOVEL, unsafe_allow_html=True)


def cabecalho(titulo: str, subtitulo: str = "", etiquetas: list = None) -> None:
    """Cabeçalho de página: título grande e descrição (o mesmo desenho em todas as páginas; ver cabecalho_pagina para
    as páginas que têm ações à direita)."""
    tags = "".join(f'<span class="ec-etiqueta">{escape(t)}</span>' for t in (etiquetas or []))
    sub = f'<p>{escape(subtitulo)}</p>' if subtitulo else ""
    extra = f'<div class="ec-etiquetas">{tags}</div>' if tags else ""
    st.markdown(f'<div class="pg-cab"><h1>{escape(titulo)}</h1>{sub}{extra}</div>', unsafe_allow_html=True)


def celulas_grelha(n: int, por_linha: int = 3, gap: str = "medium") -> list:
    """Uma célula por cartão, linha a linha. Quando as colunas se empilham (telemóvel, tablet) os cartões ficam pela
    ordem certa (com uma coluna por posição ficavam 1, 4, 2, 5, 3 e o cartão «Nova…» no meio)."""
    celulas = []
    for _ in range(0, max(n, 1), por_linha):
        celulas += list(st.columns(por_linha, gap=gap))
    return celulas


def titulo_cartao(texto: str, nota: str = "") -> None:
    """Título de um cartão ou secção (o mesmo tamanho e peso em todas as páginas), com uma nota opcional à direita."""
    st.markdown(f"<div class='mi-sec'><b>{escape(texto)}</b>{f'<span>{escape(nota)}</span>' if nota else ''}</div>",
                unsafe_allow_html=True)


_ESTADO_IA = {"lugar": None}  # o indicador que está no ecrã agora (para mostrar os passos da pesquisa)


def passo_pensar(texto: str, detalhe: str = "", tipo: str | None = None, fontes=(), en: tuple | None = None) -> None:
    """Atualiza o indicador que está no ecrã com o passo em curso (ex.: «A pesquisar na web» · «nova temporada…»).
    en=(texto, detalhe) em inglês, quando as respostas são em inglês."""
    lugar = _ESTADO_IA.get("lugar")
    if lugar is None:
        return
    if en and st.session_state.cfg.get("idioma") == "English":
        texto, detalhe = en
    try:
        lugar.markdown(idt.pensar_html(texto, detalhe, tipo, fontes), unsafe_allow_html=True)
    except Exception:  # noqa: BLE001 — o indicador nunca pode estragar a resposta
        pass


@contextmanager
def a_pensar(texto: str = "A pensar", detalhe: str = ""):
    """Indicador animado enquanto a IA trabalha."""
    lugar = st.empty()
    lugar.markdown(idt.pensar_html(texto, detalhe), unsafe_allow_html=True)
    anterior, _ESTADO_IA["lugar"] = _ESTADO_IA.get("lugar"), lugar
    try:
        yield
    finally:
        _ESTADO_IA["lugar"] = anterior
        lugar.empty()


def com_animacao(fluxo, texto: str = "A pensar"):
    """Mostra o indicador (com os passos da pesquisa, se houver) até chegar o primeiro pedaço da resposta."""
    lugar = st.empty()
    lugar.markdown(idt.pensar_html(texto), unsafe_allow_html=True)
    _ESTADO_IA["lugar"] = lugar
    try:
        for parte in fluxo:
            if _ESTADO_IA.get("lugar") is lugar:
                _ESTADO_IA["lugar"] = None
                lugar.empty()
            yield parte
    finally:
        if _ESTADO_IA.get("lugar") is lugar:
            _ESTADO_IA["lugar"] = None
        lugar.empty()


def escrever_fluxo(fluxo, texto: str = "A pensar") -> str:
    """Como st.write_stream, mas as fórmulas aparecem desenhadas (como no papel) enquanto o texto vai chegando."""
    lugar = st.empty()
    acumulado = ""
    for parte in com_animacao(fluxo, texto):
        acumulado += str(parte)
        lugar.markdown(mt.normalizar(acumulado) + " ▍")
    lugar.markdown(mt.normalizar(acumulado))
    return acumulado


def md(texto, **k) -> None:
    """st.markdown com as fórmulas normalizadas."""
    st.markdown(mt.normalizar(texto), **k)


# =============================================================== guardar / carregar
def ler_json(caminho: Path, defeito):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defeito


def escrever_json(caminho: Path, dados, enviar: bool = True) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    if enviar:
        enviar_para_a_nuvem(caminho)


# ---------------------------------------------------------------- cópia online dos dados de cada conta (Supabase)
# Numa app publicada (ex.: Streamlit Community Cloud) o disco apaga-se quando o servidor reinicia. Com o Supabase
# ligado, cada ficheiro da conta (perfil, cadeiras, avaliações) tem uma cópia na tabela dados_utilizador: ao entrar,
# a app traz os dados para a pasta da conta; cada vez que grava, envia a cópia. A pasta continua a ser a da app.
def _chave_nuvem(caminho) -> str | None:
    try:
        rel = Path(caminho).resolve().relative_to(PASTA_UTILIZADOR.resolve()).as_posix()
    except (ValueError, NameError):
        return None
    return None if rel.startswith("backup/") or not rel.endswith(".json") else rel


def _estado_nuvem() -> Path:
    """Lista dos ficheiros desta conta que já estão online (não acaba em .json: não sobe)."""
    return PASTA_UTILIZADOR / "nuvem.estado"


def _marcar_nuvem(chave: str, online: bool) -> None:
    conhecidas = set(ler_json(_estado_nuvem(), []))
    if (chave in conhecidas) != online:
        (conhecidas.add if online else conhecidas.discard)(chave)
        _estado_nuvem().parent.mkdir(parents=True, exist_ok=True)
        _estado_nuvem().write_text(json.dumps(sorted(conhecidas)), encoding="utf-8")


def enviar_para_a_nuvem(caminho) -> None:
    if not st.session_state.get("_nuvem"):
        return
    chave = _chave_nuvem(caminho)
    if not chave:
        return
    try:
        obter_backend_salas().dados_guardar(chave, json.loads(Path(caminho).read_text(encoding="utf-8")))
        isess.PENDENTES_NUVEM.discard((UID, chave))
        _marcar_nuvem(chave, True)
    except Exception:  # noqa: BLE001 — sem ligação: fica guardado aqui e volta a tentar na próxima ação
        isess.PENDENTES_NUVEM.add((UID, chave))


def apagar_ficheiro_utilizador(caminho: Path) -> None:
    """Apaga um ficheiro da conta (ex.: uma cadeira) aqui e na cópia online."""
    caminho.unlink(missing_ok=True)
    chave = _chave_nuvem(caminho) if st.session_state.get("_nuvem") else None
    if chave:
        isess.PENDENTES_NUVEM.discard((UID, chave))
        try:
            obter_backend_salas().dados_apagar(chave)
            _marcar_nuvem(chave, False)
        except Exception:  # noqa: BLE001 — fica marcada como online: na próxima entrada a app volta a tentar
            isess.APAGAR_NUVEM.add((UID, chave))


def sincronizar_da_nuvem() -> None:
    """No início de cada sessão: traz os dados do Supabase para a pasta da conta (os que mudaram noutro dispositivo).
    O que ainda não tinha subido (sem ligação) sobe primeiro; ficheiros que só existem aqui sobem (nada se perde),
    exceto os que já tinham estado online e foram apagados noutro dispositivo. Depois, cada gravação envia a cópia."""
    if not st.session_state.get("_nuvem"):
        return
    backend = obter_backend_salas()
    for uid_, chave in list(isess.APAGAR_NUVEM):  # apagados sem ligação
        if uid_ == UID:
            backend.dados_apagar(chave)
            isess.APAGAR_NUVEM.discard((uid_, chave))
            _marcar_nuvem(chave, False)
    for uid_, chave in list(isess.PENDENTES_NUVEM):  # gravados sem ligação: o que está aqui é o mais recente
        if uid_ == UID and (PASTA_UTILIZADOR / chave).exists():
            enviar_para_a_nuvem(PASTA_UTILIZADOR / chave)
    if st.session_state.get("_sincronizado") == UID:
        return
    remoto = backend.dados_ler_todos()
    for chave, valor in remoto.items():
        alvo = isess.caminho_seguro(PASTA_UTILIZADOR, chave)
        if alvo is not None:
            escrever_json(alvo, valor, enviar=False)
    conhecidas = set(ler_json(_estado_nuvem(), []))
    for f in list(PASTA_UTILIZADOR.rglob("*.json")) if PASTA_UTILIZADOR.exists() else []:
        chave = _chave_nuvem(f)
        if chave and chave not in remoto:
            if chave in conhecidas:  # já esteve online e foi apagado noutro dispositivo
                f.unlink(missing_ok=True)
            else:
                enviar_para_a_nuvem(f)
    _estado_nuvem().parent.mkdir(parents=True, exist_ok=True)
    _estado_nuvem().write_text(json.dumps(sorted(set(remoto) | {
        k for k in (_chave_nuvem(f) for f in PASTA_UTILIZADOR.rglob("*.json")) if k and (UID, k) not in isess.PENDENTES_NUVEM
    })), encoding="utf-8")
    st.session_state._sincronizado = UID


def nome_seguro(texto: str) -> str:
    return re.sub(r"[^\w\- ]", "_", texto).strip() or "cadeira"


def caminho_cadeira(nome: str) -> Path:
    return PASTA_DADOS / f"{nome_seguro(nome)}.json"


def carregar_cadeiras() -> dict:
    cadeiras = {}
    for f in sorted(PASTA_DADOS.glob("*.json")):
        dados = ler_json(f, None)
        if dados and "nome" in dados:
            dados.setdefault("ficheiros", {})
            dados.setdefault("quiz_historico", [])
            dados.setdefault("teste_historico", [])
            cadeiras[dados["nome"]] = dados
    return cadeiras


def nova_cadeira(nome: str) -> dict:
    return {"nome": nome, "ficheiros": {}, "quiz_historico": [], "teste_historico": []}


def guardar(cadeira: str) -> None:
    if not st.session_state.get("_conta_uid"):  # sem sessão iniciada não há onde guardar
        return
    escrever_json(caminho_cadeira(cadeira), st.session_state.cadeiras[cadeira])


# Preferências de cada pessoa (ficam no perfil da conta); o resto do config.json é da app (administrador).
PREFERENCIAS = ("tema", "velocidade", "idioma", "web") + dfs.CHAVES  # as novas (avisos, IA, acessibilidade…): definicoes.py


def config_do_servidor() -> dict:
    """Chaves e serviços definidos por quem gere a app em .streamlit/secrets.toml ([ia], [supabase]).
    Assim, numa app publicada, ninguém precisa de ver nem de escrever chaves."""
    try:
        ia = dict(st.secrets.get("ia", {}) or {})
        sup = dict(st.secrets.get("supabase", {}) or {})
    except Exception:  # noqa: BLE001 — sem secrets.toml
        return {}
    def real(v) -> bool:  # ignora os valores do ficheiro de exemplo («a-chave-…», «o-teu-…», «...»)
        v = str(v or "")
        return bool(v) and not any(x in v for x in ("a-chave", "o-teu", "..."))

    ia = {k: v for k, v in ia.items() if k == "fornecedor" or real(v)}
    sup = {k: v for k, v in sup.items() if real(v)}
    srv = {}
    if ia.get("fornecedor") in ("Gemini", "Claude"):
        srv["fornecedor"] = ia["fornecedor"]
    chaves = {nome: str(ia[c]) for nome, c in (("Gemini", "gemini"), ("Claude", "claude"), ("Tavily", "tavily")) if ia.get(c)}
    if chaves:
        srv["chaves"] = chaves
    if sup.get("url") and sup.get("chave"):
        srv["supabase_url"], srv["supabase_chave"] = str(sup["url"]), str(sup["chave"])
    return srv


def guardar_config() -> None:
    cfg = dict(st.session_state.cfg)
    cfg["chaves"] = dict(cfg.get("chaves") or {})
    prefs = {k: cfg.pop(k) for k in PREFERENCIAS if k in cfg}
    perfil_ = st.session_state.get("perfil")
    if st.session_state.get("_conta_uid") and isinstance(perfil_, dict) and perfil_.get("preferencias") != prefs:
        perfil_["preferencias"] = prefs
        guardar_perfil()
    srv = st.session_state.get("_cfg_do_servidor") or {}
    for nome_, valor_ in (srv.get("chaves") or {}).items():  # as chaves do servidor nunca vão para o config.json
        if cfg["chaves"].get(nome_) == valor_:
            cfg["chaves"].pop(nome_)
    for k_ in ("fornecedor", "supabase_url", "supabase_chave"):
        if k_ in srv and cfg.get(k_) == srv[k_]:
            cfg.pop(k_, None)
    if not cfg.get("lembrar_chave"):
        cfg["chaves"] = {}
    # As Definições estão sempre desenhadas na barra lateral e chamam isto em todas as execuções:
    # só se escreve no disco quando alguma coisa mudou (antes eram duas escritas por clique, em qualquer menu).
    texto = json.dumps(cfg, ensure_ascii=False, sort_keys=True)
    if st.session_state.get("_config_gravada") == texto and FICHEIRO_CONFIG.exists():
        return
    escrever_json(FICHEIRO_CONFIG, cfg)
    st.session_state._config_gravada = texto


def guardar_perfil() -> None:
    if not st.session_state.get("_conta_uid"):
        return
    escrever_json(FICHEIRO_PERFIL, st.session_state.perfil)


# =============================================================== extração de texto
def extrair_pdf(dados: bytes) -> str:
    doc = pymupdf.open(stream=dados, filetype="pdf")
    return "\n".join(f"[Página {i + 1}]\n{p.get_text()}" for i, p in enumerate(doc))


def extrair_pptx(dados: bytes) -> str:
    prs = Presentation(io.BytesIO(dados))
    partes = []
    for i, slide in enumerate(prs.slides, start=1):
        textos = [s.text_frame.text for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            textos.append("Notas: " + slide.notes_slide.notes_text_frame.text)
        partes.append(f"[Slide {i}]\n" + "\n".join(textos))
    return "\n".join(partes)


def extrair_docx(dados: bytes) -> str:
    return "\n".join(p.text for p in Document(io.BytesIO(dados)).paragraphs if p.text.strip())


def extrair_texto(nome: str, dados: bytes) -> str:
    ext = nome.lower().rsplit(".", 1)[-1]
    if ext in TIPOS_IMAGEM:
        return extrair_imagem(nome, dados)
    if ext == "pdf":
        return extrair_pdf(dados)
    if ext == "pptx":
        return extrair_pptx(dados)
    if ext == "docx":
        return extrair_docx(dados)
    return dados.decode("utf-8", errors="ignore")


def ler_ficheiros(enviados) -> dict:
    """Lê ficheiros carregados e devolve {nome: texto}, avisando dos que não têm texto."""
    lidos = {}
    for f in enviados or []:
        try:
            texto = extrair_texto(f.name, f.getvalue())
        except Exception:  # noqa: BLE001
            st.error(f"Não consegui ler {f.name}.")
            continue
        if texto.strip():
            lidos[f.name] = texto
        else:
            st.warning(f"{f.name} não tem texto (pode ser um PDF digitalizado em imagem).")
    return lidos


# =============================================================== IA
def e_limite(texto: str) -> bool:
    return "429" in texto or "RESOURCE_EXHAUSTED" in texto or "quota" in texto.lower()


def e_sobrecarga(texto: str) -> bool:
    """Erro passageiro do lado da Google (modelo sobrecarregado ou falha interna): muda-se de modelo."""
    t = texto.lower()
    return any(x in texto for x in ("503", "UNAVAILABLE", "500 INTERNAL", "INTERNAL")) or "overloaded" in t \
        or "high demand" in t or "deadline" in t


def segundos_de_espera(texto: str):
    """Se o erro for um limite por minuto, devolve quantos segundos a Google pede para esperar."""
    if not e_limite(texto) or "PerDay" in texto:
        return None
    m = re.search(r"retry[^0-9]{0,30}?(\d+(?:\.\d+)?)\s*s", texto, re.IGNORECASE)
    return int(float(m.group(1))) if m else 30


def sem_ia_texto(para: str = "") -> str:
    """Quando a IA ainda não tem chave: o administrador sabe onde a pôr; os outros só veem que não está disponível."""
    if e_admin():
        return f"Indica a chave da IA no teu Perfil → Administração{(' ' + para) if para else ''}."
    return "O assistente de IA ainda não está disponível nesta app. Avisa quem gere a app."


def mostrar_erro(erro: Exception) -> None:
    texto = str(erro)
    if e_limite(texto) and "limit: 0" in texto:
        st.error("A tua chave não tem acesso gratuito a estes modelos (limite 0). Cria uma chave nova em "
                 "aistudio.google.com.")
    elif e_limite(texto) and "PerDay" in texto:
        st.error("Todos os modelos gratuitos que experimentei atingiram o limite **diário**. Tenta amanhã.")
    elif e_limite(texto):
        st.error("Atingiste o limite gratuito **por minuto**. Espera um minuto e tenta outra vez.")
    elif "API key" in texto or "API_KEY" in texto or "401" in texto or "403" in texto or "PERMISSION" in texto:
        st.error("A chave da API não é válida. Confirma-a no teu **Perfil** → **Administração**." if e_admin() else
                 "Há um problema com a ligação à IA. Avisa quem gere a app.")
    elif e_sobrecarga(texto):
        st.error("Os modelos da Google estão sobrecarregados neste momento (experimentei todos). Costuma passar em "
                 "poucos minutos: tenta outra vez daqui a pouco.")
    else:
        st.error("Ocorreu um erro ao falar com a IA.")
    with st.expander("Ver detalhes do erro"):
        st.code(texto[:3000])


@st.cache_data(ttl=3600, show_spinner=False)
def modelos_gemini(chave: str) -> list:
    """Modelos que existem para esta chave (para não depender de nomes fixos). Fica em cache 1 hora: antes, a app
    perguntava à Google antes de cada resposta."""
    return dz.modelos_em_cache(chave, lambda: _listar_modelos_gemini(chave))


def _listar_modelos_gemini(chave: str) -> list:
    from google import genai

    cliente = genai.Client(api_key=chave)
    nomes = set()
    excluir = ("tts", "image", "embedding", "live", "audio", "vision", "robotics", "computer", "native")
    for m in cliente.models.list():
        nome = (m.name or "").replace("models/", "")
        acoes = getattr(m, "supported_actions", None) or []
        if nome.startswith("gemini") and "generateContent" in acoes and not any(x in nome for x in excluir):
            nomes.add(nome)
    return sorted(nomes, reverse=True)


def versao_modelo(nome: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", nome)
    return float(m.group(1)) if m else 0.0


def candidatos_gemini(tarefa: str = "normal") -> list:
    """Modelos a experimentar, pela ordem certa para a velocidade escolhida e para a tarefa («leve», «simples»,
    «complexa»): o mais rápido para o que é simples, um mais capaz para o que pede raciocínio."""
    cfg = st.session_state.cfg
    try:
        modelos = modelos_gemini(cfg["chaves"].get("Gemini", ""))
    except Exception:  # noqa: BLE001
        modelos = []
    velocidade = cfg.get("velocidade", "Rápida")
    rapida = tarefa == "leve" or (velocidade == "Rápida" and tarefa != "complexa")
    lista = dz.ordenar_modelos(modelos, velocidade, tarefa) or (
        ["gemini-2.5-flash-lite", "gemini-2.5-flash"] if rapida else ["gemini-2.5-flash", "gemini-2.5-flash-lite"])
    escolhido = cfg.get("modelo_gemini", "Automático")
    if escolhido and escolhido != "Automático":
        lista = [escolhido] + [m for m in lista if m != escolhido]
    elif cfg.get("modelo_ok") in lista and ("flash-lite" in cfg["modelo_ok"]) == ("flash-lite" in lista[0]):
        lista = [cfg["modelo_ok"]] + [m for m in lista if m != cfg["modelo_ok"]]  # o último que funcionou, da mesma família
    return lista[:6]


def config_gemini(modelo: str, sistema: str, json_mode: bool, pensar_menos: bool):
    from google.genai import types

    opcoes = {"system_instruction": sistema, "temperature": 0.4,
              "response_mime_type": "application/json" if json_mode else "text/plain"}
    velocidade = st.session_state.cfg.get("velocidade", "Rápida")
    if pensar_menos and velocidade != "Máxima qualidade":
        try:
            if modelo.startswith("gemini-2"):
                opcoes["thinking_config"] = types.ThinkingConfig(thinking_budget=0 if velocidade == "Rápida" else 1024)
            else:
                opcoes["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        except Exception:  # noqa: BLE001 — versão antiga da biblioteca: segue sem esta opção
            pass
    return types.GenerateContentConfig(**opcoes)


def _tentar_modelos(funcao, tarefa: str = "normal"):
    """Experimenta os modelos por ordem: espera nos limites por minuto e muda de modelo nos diários."""
    cfg = st.session_state.cfg
    ultimo_erro = None
    for modelo in candidatos_gemini(tarefa):
        for tentativa in range(2):
            try:
                resultado = funcao(modelo)
            except Exception as erro:  # noqa: BLE001
                ultimo_erro = erro
                texto = str(erro)
                espera = segundos_de_espera(texto)
                if tentativa == 0 and espera is not None and espera <= 60:
                    with st.spinner(f"Limite por minuto atingido. A tentar outra vez dentro de {espera} s..."):
                        time.sleep(espera + 1)
                    continue
                if e_limite(texto) or e_sobrecarga(texto) or "404" in texto or "NOT_FOUND" in texto:
                    break  # experimenta o modelo seguinte
                raise
            if cfg.get("modelo_ok") != modelo:
                cfg["modelo_ok"] = modelo
                guardar_config()
            return resultado
    raise ultimo_erro or RuntimeError("Nenhum modelo disponível.")


def _conteudo_gemini(mensagens: list) -> list:
    return [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in mensagens]


def chamar_ia(mensagens: list, json_mode: bool = False, sistema: str = SISTEMA, pensar: bool = False,
              tarefa: str = "normal") -> str:
    """pensar=True deixa o modelo raciocinar antes de responder (mais lento, melhor para tarefas difíceis como o 3D)."""
    cfg = st.session_state.cfg
    if cfg["fornecedor"] == "Gemini":
        from google import genai

        cliente = genai.Client(api_key=cfg["chaves"].get("Gemini", ""))
        conteudo = _conteudo_gemini(mensagens)

        def gerar(modelo):
            try:
                return cliente.models.generate_content(
                    model=modelo, contents=conteudo, config=config_gemini(modelo, sistema, json_mode, not pensar))
            except Exception as erro:  # noqa: BLE001
                if "thinking" not in str(erro).lower():
                    raise
                return cliente.models.generate_content(
                    model=modelo, contents=conteudo, config=config_gemini(modelo, sistema, json_mode, False))

        return _tentar_modelos(gerar, "complexa" if pensar else tarefa).text or ""

    import anthropic

    cliente = anthropic.Anthropic(api_key=cfg["chaves"].get("Claude", ""))
    resposta = cliente.messages.create(model=MODELO_CLAUDE, max_tokens=8000, system=sistema, messages=mensagens)
    return "".join(b.text for b in resposta.content if b.type == "text")


LEMBRETE_WEB_PT = "\n\n(Pesquisa na web com a Google antes de responder.)"
LEMBRETE_WEB_EN = "\n\n(Search the web with Google before answering.)"
AVISO_PESQUISA_PROPRIA = (" A pesquisa na web foi feita pela aplicação e os resultados estão entre <resultados_web>"
                          "</resultados_web> (notícias com a data, previsões do tempo, artigos). Responde DIRETAMENTE à "
                          "pergunta com esses resultados, citando-os com [n] (não digas «isto não vem dos teus documentos»: "
                          "vem da web). Não inventes nada que não esteja nos resultados; se não chegarem, diz o que "
                          "encontraste e o que falta. Não mudes de assunto para os estudos. Datas, horas, temperaturas e "
                          "outros números do dia a dia vão em texto normal, sem LaTeX (ex.: 2 de novembro, 23 °C).")
AVISO_SEM_WEB = (" ATENÇÃO: a pesquisa na web NÃO está disponível nesta resposta. Não digas que pesquisaste, não cites "
                 "sites nem pesquisas e não inventes informação atual (tempo, notícias, resultados, preços, datas recentes): "
                 "se a pergunta precisar disso, diz claramente que não conseguiste pesquisar na web agora e responde só ao "
                 "que sabes com segurança ou com os documentos.")


def consultas_de_pesquisa(pergunta: str) -> dict:
    """A IA transforma a pergunta numa pesquisa curta (em português e em inglês) e diz de que tipo é."""
    try:
        r = extrair_json(chamar_ia([{"role": "user", "content":
            f"Hoje é {date.today().isoformat()}. Escreve a melhor pesquisa curta (3 a 8 palavras-chave, sem aspas) para "
            "encontrar na web a resposta a esta pergunta e diz o tipo: «atual» (algo recente ou que muda: notícias, "
            "lançamentos, datas de eventos, resultados, preços, quem ocupa um cargo), «tempo» (previsão meteorológica) ou "
            "«geral» (conhecimento que não muda). Responde só com UM objeto JSON (não uma lista): {\"pt\": \"pesquisa em "
            "português\", \"en\": \"search in English\", \"tipo\": \"atual|tempo|geral\", \"local\": \"cidade (só no tempo)\"}.\n"
            f"Pergunta: {pergunta[:600]}"}], json_mode=True, sistema="Respondes só com JSON.", tarefa="leve"))
        if "_lista" in r:  # às vezes vem uma lista de pesquisas: fica a primeira
            r = next((x for x in r["_lista"] if isinstance(x, dict)), {})
        tipo = str(r.get("tipo") or "").strip().lower()
        tipo = tipo if tipo in ("atual", "tempo", "geral") else "atual"  # na dúvida, procura também nas notícias
        return {"pt": str(r.get("pt") or pergunta)[:120], "en": str(r.get("en") or pergunta)[:120], "tipo": tipo,
                "local": str(r.get("local") or "")[:60], "pergunta": pergunta[:600]}
    except Exception:  # noqa: BLE001 — sem a IA (ex.: modelos sobrecarregados), a pesquisa usa a própria pergunta
        tipo = "tempo" if pw.parece_tempo(pergunta) else "atual"
        return {"pt": pergunta[:120], "en": pergunta[:120], "tipo": tipo, "local": "", "pergunta": pergunta[:600]}


def pesquisa_propria(pergunta: str) -> tuple[list, str]:
    """Pesquisa feita pela app (Tavily, se houver chave; senão notícias, tempo e Wikipédia), para quando a da Google
    não está disponível. Vai mostrando os passos no indicador."""
    passo_pensar("A preparar a pesquisa", "A escolher as melhores palavras e fontes", "web",
                 en=("Preparing the search", "Choosing the best keywords and sources"))
    consultas = consultas_de_pesquisa(pergunta)
    st.session_state["_consulta_web"] = consultas["pt"]
    tavily = (cfg.get("chaves") or {}).get("Tavily") or None
    plano = pw.preparar(consultas)  # o mesmo que a pesquisa vai fazer (tipo e localidade)
    if tavily:
        onde, onde_en = "toda a web (Tavily)", "the whole web (Tavily)"
    elif plano["tipo"] == "tempo":
        onde, onde_en = f"previsão do tempo para {plano['local']}", f"weather forecast for {plano['local']}"
    elif plano["tipo"] == "atual":
        onde, onde_en = "notícias recentes", "recent news"
    else:
        onde, onde_en = "Wikipédia", "Wikipedia"
    passo_pensar("A pesquisar na web", f"«{consultas['pt']}» · {onde}", "web",
                 en=("Searching the web", f"«{consultas['en']}» · {onde_en}"))
    resultados, motor = pw.pesquisar(consultas, tavily)
    if resultados:
        n = len(resultados)
        passo_pensar(f"A ler {n} fonte{'s' if n != 1 else ''}", tipo="ler",
                     fontes=[pw.nome_da_fonte(r) for r in resultados],
                     en=(f"Reading {n} source{'s' if n != 1 else ''}", ""))
    return resultados, motor


def sem_lembrete(texto: str) -> str:
    return texto.replace(LEMBRETE_WEB_PT, "").replace(LEMBRETE_WEB_EN, "")


def anexar_resultados(texto: str, resultados: list) -> str:
    return (sem_lembrete(texto) + "\n\n<resultados_web>\n" + pw.bloco_para_ia(resultados) + "\n</resultados_web>")


def guardar_resultados_web(resultados: list, motor: str) -> None:
    st.session_state["_fontes_web"] = [(r["titulo"], r["url"]) for r in resultados]
    st.session_state["_info_web"] = (
        "Pesquisa feita com a Tavily." if motor == "Tavily" else
        f"Pesquisa feita pela app ({motor})." + (" A pesquisa Google não está disponível na chave do Gemini; para "
        "pesquisar em toda a web, junta uma chave grátis da Tavily no teu Perfil → Administração." if e_admin() else "")) + (
        f" Pesquisei: «{st.session_state['_consulta_web']}»." if st.session_state.get("_consulta_web") else "")


def chamar_ia_stream(mensagens: list, sistema: str | None = None, web: bool = False, tarefa: str = "normal"):
    """Devolve a resposta aos poucos. Com web=True (só Gemini) pode pesquisar na Google; as fontes ficam em
    st.session_state["_fontes_web"]."""
    sistema = sistema or sistema_chat()
    st.session_state["_fontes_web"] = []
    st.session_state.pop("_info_web", None)
    cfg_ = st.session_state.cfg
    if cfg_["fornecedor"] == "Gemini":
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=cfg_["chaves"].get("Gemini", ""))
        conteudo = _conteudo_gemini(mensagens)

        def configurar(modelo, pensar_menos, com_web):
            conf = config_gemini(modelo, sistema, False, pensar_menos)
            if com_web:
                conf.tools = [types.Tool(google_search=types.GoogleSearch())]
            return conf

        def abrir(modelo):
            tentativas = [(True, web), (False, web)] + ([(True, False)] if web else [])
            ultimo = None
            for pensar_menos, com_web in tentativas:
                try:
                    fluxo = iter(cliente.models.generate_content_stream(
                        model=modelo, contents=conteudo, config=configurar(modelo, pensar_menos, com_web)))
                    return next(fluxo, None), fluxo
                except Exception as erro:  # noqa: BLE001
                    ultimo = erro
                    texto = str(erro).lower()
                    if e_limite(str(erro)) or not ("thinking" in texto or "tool" in texto or "search" in texto
                                                   or "grounding" in texto):
                        raise
                    if com_web and ("tool" in texto or "search" in texto or "grounding" in texto):
                        st.session_state["_aviso_web"] = "A pesquisa na web não está disponível para este modelo."
            raise ultimo

        def recolher_fontes(parte):
            try:
                meta = parte.candidates[0].grounding_metadata
                for pedaco in (meta.grounding_chunks or []):
                    if pedaco.web and pedaco.web.uri:
                        par = (pedaco.web.title or pedaco.web.uri, pedaco.web.uri)
                        if par not in st.session_state["_fontes_web"]:
                            st.session_state["_fontes_web"].append(par)
            except (AttributeError, IndexError, TypeError):
                pass

        def abrir_com_web():
            """Nem todos os modelos aceitam a pesquisa Google: experimenta-a em cada um antes de desistir dela."""
            ultimo_erro, erros = None, []
            for modelo in candidatos_gemini(tarefa):
                for pensar_menos in (True, False):
                    try:
                        fluxo_ = iter(cliente.models.generate_content_stream(
                            model=modelo, contents=conteudo, config=configurar(modelo, pensar_menos, True)))
                        return next(fluxo_, None), fluxo_
                    except Exception as erro:  # noqa: BLE001
                        ultimo_erro = erro
                        texto_erro = str(erro)
                        erros.append(f"{modelo}: {texto_erro[:600]}")
                        if "api key" in texto_erro.lower() or "api_key" in texto_erro.lower():
                            raise
                        if e_limite(texto_erro) and any(x in texto_erro.lower() for x in ("search", "grounding")):
                            raise  # a quota da pesquisa é da chave, não do modelo: não vale a pena tentar os outros
                        espera = segundos_de_espera(texto_erro)
                        if espera is not None and espera <= 20 and pensar_menos:  # limite por minuto: espera e repete
                            time.sleep(espera + 1)
                            continue
                        if "thinking" not in texto_erro.lower():
                            break  # este modelo não dá (pesquisa não suportada, sem quota...): passa ao seguinte
            st.session_state["_erros_web"] = erros
            raise ultimo_erro or RuntimeError("Sem modelos.")

        if web:
            try:
                if dz.pesquisa_google_indisponivel(cfg_["chaves"].get("Gemini", "")):
                    raise RuntimeError("429 a pesquisa Google não está disponível nesta chave (verificado há pouco)")
                passo_pensar("A pesquisar na web", "Pesquisa Google", "web", en=("Searching the web", "Google Search"))
                primeiro, fluxo = abrir_com_web()
            except Exception as erro:  # noqa: BLE001
                if "api key" in str(erro).lower() or "api_key" in str(erro).lower():
                    raise
                if not e_sobrecarga(str(erro)):  # sem quota / sem suporte: ninguém volta a tentar durante 30 min
                    dz.marcar_sem_pesquisa_google(cfg_["chaves"].get("Gemini", ""))
                pergunta_ = "".join(p_["text"] for p_ in conteudo[-1]["parts"]) if conteudo else ""
                resultados, motor = pesquisa_propria(sem_lembrete(pergunta_)) if pergunta_.strip() else ([], "")
                if resultados:  # a app pesquisou sozinha: a IA responde com esses resultados
                    guardar_resultados_web(resultados, motor)
                    st.session_state.pop("_erros_web", None)
                    sistema = sistema + AVISO_PESQUISA_PROPRIA
                    conteudo = conteudo[:-1] + [{**conteudo[-1], "parts": [{"text": anexar_resultados(pergunta_, resultados)}]}]
                else:
                    passo_pensar("A pensar", "Sem resultados na web: responde com o que sabe", "pensar",
                                 en=("Thinking", "No web results: answering with what it knows"))
                    st.session_state["_aviso_web"] = (
                        "A tua chave do Gemini não tem quota para a pesquisa na web neste momento (o limite gratuito da "
                        "Google acabou ou o teu plano não inclui pesquisa) e a pesquisa alternativa não encontrou nada. "
                        "Esta resposta usa só os teus documentos." if e_limite(str(erro))
                        else "Não foi possível pesquisar na web agora. Esta resposta usa só os teus documentos.")
                    # sem pesquisa, a IA não pode fingir que pesquisou nem inventar dados atuais
                    sistema = sistema + AVISO_SEM_WEB
                    conteudo = [{**c, "parts": [{"text": sem_lembrete(p_["text"])} for p_ in c["parts"]]} for c in conteudo]
                web = False
                primeiro, fluxo = _tentar_modelos(abrir, tarefa)
        else:
            primeiro, fluxo = _tentar_modelos(abrir, tarefa)
        for parte in itertools.chain([primeiro] if primeiro is not None else [], fluxo):
            recolher_fontes(parte)
            if parte.text:
                yield parte.text
        return

    import anthropic

    cliente = anthropic.Anthropic(api_key=cfg_["chaves"].get("Claude", ""))
    if web and mensagens:  # o Claude não pesquisa sozinho: a app pesquisa e dá-lhe os resultados
        resultados, motor = pesquisa_propria(sem_lembrete(mensagens[-1]["content"]))
        if resultados:
            guardar_resultados_web(resultados, motor)
            sistema = sistema + AVISO_PESQUISA_PROPRIA
            mensagens = mensagens[:-1] + [{**mensagens[-1], "content": anexar_resultados(mensagens[-1]["content"], resultados)}]
        else:
            st.session_state["_aviso_web"] = "A pesquisa na web não encontrou nada desta vez: esta resposta usa só os teus documentos."
            sistema = sistema + AVISO_SEM_WEB
            mensagens = mensagens[:-1] + [{**mensagens[-1], "content": sem_lembrete(mensagens[-1]["content"])}]
    with cliente.messages.stream(model=MODELO_CLAUDE, max_tokens=4000, system=sistema, messages=mensagens) as fluxo:
        yield from fluxo.text_stream


def extrair_imagem(nome: str, dados: bytes) -> str:
    """Lê uma fotografia com matéria (texto, fórmulas, esquemas) através da IA escolhida."""
    cfg_ = st.session_state.cfg
    if not cfg_["chaves"].get(cfg_["fornecedor"]):
        raise ValueError(sem_ia_texto("para ler fotografias"))
    ext = nome.lower().rsplit(".", 1)[-1]
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    pedido = ("Transcreve todo o texto desta imagem (apontamentos, slide ou página de livro), mantendo a estrutura. "
              "Escreve fórmulas em LaTeX. Descreve em poucas linhas esquemas ou gráficos que tenham matéria. "
              "Responde só com a transcrição, em português de Portugal quando acrescentares descrições.")
    if cfg_["fornecedor"] == "Gemini":
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=cfg_["chaves"]["Gemini"])
        conteudo = [types.Part.from_bytes(data=dados, mime_type=mime), pedido]
        resposta = _tentar_modelos(lambda m: cliente.models.generate_content(model=m, contents=conteudo))
        texto = resposta.text or ""
    else:
        import anthropic

        cliente = anthropic.Anthropic(api_key=cfg_["chaves"]["Claude"])
        resposta = cliente.messages.create(model=MODELO_CLAUDE, max_tokens=4000, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(dados).decode()}},
            {"type": "text", "text": pedido}]}])
        texto = "".join(b.text for b in resposta.content if b.type == "text")
    return f"[Fotografia: {nome}]\n{texto}"


def sistema_chat(web: bool = False) -> str:
    """Instruções do assistente (com as preferências de resposta das Definições → Inteligência artificial)."""
    return _sistema_chat_base(web) + dfs.instrucoes_ia(st.session_state.cfg)


def _sistema_chat_base(web: bool = False) -> str:
    """Instruções do assistente, no idioma escolhido. Com web=True a IA tem de pesquisar na Google antes de responder
    (sem isto, com os documentos à frente, o modelo quase nunca pesquisava)."""
    if st.session_state.cfg.get("idioma", "Português") == "English":
        base = ("You are a calm, patient tutor for university and secondary-school students. Answer in clear, simple "
                "English, step by step, with examples. Write every formula in LaTeX: $...$ inline and $$...$$ on its own "
                "line for important formulas; never use \\( \\) or \\[ \\], never plain-text formulas." + ESTILO_EN + " ")
        if web:
            return base + ("Google Search is ON: ALWAYS search the web before answering, to check, update and complete the "
                           "answer. The answer comes from the web; use the student's documents between <fontes></fontes> "
                           "only when they are about the question, and never say the information «is not in the documents». "
                           "Say where each piece of information comes from (website or document).")
        return base + ("Use the excerpts of the student's documents between <fontes></fontes> when they are about the question "
                       "and cite them (file, page or slide). If they are not enough, say so and answer from general knowledge, "
                       "making that clear. If the sources say no excerpt is related to the question, just answer directly "
                       "from general knowledge without mentioning the documents.")
    if web:
        return SISTEMA_CHAT_WEB + ("\n\nMODO ATUAL\nA pesquisa na web (Google) está LIGADA: pesquisa SEMPRE na web antes de responder, para "
                                   "confirmar, atualizar e completar a resposta. A resposta vem da web; os documentos do aluno "
                                   "entre <fontes></fontes> só entram se forem sobre a pergunta. Nunca digas que a informação "
                                   "«não está nos documentos» nem «não vem dos teus documentos»: o aluno pediu à web. Indica de "
                                   "onde vem cada informação (site ou documento).")
    return SISTEMA_CHAT + ("\n\nMODO ATUAL\nUsa os excertos dos documentos do aluno entre <fontes></fontes> quando são sobre a "
                           "pergunta e indica de onde vem cada informação. Se não chegarem, di-lo e responde com conhecimento "
                           "geral, deixando isso claro. Se as fontes disserem que nenhum excerto tem a ver com a pergunta, "
                           "responde diretamente com conhecimento geral, sem comentar a falta dos documentos.")


def limite_caracteres() -> int:
    cfg = st.session_state.cfg
    if cfg.get("fornecedor") == "Claude":
        return 400_000
    return VELOCIDADES.get(cfg.get("velocidade", "Rápida"), VELOCIDADES["Rápida"])["caracteres"]


def selecionar_texto(ficheiros: dict, consulta: str = "", limite: int = None) -> str:
    """Junta os documentos. Se forem grandes demais, escolhe os excertos mais relevantes para a consulta
    (ou, sem consulta, excertos espalhados por toda a matéria)."""
    limite = limite or limite_caracteres()
    completo = "\n\n".join(f"=== FICHEIRO: {n} ===\n{t}" for n, t in ficheiros.items())
    if len(completo) <= limite:
        return completo
    blocos = [(nome, i, texto[i:i + TAMANHO_BLOCO])
              for nome, texto in ficheiros.items() for i in range(0, len(texto), TAMANHO_BLOCO)]
    n_max = max(1, limite // (TAMANHO_BLOCO + 60))
    palavras = set(re.findall(r"\w{4,}", consulta.lower()))
    if palavras:
        escolhidos = sorted(blocos, key=lambda b: sum(b[2].lower().count(p) for p in palavras), reverse=True)[:n_max]
    else:
        passo = len(blocos) / n_max
        escolhidos = [blocos[int(i * passo)] for i in range(n_max)]
    escolhidos.sort(key=lambda b: (b[0], b[1]))
    return "\n\n".join(f"=== EXCERTO DE: {n} ===\n{t}" for n, _, t in escolhidos)


def extrair_json(texto: str):
    """JSON da resposta da IA (tolera blocos ```json e texto à volta). Uma lista no topo vem como {"_lista": [...]}."""
    t = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", texto or "")
    try:
        dados = json.loads(mt.reparar_json_latex(t))
    except json.JSONDecodeError:
        inicio, fim = t.find("{"), t.rfind("}")
        if inicio == -1:
            raise ValueError("sem JSON")
        dados = json.loads(mt.reparar_json_latex(t[inicio:fim + 1]))
    if isinstance(dados, list):
        return {"_lista": dados}
    if not isinstance(dados, dict):
        raise ValueError("JSON inesperado")
    return dados


def pedir(fontes: str, pedido: str, json_mode: bool = False):
    """Pedido único com os documentos como fonte. Devolve texto (ou dict se json_mode) ou None."""
    try:
        if json_mode:
            pedido += " " + mt.REGRAS_FORMULAS_JSON
        texto = chamar_ia([{"role": "user", "content": f"<fontes>\n{fontes}\n</fontes>\n\n{pedido}"}], json_mode)
        return extrair_json(texto) if json_mode else texto
    except (ValueError, json.JSONDecodeError):
        st.error("A IA não devolveu um formato válido. Tenta outra vez.")
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
    return None


def pedir_a_escrever(fontes: str, pedido: str):
    """Como pedir(), mas mostra o texto a aparecer (para resumos)."""
    try:
        resposta = escrever_fluxo(chamar_ia_stream(
            [{"role": "user", "content": f"<fontes>\n{fontes}\n</fontes>\n\n{pedido}"}], sistema=SISTEMA), "A escrever o resumo")
        return resposta if isinstance(resposta, str) else "".join(map(str, resposta))
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
    return None


# =============================================================== exportações
def criar_pptx(dados: dict) -> bytes:
    prs = Presentation()
    capa = prs.slides.add_slide(prs.slide_layouts[0])
    capa.shapes.title.text = dados.get("titulo", "Resumo")
    capa.placeholders[1].text = "Gerado com base nos teus documentos"
    for s in dados.get("slides", []):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = s.get("titulo", "")
        corpo = slide.placeholders[1].text_frame
        corpo.clear()
        for j, ponto in enumerate(s.get("pontos", [])):
            par = corpo.paragraphs[0] if j == 0 else corpo.add_paragraph()
            par.text = ponto
            par.font.size = Pt(20)
        if s.get("notas"):
            slide.notes_slide.notes_text_frame.text = s["notas"]
    saida = io.BytesIO()
    prs.save(saida)
    return saida.getvalue()


def escapar_ics(texto: str) -> str:
    return str(texto).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def criar_ics(dias: list, cadeira: str) -> str:
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mondego IA//PT", "CALSCALE:GREGORIAN"]
    for i, d in enumerate(dias):
        try:
            dia = date.fromisoformat(str(d.get("data", ""))[:10])
        except ValueError:
            continue
        linhas += [
            "BEGIN:VEVENT",
            f"UID:{nome_seguro(cadeira).replace(' ', '-')}-{dia:%Y%m%d}-{i}@mondego-ia",
            f"DTSTAMP:{agora}",
            f"DTSTART;VALUE=DATE:{dia:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dia + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escapar_ics(d.get('cadeira') or cadeira)}: {escapar_ics(d.get('temas', 'Estudo'))}",
            f"DESCRIPTION:{escapar_ics(d.get('tarefas') or d.get('tipo') or '')}",
            "END:VEVENT",
        ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas)


def csv_anki(cartoes: list) -> str:
    saida = io.StringIO()
    csv.writer(saida, delimiter="\t").writerows((c.get("frente", ""), c.get("verso", "")) for c in cartoes)
    return saida.getvalue()


# =============================================================== cadeiras e avaliações
# As datas das provas vivem só no repositório central (avaliacoes.json). As cadeiras guardam apenas
# o objetivo (nota pretendida) e a dificuldade sentida, em cadeira["objetivo"].
def repo() -> av.Avaliacoes:
    return st.session_state.repo


def objetivo(d: dict) -> dict:
    return d.get("objetivo") or {}


def fmt_data(dia, com_ano: bool = True) -> str:
    dia = av.para_data(dia)
    return f"{dia:%d/%m/%Y}" if com_ano else f"{dia:%d/%m}"


def fmt_quando(r: dict) -> str:
    return fmt_data(r["data"]) + (f" às {r['hora']}" if r.get("hora") else "")


def data_avaliacao(d: dict):
    """Data da próxima avaliação da cadeira (ou None)."""
    r = repo().proxima(d["nome"])
    return av.para_data(r["data"]) if r else None


def contexto_cadeira(d: dict) -> str:
    """Texto para a IA: próximas avaliações (com as datas atuais), objetivo e dificuldade."""
    partes = []
    futuras = repo().proximas(d["nome"])
    if futuras:
        partes.append("Próximas avaliações: " + "; ".join(
            f"{r['nome']} ({r['tipo'].lower()}) a {fmt_quando(r)}, {av.texto_faltam(r)}" for r in futuras[:4]) + ".")
    obj = objetivo(d)
    if obj.get("nota_alvo"):
        partes.append(f"Quer tirar {obj['nota_alvo']} valores.")
    if obj.get("dificuldade"):
        partes.append(f"Sente a cadeira como {obj['dificuldade'].lower()}.")
    return " ".join(partes)


def editor_cadeiras(chave: str) -> pd.DataFrame:
    """Tabela das cadeiras. A data/tipo é a avaliação principal da cadeira, guardada no repositório central."""
    linhas = []
    for nome, d in st.session_state.cadeiras.items():
        r = repo().principal(nome)
        obj = objetivo(d)
        linhas.append({"Cadeira": nome, "Avaliação": av.para_data(r["data"]) if r else None,
                       "Tipo": r["tipo"] if r else "Exame", "Nota pretendida": obj.get("nota_alvo") or 14,
                       "Dificuldade": obj.get("dificuldade") or "Média"})
    if not linhas:
        linhas = [{"Cadeira": "", "Avaliação": date.today() + timedelta(days=21), "Tipo": "Exame",
                   "Nota pretendida": 14, "Dificuldade": "Média"}]
    return st.data_editor(
        pd.DataFrame(linhas), key=chave, num_rows="dynamic", hide_index=True,
        column_config={
            "Cadeira": st.column_config.TextColumn("Cadeira", required=True, width="medium"),
            "Avaliação": st.column_config.DateColumn("Avaliação principal", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS),
            "Nota pretendida": st.column_config.NumberColumn("Nota pretendida", min_value=10, max_value=20, step=1),
            "Dificuldade": st.column_config.SelectboxColumn("Como sentes a cadeira", options=DIFICULDADES),
        },
    )


def aplicar_cadeiras(tabela: pd.DataFrame) -> int:
    validas = 0
    for _, r in tabela.iterrows():
        nome = r.get("Cadeira")
        if not isinstance(nome, str) or not nome.strip():
            continue
        nome = nome.strip()
        v, nota = r.get("Avaliação"), r.get("Nota pretendida")
        d = st.session_state.cadeiras.setdefault(nome, nova_cadeira(nome))
        d["objetivo"] = {
            "nota_alvo": None if nota is None or pd.isna(nota) else int(nota),
            "dificuldade": r.get("Dificuldade") if isinstance(r.get("Dificuldade"), str) else "Média",
        }
        guardar(nome)
        if v is not None and not pd.isna(v):
            try:
                repo().definir_principal(nome, pd.Timestamp(v).date(),
                                         r.get("Tipo") if isinstance(r.get("Tipo"), str) else "Exame",
                                         cadeiras_validas=list(st.session_state.cadeiras))
            except av.ErroValidacao as erro:
                st.error(f"{nome}: {erro}")
        validas += 1
    return validas


def adicionar_ficheiros(cadeira: str, enviados) -> int:
    novos = {n: t for n, t in ler_ficheiros(enviados).items()
             if n not in st.session_state.cadeiras[cadeira]["ficheiros"]}
    st.session_state.cadeiras[cadeira]["ficheiros"].update(novos)
    guardar(cadeira)
    return len(novos)


def media_treinos(d: dict):
    notas = [h["nota"] for h in d.get("quiz_historico", [])] + \
            [h["nota"] for h in d.get("teste_historico", []) if isinstance(h.get("nota"), (int, float))]
    return sum(notas) / len(notas) if notas else None


# =============================================================== componentes próprios (3D, simulações, mapas, código)
import mimetypes

import streamlit.components.v1 as components

mimetypes.add_type("text/javascript", ".js")  # alguns Windows registam .js como text/plain e o browser recusa os módulos
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("model/gltf-binary", ".glb")
_MONDEGO = components.declare_component("mondego", path=str(PASTA / "componentes" / "mondego"))
PASTA_AUDIO = PASTA / "componentes" / "mondego" / "audio"  # falas do assistente (o componente toca-as daqui)
PASTA_MODELOS = PASTA / "componentes" / "mondego" / "modelos"  # GLB feitos pelo Blender (o visualizador lê-os daqui)


def guardar_audio(wav: bytes) -> str:
    """Guarda a fala e devolve o caminho relativo ao componente. Ficam só as 8 mais recentes."""
    PASTA_AUDIO.mkdir(parents=True, exist_ok=True)
    nome = f"voz_{uuid.uuid4().hex[:12]}.wav"
    (PASTA_AUDIO / nome).write_bytes(wav)
    antigas = sorted(PASTA_AUDIO.glob("voz_*.wav"), key=lambda f: f.stat().st_mtime)[:-8]
    for f in antigas:
        try:
            f.unlink()
        except OSError:
            pass
    return "audio/" + nome


def versao_componentes() -> str:
    """Muda quando um ficheiro do componente muda: o browser carrega logo a versão nova (sem usar a da cache)."""
    try:
        return str(int(max(f.stat().st_mtime for f in (PASTA / "componentes" / "mondego").glob("*.js"))))
    except ValueError:
        return "0"


def componente(modo: str, chave: str, altura: int = 480, **args):
    """Componente do Mondego (componentes/mondego): visor3d, fisica, tabela, mapa, linha ou codigo."""
    return _MONDEGO(modo=modo, tema=cfg.get("tema", "Automático"), altura=altura, versao=versao_componentes(),
                    key=chave, default=None, **args)


def evento(valor, chave: str):
    """O componente devolve sempre o último valor; isto devolve-o só uma vez (cada evento traz a hora em que aconteceu)."""
    if isinstance(valor, dict) and valor.get("t") and st.session_state.get(f"_ev_{chave}") != valor["t"]:
        st.session_state[f"_ev_{chave}"] = valor["t"]
        return valor
    return None


def explicador(contexto: str, chave: str, exemplo: str = "") -> None:
    """Pergunta rápida ao explicador com IA, com o contexto da ferramenta aberta."""
    with st.expander("Perguntar ao explicador (IA)", icon=":material/school:"):
        pergunta = st.text_input("A tua pergunta", key=f"exp_{chave}", placeholder=exemplo or "O que queres perceber melhor?")
        if st.button("Perguntar", key=f"expb_{chave}", icon=":material/send:", disabled=not tem_chave) and pergunta.strip():
            try:
                escrever_fluxo(chamar_ia_stream([{"role": "user", "content": f"Contexto (ferramenta do Laboratório): {contexto}\n\n"
                                                                             f"Pergunta do aluno: {pergunta}"}],
                                                sistema=sistema_chat()), "A pensar")
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
        if not tem_chave:
            st.caption(sem_ia_texto("para usar o explicador"))


# =============================================================== navegação
# Pedidos pendentes que pertencem a um ecrã: ao mudar de menu deixam de fazer sentido e não podem
# "aparecer" mais tarde noutro sítio (ex.: uma janela de avaliação que abre ao voltar ao Calendário).
PENDENTES_DE_VISTA = ("abrir_avaliacao", "nova_avaliacao_dia", "nova_avaliacao_cadeira", "ferramenta_pendente", "salas_dialogo",
                      "plano_wiz", "abrir_plano_pedido", "_apagar_sessao", "_defs_pedido",
                      "pergunta_pendente", "acao_pendente", "cal_erro", "_exportar", "e3d_sel", "e3d_sel_ver")


def navegar(vista: str, **extra) -> None:
    """Muda de menu sem voltar a correr o script. Usada em on_click: o Streamlit corre-a ANTES do script,
    por isso a troca de menu faz-se numa só execução (sem desenhar primeiro o menu antigo)."""
    for k in PENDENTES_DE_VISTA:
        st.session_state.pop(k, None)
    st.session_state.vista = vista
    for k, v in extra.items():
        st.session_state[k] = v


def janela(titulo: str, **kw):
    """st.dialog que, ao fechar, atualiza a página (para o resto do ecrã mostrar o que mudou na janela)."""
    try:
        return st.dialog(titulo, on_dismiss="rerun", **kw)
    except TypeError:  # versões do Streamlit sem on_dismiss
        return st.dialog(titulo, **kw)


def curto(texto: str, n: int = 30) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def chave_curta(texto: str) -> str:
    import hashlib
    return hashlib.md5(texto.encode()).hexdigest()[:8]


PALETA_CADEIRAS = ["#17798A", "#2E6DB4", "#3E8E5A", "#7D4FA8", "#2AA5B8", "#B7841A", "#D9708F", "#5E7C8C"]


def cor_cadeira(nome: str) -> str:
    """Cor de uma sala pessoal (a escolhida nas definições da sala ou, sem escolha, uma fixa pelo nome)."""
    import salas as sl

    escolhida = ((st.session_state.get("cadeiras") or {}).get(nome) or {}).get("cor")
    if escolhida in sl.CORES_SALA:
        return sl.CORES_SALA[escolhida]
    return PALETA_CADEIRAS[int(chave_curta(nome), 16) % len(PALETA_CADEIRAS)]


# Cores das tarefas no plano e no calendário: as da paleta e as que se podem escolher para uma sala (as classes
# «…_cor3» e «sesc3_…» usam a posição nesta lista)
CORES_TAREFAS = PALETA_CADEIRAS + [c for c in _salas_mod.CORES_SALA.values() if c not in PALETA_CADEIRAS]


def indice_cor_sala(nome: str, sem_sala: int = 0) -> int:
    """Posição da cor da sala em CORES_TAREFAS (antes, uma cor escolhida fora da paleta fazia falhar a página)."""
    if not nome:
        return sem_sala
    cor = cor_cadeira(nome)
    return CORES_TAREFAS.index(cor) if cor in CORES_TAREFAS else sem_sala


def sala_pessoal(nome: str) -> dict:
    """Uma sala só tua (onde estão as fontes, flashcards, quizzes e o plano), com a mesma forma das salas partilhadas
    para ter o mesmo cartão, ícone e cor. Por dentro continua a ser o que a app guardava como «cadeira»."""
    d = (st.session_state.get("cadeiras") or {}).get(nome) or {}
    return {"id": "p" + chave_curta(nome), "nome": nome, "tipo": "cadeira", "pessoal": True, "cor": d.get("cor") or "",
            "cor_hex": cor_cadeira(nome), "icone": d.get("icone") or "", "descricao": d.get("descricao") or "",
            "n_documentos": len(d.get("ficheiros") or {})}


def ico_sala_html(sala: dict, classe: str = "cd-ico") -> str:
    """Ícone da sala (o escolhido ou o sugerido pelo nome) num quadrado com a cor da sala."""
    import salas as sl

    cor = sala.get("cor_hex") or sl.CORES_SALA.get(sala.get("cor") or "turquesa", "#2AA5B8")
    return (f"<div class='{classe} mi-sala-ico' style='--c:{cor}'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>"
            f"{sl.icone_da_sala(sala)}</span></div>")


def criar_sala_pessoal(nome: str, **extra) -> str:
    """Cria a sala só tua (ou devolve a que já tem esse nome). Devolve o nome final."""
    import salas_backend as sb

    nome = sb.validar_nome_sala(nome)
    if nome not in st.session_state.cadeiras:
        st.session_state.cadeiras[nome] = nova_cadeira(nome)
    st.session_state.cadeiras[nome].update({k: v for k, v in extra.items() if v is not None})
    guardar(nome)
    return nome


def renomear_sala_pessoal(antigo: str, novo: str) -> str:
    """Muda o nome de uma sala pessoal e de tudo o que aponta para ela: avaliações, planos (e as tarefas já feitas),
    conversas e tempo de foco. Os documentos, flashcards e quizzes vão com ela."""
    import salas_backend as sb

    novo = sb.validar_nome_sala(novo)
    if novo == antigo:
        return antigo
    if novo in st.session_state.cadeiras:
        raise sb.ErroSalas("Já tens uma sala com esse nome.")
    d = st.session_state.cadeiras.pop(antigo)
    d["nome"] = novo
    for s_ in (d.get("plano") or {}).get("dias", []):
        if s_.get("cadeira") == antigo:
            s_["cadeira"] = novo
    st.session_state.cadeiras[novo] = d
    guardar(novo)
    if caminho_cadeira(antigo) != caminho_cadeira(novo):
        apagar_ficheiro_utilizador(caminho_cadeira(antigo))
    validas = list(st.session_state.cadeiras)
    for r_ in repo().da_cadeira(antigo):
        era_principal = bool(r_.get("principal"))
        repo().atualizar(r_["id"], cadeiras_validas=validas, cadeira=novo)
        if era_principal:  # mudar de sala tira a marca de principal: a avaliação continua a ser a principal
            repo().atualizar(r_["id"], cadeiras_validas=validas, principal=True)
    for s_ in (perfil.get("plano_geral") or {}).get("dias", []):
        if s_.get("cadeira") == antigo:
            s_["cadeira"] = novo
    perfil["feitas"] = sorted({("|".join([f.split("|", 2)[0], novo, f.split("|", 2)[2]])
                                if f.count("|") >= 2 and f.split("|", 2)[1] == antigo else f) for f in perfil.get("feitas", [])})
    for c_ in (perfil.get("conversas") or {}).values():
        if c_.get("cadeira") == antigo:
            c_["cadeira"] = novo
    for f_ in perfil.get("foco", []):
        if f_.get("cadeira") == antigo:
            f_["cadeira"] = novo
    guardar_perfil()
    return novo


def ir(vista: str, **extra) -> None:
    """Para quando a mudança só se decide a meio do script (ex.: depois de gravar algo)."""
    navegar(vista, **extra)
    st.rerun()


def nova_conversa_vazia() -> None:
    ir("chat", conversa_id=None)


def info_aluno() -> str:
    linhas = [f"Hoje é {DIAS_SEMANA[date.today().weekday()].lower()}, {date.today():%d/%m/%Y}."]
    if st.session_state.perfil.get("nome"):
        linhas.append(f"O utilizador chama-se {st.session_state.perfil['nome']}.")
    if st.session_state.perfil.get("academico"):
        linhas.append(ac.descricao_perfil(st.session_state.perfil["academico"]))
        if st.session_state.perfil["academico"].get("vinculo") == "Professor":
            linhas.append("É PROFESSOR, não aluno: ajuda-o a ensinar (preparar aulas, fichas de exercícios, testes com "
                          "cotações e critérios de correção, explicações e exemplos para os alunos, respostas a dúvidas "
                          "de alunos). Trata-o por tu, como colega; não lhe sugiras estudar para avaliações. As salas "
                          "partilhadas dele são turmas; as salas só dele servem para preparar as aulas.")
    for nome, d in st.session_state.cadeiras.items():
        linhas.append(f"- {nome}: {contexto_cadeira(d) or 'sem avaliações futuras marcadas'}")
    hoje = sessoes_do_dia(date.today())
    if hoje:
        linhas.append("Tarefas de estudo de hoje: " + "; ".join(
            f"{s.get('cadeira')}: {s.get('temas')}{' (feita)' if s['feita'] else ''}" for s in hoje))
    return "<aluno>\n" + "\n".join(linhas) + "\n</aluno>"


def sessoes_do_dia(dia: date) -> list:
    return [s for s in av.sessoes_de_estudo(st.session_state.perfil, st.session_state.cadeiras)
            if s["data"] == dia.isoformat()]


def marcar_sessao(ident: str, feita: bool) -> None:
    feitas = set(st.session_state.perfil.setdefault("feitas", []))
    (feitas.add if feita else feitas.discard)(ident)
    st.session_state.perfil["feitas"] = sorted(feitas)
    guardar_perfil()


def fontes_conversa(conversa: dict, pergunta: str) -> str:
    """Excertos dos documentos que interessam a esta pergunta (de uma cadeira, se a conversa for dela; senão, de todas).
    Antes ia sempre o máximo de texto (~130 mil caracteres) em todas as perguntas, mesmo nas que nada tinham a ver com
    os documentos: era o que mais atrasava o início da resposta."""
    extra = conversa.get("ficheiros", {})
    cadeira = conversa.get("cadeira")
    if cadeira and cadeira in st.session_state.cadeiras:
        ficheiros = {**st.session_state.cadeiras[cadeira]["ficheiros"], **extra}
        limite = min(limite_caracteres(), 60_000)
    else:
        ficheiros = {f"{nome} · {f}": t for nome, d in st.session_state.cadeiras.items() for f, t in d["ficheiros"].items()}
        ficheiros.update({f"Ficheiros desta conversa · {f}": t for f, t in extra.items()})
        limite = min(limite_caracteres(), 40_000)
    if not ficheiros:
        return "(o aluno ainda não carregou documentos)"
    if extra and sum(len(t) for t in extra.values()) <= limite:  # o que foi anexado nesta conversa vai sempre inteiro
        resto, _ = dz.selecionar_relevante({k: v for k, v in ficheiros.items() if not k.endswith(tuple(extra))},
                                           pergunta, limite - sum(len(t) for t in extra.values()), TAMANHO_BLOCO)
        anexos = "\n\n".join(f"=== FICHEIRO ANEXADO: {n} ===\n{t}" for n, t in extra.items())
        return anexos + ("\n\n" + resto if resto else "")
    texto, n = dz.selecionar_relevante(ficheiros, pergunta, limite, TAMANHO_BLOCO)
    return texto if n else "(nenhum excerto dos documentos do aluno tem a ver com esta pergunta)"


def saudacao() -> str:
    hora = datetime.now().hour
    base = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 20 else "Boa noite"
    nome = (st.session_state.perfil.get("nome") or "").split(" ")[0]
    return f"{base}, {nome}" if nome else base


# =============================================================== conta com sessão iniciada
# (definido antes do estado inicial: a conta decide que dados se carregam)
def utilizador_externo() -> dict | None:
    """Conta Google/Facebook/... com sessão iniciada (st.user), ou None."""
    try:
        u = getattr(st, "user", None)
        if u is None:
            return None
        d = u.to_dict() if hasattr(u, "to_dict") else dict(u)
        if d.get("is_logged_in"):
            return {"nome": d.get("name") or "", "email": d.get("email") or "", "foto": d.get("picture") or ""}
    except Exception:  # noqa: BLE001
        pass
    return None


def ligar_conta_externa() -> None:
    """Com sessão Google/Microsoft/…: entra na conta local com o mesmo email (é a conta da app, das Salas e do 3D)."""
    ext = utilizador_externo()
    if not ext or st.session_state.get("_conta_ligada") == ext["email"]:
        return
    try:
        backend = obter_backend_salas()
        if backend.nome == "local" and ext["email"]:
            backend.entrar_externo(ext["email"], ext["nome"], "Aluno")
    except Exception:  # noqa: BLE001 — a app funciona na mesma sem esta ligação
        pass
    st.session_state._conta_ligada = ext["email"]


def conta_app() -> dict | None:
    """Quem tem a sessão iniciada na app: conta Google/Microsoft/Facebook (st.user) ou conta com email.
    É a mesma conta das Salas e do 3D Studio (não há segundo início de sessão)."""
    ext = utilizador_externo()
    if ext:
        return {**ext, "origem": "externa"}
    try:
        c = obter_backend_salas().atual()
    except Exception:  # noqa: BLE001
        c = None
    return {"nome": c.get("nome") or "", "email": c.get("email") or "", "foto": c.get("foto"), "origem": "email"} if c else None


def sessoes_lembradas() -> isess.SessoesLembradas:
    if "_sessoes_lembradas" not in st.session_state:
        st.session_state._sessoes_lembradas = isess.SessoesLembradas(PASTA / "sessoes_lembradas.sqlite")
    return st.session_state._sessoes_lembradas


def cookie_sessao() -> str | None:
    """O código de «manter a sessão iniciada» guardado neste browser (cookie), se houver."""
    try:
        return st.context.cookies.get(isess.NOME_COOKIE) or None
    except Exception:  # noqa: BLE001 — versões sem st.context
        return None


def pedido_local() -> bool:
    """A app está a ser usada no próprio computador (localhost)?"""
    try:
        host = str(st.context.headers.get("Host") or "")
    except Exception:  # noqa: BLE001
        return True
    return host.split(":")[0] in ("localhost", "127.0.0.1", "[::1]", "")


def cookie_nuvem() -> str | None:
    try:
        return st.context.cookies.get(isess.NOME_COOKIE_NUVEM) or None
    except Exception:  # noqa: BLE001
        return None


def pedir_cookie(nome: str, valor: str) -> None:
    """Guarda (ou apaga, com valor vazio) um cookie neste browser na próxima execução estável."""
    pendentes = [c for c in st.session_state.get("_cookie_pendente") or [] if c[0] != nome]
    st.session_state._cookie_pendente = pendentes + [(nome, valor)]


def lembrar_sessao(backend) -> None:
    """Fica com a sessão iniciada NESTE browser (telemóvel, tablet ou computador) até «Terminar sessão»."""
    s = backend.sessao
    if backend.nome != "local":  # Supabase: o browser guarda o refresh token (codificado); muda a cada renovação
        if s.get("refresh_token"):
            pedir_cookie(isess.NOME_COOKIE_NUVEM, isess.codificar(s["refresh_token"]))
            st.session_state._lembrar_nuvem = s["refresh_token"]
        return
    token = sessoes_lembradas().criar({"backend": backend.nome, "uid": s.get("uid")})
    st.session_state._token_sessao = token
    pedir_cookie(isess.NOME_COOKIE, token)


def url_da_app() -> str:
    """Endereço público da app (para o regresso do Google…): [app] url no secrets.toml, url_publica, ou localhost."""
    try:
        url = (st.secrets.get("app", {}) or {}).get("url")
    except Exception:  # noqa: BLE001
        url = None
    return str(url or cfg.get("url_publica") or "http://localhost:8501").rstrip("/")


def cookie(nome: str) -> str | None:
    try:
        return st.context.cookies.get(nome) or None
    except Exception:  # noqa: BLE001
        return None


def concluir_oauth() -> None:
    """Regresso do Google/Microsoft/Apple/Facebook (pelo Supabase): troca o «code» pela sessão e lembra-a.
    O verificador PKCE ficou na memória do servidor; o estado que o identifica vem no endereço ou no cookie."""
    q = st.query_params
    if not (q.get("code") or q.get("mondego_estado") or q.get("error_description")):
        return
    try:
        backend = obter_backend_salas()
    except Exception:  # noqa: BLE001
        return
    if backend.nome != "supabase":
        return
    codigo, erro = q.get("code"), q.get("error_description")
    estado = q.get("mondego_estado") or cookie(isess.NOME_COOKIE_PKCE)
    for k in ("code", "mondego_estado", "error", "error_code", "error_description"):
        if k in q:
            del st.query_params[k]
    pedir_cookie(isess.NOME_COOKIE_PKCE, "")
    if erro:
        st.session_state._erro_entrada = f"Não foi possível entrar: {erro}"
        return
    verificador = (isess.PKCE.pop(estado, None) or (None,))[0] if estado else None
    if not codigo or not verificador:
        st.session_state._erro_entrada = "O início de sessão demorou demasiado ou foi interrompido. Tenta outra vez."
        return
    try:
        backend.entrar_oauth(codigo, verificador)
        lembrar_sessao(backend)
    except Exception as e:  # noqa: BLE001
        st.session_state._erro_entrada = str(e) or "Não foi possível entrar com essa conta."


def restaurar_sessao() -> None:
    """Ao abrir a app (ou atualizar a página), volta a entrar com a sessão lembrada neste browser."""
    backend = None
    try:
        backend = obter_backend_salas()
        if backend.atual():
            if backend.nome == "supabase":
                backend.renovar_se_preciso()  # antes de expirar: o refresh token novo vai para o cookie nesta execução
            return
    except Exception:  # noqa: BLE001 — a sessão expirou: tenta a lembrada neste browser
        if backend is None or backend.nome != "supabase" or backend.sessao.get("uid"):
            return
    if backend.nome != "local":  # Supabase: o refresh token guardado neste browser
        cod = cookie_nuvem()
        if cod and cod != st.session_state.get("_token_rejeitado"):
            import salas_backend as sb

            try:
                backend.entrar_com_refresh(isess.descodificar(cod) or "")
                lembrar_sessao(backend)  # o refresh token mudou: guarda o novo
                return
            except sb.ErroSalas:  # o servidor diz que já não vale (expirou ou terminou noutro sítio): esquece-o
                backend.sessao.clear()
                st.session_state._token_rejeitado = cod
                pedir_cookie(isess.NOME_COOKIE_NUVEM, "")
            except Exception:  # noqa: BLE001 — sem ligação: o cookie fica (na próxima vez entra) e avisa
                backend.sessao.clear()
                st.session_state._erro_entrada = ("Sem ligação ao servidor das contas. Verifica a internet e atualiza a "
                                                  "página; a tua sessão continua guardada neste dispositivo.")
        return
    token = cookie_sessao()
    if token and token != st.session_state.get("_token_rejeitado"):
        dados = sessoes_lembradas().obter(token)
        if dados and dados.get("backend") == backend.nome:
            backend.sessao["uid"] = dados.get("uid")
            if backend.atual():
                st.session_state._token_sessao = token
                return
            backend.sessao.pop("uid", None)
        st.session_state._token_rejeitado = token  # o código já não serve: apaga-o deste browser
        pedir_cookie(isess.NOME_COOKIE, "")
    # versão anterior: a sessão ficava lembrada para o computador inteiro (config.json). No próprio computador passa
    # para um cookie deste browser; nos outros dispositivos não entra sozinha.
    antiga = cfg.get("sessao_guardada")
    if antiga and pedido_local():
        if antiga.get("backend") == backend.nome == "local":
            backend.sessao["uid"] = antiga.get("uid")
            if backend.atual():
                lembrar_sessao(backend)
            else:
                backend.sessao.pop("uid", None)
        cfg.pop("sessao_guardada", None)
        guardar_config()


def admins_da_app() -> list:
    """Quem gere a app: os emails em config.json («admins») e em secrets.toml ([admin] emails)."""
    lista = list(cfg.get("admins") or [])
    try:
        lista += [e for e in (st.secrets.get("admin", {}) or {}).get("emails", []) or []
                  if not str(e).lower().endswith("@exemplo.pt")]  # o email do ficheiro de exemplo não conta
    except Exception:  # noqa: BLE001
        pass
    return lista


def e_admin() -> bool:
    """Só o administrador vê as chaves, as credenciais e as outras «coisas da API»."""
    return isess.e_admin((conta_entrada or {}).get("email"), admins_da_app())


def uid_da_conta(conta: dict | None) -> str | None:
    if not conta:
        return None
    try:
        uid = (obter_backend_salas().sessao or {}).get("uid")
    except Exception:  # noqa: BLE001
        uid = None
    if uid:
        return re.sub(r"[^\w-]", "", str(uid))[:64] or None
    import hashlib

    return "ext_" + hashlib.sha256(conta["email"].strip().lower().encode()).hexdigest()[:24]


MANTER_AO_TROCAR = {"salas_sessao", "_backend_salas", "_intro_inicio", "sala_convite", "_cookie_pendente",
                    "_token_sessao", "_token_rejeitado", "_sessoes_lembradas", "_lembrar_nuvem", "_erro_entrada"}


def trocar_de_conta(uid: str | None, conta: dict | None) -> None:
    """Entrou (ou saiu) uma conta: esquece os dados da sessão anterior (os desta pessoa carregam-se a seguir). A primeira
    conta da app fica administradora e fica com os dados de antes das contas (os originais ficam em «antes_das_contas»)."""
    local = getattr(obter_backend_salas(), "nome", "local") == "local"
    if uid and local:  # online (Supabase) os administradores vêm de [admin] no secrets.toml
        if not admins_da_app() and conta and conta.get("email"):
            cfg["admins"] = [conta["email"].strip().lower()]
            guardar_config()
        if not cfg.get("dados_antigos_migrados"):
            destino = PASTA / "utilizadores" / uid
            if isess.migrar_dados_antigos(PASTA, destino):
                p_ = ler_json(destino / "perfil.json", {})  # a cor, a velocidade… que estavam no config.json
                p_.setdefault("preferencias", {k: cfg[k] for k in PREFERENCIAS if k in cfg})
                escrever_json(destino / "perfil.json", p_)
            cfg["dados_antigos_migrados"] = uid
            guardar_config()
    if "_conta_uid" in st.session_state:  # já havia outra pessoa (ou ninguém) nesta sessão: começa limpo
        for k in list(st.session_state.keys()):
            if k not in MANTER_AO_TROCAR:
                del st.session_state[k]
    st.session_state._conta_uid = uid
    if st.session_state.get("sala_convite"):
        st.session_state.vista = "salas"


def escrever_cookie_pendente() -> None:
    """Guarda ou apaga o cookie da sessão neste browser (depois de entrar ou de terminar sessão). Com o Supabase, o
    refresh token muda sempre que a sessão se renova: o cookie acompanha-o (senão, ao voltar, já não servia)."""
    lembrado = st.session_state.get("_lembrar_nuvem")
    guardado = st.session_state.get("_backend_salas")
    if lembrado and guardado and getattr(guardado[1], "nome", "") == "supabase":
        atual = guardado[1].sessao.get("refresh_token")
        if atual and atual != lembrado:
            pedir_cookie(isess.NOME_COOKIE_NUVEM, isess.codificar(atual))
            st.session_state._lembrar_nuvem = atual
    pendentes = st.session_state.pop("_cookie_pendente", None)
    if not pendentes:
        return
    try:
        components.html("".join(isess.js_cookie(valor or None, nome=nome) for nome, valor in pendentes), height=0)
    except Exception:  # noqa: BLE001
        pass


def obter_backend_salas():
    """As contas e as salas (Supabase, se estiver ligado; senão, uma base de dados neste computador).
    Fica guardado na sessão: a app pergunta pela conta em todas as execuções (ecrã de entrada)."""
    import salas_backend as sb

    sessao = st.session_state.setdefault("salas_sessao", {})
    local = PASTA / "salas_local.sqlite"
    chave = (cfg.get("supabase_url"), cfg.get("supabase_chave"), sb.__dict__.get("_carregado_em"))
    guardado = st.session_state.get("_backend_salas")
    if guardado and guardado[0] == chave and guardado[1].sessao is sessao and (chave[0] or local.exists()):
        return guardado[1]
    if cfg.get("supabase_url") and cfg.get("supabase_chave") and not isess.chave_secreta(cfg["supabase_chave"]):
        backend = sb.BackendSupabase(cfg["supabase_url"], cfg["supabase_chave"], sessao)
    else:
        backend = sb.BackendLocal(local, sessao)
    st.session_state["_backend_salas"] = (chave, backend)
    return backend


# =============================================================== estado inicial
def carregar_cfg() -> None:
    st.session_state.cfg = {"fornecedor": "Gemini", "chaves": {}, "lembrar_chave": True,
                            "modelo_gemini": "Automático", "velocidade": "Rápida",
                            "tema": "Automático", "idioma": "Português", "web": True}
    _guardada = ler_json(FICHEIRO_CONFIG, {})
    if "velocidade" not in _guardada:  # configuração de uma versão antiga: voltar à escolha automática
        _guardada["modelo_gemini"] = "Automático"
    st.session_state.cfg.update(_guardada)
    if not st.session_state.cfg.get("modelo_gemini"):
        st.session_state.cfg["modelo_gemini"] = "Automático"
    if st.session_state.cfg.get("velocidade") not in VELOCIDADES:
        st.session_state.cfg["velocidade"] = "Rápida"
    if st.session_state.cfg.get("tema") not in idt.TEMAS:
        st.session_state.cfg["tema"] = "Automático"
    _srv = config_do_servidor()  # chaves de quem gere a app (secrets.toml): por cima das do config.json, nunca gravadas
    st.session_state._cfg_do_servidor = _srv
    st.session_state.cfg.update({k: v for k, v in _srv.items() if k != "chaves"})
    st.session_state.cfg["chaves"] = {**(st.session_state.cfg.get("chaves") or {}), **_srv.get("chaves", {})}


if "cfg" not in st.session_state:
    carregar_cfg()
cfg = st.session_state.cfg
# Quem tem a sessão iniciada (cookie deste browser ou Google/Microsoft/…). Decide que dados se carregam a seguir.
concluir_oauth()
restaurar_sessao()
ligar_conta_externa()
def nome_real_da_conta(conta: dict | None) -> str:
    """O nome da conta, se for mesmo o da pessoa. Uma conta criada com email fica com o próprio email como nome até a
    primeira entrada perguntar o verdadeiro (logo a seguir)."""
    nome = " ".join(str((conta or {}).get("nome") or "").split())
    return "" if not nome or nome.lower() == str((conta or {}).get("email") or "").strip().lower() else nome


conta_entrada = conta_app()
_uid_entrada = uid_da_conta(conta_entrada)
if "_conta_uid" not in st.session_state or _uid_entrada != st.session_state.get("_conta_uid"):
    trocar_de_conta(_uid_entrada, conta_entrada)  # entrou ou saiu alguém: os dados passam a ser os dessa pessoa
    if "cfg" not in st.session_state:
        carregar_cfg()  # sem as preferências da pessoa anterior
    cfg = st.session_state.cfg

# Cada conta tem os seus dados (perfil, cadeiras, avaliações, cópias) em utilizadores/<id da conta>/.
# Sem sessão iniciada (ecrã de entrada) não se lê nem se grava nada.
UID = st.session_state.get("_conta_uid")
PASTA_UTILIZADOR = PASTA / "utilizadores" / (UID or "_sem_conta")
PASTA_DADOS = PASTA_UTILIZADOR / "dados"
FICHEIRO_PERFIL = PASTA_UTILIZADOR / "perfil.json"
FICHEIRO_AVALIACOES = PASTA_UTILIZADOR / "avaliacoes.json"
PASTA_BACKUP = PASTA_UTILIZADOR / "backup"
FICHEIRO_LAB = PASTA_UTILIZADOR / "laboratorio.json"  # trabalho do Laboratório das salas (cronologias, testes, glossário…)
st.session_state._nuvem = bool(UID) and getattr(obter_backend_salas(), "nome", "") == "supabase"
if st.session_state._nuvem and time.time() - st.session_state.get("_nuvem_falhou", 0) > 60:
    try:
        sincronizar_da_nuvem()
        st.session_state.pop("_nuvem_falhou", None)
    except Exception:  # noqa: BLE001 — sem ligação: usa o que houver aqui, avisa e volta a tentar daqui a um minuto
        st.session_state._nuvem_falhou = time.time()
        st.session_state._aviso_nuvem = True
if "cadeiras" not in st.session_state:
    st.session_state.cadeiras = carregar_cadeiras() if UID else {}
if "perfil" not in st.session_state:
    _vazio = {"nome": "", "horas_dia": 2, "folga": [], "concluido": False}
    st.session_state.perfil = ler_json(FICHEIRO_PERFIL, _vazio) if UID else _vazio
    for _k, _v in (st.session_state.perfil.get("preferencias") or {}).items():  # cor, velocidade… desta pessoa
        if _k in PREFERENCIAS and (_k != "tema" or _v in idt.TEMAS) and (_k != "velocidade" or _v in VELOCIDADES):
            st.session_state.cfg[_k] = _v
st.session_state.cfg.update(dfs.limpar(st.session_state.cfg))  # preferências novas: sempre completas e válidas
st.session_state.perfil.setdefault("conversas", {})
st.session_state.perfil.setdefault("academico", {})
# Lido do disco em cada execução: assim todas as páginas (e separadores do browser) veem sempre os mesmos dados.
st.session_state.repo = av.Avaliacoes(FICHEIRO_AVALIACOES, ao_gravar=enviar_para_a_nuvem)
if UID:
    for _nome in av.migrar_de_cadeiras(st.session_state.repo, st.session_state.cadeiras, PASTA_BACKUP):
        guardar(_nome)
    if nome_real_da_conta(conta_entrada) and not st.session_state.perfil.get("nome"):  # nome do Google/Microsoft/conta
        st.session_state.perfil["nome"] = conta_entrada["nome"]
        guardar_perfil()
st.session_state.setdefault("vista", "inicio")
if "_ligacao_lida" not in st.session_state:  # página recarregada (ex.: ao mudar o tema) nas Definições: volta lá
    st.session_state._ligacao_lida = True
    if st.query_params.get("p") == "definicoes":
        st.session_state.vista = "definicoes"
        st.session_state.def_cat = st.query_params.get("c")
        st.session_state.def_aberta = True
        st.session_state._pagina_inicial_de = st.session_state.get("_conta_uid")
if st.session_state.get("_conta_uid") and st.session_state.get("_pagina_inicial_de") != st.session_state.get("_conta_uid"):
    # ao entrar: a página que a pessoa escolheu em Definições → Personalização
    st.session_state._pagina_inicial_de = st.session_state.get("_conta_uid")
    if st.session_state.vista == "inicio":
        st.session_state.vista = dfs.VISTA_INICIAL.get(st.session_state.cfg.get("pagina_inicial"), "inicio")
        if st.session_state.vista == "inicio" and e_telemovel():  # como no Claude: abre pronta para escrever
            st.session_state.vista, st.session_state.conversa_id = "chat", None
if st.query_params.get("sala"):
    st.session_state.sala_convite = st.query_params.get("sala")
    st.session_state.vista = "salas"
    del st.query_params["sala"]
if st.session_state.vista == "painel":  # o antigo Painel passou a ser o Início
    st.session_state.vista = "inicio"
st.session_state.setdefault("conversa_id", None)
st.session_state.setdefault("passo", 0)
st.session_state.setdefault("versao_upload", 0)
cfg = st.session_state.cfg
# 3D Studio: escondido por agora (pedido do utilizador). Todo o código continua na app; para voltar a mostrá-lo basta
# pôr "estudio3d": true no config.json (ou mudar o valor por omissão aqui).
ESTUDIO_3D = bool(cfg.get("estudio3d", False))
perfil = st.session_state.perfil
conversas = perfil["conversas"]
acad = perfil["academico"]


def registar_uso() -> None:
    """Tempo ativo na app (aproximado): soma os intervalos entre interações que não passem de 10 minutos.
    Só guarda se o utilizador o permitir no perfil. Grava no máximo uma vez por minuto."""
    if not perfil.get("guardar_estatisticas", True):
        return
    agora = time.time()
    ultimo = st.session_state.get("_uso_ultimo")
    st.session_state._uso_ultimo = agora
    if ultimo and 0 < agora - ultimo < 600:
        st.session_state._uso_pend = st.session_state.get("_uso_pend", 0.0) + (agora - ultimo)
    if st.session_state.get("_uso_pend", 0.0) >= 60:
        uso = perfil.setdefault("uso", {})
        hoje = date.today().isoformat()
        uso[hoje] = int(uso.get(hoje, 0) + st.session_state._uso_pend)
        st.session_state._uso_pend = 0.0
        guardar_perfil()


if UID:
    registar_uso()

FORNECEDORES_LOGIN = {"google": "Google", "microsoft": "Microsoft", "apple": "Apple", "facebook": "Facebook",
                      "auth0": "outra conta"}


def fornecedores_login() -> list:
    """Fornecedores configurados em .streamlit/secrets.toml (secção [auth]). Vazio = ainda não configurado."""
    if not hasattr(st, "login"):
        return []
    try:
        auth = st.secrets.get("auth", {})
        conf = {"auth": {k: (dict(v) if hasattr(v, "keys") else v) for k, v in auth.items()}}
        prontos = isess.fornecedores_configurados(conf)
        return [f for f in FORNECEDORES_LOGIN if f in prontos]
    except Exception:  # noqa: BLE001 — sem secrets.toml
        return []


def authlib_instalado() -> bool:
    import importlib.util

    return importlib.util.find_spec("authlib") is not None


# ---------------------------------------------------------------- início de sessão da app (uma conta para tudo)


def terminar_sessao() -> None:
    """Termina a sessão em toda a app (conta com email e Google/Microsoft/Apple/Facebook), só neste browser."""
    token = st.session_state.get("_token_sessao") or cookie_sessao()
    if token:
        sessoes_lembradas().apagar(token)
    st.session_state._token_rejeitado = cookie_sessao() or cookie_nuvem()
    pedir_cookie(isess.NOME_COOKIE, "")
    pedir_cookie(isess.NOME_COOKIE_NUVEM, "")
    st.session_state.pop("_token_sessao", None)
    st.session_state.pop("_lembrar_nuvem", None)
    try:
        obter_backend_salas().sair()
    except Exception:  # noqa: BLE001
        st.session_state.pop("salas_sessao", None)
    if cfg.pop("sessao_guardada", None) is not None:
        guardar_config()
    for k in ("_conta_ligada", "sala_aberta", "en_modo"):
        st.session_state.pop(k, None)
    if utilizador_externo() and hasattr(st, "logout"):
        st.logout()


def botoes_login(prefixo: str) -> None:
    """Botões «Continuar com Google/Facebook…» (ou como os configurar)."""
    fornecedores = fornecedores_login()
    if fornecedores:
        for f in fornecedores:
            st.button(f"Continuar com {FORNECEDORES_LOGIN[f]}", key=f"{prefixo}_login_{f}", width="stretch",
                      icon=":material/login:", on_click=st.login, args=(f,))
        return
    with st.expander("Entrar com Google, Facebook ou Microsoft", icon=":material/login:"):
        st.caption("Ainda não está configurado neste computador. É preciso criar as credenciais OAuth (gratuitas) e "
                   "pô-las em `.streamlit/secrets.toml` — o ficheiro `.streamlit/secrets.toml.exemplo` tem o modelo e os "
                   "passos. Depois disso aparecem aqui os botões «Continuar com Google» e «Continuar com Facebook…».")

# A página é em português de Portugal: o Streamlit marca-a como inglês (lang="en") e o browser do telemóvel
# traduzia-a sozinho (os ícones apareciam como palavras — «GRUPOS» — e o texto em português do Brasil).
LINGUA_JS = """<script>(function(){try{var d=window.parent.document,h=d.documentElement;
if(h.getAttribute('lang')!=='pt-PT')h.setAttribute('lang','pt-PT');h.setAttribute('translate','no');h.classList.add('notranslate');
if(!d.querySelector('meta[name="google"][content="notranslate"]')){var m=d.createElement('meta');m.name='google';
m.content='notranslate';d.head.appendChild(m);}
if(!d.getElementById('mi-menu-tlm')){var sc=d.createElement('script');sc.id='mi-menu-tlm';
/* no telemóvel, escolher uma página no menu fecha-o (como no Claude); o código fica na própria página, porque este
   iframe é substituído quando a página se atualiza */
sc.textContent="document.addEventListener('click',function(e){try{if(window.innerWidth>640)return;"+
"var b=e.target.closest&&e.target.closest('[data-testid=\\"stSidebar\\"] .stButton button');"+
"if(!b||b.closest('.st-key-conv_mais'))return;setTimeout(function(){var c=document.querySelector("+
"'[data-testid=\\"stSidebarCollapseButton\\"] button');if(c)c.click();},80);}catch(x){}},true);";
d.head.appendChild(sc);}
}catch(e){}})();</script>"""

# tema escolhido (claro, escuro ou automático) — aplicado em todas as páginas, também às caixas, menus e janelas do
# próprio Streamlit (o script põe o tema do Streamlit igual ao da app; ver identidade.tema_js)
st.markdown(idt.css_tema(cfg.get("tema", "Automático")), unsafe_allow_html=True)
try:
    # recarregar a página para trocar o tema do Streamlit só quando isso não faz perder a sessão
    components.html(idt.tema_js(cfg.get("tema", "Automático"), pode_recarregar=not UID or bool(cookie_sessao() or cookie_nuvem()))
                    + LINGUA_JS, height=0)
except Exception:  # noqa: BLE001 — sem o script a app funciona na mesma (só não sincroniza o tema do Streamlit)
    pass
# Preferências de aparência e acessibilidade (tamanho do texto, contraste, leitura, foco, movimento) e o movimento das
# páginas: entram no início de cada página, menos nos laboratórios (que ficam exatamente como estão).
# Movimento e microinterações das páginas (fora dos laboratórios, que ficam como estão): o que se mexe responde a uma
# ação (carregar num botão, abrir uma janela, um menu ou um aviso); nada se mexe sozinho. «Reduzir animações» (nas
# Definições) desliga tudo isto.
ESTILO_GLOBAL_NOVO = """
:root { --mi-sai:cubic-bezier(.2,.7,.2,1); }
/* Barra de conversa como a do Claude: o texto em cima e, por baixo, o «+» à esquerda e o enviar à direita, dentro da
   mesma caixa. O clipe do Streamlit dá lugar ao «+» (arrastar e colar ficheiros para a caixa continua a funcionar) */
[class*="st-key-mbarra_"] { display:block !important; position:relative; padding:0 !important; border:1px solid var(--borda-campo);
  border-radius:20px; background:var(--campo); box-shadow:0 4px 22px var(--sombra); transition:border-color .15s, box-shadow .15s; }
[class*="st-key-mbarra_"]:focus-within { border-color:var(--acento);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--acento) 18%, transparent), 0 4px 22px var(--sombra); }
[class*="st-key-mbarra_"] > [class*="st-key-mmais_"] { position:absolute !important; left:0.65rem; bottom:0.65rem; z-index:3;
  margin:0 !important; width:auto !important; }
[class*="st-key-mbarra_"] > :not([class*="st-key-mmais_"]) { width:100% !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"], .stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div,
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div > div,
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] [data-baseweb="textarea"] { border:none !important;
  box-shadow:none !important; background:transparent !important; outline:none !important; min-height:0 !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div { padding:0 !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div > div { flex-wrap:wrap !important; align-items:flex-end !important;
  padding:0.9rem 0.65rem 0.65rem 1rem !important; gap:0 !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div > div > div:first-child { flex:1 0 100% !important; min-height:2.5rem; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInput"] > div > div > div:last-child { margin:0 0 0 auto !important; }
.stApp [class*="st-key-mbarra_"] textarea { padding:0 !important; min-height:1.6rem !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInputFileUploadButton"] { display:none !important; }
/* o «+» e o enviar: quadrados de cantos suaves, do mesmo tamanho e à mesma altura */
[class*="st-key-mmais_"] button { box-sizing:border-box !important; width:2rem !important; min-width:2rem !important; height:2rem !important;
  min-height:0 !important; padding:0 !important; border-radius:9px !important; border:1px solid var(--linha) !important;
  background:transparent !important; color:var(--texto) !important; display:grid !important; place-items:center !important; }
[class*="st-key-mmais_"] button:hover, [class*="st-key-mmais_"] button[aria-expanded="true"] { background:var(--bolha) !important; }
[class*="st-key-mmais_"] button > div, [class*="st-key-mmais_"] button > div > div,
[class*="st-key-mmais_"] button > div > div > span, [class*="st-key-mmais_"] button > div > div > span > span {
  display:grid !important; place-items:center !important; margin:0 !important; padding:0 !important; gap:0 !important; }
[class*="st-key-mmais_"] button > div > div[aria-hidden="true"] { display:none !important; }
[class*="st-key-mmais_"] button [data-testid="stMarkdownContainer"] { position:absolute !important; width:1px; height:1px;
  overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
[class*="st-key-mmais_"] button [data-testid="stIconMaterial"] { font-size:1.25rem !important; line-height:1 !important;
  width:1.25rem; height:1.25rem; margin:0 !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInputSubmitButton"] { box-sizing:border-box; width:2rem !important;
  height:2rem !important; border-radius:9px !important; background:var(--acento) !important; color:#fff !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInputSubmitButton"] svg { color:#fff !important; fill:#fff !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInputSubmitButton"]:disabled { background:var(--bolha) !important; opacity:1 !important; }
.stApp [class*="st-key-mbarra_"] [data-testid="stChatInputSubmitButton"]:disabled svg { color:var(--suave) !important; fill:var(--suave) !important; }
/* o menu do «+», como o do Claude: estreito, feito de linhas (ícone + texto), sem caixas à volta */
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) { width:19.5rem !important; max-width:calc(100vw - 2rem) !important;
  padding:0.4rem !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stVerticalBlock"] { gap:0.05rem !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) hr { margin:0.3rem 0.45rem !important; }
.mi-mlinha { display:flex; align-items:center; gap:0.65rem; padding:0 0.55rem; font-size:0.95rem; color:var(--texto); white-space:nowrap; }
.mi-mlinha .material-symbols-rounded { font-size:1.25rem; color:var(--suave); }
/* «Adicionar ficheiros ou fotos»: a zona de carregar é uma linha do menu (carregar em qualquer sítio dela abre a escolha
   de ficheiros); os ficheiros escolhidos aparecem por baixo, cada um com o «×» para o tirar */
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"] { position:relative; display:flex !important; flex-wrap:wrap;
  flex-direction:row !important; justify-content:flex-start !important; align-items:center !important; gap:0 0.65rem; min-height:0 !important; padding:0 !important; border:none !important;
  border-radius:8px !important; background:transparent !important; }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"]::before { content:"attach_file"; order:0; padding-left:0.55rem;
  font-family:'Material Symbols Rounded'; font-size:1.25rem; line-height:2.5rem; color:var(--suave); }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"]::after { content:"Adicionar ficheiros ou fotos"; order:1; flex:1;
  font-size:0.95rem; line-height:2.5rem; color:var(--texto); }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"]:hover { background:var(--bolha) !important; }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"]:has(button:focus-visible) { box-shadow:inset 0 0 0 2px var(--acento); }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"] > span,
[class*="st-key-mais_fich_"] [data-testid="stBaseButton-borderlessIcon"] { position:absolute !important; top:0; left:0; right:0;
  height:2.5rem; width:100% !important; margin:0 !important; opacity:0; z-index:2; }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"] > span button { width:100% !important; height:100% !important; }
[class*="st-key-mais_fich_"] [data-testid="stFileUploaderDropzone"] > div:not([data-testid]) { order:2; flex:1 0 100%;
  padding:0 0.35rem 0.35rem 2.35rem; }
/* «Tirar fotografia» (telemóvel) e «Fechar a câmara»: linhas do menu */
[class*="st-key-mais_tlm_"] .stButton button { justify-content:flex-start !important; gap:0.65rem; padding:0.5rem 0.55rem !important;
  min-height:0 !important; border-radius:8px !important; color:var(--texto) !important; font-weight:400 !important; }
[class*="st-key-mais_tlm_"] .stButton button:hover { background:var(--bolha) !important; }
[class*="st-key-mais_tlm_"] .stButton button > div { justify-content:flex-start !important; }
[class*="st-key-mais_tlm_"] .stButton button [data-testid="stIconMaterial"] { font-size:1.25rem; color:var(--suave); }
[class*="st-key-mais_tlm_"] .stButton button p { font-size:0.95rem; }
/* no computador há captura de ecrã; no telemóvel, a câmara (como no Claude) */
@media (hover:hover) and (pointer:fine) { [class*="st-key-mais_tlm_"] { display:none !important; } }
@media (pointer:coarse) { [class*="st-key-mais_pc_"] { display:none !important; } }
/* «Pesquisar na web»: ícone e texto à esquerda, interruptor à direita */
[class*="st-key-mais_web_"], [class*="st-key-mais_web_"] [data-testid="stCheckbox"] { width:100% !important; }
[class*="st-key-mais_web_"] label { flex-direction:row-reverse !important; justify-content:space-between !important;
  width:100% !important; padding:0.45rem 0.55rem !important; border-radius:8px; cursor:pointer; }
[class*="st-key-mais_web_"] label:hover { background:var(--bolha); }
[class*="st-key-mais_web_"] [data-testid="stMarkdownContainer"] p { display:flex; align-items:center; gap:0.65rem; font-size:0.95rem; }
[class*="st-key-mais_web_"] [data-testid="stMarkdownContainer"] p::before { content:"language"; font-family:'Material Symbols Rounded';
  font-size:1.25rem; color:var(--suave); }
/* «Documentos»: texto à esquerda, escolha da cadeira à direita */
[class*="st-key-mais_docs_"] { flex-wrap:nowrap !important; padding:0.2rem 0 !important; }
[class*="st-key-mais_docs_"] > div:first-child { flex:1 1 auto !important; width:auto !important; min-width:0; }
[class*="st-key-mais_docs_"] > div:last-child { flex:none !important; width:10.5rem !important; }
[class*="st-key-mais_docs_"] [data-baseweb="select"] > div { min-height:2.1rem !important; font-size:0.88rem; }
/* «Estilo das respostas»: uma linha que abre por baixo, como um submenu */
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpander"] details { border:none !important;
  background:transparent !important; box-shadow:none !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpander"] summary { padding:0.5rem 0.55rem !important;
  border-radius:8px; font-size:0.95rem; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpander"] summary:hover { background:var(--bolha); }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpander"] summary p { font-size:0.95rem !important;
  font-weight:400 !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpander"] summary > span { gap:0.65rem !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpanderIcon"] { color:var(--suave); font-size:1.25rem !important; }
[data-testid="stPopoverBody"]:has([class*="st-key-mais_fich_"]) [data-testid="stExpanderDetails"] { padding:0.2rem 0.55rem 0.5rem 0.55rem !important; }
/* anexos escolhidos no «+»: dentro da caixa, por cima do texto (como no Claude), cada um com o seu «×» */
[class*="st-key-manexos_"] { flex-wrap:wrap !important; gap:0.45rem !important; padding:0.75rem 0.75rem 0 0.75rem; }
[class*="st-key-manx_"] { flex:none !important; width:auto !important; max-width:15rem; gap:0 !important; flex-wrap:nowrap !important;
  padding:0.25rem 0.15rem 0.25rem 0.3rem; border:1px solid var(--linha); border-radius:10px; background:var(--bolha); }
[class*="st-key-manx_"] > div:first-child { flex:1 1 auto !important; width:auto !important; min-width:0; }
[class*="st-key-manx_"] > div:not(:first-child) { flex:none !important; width:auto !important; }
[class*="st-key-manx_"] [data-testid="stMarkdownContainer"] { margin:0 !important; }
.mi-anexo { display:flex; align-items:center; gap:0.5rem; min-width:0; font-size:0.85rem; color:var(--texto); line-height:1.2; }
.mi-anexo img, .mi-anexo .material-symbols-rounded { width:2.1rem; height:2.1rem; flex:none; border-radius:6px; }
.mi-anexo img { object-fit:cover; }
.mi-anexo .material-symbols-rounded { display:grid; place-items:center; background:var(--cartao); color:var(--acento); font-size:1.15rem; }
.mi-anexo-n { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[class*="st-key-anx_x_"] button { min-height:0 !important; padding:0.2rem !important; color:var(--suave) !important; }
[class*="st-key-anx_x_"] button:hover { color:var(--texto) !important; }
[class*="st-key-anx_x_"] button [data-testid="stMarkdownContainer"] { position:absolute !important; width:1px; height:1px;
  overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
[class*="st-key-anx_resumir_"] button { min-height:0 !important; color:var(--suave) !important; }
[class*="st-key-anx_resumir_"] button p { font-size:0.85rem; }
/* Perfil → atalhos para as Definições: lista alinhada à esquerda, como a navegação das Definições */
.st-key-perfil_atalhos .stButton button { justify-content:flex-start; text-align:left; border-radius:var(--r-sm) !important;
  padding:0.45rem 0.55rem !important; color:var(--texto); font-weight:400; }
.st-key-perfil_atalhos .stButton button > div { flex:1 1 auto; justify-content:flex-start; min-width:0; }
.st-key-perfil_atalhos .stButton button:hover { background:var(--bolha); }
.st-key-perfil_atalhos .stButton button::after { content:"chevron_right"; font-family:'Material Symbols Rounded';
  font-size:1.15rem; line-height:1; color:var(--suave); }
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, .stLinkButton > a,
[data-testid="stPopoverButton"] { transition:background .14s ease, border-color .14s ease, color .14s ease, transform .1s ease !important;
  touch-action:manipulation; }
.stButton > button:active:not(:disabled), .stDownloadButton > button:active:not(:disabled),
[data-testid="stFormSubmitButton"] > button:active:not(:disabled), [data-testid="stPopoverButton"]:active { transform:scale(.97); }
[data-testid="stMain"] :is(button, a, input, textarea, [role="tab"], [role="radio"], [role="switch"]):focus-visible {
  outline:2px solid var(--foco, var(--acento)); outline-offset:2px; }
@keyframes mi-dlg { from { opacity:0; transform:translateY(10px) scale(.985); } to { opacity:1; transform:none; } }
[data-testid="stDialog"] [role="dialog"] { animation:mi-dlg .22s var(--mi-sai) both; }
@keyframes mi-pop { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:none; } }
/* menus: só a opacidade anima — o Streamlit põe o menu no sítio com «transform», que uma animação de
   movimento anulava (o menu abria no canto da página) */
@keyframes mi-aparece { from { opacity:0; } to { opacity:1; } }
[data-testid="stPopoverBody"] { animation:mi-aparece .14s ease-out both; }
[data-testid="stExpander"] details[open] > div { animation:mi-pop .18s var(--mi-sai) both; }
[data-testid="stDialog"] [role="dialog"], [data-testid="stPopoverBody"] { overscroll-behavior:contain; }
/* avisos do Início */
.st-key-inicio_avisos { gap:0.15rem !important; }
.stApp [class*="st-key-avisol_"] { flex-wrap:nowrap !important; padding:0.55rem 0.15rem; border-top:1px solid var(--linha);
  animation:mi-pop .2s var(--mi-sai) both; }
.stApp [class*="st-key-avisol_"] > div:first-child { flex:1 1 0 !important; min-width:0 !important; width:auto !important; }
.stApp [class*="st-key-avisol_"] > div:not(:first-child) { flex:none !important; width:auto !important; }
[class*="st-key-avisol_"] [data-testid="stMarkdownContainer"] { margin-bottom:0 !important; }
.mi-aviso { display:flex; gap:0.7rem; align-items:flex-start; min-width:0; }
.mi-aviso > .material-symbols-rounded { flex:none; width:2rem; height:2rem; display:grid; place-items:center; border-radius:10px;
  background:var(--bolha); color:var(--suave); font-size:1.15rem; }
[class*="st-key-avisol_"][class*="_urg"] .mi-aviso > .material-symbols-rounded { background:var(--aviso-claro); color:var(--aviso); }
.mi-aviso b { display:block; font-weight:600; color:var(--texto); font-size:var(--t-base); line-height:1.35; overflow-wrap:anywhere; }
.mi-aviso div > span { display:block; color:var(--suave); font-size:var(--t-sm); line-height:1.4; margin-top:0.1rem; overflow-wrap:anywhere; }
[class*="st-key-aviso_fechar_"] button { color:var(--suave) !important; padding:0 0.3rem !important; min-height:2rem; }
/* só o ícone se vê; o nome «Dispensar» fica para os leitores de ecrã */
[class*="st-key-aviso_fechar_"] button [data-testid="stMarkdownContainer"] { position:absolute !important; width:1px; height:1px;
  overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
@media (max-width: 640px) {
  .stApp [class*="st-key-avisol_"] { flex-wrap:wrap !important; }
  .stApp [class*="st-key-avisol_"] > div:first-child { flex-basis:calc(100% - 2.6rem) !important; }
  .stApp [class*="st-key-avisol_"] > div:nth-child(2) { margin-left:2.7rem; }
}
/* barras e linhas partilhadas (histórico do cronómetro, avisos, definições) */
.pl-barras { display:flex; flex-direction:column; gap:0.35rem; margin:0.3rem 0 0.6rem; }
.pl-barra { display:grid; grid-template-columns:minmax(0, 9rem) 1fr auto; gap:0.6rem; align-items:center; font-size:0.82rem; color:var(--texto); }
.pl-barra span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pl-barra div { height:7px; border-radius:99px; background:var(--bolha); overflow:hidden; }
.pl-barra div i { display:block; height:100%; border-radius:99px; }
.pl-barra b { font-weight:500; color:var(--suave); font-size:0.78rem; font-variant-numeric:tabular-nums; }
.df-valor { color:var(--texto); font-size:var(--t-base); overflow-wrap:anywhere; }
.df-valor small { display:block; color:var(--suave); font-size:var(--t-sm); }
.cd-tag.novas { background:var(--acento-claro); color:var(--acento-esc); }
/* perfil: progresso por cadeira */
.mi-progs { display:flex; flex-direction:column; }
.mi-prog { display:grid; grid-template-columns:minmax(0, 13rem) minmax(5rem, 1fr); gap:0.25rem 1rem; padding:0.65rem 0;
  border-top:1px solid var(--linha); align-items:center; }
.mi-prog:first-child { border-top:none; }
.mi-prog-c { min-width:0; }
.mi-prog-c b { display:block; font-weight:600; color:var(--texto); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mi-prog-c span { display:block; font-size:var(--t-sm); color:var(--suave); }
.mi-prog-b { height:8px; border-radius:99px; background:var(--bolha); overflow:hidden; }
.mi-prog-b i { display:block; height:100%; border-radius:99px; }
.mi-prog-b.vazio { opacity:.5; }
.mi-prog-t { grid-column:1 / -1; font-size:var(--t-sm); color:var(--suave); font-variant-numeric:tabular-nums; }
.mi-prog-t em { font-style:normal; margin-left:0.6rem; padding:0.05rem 0.5rem; border-radius:999px; background:var(--aviso-claro);
  color:var(--aviso); }
@media (max-width: 640px) { .mi-prog { grid-template-columns:1fr; } }
/* barra lateral: o cronómetro mini não ocupa espaço quando não está a contar */
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(iframe[title*="mondego"][height="0"]) { margin:0 !important; }
"""


def aplicar_preferencias_visuais() -> None:
    css = dfs.css_preferencias(cfg, cfg.get("tema", "Automático"))
    st.markdown("<style>" + ESTILO_GLOBAL_NOVO + css[len("<style>"):], unsafe_allow_html=True)


def definicoes_ia(horizontal: bool = False, com_3d: bool = False) -> None:
    cfg["fornecedor"] = st.radio(
        "Fornecedor da IA", ["Gemini", "Claude"], index=0 if cfg["fornecedor"] == "Gemini" else 1,
        captions=["Gratuito, com limites diários", "Pago, melhor qualidade"], horizontal=horizontal,
    )
    ajuda = "Cria grátis em aistudio.google.com → Get API key" if cfg["fornecedor"] == "Gemini" \
        else "Cria em console.anthropic.com → API Keys (pago)"
    do_servidor = ((st.session_state.get("_cfg_do_servidor") or {}).get("chaves") or {}).get(cfg["fornecedor"])
    if do_servidor:  # vem dos segredos do servidor: não aparece (nem no browser do administrador) e muda-se lá
        st.info(f"A chave do {cfg['fornecedor']} está nos segredos do servidor (secção [ia] do secrets.toml ou das "
                "Secrets do Streamlit Cloud). Para a mudar, muda-a lá e reinicia a app.", icon=":material/lock:")
        cfg["chaves"][cfg["fornecedor"]] = do_servidor
    else:
        chave = st.text_input(f"Chave da API ({cfg['fornecedor']})", value=cfg["chaves"].get(cfg["fornecedor"], ""),
                              type="password", help=ajuda)
        cfg["chaves"][cfg["fornecedor"]] = chave.strip()
        cfg["lembrar_chave"] = st.checkbox("Lembrar a chave neste computador", value=cfg.get("lembrar_chave", True))
    if cfg["fornecedor"] == "Gemini" and cfg["chaves"].get("Gemini"):
        try:
            modelos = modelos_gemini(cfg["chaves"]["Gemini"])
            st.success("Chave válida.")
        except Exception as erro:  # noqa: BLE001
            modelos = []
            mostrar_erro(erro)
        if modelos:
            opcoes = ["Automático"] + modelos
            atual = cfg.get("modelo_gemini") if cfg.get("modelo_gemini") in opcoes else "Automático"
            cfg["modelo_gemini"] = st.selectbox("Modelo", opcoes, index=opcoes.index(atual),
                                                help="'Automático' escolhe o mais rápido disponível e muda sozinho "
                                                     "quando um modelo chega ao limite.")
    if com_3d and ESTUDIO_3D:
        st.divider()
        meshy = st.text_input("Chave Meshy (geração 3D realista, opcional)", value=cfg["chaves"].get("Meshy", ""),
                              type="password", help="Serviço pago de geração de malhas 3D (meshy.ai). Sem esta chave, o "
                                                    "3D Studio cria modelos com a IA do Mondego.")
        cfg["chaves"]["Meshy"] = meshy.strip()
        definicoes_blender()
    guardar_config()
    st.caption("No plano gratuito do Gemini, a Google pode usar os pedidos para melhorar os seus modelos. "
               "Não carregues documentos confidenciais.")


def servidor_blender() -> dict | None:
    """Servidor Blender para todos os utilizadores: primeiro .streamlit/secrets.toml ([blender] url/token, ideal na app
    online), depois as Definições."""
    try:
        sec = st.secrets.get("blender", {})
        if sec.get("url") and sec.get("token"):
            return {"url": str(sec["url"]), "token": str(sec["token"])}
    except Exception:  # noqa: BLE001 — sem secrets.toml
        pass
    if cfg.get("blender_url") and cfg.get("blender_token"):
        return {"url": cfg["blender_url"], "token": cfg["blender_token"]}
    return None


def motor_blender() -> str | None:
    """Que Blender vai ser usado: «Servidor Blender», «Blender 5.2» (neste computador) ou None."""
    if servidor_blender():
        return "Servidor Blender"
    exe = mb.encontrar_blender(cfg.get("blender_caminho"))
    return mb.nome_blender(exe) if exe else None


def definicoes_blender() -> None:
    st.divider()
    titulo_cartao("Motor Blender (modelos 3D com mais qualidade)")
    motor = motor_blender()
    if motor == "Servidor Blender":
        st.caption("Os modelos 3D são melhorados no servidor Blender, para todos os utilizadores desta app.")
    elif motor:
        st.caption(f"Encontrei o **{motor}** neste computador: os modelos 3D são melhorados aqui (arestas arredondadas, "
                   "superfícies lisas, relevo orgânico e materiais realistas).")
    else:
        st.caption("Não encontrei o Blender neste computador. Instala-o (grátis, em blender.org) ou liga um servidor Blender.")
    cfg["blender_auto"] = st.toggle("Melhorar os modelos com o Blender automaticamente", value=cfg.get("blender_auto", True),
                                    disabled=not motor, help="Depois de a IA criar ou alterar um modelo, o Blender refaz as peças.")
    caminho = st.text_input("Caminho do Blender (só se não for encontrado sozinho)", value=cfg.get("blender_caminho", ""),
                            placeholder=r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
    if caminho.strip() != cfg.get("blender_caminho", ""):
        cfg["blender_caminho"] = caminho.strip()
        guardar_config()
    if motor and st.button("Testar o Blender", icon=":material/science:", key="blender_teste",
                           help="Constrói um modelo pequeno (caixa, cilindro, forma orgânica, vaso, tubo e placa)."):
        teste = e3.normalizar_modelo({"titulo": "Teste", "partes": [
            {"id": "caixa", "tipo": "caixa", "dims": {"largura": 1, "altura": 0.5, "profundidade": 0.8}, "material": "brilhante"},
            {"id": "cilindro", "tipo": "cilindro", "dims": {"raio_topo": 0.3, "raio_base": 0.3, "altura": 1}, "material": "metal"},
            {"id": "celula", "tipo": "organico", "dims": {"raio": 0.5, "irregularidade": 0.2}, "material": "padrao"},
            {"id": "vaso", "tipo": "torno", "dims": {"perfil": [[0, 0], [0.4, 0.05], [0.3, 0.6], [0.35, 0.8]]}, "material": "vidro"},
            {"id": "tubo", "tipo": "tubo", "dims": {"pontos": [[0, 0, 0], [0.5, 0.5, 0], [1, 0, 0]], "raio": 0.08}},
            {"id": "placa", "tipo": "extrusao", "dims": {"forma": [[0, 0], [1, 0], [1, 0.5], [0, 0.5]], "profundidade": 0.1}},
            {"id": "luz", "tipo": "esfera", "dims": {"raio": 0.2}, "material": "emissivo"}]})
        try:
            inicio = time.time()
            with st.spinner("A construir um modelo de teste no Blender..."):
                dados, nome = mb.construir(teste, servidor_blender(), cfg.get("blender_caminho"))
            st.success(f"{nome}: modelo de teste feito em {time.time() - inicio:.1f} s ({len(dados) // 1024} KB). Está tudo pronto.")
        except mb.ErroBlender as erro:
            st.error("O Blender não conseguiu construir o modelo de teste.")
            st.code(str(erro)[-2500:])
    with st.expander("Servidor Blender (para a app online)", icon=":material/dns:"):
        st.caption("Para que todos os utilizadores tenham modelos feitos no Blender, corre o servidor (pasta servidor_blender, "
                   "com Docker) num computador sempre ligado e indica aqui o endereço e a chave. Na app online põe-nos em "
                   "`.streamlit/secrets.toml`, na secção `[blender]`.")
        url = st.text_input("Endereço do servidor", value=cfg.get("blender_url", ""), placeholder="https://blender.exemplo.pt")
        token = st.text_input("Chave do servidor", value=cfg.get("blender_token", ""), type="password")
        c1, c2 = st.columns(2)
        if c1.button("Guardar servidor", key="blender_guardar", width="stretch"):
            cfg.update(blender_url=url.strip(), blender_token=token.strip())
            guardar_config()
            st.rerun()
        if c2.button("Testar ligação", key="blender_testar", width="stretch", disabled=not (url and token)):
            try:
                estado = mb.estado_servidor(url.strip(), token.strip())
                st.success(f"Servidor ligado: {estado.get('blender', 'Blender')}.")
            except mb.ErroBlender as erro:
                st.error(str(erro))


def exportar_dados() -> bytes:
    """Todos os dados do utilizador num .zip (direito de acesso/portabilidade — RGPD). A chave da IA não vai."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for f in [FICHEIRO_PERFIL, FICHEIRO_AVALIACOES, FICHEIRO_LAB] + sorted(PASTA_DADOS.glob("*.json")):
            if f.exists():
                z.write(f, f.relative_to(PASTA_UTILIZADOR).as_posix())
        try:  # modelos 3D da conta com sessão iniciada (3D Studio)
            import biblioteca3d as b3

            bib = b3.abrir(obter_backend_salas())
            if bib.contas.atual():
                for m in bib.meus("todos"):
                    z.writestr(f"modelos3d/{e3.slug(m['titulo'])}_{m['id'][:6]}.json",
                               json.dumps(bib.obter(m["id"])["modelo"], ensure_ascii=False, indent=1))
        except Exception:  # noqa: BLE001 — a exportação do resto não pode falhar por causa disto
            pass
        z.writestr("config.json", json.dumps({k: cfg[k] for k in PREFERENCIAS if k in cfg}, ensure_ascii=False, indent=1))
    return memoria.getvalue()


def importar_dados(conteudo: bytes) -> str:
    """Substitui os dados desta conta pelos de um .zip de «Descarregar todos os meus dados» (ex.: do computador para a
    app publicada). O que havia antes fica numa cópia em backup/antes_de_importar. Com o Supabase, tudo sobe."""
    import shutil

    lido = isess.ler_zip_dados(conteudo, PREFERENCIAS)  # valida tudo antes de mexer em alguma coisa
    ficheiros = lido["ficheiros"]
    copia = PASTA_BACKUP / "antes_de_importar"
    shutil.rmtree(copia, ignore_errors=True)
    for f in [FICHEIRO_PERFIL, FICHEIRO_AVALIACOES, FICHEIRO_LAB] + sorted(PASTA_DADOS.glob("*.json")):
        if f.exists():
            (copia / f.relative_to(PASTA_UTILIZADOR)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, copia / f.relative_to(PASTA_UTILIZADOR))
    novas = {n for n in ficheiros if n.startswith("dados/")}
    for f in sorted(PASTA_DADOS.glob("*.json")):
        if f.relative_to(PASTA_UTILIZADOR).as_posix() not in novas:
            apagar_ficheiro_utilizador(f)
    perfil_novo = dict(ficheiros["perfil.json"])
    if lido["preferencias"]:
        perfil_novo["preferencias"] = {**(perfil_novo.get("preferencias") or {}), **lido["preferencias"]}
    for nome_, dados_ in ficheiros.items():
        if nome_ != "perfil.json":
            escrever_json(PASTA_UTILIZADOR / nome_, dados_)
    if "avaliacoes.json" not in ficheiros:
        escrever_json(FICHEIRO_AVALIACOES, [])
    if "laboratorio.json" not in ficheiros and FICHEIRO_LAB.exists():
        apagar_ficheiro_utilizador(FICHEIRO_LAB)
    escrever_json(FICHEIRO_PERFIL, perfil_novo)
    for k in ("cadeiras", "perfil", "conversa_id", "cadeira_atual", "_exportar", "passo", "_lab_dados_uid"):
        st.session_state.pop(k, None)
    st.session_state.cfg.update({k: v for k, v in (perfil_novo.get("preferencias") or {}).items() if k in PREFERENCIAS})
    n = len(novas)
    return (f"Dados importados: perfil, {n} sala{'s' if n != 1 else ''}"
            + (" e avaliações." if "avaliacoes.json" in ficheiros else ".")
            + (" Os modelos 3D do .zip não se importam (ficam na tua conta do 3D Studio)." if any(
                i.startswith("modelos3d/") for i in lido["ignorados"]) else ""))


def apagar_todos_os_dados() -> None:
    """Direito ao apagamento (RGPD): apaga a conta desta pessoa e os dados dela (perfil, cadeiras, avaliações,
    conversas, cópias). Os dados das outras pessoas e a configuração da app ficam."""
    import shutil
    for f in [FICHEIRO_PERFIL, FICHEIRO_AVALIACOES, FICHEIRO_LAB] + list(PASTA_DADOS.glob("*.json")):
        f.unlink(missing_ok=True)
    shutil.rmtree(PASTA_BACKUP, ignore_errors=True)
    if UID:
        shutil.rmtree(PASTA / "utilizadores" / UID, ignore_errors=True)
        sessoes_lembradas().apagar_da_conta(st.session_state.get("salas_sessao", {}).get("uid") or UID)
    try:
        backend = obter_backend_salas()
        if hasattr(backend, "apagar_conta"):
            backend.apagar_conta()
        else:
            backend.sair()
    except Exception:  # noqa: BLE001
        pass
    if utilizador_externo() and hasattr(st, "logout"):
        st.logout()
    for k in list(st.session_state.keys()):
        if k not in ("_sessoes_lembradas",):
            del st.session_state[k]
    pedir_cookie(isess.NOME_COOKIE, "")
    pedir_cookie(isess.NOME_COOKIE_NUVEM, "")


def definicoes_pesquisa_web() -> None:
    st.caption("Com a pesquisa na web ligada, a IA usa a pesquisa da Google (se a tua chave do Gemini tiver quota para "
               "isso). Se não tiver, a app pesquisa sozinha em fontes abertas: notícias (Google Notícias), tempo "
               "(Open-Meteo) e Wikipédia. Com uma chave grátis da **Tavily** (tavily.com → Sign up → API key, 1000 "
               "pesquisas por mês, sem cartão) pesquisa em toda a web.")
    if ((st.session_state.get("_cfg_do_servidor") or {}).get("chaves") or {}).get("Tavily"):
        st.info("A chave da Tavily está nos segredos do servidor (secção [ia]).", icon=":material/lock:")
        return
    tavily = st.text_input("Chave da Tavily (opcional)", value=cfg["chaves"].get("Tavily", ""), type="password",
                           key="chave_tavily", placeholder="tvly-...")
    if tavily.strip() != cfg["chaves"].get("Tavily", ""):
        cfg["chaves"]["Tavily"] = tavily.strip()
        guardar_config()
        st.success("Guardada.")


def definicoes_salas() -> None:
    if isess.chave_secreta((st.session_state.get("_cfg_do_servidor") or {}).get("supabase_chave")):
        st.error("A chave do Supabase nos segredos do servidor é a secreta (service_role). A app não a usa: troca-a pela "
                 "anon / publishable.")
        return
    if (st.session_state.get("_cfg_do_servidor") or {}).get("supabase_url"):
        st.info("O Supabase está ligado pelos segredos do servidor (secção [supabase]). As contas, as salas e os dados de "
                "cada pessoa ficam lá. Para mudar, muda os segredos e reinicia a app.", icon=":material/lock:")
        return
    st.caption("Sem isto, as Salas funcionam só neste computador. Com o Supabase, colegas noutros computadores "
               "podem entrar nas tuas salas. Usa a chave **anon / public** (nunca a service_role).")
    url = st.text_input("Project URL do Supabase", value=cfg.get("supabase_url", ""), placeholder="https://xxxx.supabase.co")
    chave_sb = st.text_input("Chave anon / public", value=cfg.get("supabase_chave", ""), type="password")
    publica = st.text_input("Endereço público da app (para os links de convite)", value=cfg.get("url_publica", ""),
                            placeholder="http://localhost:8501")
    if isess.chave_secreta(cfg.get("supabase_chave")):
        st.error("A chave guardada é a secreta (service_role). A app não a usa: põe a chave anon / publishable.")
    if st.button("Guardar ligação", key="guardar_supabase"):
        if url and not url.startswith("https://"):
            st.error("O Project URL começa por https://")
        elif isess.chave_secreta(chave_sb):
            st.error("Essa é a chave secreta (service_role / sb_secret_…), que dá acesso a tudo. Usa a chave "
                     "**anon / public** ou a **publishable** (sb_publishable_…).")
        else:
            cfg.update(supabase_url=url.strip(), supabase_chave=chave_sb.strip(), url_publica=publica.strip())
            guardar_config()
            st.session_state.pop("salas_sessao", None)
            st.success("Guardado.")


def definicoes_inicio_sessao() -> None:
    """Botões «Continuar com …» do ecrã de entrada: só aparecem aos utilizadores os que estão configurados aqui."""
    backend = obter_backend_salas()
    if backend.nome == "supabase":
        isess.CACHE_FORNECEDORES.pop(backend.url, None)
        ativos = fornecedores_supabase(backend)
        st.caption("Com o Supabase ligado (app publicada), quem trata da entrada é o Supabase. Liga cada fornecedor no "
                   "painel do Supabase: **Authentication → Providers** (Google, Azure para a Microsoft, Apple, Facebook), "
                   "com o URI de regresso que o Supabase mostra. Em **Authentication → URL Configuration**, junta o "
                   f"endereço da app (`{url_da_app()}/**`) às Redirect URLs.")
        for f, nome in isess.FORNECEDORES.items():
            st.markdown(f"**{nome}** · " + ("<span class='mi-ligado'>ligado</span>" if f in ativos
                                             else "<span class='ec-meta'>desligado</span>"), unsafe_allow_html=True)
        return
    prontos = fornecedores_login()
    st.caption("No ecrã de entrada, os utilizadores só veem os botões que já funcionam. Configura cada um uma vez "
               "(credenciais grátis do fornecedor) e reinicia a app.")
    if not authlib_instalado():
        st.warning("Falta a biblioteca de autenticação: `py -3.14 -m pip install Authlib`.", icon=":material/download:")
    for f, nome in isess.FORNECEDORES.items():
        c1, c2 = st.columns([2.2, 1], vertical_alignment="center")
        c1.markdown(f"**{nome}** · " + ("<span class='mi-ligado'>ligado</span>" if f in prontos
                                         else "<span class='ec-meta'>por configurar</span>"), unsafe_allow_html=True)
        if c2.button("Mudar" if f in prontos else "Configurar", key=f"adm_cfg_{f}", width="stretch"):
            DIALOGOS_FORNECEDOR[f]()


def importar_ui(titulo: str = "Trazer os meus dados de outro computador (.zip)") -> None:
    with st.expander(titulo, icon=":material/upload:"):
        st.caption("Usa o .zip de «Descarregar todos os meus dados» da outra app (por exemplo, a do teu computador: "
                   "Perfil → Os teus dados). Os dados desta conta passam a ser os do ficheiro: perfil, conversas, "
                   "salas e avaliações.")
        zip_ = st.file_uploader("Ficheiro .zip", type=["zip"], key="importar_zip")
        substituir = st.checkbox("Substituir os dados desta conta pelos do ficheiro", key="importar_confirmar")
        if st.button("Importar", key="importar_dados", width="stretch", icon=":material/upload:",
                     disabled=not (zip_ and substituir)) and zip_ and substituir:
            try:
                st.session_state._importado = importar_dados(zip_.getvalue())
                st.session_state.pop("importar_confirmar", None)
                st.rerun()
            except isess.ErroImportar as erro:
                st.error(str(erro))


# =============================================================== perguntas iniciais (uma por ecrã)
def passo_ia_em_curso() -> bool:
    """O passo da chave já começou neste ecrã (para não desaparecer a meio quando a chave fica escrita)."""
    return bool(st.session_state.get("_passo_ia_visto")) and e_admin()


VINCULOS = {
    "Aluno": (":material/school:", "Sou aluno",
              "Estuda com os teus apontamentos, prepara as avaliações e junta-te às salas dos teus professores e colegas."),
    "Professor": (":material/co_present:", "Sou professor",
                  "Cria turmas para as cadeiras que dás, partilha materiais e avisos e prepara aulas, fichas e testes."),
}


def passos_onboarding(so_academico: bool) -> list:
    """Primeira entrada: aluno ou professor primeiro (decide o resto), depois o nome e onde estuda ou ensina.
    As salas criam-se dentro da app, não aqui."""
    passos = ["vinculo", "nome", "ensino" if acad.get("vinculo") == "Professor" else "estudos"]
    if not so_academico:
        sem_chave = not (cfg.get("chaves") or {}).get(cfg.get("fornecedor", "Gemini"))
        if (e_admin() and sem_chave) or passo_ia_em_curso():
            passos.append("ia")
    return passos


def _ob_titulo(titulo: str, sub: str = "") -> None:
    st.markdown(f"<h2 class='ob-titulo'>{escape(titulo)}</h2>" + (f"<p class='ob-sub'>{escape(sub)}</p>" if sub else ""),
                unsafe_allow_html=True)


# «Onde estudas / ensinas?»: uma só escolha entre três (antes eram duas perguntas, nível de ensino e instituição)
ONDE = {"uc": (":material/account_balance:", ac.UC),
        "outra": (":material/school:", "Outra instituição"),
        "secundario": (":material/menu_book:", "Ensino secundário")}


def _ob_onde(prof: bool) -> str:
    """Universidade de Coimbra, outra instituição do ensino superior ou ensino secundário. Guarda o nível e a
    instituição (os campos de sempre) e devolve a escolha."""
    if acad.get("nivel") == "Ensino secundário":
        atual = "secundario"
    elif acad.get("instituicao") and acad.get("instituicao") != ac.UC:
        atual = "outra"
    else:
        atual = "uc"
    legendas = {"uc": "Escolhes os teus departamentos" if prof else "Escolhes o teu grau e o teu curso",
                "outra": "Outra universidade ou politécnico",
                "secundario": "Escolhes as disciplinas que dás" if prof else "Do 10.º ao 12.º ano"}
    escolha = st.radio("Onde ensinas" if prof else "Onde estudas", list(ONDE), index=list(ONDE).index(atual),
                       format_func=lambda k: f"{ONDE[k][0]} {ONDE[k][1]}", captions=[legendas[k] for k in ONDE],
                       key="ob_onde", label_visibility="collapsed") or atual
    if escolha == "secundario":
        acad["nivel"] = "Ensino secundário"
    else:
        acad["nivel"] = "Ensino superior"
        if escolha == "uc":
            acad["instituicao"] = ac.UC
    return escolha


def _ob_outra_instituicao() -> str | None:
    """Qual é a outra instituição do ensino superior (da lista, ou escrita à mão em «Outra»)."""
    outras = [i for i in ac.INSTITUICOES if i != ac.UC]
    atual = acad.get("instituicao") if acad.get("instituicao") in outras else (
        "Outra" if acad.get("instituicao_outra") and "Outra" in outras else outras[0])
    esc = st.selectbox("Instituição", outras, index=outras.index(atual), key="ob_inst_outra")
    if esc != "Outra":
        acad["instituicao"] = esc
        return None
    nome_inst = st.text_input("Nome da instituição", value=acad.get("instituicao_outra", ""), key="ob_inst_nome")
    acad["instituicao_outra"] = nome_inst.strip()
    acad["instituicao"] = nome_inst.strip() or "Outra"
    return None if nome_inst.strip() else "Escreve o nome da instituição."


def ecra_onboarding(passo_id: str):
    """Desenha um ecrã e devolve (tabela, erro_de_validacao) para o botão Continuar."""
    tabela, erro = None, None
    if passo_id == "vinculo":
        _ob_titulo("Como vais usar o Mondego IA?", "Isto muda o que a app te mostra. Podes alterar mais tarde no teu Perfil.")
        atual = acad.get("vinculo") if acad.get("vinculo") in VINCULOS else None
        escolha = st.radio("Como vais usar o Mondego IA", list(VINCULOS), index=list(VINCULOS).index(atual) if atual else None,
                           format_func=lambda v: f"{VINCULOS[v][0]} {VINCULOS[v][1]}", captions=[VINCULOS[v][2] for v in VINCULOS],
                           key="ob_vinculo", label_visibility="collapsed")
        if escolha:
            acad["vinculo"] = escolha
        else:
            erro = "Escolhe se és aluno ou professor."
        if not so_academico:  # quem já usava a app noutro computador traz tudo e não precisa de responder a mais nada
            importar_ui("Já usavas o Mondego IA noutro computador? Traz os teus dados (.zip)")
    elif passo_id == "nome":
        prof = acad.get("vinculo") == "Professor"
        _ob_titulo("Como te chamas?", "É assim que " + ("os teus alunos e colegas" if prof else "os teus colegas") +
                   " te veem nas salas.")
        perfil["nome"] = st.text_input("Nome completo", value=perfil.get("nome", ""), max_chars=100, key="ob_nome",
                                       autocomplete="name",
                                       placeholder="ex.: Marta Lopes" if prof else "ex.: Maria João Santos").strip()
        if len(perfil["nome"]) < 2:
            erro = "Escreve o teu nome completo."
    elif passo_id == "estudos":
        _ob_titulo("Onde estudas?", "Para as explicações e os exemplos virem ao teu nível.")
        onde = _ob_onde(prof=False)
        if onde == "secundario":
            opcoes = ac.AREAS_SECUNDARIO
            base = str(acad.get("area") or "").split(":")[0]
            escolha = st.selectbox("Área ou curso", opcoes, index=opcoes.index(base) if base in opcoes else 0, key="ob_area")
            if escolha in ("Outro", "Curso profissional"):
                outro = st.text_input("Qual?", value=acad.get("area_detalhe", ""), key="ob_area_det",
                                      placeholder="ex.: Técnico de Informática").strip()
                acad["area_detalhe"] = outro
                acad["area"] = f"{escolha}: {outro}" if outro else escolha
                if not outro:
                    erro = "Escreve a tua área ou curso."
            else:
                acad["area"] = escolha
        else:
            erro = _ob_outra_instituicao() if onde == "outra" else None
            acad["grau"] = st.selectbox("Grau", ac.GRAUS, index=ac.GRAUS.index(acad["grau"]) if acad.get("grau") in ac.GRAUS else 0,
                                        key="ob_grau")
            lista = ac.cursos_de(acad.get("instituicao", ""), acad.get("grau", ""))
            if lista:
                opcoes = lista + ["Outro (escrever)"]
                atual = acad.get("curso") if acad.get("curso") in lista else None
                esc = st.selectbox("Curso", opcoes, index=opcoes.index(atual) if atual else None, key="ob_curso",
                                   placeholder="Escolhe ou escreve para procurar")
                if esc == "Outro (escrever)":
                    acad["curso"] = st.text_input("Nome do curso", key="ob_curso_nome",
                                                  value="" if acad.get("curso") in lista else acad.get("curso", "")).strip()
                else:
                    acad["curso"] = esc or ""
            else:
                acad["curso"] = st.text_input("Curso", value=acad.get("curso", ""), key="ob_curso_livre",
                                              placeholder="ex.: Mestrado em Engenharia Informática").strip()
            if not erro and not acad.get("curso"):
                erro = "Escolhe ou escreve o teu curso."
    elif passo_id == "ensino":
        _ob_titulo("Onde ensinas?", "Para as turmas e os materiais que preparares virem ao nível certo.")
        onde = _ob_onde(prof=True)
        if onde == "secundario":
            acad["disciplinas"] = st.multiselect("Disciplinas que dás", ac.DISCIPLINAS_SECUNDARIO, key="ob_disc",
                                                 default=[d for d in acad.get("disciplinas", []) if d in ac.DISCIPLINAS_SECUNDARIO],
                                                 placeholder="Escolhe uma ou mais")
            if not acad["disciplinas"]:
                erro = "Escolhe pelo menos uma disciplina."
        else:
            erro = _ob_outra_instituicao() if onde == "outra" else None
            if acad.get("instituicao") == ac.UC:
                acad["departamentos"] = st.multiselect(
                    "Departamentos", ac.DEPARTAMENTOS_UC, key="ob_dep", placeholder="Escolhe um ou mais",
                    default=[d for d in acad.get("departamentos", []) if d in ac.DEPARTAMENTOS_UC])
            else:
                texto = st.text_input("Departamentos (separados por vírgulas)", value=", ".join(acad.get("departamentos", [])),
                                      key="ob_dep_livre")
                acad["departamentos"] = [d.strip() for d in texto.split(",") if d.strip()]
            if not erro and not acad.get("departamentos"):
                erro = "Escolhe pelo menos um departamento."
    elif passo_id == "ia":
        st.session_state._passo_ia_visto = True
        _ob_titulo("Liga a inteligência artificial", "Só tu vês isto, porque és quem gere a app: as outras pessoas usam-na sem chaves.")
        st.markdown("Precisas de uma chave **gratuita** do Google Gemini: vai a **aistudio.google.com**, entra com a tua "
                    "conta Google e carrega em **Get API key**. Também o podes fazer mais tarde no teu Perfil → Administração.")
        definicoes_ia(horizontal=True)
    return tabela, erro


def sincronizar_conta_com_perfil() -> None:
    """O nome e «aluno ou professor» escolhidos na primeira entrada passam para a conta (é o que as salas usam: os
    colegas veem o nome; os professores criam turmas)."""
    try:
        backend = obter_backend_salas()
        conta = backend.atual()
        if not conta:
            return
        if perfil.get("nome") and perfil["nome"] != conta.get("nome"):
            backend.mudar_perfil(nome=perfil["nome"])
        if acad.get("vinculo") in VINCULOS and acad["vinculo"] != conta.get("vinculo"):
            backend.mudar_vinculo(acad["vinculo"])
    except Exception:  # noqa: BLE001 — a primeira entrada nunca fica presa por causa das salas
        pass


# =============================================================== ecrã de entrada (início de sessão)
def _svg_url(svg: str) -> str:
    from urllib.parse import quote

    return "data:image/svg+xml;utf8," + quote(svg)


LOGO_GOOGLE = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 '
    '32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 13 4 4 13 4 24s9 20 '
    '20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 '
    '8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 '
    '35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.1H42V20H24v8'
    'h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"/></svg>')
LOGO_MICROSOFT = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 22 22"><path fill="#F25022" d="M1 1h9.5v9.5H1z"/><path fill="#7FBA00" '
    'd="M11.5 1H21v9.5h-9.5z"/><path fill="#00A4EF" d="M1 11.5h9.5V21H1z"/><path fill="#FFB900" d="M11.5 11.5H21V21h-9.5z"/></svg>')

LOGO_APPLE = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027'
    '-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935'
    '-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182'
    '-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 '
    '3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715'
    '-.688 3.559-1.701"/></svg>')
LOGO_FACEBOOK = _svg_url(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#0866FF" d="M9.101 23.691v-7.98H6.627v-3.667h2.474'
    'v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653'
    '-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752'
    'v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 '
    '12c0 5.628 3.874 10.35 9.101 11.647Z"/></svg>')

ESTILO_ONBOARDING = """<style>
/* primeira entrada: um cartão por pergunta, com os passos em cima (como no ecrã de entrada) */
div.st-key-ob_cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:22px; max-width:36rem;
  margin:0 auto; padding:1.5rem 1.9rem 1.3rem; box-shadow:0 1px 2px var(--sombra), 0 12px 32px var(--sombra); gap:0.85rem; }
.ob-passos { display:flex; align-items:center; gap:0.35rem; }
.ob-passos i { flex:1; height:4px; border-radius:2px; background:var(--linha); max-width:3.2rem; }
.ob-passos i.feito, .ob-passos i.agora { background:var(--acento); }
.ob-passos span { margin-left:auto; color:var(--suave); font-size:0.8rem; white-space:nowrap; }
h2.ob-titulo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important; font-weight:600 !important;
  font-size:1.55rem !important; letter-spacing:-0.015em; line-height:1.2; margin:0.5rem 0 0.25rem !important; padding:0 !important;
  color:var(--texto); text-wrap:balance; }
p.ob-sub { color:var(--suave); font-size:0.93rem !important; line-height:1.5; margin:0 0 0.5rem !important; }
div.st-key-ob_seguinte button { min-height:2.75rem; border-radius:12px; }
@media (max-width:640px) {
  div.st-key-ob_cartao { padding:1.2rem 1.1rem 1.1rem; border-radius:18px; }
}
</style>"""

ESTILO_ENTRAR = """<style>
.en-topo { margin:0.4rem 0 3.2vh; }
.en-titulo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important; font-weight:500; font-size:clamp(2rem, 3.3vw, 2.85rem) !important;
  line-height:1.08; letter-spacing:-0.02em; color:var(--texto); margin:0 0 0.9rem; text-align:center; }
p.en-sub { color:var(--suave); font-size:1.05rem !important; line-height:1.55; text-align:center; max-width:30rem; margin:0 auto 1.6rem !important; }
div.st-key-en_cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:22px; padding:1.4rem 1.4rem 1.1rem;
  box-shadow:0 1px 2px var(--sombra), 0 12px 32px var(--sombra); max-width:26rem; margin:0 auto; }
div.st-key-en_cartao .stButton > button, div.st-key-en_cartao [data-testid="stFormSubmitButton"] > button {
  min-height:2.85rem; border-radius:12px; font-size:0.97rem; }
div[class*="st-key-en_fornecedor_"] button { background:var(--cartao) !important; border:1px solid var(--linha) !important;
  color:var(--texto) !important; }
div[class*="st-key-en_fornecedor_"] button:hover { background:var(--bolha) !important; border-color:var(--suave) !important; }
div[class*="st-key-en_fornecedor_"] button p { color:var(--texto) !important; font-weight:500; }
div[class*="st-key-en_fornecedor_"] button > div { width:auto !important; flex:0 1 auto !important; }
div[class*="st-key-en_fornecedor_"] button::before { content:""; width:18px; height:18px; flex:none; margin-right:0.65rem;
  background:center / contain no-repeat; }
div.st-key-en_fornecedor_google button::before { background-image:url("GOOGLE"); }
div.st-key-en_fornecedor_microsoft button::before { background-image:url("MICROSOFT"); }
div.st-key-en_fornecedor_apple button::before { background:var(--texto);
  -webkit-mask:url("APPLE") center / contain no-repeat; mask:url("APPLE") center / contain no-repeat; }
div.st-key-en_fornecedor_facebook button::before { background-image:url("FACEBOOK"); }
.en-oauths { display:flex; flex-direction:column; gap:0.6rem; }
a.en-oauth { display:flex; align-items:center; justify-content:center; gap:0.65rem; min-height:2.6rem; border-radius:12px;
  border:1px solid var(--linha); background:var(--cartao); color:var(--texto) !important; text-decoration:none !important;
  font-weight:500; font-size:0.97rem; }
a.en-oauth:hover { background:var(--bolha); border-color:var(--suave); }
a.en-oauth::before { content:""; width:18px; height:18px; flex:none; background:center / contain no-repeat; }
a.en-oauth-google::before { background-image:url("GOOGLE"); }
a.en-oauth-microsoft::before { background-image:url("MICROSOFT"); }
a.en-oauth-facebook::before { background-image:url("FACEBOOK"); }
a.en-oauth-apple::before { background:var(--texto); -webkit-mask:url("APPLE") center / contain no-repeat;
  mask:url("APPLE") center / contain no-repeat; }
div.st-key-en_fornecedor_auth0 button::before { background-image:none; content:"+"; font-size:1.1rem; color:var(--suave);
  width:auto; height:auto; }
div.st-key-en_cartao { gap:0.6rem; }
div.st-key-en_cartao .stButton > button, div.st-key-en_cartao [data-testid="stFormSubmitButton"] > button { min-height:2.6rem !important; }
p.en-cartao-titulo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.45rem !important; color:var(--texto);
  text-align:center; margin:0 0 0.35rem !important; }
div.st-key-en_trocar button { justify-content:center; color:var(--suave) !important; }
div.st-key-en_trocar button p { color:var(--suave) !important; font-size:0.92rem; }
div.st-key-en_trocar button strong { color:var(--acento) !important; font-weight:600; }
div.st-key-en_trocar button:hover strong { text-decoration:underline; }
div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"] { background:var(--texto) !important; border-color:var(--texto) !important; }
div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"], div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"] *,
div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"]:not(:disabled):hover,
div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"]:not(:disabled):hover * { color:var(--fundo) !important; }
div.st-key-en_cartao [data-testid="stBaseButton-primaryFormSubmit"]:not(:disabled):hover { opacity:0.88; }
div.st-key-en_cartao [data-testid="stTextInputRootElement"] { min-height:2.85rem; border-radius:12px; }
div.st-key-en_cartao [data-testid="stForm"] { border:none; padding:0; }
.en-ou { display:flex; align-items:center; gap:0.8rem; color:var(--suave); font-size:0.78rem; letter-spacing:0.08em;
  text-transform:uppercase; margin:0.35rem 0 0.6rem; }
.en-ou::before, .en-ou::after { content:""; flex:1; height:1px; background:var(--linha); }
p.en-passo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.35rem !important; color:var(--texto); margin:0 0 0.15rem !important; }
p.en-email { color:var(--suave); font-size:0.9rem !important; margin:0 0 0.8rem !important; word-break:break-all; }
p.en-legal { color:var(--suave); font-size:0.78rem !important; line-height:1.5; text-align:center; max-width:24rem;
  margin:1rem auto 0 !important; }
/* pré-visualização da app à direita (como no ecrã de entrada do Claude) */
div.st-key-en_palco { border-radius:28px; padding:2rem 1.8rem; min-height:34rem; display:flex; flex-direction:column;
  justify-content:center; gap:1rem; position:relative; overflow:hidden;
  background:radial-gradient(120% 90% at 85% 10%, color-mix(in srgb, var(--logo-onda1) 22%, transparent), transparent 60%),
             radial-gradient(90% 80% at 10% 100%, color-mix(in srgb, var(--logo-onda2) 22%, transparent), transparent 60%),
             var(--lateral); border:1px solid var(--linha); }
.en-janela { background:var(--fundo); border:1px solid var(--linha); border-radius:18px; padding:1rem 1.1rem 1.1rem;
  box-shadow:0 18px 40px var(--sombra); }
.en-barra { display:flex; align-items:center; gap:0.35rem; margin-bottom:0.9rem; color:var(--suave); font-size:0.78rem; }
.en-barra i { width:9px; height:9px; border-radius:50%; background:var(--linha); display:block; }
.en-barra span { margin-left:0.4rem; }
.en-eu { margin-left:auto; width:fit-content; max-width:85%; background:var(--bolha); color:var(--texto); border-radius:16px;
  padding:0.55rem 0.85rem; font-size:0.92rem; margin-bottom:0.8rem; }
.en-resp { color:var(--texto); font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:0.98rem; line-height:1.6; }
.en-resp p { margin:0.5rem 0; }
.en-formula { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-style:italic; text-align:center; font-size:1.1rem; margin:0.6rem 0;
  padding:0.55rem; border-radius:10px; background:var(--cartao); border:1px solid var(--linha); }
.en-fonte { display:inline-block; font-family:'Inter', sans-serif; font-size:0.74rem; color:var(--suave); background:var(--bolha);
  border-radius:999px; padding:0.15rem 0.55rem; }
.en-minis { display:grid; grid-template-columns:1fr 1fr; gap:0.8rem; margin-top:1rem; }
.en-resp .mi-estado, .en-resp .mi-fonte { font-family:'Inter', sans-serif; }
.en-mini { background:var(--fundo); border:1px solid var(--linha); border-radius:14px; padding:0.75rem 0.9rem; }
.en-mini b { display:block; font-size:0.72rem; letter-spacing:0.06em; text-transform:uppercase; color:var(--suave); font-weight:600; }
.en-mini span { display:block; color:var(--texto); font-size:0.95rem; margin-top:0.2rem; }
@media (max-width: 900px) {  /* tablet e telemóvel: só o cartão, centrado e na largura toda */
  div[data-testid="stColumn"]:has(div.st-key-en_palco) { display:none !important; }
  div[data-testid="stHorizontalBlock"]:has(div.st-key-en_palco) > div[data-testid="stColumn"] {
    flex:1 1 100% !important; width:100% !important; max-width:100% !important; }
  .en-topo { margin-bottom:2vh; }
}
</style>""".replace("GOOGLE", LOGO_GOOGLE).replace("MICROSOFT", LOGO_MICROSOFT).replace("APPLE", LOGO_APPLE) \
    .replace("FACEBOOK", LOGO_FACEBOOK)

PREVISAO_ENTRAR = (
    '<div class="en-janela"><div class="en-barra"><i></i><i></i><i></i><span>Assistente</span></div>'
    '<div class="en-eu">Explica-me a regra da cadeia com um exemplo.</div><div class="en-resp">'
    + idt.pensar_html("A ler 2 fontes", tipo="ler", fontes=["Sebenta de Cálculo I", "Aula 7"])
    + '<p>Para derivar uma função composta, derivas a função de fora e multiplicas pela derivada da de dentro:</p>'
    '<div class="en-formula">(f ∘ g)′(x) = f′(g(x)) · g′(x)</div>'
    '<p>Por exemplo, para sen(x²): cos(x²) · 2x. <span class="en-fonte">Sebenta de Cálculo I, p. 42</span></p></div></div>'
    '<div class="en-minis"><div class="en-mini"><b>Flashcards</b><span>12 para rever hoje</span></div>'
    '<div class="en-mini"><b>Próxima avaliação</b><span>Exame de Álgebra · 3 dias</span></div>'
    '<div class="en-mini"><b>Plano de estudo</b><span>Hoje: Matrizes, 45 min</span></div>'
    '<div class="en-mini"><b>Salas</b><span>Grupo de Física · 5 colegas</span></div></div>'
)


PASSOS_FORNECEDOR = {
    "google": [
        "Abre [console.cloud.google.com](https://console.cloud.google.com/) e cria um projeto (por exemplo, *Mondego IA*).",
        "Configura o ecrã de consentimento OAuth: tipo **Externo**, nome *Mondego IA* e o teu email. Para qualquer conta "
        "Google poder entrar, carrega em **Publicar app** (com só o email e o perfil, a Google não pede verificação); "
        "enquanto estiver em teste, só entram os **utilizadores de teste**.",
        "Cria um **ID do cliente OAuth** do tipo **Aplicação Web**, com este URI de redirecionamento autorizado: `{uri}`",
        "Copia o **ID do cliente** e o **segredo do cliente** para aqui.",
    ],
    "microsoft": [
        "Abre [portal.azure.com](https://portal.azure.com/) → **Microsoft Entra ID** → **Registos de aplicações** → "
        "**Novo registo** (a conta do Azure é grátis).",
        "Nome *Mondego IA*; tipos de conta: **Apenas contas Microsoft pessoais** (Outlook, Hotmail, Live); URI de "
        "redirecionamento: **Web**, `{uri}`",
        "Copia o **ID da aplicação (cliente)** da página **Descrição geral**.",
        "Em **Certificados e segredos** → **Novo segredo do cliente**, copia o **Valor** (só aparece uma vez).",
    ],
    "auth0": [
        "O {nome} não usa o padrão que o Streamlit aceita, por isso entra através do **Auth0** (grátis): cria uma conta em "
        "[auth0.com](https://auth0.com/) → **Applications** → **Create Application** → **Regular Web Application**.",
        "Em **Settings**, põe em **Allowed Callback URLs**: `{uri}` e copia o **Domain**, o **Client ID** e o **Client Secret**.",
        "Em **Authentication** → **Social**, ativa o **{nome}** e segue os passos que o Auth0 mostra.{extra}",
        "Escreve aqui o domínio, o Client ID e o Client Secret (se já ligaste o Facebook ou o Apple, os dois primeiros "
        "já vêm preenchidos).",
    ],
}


def _configurar_fornecedor(f: str) -> None:
    nome = isess.FORNECEDORES[f]
    st.markdown(f"Para o botão **Continuar com {nome}** funcionar neste computador, a app precisa de credenciais grátis "
                f"do {nome}. Só tens de fazer isto uma vez: depois, carregas no botão, escolhes a tua conta e pronto.")
    if not authlib_instalado():
        st.warning("Primeiro instala a biblioteca de autenticação: fecha a app e corre no PowerShell "
                   "`py -3.14 -m pip install Authlib`.", icon=":material/download:")
    extra = " O Apple só funciona com uma conta de programador da Apple (que é paga)." if f == "apple" else ""
    passos = PASSOS_FORNECEDOR["auth0" if f in isess.PELO_AUTH0 else f]
    st.markdown("\n".join(f"{i}. " + p_.format(uri=isess.REDIRECT_PADRAO, nome=nome, extra=extra)
                          for i, p_ in enumerate(passos, 1)))
    caminho = PASTA / ".streamlit" / "secrets.toml"
    try:
        atual = isess.ler_toml(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    except Exception:  # noqa: BLE001 — ficheiro estragado: começa de novo (só a secção [auth] muda)
        atual = {}
    dominio = ""
    if f in isess.PELO_AUTH0:
        ja = isess.dados_auth0(atual)
        dominio = st.text_input("Domínio do Auth0", value=ja.get("dominio", ""), placeholder="o-teu-nome.eu.auth0.com",
                                key=f"en_cfg_{f}_dominio")
        cid = st.text_input("Client ID", value=ja.get("client_id", ""), key=f"en_cfg_{f}_id")
        segredo = st.text_input("Client Secret", type="password", key=f"en_cfg_{f}_segredo")
    else:
        cid = st.text_input("ID da aplicação (cliente)" if f == "microsoft" else "ID do cliente", key=f"en_cfg_{f}_id",
                            placeholder="….apps.googleusercontent.com" if f == "google" else "")
        segredo = st.text_input("Segredo do cliente", type="password", key=f"en_cfg_{f}_segredo")
    st.caption("Ficam guardados em `.streamlit/secrets.toml`, só neste computador. Esse ficheiro nunca é partilhado nem "
               "entra na exportação dos teus dados.")
    if st.button("Guardar", type="primary", icon=":material/save:", width="stretch", key=f"en_cfg_{f}_guardar"):
        erro = isess.validar(f, cid, segredo, dominio)
        if erro:
            st.error(erro)
            return
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(isess.para_toml(isess.com_fornecedor(atual, f, cid, segredo, dominio)), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            st.error(f"Não consegui guardar o ficheiro: {e}")
            return
        for k in ("id", "segredo", "dominio"):
            st.session_state.pop(f"en_cfg_{f}_{k}", None)
        st.success(f"Guardado. Fecha a app (Ctrl+C no PowerShell) e volta a abri-la: o botão «Continuar com {nome}» "
                   "passa a funcionar.", icon=":material/check_circle:")


def _fazer_dialogo(f: str):
    def corpo() -> None:
        _configurar_fornecedor(f)
    corpo.__name__ = f"configurar_{f}"
    return janela(f"Entrar com {isess.FORNECEDORES[f]}", width="medium")(corpo)


DIALOGOS_FORNECEDOR = {f: _fazer_dialogo(f) for f in isess.FORNECEDORES}


def concluir_entrada(backend, lembrar: bool) -> None:
    if lembrar:
        lembrar_sessao(backend)
    conta = backend.atual() or {}
    if nome_real_da_conta(conta) and not perfil.get("nome"):
        perfil["nome"] = conta["nome"]
        guardar_perfil()
    st.session_state.pop("en_modo", None)
    st.rerun()


def fornecedores_supabase(backend) -> list:
    """Fornecedores ligados no painel do Supabase (pergunta no máximo a cada 5 minutos)."""
    guardado = isess.CACHE_FORNECEDORES.get(backend.url)
    if guardado and time.time() - guardado[0] < 300:
        return guardado[1]
    try:
        ativos = backend.fornecedores_ativos()
    except Exception:  # noqa: BLE001
        ativos = []
    isess.CACHE_FORNECEDORES[backend.url] = (time.time(), ativos)
    return ativos


def botoes_fornecedores() -> bool:
    """Google, Microsoft, Apple e Facebook, como nas outras apps: carregas, escolhes a conta e entras. Só aparecem os que
    o administrador já ligou; as credenciais nunca aparecem aos utilizadores. Com o Supabase (app publicada), quem trata
    da entrada é o Supabase; sem ele, o login do Streamlit."""
    backend = obter_backend_salas()
    if backend.nome == "supabase":
        ativos = fornecedores_supabase(backend)
        if not ativos:
            return False
        if "_pkce" not in st.session_state or st.session_state._pkce[0] not in isess.PKCE:
            estado_, _verificador, desafio_ = isess.novo_pkce()
            st.session_state._pkce = (estado_, desafio_)
        estado_, desafio_ = st.session_state._pkce
        # O regresso é o endereço da app tal e qual (é o que se põe no Supabase); o estado vai num cookie de 15 min.
        regresso = url_da_app() + "/"
        ligacoes = "".join(f'<a class="en-oauth en-oauth-{f}" href="{escape(backend.url_oauth(f, regresso, desafio_))}" '
                           f'target="_self">Continuar com {isess.FORNECEDORES[f]}</a>' for f in ativos)
        st.markdown(f'<div class="en-oauths">{ligacoes}</div>', unsafe_allow_html=True)
        try:  # o Streamlit abre as ligações noutro separador: estas ficam no mesmo (como nas outras apps)
            components.html(isess.js_cookie(estado_, dias=1 / 96, nome=isess.NOME_COOKIE_PKCE)
                            + "<script>(function(){var n=0,t=setInterval(function(){try{window.parent.document"
                            ".querySelectorAll('a.en-oauth').forEach(function(a){a.target='_self';a.removeAttribute('rel');});}"
                            "catch(e){}if(++n>20)clearInterval(t);},250);})();</script>", height=0)
        except Exception:  # noqa: BLE001
            pass
        return True
    prontos = fornecedores_login() if authlib_instalado() else []
    for f, nome in isess.FORNECEDORES.items():
        if f in prontos:
            st.button(f"Continuar com {nome}", key=f"en_fornecedor_{f}", width="stretch", on_click=st.login, args=(f,))
    if "auth0" in prontos:  # configuração antiga do exemplo (uma só entrada pelo Auth0)
        st.button("Continuar com outra conta", key="en_fornecedor_auth0", width="stretch", on_click=st.login,
                  args=("auth0",))
    return bool(prontos)


def ecra_entrar() -> None:
    """Ecrã de entrada ao abrir a app, como nas outras apps: «Iniciar sessão» com Google, Microsoft, Apple, Facebook ou
    email e palavra-passe, e em baixo «Ainda não tens conta? Criar conta». À direita, uma pré-visualização da app.
    A conta serve para tudo (também nas Salas e no 3D Studio)."""
    import salas_backend as sb

    st.markdown(ESTILO_ENTRAR, unsafe_allow_html=True)
    st.markdown(f"<div class='en-topo'>{idt.logo_html('md')}</div>", unsafe_allow_html=True)
    esq, dir_ = st.columns([1, 1.08], gap="large", vertical_alignment="center")
    backend = obter_backend_salas()
    modo = st.session_state.get("en_modo", "entrar")
    with esq:
        st.markdown("<h1 class='en-titulo'>Estuda com a tua matéria.</h1>"
                    "<p class='en-sub'>Explica, resume e prepara-te para as avaliações com os teus próprios apontamentos."
                    "</p>", unsafe_allow_html=True)
        with st.container(key="en_cartao"):
            st.markdown(f"<p class='en-cartao-titulo'>{'Criar conta' if modo == 'criar' else 'Iniciar sessão'}</p>",
                        unsafe_allow_html=True)
            erro_entrada = st.session_state.pop("_erro_entrada", None)
            if erro_entrada:
                st.error(erro_entrada)
            aviso_entrada = st.session_state.pop("_aviso_entrada", None)
            if aviso_entrada:
                st.info(aviso_entrada, icon=":material/mark_email_unread:")
            if botoes_fornecedores():
                st.markdown("<div class='en-ou'>ou</div>", unsafe_allow_html=True)
            if modo == "criar":
                # só o email e a palavra-passe: «aluno ou professor» e o nome vêm a seguir, já dentro da app
                with st.form("en_form_criar", border=False):
                    email = st.text_input("Email", key="en_email_c", placeholder="Email", label_visibility="collapsed",
                                          autocomplete="email")
                    pp = st.text_input("Palavra-passe", type="password", key="en_pp_novo", autocomplete="new-password",
                                       placeholder="Palavra-passe (mínimo 8 caracteres)", label_visibility="collapsed")
                    lembrar = st.checkbox("Manter a sessão iniciada neste dispositivo", value=True, key="en_lembrar_novo")
                    if st.form_submit_button("Criar conta", type="primary", width="stretch"):
                        try:
                            backend.registar(email, pp, (email or "").strip().lower(), acad.get("vinculo") or "Aluno")
                            concluir_entrada(backend, lembrar)
                        except sb.ContaPorConfirmar as aviso:  # online: confirmar o email primeiro
                            st.session_state.en_modo = "entrar"
                            st.session_state._aviso_entrada = str(aviso)
                            st.rerun()
                        except sb.ErroSalas as erro:
                            st.error(str(erro))
                troca = "Já tens conta? **Iniciar sessão**"
            else:
                with st.form("en_form_entrar", border=False):
                    email = st.text_input("Email", key="en_email_e", placeholder="Email", label_visibility="collapsed",
                                          autocomplete="email")
                    pp = st.text_input("Palavra-passe", type="password", key="en_pp", placeholder="Palavra-passe",
                                       label_visibility="collapsed", autocomplete="current-password")
                    lembrar = st.checkbox("Manter a sessão iniciada neste dispositivo", value=True, key="en_lembrar")
                    if st.form_submit_button("Iniciar sessão", type="primary", width="stretch"):
                        try:
                            backend.entrar(email, pp)
                            concluir_entrada(backend, lembrar)
                        except sb.ErroSalas as erro:
                            existe = getattr(backend, "existe", None)
                            if existe and sb.EMAIL_RE.match((email or "").strip()) and not existe(email):
                                st.error("Não há nenhuma conta com este email. Carrega em «Criar conta», aqui em baixo.")
                            else:
                                st.error(str(erro))
                troca = "Ainda não tens conta? **Criar conta**"
            if st.button(troca, type="tertiary", key="en_trocar", width="stretch"):
                st.session_state.en_modo = "entrar" if modo == "criar" else "criar"
                st.rerun()
        st.markdown("<p class='en-legal'>Os teus apontamentos, conversas e estatísticas ficam guardados na tua conta e só "
                    "tu os vês. Podes descarregá-los ou apagá-los a qualquer momento no teu Perfil → Os teus dados.</p>",
                    unsafe_allow_html=True)
    with dir_:
        with st.container(key="en_palco"):
            st.markdown(PREVISAO_ENTRAR, unsafe_allow_html=True)


escrever_cookie_pendente()
if st.session_state.get("_importado"):
    st.toast(st.session_state.pop("_importado"), icon=":material/check_circle:")
if conta_entrada and perfil.get("concluido") and st.session_state.pop("_boas_vindas", False):
    st.toast("Está tudo pronto. Cria a tua primeira " + ("turma" if acad.get("vinculo") == "Professor" else "sala") +
             " em Salas.", icon=":material/waving_hand:")
if st.session_state.pop("_aviso_nuvem", None):
    st.toast("Sem ligação à cópia online dos teus dados: estás a ver o que está neste servidor. "
             "O que mudares sobe quando a ligação voltar.", icon=":material/cloud_off:")
so_academico = perfil.get("concluido") and st.session_state.get("editar_academico")

# =============================================================== área principal: um contentor por menu
# Cada troca de menu tem de deixar o ecrã limpo de imediato. Sem isto, o Streamlit reaproveita os elementos do
# menu anterior pela posição e mantém-nos visíveis (esbatidos) até o novo menu acabar de ser desenhado.
vista_desenhada = ("entrar" if not conta_entrada else
                   "perguntas" if (not perfil.get("concluido") or so_academico) else st.session_state.vista)
# o "ecrã" inclui o que está aberto dentro do menu: mudar de cadeira, de conversa ou de sala também é trocar de ecrã
ecra = (vista_desenhada, {"cadeira": st.session_state.get("cadeira_atual"), "chat": st.session_state.get("conversa_id"),
                          "salas": st.session_state.get("sala_aberta"), "laboratorio": st.session_state.get("lab_area"),
                          "estudio3d": (st.session_state.get("e3d_secao"), st.session_state.get("e3d_aberto"),
                                        st.session_state.get("e3d_ver"))}.get(vista_desenhada))
mudou_de_vista = st.session_state.get("_ecra_desenhado") != ecra
st.session_state._ecra_desenhado = ecra
LARGURAS = {"entrar": 1180, "perguntas": 800, "chat": 800, "cadeira": 1200, "estudio3d": 1360, "laboratorio": 1200, "perfil": 1100, "definicoes": 1120}
# Animação de entrada ao abrir a app (uma vez por abertura). Continua a ser enviada nos primeiros segundos para não
# ser cortada a meio se houver outra execução logo a seguir (ex.: o calendário a carregar).
st.session_state.setdefault("_intro_inicio", time.time())
mostrar_intro = time.time() - st.session_state._intro_inicio < 3.5 and bool(cfg.get("intro", True))
# Sempre um só bloco de estilo, na mesma posição: a largura nunca fica "presa" no valor do menu anterior.
# Na execução que troca de menu, esconde também o que sobrar do menu anterior (diálogos, caixa de conversa fixa
# no fundo, mensagens) — nas outras execuções o Streamlit continua a esbater normalmente.
st.markdown(f"<style>.block-container{{max-width:{LARGURAS.get(vista_desenhada, 1100)}px;}}"
            # o iframe (vazio) que põe a animação de entrada na página não ocupa espaço
            '[data-testid="stElementContainer"]:has(iframe[srcdoc*="mi-intro-css"]) {position:absolute !important; '
            'width:0 !important; height:0 !important; overflow:hidden !important; margin:0 !important;}'
            + (':is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-stale="true"], [data-testid="stBottom"] [data-stale="true"], '
               '[data-testid="stDialog"][data-stale="true"], [data-stale="true"] [data-testid="stDialog"] '
               '{display:none !important;}' if mudou_de_vista else "") + "</style>"
            # fundo da animação logo no primeiro instante (o script da animação esconde-o quando entra)
            + (idt.capa_html() if mostrar_intro else ""), unsafe_allow_html=True)
if mostrar_intro:
    # A animação de entrada vai para o documento da página por um script (uma vez por abertura). Antes era um
    # elemento do Streamlit: cada nova execução nos primeiros segundos escondia-o, recomeçava-o ou cortava-o a meio.
    try:
        components.html(idt.intro_js(), height=0)
    except Exception:  # noqa: BLE001
        pass
# Ao mudar de menu, o st.empty() substitui de uma vez o contentor do menu anterior (com tudo o que tinha dentro)
# e o novo contentor começa vazio: nada do menu antigo (separadores abertos, expansores, texto escrito) passa
# para o novo. Nas outras execuções usa-se o mesmo contentor, para não perder o estado dos widgets.
principal = (st.empty() if mudou_de_vista else st).container(key=f"vista_{vista_desenhada}")
principal.__enter__()  # tudo o que os menus desenham a seguir fica dentro deste contentor (st.stop() termina a execução)


@contextmanager
def fixo_no_fundo():
    """A caixa de conversa só fica fixa no fundo da página quando é criada fora de qualquer contentor."""
    principal.__exit__(None, None, None)
    try:
        yield
    finally:
        principal.__enter__()


if not conta_entrada:  # ecrã de entrada, como nas outras apps (Google, Microsoft, email)
    ecra_entrar()
    st.stop()

if not perfil.get("concluido") or so_academico:
    passos = passos_onboarding(bool(so_academico))
    passo = min(st.session_state.passo, len(passos) - 1)
    st.markdown(ESTILO_ONBOARDING + f'<div class="mi-logo-centro">{idt.logo_html("lg")}</div>', unsafe_allow_html=True)
    with st.container(key="ob_cartao"):
        st.markdown(f"<div class='ob-passos' role='img' aria-label='Passo {passo + 1} de {len(passos)}'>" +
                    "".join(f"<i class='{'feito' if i < passo else 'agora' if i == passo else ''}'></i>" for i in range(len(passos)))
                    + f"<span>Passo {passo + 1} de {len(passos)}</span></div>", unsafe_allow_html=True)
        tabela, erro = ecra_onboarding(passos[passo])
        # a resposta deste ecrã pode mudar os passos seguintes (ex.: «Professor» pergunta onde ensina)
        passos = passos_onboarding(bool(so_academico))
        ultimo = passo == len(passos) - 1
        c1, c2 = st.columns([1, 1], vertical_alignment="center")
        if passo > 0 and c1.button("Voltar", type="tertiary", icon=":material/arrow_back:", key="ob_voltar"):
            st.session_state.passo = passo - 1
            st.rerun()
        if c2.button(("Guardar" if so_academico else "Começar a usar") if ultimo else "Continuar", type="primary",
                     width="stretch", key="ob_seguinte"):
            if erro:
                st.error(erro, icon=":material/error:")
            else:
                perfil["academico"] = acad
                guardar_perfil()
                if ultimo:
                    perfil["concluido"] = True
                    acad["completo"] = True
                    guardar_perfil()
                    sincronizar_conta_com_perfil()
                    st.session_state.passo = 0
                    if not so_academico:
                        st.session_state._boas_vindas = True
                    st.session_state.pop("editar_academico", None)
                    ir("inicio")
                st.session_state.passo = passo + 1
                st.rerun()
    if so_academico and st.button("Cancelar", type="tertiary", key="ob_cancelar"):
        st.session_state.pop("editar_academico", None)
        st.session_state.passo = 0
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- usados na barra lateral (avisos e cronómetro)
def fmt_duracao(segundos: float) -> str:
    m = int(segundos // 60)
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


# ---------------------------------------------------------------- avisos (notificações dentro da app)
def temas_fracos() -> list:
    """[(cadeira, tema)]: em cada cadeira, o tema com pior percentagem nos quizzes (pelo menos 2 perguntas, menos de 60%)."""
    fracos = []
    for nome_c, d in st.session_state.cadeiras.items():
        pior = None
        for tema_, (certas_, total_) in (d.get("quiz_temas") or {}).items():
            if total_ >= 2 and certas_ / total_ < 0.6 and (pior is None or certas_ / total_ < pior[1]):
                pior = (tema_, certas_ / total_)
        if pior:
            fracos.append((nome_c, pior[0], pior[1]))
    return [(c, t) for c, t, _ in sorted(fracos, key=lambda x: x[2])]


def por_ler_na_sala(backend, sala: dict, eu: str | None) -> int:
    """Mensagens de colegas desde a última vez que abriste a conversa desta sala (0 se nunca a abriste)."""
    import salas as sl_p

    desde = (perfil.get("salas_vistas") or {}).get(sala["id"])
    if not desde or not sl_p.chat_ativo(sala):
        return 0
    try:
        return dfs.mensagens_novas(backend.mensagens(sala["id"], 50), desde, eu)
    except Exception:  # noqa: BLE001
        return 0


def salas_com_mensagens_novas() -> list:
    """[(id, nome, n)]: mensagens de colegas desde a última vez que abriste a conversa de cada sala (no máximo 6 salas)."""
    vistas = perfil.get("salas_vistas") or {}
    if not vistas:
        return []
    try:
        backend = obter_backend_salas()
        conta = backend.atual()
        if not conta:
            return []
        resultado = []
        for sala_ in backend.minhas_salas()[:6]:
            if sala_["id"] not in vistas:
                continue
            n = dfs.mensagens_novas(backend.mensagens(sala_["id"], 50), vistas[sala_["id"]], conta["id"])
            if n:
                resultado.append((sala_["id"], sala_["nome"], n))
        return resultado
    except Exception:  # noqa: BLE001 — os avisos nunca impedem o Início de abrir
        return []


def avisos_de_hoje(com_salas: bool = True) -> list:
    hoje_ = date.today()
    vistos = dfs.limpar_vistos(perfil.get("avisos_vistos"), hoje_)
    if vistos != (perfil.get("avisos_vistos") or {}):
        perfil["avisos_vistos"] = vistos
    sessoes_h = sessoes_do_dia(hoje_)
    atrasadas_ = sum(1 for s_ in av.sessoes_de_estudo(perfil, st.session_state.cadeiras)
                     if s_["data"] < hoje_.isoformat() and not s_["feita"])
    por_rever = [(rs.resumo(d.get("cartoes") or [], hoje_)["para_hoje"], n) for n, d in st.session_state.cadeiras.items()
                 if d.get("cartoes")]
    cartoes_ = sum(x for x, _ in por_rever)
    return dfs.avisos(hoje_, cfg, repo().proximas(), (sum(x["feita"] for x in sessoes_h), len(sessoes_h)), atrasadas_,
                      cartoes_, max(por_rever)[1] if cartoes_ else None, temas_fracos(),
                      salas_com_mensagens_novas() if com_salas else [], vistos)


def dispensar_aviso(ident: str) -> None:
    perfil.setdefault("avisos_vistos", {})[ident] = date.today().isoformat()
    guardar_perfil()


def registar_foco(minutos: float, cadeira: str | None = None) -> None:
    if minutos < 1:
        return
    perfil.setdefault("foco", []).append({"data": date.today().isoformat(), "hora": datetime.now().strftime("%H:%M"),
                                          "cadeira": cadeira, "minutos": round(minutos)})
    guardar_perfil()


def minutos_foco_hoje() -> int:
    return sum(f.get("minutos", 0) for f in perfil.get("foco", []) if f.get("data") == date.today().isoformat())


def tratar_evento_crono(valor, chave: str) -> None:
    ev = evento(valor, chave)
    if ev and ev.get("evento") == "foco":
        registar_foco(float(ev.get("minutos") or 0), ev.get("cadeira") if ev.get("cadeira") in st.session_state.cadeiras else None)
        st.toast(f"Sessão de foco registada: {ev.get('minutos')} min.", icon=":material/timer:")


def cronometro_mini() -> None:
    """Na barra lateral (fora do Início): só aparece enquanto o cronómetro conta; regista os minutos quando acaba."""
    valor = componente("crono", "crono_mini", 0, cadeiras=list(st.session_state.cadeiras), mini=True,
                       comando=st.session_state.pop("crono_cmd", None))
    tratar_evento_crono(valor, "crono_mini")



# =============================================================== barra lateral
if not ESTUDIO_3D and st.session_state.vista == "estudio3d":
    st.session_state.vista = "inicio"
vista = st.session_state.vista
AREAS_LAB = {
    "fisica": (":material/rocket_launch:", "Física", "Mecânica, eletricidade, ondas, ótica, termodinâmica… A IA explica "
               "tudo e faz uma simulação quando pedires."),
    "quimica": (":material/science:", "Química", "IA que explica Química, mais tabela periódica, massa molar, acerto de "
                "equações e moléculas em 3D."),
    "matematica": (":material/function:", "Matemática", "IA que explica e resolve passo a passo, mais gráficos 2D e 3D "
                   "de funções."),
    "biologia": (":material/genetics:", "Biologia e Anatomia", "IA que explica Biologia e Anatomia, mais do DNA à proteína "
                 "e quadrados de Punnett."),
    "historia": (":material/public:", "História e Geografia", "IA que explica História e Geografia, com linhas do tempo "
                 "e mapas feitos a pedido."),
    "programacao": (":material/code:", "Programação", "IA que explica programação e algoritmos, mais Python no browser "
                    "com exercícios."),
}
CHAVE_SECCAO_LAB = {"quimica": "lab_quim", "matematica": "lab_mat", "biologia": "lab_bio", "historia": "lab_hist",
                    "programacao": "lab_prog"}
# Navegação principal (como nas melhores apps de IA): nova conversa, pesquisa, os sítios da app e as conversas
# recentes. O Laboratório deixou de ser uma página: é uma opção de cada sala (Salas → Criar sala → Laboratório).
# As cadeiras passaram a ser salas (só tuas): já não há um menu «Cadeiras», tudo está em «Salas».
SEPARADORES = [("inicio", "Início", ":material/home:"), ("salas", "Salas", ":material/groups:"), ("calendario", "Calendário", ":material/calendar_month:"),
               ("estudio3d", "3D Studio", ":material/view_in_ar:")]
if not ESTUDIO_3D:
    SEPARADORES = [s_ for s_ in SEPARADORES if s_[0] != "estudio3d"]
if vista in ("laboratorio", "cadeiras"):  # endereços antigos: o Laboratório e as cadeiras estão agora nas salas
    vista = st.session_state.vista = "salas"
SEPARADOR_DE = {"inicio": "inicio", "calendario": "calendario", "salas": "salas", "cadeira": "salas", "chat": "chat", "estudio3d": "estudio3d", "perfil": "perfil", "definicoes": "definicoes"}
separador = SEPARADOR_DE.get(vista, "inicio")
with st.sidebar:
    st.markdown(f'<div class="mi-logo-lateral">{idt.logo_html("md")}</div>', unsafe_allow_html=True)
    st.button("Nova conversa", key="nova_conversa_lateral", icon=":material/edit_square:", on_click=navegar,
              args=("chat",), kwargs={"conversa_id": None}, help="Começar uma conversa nova com o assistente")
    consulta_c = st.text_input("Pesquisar conversas", key="conv_pesquisa", placeholder="Pesquisar conversas",
                               label_visibility="collapsed", icon=":material/search:") if conversas else ""
    for chave_sep, rotulo, icone in SEPARADORES:
        st.button(rotulo, key=f"sep_{chave_sep}", icon=icone, type="secondary" if separador == chave_sep else "tertiary",
                  on_click=navegar, args=(chave_sep,), kwargs={"estudio3d": {"e3d_ver": None}}.get(chave_sep, {}))

    etiquetas_laterais = []  # (chave do botão, texto à direita, em destaque?)
    if UID and separador != "inicio" and perfil.get("concluido"):
        try:  # quantos avisos esperam no Início (as salas só se contam no próprio Início)
            _avisos_l = avisos_de_hoje(com_salas=False)
            if _avisos_l:
                etiquetas_laterais.append(("sep_inicio", str(len(_avisos_l)), any(a_["urgente"] for a_ in _avisos_l)))
        except Exception:  # noqa: BLE001
            pass
    if UID and separador != "inicio":
        cronometro_mini()

    def faltam_curto(r_: dict) -> str:
        dias_ = av.dias_ate(r_, date.today())
        return "hoje" if dias_ <= 0 else "amanhã" if dias_ == 1 else f"{dias_} dias"

    if separador == "salas":  # as salas da pessoa (só tuas e partilhadas), para saltar entre elas
        try:
            backend_l = obter_backend_salas()
            conta_l = backend_l.atual()
            salas_l = backend_l.minhas_salas() if conta_l else []
        except Exception:  # noqa: BLE001 — a barra lateral nunca falha por causa das salas
            conta_l, salas_l = None, []
        import salas as _sl_nav

        # as só tuas primeiro, pela avaliação mais próxima (como estavam as cadeiras), depois as partilhadas
        pessoais_l = sorted(st.session_state.cadeiras, key=lambda n_: (data_avaliacao(st.session_state.cadeiras[n_]) or date.max,
                                                                       dz._sem_acentos(n_)))
        botoes_l = [("p", sala_pessoal(n_)) for n_ in pessoais_l[:10]] + [("s", s_) for s_ in salas_l[:8]]
        if botoes_l:  # cada sala com o seu ícone na cor dela (como na página Salas)
            cores_nav = "".join(f".st-key-navsala_{re.sub(r'[^A-Za-z0-9_-]', '-', str(s_['id']))}"
                                f"{{--c:{s_.get('cor_hex') or _sl_nav.CORES_SALA.get(s_.get('cor') or 'turquesa', '#2AA5B8')}}}"
                                for _, s_ in botoes_l)
            st.markdown(f'<div class="ec-secao">As tuas salas</div><style>{cores_nav}</style>', unsafe_allow_html=True)
        por_rever = []
        for tipo_l, sala_ in botoes_l:
            chave_l = f"navsala_{sala_['id']}"
            if tipo_l == "p":
                nome = sala_["nome"]
                ativa = vista == "cadeira" and st.session_state.get("cadeira_atual") == nome
                st.button(curto(nome, 26), key=chave_l, icon=f":material/{_sl_nav.icone_da_sala(sala_)}:",
                          type="secondary" if ativa else "tertiary", help=nome if len(nome) > 26 else None,
                          on_click=navegar, args=("cadeira",), kwargs={"cadeira_atual": nome})
                prox_l = repo().proxima(nome)
                if prox_l:
                    etiquetas_laterais.append((chave_l, faltam_curto(prox_l), av.dias_ate(prox_l, date.today()) <= 3))
                cartoes_l = st.session_state.cadeiras[nome].get("cartoes") or []
                if cartoes_l:
                    por_rever.append((rs.resumo(cartoes_l, date.today())["para_hoje"], nome))
            else:
                aberta_ = vista == "salas" and st.session_state.get("sala_aberta") == sala_["id"]
                st.button(curto(sala_["nome"], 26), key=chave_l, icon=f":material/{_sl_nav.icone_da_sala(sala_)}:",
                          type="secondary" if aberta_ else "tertiary", on_click=navegar, args=("salas",),
                          kwargs={"sala_aberta": sala_["id"]})
        st.button("Nova sala", icon=":material/add:", key="nav_criar_sala", type="tertiary", on_click=navegar,
                  args=("salas",), kwargs={"sala_aberta": None, "salas_dialogo": "criar"})
        if conta_l:
            st.button("Entrar numa sala", icon=":material/login:", key="nav_entrar_sala", type="tertiary",
                      on_click=navegar, args=("salas",), kwargs={"sala_aberta": None, "salas_dialogo": "entrar"})
        total_rever = sum(n_ for n_, _ in por_rever)
        if total_rever:
            mais_l = max(por_rever)[1]
            st.button("Rever flashcards", key="nav_rever_cartoes", icon=":material/style:", type="tertiary",
                      help=f"Começa por {mais_l}", on_click=navegar, args=("cadeira",),
                      kwargs={"cadeira_atual": mais_l, "ferramenta_pendente": "Flashcards"})
            etiquetas_laterais.append(("nav_rever_cartoes", str(total_rever), False))

    # ---------- conversas recentes (sempre visíveis, como no Claude), fixadas primeiro e por data
    if conversas:
        grupos_c, escondidas_c = hc.agrupar(conversas, date.today(), consulta_c or "",
                                              None if st.session_state.get("conv_todas") else
                                              (hc.LIMITE if separador == "chat" else 12))
        if not grupos_c:
            st.caption("Nenhuma conversa encontrada.")
        for grupo_c, itens_c in grupos_c:
            st.markdown(f'<div class="ec-secao">{escape(grupo_c)}</div>', unsafe_allow_html=True)
            for cid, conv in itens_c:
                ativa = vista == "chat" and st.session_state.conversa_id == cid
                st.button(conv.get("titulo") or "Conversa", key=f"conv_{cid}", type="secondary" if ativa else "tertiary",
                          icon=":material/push_pin:" if conv.get("fixada") else None, help=conv.get("titulo"),
                          on_click=navegar, args=("chat",), kwargs={"conversa_id": cid})
        if escondidas_c or st.session_state.get("conv_todas"):
            st.button("Mostrar menos" if st.session_state.get("conv_todas") else f"Mostrar todas (mais {escondidas_c})",
                      key="conv_mais", type="tertiary", icon=":material/unfold_less:" if st.session_state.get("conv_todas")
                      else ":material/unfold_more:", on_click=lambda: st.session_state.update(
                          conv_todas=not st.session_state.get("conv_todas")))

    estilo_etiquetas = "".join(
        f'.st-key-{k_} button::after {{ content:"{t_}"; padding:0 0.5rem; '
        + ("background:var(--acento-claro); color:var(--acento-esc);" if urg_ else "background:var(--bolha); color:var(--suave);")
        + "}" for k_, t_, urg_ in etiquetas_laterais if re.fullmatch(r"[\w-]+", k_))
    if estilo_etiquetas:
        st.markdown(f"<style>{estilo_etiquetas}</style>", unsafe_allow_html=True)
    # ---------- a pessoa: perfil e definições, no fundo
    with st.container(key="lateral_conta"):
        _ext = utilizador_externo()
        st.button((perfil.get("nome") or (_ext or {}).get("nome") or "O meu perfil").split(" ")[0][:22] + " · Perfil",
                  key="sep_perfil", icon=":material/account_circle:", type="secondary" if vista == "perfil" else "tertiary",
                  on_click=navegar, args=("perfil",))
        st.button("Definições", key="sep_definicoes", icon=":material/settings:",
                  type="secondary" if vista == "definicoes" else "tertiary", on_click=navegar, args=("definicoes",),
                  kwargs={"def_aberta": False})
if vista != "definicoes":
    if st.session_state.pop("_defs_sujo", None):  # saiu das Definições com um formulário a meio
        st.toast("Saíste das Definições sem guardar as alterações que estavas a fazer.", icon=":material/warning:")
    if st.query_params.get("p") == "definicoes":
        for _k in ("p", "c"):
            if _k in st.query_params:
                del st.query_params[_k]
# aparência e acessibilidade escolhidas nas Definições: em todas as páginas menos nos laboratórios — dentro de uma sala
# decide a própria página (quando já sabe se o separador aberto é o Laboratório) — e no 3D Studio
if vista != "estudio3d" and not (vista == "salas" and st.session_state.get("sala_aberta")):
    aplicar_preferencias_visuais()

tem_chave = bool(cfg["chaves"].get(cfg["fornecedor"]))
if not tem_chave and vista not in ("salas", "estudio3d"):
    st.warning("Abre o teu **Perfil** (no fundo da barra lateral) → **Administração** e indica a chave da IA." if e_admin()
               else "O assistente de IA ainda não está disponível nesta app. Avisa quem gere a app.", icon=":material/info:")


# =============================================================== CHAT
def responder(conversa: dict, pergunta: str, anexos: bool = False) -> None:
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    with st.chat_message("user"):
        st.markdown(pergunta)
    anteriores = [m for m in conversa["mensagens"] if not m.get("falhou")]
    ultima_resposta = next((m["content"] for m in reversed(anteriores) if m["role"] == "assistant"), "")
    tarefa = dz.complexidade(pergunta, anexos or (not anteriores and bool(conversa.get("ficheiros"))),
                             ultima_resposta)  # o modelo mais rápido para o simples, um mais capaz para o resto
    mensagens = [
        {"role": "user", "content": f"{info_aluno()}\n\n<fontes>\n{fontes_conversa(conversa, pergunta)}\n</fontes>\n\n"
                                    "Vou fazer-te perguntas sobre esta matéria."},
        {"role": "assistant", "content": "Combinado. Podes perguntar."},
    ] + dz.contexto_conversa(anteriores)
    com_web = bool(cfg.get("web"))
    lembrete = (LEMBRETE_WEB_EN if cfg.get("idioma") == "English" else LEMBRETE_WEB_PT) if com_web else ""
    mensagens.append({"role": "user", "content": pergunta + lembrete})
    with st.chat_message("assistant", avatar=avatar):
        try:
            resposta = escrever_fluxo(chamar_ia_stream(mensagens, sistema=sistema_chat(com_web), web=com_web, tarefa=tarefa),
                                      ("A pesquisar na web" if com_web else "A pensar") if cfg.get("idioma") != "English"
                                      else ("Searching the web" if com_web else "Thinking"))
        except Exception as erro:  # noqa: BLE001 — a pergunta fica na conversa, com «Tentar outra vez»
            mostrar_erro(erro)
            conversa["mensagens"] = anteriores + [{"role": "user", "content": pergunta, "falhou": True}]
            conversa["atualizada"] = datetime.now().isoformat(timespec="seconds")
            guardar_perfil()
            st.button("Tentar outra vez", icon=":material/refresh:", key="msgacao_repetir_agora", type="primary",
                      on_click=regenerar_resposta, args=(st.session_state.conversa_id,))
            return
        resposta = resposta if isinstance(resposta, str) else "".join(map(str, resposta))
        fontes_web = st.session_state.get("_fontes_web") or []
        if fontes_web:
            titulo = "Fontes na web" if cfg.get("idioma") != "English" else "Web sources"
            bloco = f"\n\n**{titulo}:**\n" + "\n".join(f"- [{escape(t)}]({u})" for t, u in fontes_web[:8])
            st.markdown(bloco)
            resposta += bloco
        aviso_web = st.session_state.pop("_aviso_web", None)
        erros_web = st.session_state.pop("_erros_web", None)
        info_web = st.session_state.pop("_info_web", None)
        if info_web:
            st.caption(f":material/travel_explore: {info_web}")
        if aviso_web:
            st.warning(aviso_web, icon=":material/travel_explore:")
            if erros_web and e_admin():
                with st.expander("Resposta da Google (para perceber o problema)"):
                    st.code("\n\n".join(erros_web)[:4000], language=None)
        elif com_web and not fontes_web:
            st.caption(":material/travel_explore: Desta vez a IA respondeu sem abrir sites (não encontrou nada melhor na web).")
    if resposta:
        nova = {"role": "assistant", "content": resposta}
        avisos = {k: v for k, v in (("info", info_web), ("aviso", aviso_web),
                                     ("sem_sites", bool(com_web and not fontes_web and not aviso_web))) if v}
        if avisos:  # os avisos da pesquisa ficam com a resposta (continuam à vista depois)
            nova["avisos"] = avisos
        conversa["mensagens"] = anteriores + [{"role": "user", "content": pergunta}, nova]
        conversa["atualizada"] = datetime.now().isoformat(timespec="seconds")
        if conversa.get("titulo_auto") and len(conversa["mensagens"]) == 2:  # como no Claude: título curto feito pela IA
            novo_titulo = titulo_com_ia(pergunta, resposta)
            if novo_titulo:
                conversa["titulo"], conversa["titulo_auto"] = novo_titulo, False
        guardar_perfil()
        if not (erros_web and e_admin()):  # (o detalhe técnico da Google fica à vista para quem gere a app)
            st.rerun()  # volta a desenhar com os botões de cada mensagem (copiar, gerar outra, editar) e o título novo


def regenerar_resposta(cid: str) -> None:
    """«Gerar outra resposta» / «Tentar outra vez»: tira a última resposta (se houver) e volta a fazer a última pergunta."""
    conversa_ = conversas.get(cid)
    if not conversa_:
        return
    msgs = conversa_["mensagens"]
    if msgs and msgs[-1]["role"] == "assistant":
        msgs.pop()
    if msgs and msgs[-1]["role"] == "user":
        st.session_state.pergunta_pendente = msgs.pop()["content"]
    st.session_state.pop("editar_msg", None)


def editar_mensagem(cid: str, indice: int) -> None:
    st.session_state.editar_msg = [cid, indice]


COPIAR_JS = r"""(function(){
function texto(b){try{return new TextDecoder().decode(Uint8Array.from(atob(b.getAttribute('data-t')),function(c){return c.charCodeAt(0);}));}catch(e){return '';}}
function feito(b){var r=b.querySelector('.mi-copiar-txt');b.classList.add('ok');if(r){var a=r.getAttribute('data-normal')||r.textContent;r.setAttribute('data-normal',a);r.textContent=b.getAttribute('data-ok')||'Copiado';setTimeout(function(){r.textContent=a;b.classList.remove('ok');},1600);}}
function alternativa(t,b){var ta=document.createElement('textarea');ta.value=t;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.top='-1000px';document.body.appendChild(ta);ta.select();try{if(document.execCommand('copy'))feito(b);}catch(e){}document.body.removeChild(ta);}
function copiar(b){var t=texto(b);if(!t)return;if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(function(){feito(b);},function(){alternativa(t,b);});}else{alternativa(t,b);}}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('.mi-copiar');if(b){e.preventDefault();copiar(b);}});
document.addEventListener('keydown',function(e){var b=e.target;if((e.key==='Enter'||e.key===' ')&&b.classList&&b.classList.contains('mi-copiar')){e.preventDefault();copiar(b);}});
})();"""


def ativar_copiar() -> None:
    """Liga os botões «Copiar» (uma vez por página): o script fica no documento da app, por isso o clique copia mesmo."""
    try:
        components.html("<script>(function(){var d=window.parent.document;if(d.getElementById('mi-copiar-js'))return;"
                        "var s=d.createElement('script');s.id='mi-copiar-js';s.textContent=" + json.dumps(COPIAR_JS)
                        + ";d.head.appendChild(s);})();</script>", height=0)
    except Exception:  # noqa: BLE001
        pass


def botao_copiar_html(texto: str, en: bool = False) -> str:
    dados = base64.b64encode(texto.encode("utf-8")).decode()
    rotulo, feito = ("Copy", "Copied") if en else ("Copiar", "Copiado")
    return (f"<span class='mi-copiar' role='button' tabindex='0' aria-label='{rotulo}' data-ok='{feito}' data-t='{dados}'>"
            f"<span class='material-symbols-rounded' translate='no' aria-hidden='true'>content_copy</span>"
            f"<span class='mi-copiar-txt'>{rotulo}</span></span>")


def mostrar_mensagens(conversa: dict, cid: str) -> None:
    """A conversa: as mensagens mais recentes (as antigas a pedido), com copiar, gerar outra resposta e editar."""
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    msgs = conversa["mensagens"]
    en = cfg.get("idioma") == "English"
    inicio = 0 if st.session_state.get("conv_antigas") == cid or len(msgs) <= 40 else len(msgs) - 40
    if inicio:
        st.button(f"Mostrar as {inicio} mensagens anteriores", key="conv_antigas_btn", type="tertiary",
                  icon=":material/expand_less:", on_click=lambda: st.session_state.update(conv_antigas=cid))
    editar = st.session_state.get("editar_msg")
    ultima_resp = max((i for i, m in enumerate(msgs) if m["role"] == "assistant"), default=None)
    for i in range(inicio, len(msgs)):
        m = msgs[i]
        assistente = m["role"] == "assistant"
        with st.chat_message(m["role"], avatar=avatar if assistente else None):
            if not assistente and editar == [cid, i]:
                novo = st.text_area("Editar a mensagem", value=m["content"], key=f"edit_txt_{cid}_{i}",
                                    label_visibility="collapsed", height=110)
                a_, b_, _ = st.columns([1.3, 1.1, 3])
                if a_.button("Enviar", key=f"msgacao_enviar_{cid}_{i}", type="primary", icon=":material/send:",
                             disabled=not tem_chave) and novo.strip():
                    conversa["mensagens"] = msgs[:i]  # as respostas a seguir deixam de fazer sentido: a conversa segue daqui
                    guardar_perfil()
                    st.session_state.pop("editar_msg", None)
                    st.session_state.pergunta_pendente = novo.strip()
                    st.rerun()
                if b_.button("Cancelar", key=f"msgacao_cancelar_{cid}_{i}"):
                    st.session_state.pop("editar_msg", None)
                    st.rerun()
                continue
            md(m["content"])
            avisos_m = m.get("avisos") or {}
            if avisos_m.get("info"):
                st.caption(f":material/travel_explore: {avisos_m['info']}")
            if avisos_m.get("aviso"):
                st.warning(avisos_m["aviso"], icon=":material/travel_explore:")
            elif avisos_m.get("sem_sites"):
                st.caption(":material/travel_explore: Desta vez a IA respondeu sem abrir sites (não encontrou nada melhor na web).")
            with st.container(horizontal=True, key=f"msgacoes_{cid}_{i}", gap="small"):
                if assistente:
                    st.markdown(botao_copiar_html(m["content"], en), unsafe_allow_html=True)
                    if i == ultima_resp and i == len(msgs) - 1 and tem_chave:
                        st.button("", icon=":material/refresh:", key=f"msgacao_regen_{cid}", type="tertiary",
                                  help="Gerar outra resposta" if not en else "Regenerate",
                                  on_click=regenerar_resposta, args=(cid,))
                elif m.get("falhou"):
                    st.caption(":material/error: Não chegou a haver resposta.")
                    st.button("Tentar outra vez", icon=":material/refresh:", key=f"msgacao_repetir_{cid}", type="tertiary",
                              on_click=regenerar_resposta, args=(cid,), disabled=not tem_chave)
                elif tem_chave:
                    st.button("", icon=":material/edit:", key=f"msgacao_editar_{cid}_{i}", type="tertiary",
                              help="Editar e voltar a perguntar" if not en else "Edit", on_click=editar_mensagem,
                              args=(cid, i))
            if assistente and i == ultima_resp and i == len(msgs) - 1 and tem_chave and len(m["content"]) > 120:
                with st.container(horizontal=True, key=f"seguir_{cid}", gap="small"):
                    for rotulo_s, icone_s, pedido_s in (SEGUIMENTO_EN if en else SEGUIMENTO):
                        st.button(rotulo_s, icon=icone_s, key=f"seguir_{cid}_{rotulo_s[:12]}", type="secondary",
                                  on_click=lambda p_=pedido_s: st.session_state.update(pergunta_pendente=p_))
    ativar_copiar()


# continuar a explicação com um clique (as perguntas vão como se o aluno as tivesse escrito)
SEGUIMENTO = [("Mais simples", ":material/child_care:", "Explica outra vez de forma mais simples, com um exemplo do dia a dia."),
              ("Um exemplo", ":material/lightbulb:", "Dá-me um exemplo resolvido passo a passo."),
              ("Exercícios", ":material/edit_note:", "Faz-me 3 exercícios sobre isto, do mais fácil ao mais difícil, com as "
                                                      "soluções no fim (escondidas até eu pedir)."),
              ("Resumo", ":material/summarize:", "Resume o essencial em 3 a 5 pontos curtos.")]
SEGUIMENTO_EN = [("Simpler", ":material/child_care:", "Explain it again more simply, with an everyday example."),
                 ("An example", ":material/lightbulb:", "Give me a worked example, step by step."),
                 ("Exercises", ":material/edit_note:", "Give me 3 exercises on this, from easiest to hardest, with the "
                                                       "solutions at the end."),
                 ("Summary", ":material/summarize:", "Summarise the key points in 3 to 5 short bullets.")]


def pedido_rapido(texto: str, sistema: str) -> str:
    """Um pedido curto à IA, sem esperas nem novas tentativas (para coisas secundárias, como o título da conversa)."""
    cfg_ = st.session_state.cfg
    if cfg_["fornecedor"] == "Gemini":
        from google import genai

        cliente = genai.Client(api_key=cfg_["chaves"].get("Gemini", ""))
        modelo = candidatos_gemini("leve")[0]
        r = cliente.models.generate_content(model=modelo, contents=[{"role": "user", "parts": [{"text": texto}]}],
                                            config=config_gemini(modelo, sistema, False, True))
        return r.text or ""
    import anthropic

    cliente = anthropic.Anthropic(api_key=cfg_["chaves"].get("Claude", ""))
    r = cliente.messages.create(model=MODELO_CLAUDE, max_tokens=60, system=sistema,
                                messages=[{"role": "user", "content": texto}])
    return "".join(b.text for b in r.content if b.type == "text")


def titulo_com_ia(pergunta: str, resposta: str) -> str | None:
    """Título curto para o histórico (3 a 6 palavras). Se falhar, fica o provisório: nunca estraga a conversa."""
    try:
        return hc.limpar_titulo(pedido_rapido(
            hc.PEDIDO_TITULO.format(pergunta=pergunta[:500], resposta=resposta[:400]),
            "Dás títulos curtos a conversas. Respondes só com o título."))
    except Exception:  # noqa: BLE001
        return None


def criar_conversa(texto: str, cadeira, ficheiros: dict) -> str:
    cid = uuid.uuid4().hex[:10]
    agora = datetime.now().isoformat(timespec="seconds")
    conversas[cid] = {"titulo": hc.titulo_provisorio(texto), "titulo_auto": True,
                      "cadeira": cadeira, "mensagens": [], "ficheiros": ficheiros, "criada": agora, "atualizada": agora}
    guardar_perfil()
    return cid


def guardar_anexos(cadeira, enviados) -> dict:
    """Ficheiros anexados no chat: vão para a cadeira (se houver) ou ficam só nesta conversa."""
    if not enviados:
        return {}
    if cadeira and cadeira in st.session_state.cadeiras:
        n = adicionar_ficheiros(cadeira, enviados)
        if n:
            st.toast(f"{n} documento(s) guardado(s) em {cadeira}.")
        return {}
    return ler_ficheiros(enviados)


class AnexoFoto:
    """Fotografia tirada com a câmara, com um nome que diz o que é (a câmara chama-lhe sempre «image.jpg»)."""

    def __init__(self, nome: str, dados: bytes):
        self.name, self._dados, self.type, self.size = nome, dados, "image/jpeg", len(dados)

    def getvalue(self) -> bytes:
        return self._dados


# Os botões da câmara do Streamlit vêm em inglês: este script (só carregado quando a câmara do «+» abre) põe-nos em
# português. Fica de fora do identidade.py, que também serve os laboratórios.
TRADUZ_CAMARA = r"""<script>(function(){try{var d=window.parent.document;if(d.getElementById('mi-camara-pt'))return;
var s=d.createElement('script');s.id='mi-camara-pt';
s.textContent="(function(){var F={'Take Photo':'Tirar fotografia','Clear photo':'Tirar outra'};"+
"function t(n){if(n.nodeType===3){var l=n.nodeValue.trim();if(F[l])n.nodeValue=n.nodeValue.replace(l,F[l]);return;}"+
"if(n.nodeType!==1)return;var w=document.createTreeWalker(n,4),x;while((x=w.nextNode()))t(x);}"+
"t(document.body);new MutationObserver(function(ms){ms.forEach(function(m){if(m.type==='characterData')t(m.target);"+
"else m.addedNodes.forEach(t);});}).observe(document.body,{childList:true,subtree:true,characterData:true});})();";
d.head.appendChild(s);}catch(e){}})();</script>"""
ICONE_ANEXO = {"pdf": "picture_as_pdf", "pptx": "slideshow", "docx": "description", "txt": "notes", "md": "notes"}
RESUMO_ANEXOS = "Faz-me um resumo curto dos documentos que acabei de anexar."


def limpar_anexos(ctx: str) -> None:
    """Esvazia os anexos escolhidos no «+» (o carregador e a câmara recomeçam do zero)."""
    st.session_state[f"_anx_v_{ctx}"] = st.session_state.get(f"_anx_v_{ctx}", 0) + 1
    st.session_state.pop(f"_cam_{ctx}", None)


def anexos_do_mais(ctx: str) -> list:
    """Ficheiros e fotografia escolhidos no «+» e ainda não enviados."""
    ss = st.session_state
    n = ss.get(f"_anx_v_{ctx}", 0)
    lista = list(ss.get(f"mais_fich_{ctx}_{n}") or [])
    captura_recebida(ctx, n, ss.get(f"mais_ecra_c_{ctx}_{n}"))  # a captura chega antes de o menu ser desenhado
    lista += [AnexoFoto(nome_c, dados_c) for nome_c, dados_c in ss.get(f"_capturas_{ctx}_{n}", [])]
    foto = ss.get(f"mais_cam_{ctx}_{n}")
    if foto is not None:
        nome = ss.setdefault(f"_cam_nome_{ctx}_{n}", f"fotografia-{datetime.now():%d%m-%H%M%S}.jpg")
        lista.append(AnexoFoto(nome, foto.getvalue()))
    fora = ss.get(f"_anx_fora_{ctx}_{n}", set())  # os que a pessoa tirou com o «×»
    return [f for f in lista if f.name not in fora]


def tirar_anexo(ctx: str, nome: str) -> None:
    """«×» de um anexo: sai da lista (os outros ficam)."""
    n = st.session_state.get(f"_anx_v_{ctx}", 0)
    st.session_state.setdefault(f"_anx_fora_{ctx}_{n}", set()).add(nome)


def miniatura(nome: str, dados: bytes) -> str | None:
    """Miniatura (data URI) de uma imagem anexada, para a etiqueta do anexo. Fica em memória durante a sessão."""
    cache = st.session_state.setdefault("_miniaturas", {})
    chave = (nome, len(dados))
    if chave not in cache:
        try:
            from PIL import Image

            im = Image.open(io.BytesIO(dados))
            im.thumbnail((88, 88))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=72)
            cache[chave] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:  # noqa: BLE001
            cache[chave] = None
    return cache[chave]


def opcao_ia_mudou(chave_cfg: str, chave_widget: str) -> None:
    """Uma opção da IA mudada no «+» fica na conta (é a mesma das Definições → Inteligência artificial)."""
    valor = st.session_state.get(chave_widget)
    if valor is not None and valor != cfg.get(chave_cfg):
        cfg[chave_cfg] = valor
        guardar_config()


def cadeira_da_conversa_mudou(ctx: str, conversa: dict | None) -> None:
    valor = st.session_state.get(f"mais_cad_{ctx}") or None
    if conversa is None:
        st.session_state["_cad_nova"] = valor
    elif conversa.get("cadeira") != valor:
        conversa["cadeira"] = valor
        guardar_perfil()


def captura_recebida(ctx: str, n: int, valor) -> None:
    """Guarda nos anexos a captura de ecrã que o componente devolveu (imagem JPEG em base64)."""
    ev = evento(valor, f"mais_ecra_c_{ctx}_{n}")
    if not ev or ev.get("evento") != "captura" or not str(ev.get("imagem", "")).startswith("data:image/"):
        return
    import base64
    try:
        dados = base64.b64decode(ev["imagem"].split(",", 1)[1])
    except (ValueError, IndexError):
        return
    lista = st.session_state.setdefault(f"_capturas_{ctx}_{n}", [])
    lista.append((f"captura-{datetime.now():%d%m-%H%M%S}.jpg", dados))


def menu_mais(ctx: str, conversa: dict | None) -> None:
    """O «+» da barra de conversa, como no Claude: anexar ficheiros ou fotos, tirar uma captura de ecrã (no computador)
    ou uma fotografia (no telemóvel), pesquisar na web, de que cadeira são os documentos e o estilo das respostas.
    Só opções que a app faz de verdade."""
    ss = st.session_state
    n = ss.get(f"_anx_v_{ctx}", 0)
    with st.popover("Anexar e opções", icon=":material/add:", key=f"mmais_{ctx}"):
        st.file_uploader("Adicionar ficheiros ou fotos", type=TIPOS_FICHEIRO, accept_multiple_files=True,
                         key=f"mais_fich_{ctx}_{n}", label_visibility="collapsed")
        with st.container(key=f"mais_pc_{ctx}"):  # computador: captura de ecrã (o browser pergunta o que partilhar)
            captura_recebida(ctx, n, componente("captura", f"mais_ecra_c_{ctx}_{n}", altura=40))
        with st.container(key=f"mais_tlm_{ctx}"):  # telemóvel: câmara (só liga quando a pessoa pede)
            if ss.get(f"_cam_{ctx}"):
                st.camera_input("Fotografia", key=f"mais_cam_{ctx}_{n}", label_visibility="collapsed")
                try:
                    components.html(TRADUZ_CAMARA, height=0)
                except Exception:  # noqa: BLE001
                    pass
                st.button("Fechar a câmara", icon=":material/no_photography:", key=f"mais_cam_fechar_{ctx}",
                          type="tertiary", width="stretch", on_click=lambda: ss.pop(f"_cam_{ctx}", None))
            else:
                st.button("Tirar fotografia", icon=":material/photo_camera:", key=f"mais_cam_abrir_{ctx}", type="tertiary",
                          width="stretch", on_click=lambda: ss.update({f"_cam_{ctx}": True}))
        st.divider()
        st.toggle("Pesquisar na web", value=cfg.get("web", True), key=f"mais_web_{ctx}",
                  on_change=opcao_ia_mudou, args=("web", f"mais_web_{ctx}"))
        nomes_c = list(st.session_state.cadeiras)
        if nomes_c:
            opcoes_c = [""] + nomes_c
            atual_c = conversa.get("cadeira") if conversa is not None else ss.get("_cad_nova")
            with st.container(horizontal=True, key=f"mais_docs_{ctx}", vertical_alignment="center", gap="small"):
                st.markdown("<div class='mi-mlinha'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>folder_open</span>"
                            "Documentos</div>", unsafe_allow_html=True)
                st.selectbox("Documentos", opcoes_c, index=opcoes_c.index(atual_c) if atual_c in opcoes_c else 0,
                             format_func=lambda c: c or "Todas as salas", key=f"mais_cad_{ctx}",
                             label_visibility="collapsed", on_change=cadeira_da_conversa_mudou, args=(ctx, conversa))
        with st.expander("Estilo das respostas", icon=":material/tune:"):
            p_ = dfs.limpar(cfg)
            st.segmented_control("Respostas", dfs.OPCOES["ia_tamanho"], default=p_["ia_tamanho"], key=f"mais_tam_{ctx}",
                                 on_change=opcao_ia_mudou, args=("ia_tamanho", f"mais_tam_{ctx}"))
            st.segmented_control("Nível", dfs.OPCOES["ia_nivel"], default=p_["ia_nivel"], key=f"mais_niv_{ctx}",
                                 on_change=opcao_ia_mudou, args=("ia_nivel", f"mais_niv_{ctx}"))
            st.segmented_control("Idioma", ["Português", "English"], default=cfg.get("idioma", "Português"),
                                 key=f"mais_idi_{ctx}", on_change=opcao_ia_mudou, args=("idioma", f"mais_idi_{ctx}"))
            st.caption("Ficam guardadas na tua conta, como em Definições → Inteligência artificial.")


def barra_conversa(ctx: str, placeholder: str, chave_entrada: str, conversa: dict | None = None):
    """Barra de conversa: «+» à esquerda (dentro da caixa), a caixa de texto e, por cima, os anexos escolhidos.
    Também se pode arrastar ou colar ficheiros para a caixa. Devolve (texto, ficheiros) quando a pessoa envia; senão
    (None, [])."""
    pendentes = anexos_do_mais(ctx)
    resumir = False
    with st.container(key=f"mbarra_{ctx}"):
        if pendentes:  # como no Claude: os anexos ficam dentro da caixa, por cima do texto, cada um com o seu «×»
            with st.container(horizontal=True, key=f"manexos_{ctx}", gap="small", vertical_alignment="center"):
                for i, f in enumerate(pendentes):
                    ext = f.name.lower().rsplit(".", 1)[-1]
                    mini = miniatura(f.name, f.getvalue()) if ext in TIPOS_IMAGEM else None
                    visual = (f"<img src='{mini}' alt=''>" if mini else
                              f"<span class='material-symbols-rounded' translate='no' aria-hidden='true'>"
                              f"{'image' if ext in TIPOS_IMAGEM else ICONE_ANEXO.get(ext, 'draft')}</span>")
                    with st.container(horizontal=True, key=f"manx_{ctx}_{i}", gap=None, vertical_alignment="center"):
                        st.markdown(f"<div class='mi-anexo' title='{escape(f.name)}'>{visual}<span class='mi-anexo-n'>"
                                    f"{escape(f.name)}</span></div>", unsafe_allow_html=True)
                        st.button("Tirar", icon=":material/close:", key=f"anx_x_{ctx}_{i}", type="tertiary",
                                  help=f"Tirar {f.name}", on_click=tirar_anexo, args=(ctx, f.name))
                resumir = st.button("Resumir", icon=":material/summarize:", key=f"anx_resumir_{ctx}", type="tertiary",
                                    help="Envia só os anexos e pede um resumo curto", disabled=not tem_chave)
        menu_mais(ctx, conversa)
        entrada = st.chat_input(placeholder, accept_file="multiple", file_type=TIPOS_FICHEIRO, key=chave_entrada,
                                disabled=not tem_chave)
    if not (entrada or resumir) or not tem_chave:
        return None, []
    ficheiros = list(entrada.files if entrada else []) + pendentes
    texto = (entrada.text if entrada else "") or (RESUMO_ANEXOS if ficheiros else "")
    if pendentes:
        limpar_anexos(ctx)
    return (texto, ficheiros) if texto else (None, [])


def compositor_assistente(destaque: bool = False) -> None:
    """Caixa de pergunta ao assistente, com o «+» (anexos, fotografia, pesquisa na web, cadeira e estilo).
    Responde com os documentos de todas as cadeiras, ou só de uma se a pessoa escolher no «+»."""
    if destaque:
        st.markdown("<div class='ec-pergunta-titulo'>Em que te posso ajudar?</div>", unsafe_allow_html=True)
    if e_telemovel():  # como no Claude: no telemóvel a caixa fica fixa no fundo do ecrã
        with fixo_no_fundo(), st.bottom, st.container(key="compositor"):
            texto, ficheiros = barra_conversa("novo", "Pergunta qualquer coisa…", "entrada_nova")
    else:
        with st.container(key="compositor"):
            texto, ficheiros = barra_conversa("novo", "Pergunta qualquer coisa…", "entrada_nova")
    if texto:
        cadeira_n = st.session_state.get("_cad_nova") if st.session_state.get("_cad_nova") in st.session_state.cadeiras else None
        anexos = guardar_anexos(cadeira_n, ficheiros)
        cid = criar_conversa(texto, cadeira_n, anexos)
        ir("chat", conversa_id=cid, pergunta_pendente=texto)


if vista == "chat":
    conversa = conversas.get(st.session_state.conversa_id) if st.session_state.conversa_id else None
    nomes_cadeiras = list(st.session_state.cadeiras)

    if conversa is None:  # ---------- ecrã inicial
        st.markdown(f'<div class="ec-saudacao{" tlm" if e_telemovel() else ""}">{ICONE_SVG}<span>{escape(saudacao())}</span></div>',
                    unsafe_allow_html=True)
        compositor_assistente()
    else:  # ---------- conversa aberta
        c1, c2 = st.columns([6, 1.3], vertical_alignment="center")
        etiqueta = conversa.get("cadeira") or "Todas as salas"
        lugar_titulo = c1.empty()

        def cabecalho_conversa() -> None:
            fixa = ' <span class="material-symbols-rounded ec-fixa" title="Fixada">push_pin</span>' if conversa.get("fixada") else ""
            lugar_titulo.markdown(f'<div class="ec-titulo-conversa">{escape(conversa.get("titulo", ""))}{fixa} &nbsp;'
                                  f'<span class="ec-contexto">{escape(etiqueta)}</span></div>', unsafe_allow_html=True)

        cabecalho_conversa()
        cid_atual = st.session_state.conversa_id
        with c2.popover("Mais", icon=":material/more_horiz:", help="Fixar, mudar o nome ou apagar a conversa"):
            if st.button("Tirar dos fixados" if conversa.get("fixada") else "Fixar no topo", key="conv_fixar",
                         icon=":material/push_pin:", width="stretch"):
                conversa["fixada"] = not conversa.get("fixada")
                guardar_perfil()
                st.rerun()
            novo_nome = st.text_input("Nome da conversa", value=conversa.get("titulo", ""), key=f"conv_nome_{cid_atual}",
                                      max_chars=80)
            if st.button("Mudar o nome", key="conv_renomear", icon=":material/edit:", width="stretch"):
                nome_limpo = " ".join(str(novo_nome or "").split())
                if nome_limpo and nome_limpo != conversa.get("titulo"):
                    conversa["titulo"], conversa["titulo_auto"] = nome_limpo, False
                    guardar_perfil()
                    st.rerun()
            if st.session_state.get("_apagar_conv") == cid_atual:
                st.caption("Apagar esta conversa? Não pode ser desfeito.")
                if st.button("Sim, apagar", icon=":material/delete:", key="conv_apagar_ok", type="primary", width="stretch"):
                    st.session_state.pop("_apagar_conv", None)
                    conversas.pop(st.session_state.conversa_id, None)
                    guardar_perfil()
                    nova_conversa_vazia()
            elif st.button("Apagar conversa", icon=":material/delete:", key="conv_apagar", width="stretch"):
                st.session_state["_apagar_conv"] = cid_atual
                st.rerun()
        mostrar_mensagens(conversa, cid_atual)
        with fixo_no_fundo(), st.bottom:
            texto_b, ficheiros_b = barra_conversa(cid_atual, "Responder…", f"entrada_{cid_atual}", conversa)
        pergunta = st.session_state.pop("pergunta_pendente", None)
        com_anexos = False
        if texto_b:
            anexos = guardar_anexos(conversa.get("cadeira"), ficheiros_b)
            if anexos:
                conversa.setdefault("ficheiros", {}).update(anexos)
                guardar_perfil()
            com_anexos = bool(ficheiros_b)
            pergunta = texto_b
        if pergunta and tem_chave:
            responder(conversa, pergunta, com_anexos)
    st.stop()

# =============================================================== PLANOS DE ESTUDO (assistente com perguntas, ligado às avaliações)
# O plano diz o que estudar em cada dia, sem horas nem durações. A IA lê a matéria e propõe os temas de cada cadeira; a
# distribuição pelos dias (revisões espaçadas, cadeiras intercaladas, carga equilibrada) e a reorganização do que ficou
# por fazer são feitas em plano_estudo.py, sempre da mesma maneira.
def prefs_plano() -> dict:
    return pe.preferencias(perfil.get("plano_prefs"), perfil)


def guardar_prefs_plano(prefs: dict) -> None:
    perfil["plano_prefs"] = {k: prefs[k] for k in ("folga", "ritmo", "comecar", "estilo")}
    perfil["folga"] = list(prefs["folga"])
    guardar_perfil()


def cadeiras_do_ambito(ambito: dict) -> list:
    if ambito.get("tipo") == "cadeira":
        return [ambito["cadeira"]] if ambito.get("cadeira") in st.session_state.cadeiras else []
    return [n for n in st.session_state.cadeiras if repo().proxima(n)]


def limites_do_ambito(ambito: dict) -> dict:
    """{cadeira: data da avaliação}: o plano de cada cadeira acaba no dia anterior."""
    if ambito.get("tipo") == "cadeira":
        r = repo().obter(ambito.get("avaliacao_id")) or repo().proxima(ambito.get("cadeira"))
        return {ambito["cadeira"]: av.para_data(r["data"]) if r else None}
    return {n: av.para_data(repo().proximas(n)[-1]["data"]) for n in cadeiras_do_ambito(ambito)}


def texto_ambito(ambito: dict) -> str:
    if ambito.get("tipo") == "cadeira":
        r = repo().obter(ambito.get("avaliacao_id"))
        return f"{ambito['cadeira']} · {r['nome']} ({fmt_data(r['data'], False)})" if r else ambito.get("cadeira", "")
    return "Todas as salas com avaliações"


def fontes_do_ambito(ambito: dict, limite_total: int | None = None) -> str:
    nomes = cadeiras_do_ambito(ambito)
    parte = (limite_total or limite_caracteres()) // max(1, len(nomes))
    blocos = []
    for n in nomes:
        d = st.session_state.cadeiras[n]
        materia = selecionar_texto(d["ficheiros"], "", parte) if d["ficheiros"] else "(sem documentos)"
        blocos.append(f"=== CADEIRA: {n} ===\n{contexto_cadeira(d)}\nMatéria:\n{materia}")
    return "\n\n".join(blocos)


def perguntas_ia_plano(ambito: dict) -> list:
    """A IA lê a matéria e faz 3 a 5 perguntas para conhecer o aluno antes de planear (sem repetir o que já se sabe)."""
    pedido = (
        "Vais criar um plano de estudo para este aluno. Antes, faz-lhe 3 a 5 perguntas curtas e úteis para o conheceres: "
        "que temas acha mais difíceis (usa os temas REAIS das fontes nas opções), o que já estudou ou domina, como é a "
        "avaliação (se não souberes), que tipo de exercícios costumam sair e o que quer conseguir. Não perguntes "
        "que dias estuda nem horários ou durações (já sei; o plano não tem horas). "
        "Responde só com JSON: {\"perguntas\": [{\"pergunta\": \"...\", \"tipo\": \"multipla\" | \"escolha\" | \"texto\", "
        "\"opcoes\": [\"...\"]}]}. «multipla» = pode escolher várias (até 8 opções), «escolha» = uma só (2 a 5 opções), "
        "«texto» = resposta livre curta (sem opções). Em português de Portugal, tratando o aluno por tu.")
    try:
        r = extrair_json(chamar_ia([{"role": "user", "content": f"{info_aluno()}\n\n<fontes>\n{fontes_do_ambito(ambito, 24000)}"
                                                                f"\n</fontes>\n\n{pedido}"}], json_mode=True, sistema=SISTEMA_CHAT))
    except Exception:  # noqa: BLE001 — sem perguntas, o assistente continua na mesma
        return []
    perguntas = []
    for i, p in enumerate((r.get("perguntas") or r.get("_lista") or [])[:5]):
        if not isinstance(p, dict) or not str(p.get("pergunta") or "").strip():
            continue
        tipo = p.get("tipo") if p.get("tipo") in ("multipla", "escolha", "texto") else "texto"
        opcoes = list(dict.fromkeys(str(o).strip()[:90] for o in (p.get("opcoes") or []) if str(o).strip()))[:8]
        if tipo != "texto" and len(opcoes) < 2:
            tipo, opcoes = "texto", []
        perguntas.append({"id": f"p{i}", "pergunta": str(p["pergunta"]).strip()[:220], "tipo": tipo, "opcoes": opcoes})
    return perguntas


def gerar_rascunho_plano(ambito: dict, prefs: dict, respostas: list | None = None, nota: str = "",
                         feitos_txt: str = "") -> dict | None:
    """A IA lê a matéria e propõe os TEMAS de cada cadeira (dificuldade, importância e tarefas concretas); a app
    distribui-os pelos dias (plano_estudo.distribuir). Não guarda nada.
    Devolve {"unidades", "dias" (as tarefas), "info", "guia", "resumo"}."""
    hoje = date.today()
    nomes = cadeiras_do_ambito(ambito)
    if not nomes:
        st.error("Não há avaliações futuras para planear. Marca-as primeiro no Calendário.")
        return None
    linhas_cad = []
    for n in nomes:
        obj = objetivo(st.session_state.cadeiras[n])
        linhas_cad.append(f"- {n}: {contexto_cadeira(st.session_state.cadeiras[n]) or 'sem avaliações'} Dificuldade para o "
                          f"aluno: {obj.get('dificuldade') or 'Média'}. Nota pretendida: {obj.get('nota_alvo') or '—'}.")
    alvo = ""
    if ambito.get("tipo") == "cadeira":
        r = repo().obter(ambito.get("avaliacao_id")) or repo().proxima(ambito["cadeira"])
        alvo = (f"O plano é para «{r['nome']}» ({r['tipo'].lower()}) de {ambito['cadeira']}, a {r['data']}.\n") if r else ""
    respostas_txt = "\n".join(f"- {q} → {a}" for q, a in (respostas or []) if str(a).strip())
    if not feitos_txt:
        antigo = plano_existente(ambito).get("dias") or []
        cad_fixa = ambito.get("cadeira") if ambito.get("tipo") == "cadeira" else None
        ja = pe.estudados(antigo, set(perfil.get("feitas", [])), cad_fixa)
        if ja:
            feitos_txt = ("O aluno já estudou estes temas (se os incluíres, usa exatamente estes nomes): "
                          + "; ".join(f"{c}: {', '.join(sorted(t))}" for c, t in ja.items()))
    pedido = (
        f"Hoje é {DIAS_SEMANA[hoje.weekday()].lower()}, {hoje.isoformat()}.\n{alvo}"
        f"Cadeiras e avaliações:\n" + "\n".join(linhas_cad) + "\n\nComo o aluno gosta de estudar:\n"
        f"- Quer começar {prefs['comecar'].lower()}. Estilo: {prefs['estilo'].lower()}.\n"
        + (f"- Outras indicações do perfil: {perfil.get('notas')}\n" if perfil.get("notas") else "")
        + (f"\nO que o aluno respondeu:\n{respostas_txt}\n" if respostas_txt else "")
        + (f"\nO aluno pediu agora: {nota}\n" if nota.strip() else "")
        + (f"\n{feitos_txt}\n" if feitos_txt else "")
        + "\nLê a matéria das fontes e divide-a nos TEMAS que o aluno tem de estudar em cada cadeira, pela ordem em que "
        "a matéria se dá (no máximo 12 por cadeira). Usa temas concretos tirados das fontes (capítulos, conceitos), nada "
        "genérico. Para cada tema indica a dificuldade para este aluno (Fácil, Média ou Difícil), a importância para a "
        "avaliação (Baixa, Média ou Alta) e três tarefas curtas, claras e concretas, começadas por um verbo e sem horas "
        "nem durações: «estudar» (ex.: «Estudar funções: domínio e contradomínio»), «praticar» (ex.: «Resolver os "
        "exercícios 3 a 8 da ficha 2») e «rever» (ex.: «Rever os teoremas de limites e fazer um resumo»). Não ponhas "
        "datas: a app distribui as tarefas pelos dias, com revisões espaçadas e um teste de treino antes de cada "
        "avaliação. Responde só com JSON: "
        '{"resumo": "1-2 frases a explicar a estratégia ao aluno", "cadeiras": [{"cadeira": "nome exato da cadeira", '
        '"temas": [{"tema": "...", "dificuldade": "Média", "importancia": "Alta", "estudar": "...", "praticar": "...", '
        '"rever": "..."}]}], "guia": "markdown: prioridades, os temas difíceis e como os atacar, o que costuma sair, dicas"}')
    r = pedir(fontes_do_ambito(ambito), pedido, json_mode=True)
    if not r:
        return None
    unidades = pe.validar_unidades(r, nomes, cadeira_fixa=ambito.get("cadeira") if ambito.get("tipo") == "cadeira" else None)
    if not unidades:
        st.error("A IA não propôs temas para estudar. Tenta outra vez.")
        return None
    dias, info = pe.distribuir(unidades, limites_do_ambito(ambito), hoje, prefs)
    if not dias:
        st.error("Não há dias de estudo antes da avaliação. Vê os dias em que estudas e tenta outra vez.")
        return None
    return {"unidades": unidades, "dias": dias, "info": info, "guia": str(r.get("guia") or ""),
            "resumo": str(r.get("resumo") or "").strip()[:400]}


def plano_existente(ambito: dict) -> dict:
    return (perfil.get("plano_geral") if ambito.get("tipo") != "cadeira"
            else st.session_state.cadeiras.get(ambito.get("cadeira"), {}).get("plano")) or {}


def distribuir_rascunho(ambito: dict, rascunho: dict, prefs: dict, manter: bool) -> tuple[list, dict]:
    """As tarefas do plano novo. A manter o que já foi feito, os temas já estudados não voltam a ser dados (só revistos)."""
    est, ocup = {}, {}
    if manter and rascunho.get("unidades"):
        cad_fixa = ambito.get("cadeira") if ambito.get("tipo") == "cadeira" else None
        antigo, feitas = plano_existente(ambito).get("dias") or [], set(perfil.get("feitas", []))
        est = pe.estudados(antigo, feitas, cad_fixa)
        ocup = pe.ocupados(antigo, feitas, date.today(), cad_fixa)  # o que já fizeste hoje conta para o ritmo de hoje
    if not est and not ocup:
        return rascunho["dias"], rascunho.get("info") or {}
    return pe.distribuir(rascunho["unidades"], limites_do_ambito(ambito), date.today(), prefs, est, ocup)


def guardar_plano(ambito: dict, rascunho: dict, manter: bool = True) -> None:
    """Guarda o plano. Com manter=True as tarefas já feitas ficam (o resto do plano antigo dá lugar ao novo, que volta a
    incluir essa matéria); sem manter, o plano antigo sai por completo."""
    feitas = set(perfil.get("feitas", []))
    agora = datetime.now().isoformat(timespec="seconds")
    novo = {k: v for k, v in rascunho.items() if k != "info"}
    if ambito.get("tipo") == "cadeira":
        nome = ambito["cadeira"]
        d = st.session_state.cadeiras[nome]
        antigo = (d.get("plano") or {}).get("dias") or []
        dias = pe.fundir(antigo, rascunho["dias"], feitas, date.today(), nome) if manter and antigo else rascunho["dias"]
        r = repo().obter(ambito.get("avaliacao_id")) or repo().proxima(nome)
        d["plano"] = {**novo, "dias": pe.ordenar(dias), "avaliacao_id": r["id"] if r else None,
                      "data_avaliacao": r["data"] if r else None, "cadeira": nome, "criado": agora}
        guardar(nome)
        ids_antigos = pe.ids_do_plano(antigo, nome)
    else:
        antigo = (perfil.get("plano_geral") or {}).get("dias") or []
        dias = pe.fundir(antigo, rascunho["dias"], feitas, date.today()) if manter and antigo else rascunho["dias"]
        perfil["plano_geral"] = {**novo, "dias": pe.ordenar(dias), "datas": av.fotografia_datas(repo()), "criado": agora}
        ids_antigos = pe.ids_do_plano(antigo)
    if not manter and ids_antigos:
        perfil["feitas"] = [f for f in perfil.get("feitas", []) if f not in ids_antigos]
    guardar_perfil()


def planos_existentes() -> list:
    """[(origem, cadeira, plano)]: o plano geral ("g") e os de cada cadeira ("c") que têm tarefas."""
    lista = []
    if (perfil.get("plano_geral") or {}).get("dias"):
        lista.append(("g", None, perfil["plano_geral"]))
    for nome, d in st.session_state.cadeiras.items():
        if (d.get("plano") or {}).get("dias"):
            lista.append(("c", nome, d["plano"]))
    return lista


def ambito_do_plano(origem: str, nome: str | None, plano: dict) -> dict:
    if origem == "g":
        return {"tipo": "geral"}
    alvo = repo().obter(plano.get("avaliacao_id")) or repo().proxima(nome)
    return {"tipo": "cadeira", "cadeira": nome, "avaliacao_id": alvo["id"] if alvo else None}


def apagar_plano(origem: str, nome: str | None) -> None:
    if origem == "g":
        dias = (perfil.pop("plano_geral", None) or {}).get("dias") or []
        ids = pe.ids_do_plano(dias)
    else:
        dias = (st.session_state.cadeiras[nome].pop("plano", None) or {}).get("dias") or []
        ids = pe.ids_do_plano(dias, nome)
        guardar(nome)
    perfil["feitas"] = [f for f in perfil.get("feitas", []) if f not in ids]
    guardar_perfil()


def localizar_sessao(ident: str):
    for origem, nome, plano in planos_existentes():
        for i, s in enumerate(plano["dias"]):
            if av.id_sessao(s, nome) == ident:
                return origem, nome, plano, i
    return None


def guardar_dono(origem: str, nome: str | None) -> None:
    if origem == "c":
        guardar(nome)
    guardar_perfil()


def alterar_sessao(ident: str, **campos) -> str | None:
    """Muda uma tarefa (dia, tipo, texto...). Se o identificador mudar, continua marcada como feita."""
    loc = localizar_sessao(ident)
    if not loc:
        return None
    origem, nome, plano, i = loc
    plano["dias"][i].update(campos)
    for campo in ("hora", "duracao_min"):  # de planos antigos: o plano já não tem horas nem durações
        plano["dias"][i].pop(campo, None)
    novo = av.id_sessao(plano["dias"][i], nome)
    feitas = perfil.setdefault("feitas", [])
    if novo != ident and ident in feitas:
        feitas[feitas.index(ident)] = novo
    plano["dias"] = pe.ordenar(plano["dias"])
    guardar_dono(origem, nome)
    return novo


def apagar_sessao(ident: str) -> None:
    loc = localizar_sessao(ident)
    if loc:
        origem, nome, plano, i = loc
        plano["dias"].pop(i)
        perfil["feitas"] = [f for f in perfil.get("feitas", []) if f != ident]
        if not plano["dias"]:
            apagar_plano(origem, nome)
        else:
            guardar_dono(origem, nome)


def plano_de(origem: str, nome: str | None) -> dict | None:
    return perfil.get("plano_geral") if origem == "g" else st.session_state.cadeiras.get(nome, {}).get("plano")


def limites_do_plano(origem: str, nome: str | None, plano: dict) -> dict:
    """{cadeira: data da avaliação} com as datas de agora (para reorganizar). No plano geral, uma cadeira que já não tem
    avaliações por vir fica com a data de hoje: as tarefas por fazer dela saem do plano."""
    if origem == "c":
        alvo = repo().obter(plano.get("avaliacao_id")) or repo().proxima(nome)
        return {nome: av.para_data(alvo["data"]) if alvo else None}
    limites = {}
    for c in {t.get("cadeira") for t in plano.get("dias", []) if t.get("cadeira")}:
        futuras = repo().proximas(c) if c in st.session_state.cadeiras else []
        limites[c] = av.para_data(futuras[-1]["data"]) if futuras else date.today()
    return limites


def reorganizar_plano(origem: str, nome: str | None) -> dict | None:
    """Volta a distribuir o que está por fazer pelos dias que faltam (sem IA): o que ficou para trás não se perde nem se
    acumula no mesmo dia, as datas das avaliações são respeitadas e o que já foi feito não muda."""
    plano = plano_de(origem, nome)
    if not plano or not plano.get("dias"):
        return None
    novos, info = pe.reorganizar(plano["dias"], set(perfil.get("feitas", [])), date.today(),
                                 limites_do_plano(origem, nome, plano), prefs_plano(), cadeira=nome)
    plano["dias"] = novos
    if origem == "c":
        alvo = repo().obter(plano.get("avaliacao_id")) or repo().proxima(nome)
        if alvo:
            plano["avaliacao_id"], plano["data_avaliacao"] = alvo["id"], alvo["data"]
        guardar(nome)
    else:
        plano["datas"] = av.fotografia_datas(repo())
    guardar_perfil()
    return info


def texto_reorganizado(info: dict) -> str:
    movidas = info.get("movidas", 0)
    partes = [f"Plano reorganizado: {movidas} {'tarefa mudou' if movidas == 1 else 'tarefas mudaram'} de dia."
              if movidas else "Plano reorganizado: não foi preciso mudar nada de dia."]
    if info.get("retiradas"):
        partes.append(f"{info['retiradas']} {'tarefa' if info['retiradas'] == 1 else 'tarefas'} de avaliações que já "
                      "passaram saíram do plano.")
    if info.get("cheios"):
        partes.append("Falta pouco tempo para a avaliação: alguns dias ficaram com mais tarefas do que o teu ritmo.")
    if info.get("revisoes_cortadas"):
        partes.append(f"{info['revisoes_cortadas']} {'revisão extra ficou' if info['revisoes_cortadas'] == 1 else 'revisões extra ficaram'} "
                      "de fora por falta de dias.")
    return " ".join(partes)


def reorganizar_cb(origem: str, nome: str | None) -> None:
    info = reorganizar_plano(origem, nome)
    if info is not None:
        st.session_state.cal_msg = texto_reorganizado(info)


def adiar_tarefa(ident: str) -> str | None:
    """Passa uma tarefa por fazer para o próximo dia de estudo (nunca para o dia da avaliação ou depois)."""
    loc = localizar_sessao(ident)
    if not loc:
        return None
    origem, nome, plano, i = loc
    cadeira = plano["dias"][i].get("cadeira") or nome
    limite = limites_do_plano(origem, nome, plano).get(cadeira)
    novo = pe.adiar(plano["dias"], ident, date.today(), prefs_plano()["folga"], nome, limite=limite)
    if novo:
        plano["dias"] = pe.ordenar(plano["dias"])
        guardar_dono(origem, nome)
    return novo


# ---------------------------------------------------------------- assistente do plano (janela em 4 passos)
PASSOS_PLANO = ["O que planear", "Como estudas", "Perguntas da IA", "O teu plano"]
ESTILO_PLANO = """<style>
.pl-passos { display:flex; gap:0.35rem; margin:0 0 1rem; flex-wrap:wrap; }
.pl-passos span { font-size:0.78rem; padding:0.2rem 0.7rem; border-radius:999px; background:var(--bolha); color:var(--suave);
  white-space:nowrap; }
.pl-passos span.on { background:var(--primario); color:#fff; font-weight:600; }
.pl-passos span.ok { background:var(--acento-claro); color:var(--acento-esc); }
.pl-titulo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.35rem; font-weight:600; color:var(--texto); margin:0 0 0.2rem; }
.pl-sub { color:var(--suave); font-size:0.9rem; margin:0 0 0.8rem; }
.pl-barras { display:flex; flex-direction:column; gap:0.35rem; margin:0.3rem 0 0.6rem; }
.pl-barra { display:grid; grid-template-columns:minmax(0, 9rem) 1fr auto; gap:0.6rem; align-items:center; font-size:0.82rem; color:var(--texto); }
.pl-barra span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pl-barra div { height:7px; border-radius:99px; background:var(--bolha); overflow:hidden; }
.pl-barra div i { display:block; height:100%; border-radius:99px; }
.pl-barra b { font-weight:500; color:var(--suave); font-size:0.78rem; }
.pl-chips { display:flex; flex-wrap:wrap; gap:0.3rem; }
.pl-chip { display:inline-flex; align-items:center; font-size:0.76rem; padding:0.08rem 0.6rem; border-radius:999px;
  background:var(--bolha); color:var(--texto); white-space:nowrap; }
.pl-ponto { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:0.4rem; flex:none; }
/* um cartão por dia: nome do dia, data, progresso discreto e as tarefas (sem horas nem durações) */
.pl-grade { display:grid; grid-template-columns:repeat(auto-fill, minmax(15rem, 1fr)); gap:0.6rem; }
.pl-cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:var(--r-md); padding:0.7rem 0.85rem 0.6rem;
  min-width:0; }
.pl-dcab { display:flex; align-items:baseline; justify-content:space-between; gap:0.5rem; margin:0 0 0.3rem; min-width:0; }
.pl-dcab > div { min-width:0; }
.pl-dcab b { font-weight:600; color:var(--texto); font-size:0.95rem; margin-right:0.35rem; }
.pl-dcab span { color:var(--suave); font-size:0.8rem; }
.pl-dcab .n { font-variant-numeric:tabular-nums; font-size:0.78rem; white-space:nowrap; flex:none; }
.pl-dcab .n.ok { color:var(--sucesso); font-weight:600; }
.pl-dbarra { height:3px; border-radius:99px; background:var(--bolha); overflow:hidden; margin:0 0 0.45rem; }
.pl-dbarra i { display:block; height:100%; background:var(--sucesso); border-radius:99px; }
.pl-tar { display:flex; align-items:baseline; font-size:0.88rem; color:var(--texto); padding:0.2rem 0 0.2rem 0.5rem; line-height:1.35;
  border-left:3px solid var(--cor, var(--acento)); margin-bottom:0.25rem; }
.pl-tar b { font-weight:600; }
/* no plano guardado: cada dia num cartão com uma caixa para marcar cada tarefa */
[class*="st-key-pldia_"], [class*="st-key-plpend_"] { background:var(--cartao); border:1px solid var(--linha);
  border-radius:var(--r-md); padding:0.7rem 0.85rem 0.55rem; gap:0.2rem !important; }
[class*="st-key-pldia_"][class*="_hoje"] { border:1.5px solid var(--acento); box-shadow:0 0 0 3px var(--acento-claro); }
[class*="st-key-plpend_"] { border-color:var(--aviso); }
[class*="st-key-pldia_"] [data-testid="stMarkdownContainer"]:has(.pl-dcab),
[class*="st-key-plpend_"] [data-testid="stMarkdownContainer"]:has(.pl-dcab) { margin-bottom:0 !important; }
.stApp [class*="st-key-pltar_"] { flex-wrap:nowrap !important; gap:0.2rem !important; align-items:flex-start !important;
  border-left:3px solid var(--cor, var(--acento)) !important; padding-left:0.45rem; }
[class*="st-key-pltar_"] [data-testid="stCheckbox"] { flex:1 1 0 !important; min-width:0 !important; width:auto !important; }
[class*="st-key-pltar_"] [data-testid="stCheckbox"] [data-testid="stMarkdownContainer"],
[class*="st-key-pltar_"] [data-testid="stCheckbox"] p { white-space:normal !important; overflow:visible !important;
  text-overflow:clip !important; }
[class*="st-key-pltar_"] [data-testid="stCheckbox"] p { font-size:0.88rem; line-height:1.35; overflow-wrap:anywhere; }
[class*="st-key-pltar_"]:has(input:checked) [data-testid="stCheckbox"] p { text-decoration:line-through; color:var(--suave); }
[class*="st-key-pltar_"] [data-testid="stButton"] { flex:none !important; width:auto !important; }
[class*="st-key-pltar_"] [data-testid="stButton"] button { min-height:1.5rem; padding:0 0.25rem; color:var(--suave); }
""" + "".join(f'[class*="st-key-pltar_"][class*="_cor{i}"] {{ --cor:{c}; }}\n' for i, c in enumerate(CORES_TAREFAS)) + "</style>"


def novo_assistente_plano(ambito: dict | None = None) -> None:
    """on_click: abre o assistente do plano (a janela abre na execução seguinte, em qualquer página que o peça)."""
    st.session_state.plano_wiz = {"passo": 1, "ambito": ambito or {"tipo": "geral"}, "prefs": prefs_plano(),
                                  "perguntas": None, "respostas": {}, "nota": "", "rascunho": None}
    st.session_state.abrir_plano_pedido = True


def abrir_plano_se_pedido() -> bool:
    """Abre o assistente se alguém o pediu (botão, outra janela, passo seguinte). Devolve True se abriu."""
    if st.session_state.pop("abrir_plano_pedido", None) and st.session_state.get("plano_wiz"):
        dialogo_plano()
        return True
    return False


def passo_plano(n: int) -> None:
    st.session_state.plano_wiz["passo"] = n
    st.session_state.abrir_plano_pedido = True
    st.rerun(scope="fragment")


def n_tarefas(n: int) -> str:
    return f"{n} {'tarefa' if n == 1 else 'tarefas'}"


def nome_do_dia(dia) -> tuple[str, str]:
    """(«Hoje» / «Amanhã» / «Quinta-feira», «19 de novembro»)."""
    d, hoje = av.para_data(dia), date.today()
    data_ = f"{d.day} de {av.MESES[d.month - 1].lower()}" + (f" de {d.year}" if d.year != hoje.year else "")
    especial = {hoje: "Hoje", hoje + timedelta(days=1): "Amanhã", hoje - timedelta(days=1): "Ontem"}.get(d)
    if especial:
        return especial, f"{DIAS_LONGOS[d.weekday()]}, {data_}"
    return DIAS_LONGOS[d.weekday()].capitalize(), data_


def cabecalho_dia_html(dia, total: int, feitas: int | None = None) -> str:
    """Cabeçalho do cartão de um dia; com «feitas», um progresso discreto (2/4 e uma barra fina)."""
    nome, data_ = nome_do_dia(dia)
    if feitas is None:
        conta, barra = f"<span class='n'>{n_tarefas(total)}</span>", ""
    else:
        conta = (f"<span class='n ok'>✓ {feitas}/{total}</span>" if total and feitas >= total
                 else f"<span class='n'>{feitas}/{total}</span>")
        barra = f"<div class='pl-dbarra'><i style='width:{100 * feitas / max(1, total):.0f}%'></i></div>"
    return f"<div class='pl-dcab'><div><b>{escape(nome)}</b><span>{escape(data_)}</span></div>{conta}</div>{barra}"


def plano_previa_html(tarefas: list) -> str:
    """Pré-visualização (só leitura): um cartão por dia com «Cadeira — tarefa»."""
    cartoes = []
    for dia, lista in pe.por_dia(tarefas).items():
        linhas = "".join(f"<div class='pl-tar' style='--cor:{cor_cadeira(t.get('cadeira') or '')}'><span><b>"
                         f"{escape(str(t.get('cadeira') or ''))}</b> — {escape(pe.texto_da_tarefa(t)[0])}</span></div>"
                         for t in lista)
        cartoes.append(f"<div class='pl-cartao'>{cabecalho_dia_html(dia, len(lista))}{linhas}</div>")
    return "<div class='pl-grade'>" + "".join(cartoes) + "</div>"


def barras_cadeiras_html(por_cadeira: dict) -> str:
    maior = max(por_cadeira.values() or [1]) or 1
    return "<div class='pl-barras'>" + "".join(
        f"<div class='pl-barra'><span>{escape(n)}</span><div><i style='width:{100 * m / maior:.0f}%;background:{cor_cadeira(n)}'>"
        f"</i></div><b>{n_tarefas(m)}</b></div>" for n, m in sorted(por_cadeira.items(), key=lambda kv: -kv[1])) + "</div>"


def avisos_do_rascunho(info: dict) -> None:
    if info.get("sem_dias"):
        st.warning(f"Sem dias de estudo antes da avaliação de {', '.join(info['sem_dias'])}: escolhe mais dias no passo 2.",
                   icon=":material/event_busy:")
    if info.get("cheios"):
        st.caption(f":material/info: Falta pouco tempo: em {len(info['cheios'])} "
                   f"{'dia há' if len(info['cheios']) == 1 else 'dias há'} mais tarefas do que o teu ritmo, para caber a "
                   "matéria toda antes da avaliação.")


def _assistente_plano() -> None:
    wiz = st.session_state.get("plano_wiz")
    st.session_state.pop("abrir_plano_pedido", None)
    if not wiz:
        st.caption("O assistente foi fechado.")
        return
    passo = wiz.get("passo", 1)
    st.markdown(ESTILO_PLANO + "<div class='pl-passos'>" + "".join(
        f"<span class='{'on' if i + 1 == passo else 'ok' if i + 1 < passo else ''}'>{i + 1} · {t}</span>"
        for i, t in enumerate(PASSOS_PLANO)) + "</div>", unsafe_allow_html=True)

    if passo == 1:  # ------------------------------------------------ o que planear
        futuras = repo().proximas()
        st.markdown("<div class='pl-titulo'>O que queres planear?</div><div class='pl-sub'>O plano vai de hoje até ao dia "
                    "anterior a cada avaliação e aparece no Calendário.</div>", unsafe_allow_html=True)
        if not futuras:
            st.info("Ainda não tens avaliações marcadas. Marca primeiro os testes e exames: o plano é feito à volta delas.")
            if st.button("Marcar uma avaliação", icon=":material/add:", type="primary", key="plw_marcar"):
                st.session_state.pop("plano_wiz", None)
                navegar("calendario", nova_avaliacao_dia=date.today().isoformat())
                st.rerun()
            return
        amb = wiz["ambito"]
        modo = st.radio("Plano", ["geral", "avaliacao"], index=1 if amb.get("tipo") == "cadeira" else 0, key="plw_modo",
                        format_func={"geral": "Todas as salas (divide o tempo entre elas)",
                                     "avaliacao": "Só uma avaliação"}.get, label_visibility="collapsed")
        escolha = None
        if modo == "avaliacao":
            ids = [r["id"] for r in futuras]
            pre = amb.get("avaliacao_id") if amb.get("avaliacao_id") in ids else next(
                (r["id"] for r in futuras if r["cadeira"] == amb.get("cadeira")), ids[0])
            escolha = st.selectbox("Avaliação", ids, index=ids.index(pre), key="plw_aval",
                                   format_func=lambda i: f"{repo().obter(i)['cadeira']} · {repo().obter(i)['nome']} · "
                                                         f"{fmt_data(repo().obter(i)['data'], False)} ({av.texto_faltam(repo().obter(i))})")
        novo = {"tipo": "geral"} if modo == "geral" else {"tipo": "cadeira", "cadeira": repo().obter(escolha)["cadeira"],
                                                          "avaliacao_id": escolha}
        existe = (perfil.get("plano_geral") if novo["tipo"] == "geral"
                  else st.session_state.cadeiras.get(novo["cadeira"], {}).get("plano")) or {}
        nomes_sem_fontes = [n for n in cadeiras_do_ambito(novo) if not st.session_state.cadeiras[n]["ficheiros"]]
        if existe.get("dias"):
            st.caption(":material/info: Já tens um plano para isto. No fim podes escolher manter as tarefas que já fizeste.")
        if nomes_sem_fontes:
            st.caption(f":material/warning: Sem fontes em {', '.join(nomes_sem_fontes)}: a IA planeia sem conhecer a matéria. "
                       "Junta as fontes na sala para temas mais concretos.")
        if st.button("Seguinte", type="primary", icon=":material/arrow_forward:", key="plw_seg1", width="stretch"):
            if novo != wiz["ambito"]:
                wiz.update(perguntas=None, respostas={}, rascunho=None)
            wiz["ambito"] = novo
            passo_plano(2)
        return

    if passo == 2:  # ------------------------------------------------ como estudas
        prefs = wiz["prefs"]
        st.markdown("<div class='pl-titulo'>Como gostas de estudar?</div><div class='pl-sub'>Fica guardado para os "
                    "próximos planos. O plano diz o que estudar em cada dia, sem horários: o tempo organizas tu.</div>",
                    unsafe_allow_html=True)
        dias = st.pills("Dias em que estudas", pe.DIAS_SEMANA, selection_mode="multi", key="plw_dias",
                        default=[d for d in pe.DIAS_SEMANA if d not in prefs["folga"]])
        ritmo = st.segmented_control("Ritmo", list(pe.RITMOS), default=prefs["ritmo"], key="plw_ritmo") or prefs["ritmo"]
        st.caption(" · ".join(f"{r}: até {n} tarefas por dia" for r, n in pe.RITMOS.items())
                   + ". Conta com todas as salas juntas.")
        comecar = st.radio("Por onde começar", pe.COMECAR, index=pe.COMECAR.index(prefs["comecar"]), key="plw_com",
                           horizontal=True)
        estilo = st.segmented_control("Estilo", pe.ESTILOS, default=prefs["estilo"], key="plw_est") or prefs["estilo"]
        nomes = cadeiras_do_ambito(wiz["ambito"])
        st.markdown("**Como sentes a matéria de cada sala**")
        objetivos = {}
        for n in nomes:
            obj = objetivo(st.session_state.cadeiras[n])
            a, b, c = st.columns([2.2, 2.4, 1.2], vertical_alignment="center")
            a.markdown(f"<span class='pl-ponto' style='background:{cor_cadeira(n)}'></span>{escape(n)}", unsafe_allow_html=True)
            dif = b.segmented_control(f"Dificuldade de {n}", pe.DIFICULDADES, default=obj.get("dificuldade") or "Média",
                                      key=f"plw_dif_{chave_curta(n)}", label_visibility="collapsed") or obj.get("dificuldade") or "Média"
            nota = c.number_input(f"Nota pretendida em {n}", 10, 20, int(obj.get("nota_alvo") or 14), key=f"plw_nota_{chave_curta(n)}",
                                  label_visibility="collapsed", help="Nota que queres tirar")
            objetivos[n] = (dif, nota)
        st.caption("A nota é a que queres tirar (10 a 20). A IA tem isto em conta ao avaliar a dificuldade de cada tema: "
                   "os temas difíceis têm mais revisões e exercícios para refazer.")
        v, s_ = st.columns(2)
        if v.button("Voltar", icon=":material/arrow_back:", key="plw_voltar2", width="stretch"):
            passo_plano(1)
        if s_.button("Seguinte", type="primary", icon=":material/arrow_forward:", key="plw_seg2", width="stretch"):
            if not dias:
                st.error("Escolhe pelo menos um dia em que podes estudar.")
                return
            wiz["prefs"] = pe.preferencias({"folga": [d for d in pe.DIAS_SEMANA if d not in dias], "ritmo": ritmo,
                                            "comecar": comecar, "estilo": estilo})
            guardar_prefs_plano(wiz["prefs"])
            for n, (dif, nota) in objetivos.items():
                st.session_state.cadeiras[n]["objetivo"] = {**objetivo(st.session_state.cadeiras[n]), "dificuldade": dif,
                                                            "nota_alvo": int(nota)}
                guardar(n)
            wiz["rascunho"] = None
            passo_plano(3)
        return

    if passo == 3:  # ------------------------------------------------ perguntas da IA
        if wiz.get("perguntas") is None:
            with a_pensar("A ler a matéria para te fazer umas perguntas"):
                wiz["perguntas"] = perguntas_ia_plano(wiz["ambito"]) if tem_chave else []
        st.markdown("<div class='pl-titulo'>Umas perguntas rápidas</div><div class='pl-sub'>Quanto mais souber de ti, melhor "
                    "fica o plano. Podes deixar em branco o que não quiseres responder.</div>", unsafe_allow_html=True)
        respostas = {}
        for p in wiz["perguntas"]:
            anterior = wiz["respostas"].get(p["id"])
            if p["tipo"] == "multipla":
                respostas[p["id"]] = st.multiselect(p["pergunta"], p["opcoes"], key=f"plw_{p['id']}",
                                                    default=[o for o in (anterior or []) if o in p["opcoes"]],
                                                    placeholder="Escolhe uma ou mais opções")
            elif p["tipo"] == "escolha":
                respostas[p["id"]] = st.radio(p["pergunta"], p["opcoes"], key=f"plw_{p['id']}",
                                              index=p["opcoes"].index(anterior) if anterior in p["opcoes"] else None)
            else:
                respostas[p["id"]] = st.text_input(p["pergunta"], value=anterior or "", key=f"plw_{p['id']}")
        if not wiz["perguntas"]:
            st.caption("Desta vez a IA não preparou perguntas, mas podes contar-lhe o que quiseres aqui em baixo.")
        extra = st.text_area("Mais alguma coisa que a IA deva saber? (opcional)", value=wiz.get("nota", ""), height=80,
                             key="plw_extra", placeholder="ex.: às quartas tenho aulas até às 18h; quero o fim de semana "
                                                          "mais leve; já sei bem a primeira parte da matéria")
        v, s_ = st.columns(2)
        if v.button("Voltar", icon=":material/arrow_back:", key="plw_voltar3", width="stretch"):
            passo_plano(2)
        if s_.button("Criar o plano", type="primary", icon=":material/auto_awesome:", key="plw_criar", width="stretch",
                     disabled=not tem_chave):
            wiz.update(respostas=respostas, nota=extra.strip(), rascunho=None)
            passo_plano(4)
        return

    # ---------------------------------------------------------------- o teu plano (pré-visualização antes de guardar)
    ambito = wiz["ambito"]
    if wiz.get("rascunho") is None:
        respostas = []
        for p in wiz.get("perguntas") or []:
            valor = wiz["respostas"].get(p["id"])
            respostas.append((p["pergunta"], ", ".join(valor) if isinstance(valor, list) else valor or ""))
        with a_pensar("A montar o teu plano"):
            wiz["rascunho"] = gerar_rascunho_plano(ambito, wiz["prefs"], respostas, wiz.get("nota", "")) or False
    rascunho = wiz["rascunho"]
    if not rascunho:
        v, s_ = st.columns(2)
        if v.button("Voltar", icon=":material/arrow_back:", key="plw_voltar4e", width="stretch"):
            passo_plano(3)
        if s_.button("Tentar outra vez", icon=":material/refresh:", key="plw_tentar", width="stretch", type="primary"):
            wiz["rascunho"] = None
            passo_plano(4)
        return
    existe = plano_existente(ambito)
    # o interruptor «Manter» fica no fim, mas a pré-visualização já mostra o plano com a escolha feita
    manter = bool(st.session_state.get("plw_manter", True)) if existe.get("dias") else True
    dias, info = distribuir_rascunho(ambito, rascunho, wiz["prefs"], manter)
    res = pe.resumo(dias, set(), None)
    n_dias = len({t["data"] for t in dias})
    st.markdown(f"<div class='pl-titulo'>O teu plano · {escape(texto_ambito(ambito))}</div><div class='pl-sub'>"
                f"{n_tarefas(res['total'])} em {n_dias} {'dia' if n_dias == 1 else 'dias'} · de "
                f"{fmt_data(res['inicio'], False)} a {fmt_data(res['fim'], False)}</div>", unsafe_allow_html=True)
    if rascunho.get("resumo"):
        st.info(rascunho["resumo"], icon=":material/lightbulb:")
    avisos_do_rascunho(info)
    if len(res["por_cadeira"]) > 1:
        st.markdown(barras_cadeiras_html(res["por_cadeira"]), unsafe_allow_html=True)
    with st.container(height=380, border=False):
        st.markdown(plano_previa_html(dias), unsafe_allow_html=True)
    if rascunho.get("guia"):
        with st.expander("Conselhos da IA para este plano", icon=":material/tips_and_updates:"):
            md(rascunho["guia"])
    ajuste = st.text_input("Queres mudar alguma coisa?", key="plw_ajuste",
                           placeholder="ex.: começa por integrais; junta o capítulo 4; mais exercícios de derivadas")
    if existe.get("dias"):
        st.toggle("Manter as tarefas que já fizeste", value=True, key="plw_manter",
                  help="Os temas que já estudaste só voltam em revisões. Desligado: o plano antigo é substituído por completo.")
    v, r_, g = st.columns([1, 1.15, 1.6])
    if v.button("Voltar", icon=":material/arrow_back:", key="plw_voltar4", width="stretch"):
        passo_plano(3)
    if r_.button("Refazer", icon=":material/refresh:", key="plw_refazer", width="stretch", disabled=not tem_chave,
                 help="A IA faz outro plano, com o que escreveste em «Queres mudar alguma coisa?»."):
        wiz["nota"] = "\n".join(x for x in [wiz.get("nota", ""), ajuste.strip()] if x)
        wiz["rascunho"] = None
        passo_plano(4)
    if g.button("Guardar no calendário", type="primary", icon=":material/event_available:", key="plw_guardar", width="stretch"):
        guardar_plano(ambito, {**rascunho, "dias": dias}, manter)
        st.session_state.pop("plano_wiz", None)
        st.session_state.cal_msg = f"Plano guardado: {n_tarefas(res['total'])} no calendário."
        st.rerun()


dialogo_plano = janela("Plano de estudo com IA", width="large")(_assistente_plano)


# ---------------------------------------------------------------- uma tarefa do plano (ver, marcar, adiar, mudar, apagar)
def _janela_sessao(ident: str) -> None:
    loc = localizar_sessao(ident)
    if not loc:
        st.warning("Esta tarefa já não existe (o plano pode ter sido reorganizado, refeito ou apagado).")
        return
    origem, nome, plano, i = loc
    s = plano["dias"][i]
    cadeira = s.get("cadeira") or nome
    feita = ident in set(perfil.get("feitas", []))
    h = chave_curta(ident)
    cor = cor_cadeira(cadeira)
    principal, detalhe = pe.texto_da_tarefa(s)
    st.markdown(ESTILO_PLANO, unsafe_allow_html=True)
    st.markdown(f"<div class='pl-chips pl-chips-topo'><span class='pl-chip' style='background:{cor}26;"
                f"color:var(--texto)'><span class='pl-ponto' style='background:{cor}'></span>{escape(cadeira)}</span>"
                f"<span class='pl-chip'>{escape(pe.tipo_de(s))}</span>"
                f"<span class='pl-chip'>{'Plano geral' if origem == 'g' else 'Plano da sala'}</span></div>"
                f"<div class='pl-titulo'>{escape(principal)}</div>"
                f"<div class='pl-sub'>{escape(data_longa(s['data']).capitalize())}</div>", unsafe_allow_html=True)
    if detalhe:
        with st.container(border=True):
            md(detalhe)
    nova = st.toggle("Feita", value=feita, key=f"sesd_feita_{h}")
    if nova != feita:
        marcar_sessao(ident, nova)
        st.rerun(scope="fragment")
    if not feita and st.button("Passar para o próximo dia", icon=":material/redo:", key=f"sesd_adiar_{h}", width="stretch",
                               help="Fica no fim da lista do próximo dia em que estudas."):
        novo = adiar_tarefa(ident)
        if novo:
            st.session_state.cal_msg = f"Tarefa passada para {data_longa(novo.split('|', 1)[0])}."
            st.session_state.cal_ref = av.para_data(novo.split("|", 1)[0])
            st.rerun()
        st.warning("Não há mais dias de estudo antes da avaliação. Podes reorganizar o plano ou mudar o dia à mão.",
                   icon=":material/event_busy:")
    with st.expander("Mudar esta tarefa", icon=":material/edit_calendar:"):
        with st.form(f"form_sessao_{h}", border=False):
            c1, c2 = st.columns(2)
            novo_dia = c1.date_input("Dia", value=av.para_data(s["data"]), format="DD/MM/YYYY")
            tipo = c2.selectbox("Tipo", pe.TIPOS_TAREFA, index=pe.TIPOS_TAREFA.index(pe.tipo_de(s)))
            temas = st.text_input("O que fazer", value=principal)
            tarefas = st.text_area("Pormenores (opcional)", value=detalhe, height=80)
            if st.form_submit_button("Guardar", type="primary", icon=":material/check:", width="stretch"):
                if not temas.strip():
                    st.error("Escreve o que há para fazer.")
                else:
                    alterar_sessao(ident, data=novo_dia.isoformat(), tipo=tipo, temas=" ".join(temas.split()),
                                   tarefas=tarefas.strip())
                    st.session_state.cal_msg = "Tarefa alterada."
                    st.session_state.cal_ref = novo_dia
                    st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("Abrir a sala", icon=":material/menu_book:", key=f"sesd_cad_{h}", width="stretch",
                 disabled=cadeira not in st.session_state.cadeiras):
        navegar("cadeira", cadeira_atual=cadeira)
        st.rerun()
    if st.session_state.get("_apagar_sessao") == ident:
        if c2.button("Sim, apagar", icon=":material/delete:", key=f"sesd_sim_{h}", type="primary", width="stretch"):
            apagar_sessao(ident)
            st.session_state.pop("_apagar_sessao", None)
            st.session_state.cal_msg = "Tarefa apagada do plano."
            st.rerun()
    elif c2.button("Apagar tarefa", icon=":material/delete:", key=f"sesd_apagar_{h}", width="stretch"):
        st.session_state["_apagar_sessao"] = ident
        st.rerun(scope="fragment")


dialogo_sessao = janela("Tarefa de estudo")(_janela_sessao)


def marcar_feita_cb(ident: str, chave: str) -> None:
    marcar_sessao(ident, bool(st.session_state.get(chave)))


def chave_tarefa(prefixo: str, ident: str, feita: bool) -> str:
    """Chave da caixa de uma tarefa. Leva o estado «feita»: quando a tarefa é marcada noutro sítio (Início, plano,
    calendário), a caixa é criada de novo com o valor certo, em vez de ficar com um valor antigo."""
    return f"{prefixo}_{chave_curta(ident)}_{int(bool(feita))}"


def linha_tarefa(t: dict, ident: str, feita: bool, k: str, com_dia: bool = False) -> None:
    """Uma tarefa: caixa para marcar («Cadeira — o que fazer») e um botão discreto para a abrir."""
    cad = t.get("cadeira") or ""
    principal, detalhe = pe.texto_da_tarefa(t)
    indice = indice_cor_sala(cad)
    h = chave_curta(ident)
    with st.container(horizontal=True, key=f"pltar_{k}_{h}_cor{indice}"):
        chave_chk = chave_tarefa(f"plchk_{k}", ident, feita)
        quando = f" · {fmt_data(t['data'], False)}" if com_dia else ""
        st.checkbox(f"**{cad}** — {principal}{quando}", value=feita, key=chave_chk, on_change=marcar_feita_cb,
                    args=(ident, chave_chk), help=detalhe or None, width="stretch")
        if st.button("", icon=":material/more_horiz:", key=f"plabrir_{k}_{h}", type="tertiary",
                     help="Passar para o dia seguinte, mudar ou apagar"):
            dialogo_sessao(ident)


def cartao_plano(origem: str, nome: str | None, plano: dict, chave: str) -> None:
    """Um plano no ecrã: progresso, um cartão por dia com as tarefas para marcar (sem horas nem durações), o que ficou
    por fazer (com «Reorganizar»), Refazer e Apagar."""
    feitas = set(perfil.get("feitas", []))
    res = pe.resumo(plano["dias"], feitas, nome)
    alvo = repo().obter(plano.get("avaliacao_id")) if origem == "c" else None
    titulo = "Plano geral" if origem == "g" else f"Plano de {nome}"
    sub = (f"para «{alvo['nome']}» · {fmt_data(alvo['data'])} · {av.texto_faltam(alvo)}" if alvo
           else f"todas as salas · até {fmt_data(res['fim'])}" if origem == "g" and res["fim"] else "")
    k = f"{chave}_{origem}_{chave_curta(nome or 'geral')}"
    st.markdown(ESTILO_PLANO, unsafe_allow_html=True)
    with st.container(border=True, key=f"plcard_{k}"):
        c1, c2, c3 = st.columns([4, 1.25, 1.2], vertical_alignment="center")
        c1.markdown(f"<div class='pl-titulo'>{escape(titulo)}</div><div class='pl-sub sem-margem'>{escape(sub)}</div>",
                    unsafe_allow_html=True)
        c2.button("Refazer", icon=":material/auto_awesome:", key=f"plrefazer_{k}", width="stretch", disabled=not tem_chave,
                  help="A IA volta a perguntar-te e faz um plano novo.", on_click=novo_assistente_plano,
                  args=(ambito_do_plano(origem, nome, plano),))
        with c3.popover("Apagar", icon=":material/delete:", width="stretch"):
            st.caption("Tira todas as tarefas deste plano do calendário. As avaliações ficam.")
            if st.button("Sim, apagar o plano", type="primary", icon=":material/delete:", key=f"plapagar_{k}"):
                apagar_plano(origem, nome)
                st.session_state.cal_msg = f"{titulo} apagado."
                st.rerun()
        st.progress(res["feitas"] / max(1, res["total"]), text=f"{res['feitas']} de {n_tarefas(res['total'])} feitas")
        if plano.get("resumo"):
            st.caption(plano["resumo"])
        if origem == "g" and len(res["por_cadeira"]) > 1:
            st.markdown(barras_cadeiras_html(res["por_cadeira"]), unsafe_allow_html=True)
        quais = st.segmented_control("Dias", ["Próximos dias", "Todo o plano"], default="Próximos dias",
                                     key=f"plquais_{k}", label_visibility="collapsed") or "Próximos dias"
        hoje_iso = date.today().isoformat()
        grupos = pe.por_dia(plano["dias"])
        atrasadas = [t for t in pe.ordenar(plano["dias"])
                     if str(t.get("data"))[:10] < hoje_iso and av.id_sessao(t, nome) not in feitas]
        if atrasadas:
            with st.container(key=f"plpend_{k}"):
                st.markdown(f"<div class='pl-dcab'><div><b>Ficaram por fazer</b><span>{n_tarefas(len(atrasadas))} de dias "
                            "que já passaram</span></div></div>", unsafe_allow_html=True)
                if quais == "Próximos dias":  # em «Todo o plano» aparecem no dia de cada uma
                    for t in atrasadas[:8]:
                        linha_tarefa(t, av.id_sessao(t, nome), False, f"{k}_p", com_dia=True)
                    if len(atrasadas) > 8:
                        st.caption(f"e mais {len(atrasadas) - 8}.")
                st.button("Reorganizar o plano", icon=":material/event_repeat:", key=f"plreorg_{k}",
                          on_click=reorganizar_cb, args=(origem, nome),
                          help="Espalha o que ficou por fazer pelos dias que faltam até à avaliação, sem sobrecarregar "
                               "nenhum dia. O que já fizeste não muda.")
        futuros = [d for d in grupos if d >= hoje_iso]
        mostrar = futuros[:6] if quais == "Próximos dias" else list(grupos)[:90]
        if not mostrar:
            st.caption("Não há tarefas por vir neste plano.")
        for cel, dia in zip(celulas_grelha(len(mostrar), 2, gap="small"), mostrar):
            lista = grupos[dia]
            ids = [av.id_sessao(t, nome) for t in lista]
            with cel.container(key=f"pldia_{k}_{dia}{'_hoje' if dia == hoje_iso else ''}"):
                st.markdown(cabecalho_dia_html(dia, len(lista), sum(i_ in feitas for i_ in ids)), unsafe_allow_html=True)
                for t, ident in zip(lista, ids):
                    linha_tarefa(t, ident, ident in feitas, k)
        if quais == "Próximos dias" and len(futuros) > len(mostrar):
            st.caption(f"Mais {len(futuros) - len(mostrar)} dias no plano: escolhe «Todo o plano» para os veres.")
        if plano.get("guia"):
            with st.expander("Conselhos da IA", icon=":material/tips_and_updates:"):
                md(plano["guia"])


def avisos_de_planos() -> list:
    """Planos criados para datas que entretanto mudaram. Nada é alterado sem o utilizador pedir."""
    avisos = []
    feitas = set(perfil.get("feitas", []))
    for nome, d in st.session_state.cadeiras.items():
        estado = av.estado_plano_cadeira(d.get("plano"), repo(), feitas)
        if estado:
            if estado["motivo"] == "apagada":
                txt = (f"O plano de **{nome}** era para uma avaliação que foi apagada. O plano foi mantido "
                       f"({n_tarefas(estado['concluidas'])} feitas).")
            else:
                txt = (f"A avaliação de **{nome}** mudou de {fmt_data(estado['data_plano'])} para "
                       f"{fmt_data(estado['data_nova'])}. O plano ainda usa a data antiga "
                       f"({n_tarefas(estado['concluidas'])} feitas ficam guardadas"
                       + (f"; {n_tarefas(estado['depois_da_prova'])} ficaram depois da nova data" if estado['depois_da_prova'] else "")
                       + ").")
            avisos.append(("cadeira", nome, txt))
    plano_g = perfil.get("plano_geral") or {}
    if plano_g.get("dias"):
        mudancas = av.mudancas_desde(plano_g.get("datas"), repo())
        if mudancas:
            novas = sum(1 for m in mudancas if m[0] == "nova")
            avisos.append(("geral", None, f"Desde que o plano geral foi criado, {len(mudancas)} avaliação(ões) "
                                          "foram criadas, mudaram de data ou foram apagadas."
                                          + (" Para incluir as avaliações novas no plano, usa «Refazer»." if novas else "")))
    return avisos


def mostrar_avisos_de_planos(chave: str) -> None:
    for tipo, nome, texto in avisos_de_planos():
        with st.container(border=True):
            st.markdown(f":material/update: {texto}")
            if tipo == "cadeira":
                if st.button("Reorganizar o plano (mantém o que já fizeste)", key=f"reorg_{chave}_{nome}"):
                    d = st.session_state.cadeiras[nome]
                    registo = repo().obter(d["plano"].get("avaliacao_id")) or repo().proxima(nome)
                    if registo is None:
                        st.error("Esta sala já não tem avaliações futuras. Cria uma no Calendário.")
                    else:
                        info = reorganizar_plano("c", nome)
                        if info is not None:
                            st.session_state.cal_msg = (texto_reorganizado(info)
                                                        + f" O plano de {nome} vai agora até {fmt_data(registo['data'])}.")
                            st.rerun()
            elif st.button("Atualizar o plano geral (mantém o que já fizeste)", key=f"reorg_{chave}_geral"):
                info = reorganizar_plano("g", None)
                if info is not None:
                    st.session_state.cal_msg = texto_reorganizado(info)
                    st.rerun()


# =============================================================== CALENDÁRIO
SLUG_TIPO = {"Exame": "exame", "Teste": "teste", "Trabalho": "trabalho", "Apresentação": "apresentacao",
             "Outro": "outro"}
DIAS_LONGOS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

ESTILO_CALENDARIO = """
<style>
/* células do mês */
[class*="st-key-diaN_"], [class*="st-key-diaH_"], [class*="st-key-diaF_"] {
    background:var(--cartao); border:1px solid var(--linha); border-radius:12px; padding:0.25rem 0.3rem 0.4rem;
    min-height:112px; gap:0.12rem !important; }
[class*="st-key-diaF_"] { background:transparent; opacity:0.45; }
[class*="st-key-diaH_"] { border:1.5px solid var(--acento); box-shadow:0 0 0 3px var(--acento-claro); }
[class*="st-key-num_"] button { min-height:1.55rem !important; padding:0 0.45rem !important; font-weight:600;
    font-size:0.85rem; border-radius:999px; color:var(--texto); }
[class*="st-key-diaH_"] [class*="st-key-num_"] button { background:var(--primario) !important; }
[class*="st-key-diaH_"] [class*="st-key-num_"] button, [class*="st-key-diaH_"] [class*="st-key-num_"] button * { color:#FFFFFF !important; }
/* eventos */
[class*="st-key-ev_"] button { width:100%; justify-content:flex-start; min-height:1.45rem !important;
    padding:0.05rem 0.4rem !important; border-radius:6px; border:none; border-left:3px solid; }
[class*="st-key-ev_"] button p { font-size:0.76rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
[class*="st-key-ev_exame"] button { background:#DDF0F1; border-left-color:#17798A; color:#0B4F5A; }
[class*="st-key-ev_teste"] button { background:#F8EDD5; border-left-color:#D4A03A; color:#6E5212; }
[class*="st-key-ev_trabalho"] button { background:#E3EEE5; border-left-color:#5E8C6A; color:#2F5239; }
[class*="st-key-ev_apresentacao"] button { background:#E4E9F4; border-left-color:#6A7FB0; color:#33456F; }
[class*="st-key-ev_outro"] button { background:#EEF2F1; border-left-color:#7C8C91; color:#3E4D52; }
[class*="st-key-ev_"][class*="_p_"] button { opacity:0.55; }
[class*="st-key-ev_"][class*="_p_"] button p { text-decoration:line-through; }
[class*="st-key-ses_"] button { width:100%; justify-content:flex-start; min-height:1.3rem !important;
    padding:0 0.4rem !important; border:1px dashed #CFC7B6; background:transparent; border-radius:6px; }
[class*="st-key-ses_"] button p { font-size:0.72rem; color:var(--suave); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* sessões do plano de estudo: uma por linha, com a cor da cadeira (clicar abre a sessão) */
div[class*="st-key-sesc"] button[kind] { width:100%; justify-content:flex-start; min-height:1.35rem !important;
    padding:0.05rem 0.4rem !important; border:none !important; border-left:3px solid !important; border-radius:6px !important; }
div[class*="st-key-sesc"] button p { font-size:0.72rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
div[class*="st-key-sesc"][class*="_f_"] button { opacity:0.5; }
div[class*="st-key-sesc"][class*="_f_"] button p { text-decoration:line-through; }
""" + "".join(f'div[class*="st-key-sesc{i}_"] button[kind] {{ background:{c}24 !important; border-left-color:{c} !important; }}\n'
              f'div[class*="st-key-sesc{i}_"] {{ --cor:{c}; }}\n' for i, c in enumerate(CORES_TAREFAS)) \
  + "".join(f'[class*="st-key-ev_{SLUG_TIPO[t]}"] {{ --cor:{c}; }}\n' for t, c in av.CORES.items()) + """
/* grelha: 7 colunas sempre lado a lado, também no telemóvel */
[class*="st-key-calsem_"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; gap:0.3rem !important; }
[class*="st-key-calsem_"] [data-testid="stColumn"] { min-width:0 !important; flex:1 1 0 !important; width:auto !important; }
.ec-dias-semana { display:grid; grid-template-columns:repeat(7, 1fr); gap:0.3rem; margin:0 0 0.25rem; }
.ec-dias-semana div { text-align:center; font-size:0.75rem; color:var(--suave); font-weight:600; letter-spacing:0.04em; }
.ec-mes { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.55rem; font-weight:600; color:var(--texto);
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ec-legenda { display:flex; flex-wrap:wrap; gap:0.35rem 0.9rem; font-size:0.8rem; color:var(--suave); margin:0.2rem 0 0.6rem; }
.ec-legenda span { display:inline-flex; align-items:center; gap:0.35rem; }
.ec-legenda i { width:10px; height:10px; border-radius:3px; display:inline-block; }
.ec-ponto { width:10px; height:10px; border-radius:3px; display:inline-block; margin-right:0.35rem; }
.ec-agenda-data { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; text-align:center; line-height:1.05; }
.ec-agenda-data b { font-size:1.6rem; display:block; color:var(--texto); }
.ec-agenda-data small { font-size:0.75rem; color:var(--suave); text-transform:uppercase; letter-spacing:0.05em; }
.ec-agenda-data.passou { opacity:0.55; }
/* cada linha da Agenda fica sempre na horizontal (dia | avaliação | Abrir), também no telemóvel */
[class*="st-key-ag_linha_"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; }
[class*="st-key-ag_linha_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:0 !important; }
[class*="st-key-ag_linha_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex:0 0 3rem !important;
    width:3rem !important; }
[class*="st-key-ag_linha_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child { flex:0 0 auto !important;
    width:auto !important; }
.ec-passou { color:var(--suave); font-size:0.78rem; background:var(--bolha); border-radius:999px; padding:0.05rem 0.55rem; white-space:nowrap; }
.ec-faltam { color:var(--acento-esc); font-size:0.78rem; background:var(--acento-claro); border-radius:999px; padding:0.05rem 0.55rem; white-space:nowrap; }
@media (max-width: 640px) {
  [class*="st-key-diaN_"], [class*="st-key-diaH_"], [class*="st-key-diaF_"] { min-height:66px; padding:0.15rem; border-radius:8px; }
  [class*="st-key-ev_"] button p, [class*="st-key-ses_"] button p { font-size:0.6rem; }
  [class*="st-key-ev_"] button, [class*="st-key-ses_"] button { padding:0 0.15rem !important; min-height:1.1rem !important; }
  [class*="st-key-num_"] button { font-size:0.72rem; padding:0 0.25rem !important; }
  .ec-mes { font-size:1.2rem; }

  /* ---- telemóvel: barra compacta — o mês à esquerda e ‹ Hoje › à direita; por baixo as vistas e o «+» */
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { display:grid !important;
      grid-template-columns:minmax(0, 1fr) 5.1rem 2.6rem; grid-template-areas:"tit nav nav" "vis vis novo";
      gap:0.7rem 0.5rem !important; align-items:center; }
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      min-width:0 !important; width:auto !important; }
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) {
      grid-area:nav; }
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { grid-area:tit; }
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) { grid-area:vis; }
  .st-key-cal_barra > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) { grid-area:novo; }
  .st-key-cal_barra .ec-mes { font-size:1.3rem; letter-spacing:-0.01em; }
  .st-key-cal_barra [data-testid="stMarkdownContainer"]:has(.ec-mes) { margin-bottom:0 !important; }
  .st-key-cal_nav [data-testid="stHorizontalBlock"] { gap:0.3rem !important; }
  .st-key-cal_nav button { width:100%; min-height:2.2rem !important; height:2.2rem; padding:0 0.4rem !important; border-radius:999px; }
  .st-key-cal_nav button p { font-size:0.85rem; }
  .st-key-cal_barra [data-testid="stColumn"]:nth-child(3) [data-testid="stElementContainer"],
  .st-key-cal_barra [data-testid="stButtonGroup"], .st-key-cal_barra [data-testid="stButtonGroup"] [role="radiogroup"] {
      width:100% !important; }
  .st-key-cal_barra [data-testid="stButtonGroup"] [role="radiogroup"] { display:flex; }
  .st-key-cal_barra [data-testid="stButtonGroup"] button { flex:1 1 0; min-width:0; min-height:2.4rem; padding:0 0.25rem; }
  .st-key-cal_barra [data-testid="stButtonGroup"] button p { font-size:0.85rem; }
  .st-key-cal_barra [data-testid="stColumn"]:nth-child(4) button { width:2.6rem !important; min-width:2.6rem; height:2.4rem;
      min-height:2.4rem !important; padding:0 !important; border-radius:12px; }
  .st-key-cal_barra [data-testid="stColumn"]:nth-child(4) button [data-testid="stMarkdownContainer"] { position:absolute;
      width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
  .st-key-cal_barra [data-testid="stColumn"]:nth-child(4) button span:has([data-testid="stIconMaterial"]) { margin:0 !important; }

  /* filtros e legenda mais discretos */
  .st-key-cal_filtros { gap:0.55rem !important; }
  .st-key-cal_filtros [data-testid="stExpander"] summary { padding:0.5rem 0.85rem; }
  .st-key-cal_filtros [data-testid="stExpander"] summary p { font-size:0.88rem; }
  .st-key-cal_filtros .ec-legenda { font-size:0.72rem; gap:0.2rem 0.75rem; margin:0; }
  .st-key-cal_filtros .ec-legenda span { gap:0.3rem; }
  .st-key-cal_filtros .ec-legenda i { width:7px; height:7px; border-radius:50%; }
  .st-key-cal_filtros .ec-legenda i.ses { background:transparent !important; box-shadow:inset 0 0 0 1.5px var(--acento);
      width:8px; height:8px; }

  /* mês num só cartão: dias sem caixas, o número num círculo (hoje preenchido) e, por baixo, um ponto por avaliação
     (cor do tipo) e um anel por tarefa de estudo (cor da sala); tocar no dia abre o dia com tudo */
  .st-key-cal_grelha { gap:0 !important; background:var(--cartao); border:1px solid var(--linha); border-radius:16px;
      padding:0.55rem 0.25rem 0.3rem; }
  .st-key-cal_grelha .ec-dias-semana { gap:0; margin:0 0 0.35rem; }
  .st-key-cal_grelha [data-testid="stMarkdownContainer"]:has(.ec-dias-semana) { margin-bottom:0 !important; }
  .st-key-cal_grelha .ec-dias-semana div { font-size:0.66rem; letter-spacing:0.06em; text-transform:uppercase; }
  .st-key-cal_grelha [class*="st-key-calsem_"] { border-top:1px solid var(--linha); padding-top:0.2rem; }
  .st-key-cal_grelha .st-key-calsem_0 { border-top:none; }
  .st-key-cal_grelha [class*="st-key-calsem_"] [data-testid="stHorizontalBlock"] { gap:0 !important; }
  .st-key-cal_grelha :is([class*="st-key-diaN_"], [class*="st-key-diaH_"], [class*="st-key-diaF_"]) { position:relative;
      min-height:3.3rem; padding:0.15rem 0 0.4rem; border:none; border-radius:10px; background:transparent; box-shadow:none;
      flex-direction:row !important; flex-wrap:wrap !important; justify-content:center; align-content:flex-start;
      gap:3px !important; }
  .st-key-cal_grelha [class*="st-key-diaF_"] { opacity:0.35; }
  .st-key-cal_grelha [class*="st-key-num_"] { flex:0 0 100% !important; width:100% !important; display:flex;
      justify-content:center; margin-bottom:1px; }
  .st-key-cal_grelha [class*="st-key-num_"], .st-key-cal_grelha [class*="st-key-num_"] :is(div, span) { position:static !important; }
  .st-key-cal_grelha [class*="st-key-num_"] [data-testid="stButton"] { display:flex; justify-content:center; width:100%; }
  .st-key-cal_grelha [class*="st-key-num_"] .stTooltipHoverTarget { justify-content:center !important; }
  .st-key-cal_grelha [class*="st-key-num_"] button { position:static !important; width:1.85rem; height:1.85rem;
      min-height:1.85rem !important; padding:0 !important; border-radius:50%; justify-content:center; }
  .st-key-cal_grelha [class*="st-key-num_"] button p { font-size:0.86rem; font-weight:500; }
  .st-key-cal_grelha [class*="st-key-diaH_"] [class*="st-key-num_"] button p { font-weight:700; }
  .st-key-cal_grelha [class*="st-key-num_"] button::after { content:""; position:absolute; inset:0; border-radius:10px; }
  .st-key-cal_grelha [class*="st-key-num_"] button:active::after { background:var(--bolha); opacity:0.6; }
  .st-key-cal_grelha [class*="st-key-dia"] > [data-testid="stLayoutWrapper"] { flex:0 0 auto !important; width:auto !important;
      min-width:0 !important; pointer-events:none; }
  .st-key-cal_grelha [class*="st-key-dia"] > [data-testid="stLayoutWrapper"]:has(> [class*="st-key-ses_"]),
  .st-key-cal_grelha [class*="st-key-dia"] > [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {
      display:none !important; }
  .st-key-cal_grelha :is([class*="st-key-ev_"], [class*="st-key-sesc"]),
  .st-key-cal_grelha :is([class*="st-key-ev_"], [class*="st-key-sesc"]) :is([data-testid="stElementContainer"], .stTooltipHoverTarget) {
      width:auto !important; min-width:0 !important; }
  .st-key-cal_grelha :is([class*="st-key-ev_"], [class*="st-key-sesc"]) :is([data-testid="stElementContainer"],
      [data-testid="stButton"], .stTooltipIcon, .stTooltipHoverTarget) { display:flex !important; line-height:0; }
  .st-key-cal_grelha :is([class*="st-key-ev_"], [class*="st-key-sesc"]) [data-testid="stButton"] > div { line-height:0; }
  .st-key-cal_grelha [class*="st-key-ev_"] button, .st-key-cal_grelha div[class*="st-key-sesc"] button[kind] {
      width:7px !important; height:7px; min-height:0 !important; padding:0 !important; border:none !important;
      border-radius:50% !important; background:var(--cor) !important; opacity:1; }
  .st-key-cal_grelha div[class*="st-key-sesc"] button[kind] { background:transparent !important;
      box-shadow:inset 0 0 0 1.5px var(--cor); }
  .st-key-cal_grelha [class*="st-key-ev_"][class*="_p_"] button,
  .st-key-cal_grelha div[class*="st-key-sesc"][class*="_f_"] button[kind] { opacity:0.4; }
  .st-key-cal_grelha :is([class*="st-key-ev_"], [class*="st-key-sesc"]) button [data-testid="stMarkdownContainer"] {
      position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
}
</style>
"""


def data_longa(dia) -> str:
    dia = av.para_data(dia)
    return f"{DIAS_LONGOS[dia.weekday()]}, {dia.day} de {av.MESES[dia.month - 1].lower()} de {dia.year}"


def legenda_html(com_sessoes: bool) -> str:
    itens = "".join(f'<span><i style="background:{av.CORES[t]}"></i>{t}</span>' for t in av.TIPOS)
    if com_sessoes:
        itens += ('<span><i class="ses" style="background:linear-gradient(90deg,#17798A 30%,#2E6DB424 30%)"></i>Tarefa de estudo '
                  '(cor da sala)</span>')
    return f'<div class="ec-legenda">{itens}</div>'


def etiqueta_tipo(tipo: str) -> str:
    return (f'<span style="background:{av.CORES.get(tipo, "#7C8C91")}22;color:{av.CORES.get(tipo, "#7C8C91")};'
            f'border-radius:999px;padding:0.1rem 0.6rem;font-size:0.8rem;font-weight:600">{escape(tipo)}</span>')


def formulario_avaliacao(chave: str, base: dict | None = None, dia_inicial=None, cadeira_inicial=None):
    """Formulário de criar/editar. Devolve os dados se foi submetido, senão None."""
    nomes = list(st.session_state.cadeiras)
    base = base or {}
    cad_ini = base.get("cadeira") or cadeira_inicial
    with st.form(chave, enter_to_submit=False, border=False):
        nome = st.text_input("Nome da avaliação", value=base.get("nome", ""), placeholder="ex.: Exame final",
                             max_chars=120)
        with st.container(key=f"avl1_{chave}"):
            c1, c2 = st.columns(2)
        cadeira = c1.selectbox("Sala", nomes, index=nomes.index(cad_ini) if cad_ini in nomes else 0)
        tipo = c2.selectbox("Tipo", TIPOS, index=TIPOS.index(base["tipo"]) if base.get("tipo") in TIPOS else 1)
        with st.container(key=f"avl2_{chave}"):
            c3, c4 = st.columns(2)
        dia = c3.date_input("Data *", value=av.para_data(base.get("data")) or dia_inicial, format="DD/MM/YYYY",
                            min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
        hora_atual = datetime.strptime(base["hora"], "%H:%M").time() if base.get("hora") else None
        hora = c4.time_input("Hora (opcional)", value=hora_atual, step=900,
                             help="Deixa em branco para um evento de dia inteiro.")
        notas = st.text_area("Notas (opcional)", value=base.get("notas", ""), height=90,
                             placeholder="ex.: matéria dos capítulos 1 a 4, sala 2.3, levar calculadora")
        enviado = st.form_submit_button("Guardar", type="primary", icon=":material/check:", width="stretch")
    if not enviado:
        return None
    return {"nome": nome, "cadeira": cadeira, "tipo": tipo, "data": dia, "hora": hora, "notas": notas}


def envio_repetido(dados: dict) -> bool:
    """Evita guardar duas vezes o mesmo formulário (ex.: duplo clique)."""
    assinatura = json.dumps(dados, default=str, sort_keys=True)
    anterior = st.session_state.get("_ultimo_envio")
    st.session_state._ultimo_envio = (assinatura, time.time())
    return bool(anterior and anterior[0] == assinatura and time.time() - anterior[1] < 3)


@st.dialog("Nova avaliação")
def dialogo_nova(dia_inicial=None, cadeira_inicial=None):
    if not st.session_state.cadeiras:
        st.info("Primeiro cria uma sala só tua (Salas → Criar sala).")
        return
    dados = formulario_avaliacao("form_nova_avaliacao", dia_inicial=dia_inicial, cadeira_inicial=cadeira_inicial)
    if dados is None:
        return
    if envio_repetido(dados):
        st.info("Esta avaliação já foi guardada.")
        return
    try:
        r = repo().criar(dados["nome"], dados["cadeira"], dados["tipo"], dados["data"], dados["hora"], dados["notas"],
                         cadeiras_validas=list(st.session_state.cadeiras))
    except av.ErroValidacao as erro:
        st.error(str(erro))
        return
    st.session_state.cal_msg = f"«{r['nome']}» guardada para {data_longa(r['data'])}."
    st.session_state.cal_ref = av.para_data(r["data"])
    st.rerun()


@st.dialog("Avaliação", width="large")
def dialogo_avaliacao(ident: str):
    r = repo().obter(ident)
    if r is None:
        st.warning("Esta avaliação já não existe.")
        return
    modo = st.session_state.get(f"modo_{ident}", "ver")

    if modo == "editar":
        st.markdown("#### Editar avaliação")
        dados = formulario_avaliacao(f"form_editar_{ident}", base=r)
        if st.button("Cancelar", key=f"cancelar_ed_{ident}"):
            st.session_state[f"modo_{ident}"] = "ver"
            st.rerun(scope="fragment")
        if dados is not None:
            try:
                novo, antigo = repo().atualizar(ident, cadeiras_validas=list(st.session_state.cadeiras), **dados)
            except av.ErroValidacao as erro:
                st.error(str(erro))
                return
            msg = f"Alterações guardadas em «{novo['nome']}»."
            if antigo["data"] != novo["data"]:
                msg += f" Passou de {fmt_data(antigo['data'])} para {fmt_data(novo['data'])}."
            st.session_state.cal_msg = msg
            st.session_state.cal_ref = av.para_data(novo["data"])
            st.session_state[f"modo_{ident}"] = "ver"
            st.rerun()
        return

    if modo == "apagar":
        st.markdown(f"#### Apagar «{escape(r['nome'])}»?")
        st.write(f"{r['cadeira']} · {data_longa(r['data'])}. Esta ação não pode ser desfeita.")
        plano = st.session_state.cadeiras.get(r["cadeira"], {}).get("plano") or {}
        if plano.get("avaliacao_id") == ident:
            st.caption("O plano de preparação desta avaliação não é apagado: continua na sala.")
        c1, c2 = st.columns(2)
        if c1.button("Sim, apagar", type="primary", icon=":material/delete:", width="stretch"):
            repo().apagar(ident)
            st.session_state.cal_msg = f"«{r['nome']}» foi apagada."
            st.session_state[f"modo_{ident}"] = "ver"
            st.rerun()
        if c2.button("Cancelar", width="stretch"):
            st.session_state[f"modo_{ident}"] = "ver"
            st.rerun(scope="fragment")
        return

    # ---- ver detalhes
    passou = av.ja_passou(r)
    st.markdown(f"### {escape(r['nome'])}")
    st.markdown(f"{etiqueta_tipo(r['tipo'])} &nbsp; <b>{escape(r['cadeira'])}</b> &nbsp; "
                f"<span class='{'ec-passou' if passou else 'ec-faltam'}'>{av.texto_faltam(r)}</span>",
                unsafe_allow_html=True)
    st.markdown(f":material/event: {data_longa(r['data']).capitalize()}  \n"
                f":material/schedule: {('às ' + r['hora']) if r.get('hora') else 'Dia inteiro (sem hora definida)'}")
    if r.get("notas"):
        with st.container(border=True):
            st.markdown(r["notas"])

    # plano de preparação
    d = st.session_state.cadeiras.get(r["cadeira"], {})
    plano = d.get("plano") or {}
    feitas = set(perfil.get("feitas", []))
    st.markdown("##### Preparação")
    if plano.get("avaliacao_id") == ident:
        sessoes = plano.get("dias", [])
        n_feitas = sum(av.id_sessao(s, r["cadeira"]) in feitas for s in sessoes)
        futuras = [s for s in sessoes if (av.para_data(s.get("data")) or date.min) >= date.today()]
        st.caption(f"Plano com {n_tarefas(len(sessoes))} · {n_feitas} feitas · {len(futuras)} por vir.")
        estado = av.estado_plano_cadeira(plano, repo(), feitas)
        if estado:
            st.warning(f"O plano foi feito para {fmt_data(estado['data_plano'])}. Reorganiza-o no Calendário ou na "
                       "sala: as tarefas feitas ficam guardadas.")
        if st.button("Ver o plano", icon=":material/calendar_month:"):
            ir("calendario", cal_vista="Plano")
    elif passou:
        st.caption("Esta avaliação já passou.")
    else:
        st.caption("Ainda não há um plano de preparação para esta avaliação.")
        if not d.get("ficheiros"):
            st.caption("Junta primeiro as fontes da sala para a IA conhecer a matéria.")
        elif st.button("Criar plano de preparação", icon=":material/auto_awesome:", type="primary",
                       disabled=not tem_chave, help="A IA faz-te umas perguntas e organiza o que estudar em cada dia até à avaliação."):
            novo_assistente_plano({"tipo": "cadeira", "cadeira": r["cadeira"], "avaliacao_id": ident})
            st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("Editar", icon=":material/edit:", width="stretch"):
        st.session_state[f"modo_{ident}"] = "editar"
        st.rerun(scope="fragment")
    if c2.button("Apagar", icon=":material/delete:", width="stretch"):
        st.session_state[f"modo_{ident}"] = "apagar"
        st.rerun(scope="fragment")


@st.dialog("Dia", width="large")
def dialogo_dia(dia: date):
    with st.container(key="dia_janela"):
        st.markdown(f"### {data_longa(dia).capitalize()}")
        eventos = repo().filtrar(dia, dia)
        if eventos:
            for r in eventos:
                with st.container(key=f"diaev_{r['id']}"):
                    c1, c2 = st.columns([5, 1], vertical_alignment="center")
                c1.markdown(f"<span class='ec-ponto' style='background:{av.CORES[r['tipo']]}'></span>"
                            f"**{escape(r['nome'])}** · {escape(r['cadeira'])} · "
                            f"{r['hora'] if r.get('hora') else 'dia inteiro'}", unsafe_allow_html=True)
                if c2.button("Abrir", key=f"dia_abrir_{r['id']}"):
                    st.session_state.abrir_avaliacao = r["id"]
                    st.rerun()
        else:
            st.caption("Sem avaliações neste dia.")
        sessoes = sessoes_do_dia(dia)
        if sessoes:
            st.markdown("##### Plano de estudo")
            for s in sessoes:
                principal, detalhe = pe.texto_da_tarefa(s)
                chave_d = chave_tarefa("dia_ses", s["id"], s["feita"])
                st.checkbox(f"**{s.get('cadeira', '')}** — {principal}", value=s["feita"], key=chave_d,
                            help=detalhe or None, on_change=marcar_feita_cb, args=(s["id"], chave_d))
        if st.button("Nova avaliação neste dia", icon=":material/add:", type="primary"):
            st.session_state.nova_avaliacao_dia = dia
            st.rerun()


def vista_calendario() -> None:
    st.markdown(ESTILO_CALENDARIO, unsafe_allow_html=True)
    st.session_state.setdefault("cal_ref", date.today())
    if not st.session_state.get("cal_vista"):
        st.session_state.cal_vista = "Mês"
    ref: date = st.session_state.cal_ref
    nomes = list(st.session_state.cadeiras)

    # janelas pedidas a partir de outros diálogos (um diálogo não pode abrir outro diretamente)
    if abrir_plano_se_pedido():
        pass
    elif "abrir_avaliacao" in st.session_state:
        dialogo_avaliacao(st.session_state.pop("abrir_avaliacao"))
    elif "nova_avaliacao_dia" in st.session_state:
        dialogo_nova(st.session_state.pop("nova_avaliacao_dia"))
    elif "nova_avaliacao_cadeira" in st.session_state:
        dialogo_nova(None, st.session_state.pop("nova_avaliacao_cadeira"))

    cabecalho("Calendário", "Avaliações e plano de estudo, sempre com as datas atuais.")
    if "cal_msg" in st.session_state:
        st.success(st.session_state.pop("cal_msg"), icon=":material/check_circle:")
    mostrar_avisos_de_planos("cal")

    # ---- barra de navegação
    vista_atual = st.session_state.cal_vista
    if vista_atual == "Mês":
        titulo = f"{av.MESES[ref.month - 1]} {ref.year}"
    elif vista_atual == "Semana":
        ini = av.inicio_semana(ref)
        fim = ini + timedelta(days=6)
        titulo = f"{ini.day} {av.MESES[ini.month - 1][:3].lower()} – {fim.day} {av.MESES[fim.month - 1][:3].lower()} {fim.year}"
    else:
        titulo = "Agenda" if vista_atual == "Agenda" else "Plano de estudo"
    with st.container(key="cal_barra"):
        c_nav, c_tit, c_vis, c_novo = st.columns([2.2, 2.6, 3.6, 2], vertical_alignment="center")
    passo = {"Mês": "mes", "Semana": 7}.get(vista_atual)
    if passo is not None:  # na Agenda e no Plano não há meses nem semanas para percorrer
        with c_nav.container(key="cal_nav"):
            b1, b2, b3 = st.columns([1, 1.6, 1])
            if b1.button("", icon=":material/chevron_left:", key="cal_ant", help="Anterior"):
                st.session_state.cal_ref = av.mudar_mes(ref, -1) if passo == "mes" else ref - timedelta(days=7)
                st.rerun()
            if b2.button("Hoje", key="cal_hoje", width="stretch"):
                st.session_state.cal_ref = date.today()
                st.rerun()
            if b3.button("", icon=":material/chevron_right:", key="cal_seg", help="Seguinte"):
                st.session_state.cal_ref = av.mudar_mes(ref, 1) if passo == "mes" else ref + timedelta(days=7)
                st.rerun()
    c_tit.markdown(f'<div class="ec-mes">{titulo}</div>', unsafe_allow_html=True)
    with c_vis:
        st.segmented_control("Vista", ["Mês", "Semana", "Agenda", "Plano"], key="cal_vista", label_visibility="collapsed")
    if c_novo.button("Nova avaliação", icon=":material/add:", type="primary", width="stretch",
                     disabled=not nomes):
        dialogo_nova(ref if vista_atual in ("Mês", "Semana") else None)
    vista_atual = st.session_state.cal_vista or "Mês"

    # ---- filtros e legenda
    if vista_atual == "Plano":
        filtro_cad, filtro_tipo, mostrar_sessoes = nomes, TIPOS, True
        st.markdown(ESTILO_PLANO, unsafe_allow_html=True)
    else:
        with st.container(key="cal_filtros"):
            with st.expander("Filtros", icon=":material/filter_list:"):
                filtro_cad = st.multiselect("Salas", nomes, default=nomes, key="cal_f_cad")
                filtro_tipo = st.multiselect("Tipos de avaliação", TIPOS, default=TIPOS, key="cal_f_tipo")
                mostrar_sessoes = st.toggle("Mostrar o plano de estudo", value=True, key="cal_f_ses")
            st.markdown(legenda_html(mostrar_sessoes), unsafe_allow_html=True)

    todas = repo().todas()
    if not nomes:
        st.info("Ainda não tens salas só tuas. Cria uma em Salas para poderes marcar avaliações.")
        return
    if not todas:
        with st.container(border=True):
            st.markdown("**Ainda não tens avaliações marcadas.**")
            st.caption("Marca os teus testes, exames e trabalhos para os veres aqui e a IA os usar nos planos de estudo.")
            if st.button("Criar a primeira avaliação", icon=":material/add:", type="primary"):
                dialogo_nova(date.today())

    sessoes = av.sessoes_de_estudo(perfil, st.session_state.cadeiras) if mostrar_sessoes else []
    sessoes = [s for s in sessoes if (s.get("cadeira") in filtro_cad) or not s.get("cadeira")]

    def eventos_entre(inicio, fim):
        return repo().filtrar(inicio, fim, filtro_cad, filtro_tipo)

    def por_dia(lista):
        grupos = {}
        for item in lista:
            grupos.setdefault(item["data"], []).append(item)
        return grupos

    def botao_evento(r, dia_iso, curto=True):
        passou = av.ja_passou(r)
        rotulo = (f"{r['hora']} " if r.get("hora") else "") + r["nome"]
        if not curto:
            rotulo += f" · {r['cadeira']}"
        with st.container(key=f"ev_{SLUG_TIPO.get(r['tipo'], 'outro')}_{'p' if passou else 'f'}_{r['id']}_{dia_iso.replace('-', '')}"):
            if st.button(rotulo, key=f"evb_{r['id']}_{dia_iso}", help=f"{r['tipo']} · {r['cadeira']}"):
                st.session_state[f"modo_{r['id']}"] = "ver"
                dialogo_avaliacao(r["id"])

    def botao_sessao(s, dia_iso, curto=True):
        """Tarefa do plano: cor da cadeira, riscada quando feita; clicar abre-a (marcar, mudar de dia, apagar)."""
        cad = s.get("cadeira") or ""
        principal = pe.texto_da_tarefa(s)[0]
        rotulo = ("✓ " if s["feita"] else "") + (principal if curto else f"{cad}: {principal}")
        indice = indice_cor_sala(cad, 7)
        with st.container(key=f"sesc{indice}_{'f' if s['feita'] else 'p'}_{chave_curta(s['id'])}_{dia_iso.replace('-', '')}"):
            if st.button(rotulo, key=f"sescb_{chave_curta(s['id'])}_{dia_iso}", type="tertiary",
                         help=f"{cad} · {pe.tipo_de(s)}" + (" · feita" if s["feita"] else "")):
                dialogo_sessao(s["id"])

    # ---- vista mensal
    if vista_atual == "Mês":
        semanas = av.semanas_do_mes(ref.year, ref.month)
        ev = por_dia(eventos_entre(semanas[0][0], semanas[-1][-1]))
        ses = por_dia(sessoes)
        with st.container(key="cal_grelha"):
            st.markdown('<div class="ec-dias-semana">' + "".join(f"<div>{d}</div>" for d in av.DIAS_CURTOS) + "</div>",
                        unsafe_allow_html=True)
            for i, semana in enumerate(semanas):
                with st.container(key=f"calsem_{i}"):
                    colunas = st.columns(7, gap="small")
                    for col, dia in zip(colunas, semana):
                        iso = dia.isoformat()
                        classe = "diaH" if dia == date.today() else ("diaN" if dia.month == ref.month else "diaF")
                        with col.container(key=f"{classe}_{dia:%Y%m%d}"):
                            if st.button(str(dia.day), key=f"num_{dia:%Y%m%d}", type="tertiary",
                                         help=data_longa(dia).capitalize()):
                                dialogo_dia(dia)
                            lista = ev.get(iso, [])
                            for r in lista[:3]:
                                botao_evento(r, iso)
                            if len(lista) > 3:
                                st.caption(f"+{len(lista) - 3} mais")
                            s_dia = ses.get(iso, [])
                            for s in s_dia[:2]:
                                botao_sessao(s, iso)
                            if len(s_dia) > 2:
                                with st.container(key=f"ses_{dia:%Y%m%d}"):
                                    if st.button(f"+{n_tarefas(len(s_dia) - 2)}", key=f"sesb_{dia:%Y%m%d}"):
                                        dialogo_dia(dia)

    # ---- vista semanal
    elif vista_atual == "Semana":
        ini = av.inicio_semana(ref)
        dias = [ini + timedelta(days=i) for i in range(7)]
        ev = por_dia(eventos_entre(dias[0], dias[-1]))
        ses = por_dia(sessoes)
        colunas = st.columns(7, gap="small")
        for col, dia in zip(colunas, dias):
            iso = dia.isoformat()
            classe = "diaH" if dia == date.today() else "diaN"
            with col.container(key=f"{classe}_s{dia:%Y%m%d}"):
                if st.button(f"{av.DIAS_CURTOS[dia.weekday()]} {dia.day}", key=f"num_s{dia:%Y%m%d}", type="tertiary"):
                    dialogo_dia(dia)
                for r in ev.get(iso, []):
                    botao_evento(r, iso, curto=False)
                    st.caption(f"{r['tipo']} · {r['hora'] or 'dia inteiro'}")
                for s in ses.get(iso, []):
                    botao_sessao(s, iso, curto=False)
                if not ev.get(iso) and not ses.get(iso):
                    st.caption("Livre")

    # ---- planos de estudo: progresso, tarefas de cada dia, reorganizar, refazer e apagar
    elif vista_atual == "Plano":
        planos = planos_existentes()
        c1, c2 = st.columns([4, 1.6], vertical_alignment="center")
        c1.caption("A IA lê a matéria e diz-te o que estudar em cada dia, sem horários: tu organizas o teu tempo. "
                   "Marca as tarefas feitas; o que ficar por fazer pode ser reorganizado pelos dias que faltam.")
        c2.button("Novo plano com IA", icon=":material/auto_awesome:", type="primary" if not planos else "secondary",
                  width="stretch", key="cal_novo_plano", disabled=not tem_chave, on_click=novo_assistente_plano)
        if not planos:
            with st.container(border=True):
                st.markdown("<div class='pl-titulo'>Ainda não tens um plano de estudo</div><div class='pl-sub'>Em quatro "
                            "passos: o que queres planear, como gostas de estudar, umas perguntas da IA sobre a matéria e "
                            "o plano pronto para veres antes de guardar.</div>", unsafe_allow_html=True)
        for origem, nome_p, plano in planos:
            cartao_plano(origem, nome_p, plano, "cal")

    # ---- agenda
    else:
        quais = st.segmented_control("Mostrar", ["Próximas", "Passadas", "Todas"], key="cal_agenda_quais",
                                     default="Próximas", label_visibility="collapsed") or "Próximas"
        lista = repo().filtrar(cadeiras=filtro_cad, tipos=filtro_tipo)
        if quais == "Próximas":
            lista = [r for r in lista if not av.ja_passou(r)]
        elif quais == "Passadas":
            lista = list(reversed([r for r in lista if av.ja_passou(r)]))
        if not lista:
            st.caption("Nada para mostrar com estes filtros.")
        mes_atual = None
        for r in lista:
            dia = av.para_data(r["data"])
            if (dia.year, dia.month) != mes_atual:
                mes_atual = (dia.year, dia.month)
                st.markdown(f"##### {av.MESES[dia.month - 1]} {dia.year}")
            passou = av.ja_passou(r)
            with st.container(border=True, key=f"ag_linha_{r['id']}"):
                c1, c2, c3 = st.columns([1, 6, 1.4], vertical_alignment="center")
                c1.markdown(f'<div class="ec-agenda-data{" passou" if passou else ""}"><b>{dia.day}</b>'
                            f'<small>{av.DIAS_CURTOS[dia.weekday()]}</small></div>', unsafe_allow_html=True)
                c2.markdown(f"<span class='ec-ponto' style='background:{av.CORES[r['tipo']]}'></span>"
                            f"**{escape(r['nome'])}** &nbsp; <span class='{'ec-passou' if passou else 'ec-faltam'}'>"
                            f"{av.texto_faltam(r)}</span><br><span class='ec-meta'>{escape(r['cadeira'])} · "
                            f"{r['tipo']} · {r['hora'] or 'dia inteiro'}</span>", unsafe_allow_html=True)
                if c3.button("Abrir", key=f"ag_{r['id']}", width="stretch"):
                    st.session_state[f"modo_{r['id']}"] = "ver"
                    dialogo_avaliacao(r["id"])


if vista == "calendario":
    vista_calendario()
    st.stop()

# =============================================================== INÍCIO
def css_fullcalendar() -> str:
    """Estilo do calendário arrastável (corre dentro de um iframe, por isso leva as cores do tema)."""
    claro = ("--fc-border-color:#DCE3E1;--fc-today-bg-color:rgba(23,121,138,.07);--fc-page-bg-color:#FFFFFF;"
             "--fc-neutral-bg-color:#EEF2F1;--fc-list-event-hover-bg-color:#EEF2F1;--fc-button-bg-color:#FFFFFF;"
             "--fc-button-text-color:#16232B;--fc-button-border-color:#DCE3E1;--fc-button-hover-bg-color:#EEF2F1;"
             "--fc-button-hover-border-color:#DCE3E1;--fc-button-active-bg-color:#DDF0F1;"
             "--fc-button-active-border-color:#17798A;--mi-texto:#16232B;--mi-suave:#5A6B70;--mi-sessao:#EAF1F0;--mi-ativo:#0F5E6B;")
    escuro = ("--fc-border-color:#26353B;--fc-today-bg-color:rgba(76,195,210,.09);--fc-page-bg-color:#172328;"
              "--fc-neutral-bg-color:#1C2B31;--fc-list-event-hover-bg-color:#1C2B31;--fc-button-bg-color:#172328;"
              "--fc-button-text-color:#E6EEF0;--fc-button-border-color:#26353B;--fc-button-hover-bg-color:#1C2B31;"
              "--fc-button-hover-border-color:#26353B;--fc-button-active-bg-color:#12343B;"
              "--fc-button-active-border-color:#4CC3D2;--mi-texto:#E6EEF0;--mi-suave:#93A6AB;--mi-sessao:#1C2B31;--mi-ativo:#7FD6E0;")
    tema = cfg.get("tema", "Automático")
    vars_ = (f".fc{{{escuro}}}" if tema == "Escuro" else f".fc{{{claro}}}"
             + (f"@media (prefers-color-scheme: dark){{.fc{{{escuro}}}}}" if tema == "Automático" else ""))
    return vars_ + """
html, body { background: transparent !important; }
.fc { font-family: Inter, system-ui, sans-serif; color: var(--mi-texto); background: var(--fc-page-bg-color);
      border-radius: 14px; overflow: hidden; }
.fc .fc-toolbar-title { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 1.25rem; font-weight: 600; }
.fc .fc-button { border-radius: 9px !important; box-shadow: none !important; text-transform: none; font-size: .85rem;
      padding: .3rem .7rem; }
.fc .fc-button-primary:not(:disabled).fc-button-active { color: var(--mi-ativo); }
.fc .fc-daygrid-dot-event, .fc .fc-daygrid-block-event { overflow: hidden; }
.fc .fc-daygrid-event .fc-event-time { flex: none; }
/* no mês as células são estreitas: mostra-se o nome (a hora está nas próximas avaliações e na semana) */
.fc .fc-dayGridMonth-view .fc-daygrid-event .fc-event-time { display: none; }
.fc .fc-daygrid-event .fc-event-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fc a, .fc .fc-col-header-cell-cushion, .fc .fc-daygrid-day-number { color: var(--mi-texto); text-decoration: none; }
.fc .fc-col-header-cell-cushion { font-size: .78rem; color: var(--mi-suave); text-transform: uppercase; }
.fc .fc-day-today .fc-daygrid-day-number { background: #17798A; color: #fff !important; border-radius: 999px; padding: 2px 7px; }
.fc-event { border-radius: 6px !important; font-size: .78rem; padding: 1px 4px; cursor: grab; }
.fc-event.mi-passou { opacity: .5; }
.fc-event.mi-sessao { border-width: 0 0 0 3px !important; border-style: solid !important; }
.fc-event.mi-sessao .fc-event-title, .fc-event.mi-sessao .fc-event-time { color: var(--mi-texto) !important; }
.fc-event.mi-feita { opacity: .55; text-decoration: line-through; }
@media (max-width: 640px) { .fc .fc-toolbar { flex-direction: column; gap: .4rem; } .fc .fc-toolbar-title { font-size: 1.05rem; } }
"""


def eventos_calendario() -> tuple[list, dict]:
    """Avaliações (fonte única) e tarefas dos planos de estudo (o dia inteiro, sem horas), no formato do FullCalendar.
    Devolve também um mapa id_evento -> onde está o registo, para aplicar os movimentos."""
    eventos, mapa = [], {}
    for r in repo().todas():
        ev_id = f"a|{r['id']}"
        cor = av.CORES.get(r["tipo"], "#7C8C91")
        eventos.append({"id": ev_id, "title": f"{r['nome']} · {r['cadeira']}",
                        "start": f"{r['data']}T{r['hora']}:00" if r.get("hora") else r["data"],
                        "allDay": not r.get("hora"), "backgroundColor": cor, "borderColor": cor, "textColor": "#FFFFFF",
                        "classNames": ["mi-passou"] if av.ja_passou(r) else []})
        mapa[ev_id] = ("avaliacao", r["id"])
    feitas = set(perfil.get("feitas", []))
    planos = [("g", None, (perfil.get("plano_geral") or {}).get("dias", []))]
    planos += [("c", nome, (d.get("plano") or {}).get("dias", [])) for nome, d in st.session_state.cadeiras.items()]
    for origem, nome, dias in planos:
        for i, sessao in enumerate(dias):
            if not av.para_data(sessao.get("data")):
                continue
            cadeira = sessao.get("cadeira") or nome
            feita = av.id_sessao(sessao, cadeira) in feitas
            ev_id = f"{origem}|{nome or ''}|{i}"
            cor = cor_cadeira(cadeira or "")
            dia_iso = str(sessao["data"])[:10]
            evento_fc = {"id": ev_id, "title": f"{'✓ ' if feita else ''}{cadeira}: {pe.texto_da_tarefa(sessao)[0]}",
                         "start": dia_iso, "allDay": True, "backgroundColor": f"{cor}33", "borderColor": cor,
                         "classNames": ["mi-sessao"] + (["mi-feita"] if feita else [])}
            eventos.append(evento_fc)
            mapa[ev_id] = ("sessao", origem, nome, i)
    return eventos, mapa


def mover_evento(ev: dict, mapa: dict) -> None:
    """Aplica um arrastar-e-largar ao registo original (sem criar duplicados)."""
    alvo = mapa.get(ev.get("id"))
    inicio = str(ev.get("start") or "")
    novo_dia = inicio[:10]
    if not alvo or not av.para_data(novo_dia):
        return
    if alvo[0] == "avaliacao":
        nova_hora = None if ev.get("allDay") or "T" not in inicio else inicio[11:16]
        try:
            novo, antigo = repo().atualizar(alvo[1], cadeiras_validas=list(st.session_state.cadeiras),
                                            data=novo_dia, hora=nova_hora)
            st.session_state.cal_msg = (f"«{novo['nome']}» passou de {fmt_data(antigo['data'])} para "
                                        f"{fmt_data(novo['data'])}" + (f" às {novo['hora']}" if novo.get("hora") else "") + ".")
        except av.ErroValidacao as erro:
            st.session_state.cal_erro = str(erro)
        return
    _, origem, nome, i = alvo
    plano = perfil.get("plano_geral") if origem == "g" else st.session_state.cadeiras.get(nome, {}).get("plano")
    if not plano or i >= len(plano.get("dias", [])):
        return
    sessao = plano["dias"][i]
    cadeira = sessao.get("cadeira") or nome
    id_antigo = av.id_sessao(sessao, cadeira)
    sessao["data"] = novo_dia  # só o dia: as tarefas do plano não têm hora (mesmo se largadas numa hora, na semana)
    for campo in ("hora", "duracao_min"):
        sessao.pop(campo, None)
    feitas = perfil.setdefault("feitas", [])
    if id_antigo in feitas:  # a tarefa continua marcada como feita depois de mudar de dia
        feitas[feitas.index(id_antigo)] = av.id_sessao(sessao, cadeira)
    guardar_perfil()
    if origem == "c":
        guardar(nome)
    st.session_state.cal_msg = f"Tarefa de {cadeira} passou para {fmt_data(novo_dia)}."


def calendario_inicio() -> None:
    eventos, mapa = eventos_calendario()
    try:
        from streamlit_calendar import calendar as calendario_fc
    except ImportError:
        calendario_fc = None
    if calendario_fc is None:
        st.caption("Para arrastar eventos no calendário, instala o componente: `py -3.14 -m pip install "
                   "streamlit-calendar` (o `iniciar.bat` faz isto sozinho). Entretanto, aqui ficam os próximos 14 dias.")
        fim = date.today() + timedelta(days=14)
        proximos = repo().filtrar(date.today(), fim)
        for r in proximos:
            st.markdown(f"<span class='ec-ponto' style='background:{av.CORES[r['tipo']]}'></span>**{escape(r['nome'])}** · "
                        f"{escape(r['cadeira'])} <span class='ec-meta'>· {fmt_quando(r)}</span>", unsafe_allow_html=True)
        if not proximos:
            st.caption("Sem avaliações nos próximos 14 dias.")
        st.button("Abrir o calendário completo", icon=":material/calendar_month:",
                  on_click=navegar, args=("calendario",))
        return
    st.session_state.setdefault("fc_versao", 0)
    opcoes = {
        "initialView": st.session_state.get("fc_vista", "dayGridMonth"),
        "initialDate": st.session_state.get("fc_data", date.today().isoformat()),
        "locale": "pt", "firstDay": 1, "editable": True, "eventDurationEditable": False, "height": 560,
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,listMonth"},
        "buttonText": {"today": "Hoje", "month": "Mês", "week": "Semana", "list": "Agenda"},
        "allDayText": "Dia", "noEventsText": "Sem eventos", "moreLinkText": "mais", "moreLinkHint": "Ver mais {0}",
        "dayMaxEvents": 3, "nowIndicator": True,
        "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
        "slotLabelFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    }
    argumentos = dict(events=eventos, options=opcoes, custom_css=css_fullcalendar(),
                      key=f"fc_inicio_{st.session_state.fc_versao}")
    try:
        estado = calendario_fc(callbacks=["dateClick", "eventClick", "eventChange"], **argumentos)
    except TypeError:  # versões antigas do componente não têm o parâmetro "callbacks"
        estado = calendario_fc(**argumentos)
    st.caption("Arrasta uma prova ou uma tarefa de estudo para outro dia para a mudar (as provas também mudam de hora, "
               "na semana). Clica numa tarefa para a marcar como feita, passar para outro dia ou apagar.")
    if not estado or estado.get("callback") not in ("eventChange", "eventClick", "dateClick"):
        return
    # O componente devolve sempre o último evento: depois de o tratar, recriamo-lo (nova chave) para não repetir.
    st.session_state.fc_versao += 1
    tipo = estado["callback"]
    if tipo == "eventChange":
        ev = estado["eventChange"]["event"]
        st.session_state.fc_data = str(ev.get("start", ""))[:10] or date.today().isoformat()
        mover_evento(ev, mapa)
        st.rerun()
    elif tipo == "eventClick":
        ev = estado["eventClick"]["event"]
        alvo = mapa.get(ev.get("id"))
        st.session_state.fc_data = str(ev.get("start", ""))[:10] or date.today().isoformat()
        if alvo and alvo[0] == "avaliacao":
            st.session_state[f"modo_{alvo[1]}"] = "ver"
            dialogo_avaliacao(alvo[1])
        elif alvo and alvo[0] == "sessao":
            _, origem_s, nome_s, i_s = alvo
            plano_s = perfil.get("plano_geral") if origem_s == "g" else st.session_state.cadeiras.get(nome_s, {}).get("plano")
            if plano_s and i_s < len(plano_s.get("dias", [])):
                dialogo_sessao(av.id_sessao(plano_s["dias"][i_s], nome_s))
        elif av.para_data(str(ev.get("start", ""))[:10]):
            dialogo_dia(av.para_data(str(ev["start"])[:10]))
    elif tipo == "dateClick":
        dia = av.para_data(str(estado["dateClick"].get("date", ""))[:10])
        if dia:
            st.session_state.fc_data = dia.isoformat()
            dialogo_dia(dia)


# ---------------------------------------------------------------- cronómetro de estudo (componente no browser)
def cronometro() -> None:
    # um pedido por voz («põe o cronómetro a 40 minutos») chega aqui uma única vez
    comando = st.session_state.pop("crono_cmd", None)
    valor = componente("crono", "crono_inicio", 380, cadeiras=list(st.session_state.cadeiras), comando=comando,
                       resumo=dfs.resumo_foco(perfil.get("foco", []), date.today()))
    tratar_evento_crono(valor, "crono_inicio")
    historico_foco()


def apagar_sessao_foco(indice: int) -> None:
    foco = perfil.get("foco", [])
    if 0 <= indice < len(foco):
        foco.pop(indice)
        guardar_perfil()


def historico_foco() -> None:
    """Sessões recentes do cronómetro e os minutos por cadeira nos últimos 7 dias."""
    foco = perfil.get("foco", [])
    if not foco:
        return
    r_ = dfs.resumo_foco(foco, date.today())
    with st.popover("Histórico de foco", icon=":material/history:", width="stretch"):
        st.markdown(f"<div class='mi-sec'><b>Últimos 7 dias</b><span>{fmt_duracao(r_['semana'] * 60)}</span></div>",
                    unsafe_allow_html=True)
        if r_["por_cadeira"]:
            maior = max(r_["por_cadeira"].values()) or 1
            st.markdown("<div class='pl-barras'>" + "".join(
                f"<div class='pl-barra'><span>{escape(n)}</span><div><i style='width:{100 * m / maior:.0f}%;"
                f"background:{cor_cadeira(n) if n in st.session_state.cadeiras else 'var(--suave)'}'></i></div>"
                f"<b>{fmt_duracao(m * 60)}</b></div>" for n, m in r_["por_cadeira"].items()) + "</div>", unsafe_allow_html=True)
        st.markdown("<div class='mi-sec'><b>Sessões recentes</b></div>", unsafe_allow_html=True)
        recentes = sorted(enumerate(foco), key=lambda kv: (kv[1].get("data", ""), kv[1].get("hora", "")), reverse=True)[:8]
        for i_f, f_ in recentes:
            a, b = st.columns([5, 1], vertical_alignment="center")
            d_ = av.para_data(f_.get("data"))
            quando_ = ("Hoje" if d_ == date.today() else "Ontem" if d_ == date.today() - timedelta(days=1)
                       else fmt_data(d_, False) if d_ else "—") + (f", {f_['hora']}" if f_.get("hora") else "")
            a.markdown(f"<div class='df-valor'>{escape(quando_)} · <b>{int(f_.get('minutos') or 0)} min</b>"
                       f"<small>{escape(f_.get('cadeira') or 'Sem sala')}</small></div>", unsafe_allow_html=True)
            b.button("", icon=":material/close:", key=f"foco_apagar_{i_f}", type="tertiary", help="Apagar esta sessão",
                     on_click=apagar_sessao_foco, args=(i_f,))
        st.button("Ver as estatísticas", icon=":material/insights:", key="foco_estat", width="stretch", on_click=navegar,
                  args=("perfil",))


# ---------------------------------------------------------------- assistente Mondego por voz (Início)
SISTEMA_VOZ = (
    "És o Mondego, o assistente de estudo por voz da app Mondego IA: um explicador simpático, paciente e entusiasta, "
    "que fala como um bom professor português. Falas SEMPRE em português de Portugal: tratas o aluno por tu, usas "
    "«estás a fazer» (nunca «estás fazendo»), «ecrã», «telemóvel», «casa de banho», nunca «você». Quando falas de ti "
    "usas o masculino («estou pronto», «fico contente»).\n"
    "COMO RESPONDES:\n"
    "- A primeira frase responde logo à pergunta. Depois explicas o essencial.\n"
    "- Ajustas o tamanho: pergunta simples ou conversa, 1 a 3 frases; explicação de matéria, até 8 frases curtas com "
    "um exemplo concreto do dia a dia ou um número simples.\n"
    "- O campo «fala» vai ser lido em voz alta: frases curtas e naturais, sem listas, títulos, markdown, emojis, links "
    "nem símbolos. Dizes as fórmulas por palavras («x ao quadrado», «a derivada de f em ordem a x»).\n"
    "- Quando houver fórmulas ou passos que ajudem a ler no ecrã, pões essa versão escrita em «escrito» (markdown "
    "curto, fórmulas em LaTeX entre $...$). Caso contrário, «escrito» fica vazio.\n"
    "- Usas os documentos do aluno (entre <fontes>) quando a pergunta é sobre a matéria e dizes de onde vem "
    "(«nos teus apontamentos de Álgebra…»). Se não estiver lá, usas o teu conhecimento e dizes isso numa frase curta.\n"
    "- Usas os dados da app (entre <aluno> e <app>) para perguntas como «o que tenho de estudar hoje?», «quando é o "
    "próximo teste?» ou «quanto estudei esta semana?», e para dares conselhos concretos. Nunca inventas datas, notas "
    "nem dados da app.\n"
    "- O reconhecimento de voz pode trocar palavras: interpreta a intenção mais provável; se for mesmo ambíguo, "
    "perguntas numa frase.\n"
    "- Quando fizer sentido, terminas com uma pergunta curta ou uma sugestão útil (variando, nunca sempre igual).\n"
    "AÇÕES NA APP: quando o aluno pede claramente para abrir ou fazer algo, preenches «acao» (e na fala confirmas "
    "o que vais fazer, por exemplo «Vou abrir os flashcards de Álgebra.»). Ações possíveis:\n"
    '  {"tipo": "abrir", "destino": "inicio|calendario|salas|estudio3d|perfil|assistente"}\n'
    '  {"tipo": "abrir_cadeira", "cadeira": "<nome exato da lista de salas só tuas>", "ferramenta": "Conversa|Resumo|'
    'Guia de estudo|Mapa de conceitos|Quiz|Flashcards|Teste|Slides|Plano|Progresso"}\n'
    '  {"tipo": "cronometro", "minutos": 25, "pausa": 5, "cadeira": "<nome exato ou null>"}\n'
    '  {"tipo": "criar_3d", "descricao": "<descrição completa do modelo 3D pedido>"}\n'
    "Se não houver nada para fazer na app, «acao» é null.\n"
    "Se a pergunta precisar de informação atual da internet (notícias, resultados, preços, horários, acontecimentos "
    "recentes), põe «precisa_web» a true.\n"
    'Responde só com JSON: {"fala": "...", "escrito": "", "acao": null, "precisa_web": false}'
)
if not ESTUDIO_3D:  # sem 3D Studio: o assistente não oferece abrir nem criar modelos 3D
    SISTEMA_VOZ = SISTEMA_VOZ.replace("|estudio3d", "").replace(
        '  {"tipo": "criar_3d", "descricao": "<descrição completa do modelo 3D pedido>"}\n', "")
DESTINOS_VOZ = {"inicio": "inicio", "calendario": "calendario", "cadeiras": "salas", "laboratorio": "salas",
                "estudio3d": "estudio3d", "perfil": "perfil", "assistente": "chat", "chat": "chat", "salas": "salas"}
FERRAMENTAS_VOZ = ("Conversa", "Resumo", "Guia de estudo", "Mapa de conceitos", "Quiz", "Flashcards", "Teste", "Slides",
                   "Plano", "Progresso")  # as mesmas do Estúdio da cadeira (ESTUDIO, definido mais abaixo)


def contexto_app_voz() -> str:
    """O que o assistente sabe da app neste momento (além do perfil e das avaliações)."""
    hoje = date.today()
    semana = sum(f.get("minutos", 0) for f in perfil.get("foco", []) if f.get("data", "") >= (hoje - timedelta(days=6)).isoformat())
    linhas = [f"Agora são {datetime.now():%H:%M}.",
              f"Salas só tuas, uma por cadeira (nomes exatos): {', '.join(st.session_state.cadeiras) or 'nenhuma ainda'}.",
              f"Tempo de foco: {minutos_foco_hoje()} min hoje e {semana} min nos últimos 7 dias."]
    for nome, d in st.session_state.cadeiras.items():
        if d.get("cartoes"):
            n = rs.resumo(d["cartoes"], hoje)["para_hoje"]
            if n:
                linhas.append(f"Flashcards de {nome} para rever hoje: {n}.")
        if d.get("quiz_historico"):
            u = d["quiz_historico"][-1]
            linhas.append(f"Último quiz de {nome}: {u.get('nota', '?')} valores.")
    futuras = repo().proximas()
    if futuras:
        linhas.append("Próximas avaliações: " + "; ".join(f"{r['nome']} de {r['cadeira']} a {fmt_quando(r)} ({av.texto_faltam(r)})"
                                                         for r in futuras[:5]) + ".")
    return "<app>\n" + "\n".join(linhas) + "\n</app>"


def validar_acao_voz(acao) -> dict | None:
    """Só deixa passar ações conhecidas, com valores válidos (a IA pode enganar-se nos nomes)."""
    import difflib

    if not isinstance(acao, dict):
        return None
    tipo = str(acao.get("tipo", "")).strip()
    nomes = list(st.session_state.cadeiras)

    def cadeira_certa(nome):
        if not nome:
            return None
        por_baixo = {n.lower(): n for n in nomes}
        if str(nome).lower() in por_baixo:
            return por_baixo[str(nome).lower()]
        parecida = difflib.get_close_matches(str(nome).lower(), list(por_baixo), n=1, cutoff=0.55)
        return por_baixo[parecida[0]] if parecida else None

    if not ESTUDIO_3D and (tipo == "criar_3d" or str(acao.get("destino")) == "estudio3d"):
        return None
    if tipo == "abrir" and str(acao.get("destino")) in DESTINOS_VOZ:
        return {"tipo": "abrir", "destino": DESTINOS_VOZ[str(acao["destino"])]}
    if tipo == "abrir_cadeira":
        nome = cadeira_certa(acao.get("cadeira"))
        if nome:
            ferramenta = acao.get("ferramenta") if acao.get("ferramenta") in FERRAMENTAS_VOZ else "Conversa"
            return {"tipo": "abrir_cadeira", "cadeira": nome, "ferramenta": ferramenta}
    if tipo == "laboratorio":  # o Laboratório está agora dentro das salas
        return {"tipo": "abrir", "destino": "salas"}
    if tipo == "cronometro":
        try:
            minutos = int(round(float(acao.get("minutos") or 25)))
            pausa = int(round(float(acao.get("pausa") if acao.get("pausa") is not None else 5)))
        except (TypeError, ValueError):
            return None
        if 1 <= minutos <= 240:
            return {"tipo": "cronometro", "minutos": minutos, "pausa": pausa if pausa in (0, 5, 10, 15) else 5,
                    "cadeira": cadeira_certa(acao.get("cadeira"))}
    if tipo == "criar_3d" and str(acao.get("descricao", "")).strip():
        return {"tipo": "criar_3d", "descricao": str(acao["descricao"]).strip()[:800]}
    return None


def executar_acao_voz(acao: dict) -> None:
    tipo = acao["tipo"]
    if tipo == "cronometro":  # o cronómetro está no Início: começa já
        st.session_state.crono_cmd = {"id": uuid.uuid4().hex[:8], "minutos": acao["minutos"], "pausa": acao["pausa"],
                                      "cadeira": acao.get("cadeira") or ""}
        st.rerun()
    if tipo == "abrir":
        ir(acao["destino"])
    elif tipo == "abrir_cadeira":
        ir("cadeira", cadeira_atual=acao["cadeira"], ferramenta_pendente=acao["ferramenta"])
    elif tipo == "criar_3d":
        ir("estudio3d", e3d_secao="criar", e3d_aberto=None, e3d_desc=acao["descricao"])


def voz_escolhida() -> str:
    """O Mondego fala sempre com a voz masculina Charon (Google). Só se ela não estiver disponível (sem chave do Gemini
    ou falha do serviço) é que usa a voz do browser, para não ficar calado."""
    if cfg.get("fornecedor") != "Gemini" or not cfg["chaves"].get("Gemini") or st.session_state.get("_tts_indisponivel"):
        return vt.VOZ_BROWSER
    return vt.VOZ_POR_OMISSAO


def pensar_resposta_voz(pergunta: str, hist: list) -> dict:
    """Pergunta → {"fala", "escrito", "acao"}. Usa os documentos, os dados da app e, se for preciso, a web."""
    docs = {f"{c} · {n}": t for c, d in st.session_state.cadeiras.items() for n, t in d["ficheiros"].items()}
    fontes = selecionar_texto(docs, pergunta, 25_000) if docs else "(o aluno ainda não carregou documentos)"
    ingles = cfg.get("idioma") == "English"
    sistema = SISTEMA_VOZ + (" Answer in natural spoken English (the JSON keys stay the same)." if ingles else "") \
        + dfs.instrucoes_ia(cfg, voz=True)
    contexto = [{"role": "user", "content": f"{info_aluno()}\n{contexto_app_voz()}\n\n<fontes>\n{fontes}\n</fontes>\n\n"
                                            "Vamos conversar por voz."},
                {"role": "assistant", "content": '{"fala": "Combinado, estou a ouvir.", "escrito": "", "acao": null}'}]
    bruto = chamar_ia(contexto + hist[-12:], json_mode=True, sistema=sistema)
    try:
        dados = extrair_json(bruto)
    except (ValueError, json.JSONDecodeError):
        dados = {"fala": bruto}
    fala = str(dados.get("fala") or "").strip()
    if dados.get("precisa_web") and cfg.get("fornecedor") == "Gemini" and cfg.get("web", True):
        try:  # segunda volta, com pesquisa na Google, só quando a pergunta precisa de informação atual
            fala_web = "".join(chamar_ia_stream(
                hist[-6:], web=True,
                sistema=("És o Mondego, assistente de estudo por voz. Responde em português de Portugal (tu, nunca você), "
                         "em 2 a 5 frases curtas e naturais para serem lidas em voz alta, sem listas nem símbolos, e diz "
                         "brevemente de onde vem a informação." if not ingles else
                         "You are Mondego, a voice study assistant. Answer in 2-5 short natural spoken sentences, no lists "
                         "or symbols, and briefly say where the information comes from."))).strip()
            if fala_web:
                fala, dados["escrito"] = fala_web, ""
        except Exception:  # noqa: BLE001 — fica a resposta sem web
            pass
    if not fala:
        fala = "Desculpa, não consegui responder. Podes repetir?" if not ingles else "Sorry, I couldn't answer. Can you repeat?"
    return {"fala": fala, "escrito": str(dados.get("escrito") or "").strip(), "acao": validar_acao_voz(dados.get("acao"))}


def gerar_audio_resposta(resp: dict) -> None:
    """Segunda fase: a resposta já está no ecrã; agora cria a fala com a voz escolhida."""
    voz = voz_escolhida()
    if voz == vt.VOZ_BROWSER:
        resp["audio_estado"] = "browser"
        return
    try:
        wav, modelo = vt.sintetizar(cfg["chaves"]["Gemini"], resp["fala"], voz)
        resp.update(audio=guardar_audio(wav), audio_estado="pronto")
        st.session_state["_tts_modelo"] = modelo
    except Exception as erro:  # noqa: BLE001 — fica a voz do browser
        resp["audio_estado"] = "falhou"
        texto = str(erro)
        if getattr(erro, "codigo", None) in (401, 403, 404) or "api key" in texto.lower():
            st.session_state["_tts_indisponivel"] = texto  # não volta a tentar nesta sessão
        resp["aviso"] = "A voz da Google não está disponível agora; usei a voz do browser."


def transcricao_disponivel() -> bool:
    """A esfera grava e a app transcreve com a Google quando o Gemini está escolhido e tem chave (a chave nunca vai
    para o browser). Sem isso, ouve só com o reconhecimento do browser."""
    return (cfg.get("fornecedor") == "Gemini" and bool(cfg["chaves"].get("Gemini"))
            and not st.session_state.get("_ouvir_indisponivel"))


def vocabulario_voz() -> list:
    """Palavras que a pessoa provavelmente vai dizer e que um reconhecimento genérico erra: as cadeiras, as avaliações,
    os documentos e os nomes das partes da app."""
    termos = ["Mondego", "flashcards", "quiz", "Pomodoro", "cronómetro", "Laboratório", "Salas", "Calendário",
              "Definições", "Assistente", "plano de estudo"]
    termos += list(st.session_state.cadeiras)
    try:
        termos += [r["nome"] for r in repo().proximas()[:15]]
    except Exception:  # noqa: BLE001 — sem avaliações, fica o resto
        pass
    for d in st.session_state.cadeiras.values():
        for nome in list(d.get("ficheiros") or {})[:8]:
            nome = re.sub(r"[_-]+", " ", Path(nome).stem).strip()
            if 2 < len(nome) <= 40:
                termos.append(nome)
    vistos, saida = set(), []
    for t in termos:
        t = str(t).strip()[:60]
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            saida.append(t)
    return saida[:100]


def ouvir_audio_voz(ev: dict) -> str:
    """Gravação vinda da esfera → o que a pessoa disse. Transcreve com a Google (modelo de transcrição; se não der, um
    modelo de texto que ouve o áudio com a conversa recente). Se falhar, fica o que o reconhecimento do browser ouviu."""
    rascunho = re.sub(r"\s+", " ", str(ev.get("rascunho") or "")).strip()[:1500]
    if not transcricao_disponivel():
        return rascunho
    try:
        wav = base64.b64decode(str(ev.get("wav") or ""), validate=True)
    except ValueError:
        return rascunho
    if not vt.e_wav(wav) or len(wav) > 4_000_000:  # 4 MB ≈ 2 minutos a 16 kHz (a esfera grava no máximo 1 minuto)
        return rascunho
    hist = st.session_state.get("voz_hist") or []
    conversa = "\n".join(("Aluno: " if m["role"] == "user" else "Mondego: ") + str(m["content"])[:240] for m in hist[-6:])
    try:
        texto, modelo = vt.transcrever(cfg["chaves"]["Gemini"], wav, "en-GB" if cfg.get("idioma") == "English" else "pt-PT",
                                       vocabulario_voz(), conversa, rascunho, modelos_texto=candidatos_gemini("leve"))
        st.session_state["_ouvir_modelo"] = modelo
    except vt.ErroVoz as erro:
        if erro.codigo == 401 or "api key" in str(erro).lower():
            st.session_state["_ouvir_indisponivel"] = str(erro)  # chave inválida: não volta a tentar nesta sessão
        return rascunho
    except Exception:  # noqa: BLE001 — fica o que o browser ouviu
        return rascunho
    return texto or rascunho


def assistente_voz() -> None:
    hist = st.session_state.setdefault("voz_hist", [])
    resp = st.session_state.get("voz_resp") or {}
    erro = st.session_state.get("voz_erro") or {}
    acao = st.session_state.get("voz_acao")
    voz = voz_escolhida()
    valor = componente("voz", "voz_inicio", 240, idioma=cfg.get("idioma", "Português"), historico=hist[-10:],
                       resposta=resp.get("texto"), fala=resp.get("fala"), resposta_id=resp.get("id"), audio=resp.get("audio"),
                       audio_estado=resp.get("audio_estado"), aviso=resp.get("aviso"), erro=erro.get("texto"),
                       erro_id=erro.get("id"), ativo=tem_chave, acao_pendente=bool(acao),
                       falar=bool(cfg.get("voz_alta", True)), continua=bool(cfg.get("voz_continua", True)),
                       ritmo=dfs.VELOCIDADE_VOZ.get(cfg.get("voz_velocidade"), 1.0),
                       menos_movimento=cfg.get("movimento") == "Reduzido", transcreve=transcricao_disponivel())
    ev = evento(valor, "voz_inicio")
    if ev and ev.get("evento") == "pref":  # as opções mudadas na própria esfera ficam nas Definições desta conta
        for chave_v, campo_v in (("voz_alta", "falar"), ("voz_continua", "continua")):
            if isinstance(ev.get(campo_v), bool):
                cfg[chave_v] = ev[campo_v]
        guardar_config()
        return
    # 2.ª fase: o texto já foi mostrado; agora a fala (assim a resposta aparece mais depressa)
    if resp.get("audio_estado") == "pendente":
        gerar_audio_resposta(resp)
        st.rerun()
    if ev and ev.get("evento") == "fim_fala":
        if acao:
            st.session_state.pop("voz_acao", None)
            executar_acao_voz(acao)
        return
    if ev and ev.get("evento") == "audio":  # falou: a gravação passa a texto e segue como uma pergunta
        texto = ouvir_audio_voz(ev)
        if not texto:
            st.session_state.voz_erro = {"id": uuid.uuid4().hex[:8],
                                         "texto": "Não percebi o que disseste. Fala outra vez, mais perto do microfone."}
            st.rerun()
        ev = {**ev, "evento": "pergunta", "texto": texto}
    if not (ev and ev.get("evento") == "pergunta" and str(ev.get("texto", "")).strip()):
        if hist and st.button("Limpar conversa", key="voz_limpar", type="tertiary", icon=":material/delete_sweep:"):
            hist.clear()
            st.session_state.pop("voz_resp", None)
            st.rerun()
        return
    pergunta = str(ev["texto"]).strip()[:1500]
    hist.append({"role": "user", "content": pergunta})
    try:
        r = pensar_resposta_voz(pergunta, hist)
    except Exception as erro_ia:  # noqa: BLE001
        hist.pop()
        st.session_state.voz_erro = {"id": uuid.uuid4().hex[:8], "texto": "Não consegui responder agora. Tenta outra vez."}
        mostrar_erro(erro_ia)
        return
    hist.append({"role": "assistant", "content": r["escrito"] or r["fala"]})
    del hist[:-40]
    estado_audio = "nenhum" if ev.get("falar") is False else "browser" if voz == vt.VOZ_BROWSER else "pendente"
    st.session_state.voz_resp = {"id": uuid.uuid4().hex[:8], "texto": hist[-1]["content"], "fala": r["fala"],
                                 "audio_estado": estado_audio}
    if r["acao"]:
        if r["acao"]["tipo"] == "cronometro":  # não sai do Início: começa já, enquanto responde
            st.session_state.crono_cmd = {"id": uuid.uuid4().hex[:8], "minutos": r["acao"]["minutos"],
                                          "pausa": r["acao"]["pausa"], "cadeira": r["acao"].get("cadeira") or ""}
        else:  # mudar de página só depois de acabar de falar (senão a fala era cortada)
            st.session_state.voz_acao = r["acao"]
    st.rerun()


def resumo_do_dia() -> None:
    """Quatro números do dia: próxima avaliação, foco, plano de hoje e flashcards para rever."""
    futuras = repo().proximas()
    prox = futuras[0] if futuras else None
    sessoes = sessoes_do_dia(date.today())
    feitas = sum(x["feita"] for x in sessoes)
    semana = sum(f.get("minutos", 0) for f in perfil.get("foco", [])
                 if f.get("data", "") >= (date.today() - timedelta(days=6)).isoformat())
    cartoes_hoje = sum(rs.resumo(d.get("cartoes") or [], date.today())["para_hoje"] for d in st.session_state.cadeiras.values()
                       if d.get("cartoes"))
    dias = av.dias_ate(prox, date.today()) if prox else None
    cartoes = [
        ("Próxima avaliação", ("Hoje" if dias == 0 else "Amanhã" if dias == 1 else f"{dias} dias") if prox else "—",
         f"{prox['nome']} · {prox['cadeira']}" if prox else "Nada marcado", bool(prox) and dias is not None and dias <= 3),
        ("Foco hoje", f"{minutos_foco_hoje()} min", f"{semana} min nos últimos 7 dias", False),
        ("Plano de hoje", f"{feitas}/{len(sessoes)}" if sessoes else "—", "tarefas feitas" if sessoes else "Nada planeado", False),
        ("Flashcards", str(cartoes_hoje), "para rever hoje", False),
    ]
    st.markdown("<div class='mi-dia'>" + "".join(
        f"<div class='mi-dia-c{' urgente' if urg else ''}'><div class='r'>{escape(r)}</div><div class='v'>{escape(v)}</div>"
        f"<div class='s'>{escape(sub)}</div></div>" for r, v, sub, urg in cartoes) + "</div>", unsafe_allow_html=True)


ESTILO_INICIO = """
<style>
/* Início do professor: as turmas numa lista (cada linha abre a turma) */
[class*="st-key-inicio_turma_"] { position:relative; }
[class*="st-key-inicio_turma_"] .stButton { position:absolute; inset:0; margin:0; z-index:1; }
[class*="st-key-inicio_turma_"] .stButton button { width:100%; height:100%; opacity:0; }
[class*="st-key-inicio_turma_"]:hover .mi-turma { background:var(--bolha); }
[class*="st-key-inicio_turma_"]:has(button:focus-visible) .mi-turma { outline:2px solid var(--acento); outline-offset:-2px; }
.mi-turma { display:flex; align-items:center; gap:0.75rem; padding:0.5rem 0.55rem; border-radius:12px; transition:background .12s ease; }
.mi-turma .mi-sala-ico { width:38px; height:38px; border-radius:11px; display:grid; place-items:center; flex:none; }
.mi-turma .mi-sala-ico .material-symbols-rounded { font-size:21px; }
.mi-turma b { display:block; font-weight:600; color:var(--texto); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mi-turma span { color:var(--suave); font-size:0.85rem; }
.st-key-caixa_assistente_inicio { background:var(--cartao) !important; box-shadow:var(--sombra-1); }

</style>
"""


PREPARAR_PROFESSOR = [
    ("planear", ":material/event_note:", "Planear uma aula",
     "Ajuda-me a planear uma aula. Pergunta-me primeiro a cadeira, o tema, a duração e o nível da turma, e depois "
     "propõe os objetivos, a sequência de atividades com tempos e um exercício para o fim."),
    ("ficha", ":material/assignment:", "Criar uma ficha de exercícios",
     "Quero criar uma ficha de exercícios para os meus alunos. Pergunta-me o tema, o nível e quantos exercícios, e "
     "faz a ficha do mais fácil para o mais difícil, com as soluções numa secção à parte."),
    ("teste", ":material/fact_check:", "Fazer um teste com critérios",
     "Ajuda-me a fazer um teste. Pergunta-me a matéria, a duração e o tipo de perguntas, e faz o enunciado com "
     "cotações (a somar 20 valores) e os critérios de correção de cada pergunta."),
]


def preparar_com_ia(texto: str) -> None:
    """Começa uma conversa com o pedido já escrito (o assistente responde logo, com perguntas se precisar)."""
    cid = criar_conversa(texto, None, {})
    navegar("chat", conversa_id=cid, pergunta_pendente=texto)


def turmas_do_professor() -> tuple[list, int]:
    """(salas partilhadas, mensagens novas) de quem é professor: as turmas que criou primeiro."""
    try:
        backend = obter_backend_salas()
        if not backend.atual():
            return [], 0
        salas_ = sorted(backend.minhas_salas(), key=lambda x: (not x.get("e_criador"), dz._sem_acentos(x["nome"])))
    except Exception:  # noqa: BLE001 — o Início nunca falha por causa das salas
        return [], 0
    novas = sum(n for _, _, n in salas_com_mensagens_novas())
    return salas_, novas


def inicio_professor() -> None:
    """Início de quem ensina: as turmas, as mensagens dos alunos, os avisos e o que preparar com a IA."""
    import salas as sl

    turmas, novas = turmas_do_professor()
    minhas_t = [t for t in turmas if t.get("e_criador")]
    alunos = sum(max(0, int(t.get("n_membros") or 1) - 1) for t in minhas_t)
    futuras = repo().proximas()
    prox = futuras[0] if futuras else None
    dias = av.dias_ate(prox, date.today()) if prox else None
    cartoes = [
        ("Turmas", str(len(minhas_t)), "criadas por ti" if minhas_t else "Cria a primeira em Salas", False),
        ("Alunos", str(alunos), "nas tuas turmas", False),
        ("Mensagens novas", str(novas), "nas conversas das turmas" if novas else "Tudo lido", bool(novas)),
        ("Próxima avaliação", ("Hoje" if dias == 0 else "Amanhã" if dias == 1 else f"{dias} dias") if prox else "—",
         f"{prox['nome']} · {prox['cadeira']}" if prox else "Nada marcado", bool(prox) and dias is not None and dias <= 3),
    ]
    st.markdown("<div class='mi-dia'>" + "".join(
        f"<div class='mi-dia-c{' urgente' if urg else ''}'><div class='r'>{escape(r)}</div><div class='v'>{escape(v)}</div>"
        f"<div class='s'>{escape(sub)}</div></div>" for r, v, sub, urg in cartoes) + "</div>", unsafe_allow_html=True)
    cartao_avisos()
    with st.container(border=True, key="caixa_assistente_inicio"):
        c1, c2 = st.columns([3, 1.4], vertical_alignment="center")
        with c1:
            titulo_cartao("Assistente Mondego")
        c2.button("Preferes escrever?", icon=":material/forum:", key="inicio_para_chat", type="tertiary", width="stretch",
                  on_click=navegar, args=("chat",), kwargs={"conversa_id": None},
                  help="Para escrever, anexar PDFs e fotografias, usa o Assistente.")
        assistente_voz()
    esquerda, direita = st.columns([1.75, 1], gap="large")
    with esquerda:
        with st.container(border=True, key="inicio_turmas"):
            c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
            with c1:
                titulo_cartao("As tuas turmas")
            c2.button("Criar turma", icon=":material/add:", key="inicio_criar_turma", type="tertiary", width="stretch",
                      on_click=navegar, args=("salas",), kwargs={"sala_aberta": None, "salas_dialogo": "criar"})
            if not turmas:
                st.caption("Ainda não tens turmas. Cria uma para cada cadeira que dás: os alunos entram com o código e "
                           "encontram lá os materiais, os avisos e um assistente que responde com eles.")
            for t in turmas[:6]:
                n_al = max(0, int(t.get("n_membros") or 1) - 1)
                sub = " · ".join(x for x in [t.get("cadeira") or "", f"{n_al} aluno{'s' if n_al != 1 else ''}"
                                             if t.get("e_criador") else "Membro"] if x)
                with st.container(key=f"inicio_turma_{t['id'][:12]}"):
                    st.markdown(f"<div class='mi-turma'>{ico_sala_html(t)}<div class='mi-encolhe'><b>{escape(t['nome'])}"
                                f"</b><span>{escape(sub)}</span></div></div>", unsafe_allow_html=True)
                    st.button("Abrir", key=f"inicio_abrir_turma_{t['id']}", type="tertiary", on_click=navegar,
                              args=("salas",), kwargs={"sala_aberta": t["id"]})
        st.write("")
        calendario_inicio()
    with direita:
        with st.container(border=True, key="inicio_preparar"):
            titulo_cartao("Preparar com a IA")
            st.caption("O assistente pergunta-te o que falta e prepara-o contigo.")
            for chave_p, icone_p, rotulo_p, pedido_p in PREPARAR_PROFESSOR:
                st.button(rotulo_p, icon=icone_p, key=f"preparar_{chave_p}", width="stretch", disabled=not tem_chave,
                          on_click=preparar_com_ia, args=(pedido_p,))
        st.write("")
        cartao_proxima_avaliacao()


def cartao_proxima_avaliacao() -> None:
    """Próximas avaliações (até 4): a primeira com a contagem exata (horas e minutos no próprio dia). O número grande
    do dia já está nos números do Início; aqui fica a lista, sem repetir o destaque."""
    futuras = repo().proximas()
    if not futuras:
        with st.container(border=True):
            titulo_cartao("Próximas avaliações")
            st.caption("Ainda não tens avaliações marcadas. Marca os teus testes e exames para veres aqui quanto tempo falta.")
            if st.button("Nova avaliação", icon=":material/add:", type="primary"):
                dialogo_nova(None)
        return
    agora = datetime.now()

    def falta(r: dict) -> str:
        dias = av.dias_ate(r, agora.date())
        if dias >= 2:
            return f"{dias} dias"
        if dias == 1:
            return "amanhã"
        if r.get("hora"):
            horas, resto = divmod(max(0, int((av.data_hora(r) - agora).total_seconds()) // 60), 60)
            return f"daqui a {horas}h{resto:02d}" if horas else f"daqui a {resto} min"
        return "hoje"

    linhas = []
    for n, r in enumerate(futuras[:4]):
        urgente = av.dias_ate(r, agora.date()) <= 3
        cor = av.CORES.get(r["tipo"], "#7C8C91")
        linhas.append(f"<div class='mi-av{' primeira' if n == 0 else ''}'><i style='background:{cor}'></i>"
                      f"<div class='mi-av-c'><b>{escape(r['nome'])}</b><span>{escape(r['cadeira'])} · {r['tipo']} · "
                      f"{data_longa(r['data'])}{(' às ' + r['hora']) if r.get('hora') else ''}</span></div>"
                      f"<em class='cd-tag{' urg' if urgente else ''}'>{falta(r)}</em></div>")
    mais = len(futuras) - 4
    st.markdown("<div class='mi-avs'><div class='mi-sec'><b>Próximas avaliações</b>"
                f"<span>{len(futuras)} marcada{'s' if len(futuras) != 1 else ''}</span></div>" + "".join(linhas)
                + (f"<div class='ec-meta mi-av-mais'>e mais {mais} no calendário</div>" if mais > 0 else "") + "</div>",
                unsafe_allow_html=True)


def abrir_aviso(destino: tuple, ident: str) -> None:
    tipo, alvo = destino
    if tipo == "avaliacao":
        navegar("calendario", abrir_avaliacao=alvo, **{f"modo_{alvo}": "ver"})
    elif tipo == "plano":
        navegar("calendario", cal_vista="Plano")
    elif tipo == "cartoes" and alvo in st.session_state.cadeiras:
        navegar("cadeira", cadeira_atual=alvo, ferramenta_pendente="Flashcards")
    elif tipo == "cadeira" and alvo in st.session_state.cadeiras:
        navegar("cadeira", cadeira_atual=alvo, ferramenta_pendente="Quiz")
    elif tipo == "sala":
        navegar("salas", sala_aberta=alvo)
    if tipo in ("cartoes", "cadeira", "sala"):
        dispensar_aviso(ident)


ROTULO_AVISO = {"avaliacoes": "Ver", "tarefas": "Reorganizar", "estudo": "Ver o plano", "cartoes": "Rever",
                "revisao": "Fazer um quiz", "salas": "Abrir a sala"}


def cartao_avisos() -> None:
    """Os avisos do dia, discretos: até 4 linhas, cada uma com uma ação e «Dispensar» (volta amanhã se ainda fizer
    sentido). Escolhem-se em Definições → Notificações."""
    lista = avisos_de_hoje()
    if not lista:
        return
    with st.container(border=True, key="inicio_avisos"):
        mais = len(lista) - 4
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        c1.markdown(f"<div class='mi-sec'><b>Avisos</b><span>{len(lista)} para hoje</span></div>", unsafe_allow_html=True)
        c2.button("Escolher avisos", icon=":material/tune:", key="avisos_defs", type="tertiary", width="stretch",
                  on_click=navegar, args=("definicoes",), kwargs={"def_cat": "notificacoes", "def_aberta": True})
        for a_ in lista[:4]:
            h = chave_curta(a_["id"])
            with st.container(horizontal=True, key=f"avisol_{h}{'_urg' if a_['urgente'] else ''}", gap="small",
                              vertical_alignment="center"):
                st.markdown(f"<div class='mi-aviso'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>{a_['icone']}</span>"
                            f"<div><b>{escape(a_['titulo'])}</b><span>{escape(a_['texto'])}</span></div></div>",
                            unsafe_allow_html=True)
                st.button(ROTULO_AVISO.get(a_["tipo"], "Abrir"), key=f"aviso_abrir_{h}", on_click=abrir_aviso,
                          args=(a_["destino"], a_["id"]))
                st.button("Dispensar", icon=":material/close:", key=f"aviso_fechar_{h}", type="tertiary",
                          help="Dispensar por hoje", on_click=dispensar_aviso, args=(a_["id"],))
        if mais > 0:
            st.caption(f"e mais {mais} {'aviso' if mais == 1 else 'avisos'}.")


if vista == "inicio":
    st.markdown(ESTILO_CALENDARIO, unsafe_allow_html=True)
    if abrir_plano_se_pedido():
        pass
    elif "abrir_avaliacao" in st.session_state:
        dialogo_avaliacao(st.session_state.pop("abrir_avaliacao"))
    elif "nova_avaliacao_dia" in st.session_state:
        dialogo_nova(st.session_state.pop("nova_avaliacao_dia"))
    cabecalho(saudacao(), f"{DIAS_SEMANA[date.today().weekday()]}, {data_longa(date.today()).split(', ', 1)[1]}")
    if "_toast" in st.session_state:
        st.toast(st.session_state.pop("_toast"), icon=":material/timer:")
    if "cal_msg" in st.session_state:
        st.success(st.session_state.pop("cal_msg"), icon=":material/check_circle:")
    if "cal_erro" in st.session_state:
        st.error(st.session_state.pop("cal_erro"))
    if not acad.get("completo"):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
            c1.markdown("**Completa o teu perfil** — nível de ensino, curso e se és aluno ou professor. Demora um "
                        "minuto e torna as respostas do assistente mais adequadas.")
            if c2.button("Completar", type="primary", width="stretch"):
                st.session_state.editar_academico = True
                st.session_state.passo = 0
                st.rerun()
    mostrar_avisos_de_planos("inicio")

    st.markdown(ESTILO_INICIO, unsafe_allow_html=True)
    if acad.get("vinculo") == "Professor":  # quem ensina vê as turmas e o que preparar, não um plano de estudo
        inicio_professor()
        st.stop()
    # 1. o dia num relance (o mais importante primeiro) e os avisos
    resumo_do_dia()
    cartao_avisos()
    # 2. Assistente Mondego: falar (voz) ou escrever — a ação principal do Início
    with st.container(border=True, key="caixa_assistente_inicio"):
        c1, c2 = st.columns([3, 1.4], vertical_alignment="center")
        with c1:
            titulo_cartao("Assistente Mondego")
        c2.button("Preferes escrever?", icon=":material/forum:", key="inicio_para_chat", type="tertiary", width="stretch",
                  on_click=navegar, args=("chat",), kwargs={"conversa_id": None},
                  help="Para escrever, anexar PDFs e fotografias, usa o Assistente.")
        assistente_voz()
    # 3. próximas avaliações e calendário | plano de hoje e cronómetro
    esquerda, direita = st.columns([1.75, 1], gap="large")
    with esquerda:
        cartao_proxima_avaliacao()
        st.write("")
        calendario_inicio()
    with direita:
        with st.container(border=True):
            titulo_cartao("Plano de hoje")
            sessoes_hoje = sessoes_do_dia(date.today())
            for s_ in sessoes_hoje:
                principal_, detalhe_ = pe.texto_da_tarefa(s_)
                chave_h = chave_tarefa("hoje", s_["id"], s_["feita"])
                st.checkbox(f"**{s_.get('cadeira', '')}** — {principal_}", value=s_["feita"], key=chave_h,
                            help=detalhe_ or None, on_change=marcar_feita_cb, args=(s_["id"], chave_h))
            if sessoes_hoje:
                n_feitas = sum(x["feita"] for x in sessoes_hoje)
                st.progress(n_feitas / len(sessoes_hoje), text=f"{n_feitas} de {len(sessoes_hoje)} feitas")
            else:
                st.caption("Nada planeado para hoje.")
            seguintes = [x for x in av.sessoes_de_estudo(perfil, st.session_state.cadeiras)
                         if date.today().isoformat() < x["data"] <= (date.today() + timedelta(days=3)).isoformat()]
            if seguintes:
                st.markdown("<div class='ec-meta mi-proximos'><b>Próximos dias</b></div>", unsafe_allow_html=True)
                for x in seguintes[:4]:
                    st.markdown(f"<div class='ec-meta'>{fmt_data(x['data'], False)} · {escape(str(x.get('cadeira', '')))}: "
                                f"{escape(pe.texto_da_tarefa(x)[0])}</div>", unsafe_allow_html=True)
            planos_i = planos_existentes()
            if not planos_i:
                st.button("Criar plano de estudo", icon=":material/auto_awesome:", width="stretch", type="primary",
                          key="inicio_criar_plano", disabled=not tem_chave or not st.session_state.cadeiras,
                          help="A IA pergunta-te como gostas de estudar e o que achas mais difícil.",
                          on_click=novo_assistente_plano)
            else:
                b1, b2 = st.columns([1.25, 1])
                b1.button("Ver o plano", icon=":material/event_note:", width="stretch", key="inicio_ver_plano",
                          on_click=navegar, args=("calendario",), kwargs={"cal_vista": "Plano"})
                with b2.popover("Gerir", icon=":material/tune:", width="stretch"):
                    st.button("Refazer com a IA", icon=":material/auto_awesome:", key="inicio_refazer_plano",
                              width="stretch", disabled=not tem_chave, on_click=novo_assistente_plano,
                              args=(ambito_do_plano(*planos_i[0]),))
                    for origem_i, nome_i, _p in planos_i:
                        if st.button(f"Apagar o plano {'geral' if origem_i == 'g' else 'de ' + nome_i}",
                                     icon=":material/delete:", key=f"inicio_apagar_{origem_i}_{chave_curta(nome_i or 'g')}",
                                     width="stretch"):
                            apagar_plano(origem_i, nome_i)
                            st.session_state.cal_msg = "Plano apagado."
                            st.rerun()
        with st.container(border=True):
            titulo_cartao("Cronómetro de estudo")
            cronometro()
    st.stop()

# =============================================================== PERFIL (conta, estatísticas e projetos)
def grafico_tema(grafico):
    """Gráfico Altair com fundo transparente e letra/grelha neutras: lê-se bem no tema claro e no escuro
    (o tema do Streamlit é sempre o claro; o escuro é feito com CSS e não chega aos gráficos)."""
    cinza = "#7C8C91"
    return (grafico.properties(background="transparent")
            .configure_axis(labelColor=cinza, titleColor=cinza, gridColor="rgba(140,133,122,0.22)", domainColor=cinza,
                            tickColor=cinza, labelFontSize=11.5)
            .configure_legend(labelColor=cinza, titleColor=cinza, labelFontSize=12)
            .configure_view(strokeWidth=0))


def estatisticas_perfil() -> dict:
    hoje = date.today()
    uso = perfil.get("uso", {})
    foco = perfil.get("foco", [])
    cadeiras = st.session_state.cadeiras.values()
    quizzes = [h for d in cadeiras for h in d.get("quiz_historico", [])]
    testes = [h for d in cadeiras for h in d.get("teste_historico", []) if isinstance(h.get("nota"), (int, float))]
    modelos, conta_3d = [], False
    try:
        if not ESTUDIO_3D:
            raise LookupError("3D Studio escondido")
        import biblioteca3d as b3

        bib = b3.abrir(obter_backend_salas())
        if bib.contas.atual():
            conta_3d = True
            modelos = bib.meus("todos")
    except Exception:  # noqa: BLE001
        pass
    semana = [(hoje - timedelta(days=i)).isoformat() for i in range(7)]
    pend = st.session_state.get("_uso_pend", 0)  # tempo desta sessão ainda por gravar (grava-se de minuto a minuto)
    return {
        "uso_total": sum(uso.values()) + pend, "uso_hoje": uso.get(hoje.isoformat(), 0) + pend,
        "uso_semana": sum(uso.get(d, 0) for d in semana) + pend, "conta_3d": conta_3d,
        "foco_total": sum(f.get("minutos", 0) for f in foco) * 60,
        "foco_semana": sum(f.get("minutos", 0) for f in foco if f.get("data") in semana) * 60,
        "quizzes": len(quizzes), "media_quiz": (sum(h["nota"] for h in quizzes) / len(quizzes)) if quizzes else None,
        "testes": len(testes), "cartoes": sum(c.get("vistas", 0) for d in cadeiras for c in (d.get("cartoes") or [])),
        "conversas": len(conversas), "modelos": modelos, "linhas": len(perfil.get("linhas_tempo", {})),
        "mapas": len(perfil.get("mapas", {})),
        "materiais": sum(bool(d.get(k)) for d in cadeiras for k in ("resumo", "guia", "mapa", "slides", "quiz", "cartoes", "teste")),
        "documentos": sum(len(d["ficheiros"]) for d in cadeiras),
    }


ESTILO_SALAS = """<style>
.sl-pessoa { display:flex; align-items:center; gap:0.6rem; color:var(--texto); }
.sl-pessoa b, .sl-doc b { color:var(--texto) !important; }
.sl-avatar { width:34px; height:34px; border-radius:50%; flex:0 0 34px; display:grid; place-items:center; color:#fff;
  font-weight:600; font-size:0.95rem; object-fit:cover; }
.sl-doc { display:flex; flex-direction:column; min-width:0; }
.sl-doc b { font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--texto); }
.sl-doc span { font-size:var(--t-xs); color:var(--suave); }
</style>"""


def avatar_html(nome: str, foto: bytes | None = None) -> str:
    if foto:
        return f"<img class='sl-avatar' src='data:image/jpeg;base64,{base64.b64encode(foto).decode()}' alt=''>"
    paleta = ["#17798A", "#2E6DB4", "#3E8E5A", "#7D4FA8", "#2AA5B8", "#D9708F", "#7C8C91"]
    cor = paleta[sum(map(ord, nome or "?")) % len(paleta)]
    return f"<span class='sl-avatar' style='background:{cor}'>{escape((nome or '?')[:1].upper())}</span>"


def foto_quadrada(dados: bytes, lado: int = 256) -> bytes:
    """Fotografia de perfil: corta ao centro em quadrado, reduz e guarda em JPEG (fica leve)."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(dados))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (lado, lado), Image.LANCZOS)
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=86)
    return saida.getvalue()


def conta_salas_atual():
    """Conta das Salas com sessão iniciada (ou None), sem rebentar se a base de dados não abrir."""
    try:
        backend = obter_backend_salas()
        return backend, backend.atual()
    except Exception:  # noqa: BLE001
        return None, None


@st.dialog("Editar perfil")
def dialogo_editar_perfil() -> None:
    import salas_backend as sb

    nome_atual = perfil.get("nome") or ""
    nome = st.text_input("Nome", value=nome_atual, max_chars=80, key="ep_nome",
                         help="Aparece no Início, nas respostas do assistente e nas Salas.")
    foto_atual = base64.b64decode(perfil["foto"]) if perfil.get("foto") else None
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if foto_atual:
        c1.image(foto_atual, width=84)
    else:
        c1.markdown(f"<div class='mi-avatar-g'>{escape((nome or '?')[:1].upper())}</div>", unsafe_allow_html=True)
    nova = c2.file_uploader("Fotografia", type=["png", "jpg", "jpeg", "webp"], key="ep_foto",
                            help="Fica guardada neste computador; nas Salas os colegas também a veem.")
    remover = bool(foto_atual) and c2.checkbox("Remover a fotografia", key="ep_remover")
    titulo_cartao("Perfil académico")
    st.caption(ac.resumo_perfil(acad) if acad.get("nivel") else "Ainda não preenchido.")
    a, b = st.columns(2)
    if a.button("Guardar", type="primary", width="stretch", key="ep_guardar"):
        nome = " ".join(nome.split())
        if len(nome) < 2:
            st.error("Escreve o teu nome (pelo menos 2 letras).")
            return
        foto_nova = None
        if nova is not None:
            try:
                foto_nova = foto_quadrada(nova.getvalue())
            except Exception:  # noqa: BLE001
                st.error("Não consegui abrir essa imagem. Experimenta outra (PNG ou JPEG).")
                return
        perfil["nome"] = nome
        if foto_nova:
            perfil["foto"] = base64.b64encode(foto_nova).decode()
        elif remover:
            perfil.pop("foto", None)
        guardar_perfil()
        backend, conta = conta_salas_atual()
        if conta:
            try:
                backend.mudar_perfil(nome=nome, foto=foto_nova, apagar_foto=remover and not foto_nova)
            except sb.ErroSalas as erro:
                st.warning(f"Perfil guardado, mas não consegui atualizar a conta das Salas: {erro}")
        st.toast("Perfil atualizado.", icon=":material/check_circle:")
        st.rerun()
    if b.button("Editar o perfil académico", icon=":material/school:", width="stretch", key="ep_acad"):
        st.session_state.editar_academico = True
        st.session_state.passo = 0
        st.rerun()


def progresso_por_cadeira() -> None:
    """Por cadeira, com os dados que a app tem: tarefas do plano feitas, notas dos quizzes (média e a última), tempo de
    foco nos últimos 7 dias, flashcards para rever e o tema a rever."""
    nomes = sorted(st.session_state.cadeiras, key=lambda n_: (data_avaliacao(st.session_state.cadeiras[n_]) or date.max,
                                                              dz._sem_acentos(n_)))
    if not nomes:
        return
    feitas_ = set(perfil.get("feitas", []))
    tarefas_ = av.sessoes_de_estudo(perfil, st.session_state.cadeiras)
    foco_7 = dfs.resumo_foco(perfil.get("foco", []), date.today())["por_cadeira"]
    fracos = dict(temas_fracos())
    linhas = []
    for nome_c in nomes:
        d = st.session_state.cadeiras[nome_c]
        t_c = [t for t in tarefas_ if t.get("cadeira") == nome_c]
        notas = [h_["nota"] for h_ in d.get("quiz_historico", []) if isinstance(h_.get("nota"), (int, float))]
        rever = rs.resumo(d.get("cartoes") or [], date.today())["para_hoje"] if d.get("cartoes") else 0
        prox = repo().proxima(nome_c)
        partes = []
        if t_c:
            partes.append(f"plano {sum(t['feita'] for t in t_c)}/{len(t_c)}")
        if notas:
            partes.append(f"quizzes {sum(notas) / len(notas):.1f}".replace(".", ",") + f" (último {notas[-1]:.1f})".replace(".", ","))
        if foco_7.get(nome_c):
            partes.append(f"foco {fmt_duracao(foco_7[nome_c] * 60)} em 7 dias")
        if rever:
            partes.append(f"{rever} flashcards por rever")
        pct = 100 * sum(t["feita"] for t in t_c) / len(t_c) if t_c else None
        linhas.append(
            f"<div class='mi-prog'><div class='mi-prog-c'><b>{escape(nome_c)}</b><span>"
            + (escape(f"{prox['nome']} {av.texto_faltam(prox)}") if prox else "sem avaliações marcadas") + "</span></div>"
            + (f"<div class='mi-prog-b' role='img' aria-label='{pct:.0f}% do plano feito'><i style='width:{pct:.0f}%;"
               f"background:{cor_cadeira(nome_c)}'></i></div>" if pct is not None else "<div class='mi-prog-b vazio'></div>")
            + f"<div class='mi-prog-t'>{escape(' · '.join(partes) or 'ainda sem atividade')}"
            + (f"<em>Rever: {escape(fracos[nome_c])}</em>" if nome_c in fracos else "") + "</div></div>")
    with st.container(border=True, key="perfil_progresso"):
        titulo_cartao("Progresso por sala", "plano, quizzes, foco e revisões")
        st.markdown("<div class='mi-progs'>" + "".join(linhas) + "</div>", unsafe_allow_html=True)


def pagina_perfil() -> None:
    ext = utilizador_externo()
    nome = perfil.get("nome") or (ext or {}).get("nome") or "O meu perfil"
    st.markdown(ESTILO_SALAS, unsafe_allow_html=True)
    with st.container(key="perfil_topo"):  # cabeçalho como o das outras páginas, com a fotografia à esquerda
        c1, c2, c3 = st.columns([1, 5, 1.6], vertical_alignment="center")
        if perfil.get("foto"):
            c1.image(base64.b64decode(perfil["foto"]), width=72)
        elif ext and ext.get("foto"):
            c1.image(ext["foto"], width=72)
        else:
            c1.markdown(f"<div class='mi-avatar-g'>{escape(nome[:1].upper())}</div>", unsafe_allow_html=True)
        linha = ac.resumo_perfil(acad) if acad.get("nivel") else "Perfil académico por completar"
        c2.markdown(f"<div class='pg-cab pf-cab'><h1>{escape(nome)}</h1><p>{escape(linha)}</p></div>", unsafe_allow_html=True)
        if c3.button("Editar perfil", icon=":material/edit:", type="primary", width="stretch", key="editar_perfil"):
            dialogo_editar_perfil()
    e = estatisticas_perfil()
    st.markdown("<div class='mi-dia'>" + "".join(
        f"<div class='mi-dia-c'><div class='r'>{escape(r)}</div><div class='v'>{escape(v)}</div><div class='s'>{escape(sub)}</div></div>"
        for r, v, sub in [
            ("Tempo na aplicação", fmt_duracao(e["uso_total"]), f"hoje {fmt_duracao(e['uso_hoje'])} · 7 dias {fmt_duracao(e['uso_semana'])}"),
            ("Tempo de estudo (foco)", fmt_duracao(e["foco_total"]), f"7 dias: {fmt_duracao(e['foco_semana'])}"),
            ("Quizzes e testes", f"{e['quizzes'] + e['testes']}", (f"média dos quizzes {e['media_quiz']:.1f}".replace(".", ",") + " valores")
             if e["media_quiz"] is not None else "ainda sem notas"),
            ("Flashcards revistos", str(e["cartoes"]), "revisões em todas as salas"),
        ]) + "</div>", unsafe_allow_html=True)
    esq, dir_ = st.columns([1.6, 1], gap="large")
    with esq:
        with st.container(border=True):
            titulo_cartao("Os últimos 14 dias")
            dias = [(date.today() - timedelta(days=i)) for i in range(13, -1, -1)]
            foco_dia = {}
            for f in perfil.get("foco", []):
                foco_dia[f.get("data")] = foco_dia.get(f.get("data"), 0) + f.get("minutos", 0)
            import altair as alt

            series = ["Na aplicação", "A estudar"]
            linhas = [{"dia": d.strftime("%d/%m"), "série": series[0], "minutos": round(perfil.get("uso", {}).get(d.isoformat(), 0) / 60)}
                      for d in dias] + [{"dia": d.strftime("%d/%m"), "série": series[1], "minutos": foco_dia.get(d.isoformat(), 0)}
                                        for d in dias]
            barras = alt.Chart(pd.DataFrame(linhas)).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("dia:N", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelOverlap="greedy")),
                xOffset=alt.XOffset("série:N", sort=series),
                y=alt.Y("minutos:Q", title="minutos", axis=alt.Axis(tickMinStep=1)),
                color=alt.Color("série:N", sort=series, scale=alt.Scale(domain=series, range=["#E0B04B", "#17798A"]),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("dia:N", title="Dia"), alt.Tooltip("série:N", title=" "), alt.Tooltip("minutos:Q", title="Minutos")],
            ).properties(height=240)
            st.altair_chart(grafico_tema(barras), theme=None, width="stretch")
            por_cadeira = {}
            for f in perfil.get("foco", []):
                if f.get("cadeira"):
                    por_cadeira[f["cadeira"]] = por_cadeira.get(f["cadeira"], 0) + f.get("minutos", 0)
            if por_cadeira:
                st.caption("Tempo de estudo por sala: " + " · ".join(f"{c}: {fmt_duracao(m * 60)}" for c, m in
                                                                        sorted(por_cadeira.items(), key=lambda kv: -kv[1])))
        progresso_por_cadeira()
        with st.container(border=True):
            titulo_cartao("Criado com IA")
            itens = ([("Modelos 3D", len(e["modelos"]), ":material/view_in_ar:")] if ESTUDIO_3D else []) + [
                     ("Conversas com o assistente", e["conversas"], ":material/forum:"),
                     ("Materiais de estudo (resumos, quizzes, flashcards…)", e["materiais"], ":material/auto_awesome:"),
                     ("Linhas do tempo", e["linhas"], ":material/timeline:"), ("Mapas", e["mapas"], ":material/map:")]
            st.markdown("<div class='mi-contas'>" + "".join(
                f"<div><span class='material-symbols-rounded' translate='no'>{icone.split('/')[1].strip(':')}</span><span>{escape(rotulo)}</span>"
                f"<b>{n}</b></div>" for rotulo, n, icone in itens) + "</div>", unsafe_allow_html=True)
            if ESTUDIO_3D and not e["conta_3d"]:
                st.caption("Os modelos 3D ficam na tua conta do 3D Studio: entra lá para os contar aqui.")
            if ESTUDIO_3D and e["modelos"]:
                st.caption("Modelos recentes: " + ", ".join(m["titulo"] for m in e["modelos"][:5]))
                st.button("Abrir os meus modelos 3D", icon=":material/view_in_ar:", on_click=navegar, args=("estudio3d",),
                          kwargs={"e3d_secao": "meus", "e3d_aberto": None, "e3d_ver": None})
    with dir_:
        with st.container(border=True):
            titulo_cartao("Conta")
            if ext:  # o mesmo desenho da conta das Salas: nome e email da conta ligada
                st.markdown(f"<div class='sl-pessoa'>{avatar_html(ext['nome'] or ext['email'])}<div><b>"
                            f"{escape(ext['nome'] or ext['email'])}</b><br><span class='ec-meta'>{escape(ext['email'] or '')}"
                            "</span></div></div>", unsafe_allow_html=True)
                st.caption("A sessão fica iniciada neste browser até a terminares. É a mesma conta das Salas.")
                st.button("Terminar sessão", icon=":material/logout:", on_click=terminar_sessao, width="stretch",
                          key="perfil_sair")
            else:
                _b, conta = conta_salas_atual()
                if conta:
                    st.markdown(f"<div class='sl-pessoa'>{avatar_html(conta['nome'], conta.get('foto'))}<div><b>{escape(conta['nome'])}"
                                f"</b><br><span class='ec-meta'>{escape(conta['email'])} · conta das Salas</span></div></div>",
                                unsafe_allow_html=True)
                    st.caption("O nome e a fotografia que mudares aqui também mudam nesta conta (os colegas das salas veem-nos).")
                    st.button("Terminar sessão", icon=":material/logout:", on_click=terminar_sessao, width="stretch",
                              key="perfil_sair")
                else:
                    st.caption("Entra com a tua conta para ficares com o perfil identificado (e usares a mesma conta nas Salas).")
                    botoes_login("perfil")
        with st.container(border=True, key="perfil_atalhos"):
            titulo_cartao("Definições")
            for cat_, rot_ in (("conta", "Nome, palavra-passe e sessões"), ("privacidade", "Os teus dados e a privacidade"),
                               ("notificacoes", "Avisos"), ("acessibilidade", "Acessibilidade")):
                st.button(rot_, key=f"perfil_ir_{cat_}", icon=f":material/{dict((c[0], c[2]) for c in dfs.CATEGORIAS)[cat_]}:",
                          type="tertiary", width="stretch", on_click=navegar, args=("definicoes",),
                          kwargs={"def_cat": cat_, "def_aberta": True})
        with st.container(border=True):
            titulo_cartao("Perfil académico")
            st.caption(ac.resumo_perfil(acad) if acad.get("nivel") else "Ainda não preenchido.")
            if st.button("Editar o perfil académico", icon=":material/edit:", width="stretch"):
                st.session_state.editar_academico = True
                st.session_state.passo = 0
                st.rerun()
    if e_admin():  # as «coisas da API» só aparecem a quem gere a app
        with st.container(border=True, key="perfil_admin"):
            titulo_cartao("Administração da app", "só tu vês isto")
            aba_ia, aba_web, aba_salas, aba_entrada = st.tabs(["Chave da IA", "Pesquisa na web", "Salas online",
                                                                "Início de sessão"])
            with aba_ia:
                definicoes_ia(horizontal=True, com_3d=True)
            with aba_web:
                definicoes_pesquisa_web()
            with aba_salas:
                definicoes_salas()
            with aba_entrada:
                definicoes_inicio_sessao()


if vista == "perfil":
    st.markdown(ESTILO_INICIO, unsafe_allow_html=True)
    pagina_perfil()
    st.stop()


# =============================================================== DEFINIÇÕES (página por categorias)
# Tudo o que a pessoa pode ajustar, num só sítio: navegação por categorias (à esquerda no computador; lista → categoria
# no telemóvel), pesquisa, linhas «título e descrição | controlo». As escolhas simples guardam-se logo (e a página diz
# quando guardou); os formulários (nome, palavra-passe, objetivos) têm «Guardar alterações» e avisam se ficar algo por
# guardar. As preferências ficam no perfil da conta (seguem a pessoa para outros dispositivos). Regras em definicoes.py.
ESTILO_DEFS = """<style>
.df-cab { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin:0 0 0.9rem; }
.df-cab h2 { font-size:var(--t-xl); font-weight:650; letter-spacing:-0.02em; margin:0; color:var(--texto); text-wrap:balance; }
.df-cab p { margin:0.2rem 0 0; color:var(--suave); font-size:var(--t-base); line-height:1.45; }
.df-estado { flex:none; display:inline-flex; align-items:center; gap:0.3rem; font-size:var(--t-sm); color:var(--suave);
  padding:0.18rem 0.6rem; border-radius:var(--r-pilula); background:var(--bolha); white-space:nowrap; margin-top:0.2rem;
  font-variant-numeric:tabular-nums; }
.df-estado .material-symbols-rounded { font-size:1rem; }
.df-estado.ok { color:var(--sucesso); background:var(--sucesso-claro); }
.df-estado.por { color:var(--aviso); background:var(--aviso-claro); }
.df-grupo { margin:1.1rem 0 0.35rem 0.15rem; }
.df-grupo b { display:block; font-size:var(--t-md); font-weight:600; color:var(--texto); letter-spacing:-0.01em; }
.df-grupo span { display:block; font-size:var(--t-sm); color:var(--suave); margin-top:0.1rem; line-height:1.45; }
[data-testid="stMarkdownContainer"]:has(> .df-cab, > .df-grupo, > .df-rot, > .df-valor, > .df-nav-t) { margin-bottom:0 !important; }
/* grupo: um cartão com linhas separadas por um fio */
[class*="st-key-defg_"] { gap:0 !important; padding-top:0.35rem !important; padding-bottom:0.35rem !important; }
[class*="st-key-defg_"] > div:not(:has([class*="st-key-defl_"])) { margin:0.45rem 0; }
.stApp [class*="st-key-defl_"] { flex-wrap:wrap !important; align-items:center !important; gap:0.5rem 1.2rem !important;
  padding:0.7rem 0; border-top:1px solid var(--linha); }
[class*="st-key-defg_"] > div:first-child [class*="st-key-defl_"], [class*="st-key-defg_"] > [class*="st-key-defl_"]:first-child {
  border-top:none; }
.stApp [class*="st-key-defl_"] > div:first-child { flex:1 1 13rem !important; min-width:0 !important; width:auto !important; }
.stApp [class*="st-key-defl_"] > div:not(:first-child) { flex:0 1 auto !important; width:auto !important; max-width:100%; }
.df-rot b { display:block; font-weight:550; color:var(--texto); font-size:var(--t-base); line-height:1.35; }
.df-rot span { display:block; color:var(--suave); font-size:var(--t-sm); line-height:1.45; margin-top:0.12rem; max-width:62ch; }
.df-valor { color:var(--texto); font-size:var(--t-base); overflow-wrap:anywhere; }
.df-valor small { display:block; color:var(--suave); font-size:var(--t-sm); }
[class*="st-key-defl_"] [data-testid="stSelectbox"] { min-width:13rem; }
[class*="st-key-defl_"] [data-testid="stNumberInput"] { width:7.5rem; }
/* zona de perigo */
.stApp .st-key-defg_perigo { border-color:color-mix(in srgb, var(--erro) 45%, var(--linha)) !important; }
.st-key-defs_apagar_conta button, .st-key-apagar_conta button { background:var(--erro) !important; border-color:var(--erro) !important;
  color:#fff !important; }
.st-key-defs_apagar_conta button p, .st-key-apagar_conta button p { color:#fff !important; }
/* navegação por categorias */
.df-nav-t { font-size:0.72rem; color:var(--suave); margin:0.9rem 0 0.3rem 0.6rem; font-weight:600; letter-spacing:0.02em; }
.st-key-defs_nav { gap:0.15rem !important; position:sticky; top:4.2rem; }
.st-key-defs_nav .stButton, .st-key-defs_nav .stButton button { width:100% !important; }
.st-key-defs_nav .stButton button { justify-content:flex-start; text-align:left; border-radius:var(--r-sm) !important;
  padding:0.42rem 0.65rem !important; min-height:2.3rem !important; box-shadow:none !important; position:relative; }
.st-key-defs_nav .stButton button > div { flex:1 1 auto; justify-content:flex-start; min-width:0; }
.st-key-defs_nav .stButton button p { font-size:0.92rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.st-key-defs_nav .stButton button[kind="tertiary"] { color:var(--texto); font-weight:400; }
.st-key-defs_nav .stButton button[kind="tertiary"]:hover { background:var(--bolha); }
.st-key-defs_nav .stButton button[kind="secondary"] { background:var(--acento-claro) !important; border:none !important; font-weight:600; }
.st-key-defs_nav .stButton button[kind="secondary"] :is(p, [data-testid="stIconMaterial"]) { color:var(--acento-esc) !important; }
.st-key-defs_nav .stButton button[kind="secondary"]::before { content:""; position:absolute; left:0; top:22%; bottom:22%; width:3px;
  border-radius:3px; background:var(--acento); }
.st-key-defs_nav .stButton button:focus-visible { outline:2px solid var(--foco, var(--acento)); outline-offset:2px; }
.st-key-defs_voltar { display:none; }
.st-key-defs_voltar button { padding-left:0 !important; color:var(--acento-esc) !important; }
/* o conteúdo entra com um movimento curto (mostra o que mudou ao escolher outra categoria) */
@keyframes df-entra { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
[class*="st-key-defs_c_"] { animation:df-entra 0.22s cubic-bezier(.2,.7,.2,1) both; }
/* telemóvel, tablet e ecrãs estreitos com a barra lateral aberta: primeiro a lista de categorias, depois a categoria */
@media (max-width: 820px) {
  .st-key-defs_estado_l [class*="st-key-defs_c_"] { display:none; }
  .st-key-defs_estado_a .st-key-defs_nav { display:none; }
  .st-key-defs_estado_a .st-key-defs_voltar { display:block; }
  .st-key-defs_nav { position:static; }
  .st-key-defs_nav [class*="st-key-defcat_"], .st-key-defs_nav [class*="st-key-defs_res_"] { width:100% !important; }
  .st-key-defs_nav .stButton button { min-height:3rem !important; padding:0.55rem 0.7rem !important; background:var(--cartao) !important;
    border:1px solid var(--linha) !important; }
  .st-key-defs_nav .stButton button::after { content:"chevron_right"; font-family:'Material Symbols Rounded'; font-size:1.25rem;
    color:var(--suave); margin-left:auto; flex:none; }
  .st-key-defs_nav .stButton button[kind="secondary"] { background:var(--cartao) !important; }
  .st-key-defs_nav .stButton button[kind="secondary"]::before { display:none; }
  @keyframes df-entra { from { opacity:0; transform:translateX(14px); } to { opacity:1; transform:none; } }
  .df-cab { flex-wrap:wrap; }
}
@media (min-width: 821px) and (max-width: 1100px) {
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) .st-key-defs_estado_l [class*="st-key-defs_c_"] { display:none; }
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) .st-key-defs_estado_a .st-key-defs_nav { display:none; }
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) .st-key-defs_estado_a .st-key-defs_voltar { display:block; }
  .stApp:not(:has([data-testid="stExpandSidebarButton"])) .st-key-defs_nav { position:static; }
}
</style>"""


def prefs_atuais() -> dict:
    """As preferências desta pessoa (tema, IA, avisos, acessibilidade…), sempre completas e válidas."""
    return dfs.limpar(st.session_state.cfg)


def _defs_guardado(texto: str = "Alterações guardadas.") -> None:
    st.session_state._defs_guardado = datetime.now().strftime("%H:%M")
    st.session_state._defs_toast = texto


def mudar_pref_cb(chave: str, widget: str, converter=None) -> None:
    """on_change das escolhas simples: guarda logo (no perfil da conta) e a página confirma."""
    valor = st.session_state.get(widget)
    if valor is None:  # carregar outra vez na opção escolhida não a desmarca
        return
    st.session_state.cfg[chave] = converter(valor) if converter else valor
    guardar_config()
    _defs_guardado()


def mudar_aviso_cb(campo: str, widget: str) -> None:
    valor = st.session_state.get(widget)
    if valor is None:
        return
    avisos_ = dfs.limpar_avisos(st.session_state.cfg.get("avisos"))
    avisos_[campo] = valor
    st.session_state.cfg["avisos"] = avisos_
    guardar_config()
    _defs_guardado()


@contextmanager
def grupo_def(chave: str, titulo: str, descricao: str = ""):
    """Um grupo de definições: título (e descrição) por cima de um cartão com as linhas."""
    st.markdown(f"<div class='df-grupo'><b>{escape(titulo)}</b>" + (f"<span>{escape(descricao)}</span>" if descricao else "")
                + "</div>", unsafe_allow_html=True)
    with st.container(border=True, key=f"defg_{chave}"):
        yield


def linha_def(chave: str, titulo: str, descricao: str = ""):
    """Uma linha: título e descrição à esquerda; devolve o contentor onde entra o controlo, à direita."""
    caixa = st.container(horizontal=True, key=f"defl_{chave}", gap="small")
    caixa.markdown(f"<div class='df-rot'><b>{escape(titulo)}</b>" + (f"<span>{escape(descricao)}</span>" if descricao else "")
                   + "</div>", unsafe_allow_html=True)
    return caixa


def interruptor_def(chave: str, titulo: str, descricao: str, valor: bool, ao_mudar, args: tuple, desligado: bool = False) -> None:
    with linha_def(chave, titulo, descricao):
        st.toggle(titulo, value=bool(valor), key=f"defs_w_{chave}", label_visibility="collapsed", on_change=ao_mudar,
                  args=args, disabled=desligado)


def escolha_def(chave: str, titulo: str, descricao: str, opcoes: list, valor, ao_mudar, args: tuple, formato=None,
                desligado: bool = False) -> None:
    with linha_def(chave, titulo, descricao):
        st.segmented_control(titulo, opcoes, default=valor, key=f"defs_w_{chave}", label_visibility="collapsed",
                             on_change=ao_mudar, args=args, format_func=formato or str, disabled=desligado)


def valor_def(chave: str, titulo: str, descricao: str, valor: str, nota: str = "") -> None:
    with linha_def(chave, titulo, descricao):
        st.markdown(f"<div class='df-valor'>{escape(valor)}" + (f"<small>{escape(nota)}</small>" if nota else "") + "</div>",
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- alterações por guardar (formulários)
CHAVES_FORM = {"conta": ("defs_nome", "defs_foto_rm", "defs_pp_atual", "defs_pp_nova", "defs_pp_conf"),
               "academico": ("defs_dias", "defs_ritmo", "defs_com", "defs_est", "defs_notas")}


def dias_de_estudo_atuais() -> list:
    return [d for d in pe.DIAS_SEMANA if d not in prefs_plano()["folga"]]


def defs_por_guardar(cat: str) -> str | None:
    """Há alterações por guardar nesta categoria? Devolve o nome do grupo (ou None). Lê os valores dos campos, por isso
    também serve nos on_click (antes de a página voltar a ser desenhada)."""
    ss = st.session_state
    if cat == "conta":
        if "defs_nome" in ss and " ".join(str(ss.defs_nome or "").split()) != (perfil.get("nome") or ""):
            return "Perfil"
        if ss.get(f"defs_foto_{ss.get('_defs_foto_v', 0)}") is not None or ss.get("defs_foto_rm"):
            return "Perfil"
        if any(ss.get(k) for k in ("defs_pp_atual", "defs_pp_nova", "defs_pp_conf")):
            return "Palavra-passe"
    elif cat == "academico":
        for nome_c, d in ss.cadeiras.items():
            h, obj = chave_curta(nome_c), objetivo(d)
            if f"defs_dif_{h}" in ss and (ss[f"defs_dif_{h}"] or "Média") != (obj.get("dificuldade") or "Média"):
                return "Salas e objetivos"
            if f"defs_nota_{h}" in ss and int(ss[f"defs_nota_{h}"] or 14) != int(obj.get("nota_alvo") or 14):
                return "Salas e objetivos"
        p = prefs_plano()
        if ("defs_dias" in ss and set(ss.defs_dias or []) != set(dias_de_estudo_atuais())) or \
                ("defs_ritmo" in ss and (ss.defs_ritmo or p["ritmo"]) != p["ritmo"]) or \
                ("defs_com" in ss and ss.defs_com != p["comecar"]) or \
                ("defs_est" in ss and (ss.defs_est or p["estilo"]) != p["estilo"]) or \
                ("defs_notas" in ss and str(ss.defs_notas or "").strip() != str(perfil.get("notas") or "").strip()):
            return "Como estudas"
    return None


def defs_repor(cat: str) -> None:
    """Deita fora o que está escrito nos formulários da categoria (voltam a mostrar o que está guardado)."""
    ss = st.session_state
    for k in CHAVES_FORM.get(cat, ()):
        ss.pop(k, None)
    if cat == "conta":
        ss.pop(f"defs_foto_{ss.get('_defs_foto_v', 0)}", None)
        ss._defs_foto_v = ss.get("_defs_foto_v", 0) + 1
    if cat == "academico":
        for k in [k for k in ss if str(k).startswith(("defs_dif_", "defs_nota_"))]:
            ss.pop(k, None)


def abrir_categoria(cat: str) -> None:
    """on_click das categorias (e dos resultados da pesquisa): muda de categoria, a não ser que haja alterações por
    guardar na atual — nesse caso fica e pergunta."""
    ss = st.session_state
    atual = ss.get("def_cat") if ss.get("def_cat") in dfs.TITULOS else "conta"
    ss.defs_q = ""
    if cat != atual and defs_por_guardar(atual):
        ss._defs_pedido = cat
        return
    ss.pop("_defs_pedido", None)
    ss.def_cat, ss.def_aberta = cat, True


def fechar_categoria() -> None:
    """No telemóvel: voltar à lista de categorias (também pergunta se houver alterações por guardar)."""
    ss = st.session_state
    atual = ss.get("def_cat") if ss.get("def_cat") in dfs.TITULOS else "conta"
    if defs_por_guardar(atual):
        ss._defs_pedido = "_lista"
        return
    ss.def_aberta = False


def descartar_e_seguir(cat: str) -> None:
    ss = st.session_state
    destino = ss.pop("_defs_pedido", None)
    defs_repor(cat)
    if destino == "_lista":
        ss.def_aberta = False
    elif destino in dfs.TITULOS:
        ss.def_cat, ss.def_aberta = destino, True


def barra_guardar(chave: str, sujo: bool, rotulo: str = "Guardar alterações") -> bool:
    """«Guardar» (ativo só quando há alterações) e «Repor». Devolve True quando se carrega em guardar."""
    with st.container(horizontal=True, key=f"defb_{chave}", gap="small"):
        guardar_ = st.button(rotulo, type="primary", icon=":material/check:", key=f"defs_g_{chave}", disabled=not sujo)
        if sujo:
            st.button("Repor", key=f"defs_r_{chave}", on_click=defs_repor, args=(st.session_state.get("def_cat", "conta"),),
                      help="Volta ao que está guardado.")
            st.caption(":material/edit_note: Alterações por guardar")
    return guardar_ and sujo


# ---------------------------------------------------------------- ações com confirmação
@st.dialog("Apagar a conta")
def dialogo_apagar_conta() -> None:
    st.markdown("Isto apaga **a tua conta e todos os teus dados**: perfil, salas e documentos, avaliações, planos, "
                "conversas e estatísticas. As salas que criaste também são apagadas. **Não pode ser desfeito.**")
    st.caption("Se quiseres ficar com uma cópia, descarrega primeiro os teus dados (Privacidade e segurança).")
    confirmar = st.checkbox("Quero apagar a minha conta e todos os meus dados", key="defs_apagar_ok")
    a, b = st.columns(2)
    if a.button("Cancelar", width="stretch", key="defs_apagar_nao"):
        st.rerun()
    if b.button("Apagar a conta", type="primary", icon=":material/delete_forever:", width="stretch", disabled=not confirmar,
                key="defs_apagar_conta") and confirmar:
        apagar_todos_os_dados()
        st.rerun()


def apagar_conversas() -> int:
    n = len(conversas)
    conversas.clear()
    st.session_state.conversa_id = None
    guardar_perfil()
    return n


@st.dialog("Apagar todas as conversas")
def dialogo_apagar_conversas() -> None:
    n = len(conversas)
    st.markdown(f"Vais apagar **{n} {'conversa' if n == 1 else 'conversas'}** com o assistente (também as fixadas). "
                "As conversas das salas não são apagadas. **Não pode ser desfeito.**")
    a, b = st.columns(2)
    if a.button("Cancelar", width="stretch", key="defs_conv_nao"):
        st.rerun()
    if b.button("Apagar as conversas", type="primary", icon=":material/delete:", width="stretch", key="defs_conv_sim"):
        apagar_conversas()
        _defs_guardado(f"{n} {'conversa apagada' if n == 1 else 'conversas apagadas'}.")
        st.rerun()


@st.dialog("Apagar as estatísticas de tempo")
def dialogo_apagar_estatisticas() -> None:
    st.markdown("Apaga o **tempo na aplicação** e as **sessões do cronómetro** guardados até agora. As notas dos quizzes e "
                "dos testes ficam. **Não pode ser desfeito.**")
    a, b = st.columns(2)
    if a.button("Cancelar", width="stretch", key="defs_est_nao"):
        st.rerun()
    if b.button("Apagar as estatísticas", type="primary", icon=":material/delete:", width="stretch", key="defs_est_sim"):
        perfil["uso"], perfil["foco"] = {}, []
        guardar_perfil()
        _defs_guardado("Estatísticas de tempo apagadas.")
        st.rerun()


def lembradas_desta_conta():
    """(objeto das sessões lembradas, id da conta, código deste browser)."""
    if not hasattr(sessoes_lembradas(), "contar"):  # módulo recarregado com a app aberta: cria o objeto de novo
        st.session_state.pop("_sessoes_lembradas", None)
    return (sessoes_lembradas(), st.session_state.get("salas_sessao", {}).get("uid") or UID,
            st.session_state.get("_token_sessao") or cookie_sessao())


def terminar_outras_sessoes() -> None:
    lembradas, uid_, token = lembradas_desta_conta()
    n = lembradas.apagar_outras(uid_, token)
    _defs_guardado(f"Sessão terminada em {n} {'outro dispositivo' if n == 1 else 'outros dispositivos'}." if n
                   else "Não havia outras sessões iniciadas.")


# ---------------------------------------------------------------- categorias
def defs_conta() -> None:
    import salas_backend as sb

    ss = st.session_state
    ext = utilizador_externo()
    backend, conta = conta_salas_atual()
    nome_atual = perfil.get("nome") or ""
    foto_atual = base64.b64decode(perfil["foto"]) if perfil.get("foto") else None
    with grupo_def("perfil", "Perfil", "O nome e a fotografia aparecem no Início, nas respostas do assistente e nas salas."):
        c1, c2 = st.columns([1, 4.2], vertical_alignment="center")
        if foto_atual:
            c1.image(foto_atual, width=84)
        elif ext and ext.get("foto"):
            c1.image(ext["foto"], width=84)
        else:
            c1.markdown(f"<div class='mi-avatar-g'>{escape((nome_atual or '?')[:1].upper())}</div>", unsafe_allow_html=True)
        nome = c2.text_input("Nome", value=nome_atual, max_chars=80, key="defs_nome", autocomplete="name")
        nova = st.file_uploader("Fotografia (PNG, JPEG ou WebP)", type=["png", "jpg", "jpeg", "webp"],
                                key=f"defs_foto_{ss.get('_defs_foto_v', 0)}")
        remover = bool(foto_atual) and st.checkbox("Remover a fotografia", key="defs_foto_rm")
        if barra_guardar("perfil", defs_por_guardar("conta") == "Perfil"):
            nome = " ".join(nome.split())
            foto_nova, erro_ = None, None
            if len(nome) < 2:
                erro_ = "Escreve o teu nome (pelo menos 2 letras)."
            elif nova is not None:
                try:
                    foto_nova = foto_quadrada(nova.getvalue())
                except Exception:  # noqa: BLE001
                    erro_ = "Não consegui abrir essa imagem. Experimenta outra (PNG ou JPEG)."
            if erro_:
                st.error(erro_, icon=":material/error:")
            else:
                perfil["nome"] = nome
                if foto_nova:
                    perfil["foto"] = base64.b64encode(foto_nova).decode()
                elif remover:
                    perfil.pop("foto", None)
                guardar_perfil()
                aviso_ = ""
                if conta:
                    try:
                        backend.mudar_perfil(nome=nome, foto=foto_nova, apagar_foto=remover and not foto_nova)
                    except sb.ErroSalas as erro:
                        aviso_ = f" (A conta das salas não foi atualizada: {erro})"
                defs_repor("conta")
                _defs_guardado("Perfil guardado." + aviso_)
                st.rerun()
    email = (ext or {}).get("email") or (conta or {}).get("email") or ""
    with grupo_def("entrada", "Email e forma de entrar"):
        valor_def("email", "Email", "Identifica a tua conta. Não pode ser mudado aqui.", email or "—")
        valor_def("forma", "Entras com", "", "Conta Google, Microsoft ou outra" if ext else "Email e palavra-passe",
                  "A sessão é a dessa conta." if ext else "")
    if conta and not ext:
        with grupo_def("pp", "Palavra-passe", "Pelo menos 8 caracteres. Se entras com Google ou Microsoft através da conta "
                                              "online, a palavra-passe muda-se nesse serviço."):
            atual = st.text_input("Palavra-passe atual", type="password", key="defs_pp_atual", autocomplete="current-password")
            c1, c2 = st.columns(2)
            nova_pp = c1.text_input("Palavra-passe nova", type="password", key="defs_pp_nova", autocomplete="new-password")
            conf = c2.text_input("Repetir a palavra-passe nova", type="password", key="defs_pp_conf", autocomplete="new-password")
            if barra_guardar("pp", bool(atual or nova_pp or conf), "Mudar a palavra-passe"):
                problema = "Escreve a palavra-passe atual." if not atual else dfs.validar_palavra_passe(nova_pp, conf, atual)
                if not problema:
                    try:
                        with st.spinner("A mudar a palavra-passe…"):
                            backend.mudar_palavra_passe(atual, nova_pp)
                    except sb.ErroSalas as erro:
                        problema = str(erro)
                    except Exception:  # noqa: BLE001 — sem ligação ao servidor das contas
                        problema = "Não consegui falar com o servidor das contas. Vê a ligação à internet e tenta outra vez."
                if problema:
                    st.error(problema, icon=":material/error:")
                else:
                    defs_repor("conta")
                    _defs_guardado("Palavra-passe mudada.")
                    st.rerun()
    with grupo_def("sessao", "Sessão"):
        with linha_def("sair", "Neste dispositivo", "A sessão fica iniciada neste browser durante 30 dias ou até a terminares."):
            st.button("Terminar sessão", icon=":material/logout:", key="defs_sair", on_click=terminar_sessao)
        if st.session_state.get("_nuvem"):
            valor_def("outras", "Outros dispositivos", "Com a conta online, terminar a sessão aqui termina-a em todos os "
                      "dispositivos.", "")
        else:
            lembradas, uid_, token = lembradas_desta_conta()
            outras = max(0, lembradas.contar(uid_) - (1 if token and lembradas.obter(token) else 0))
            with linha_def("outras", "Outros dispositivos",
                           f"{outras} {'outro browser tem' if outras == 1 else 'outros browsers têm'} a sessão desta conta "
                           "iniciada." if outras else "Não há outras sessões iniciadas com esta conta."):
                st.button("Terminar nos outros", icon=":material/devices:", key="defs_sair_outros", disabled=not outras,
                          on_click=terminar_outras_sessoes)
    with grupo_def("perigo", "Apagar a conta", "Apaga a conta e todos os teus dados, para sempre."):
        with linha_def("apagar", "Apagar a conta e os dados", "Pede confirmação antes de apagar."):
            if st.button("Apagar a conta…", icon=":material/delete_forever:", key="defs_apagar_abrir"):
                dialogo_apagar_conta()


def defs_academico() -> None:
    ss = st.session_state
    with grupo_def("acad", "Curso e instituição", "A IA usa isto para ajustar as explicações ao teu nível."):
        valor_def("acad_resumo", "Perfil académico", "", ac.resumo_perfil(acad) if acad.get("nivel") else "Ainda não preenchido")
        with linha_def("acad_editar", "Mudar o nível, a instituição, o curso ou o ano", "Abre as perguntas do perfil académico."):
            if st.button("Editar", icon=":material/edit:", key="defs_acad_editar"):
                ss.editar_academico = True
                ss.passo = 0
                st.rerun()
    nomes = sorted(ss.cadeiras, key=lambda n_: (data_avaliacao(ss.cadeiras[n_]) or date.max, dz._sem_acentos(n_)))
    with grupo_def("cadeiras", "Salas e objetivos", "A nota que queres tirar e a dificuldade que sentes em cada sala. "
                                                       "Entram nos planos de estudo."):
        if not nomes:
            with linha_def("sem_cad", "Ainda não tens salas só tuas", "Cria a primeira para juntares as fontes e definires objetivos."):
                st.button("Abrir Salas", icon=":material/groups:", key="defs_ir_cadeiras", on_click=navegar, args=("salas",))
        for nome_c in nomes:
            h, obj = chave_curta(nome_c), objetivo(ss.cadeiras[nome_c])
            prox = repo().proxima(nome_c)
            with linha_def(f"cad_{h}", nome_c, f"{prox['nome']} · {fmt_data(prox['data'])} · {av.texto_faltam(prox)}" if prox
                           else "Sem avaliações marcadas"):
                st.segmented_control(f"Dificuldade de {nome_c}", pe.DIFICULDADES, default=obj.get("dificuldade") or "Média",
                                     key=f"defs_dif_{h}", label_visibility="collapsed")
                st.number_input(f"Nota pretendida em {nome_c}", 10, 20, int(obj.get("nota_alvo") or 14), key=f"defs_nota_{h}",
                                label_visibility="collapsed", help="Nota que queres tirar (10 a 20)")
        if nomes and barra_guardar("cadeiras", defs_por_guardar("academico") == "Salas e objetivos", "Guardar objetivos"):
            for nome_c in nomes:
                h = chave_curta(nome_c)
                ss.cadeiras[nome_c]["objetivo"] = {**objetivo(ss.cadeiras[nome_c]),
                                                   "dificuldade": ss.get(f"defs_dif_{h}") or "Média",
                                                   "nota_alvo": int(ss.get(f"defs_nota_{h}") or 14)}
                guardar(nome_c)
            defs_repor("academico")
            _defs_guardado("Objetivos guardados.")
            st.rerun()
    p = prefs_plano()
    with grupo_def("estudo", "Como estudas", "Preferências de aprendizagem: usadas quando a app distribui o plano de estudo."):
        dias = st.pills("Dias em que estudas", pe.DIAS_SEMANA, selection_mode="multi", key="defs_dias",
                        default=dias_de_estudo_atuais())
        ritmo = st.segmented_control("Ritmo", list(pe.RITMOS), default=p["ritmo"], key="defs_ritmo",
                                     help=" · ".join(f"{r}: até {n} tarefas por dia" for r, n in pe.RITMOS.items())) or p["ritmo"]
        comecar = st.radio("Por onde começar", pe.COMECAR, index=pe.COMECAR.index(p["comecar"]), key="defs_com", horizontal=True)
        estilo = st.segmented_control("Estilo", pe.ESTILOS, default=p["estilo"], key="defs_est") or p["estilo"]
        notas = st.text_area("Outras indicações para os planos (opcional)", value=perfil.get("notas", ""), key="defs_notas",
                             height=80, max_chars=400, placeholder="ex.: aprendo melhor com exemplos resolvidos…")
        if barra_guardar("estudo", defs_por_guardar("academico") == "Como estudas"):
            if not dias:
                st.error("Escolhe pelo menos um dia em que estudas.", icon=":material/error:")
            else:
                guardar_prefs_plano(pe.preferencias({"folga": [d for d in pe.DIAS_SEMANA if d not in dias], "ritmo": ritmo,
                                                     "comecar": comecar, "estilo": estilo}))
                perfil["notas"] = notas.strip()
                guardar_perfil()
                defs_repor("academico")
                _defs_guardado("Preferências de estudo guardadas.")
                st.rerun()


def defs_personalizacao() -> None:
    p = prefs_atuais()
    with grupo_def("tema", "Aparência"):
        escolha_def("tema", "Tema", "«Automático» segue o modo claro ou escuro do teu computador ou telemóvel.", idt.TEMAS,
                    cfg.get("tema", "Automático"), mudar_pref_cb, ("tema", "defs_w_tema"),
                    formato={"Automático": ":material/brightness_auto: Automático", "Claro": ":material/light_mode: Claro",
                             "Escuro": ":material/dark_mode: Escuro"}.get)
    with grupo_def("interface", "Interface"):
        with linha_def("pagina", "Página ao abrir a app", "O que vês primeiro depois de entrares."):
            st.selectbox("Página ao abrir a app", dfs.OPCOES["pagina_inicial"], key="defs_w_pagina",
                         index=dfs.OPCOES["pagina_inicial"].index(p["pagina_inicial"]), label_visibility="collapsed",
                         on_change=mudar_pref_cb, args=("pagina_inicial", "defs_w_pagina"))
        interruptor_def("intro", "Animação de entrada", "A animação curta do logótipo ao abrir a app.", p["intro"],
                        mudar_pref_cb, ("intro", "defs_w_intro"))
        interruptor_def("movimento", "Reduzir animações", "Tira as transições e os movimentos da interface (fora dos "
                        "laboratórios).", p["movimento"] == "Reduzido", mudar_pref_cb,
                        ("movimento", "defs_w_movimento", lambda v: "Reduzido" if v else "Normal"))


def defs_notificacoes() -> None:
    a = prefs_atuais()["avisos"]
    off = not a["ativos"]
    with grupo_def("avisos", "Avisos na app", "Aparecem no Início, discretos, e podes dispensar cada um."):
        interruptor_def("av_ativos", "Mostrar avisos", "Desligado: o Início não mostra avisos nenhuns.", a["ativos"],
                        mudar_aviso_cb, ("ativos", "defs_w_av_ativos"))
    with grupo_def("avisos_tipos", "O que avisar"):
        interruptor_def("av_avaliacoes", "Avaliações próximas", "Testes, exames e entregas que estão a chegar.", a["avaliacoes"],
                        mudar_aviso_cb, ("avaliacoes", "defs_w_av_avaliacoes"), off)
        with linha_def("av_dias", "Antecedência", "Com quantos dias de antecedência começa o aviso de uma avaliação."):
            st.selectbox("Antecedência", dfs.DIAS_AVISO, index=dfs.DIAS_AVISO.index(a["dias"]), key="defs_w_av_dias",
                         label_visibility="collapsed", format_func=lambda d: "1 dia" if d == 1 else f"{d} dias",
                         on_change=mudar_aviso_cb, args=("dias", "defs_w_av_dias"), disabled=off or not a["avaliacoes"])
        interruptor_def("av_estudo", "Lembrete de estudo", "As tarefas do plano de hoje que ainda faltam.", a["estudo"],
                        mudar_aviso_cb, ("estudo", "defs_w_av_estudo"), off)
        interruptor_def("av_tarefas", "Tarefas pendentes", "Tarefas do plano que ficaram por fazer em dias que já passaram.",
                        a["tarefas"], mudar_aviso_cb, ("tarefas", "defs_w_av_tarefas"), off)
        interruptor_def("av_cartoes", "Flashcards para rever", "Os cartões que a revisão espaçada marca para hoje.",
                        a["cartoes"], mudar_aviso_cb, ("cartoes", "defs_w_av_cartoes"), off)
        interruptor_def("av_revisao", "Sugestões da IA para rever", "Os temas em que erraste mais no último quiz de cada sala.",
                        a["revisao"], mudar_aviso_cb, ("revisao", "defs_w_av_revisao"), off)
        interruptor_def("av_salas", "Atividade das salas", "Mensagens novas nas tuas salas desde a última vez que as abriste.",
                        a["salas"], mudar_aviso_cb, ("salas", "defs_w_av_salas"), off)
    st.caption(":material/info: Os avisos aparecem dentro da app. Avisos por email ou notificações no telemóvel ainda não "
               "existem nesta versão.")


def defs_ia() -> None:
    p = prefs_atuais()
    with grupo_def("ia_resp", "Respostas", "Vale para o assistente, as conversas das salas e a voz."):
        escolha_def("idioma", "Idioma das respostas", "", ["Português", "English"], cfg.get("idioma", "Português"),
                    mudar_pref_cb, ("idioma", "defs_w_idioma"))
        escolha_def("ia_tamanho", "Tamanho das respostas", "Curtas vão ao essencial; detalhadas explicam passo a passo.",
                    dfs.OPCOES["ia_tamanho"], p["ia_tamanho"], mudar_pref_cb, ("ia_tamanho", "defs_w_ia_tamanho"))
        escolha_def("ia_nivel", "Nível das explicações", "Simples: como a quem vê o tema pela primeira vez. Avançado: com rigor "
                    "técnico.", dfs.OPCOES["ia_nivel"], p["ia_nivel"], mudar_pref_cb, ("ia_nivel", "defs_w_ia_nivel"))
        escolha_def("ia_tom", "Tom", "Próximo e encorajador, ou neutro e objetivo.", dfs.OPCOES["ia_tom"], p["ia_tom"],
                    mudar_pref_cb, ("ia_tom", "defs_w_ia_tom"))
        nomes_vel = list(VELOCIDADES)
        with linha_def("velocidade", "Velocidade", VELOCIDADES[cfg.get("velocidade", "Rápida")]["descricao"] + "."):
            st.selectbox("Velocidade das respostas", nomes_vel, index=nomes_vel.index(cfg.get("velocidade", "Rápida")),
                         key="defs_w_velocidade", label_visibility="collapsed", on_change=mudar_pref_cb,
                         args=("velocidade", "defs_w_velocidade"))
        interruptor_def("web", "Pesquisar na web", "A IA pesquisa na web antes de responder e mostra os sites no fim.",
                        cfg.get("web", True), mudar_pref_cb, ("web", "defs_w_web"))
    with grupo_def("ia_voz", "Voz", "O assistente por voz do Início."):
        interruptor_def("voz_alta", "Responder em voz alta", "Desligado: a resposta aparece só escrita.", p["voz_alta"],
                        mudar_pref_cb, ("voz_alta", "defs_w_voz_alta"))
        interruptor_def("voz_continua", "Conversa contínua", "Depois de responder, volta a ouvir sem teres de carregar na esfera.",
                        p["voz_continua"], mudar_pref_cb, ("voz_continua", "defs_w_voz_continua"))
        escolha_def("voz_velocidade", "Velocidade da voz", "A que velocidade a resposta é lida.", dfs.OPCOES["voz_velocidade"],
                    p["voz_velocidade"], mudar_pref_cb, ("voz_velocidade", "defs_w_voz_velocidade"))
    n = len(conversas)
    with grupo_def("ia_hist", "Histórico"):
        with linha_def("conversas", "Conversas com o assistente",
                       f"{n} {'conversa guardada' if n == 1 else 'conversas guardadas'} na tua conta." if n
                       else "Ainda não tens conversas guardadas."):
            if st.button("Apagar todas…", icon=":material/delete:", key="defs_conv_apagar", disabled=not n):
                dialogo_apagar_conversas()
    st.caption(":material/info: As perguntas e os excertos dos teus documentos são enviados à IA só para gerar as respostas. "
               "No plano gratuito do Gemini, a Google pode usar os pedidos para melhorar os seus modelos: não carregues "
               "documentos confidenciais.")
    if e_admin():
        with grupo_def("ia_admin", "Administração", "Só tu vês isto."):
            with linha_def("admin", "Chave, modelo e serviços da IA", "Ficam no Perfil → Administração da app."):
                st.button("Abrir a administração", icon=":material/admin_panel_settings:", key="defs_ir_admin",
                          on_click=navegar, args=("perfil",))


def defs_privacidade() -> None:
    ss = st.session_state
    with grupo_def("dados", "Os teus dados",
                   "Ficam guardados na tua conta, online (estão em todos os teus dispositivos), e só tu os vês."
                   if ss.get("_nuvem") else
                   "Ficam guardados na tua conta, no computador onde a app está instalada, e só tu os vês."):
        with linha_def("exportar", "Descarregar os meus dados", "Um ficheiro .zip com o perfil, as salas, os documentos e as "
                       "avaliações. As chaves da IA não vão."):
            if ss.get("_exportar"):
                st.download_button("Descarregar o .zip", ss._exportar, file_name="mondego_ia_dados.zip", mime="application/zip",
                                   icon=":material/download:", key="defs_zip")
            else:
                st.button("Preparar o .zip", icon=":material/folder_zip:", key="defs_zip_preparar",
                          on_click=lambda: st.session_state.update(_exportar=exportar_dados()))
        importar_ui()
        with linha_def("repetir", "Repetir as perguntas iniciais", "Volta a mostrar as perguntas do primeiro dia (nome, perfil "
                       "académico, salas). Os teus dados ficam."):
            if st.button("Repetir", icon=":material/restart_alt:", key="defs_repetir"):
                perfil["concluido"] = False
                ss.passo = 0
                guardar_perfil()
                st.rerun()
    tem_est = bool(perfil.get("uso") or perfil.get("foco"))
    with grupo_def("estat", "Estatísticas de utilização"):
        with linha_def("guardar_est", "Guardar o tempo na app e de estudo", "Serve para as estatísticas do teu Perfil. Desligado: "
                       "a app deixa de contar o tempo."):
            guardar_est = st.toggle("Guardar o tempo na app e de estudo", value=perfil.get("guardar_estatisticas", True),
                                    key="defs_w_guardar_est", label_visibility="collapsed")
            if guardar_est != perfil.get("guardar_estatisticas", True):
                perfil["guardar_estatisticas"] = guardar_est
                guardar_perfil()
                _defs_guardado()
                st.rerun()
        with linha_def("apagar_est", "Apagar as estatísticas de tempo", "Tempo na aplicação e sessões do cronómetro."
                       if tem_est else "Ainda não há estatísticas guardadas."):
            if st.button("Apagar…", icon=":material/delete:", key="defs_est_apagar", disabled=not tem_est):
                dialogo_apagar_estatisticas()
    n = len(conversas)
    with grupo_def("conv", "Conversas, voz e microfone"):
        with linha_def("conv_n", "Conversas com o assistente", f"{n} {'conversa guardada' if n == 1 else 'conversas guardadas'} "
                       "na tua conta; só tu as vês." if n else "Ainda não tens conversas guardadas."):
            if st.button("Apagar todas…", icon=":material/delete:", key="defs_conv_apagar2", disabled=not n):
                dialogo_apagar_conversas()
        with linha_def("voz_dados", "Áudio e transcrições da voz", "A app não guarda o áudio. O reconhecimento de voz é feito "
                       "pelo serviço de voz do teu browser; a conversa por voz fica só nesta sessão."):
            if st.button("Limpar a conversa por voz", icon=":material/delete_sweep:", key="defs_voz_limpar",
                         disabled=not ss.get("voz_hist")):
                ss.voz_hist = []
                ss.pop("voz_resp", None)
                _defs_guardado("Conversa por voz limpa.")
                st.rerun()
        valor_def("micro", "Permissão do microfone", "O browser pede autorização quando carregas na esfera. Para a retirar, usa "
                  "o cadeado na barra de endereço do browser.", "Gerida pelo browser")
    with grupo_def("seg", "Segurança da conta"):
        with linha_def("seg_sessoes", "Palavra-passe e sessões", "Mudar a palavra-passe e terminar a sessão noutros dispositivos."):
            st.button("Abrir Conta e perfil", icon=":material/account_circle:", key="defs_ir_conta", on_click=abrir_categoria,
                      args=("conta",))
        with linha_def("seg_apagar", "Apagar a conta e os dados", "Para sempre. Pede confirmação antes de apagar."):
            if st.button("Apagar a conta…", icon=":material/delete_forever:", key="defs_apagar_abrir2"):
                dialogo_apagar_conta()


def defs_acessibilidade() -> None:
    p = prefs_atuais()
    with grupo_def("ler", "Ver e ler"):
        escolha_def("texto", "Tamanho do texto", "Aumenta as letras de toda a app.", dfs.OPCOES["texto"], p["texto"],
                    mudar_pref_cb, ("texto", "defs_w_texto"))
        interruptor_def("contraste", "Contraste alto", "Texto e contornos mais marcados; as ligações ficam sublinhadas.",
                        p["contraste"], mudar_pref_cb, ("contraste", "defs_w_contraste"))
        interruptor_def("leitura", "Leitura confortável", "Mais espaço entre linhas e parágrafos e linhas mais curtas nas "
                        "respostas.", p["leitura"], mudar_pref_cb, ("leitura", "defs_w_leitura"))
    with grupo_def("mov", "Movimento e teclado"):
        interruptor_def("movimento2", "Menos movimento", "Tira as animações e as transições da interface.",
                        p["movimento"] == "Reduzido", mudar_pref_cb,
                        ("movimento", "defs_w_movimento2", lambda v: "Reduzido" if v else "Normal"))
        interruptor_def("foco", "Realçar o foco do teclado", "Um contorno bem visível à volta do controlo que está selecionado.",
                        p["foco"], mudar_pref_cb, ("foco", "defs_w_foco"))
        valor_def("teclas", "Navegar com o teclado", "Tab e Shift+Tab percorrem os controlos; Enter ou Espaço ativam; Esc fecha "
                  "janelas e menus. No assistente, Enter envia e Shift+Enter muda de linha.", "")
    st.caption(":material/info: Estas opções aplicam-se a toda a app, menos aos laboratórios das salas, que mantêm o seu "
               "aspeto.")
    if any(k in dfs.alteradas(p) for k in ("texto", "contraste", "leitura", "foco", "movimento")):
        def repor_acess():
            for k in ("texto", "contraste", "leitura", "foco", "movimento"):
                st.session_state.cfg[k] = dfs.PADRAO[k]
                st.session_state.pop(f"defs_w_{k}", None)
            st.session_state.pop("defs_w_movimento2", None)
            guardar_config()
            _defs_guardado("Acessibilidade reposta.")
        st.button("Repor a acessibilidade", icon=":material/restart_alt:", key="defs_acess_repor", on_click=repor_acess)


def versao_da_app() -> str:
    try:
        ultima = max(f.stat().st_mtime for f in PASTA.glob("*.py"))
        return f"Atualizada em {datetime.fromtimestamp(ultima):%d/%m/%Y}"
    except (OSError, ValueError):
        return "—"


def relatorio_de_problema(texto: str) -> str:
    try:
        navegador = st.context.headers.get("User-Agent", "")
    except Exception:  # noqa: BLE001
        navegador = ""
    return ("Mondego IA — relatório de problema\n"
            f"Data: {datetime.now():%d/%m/%Y %H:%M}\nVersão: {versao_da_app()} · Streamlit {getattr(st, '__version__', '')}\n"
            f"Browser: {navegador}\nTema: {cfg.get('tema')} · Conta online: {'sim' if st.session_state.get('_nuvem') else 'não'}\n\n"
            f"O que aconteceu:\n{texto.strip()}\n")


def defs_ajuda() -> None:
    from urllib.parse import quote

    with grupo_def("faq", "Perguntas frequentes"):
        for i, (pergunta, resposta) in enumerate(dfs.PERGUNTAS):
            with st.expander(pergunta):
                st.markdown(resposta)
    suporte = str(cfg.get("email_suporte") or "").strip()
    with grupo_def("contacto", "Contacto e problemas"):
        if suporte:
            with linha_def("contacto", "Falar com o suporte", f"Escreve para {suporte}."):
                st.link_button("Enviar email", f"mailto:{suporte}?subject={quote('Mondego IA — pedido de ajuda')}",
                               icon=":material/mail:")
        else:
            valor_def("contacto", "Falar com o suporte", "Esta instalação ainda não indicou um email de suporte: fala com quem "
                      "gere a app (a tua escola ou quem a instalou).", "")
        texto = st.text_area("Reportar um problema", key="defs_problema", height=110, max_chars=2000,
                             placeholder="O que estavas a fazer, o que esperavas e o que aconteceu…")
        relatorio = relatorio_de_problema(texto) if texto.strip() else ""
        with st.container(horizontal=True, key="defb_problema", gap="small"):
            st.download_button("Descarregar o relatório (.txt)", relatorio or " ", file_name="mondego_ia_problema.txt",
                               mime="text/plain", icon=":material/download:", key="defs_problema_txt", disabled=not relatorio)
            if suporte:
                st.link_button("Enviar por email", f"mailto:{suporte}?subject={quote('Mondego IA — problema')}"
                               f"&body={quote(relatorio[:1500])}", icon=":material/send:", disabled=not relatorio)
        st.caption("O relatório junta a versão da app e o browser, para ajudar a encontrar o problema. Não leva dados teus "
                   "nem documentos.")
        if e_admin():
            novo = st.text_input("Email de suporte desta instalação (só tu vês este campo)", value=suporte, key="defs_suporte",
                                 placeholder="ex.: apoio@a-tua-escola.pt…", autocomplete="off")
            if novo.strip() != suporte and st.button("Guardar o email de suporte", key="defs_suporte_g", type="primary"):
                if novo.strip() and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", novo.strip()):
                    st.error("Escreve um email válido.", icon=":material/error:")
                else:
                    cfg["email_suporte"] = novo.strip()
                    guardar_config()
                    _defs_guardado("Email de suporte guardado.")
                    st.rerun()
    with grupo_def("sobre", "Privacidade e versão"):
        valor_def("priv", "Privacidade", "Os teus dados ficam na tua conta e só tu os vês. As perguntas e os excertos dos "
                  "documentos são enviados à IA apenas para gerar as respostas. Podes descarregar ou apagar tudo em "
                  "Privacidade e segurança.", "")
        valor_def("versao", "Versão da aplicação", "Mondego IA", versao_da_app(), f"Streamlit {getattr(st, '__version__', '')}")


PAGINAS_DEFS = {"conta": defs_conta, "academico": defs_academico, "personalizacao": defs_personalizacao,
                "notificacoes": defs_notificacoes, "ia": defs_ia, "privacidade": defs_privacidade,
                "acessibilidade": defs_acessibilidade, "ajuda": defs_ajuda}


def pagina_definicoes() -> None:
    ss = st.session_state
    st.markdown(ESTILO_DEFS, unsafe_allow_html=True)
    cat = ss.get("def_cat") if ss.get("def_cat") in dfs.TITULOS else "conta"
    if ss.get("_defs_toast"):
        st.toast(ss.pop("_defs_toast"), icon=":material/check_circle:")
    cabecalho("Definições", "A tua conta, a aparência, os avisos e a forma como a IA te responde.")
    with st.container(key="defs_estado_a" if ss.get("def_aberta") else "defs_estado_l"):
        esq, dir_ = st.columns([1, 2.9], gap="large")
        with esq.container(key="defs_nav"):
            consulta = st.text_input("Procurar nas definições", key="defs_q", placeholder="Procurar nas definições…",
                                     label_visibility="collapsed", icon=":material/search:", autocomplete="off")
            if consulta.strip():
                achados = dfs.procurar(consulta)
                st.markdown(f"<div class='df-nav-t'>{len(achados)} {'resultado' if len(achados) == 1 else 'resultados'}</div>",
                            unsafe_allow_html=True)
                for i, (c, titulo) in enumerate(achados[:12]):
                    st.button(titulo, key=f"defs_res_{i}", type="tertiary", icon=f":material/{dict((x[0], x[2]) for x in dfs.CATEGORIAS)[c]}:",
                              help=dfs.TITULOS[c], on_click=abrir_categoria, args=(c,))
                if not achados:
                    st.caption("Nada encontrado. Experimenta outra palavra, por exemplo «tema», «palavra-passe» ou «avisos».")
            else:
                for c, titulo, icone, _desc in dfs.CATEGORIAS:
                    # sem dica ao passar o rato: tapava a categoria de cima (a descrição está no topo da categoria)
                    st.button(titulo, key=f"defcat_{c}", icon=f":material/{icone}:",
                              type="secondary" if c == cat else "tertiary", on_click=abrir_categoria, args=(c,))
        with dir_.container(key=f"defs_c_{cat}"):
            with st.container(key="defs_voltar"):
                st.button("Definições", icon=":material/arrow_back:", key="defs_voltar_b", type="tertiary", on_click=fechar_categoria)
            por_guardar = defs_por_guardar(cat)
            if por_guardar:
                estado = "<span class='df-estado por'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>edit_note</span>Alterações por guardar</span>"
            elif ss.get("_defs_guardado"):
                estado = (f"<span class='df-estado ok'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>check</span>"
                          f"Guardado às {ss._defs_guardado}</span>")
            else:
                estado = ""
            titulo, descricao = dfs.TITULOS[cat], next(x[3] for x in dfs.CATEGORIAS if x[0] == cat)
            st.markdown(f"<div class='df-cab'><div><h2>{escape(titulo)}</h2><p>{escape(descricao)}.</p></div>{estado}</div>",
                        unsafe_allow_html=True)
            pedido = ss.get("_defs_pedido")
            if pedido and por_guardar:
                with st.container(border=True, key="defs_aviso_sair"):
                    st.markdown(f":material/warning: **Tens alterações por guardar em «{por_guardar}».** Guarda-as primeiro, "
                                "ou descarta-as para continuar.")
                    with st.container(horizontal=True, key="defb_sair", gap="small"):
                        st.button("Continuar a editar", key="defs_ficar", type="primary",
                                  on_click=lambda: st.session_state.pop("_defs_pedido", None))
                        st.button("Descartar e sair", key="defs_descartar", on_click=descartar_e_seguir, args=(cat,))
            elif pedido:
                ss.pop("_defs_pedido", None)
            PAGINAS_DEFS[cat]()
    # sair da página (ou fechar o separador) com alterações por guardar: a app avisa
    por_guardar = defs_por_guardar(cat)
    ss._defs_sujo = f"{dfs.TITULOS[cat]} → {por_guardar}" if por_guardar else None
    st.query_params.update({"p": "definicoes", "c": cat})  # se a página recarregar (ex.: mudar o tema), volta aqui
    try:
        components.html("<script>try{window.parent.onbeforeunload=" + ("function(e){e.preventDefault();e.returnValue='';return '';}"
                        if por_guardar else "null") + ";}catch(e){}</script>", height=0)
    except Exception:  # noqa: BLE001
        pass


if vista == "definicoes":
    st.markdown(ESTILO_INICIO, unsafe_allow_html=True)
    pagina_definicoes()
    st.stop()

# =============================================================== listas de cartões (Salas, Cadeiras) e conversa das salas
# Desenho comum às páginas com listas, ao estilo dos «Projects» do Claude: título grande com as ações à direita, uma
# barra de pesquisa e cartões limpos (borda fina, sombra só ao passar o rato). O cartão inteiro abre a sala/cadeira:
# um botão transparente cobre o cartão (se o CSS não se aplicar, aparece um botão «Abrir» normal e tudo funciona).
ESTILO_LISTAS = """<style>
/* ---- sala aberta: cabeçalho, separadores e conversa ---- */
.sr-topo { display:flex; align-items:center; gap:0.85rem; min-width:0; }
.sr-ico { width:52px; height:52px; border-radius:15px; flex:none; display:grid; place-items:center; font-weight:700;
  font-size:1.35rem; }
.sr-nome { font-size:1.65rem !important; font-weight:650 !important; letter-spacing:-0.025em; margin:0 !important;
  padding:0 !important; color:var(--texto); line-height:1.2 !important; overflow-wrap:anywhere; }
.sr-desc { color:var(--suave); font-size:0.93rem; margin-top:0.1rem; }
.sr-meta { display:flex; align-items:center; flex-wrap:wrap; gap:0.4rem 0.7rem; margin:0.7rem 0 0.2rem; color:var(--suave);
  font-size:0.84rem; }
.sr-pilha { display:inline-flex; }
.sr-pilha .sl-avatar { width:26px; height:26px; flex-basis:26px; font-size:0.72rem; border:2px solid var(--fundo);
  margin-left:-7px; }
.sr-pilha .sl-avatar:first-child { margin-left:0; }
div[class*="st-key-voltar_salas"] button { color:var(--suave) !important; padding-left:0.2rem !important; }
div[class*="st-key-sala_secao_"] [data-testid="stButtonGroup"] { gap:0.2rem; border-bottom:1px solid var(--linha);
  width:100%; padding-bottom:0; flex-wrap:nowrap; overflow-x:auto; }
div[class*="st-key-sala_secao_"] [data-testid="stButtonGroup"] button { background:transparent !important; border:none !important;
  border-bottom:2px solid transparent !important; border-radius:0 !important; padding:0.45rem 0.75rem !important;
  box-shadow:none !important; }
div[class*="st-key-sala_secao_"] [data-testid="stButtonGroup"] button * { color:var(--suave) !important; }
div[class*="st-key-sala_secao_"] [data-testid="stButtonGroup"] button[kind*="Active"] { border-bottom-color:var(--acento) !important; }
div[class*="st-key-sala_secao_"] [data-testid="stButtonGroup"] button[kind*="Active"] * { color:var(--texto) !important;
  font-weight:600; }
.cv-lista { display:flex; flex-direction:column-reverse; overflow-y:auto; max-height:min(58vh, 540px); min-height:240px;
  padding:0.4rem 0.3rem 0.6rem; scroll-behavior:smooth; }
.cv-dia { display:flex; align-items:center; gap:0.7rem; color:var(--suave); font-size:0.75rem; font-weight:600;
  letter-spacing:0.03em; margin:1rem 0 0.6rem; }
.cv-dia::before, .cv-dia::after { content:""; flex:1; height:1px; background:var(--linha); }
.cv-msg { display:flex; gap:0.6rem; align-items:flex-end; margin-top:0.75rem; }
.cv-msg.seguida { margin-top:0.18rem; }
.cv-msg.seguida .sl-avatar { visibility:hidden; height:0; }
.cv-msg .sl-avatar { width:30px; height:30px; flex-basis:30px; font-size:0.8rem; }
.cv-corpo { display:flex; flex-direction:column; max-width:min(78%, 560px); min-width:0; }
.cv-cab { display:flex; align-items:baseline; gap:0.45rem; font-size:0.78rem; color:var(--suave); margin:0 0 0.2rem 0.35rem; }
.cv-cab b { color:var(--texto); font-weight:600; font-size:0.82rem; }
.cv-bolha { background:var(--cartao); border:1px solid var(--linha); color:var(--texto); border-radius:16px 16px 16px 5px;
  padding:0.5rem 0.8rem; font-size:0.94rem; line-height:1.5; overflow-wrap:anywhere; white-space:pre-wrap; }
.cv-msg.seguida .cv-bolha { border-radius:5px 16px 16px 5px; }
.cv-msg.meu { flex-direction:row-reverse; }
.cv-msg.meu .cv-corpo { align-items:flex-end; }
.cv-msg.meu .cv-cab { margin:0 0.35rem 0.2rem 0; }
.cv-msg.meu .cv-bolha { background:var(--acento-claro); border-color:transparent; border-radius:16px 16px 5px 16px; }
.cv-msg.meu.seguida .cv-bolha { border-radius:16px 5px 5px 16px; }
.cv-msg.meu .sl-avatar { display:none; }
.cv-vazio { margin:auto; text-align:center; color:var(--suave); padding:2.5rem 1rem; }
.cv-vazio .material-symbols-rounded { font-size:34px; color:var(--acento); }
.cv-vazio b { display:block; color:var(--texto); margin:0.4rem 0 0.2rem; }
.sa-ola { text-align:center; padding:2.2rem 1rem 0.6rem; }
.sa-ola svg { height:58px; width:auto; }
.sa-ola b { display:block; font-size:1.35rem; font-weight:650; letter-spacing:-0.02em; color:var(--texto); margin:0.6rem 0 0.3rem; }
.sa-ola p { color:var(--suave) !important; margin:0 !important; }
div[class*="st-key-sa_ideias_"] [data-testid="stButtonGroup"] { justify-content:center; }
div[class*="st-key-sa_ideias_"] [data-testid="stButtonGroup"] button { border-radius:999px !important; }
@media (max-width: 640px) {
  .pg-cab h1 { font-size:1.5rem !important; } .sr-nome { font-size:1.35rem !important; } .sr-ico { width:42px; height:42px; }
  div[class*="st-key-pg_acoes"] { justify-content:flex-start; }
  .cv-corpo { max-width:86%; }
  div.stVerticalBlock[class*="st-key-card_"] { min-height:0; }
}
</style>"""


def estilos(*blocos: str) -> str:
    """Junta vários blocos <style>…</style> num só st.markdown. Cada bloco começa numa linha nova: em Markdown, um
    «</style><style>» na mesma linha fecha o bloco de HTML e o CSS que vem a seguir aparecia como texto na página."""
    return "\n".join(b.strip() for b in blocos) + "\n"


def cabecalho_pagina(titulo: str, subtitulo: str):
    """Título grande à esquerda e um contentor à direita para as ações (devolve-o)."""
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    c1.markdown(f"<div class='pg-cab'><h1>{escape(titulo)}</h1><p>{escape(subtitulo)}</p></div>", unsafe_allow_html=True)
    return c2.container(horizontal=True, key="pg_acoes", gap="small")


def cartao_clicavel(chave: str, rotulo_botao: str, chave_botao: str, html: str, ao_clicar, args=(), kwargs=None):
    """Um cartão inteiro que se abre com um clique (o botão cobre o cartão). Devolve o contentor do cartão."""
    cartao = st.container(border=True, key=f"card_{chave}")
    with cartao:
        st.markdown(html, unsafe_allow_html=True)
        with st.container(key=f"sobre_{chave}"):
            st.button(rotulo_botao, key=chave_botao, type="tertiary", on_click=ao_clicar, args=args, kwargs=kwargs or {})
    return cartao


# =============================================================== LABORATÓRIO


def latex_quimica(texto: str) -> str:
    """2H2 + O2 → 2H2O  →  $\\mathrm{2H_{2} + O_{2} \\rightarrow 2H_{2}O}$ (índices como no papel)."""
    t = re.sub(r"([A-Za-z\)\]])(\d+)", r"\1_{\2}", texto).replace("→", r"\rightarrow").replace("·", r"\cdot ")
    return f"$\\mathrm{{{t}}}$"


# --------------------------------------------------------------- IA de cada área (explica tudo; modelo só a pedido)
CORES_LAB = {"fisica": "#2E6DB4", "quimica": "#7D4FA8", "matematica": "#D2603A", "biologia": "#3E8E5A",
             "historia": "#B7841A", "programacao": "#2A93A6"}
IA_LAB = {
    "fisica": {"papel": "professor de Física (mecânica, eletromagnetismo, termodinâmica, ondas, ótica e física moderna)",
               "exemplos": ["Explica o lançamento de um projétil", "O que é a indução eletromagnética?",
                            "Porque é que o céu é azul?"],
               "modelos": "Em Física quase sempre «simulacao» (movimentos, forças, energia, ondas, circuitos, ótica, "
                          "campos); «diagrama» só para relações entre conceitos."},
    "quimica": {"papel": "professor de Química (geral, orgânica, físico-química, bioquímica e química analítica)",
                "exemplos": ["Explica o equilíbrio químico e o princípio de Le Chatelier", "O que é uma ligação covalente?",
                             "Como funciona uma titulação ácido-base?"],
                "modelos": "Em Química: «simulacao» para partículas, velocidade de reação, equilíbrio, gases, titulações, "
                           "orbitais em 2D; «diagrama» para mecanismos, classificações e etapas."},
    "matematica": {"papel": "professor de Matemática (cálculo, álgebra linear, geometria, probabilidades, estatística, "
                            "equações diferenciais e matemática discreta)",
                   "exemplos": ["Explica o que é a derivada", "Como se calcula um determinante 3×3?",
                                "Resolve ∫ x·eˣ dx passo a passo"],
                   "modelos": "Em Matemática: «simulacao» para gráficos com parâmetros (sliders), construções geométricas, "
                              "probabilidades, limites, séries, transformações lineares; «diagrama» para demonstrações "
                              "por passos ou classificações."},
    "biologia": {"papel": "professor de Biologia e Anatomia (célula, genética, fisiologia, anatomia humana, ecologia e "
                          "evolução)",
                 "exemplos": ["Explica a mitose e a meiose", "Como funciona a sinapse?", "O que é a fotossíntese?"],
                 "modelos": "Em Biologia: «diagrama» para estruturas, ciclos, vias metabólicas e classificações; "
                            "«simulacao» para processos animados (osmose, populações, potencial de ação, enzimas)."},
    "historia": {"papel": "professor de História e Geografia (história de Portugal e mundial, geografia física e humana)",
                 "exemplos": ["Explica as causas da Revolução Francesa", "Como foi o 25 de Abril?",
                              "Porque é que existem estações do ano?"],
                 "modelos": "Em História e Geografia: «linha_tempo» para sequências de acontecimentos, «mapa» para "
                            "lugares, percursos e conflitos, «diagrama» para causas e consequências; «simulacao» só para "
                            "fenómenos físicos (estações do ano, placas tectónicas, clima).",
                 "web": True},
    "programacao": {"papel": "professor de Programação e Algoritmos (Python, C, Java, estruturas de dados, complexidade, "
                             "bases de dados e programação orientada a objetos)",
                    "exemplos": ["Explica a recursividade com um exemplo", "Como funciona o quicksort?",
                                 "O que é a complexidade O(n log n)?"],
                    "modelos": "Em Programação: «simulacao» para algoritmos passo a passo (ordenação, pesquisa, recursão, "
                               "pilhas, filas, árvores, grafos); «diagrama» para fluxogramas e classes."},
}
PEDE_MODELO = re.compile(
    r"\b(faz|faça|fazer|faz-me|cria|criar|cria-me|gera|gerar|mostra|mostrar|mostra-me|desenha|desenhar|desenha-me|"
    r"quero|queria|constr[oó]i|construir|podes fazer|preciso de)\b[^.?!\n]{0,40}?\b(modelo|simula\w*|anima\w*|"
    r"diagrama|esquema|mapa|linha do tempo|cronologia|gr[aá]fico|visualiza\w*|interativ\w*)"
    r"|\bcom (um |uma )?(modelo|simula\w*|anima\w*|diagrama|esquema|mapa|linha do tempo|gr[aá]fico)\b", re.I)


def quer_modelo(texto: str) -> bool:
    """O aluno pediu um modelo na própria pergunta (ex.: «explica e faz uma simulação», «mostra num mapa»)."""
    return bool(PEDE_MODELO.search(texto or ""))


def nome_area(area: str) -> str:
    return AREAS_LAB[area][1]


def sistema_lab(area: str, com_modelo: bool) -> str:
    info = IA_LAB[area]
    texto = (f"És a IA de {nome_area(area)} do Laboratório do Mondego IA: um {info['papel']} paciente e rigoroso, para "
             "estudantes do ensino superior e do secundário. Explicas COMPLETAMENTE o que o aluno pedir, em português de "
             "Portugal. Estrutura (adapta ao pedido: uma pergunta simples tem uma resposta mais curta): começa pela ideia "
             "principal em uma ou duas frases; depois explica passo a passo, com o raciocínio e a intuição; mostra as "
             "fórmulas, leis, datas ou conceitos-chave; dá um exemplo concreto (se for um exercício, resolve-o passo a "
             "passo, com unidades, e verifica o resultado); aponta os erros e confusões mais comuns; termina com "
             "«Em resumo» (3 a 5 pontos curtos). Usa títulos curtos (###), listas e **negrito** só no essencial. "
             "Não inventes: se não tiveres a certeza de um facto, di-lo. ")
    if area == "programacao":
        texto += "Mostra código em blocos ```linguagem, curto e comentado. "
    texto += mt.REGRAS_FORMULAS + "\n" + info_aluno()
    if com_modelo:
        texto += ("\nA seguir à tua resposta vai ser criado automaticamente um modelo visual simples (é outra ferramenta "
                  "que o faz). Se o aluno só pediu o modelo de algo que já explicaste, responde em 2 a 4 frases sobre o "
                  "que deve observar nele. Não escrevas o código do modelo nem o descrevas em pormenor.")
    else:
        texto += "\nNão ofereças nem descrevas modelos, simulações ou diagramas: o aluno pede-os quando quiser."
    return texto


def ano_evento(e: dict) -> float:
    try:
        return float(e.get("ano"))
    except (TypeError, ValueError):
        return 0.0


def extrair_html(texto: str) -> str:
    """O HTML do modelo (dentro de ```html ... ```, mesmo que a resposta tenha sido cortada)."""
    m = re.search(r"```(?:html)?\s*(.*?)(?:```|$)", texto or "", re.S | re.I)
    codigo = (m.group(1) if m else (texto or "")).strip()
    if not re.search(r"<(script|canvas|svg)\b", codigo, re.I):
        raise ValueError("A resposta não trouxe um modelo em HTML.")
    return codigo[:160_000]


REGRAS_SIMULACAO = (
    "Regras:\n"
    "- Um único documento HTML com CSS e JavaScript puro lá dentro. Sem bibliotecas, sem ficheiros nem imagens externas, "
    "sem pedidos à internet.\n"
    "- Todo o texto em português de Portugal (rótulos, botões, legendas; vírgula decimal e unidades SI). Sem LaTeX nem "
    "$...$: escreve símbolos com caracteres normais (v₀, θ, Δt, m/s², λ, ½).\n"
    "- Desenha em <canvas> (ou SVG). Anima com requestAnimationFrame quando houver movimento ou um processo.\n"
    "- 1 a 4 controlos claros que mudam o modelo logo: sliders <input type=range> com o valor e a unidade ao lado, e "
    "botões como Iniciar/Pausar, Repor ou Passo seguinte.\n"
    "- Mostra os valores importantes calculados (com unidades) e uma legenda curta das cores. Ciência e contas corretas.\n"
    "- Visual limpo e bonito: fundo transparente; usa as variáveis CSS já definidas var(--texto), var(--suave), "
    "var(--cartao), var(--linha), var(--bolha) e as cores var(--acento), var(--acento2), var(--acento3), var(--acento4) "
    "(no canvas lê-as com getComputedStyle(document.documentElement)); não as redefinas nem inventes outras cores de "
    "fundo; cantos arredondados; espaço à volta; letra herdada; nada de min-height:100vh.\n"
    "- Ocupa 100% da largura (redesenha quando a largura muda; usa devicePixelRatio para ficar nítido). Altura total "
    "entre 320 e 560 px.\n"
    "- Proibido: alert, prompt, confirm, localStorage, cookies, fetch, XMLHttpRequest, WebSocket, eval, formulários e links.\n"
    "- Código robusto, sem erros na consola; começa a funcionar sozinho assim que abre.\n"
    "Responde só com o HTML completo dentro de ```html ... ```.")
SISTEMA_SIMULACAO = ("És um programador de visualizações educativas interativas: rigoroso na ciência, cuidadoso no código e "
                     "com bom gosto visual.")


def codigo_simulacao(area: str, ideia: str, titulo: str, pergunta: str) -> str:
    pedido = (f"Escreve um modelo interativo SIMPLES para um estudante de {nome_area(area)} perceber: {ideia}\n"
              f"Título (aparece por cima do modelo; não o repitas lá dentro): {titulo}\n"
              f"Pergunta original do aluno: {pergunta}\n\n" + REGRAS_SIMULACAO)
    return extrair_html(chamar_ia([{"role": "user", "content": pedido}], sistema=SISTEMA_SIMULACAO, pensar=True))


def gerar_modelo_lab(area: str, pergunta: str, explicacao: str, pedido: str = "", atual: dict | None = None) -> dict:
    """1) a IA escolhe o modelo que mais ajuda (simulação, diagrama, linha do tempo ou mapa) e prepara os dados;
    2) numa simulação, escreve-a. Com «atual», refaz esse modelo com a alteração pedida."""
    contexto = ""
    if atual:
        resumo_atual = {k: v for k, v in atual.items() if k not in ("html", "erro", "criado", "v")}
        contexto = (f"Modelo atual (o aluno quer alterá-lo): {json.dumps(resumo_atual, ensure_ascii=False)[:4000]}\n"
                    f"Alteração pedida: «{pedido}»\n\n")
    elif pedido:
        contexto = f"O aluno pediu: «{pedido}»\n\n"
    instrucoes = (
        f"Área: {nome_area(area)}. O aluno perguntou: «{pergunta}»\n\nExplicação que recebeu (resumo):\n"
        f"{explicacao[:3500]}\n\n{contexto}"
        "Escolhe o modelo visual SIMPLES que mais ajuda a perceber isto e responde só com JSON:\n"
        '{"tipo": "simulacao" | "diagrama" | "linha_tempo" | "mapa", "titulo": "curto", '
        '"como_usar": "1-2 frases para o aluno: o que mexer e o que observar", '
        '"ideia": "(só simulacao) o que o modelo mostra, que controlos tem (1 a 4) e que valores apresenta — para quem o vai programar", '
        '"direcao": "LR ou TB (só diagrama)", "nos": [{"id": "a", "texto": "...", "destaque": false}], '
        '"ligacoes": [{"de": "a", "para": "b", "texto": "(opcional)"}], '
        '"eventos": [{"data": "...", "ano": 1789, "titulo": "...", "descricao": "1-2 frases", "categoria": "..."}], '
        '"locais": [{"nome": "...", "lat": 38.7, "lon": -9.1, "data": "(opcional)", "descricao": "1 frase"}], '
        '"ligar": false}\n'
        "«simulacao» = modelo interativo e animado (movimentos, forças, processos, gráficos que mudam, algoritmos passo a "
        "passo); «diagrama» = esquema de caixas e setas (estruturas, classificações, etapas, causas e consequências; 4 a 16 "
        "caixas, a principal com destaque true); «linha_tempo» = 6 a 16 acontecimentos com datas exatas; «mapa» = 3 a 15 "
        "locais com coordenadas reais em graus decimais (ligar true se formam um percurso por ordem). "
        + IA_LAB[area]["modelos"] + " Se o aluno pediu um tipo (simulação, esquema/diagrama, linha do tempo, mapa), usa "
        "esse. Inclui só os campos do tipo escolhido. Factos e coordenadas verdadeiros.")
    plano = extrair_json(chamar_ia([{"role": "user", "content": instrucoes}], json_mode=True, sistema=SISTEMA_CHAT))
    tipo = plano.get("tipo")
    modelo = {"tipo": tipo, "titulo": str(plano.get("titulo") or "Modelo")[:90],
              "como_usar": str(plano.get("como_usar") or "")[:320], "criado": datetime.now().isoformat(timespec="seconds")}
    if tipo == "diagrama":
        nos = [n for n in (plano.get("nos") or []) if isinstance(n, dict) and (n.get("texto") or n.get("id"))][:24]
        if len(nos) < 2:
            raise ValueError("O diagrama veio vazio.")
        modelo.update(nos=nos, ligacoes=[l for l in (plano.get("ligacoes") or []) if isinstance(l, dict)][:40],
                      direcao="TB" if str(plano.get("direcao", "")).upper() == "TB" else "LR")
    elif tipo == "linha_tempo":
        eventos = sorted([e for e in (plano.get("eventos") or []) if isinstance(e, dict) and e.get("titulo")], key=ano_evento)
        if len(eventos) < 2:
            raise ValueError("A linha do tempo veio vazia.")
        modelo["eventos"] = eventos[:20]
    elif tipo == "mapa":
        locais = [l for l in (plano.get("locais") or []) if isinstance(l, dict) and isinstance(l.get("lat"), (int, float))
                  and isinstance(l.get("lon"), (int, float)) and -90 <= l["lat"] <= 90 and -180 <= l["lon"] <= 180]
        if not locais:
            raise ValueError("O mapa veio sem locais válidos.")
        modelo.update(locais=locais[:20], ligar=bool(plano.get("ligar")))
    else:
        ideia = str(plano.get("ideia") or plano.get("como_usar") or modelo["titulo"])
        if atual and atual.get("tipo") == "simulacao" and atual.get("html"):
            modelo["html"] = alterar_simulacao(atual["html"], pedido)
        else:
            modelo["html"] = codigo_simulacao(area, ideia, modelo["titulo"], pergunta)
        modelo.update(tipo="simulacao", ideia=ideia[:600])
    return modelo


def alterar_simulacao(html_atual: str, pedido: str, erro: str = "") -> str:
    """Muda (ou corrige) um modelo interativo já feito, mantendo o resto."""
    if erro:
        tarefa = f"Este modelo dá o erro «{erro}» na consola do browser. Corrige-o, mantendo o mesmo modelo."
    else:
        tarefa = f"Altera este modelo como o aluno pediu: «{pedido}». Mantém tudo o resto."
    texto = chamar_ia([{"role": "user", "content": f"{tarefa}\n\n```html\n{html_atual[:60_000]}\n```\n\n" + REGRAS_SIMULACAO}],
                      sistema=SISTEMA_SIMULACAO, pensar=True)
    return extrair_html(texto)


def dot_diagrama(modelo: dict, cor: str) -> str:
    """Diagrama da IA (caixas e setas) em Graphviz, com o estilo da app (caixas claras, letra escura, em qualquer tema)."""
    import textwrap

    def q(texto, largura=24) -> str:
        limpo = str(texto or "").replace("\\", "/").replace('"', "'").strip()[:120]
        return '"' + "\\n".join(textwrap.wrap(limpo, largura) or [""]) + '"'
    linhas = ["digraph G {", f'graph [bgcolor="transparent", rankdir={modelo.get("direcao", "LR")}, pad=0.3, '
              'nodesep=0.35, ranksep=0.55];',
              'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#DCE3E1", '
              'fillcolor="#FFFFFF", fontcolor="#12202A", margin="0.2,0.1"];',
              'edge [color="#8A9BA0", penwidth=1.2, arrowsize=0.7, fontname="Helvetica", fontsize=9, fontcolor="#7C8C91"];']
    ids = {}
    for i, n in enumerate(modelo.get("nos") or []):
        ids[str(n.get("id", i))] = f"n{i}"
        extra = f', fillcolor="{cor}", color="{cor}", fontcolor="#FFFFFF", fontsize=12' if n.get("destaque") else ""
        linhas.append(f'n{i} [label={q(n.get("texto") or n.get("id"))}{extra}];')
    for ligacao in modelo.get("ligacoes") or []:
        a, b = ids.get(str(ligacao.get("de"))), ids.get(str(ligacao.get("para")))
        if a and b:
            rotulo = f" [label={q(ligacao['texto'], 18)}]" if ligacao.get("texto") else ""
            linhas.append(f"{a} -> {b}{rotulo};")
    return "\n".join(linhas + ["}"])


def aparar_lab(historico: list) -> None:
    """Guarda as últimas 30 mensagens e o código dos 8 modelos mais recentes (o perfil não cresce sem fim)."""
    del historico[:-30]
    while historico and historico[0].get("role") != "user":
        del historico[0]
    for m in [m for m in historico if m.get("modelo")][:-8]:
        m.pop("modelo", None)


def marcar(chave: str, valor) -> None:
    st.session_state[chave] = valor


def fazer_modelo_lab(area: str, mensagem: dict, pergunta: str, pedido: str = "", atual: dict | None = None,
                     corrigir: str = "") -> bool:
    """Cria (ou altera/corrige) o modelo de uma resposta e guarda-o na conversa da área. Devolve False se falhou
    (a mensagem de erro fica à vista); quando corre bem, volta a desenhar a página."""
    with a_pensar("A corrigir o modelo" if corrigir else "A fazer um modelo para perceberes"):
        try:
            if corrigir:
                novo = dict(atual, html=alterar_simulacao(atual["html"], "", corrigir))
                novo.pop("erro", None)
            else:
                novo = gerar_modelo_lab(area, pergunta, mensagem.get("content", ""), pedido, atual)
        except (ValueError, json.JSONDecodeError):
            st.error("Não consegui fazer o modelo desta vez. Tenta outra vez ou pede de outra forma.")
            return False
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return False
    novo["v"] = (atual or {}).get("v", 0) + 1
    mensagem["modelo"] = novo
    aparar_lab(perfil["lab_ia"][area])
    guardar_perfil()
    st.rerun()


def mostrar_modelo_lab(area: str, mensagem: dict, pergunta: str) -> None:
    modelo = mensagem["modelo"]
    ident = mensagem["id"]
    with st.container(border=True, key=f"labmod_{area}_{ident}"):
        st.markdown(f"<div class='lab-mod-tit'>{escape(modelo.get('titulo') or 'Modelo')}</div>", unsafe_allow_html=True)
        if modelo.get("como_usar"):
            st.caption(modelo["como_usar"])
        tipo = modelo.get("tipo")
        if tipo == "simulacao":
            chave = f"labsim_{area}_{ident}"
            ev = evento(componente("simulacao", chave, 440, html=modelo.get("html", "")), chave)
            if ev and ev.get("evento") == "erro" and not modelo.get("erro"):
                modelo["erro"] = str(ev.get("erro", ""))[:400]
                guardar_perfil()
        elif tipo == "diagrama":
            st.graphviz_chart(dot_diagrama(modelo, CORES_LAB[area]))
        elif tipo == "linha_tempo":
            componente("linha", f"lablinha_{area}_{ident}", 480, eventos=modelo.get("eventos") or [])
            st.caption("Feita pela IA: confirma as datas mais importantes no manual ou nas tuas fontes.")
        elif tipo == "mapa":
            componente("mapa", f"labmapa_{area}_{ident}", 440, locais=modelo.get("locais") or [], ligar=modelo.get("ligar", False))
            st.caption("Coordenadas indicadas pela IA. Mapa © OpenStreetMap.")
        if modelo.get("erro"):
            c_e, c_b = st.columns([3, 1], vertical_alignment="center")
            c_e.warning(f"O modelo deu um erro ao correr: {modelo['erro'][:160]}", icon=":material/bug_report:")
            if c_b.button("Corrigir", key=f"labfix_{area}_{ident}", icon=":material/build:", width="stretch",
                          disabled=not tem_chave):
                fazer_modelo_lab(area, mensagem, pergunta, atual=modelo, corrigir=modelo["erro"])
        c1, c2, c3, _ = st.columns([1.2, 1, 1, 2.2])
        with c1.popover("Alterar", icon=":material/edit:", width="stretch"):
            pedido = st.text_input("O que queres mudar?", key=f"labalt_t_{area}_{ident}",
                                   placeholder="ex.: junta a resistência do ar; mais lento; põe as datas em cima")
            if st.button("Aplicar", key=f"labalt_{area}_{ident}", type="primary", icon=":material/auto_awesome:",
                         disabled=not tem_chave) and pedido.strip():
                fazer_modelo_lab(area, mensagem, pergunta, pedido.strip(), atual=modelo)
        if c2.button("Refazer", key=f"labrefazer_{area}_{ident}", icon=":material/refresh:", width="stretch",
                     disabled=not tem_chave):
            fazer_modelo_lab(area, mensagem, pergunta, "Faz um modelo diferente e melhor do que o anterior.")
        if c3.button("Remover", key=f"labremover_{area}_{ident}", icon=":material/delete:", width="stretch", type="tertiary"):
            mensagem.pop("modelo", None)
            guardar_perfil()
            st.rerun()


def responder_lab(area: str, historico: list, pergunta: str, com_modelo: bool) -> None:
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    with st.chat_message("user"):
        st.markdown(pergunta)
    anteriores = [{"role": m["role"], "content": m["content"]} for m in historico[-10:]]
    with st.chat_message("assistant", avatar=avatar):
        try:
            resposta = escrever_fluxo(chamar_ia_stream(anteriores + [{"role": "user", "content": pergunta}],
                                                       sistema=sistema_lab(area, com_modelo),
                                                       web=bool(IA_LAB[area].get("web") and cfg.get("web", True))),
                                      "A pensar")
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        fontes_web = st.session_state.get("_fontes_web") or []
        if fontes_web:
            bloco = "\n\n**Fontes na web:**\n" + "\n".join(f"- [{escape(t)}]({u})" for t, u in fontes_web[:6])
            st.markdown(bloco)
            resposta += bloco
        st.session_state.pop("_aviso_web", None)
        if not resposta.strip():
            st.warning("A IA não respondeu. Tenta outra vez.")
            return
        mensagem = {"id": uuid.uuid4().hex[:8], "role": "assistant", "content": resposta}
        historico += [{"id": uuid.uuid4().hex[:8], "role": "user", "content": pergunta}, mensagem]
        aparar_lab(historico)
        guardar_perfil()
        if com_modelo and not fazer_modelo_lab(area, mensagem, pergunta, pergunta if quer_modelo(pergunta) else ""):
            return  # o erro do modelo fica à vista; a explicação já está guardada
    st.rerun()


def escolher_ideia(area: str) -> None:
    st.session_state[f"lab_ia_pend_{area}"] = st.session_state.get(f"lab_ia_ideias_{area}")
    st.session_state[f"lab_ia_ideias_{area}"] = None


def ia_do_laboratorio(area: str) -> None:
    """Conversa com a IA da área: explica tudo o que o aluno pedir e, só quando ele quiser, faz um modelo simples."""
    nome = nome_area(area)
    historico = perfil.setdefault("lab_ia", {}).setdefault(area, [])
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    chave_fazer = f"lab_ia_fazer_{area}"
    abertos = st.session_state.setdefault(f"lab_ia_abertos_{area}", [])

    c1, c2, c3 = st.columns([3, 1.7, 1.25], vertical_alignment="center")
    c1.markdown(f"<div class='lab-ia-rot'><span class='material-symbols-rounded'>auto_awesome</span> IA de {escape(nome)}"
                "</div>", unsafe_allow_html=True)
    sempre = c2.toggle("Juntar sempre um modelo", key=f"lab_ia_mod_{area}",
                       help="Ligado: cada resposta vem com um modelo simples (simulação, esquema, linha do tempo ou mapa). "
                            "Desligado: só há modelo quando o pedires (na pergunta ou no botão por baixo da resposta).")
    if historico and c3.button("Nova conversa", key=f"lab_ia_limpar_{area}", icon=":material/add_comment:",
                               width="stretch"):
        perfil["lab_ia"][area] = []
        guardar_perfil()
        st.rerun()
    if not tem_chave:
        st.info(sem_ia_texto(f"para falar com a IA de {nome}"), icon=":material/key:")

    if not historico:
        with st.container(key=f"labvazio_{area}"):
            st.markdown(f"<div class='lab-vazio'><div class='lab-vazio-t'>O que queres perceber de {escape(nome)}?</div>"
                        "<div class='lab-vazio-s'>Pergunta o que quiseres: explico tudo, passo a passo, com fórmulas e "
                        "exemplos. Se quiseres ver para perceber, pede um modelo — uma simulação, um esquema, uma linha "
                        "do tempo ou um mapa — e eu faço-o à medida do que pediste.</div></div>", unsafe_allow_html=True)
            st.pills("Ideias", IA_LAB[area]["exemplos"], key=f"lab_ia_ideias_{area}", on_change=escolher_ideia,
                     args=(area,), label_visibility="collapsed")

    visiveis = historico[-24:]
    ultimo_modelo = next((m["id"] for m in reversed(visiveis) if m.get("modelo")), None)
    for k, m in enumerate(visiveis):
        assistente = m["role"] == "assistant"
        with st.chat_message(m["role"], avatar=avatar if assistente else None):
            md(m["content"])
            if not assistente:
                continue
            pergunta_m = visiveis[k - 1]["content"] if k and visiveis[k - 1]["role"] == "user" else ""
            if st.session_state.get(chave_fazer) == m["id"]:
                st.session_state.pop(chave_fazer, None)
                fazer_modelo_lab(area, m, pergunta_m)
            elif m.get("modelo") and (m["id"] == ultimo_modelo or m["id"] in abertos):
                mostrar_modelo_lab(area, m, pergunta_m)
            elif m.get("modelo"):
                st.button(f"Ver o modelo: {m['modelo'].get('titulo', '')[:40]}", key=f"labver_{area}_{m['id']}",
                          icon=":material/visibility:", type="tertiary", on_click=abertos.append, args=(m["id"],))
            elif tem_chave:
                st.button("Criar um modelo para perceber", key=f"labmk_{area}_{m['id']}", icon=":material/draw:",
                          type="tertiary", on_click=marcar, args=(chave_fazer, m["id"]))

    with fixo_no_fundo():
        entrada = st.chat_input(f"Pergunta o que quiseres de {nome}…", key=f"lab_ia_in_{area}", disabled=not tem_chave)
    pergunta = entrada or st.session_state.pop(f"lab_ia_pend_{area}", None)
    if pergunta and tem_chave:
        responder_lab(area, historico, pergunta, bool(sempre) or quer_modelo(pergunta))


def pagina_quimica(aba: str) -> None:
    if aba == "Tabela periódica":
        componente("tabela", "lab_tabela", 620, elementos=lab.ELEMENTOS, cores=lab.CORES_CATEGORIA)
        explicador("tabela periódica dos elementos", "quim_tab", "ex.: porque é que os gases nobres não reagem?")
    elif aba == "Massa molar":
        formula = st.text_input("Fórmula química", key="lab_formula", placeholder="ex.: H2SO4, Ca(OH)2, CuSO4·5H2O")
        if formula.strip():
            try:
                r = lab.massa_molar(formula)
                c1, c2 = st.columns([1, 2])
                c1.metric("Massa molar", f"{r['massa']:.3f} g/mol".replace(".", ","))
                c2.markdown(latex_quimica(r["formula"]))
                st.dataframe([{"Elemento": f"{l['elemento']} ({l['nome']})", "Átomos": l["atomos"],
                               "Massa atómica": l["massa_atomica"], "Contribuição (g/mol)": l["contribuicao"],
                               "% em massa": l["percentagem"]} for l in r["composicao"]], hide_index=True)
            except lab.ErroLab as erro:
                st.error(str(erro))
    elif aba == "Acertar equações":
        eq = st.text_input("Equação química", key="lab_eq", placeholder="ex.: C3H8 + O2 -> CO2 + H2O")
        if eq.strip():
            try:
                r = lab.acertar_equacao(eq)
                with st.container(border=True):
                    md(latex_quimica(r["acertada"]))
                st.caption("Verificação (átomos de cada elemento nos reagentes = nos produtos): " +
                           ", ".join(f"{el}: {a} = {b}" for el, (a, b) in r["verificacao"].items()))
            except lab.ErroLab as erro:
                st.error(str(erro))
        explicador("acerto de equações químicas", "quim_eq", "ex.: como se acerta uma equação redox?")
    else:
        moleculas_3d()


def pubchem_sdf(nome: str):
    """Estrutura 3D real de uma molécula (PubChem). Devolve (sdf, propriedades)."""
    import httpx
    from urllib.parse import quote

    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/" + quote(nome.strip())
    with httpx.Client(timeout=20) as cliente:
        r = cliente.get(base + "/SDF", params={"record_type": "3d"})
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        p = cliente.get(base + "/property/MolecularFormula,MolecularWeight,IUPACName/JSON")
        props = (p.json().get("PropertyTable", {}).get("Properties") or [{}])[0] if p.status_code == 200 else {}
        return r.text, props


def moleculas_3d() -> None:
    nome = st.text_input("Molécula", key="lab_mol", placeholder="ex.: água, cafeína, glicose, etanol, aspirina, metano")
    if not nome.strip():
        st.caption("Escreve o nome de uma molécula: a estrutura 3D vem do PubChem (dados reais, com as posições dos átomos).")
        return
    cache = st.session_state.setdefault("_moleculas", {})
    chave = nome.strip().lower()
    if chave not in cache:
        with a_pensar("A procurar a estrutura no PubChem"):
            try:
                sdf, props = pubchem_sdf(nome)
                if sdf is None and tem_chave:  # nome em português: pede à IA o nome em inglês
                    ingles = chamar_ia([{"role": "user", "content": f"Nome em inglês (só o nome, sem mais nada) da molécula: {nome}"}],
                                       sistema="Respondes só com o nome químico em inglês.").strip().strip(".")
                    sdf, props = pubchem_sdf(ingles) if ingles else (None, None)
                cache[chave] = (sdf, props)
            except Exception as erro:  # noqa: BLE001
                st.error(f"Não foi possível contactar o PubChem ({erro}). Verifica a ligação à internet.")
                return
    sdf, props = cache[chave]
    if not sdf:
        st.warning("Não encontrei essa molécula no PubChem (ou não tem estrutura 3D). Experimenta o nome em inglês.")
        return
    try:
        modelo = e3.molecula_de_sdf(sdf, nome.strip().capitalize())
    except e3.ErroModelo as erro:
        st.error(str(erro))
        return
    c1, c2 = st.columns([2.2, 1], gap="medium")
    with c1:
        componente("visor3d", "lab_mol_visor", 460, modelo=modelo, enquadrar=chave, enviar_selecao=False, capa=False)
    with c2:
        if props:
            st.markdown(f"**{escape(nome.strip().capitalize())}**")
            md(latex_quimica(props.get("MolecularFormula", "")))
            st.caption(f"Massa molar: {props.get('MolecularWeight', '?')} g/mol  \nNome IUPAC: {props.get('IUPACName', '—')}")
        st.caption("Cores: C cinzento-escuro, H branco, O vermelho, N azul, S amarelo. Fonte: PubChem (NIH).")
        if ESTUDIO_3D and st.button("Guardar no 3D Studio", icon=":material/view_in_ar:", key="lab_mol_guardar"):
            guardar_no_3d(modelo, f"Molécula do PubChem: {nome.strip()}")


def guardar_no_3d(modelo: dict, nota: str) -> None:
    import biblioteca3d as b3

    try:
        bib = biblioteca_3d()
        if not bib.contas.atual():
            st.warning("Entra na tua conta no 3D Studio (Os meus modelos) para guardar modelos.")
            return
        novo = bib.criar(modelo, nota=nota, creditos=bib.contas.atual()["nome"])
        ir("estudio3d", e3d_secao="criar", e3d_aberto=novo["id"])
    except b3.Erro3D as erro:
        st.error(str(erro))


def pagina_matematica(aba: str) -> None:
    if aba == "Gráficos 2D":
        import altair as alt

        c1, c2, c3 = st.columns(3)
        exprs = [c1.text_input("f(x) =", "x^2 - 3x + 2", key="lab_f"), c2.text_input("g(x) =", "", key="lab_g",
                 placeholder="opcional, ex.: 2sin(x)"), c3.text_input("h(x) =", "", key="lab_h", placeholder="opcional")]
        a, b, x0 = st.columns(3)
        ini = a.number_input("Início do intervalo", value=-5.0, key="lab_a")
        fim = b.number_input("Fim do intervalo", value=5.0, key="lab_b")
        ponto = x0.number_input("Ponto para a derivada", value=1.0, key="lab_x0")
        linhas, info = [], []
        for nome_f, texto in zip("fgh", exprs):
            if not texto.strip():
                continue
            try:
                f = lab.compilar(texto)
                xs, ys = lab.amostrar(f, ini, fim)
            except lab.ErroLab as erro:
                st.error(f"{nome_f}(x): {erro}")
                continue
            seg = np.cumsum(np.isnan(ys))
            linhas += [{"x": float(x), "y": float(y), "função": f"{nome_f}(x)", "seg": f"{nome_f}{s}"}
                       for x, y, s in zip(xs, ys, seg) if np.isfinite(y)]
            try:
                integ = f"{lab.integral(f, ini, fim):.4f}".replace(".", ",")
            except lab.ErroLab:
                integ = "não definido"
            rz = lab.raizes(f, ini, fim)
            ext = lab.extremos(f, ini, fim)
            info.append(f"**{nome_f}(x)** · zeros: {', '.join(f'{r:g}'.replace('.', ',') for r in rz[:8]) or 'nenhum'} · "
                        f"$f'({ponto:g}) \\approx {lab.derivada(f, ponto):.4f}$ · "
                        f"$\\int_{{{ini:g}}}^{{{fim:g}}} {nome_f}(x)\\,dx \\approx {integ}$"
                        + (" · " + "; ".join(f"{e['tipo']} em ({e['x']:g}; {e['y']:g})" for e in ext[:4]) if ext else ""))
        if linhas:
            dados_g = pd.DataFrame(linhas)
            grafico = alt.Chart(dados_g).mark_line(strokeWidth=2.4).encode(
                x=alt.X("x:Q", title="x"), y=alt.Y("y:Q", title="y"),
                color=alt.Color("função:N", scale=alt.Scale(range=["#17798A", "#2AA5B8", "#E0B04B"]),
                                legend=alt.Legend(orient="top", title=None)),
                detail="seg:N", tooltip=[alt.Tooltip("função:N"), alt.Tooltip("x:Q", format=".3f"), alt.Tooltip("y:Q", format=".3f")])
            eixos = alt.Chart(pd.DataFrame({"z": [0]})).mark_rule(color="#7C8C91", strokeWidth=1)
            st.altair_chart(grafico_tema((eixos.encode(y="z:Q") + eixos.encode(x="z:Q") + grafico).interactive()), theme=None,
                            width="stretch")
            for linha in info:
                md(linha)
        explicador(f"gráficos das funções {', '.join(e for e in exprs if e.strip())}", "mat2d",
                   "ex.: o que significa a derivada ser zero?")
    else:
        texto = st.text_input("z = f(x, y)", "sin(x) * cos(y)", key="lab_fxy")
        intervalo = st.slider("Intervalo de x e y (−a a a)", 1.0, 10.0, 3.0, 0.5, key="lab_int")
        try:
            alturas, info = lab.grelha_superficie(texto, intervalo, 70)
            modelo = e3.modelo_superficie(f"z = {texto}", alturas, 70, 70)
            componente("visor3d", "lab_superficie", 480, modelo=modelo, enquadrar="sup", enviar_selecao=False, capa=False)
            st.caption(f"x e y entre −{intervalo:g} e {intervalo:g} · z entre {info['zmin']:.3g} e {info['zmax']:.3g} "
                       "(altura reescalada para caber; azul = baixo, vermelho = alto).")
            if ESTUDIO_3D and st.button("Guardar no 3D Studio", icon=":material/view_in_ar:", key="lab_sup_guardar"):
                guardar_no_3d(modelo, f"Gráfico 3D: z = {texto}")
        except lab.ErroLab as erro:
            st.error(str(erro))


PALETA_FENOTIPOS = ["#17798A", "#2E6DB4", "#3E8E5A", "#D9A21F", "#7D4FA8", "#2AA5B8", "#D9708F", "#7C8C91"]


def fenotipo_de(genotipo: str) -> str:
    return " ".join(("dominante " if any(c.isupper() for c in genotipo[i:i + 2]) else "recessivo ") + genotipo[i].upper()
                    for i in range(0, len(genotipo), 2))


def html_codoes(codoes: list) -> str:
    chips = []
    for i, c in enumerate(codoes):
        classe = "fim" if c["aa"] == "*" else ("ini" if i == 0 and c["codao"] == "AUG" else "")
        chips.append(f"<div class='bio-cod {classe}' title='{escape(c['nome'])}'><b>{escape(c['codao'])}</b>"
                     f"<span>{escape(c['abrev'])}</span></div>")
    return "<div class='bio-cods'>" + "".join(chips) + "</div>"


def html_punnett(r: dict) -> str:
    fenos = list(r["fenotipos"])
    cor = {f: PALETA_FENOTIPOS[i % len(PALETA_FENOTIPOS)] for i, f in enumerate(fenos)}
    cab = "".join(f"<th>{escape(g)}</th>" for g in r["gametas_mae"])
    corpo = ""
    for gp, linha in zip(r["gametas_pai"], r["tabela"]):
        celulas = "".join(f"<td style='background:{cor[fenotipo_de(g)]}26;border-color:{cor[fenotipo_de(g)]}55'>"
                          f"{escape(g)}</td>" for g in linha)
        corpo += f"<tr><th>{escape(gp)}</th>{celulas}</tr>"
    legenda = ""
    for f, prop in r["fenotipos"].items():
        n, total = (int(x) for x in prop.split("/"))
        legenda += (f"<div class='bio-leg'><i style='background:{cor[f]}'></i><span>{escape(f)}</span>"
                    f"<b>{prop} · {round(100 * n / total)}%</b><div class='bio-barra'><div style='width:{100 * n / total:.1f}%;"
                    f"background:{cor[f]}'></div></div></div>")
    genos = "".join(f"<span class='bio-geno'>{escape(g)} <b>{p_}</b></span>" for g, p_ in r["genotipos"].items())
    return (f"<div class='bio-pun'><table><tr><th class='canto'>gâmetas</th>{cab}</tr>{corpo}</table>"
            f"<div class='bio-pun-lado'><div class='bio-sub'>Fenótipos</div>{legenda}"
            f"<div class='bio-sub'>Genótipos</div><div class='bio-genos'>{genos}</div></div></div>")


def pagina_biologia(aba: str) -> None:
    if aba == "Do DNA à proteína":
        with st.container(border=True):
            seq = st.text_area("Sequência de DNA", "TACGGTCATTTAACT", key="lab_dna", height=80)
            c1, c2 = st.columns(2)
            cadeia = c1.radio("Esta sequência é a cadeia…", ["molde", "codificante"], horizontal=True, key="lab_cadeia",
                              format_func={"molde": "Molde (3'→5')", "codificante": "Codificante (5'→3')"}.get)
            desde = c2.toggle("Começar no codão de iniciação (AUG)", True, key="lab_aug")
        try:
            r = lab.expressao_genica(seq, cadeia, desde)
            st.markdown("<div class='bio-passo'><b>1</b> Transcrição: o DNA é copiado para mRNA</div>", unsafe_allow_html=True)
            st.code(" ".join(r["mrna"][i:i + 3] for i in range(0, len(r["mrna"]), 3)), language=None)
            if r["codoes"]:
                st.markdown("<div class='bio-passo'><b>2</b> Tradução: cada codão dá um aminoácido</div>",
                            unsafe_allow_html=True)
                st.markdown(html_codoes(r["codoes"]), unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Codões lidos", len(r["codoes"]))
                m2.metric("Aminoácidos", len(r["proteina"]))
                m3.metric("Nucleótidos do mRNA", len(r["mrna"]))
                st.markdown(f"**Proteína:** {r['proteina_abrev'] or '—'}  ·  `{r['proteina']}`")
                with st.expander("Tabela dos codões", icon=":material/table:"):
                    st.dataframe([{"Codão": c["codao"], "Aminoácido": c["nome"], "Abrev.": c["abrev"]} for c in r["codoes"]],
                                 hide_index=True)
            if r["aviso"]:
                st.caption(r["aviso"])
        except lab.ErroLab as erro:
            st.error(str(erro))
        explicador("transcrição e tradução (código genético)", "bio_dna", "ex.: o que acontece numa mutação pontual?")
    elif aba == "Genética (Punnett)":
        with st.container(border=True):
            c1, c2 = st.columns(2)
            pai = c1.text_input("Genótipo de um progenitor", "AaBb", key="lab_pai")
            mae = c2.text_input("Genótipo do outro progenitor", "AaBb", key="lab_mae")
            st.caption("Maiúscula = alelo dominante. Escreve um par de letras por gene (Aa, AaBb, AaBbCc…).")
        try:
            r = lab.punnett(pai, mae)
            st.markdown(html_punnett(r), unsafe_allow_html=True)
        except lab.ErroLab as erro:
            st.error(str(erro))
        explicador("genética mendeliana e quadrados de Punnett", "bio_pun", "ex.: o que é a dominância incompleta?")
    else:
        st.caption("Escolhe um modelo para criar no 3D Studio (com a IA) ou explora os da comunidade.")
        opcoes = {k: v for k, v in SUGESTOES_3D.items() if v[1] in ("Anatomia", "Biologia celular", "Molécula")}
        cols = st.columns(len(opcoes))
        for col, (nome, (desc, tipo)) in zip(cols, opcoes.items()):
            col.button(nome, key=f"bio3d_{nome}", width="stretch", on_click=navegar, args=("estudio3d",),
                       kwargs={"e3d_secao": "criar", "e3d_aberto": None, "e3d_desc": desc, "e3d_tipo": tipo})
        try:
            bib = biblioteca_3d()
            modelos = [m for cat in ("Anatomia", "Biologia") for m in bib.pesquisar(categoria=cat, limite=6)][:6]
        except Exception:  # noqa: BLE001
            modelos = []
        if modelos:
            titulo_cartao("Da comunidade")
            st.markdown(ESTILO_3D, unsafe_allow_html=True)
            grelha_3d(modelos, "bio")


def gerar_tema_ia(pedido: str, cadeira_fontes: str | None) -> dict | None:
    fontes = ""
    if cadeira_fontes and cadeira_fontes in st.session_state.cadeiras:
        fontes = selecionar_texto(st.session_state.cadeiras[cadeira_fontes]["ficheiros"], pedido)
    texto = ""
    try:
        conteudo = (f"<fontes>\n{fontes}\n</fontes>\n\n{pedido}" if fontes else pedido) + " " + mt.REGRAS_FORMULAS_JSON
        texto = chamar_ia([{"role": "user", "content": conteudo}], json_mode=True, sistema=SISTEMA if fontes else SISTEMA_CHAT)
        return extrair_json(texto)
    except (ValueError, json.JSONDecodeError) as erro:
        st.error("A IA não devolveu um formato válido. Tenta outra vez.")
        with st.expander("Detalhe técnico"):
            st.caption(str(erro))
            st.code((texto or "(resposta vazia)")[:3000], language=None)
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
    return None


def pagina_historia(aba: str) -> None:
    tipo = "linhas_tempo" if aba == "Linha do tempo" else "mapas"
    guardados = perfil.setdefault(tipo, {})
    c1, c2 = st.columns([2, 1])
    tema = c1.text_input("Tema", key=f"lab_tema_{tipo}", placeholder="ex.: Descobrimentos portugueses" if tipo == "mapas"
                         else "ex.: Revolução Francesa, 25 de Abril, História da Universidade de Coimbra")
    fontes_de = c2.selectbox("Usar as fontes da cadeira", [None] + list(st.session_state.cadeiras), key=f"lab_fontes_{tipo}",
                             format_func=lambda c: "Não (conhecimento geral)" if c is None else c)
    if st.button("Criar com IA", type="primary", icon=":material/auto_awesome:", disabled=not (tem_chave and tema.strip()),
                 key=f"lab_criar_{tipo}"):
        if tipo == "linhas_tempo":
            pedido = (f"Cria uma linha do tempo sobre: {tema}. Entre 8 e 18 acontecimentos importantes, por ordem cronológica, "
                      "com datas exatas e factos verificáveis. Responde só com JSON: {\"titulo\": \"...\", \"eventos\": "
                      "[{\"data\": \"ex.: 14 de julho de 1789\", \"ano\": 1789, \"titulo\": \"...\", \"descricao\": \"2-3 frases\", "
                      "\"categoria\": \"tema curto (ex.: Política, Ciência, Guerra)\"}]}")
        else:
            pedido = (f"Cria um mapa sobre: {tema}. Entre 5 e 15 locais importantes, com coordenadas geográficas reais e exatas "
                      "(graus decimais). Responde só com JSON: {\"titulo\": \"...\", \"ligar\": true se os locais formam um "
                      "percurso por ordem, \"locais\": [{\"nome\": \"...\", \"lat\": 38.7, \"lon\": -9.1, \"data\": \"(opcional)\", "
                      "\"descricao\": \"1-2 frases\"}]}")
        with a_pensar("A preparar"):
            r = gerar_tema_ia(pedido, fontes_de)
        itens = (r or {}).get("eventos" if tipo == "linhas_tempo" else "locais") or (r or {}).get("_lista") or []
        if itens:
            if tipo == "linhas_tempo":
                itens = sorted([e for e in itens if isinstance(e, dict) and e.get("titulo")],
                               key=lambda e: float(e.get("ano") or 0) if str(e.get("ano") or "").lstrip("-").replace(".", "").isdigit() else 0)
            else:
                itens = [l for l in itens if isinstance(l, dict) and isinstance(l.get("lat"), (int, float))
                         and isinstance(l.get("lon"), (int, float)) and -90 <= l["lat"] <= 90 and -180 <= l["lon"] <= 180]
            ident = uuid.uuid4().hex[:8]
            guardados[ident] = {"titulo": str(r.get("titulo") or tema)[:100], "itens": itens, "ligar": bool(r.get("ligar")),
                                "criado": datetime.now().isoformat(timespec="seconds"), "fontes": fontes_de}
            for antigo in sorted(guardados, key=lambda k: guardados[k]["criado"])[:-12]:  # guarda os 12 mais recentes
                guardados.pop(antigo)
            st.session_state[f"lab_sel_{tipo}"] = ident
            guardar_perfil()
            st.rerun()
        elif r is not None:
            st.error("A resposta não trouxe dados utilizáveis. Tenta outra vez.")
    if not tem_chave:
        st.caption(sem_ia_texto("para criar linhas do tempo e mapas"))
    if guardados:
        ids = sorted(guardados, key=lambda k: guardados[k]["criado"], reverse=True)
        atual = st.session_state.get(f"lab_sel_{tipo}") if st.session_state.get(f"lab_sel_{tipo}") in ids else ids[0]
        escolha = st.selectbox("Guardados", ids, index=ids.index(atual), format_func=lambda k: guardados[k]["titulo"],
                               key=f"lab_lista_{tipo}")
        item = guardados[escolha]
        if tipo == "linhas_tempo":
            componente("linha", f"lab_linha", 500, eventos=item["itens"])
            st.caption("Feita pela IA: confirma as datas e os factos mais importantes nas tuas fontes ou no manual.")
        else:
            componente("mapa", f"lab_mapa", 480, locais=item["itens"], ligar=item.get("ligar", False))
            st.caption("As coordenadas são indicadas pela IA: confirma as mais importantes. Mapa © OpenStreetMap.")
        if item.get("fontes"):
            st.caption(f"Feito a partir das fontes de «{item['fontes']}».")
        if st.button("Apagar", key=f"lab_apagar_{tipo}", type="tertiary"):
            guardados.pop(escolha)
            guardar_perfil()
            st.rerun()
        explicador(f"{'linha do tempo' if tipo == 'linhas_tempo' else 'mapa'} sobre {item['titulo']}", f"hist_{tipo}",
                   "ex.: quais foram as causas principais?")


CODIGO_INICIAL = '''# Experimenta: altera o código e carrega em Executar (ou Ctrl+Enter)
def fatorial(n):
    return 1 if n <= 1 else n * fatorial(n - 1)

for i in range(1, 8):
    print(f"{i}! = {fatorial(i)}")
'''


def pagina_programacao() -> None:
    exercicio = st.session_state.get("lab_exercicio")
    c1, c2, c3 = st.columns([1.2, 2, 1], vertical_alignment="bottom")
    nivel = c1.selectbox("Nível", ["Iniciante", "Intermédio", "Avançado"], key="lab_nivel")
    tema = c2.text_input("Tema do exercício (opcional)", key="lab_tema_prog", placeholder="ex.: listas, ciclos, dicionários, recursão")
    if c3.button("Novo exercício", icon=":material/auto_awesome:", width="stretch", disabled=not tem_chave):
        with a_pensar("A preparar um exercício"):
            try:
                r = extrair_json(chamar_ia([{"role": "user", "content":
                    f"Cria um exercício de programação em Python, nível {nivel.lower()}, sobre {tema or 'um tema à escolha'}. "
                    "Responde só com JSON: {\"titulo\": \"...\", \"enunciado\": \"markdown curto com exemplo de entrada e saída\", "
                    "\"codigo_inicial\": \"código Python com a estrutura e comentários TODO, sem a solução\", "
                    "\"dica\": \"uma pista\"}"}], json_mode=True, sistema=SISTEMA_CHAT))
                st.session_state.lab_exercicio = r
                st.session_state.lab_codigo = r.get("codigo_inicial") or CODIGO_INICIAL
                st.session_state.lab_codigo_v = st.session_state.get("lab_codigo_v", 0) + 1
                st.session_state.pop("lab_ajuda", None)
                st.rerun()
            except (ValueError, json.JSONDecodeError):
                st.error("A IA não devolveu um exercício válido. Tenta outra vez.")
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
    if exercicio:
        with st.container(border=True):
            st.markdown(f"**{escape(str(exercicio.get('titulo', 'Exercício')))}**")
            md(str(exercicio.get("enunciado", "")))
            if exercicio.get("dica"):
                with st.expander("Dica"):
                    md(str(exercicio["dica"]))
    valor = componente("codigo", "lab_codigo_ed", 420, codigo=st.session_state.get("lab_codigo", CODIGO_INICIAL),
                       chave_codigo=st.session_state.get("lab_codigo_v", 0))
    ev = evento(valor, "lab_codigo_ed")
    if ev and ev.get("evento") == "ajuda":
        st.session_state.lab_ajuda = {"codigo": ev.get("codigo", ""), "saida": ev.get("saida", ""), "t": ev["t"]}
    ajuda = st.session_state.get("lab_ajuda")
    if ajuda:
        with st.container(border=True):
            titulo_cartao("Ajuda da IA")
            if not tem_chave:
                st.caption(sem_ia_texto())
            elif ajuda.get("resposta"):
                md(ajuda["resposta"])
            else:
                contexto = (f"Exercício: {exercicio.get('enunciado')}\n\n" if exercicio else "")
                try:
                    ajuda["resposta"] = escrever_fluxo(chamar_ia_stream([{"role": "user", "content":
                        f"{contexto}Código do aluno:\n```python\n{ajuda['codigo']}\n```\nSaída/erro ao executar:\n```\n"
                        f"{ajuda['saida'] or '(ainda não executado)'}\n```\nExplica o que o código faz e, se houver erro, onde "
                        "está e porquê. Dá pistas para o aluno corrigir sozinho; só mostra a solução completa se o código "
                        "já estiver quase certo."}], sistema=sistema_chat()), "A ler o teu código")
                except Exception as erro:  # noqa: BLE001
                    mostrar_erro(erro)
    st.caption("O código corre no teu browser (Pyodide): não tem acesso aos teus ficheiros. Bibliotecas como numpy carregam "
               "sozinhas quando as importas.")


FERRAMENTAS_LAB = {
    "fisica": [],
    "quimica": [("Tabela periódica", ":material/grid_on:"), ("Massa molar", ":material/scale:"),
                ("Acertar equações", ":material/balance:"), ("Moléculas 3D", ":material/hub:")],
    "matematica": [("Gráficos 2D", ":material/show_chart:"), ("Gráficos 3D", ":material/view_in_ar:")],
    "biologia": [("Do DNA à proteína", ":material/genetics:"), ("Genética (Punnett)", ":material/grid_view:")]
                + ([("Anatomia 3D", ":material/view_in_ar:")] if ESTUDIO_3D else []),
    "historia": [("Linha do tempo", ":material/timeline:"), ("Mapa interativo", ":material/map:")],
    "programacao": [("Editor de Python", ":material/terminal:")],
}
ESTILO_LAB = "<style>" + "".join(
    f'div.stVerticalBlock[class*="st-key-labcard_{a}"], div.stVerticalBlock[class*="st-key-labtopo_{a}"] '
    f'{{ border-top:4px solid {c} !important; border-top-color:{c} !important; }} '
    f'div.stVerticalBlock[class*="st-key-labtopo_{a}"] {{ background:linear-gradient(120deg, var(--cartao) 55%, {c}1F 140%); }} '
    f'div.stVerticalBlock[class*="st-key-labmod_{a}_"] {{ border-left:3px solid {c} !important; }} '
    for a, c in CORES_LAB.items()) + """
.lab-ico { width:44px; height:44px; border-radius:13px; display:flex; align-items:center; justify-content:center; flex:none; }
.lab-ico span { font-size:25px; line-height:1; }
.lab-ico.grande { width:54px; height:54px; border-radius:16px; } .lab-ico.grande span { font-size:31px; }
.lab-card-nome { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.22rem; font-weight:600; color:var(--texto);
  margin:0.7rem 0 0.15rem; }
.lab-card-desc { color:var(--suave); font-size:0.88rem; line-height:1.45; min-height:3.9em; }
.lab-tags { display:flex; flex-wrap:wrap; align-content:flex-start; gap:0.3rem; margin:0.55rem 0 0.2rem; min-height:2.9rem; }
.lab-tag { font-size:0.72rem; padding:0.06rem 0.55rem; border-radius:999px; background:var(--bolha); color:var(--texto);
  white-space:nowrap; }
.lab-tag.ia { background:var(--acento-claro); color:var(--acento-esc); font-weight:600; }
.lab-hero { display:flex; align-items:center; gap:0.95rem; min-width:0; }
.lab-nome { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.7rem; font-weight:600; color:var(--texto);
  line-height:1.15; margin:0 !important; }
.lab-desc { color:var(--suave); font-size:0.92rem; margin:0.15rem 0 0 !important; }
.lab-ia-rot { display:flex; align-items:center; gap:0.4rem; font-weight:600; color:var(--texto); font-size:0.98rem; }
.lab-ia-rot span { color:var(--acento); font-size:20px; }
.lab-vazio { text-align:center; padding:2.4rem 1rem 0.8rem; }
.lab-vazio-t { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.65rem; color:var(--texto); line-height:1.25; }
.lab-vazio-s { color:var(--suave); max-width:600px; margin:0.55rem auto 0.4rem; font-size:0.95rem; line-height:1.55; }
div.stVerticalBlock[class*="st-key-labvazio_"] { align-items:center; }
div[class*="st-key-labvazio_"] [data-testid="stButtonGroup"] button { border-radius:999px !important; }
.lab-mod-tit { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:1.15rem; font-weight:600; color:var(--texto); }
.bio-passo { display:flex; align-items:center; gap:0.5rem; font-weight:600; color:var(--texto); margin:0.6rem 0 0.3rem; }
.bio-passo b { display:inline-grid; place-items:center; width:22px; height:22px; border-radius:50%; background:var(--primario);
  color:#fff; font-size:0.75rem; }
.bio-cods { display:flex; flex-wrap:wrap; gap:6px; margin:0.2rem 0 0.8rem; }
.bio-cod { display:flex; flex-direction:column; align-items:center; min-width:52px; padding:6px 8px; border-radius:10px;
  background:var(--cartao); border:1px solid var(--linha); }
.bio-cod b { font-family:ui-monospace, Menlo, monospace; font-size:0.95rem; color:var(--texto); letter-spacing:0.04em; }
.bio-cod span { font-size:0.75rem; color:var(--suave); }
.bio-cod.ini { border-color:#3E8E5A; background:#3E8E5A1A; } .bio-cod.fim { border-color:#C0392B; background:#C0392B1A; }
.bio-pun { display:flex; flex-wrap:wrap; gap:1.4rem; align-items:flex-start; margin:0.4rem 0 0.8rem; }
.bio-pun table { border-collapse:separate; border-spacing:4px; }
.bio-pun th { font-family:ui-monospace, Menlo, monospace; font-weight:600; color:var(--suave); padding:4px 8px; font-size:0.85rem; }
.bio-pun th.canto { font-family:'Inter', sans-serif; font-weight:400; font-size:0.72rem; }
.bio-pun td { font-family:ui-monospace, Menlo, monospace; text-align:center; padding:9px 10px; border-radius:9px;
  border:1px solid var(--linha); color:var(--texto); font-size:0.92rem; min-width:56px; }
.bio-pun-lado { flex:1; min-width:240px; }
.bio-sub { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--suave); margin:0.2rem 0 0.4rem; }
.bio-leg { display:grid; grid-template-columns:12px 1fr auto; gap:0.2rem 0.5rem; align-items:center; margin-bottom:0.55rem;
  color:var(--texto); font-size:0.88rem; }
.bio-leg i { width:12px; height:12px; border-radius:4px; }
.bio-leg b { font-weight:600; font-size:0.85rem; }
.bio-barra { grid-column:2 / 4; height:6px; border-radius:99px; background:var(--bolha); overflow:hidden; }
.bio-barra div { height:100%; border-radius:99px; }
.bio-genos { display:flex; flex-wrap:wrap; gap:0.35rem; }
.bio-geno { font-family:ui-monospace, Menlo, monospace; font-size:0.82rem; padding:0.1rem 0.55rem; border-radius:8px;
  background:var(--bolha); color:var(--texto); }
.bio-geno b { color:var(--suave); font-weight:500; }
</style>"""


def icone_lab_html(area: str, grande: bool = False) -> str:
    nome_icone = AREAS_LAB[area][0].split("/")[-1].strip(":")
    cor = CORES_LAB[area]
    return (f"<div class='lab-ico{' grande' if grande else ''}' style='background:{cor}1F;color:{cor}'>"
            f"<span class='material-symbols-rounded'>{nome_icone}</span></div>")



# =============================================================== LABORATÓRIO DAS SALAS (História, Biologia e as outras áreas)
# O Laboratório deixou de ser uma página: quem cria uma sala escolhe se o quer e que ferramentas os membros têm. As
# ferramentas usam os materiais da sala (se a pessoa quiser) e guardam o trabalho de cada pessoa em laboratorio.json.
ESTILO_LAB_SALA = """
<style>
.lb-cab { display:flex; align-items:center; gap:0.6rem; margin:0.2rem 0 0.6rem; }
.lb-cab b { font-size:1.08rem; color:var(--texto); }
.lb-cab span { color:var(--suave); font-size:0.88rem; }
.lb-sec { font-size:0.72rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--suave); font-weight:600;
  margin:0.9rem 0 0.35rem; }
.lb-certeza { display:inline-block; font-size:0.72rem; font-weight:600; border-radius:999px; padding:0.05rem 0.55rem;
  margin-left:0.35rem; vertical-align:0.1em; }
.lb-certeza.confirmado { background:#DCF2E4; color:#166534; } .lb-certeza.aproximado { background:#FBEFD5; color:#8A5A00; }
.lb-certeza.incerto { background:#FDE2E1; color:#9F1C14; }
.lb-chip { display:inline-block; background:var(--bolha); color:var(--texto); border-radius:999px; padding:0.1rem 0.6rem;
  font-size:0.8rem; margin:0 0.25rem 0.3rem 0; }
.lb-etapa { display:grid; grid-template-columns:28px 1fr; gap:0.55rem; align-items:start; margin:0 0 0.7rem; }
.lb-etapa i { font-style:normal; display:grid; place-items:center; width:26px; height:26px; border-radius:50%;
  background:var(--primario); color:#fff; font-size:0.8rem; font-weight:700; }
.lb-etapa b { color:var(--texto); } .lb-etapa div { color:var(--texto); line-height:1.55; font-size:0.95rem; }
.lb-nota { font-size:2.4rem; font-weight:700; letter-spacing:-0.03em; color:var(--texto); line-height:1; }
.lb-q { font-weight:600; color:var(--texto); margin-bottom:0.2rem; }
.lb-tipo { font-size:0.72rem; color:var(--suave); text-transform:uppercase; letter-spacing:0.04em; }
.lb-doc { border-left:3px solid var(--destaque); background:var(--bolha); padding:0.6rem 0.9rem; border-radius:8px;
  color:var(--texto); font-size:0.93rem; line-height:1.55; white-space:pre-wrap; }
.lb-fontes a { color:var(--acento); }
</style>"""


def lab_dados() -> dict:
    """O trabalho do Laboratório desta pessoa (cronologias, comparações, testes, glossário…), em laboratorio.json."""
    if st.session_state.get("_lab_dados_uid") != UID:
        st.session_state._lab_dados = ler_json(FICHEIRO_LAB, {}) if UID else {}
        st.session_state._lab_dados_uid = UID
    return st.session_state._lab_dados


def guardar_lab() -> None:
    if UID:
        escrever_json(FICHEIRO_LAB, lab_dados())


def lab_lista(area: str, tipo: str, maximo: int = 12) -> list:
    lista = lab_dados().setdefault(area, {}).setdefault(tipo, [])
    del lista[:-maximo]
    return lista


def nivel_aluno() -> str:
    nivel = acad.get("nivel") or "não indicado"
    extra = acad.get("curso") or acad.get("area") or ""
    return f"{nivel}{' — ' + extra if extra else ''} ({acad.get('vinculo') or 'Aluno'})"


def ia_json(pedido: str, sistema: str, rotulo: str, tarefa: str = "complexa"):
    with a_pensar(rotulo):
        try:
            return extrair_json(chamar_ia([{"role": "user", "content": pedido}], json_mode=True,
                                          sistema=sistema + FORMATO_EXATO, tarefa=tarefa))
        except (ValueError, json.JSONDecodeError):
            st.error("A IA não devolveu um formato válido. Tenta outra vez.")
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
    return None


def escrever_ia(pedido: str, sistema: str, rotulo: str, web: bool = False, tarefa: str = "complexa") -> str | None:
    """Resposta da IA a aparecer aos poucos (com as fontes da web no fim, se houver)."""
    try:
        r = escrever_fluxo(chamar_ia_stream([{"role": "user", "content": pedido}], sistema=sistema, web=web,
                                            tarefa=tarefa), rotulo)
        r = r if isinstance(r, str) else "".join(map(str, r))
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return None
    fontes = st.session_state.get("_fontes_web") or []
    st.session_state.pop("_aviso_web", None)
    if fontes:
        bloco = "\n\n**Fontes:**\n" + "\n".join(f"- [{escape(t)}]({u})" for t, u in fontes[:8])
        st.markdown(bloco)
        r += bloco
    return r


def fontes_web_tema(tema: str) -> list:
    """Fontes para fundamentar (Tavily, se houver chave; senão Wikipédia/notícias). Só com a pesquisa na web ligada."""
    if not cfg.get("web", True) or not tema.strip():
        return []
    with a_pensar("A procurar fontes", tema[:80]):
        try:
            resultados, _ = pw.pesquisar(lh.consultas_fontes(tema), (cfg.get("chaves") or {}).get("Tavily") or None)
        except Exception:  # noqa: BLE001
            resultados = []
    return resultados[:5]


def mostrar_fontes(resultados: list) -> None:
    if resultados:
        st.markdown("<div class='lb-sec'>Fontes consultadas</div><div class='lb-fontes'>" + "<br>".join(
            f"[{i}] <a href='{escape(r.get('url', ''))}' target='_blank'>{escape(r.get('titulo', ''))}</a>"
            for i, r in enumerate(resultados, 1)) + "</div>", unsafe_allow_html=True)


def badge_certeza(c: str) -> str:
    c = c if c in lh.CERTEZAS else "incerto"
    return f"<span class='lb-certeza {c}'>{escape(lh.CERTEZAS[c])}</span>"


def usar_materiais(ctx: dict, chave: str) -> bool:
    if ctx.get("n_materiais"):
        return st.toggle(f"Usar os materiais da sala ({ctx['n_materiais']})", key=f"{chave}_mat",
                         help="A IA baseia-se nos documentos da sala que podes ver e diz de onde vem cada informação.")
    return False


def texto_de_ficheiro(enviado) -> str:
    """Texto de um PDF, Word, PowerPoint, texto ou imagem (a imagem é lida pela IA)."""
    if not enviado:
        return ""
    lidos = ler_ficheiros([enviado])
    return next(iter(lidos.values()), "") if lidos else ""


def guardados_ui(lista: list, chave: str, rotulo: str = "Anteriores"):
    """Escolher um trabalho guardado (o mais recente primeiro). Devolve o item escolhido ou None."""
    if not lista:
        return None
    ordem = list(reversed(range(len(lista))))
    i = st.selectbox(rotulo, ordem, format_func=lambda k: lista[k].get("titulo") or lista[k].get("tema") or "—",
                     key=f"{chave}_sel")
    return lista[i] if i is not None else None


# ---------------------------------------------------------------- testes (História e Biologia)
def preparar_teste(area: str, ctx: dict) -> None:
    chave = f"tst_{area}_{ctx['chave']}"
    historico = lab_lista(area, "testes", 30)
    dificuldade, fracos = ex.adaptar(historico)
    atual = st.session_state.get(chave)
    if not atual:
        c1, c2 = st.columns([2.2, 1])
        tema = c1.text_input("Tema do teste", key=f"{chave}_tema", placeholder="ex.: Estado Novo" if area == "historia"
                             else "ex.: divisão celular")
        n = c2.number_input("Perguntas", 4, 12, 6, key=f"{chave}_n")
        tipos = st.multiselect("Tipos de pergunta", ex.TIPOS_DA_AREA[area], default=ex.TIPOS_DA_AREA[area],
                               format_func=ex.TIPOS.get, key=f"{chave}_tipos")
        materiais = usar_materiais(ctx, chave)
        if historico:
            st.caption(f":material/insights: Teste adaptado: dificuldade {dificuldade}"
                       + (f" · insiste em {', '.join(fracos)}" if fracos else "") + f" · {len(historico)} teste(s) feito(s).")
        if st.button("Criar teste", type="primary", icon=":material/quiz:", key=f"{chave}_criar",
                     disabled=not (tem_chave and tema.strip() and tipos)):
            fontes = ctx["fontes"](tema) if materiais else ""
            sistema_ = (lh.sistema if area == "historia" else lb.sistema)(nivel_aluno())
            r = ia_json(ex.pedido_teste(area, tema, tipos, n, nivel_aluno(), dificuldade, fracos, fontes), sistema_,
                        "A preparar o teste")
            if r is not None:
                try:
                    st.session_state[chave] = {**ex.validar_teste(r, tipos), "tema": tema.strip()}
                    st.rerun()
                except ValueError as erro:
                    st.error(f"{erro} Tenta outra vez.")
        if not tem_chave:
            st.caption(sem_ia_texto("para criar testes"))
        if historico:
            st.markdown("<div class='lb-sec'>Os teus testes</div>", unsafe_allow_html=True)
            st.dataframe([{"Data": h.get("data", "")[:10], "Tema": h.get("tema"), "Nota": f"{h.get('nota', 0)} %",
                           "A melhorar": ", ".join(h.get("fracos") or []) or "—"} for h in reversed(historico)],
                         hide_index=True, width="stretch")
        return
    st.markdown(f"<div class='lb-cab'><b>{escape(atual['titulo'])}</b><span>{len(atual['perguntas'])} perguntas</span></div>",
                unsafe_allow_html=True)
    correcao = atual.get("correcao")
    if not correcao:
        with st.form(f"{chave}_form", border=False):
            respostas = {}
            for k, p in enumerate(atual["perguntas"], 1):
                with st.container(border=True):
                    st.markdown(f"<div class='lb-tipo'>{k}. {escape(ex.TIPOS[p['tipo']])} · {escape(p['tema'])}</div>",
                                unsafe_allow_html=True)
                    pid = p["id"]
                    if p["tipo"] == "escolha_multipla":
                        st.markdown(f"<div class='lb-q'>{escape(p['pergunta'])}</div>", unsafe_allow_html=True)
                        respostas[pid] = st.radio("Resposta", list(range(len(p["opcoes"]))), index=None,
                                                  format_func=lambda i, p=p: p["opcoes"][i], key=f"{chave}_{pid}",
                                                  label_visibility="collapsed")
                    elif p["tipo"] == "verdadeiro_falso":
                        st.markdown(f"<div class='lb-q'>{escape(p['afirmacao'])}</div>", unsafe_allow_html=True)
                        r_ = st.radio("Resposta", ["Verdadeiro", "Falso"], index=None, horizontal=True,
                                      key=f"{chave}_{pid}", label_visibility="collapsed")
                        respostas[pid] = None if r_ is None else r_ == "Verdadeiro"
                    elif p["tipo"] == "associacao":
                        st.markdown(f"<div class='lb-q'>{escape(p['instrucao'])}</div>", unsafe_allow_html=True)
                        opcoes_b = ex.opcoes_associacao(p)
                        respostas[pid] = {}
                        for j, par in enumerate(p["pares"]):
                            respostas[pid][par["a"]] = st.selectbox(par["a"], [None] + opcoes_b, key=f"{chave}_{pid}_{j}",
                                                                     format_func=lambda o: "— escolhe —" if o is None else o)
                    else:
                        if p.get("documento"):
                            st.markdown(f"<div class='lb-doc'>{escape(p['documento'])}</div>", unsafe_allow_html=True)
                            if p.get("fonte"):
                                st.caption(f"Fonte: {p['fonte']}")
                        if p.get("contexto"):
                            st.markdown(f"<div class='lb-doc'>{escape(p['contexto'])}</div>", unsafe_allow_html=True)
                        if p.get("colunas"):
                            st.caption(p.get("titulo_dados") or "Dados")
                            st.dataframe(pd.DataFrame(p["linhas"], columns=p["colunas"]), hide_index=True)
                        st.markdown(f"<div class='lb-q'>{escape(p['pergunta'])}</div>", unsafe_allow_html=True)
                        respostas[pid] = st.text_area("A tua resposta", key=f"{chave}_{pid}", height=120,
                                                      label_visibility="collapsed", placeholder="Escreve a tua resposta…")
            enviar = st.form_submit_button("Corrigir o teste", type="primary", icon=":material/fact_check:")
        if st.button("Desistir deste teste", key=f"{chave}_sair", type="tertiary", icon=":material/close:"):
            st.session_state.pop(chave, None)
            st.rerun()
        if enviar:
            correcoes = {p["id"]: ex.corrigir_objetiva(p, respostas.get(p["id"])) for p in atual["perguntas"]
                         if p["tipo"] in ex.OBJETIVAS}
            abertas = [p for p in atual["perguntas"] if p["tipo"] not in ex.OBJETIVAS]
            conselhos = []
            if abertas:
                sistema_ = (lh.sistema if area == "historia" else lb.sistema)(nivel_aluno())
                r = ia_json(ex.pedido_correcao(abertas, respostas, nivel_aluno()), sistema_, "A corrigir as respostas")
                if r is None:
                    return
                avaliadas, conselhos = ex.validar_correcao(r, [p["id"] for p in abertas])
                correcoes.update(avaliadas)
            diag = ex.diagnostico(atual["perguntas"], correcoes)
            atual["correcao"] = {"correcoes": correcoes, "diag": diag, "conselhos": conselhos,
                                 "respostas": {k: v for k, v in respostas.items() if not isinstance(v, dict)}}
            historico.append({"data": datetime.now().isoformat(timespec="seconds"), "tema": atual["tema"],
                              "titulo": atual["titulo"], "nota": diag["nota"], "fracos": diag["fracos"],
                              "fortes": diag["fortes"]})
            guardar_lab()
            st.rerun()
        return
    diag = correcao["diag"]
    c1, c2 = st.columns([1, 2.4])
    c1.markdown(f"<div class='lb-sec'>Nota</div><div class='lb-nota'>{diag['nota']}%</div>", unsafe_allow_html=True)
    with c2:
        if diag["fracos"]:
            st.markdown("<div class='lb-sec'>Precisas de melhorar</div>" + "".join(
                f"<span class='lb-chip'>{escape(t)} · {diag['por_tema'][t]}%</span>" for t in diag["fracos"]),
                unsafe_allow_html=True)
        if diag["fortes"]:
            st.markdown("<div class='lb-sec'>Já dominas</div>" + "".join(
                f"<span class='lb-chip'>{escape(t)}</span>" for t in diag["fortes"]), unsafe_allow_html=True)
    for conselho in correcao.get("conselhos") or []:
        st.markdown(f"- {conselho}")
    for k, p in enumerate(atual["perguntas"], 1):
        c = correcao["correcoes"].get(p["id"], {})
        icone = "check_circle" if c.get("certa") else "cancel" if c.get("pontos", 0) < 50 else "error"
        with st.expander(f":material/{icone}: {k}. {curto(p.get('pergunta') or p.get('afirmacao') or p.get('instrucao'), 80)}"
                         f" — {c.get('pontos', 0)} pontos"):
            if c.get("feedback"):
                md(c["feedback"])
            for falta in c.get("faltou") or []:
                st.markdown(f"- Faltou: {falta}")
            if p.get("resposta_modelo"):
                st.caption("Resposta modelo")
                md(p["resposta_modelo"])
    a_, b_ = st.columns(2)
    if a_.button("Novo teste adaptado", type="primary", icon=":material/autorenew:", key=f"{chave}_novo", width="stretch"):
        st.session_state.pop(chave, None)
        st.session_state[f"{chave}_tema"] = atual["tema"]
        st.rerun()
    if b_.button("Fechar", key=f"{chave}_fechar", width="stretch"):
        st.session_state.pop(chave, None)
        st.rerun()


# ---------------------------------------------------------------- História
def historia_explicar(ctx: dict) -> None:
    chave = f"hex_{ctx['chave']}"
    tema = st.text_input("Acontecimento, período ou tema", key=f"{chave}_tema",
                         placeholder="ex.: Revolução Liberal de 1820, Guerra Fria, Descobrimentos portugueses")
    materiais = usar_materiais(ctx, chave)
    guardadas = lab_lista("historia", "explicacoes", 10)
    if st.button("Explicar", type="primary", icon=":material/school:", key=f"{chave}_ir",
                 disabled=not (tem_chave and tema.strip())):
        pedido = lh.pedido_explicacao(tema.strip())
        if materiais:
            pedido = f"<fontes>\n{ctx['fontes'](tema)}\n</fontes>\n\n" + pedido
        texto = escrever_ia(pedido, lh.sistema(nivel_aluno()), "A preparar a explicação", web=bool(cfg.get("web", True)))
        if texto:
            guardadas.append({"tema": tema.strip(), "titulo": tema.strip(), "texto": texto,
                              "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
        return
    if not tem_chave:
        st.caption(sem_ia_texto("para as explicações"))
    item = guardados_ui(guardadas, chave, "Explicações anteriores")
    if item:
        with st.container(border=True):
            md(item["texto"])


def historia_documentos(ctx: dict) -> None:
    chave = f"hdoc_{ctx['chave']}"
    c1, c2 = st.columns([1.6, 1])
    texto = c1.text_area("Documento", key=f"{chave}_txt", height=170,
                         placeholder="Cola aqui o texto do documento (ou carrega um ficheiro ao lado)")
    enviado = c2.file_uploader("Ficheiro (PDF, Word, imagem…)", type=TIPOS_FICHEIRO, key=f"{chave}_up")
    origem = c2.text_input("Origem (opcional)", key=f"{chave}_orig", placeholder="ex.: manual, p. 112")
    guardadas = lab_lista("historia", "documentos", 8)
    if st.button("Analisar o documento", type="primary", icon=":material/plagiarism:", key=f"{chave}_ir",
                 disabled=not (tem_chave and (texto.strip() or enviado))):
        conteudo = texto.strip() or texto_de_ficheiro(enviado)
        if not conteudo.strip():
            st.error("Não consegui ler o documento. Experimenta colar o texto.")
            return
        r = ia_json(lh.pedido_documento(conteudo, origem), lh.sistema(nivel_aluno()), "A analisar o documento")
        if r is not None:
            try:
                analise = lh.validar_documento(r)
            except ValueError as erro:
                st.error(f"{erro} Tenta outra vez.")
                return
            guardadas.append({"titulo": curto(analise["assunto"] or conteudo, 70), "analise": analise,
                              "excerto": conteudo[:1500], "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
            st.session_state[f"{chave}_sel"] = len(guardadas) - 1
            st.rerun()
    item = guardados_ui(guardadas, chave, "Análises")
    if not item:
        return
    a = item["analise"]
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='lb-sec'>Natureza</div>{escape(a['natureza'] or '—')}"
                    f"<div class='lb-sec'>Autor</div>{escape(a['autor']['valor'])}{badge_certeza(a['autor']['certeza'])}"
                    f"<div class='lb-sec'>Data</div>{escape(a['data']['valor'])}{badge_certeza(a['data']['certeza'])}",
                    unsafe_allow_html=True)
        c2.markdown(f"<div class='lb-sec'>Assunto</div>{escape(a['assunto'])}<div class='lb-sec'>Público-alvo</div>"
                    f"{escape(a['publico_alvo'] or '—')}<div class='lb-sec'>Intenção do autor</div>{escape(a['intencao'] or '—')}",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='lb-sec'>Contexto histórico</div>{escape(a['contexto'])}<div class='lb-sec'>Mensagem</div>"
                    f"{escape(a['mensagem'])}", unsafe_allow_html=True)
        if a["relacao"]:
            st.markdown("<div class='lb-sec'>Relação com os acontecimentos</div>", unsafe_allow_html=True)
            for x in a["relacao"]:
                st.markdown(f"- {x}")
        f1, f2, f3 = st.columns(3)
        for col, titulo, lista in ((f1, "Factos", a["factos"]), (f2, "Interpretações", a["interpretacoes"]),
                                   (f3, "Não se pode confirmar", a["nao_confirmado"])):
            with col.container(border=True):
                st.markdown(f"**{titulo}**")
                for x in lista or ["—"]:
                    st.markdown(f"- {x}")
        if a["perguntas_para_pensar"]:
            st.markdown("<div class='lb-sec'>Para pensares</div>", unsafe_allow_html=True)
            for x in a["perguntas_para_pensar"]:
                st.markdown(f"- {x}")


def historia_cronologia(ctx: dict) -> None:
    chave = f"hcr_{ctx['chave']}"
    tema = st.text_input("Tema da cronologia", key=f"{chave}_tema",
                         placeholder="ex.: Implantação da República, Segunda Guerra Mundial, 25 de Abril")
    materiais = usar_materiais(ctx, chave)
    guardadas = lab_lista("historia", "cronologias", 12)
    if st.button("Criar cronologia", type="primary", icon=":material/timeline:", key=f"{chave}_ir",
                 disabled=not (tem_chave and tema.strip())):
        fontes = fontes_web_tema(tema)
        pedido = lh.pedido_cronologia(tema.strip())
        if fontes:
            pedido += "\nResultados da web (usa-os para confirmar as datas):\n" + lh.bloco_fontes(fontes)
        if materiais:
            pedido += f"\n<fontes>\n{ctx['fontes'](tema)}\n</fontes>"
        r = ia_json(pedido, lh.sistema(nivel_aluno()), "A montar a cronologia")
        if r is not None:
            try:
                crono = lh.validar_cronologia(r)
            except ValueError as erro:
                st.error(f"{erro} Tenta outra vez.")
                return
            guardadas.append({**crono, "tema": tema.strip(), "fontes": [{"titulo": f["titulo"], "url": f["url"]} for f in fontes],
                              "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
            st.session_state[f"{chave}_sel"] = len(guardadas) - 1
            st.rerun()
    item = guardados_ui(guardadas, chave, "Cronologias")
    if not item:
        return
    componente("linha", f"{chave}_linha", 480, eventos=[{k: e[k] for k in ("data", "ano", "titulo", "descricao", "categoria")}
                                                         for e in item["eventos"]])
    for e in item["eventos"]:
        with st.expander(f"{e['data']} · {e['titulo']}"):
            st.markdown(f"{escape(e['descricao'])}{badge_certeza(e['certeza'])}", unsafe_allow_html=True)
            if e.get("contexto"):
                st.markdown(f"**Contexto:** {e['contexto']}")
            if e.get("importancia"):
                st.markdown(f"**Importância:** {e['importancia']}")
            if e.get("relacoes"):
                st.markdown("**Relaciona-se com:** " + "; ".join(e["relacoes"]))
    dot = lh.dot_relacoes(item, "#17798A")
    if dot:
        st.markdown("<div class='lb-sec'>Relações entre acontecimentos</div>", unsafe_allow_html=True)
        st.graphviz_chart(dot)
    mostrar_fontes(item.get("fontes") or [])
    st.caption("Datas e factos verificados pela IA com as fontes indicadas; confirma no manual as mais importantes.")


def historia_comparar(ctx: dict) -> None:
    chave = f"hcmp_{ctx['chave']}"
    itens_t = st.text_input("O que queres comparar (separa com ;)", key=f"{chave}_itens",
                            placeholder="ex.: Revolução Francesa; Revolução Russa  ·  Monarquia Constitucional; Estado Novo")
    criterios_t = st.text_input("Critérios (opcional, separa com ;)", key=f"{chave}_crit",
                                placeholder="ex.: causas; protagonistas; regime político; consequências")
    itens = [x.strip() for x in re.split(r";|\bvs\.?\b|\bversus\b", itens_t or "") if x.strip()][:5]
    guardadas = lab_lista("historia", "comparacoes", 10)
    if st.button("Comparar", type="primary", icon=":material/compare_arrows:", key=f"{chave}_ir",
                 disabled=not (tem_chave and len(itens) >= 2)):
        criterios = [x.strip() for x in (criterios_t or "").split(";") if x.strip()][:10]
        fontes = fontes_web_tema(" ".join(itens))
        pedido = lh.pedido_comparacao(itens, criterios)
        if fontes:
            pedido += "\nResultados da web:\n" + lh.bloco_fontes(fontes)
        r = ia_json(pedido, lh.sistema(nivel_aluno()), "A comparar")
        if r is not None:
            try:
                comp = lh.validar_comparacao(r, itens)
            except ValueError as erro:
                st.error(f"{erro} Tenta outra vez.")
                return
            guardadas.append({**comp, "fontes": [{"titulo": f["titulo"], "url": f["url"]} for f in fontes],
                              "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
            st.session_state[f"{chave}_sel"] = len(guardadas) - 1
            st.rerun()
    if itens_t and len(itens) < 2:
        st.caption("Escreve pelo menos duas coisas, separadas por «;».")
    item = guardados_ui(guardadas, chave, "Comparações")
    if not item:
        return
    st.dataframe(lh.tabela_comparacao(item), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        titulo_cartao("Semelhanças")
        for x in item["semelhancas"] or ["—"]:
            st.markdown(f"- {x}")
    with c2.container(border=True):
        titulo_cartao("Diferenças")
        for x in item["diferencas"] or ["—"]:
            st.markdown(f"- {x}")
    if item.get("conclusao"):
        st.markdown(f"**Conclusão.** {item['conclusao']}")
    if item.get("debates"):
        st.markdown("<div class='lb-sec'>Debates entre historiadores</div>", unsafe_allow_html=True)
        for x in item["debates"]:
            st.markdown(f"- {x}")
    mostrar_fontes(item.get("fontes") or [])


def historia_resumos(ctx: dict) -> None:
    chave = f"hres_{ctx['chave']}"
    tema = st.text_input("Tema do resumo", key=f"{chave}_tema", placeholder="ex.: A Primeira República (1910–1926)")
    c1, c2 = st.columns([1.2, 1])
    org = c1.radio("Organizar", list(lh.ORGANIZACAO_RESUMO), format_func=lh.ORGANIZACAO_RESUMO.get, key=f"{chave}_org")
    objetivo = c2.text_input("Objetivo de estudo", key=f"{chave}_obj", placeholder="ex.: teste de sexta, capítulo 4",
                             disabled=org != "objetivo")
    materiais = usar_materiais(ctx, chave)
    if org == "capitulo" and not materiais:
        st.caption("«Por capítulo» funciona com os materiais da sala ligados.")
    guardados = lab_lista("historia", "resumos", 10)
    if st.button("Fazer o resumo", type="primary", icon=":material/summarize:", key=f"{chave}_ir",
                 disabled=not (tem_chave and tema.strip())):
        pedido = lh.pedido_resumo(tema.strip(), org, objetivo)
        if materiais:
            pedido = f"<fontes>\n{ctx['fontes'](tema)}\n</fontes>\n\n" + pedido
        texto = escrever_ia(pedido, lh.sistema(nivel_aluno()), "A escrever o resumo", web=bool(cfg.get("web", True)))
        if texto:
            guardados.append({"titulo": f"{tema.strip()} · {lh.ORGANIZACAO_RESUMO[org].lower()}", "texto": texto,
                              "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
        return
    item = guardados_ui(guardados, chave, "Resumos")
    if item:
        with st.container(border=True):
            md(item["texto"])
        st.download_button("Descarregar (.md)", item["texto"].encode("utf-8"), file_name="resumo.md",
                           icon=":material/download:", key=f"{chave}_dl")


def pagina_lab_historia(secao: str, ctx: dict) -> None:
    {"explicar": historia_explicar, "documentos": historia_documentos, "cronologia": historia_cronologia,
     "comparar": historia_comparar, "resumos": historia_resumos}.get(secao, lambda c: None)(ctx)
    if secao == "testes":
        preparar_teste("historia", ctx)
    elif secao == "mapa":
        pagina_historia("Mapa interativo")


# ---------------------------------------------------------------- Biologia
def biologia_explicar(ctx: dict) -> None:
    chave = f"bex_{ctx['chave']}"
    conceito = st.text_input("Conceito ou pergunta", key=f"{chave}_tema",
                             placeholder="ex.: enzimas, sinapse, sistema imunitário, potencial de ação")
    materiais = usar_materiais(ctx, chave)
    guardadas = lab_lista("biologia", "explicacoes", 10)
    if st.button("Explicar", type="primary", icon=":material/school:", key=f"{chave}_ir",
                 disabled=not (tem_chave and conceito.strip())):
        pedido = lb.pedido_explicacao(conceito.strip())
        if materiais:
            pedido = f"<fontes>\n{ctx['fontes'](conceito)}\n</fontes>\n\n" + pedido
        texto = escrever_ia(pedido, lb.sistema(nivel_aluno()), "A preparar a explicação")
        if texto:
            guardadas.append({"titulo": conceito.strip(), "texto": texto, "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
        return
    item = guardados_ui(guardadas, chave, "Explicações anteriores")
    if item:
        with st.container(border=True):
            md(item["texto"])


def mostrar_processo(proc: dict, chave: str) -> None:
    st.markdown(f"<div class='lb-cab'><b>{escape(proc['nome'])}</b><span>{escape(proc.get('onde') or '')}</span></div>",
                unsafe_allow_html=True)
    if proc.get("resumo"):
        md(proc["resumo"])
    st.graphviz_chart(lb.dot_processo(proc, "#17798A"))
    for i, etapa in enumerate(proc["etapas"], 1):
        titulo, descricao = etapa[0], etapa[1]
        st.markdown(f"<div class='lb-etapa'><i>{i}</i><div><b>{escape(titulo)}</b><br>{escape(descricao)}</div></div>",
                    unsafe_allow_html=True)
    if proc.get("conceitos"):
        st.markdown("<div class='lb-sec'>Conceitos-chave</div>" + "".join(
            f"<span class='lb-chip'>{escape(c)}</span>" for c in proc["conceitos"]), unsafe_allow_html=True)


def divisao_celular(chave: str, tipo: str | None = None) -> None:
    tipo = tipo or st.segmented_control("Divisão", ["mitose", "meiose"], default="mitose", key=f"{chave}_tipo",
                                        format_func=str.capitalize) or "mitose"
    fases = lb.FASES[tipo]
    fase = st.select_slider("Fase", fases, key=f"{chave}_{tipo}_fase")
    i = fases.index(fase) if fase in fases else 0
    st.markdown(lb.svg_divisao(tipo, i), unsafe_allow_html=True)
    st.caption(lb.DESCRICAO_FASES.get((tipo, fases[i]), ""))


def biologia_processos(ctx: dict) -> None:
    chave = f"bpr_{ctx['chave']}"
    opcoes = list(lb.PROCESSOS) + ["_outro"]
    escolha = st.selectbox("Processo", opcoes, key=f"{chave}_proc",
                           format_func=lambda k: "Outro processo (com a IA)…" if k == "_outro" else lb.PROCESSOS[k]["nome"])
    if escolha == "_outro":
        nome = st.text_input("Que processo?", key=f"{chave}_outro", placeholder="ex.: ciclo do azoto, coagulação do sangue")
        guardados = lab_lista("biologia", "processos", 8)
        if st.button("Descrever em etapas", type="primary", icon=":material/route:", key=f"{chave}_ir",
                     disabled=not (tem_chave and nome.strip())):
            r = ia_json(lb.pedido_processo(nome.strip()), lb.sistema(nivel_aluno()), "A organizar as etapas")
            if r is not None:
                try:
                    guardados.append({**lb.validar_processo(r), "titulo": nome.strip()})
                    guardar_lab()
                    st.session_state[f"{chave}_g_sel"] = len(guardados) - 1
                    st.rerun()
                except ValueError as erro:
                    st.error(f"{erro} Tenta outra vez.")
        item = guardados_ui(guardados, f"{chave}_g", "Processos guardados")
        if item:
            mostrar_processo(item, chave)
        return
    proc = lb.PROCESSOS[escolha]
    mostrar_processo(proc, chave)
    if escolha in ("mitose", "meiose"):
        st.markdown("<div class='lb-sec'>Fase a fase</div>", unsafe_allow_html=True)
        divisao_celular(f"{chave}_div", escolha)
    if tem_chave and st.button("Explicar com mais pormenor (IA)", icon=":material/auto_awesome:", key=f"{chave}_mais"):
        escrever_ia(lb.pedido_explicacao(proc["nome"]), lb.sistema(nivel_aluno()), "A explicar")


def biologia_genetica(ctx: dict) -> None:
    chave = f"bgen_{ctx['chave']}"
    parte = st.segmented_control("Ferramenta", ["Exercícios", "Quadro de Punnett", "Do DNA à proteína", "Hardy-Weinberg"],
                                 default="Exercícios", key=f"{chave}_parte") or "Exercícios"
    if parte == "Quadro de Punnett":
        pagina_biologia("Genética (Punnett)")
        return
    if parte == "Do DNA à proteína":
        pagina_biologia("Do DNA à proteína")
        return
    if parte == "Hardy-Weinberg":
        q2 = st.number_input("Frequência do fenótipo recessivo na população (q²)", 0.0, 1.0, 0.04, step=0.01,
                             key=f"{chave}_q2", format="%.4f")
        try:
            r = lb.hardy_weinberg(q2)
            m1, m2, m3 = st.columns(3)
            m1.metric("q (alelo recessivo)", f"{r['q']:.3f}".replace(".", ","))
            m2.metric("p (alelo dominante)", f"{r['p']:.3f}".replace(".", ","))
            m3.metric("Heterozigóticos (2pq)", f"{r['Aa']:.1%}".replace(".", ","))
            st.caption(f"Em equilíbrio: AA = p² = {r['AA']:.3f} · Aa = 2pq = {r['Aa']:.3f} · aa = q² = {r['aa']:.3f}. "
                       "Pressupõe população grande, cruzamentos ao acaso e sem mutação, migração nem seleção.")
        except ValueError as erro:
            st.error(str(erro))
        return
    tipo = st.selectbox("Tipo de exercício", list(lb.TIPOS_GENETICA), format_func=lb.TIPOS_GENETICA.get, key=f"{chave}_tipo")
    atual = st.session_state.get(f"{chave}_ex")
    if not atual or atual["tipo"] != tipo or st.button("Novo exercício", icon=":material/casino:", key=f"{chave}_novo"):
        atual = lb.exercicio_genetica(tipo, random.randrange(1_000_000))
        st.session_state[f"{chave}_ex"] = atual
        st.session_state.pop(f"{chave}_verif", None)
    with st.container(border=True):
        st.markdown(f"<div class='lb-q'>{escape(atual['enunciado'])}</div>", unsafe_allow_html=True)
        resp = st.text_input("A tua resposta (ex.: 1/4, 25 %, 0,25)", key=f"{chave}_resp_{atual['semente']}")
        if st.button("Verificar", type="primary", key=f"{chave}_ver", disabled=not resp.strip()):
            st.session_state[f"{chave}_verif"] = lb.verificar_resposta(atual, resp)
        verif = st.session_state.get(f"{chave}_verif")
        if verif is True:
            st.success(f"Certo! A resposta é {atual['resposta']}.", icon=":material/check_circle:")
        elif verif is False:
            st.error("Ainda não. Vê a resolução passo a passo.", icon=":material/cancel:")
        elif verif is None and f"{chave}_verif" in st.session_state:
            st.warning("Escreve um número: uma fração (1/4), uma percentagem (25 %) ou um decimal (0,25).")
        with st.expander("Resolução passo a passo", expanded=verif is False):
            for i, p_ in enumerate(atual["passos"], 1):
                st.markdown(f"**{i}.** {p_}")


def biologia_experiencias(ctx: dict) -> None:
    chave = f"bexp_{ctx['chave']}"
    c1, c2 = st.columns([1.6, 1])
    texto = c1.text_area("Experiência, protocolo, tabela ou resultados", key=f"{chave}_txt", height=170,
                         placeholder="Descreve a experiência ou cola o protocolo e os resultados…")
    enviado = c2.file_uploader("Ou carrega um ficheiro / fotografia", type=TIPOS_FICHEIRO, key=f"{chave}_up")
    guardadas = lab_lista("biologia", "experiencias", 8)
    if st.button("Interpretar", type="primary", icon=":material/biotech:", key=f"{chave}_ir",
                 disabled=not (tem_chave and (texto.strip() or enviado))):
        conteudo = texto.strip() or texto_de_ficheiro(enviado)
        if not conteudo.strip():
            st.error("Não consegui ler o ficheiro. Experimenta escrever ou colar o texto.")
            return
        r = ia_json(lb.pedido_experiencia(conteudo), lb.sistema(nivel_aluno()), "A interpretar a experiência")
        if r is not None:
            try:
                analise = lb.validar_experiencia(r)
            except ValueError as erro:
                st.error(f"{erro} Tenta outra vez.")
                return
            guardadas.append({"titulo": curto(analise["problema"] or conteudo, 70), "analise": analise,
                              "criado": datetime.now().isoformat(timespec="seconds")})
            guardar_lab()
            st.session_state[f"{chave}_sel"] = len(guardadas) - 1
            st.rerun()
    item = guardados_ui(guardadas, chave, "Interpretações")
    if not item:
        return
    a = item["analise"]
    with st.container(border=True):
        st.markdown(f"<div class='lb-sec'>Problema</div>{escape(a['problema'])}<div class='lb-sec'>Hipótese</div>"
                    f"{escape(a['hipotese'] or '—')}", unsafe_allow_html=True)
        v = a["variaveis"]
        st.dataframe([{"Variável": "Independente (o que se muda)", "Qual": v["independente"] or "—"},
                      {"Variável": "Dependente (o que se mede)", "Qual": v["dependente"] or "—"},
                      {"Variável": "Controladas (mantêm-se iguais)", "Qual": "; ".join(v["controladas"]) or "—"}],
                     hide_index=True, width="stretch")
        if a["controlo"]:
            st.markdown(f"**Controlo:** {a['controlo']}")
        for titulo, lista in (("Procedimento", a["procedimento"]), ("Conclusões", a["conclusoes"]),
                              ("Possíveis erros experimentais", a["erros"]), ("Como melhorar", a["melhorias"]),
                              ("O que não se pode concluir com estes dados", a["falta_informacao"])):
            if lista:
                st.markdown(f"<div class='lb-sec'>{titulo}</div>", unsafe_allow_html=True)
                for x in lista:
                    st.markdown(f"- {x}")
        if a["resultados"]:
            st.markdown(f"<div class='lb-sec'>Resultados</div>{escape(a['resultados'])}", unsafe_allow_html=True)


def biologia_dados(ctx: dict) -> None:
    import altair as alt

    chave = f"bdad_{ctx['chave']}"
    enviado = st.file_uploader("Tabela (CSV ou Excel) ou imagem de um gráfico", type=["csv", "xlsx"] + TIPOS_IMAGEM,
                               key=f"{chave}_up")
    descricao = st.text_input("O que mostram os dados? (opcional)", key=f"{chave}_desc",
                              placeholder="ex.: taxa de fotossíntese a diferentes intensidades de luz")
    if not enviado:
        st.caption("Carrega uma tabela para ver o gráfico, os números principais e a interpretação, ou uma fotografia de "
                   "um gráfico do manual.")
        return
    nome = enviado.name.lower()
    if nome.endswith((".csv", ".xlsx")):
        try:
            df = pd.read_csv(enviado, sep=None, engine="python") if nome.endswith(".csv") else pd.read_excel(enviado)
        except Exception as erro:  # noqa: BLE001
            st.error(f"Não consegui ler a tabela ({erro}).")
            return
        df = df.dropna(how="all").head(500)
        st.dataframe(df, hide_index=True, width="stretch")
        numericas = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(df.columns) >= 2 and numericas:
            c1, c2 = st.columns(2)
            x = c1.selectbox("Eixo dos x", list(df.columns), key=f"{chave}_x")
            ys = c2.multiselect("Eixo dos y", [c for c in numericas if c != x], default=[c for c in numericas if c != x][:2],
                                key=f"{chave}_y")
            if ys:
                longo = df[[x] + ys].melt(x, var_name="série", value_name="valor")
                tipo_x = "Q" if pd.api.types.is_numeric_dtype(df[x]) else "N"
                graf = alt.Chart(longo).mark_line(point=True, strokeWidth=2.2).encode(
                    x=alt.X(f"{x}:{tipo_x}", title=str(x)), y=alt.Y("valor:Q", title=None),
                    color=alt.Color("série:N", legend=alt.Legend(orient="top", title=None)),
                    tooltip=[f"{x}:{tipo_x}", "série:N", "valor:Q"])
                st.altair_chart(grafico_tema(graf), theme=None, width="stretch")
        colunas = [str(c) for c in df.columns]
        linhas = df.astype(object).where(df.notna(), None).values.tolist()
        est = lb.estatisticas(colunas, linhas)
        if est:
            st.dataframe([{"Coluna": c, "Mínimo": v["min"], "Máximo": v["max"], "Média": v["media"],
                           **({"Tendência": next((f"{x_:+.3g} por unidade" for k_, x_ in v.items() if k_.startswith("declive")), "—")})}
                          for c, v in est.items()], hide_index=True, width="stretch")
        if st.button("Interpretar os dados", type="primary", icon=":material/insights:", key=f"{chave}_ir",
                     disabled=not tem_chave):
            escrever_ia(lb.pedido_dados(descricao, colunas, linhas, est), lb.sistema(nivel_aluno()), "A interpretar")
    else:
        st.image(enviado.getvalue(), width="stretch")
        if st.button("Interpretar o gráfico", type="primary", icon=":material/insights:", key=f"{chave}_ir_img",
                     disabled=not tem_chave):
            with a_pensar("A ler o gráfico"):
                try:
                    lido = extrair_imagem(enviado.name, enviado.getvalue())
                except Exception as erro:  # noqa: BLE001
                    mostrar_erro(erro)
                    return
            escrever_ia(lb.pedido_dados(descricao + "\nDescrição do gráfico lida da imagem:\n" + lido, ["(da imagem)"], [], {}),
                        lb.sistema(nivel_aluno()), "A interpretar")


def biologia_glossario(ctx: dict) -> None:
    chave = f"bglo_{ctx['chave']}"
    dados = lab_dados().setdefault("biologia", {})
    glossario = dados.setdefault("glossario", [])
    c1, c2, c3 = st.columns([2.2, 0.8, 1], vertical_alignment="bottom")
    tema = c1.text_input("Juntar conceitos sobre", key=f"{chave}_tema", placeholder="ex.: célula eucariótica, genética")
    n = c2.number_input("Quantos", 4, 20, 8, key=f"{chave}_n")
    if c3.button("Juntar", type="primary", icon=":material/add:", key=f"{chave}_ir", width="stretch",
                 disabled=not (tem_chave and tema.strip())):
        r = ia_json(lb.pedido_glossario(tema.strip(), int(n)), lb.sistema(nivel_aluno()), "A escrever o glossário",
                    tarefa="simples")
        if r is not None:
            try:
                dados["glossario"] = lb.juntar_glossario(glossario, lb.validar_glossario(r))
                guardar_lab()
                st.rerun()
            except ValueError as erro:
                st.error(f"{erro} Tenta outra vez.")
    if not glossario:
        st.markdown("<div class='mi-vazio'><b>O teu glossário está vazio</b>Junta conceitos de um tema e eles ficam "
                    "aqui, por ordem alfabética, para pesquisares e reveres.</div>", unsafe_allow_html=True)
        return
    filtro = st.text_input("Pesquisar no glossário", key=f"{chave}_filtro", placeholder="Pesquisar",
                           label_visibility="collapsed", icon=":material/search:")
    alvo = dz.termos(filtro) if filtro else []
    for i, e in enumerate(glossario):
        texto = f"{e['conceito']} {e['definicao']} {' '.join(e['relacionados'])}"
        if alvo and not all(t in dz._sem_acentos(texto) for t in alvo):
            continue
        with st.container(border=True):
            a_, b_ = st.columns([12, 1])
            a_.markdown(f"**{escape(e['conceito'])}** — {escape(e['definicao'])}")
            if e.get("exemplo"):
                a_.caption(f"Exemplo: {e['exemplo']}")
            if e.get("relacionados"):
                a_.markdown("".join(f"<span class='lb-chip'>{escape(r)}</span>" for r in e["relacionados"]),
                            unsafe_allow_html=True)
            if b_.button("", icon=":material/delete:", key=f"{chave}_del_{i}", type="tertiary", help="Tirar do glossário"):
                glossario.pop(i)
                guardar_lab()
                st.rerun()
    st.download_button("Descarregar o glossário (CSV)", pd.DataFrame(glossario).to_csv(index=False).encode("utf-8"),
                       file_name="glossario_biologia.csv", icon=":material/download:", key=f"{chave}_dl")


def biologia_simulacoes(ctx: dict) -> None:
    chave = f"bsim_{ctx['chave']}"
    escolha = st.segmented_control("Simulação", ["Divisão celular", "Osmose", "Pedir à IA"], default="Divisão celular",
                                   key=f"{chave}_qual") or "Divisão celular"
    if escolha == "Divisão celular":
        st.caption("Avança fase a fase numa célula com 2n = 4 (dois pares de cromossomas homólogos).")
        divisao_celular(chave)
    elif escolha == "Osmose":
        st.caption("Muda a quantidade de soluto de cada lado da membrana semipermeável e observa para onde vai a água.")
        componente("simulacao", f"{chave}_osmose", 420, html=lb.SIMULACAO_OSMOSE)
    else:
        guardadas = lab_lista("biologia", "simulacoes", 4)
        pedido = st.text_input("Que processo queres ver?", key=f"{chave}_pedido",
                               placeholder="ex.: potencial de ação num neurónio, crescimento de uma população")
        if st.button("Criar simulação", type="primary", icon=":material/auto_awesome:", key=f"{chave}_ir",
                     disabled=not (tem_chave and pedido.strip())):
            with a_pensar("A criar a simulação"):
                try:
                    modelo = gerar_modelo_lab("biologia", pedido.strip(), "", "Faz uma simulação interativa.")
                    guardadas.append({**modelo, "titulo": modelo.get("titulo") or pedido.strip()})
                    guardar_lab()
                    st.session_state[f"{chave}_g_sel"] = len(guardadas) - 1
                    st.rerun()
                except (ValueError, json.JSONDecodeError):
                    st.error("Não consegui fazer a simulação desta vez. Tenta pedir de outra forma.")
                except Exception as erro:  # noqa: BLE001
                    mostrar_erro(erro)
        item = guardados_ui(guardadas, f"{chave}_g", "Simulações criadas")
        if item:
            if item.get("como_usar"):
                st.caption(item["como_usar"])
            if item.get("tipo") == "simulacao":
                componente("simulacao", f"{chave}_ia", 440, html=item.get("html", ""))
            elif item.get("tipo") == "diagrama":
                st.graphviz_chart(dot_diagrama(item, CORES_LAB["biologia"]))


def pagina_lab_biologia(secao: str, ctx: dict) -> None:
    {"explicar": biologia_explicar, "processos": biologia_processos, "genetica": biologia_genetica,
     "experiencias": biologia_experiencias, "dados": biologia_dados, "glossario": biologia_glossario,
     "simulacoes": biologia_simulacoes}.get(secao, lambda c: None)(ctx)
    if secao == "testes":
        preparar_teste("biologia", ctx)


# ---------------------------------------------------------------- o Laboratório dentro da sala
def fontes_da_sala(backend, sala: dict, consulta: str, limite: int = 30_000) -> str:
    try:
        ficheiros = backend.ficheiros(sala["id"])  # só os que esta pessoa pode ver
    except Exception:  # noqa: BLE001
        return ""
    texto, _ = dz.selecionar_relevante({f["nome"]: f.get("texto_extraido") or "" for f in ficheiros}, consulta, limite,
                                       TAMANHO_BLOCO)
    return texto


def laboratorio_da_sala(backend, sala: dict) -> None:
    import salas as sl

    st.markdown(estilos(ESTILO_LAB, ESTILO_LAB_SALA), unsafe_allow_html=True)
    por_area = sl.ferramentas_por_area(sala.get("ferramentas_lab"))
    if not por_area:
        st.info("O Laboratório desta sala ainda não tem ferramentas." + (" Escolhe-as nas Definições da sala."
                if sala.get("e_criador") else ""), icon=":material/science:")
        return
    areas = list(por_area)
    area = areas[0]
    if len(areas) > 1:
        area = st.segmented_control("Área", areas, default=areas[0], key=f"slab_area_{sala['id']}",
                                    format_func=lambda a: f"{sl.LABORATORIO[a][1]} {sl.LABORATORIO[a][0]}",
                                    label_visibility="collapsed") or areas[0]
    ferramentas = por_area[area]
    nomes = sl.LABORATORIO[area][2]
    icones = {**{k: v[1] for k, v in lh.SECOES.items()}} if area == "historia" else \
        {**{k: v[1] for k, v in lb.SECOES.items()}} if area == "biologia" else {}
    ferramenta = ferramentas[0]
    if len(ferramentas) > 1:
        ferramenta = st.segmented_control("Ferramenta", ferramentas, default=ferramentas[0],
                                          key=f"slab_f_{sala['id']}_{area}", label_visibility="collapsed",
                                          format_func=lambda f: f"{icones.get(f, '')} {nomes[f]}".strip()) or ferramentas[0]
    try:
        n_materiais = len(backend.ficheiros(sala["id"]))
    except Exception:  # noqa: BLE001
        n_materiais = 0
    ctx = {"sala": sala, "chave": sala["id"][:8], "n_materiais": n_materiais,
           "fontes": lambda consulta: fontes_da_sala(backend, sala, consulta)}
    if not tem_chave and ferramenta not in ("tabela", "massa", "equacoes", "moleculas", "graficos2d", "graficos3d",
                                            "python", "genetica", "processos", "simulacoes", "mapa"):
        st.info(sem_ia_texto("para usar esta ferramenta"), icon=":material/key:")
    if area == "historia":
        pagina_lab_historia(ferramenta, ctx)
    elif area == "biologia":
        pagina_lab_biologia(ferramenta, ctx)
    elif ferramenta == "ia":
        ia_do_laboratorio(area)
    elif area == "quimica":
        pagina_quimica({"tabela": "Tabela periódica", "massa": "Massa molar", "equacoes": "Acertar equações",
                        "moleculas": "Moléculas 3D"}[ferramenta])
    elif area == "matematica":
        pagina_matematica("Gráficos 2D" if ferramenta == "graficos2d" else "Gráficos 3D")
    elif area == "programacao":
        pagina_programacao()


def campos_laboratorio(prefixo: str, atual: dict) -> dict:
    """«Ativar Laboratório nesta sala» e as ferramentas (as que existem na app), por área."""
    import salas as sl

    lab_on = st.toggle("Ativar Laboratório nesta sala", value=bool(atual.get("laboratorio")), key=f"{prefixo}_lab",
                       help="Ferramentas de estudo por área (História, Biologia, Química…) dentro da sala, para todos os "
                            "membros. Desligado, a sala fica sem elas.")
    escolhidas = []
    if lab_on:
        st.caption("Escolhe as ferramentas que os membros vão ter. Podes mudar depois nas Definições da sala.")
        atuais = set(atual.get("ferramentas_lab") or [])
        colunas = st.columns(2)
        for k, (area, (nome, icone, ferramentas)) in enumerate(sl.LABORATORIO.items()):
            with colunas[k % 2].container(border=True):
                ja = [f"{area}.{f}" for f in ferramentas if f"{area}.{f}" in atuais]
                ativo = st.checkbox(f"{icone} {nome}", value=bool(ja), key=f"{prefixo}_lab_{area}")
                if ativo:
                    escolhidas += st.multiselect(
                        f"Ferramentas de {nome}", [f"{area}.{f}" for f in ferramentas],
                        default=ja or [f"{area}.{f}" for f in ferramentas], format_func=sl.nome_ferramenta,
                        key=f"{prefixo}_labf_{area}", label_visibility="collapsed")
    return {"laboratorio": lab_on, "ferramentas_lab": escolhidas if lab_on else list(atual.get("ferramentas_lab") or [])}


# =============================================================== SALAS
SISTEMA_SALA = (
    "És o assistente de uma sala de estudo. Respondes APENAS com base nos materiais da sala entre <fontes></fontes> "
    "(texto de documentos e fotografias). Indicas a origem de cada informação entre parênteses retos, por exemplo "
    "[nome do ficheiro]. Se a resposta não estiver nos materiais, dizes que não está nos materiais da sala. "
    "Explicas de forma simples, calma e com exemplos. " + mt.REGRAS_FORMULAS
)


def link_da_sala(codigo: str) -> str:
    import salas as sl

    return sl.link_convite(cfg.get("url_publica") or "http://localhost:8501", codigo)


def ecra_contas(backend, titulo: str = "Entra para usar as Salas") -> None:
    import salas_backend as sb

    st.markdown(f"#### {titulo}")
    if backend.nome == "local":
        botoes_login("contas")
    entrar_t, criar_t = st.tabs(["Entrar", "Criar conta"])
    with entrar_t:
        with st.form("form_entrar_salas", border=False):
            email = st.text_input("Email", key="salas_email_e")
            pp = st.text_input("Palavra-passe", type="password", key="salas_pp_e")
            if st.form_submit_button("Entrar", type="primary", width="stretch"):
                try:
                    backend.entrar(email, pp)
                    st.rerun()
                except sb.ErroSalas as erro:
                    st.error(str(erro))
    with criar_t:
        with st.form("form_criar_conta_salas", border=False):
            nome = st.text_input("Nome", value=perfil.get("nome", ""))
            email = st.text_input("Email", key="salas_email_c")
            pp = st.text_input("Palavra-passe (mínimo 8 caracteres)", type="password", key="salas_pp_c")
            vinculo = st.radio("És", ["Aluno", "Professor"], horizontal=True,
                               index=1 if acad.get("vinculo") == "Professor" else 0)
            if st.form_submit_button("Criar conta", type="primary", width="stretch"):
                try:
                    backend.registar(email, pp, nome, vinculo)
                    st.rerun()
                except sb.ErroSalas as erro:
                    st.error(str(erro))


def campos_regras_sala(prefixo: str, atual: dict) -> dict:
    """Os controlos das regras da sala (iguais ao criar e nas definições). Só o criador os vê."""
    import salas as sl

    st.markdown("**Funcionalidades e regras** <span class='ec-meta'>— só quem cria a sala as pode mudar</span>",
                unsafe_allow_html=True)
    chat = st.radio("Conversa entre membros", list(sl.CHAT_MODOS), format_func=sl.CHAT_MODOS.get, horizontal=True,
                    index=list(sl.CHAT_MODOS).index(atual.get("chat_modo", "todos")), key=f"{prefixo}_chat",
                    help="«Só eu escrevo» serve para avisos: os membros leem, mas não escrevem.")
    publica = st.radio("Quem pode pôr documentos nos materiais da sala", list(sl.QUEM_PUBLICA), format_func=sl.QUEM_PUBLICA.get,
                       horizontal=True, index=list(sl.QUEM_PUBLICA).index(atual.get("quem_publica", "todos")),
                       key=f"{prefixo}_publica", help="Os documentos dos materiais são vistos por todos os membros.")
    convites = st.radio("Quem pode ver o código de convite", list(sl.QUEM_CONVIDA), format_func=sl.QUEM_CONVIDA.get,
                        horizontal=True, index=list(sl.QUEM_CONVIDA).index(atual.get("convites", "todos")), key=f"{prefixo}_conv")
    c1, c2 = st.columns(2)
    privados = c1.toggle("Ficheiros privados de cada membro", value=atual.get("ficheiros_privados", True), key=f"{prefixo}_priv",
                         help="Cada membro pode juntar ficheiros só seus: ninguém mais os vê, só o assistente dessa pessoa.")
    assistente = c2.toggle("Assistente de IA da sala", value=atual.get("assistente_ativo", True), key=f"{prefixo}_ia",
                           help="Responde a perguntas só com os materiais da sala (e os ficheiros privados de quem pergunta).")
    return {"chat_modo": chat, "quem_publica": publica, "convites": convites, "ficheiros_privados": privados,
            "assistente_ativo": assistente}


def campo_icone_sala(pre: str, atual: str = "") -> str:
    """Escolha do ícone da sala: «Automático» (pelo nome) ou um dos ícones do catálogo."""
    import salas as sl

    opcoes = [""] + list(sl.ICONES_SALA)
    escolha = st.pills("Ícone", opcoes, default=atual if atual in opcoes else "", key=f"{pre}_icone",
                       format_func=lambda k: ":material/auto_awesome: Automático" if not k
                       else f":material/{sl.ICONES_SALA[k][0]}:",
                       help="Sem escolha, a sala recebe um ícone pelo nome (por exemplo, «Álgebra» → funções).")
    if escolha:
        st.caption(f"Ícone escolhido: {sl.ICONES_SALA[escolha][1]}")
    return escolha or ""


def campos_aparencia_sala(pre: str, nome: str, atual: dict, tipo: str = "grupo_estudo") -> tuple[str, str]:
    """Ícone e cor da sala, com a sala como vai aparecer (o cartão muda logo ao escolher). Devolve (cor, ícone)."""
    import salas as sl

    cores = list(sl.CORES_SALA)
    cor_atual = atual.get("cor") if atual.get("cor") in cores else ""
    with st.container(key=f"corsala_{pre}"):  # cada cor com a sua bolinha (as cores vão no estilo da pré-visualização)
        cor = st.pills("Cor", cores, default=cor_atual or None, key=f"{pre}_cor", format_func=str.capitalize) or cor_atual
    icone = campo_icone_sala(pre, atual.get("icone") or "")
    previa = {"nome": nome or "A tua sala", "descricao": atual.get("descricao") or "", "tipo": tipo, "icone": icone,
              "cor": cor or ("" if atual.get("cor_hex") else "turquesa"), "cor_hex": "" if cor else atual.get("cor_hex", "")}
    cores_css = "".join(f".st-key-corsala_{pre} [data-testid='stButtonGroup'] button:nth-child({i + 1}){{--c:{sl.CORES_SALA[c]}}}"
                        for i, c in enumerate(cores))
    st.markdown(f"<style>{cores_css}</style><div class='cs-previa'>{ico_sala_html(previa)}<div class='mi-encolhe'><b>{escape(previa['nome'])}</b>"
                f"<span>Assim fica a sala nas Salas e na barra lateral</span></div></div>", unsafe_allow_html=True)
    return cor, icone


@st.dialog("Criar sala", width="large")
def dialogo_criar_sala(backend, utilizador: dict) -> None:
    import salas as sl
    import salas_backend as sb

    e_prof = (utilizador or {}).get("vinculo") == "Professor"
    tipos = {"pessoal": (":material/person:", "Só para mim",
                         "Para preparares as aulas: juntas os teus materiais e a IA ajuda com resumos, fichas e testes."
                         if e_prof else "Juntas as fontes de uma cadeira e tens conversa com elas, resumos, quizzes, "
                                        "flashcards e um plano de estudo."),
             "partilhada": (":material/co_present:", "Turma",
                            "Os alunos entram com o código e encontram os materiais, os avisos e um assistente que "
                            "responde com eles.") if e_prof else
                           (":material/groups:", "Com colegas",
                            "Partilham materiais, conversam e têm um assistente que responde com o que está na sala.")}
    ordem = ["partilhada", "pessoal"] if e_prof else ["pessoal", "partilhada"]
    if not utilizador:
        ordem = ["pessoal"]
    escolha = st.radio("Para quem é a sala?", ordem, key="cs_tipo", format_func=lambda k: f"{tipos[k][0]} {tipos[k][1]}",
                       captions=[tipos[k][2] for k in ordem])
    pessoal = escolha == "pessoal"
    tipo_backend = "cadeira" if pessoal else sl.tipo_de_sala_permitido((utilizador or {}).get("vinculo", "Aluno"))
    padrao = sl.definicoes_padrao(tipo_backend)
    c1, c2 = st.columns([1.4, 1]) if (e_prof and not pessoal) else (st.container(), None)
    nome = c1.text_input("Nome da sala", max_chars=80, key="cs_nome",
                         placeholder=("ex.: Álgebra Linear – Turma 2" if e_prof and not pessoal else
                                      "ex.: Preparar Álgebra Linear" if e_prof else
                                      "ex.: Álgebra Linear" if pessoal else "ex.: Grupo de Álgebra"))
    cadeira = c2.text_input("Cadeira", placeholder="ex.: Álgebra Linear", key="cs_cadeira") if c2 else None
    descricao = st.text_input("Descrição (opcional)", max_chars=300, key="cs_desc",
                              placeholder="O que vais estudar, objetivos…" if pessoal else "Para que é a sala, horários, regras…")
    with st.container(border=True, key="cs_aparencia"):
        titulo_cartao("Aparência")
        cor, icone = campos_aparencia_sala("cs", nome, {"descricao": descricao, "cor": "" if pessoal else padrao["cor"],
                                                        "cor_hex": cor_cadeira(nome or "nova") if pessoal else ""},
                                           tipo_backend)
    regras, lab_cfg = {}, {}
    if not pessoal:
        with st.expander("Regras e Laboratório", icon=":material/tune:"):
            regras = campos_regras_sala("cs", padrao)
            st.divider()
            titulo_cartao("Laboratório")
            lab_cfg = campos_laboratorio("cs", padrao)
    if st.button("Criar sala", type="primary", icon=":material/add:", width="stretch", key="cs_criar"):
        try:
            if pessoal:
                if nome and " ".join(nome.split()) in st.session_state.cadeiras:
                    raise sb.ErroSalas("Já tens uma sala só tua com esse nome.")
                nome_final = criar_sala_pessoal(nome, cor=cor or None, icone=icone or None,
                                                descricao=" ".join(descricao.split()) or None)
                st.session_state.cal_msg = "Sala criada. Junta as fontes (apontamentos, slides, sebentas) para começar."
                ir("cadeira", cadeira_atual=nome_final)
            nova = backend.criar_sala(nome, cadeira=cadeira, descricao=descricao, cor=cor or padrao["cor"], icone=icone,
                                      **(regras or {k: padrao[k] for k in ("chat_modo", "quem_publica", "convites",
                                                                            "ficheiros_privados", "assistente_ativo")}),
                                      **(lab_cfg or {"laboratorio": padrao.get("laboratorio", False),
                                                     "ferramentas_lab": padrao.get("ferramentas_lab", [])}))
            st.session_state.sala_aberta = nova["id"]
            st.session_state.cal_msg = ("Turma criada. Partilha o código com os teus alunos (separador Membros)." if e_prof
                                        else "Sala criada. Convida os colegas com o código (separador Membros).")
            st.rerun()
        except sb.ErroSalas as erro:
            st.error(str(erro))


@janela("Definições da sala", width="large")
def dialogo_definicoes_pessoal(nome_sala: str) -> None:
    """Definições de uma sala só tua: nome, aparência, descrição, objetivo e apagar."""
    import salas_backend as sb

    d = st.session_state.cadeiras[nome_sala]
    pre = f"dp_{chave_curta(nome_sala)}"
    nome = st.text_input("Nome da sala", value=nome_sala, max_chars=80, key=f"{pre}_nome")
    descricao = st.text_input("Descrição", value=d.get("descricao") or "", max_chars=300, key=f"{pre}_desc",
                              placeholder="O que vais estudar, objetivos…")
    with st.container(border=True):
        titulo_cartao("Aparência")
        cor, icone = campos_aparencia_sala(pre, nome, {**sala_pessoal(nome_sala), "descricao": descricao}, "cadeira")
    with st.container(border=True):
        titulo_cartao("Objetivo")
        obj = objetivo(d)
        c1, c2 = st.columns(2)
        nota = c1.number_input("Nota que queres tirar", 10, 20, int(obj.get("nota_alvo") or 14), key=f"{pre}_nota")
        dif = c2.segmented_control("Como sentes a matéria", DIFICULDADES, key=f"{pre}_dif",
                                   default=obj.get("dificuldade") if obj.get("dificuldade") in DIFICULDADES else "Média")
    if st.button("Guardar", type="primary", width="stretch", key=f"{pre}_guardar"):
        try:
            d.update({"cor": cor or d.get("cor") or "", "icone": icone, "descricao": " ".join(descricao.split())})
            d["objetivo"] = {**obj, "nota_alvo": int(nota), "dificuldade": dif or obj.get("dificuldade") or "Média"}
            guardar(nome_sala)
            novo = renomear_sala_pessoal(nome_sala, nome)
            st.session_state.cadeira_atual = novo
            st.session_state.cal_msg = "Definições da sala guardadas."
            st.rerun()
        except sb.ErroSalas as erro:
            st.error(str(erro))
    n_aval = len(repo().da_cadeira(nome_sala))
    with st.expander("Apagar a sala", icon=":material/delete:"):
        st.caption("Apaga as fontes, os flashcards, os quizzes e o plano desta sala" +
                   (f", e {'a avaliação' if n_aval == 1 else f'as {n_aval} avaliações'} dela no calendário." if n_aval else ".")
                   + " Não pode ser desfeito.")
        if st.checkbox("Quero apagar esta sala", key=f"{pre}_conf_apagar") and \
                st.button("Apagar sala", type="primary", key=f"{pre}_apagar"):
            repo().apagar_da_cadeira(nome_sala)
            apagar_ficheiro_utilizador(caminho_cadeira(nome_sala))
            del st.session_state.cadeiras[nome_sala]
            st.session_state.cal_msg = "Sala apagada."
            ir("salas")


@st.dialog("Entrar numa sala")
def dialogo_entrar_sala(backend) -> None:
    import salas_backend as sb

    st.caption("Escreve o código que te deram (ou abre o link de convite).")
    codigo = st.text_input("Código da sala", placeholder="ex.: K7P2QX", max_chars=12, key="es_codigo")
    if st.button("Entrar", type="primary", width="stretch"):
        try:
            st.session_state.sala_aberta = backend.entrar_com_codigo(codigo)["id"]
            st.rerun()
        except sb.ErroSalas as erro:
            st.error(str(erro))


@st.dialog("Definições da sala", width="large")
def dialogo_definicoes_sala(backend, sala: dict) -> None:
    import salas as sl
    import salas_backend as sb

    pre = f"ds_{sala['id']}"
    nome = st.text_input("Nome da sala", value=sala["nome"], max_chars=80, key=f"{pre}_nome")
    descricao = st.text_input("Descrição", value=sala.get("descricao") or "", max_chars=300, key=f"{pre}_desc")
    with st.container(border=True):
        titulo_cartao("Aparência")
        cor, icone = campos_aparencia_sala(pre, nome, {**sala, "descricao": descricao, "cor": sala.get("cor") or "terracota"},
                                           sala.get("tipo", "grupo_estudo"))
    aviso = st.text_area("Aviso fixo (aparece no topo da sala para todos)", value=sala.get("aviso") or "", max_chars=500,
                         height=80, key=f"{pre}_aviso", placeholder="ex.: O teste é na sexta às 10h, sala 2.3")
    regras = campos_regras_sala(pre, sala)
    entrada = st.toggle("Aceitar novos membros com o código", value=sala.get("entrada_aberta", True), key=f"{pre}_entrada",
                        help="Desliga para fechar a sala: quem já está continua, mas o código deixa de deixar entrar.")
    with st.container(border=True):
        titulo_cartao("Laboratório")
        lab_cfg = campos_laboratorio(pre, sala)
    if st.button("Guardar", type="primary", width="stretch", key=f"{pre}_guardar"):
        try:
            backend.atualizar_sala(sala["id"], nome=nome, descricao=descricao, cor=cor, icone=icone, aviso=aviso,
                                   entrada_aberta=entrada, **regras, **lab_cfg)
            st.session_state.cal_msg = "Definições da sala guardadas."
            st.rerun()
        except sb.ErroSalas as erro:
            st.error(str(erro))
    with st.expander("Apagar a sala", icon=":material/delete:"):
        st.caption("Apaga a sala para todos, com os materiais e as mensagens. Não dá para desfazer.")
        if st.checkbox("Quero apagar esta sala", key=f"{pre}_conf") and st.button("Apagar sala", type="primary", key=f"{pre}_apagar"):
            backend.apagar_sala(sala["id"])
            st.session_state.pop("sala_aberta", None)
            st.session_state.cal_msg = "Sala apagada."
            st.rerun()


def lista_documentos(backend, lista: list, prefixo: str) -> None:
    import salas_backend as sb

    if not lista:
        st.caption("Ainda não há nada aqui.")
        return
    pedido = st.session_state.get("sala_dl")
    for f in lista:
        a, b, c = st.columns([7, 1, 1], vertical_alignment="center")
        data = str(f.get("enviado_em", ""))[:10]
        a.markdown(f"<div class='sl-doc'><b title='{escape(f['nome'])}'>{escape(f['nome'])}</b>"
                   f"<span>{escape(f.get('dono_nome', ''))} · {data}</span></div>", unsafe_allow_html=True)
        if pedido == f["id"]:
            try:
                b.download_button("", backend.dados_ficheiro(f["id"]), file_name=f["nome"], icon=":material/download:",
                                  key=f"dl_{prefixo}_{f['id']}", help="Guardar no computador", type="primary")
            except sb.ErroSalas as erro:
                st.error(str(erro))
        elif b.button("", icon=":material/download:", key=f"dlp_{prefixo}_{f['id']}", type="tertiary", help="Descarregar"):
            st.session_state.sala_dl = f["id"]
            st.rerun()
        if f.get("pode_apagar") and c.button("", icon=":material/delete:", key=f"apagar_f_{f['id']}", type="tertiary",
                                             help="Apagar"):
            try:
                backend.apagar_ficheiro(f["id"])
                st.toast(f"«{f['nome']}» apagado.", icon=":material/delete:")
                st.rerun()
            except sb.ErroSalas as erro:
                st.error(str(erro))


def enviar_para_sala(backend, sala: dict, enviados, partilhado: bool) -> None:
    import salas_backend as sb

    with a_pensar("A ler os documentos"):
        lidos = ler_ficheiros(enviados)
        n = 0
        for f in enviados:
            if f.name in lidos:
                try:
                    backend.enviar_ficheiro(sala["id"], f.name, f.getvalue(), getattr(f, "type", "") or "", partilhado, lidos[f.name])
                    n += 1
                except sb.ErroSalas as erro:
                    st.error(str(erro))
    st.session_state.versao_upload += 1
    if n:
        st.toast(f"{n} documento(s) adicionado(s).", icon=":material/check_circle:")
        st.rerun()


def materiais_da_sala(backend, sala: dict) -> None:
    import salas as sl

    eu = backend.atual()["id"]
    ficheiros = backend.ficheiros(sala["id"])
    partilhados = [f for f in ficheiros if f["pasta_fixa"]]
    privados = [f for f in ficheiros if not f["pasta_fixa"]]
    colunas = st.columns(2 if sl.pode_ter_privados(sala) else 1, gap="medium")
    with colunas[0].container(border=True):
        st.markdown(f"**Materiais da sala** <span class='ec-meta'>· {len(partilhados)} · todos os membros veem</span>",
                    unsafe_allow_html=True)
        lista_documentos(backend, partilhados, "p")
        if sl.pode_partilhar(sala, eu):
            enviados = st.file_uploader("Partilhar documentos com a sala", type=TIPOS_FICHEIRO, accept_multiple_files=True,
                                        key=f"up_sala_p_{sala['id']}_{st.session_state.versao_upload}")
            if enviados:
                enviar_para_sala(backend, sala, enviados, True)
        else:
            st.caption("Nesta sala só quem a criou põe documentos aqui.")
    if sl.pode_ter_privados(sala):
        with colunas[1].container(border=True):
            st.markdown(f"**Os meus ficheiros privados** <span class='ec-meta'>· {len(privados)} · só tu vês</span>",
                        unsafe_allow_html=True)
            lista_documentos(backend, privados, "m")
            enviados = st.file_uploader("Juntar ficheiros só para mim", type=TIPOS_FICHEIRO, accept_multiple_files=True,
                                        key=f"up_sala_m_{sala['id']}_{st.session_state.versao_upload}",
                                        help="O assistente da sala usa-os nas tuas respostas; mais ninguém os vê.")
            if enviados:
                enviar_para_sala(backend, sala, enviados, False)


IDEIAS_SALA = ["Resume os materiais da sala", "Quais são os conceitos mais importantes?",
               "Faz-me 5 perguntas para rever", "Explica o tema mais difícil de forma simples"]


def assistente_da_sala(backend, sala: dict) -> None:
    ficheiros = backend.ficheiros(sala["id"])  # só os que esta pessoa pode ver
    historico = perfil.setdefault("salas_chat", {}).setdefault(sala["id"], [])
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    en = cfg.get("idioma") == "English"
    escolha = None
    if historico:
        with st.container(horizontal=True, key=f"sa_topo_{sala['id'][:12]}", gap="small"):
            st.caption(f":material/description: Respondo só com os {len(ficheiros)} documento(s) que podes ver nesta sala.")
            if st.button("Nova conversa", icon=":material/add_comment:", key=f"limpa_sala_{sala['id']}", type="tertiary"):
                historico.clear()
                guardar_perfil()
                st.rerun()
    elif ficheiros:
        st.markdown(f"<div class='sa-ola'>{ICONE_SVG}<b>Pergunta sobre os materiais da sala</b><p>Respondo só com os "
                    f"{len(ficheiros)} documento(s) que podes ver e digo de onde vem cada resposta.</p></div>",
                    unsafe_allow_html=True)
        # A chave muda depois de cada escolha, para a ideia não ficar selecionada se a resposta falhar.
        n_k = f"sa_ideias_n_{sala['id']}"
        escolha = st.pills("Ideias", IDEIAS_SALA, key=f"sa_ideias_{sala['id']}_{st.session_state.get(n_k, 0)}",
                           label_visibility="collapsed")
        if escolha:
            st.session_state[n_k] = st.session_state.get(n_k, 0) + 1
    else:
        st.markdown(f"<div class='sa-ola'>{ICONE_SVG}<b>Ainda não há materiais</b><p>Quando houver documentos nos "
                    "materiais da sala (ou nos teus ficheiros privados), respondo com base neles.</p></div>",
                    unsafe_allow_html=True)
    for m in historico:
        with st.chat_message(m["role"], avatar=avatar if m["role"] == "assistant" else None):
            md(m["content"])
            if m["role"] == "assistant":
                st.markdown(botao_copiar_html(m["content"], en), unsafe_allow_html=True)
    if historico:
        ativar_copiar()
    pergunta = st.chat_input("Pergunta sobre os materiais da sala…", key=f"chat_sala_{sala['id']}",
                             disabled=not (tem_chave and ficheiros)) or escolha
    if not pergunta or not (tem_chave and ficheiros):
        return
    with st.chat_message("user"):
        st.markdown(pergunta)
    fontes = selecionar_texto({f["nome"]: f.get("texto_extraido") or "" for f in ficheiros}, pergunta)
    idioma = " Answer in English." if en else " Respondes em português de Portugal."
    mensagens = [{"role": "user", "content": f"<fontes>\n{fontes}\n</fontes>\n\nVou fazer perguntas sobre estes materiais."},
                 {"role": "assistant", "content": "Combinado."}] + dz.contexto_conversa(historico) + \
        [{"role": "user", "content": pergunta}]
    with st.chat_message("assistant", avatar=avatar):
        try:
            resposta = escrever_fluxo(chamar_ia_stream(mensagens, sistema=SISTEMA_SALA + idioma,
                                                       tarefa=dz.complexidade(pergunta)), "A ler os materiais")
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
    resposta = resposta if isinstance(resposta, str) else "".join(map(str, resposta))
    if resposta:
        historico += [{"role": "user", "content": pergunta}, {"role": "assistant", "content": resposta}]
        guardar_perfil()
        st.rerun()


def dia_legivel(dia: date) -> str:
    hoje = date.today()
    if dia == hoje:
        return "Hoje"
    if dia == hoje - timedelta(days=1):
        return "Ontem"
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
             "novembro", "dezembro"]
    return f"{dia.day} de {meses[dia.month - 1]}" + (f" de {dia.year}" if dia.year != hoje.year else "")


def html_conversa_sala(lista: list, eu: str) -> str:
    """As mensagens como numa app de mensagens: separadores por dia, as minhas à direita, as dos outros à esquerda com
    o nome; mensagens seguidas da mesma pessoa (até 5 min) ficam juntas. A lista começa no fim (as mais recentes)."""
    if not lista:
        return ("<div class='cv-lista'><div class='cv-vazio'><span class='material-symbols-rounded' translate='no'>forum</span>"
                "<b>Ainda não há mensagens</b>Escreve a primeira mensagem para a sala.</div></div>")
    partes, dia_ant, ant = [], None, None
    for m in lista:
        try:
            quando = datetime.fromisoformat(str(m.get("enviada_em") or "")[:19])
        except ValueError:
            quando = None
        dia = quando.date() if quando else None
        if dia and dia != dia_ant:
            partes.append(f"<div class='cv-dia'>{escape(dia_legivel(dia))}</div>")
            ant = None
        seguida = bool(ant and ant[0] == m["autor_id"] and quando and ant[1] and (quando - ant[1]).total_seconds() < 300)
        meu = m["autor_id"] == eu
        classes = "cv-msg" + (" meu" if meu else "") + (" seguida" if seguida else "")
        cab = "" if seguida else (f"<div class='cv-cab'>{'' if meu else '<b>' + escape(m.get('autor_nome') or '?') + '</b>'}"
                                  f"<time>{quando.strftime('%H:%M') if quando else ''}</time></div>")
        partes.append(f"<div class='{classes}'>{avatar_html(m.get('autor_nome') or '?')}<div class='cv-corpo'>{cab}"
                      f"<div class='cv-bolha'>{escape(str(m.get('texto') or '')).replace(chr(10), '<br>')}</div></div></div>")
        dia_ant, ant = dia or dia_ant, (m["autor_id"], quando)
    return "<div class='cv-lista' role='log' aria-live='polite'><div>" + "".join(partes) + "</div></div>"


@st.fragment(run_every=5)
def mensagens_da_sala(sala_id: str) -> None:
    """Conversa entre membros; atualiza sozinha a cada 5 segundos (só enquanto esta secção está aberta)."""
    import salas_backend as sb

    backend = obter_backend_salas()
    try:
        lista = backend.mensagens(sala_id)
    except sb.ErroSalas as erro:
        st.error(str(erro))
        return
    eu = backend.atual()["id"]
    with st.container(border=True, key=f"cv_caixa_{sala_id[:12]}"):
        st.markdown(html_conversa_sala(lista, eu), unsafe_allow_html=True)
    apagaveis = [m for m in lista if m.get("pode_apagar")][-15:]
    if apagaveis:
        with st.popover("Apagar mensagens", icon=":material/delete:"):
            st.caption("As tuas mensagens" + (" e, como criador, as dos outros" if any(m["autor_id"] != eu for m in apagaveis)
                                              else "") + " (as mais recentes).")
            for m in reversed(apagaveis):
                a, b = st.columns([6, 1], vertical_alignment="center")
                a.markdown(f"<span class='ec-meta'>{escape(m.get('autor_nome') or '')} · "
                           f"{str(m.get('enviada_em', ''))[11:16]}</span><br>{escape(curto(str(m.get('texto') or ''), 90))}",
                           unsafe_allow_html=True)
                if b.button("", icon=":material/close:", key=f"apagar_msg_{m['id']}", type="tertiary",
                            help="Apagar mensagem"):
                    try:
                        backend.apagar_mensagem(m["id"])
                    except sb.ErroSalas as erro:
                        st.error(str(erro))
                    st.rerun(scope="fragment")


def conversa_da_sala(backend, sala: dict) -> None:
    import salas as sl
    import salas_backend as sb

    eu = backend.atual()["id"]
    if sala["chat_modo"] == "criador":
        st.caption(":material/campaign: Canal de avisos: só quem criou a sala escreve aqui." if not sala["e_criador"]
                   else ":material/campaign: Canal de avisos: só tu escreves; os membros leem.")
    mensagens_da_sala(sala["id"])
    if sl.pode_escrever_no_chat(sala, eu, [sl.Membro(sala["id"], eu, sala.get("papel") or "aluno")]):
        texto = st.chat_input("Escreve uma mensagem para a sala…", key=f"msg_sala_{sala['id']}")
        if texto and texto.strip():
            try:
                backend.enviar_mensagem(sala["id"], texto)
                st.rerun()
            except sb.ErroSalas as erro:
                st.error(str(erro))


def membros_da_sala(backend, sala: dict) -> None:
    import salas as sl
    import salas_backend as sb

    eu = backend.atual()["id"]
    esq, dir_ = st.columns([1.5, 1], gap="medium")
    with esq.container(border=True):
        lista = backend.membros(sala["id"])
        st.markdown(f"**Membros** <span class='ec-meta'>· {len(lista)}</span>", unsafe_allow_html=True)
        nomes_papel = {"criador": "Criador", "professor": "Professor", "aluno": "Aluno"}
        ordem_papel = {"criador": 0, "professor": 1, "aluno": 2}
        lista = sorted(lista, key=lambda m_: (ordem_papel.get(m_["papel"], 3), m_["utilizador_id"] != eu, m_["nome"].lower()))
        a_remover = st.session_state.get(f"_remover_{sala['id']}")
        for m in lista:
            a, b = st.columns([6, 1.6], vertical_alignment="center")
            a.markdown(f"<div class='sl-pessoa'>{avatar_html(m['nome'], m.get('foto'))}<div><b>{escape(m['nome'])}</b>"
                       + (" <span class='cd-tag'>tu</span>" if m["utilizador_id"] == eu else "")
                       + f"<br><span class='ec-meta'>"
                       f"{nomes_papel.get(m['papel'], m['papel'])}</span></div></div>", unsafe_allow_html=True)
            if not sl.pode_remover_membro(sala, m["utilizador_id"], eu):
                continue
            if a_remover == m["utilizador_id"]:  # segundo clique: confirma
                if b.button("Confirmar", key=f"rem_ok_{sala['id']}_{m['utilizador_id']}", type="primary", width="stretch",
                            help=f"Tirar {m['nome']} da sala"):
                    try:
                        backend.remover_membro(sala["id"], m["utilizador_id"])
                        st.session_state.pop(f"_remover_{sala['id']}", None)
                        st.toast(f"{m['nome']} saiu da sala.")
                        st.rerun()
                    except sb.ErroSalas as erro:
                        st.error(str(erro))
            elif b.button("Remover", key=f"rem_m_{sala['id']}_{m['utilizador_id']}", type="tertiary", width="stretch"):
                st.session_state[f"_remover_{sala['id']}"] = m["utilizador_id"]
                st.rerun()
    with dir_.container(border=True):
        titulo_cartao("Convidar")
        if sala.get("codigo"):
            st.caption("Partilha o código ou o link." + ("" if sala.get("entrada_aberta", True) else
                                                         " A sala está fechada a novos membros (Definições)."))
            st.code(sala["codigo"], language=None)
            st.code(link_da_sala(sala["codigo"]), language=None)
            if sala["e_criador"] and st.button("Gerar código novo", icon=":material/autorenew:", key=f"novo_cod_{sala['id']}",
                                               help="O código antigo deixa de funcionar."):
                backend.novo_codigo(sala["id"])
                st.rerun()
        else:
            st.caption("Nesta sala só quem a criou pode convidar pessoas.")
        if not sala["e_criador"]:
            with st.popover("Sair da sala", icon=":material/logout:", width="stretch"):
                st.caption("Deixas de ver os materiais e a conversa. Podes voltar com o código.")
                if st.button("Sair", type="primary", key=f"sair_sala_{sala['id']}"):
                    backend.sair_da_sala(sala["id"])
                    st.session_state.pop("sala_aberta", None)
                    st.rerun()


def vista_sala(backend, sala_id: str) -> None:
    import salas as sl
    import salas_backend as sb

    try:
        sala = backend.obter_sala(sala_id)
    except sb.ErroSalas as erro:
        st.error(str(erro))
        st.session_state.pop("sala_aberta", None)
        return
    cor = sl.CORES_SALA.get(sala.get("cor") or "turquesa", "#2AA5B8")
    tipo = ("Turma" + (f" · {sala['cadeira']}" if sala.get("cadeira") else "")) if sala["tipo"] == "cadeira" \
        else "Grupo de estudo"
    st.button("Salas", icon=":material/arrow_back:", key="voltar_salas", type="tertiary",
              on_click=lambda: st.session_state.pop("sala_aberta", None))
    try:
        membros_l = backend.membros(sala["id"])
    except Exception:  # noqa: BLE001
        membros_l = []
    pilha = "".join(avatar_html(m["nome"], m.get("foto")) for m in membros_l[:5])
    n_m = sala.get("n_membros", len(membros_l) or 1)
    meta = [f"{n_m} membro{'s' if n_m != 1 else ''}", f"{sala.get('n_documentos', 0)} documento"
            f"{'s' if sala.get('n_documentos', 0) != 1 else ''}", "Criada por ti" if sala.get("e_criador") else tipo]
    # com o separador Laboratório aberto, a sala fica como era (o Laboratório não pode mudar nesta fase, nem de lugar)
    tem_lab_ = bool(sala.get("laboratorio") and sala.get("ferramentas_lab"))
    no_lab_ = tem_lab_ and (st.session_state.get(f"sala_secao_{sala['id']}") or
                            ("Assistente" if sala.get("assistente_ativo", True) else "Laboratório")) == "Laboratório"
    c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
    c1.markdown(f"<div class='sr-topo'>{ico_sala_html(sala, 'sr-ico')}<div class='mi-encolhe'><h1 class='sr-nome'>"
                f"{escape(sala['nome'])}</h1><div class='sr-desc'>{escape(' '.join((sala.get('descricao') or tipo).split()))}</div></div></div>"
                f"<div class='sr-meta'><span class='sr-pilha'>{pilha}</span>"
                + "".join(f"<span>{escape(x)}</span>" for x in meta)
                + ("<span class='cd-tag lab'><span class='material-symbols-rounded' translate='no'>science</span>Laboratório</span>"
                   if sala.get("laboratorio") and sala.get("ferramentas_lab") else "") + "</div>", unsafe_allow_html=True)
    with c2.container(horizontal=True, key="pg_acoes_sala", gap="small"):
        if sala.get("codigo"):
            with st.popover("Convidar", icon=":material/person_add:"):
                st.caption("Partilha o código ou o link da sala." + ("" if sala.get("entrada_aberta", True) else
                                                                     " A sala está fechada a novos membros (Definições)."))
                st.code(sala["codigo"], language=None)
                st.code(link_da_sala(sala["codigo"]), language=None)
        if not no_lab_:
            with st.popover("Estudar", icon=":material/timer:"):
                cad_sala = sala.get("cadeira") if sala.get("cadeira") in st.session_state.cadeiras else None
                st.caption("Começa uma sessão de foco no cronómetro" + (f", ligada a {cad_sala}." if cad_sala else ".")
                           + " Continua a contar enquanto andas pela app (vês o tempo na barra lateral).")
                minutos_s = st.segmented_control("Minutos", [25, 45, 60], default=25, key=f"sala_foco_min_{sala['id']}",
                                                 format_func=lambda m: f"{m} min") or 25
                st.button("Começar", type="primary", icon=":material/play_arrow:", key=f"sala_foco_{sala['id']}", width="stretch",
                          on_click=lambda m=minutos_s, c=cad_sala: st.session_state.update(
                              crono_cmd={"id": uuid.uuid4().hex[:8], "minutos": m, "pausa": 5, "cadeira": c or ""}))
        if sala["e_criador"] and st.button("Definições", icon=":material/settings:", key="def_sala"):
            dialogo_definicoes_sala(backend, sala)
    if sala.get("aviso"):
        st.info(sala["aviso"], icon=":material/campaign:")
    # Só se desenha a secção aberta (antes, os separadores desenhavam tudo em cada clique, e a conversa da sala
    # atualizava-se a cada 5 s mesmo noutro separador). Sem Laboratório, a sala não mostra nada dele.
    icones_sec = {"Assistente": ":material/auto_awesome:", "Laboratório": ":material/science:",
                  "Materiais": ":material/folder_open:", "Conversa": ":material/forum:", "Avisos": ":material/campaign:",
                  "Membros": ":material/group:"}
    abas = (["Assistente"] if sala.get("assistente_ativo", True) else []) + \
           (["Laboratório"] if sala.get("laboratorio") and sala.get("ferramentas_lab") else []) + ["Materiais"] + \
           (["Conversa" if sala["chat_modo"] == "todos" else "Avisos"] if sl.chat_ativo(sala) else []) + ["Membros"]
    chave_sec = f"sala_secao_{sala['id']}"
    if st.session_state.get(chave_sec) not in abas:
        st.session_state.pop(chave_sec, None)
    novas_c = por_ler_na_sala(backend, sala, (backend.atual() or {}).get("id")) \
        if st.session_state.get(chave_sec) not in ("Conversa", "Avisos") and not no_lab_ else 0
    aba = st.segmented_control("Secção da sala", abas, default=abas[0], key=chave_sec, label_visibility="collapsed",
                               format_func=lambda a: f"{icones_sec[a]} {a}" + (f" · {novas_c}" if novas_c and a in
                                                                                 ("Conversa", "Avisos") else "")) or abas[0]
    if aba != "Laboratório":  # o Laboratório fica exatamente como está (sem as preferências visuais das Definições)
        aplicar_preferencias_visuais()
    if aba == "Assistente":
        assistente_da_sala(backend, sala)
    elif aba == "Laboratório":
        laboratorio_da_sala(backend, sala)
    elif aba == "Materiais":
        materiais_da_sala(backend, sala)
    elif aba in ("Conversa", "Avisos"):
        conversa_da_sala(backend, sala)
        vistas_ = perfil.setdefault("salas_vistas", {})
        agora_ = datetime.now().isoformat(timespec="seconds")
        if vistas_.get(sala["id"], "")[:16] != agora_[:16]:  # no máximo uma escrita por minuto
            vistas_[sala["id"]] = agora_
            guardar_perfil()
    else:
        membros_da_sala(backend, sala)


if vista == "salas":
    import salas_backend as sb

    st.markdown(estilos(ESTILO_SALAS, ESTILO_LISTAS), unsafe_allow_html=True)
    if "cal_msg" in st.session_state:
        st.toast(st.session_state.pop("cal_msg"), icon=":material/check_circle:")
    backend = obter_backend_salas()
    try:
        utilizador = backend.atual()
    except sb.ErroSalas as erro:
        st.error(str(erro))
        utilizador = None
    if not utilizador:
        cabecalho("Salas", "Salas só tuas, grupos de estudo e turmas: materiais, conversa, um assistente só da sala "
                           "e, se quiseres, um Laboratório.")
        _, meio, _ = st.columns([1, 2.2, 1])
        with meio.container(border=True):
            ecra_contas(backend)
        if backend.nome == "local" and e_admin():
            meio.caption("Modo neste computador: as contas e as salas ficam guardadas só aqui. Para colegas noutros "
                         "computadores, liga o Supabase no teu Perfil → Administração → Salas online.")
        st.stop()
    if perfil.get("foto") and not utilizador.get("foto"):  # a fotografia do perfil passa para a conta (os colegas veem-na)
        try:
            backend.mudar_perfil(foto=base64.b64decode(perfil["foto"]))
        except Exception:  # noqa: BLE001
            pass

    pedido_janela = st.session_state.pop("salas_dialogo", None)  # pedido da barra lateral
    if pedido_janela == "criar":
        dialogo_criar_sala(backend, utilizador)
    elif pedido_janela == "entrar":
        dialogo_entrar_sala(backend)
    convite = st.session_state.pop("sala_convite", None)
    if convite:
        try:
            st.session_state.sala_aberta = backend.entrar_com_codigo(convite)["id"]
            st.session_state.cal_msg = "Entraste na sala pelo link de convite."
            st.rerun()
        except sb.ErroSalas as erro:
            st.error(str(erro))

    if st.session_state.get("sala_aberta"):
        vista_sala(backend, st.session_state.sala_aberta)
        st.stop()

    e_prof_s = utilizador.get("vinculo") == "Professor"
    with cabecalho_pagina("Salas", "As tuas turmas e salas: materiais, avisos, conversa, assistente e Laboratório." if e_prof_s
                          else "Os teus sítios de estudo: só teus, com colegas ou com os teus professores."):
        if st.button("Entrar com código", icon=":material/login:", key="abrir_entrar_sala"):
            dialogo_entrar_sala(backend)
        if st.button("Criar sala", type="primary", icon=":material/add:", key="abrir_criar_sala"):
            dialogo_criar_sala(backend, utilizador)

    import salas as sl_

    minhas = backend.minhas_salas()
    pessoais = sorted(st.session_state.cadeiras, key=lambda n_: (data_avaliacao(st.session_state.cadeiras[n_]) or date.max,
                                                                 dz._sem_acentos(n_)))
    if not minhas and not pessoais:
        st.markdown("<div class='pg-vazio'><span class='material-symbols-rounded' translate='no'>"
                    + ("co_present" if e_prof_s else "meeting_room") + "</span><b>Ainda não tens salas</b><p>"
                    + ("Cria uma turma para cada cadeira que dás: os alunos entram com o código e encontram lá os "
                       "materiais, os avisos e um assistente que responde com eles. Também podes criar uma sala só tua "
                       "para preparar as aulas." if e_prof_s else
                       "Cria uma sala só tua para cada cadeira: juntas lá os apontamentos e tens conversa com as fontes, "
                       "resumos, quizzes, flashcards e um plano de estudo. Para estudar com colegas, cria uma sala com "
                       "eles ou entra com o código que te deram.") + "</p></div>", unsafe_allow_html=True)
    else:
        b1, b2 = st.columns([2.2, 1.3], vertical_alignment="center")
        busca_s = b1.text_input("Pesquisar salas", key="pg_busca_salas", placeholder="Pesquisar salas…",
                                label_visibility="collapsed", icon=":material/search:")
        filtro = b2.segmented_control("Mostrar", ["Todas", "Só tuas", "Partilhadas"], default="Todas",
                                      key="salas_filtro", label_visibility="collapsed") or "Todas"
        itens = ([("p", sala_pessoal(n_)) for n_ in pessoais] if filtro != "Partilhadas" else []) + \
                ([("s", x) for x in minhas] if filtro != "Só tuas" else [])
        termos_s = dz.termos(busca_s) if busca_s else []
        if termos_s:
            itens = [(t_, x) for t_, x in itens if all(t in dz._sem_acentos(f"{x['nome']} {x.get('descricao') or ''} "
                                                                             f"{x.get('cadeira') or ''}") for t in termos_s)]
        st.markdown(f"<div class='pg-contagem'>{len(itens)} sala{'s' if len(itens) != 1 else ''}</div>",
                    unsafe_allow_html=True)

        def abrir_sala(sid: str) -> None:
            st.session_state.sala_aberta = sid

        colunas = celulas_grelha(len(itens))
        for n, (tipo_i, sala) in enumerate(itens):
            if tipo_i == "p":  # sala só tua: a próxima avaliação, as fontes e os flashcards de hoje
                nome_p = sala["nome"]
                d_p = st.session_state.cadeiras[nome_p]
                r_p = repo().proxima(nome_p)
                res_p = rs.resumo(d_p.get("cartoes") or [], date.today()) if d_p.get("cartoes") else None
                if r_p:
                    dias_p_ = av.dias_ate(r_p, date.today())
                    linha_p = (f"<div class='cd-linha'><i style='background:{av.CORES[r_p['tipo']]}'></i>"
                               f"<span>{escape(r_p['nome'])} · {fmt_data(r_p['data'], False)}</span>"
                               f"<span class='cd-tag{' urg' if dias_p_ <= 3 else ''}'>{escape(av.texto_faltam(r_p))}</span></div>")
                else:
                    linha_p = f"<div class='cd-desc'>{escape(' '.join((sala['descricao'] or 'Sem avaliações marcadas').split()))}</div>"
                n_f = sala["n_documentos"]
                meta_p = (f"<span class='cd-papel'>Só tu</span>"
                          f"<span class='cd-num'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>description</span>"
                          f"{n_f} fonte{'s' if n_f != 1 else ''}</span>"
                          + (f"<span class='cd-num'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>style</span>"
                             f"{res_p['para_hoje']} para rever</span>" if res_p and res_p["para_hoje"] else ""))
                html_p = (f"<div class='cd-topo'>{ico_sala_html(sala)}<div class='cd-nome' title='{escape(nome_p)}'>"
                          f"{escape(nome_p)}</div></div>{linha_p}<div class='cd-meta sala'>{meta_p}</div>")
                with colunas[n]:
                    cartao_clicavel(f"sala_{sala['id']}", "Abrir", f"abrir_{sala['id']}", html_p, navegar, ("cadeira",),
                                    {"cadeira_atual": nome_p})
                continue
            tipo_s = ("Turma" + (f" · {sala['cadeira']}" if sala.get("cadeira") else "")) \
                if sala["tipo"] == "cadeira" else "Grupo de estudo"
            n_mb, n_dc = sala.get("n_membros", 1), sala.get("n_documentos", 0)
            meta_s = (f"<span class='cd-papel'>{'Criada por ti' if sala.get('e_criador') else 'Membro'}</span>"
                      f"<span class='cd-num'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>group</span>"
                      f"{n_mb} membro{'s' if n_mb != 1 else ''}</span>"
                      f"<span class='cd-num'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>description</span>"
                      f"{n_dc} documento{'s' if n_dc != 1 else ''}</span>")
            novas_s = por_ler_na_sala(backend, sala, utilizador["id"]) if n < 12 else 0
            etiquetas = ((f"<span class='cd-tag novas'><span class='material-symbols-rounded' translate='no'>forum</span>{novas_s} "
                          f"{'nova' if novas_s == 1 else 'novas'}</span>" if novas_s else "")
                         + ("<span class='cd-tag lab'><span class='material-symbols-rounded' translate='no'>science</span>Laboratório</span>"
                            if sala.get("laboratorio") and sala.get("ferramentas_lab") else "")
                         + ("<span class='cd-tag'>Avisos</span>" if sala.get("chat_modo") == "criador" else ""))
            html_s = (f"<div class='cd-topo'>{ico_sala_html(sala)}<div class='cd-nome' title='{escape(sala['nome'])}'>"
                      f"{escape(sala['nome'])}</div></div><div class='cd-desc'>{escape(' '.join((sala.get('descricao') or tipo_s).split()))}</div>"
                      f"<div class='cd-meta sala'>{meta_s}</div>"
                      + (f"<div class='cd-tags'>{etiquetas}</div>" if etiquetas else ""))
            with colunas[n]:
                cartao_clicavel(f"sala_{sala['id'][:12]}", "Abrir", f"abrir_sala_{sala['id']}", html_s, abrir_sala,
                                (sala["id"],))
        if not itens:
            st.caption("Nenhuma sala com esse nome neste filtro." if termos_s else
                       "Ainda não tens salas neste grupo.")
    # Quem está ligado (é a mesma conta da app; terminar a sessão faz-se no perfil, na barra lateral).
    st.markdown(f"<div class='pg-rodape'>{avatar_html(utilizador['nome'], utilizador.get('foto'))}<span>Nas salas, és "
                f"<b>{escape(utilizador['nome'])}</b> · {escape(utilizador.get('vinculo') or '')} · "
                f"{escape(utilizador.get('email') or '')}</span></div>", unsafe_allow_html=True)
    if backend.nome == "local" and e_admin():
        st.caption(":material/computer: Modo neste computador: as contas e as salas ficam guardadas só aqui (dá para "
                   "experimentar com duas contas). Para colegas noutros computadores, liga o Supabase no teu Perfil → Administração → Salas online.")
    st.stop()

ESTILO_3D = """
<style>
[class*="st-key-c3d_"] img { aspect-ratio:16/10; object-fit:cover; border-radius:10px; }
[class*="st-key-c3d_"] .stMarkdown p { margin-bottom:0.1rem; }
.e3d-sem-capa { aspect-ratio:16/10; border-radius:10px; background:var(--bolha); display:grid; place-items:center; }
.e3d-sem-capa svg { height:56%; width:auto; opacity:0.55; }
.e3d-chips { display:flex; flex-wrap:wrap; gap:0.3rem; margin:0.2rem 0 0.4rem; }
.e3d-chip { background:var(--bolha); color:var(--texto); border-radius:999px; padding:0.05rem 0.6rem; font-size:0.78rem; }
.e3d-estado { display:inline-block; border-radius:999px; padding:0.05rem 0.6rem; font-size:0.78rem; font-weight:500;
  background:var(--acento-claro); color:var(--acento-esc); }
[class*="st-key-lab_cartao_"] { min-height:10.5rem; }
.lab-icone { font-size:1.6rem; line-height:1; }
</style>
"""


# =============================================================== 3D STUDIO
SECOES_3D = {"explorar": "Explorar", "criar": "Criar com IA", "meus": "Os meus modelos"}
NOMES_MATERIAIS = {"padrao": "Normal", "brilhante": "Brilhante", "mate": "Mate", "metal": "Metal",
                   "vidro": "Vidro (transparente)", "emissivo": "Luminoso", "tecido": "Tecido (orgânico)"}
SUGESTOES_3D = {
    "Coração humano": ("Cria um coração humano em 3D com todas as suas estruturas principais: aurículas, ventrículos, "
                       "aorta, artéria pulmonar, veias cavas e válvulas", "Anatomia"),
    "Célula animal": ("Uma célula animal em corte com núcleo, nucléolo, mitocôndrias, retículo endoplasmático, complexo de "
                      "Golgi, lisossomas e membrana", "Biologia celular"),
    "Neurónio": ("Um neurónio com corpo celular, núcleo, dendrites, axónio, bainha de mielina, nódulos de Ranvier e "
                 "terminais do axónio", "Anatomia"),
    "Molécula de ADN": ("Uma dupla hélice de ADN com as cadeias de açúcar-fosfato e os pares de bases A-T e C-G em cores "
                        "diferentes", "Molécula"),
    "Sistema solar": ("O sistema solar com o Sol e os oito planetas por ordem, com tamanhos relativos simplificados e os "
                      "anéis de Saturno", "Outro"),
    "Motor de 4 tempos": ("Um cilindro de motor de combustão de 4 tempos em corte: pistão, biela, cambota, válvulas de "
                          "admissão e escape, vela", "Máquina ou mecanismo"),
    "Olho humano": ("Um olho humano em corte com córnea, íris, pupila, cristalino, retina, nervo ótico e humor vítreo",
                    "Anatomia"),
    "Vulcão em corte": ("Um vulcão em corte com câmara magmática, chaminé, cratera, camadas de lava e cinza",
                        "Relevo ou geografia"),
}


def biblioteca_3d():
    import biblioteca3d as b3

    return b3.abrir(obter_backend_salas())


def ir_3d(**extra) -> None:
    navegar("estudio3d", **extra)


def sem_capa_html() -> str:
    return f'<div class="e3d-sem-capa">{ICONE_SVG}</div>'


def cartao_3d(m: dict, prefixo: str, meu: bool = False) -> None:
    with st.container(border=True, key=f"c3d_{prefixo}_{m['id']}"):
        if m.get("capa"):
            st.image(m["capa"], width="stretch")
        else:
            st.markdown(sem_capa_html(), unsafe_allow_html=True)
        st.markdown(f"**{escape(m['titulo'])}**")
        if meu:
            estado = ("Público" if m["visibilidade"] == "publico" else "Privado") if m["publicado"] else "Em desenvolvimento"
            st.caption(f"{estado} · versão {m['versao_atual']}")
        else:
            st.caption(f"{m.get('dono_nome', '')} · {m.get('categoria', '')}")
        st.caption(f":material/favorite: {m.get('gostos', 0)}  ·  :material/visibility: {m.get('visualizacoes', 0)}"
                   + ("  ·  :material/call_split: remix" if m.get("origem_id") else ""))
        if meu:
            st.button("Abrir no editor", key=f"ab3d_{prefixo}_{m['id']}", width="stretch",
                      on_click=ir_3d, kwargs={"e3d_secao": "criar", "e3d_aberto": m["id"], "e3d_ver": None})
        else:
            st.button("Ver modelo", key=f"ab3d_{prefixo}_{m['id']}", width="stretch",
                      on_click=ir_3d, kwargs={"e3d_secao": "explorar", "e3d_ver": m["id"]})


def grelha_3d(lista: list, prefixo: str, meu_uid: str | None = None) -> None:
    colunas = st.columns(3)
    for i, m in enumerate(lista):
        with colunas[i % 3]:
            cartao_3d(m, prefixo, meu=bool(meu_uid) and m.get("dono_id") == meu_uid)


def dados_glb(bib, registo: dict):
    """Ficheiro GLB do modelo (em cache nesta sessão) como data URL para o visualizador."""
    glb = (registo["modelo"].get("glb") or {})
    if not glb.get("id"):
        return None, None
    cache = st.session_state.setdefault("_glb_cache", {})
    if glb["id"] not in cache:
        import biblioteca3d as b3

        try:
            cache[glb["id"]] = "data:model/gltf-binary;base64," + base64.b64encode(bib.obter_glb(glb["id"], registo["id"])).decode()
        except b3.Erro3D as erro:
            st.error(str(erro))
            return None, glb["id"]
    return cache[glb["id"]], glb["id"]


def melhorar_com_blender(bib, modelo_id: str) -> bool:
    """O Blender refaz as peças do modelo (biséis, superfícies lisas, relevo, materiais) e o GLB fica junto da versão atual."""
    import biblioteca3d as b3

    try:
        registo = bib.obter(modelo_id)
        modelo = registo["modelo"]
        if not mb.hashes(modelo):
            return False
        motor = motor_blender() or "Blender"
        with a_pensar(f"A melhorar o modelo no {motor} (arestas, superfícies e materiais)"):
            dados, motor = mb.construir(modelo, servidor_blender(), cfg.get("blender_caminho"))
        gid = bib.guardar_glb("blender.glb", dados)
        modelo = {**modelo, "blender": {"id": gid, "hashes": mb.hashes(modelo), "motor": motor,
                                        "em": datetime.now().isoformat(timespec="minutes")}}
        bib.anexar_blender(modelo_id, modelo)
        st.session_state.pop("e3d_blender_erro", None)
        return True
    except (mb.ErroBlender, b3.Erro3D, e3.ErroModelo) as erro:
        st.session_state["e3d_blender_erro"] = str(erro)
        return False


def blender_automatico(bib, modelo_id: str) -> None:
    """Depois de a IA criar ou alterar um modelo: refaz no Blender as peças que mudaram de forma (se houver Blender)."""
    if not cfg.get("blender_auto", True) or not motor_blender():
        return
    try:
        if mb.por_refazer(bib.obter(modelo_id)["modelo"]):
            melhorar_com_blender(bib, modelo_id)
    except Exception:  # noqa: BLE001 — o modelo fica com as peças simples
        pass


def url_blender(bib, registo: dict) -> tuple:
    """GLB do Blender para o visualizador (ficheiro servido pelo componente) e as peças que ainda correspondem a ele."""
    import biblioteca3d as b3

    b = registo["modelo"].get("blender") or {}
    ids = mb.pecas_atualizadas(registo["modelo"])
    if not b.get("id") or not ids:
        return None, []
    destino = PASTA_MODELOS / f"{b['id']}.glb"
    if not destino.exists():
        try:
            dados = bib.obter_glb(b["id"], registo["id"])
        except b3.Erro3D:
            return None, []
        PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
    return f"modelos/{b['id']}.glb", ids


def visor_3d(bib, registo: dict, chave: str, chave_sel: str, altura: int = 540) -> None:
    """Visualizador 3D real (Three.js) + eventos: seleção de peça, capa capturada e lista de malhas do GLB."""
    glb_url, glb_id = dados_glb(bib, registo)

    def tratar(ev) -> bool:
        """Devolve True se a seleção mudou (o visualizador tem de receber a peça nova)."""
        if not ev:
            return False
        if ev.get("evento") == "selecao":
            mudou = st.session_state.get(chave_sel) != ev.get("id")
            st.session_state[chave_sel] = ev.get("id")
            return mudou
        if ev.get("evento") == "capa" and str(ev.get("imagem", "")).startswith("data:image"):
            st.session_state[f"e3d_capa_{registo['id']}"] = base64.b64decode(ev["imagem"].split(",", 1)[1])
            st.toast("Capa capturada. Usa-a ao publicar o modelo.", icon=":material/photo_camera:")
        elif ev.get("evento") == "malhas" and glb_id:
            st.session_state[f"e3d_malhas_{glb_id}"] = ev.get("lista") or []
        return False
    # o valor do componente já está no session_state antes de o desenhar: tratar primeiro, para o visualizador receber
    # logo a peça selecionada (senão a resposta seguinte apagava o destaque)
    tratar(evento(st.session_state.get(chave), chave))
    blender, blender_ids = url_blender(bib, registo)
    valor = componente("visor3d", chave, altura, modelo=registo["modelo"], glb=glb_url, glb_id=glb_id,
                       blender=blender, blender_ids=blender_ids,
                       selecionada=st.session_state.get(chave_sel), enquadrar=registo["id"],
                       pedir_malhas=bool(glb_id) and f"e3d_malhas_{glb_id}" not in st.session_state)
    if tratar(evento(valor, chave)):
        st.rerun()


def info_peca(modelo: dict, sel: str | None, malhas: list) -> dict | None:
    if not sel:
        return None
    for p in modelo["partes"]:
        if p["id"] == sel:
            return p
    for m in malhas:
        if m["id"] == sel:
            aj = (modelo.get("ajustes_glb") or {}).get(sel, {})
            return {"id": sel, "nome": m["nome"], "tipo": "malha", "cor": aj.get("cor", "#C9C2B4"),
                    "material": aj.get("material", {"tipo": "padrao", "opacidade": 1.0}), "etiqueta": aj.get("etiqueta", ""),
                    "descricao": aj.get("descricao", ""), "visivel": aj.get("visivel", True), "escala": [aj.get("escala", 1.0)] * 3,
                    "glb": True}
    return None


def gerar_modelo_3d(descricao, tipo, detalhe, complexidade, estilo, incluir, etiquetas):
    try:
        texto = chamar_ia([{"role": "user", "content": e3.pedido_gerar(descricao, tipo, detalhe, complexidade, estilo,
                                                                        incluir, etiquetas)}],
                          json_mode=True, sistema=e3.SISTEMA_3D, pensar=True)
        modelo = e3.normalizar_modelo(extrair_json(texto))
        if modelo["titulo"] in ("", "Modelo 3D"):
            modelo["titulo"] = descricao.strip()[:80]
        return modelo
    except (ValueError, json.JSONDecodeError):
        st.error("A IA não devolveu um modelo válido. Tenta outra vez (ou com menos detalhe).")
    except e3.ErroModelo as erro:
        st.error(f"O modelo gerado não pôde ser usado: {erro} Tenta outra vez.")
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
    return None


def rever_modelo_3d(descricao: str, modelo: dict) -> tuple[dict, str]:
    """Segunda passagem: a IA compara o modelo com o pedido e aplica só as correções necessárias."""
    try:
        texto = chamar_ia([{"role": "user", "content": e3.pedido_rever(descricao, modelo)}], json_mode=True,
                          sistema=e3.SISTEMA_3D, pensar=True)
        resposta = extrair_json(texto)
        operacoes = resposta.get("operacoes") or []
        if not operacoes:
            return modelo, str(resposta.get("resumo") or "o modelo cumpre o pedido.")
        novo, _ = e3.aplicar_operacoes(modelo, operacoes)
        return novo, str(resposta.get("resumo") or "corrigi o que faltava.")
    except Exception:  # noqa: BLE001 — se a verificação falhar, fica o modelo da primeira passagem
        return modelo, ""


def editar_modelo_3d(bib, registo: dict, instrucao: str, so_selecionada: bool) -> None:
    """Edição por conversa: a IA devolve operações sobre o modelo existente; só muda o que foi pedido."""
    import biblioteca3d as b3

    modelo = registo["modelo"]
    glb_id = (modelo.get("glb") or {}).get("id")
    malhas = st.session_state.get(f"e3d_malhas_{glb_id}", []) if glb_id else []
    sel = st.session_state.get("e3d_sel") if so_selecionada else None
    nome_sel = (info_peca(modelo, sel, malhas) or {}).get("nome") if sel else None
    historico = st.session_state.setdefault(f"e3d_chat_{registo['id']}", [])
    historico.append({"role": "user", "content": instrucao + (f"  ·  _só: {nome_sel}_" if nome_sel else "")})
    try:
        with a_pensar("A alterar o modelo"):
            texto = chamar_ia([{"role": "user", "content": e3.pedido_editar(modelo, instrucao, sel,
                                                                             [m["id"] for m in malhas])}],
                              json_mode=True, sistema=e3.SISTEMA_3D, pensar=True)
        resposta = extrair_json(texto)
        novo, relatorio = e3.aplicar_operacoes({**modelo, "_malhas_glb": [m["id"] for m in malhas]},
                                               resposta.get("operacoes") or [], apenas=sel)
    except (ValueError, json.JSONDecodeError):
        historico.append({"role": "assistant", "content": "Não consegui interpretar a resposta da IA. Tenta reformular."})
        return
    except e3.ErroModelo as erro:
        historico.append({"role": "assistant", "content": f"Não apliquei: {erro}"})
        return
    except Exception as erro:  # noqa: BLE001
        historico.pop()
        mostrar_erro(erro)
        return
    if novo == e3.normalizar_modelo(modelo):
        historico.append({"role": "assistant", "content": "A IA não propôs nenhuma alteração. Tenta ser mais específico."})
        return
    try:
        n = bib.guardar_versao(registo["id"], novo, f"IA: {instrucao.strip()[:150]}")
    except b3.Erro3D as erro:
        historico.append({"role": "assistant", "content": str(erro)})
        return
    blender_automatico(bib, registo["id"])
    resumo = str(resposta.get("resumo") or "Alteração feita.").strip()
    detalhes = [r for r in relatorio if r.startswith(("Ignorado", "Peça não", "Não alterado"))]
    historico.append({"role": "assistant", "content": f"{resumo}  \n_Versão {n} guardada — podes desfazer._"
                      + ("\n\n" + "\n".join(f"- {d}" for d in detalhes[:5]) if detalhes else "")})


def painel_peca(bib, registo: dict, peca: dict) -> None:
    import biblioteca3d as b3

    with st.container(border=True):
        st.markdown(f"**{escape(peca['nome'])}**" + (f" <span class='e3d-chip'>{escape(peca['grupo'])}</span>" if peca.get("grupo") else ""),
                    unsafe_allow_html=True)
        info = [peca.get("descricao")] + ([f"**Função:** {peca['funcao']}"] if peca.get("funcao") else []) + \
               ([f"**Sabias que…** {peca['curiosidade']}"] if peca.get("curiosidade") else [])
        if any(info):
            st.caption("  \n".join(x for x in info if x))
        if not registo["pode_editar"]:
            return
        with st.form(f"f_peca_{registo['id']}_{peca['id']}", border=False):
            c1, c2 = st.columns(2)
            cor = c1.color_picker("Cor", peca["cor"])
            materiais = list(NOMES_MATERIAIS)
            mat = c2.selectbox("Material", materiais, index=materiais.index(peca["material"]["tipo"]),
                               format_func=NOMES_MATERIAIS.get)
            opac = st.slider("Opacidade", 0.05, 1.0, float(peca["material"].get("opacidade", 1.0)), 0.05)
            etiqueta = st.text_input("Etiqueta", peca.get("etiqueta", ""), max_chars=60)
            tamanho = st.slider("Tamanho (×)", 0.2, 3.0, 1.0, 0.1, help="Multiplica o tamanho atual da peça.")
            visivel = st.toggle("Visível", peca.get("visivel", True))
            c3, c4 = st.columns(2)
            aplicar = c3.form_submit_button("Aplicar", type="primary", width="stretch")
            remover = c4.form_submit_button("Remover peça" if not peca.get("glb") else "Esconder", width="stretch")
        if aplicar or remover:
            if remover:
                ops = [{"op": "remover", "id": peca["id"]}]
                nota = f"Removido: {peca['nome']}"
            else:
                campos = {"cor": cor, "material": {"tipo": mat, "opacidade": opac}, "etiqueta": etiqueta, "visivel": visivel}
                if peca.get("glb"):
                    campos["escala"] = round(peca["escala"][0] * tamanho, 3)
                elif tamanho != 1.0:
                    campos["escala"] = [round(v * tamanho, 4) for v in peca["escala"]]
                ops = [{"op": "alterar", "id": peca["id"], "campos": campos}]
                nota = f"Editado: {peca['nome']}"
            try:
                novo, _ = e3.aplicar_operacoes({**registo["modelo"], "_malhas_glb": [peca["id"]] if peca.get("glb") else []}, ops)
                bib.guardar_versao(registo["id"], novo, nota)
                if remover:
                    st.session_state.pop("e3d_sel", None)
                st.rerun()
            except (e3.ErroModelo, b3.Erro3D) as erro:
                st.error(str(erro))


def formulario_publicar(bib, registo: dict, utilizador: dict) -> None:
    import biblioteca3d as b3

    capa_vista = st.session_state.get(f"e3d_capa_{registo['id']}")
    with st.form(f"f_pub_{registo['id']}"):
        titulo = st.text_input("Título *", registo["titulo"], max_chars=100)
        descricao = st.text_area("Descrição *", registo.get("descricao") or registo["modelo"].get("descricao", ""),
                                 max_chars=2000, placeholder="O que mostra o modelo e para que serve no estudo.")
        c1, c2 = st.columns(2)
        cats = list(e3.CATEGORIAS)
        categoria = c1.selectbox("Categoria *", cats, index=cats.index(registo["categoria"]) if registo["categoria"] in cats else len(cats) - 1)
        etiquetas = c2.text_input("Etiquetas * (separadas por vírgulas)", ", ".join(registo.get("etiquetas") or []),
                                  placeholder="ex.: coração, anatomia, 10.º ano")
        st.markdown("**Imagem de capa \\***")
        if capa_vista:
            st.image(capa_vista, width=320, caption="Capturada do visualizador")
        else:
            st.caption("Usa o botão de câmara no visualizador para capturar a vista atual, ou carrega uma imagem.")
        carregada = st.file_uploader("Carregar outra imagem (opcional)", type=["png", "jpg", "jpeg", "webp"])
        visibilidade = st.radio("Visibilidade *", ["publico", "privado"], horizontal=True,
                                index=0 if registo["visibilidade"] == "publico" or not registo["publicado"] else 1,
                                format_func=lambda v: "Pública (aparece na biblioteca)" if v == "publico"
                                else "Privada (só tu e quem convidares)")
        licencas = list(b3.LICENCAS)
        licenca = st.selectbox("Licença e permissões *", licencas,
                               index=licencas.index(registo["licenca"]) if registo.get("licenca") in licencas else 0)
        creditos = st.text_input("Créditos de autoria *", registo.get("creditos") or utilizador["nome"])
        enviar = st.form_submit_button("Publicar" if not registo["publicado"] else "Atualizar publicação", type="primary")
    if enviar:
        capa = carregada.getvalue() if carregada else (capa_vista or registo.get("capa"))
        try:
            bib.publicar(registo["id"], titulo=titulo, descricao=descricao, categoria=categoria, etiquetas=etiquetas,
                         capa=capa, visibilidade=visibilidade, creditos=creditos, licenca=licenca)
            st.session_state.cal_msg = ("Publicado na biblioteca da comunidade." if visibilidade == "publico"
                                        else "Guardado como modelo privado (só tu e quem convidares o veem).")
            st.rerun()
        except b3.Erro3D as erro:
            st.error(str(erro))


def estado_blender(bib, registo: dict) -> None:
    """Linha por baixo do visualizador: o modelo está (ou não) desenhado com o Blender, e o botão para o fazer."""
    modelo = registo["modelo"]
    total = len(mb.hashes(modelo))
    if not total:
        return
    feitas = len(mb.pecas_atualizadas(modelo))
    motor = motor_blender()
    c1, c2 = st.columns([3, 1.3], vertical_alignment="center")
    b = modelo.get("blender") or {}
    if feitas == total:
        c1.caption(f":material/auto_awesome: Desenhado com o {b.get('motor') or 'Blender'}: arestas arredondadas, superfícies "
                   "lisas e materiais realistas.")
    elif feitas:
        c1.caption(f":material/auto_awesome: {feitas} de {total} peças desenhadas com o Blender; as outras mudaram depois."
                   + ("" if motor else " Para as refazer, instala o Blender (grátis, blender.org) neste computador."))
    elif motor:
        c1.caption(f":material/auto_awesome: O {motor} pode refazer este modelo com muito mais qualidade.")
    else:
        c1.caption(":material/auto_awesome: Com o Blender (grátis, blender.org) os modelos ficam muito mais detalhados. "
                   "Depois de o instalar, aparece aqui o botão.")
    if motor and registo.get("pode_editar") and feitas < total:
        if c2.button("Melhorar com o Blender" if not feitas else "Refazer no Blender", icon=":material/auto_awesome:",
                     key=f"e3d_blender_{registo['id']}", width="stretch", type="primary"):
            melhorar_com_blender(bib, registo["id"])
            st.rerun()
    if st.session_state.get("e3d_blender_erro"):
        with st.expander("O Blender não conseguiu melhorar o modelo", icon=":material/warning:"):
            st.code(st.session_state["e3d_blender_erro"][-2000:])


def editor_3d(bib, registo: dict, utilizador: dict) -> None:
    import biblioteca3d as b3

    mid = registo["id"]
    estado = ("Público" if registo["visibilidade"] == "publico" else "Privado") if registo["publicado"] else "Em desenvolvimento"
    c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
    c1.markdown(f"### {escape(registo['titulo'])}")
    c1.markdown(f"<span class='e3d-estado'>{estado}</span> <span class='ec-meta'>· versão {registo['versao_atual']}"
                + (f" · remix de «{escape(registo['origem_titulo'])}» de {escape(registo['origem_autor'] or '')}"
                   if registo.get("origem_id") else "") + "</span>", unsafe_allow_html=True)
    c2.button("Os meus modelos", icon=":material/arrow_back:", width="stretch",
              on_click=ir_3d, kwargs={"e3d_secao": "meus", "e3d_aberto": None})
    if "cal_msg" in st.session_state:
        st.success(st.session_state.pop("cal_msg"), icon=":material/check_circle:")
    glb_id = (registo["modelo"].get("glb") or {}).get("id")
    malhas = st.session_state.get(f"e3d_malhas_{glb_id}", []) if glb_id else []
    esq, dir_ = st.columns([2.15, 1], gap="medium")
    with esq:
        visor_3d(bib, registo, f"visor_ed_{mid}", "e3d_sel", altura=560)
        estado_blender(bib, registo)
        b1, b2, b3_, b4, b5 = st.columns(5)
        if b1.button("Desfazer", icon=":material/undo:", width="stretch", key=f"e3d_undo_{mid}"):
            if bib.desfazer(mid) is None:
                st.toast("Não há nada para desfazer.")
            st.rerun()
        if b2.button("Duplicar", icon=":material/content_copy:", width="stretch", key=f"e3d_dup_{mid}"):
            novo = bib.duplicar(mid)
            ir_3d(e3d_secao="criar", e3d_aberto=novo["id"])
            st.rerun()
        b3_.download_button("JSON", json.dumps(registo["modelo"], ensure_ascii=False, indent=1),
                            file_name=f"{e3.slug(registo['titulo'])}.mondego3d.json", mime="application/json",
                            icon=":material/download:", width="stretch", help="Modelo editável (para abrir noutro computador)")
        with b4.popover("Título", icon=":material/edit:", width="stretch"):
            novo_titulo = st.text_input("Novo título", registo["titulo"], key=f"e3d_tit_{mid}")
            if st.button("Guardar título", key=f"e3d_tit_b_{mid}"):
                try:
                    bib.mudar_titulo(mid, novo_titulo)
                    st.rerun()
                except b3.Erro3D as erro:
                    st.error(str(erro))
        with b5.popover("Apagar", icon=":material/delete:", width="stretch"):
            st.caption("Apaga o modelo e todas as versões. Os remixes de outras pessoas continuam.")
            if st.checkbox("Quero apagar este modelo", key=f"e3d_conf_{mid}") and st.button("Apagar", type="primary", key=f"e3d_del_{mid}"):
                bib.apagar(mid)
                ir_3d(e3d_secao="meus", e3d_aberto=None)
                st.rerun()
        with st.expander("Publicar na comunidade", icon=":material/public:", expanded=False):
            formulario_publicar(bib, registo, utilizador)
        if registo["publicado"] and registo["visibilidade"] == "privado":
            with st.expander("Partilhar com pessoas (modelo privado)", icon=":material/group_add:"):
                email = st.text_input("Email da conta", key=f"e3d_part_{mid}")
                if st.button("Partilhar", key=f"e3d_part_b_{mid}") and email:
                    try:
                        st.success(f"Partilhado com {bib.partilhar(mid, email)}.")
                    except b3.Erro3D as erro:
                        st.error(str(erro))
                for p in bib.partilhas(mid):
                    a, b = st.columns([4, 1], vertical_alignment="center")
                    a.markdown(f"{escape(p['nome'])} <span class='ec-meta'>{escape(p.get('email') or '')}</span>", unsafe_allow_html=True)
                    if b.button("Retirar", key=f"e3d_rp_{mid}_{p['id']}"):
                        bib.remover_partilha(mid, p["id"])
                        st.rerun()
        if registo["publicado"]:
            st.button("Retirar da biblioteca (volta a rascunho)", key=f"e3d_ret_{mid}", type="tertiary",
                      on_click=lambda: bib.retirar_publicacao(mid))
        with st.expander("Histórico de alterações", icon=":material/history:"):
            for v in bib.versoes(mid):
                a, b = st.columns([4, 1.2], vertical_alignment="center")
                a.markdown(f"**v{v['n']}** · {escape(v['nota'] or '')} <span class='ec-meta'>· "
                           f"{str(v['criado_em'])[:16].replace('T', ' ')}</span>", unsafe_allow_html=True)
                if v["n"] != registo["versao_atual"] and b.button("Recuperar", key=f"e3d_rec_{mid}_{v['n']}", width="stretch"):
                    bib.restaurar(mid, v["n"])
                    st.rerun()
    with dir_:
        titulo_cartao("Assistente de edição")
        sel = st.session_state.get("e3d_sel")
        peca = info_peca(registo["modelo"], sel, malhas)
        opcoes_pecas = [p["id"] for p in registo["modelo"]["partes"]] + [m["id"] for m in malhas]
        nomes = {p["id"]: p["nome"] for p in registo["modelo"]["partes"]} | {m["id"]: m["nome"] for m in malhas}
        escolha = st.selectbox("Peça selecionada", [None] + opcoes_pecas, index=([None] + opcoes_pecas).index(sel) if sel in opcoes_pecas else 0,
                               format_func=lambda i: "Nenhuma (modelo inteiro)" if i is None else nomes.get(i, i),
                               key=f"e3d_sel_box_{mid}_{sel}", help="Também podes clicar numa peça no visualizador.")
        if escolha != sel:
            st.session_state.e3d_sel = escolha
            st.rerun()
        so_peca = bool(peca) and st.toggle(f"Alterar só «{peca['nome']}»", value=True, key=f"e3d_so_{mid}")
        historico = st.session_state.setdefault(f"e3d_chat_{mid}", [])
        with st.container(height=260, border=True):
            if not historico:
                st.caption("Pede alterações em linguagem natural, por exemplo: «adiciona etiquetas às estruturas principais», "
                           "«faz um corte transversal», «torna as válvulas mais visíveis». A IA muda só o que pedires.")
            for m in historico[-12:]:
                with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user" else (str(ICONE_PNG) if ICONE_PNG.exists() else None)):
                    md(m["content"])
        rapidas = ["Adicionar etiquetas", "Mais realista", "Corte transversal", "Separar as partes", "Simplificar para estudo",
                   "Cores didáticas"]
        rapida = st.pills("Sugestões", rapidas, key=f"e3d_rap_{mid}_{len(historico)}", label_visibility="collapsed")
        pedido = st.chat_input("Pede uma alteração ao modelo…", key=f"e3d_in_{mid}", disabled=not tem_chave)
        texto = pedido or ({"Adicionar etiquetas": "Adiciona etiquetas curtas a todas as estruturas principais",
                            "Mais realista": "Torna o modelo mais realista: cores e materiais naturais e alguns detalhes",
                            "Corte transversal": "Faz um corte transversal que mostre o interior",
                            "Separar as partes": "Separa as partes (vista explodida)",
                            "Simplificar para estudo": "Simplifica para estudo: remove peças secundárias e usa cores distintas",
                            "Cores didáticas": "Usa cores didáticas e bem distintas em cada estrutura"}.get(rapida) if rapida else None)
        if not tem_chave:
            st.caption(sem_ia_texto("para editar por conversa"))
        if texto and tem_chave:
            editar_modelo_3d(bib, registo, texto, so_peca)
            st.rerun()
        if peca:
            painel_peca(bib, registo, peca)
        else:
            st.caption(f"{len(registo['modelo']['partes'])} peça(s)" + (f" · {len(malhas)} malha(s) do ficheiro" if malhas else ""))


def pagina_criar_3d(bib, utilizador: dict) -> None:
    import biblioteca3d as b3
    import gerador3d as g3

    with st.container(border=True):
        st.markdown("<div class='ec-pergunta-titulo'>Que modelo 3D queres criar?</div>", unsafe_allow_html=True)
        st.caption("Descreve exatamente o que queres (objeto, partes, cores, estilo): a IA faz isso mesmo e no fim verifica "
                   "se o modelo cumpre o pedido. Depois podes afinar por conversa.")
        sugestao = st.pills("Ideias", list(SUGESTOES_3D), key="e3d_sug", label_visibility="collapsed")
        if sugestao and st.session_state.get("_e3d_sug_aplicada") != sugestao:
            st.session_state["_e3d_sug_aplicada"] = sugestao
            st.session_state["e3d_desc"] = SUGESTOES_3D[sugestao][0]
        descricao = st.text_area("Descrição", key="e3d_desc", height=110, label_visibility="collapsed",
                                 placeholder="ex.: Um coração humano em corte com as 4 cavidades, as válvulas e os grandes vasos, "
                                             "artérias a vermelho e veias a azul")
        with st.expander("Opções (por omissão a IA decide a partir da descrição)", icon=":material/tune:"):
            c1, c2, c3 = st.columns(3)
            tipo = c1.selectbox("Tipo de modelo", e3.TIPOS_MODELO, key="e3d_tipo")
            detalhe = c2.segmented_control("Nível de detalhe", list(e3.NIVEIS_DETALHE), default="Alto", key="e3d_det") or "Alto"
            complexidade = c3.selectbox("Complexidade", e3.COMPLEXIDADES, key="e3d_comp")
            c4, c5 = st.columns([1, 2])
            estilo = c4.selectbox("Estilo visual", e3.ESTILOS, key="e3d_estilo")
            incluir = c5.text_input("Elementos que têm de aparecer (opcional)", key="e3d_incluir",
                                    placeholder="ex.: válvula mitral, septo, nódulo sinusal")
            c6, c7 = st.columns(2)
            etiquetas = c6.toggle("Com etiquetas", value=True, key="e3d_etq")
            rever = c7.toggle("Verificar e completar no fim (mais fiel)", value=True, key="e3d_rever",
                              help="Uma segunda passagem da IA compara o modelo com o teu pedido e corrige o que faltar.")
            motor = st.radio("Motor de geração", ["mondego", "meshy"], horizontal=True, key="e3d_motor",
                             format_func=lambda m: "IA do Mondego (peças editáveis, com informação)" if m == "mondego"
                             else "Meshy (malha realista)")
        chave_meshy = cfg["chaves"].get("Meshy", "")
        if motor == "meshy" and not chave_meshy:
            st.info("**A geração realista com o Meshy ainda não está ativa.** Falta a chave da API Meshy (serviço pago, com "
                    "créditos de teste): cria conta em meshy.ai, gera uma chave e cola-a no teu **Perfil → Administração**. "
                    "Entretanto usa a IA do Mondego, que cria modelos com peças editáveis.", icon=":material/info:")
        elif motor == "meshy":
            st.caption("Ligação preparada mas ainda não testada com uma conta real. O modelo é uma malha única: editas cor, "
                       "etiqueta e tamanho, e podes acrescentar peças com a IA.")
        pronto = bool(descricao.strip()) and (tem_chave if motor == "mondego" else bool(chave_meshy))
        if st.button("Criar modelo 3D", type="primary", icon=":material/view_in_ar:", disabled=not pronto):
            if motor == "mondego":
                with a_pensar("A modelar em 3D (pode demorar até um minuto)"):
                    modelo = gerar_modelo_3d(descricao, tipo, detalhe, complexidade, estilo, incluir, etiquetas)
                revisao = ""
                if modelo and rever:
                    with a_pensar("A verificar se o modelo cumpre o teu pedido"):
                        modelo, revisao = rever_modelo_3d(descricao + (f". Tem de incluir: {incluir}" if incluir.strip() else ""), modelo)
                if modelo:
                    try:
                        novo = bib.criar(modelo, nota=f"Criado com IA: {descricao.strip()[:150]}", creditos=utilizador["nome"])
                        blender_automatico(bib, novo["id"])
                        st.session_state[f"e3d_chat_{novo['id']}"] = [
                            {"role": "user", "content": descricao.strip()},
                            {"role": "assistant", "content": f"Criei «{novo['titulo']}» com {len(modelo['partes'])} peças."
                             + (f" Verificação: {revisao}" if revisao else "")
                             + " Clica numa peça para veres o que é, ou pede-me alterações."}]
                        ir_3d(e3d_secao="criar", e3d_aberto=novo["id"])
                        st.rerun()
                    except b3.Erro3D as erro:
                        st.error(str(erro))
            else:
                try:
                    tarefa = g3.GeradorMeshy(chave_meshy).iniciar(descricao)
                    st.session_state.e3d_tarefa = {"id": tarefa, "descricao": descricao.strip()}
                    st.rerun()
                except g3.ErroGerador as erro:
                    st.error(str(erro))
        if not tem_chave and motor == "mondego":
            st.caption(sem_ia_texto("para criar modelos"))
    if st.session_state.get("e3d_tarefa"):
        acompanhar_meshy(bib, utilizador)
    with st.expander("Abrir um modelo que já tens (GLB, glTF ou .mondego3d.json)", icon=":material/upload_file:"):
        ficheiro = st.file_uploader("Ficheiro 3D", type=["glb", "gltf", "json"], key=f"e3d_up_{st.session_state.versao_upload}",
                                    label_visibility="collapsed")
        if ficheiro:
            try:
                dados = ficheiro.getvalue()
                if ficheiro.name.lower().endswith(".json"):
                    novo = bib.criar(e3.normalizar_modelo(dados.decode("utf-8")), nota=f"Aberto de {ficheiro.name}",
                                     creditos=utilizador["nome"])
                else:
                    gid = bib.guardar_glb(ficheiro.name, dados)
                    novo = bib.criar({"titulo": Path(ficheiro.name).stem[:100], "partes": [],
                                      "glb": {"id": gid, "nome": ficheiro.name}}, nota=f"Aberto de {ficheiro.name}",
                                     creditos=utilizador["nome"])
                st.session_state.versao_upload += 1
                ir_3d(e3d_secao="criar", e3d_aberto=novo["id"])
                st.rerun()
            except (b3.Erro3D, e3.ErroModelo, UnicodeDecodeError) as erro:
                st.error(str(erro) if not isinstance(erro, UnicodeDecodeError) else "O ficheiro não é um modelo válido.")
    recentes = bib.meus("rascunhos")[:3]
    if recentes:
        titulo_cartao("Continuar a trabalhar")
        grelha_3d(recentes, "cont", utilizador["id"])


@st.fragment(run_every=5)
def acompanhar_meshy(bib, utilizador: dict) -> None:
    import biblioteca3d as b3
    import gerador3d as g3

    tarefa = st.session_state.get("e3d_tarefa")
    if not tarefa:
        return
    with st.container(border=True):
        try:
            gerador = g3.GeradorMeshy(cfg["chaves"].get("Meshy", ""))
            est = gerador.estado(tarefa["id"])
        except g3.ErroGerador as erro:
            st.error(str(erro))
            if st.button("Cancelar", key="e3d_tar_x"):
                st.session_state.pop("e3d_tarefa", None)
                st.rerun()
            return
        if est["estado"] in ("PENDING", "IN_PROGRESS"):
            st.progress(est["progresso"] / 100, text=f"O Meshy está a gerar o modelo… {est['progresso']}%")
            return
        st.session_state.pop("e3d_tarefa", None)
        if est["estado"] != "SUCCEEDED" or not est["glb"]:
            st.error(f"A geração falhou: {est['erro'] or est['estado']}")
            return
        try:
            gid = bib.guardar_glb("meshy.glb", gerador.descarregar(est["glb"]))
            novo = bib.criar({"titulo": tarefa["descricao"][:100], "partes": [], "glb": {"id": gid, "nome": "meshy.glb"}},
                             nota=f"Gerado pelo Meshy: {tarefa['descricao'][:150]}", creditos=utilizador["nome"])
            ir_3d(e3d_secao="criar", e3d_aberto=novo["id"])
            st.rerun(scope="app")
        except (g3.ErroGerador, b3.Erro3D) as erro:
            st.error(str(erro))


def pagina_ver_3d(bib, mid: str, utilizador: dict | None) -> None:
    import biblioteca3d as b3

    try:
        registo = bib.obter(mid)
    except b3.Erro3D as erro:
        st.error(str(erro))
        st.button("Voltar à biblioteca", on_click=ir_3d, kwargs={"e3d_ver": None})
        return
    vistos = st.session_state.setdefault("_vistos3d", set())
    if mid not in vistos:
        vistos.add(mid)
        try:
            bib.registar_visualizacao(mid)
            registo["visualizacoes"] += 1
        except b3.Erro3D:
            pass
    c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
    c1.markdown(f"### {escape(registo['titulo'])}")
    c1.markdown(f"<span class='ec-meta'>por <b>{escape(registo['dono_nome'])}</b> · {escape(registo['categoria'])} · "
                f"{str(registo.get('publicado_em') or registo['criado_em'])[:10]} · {registo['gostos']} gosto(s) · "
                f"{registo['visualizacoes']} visualizações</span>", unsafe_allow_html=True)
    c2.button("Biblioteca", icon=":material/arrow_back:", width="stretch", on_click=ir_3d, kwargs={"e3d_ver": None})
    esq, dir_ = st.columns([2.15, 1], gap="medium")
    with esq:
        visor_3d(bib, registo, f"visor_ver_{mid}", "e3d_sel_ver", altura=540)
    with dir_:
        if registo.get("etiquetas"):
            st.markdown("<div class='e3d-chips'>" + "".join(f"<span class='e3d-chip'>#{escape(t)}</span>" for t in registo["etiquetas"])
                        + "</div>", unsafe_allow_html=True)
        md(registo.get("descricao") or "")
        peca = info_peca(registo["modelo"], st.session_state.get("e3d_sel_ver"), [])
        if peca:
            with st.container(border=True):
                st.markdown(f"**{escape(peca['nome'])}**")
                st.caption("  \n".join(x for x in [peca.get("descricao") or "Sem descrição.",
                                                     f"**Função:** {peca['funcao']}" if peca.get("funcao") else "",
                                                     f"**Sabias que…** {peca['curiosidade']}" if peca.get("curiosidade") else ""] if x))
        else:
            st.caption("Clica numa peça do modelo para saberes o que é.")
        if utilizador:
            a, b = st.columns(2)
            if a.button(("Gosto" if not registo["gostei"] else "Já não gosto") + f" · {registo['gostos']}",
                        icon=":material/favorite:", width="stretch", type="primary" if registo["gostei"] else "secondary"):
                bib.gostar(mid)
                st.rerun()
            if b.button("Favorito" if not registo["favorito"] else "Nos favoritos", icon=":material/star:", width="stretch",
                        type="primary" if registo["favorito"] else "secondary"):
                bib.favorito(mid)
                st.rerun()
            with st.popover("Adicionar a uma coleção", icon=":material/collections_bookmark:", width="stretch"):
                colecoes = bib.colecoes()
                if colecoes:
                    escolha = st.selectbox("Coleção", [c["id"] for c in colecoes],
                                           format_func=lambda i: next(c["nome"] for c in colecoes if c["id"] == i), key=f"col_{mid}")
                    if st.button("Adicionar", key=f"col_b_{mid}"):
                        bib.adicionar_a_colecao(escolha, mid)
                        st.success("Adicionado.")
                nova = st.text_input("Ou cria uma coleção nova", key=f"col_n_{mid}")
                if st.button("Criar e adicionar", key=f"col_nb_{mid}") and nova:
                    try:
                        bib.adicionar_a_colecao(bib.criar_colecao(nova), mid)
                        st.success("Coleção criada.")
                    except b3.Erro3D as erro:
                        st.error(str(erro))
            if registo["pode_remix"]:
                if st.button("Remix com IA", icon=":material/auto_awesome:", type="primary", width="stretch",
                             help="Cria uma cópia tua deste modelo para modificares com a IA. O original não muda."):
                    copia = bib.remix(mid)
                    st.session_state[f"e3d_chat_{copia['id']}"] = [{"role": "assistant", "content":
                        f"Esta é a tua cópia de «{registo['titulo']}», de {registo['dono_nome']}. Pede-me alterações: o "
                        "original não muda e os créditos ficam guardados."}]
                    ir_3d(e3d_secao="criar", e3d_aberto=copia["id"], e3d_ver=None)
                    st.rerun()
            elif registo["pode_editar"]:
                st.button("Abrir no editor", icon=":material/edit:", width="stretch",
                          on_click=ir_3d, kwargs={"e3d_secao": "criar", "e3d_aberto": mid, "e3d_ver": None})
            elif not registo.get("permite_remix"):
                st.caption("O autor não autorizou remix deste modelo.")
        else:
            st.caption("Entra na tua conta (em «Os meus modelos») para gostar, guardar ou fazer remix.")
        st.caption(f"**Créditos:** {registo.get('creditos') or registo['dono_nome']}  \n**Licença:** {registo.get('licenca') or '—'}"
                   + (f"  \n**Baseado em:** «{registo['origem_titulo']}» de {registo['origem_autor']}" if registo.get("origem_id") else ""))


def pagina_explorar_3d(bib, utilizador: dict | None) -> None:
    c1, c2 = st.columns([2.4, 1.2], vertical_alignment="bottom")
    texto = c1.text_input("Pesquisar", key="e3d_q", placeholder="Pesquisar por título, descrição, categoria ou etiqueta",
                          label_visibility="collapsed")
    ordem = c2.segmented_control("Ordenar", ["populares", "recentes", "vistos"], default="populares", key="e3d_ordem",
                                 format_func={"populares": "Populares", "recentes": "Recentes", "vistos": "Mais vistos"}.get,
                                 label_visibility="collapsed") or "populares"
    categoria = st.pills("Categoria", list(e3.CATEGORIAS), key="e3d_cat", label_visibility="collapsed")
    resultados = bib.pesquisar(texto, categoria, ordem)
    if resultados:
        st.caption(f"{len(resultados)} modelo(s)" + (f" para «{texto}»" if texto.strip() else ""))
        grelha_3d(resultados, "exp", (utilizador or {}).get("id"))
    elif texto.strip() or categoria:
        st.info("Nenhum modelo corresponde à pesquisa. Experimenta outras palavras ou outra categoria.")
    else:
        with st.container(border=True):
            st.markdown("**Ainda não há modelos publicados.**")
            st.caption("Sê o primeiro: cria um modelo com IA e publica-o na comunidade.")
            st.button("Criar com IA", type="primary", icon=":material/auto_awesome:", on_click=ir_3d, kwargs={"e3d_secao": "criar"})


def pagina_meus_3d(bib, utilizador: dict) -> None:
    import biblioteca3d as b3

    filtros = {"todos": "Todos", "rascunhos": "Em desenvolvimento", "publicos": "Públicos", "privados": "Privados",
               "partilhados": "Partilhados comigo", "favoritos": "Favoritos", "colecoes": "Coleções"}
    filtro = st.pills("Filtro", list(filtros), default="todos", key="e3d_filtro", format_func=filtros.get,
                      label_visibility="collapsed") or "todos"
    if filtro == "colecoes":
        with st.popover("Nova coleção", icon=":material/add:"):
            nome = st.text_input("Nome da coleção", key="col_nova")
            if st.button("Criar", key="col_nova_b"):
                try:
                    bib.criar_colecao(nome)
                    st.rerun()
                except b3.Erro3D as erro:
                    st.error(str(erro))
        colecoes = bib.colecoes()
        if not colecoes:
            st.caption("Ainda não tens coleções. Abre um modelo da biblioteca e usa «Adicionar a uma coleção».")
        for c in colecoes:
            with st.expander(f"{c['nome']} · {c['n']} modelo(s)", icon=":material/collections_bookmark:"):
                itens = bib.itens_colecao(c["id"])
                if itens:
                    grelha_3d(itens, f"col{c['id'][:6]}", utilizador["id"])
                if st.button("Apagar coleção", key=f"col_del_{c['id']}", type="tertiary"):
                    bib.apagar_colecao(c["id"])
                    st.rerun()
        return
    lista = bib.meus(filtro)
    if lista:
        grelha_3d(lista, f"meus_{filtro}", utilizador["id"])
    else:
        st.info({"todos": "Ainda não tens modelos. Cria o primeiro em «Criar com IA».",
                 "rascunhos": "Não tens modelos em desenvolvimento.", "publicos": "Ainda não publicaste nenhum modelo.",
                 "privados": "Não tens modelos privados publicados.", "partilhados": "Ninguém partilhou modelos contigo.",
                 "favoritos": "Ainda não tens favoritos."}.get(filtro, ""))


def mudar_secao_3d() -> None:
    nova = st.session_state.get("e3d_secao_sel")
    if nova:
        navegar("estudio3d", e3d_secao=nova, e3d_ver=None, e3d_aberto=None if nova != "criar" else st.session_state.get("e3d_aberto"))


if vista == "estudio3d":
    import biblioteca3d as b3
    import salas_backend as sb

    st.markdown(ESTILO_3D, unsafe_allow_html=True)
    secao = st.session_state.get("e3d_secao", "explorar")
    cabecalho("3D Studio", "Explora, cria com IA e partilha modelos 3D interativos.")
    st.session_state.e3d_secao_sel = secao
    st.segmented_control("Secção", list(SECOES_3D), format_func=SECOES_3D.get, key="e3d_secao_sel",
                         on_change=mudar_secao_3d, label_visibility="collapsed")
    try:
        bib3 = biblioteca_3d()
        utilizador3 = bib3.contas.atual()
    except (sb.ErroSalas, b3.Erro3D) as erro:
        st.error(str(erro))
        st.stop()
    if secao == "explorar":
        if st.session_state.get("e3d_ver"):
            pagina_ver_3d(bib3, st.session_state.e3d_ver, utilizador3)
        else:
            pagina_explorar_3d(bib3, utilizador3)
        st.stop()
    if not utilizador3:
        with st.container(border=True):
            ecra_contas(bib3.contas, "Entra para criar e guardar modelos 3D")
            st.caption("Usa a mesma conta das Salas. " + ("No modo deste computador, as contas ficam guardadas só aqui."
                                                          if bib3.nome == "local" else ""))
        st.stop()
    if secao == "criar":
        if st.session_state.get("e3d_aberto"):
            try:
                registo3 = bib3.obter(st.session_state.e3d_aberto)
            except b3.Erro3D as erro:
                st.error(str(erro))
                st.session_state.pop("e3d_aberto", None)
                st.stop()
            if not registo3["pode_editar"]:
                ir_3d(e3d_secao="explorar", e3d_ver=registo3["id"], e3d_aberto=None)
                st.rerun()
            editor_3d(bib3, registo3, utilizador3)
        else:
            pagina_criar_3d(bib3, utilizador3)
    else:
        if "cal_msg" in st.session_state:
            st.success(st.session_state.pop("cal_msg"), icon=":material/check_circle:")
        pagina_meus_3d(bib3, utilizador3)
    st.stop()


# =============================================================== CADEIRA (cabeçalho · resumo · separadores: Conversa e ferramentas)
ESTUDIO = {"Conversa": ":material/forum:", "Resumo": ":material/summarize:", "Guia de estudo": ":material/menu_book:",
           "Mapa de conceitos": ":material/account_tree:", "Quiz": ":material/quiz:", "Flashcards": ":material/style:",
           "Teste": ":material/edit_note:", "Slides": ":material/slideshow:", "Plano": ":material/calendar_month:",
           "Progresso": ":material/trending_up:"}
SISTEMA_FONTES = (
    "És um tutor para estudantes, calmo e claro. Respondes APENAS com base nas fontes entre <fontes></fontes> "
    "(como o NotebookLM). Depois de cada afirmação importante indicas a origem entre parênteses retos, por exemplo "
    "[ficheiro.pdf, p. 3]. Se a resposta não estiver nas fontes, dizes que não está nos documentos selecionados e "
    "sugeres que fontes acrescentar. Explicas com exemplos simples. " + mt.REGRAS_FORMULAS + FORMATO_EXATO
    + ESTILO_RESPOSTA + USO_DO_ALUNO
)


def dot_mapa(mapa: dict) -> str:
    """Converte o mapa de conceitos (JSON) num grafo Graphviz. Caixas claras com letra escura em qualquer tema."""
    def q(texto) -> str:
        return '"' + str(texto).replace('"', "'").replace("\\", "/")[:70] + '"'
    linhas = ['graph G {', 'graph [bgcolor="transparent", rankdir=LR, pad=0.3, nodesep=0.25, ranksep=0.7];',
              'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#DCE3E1", '
              'fillcolor="#FFFFFF", fontcolor="#12202A", margin="0.18,0.08"];', 'edge [color="#B9B2A3", penwidth=1.2];',
              f'centro [label={q(mapa.get("centro", "Tema"))}, fillcolor="#17798A", color="#17798A", fontcolor="#FFFFFF", fontsize=14];']
    for i, ramo in enumerate((mapa.get("ramos") or [])[:8]):
        linhas += [f'r{i} [label={q(ramo.get("conceito", ""))}, fillcolor="#DDF0F1", color="#B5DDE2"];', f"centro -- r{i};"]
        for k, detalhe in enumerate((ramo.get("detalhes") or [])[:5]):
            linhas += [f"r{i}d{k} [label={q(detalhe)}, fontsize=10];", f"r{i} -- r{i}d{k};"]
    return "\n".join(linhas + ["}"])


def chave_fonte(cadeira: str, nome: str) -> str:
    import hashlib
    return f"src_{hashlib.md5((cadeira + '|' + nome).encode()).hexdigest()[:12]}"


def conversa_cadeira(cadeira: str, dados: dict, escolhidos: list, tema: str) -> None:
    """Conversa da cadeira: responde só com as fontes selecionadas, com citações."""
    historico = dados.setdefault("chat", [])
    avatar = str(ICONE_PNG) if ICONE_PNG.exists() else None
    chave_p = f"pend_cad_{cadeira}"
    if not historico:
        with st.container(key=f"cadsug_{chave_curta(cadeira)}"):
            st.markdown(f"<div class='cad-vazio'><div class='cad-vazio-t'>O que queres saber de {escape(cadeira)}?</div>"
                        f"<div class='cad-vazio-s'>Respondo só com as {len(escolhidos)} fonte(s) selecionada(s) e indico o "
                        "ficheiro e a página de cada resposta.</div></div>", unsafe_allow_html=True)
            sugestoes = ["Resume as fontes em 5 pontos", "Quais são os conceitos-chave?",
                         "Explica-me o tema mais difícil com um exemplo", "Faz-me 3 perguntas para ver se sei"]
            st.pills("Sugestões", sugestoes, key=f"sugcad_{cadeira}", label_visibility="collapsed",
                     on_change=lambda: st.session_state.update({chave_p: st.session_state.get(f"sugcad_{cadeira}"),
                                                                f"sugcad_{cadeira}": None}))
    else:
        _, c_nova = st.columns([5, 1.3])
        if c_nova.button("Nova conversa", icon=":material/add_comment:", key=f"limpa_cad_{cadeira}", width="stretch"):
            dados["chat"] = []
            guardar(cadeira)
            st.rerun()
    for m in historico:
        with st.chat_message(m["role"], avatar=avatar if m["role"] == "assistant" else None):
            md(m["content"])
    with fixo_no_fundo():
        pergunta = st.chat_input("Pergunta sobre as fontes…", key=f"chat_cad_{cadeira}", disabled=not tem_chave)
    pergunta = st.session_state.pop(chave_p, None) or pergunta
    if not pergunta:
        return
    with st.chat_message("user"):
        st.markdown(pergunta)
    fontes = selecionar_texto({n: dados["ficheiros"][n] for n in escolhidos}, f"{tema} {pergunta}")
    idioma = " Answer in English." if cfg.get("idioma") == "English" else " Respondes em português de Portugal."
    mensagens = [{"role": "user", "content": f"{info_aluno()}\n\n<fontes>\n{fontes}\n</fontes>\n\nVou fazer perguntas sobre estas fontes."},
                 {"role": "assistant", "content": "Combinado."}] + historico[-12:] + [{"role": "user", "content": pergunta}]
    with st.chat_message("assistant", avatar=avatar):
        try:
            resposta = escrever_fluxo(chamar_ia_stream(mensagens, sistema=SISTEMA_FONTES + idioma),
                                                    "A ler as fontes")
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
    resposta = resposta if isinstance(resposta, str) else "".join(map(str, resposta))
    if resposta:
        historico += [{"role": "user", "content": pergunta}, {"role": "assistant", "content": resposta}]
        guardar(cadeira)
        st.rerun()  # volta a desenhar a conversa (sem o ecrã de boas-vindas e com o botão «Nova conversa»)


# ---------------------------------------------------------------- quiz e flashcards (componentes no browser, estilo NotebookLM)
def dados_quiz_id(perguntas: list) -> str:
    return chave_curta(json.dumps([q.get("pergunta") for q in perguntas], ensure_ascii=False))


def explicar_cartao(cartao: dict, fontes: str) -> None:
    pedido = (f"Explica-me este flashcard de forma simples, passo a passo e com um exemplo, com base nas fontes.\n"
              f"Pergunta: {cartao.get('frente')}\nResposta: {cartao.get('verso')}")
    with st.container(border=True):
        try:
            texto = escrever_fluxo(chamar_ia_stream([{"role": "user", "content": f"<fontes>\n{fontes}\n</fontes>\n\n{pedido}"}],
                                                    sistema=SISTEMA_FONTES), "A explicar")
            cartao["explicacao"] = texto
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)


cadeira = st.session_state.get("cadeira_atual")
if cadeira not in st.session_state.cadeiras:
    ir("salas")
dados = st.session_state.cadeiras[cadeira]
obj = objetivo(dados)
proxima_aval = repo().proxima(cadeira)
n_aval = len(repo().da_cadeira(cadeira))
if "cal_msg" in st.session_state:
    st.success(st.session_state.pop("cal_msg"), icon=":material/check_circle:")

chave_est = f"estudio_{cadeira}"
chave_ultimo = f"_ultimo_estudio_{cadeira}"  # o separador escolhido fica lembrado ao sair e voltar à cadeira
if "ferramenta_pendente" in st.session_state:
    st.session_state[chave_est] = st.session_state.pop("ferramenta_pendente")
if st.session_state.get(chave_est) not in ESTUDIO:
    st.session_state[chave_est] = st.session_state.get(chave_ultimo) if st.session_state.get(chave_ultimo) in ESTUDIO \
        else "Conversa"
estudio = st.session_state[chave_est]
st.session_state[chave_ultimo] = estudio
docs = list(dados["ficheiros"])
desligadas = set(dados.get("fontes_desligadas") or []) & set(docs)
escolhidos = [n for n in docs if n not in desligadas]
tema = st.session_state.get(f"tema_foco_{cadeira}", "")
ICONE_FONTE = {"pdf": ":material/picture_as_pdf:", "pptx": ":material/slideshow:", "ppt": ":material/slideshow:",
               "docx": ":material/article:", "doc": ":material/article:", "png": ":material/image:", "jpg": ":material/image:",
               "jpeg": ":material/image:", "webp": ":material/image:", "txt": ":material/notes:", "md": ":material/notes:"}


def icone_fonte(nome_f: str) -> str:
    return ICONE_FONTE.get(nome_f.rsplit(".", 1)[-1].lower() if "." in nome_f else "", ":material/description:")


def mudar_fonte(cadeira_: str, nome_f: str, chave_w: str) -> None:
    d_ = st.session_state.cadeiras[cadeira_]
    off = set(d_.get("fontes_desligadas") or [])
    (off.discard if st.session_state.get(chave_w) else off.add)(nome_f)
    d_["fontes_desligadas"] = sorted(off)
    guardar(cadeira_)


def todas_fontes(cadeira_: str, ligar: bool) -> None:
    d_ = st.session_state.cadeiras[cadeira_]
    d_["fontes_desligadas"] = [] if ligar else sorted(d_["ficheiros"])
    for n_ in d_["ficheiros"]:
        st.session_state.pop("dlg_" + chave_fonte(cadeira_, n_), None)
    guardar(cadeira_)


@janela("Fontes da sala", width="large")
def gerir_fontes(cadeira_: str) -> None:
    d_ = st.session_state.cadeiras[cadeira_]
    nomes = list(d_["ficheiros"])
    off = set(d_.get("fontes_desligadas") or [])
    enviados_ = st.file_uploader("Adicionar fontes (PDF, PowerPoint, Word, texto ou fotografias)", type=TIPOS_FICHEIRO,
                                 accept_multiple_files=True, key=f"up_dlg_{cadeira_}_{st.session_state.versao_upload}")
    if enviados_:
        with a_pensar("A ler as fontes"):
            n_ = adicionar_ficheiros(cadeira_, enviados_)
        st.session_state.versao_upload += 1
        st.toast(f"{n_} fonte(s) adicionada(s).", icon=":material/check_circle:")
        st.rerun()
    st.text_input("Focar num tema (opcional)", value=st.session_state.get(f"tema_foco_{cadeira_}", ""),
                  placeholder="ex.: valores próprios — as respostas e os materiais dão prioridade a este tema",
                  key=f"tema_dlg_{cadeira_}",
                  on_change=lambda: st.session_state.update({f"tema_foco_{cadeira_}": st.session_state[f"tema_dlg_{cadeira_}"].strip()}))
    if not nomes:
        st.caption("Ainda sem fontes.")
        return
    c1, c2, c3 = st.columns([2.2, 1, 1], vertical_alignment="bottom")
    procura = c1.text_input("Procurar", placeholder="Procurar uma fonte…", key=f"proc_{cadeira_}", label_visibility="collapsed")
    c2.button("Todas", icon=":material/done_all:", width="stretch", key=f"todas_{cadeira_}", on_click=todas_fontes, args=(cadeira_, True))
    c3.button("Nenhuma", icon=":material/remove_done:", width="stretch", key=f"nenhuma_{cadeira_}", on_click=todas_fontes, args=(cadeira_, False))
    st.caption(f"{len(nomes) - len(off & set(nomes))} de {len(nomes)} selecionadas. As que desligares não entram nas "
               "respostas nem nos materiais (ficam guardadas).")
    pend = st.session_state.get(f"apagar_fonte_{cadeira_}")
    with st.container(height=360, border=False):
        for nome_f in [n for n in nomes if procura.lower() in n.lower()]:
            a, b, c = st.columns([8, 2.2, 1], vertical_alignment="center")
            chave_w = "dlg_" + chave_fonte(cadeira_, nome_f)
            a.checkbox(f"{icone_fonte(nome_f)} {nome_f}", value=nome_f not in off, key=chave_w,
                       on_change=mudar_fonte, args=(cadeira_, nome_f, chave_w))
            b.caption(f"~{max(1, round(len(d_['ficheiros'][nome_f]) / 2500))} pág.")
            if pend == nome_f:
                if c.button("Sim", key=f"conf_rem_{chave_w}", type="primary", help="Confirmar: apagar esta fonte"):
                    del d_["ficheiros"][nome_f]
                    d_["fontes_desligadas"] = [x for x in d_.get("fontes_desligadas") or [] if x != nome_f]
                    guardar(cadeira_)
                    st.session_state.pop(f"apagar_fonte_{cadeira_}", None)
                    st.rerun(scope="fragment")
            elif c.button("", icon=":material/delete:", key=f"rem_{chave_w}", type="tertiary", help="Apagar esta fonte"):
                st.session_state[f"apagar_fonte_{cadeira_}"] = nome_f
                st.rerun(scope="fragment")
    if pend:
        st.caption(f"Carrega em **Sim** para apagar «{pend}» de vez.")


def mudar_estudio(chave: str, chave_u: str) -> None:
    """Separadores da cadeira: carregar no que já está escolhido não o desliga."""
    if st.session_state.get(chave) not in ESTUDIO:
        st.session_state[chave] = st.session_state.get(chave_u) or "Conversa"
    st.session_state[chave_u] = st.session_state[chave]


ROTULO_ESTUDIO = {"Guia de estudo": "Guia", "Mapa de conceitos": "Mapa"}
DESCRICAO_ESTUDIO = {
    "Conversa": "Pergunta o que quiseres: respondo só com as fontes selecionadas e digo de onde vem cada resposta.",
    "Resumo": "Resumo por temas, com os conceitos-chave, fórmulas, exemplos, erros comuns e o que costuma sair.",
    "Guia de estudo": "Temas principais, perguntas de revisão com resposta, glossário e por onde começar.",
    "Mapa de conceitos": "Os conceitos principais da matéria e como se ligam entre si.",
    "Quiz": "Perguntas de escolha múltipla feitas a partir das fontes, com dicas e a explicação de cada opção.",
    "Flashcards": "Cartões com repetição espaçada: cada um volta no dia certo para não o esqueceres.",
    "Teste": "Perguntas de desenvolvimento como num exame. Escreves as respostas e a IA corrige com cotação.",
    "Slides": "Diapositivos do mais simples ao mais complexo, com notas do professor e PowerPoint para descarregar.",
    "Plano": "Plano de preparação para uma avaliação: o que estudar em cada dia, no Calendário.",
    "Progresso": "Notas dos quizzes e testes, flashcards dominados e os temas onde estás mais forte e mais fraco.",
}
ESTILO_CADEIRA = """<style>
div.stVerticalBlock.st-key-cad_topo { border:none !important; background:transparent !important; padding:0 !important;
  box-shadow:none !important; margin-bottom:0.35rem; }
.cad-hero { display:flex; align-items:center; gap:0.9rem; min-width:0; }
.cad-ico { width:48px; height:48px; border-radius:var(--r-lg); background:var(--acento-claro); color:var(--acento); flex:none;
  display:flex; align-items:center; justify-content:center; }
.cad-ico span { font-size:26px; line-height:1; }
.cad-nome { font-size:var(--t-2xl); font-weight:650; letter-spacing:-0.028em; color:var(--texto); line-height:1.15;
  margin:0 !important; overflow-wrap:anywhere; }
.cad-chips { display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.45rem; }
.cad-chip { font-size:var(--t-xs); font-weight:500; padding:0.1rem 0.6rem; border-radius:var(--r-pilula); background:var(--bolha);
  color:var(--texto); white-space:nowrap; }
.cad-chip.urg { background:var(--acento-claro); color:var(--acento-esc); font-weight:600; }
.cad-chip.so-tu { display:inline-flex; align-items:center; gap:0.25rem; }
.cad-chip.so-tu .material-symbols-rounded { font-size:0.85rem; }
.cad-desc { color:var(--suave); font-size:0.9rem; margin:0.15rem 0 0.9rem; }
.cad-aval { display:flex; align-items:center; gap:0.5rem; margin:0.15rem 0 0.55rem; color:var(--texto); }
.cad-aval i { width:9px; height:9px; border-radius:50%; flex:none; }
.cad-aval span { font-size:0.8rem; color:var(--suave); display:block; }
.cad-vazio { text-align:center; padding:1.6rem 1rem 0.4rem; }
.cad-vazio-t { font-size:var(--t-xl); font-weight:650; letter-spacing:-0.02em; color:var(--texto); }
.cad-vazio-s { color:var(--suave); max-width:560px; margin:0.4rem auto 0.6rem; font-size:0.95rem; line-height:1.55; }
.st-key-vista_cadeira [data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarUser"])) {
  max-width:860px; margin-left:auto; margin-right:auto; }
.st-key-vista_cadeira [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  margin-right:max(0px, calc((100% - 860px) / 2)); max-width:min(85%, 730px); }
div.stVerticalBlock[class*="st-key-cadsug_"] { align-items:center; }
div[class*="st-key-cadsug_"] [data-testid="stButtonGroup"] button { border-radius:999px !important; }
.st-key-cad_separadores [data-testid="stSegmentedControl"] button { padding-left:0.7rem; padding-right:0.7rem; }
/* no telemóvel as ferramentas ficam numa só faixa que desliza para o lado (em vez de 4 linhas de botões) */
@media (max-width: 640px) {
  .st-key-cad_separadores [data-testid="stButtonGroup"] { overflow-x:auto; scrollbar-width:none; overscroll-behavior-x:contain;
    -webkit-mask-image:linear-gradient(90deg, #000 85%, transparent); mask-image:linear-gradient(90deg, #000 85%, transparent); }
  .st-key-cad_separadores [data-testid="stButtonGroup"]::-webkit-scrollbar { display:none; }
  .st-key-cad_separadores [data-testid="stButtonGroup"] > div { flex-wrap:nowrap !important; width:max-content; padding-right:3rem; }
  .st-key-cad_separadores [data-testid="stButtonGroup"] button { flex:none; white-space:nowrap; }
}
</style>"""
st.markdown(estilos(ESTILO_INICIO, ESTILO_CADEIRA), unsafe_allow_html=True)

abrir_plano_se_pedido()

# ---------------- cabeçalho: nome, próxima avaliação e as ações da cadeira (fontes, avaliações, mais)
futuras_c = [x for x in repo().da_cadeira(cadeira) if not av.ja_passou(x)]
chips_cad = []
if proxima_aval:
    chips_cad.append(("urg" if av.dias_ate(proxima_aval, date.today()) <= 7 else "",
                      f"{proxima_aval['nome']} · {fmt_data(proxima_aval['data'], False)} · {av.texto_faltam(proxima_aval)}"))
if obj.get("nota_alvo"):
    chips_cad.append(("", f"objetivo {obj['nota_alvo']} valores"))
if tema:
    chips_cad.append(("", f"foco: {curto(tema, 40)}"))
st.button("Salas", icon=":material/arrow_back:", key="voltar_salas_p", type="tertiary", on_click=navegar, args=("salas",),
          kwargs={"sala_aberta": None})
with st.container(border=True, key="cad_topo"):
    c1, c2, c3, c4 = st.columns([3.5, 1.25, 1.45, 1.15], vertical_alignment="center")
    sala_p = sala_pessoal(cadeira)
    c1.markdown(f"<div class='cad-hero'>{ico_sala_html(sala_p, 'cad-ico')}"
                f"<div class='mi-encolhe'><div class='cad-nome'>{escape(cadeira)}</div><div class='cad-chips'>"
                "<span class='cad-chip so-tu'><span class='material-symbols-rounded' translate='no' aria-hidden='true'>lock"
                "</span>Só tu</span>"
                + ("".join(f"<span class='cad-chip {c_}'>{escape(t_)}</span>" for c_, t_ in chips_cad)
                   or "<span class='cad-chip'>sem avaliações marcadas</span>") + "</div></div></div>",
                unsafe_allow_html=True)
    if c2.button(f"Fontes · {len(docs)}", key=f"gerir_fontes_{cadeira}", icon=":material/folder_open:", width="stretch",
                 help="Adicionar fontes, escolher as que entram nas respostas, procurar, apagar e focar num tema."):
        gerir_fontes(cadeira)
    with c3.popover(f"Avaliações · {len(futuras_c)}", icon=":material/event:", width="stretch"):
        for r in futuras_c[:5]:
            st.markdown(f"<div class='cad-aval'><i style='background:{av.CORES[r['tipo']]}'></i><div><b>{escape(r['nome'])}</b>"
                        f"<span>{fmt_quando(r)} · {av.texto_faltam(r)}</span></div></div>", unsafe_allow_html=True)
        if not futuras_c:
            st.caption("Sem avaliações futuras nesta sala.")
        st.button("Nova avaliação", icon=":material/add:", type="primary", width="stretch", key=f"nova_aval_{cadeira}",
                  on_click=navegar, args=("calendario",), kwargs={"nova_avaliacao_cadeira": cadeira})
        st.button("Abrir o calendário", icon=":material/calendar_month:", width="stretch", key=f"cal_cad_{cadeira}",
                  on_click=navegar, args=("calendario",))
    if c4.button("Definições", icon=":material/settings:", width="stretch", key=f"def_pessoal_{cadeira}",
                 help="Nome, ícone, cor, descrição, objetivo e apagar a sala."):
        dialogo_definicoes_pessoal(cadeira)

# ---------------- sem fontes: um só passo, adicionar as fontes
if not docs:
    with st.container(border=True):
        st.markdown("<div class='cad-vazio'><div class='cad-vazio-t'>Adiciona as fontes desta sala</div>"
                    "<div class='cad-vazio-s'>Sebentas, slides, apontamentos ou fotografias do quadro. Depois podes "
                    "conversar com elas e criar resumos, quizzes, flashcards, testes e um plano de estudo.</div></div>",
                    unsafe_allow_html=True)
        enviados = st.file_uploader("Carregar fontes", type=TIPOS_FICHEIRO, accept_multiple_files=True,
                                    key=f"up_vazio_{cadeira}_{st.session_state.versao_upload}", label_visibility="collapsed")
        if enviados:
            with a_pensar("A ler as fontes"):
                adicionar_ficheiros(cadeira, enviados)
            st.session_state.versao_upload += 1
            st.rerun()
    st.stop()

# ---------------- resumo da cadeira (quatro números)
dias_p = av.dias_ate(proxima_aval, date.today()) if proxima_aval else None
cartoes_cad = dados.get("cartoes") or []
res_cartoes = rs.resumo(cartoes_cad, date.today()) if cartoes_cad else None
notas_cad = [h["nota"] for h in (dados.get("quiz_historico") or []) + (dados.get("teste_historico") or [])
             if isinstance(h.get("nota"), (int, float))]
resumo_cad = [
    ("Próxima avaliação", ("Hoje" if dias_p == 0 else "Amanhã" if dias_p == 1 else f"{dias_p} dias") if proxima_aval else "—",
     f"{proxima_aval['nome']} · {fmt_data(proxima_aval['data'], False)}" if proxima_aval else "Nada marcado",
     dias_p is not None and dias_p <= 3),
    ("Fontes", f"{len(escolhidos)}/{len(docs)}" if desligadas else str(len(docs)),
     ("selecionadas" if desligadas else "todas selecionadas") + (f" · foco: {tema}" if tema else ""), not escolhidos),
    ("Flashcards", str(res_cartoes["para_hoje"]) if res_cartoes else "—",
     f"para rever hoje · {res_cartoes['dominados']} de {res_cartoes['total']} dominados" if res_cartoes else "Ainda sem cartões",
     False),
    ("Média", f"{sum(notas_cad) / len(notas_cad):.1f}".replace(".", ",") if notas_cad else "—",
     (f"em {len(notas_cad)} quiz(zes) e testes" if notas_cad else "Faz um quiz para começares")
     + (f" · objetivo {obj['nota_alvo']}" if obj.get("nota_alvo") else ""), False),
]
st.markdown("<div class='mi-dia'>" + "".join(
    f"<div class='mi-dia-c{' urgente' if urg else ''}'><div class='r'>{escape(r)}</div><div class='v'>{escape(v)}</div>"
    f"<div class='s'>{escape(sub)}</div></div>" for r, v, sub, urg in resumo_cad) + "</div>", unsafe_allow_html=True)

# ---------------- separadores: Conversa e as ferramentas de estudo (uma de cada vez, na largura toda)
with st.container(key="cad_separadores"):
    st.segmented_control("Ferramenta", list(ESTUDIO), key=chave_est, on_change=mudar_estudio, args=(chave_est, chave_ultimo),
                         format_func=lambda n_: f"{ESTUDIO[n_]} {ROTULO_ESTUDIO.get(n_, n_)}", label_visibility="collapsed")
estudio = st.session_state.get(chave_est) if st.session_state.get(chave_est) in ESTUDIO else estudio
st.markdown(f"<div class='cad-desc'>{escape(DESCRICAO_ESTUDIO[estudio])}</div>", unsafe_allow_html=True)

# ---------------- conteúdo: conversa ou ferramenta escolhida
ferramenta = None
with nullcontext():
    if not tem_chave:
        st.info(sem_ia_texto("para conversar com as fontes e usar as ferramentas"))
        st.stop()
    if not escolhidos:
        st.warning("Todas as fontes estão desligadas. Abre **Fontes** (em cima) e escolhe pelo menos uma.")
        st.stop()
    FONTES = selecionar_texto({n: dados["ficheiros"][n] for n in escolhidos}, tema)
    CONTEXTO = (contexto_cadeira(dados) + "\n" if contexto_cadeira(dados) else "") + \
               (f"Foca-te apenas no tema: {tema}.\n" if tema.strip() else "")
    if estudio == "Conversa":
        conversa_cadeira(cadeira, dados, escolhidos, tema)
    else:
        ferramenta = estudio

    # --------------------------------------------------------------- Resumo
    if ferramenta == "Resumo":
        c1, c2 = st.columns(2)
        nivel = c1.radio("Detalhe", ["Curto", "Médio", "Detalhado"], index=1, horizontal=True)
        estilo = c2.radio("Estilo", ["Tópicos", "Explicação simples", "Esquema"], horizontal=True)
        if st.button("Gerar resumo", type="primary", icon=":material/auto_awesome:"):
            with st.container(border=True):
                r = pedir_a_escrever(
                    FONTES,
                    f"{CONTEXTO}Faz um resumo {nivel.lower()} da matéria, no estilo '{estilo.lower()}', organizado por "
                    "temas com títulos. Destaca a negrito os conceitos-chave, inclui definições, fórmulas (em LaTeX entre "
                    "$...$) e exemplos. No fim acrescenta 'Erros comuns' e 'O que costuma sair em avaliação'. "
                    "Indica as fontes.")
            if r:
                dados["resumo"] = r
                guardar(cadeira)
                st.rerun()
        if dados.get("resumo"):
            with st.container(border=True):
                md(dados["resumo"])
            st.download_button("Descarregar resumo (.md)", dados["resumo"], file_name=f"resumo_{cadeira}.md",
                               icon=":material/download:")

    # --------------------------------------------------------------- Slides
    elif ferramenta == "Slides":
        n_slides = st.slider("Número de slides", 5, 25, 12)
        if st.button("Gerar slides", type="primary", icon=":material/auto_awesome:"):
            with a_pensar("A criar slides..."):
                r = pedir(FONTES,
                          f"{CONTEXTO}Cria {n_slides} slides para ajudar um estudante a compreender esta matéria, do mais "
                          "simples ao mais complexo, com exemplos concretos. Responde só com JSON: "
                          '{"titulo": "...", "slides": [{"titulo": "...", "pontos": ["...", "..."], '
                          '"notas": "explicação mais longa, como se fosse o professor a falar"}]}. '
                          "Máximo 5 pontos curtos por slide.", json_mode=True)
            if r:
                dados["slides"] = r
                guardar(cadeira)
        if dados.get("slides"):
            for i, s in enumerate(dados["slides"].get("slides", []), start=1):
                with st.expander(f"{i}. {s.get('titulo', '')}", expanded=i == 1):
                    for p in s.get("pontos", []):
                        md(f"- {p}")
                    if s.get("notas"):
                        st.info(mt.normalizar(s["notas"]))
            st.download_button("Descarregar PowerPoint", criar_pptx(dados["slides"]), file_name=f"slides_{cadeira}.pptx",
                               icon=":material/download:")

    # --------------------------------------------------------------- Quiz (estilo NotebookLM)
    elif ferramenta == "Quiz":
        h = chave_curta(cadeira)
        fracos = sorted(((t, v) for t, v in (dados.get("quiz_temas") or {}).items() if v[1] >= 2),
                        key=lambda kv: kv[1][0] / kv[1][1])[:3]
        tem_quiz = bool(dados.get("quiz"))
        with (st.expander("Personalizar e gerar um quiz novo", icon=":material/tune:") if tem_quiz
              else st.container(border=True)):
            c1, c2 = st.columns(2)
            quantidade = c1.segmented_control("Número de perguntas", ["Menos", "Padrão", "Mais"], default="Padrão",
                                              key=f"q_qtd_{h}") or "Padrão"
            dificuldade = c2.segmented_control("Dificuldade", ["Fácil", "Média", "Difícil"], default="Média",
                                               key=f"q_dif_{h}") or "Média"
            foco_q = st.text_input("Sobre o que deve ser o quiz? (opcional)", key=f"q_foco_{h}",
                                   placeholder="ex.: só a matéria do capítulo 3, ou perguntas com cálculos")
            reforcar = st.toggle("Reforçar os temas em que erro mais", value=bool(fracos), disabled=not fracos,
                                 key=f"q_ref_{h}", help="Usa o histórico das tuas respostas.")
            gerar = st.button("Gerar quiz" if not tem_quiz else "Gerar quiz novo", type="primary",
                              icon=":material/auto_awesome:", key=f"q_gerar_{h}")
        if gerar:
            n_perg = {"Menos": 5, "Padrão": 10, "Mais": 15}[quantidade]
            extra = (f"Dá mais peso a estes temas, onde o aluno tem errado: {', '.join(t for t, _ in fracos)}. "
                     if reforcar and fracos else "") + (f"Pedido do aluno: {foco_q.strip()}. " if foco_q.strip() else "")
            with a_pensar("A criar perguntas"):
                r = pedir(FONTES,
                          f"{CONTEXTO}{extra}Cria um quiz de {n_perg} perguntas de escolha múltipla, dificuldade "
                          f"{dificuldade.lower()}, como numa avaliação universitária. Cada pergunta tem 4 opções plausíveis "
                          "(só uma certa, as erradas são erros típicos dos alunos e não absurdos), varia os temas e inclui "
                          "perguntas de compreensão e de aplicação (pequeno caso ou cálculo). Não repitas a resposta na "
                          "pergunta e não uses 'todas/nenhuma das anteriores'. Responde só com JSON: "
                          '{"perguntas": [{"pergunta": "...", "opcoes": ["...", "...", "...", "..."], "correta": 0, '
                          '"justificacoes": ["porque esta opção está certa ou errada (1-2 frases), para CADA opção, pela '
                          'mesma ordem"], "dica": "pista curta que ajuda sem dar a resposta", "tema": "tema curto", '
                          '"fonte": "ficheiro, página"}]} onde "correta" é o índice da opção certa. Distribui a posição '
                          "da opção certa (não a ponhas sempre na mesma letra).", json_mode=True)
            perguntas_ok = [q for q in (r or {}).get("perguntas", [])
                            if isinstance(q, dict) and isinstance(q.get("opcoes"), list) and 2 <= len(q["opcoes"]) <= 6
                            and str(q.get("correta", "")).lstrip("-").isdigit()
                            and 0 <= int(q.get("correta", -1)) < len(q["opcoes"])]
            if perguntas_ok:
                dados["quiz"] = perguntas_ok
                st.session_state.pop(f"quizest_{cadeira}", None)
                guardar(cadeira)
                st.rerun()
            elif r is not None:
                st.error("As perguntas geradas não vieram completas. Tenta outra vez.")
        if dados.get("quiz"):
            qid = dados_quiz_id(dados["quiz"])
            valor_q = componente("quiz", f"quiz_{h}", 560, perguntas=dados["quiz"], titulo=f"Quiz · {cadeira}", quiz_id=qid)
            ev_q = evento(valor_q, f"quiz_{h}")
            if ev_q and ev_q.get("evento") == "resultado":
                temas_q = dados.setdefault("quiz_temas", {})
                for tema_q, (certas_q, total_q) in (ev_q.get("temas") or {}).items():
                    antes_q = temas_q.get(tema_q[:60], [0, 0])
                    temas_q[tema_q[:60]] = [antes_q[0] + int(certas_q), antes_q[1] + int(total_q)]
                if ev_q.get("completo") and ev_q.get("total"):
                    nota_q = round(20 * ev_q["certas"] / ev_q["total"], 1)
                    dados["quiz_historico"].append({"data": datetime.now().isoformat(timespec="minutes"), "nota": nota_q})
                guardar(cadeira)
                st.toast("Resultado guardado no teu progresso.", icon=":material/check_circle:")

    # --------------------------------------------------------------- Teste de exame
    elif ferramenta == "Teste":
        n_dev = st.slider("Número de perguntas", 1, 8, 4)
        if st.button("Gerar teste", type="primary", icon=":material/auto_awesome:"):
            with a_pensar("A preparar o teste..."):
                r = pedir(FONTES,
                          f"{CONTEXTO}Cria um teste de exame com {n_dev} perguntas de desenvolvimento/resolução, ao estilo "
                          "de um exame universitário desta cadeira. As cotações somam 20 valores. Responde só com JSON: "
                          '{"perguntas": [{"pergunta": "...", "cotacao": 5, "criterios": "o que uma resposta completa deve ter"}]}',
                          json_mode=True)
            if r and r.get("perguntas"):
                dados["teste"] = r["perguntas"]
                dados.pop("teste_correcao", None)
                guardar(cadeira)
        teste = dados.get("teste")
        if teste:
            with st.form(f"form_teste_{cadeira}"):
                respostas = []
                for i, q in enumerate(teste, start=1):
                    md(f"**{i}. ({q.get('cotacao', '?')} val.)** {q['pergunta']}")
                    respostas.append(st.text_area(f"Resposta à pergunta {i}", key=f"t_{cadeira}_{i}", height=150,
                                                  label_visibility="collapsed",
                                                  placeholder="Escreve a tua resposta. Podes escrever fórmulas como $x^2$."))
                entregar = st.form_submit_button("Entregar e corrigir", type="primary")
            if entregar:
                enunciado = json.dumps([{"pergunta": q["pergunta"], "cotacao": q.get("cotacao"), "criterios": q.get("criterios"),
                                         "resposta_do_aluno": resp or "(em branco)"} for q, resp in zip(teste, respostas)],
                                       ensure_ascii=False)
                with a_pensar("A corrigir..."):
                    r = pedir(FONTES,
                              f"{CONTEXTO}Corrige este teste como um professor justo mas exigente, com base nas fontes e "
                              f"nos critérios. Teste: {enunciado}\nResponde só com JSON: "
                              '{"correcoes": [{"nota": 3.5, "cotacao": 5, "comentario": "o que esteve bem e o que faltou", '
                              '"resposta_modelo": "resposta completa"}], "nota_final": 14.5, '
                              '"conselho": "o que estudar a seguir para chegar à nota pretendida"}', json_mode=True)
                if r:
                    dados["teste_correcao"] = r
                    dados["teste_historico"].append({"data": datetime.now().isoformat(timespec="minutes"),
                                                     "nota": r.get("nota_final")})
                    guardar(cadeira)
            correcao = dados.get("teste_correcao")
            if correcao:
                st.metric("Nota final", f"{correcao.get('nota_final', '?')} / 20 valores")
                for i, c in enumerate(correcao.get("correcoes", []), start=1):
                    with st.expander(f"Pergunta {i}: {c.get('nota')} / {c.get('cotacao')} valores"):
                        md(f"**Comentário:** {c.get('comentario', '')}")
                        md(f"**Resposta modelo:**\n\n{c.get('resposta_modelo', '')}")
                if correcao.get("conselho"):
                    st.info(mt.normalizar(correcao["conselho"]))

    # --------------------------------------------------------------- Flashcards (estilo NotebookLM)
    elif ferramenta == "Flashcards":
        h = chave_curta(cadeira)
        cartoes = dados.get("cartoes") or []
        for c_ in cartoes:
            rs.preparar(c_)
        with (st.expander("Personalizar e gerar flashcards novos", icon=":material/tune:") if cartoes
              else st.container(border=True)):
            c1, c2 = st.columns(2)
            quantidade = c1.segmented_control("Número de cartões", ["Menos", "Padrão", "Mais"], default="Padrão",
                                              key=f"fc_qtd_{h}") or "Padrão"
            dificuldade = c2.segmented_control("Dificuldade", ["Fácil", "Média", "Difícil"], default="Média",
                                               key=f"fc_dif_{h}") or "Média"
            foco_fc = st.text_input("Sobre o que devem ser os cartões? (opcional)", key=f"fc_foco_{h}",
                                    placeholder="ex.: só as fórmulas, ou as definições do capítulo 2")
            gerar = st.button("Gerar flashcards" if not cartoes else "Gerar novos", type="primary",
                              icon=":material/auto_awesome:", key=f"fc_gerar_{h}")
        if gerar:
            n_cartoes = {"Menos": 10, "Padrão": 20, "Mais": 35}[quantidade]
            with a_pensar("A criar flashcards"):
                r = pedir(FONTES,
                          f"{CONTEXTO}{('Pedido do aluno: ' + foco_fc.strip() + '. ') if foco_fc.strip() else ''}"
                          f"Cria {n_cartoes} flashcards de dificuldade {dificuldade.lower()} com os conceitos, definições, "
                          "fórmulas e resultados mais importantes. A frente é uma pergunta curta e concreta (uma só ideia); "
                          "o verso é a resposta curta e clara (1 a 3 frases ou uma fórmula com o significado de cada "
                          "símbolo). Varia o tipo: definição, fórmula, porquê, exemplo, comparação, aplicação. "
                          'Responde só com JSON: {"cartoes": [{"frente": "...", "verso": "...", "tema": "tema curto"}]}',
                          json_mode=True)
            novos = [c for c in (r or {}).get("cartoes", []) if isinstance(c, dict) and c.get("frente") and c.get("verso")]
            if novos:
                dados["cartoes"] = rs.juntar_progresso(novos, cartoes)  # mantém o progresso das frentes iguais
                st.session_state.pop(f"fila_{cadeira}", None)
                st.session_state[f"fc_i_{cadeira}"] = 0
                guardar(cadeira)
                st.rerun()
            elif r is not None:
                st.error("Os cartões gerados não vieram completos. Tenta outra vez.")
        if cartoes:
            hoje = date.today()
            res = rs.resumo(cartoes, hoje)
            modo = st.segmented_control("Modo", ["Estudar", "Rever hoje"], default="Estudar", key=f"modo_fc_{cadeira}",
                                        label_visibility="collapsed") or "Estudar"
            if modo == "Rever hoje":
                m1, m2, m3 = st.columns(3)
                m1.metric("Para rever hoje", res["para_hoje"])
                m2.metric("Dominados", f"{res['dominados']} / {res['total']}")
                m3.metric("Novos", res["caixas"][0])
            baralho = chave_curta(json.dumps([c_.get("frente") for c_ in cartoes], ensure_ascii=False))
            valor_fc = componente("cartoes", f"fc_{h}", 470, titulo=f"Flashcards · {cadeira}", baralho_id=baralho,
                                  modo_cartoes="rever" if modo == "Rever hoje" else "estudar", devidos=rs.devidos(cartoes, hoje),
                                  cartoes=[{"frente": c_.get("frente", ""), "verso": c_.get("verso", ""),
                                            "caixa_nome": rs.NOMES_CAIXAS[c_["caixa"]] if modo == "Rever hoje" else ""}
                                           for c_ in cartoes])
            ev_fc = evento(valor_fc, f"fc_{h}")
            if ev_fc and ev_fc.get("evento") == "avaliar" and 0 <= int(ev_fc.get("indice", -1)) < len(cartoes) \
                    and ev_fc.get("escolha") in ("errei", "dificil", "sabia"):
                rs.responder(cartoes[int(ev_fc["indice"])], ev_fc["escolha"], hoje)
                guardar(cadeira)
            elif ev_fc and ev_fc.get("evento") == "explicar" and 0 <= int(ev_fc.get("indice", -1)) < len(cartoes):
                st.session_state[f"fc_exp_{cadeira}"] = int(ev_fc["indice"])
            i_exp = st.session_state.get(f"fc_exp_{cadeira}")
            if i_exp is not None and i_exp < len(cartoes):
                st.markdown(f"**Explicação:** {escape(str(cartoes[i_exp].get('frente', '')))}")
                if cartoes[i_exp].get("explicacao"):
                    with st.container(border=True):
                        md(cartoes[i_exp]["explicacao"])
                else:  # primeira vez: a IA explica (fica guardado no cartão)
                    explicar_cartao(cartoes[i_exp], FONTES)
                    guardar(cadeira)
            st.download_button("Descarregar para o Anki (.txt)", csv_anki(cartoes), file_name=f"flashcards_{cadeira}.txt",
                               icon=":material/download:")

    # --------------------------------------------------------------- Plano
    elif ferramenta == "Plano":
        futuras = repo().proximas(cadeira)
        plano = dados.get("plano")
        feitas = set(perfil.get("feitas", []))
        if av.estado_plano_cadeira(plano, repo(), feitas):
            mostrar_avisos_de_planos("cadeira")
        if plano and plano.get("dias"):
            cartao_plano("c", cadeira, plano, "cad")
            c1, c2 = st.columns(2)
            c1.button("Ver no calendário", icon=":material/calendar_month:", width="stretch", key=f"plcal_{cadeira}",
                      on_click=navegar, args=("calendario",), kwargs={"cal_vista": "Plano"})
            c2.download_button("Calendário do telemóvel (.ics)", criar_ics(plano.get("dias", []), cadeira),
                               file_name=f"plano_{cadeira}.ics", mime="text/calendar", icon=":material/download:",
                               width="stretch")
        elif not futuras:
            st.info("Esta sala não tem avaliações futuras. Marca uma no Calendário para criares um plano de preparação.")
            st.button("Marcar avaliação", icon=":material/event:", type="primary",
                      on_click=navegar, args=("calendario",), kwargs={"nova_avaliacao_cadeira": cadeira})
        else:
            with st.container(border=True):
                st.markdown(ESTILO_PLANO + f"<div class='pl-titulo'>Plano de preparação com IA</div><div class='pl-sub'>"
                            f"Para «{escape(futuras[0]['nome'])}» ({fmt_data(futuras[0]['data'])}, "
                            f"{escape(av.texto_faltam(futuras[0]))}). A IA pergunta-te como gostas de estudar e o que achas "
                            "mais difícil nesta matéria, mostra-te o plano antes de guardar e põe as tarefas de cada dia no Calendário."
                            "</div>", unsafe_allow_html=True)
                st.button("Criar plano de preparação", icon=":material/auto_awesome:", type="primary",
                          key=f"plcriar_{cadeira}", on_click=novo_assistente_plano,
                          args=({"tipo": "cadeira", "cadeira": cadeira, "avaliacao_id": futuras[0]["id"]},))

    # --------------------------------------------------------------- Guia de estudo
    elif ferramenta == "Guia de estudo":
        if st.button("Gerar guia" if not dados.get("guia") else "Gerar de novo", type="primary", icon=":material/auto_awesome:"):
            with st.container(border=True):
                r = pedir_a_escrever(
                    FONTES,
                    f"{CONTEXTO}Cria um guia de estudo em markdown, claro e calmo, com estas secções: "
                    "## Temas principais (lista curta, uma frase por tema); "
                    "## Perguntas de revisão (8 a 12; depois de cada pergunta, a resposta curta em itálico); "
                    "## Glossário (termo — definição simples); ## Perguntas frequentes (3 a 5); "
                    "## Por onde começar (ordem de estudo recomendada). Indica as fontes (ficheiro, página).")
            if r:
                dados["guia"] = r
                guardar(cadeira)
                st.rerun()
        if dados.get("guia"):
            with st.container(border=True):
                md(dados["guia"])
            st.download_button("Descarregar guia (.md)", dados["guia"], file_name=f"guia_{cadeira}.md", icon=":material/download:")

    # --------------------------------------------------------------- Mapa de conceitos
    elif ferramenta == "Mapa de conceitos":
        if st.button("Gerar mapa" if not dados.get("mapa") else "Gerar de novo", type="primary", icon=":material/auto_awesome:"):
            with a_pensar("A desenhar o mapa"):
                r = pedir(FONTES,
                          f"{CONTEXTO}Cria um mapa de conceitos desta matéria. Responde só com JSON: "
                          '{"centro": "tema central (curto)", "ramos": [{"conceito": "...", "detalhes": ["...", "..."]}]} '
                          "com 4 a 7 ramos e até 4 detalhes por ramo; cada texto com no máximo 6 palavras.", json_mode=True)
            if r and r.get("ramos"):
                dados["mapa"] = r
                guardar(cadeira)
                st.rerun()
            elif r is not None:  # a IA respondeu, mas sem um mapa que se possa desenhar
                st.warning("A IA não conseguiu desenhar o mapa desta vez. Carrega outra vez em «Gerar mapa».",
                           icon=":material/refresh:")
        if dados.get("mapa"):
            with st.container(border=True):
                st.graphviz_chart(dot_mapa(dados["mapa"]))

    # --------------------------------------------------------------- Progresso
    elif ferramenta == "Progresso":
        alvo = obj.get("nota_alvo")
        if alvo:
            st.caption(f"Objetivo: {alvo} valores")
        c1, c2 = st.columns(2)
        for col, titulo, hist in (
            (c1, "Quizzes", dados["quiz_historico"]),
            (c2, "Testes de exame", [h for h in dados["teste_historico"] if isinstance(h.get("nota"), (int, float))]),
        ):
            with col.container(border=True):
                titulo_cartao(titulo, f"{len(hist)} feito{'s' if len(hist) != 1 else ''}" if hist else "")
                if hist:
                    media = sum(h["nota"] for h in hist) / len(hist)
                    st.metric("Média", f"{media:.1f}".replace(".", ",") + " valores",
                              (f"{media - alvo:+.1f}".replace(".", ",") + " em relação ao objetivo") if alvo else None)
                    serie = {"Nota": [h["nota"] for h in hist]}
                    if alvo:
                        serie["Objetivo"] = [alvo] * len(hist)
                    st.line_chart(serie, color=["#17798A", "#B9B4A5"] if alvo else ["#17798A"])
                else:
                    st.caption("Ainda não fizeste nenhum.")
        c3, c4 = st.columns(2)
        with c3.container(border=True):
            titulo_cartao("Flashcards")
            cartoes = dados.get("cartoes") or []
            if cartoes:
                res = rs.resumo(cartoes, date.today())
                st.bar_chart({rs.NOMES_CAIXAS[k]: [v] for k, v in res["caixas"].items()}, horizontal=True, stack=True,
                             color=["#DCE3E1", "#E8B95A", "#D4A03A", "#9BB58E", "#5E8C6A", "#1F8A9E"], height=150)
                st.caption(f"{res['dominados']} de {res['total']} dominados · {res['para_hoje']} para rever hoje")
            else:
                st.caption("Ainda não tens flashcards.")
        with c4.container(border=True):
            titulo_cartao("Temas no quiz")
            temas = dados.get("quiz_temas") or {}
            if temas:
                ordem = sorted(temas.items(), key=lambda kv: kv[1][0] / kv[1][1])
                for tema, (cert, tot) in ordem[:6]:
                    st.progress(cert / tot, text=f"{tema}: {cert}/{tot} certas")
            else:
                st.caption("Faz um quiz para veres os temas onde estás mais forte e mais fraco.")
        foco = [f for f in perfil.get("foco", []) if f.get("cadeira") == cadeira]
        if foco:
            st.caption(f"Tempo de foco nesta sala (cronómetro): {sum(f['minutos'] for f in foco)} min em {len(foco)} sessões.")
