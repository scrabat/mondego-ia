// Flashcards ao estilo NotebookLM: cartão grande que vira em 3D (clique ou Espaço), setas ←/→, contador, baralhar e
// «Explicar». No modo «Rever hoje» (repetição espaçada) aparecem Errei / Difícil / Sabia depois de virar; cada avaliação
// é enviada para a app, que guarda o progresso de cada cartão.
const CSS = `
.fc { color:var(--texto); }
.fc-topo { display:flex; align-items:center; gap:10px; margin-bottom:12px; flex-wrap:wrap; }
.fc-titulo { font-weight:600; font-size:15px; }
.fc-sub { font-size:12.5px; color:var(--suave); }
.fc-espaco { flex:1; }
.fc-bt { border:1px solid var(--linha); background:var(--cartao); border-radius:11px; padding:8px 14px; cursor:pointer; font-weight:500;
  display:inline-flex; align-items:center; gap:6px; }
.fc-bt:hover:not(:disabled) { border-color:var(--acento); background:var(--acento-claro); }
.fc-bt:disabled { opacity:.45; cursor:default; }
.fc-bt svg { width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
.fc-cena { perspective:1400px; }
.fc-cartao { position:relative; width:100%; height:340px; transform-style:preserve-3d; transition:transform .5s cubic-bezier(.3,.7,.3,1);
  cursor:pointer; }
.fc-cartao.virado { transform:rotateY(180deg); }
.fc-lado { position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden; border-radius:22px;
  border:1px solid var(--linha); background:var(--cartao); box-shadow:0 8px 30px rgba(16,35,43,.10);
  display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:34px 40px; overflow:auto; }
.fc-verso { transform:rotateY(180deg); background:var(--acento-claro); border-color:var(--acento); }
.fc-rotulo { position:absolute; top:16px; left:20px; font-size:11.5px; letter-spacing:.07em; text-transform:uppercase; color:var(--suave); }
.fc-caixa { position:absolute; top:14px; right:18px; font-size:11.5px; color:var(--suave); background:var(--bolha); border-radius:999px; padding:2px 9px; }
.fc-frente .fc-txt { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:25px; line-height:1.45; }
.fc-verso .fc-txt { font-size:17px; line-height:1.6; }
.fc-txt p { margin:4px 0; }
.fc-dica { position:absolute; bottom:14px; left:0; right:0; font-size:12px; color:var(--suave); }
.fc-nav { display:flex; align-items:center; justify-content:center; gap:14px; margin-top:16px; }
.fc-num { min-width:80px; text-align:center; color:var(--suave); font-variant-numeric:tabular-nums; }
.fc-aval { display:none; gap:10px; justify-content:center; margin-top:16px; }
.fc-aval.on { display:flex; }
.fc-aval .fc-bt { min-width:120px; justify-content:center; }
.fc-aval .errei:hover { border-color:#B3261E; background:rgba(179,38,30,.08); }
.fc-aval .sabia { background:var(--primario); border-color:var(--primario); color:#fff; }
.fc-barra { height:4px; border-radius:4px; background:var(--bolha); overflow:hidden; margin-bottom:14px; }
.fc-barra i { display:block; height:100%; background:var(--acento); transition:width .25s; }
.fc-fim { border:1px solid var(--linha); border-radius:22px; background:var(--cartao); padding:40px 20px; text-align:center; }
.fc-fim b { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:24px; display:block; margin-bottom:6px; }
.fc-atalhos { font-size:11.5px; color:var(--suave); text-align:center; margin-top:10px; }
@keyframes fc-entra { from { opacity:0; transform:translateX(18px); } to { opacity:1; transform:none; } }
.fc-entra { animation:fc-entra .22s ease-out; }
@media (max-width:640px) { .fc-cartao { height:300px; } .fc-frente .fc-txt { font-size:20px; } .fc-lado { padding:30px 22px; } }
`;
const ICONE = {
  ant: '<svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg>',
  seg: '<svg viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>',
  baralhar: '<svg viewBox="0 0 24 24"><path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>',
  explicar: '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></svg>',
};
let F = null, T = null;

export async function iniciar(raiz, args, Streamlit) {
  T = await import("./texto.js" + new URL(import.meta.url).search);
  T.carregarKatex();
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  F = { raiz, Streamlit, chave: null };
  new ResizeObserver(() => Streamlit.altura(raiz.scrollHeight + 4)).observe(raiz);
  document.addEventListener("keydown", teclado);
  return atualizar(args);
}

export function atualizar(args) {
  // a mesma sessão continua enquanto o baralho e o modo forem os mesmos (as avaliações não recomeçam a sessão)
  const chave = args.baralho_id + "|" + args.modo_cartoes;
  F.cartoes = args.cartoes || [];
  F.nomesCaixas = args.nomes_caixas || {};
  if (chave === F.chave) return;
  F.chave = chave;
  F.modo = args.modo_cartoes;
  F.titulo = args.titulo || "Flashcards";
  F.fila = args.modo_cartoes === "rever" ? (args.devidos || []).slice() : F.cartoes.map((_, i) => i);
  F.total = F.fila.length;
  F.pos = 0;
  F.virado = false;
  desenhar();
}

function atual() { return F.cartoes[F.fila[F.pos]]; }

