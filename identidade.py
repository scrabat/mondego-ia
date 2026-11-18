"""
Identidade visual do Mondego IA: símbolo, logótipo, temas (claro / escuro / automático) e animação de
carregamento.

O símbolo e o logótipo são desenhados em SVG com variáveis CSS. Por isso trocam sozinhos de cores com o
tema: versão clara (torre azul-escura) no modo claro e versão escura (torre branca) no modo escuro.
Se mais tarde chegarem os ficheiros originais do logótipo, basta pô-los em assets/ (ver LEIA-ME.md).
"""

NOME_APP = "Mondego IA"
TEMAS = ["Automático", "Claro", "Escuro"]

# ------------------------------------------------------------------ símbolo (torre + rio Mondego)
_TORRE = (
    '<line x1="32" y1="2" x2="32" y2="9" stroke="var(--logo-torre)" stroke-width="1.6" stroke-linecap="round"/>'
    '<circle cx="32" cy="10.5" r="1.6" fill="var(--logo-torre)"/>'
    '<path d="M25.5 19 Q32 10.5 38.5 19 Z" fill="var(--logo-torre)"/>'
    '<rect x="23.5" y="19" width="17" height="2.6" rx="0.6" fill="var(--logo-torre)"/>'
    '<rect x="25" y="21.6" width="14" height="14" fill="var(--logo-torre)"/>'
    '<circle cx="32" cy="28.6" r="4.6" fill="var(--logo-fundo)"/>'
    '<circle cx="32" cy="28.6" r="3.6" fill="var(--logo-relogio)"/>'
    '<path d="M32 28.6 V26.2 M32 28.6 L33.9 29.6" stroke="var(--logo-fundo)" stroke-width="0.9" '
    'stroke-linecap="round" fill="none"/>'
    '<rect x="22.5" y="35.6" width="19" height="2.8" rx="0.6" fill="var(--logo-torre)"/>'
    '<rect x="25" y="38.4" width="14" height="20" fill="var(--logo-torre)"/>'
    '<path d="M29.2 55 V46.5 a2.8 2.8 0 0 1 5.6 0 V55 Z" fill="var(--logo-fundo)"/>'
    '<rect x="21.5" y="58.4" width="21" height="3.4" rx="0.8" fill="var(--logo-torre)"/>'
)
_ONDAS = (
    '<path d="M12 68 q5 -3.6 10 0 t10 0 t10 0 t10 0" stroke="var(--logo-onda1)" stroke-width="2.6" '
    'fill="none" stroke-linecap="round"/>'
    '<path d="M12 74.5 q5 -3.6 10 0 t10 0 t10 0 t10 0" stroke="var(--logo-onda2)" stroke-width="2.6" '
    'fill="none" stroke-linecap="round"/>'
)


def simbolo_svg(classe: str = "mi-simbolo") -> str:
    """Torre e rio, nas cores do tema ativo."""
    return f'<svg class="{classe}" viewBox="0 0 64 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{_TORRE}{_ONDAS}</svg>'


