// Cronómetro de estudo: escolhes os minutos de foco (atalhos ou valor livre), a pausa e a cadeira. Conta no browser (não
// pede nada ao servidor a cada segundo) e continua certo mesmo que mudes de página: o estado fica guardado no browser e
// o tempo é sempre calculado a partir da hora de fim (não de contagens), por isso não se atrasa com o separador escondido.
// Dois modos: o completo (Início) e o «mini» (barra lateral, nas outras páginas, só enquanto conta). Só um deles existe
// de cada vez; o que estiver no ecrã é que regista os minutos de foco na app quando uma sessão acaba.
const CSS = `
.cr { color:var(--texto); text-align:center; }
.cr-anel { position:relative; width:184px; height:184px; margin:2px auto 8px; }
.cr-anel svg { width:100%; height:100%; transform:rotate(-90deg); }
.cr-anel circle { fill:none; stroke-width:8; }
.cr-fundo { stroke:var(--bolha); }
.cr-prog { stroke:var(--acento); stroke-linecap:round; transition:stroke-dashoffset .35s linear, stroke .3s; }
.cr-anel.pausa .cr-prog { stroke:#2AA5B8; }
.cr-anel.parada .cr-prog { stroke:var(--suave); opacity:.55; }
.cr-centro { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.cr-tempo { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:42px; font-weight:600; line-height:1;
  font-variant-numeric:tabular-nums; letter-spacing:-0.02em; }
.cr-fase { display:inline-flex; align-items:center; gap:5px; font-size:12px; font-weight:600; margin-top:8px; max-width:150px;
  padding:2px 9px; border-radius:999px; background:var(--bolha); color:var(--suave); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cr-fase.foco { background:var(--acento-claro); color:var(--acento); }
.cr-fase.pausa { background:color-mix(in srgb, #2AA5B8 16%, transparent); color:#2AA5B8; }
.cr-cad { font-size:12px; color:var(--suave); margin-top:5px; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cr-hoje { display:flex; justify-content:center; gap:14px; flex-wrap:wrap; font-size:12.5px; color:var(--suave); margin:2px 0 4px; }
.cr-hoje b { color:var(--texto); font-weight:600; font-variant-numeric:tabular-nums; }
.cr-rot { font-size:12px; color:var(--suave); text-align:left; margin:12px 0 6px; }
.cr-chips { display:flex; flex-wrap:wrap; gap:6px; }
.cr-chip { border:1px solid var(--linha); background:var(--cartao); border-radius:999px; padding:5px 11px; cursor:pointer; font-size:13px;
  transition:border-color .15s ease, background .15s ease; font-variant-numeric:tabular-nums; }
.cr-chip:hover { border-color:var(--acento); }
.cr-chip:focus-visible, .cr-bt:focus-visible, .cr select:focus-visible, .cr-livre input:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }
.cr-chip.on { background:var(--acento-claro); border-color:var(--acento); color:var(--acento); font-weight:600; }
.cr-livre { display:flex; align-items:center; gap:6px; font-size:13px; color:var(--suave); }
.cr-livre input { width:64px; border:1px solid var(--borda-campo); border-radius:8px; padding:4px 6px; background:var(--campo); color:var(--campo-texto); font:inherit; }
.cr select { width:100%; border:1px solid var(--borda-campo); border-radius:9px; padding:7px 8px; background:var(--campo); color:var(--campo-texto); font:inherit; }
.cr-bts { display:flex; gap:8px; margin-top:12px; }
.cr-bt { flex:1; display:inline-flex; align-items:center; justify-content:center; gap:6px; border:1px solid var(--linha); background:var(--cartao);
  border-radius:11px; padding:9px 10px; cursor:pointer; font-weight:500; transition:border-color .15s ease, background .15s ease; }
.cr-bt:hover { border-color:var(--acento); background:var(--acento-claro); }
.cr-bt.pri { background:var(--primario); border-color:var(--primario); color:#fff; }
.cr-bt.pri:hover { background:var(--primario-hover); color:#fff; }
.cr-bt svg { width:15px; height:15px; fill:currentColor; flex:none; }
/* mini (barra lateral) */
.cr-mini { display:flex; align-items:center; gap:10px; padding:8px 8px 8px 10px; border:1px solid var(--linha); border-radius:12px;
  background:var(--cartao); color:var(--texto); }
.cr-mini .cr-anel { width:34px; height:34px; margin:0; flex:none; }
.cr-mini .cr-anel circle { stroke-width:12; }
.cr-mini-txt { flex:1; min-width:0; text-align:left; line-height:1.2; }
.cr-mini-txt b { display:block; font-size:16px; font-weight:600; font-variant-numeric:tabular-nums; }
.cr-mini-txt span { display:block; font-size:11.5px; color:var(--suave); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cr-ic { width:30px; height:30px; flex:none; display:grid; place-items:center; border:1px solid var(--linha); background:transparent;
  border-radius:9px; cursor:pointer; color:var(--texto); }
.cr-ic:hover { border-color:var(--acento); color:var(--acento); }
.cr-ic:focus-visible { outline:2px solid var(--acento); outline-offset:1px; }
.cr-ic svg { width:14px; height:14px; fill:currentColor; }
`;
const IC = {
  play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5v14l12-7z"/></svg>',
  pausa: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
  parar: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  mais: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg>',
};
let C = null;
const AGORA = () => Date.now() / 1000;
const ANEL = 276.46;

