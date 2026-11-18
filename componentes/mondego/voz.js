// Assistente Mondego por voz: carregas na esfera e falas; ele responde por escrito e em voz alta.
// - Ouve como um assistente a sério: grava com cancelamento de eco e de ruído, percebe sozinho quando acabaste de falar
//   e a app transcreve a gravação com a Google (com as cadeiras e a conversa como contexto). O reconhecimento do browser
//   (Chrome e Edge) mostra o texto enquanto falas e fica de reserva.
// - A resposta aparece logo escrita; a fala chega a seguir com a voz do Mondego (Charon, da Google, gerada na app).
//   Só se essa voz não estiver disponível é que usa a voz do browser (prefere vozes masculinas de Portugal).
// - Seis estados, cada um com o seu aspeto: pronto, a ouvir, a pensar, a responder, em pausa e erro.
// - Responder em voz alta, conversa contínua e a velocidade da voz vêm das Definições da conta (e mudar aqui guarda lá).
// - Quando o pedido é uma ação (abrir uma página, começar o cronómetro...), avisa a app quando acaba de falar.
const CSS = `
.vz { --vz-cor:var(--acento); display:grid; grid-template-columns:auto minmax(0,1fr); gap:6px 26px; align-items:center;
  color:var(--texto); }
.vz[data-e="a_ouvir"] { --vz-cor:#2AA5B8; } .vz[data-e="a_falar"] { --vz-cor:#17798A; }
.vz[data-e="pausado"] { --vz-cor:#8A9AA0; } .vz[data-e="erro"] { --vz-cor:#C2453B; }
.vz-orbe { position:relative; width:136px; height:136px; border:0; padding:0; background:transparent; cursor:pointer;
  border-radius:50%; grid-row:span 2; -webkit-tap-highlight-color:transparent; touch-action:manipulation; }
.vz-orbe:focus-visible { outline:3px solid var(--acento); outline-offset:4px; }
.vz-orbe:disabled { cursor:progress; }
.vz-nucleo { position:absolute; inset:22px; border-radius:50%;
  background:radial-gradient(circle at 35% 30%, #CDEFF3 0%, #3FB7C8 38%, #17798A 62%, #0B4450 100%);
  box-shadow:0 12px 30px rgba(23,121,138,.35), inset 0 -8px 18px rgba(0,0,0,.18);
  transition:transform .09s linear, filter .35s ease, opacity .35s ease; }
.vz[data-e="pausado"] .vz-nucleo { filter:saturate(.25) brightness(.95); }
.vz[data-e="erro"] .vz-nucleo { background:radial-gradient(circle at 35% 30%, #F6D3CF 0%, #DB6B5F 40%, #B23A30 66%, #6E1D17 100%);
  box-shadow:0 12px 30px rgba(178,58,48,.3), inset 0 -8px 18px rgba(0,0,0,.18); }
.vz-anel { position:absolute; inset:14px; border-radius:50%; border:2px solid var(--vz-cor); opacity:0; pointer-events:none; }
.vz-arco { position:absolute; inset:24px; border-radius:50%; border:3px solid transparent; border-top-color:#fff;
  border-right-color:rgba(255,255,255,.45); opacity:0; z-index:2; pointer-events:none; }
.vz-icone { position:absolute; inset:0; display:grid; place-items:center; color:#fff; pointer-events:none; z-index:3;
  transition:opacity .2s ease; }
.vz-icone svg { width:34px; height:34px; fill:none; stroke:#fff; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
@keyframes vz-respirar { 0%,100% { transform:scale(1); } 50% { transform:scale(1.045); } }
@keyframes vz-onda { 0% { transform:scale(1); opacity:.75; } 100% { transform:scale(1.7); opacity:0; } }
@keyframes vz-girar { to { transform:rotate(360deg); } }
.vz[data-e="parado"] .vz-nucleo { animation:vz-respirar 3.2s ease-in-out infinite; }
.vz[data-e="a_ouvir"] .vz-anel { animation:vz-onda 1.4s ease-out infinite; }
.vz[data-e="a_ouvir"] .vz-anel.b { animation-delay:.7s; }
.vz[data-e="a_falar"] .vz-anel { animation:vz-onda 1.1s ease-out infinite; }
.vz[data-e="a_falar"] .vz-anel.b { animation-delay:.55s; }
.vz[data-e="a_pensar"] .vz-arco { opacity:1; animation:vz-girar .9s linear infinite; }
.vz-ondas { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); display:none; gap:4px; align-items:center;
  height:30px; z-index:3; pointer-events:none; }
.vz-ondas i { width:4px; border-radius:2px; background:rgba(255,255,255,.92); height:5px; transition:height .07s linear; }
.vz[data-e="a_falar"] .vz-ondas { display:flex; }
.vz[data-e="a_falar"] .vz-icone { opacity:0; }
/* menos movimento (Definições): sem os movimentos decorativos; o estado continua claro pela cor e pelo ícone */
.vz.calmo .vz-nucleo, .vz.calmo .vz-anel { animation:none !important; }
.vz.calmo[data-e="a_ouvir"] .vz-anel, .vz.calmo[data-e="a_falar"] .vz-anel { opacity:.6; transform:scale(1.18); }
.vz-topo { display:flex; align-items:center; gap:10px; flex-wrap:wrap; min-width:0; }
.vz-estado { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:21px; font-weight:600;
  letter-spacing:-0.01em; }
.vz-chip { display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600; padding:3px 10px 3px 8px;
  border-radius:999px; background:color-mix(in srgb, var(--vz-cor) 14%, transparent); color:var(--vz-cor); }
.vz-chip::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--vz-cor); }
.vz[data-e="a_ouvir"] .vz-chip::before { animation:vz-pisca 1s ease-in-out infinite; }
@keyframes vz-pisca { 50% { opacity:.25; } }
.vz.calmo .vz-chip::before { animation:none; }
.vz-sub { font-size:13.5px; color:var(--suave); min-height:20px; margin-top:2px; line-height:1.45; }
.vz[data-e="erro"] .vz-sub { color:var(--vz-cor); }
.vz-lado { min-width:0; align-self:end; }
.vz-baixo { min-width:0; align-self:start; }
.vz-pontos { display:inline-flex; gap:4px; margin-left:4px; vertical-align:middle; }
.vz-pontos i { width:6px; height:6px; border-radius:50%; background:var(--acento); display:block; animation:vz-p 1.1s infinite ease-in-out; }
.vz-pontos i:nth-child(2) { animation-delay:.15s; } .vz-pontos i:nth-child(3) { animation-delay:.3s; }
@keyframes vz-p { 0%,80%,100% { transform:translateY(0); opacity:.3; } 40% { transform:translateY(-5px); opacity:1; } }
.vz-trans { display:none; margin-top:8px; padding:9px 13px; border-radius:14px; border:1px dashed var(--linha);
  font-size:15px; line-height:1.5; color:var(--texto); background:var(--cartao); }
.vz-trans .p { color:var(--suave); }
.vz[data-e="a_ouvir"] .vz-trans.tem { display:block; }
.vz-ctrl { display:none; gap:8px; flex-wrap:wrap; margin-top:10px; }
.vz[data-e="a_ouvir"] .vz-ctrl, .vz[data-e="a_falar"] .vz-ctrl, .vz[data-e="pausado"] .vz-ctrl, .vz[data-e="erro"] .vz-ctrl { display:flex; }
.vz-bt { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--linha); background:var(--cartao); color:var(--texto);
  border-radius:11px; padding:7px 13px; cursor:pointer; font-weight:500; font-size:13.5px; transition:border-color .15s ease, background .15s ease; }
.vz-bt:hover { border-color:var(--acento); background:var(--acento-claro); }
.vz-bt:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }
.vz-bt.pri { background:var(--primario); border-color:var(--primario); color:#fff; }
.vz-bt.pri:hover { background:var(--primario-hover); }
.vz-bt svg { width:15px; height:15px; fill:currentColor; }
.vz-opcoes { display:flex; gap:16px; flex-wrap:wrap; margin-top:12px; font-size:12.5px; color:var(--suave); }
.vz-opcoes label { display:flex; gap:6px; align-items:center; cursor:pointer; }
.vz-opcoes input { accent-color:var(--acento); width:15px; height:15px; }
.vz-escrever { display:flex; gap:8px; margin-top:10px; }
.vz-escrever input { flex:1; min-width:0; border:1px solid var(--borda-campo); border-radius:11px; padding:8px 12px; background:var(--campo);
  color:var(--campo-texto); font:inherit; }
.vz-escrever input:focus-visible { outline:2px solid var(--acento); outline-offset:1px; }
.vz-escrever button { border:1px solid var(--primario); background:var(--primario); color:#fff; border-radius:11px; padding:8px 14px;
  cursor:pointer; font-weight:600; }
.vz-escrever button:hover { background:var(--primario-hover); }
.vz-hist { grid-column:1 / -1; display:flex; flex-direction:column; gap:8px; margin-top:8px; max-height:300px; overflow:auto;
  overscroll-behavior:contain; }
.vz-hist:empty { display:none; }
.vz-msg { border-radius:16px; padding:9px 14px; font-size:14.5px; line-height:1.55; max-width:88%; overflow-wrap:anywhere; }
.vz-msg.u { align-self:flex-end; background:var(--bolha); }
.vz-msg.a { align-self:flex-start; background:var(--cartao); border:1px solid var(--linha);
  font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:15.5px; }
.vz-msg p { margin:2px 0; }
.vz-aviso { font-size:12.5px; color:var(--suave); margin-top:8px; }
.vz-aviso:empty { display:none; }
.vz-ouvir { margin-top:6px; border:1px solid var(--linha); background:transparent; color:var(--suave); border-radius:999px;
  padding:2px 10px; font-size:12px; cursor:pointer; font-family:'Inter', system-ui, sans-serif; }
.vz-ouvir:hover { border-color:var(--acento); color:var(--acento); }
.vz-sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
@media (max-width: 560px) {
  .vz { grid-template-columns:1fr; justify-items:center; text-align:center; gap:10px; }
  .vz-orbe { grid-row:auto; }
  .vz-lado, .vz-baixo { width:100%; }
  .vz-topo, .vz-ctrl, .vz-opcoes { justify-content:center; }
  .vz-escrever { text-align:left; }
}
`;
const ICONE = {
  mic: '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  parar: '<svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>',
  pausa: '<svg viewBox="0 0 24 24"><path d="M9 6v12M15 6v12"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z"/></svg>',
  alerta: '<svg viewBox="0 0 24 24"><path d="M12 8v5M12 16.5v.5"/><circle cx="12" cy="12" r="9"/></svg>',
};
const BT = {
  pausa: '<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M7 5v14l12-7z"/></svg>',
  parar: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  mic: '<svg viewBox="0 0 24 24"><path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm6-3a6 6 0 0 1-12 0H4a8 8 0 0 0 7 7.9V22h2v-2.1A8 8 0 0 0 20 12z"/></svg>',
};
const ESTADOS = {
  parado: { titulo: "Fala com o Mondego", chip: "Pronto", icone: "mic", rotulo: "Falar com o Mondego" },
  a_ouvir: { titulo: "Estou a ouvir", chip: "A ouvir", icone: "parar", rotulo: "Parar de ouvir" },
  a_pensar: { titulo: 'A pensar<span class="vz-pontos" aria-hidden="true"><i></i><i></i><i></i></span>', chip: "A processar",
    icone: "mic", rotulo: "A pensar na resposta" },
  a_falar: { titulo: "A responder", chip: "A falar", icone: "parar", rotulo: "Pôr a resposta em pausa" },
  pausado: { titulo: "Em pausa", chip: "Pausado", icone: "play", rotulo: "Continuar a resposta" },
  erro: { titulo: "Não consegui", chip: "Erro", icone: "alerta", rotulo: "Tentar outra vez" },
};
let V = null, T = null;

