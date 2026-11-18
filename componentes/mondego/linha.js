// Linha do tempo interativa (História): eventos por ordem cronológica, filtro por tema, clique para ler mais.
const CSS = `
.lt { border:1px solid var(--linha); border-radius:16px; background:var(--cartao); padding:14px 16px; }
.lt-filtros { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.lt-filtros button { border:1px solid var(--linha); border-radius:999px; background:var(--cartao); padding:3px 11px; cursor:pointer; font-size:12.5px; }
.lt-filtros button.on { background:var(--acento-claro); border-color:var(--acento); color:var(--acento); }
.lt-lista { position:relative; margin-left:8px; padding-left:26px; border-left:2px solid var(--linha); }
.lt-ev { position:relative; margin:0 0 14px; cursor:pointer; }
.lt-ev::before { content:""; position:absolute; left:-33px; top:4px; width:12px; height:12px; border-radius:50%;
  background:var(--cartao); border:3px solid var(--acento); }
.lt-data { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-weight:600; color:var(--acento); font-size:15px; }
.lt-tit { font-weight:600; color:var(--texto); }
.lt-cat { font-size:11px; color:var(--suave); border:1px solid var(--linha); border-radius:999px; padding:0 7px; margin-left:6px; }
.lt-desc { color:var(--texto); opacity:.85; font-size:13.5px; line-height:1.5; margin-top:3px; display:none; }
.lt-ev.aberto .lt-desc { display:block; }
.lt-dica { font-size:12px; color:var(--suave); margin-bottom:8px; }
`;
let LT = null;
export function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  LT = { raiz, Streamlit, chave: null, filtro: null };
  return atualizar(args);
}
export function atualizar(args) {
  const chave = JSON.stringify(args.eventos);
  if (chave === LT.chave) return;
  LT.chave = chave; LT.filtro = null; LT.eventos = args.eventos || [];
  desenhar();
}
function desenhar() {
  const esc = (t) => String(t ?? "").replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
  const cats = [...new Set(LT.eventos.map((e) => e.categoria).filter(Boolean))];
  const lista = LT.eventos.filter((e) => !LT.filtro || e.categoria === LT.filtro);
  LT.raiz.innerHTML = `<div class="lt">${cats.length > 1 ? `<div class="lt-filtros"><button class="${LT.filtro ? "" : "on"}" data-c="">Todos</button>` +
    cats.map((c) => `<button class="${LT.filtro === c ? "on" : ""}" data-c="${esc(c)}">${esc(c)}</button>`).join("") + "</div>" : ""}
    <div class="lt-dica">Clica num acontecimento para ler a explicação.</div>
    <div class="lt-lista">${lista.map((e) => `<div class="lt-ev"><div class="lt-data">${esc(e.data)}</div>
      <div><span class="lt-tit">${esc(e.titulo)}</span>${e.categoria ? `<span class="lt-cat">${esc(e.categoria)}</span>` : ""}</div>
      <div class="lt-desc">${esc(e.descricao)}</div></div>`).join("")}</div></div>`;
  LT.raiz.querySelectorAll(".lt-filtros button").forEach((b) => b.onclick = () => { LT.filtro = b.dataset.c || null; desenhar(); });
  LT.raiz.querySelectorAll(".lt-ev").forEach((d) => d.onclick = () => { d.classList.toggle("aberto"); LT.Streamlit.altura(LT.raiz.scrollHeight + 4); });
  LT.Streamlit.altura(LT.raiz.scrollHeight + 4);
}