export function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  C = { raiz, Streamlit, args, e: ler(), mini: !!args.mini };
  setInterval(tique, 250);
  new ResizeObserver(() => Streamlit.altura(C.raiz.firstChild ? raiz.scrollHeight + 4 : 0)).observe(raiz);
  window.addEventListener("storage", (ev) => { if (ev.key === "mondego_crono") { C.e = ler(); desenhar(); } });  // outro separador
  desenhar();
  executarComando(args.comando);
}
export function atualizar(args) { C.args = args; if (!C.mini) desenharResumo(); executarComando(args.comando); }

function ler() {
  let g = null;
  try { g = JSON.parse(localStorage.getItem("mondego_crono") || "null"); } catch (e) { g = null; }
  return g || { estado: "parado", fase: "foco", foco_min: 25, pausa_min: 5, cadeira: "", fim: 0, restante: 0, duracao: 0, inicio_foco: 0 };
}

// Pedido feito ao assistente por voz («põe o cronómetro a 40 minutos»): começa logo. Cada pedido corre uma só vez.
function executarComando(cmd) {
  if (!cmd || !cmd.id || C.ultimoCmd === cmd.id) return;
  let ultimo = null;
  try { ultimo = localStorage.getItem("mondego_crono_cmd"); } catch (e) { ultimo = null; }
  C.ultimoCmd = cmd.id;
  if (ultimo === cmd.id) return;
  try { localStorage.setItem("mondego_crono_cmd", cmd.id); } catch (e) { /* sem armazenamento */ }
  const e = C.e;
  if (e.estado !== "parado" && e.fase === "foco") enviarFoco((e.duracao - restante()) / 60); // guarda o que já tinha feito
  e.foco_min = Math.max(1, Math.min(240, Math.round(+cmd.minutos || 25)));
  e.pausa_min = [0, 5, 10, 15].includes(+cmd.pausa) ? +cmd.pausa : 5;
  e.cadeira = cmd.cadeira || "";
  Object.assign(e, { estado: "a_correr", fase: "foco", duracao: e.foco_min * 60, fim: AGORA() + e.foco_min * 60, inicio_foco: AGORA() });
  gravar(); desenhar();
}