def icone_app_svg() -> str:
    """Ícone quadrado (fundo azul-petróleo, torre branca) para o separador do browser."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#1F7F93"/><stop offset="1" stop-color="#0F4C61"/></linearGradient></defs>'
        '<rect width="96" height="96" rx="22" fill="url(#g)"/>'
        '<g transform="translate(14.4 9) scale(1.05)" style="--logo-torre:#F7F4EC;--logo-fundo:#16627A;'
        '--logo-relogio:#F7F4EC;--logo-onda1:#7FD3DF;--logo-onda2:#E8B95A">' + _TORRE + _ONDAS + '</g></svg>'
    )


def logo_html(tamanho: str = "md") -> str:
    """Logótipo completo (símbolo + «Mondego IA»), discreto e legível."""
    return (f'<div class="mi-logo mi-logo-{tamanho}">{simbolo_svg()}'
            f'<span class="mi-logo-texto">Mondego<span class="mi-logo-ia"> IA</span></span></div>')


# ------------------------------------------------------------------ animação de carregamento
_ICONES_ESTADO = {
    "web": ('<svg class="mi-orbe-icone" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.4"/>'
            '<ellipse class="mi-meridiano" cx="12" cy="12" rx="4" ry="8.4"/>'
            '<ellipse class="mi-meridiano m2" cx="12" cy="12" rx="4" ry="8.4"/>'
            '<path d="M3.6 12h16.8"/><path class="fino" d="M5.3 7.8h13.4M5.3 16.2h13.4"/></svg>'),
    "ler": ('<svg class="mi-orbe-icone" viewBox="0 0 24 24" aria-hidden="true">'
            '<rect class="mi-folha f2" x="7.5" y="4" width="11" height="14" rx="2"/>'
            '<rect class="mi-folha" x="5" y="6.5" width="11" height="14" rx="2"/>'
            '<path class="mi-linha l1" d="M8 11h5"/><path class="mi-linha l2" d="M8 14h5"/>'
            '<path class="mi-linha l3" d="M8 17h3"/></svg>'),
    "pensar": ('<svg class="mi-orbe-icone mi-faisca" viewBox="0 0 24 24" aria-hidden="true">'
               '<path d="M12 3c.7 4.6 3.4 7.3 8 8-4.6.7-7.3 3.4-8 8-.7-4.6-3.4-7.3-8-8 4.6-.7 7.3-3.4 8-8z"/>'
               '<path class="mi-faisca-pequena" d="M18.5 3.5c.25 1.4 1 2.15 2.4 2.4-1.4.25-2.15 1-2.4 2.4-.25-1.4-1-2.15'
               '-2.4-2.4 1.4-.25 2.15-1 2.4-2.4z"/></svg>'),
}


def tipo_de_estado(texto: str) -> str:
    t = texto.lower()
    return "web" if any(p in t for p in ("web", "pesquis", "search")) else "pensar"


def pensar_html(texto: str = "A pensar", detalhe: str = "", tipo: str | None = None, fontes=()) -> str:
    """Estado da IA enquanto trabalha: ícone animado (globo a girar na pesquisa, folhas a ler as fontes, faísca a pensar),
    o título com um brilho a passar e, por baixo, o passo em curso (o que está a pesquisar) ou os sites que vai ler.
    No chat, o avatar ganha um anel a girar (CSS em _COMPONENTES)."""
    from html import escape
    tipo = tipo if tipo in _ICONES_ESTADO else tipo_de_estado(texto)
    chips = ""
    fontes = list(dict.fromkeys(f for f in fontes if f))
    if fontes:
        chips = "".join(f'<span class="mi-fonte" style="animation-delay:{0.08 * i:.2f}s">{escape(f)}</span>'
                        for i, f in enumerate(fontes[:4]))
        if len(fontes) > 4:
            chips += f'<span class="mi-fonte mais">+{len(fontes) - 4}</span>'
        chips = f'<span class="mi-fontes">{chips}</span>'
    det = f'<span class="mi-estado-detalhe">{escape(detalhe)}</span>' if detalhe else ""
    return (f'<div class="mi-estado mi-estado-{tipo}" role="status" aria-live="polite">'
            f'<span class="mi-orbe">{_ICONES_ESTADO[tipo]}</span>'
            f'<span class="mi-estado-corpo"><span class="mi-estado-texto">{escape(texto)}</span>{det}{chips}</span></div>')


# ------------------------------------------------------------------ animação de entrada
# Minimalista e sem lag: só se animam «transform» e «opacity», que o browser faz na placa gráfica, fora do trabalho da
# página. Assim a animação corre lisa mesmo enquanto o Streamlit está a desenhar a app por baixo (antes, o desfoque,
# os contornos e as sombras das letras eram calculados pela página e engasgavam quando ela estava ocupada).
#   1. a Torre emerge do rio (sobe de trás da linha da água); o relógio acende-se e o sino dá dois toques;
#   2. o Mondego aparece e fica a correr: duas ondas em sentidos contrários, esbatidas nas pontas;
#   3. o nome surge letra a letra, cada uma a subir de trás de uma linha invisível; depois o «IA»;
#   4. uma barra fina que só se completa quando a página está pronta; o lema aparece à medida que ela sobe;
#   5. tudo se esbate e revela a app.
_ONDA_LARGA = "M0 {y} q5 -3.6 10 0" + " t10 0" * 11          # 12 arcos de 10: de x=0 a x=120 (período de 20)
_CSS_INTRO = """
.mi-intro { position:fixed; inset:0; z-index:1000000; display:grid; place-items:center; overflow:hidden;
  contain:strict; will-change:opacity; transition:opacity .6s cubic-bezier(.4,0,.2,1) !important;
  background:radial-gradient(120% 90% at 50% 42%, var(--cartao, #FFFFFF) 0%, var(--fundo, #F6F8F7) 62%);
  font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; -webkit-font-smoothing:antialiased; }
.mi-intro-centro { display:flex; flex-direction:column; align-items:center; gap:1.15rem; will-change:transform, opacity;
  transition:transform .6s cubic-bezier(.4,0,.2,1), opacity .45s ease !important; }
.mi-intro-marca { display:flex; align-items:center; gap:1.2rem; }

/* símbolo: janela da torre (corta na linha da água), anéis do sino, brilho do relógio e o rio */
.mi-sim { position:relative; width:84px; height:105px; flex:none; }
.mi-sim-janela { position:absolute; left:0; top:0; width:100%; height:77.5%; overflow:hidden; }
.mi-sim-torre { display:block; width:100%; height:100%; transform:translateY(102%); will-change:transform;
  animation:mi-in-emerge 1.3s cubic-bezier(.16,1,.3,1) .08s forwards !important; }
.mi-sim-luz { position:absolute; left:42.8%; top:30%; width:14.4%; aspect-ratio:1; border-radius:50%; opacity:0;
  transform:scale(2.2); will-change:opacity; animation:mi-in-acende .5s ease-out .95s forwards !important; }
.mi-sim-luz i { display:block; width:100%; height:100%; border-radius:50%; will-change:opacity;
  background:radial-gradient(circle, color-mix(in srgb, var(--logo-relogio, #1F8A9E) 55%, transparent) 0%, transparent 70%);
  animation:mi-in-respira 2.6s ease-in-out 1.6s infinite !important; }
.mi-sim-anel { position:absolute; left:42.8%; top:30%; width:14.4%; aspect-ratio:1; border-radius:50%; opacity:0;
  border:1px solid var(--logo-relogio, #1F8A9E); box-sizing:border-box; will-change:transform, opacity;
  animation:mi-in-toque 1.3s cubic-bezier(.2,.6,.3,1) 1s forwards !important; }
.mi-sim-anel.a2 { animation-delay:1.32s; }
.mi-sim-rio { position:absolute; left:12.5%; width:75%; top:79%; height:21%; overflow:hidden; opacity:0;
  transform:scaleX(.5); will-change:transform, opacity;
  -webkit-mask-image:linear-gradient(90deg, transparent 0%, #000 20%, #000 80%, transparent 100%);
  mask-image:linear-gradient(90deg, transparent 0%, #000 20%, #000 80%, transparent 100%);
  animation:mi-in-abre 1s cubic-bezier(.16,1,.3,1) .32s forwards !important; }
.mi-sim-onda { position:absolute; left:0; width:250%; height:53.6%; overflow:visible; will-change:transform; }
.mi-sim-onda.o1 { top:0; animation:mi-in-corre-e 2.8s linear infinite !important; }
.mi-sim-onda.o2 { top:38.7%; transform:translateX(-16.6667%); animation:mi-in-corre-d 3.6s linear infinite !important; }

/* nome: cada letra sobe de trás de uma linha invisível */
.mi-intro-nome { display:flex; align-items:flex-end; font-weight:700; font-size:3.35rem; line-height:1.15;
  color:var(--logo-texto, #16324F); white-space:nowrap; }
.mi-l { display:inline-block; overflow:hidden; padding:.04em .05em .2em; margin:-.04em calc(-.05em - .028em) -.2em -.05em; }
.mi-l > span { display:inline-block; transform:translateY(110%); opacity:0; will-change:transform, opacity;
  animation:mi-in-letra 1.1s cubic-bezier(.16,1,.3,1) calc(.35s + var(--i) * 68ms) forwards !important; }
.mi-in-ia { display:inline-flex; margin-left:.24em; color:var(--logo-ia, #1F8A9E); }
.mi-in-ia .mi-l > span { animation-delay:calc(.5s + var(--i) * 68ms); }
.mi-intro-lema { color:var(--suave, #5A6B70); font-size:.95rem; letter-spacing:.05em; white-space:nowrap; }
/* o lema aparece à medida que a barra sobe: uma janela desliza para a direita e o texto, por dentro, desliza ao
   contrário (fica parado); a ponta da janela é esbatida (2rem, sem texto quando a barra está no zero ou no fim).
   Os dois movimentos são os da barra (mesma duração e curva). */
.mi-lema-janela { overflow:hidden; margin-right:-2rem; transform:translateX(-100%); will-change:transform;
  -webkit-mask-image:linear-gradient(90deg, #000 calc(100% - 2rem), transparent);
  mask-image:linear-gradient(90deg, #000 calc(100% - 2rem), transparent); }
.mi-lema-texto { width:max-content; padding-right:2rem; transform:translateX(100%); will-change:transform; }
.mi-intro:not(.letras) .mi-l > span { animation-play-state:paused !important; }

/* barra: avança sozinha e só se completa quando a página está pronta */
.mi-barra { width:180px; height:2px; border-radius:2px; overflow:hidden; margin-top:.4rem; opacity:0;
  background:color-mix(in srgb, var(--linha, #DCE3E1) 90%, transparent); animation:mi-in-aparece .5s ease .35s forwards !important; }
.mi-barra i { display:block; width:100%; height:100%; border-radius:2px; transform:scaleX(0); transform-origin:0 50%;
  will-change:transform; background:linear-gradient(90deg, var(--logo-onda1, #2AA5B8), var(--logo-relogio, #1F8A9E)); }

/* saída */
.mi-intro.sair { opacity:0; pointer-events:none; }
.mi-intro.sair .mi-intro-centro { transform:translateY(-10px) scale(.985); opacity:0; }

@keyframes mi-in-emerge { to { transform:translateY(0); } }
@keyframes mi-in-acende { to { opacity:1; } }
@keyframes mi-in-respira { 0%,100% { opacity:1; } 50% { opacity:.45; } }
@keyframes mi-in-toque { 0% { opacity:.85; transform:scale(1); } 100% { opacity:0; transform:scale(3.4); } }
@keyframes mi-in-abre { to { opacity:1; transform:scaleX(1); } }
@keyframes mi-in-corre-e { from { transform:translateX(0); } to { transform:translateX(-16.6667%); } }
@keyframes mi-in-corre-d { from { transform:translateX(-16.6667%); } to { transform:translateX(0); } }
@keyframes mi-in-letra { to { transform:translateY(0); opacity:1; } }
@keyframes mi-in-aparece { to { opacity:1; } }
@media (max-width:640px) {
  .mi-sim { width:60px; height:75px; } .mi-intro-nome { font-size:2.3rem; } .mi-intro-marca { gap:.8rem; }
  .mi-intro-lema { font-size:.74rem; } .mi-barra { width:150px; } }
/* A animação de entrada é sempre a completa (pedido do utilizador), mesmo com «reduzir movimento» ligado no
   Windows: as regras levam !important para vencer a regra geral da app que encurta as outras animações. */
"""


def _intro_marcacao() -> str:
    """O HTML da animação (numa só linha)."""
    t, f, r = "var(--logo-torre, #16324F)", "var(--logo-fundo, #F6F8F7)", "var(--logo-relogio, #1F8A9E)"
    torre = ('<svg class="mi-sim-torre" viewBox="0 0 64 62" preserveAspectRatio="xMidYMax meet" '
             'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' + _TORRE + '</svg>')
    onda = lambda y, cor: (f'<svg class="mi-sim-onda" viewBox="0 {y - 4.5} 120 9" preserveAspectRatio="none" '
                           f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="{_ONDA_LARGA.format(y=y)}" '
                           f'fill="none" stroke="var(--{cor})" stroke-width="2.6" stroke-linecap="round" '
                           'vector-effect="non-scaling-stroke"/></svg>')
    rio = (onda(68, "logo-onda1, #2AA5B8").replace('class="mi-sim-onda"', 'class="mi-sim-onda o1"', 1)
           + onda(74.5, "logo-onda2, #E0B04B").replace('class="mi-sim-onda"', 'class="mi-sim-onda o2"', 1))
    simbolo = (f'<div class="mi-sim" aria-hidden="true"><div class="mi-sim-janela">{torre}</div>'
               '<div class="mi-sim-luz"><i></i></div><div class="mi-sim-anel"></div><div class="mi-sim-anel a2"></div>'
               f'<div class="mi-sim-rio">{rio}</div></div>')
    letra = lambda c, i: f'<span class="mi-l"><span style="--i:{i}">{c}</span></span>'
    nome = ('<div class="mi-intro-nome" aria-label="Mondego IA">' + "".join(letra(c, i) for i, c in enumerate("Mondego"))
            + '<span class="mi-in-ia">' + "".join(letra(c, 7 + i) for i, c in enumerate("IA")) + '</span></div>')
    return ('<div class="mi-intro" id="mi-intro" role="progressbar" aria-label="A abrir o Mondego IA" aria-valuemin="0" '
            'aria-valuemax="100"><div class="mi-intro-centro">'
            f'<div class="mi-intro-marca">{simbolo}{nome}</div>'
            '<div class="mi-intro-lema"><div class="mi-lema-janela"><div class="mi-lema-texto">'
            'Estuda com as tuas fontes · Universidade de Coimbra</div></div></div>'
            '<div class="mi-barra"><i></i></div></div></div>')


def intro_html() -> str:
    """A animação completa como HTML (estilo + marcação), numa só linha."""
    return f'<style>{" ".join(_CSS_INTRO.split())}</style>{_intro_marcacao()}'


def capa_html() -> str:
    """Fundo da animação, mostrado logo no primeiro instante (antes de o script da animação correr), para a página não
    aparecer por um momento. O script esconde-a; se o script não correr, desaparece sozinha."""
    return ('<style>.mi-capa{position:fixed;inset:0;z-index:999999;pointer-events:none;'
            'background:radial-gradient(120% 90% at 50% 42%, var(--cartao, #FFFFFF) 0%, var(--fundo, #F6F8F7) 62%);'
            'animation:mi-capa-sai .35s ease 4.2s forwards}@keyframes mi-capa-sai{to{opacity:0;visibility:hidden}}</style>'
            '<div class="mi-capa"></div>')


# O script só arranca a animação e decide quando ela sai: não mexe em nada a cada imagem (a barra anda por transições
# da placa gráfica). As letras esperam pela letra Inter (no máximo 0,45 s), para não trocarem de forma a meio.
_JS_INTRO = r"""(function(){try{
var w=window.parent,d=w.document;
function semCapa(){if(!d.getElementById('mi-capa-off')){var o=d.createElement('style');o.id='mi-capa-off';
  o.textContent='.mi-capa{display:none!important}';d.head.appendChild(o);}}
if(w.__miIntro||d.getElementById('mi-intro')){return;}
w.__miIntro=1;
var s=d.createElement('style');s.id='mi-intro-css';s.textContent=__CSS__;d.head.appendChild(s);
var c=d.createElement('div');c.innerHTML=__HTML__;var el=c.firstElementChild;d.body.appendChild(el);semCapa();
var MIN=3000,MAX=8000,t0=w.performance.now(),fim=false,saiu=false,barra=el.querySelector('.mi-barra i'),
  janela=el.querySelector('.mi-lema-janela'),texto=el.querySelector('.mi-lema-texto');
var letrasJa=false;function letras(){if(letrasJa)return;letrasJa=true;el.classList.add('letras');}
try{d.fonts.load('700 54px Inter').then(letras,letras);}catch(e){letras();}
w.setTimeout(letras,450);
/* a barra, a janela do lema e o texto do lema mexem-se com a mesma transição: o lema aparece à medida que a barra sobe */
function vai(e,seg,curva){var tr='transform '+seg+'s '+curva;
  [barra,janela,texto].forEach(function(x){x.style.setProperty('transition',tr,'important');});
  barra.style.transform='scaleX('+e+')';janela.style.transform='translateX('+((e-1)*100)+'%)';
  texto.style.transform='translateX('+((1-e)*100)+'%)';}
w.setTimeout(function(){if(!fim)vai(.62,1.5,'cubic-bezier(.3,.7,.3,1)');},380);
w.setTimeout(function(){if(!fim)vai(.93,6,'cubic-bezier(.1,.6,.3,1)');},1900);
var mexeu=t0,obs=null;try{obs=new w.MutationObserver(function(){mexeu=w.performance.now();});
  obs.observe(d.querySelector('[data-testid="stMain"]')||d.body,{childList:true,subtree:true,attributes:true});}catch(e){}
function sair(){if(saiu)return;saiu=true;try{obs&&obs.disconnect();w.clearInterval(vigia);}catch(e){}el.classList.add('sair');
  w.setTimeout(function(){el.remove();s.remove();},700);}
function acabar(){if(fim)return;fim=true;vai(1,.55,'cubic-bezier(.2,.8,.2,1)');w.setTimeout(sair,1050);}
var vigia=w.setInterval(function(){var agora=w.performance.now();
  if(agora-t0>=MIN&&(agora-mexeu>450||agora-t0>=MAX))acabar();},120);
w.setTimeout(sair,MAX+2000);
}catch(e){try{window.parent.document.querySelectorAll('.mi-capa').forEach(function(x){x.remove();});}catch(e2){}}})();"""


def intro_js() -> str:
    """A animação, posta por um script diretamente no documento da página (uma vez por abertura da página). Assim fica
    fora dos elementos do Streamlit: as execuções seguintes (que marcam os elementos como antigos, esbatem-nos ou os
    escondem ao trocar de ecrã) já não a podem cortar, recomeçar ou parar a meio."""
    import json
    js = (_JS_INTRO.replace("__CSS__", json.dumps(" ".join(_CSS_INTRO.split())))
          .replace("__HTML__", json.dumps(_intro_marcacao())))
    return "<script>" + js.replace("</", "<\\/") + "</script>"


# ------------------------------------------------------------------ temas
_CLARO = """
  --fundo:#F5F7F7; --lateral:#EFF3F3; --cartao:#FFFFFF; --linha:#E1E7E6; --texto:#14222A; --suave:#58696F;
  --acento:#17798A; --acento-esc:#0F5E6B; --bolha:#EEF2F2; --acento-claro:#E0F0F2; --sombra:rgba(16,35,43,0.06);
  --destaque:#C8932F; --erro:#B42318;
  --logo-torre:#16324F; --logo-fundo:#F5F7F7; --logo-relogio:#1F8A9E; --logo-onda1:#2AA5B8; --logo-onda2:#E0B04B;
  --logo-texto:#16324F; --logo-ia:#1F8A9E; color-scheme:light;
  --linha-forte:#CBD5D3; --sucesso:#2E7D4F; --sucesso-claro:#E3F1E8; --aviso:#9A6A12; --aviso-claro:#FBF1DC;
  --erro-claro:#FDECEA;
  --sombra-1:0 1px 2px rgba(16,35,43,0.04); --sombra-2:0 4px 16px rgba(16,35,43,0.07);
  --sombra-3:0 16px 44px rgba(16,35,43,0.15);
  --fonte:'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --r-sm:6px; --r-md:8px; --r-lg:12px; --r-xl:16px; --r-pilula:999px;
  --e-1:4px; --e-2:8px; --e-3:12px; --e-4:16px; --e-5:24px; --e-6:32px;
  --t-xs:0.75rem; --t-sm:0.84rem; --t-base:0.95rem; --t-md:1.05rem; --t-lg:1.2rem; --t-xl:1.45rem; --t-2xl:1.75rem;
  --primario:#17798A; --primario-hover:#0F6878; --primario-ativo:#0B5663;
  --curva:cubic-bezier(.2,.8,.2,1); --rapido:.14s;
  --foco:0 0 0 3px color-mix(in srgb, var(--acento) 30%, transparent);
  --campo:#FFFFFF; --campo-texto:#12202A; --campo-suave:#627378; --borda-campo:#839297; --menu:#FFFFFF; --menu-hover:#EEF2F2;
  --codigo-fundo:#EAF1F0; --codigo-texto:#0F5E6B; --desligado-fundo:#EEF2F2; --desligado-borda:#E1E7E6;
  --desligado-texto:#7A8A8F;
"""
# Escuro: uma escada de superfícies (página → cartão → realce) com fios finos, sem sombras nos cartões; a cor do rio
# fica só para o que é ação ou estado (botão principal, foco, separador escolhido).
_ESCURO = """
  --fundo:#0C1316; --lateral:#0F181B; --cartao:#131D21; --linha:#223035; --texto:#E7EEF0; --suave:#91A3A9;
  --acento:#45BCCB; --acento-esc:#7FD6E0; --bolha:#1A262B; --acento-claro:#11313A; --sombra:rgba(0,0,0,0.35);
  --destaque:#E8B95A; --erro:#F97066;
  --logo-torre:#F4F1EA; --logo-fundo:#0C1316; --logo-relogio:#4FC0D0; --logo-onda1:#4FC0D0; --logo-onda2:#E8B95A;
  --logo-texto:#F4F1EA; --logo-ia:#5CCAD9; color-scheme:dark;
  --linha-forte:#30424A; --sucesso:#4CC38A; --sucesso-claro:#12302A; --aviso:#E8B95A; --aviso-claro:#33290F;
  --erro-claro:#3A1A18;
  --sombra-1:0 0 #0000; --sombra-2:0 10px 28px rgba(0,0,0,0.38);
  --sombra-3:0 22px 56px rgba(0,0,0,0.55);
  --fonte:'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --r-sm:6px; --r-md:8px; --r-lg:12px; --r-xl:16px; --r-pilula:999px;
  --e-1:4px; --e-2:8px; --e-3:12px; --e-4:16px; --e-5:24px; --e-6:32px;
  --t-xs:0.75rem; --t-sm:0.84rem; --t-base:0.95rem; --t-md:1.05rem; --t-lg:1.2rem; --t-xl:1.45rem; --t-2xl:1.75rem;
  --primario:#17798A; --primario-hover:#0F6878; --primario-ativo:#0B5663;
  --curva:cubic-bezier(.2,.8,.2,1); --rapido:.14s;
  --foco:0 0 0 3px color-mix(in srgb, var(--acento) 30%, transparent);
  --campo:#10191D; --campo-texto:#E7EEF0; --campo-suave:#8A9CA2; --borda-campo:#546A74; --menu:#162227; --menu-hover:#1F2D33;
  --codigo-fundo:#1A2A30; --codigo-texto:#7FD6E0; --desligado-fundo:#172227; --desligado-borda:#223035;
  --desligado-texto:#71848A;
"""

# Regras que fazem os componentes do Streamlit seguirem as variáveis acima (funcionam nos dois modos).
# PRINCÍPIO: o Streamlit tem um tema claro e um escuro próprios (.streamlit/config.toml, [theme.light] e [theme.dark])
# e o script tema_js() põe-no sempre igual à cor escolhida na app. Assim, caixas de escrita, menus, janelas e listas
# são escuras no modo escuro e claras no claro. Quando uma regra daqui muda a cor de um componente, muda SEMPRE o
# fundo e a letra ao mesmo tempo (nunca só um dos dois), para nunca haver letra clara sobre fundo claro.
_SELETORES_ILHA = (
    '[data-testid="stSelectbox"] [role="combobox"], [data-testid="stSelectbox"] .react-aria-ComboBox > div, '
    '[data-testid="stMultiSelect"] [role="combobox"], [data-testid="stMultiSelect"] .react-aria-ComboBox > div, '
    '[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stDateInputField"], '
    '[data-testid="stTimeInput"] > div > div, [data-testid="stTextArea"] > div > div, '
    '[data-testid="stFileUploaderDropzone"], [data-testid="stPopoverBody"], div[role="dialog"], [role="listbox"], '
    '[data-testid="stDialog"], '
    '[data-testid="portal"], [data-testid="stToast"], [data-testid="stTooltipContent"], [data-baseweb="popover"], '
    '[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div'
)
_COMPONENTES = """
.stApp, [data-testid="stHeader"], [data-testid="stBottom"] > div { background:var(--fundo) !important; }
/* Uma só letra (Inter) em toda a app: o Streamlit põe «Source Sans» no Markdown, nos títulos, nos rótulos, nos botões
   e nas caixas, e o texto aparecia em duas letras diferentes lado a lado. Os ícones, o código e as fórmulas (KaTeX)
   têm a letra própria e não são tocados (só se muda o elemento, não o que está dentro dele). */
body, .stApp, [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] :is(h1, h2, h3, h4, h5, h6, p, li, td, th),
[data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
[data-testid="stMetricDelta"], [data-testid="stExpander"] summary, [data-testid="stTooltipContent"], [data-testid="stToast"],
[data-testid="stAlertContentInfo"], [data-testid="stFileUploaderDropzone"], [data-testid="stFileUploaderFile"],
[data-testid="stTable"], [data-baseweb="select"], [data-baseweb="tab"], [role="option"], [role="tab"],
.stApp :is(button, input, textarea, select, label), [data-testid="stDialog"] :is(button, input, textarea, label),
[data-testid="stPopoverBody"] :is(button, input, textarea, label) { font-family:var(--fonte) !important; }
/* Cartões (st.container com borda): sobem um degrau em relação à página e têm os cantos de todos os cartões. Sem um
   atributo próprio no Streamlit, o script da página marca-os com data-mi-cartao="1" (ver _JS_CARTOES). */
[data-mi-cartao="1"] { background:var(--cartao); border-color:var(--linha); border-radius:var(--r-lg); box-shadow:var(--sombra-1); }
/* o iframe (vazio) do script da página não ocupa espaço */
[data-testid="stElementContainer"]:has(iframe[srcdoc*="mi-pagina-js"]) { position:absolute !important; width:0 !important;
    height:0 !important; overflow:hidden !important; margin:0 !important; }
[data-testid="stSidebar"] { background:var(--lateral) !important; border-right:1px solid var(--linha); }
/* letra clara/escura só nos elementos de texto que estão sobre a página, a barra lateral ou os cartões */
/* (numa página com a caixa de conversa fixa no fundo, o Streamlit troca stMain por stAppScrollToBottomContainer) */
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) :is(p, li, label, h1, h2, h3, h4, h5, h6, td, th, summary, legend, .katex-display),
[data-testid="stSidebar"] :is(p, li, label, h1, h2, h3, h4, h5, h6, summary) { color:var(--texto); }
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-testid="stCaptionContainer"], [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-testid="stCaptionContainer"] p, [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color:var(--suave) !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p, [data-testid="stMetricValue"],
[data-testid="stMetricValue"] div { color:var(--texto) !important; }
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] { color:var(--texto); }
[data-testid="stProgressBarTrack"] { background-color:var(--bolha) !important; }
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button, [data-testid="stToolbar"] button,
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"], [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpander"] summary svg, [data-testid="stExpander"] [data-testid="stIconMaterial"] { color:var(--texto) !important; }
[data-testid="stTooltipIcon"] svg, [data-testid="stTooltipHoverTarget"] svg { color:var(--suave) !important; stroke:var(--suave); }

/* campos, menus, janelas e listas: fundo e letra do tema escolhido (claros no claro, escuros no escuro) */
""" + _SELETORES_ILHA.replace(", ", " *, ") + """ * { color:var(--texto); }
[data-testid="stPopoverBody"], div[role="dialog"], [role="listbox"], [data-testid="stToast"], [data-testid="stTooltipContent"] {
    background:var(--menu) !important; color:var(--texto) !important; }
:is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-testid="stDateInputField"],
    [data-testid="stTimeInput"] > div > div, [data-testid="stTextArea"] > div > div, [data-baseweb="input"],
    [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div) { background:var(--campo) !important; }
.stApp input, .stApp textarea { color:var(--campo-texto) !important; -webkit-text-fill-color:var(--campo-texto) !important;
    caret-color:var(--campo-texto); background:transparent !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color:var(--campo-suave) !important;
    -webkit-text-fill-color:var(--campo-suave) !important; }
[data-baseweb="select"] > div * { color:var(--campo-texto); }
[role="option"]:hover, [role="option"][data-focused="true"], [role="option"][aria-selected="true"] { background:var(--menu-hover) !important; }
[data-testid="stFileUploaderDropzone"] { background:var(--campo) !important; }
/* «Press Enter to apply» e semelhantes (texto em inglês do Streamlit por baixo das caixas): escondidos */
[data-testid="InputInstructions"] { display:none !important; }

/* caixa do chat: a mesma cor das outras caixas de escrita, sem segunda borda por dentro (a caixa interior do Streamlit
   tem borda e cantos de 8 px próprios, que apareciam como um retângulo dentro da caixa arredondada) */
[data-testid="stChatInput"] { background:var(--campo) !important; border:1px solid var(--borda-campo) !important;
    border-radius:var(--r-xl) !important; box-shadow:var(--sombra-2) !important; }
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] > div > div { background:transparent !important;
    border:none !important; border-radius:inherit !important; box-shadow:none !important; }
[data-testid="stChatInput"]:focus-within { border-color:var(--acento) !important; box-shadow:var(--foco), var(--sombra-2) !important; }
[data-testid="stChatInput"] [data-baseweb="textarea"], [data-testid="stChatInput"] [data-baseweb="textarea"]:focus-within {
    border:none !important; box-shadow:none !important; background:transparent !important; }
[data-testid="stChatInput"] textarea { color:var(--campo-texto) !important; -webkit-text-fill-color:var(--campo-texto) !important;
    caret-color:var(--campo-texto); background:transparent !important; }
[data-testid="stChatInput"] textarea::placeholder { color:var(--campo-suave) !important; -webkit-text-fill-color:var(--campo-suave) !important; }
[data-testid="stChatInput"] button, [data-testid="stChatInput"] svg { color:var(--suave) !important; }

/* botões */
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-testid="stBaseButton-secondary"], [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) .stDownloadButton button, [data-testid="stSidebar"] [data-testid="stPopoverButton"],
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-testid="stPopoverButton"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    background:var(--cartao) !important; color:var(--texto) !important; border-color:var(--linha) !important; }
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) [data-testid="stBaseButton-secondary"] *, [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] *,
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) .stDownloadButton button *, [data-testid="stPopoverButton"] *,
[data-testid="stBaseButton-secondaryFormSubmit"] * { color:var(--texto) !important; }
[data-testid="stBaseButton-tertiary"], [data-testid="stBaseButton-tertiary"] * { color:var(--texto) !important; }
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"] * { color:#FFFFFF !important; }
[data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-primaryFormSubmit"]:disabled {
    background:var(--desligado-fundo) !important; border-color:var(--desligado-borda) !important; }
[data-testid="stBaseButton-primary"]:disabled *, [data-testid="stBaseButton-primaryFormSubmit"]:disabled * { color:var(--desligado-texto) !important; }
[data-testid="stButtonGroup"] button { background:var(--cartao) !important; border-color:var(--linha) !important; }
[data-testid="stButtonGroup"] button * { color:var(--texto) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[kind*="Active"] { background:var(--acento-claro) !important; border-color:var(--acento) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] *, [data-testid="stButtonGroup"] button[aria-pressed="true"] *,
[data-testid="stButtonGroup"] button[kind*="Active"] * { color:var(--acento-esc) !important; }

/* passar o rato por cima: o Streamlit usa o fundo claro do tema base (claro) e a letra ficava branca sobre branco
   no modo escuro. Aqui o fundo e a letra seguem sempre o tema escolhido. */
:is(:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]), [data-testid="stSidebar"], [data-testid="stBottom"]) :is(
    [data-testid^="stBaseButton-secondary"], [data-testid="stBaseButton-tertiary"], [data-testid="stPopoverButton"],
    .stDownloadButton button, [data-testid="stButtonGroup"] button, [data-testid="stBaseButton-minimal"],
    [data-testid="stBaseButton-headerNoPadding"], [role="tab"], [data-testid="stFileUploaderDropzone"] button
):is(:hover, :focus-visible, :active) { background:var(--bolha) !important; border-color:var(--linha-forte) !important;
    color:var(--texto) !important; }
:is(:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]), [data-testid="stSidebar"], [data-testid="stBottom"]) :is(
    [data-testid^="stBaseButton-secondary"], [data-testid="stBaseButton-tertiary"], [data-testid="stPopoverButton"],
    .stDownloadButton button, [data-testid="stButtonGroup"] button, [data-testid="stBaseButton-minimal"],
    [data-testid="stBaseButton-headerNoPadding"], [role="tab"]
):is(:hover, :focus-visible, :active) * { color:var(--texto) !important; }
:is(:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]), [data-testid="stSidebar"]) [data-testid="stBaseButton-tertiary"]:is(:hover, :focus-visible) {
    border-color:transparent !important; }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):not(:disabled):hover {
    background:var(--primario-hover) !important; border-color:var(--primario-hover) !important; }  /* letra branca legível nos dois temas */
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):not(:disabled):hover * { color:#FFFFFF !important; }
/* nos menus e janelas o "por cima" usa a cor de destaque dos menus */
:is([data-testid="stPopoverBody"], div[role="dialog"], [data-testid="stDialog"]) :is(
    [data-testid^="stBaseButton-secondary"], [data-testid="stBaseButton-tertiary"], [role="tab"]
):hover { background:var(--menu-hover) !important; color:var(--texto) !important; }
:is([data-testid="stPopoverBody"], div[role="dialog"], [data-testid="stDialog"]) :is(
    [data-testid^="stBaseButton-secondary"], [data-testid="stBaseButton-tertiary"], [role="tab"]
):hover * { color:var(--texto) !important; }
[data-testid="stExpander"] summary:hover { background:var(--bolha) !important; }

/* cartões e caixas da página */
[data-testid="stExpander"] details { background:var(--cartao) !important; border-color:var(--linha) !important; }
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stLayoutWrapper"] > div { border-color:var(--linha) !important; }
[data-testid="stForm"] { background:var(--cartao) !important; border-color:var(--linha) !important; }
[data-testid="stMetric"] { background:var(--fundo) !important; }
hr { border-color:var(--linha) !important; }
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"]) a { color:var(--acento); }
/* código dentro do texto */
.stApp .stMarkdown code, .stApp [data-testid="stMarkdownContainer"] code { background:var(--codigo-fundo) !important; color:var(--codigo-texto) !important;
    border-radius:5px; padding:0.05em 0.35em; }
.stApp .stMarkdown code *, .stApp [data-testid="stMarkdownContainer"] code * { color:var(--codigo-texto) !important; }
/* cabeçalho das caixas que abrem/fecham: sem fundo próprio, segue a caixa */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary:hover { background:transparent !important; }
[data-testid="stExpander"] summary *, [data-testid="stExpander"] summary:hover * { color:var(--texto) !important; }
/* ícones dos avisos legíveis em qualquer tema */
[data-testid="stAlert"] [data-testid*="Icon"], [data-testid="stAlert"] span[aria-hidden="true"] { color:var(--texto) !important; opacity:0.85; }
/* sem transições de cor na página (evita piscar de claro para escuro ao carregar) */
[data-testid="stSkipToContent"] { background:var(--cartao) !important; color:var(--texto) !important; }
.st-key-painel_fontes [data-testid="stCheckbox"] label p { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.st-key-painel_fontes [data-testid="stCheckbox"] label > div:last-child { min-width:0; overflow:hidden; }

/* ================= sistema de design: os mesmos tamanhos, cantos, sombras e estados em todos os componentes ======= */
/* botões: altura, cantos e peso iguais; passar por cima, carregar (desce 1 px), foco do teclado e desligado */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"],
[data-testid="stLinkButton"] > a {
    border-radius:var(--r-md) !important; min-height:2.3rem; font-weight:500; padding-left:.85rem; padding-right:.85rem;
    transition:background-color var(--rapido) var(--curva), border-color var(--rapido) var(--curva),
               box-shadow var(--rapido) var(--curva), transform .06s ease; }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"],
    [data-testid="stLinkButton"] > a) :is(p, [data-testid="stMarkdownContainer"] p) { font-size:.9rem; font-weight:500; }
/* botões secundários: superfície do cartão e um fio um pouco mais forte (vê-se que é botão, sem pesar) */
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"], [data-testid="stDialog"], [data-testid="stPopoverBody"])
    :is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], .stDownloadButton button,
        [data-testid="stPopoverButton"]):not(:disabled) { border-color:var(--linha-forte) !important; }
/* a seta dos menus (Convidar ⌄) fica discreta */
[data-testid="stPopoverButton"] > div > div[aria-hidden="true"] [data-testid="stIconMaterial"] { color:var(--suave) !important;
    font-size:1.1rem !important; }
@media (pointer:coarse) { .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button,
    [data-testid="stPopoverButton"] { min-height:2.75rem; } }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"]):not(:disabled):active {
    transform:translateY(1px); }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"],
    [data-testid="stButtonGroup"] button):focus-visible { outline:none !important; box-shadow:var(--foco) !important; }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):not(:disabled) {
    background:var(--primario) !important; border-color:var(--primario) !important; box-shadow:var(--sombra-1); }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):not(:disabled):active {
    background:var(--primario-ativo) !important; border-color:var(--primario-ativo) !important; }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"]):disabled {
    opacity:1; cursor:not-allowed; box-shadow:none !important; }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"]):disabled:not(
    [data-testid="stBaseButton-tertiary"], [data-testid="stBaseButton-minimal"], [data-testid="stBaseButton-borderlessIcon"]) {
    background:var(--desligado-fundo) !important; border-color:var(--desligado-borda) !important; }
:is(.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stPopoverButton"]):disabled * {
    color:var(--desligado-texto) !important; }
[data-testid="stBaseButton-tertiary"] { min-height:2.1rem !important; padding-left:.55rem !important; padding-right:.55rem !important; }

/* campos de escrita e de escolha: cantos iguais, borda subtil, foco com anel do acento */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"] {
    border-radius:var(--r-md) !important; border-color:var(--borda-campo) !important;  /* contraste 3:1 com o fundo (AA) */
    transition:border-color var(--rapido) var(--curva), box-shadow var(--rapido) var(--curva); }