export async function iniciar(raiz, args, Streamlit) {
  T = await import("./texto.js" + new URL(import.meta.url).search);
  T.carregarKatex();
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  V = { raiz, Streamlit, SR, estado: "parado", ultimaResposta: args.resposta_id || null, falarAlto: args.falar !== false,
        continua: args.continua !== false, ritmo: +args.ritmo || 1, sessao: null, audioEl: null, ctx: null,
        visual: null, aguardaAudio: false, porVoz: false, falaBrowser: false };
  raiz.innerHTML = `<div class="vz" data-e="parado">
      <button class="vz-orbe" type="button" aria-label="Falar com o Mondego"><span class="vz-anel"></span><span class="vz-anel b"></span>
        <span class="vz-nucleo"></span><span class="vz-arco"></span><span class="vz-icone">${ICONE.mic}</span>
        <span class="vz-ondas"><i></i><i></i><i></i><i></i><i></i></span></button>
      <div class="vz-lado"><div class="vz-topo"><div class="vz-estado"></div><span class="vz-chip"></span></div>
        <div class="vz-sub"></div><div class="vz-sr" aria-live="polite"></div>
        <div class="vz-trans"></div>
        <div class="vz-ctrl"></div></div>
      <div class="vz-baixo">
        <div class="vz-escrever"><input placeholder="Ou escreve aqui a tua pergunta…" aria-label="Pergunta escrita" autocomplete="off"><button type="button">Enviar</button></div>
        <div class="vz-opcoes"><label><input type="checkbox" data-o="falar"> Responder em voz alta</label>
          <label><input type="checkbox" data-o="continua"> Conversa contínua</label></div>
        <div class="vz-aviso"></div></div>
      <div class="vz-hist" aria-label="Conversa por voz"></div></div>`;
  const q = (s) => raiz.querySelector(s);
  q('[data-o="falar"]').checked = V.falarAlto;
  q('[data-o="continua"]').checked = V.continua;
  q('[data-o="falar"]').onchange = (e) => { V.falarAlto = e.target.checked; if (!V.falarAlto) pararFala(); guardarPref(); };
  q('[data-o="continua"]').onchange = (e) => { V.continua = e.target.checked; guardarPref(); };
  q(".vz-orbe").onclick = clicarOrbe;
  const inp = q(".vz-escrever input");
  const enviarEscrito = () => { const t = inp.value.trim(); if (t && V.estado !== "a_pensar") { inp.value = ""; perguntar(t, false); } };
  q(".vz-escrever button").onclick = enviarEscrito;
  inp.onkeydown = (e) => { if (e.key === "Enter") enviarEscrito(); };
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (V.estado === "a_ouvir") acabarDeOuvir(V.sessao);
    else if (V.estado === "a_falar" || V.estado === "pausado") { pararFala(); terminarFala(false); }
  });
  if ("speechSynthesis" in window) speechSynthesis.getVoices();
  new ResizeObserver(() => Streamlit.altura(raiz.scrollHeight + 6)).observe(raiz);
  V.ultimoErro = args.erro_id || null;                 // os erros que já lá estavam não são deste pedido
  const espera = lerEspera(args);
  if (espera) {                                        // a esfera foi refeita enquanto esperava pela resposta: retoma
    V.ultimaResposta = espera.antes; V.ultimoErro = espera.erro; V.porVoz = !!espera.porVoz; V.esperar = true;
    setTimeout(() => { if (V.estado === "a_pensar" && V.esperar) { V.esperar = false; limparEspera(); mudar("parado"); } }, 30000);
  }
  mudar(espera ? "a_pensar" : "parado");
  return atualizar(args);
}