function desenhar() {
  if (!F.fila.length) {
    F.raiz.innerHTML = `<div class="fc"><div class="fc-fim fc-entra"><b>${F.modo === "rever" ? "Tudo revisto por hoje" : "Sem cartões"}</b>
      <span class="fc-sub">${F.modo === "rever" ? "Os cartões voltam quando for altura de os rever (repetição espaçada)." : "Gera cartões a partir das fontes."}</span></div></div>`;
    return;
  }
  const c = atual(), rever = F.modo === "rever";
  const feitos = rever ? F.total - F.fila.length : F.pos + 1;
  F.raiz.innerHTML = `<div class="fc">
    <div class="fc-topo"><span class="fc-titulo"></span><span class="fc-sub">${rever ? `Faltam ${F.fila.length}` : `${F.cartoes.length} cartões`}</span>
      <span class="fc-espaco"></span>
      ${rever ? "" : `<button class="fc-bt" data-a="baralhar" title="Baralhar">${ICONE.baralhar}Baralhar</button>`}
      <button class="fc-bt" data-a="explicar" title="Explicar este cartão">${ICONE.explicar}Explicar</button></div>
    ${rever ? `<div class="fc-barra"><i style="width:${(feitos / Math.max(F.total, 1)) * 100}%"></i></div>` : ""}
    <div class="fc-cena"><div class="fc-cartao fc-entra ${F.virado ? "virado" : ""}" tabindex="0" role="button" aria-label="Virar o cartão">
      <div class="fc-lado fc-frente"><span class="fc-rotulo">Pergunta</span>${c.caixa_nome ? '<span class="fc-caixa"></span>' : ""}<div class="fc-txt"></div>
        <div class="fc-dica">Clica (ou carrega em Espaço) para ver a resposta</div></div>
      <div class="fc-lado fc-verso"><span class="fc-rotulo">Resposta</span><div class="fc-txt"></div>
        <div class="fc-dica">${rever ? "Como correu?" : "Clica para voltar à pergunta"}</div></div></div></div>
    ${rever ? `<div class="fc-aval ${F.virado ? "on" : ""}"><button class="fc-bt errei" data-av="errei">Errei</button>
        <button class="fc-bt" data-av="dificil">Difícil</button><button class="fc-bt sabia" data-av="sabia">Sabia</button></div>`
      : `<div class="fc-nav"><button class="fc-bt" data-a="ant" ${F.pos === 0 ? "disabled" : ""}>${ICONE.ant}</button>
        <span class="fc-num">${F.pos + 1} / ${F.fila.length}</span><button class="fc-bt" data-a="seg">${ICONE.seg}</button></div>`}
    <div class="fc-atalhos">Atalhos: Espaço virar${rever ? " · 1 Errei · 2 Difícil · 3 Sabia" : " · ← → mudar de cartão"}</div></div>`;
  F.raiz.querySelector(".fc-titulo").textContent = F.titulo;
  if (c.caixa_nome) F.raiz.querySelector(".fc-caixa").textContent = c.caixa_nome;
  T.preencher(F.raiz.querySelector(".fc-frente .fc-txt"), c.frente);
  T.preencher(F.raiz.querySelector(".fc-verso .fc-txt"), c.verso);
  F.raiz.querySelector(".fc-cartao").addEventListener("click", virar);
  F.raiz.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", (ev) => { ev.stopPropagation(); acao(b.dataset.a); }));
  F.raiz.querySelectorAll("[data-av]").forEach((b) => b.addEventListener("click", () => avaliar(b.dataset.av)));
}

function virar() {
  F.virado = !F.virado;
  F.raiz.querySelector(".fc-cartao").classList.toggle("virado", F.virado);
  F.raiz.querySelector(".fc-aval")?.classList.toggle("on", F.virado);
}

function acao(a) {
  if (a === "seg") { F.pos = (F.pos + 1) % F.fila.length; F.virado = false; desenhar(); }
  else if (a === "ant") { F.pos = Math.max(0, F.pos - 1); F.virado = false; desenhar(); }
  else if (a === "baralhar") {
    for (let i = F.fila.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [F.fila[i], F.fila[j]] = [F.fila[j], F.fila[i]]; }
    F.pos = 0; F.virado = false; desenhar();
  } else if (a === "explicar") {
    F.Streamlit.valor({ evento: "explicar", indice: F.fila[F.pos], t: Date.now() });
  }
}

function avaliar(escolha) {
  if (!F.virado) return;
  const indice = F.fila.shift();
  if (escolha === "errei") F.fila.push(indice); // volta a aparecer nesta sessão
  F.virado = false;
  F.Streamlit.valor({ evento: "avaliar", indice, escolha, t: Date.now() });
  desenhar();
}

function teclado(ev) {
  if (!F || ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;
  if (ev.code === "Space") { ev.preventDefault(); if (F.fila.length) virar(); }
  else if (F.modo === "rever" && F.virado && ["1", "2", "3"].includes(ev.key)) avaliar({ 1: "errei", 2: "dificil", 3: "sabia" }[ev.key]);
  else if (F.modo !== "rever" && ev.key === "ArrowRight") acao("seg");
  else if (F.modo !== "rever" && ev.key === "ArrowLeft") acao("ant");
}