function gravar() { try { localStorage.setItem("mondego_crono", JSON.stringify(C.e)); } catch (e) { /* sem armazenamento */ } }
function restante() { const e = C.e; return e.estado === "a_correr" ? Math.max(0, e.fim - AGORA()) : e.estado === "em_pausa" ? e.restante : e.foco_min * 60; }
const mmss = (s) => { s = Math.round(s); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m).padStart(2, "0")) + ":" + String(x).padStart(2, "0"); };
const fmtMin = (m) => m >= 60 ? Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0") : m + " min";
const esc = (t) => String(t || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function anel(classe) {
  return `<div class="cr-anel ${classe}"><svg viewBox="0 0 100 100" aria-hidden="true"><circle class="cr-fundo" cx="50" cy="50" r="44"/>
    <circle class="cr-prog" cx="50" cy="50" r="44" stroke-dasharray="${ANEL}" stroke-dashoffset="${ANEL}"/></svg>`;
}

function desenhar() {
  const e = C.e, parado = e.estado === "parado";
  if (C.mini) return desenharMini();
  const cadeiras = (C.args.cadeiras || []).map(() => `<option></option>`).join("");
  const classe = parado ? "parada" : e.fase === "pausa" ? "pausa" : "";
  C.raiz.innerHTML = `<div class="cr" role="timer" aria-label="Cronómetro de estudo">${anel(classe)}
      <div class="cr-centro"><div class="cr-tempo"></div><div class="cr-fase"></div><div class="cr-cad"></div></div></div>
    <div class="cr-hoje"></div>
    ${parado ? `<div class="cr-rot">Minutos de foco</div><div class="cr-chips" data-g="foco">${[15, 25, 45, 60, 90].map((m) =>
        `<button type="button" class="cr-chip ${e.foco_min === m ? "on" : ""}" data-m="${m}" aria-pressed="${e.foco_min === m}">${m}</button>`).join("")}
        <label class="cr-livre">outro <input type="number" min="1" max="240" inputmode="numeric" value="${[15, 25, 45, 60, 90].includes(e.foco_min) ? "" : e.foco_min}" placeholder="min" aria-label="Outro número de minutos"></label></div>
      <div class="cr-rot">Pausa a seguir</div><div class="cr-chips" data-g="pausa">${[0, 5, 10, 15].map((m) =>
        `<button type="button" class="cr-chip ${e.pausa_min === m ? "on" : ""}" data-m="${m}" aria-pressed="${e.pausa_min === m}">${m ? m + " min" : "Sem pausa"}</button>`).join("")}</div>
      <div class="cr-rot">Cadeira (opcional)</div><select aria-label="Cadeira"><option value="">Sem cadeira</option>${cadeiras}</select>
      <div class="cr-bts"><button type="button" class="cr-bt pri" data-a="iniciar">${IC.play}Iniciar</button></div>`
    : `<div class="cr-bts">${e.estado === "a_correr" ? `<button type="button" class="cr-bt" data-a="pausar">${IC.pausa}Pausar</button>`
        : `<button type="button" class="cr-bt pri" data-a="retomar">${IC.play}Retomar</button>`}
        <button type="button" class="cr-bt" data-a="mais">${IC.mais}5 min</button><button type="button" class="cr-bt" data-a="terminar">${IC.parar}Terminar</button></div>`}</div>`;
  if (parado) {
    const sel = C.raiz.querySelector("select");
    [...sel.options].slice(1).forEach((o, i) => { o.textContent = C.args.cadeiras[i]; o.value = C.args.cadeiras[i]; });
    sel.value = (C.args.cadeiras || []).includes(e.cadeira) ? e.cadeira : "";
    sel.onchange = () => { e.cadeira = sel.value; gravar(); };
    C.raiz.querySelectorAll('[data-g="foco"] .cr-chip').forEach((b) => b.onclick = () => { e.foco_min = +b.dataset.m; gravar(); desenhar(); });
    C.raiz.querySelectorAll('[data-g="pausa"] .cr-chip').forEach((b) => b.onclick = () => { e.pausa_min = +b.dataset.m; gravar(); desenhar(); });
    const livre = C.raiz.querySelector(".cr-livre input");
    livre.onchange = () => { const v = Math.round(+livre.value); if (v >= 1 && v <= 240) { e.foco_min = v; gravar(); desenhar(); } };
  }
  C.raiz.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => acao(b.dataset.a));
  desenharResumo();
  tique();
}

function desenharResumo() {
  const r = C.args.resumo, alvo = C.raiz.querySelector(".cr-hoje");
  if (!alvo) return;
  if (!r) { alvo.innerHTML = ""; return; }
  alvo.innerHTML = `<span>Hoje <b>${fmtMin(r.hoje || 0)}</b></span><span><b>${r.sessoes_hoje || 0}</b> ${r.sessoes_hoje === 1 ? "sessão" : "sessões"}</span>`
    + (r.seguidos > 1 ? `<span><b>${r.seguidos}</b> dias seguidos</span>` : "");
}