export function atualizar(args) {
  const primeira = !V.args;
  V.args = args;
  V.lingua = args.idioma === "English" ? "en-GB" : "pt-PT";
  V.ritmo = Math.min(1.5, Math.max(0.7, +args.ritmo || 1));
  if (V.audioEl) V.audioEl.playbackRate = V.ritmo;
  V.raiz.querySelector(".vz").classList.toggle("calmo", !!args.menos_movimento);
  // as opções vêm da conta (Definições → IA → Voz); se mudarem lá, mudam aqui
  // (só quando o valor muda na app: logo a seguir a mudar aqui, a app ainda manda o valor antigo antes de o guardar)
  if (typeof args.falar === "boolean" && args.falar !== V.argFalar) {
    V.argFalar = args.falar; V.falarAlto = args.falar; V.raiz.querySelector('[data-o="falar"]').checked = args.falar;
  }
  if (typeof args.continua === "boolean" && args.continua !== V.argContinua) {
    V.argContinua = args.continua; V.continua = args.continua; V.raiz.querySelector('[data-o="continua"]').checked = args.continua;
  }
  desenharHistorico(args.historico || []);
  const aviso = V.raiz.querySelector(".vz-aviso");
  if (!args.ativo) aviso.textContent = "O assistente ainda não está disponível nesta app. Avisa quem gere a app.";
  else if (args.aviso) aviso.textContent = args.aviso;
  else if (!podeOuvir()) aviso.textContent = "Este browser não reconhece voz (usa o Chrome ou o Edge). Podes escrever a pergunta.";
  if (primeira && V.estado === "parado") mudar("parado");
  if (args.resposta_id && args.resposta_id !== V.ultimaResposta) {        // resposta nova
    V.ultimaResposta = args.resposta_id;
    if (V.estado === "a_pensar" || V.esperar) { V.esperar = false; V.aguardaAudio = true; limparEspera(); }
  } else if (V.estado === "a_pensar" && args.erro_id && args.erro_id !== V.ultimoErro) {
    V.ultimoErro = args.erro_id; V.esperar = false; limparEspera(); mudar("erro", args.erro || "Não consegui responder agora. Tenta outra vez.");
  }
  if (V.aguardaAudio) {
    if (args.audio_estado === "pendente") { mudar("a_pensar", "A preparar a voz…"); return; }
    V.aguardaAudio = false;
    responder(args);
  }
}