:is([data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div):hover { border-color:var(--suave) !important; }
:is([data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"]):focus-within {
    border-color:var(--acento) !important; box-shadow:var(--foco) !important; }
[data-baseweb="input"] > div, [data-baseweb="base-input"] { border-radius:var(--r-md) !important; }
:is([data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"], [data-testid="stSidebar"]) [data-testid="stWidgetLabel"] p {
    font-size:var(--t-sm); font-weight:550; }

/* separadores (st.tabs) */
[data-baseweb="tab-list"] { gap:.25rem; }
[data-baseweb="tab-border"] { background-color:var(--linha) !important; }
[data-baseweb="tab-highlight"] { background-color:var(--acento) !important; }
[role="tab"] p { font-weight:550; color:var(--suave) !important; }
[role="tab"][aria-selected="true"] p { color:var(--texto) !important; }

/* caixas que abrem/fecham, avisos, números, tabelas, código */
[data-testid="stExpander"] details { border:1px solid var(--linha) !important; border-radius:var(--r-lg) !important; }
[data-testid="stExpander"] summary p { font-weight:550; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { border-radius:var(--r-lg) !important; }
[data-testid="stMetric"] { background:var(--cartao) !important; border:1px solid var(--linha); border-radius:var(--r-lg);
    padding:.8rem 1rem !important; }
[data-testid="stMetric"] [data-testid="stMetricLabel"] p { font-size:var(--t-sm); font-weight:500; color:var(--suave) !important; }
[data-testid="stMetricValue"] { font-variant-numeric:tabular-nums; letter-spacing:-.02em; }
[data-testid="stDataFrame"] { border-radius:var(--r-md); overflow:hidden; }
.stApp [data-testid="stCode"] pre, .stApp .stCode pre { border-radius:var(--r-md) !important; }

/* ficheiros: zona tracejada que reage ao passar por cima */
[data-testid="stFileUploaderDropzone"] { border:1.5px dashed var(--linha-forte) !important; border-radius:var(--r-lg) !important;
    transition:border-color var(--rapido) var(--curva), background-color var(--rapido) var(--curva); }
[data-testid="stFileUploaderDropzone"]:hover { border-color:var(--acento) !important; background:var(--acento-claro) !important; }

/* menus, janelas, notificações e dicas: cantos e sombras da mesma família */
[data-testid="stPopoverBody"] { border-radius:var(--r-lg) !important; border:1px solid var(--linha) !important;
    box-shadow:var(--sombra-3) !important; }
[data-testid="stDialog"] div[role="dialog"] { border-radius:var(--r-xl) !important; box-shadow:var(--sombra-3) !important; }
[data-testid="stToast"] { border-radius:var(--r-lg) !important; border:1px solid var(--linha) !important;
    box-shadow:var(--sombra-2) !important; }
[data-testid="stTooltipContent"] { border-radius:var(--r-sm) !important; }
[role="listbox"] { border-radius:var(--r-md) !important; box-shadow:var(--sombra-2) !important; }

/* barras de progresso e linhas */
[data-testid="stProgress"] [role="progressbar"] > div { border-radius:var(--r-pilula) !important; }
hr { opacity:1; }


/* logótipo e símbolo */
.mi-logo { display:flex; align-items:center; gap:0.5rem; color:var(--logo-texto); }
.mi-logo .mi-simbolo { flex-shrink:0; }
.mi-logo-texto { white-space:nowrap; font-family:'Inter', sans-serif; font-weight:700; letter-spacing:-0.02em; color:var(--logo-texto); }
.mi-logo-ia { color:var(--logo-ia); }
.mi-logo-sm .mi-simbolo { width:24px; height:30px; } .mi-logo-sm .mi-logo-texto { font-size:1.05rem; }
.mi-logo-md .mi-simbolo { width:30px; height:38px; } .mi-logo-md .mi-logo-texto { font-size:1.35rem; }
.mi-logo-lg .mi-simbolo { width:44px; height:55px; } .mi-logo-lg .mi-logo-texto { font-size:2rem; }

/* estado da IA enquanto trabalha (pensar / pesquisar na web / ler fontes) */
.mi-estado { display:flex; align-items:center; gap:0.8rem; padding:0.2rem 0; min-height:2.4rem;
  animation:mi-estado-entra .35s cubic-bezier(.2,.8,.2,1) both; }
.mi-orbe { position:relative; isolation:isolate; flex-shrink:0; width:34px; height:34px; border-radius:50%; display:grid;
  place-items:center; color:var(--logo-onda1); background:color-mix(in srgb, var(--logo-onda1) 13%, var(--cartao));
  box-shadow:0 0 0 1px color-mix(in srgb, var(--logo-onda1) 22%, transparent) inset; }
.mi-orbe::before { content:""; position:absolute; inset:-3px; border-radius:50%; padding:2px;
  background:conic-gradient(from 0deg, transparent 0 58%, color-mix(in srgb, var(--logo-onda1) 70%, transparent) 78%,
    var(--logo-onda2) 96%, transparent 100%);
  -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite:xor;
  mask:linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0); animation:mi-girar 1.15s linear infinite; }
.mi-orbe::after { content:""; position:absolute; inset:0; border-radius:50%; z-index:-1;
  background:radial-gradient(circle, color-mix(in srgb, var(--logo-onda1) 30%, transparent), transparent 70%);
  animation:mi-brilho 2.2s ease-in-out infinite; }
.mi-orbe-icone { width:19px; height:19px; fill:none; stroke:currentColor; stroke-width:1.6; stroke-linecap:round;
  stroke-linejoin:round; overflow:visible; }
.mi-orbe-icone .fino { stroke-width:1.1; opacity:.5; }
.mi-meridiano { transform-box:fill-box; transform-origin:center; animation:mi-meridiano 2.4s linear infinite; }
.mi-meridiano.m2 { animation-delay:-1.2s; opacity:.55; }
.mi-folha { fill:var(--cartao); } .mi-folha.f2 { opacity:.55; animation:mi-folha 1.6s ease-in-out infinite; }
.mi-linha { stroke-dasharray:6; stroke-dashoffset:6; animation:mi-linha 1.6s ease-in-out infinite; }
.mi-linha.l2 { animation-delay:.18s; } .mi-linha.l3 { animation-delay:.36s; }
.mi-faisca { stroke:none; }
.mi-faisca path { fill:currentColor; transform-box:fill-box; transform-origin:center; animation:mi-faisca 1.8s ease-in-out infinite; }
.mi-faisca .mi-faisca-pequena { fill:var(--logo-onda2); animation-delay:.5s; }
.mi-estado-corpo { display:flex; flex-direction:column; gap:0.18rem; min-width:0; }
.mi-estado-texto { font-size:0.97rem; font-weight:560; letter-spacing:-0.005em; line-height:1.25; width:fit-content;
  background:linear-gradient(100deg, var(--suave) 0%, var(--suave) 38%, var(--texto) 50%, var(--suave) 62%, var(--suave) 100%);
  background-size:220% 100%; -webkit-background-clip:text; background-clip:text; color:transparent;
  animation:mi-brilho-texto 2s linear infinite; }
.mi-estado-detalhe { font-size:0.8rem; color:var(--suave); opacity:.85; line-height:1.3; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis; max-width:min(560px, 70vw); }
.mi-fontes { display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.2rem; }
.mi-fonte { display:inline-flex; align-items:center; gap:0.35rem; font-size:0.74rem; line-height:1; color:var(--texto);
  padding:0.28rem 0.55rem 0.28rem 0.45rem; border-radius:999px; background:var(--bolha); border:1px solid var(--linha);
  opacity:0; animation:mi-fonte-entra .4s cubic-bezier(.2,.8,.2,1) forwards; }
.mi-fonte::before { content:""; width:6px; height:6px; border-radius:50%; background:var(--logo-onda1); }
.mi-fonte:nth-child(2n)::before { background:var(--logo-onda2); }
.mi-fonte.mais { color:var(--suave); } .mi-fonte.mais::before { display:none; }
/* no chat: o ícone fica em linha com o texto e o avatar ganha um anel a girar (o avatar já mostra a Torre) */
@property --mi-ang { syntax:'<angle>'; initial-value:0deg; inherits:false; }
[data-testid="stChatMessage"]:has(.mi-estado) { position:relative; }
[data-testid="stChatMessage"]:has(.mi-estado)::before { content:""; position:absolute; left:-3px; top:calc(0.35rem - 3px);
  width:38px; height:38px; border-radius:11px; padding:2px; pointer-events:none;
  background:conic-gradient(from var(--mi-ang), transparent 0 50%, color-mix(in srgb, var(--logo-onda1) 75%, transparent) 75%,
    var(--logo-onda2) 95%, transparent 100%);
  -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite:xor;
  mask:linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0); animation:mi-ang 1.2s linear infinite; }
[data-testid="stChatMessage"]:has(.mi-estado) [data-testid="stChatMessageAvatarImage"] { animation:mi-avatar 2.2s ease-in-out infinite; }
[data-testid="stChatMessage"] .mi-estado { align-items:flex-start; gap:0.55rem; min-height:32px; padding-top:0.3rem; }
[data-testid="stChatMessage"] .mi-orbe { width:18px; height:18px; background:none; box-shadow:none; margin-top:0.1rem; }
[data-testid="stChatMessage"] .mi-orbe::before, [data-testid="stChatMessage"] .mi-orbe::after { display:none; }
[data-testid="stChatMessage"] .mi-orbe-icone { width:17px; height:17px; }
@keyframes mi-girar { to { transform:rotate(360deg); } }
@keyframes mi-ang { to { --mi-ang:360deg; } }
@keyframes mi-avatar { 0%,100% { filter:none; } 50% { filter:brightness(1.12) saturate(1.1); } }
@keyframes mi-brilho { 0%,100% { opacity:.35; transform:scale(1); } 50% { opacity:.9; transform:scale(1.25); } }
@keyframes mi-meridiano { 0% { transform:scaleX(1); } 50% { transform:scaleX(.06); } 100% { transform:scaleX(1); } }
@keyframes mi-folha { 0%,100% { transform:translate(0,0); } 50% { transform:translate(1.5px,-1.5px); } }
@keyframes mi-linha { 0% { stroke-dashoffset:6; } 45%,75% { stroke-dashoffset:0; } 100% { stroke-dashoffset:-6; } }
@keyframes mi-faisca { 0%,100% { transform:scale(.86); opacity:.7; } 50% { transform:scale(1.08); opacity:1; } }
@keyframes mi-brilho-texto { 0% { background-position:120% 0; } 100% { background-position:-120% 0; } }
@keyframes mi-estado-entra { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
@keyframes mi-fonte-entra { from { opacity:0; transform:translateY(3px) scale(.96); } to { opacity:1; transform:none; } }
/* as animações mexem-se sempre (pedido do utilizador), mesmo com «reduzir animações» no sistema: são movimentos pequenos */
"""


# Script da página (corre uma vez por abertura e sempre que a cor da app muda):
# 1) põe o tema do próprio Streamlit (caixas, menus, janelas) igual à cor escolhida na app. O Streamlit guarda a
#    escolha no localStorage («stActiveTheme-<caminho>-v2» = "System" | "Light" | "Dark") e só a lê ao abrir a página,
#    por isso, se o modo que se vê tiver de mudar, a página recarrega UMA vez (só se isso não fizer perder a sessão);
# 2) traduz o pouco texto em inglês que o Streamlit escreve dentro dos seus componentes (zona de carregar ficheiros).
_JS_PAGINA = r"""(function(){try{
var w=window.parent,d=w.document,TEMA=__TEMA__,PODE=__PODE__;
var quero={'Claro':'Light','Escuro':'Dark'}[TEMA]||'System';
var escuro=function(t){return t==='Dark'||(t==='System'&&w.matchMedia('(prefers-color-scheme: dark)').matches);};
try{var chave='stActiveTheme-'+w.location.pathname+'-v2',atual=null;
  try{atual=JSON.parse(w.localStorage.getItem(chave));}catch(e){}
  if((atual||'System')!==quero){w.localStorage.setItem(chave,JSON.stringify(quero));
    var guarda='mi-tema-'+quero;
    if(PODE&&escuro(atual||'System')!==escuro(quero)&&!w.sessionStorage.getItem(guarda)){
      w.sessionStorage.setItem(guarda,'1');w.location.reload();return;}}}catch(e){}
if(!d.getElementById('mi-traduz-js')){var sc=d.createElement('script');sc.id='mi-traduz-js';sc.textContent=__TRADUZ__;d.head.appendChild(sc);}
if(!d.getElementById('mi-cartoes-js')){var sc2=d.createElement('script');sc2.id='mi-cartoes-js';sc2.textContent=__CARTOES__;d.head.appendChild(sc2);}
}catch(e){}})();"""


# Marca os contentores com borda (st.container(border=True)) com data-mi-cartao="1", para o CSS lhes dar a superfície e
# os cantos dos cartões (o Streamlit não lhes põe nenhum atributo próprio). Só lê o estilo de elementos novos (e os que
# mudam de classe); os que têm um desenho próprio no CSS (caixa de conversa, dias do calendário, cartões clicáveis…)
# ficam de fora. A regra do CSS não leva !important: as regras próprias de cada página continuam a mandar.
_JS_CARTOES = r"""(function(){try{var d=document,w=window,pend=false,
  PROPRIOS=/st-key-(mbarra_|manx_|dia[NHF]_|pldia_|en_|ob_|card_)/;  /* contentores que já têm um desenho próprio no CSS */
function marca(){pend=false;d.querySelectorAll('[data-testid="stVerticalBlock"]:not([data-mi-cartao])').forEach(function(e){
  var s=w.getComputedStyle(e),borda=function(l){return parseFloat(s['border'+l+'Width'])>0&&s['border'+l+'Style']!=='none';};
  var proprio=PROPRIOS.test(e.className||'');
  e.setAttribute('data-mi-cartao',(!proprio&&borda('Top')&&borda('Left')&&borda('Bottom')&&borda('Right'))?'1':'0');});}
function pede(ms){(ms||[]).forEach(function(m){if(m.type==='attributes'&&m.target.getAttribute&&
  m.target.getAttribute('data-testid')==='stVerticalBlock'){m.target.removeAttribute('data-mi-cartao');}});
  if(!pend){pend=true;w.setTimeout(marca,30);}}
marca();new MutationObserver(pede).observe(d.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
}catch(e){}})();"""


_JS_TRADUZ = r"""(function(){try{var d=document;
var FRASES={'Upload':'Carregar','Browse files':'Escolher ficheiros','Drag and drop files here':'Arrasta os ficheiros para aqui',
  'Drag and drop file here':'Arrasta o ficheiro para aqui','No results':'Sem resultados','Choose an option':'Escolhe uma opção',
  'Choose options':'Escolhe opções','Clear all':'Limpar tudo','Remove':'Remover','Copy to clipboard':'Copiar',
  'Close':'Fechar','Show password':'Mostrar a palavra-passe','Hide password':'Esconder a palavra-passe'};
var PADROES=[[/^Upload or drag and drop .*$/,'Carregar ou arrastar ficheiros'],[/^Upload .*$/,'Carregar ficheiros'],
  [/^Showing page (\d+) of (\d+)$/,'P\u00e1gina $1 de $2'],[/^File must be (.*) or smaller\.?$/,'O ficheiro tem de ter at\u00e9 $1.'],
  [/^(.*) files? are not allowed\.?$/,'Ficheiros $1 n\u00e3o s\u00e3o permitidos.']];
function frase(l){if(FRASES[l])return FRASES[l];for(var i=0;i<PADROES.length;i++){if(PADROES[i][0].test(l))return l.replace(PADROES[i][0],PADROES[i][1]);}return null;}
function traduz(n){if(n.nodeType!==3)return;var t=n.nodeValue,l=t.trim();if(!l)return;
  var m=l.match(/^(\d+)\s*([KMG]B) per file( \u2022 )?(.*)$/);
  if(m){n.nodeValue='At\u00e9 '+m[1]+' '+m[2]+' por ficheiro'+(m[4]?' \u00b7 '+m[4]:'');return;}
  var f=frase(l);if(f!==null)n.nodeValue=t.replace(l,f);}
function atributos(e){if(!e||e.nodeType!==1)return;var els=[e].concat([].slice.call(e.querySelectorAll('[aria-label],[title]')));
  els.forEach(function(x){['aria-label','title'].forEach(function(a){var v=x.getAttribute&&x.getAttribute(a);
    if(v){var f=frase(v.trim());if(f!==null&&f!==v)x.setAttribute(a,f);}});});}
function percorre(r){if(!r)return;if(r.nodeType===3){traduz(r);return;}
  var it=d.createTreeWalker(r,4),n;while((n=it.nextNode()))traduz(n);atributos(r);}
percorre(d.body);
new MutationObserver(function(ms){ms.forEach(function(m){if(m.type==='characterData')traduz(m.target);
  else m.addedNodes.forEach(percorre);});}).observe(d.body,{childList:true,subtree:true,characterData:true});
}catch(e){}})();"""


def tema_js(tema: str, pode_recarregar: bool = True) -> str:
    """Script da página: tema do Streamlit igual ao da app e tradução do texto em inglês dos componentes.
    pode_recarregar=False quando recarregar a página faria perder a sessão (entrou sem «manter a sessão iniciada»):
    nesse caso o tema do Streamlit só muda na próxima vez que a app for aberta."""
    import json
    js = (_JS_PAGINA.replace("__TEMA__", json.dumps(tema)).replace("__PODE__", "true" if pode_recarregar else "false")
          .replace("__TRADUZ__", json.dumps(_JS_TRADUZ)).replace("__CARTOES__", json.dumps(_JS_CARTOES)))
    return "<script id='mi-pagina-js'>" + js.replace("</", "<\\/") + "</script>"


def css_tema(tema: str) -> str:
    """CSS completo para o tema escolhido ('Claro', 'Escuro' ou 'Automático')."""
    if tema == "Escuro":
        variaveis = f":root {{{_ESCURO}}}"
    elif tema == "Claro":
        variaveis = f":root {{{_CLARO}}}"
    else:  # Automático: segue o sistema operativo
        variaveis = f":root {{{_CLARO}}}\n@media (prefers-color-scheme: dark) {{ :root {{{_ESCURO}}} }}"
    return f"<style>{variaveis}\n{_COMPONENTES}</style>"