function desenharMini() {
  const e = C.e;
  if (e.estado === "parado") { C.raiz.innerHTML = ""; C.Streamlit.altura(0); return; }
  C.raiz.innerHTML = `<div class="cr-mini" role="timer" aria-label="Cronómetro de estudo">${anel(e.fase === "pausa" ? "pausa" : "")}</div>
      <div class="cr-mini-txt"><b class="cr-tempo"></b><span class="cr-fase-m"></span></div>
      ${e.estado === "a_correr" ? `<button type="button" class="cr-ic" data-a="pausar" aria-label="Pausar" title="Pausar">${IC.pausa}</button>`
        : `<button type="button" class="cr-ic" data-a="retomar" aria-label="Retomar" title="Retomar">${IC.play}</button>`}
      <button type="button" class="cr-ic" data-a="terminar" aria-label="Terminar" title="Terminar">${IC.parar}</button></div>`;
  C.raiz.querySelectorAll("[data-a]").forEach((b) => b.onclick = () => acao(b.dataset.a));
  tique();
}

function acao(a) {
  const e = C.e;
  if (a === "iniciar") { Object.assign(e, { estado: "a_correr", fase: "foco", duracao: e.foco_min * 60, fim: AGORA() + e.foco_min * 60, inicio_foco: AGORA() }); }
  else if (a === "pausar") { e.restante = Math.max(0, e.fim - AGORA()); e.estado = "em_pausa"; }
  else if (a === "retomar") { e.fim = AGORA() + e.restante; e.estado = "a_correr"; }
  else if (a === "mais") { if (e.estado === "a_correr") e.fim += 300; else e.restante += 300; e.duracao += 300; }
  else if (a === "terminar") {
    if (e.fase === "foco") enviarFoco((e.duracao - restante()) / 60);
    Object.assign(e, { estado: "parado", fase: "foco" });
  }
  gravar(); desenhar();
}

function enviarFoco(minutos) {
  if (minutos >= 1) C.Streamlit.valor({ evento: "foco", minutos: Math.round(minutos), cadeira: C.e.cadeira || null, t: Date.now() });
}

function bip(vezes = 3) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    for (let i = 0; i < vezes; i++) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      const t0 = ctx.currentTime + i * 0.35;
      g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.25);
      o.start(t0); o.stop(t0 + 0.3);
    }
  } catch (e) { /* sem som */ }
}

function tique() {
  const e = C.e;
  if (e.estado === "a_correr" && e.fim - AGORA() <= 0) { // fim de uma fase
    const atrasado = AGORA() - e.fim > 5;               // acabou enquanto a página estava fechada: sem bips fora de horas
    if (!atrasado) bip();
    if (e.fase === "foco") {
      enviarFoco(e.duracao / 60);
      if (e.pausa_min > 0 && AGORA() - e.fim < e.pausa_min * 60) {
        const fimPausa = e.fim + e.pausa_min * 60;
        Object.assign(e, { fase: "pausa", duracao: e.pausa_min * 60, fim: fimPausa });
      } else Object.assign(e, { estado: "parado", fase: "foco" });
    } else {
      Object.assign(e, { estado: "parado", fase: "foco" });
    }
    gravar(); return desenhar();
  }
  const r = restante(), dur = e.estado === "parado" ? e.foco_min * 60 : Math.max(e.duracao, 1);
  const tempo = C.raiz.querySelector(".cr-tempo"), prog = C.raiz.querySelector(".cr-prog");
  if (!tempo) return;
  tempo.textContent = mmss(r);
  const fase = e.estado === "parado" ? "Pronto" : (e.estado === "em_pausa" ? "Em pausa" : e.fase === "foco" ? "Foco" : "Pausa");
  const faseEl = C.raiz.querySelector(".cr-fase");
  if (faseEl) {
    faseEl.textContent = fase;
    faseEl.className = "cr-fase" + (e.estado === "a_correr" ? (e.fase === "foco" ? " foco" : " pausa") : "");
    const cad = C.raiz.querySelector(".cr-cad");
    if (cad) cad.textContent = e.estado !== "parado" && e.cadeira ? e.cadeira : "";
  }
  const faseM = C.raiz.querySelector(".cr-fase-m");
  if (faseM) faseM.textContent = fase + (e.cadeira && e.fase === "foco" ? " · " + e.cadeira : "");
  prog.style.strokeDashoffset = String(ANEL * (e.estado === "parado" ? 1 : r / dur));
}