function guardarPref() {   // fica na conta (a app guarda nas Definições)
  V.Streamlit.valor({ evento: "pref", falar: V.falarAlto, continua: V.continua, t: Date.now() });
}

function mudar(estado, sub = "") {
  V.estado = estado;
  const E = ESTADOS[estado], vz = V.raiz.querySelector(".vz"), orbe = V.raiz.querySelector(".vz-orbe");
  vz.dataset.e = estado;
  V.raiz.querySelector(".vz-estado").innerHTML = E.titulo;
  V.raiz.querySelector(".vz-chip").textContent = E.chip;
  const pre = { parado: podeOuvir() ? "Carrega na esfera e faz a tua pergunta." : "", a_ouvir: "Fala à vontade: paro quando fizeres uma pausa.",
    a_pensar: "", a_falar: "Carrega na esfera para pôr em pausa (Esc para parar).", pausado: "Carrega na esfera para continuar.",
    erro: "" }[estado];
  V.raiz.querySelector(".vz-sub").textContent = sub || pre;
  V.raiz.querySelector(".vz-sr").textContent = E.chip + (sub ? ": " + sub : "");
  V.raiz.querySelector(".vz-icone").innerHTML = ICONE[E.icone];
  orbe.setAttribute("aria-label", E.rotulo);
  orbe.disabled = estado === "a_pensar";
  const trans = V.raiz.querySelector(".vz-trans");
  if (estado !== "a_ouvir") { trans.classList.remove("tem"); trans.innerHTML = ""; }
  // botões do estado
  const ctrl = V.raiz.querySelector(".vz-ctrl");
  const bt = (a, rotulo, icone, pri) => `<button type="button" class="vz-bt${pri ? " pri" : ""}" data-a="${a}">${BT[icone]}${rotulo}</button>`;
  ctrl.innerHTML = estado === "a_ouvir" ? bt("ouvido", "Acabei de falar", "parar")
    : estado === "a_falar" ? bt("pausa", "Pausar", "pausa") + bt("parar", "Parar", "parar")
    : estado === "pausado" ? bt("retomar", "Continuar", "play", true) + bt("parar", "Parar", "parar")
    : estado === "erro" ? (podeOuvir() ? bt("ouvir", "Tentar outra vez", "mic", true) : "") : "";
  ctrl.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => {
    const a = b.dataset.a;
    if (a === "ouvido") acabarDeOuvir(V.sessao);
    else if (a === "pausa") pausar();
    else if (a === "retomar") retomar();
    else if (a === "parar") { pararFala(); terminarFala(false); }
    else if (a === "ouvir") ouvir();
  });
}

function clicarOrbe() {
  if (V.estado === "a_ouvir") { acabarDeOuvir(V.sessao); return; }
  if (V.estado === "a_falar") return pausar();
  if (V.estado === "pausado") return retomar();
  if (V.estado === "a_pensar") return;
  if (V.porTocar) { const a = V.porTocar; V.porTocar = null; return tocar(a); }   // o browser bloqueou o som automático
  ouvir();
}

// ------------------------------------------------------------------ ouvir (microfone)
// Grava o que dizes com cancelamento de eco, redução de ruído e ganho automático e percebe sozinho quando acabaste (uma
// pausa de 1,5 s depois de falares). A app transcreve a gravação com a Google, com as tuas cadeiras e a conversa como
// contexto. O reconhecimento do browser só mostra o texto enquanto falas e fica de reserva se a transcrição falhar.
// Sem transcrição na app (sem chave do Gemini), ouve só com o reconhecimento do browser, como antes.
const OUVIR = { taxa: 16000, pausaFim: 1500, semFala: 8000, maximo: 60000, antes: 0.35, depois: 0.45 };
const MSG_OUVIR = {
  negado: "O browser não deixou usar o microfone. Permite o acesso (cadeado na barra de endereço) e tenta outra vez.",
  semMicro: "Não encontrei um microfone. Liga-o e tenta outra vez.",
  rede: "O reconhecimento de voz precisa de internet. Vê a ligação e tenta outra vez.",
  nada: "Não ouvi nada. Carrega na esfera e fala outra vez.",
};

function temMicrofone() { return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia); }
function podeOuvir() { return !!V.SR || (temMicrofone() && !!(V.args && V.args.transcreve)); }

async function abrirMicrofone() {
  const md = navigator.mediaDevices;
  try {
    return await md.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true,
                                            channelCount: 1 } });
  } catch (e) {
    if (e && (e.name === "NotAllowedError" || e.name === "SecurityError")) throw e;
    return await md.getUserMedia({ audio: true });       // microfone que não aceita estas opções
  }
}

async function ouvir() {
  if (!podeOuvir()) return;
  if (!V.args.ativo) return mudar("erro", "O assistente ainda não está disponível nesta app.");
  if (V.sessao && !V.sessao.acabou) return;
  pararFala();
  const gravar = temMicrofone() && !!V.args.transcreve;
  const s = { final: "", provisorio: "", blocos: [], amostras: 0, taxa: 0, fala: false, vozes: 0, piso: null, pico: 0,
              inicioFala: 0, fimFala: 0, ultimaVoz: 0, inicio: performance.now(), acabou: false, rec: null, micro: null,
              continuo: gravar, ouviuBrowser: false };
  V.sessao = s;
  let ctx = null;                                        // o som liga-se já, no clique (o Safari não deixa depois)
  if (temMicrofone()) {
    try { ctx = new (window.AudioContext || window.webkitAudioContext)(); ctx.resume().catch(() => {}); } catch (e) { ctx = null; }
  }
  mudar("a_ouvir");
  if (V.SR) reconhecer(s);
  if (s.continuo) vigiar(s);
  let fluxo = null, negado = false;
  if (ctx) {
    try { fluxo = await abrirMicrofone(); }
    catch (e) { negado = !!e && (e.name === "NotAllowedError" || e.name === "SecurityError"); console.warn("Microfone:", e && e.name); }
  }
  if (V.sessao !== s || s.acabou) {
    if (fluxo) fluxo.getTracks().forEach((t) => t.stop());
    if (ctx) ctx.close().catch(() => {});
    return;
  }
  if (fluxo) ligarMicro(s, ctx, fluxo, gravar);
  else if (ctx) ctx.close().catch(() => {});
  s.pronto = true;
  if (!fluxo && !V.SR) { s.acabou = true; V.sessao = null; mudar("erro", negado ? MSG_OUVIR.negado : MSG_OUVIR.semMicro); }
}

// reconhecimento do browser: o texto ao vivo (e a reserva); com gravação fica ligado até a app decidir que acabaste
function reconhecer(s) {
  const rec = new V.SR();
  rec.lang = V.lingua; rec.interimResults = true; rec.continuous = s.continuo; rec.maxAlternatives = 1;
  const trans = V.raiz.querySelector(".vz-trans");
  rec.onresult = (ev) => {
    let final = "", provisorio = "";
    for (let i = 0; i < ev.results.length; i++) {
      if (ev.results[i].isFinal) final += ev.results[i][0].transcript; else provisorio += ev.results[i][0].transcript;
    }
    if (final + provisorio !== s.final + s.provisorio && (final + provisorio).trim()) {
      s.ultimaVoz = performance.now(); s.ouviuBrowser = true;
    }
    s.final = final; s.provisorio = provisorio;
    if (V.sessao !== s) return;
    trans.classList.toggle("tem", !!(final + provisorio).trim());
    trans.innerHTML = "";
    const f = document.createElement("span"); f.textContent = final;
    const p = document.createElement("span"); p.className = "p"; p.textContent = provisorio;
    trans.append(f, p);
  };
  rec.onerror = (ev) => {
    if (ev.error === "aborted" || ev.error === "no-speech" || s.acabou) return;
    if (s.micro && s.micro.proc) return;                 // a gravação continua: a app transcreve na mesma
    if (s.continuo && !s.pronto && !/not-allowed/.test(ev.error)) return;   // à espera do microfone
    const msg = ev.error === "not-allowed" || ev.error === "service-not-allowed" ? MSG_OUVIR.negado
      : ev.error === "audio-capture" ? MSG_OUVIR.semMicro : ev.error === "network" ? MSG_OUVIR.rede
      : "Não consegui ouvir (" + ev.error + "). Tenta outra vez ou escreve a pergunta.";
    s.acabou = true; pararMicro(s); V.sessao = null;
    mudar("erro", msg);
  };
  rec.onend = () => {
    s.rec = null;
    if (s.fimRec) return s.fimRec();                     // já se tinha acabado: era o último texto
    if (s.acabou || s.continuo) return;                  // com gravação, quem decide o fim é a pausa na fala
    acabarDeOuvir(s);
  };
  s.rec = rec;
  try { rec.start(); } catch (e) { s.rec = null; }
}

// a gravação: o nível mexe a esfera; cada bloco é guardado e serve para saber se estás a falar ou calado
function ligarMicro(s, ctx, fluxo, gravar) {
  const fonte = ctx.createMediaStreamSource(fluxo), an = ctx.createAnalyser();
  an.fftSize = 256; fonte.connect(an);
  s.micro = { fluxo, ctx, fonte, proc: null };
  s.taxa = ctx.sampleRate;
  if (gravar) {
    const proc = ctx.createScriptProcessor(2048, 1, 1);
    proc.onaudioprocess = (e) => {
      if (s.acabou) return;
      const bloco = new Float32Array(e.inputBuffer.getChannelData(0));
      s.blocos.push(bloco);
      let soma = 0, pico = 0;
      for (let i = 0; i < bloco.length; i++) { const v = bloco[i]; soma += v * v; if (Math.abs(v) > pico) pico = Math.abs(v); }
      const rms = Math.sqrt(soma / bloco.length);
      if (pico > s.pico) s.pico = pico;
      // o ruído de fundo desce logo e sobe devagar (uma ventoinha não conta como fala; uma palavra também não mexe nele)
      s.piso = s.piso === null || rms < s.piso ? rms : s.piso + (rms - s.piso) * 0.01;
      if (rms > Math.max(0.006, s.piso * 3)) {
        s.vozes++;
        if (!s.fala && s.vozes >= 2) { s.fala = true; s.inicioFala = Math.max(0, s.amostras - bloco.length); }
        if (s.fala) { s.ultimaVoz = performance.now(); s.fimFala = s.amostras + bloco.length; }
      } else s.vozes = 0;
      s.amostras += bloco.length;
    };
    fonte.connect(proc); proc.connect(ctx.destination);  // não se ouve nada: a saída do bloco fica em silêncio
    s.micro.proc = proc;
  }
  const dados = new Uint8Array(an.frequencyBinCount), nucleo = V.raiz.querySelector(".vz-nucleo");
  const passo = () => {
    if (!s.micro || s.acabou) { nucleo.style.transform = ""; return; }
    an.getByteFrequencyData(dados);
    const media = dados.reduce((a, b) => a + b, 0) / dados.length;
    nucleo.style.transform = `scale(${1 + Math.min(media / 140, 0.28)})`;
    requestAnimationFrame(passo);
  };
  passo();
}

function pararMicro(s) {
  const m = s.micro;
  if (!m) return;
  s.micro = null;
  try { if (m.proc) { m.proc.onaudioprocess = null; m.proc.disconnect(); } m.fonte.disconnect(); } catch (e) { /* */ }
  m.fluxo.getTracks().forEach((t) => t.stop());
  m.ctx.close().catch(() => {});
  V.raiz.querySelector(".vz-nucleo").style.transform = "";
}

// acaba sozinho: 1,5 s calado depois de falar, 8 s sem dizer nada ou 1 minuto no total
function vigiar(s) {
  const id = setInterval(() => {
    if (s.acabou || V.sessao !== s) return clearInterval(id);
    const agora = performance.now(), falou = s.fala || s.ouviuBrowser;
    if ((falou && agora - s.ultimaVoz >= OUVIR.pausaFim) || (!falou && agora - s.inicio >= OUVIR.semFala)
        || agora - s.inicio >= OUVIR.maximo || (s.pronto && !s.micro && !s.rec)) {
      clearInterval(id);
      acabarDeOuvir(s);
    }
  }, 100);
}

async function acabarDeOuvir(s) {
  if (!s || s.acabou) return;
  s.acabou = true;
  pararMicro(s);
  if (s.fala || s.ouviuBrowser) mudar("a_pensar", "A perceber o que disseste…");
  if (s.rec) {                                           // o browser costuma dar o último texto só depois de parar
    await new Promise((fim) => { s.fimRec = fim; setTimeout(fim, 700); try { s.rec.stop(); } catch (e) { fim(); } });
  }
  if (V.sessao !== s) return;
  V.sessao = null;
  const rascunho = (s.final + " " + s.provisorio).replace(/\s+/g, " ").trim();
  const wav = (s.fala || rascunho) && s.pico > 0.0005 ? fazerWav(s) : null;
  if (wav) return enviarAudio(wav, rascunho);
  if (rascunho) return perguntar(rascunho, true);
  if (V.estado === "a_ouvir" || V.estado === "a_pensar") mudar("parado", MSG_OUVIR.nada);
}

// WAV 16 kHz, mono, 16 bits, só com a parte em que falaste (mais uma margem) e com o volume acertado
function fazerWav(s) {
  const total = s.blocos.reduce((n, b) => n + b.length, 0);
  if (!total || !s.taxa) return null;
  const tudo = new Float32Array(total);
  let o = 0;
  for (const b of s.blocos) { tudo.set(b, o); o += b.length; }
  let ini = 0, fim = total;
  if (s.fala) {
    ini = Math.max(0, s.inicioFala - Math.round(OUVIR.antes * s.taxa));
    fim = Math.min(total, s.fimFala + Math.round(OUVIR.depois * s.taxa));
  }
  const razao = s.taxa / OUVIR.taxa, n = Math.floor((fim - ini) / razao);
  if (n < OUVIR.taxa * 0.2) return null;
  let pico = 0;
  for (let i = ini; i < fim; i++) if (Math.abs(tudo[i]) > pico) pico = Math.abs(tudo[i]);
  const ganho = pico > 0 ? Math.min(6, 0.9 / pico) : 1;
  const buf = new ArrayBuffer(44 + n * 2), d = new DataView(buf);
  const txt = (p, t) => { for (let i = 0; i < t.length; i++) d.setUint8(p + i, t.charCodeAt(i)); };
  txt(0, "RIFF"); d.setUint32(4, 36 + n * 2, true); txt(8, "WAVE"); txt(12, "fmt "); d.setUint32(16, 16, true);
  d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, OUVIR.taxa, true); d.setUint32(28, OUVIR.taxa * 2, true);
  d.setUint16(32, 2, true); d.setUint16(34, 16, true); txt(36, "data"); d.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {                          // média de cada intervalo (filtra o que o ouvido não precisa)
    const a = ini + Math.floor(i * razao), b = Math.max(a + 1, Math.min(fim, ini + Math.floor((i + 1) * razao)));
    let soma = 0;
    for (let k = a; k < b; k++) soma += tudo[k];
    const v = Math.max(-1, Math.min(1, (soma / (b - a)) * ganho));
    d.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Uint8Array(buf);
}

function emBase64(bytes) {
  let texto = "";
  for (let i = 0; i < bytes.length; i += 0x8000) texto += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(texto);
}

function enviarAudio(wav, rascunho) {
  V.porVoz = true;
  if (!V.args.ativo) return mudar("erro", "O assistente ainda não está disponível nesta app.");
  V.raiz.querySelector(".vz-aviso").textContent = "";
  mudar("a_pensar", "A perceber o que disseste…");
  V.esperar = true; guardarEspera();
  V.Streamlit.valor({ evento: "audio", wav: emBase64(wav), rascunho, falar: V.falarAlto, t: Date.now() });
}

function perguntar(texto, porVoz) {
  V.porVoz = !!porVoz; // a conversa contínua só volta a ouvir quando a pergunta foi falada
  if (!V.args.ativo) return mudar("erro", "O assistente ainda não está disponível nesta app.");
  V.raiz.querySelector(".vz-aviso").textContent = "";
  mudar("a_pensar", "«" + texto + "»");
  V.esperar = true; guardarEspera();
  V.Streamlit.valor({ evento: "pergunta", texto, falar: V.falarAlto, t: Date.now() });
}

// Se a app redesenhar a esfera enquanto espera pela resposta, a nova esfera continua à espera e diz a resposta
// (fica na memória deste separador durante 90 s; numa sessão nova da app — sem a conversa — é ignorado).
const ESPERA = "mondego_voz_espera";
function guardarEspera() {
  try {
    sessionStorage.setItem(ESPERA, JSON.stringify({ t: Date.now(), antes: V.ultimaResposta, erro: V.ultimoErro || null,
      porVoz: V.porVoz, n: (V.args.historico || []).length }));
  } catch (e) { /* sem memória do separador: segue como antes */ }
}
function lerEspera(args) {
  try {
    const e = JSON.parse(sessionStorage.getItem(ESPERA) || "null");
    if (e && Date.now() - e.t < 90000 && (args.historico || []).length >= e.n) return e;
    sessionStorage.removeItem(ESPERA);
  } catch (e) { /* */ }
  return null;
}
function limparEspera() { try { sessionStorage.removeItem(ESPERA); } catch (e) { /* */ } }

// ------------------------------------------------------------------ responder (falar)
function responder(args) {
  const texto = args.fala || args.resposta || "";
  V.ultimaFala = { audio: args.audio_estado === "pronto" ? args.audio : null, texto };
  desenharHistorico(V.args.historico || [], true);
  if (!V.falarAlto || args.audio_estado === "nenhum") return terminarFala(true);
  if (args.audio_estado === "pronto" && args.audio) return tocar(new Audio(args.audio));
  falarBrowser(texto);
}

async function tocar(audio) {
  pararFala();
  V.audioEl = audio;
  audio.playbackRate = V.ritmo;
  audio.onended = () => { pararVisual(); if (V.estado === "a_falar") terminarFala(true); };
  audio.onerror = () => { pararVisual(); if (V.audioEl === audio) falarBrowser(V.ultimaFala ? V.ultimaFala.texto : ""); };
  mudar("a_falar");
  await ligarVisual(audio);
  try {
    await audio.play();
  } catch (e) {                                   // o browser não deixou tocar sem um clique
    pararVisual();
    V.porTocar = audio;
    mudar("parado", "Carrega na esfera para ouvir a resposta.");
  }
}

function pausar() {
  if (V.estado !== "a_falar") return;
  if (V.audioEl) { try { V.audioEl.pause(); } catch (e) { /* */ } }
  else if (V.falaBrowser && "speechSynthesis" in window) speechSynthesis.pause();
  pararVisual();
  mudar("pausado");
}

async function retomar() {
  if (V.estado !== "pausado") return;
  mudar("a_falar");
  if (V.audioEl) {
    V.visual = true; animarVisual();
    try { await V.audioEl.play(); } catch (e) { mudar("pausado", "Carrega na esfera para continuar."); }
  } else if (V.falaBrowser && "speechSynthesis" in window) speechSynthesis.resume();
}

// a esfera mexe-se ao ritmo da voz (só quando o som passa pelo AudioContext sem o silenciar)
async function ligarVisual(audio) {
  try {
    V.ctx = V.ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (V.ctx.state !== "running") await V.ctx.resume().catch(() => {});
    if (V.ctx.state !== "running") return;
    const fonte = V.ctx.createMediaElementSource(audio), an = V.ctx.createAnalyser();
    an.fftSize = 256;
    fonte.connect(an); an.connect(V.ctx.destination);
    V.analisador = an;
    V.visual = true;
    animarVisual();
  } catch (e) { /* sem visualização: o som toca na mesma */ }
}
function animarVisual() {
  const an = V.analisador;
  if (!an) return;
  const dados = new Uint8Array(an.frequencyBinCount), nucleo = V.raiz.querySelector(".vz-nucleo");
  const barras = [...V.raiz.querySelectorAll(".vz-ondas i")];
  const passo = () => {
    if (!V.visual) { nucleo.style.transform = ""; barras.forEach((b) => (b.style.height = "5px")); return; }
    an.getByteFrequencyData(dados);
    const media = dados.reduce((a, b) => a + b, 0) / dados.length;
    nucleo.style.transform = `scale(${1 + Math.min(media / 160, 0.22)})`;
    barras.forEach((b, i) => { const v = dados[4 + i * 9] || 0; b.style.height = 5 + Math.min(22, v / 9) + "px"; });
    requestAnimationFrame(passo);
  };
  passo();
}
function pararVisual() { V.visual = false; }

function pararFala() {
  if (V.audioEl) { try { V.audioEl.pause(); } catch (e) { /* */ } V.audioEl = null; }
  V.analisador = null;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  V.falaBrowser = false;
  pararVisual();
}

function terminarFala(seguir) {
  V.audioEl = null; V.falaBrowser = false;
  mudar("parado");
  if (V.args && V.args.acao_pendente) {           // abrir a página pedida só depois de acabar de falar
    V.Streamlit.valor({ evento: "fim_fala", t: Date.now() });
    return;
  }
  if (seguir && V.continua && V.porVoz && podeOuvir()) setTimeout(() => { if (V.estado === "parado") ouvir(); }, 450);
}

function paraFala(texto) {
  return String(texto || "")
    .replace(/\$\$?([^$]+)\$\$?/g, (_, f) => f.replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "$1 sobre $2").replace(/\^2/g, " ao quadrado")
      .replace(/\^\{?(\w+)\}?/g, " elevado a $1").replace(/\\sqrt\{([^}]*)\}/g, "raiz de $1").replace(/[\\{}_]/g, " "))
    .replace(/[*#`>|]/g, "").replace(/\[(.*?)\]\(.*?\)/g, "$1").replace(/\s+/g, " ").trim();
}

function vozBrowser() {
  const vozes = speechSynthesis.getVoices(), L = V.lingua;
  const masc = /duarte|cristiano|ant[oó]nio|ricardo|daniel|ryan|george|thomas|guy|male|masculin/i;
  const daLingua = vozes.filter((v) => v.lang.replace("_", "-") === L);
  return daLingua.find((v) => masc.test(v.name) && /natural|online/i.test(v.name)) || daLingua.find((v) => masc.test(v.name))
    || daLingua.find((v) => /natural|online/i.test(v.name)) || daLingua[0]
    || vozes.find((v) => v.lang.startsWith(L.slice(0, 2))) || null;
}

function falarBrowser(texto) {
  if (!("speechSynthesis" in window)) return terminarFala(true);
  const fala = new SpeechSynthesisUtterance(paraFala(texto));
  fala.lang = V.lingua;
  const v = vozBrowser();
  if (v) fala.voice = v;
  fala.rate = 1.03 * V.ritmo;
  fala.onend = () => { if (V.estado === "a_falar" || V.estado === "pausado") terminarFala(true); };
  fala.onerror = (e) => { if (e.error === "interrupted" || e.error === "canceled") return; if (V.estado === "a_falar") terminarFala(false); };
  pararFala();
  V.falaBrowser = true;
  mudar("a_falar");
  speechSynthesis.speak(fala);
  const aviso = V.raiz.querySelector(".vz-aviso");
  if (!v && V.lingua === "pt-PT") aviso.textContent = "Não encontrei uma voz em português de Portugal neste computador; foi usada a voz por omissão.";
}

function desenharHistorico(hist, forcar = false) {
  const caixa = V.raiz.querySelector(".vz-hist");
  const chave = JSON.stringify(hist) + (V.ultimaFala ? V.ultimaFala.texto.length : 0);
  if (chave === V.histChave && !forcar) return;
  V.histChave = chave;
  caixa.innerHTML = "";
  hist.slice(-10).forEach((m, i, lista) => {
    const d = document.createElement("div");
    d.className = "vz-msg " + (m.role === "user" ? "u" : "a");
    T.preencher(d, m.content);
    if (m.role !== "user" && i === lista.length - 1 && V.ultimaFala) {
      const b = document.createElement("button");
      b.className = "vz-ouvir"; b.type = "button"; b.textContent = "▶ Ouvir outra vez";
      b.onclick = () => { V.porVoz = false; V.ultimaFala.audio ? tocar(new Audio(V.ultimaFala.audio)) : falarBrowser(V.ultimaFala.texto); };
      d.appendChild(b);
    }
    caixa.appendChild(d);
  });
  caixa.scrollTop = caixa.scrollHeight;
}
