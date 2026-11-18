// Tabela periódica interativa (dados de laboratorio.py). Clica num elemento para ver os detalhes; filtra por família.
const CSS = `
.tp { border:1px solid var(--linha); border-radius:16px; background:var(--cartao); padding:12px; }
.tp-topo { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
.tp-topo input { border:1px solid var(--linha); border-radius:9px; padding:6px 10px; background:var(--cartao); min-width:200px; }
.tp-leg { display:flex; flex-wrap:wrap; gap:6px; }
.tp-leg button { border:1px solid var(--linha); border-radius:999px; padding:2px 9px; font-size:11.5px; cursor:pointer; color:#12202A; }
.tp-leg button.off { opacity:.35; }
.tp-grelha { display:grid; grid-template-columns:repeat(18, minmax(0, 1fr)); gap:3px; }
.tp-el { aspect-ratio:1/1.1; border-radius:6px; padding:2px 3px; cursor:pointer; color:#12202A; border:1px solid rgba(0,0,0,.06);
  display:flex; flex-direction:column; justify-content:space-between; overflow:hidden; transition:transform .08s; }
.tp-el:hover { transform:scale(1.12); z-index:2; box-shadow:0 3px 10px rgba(0,0,0,.18); }
.tp-el.apagado { opacity:.18; }
.tp-el.sel { outline:2px solid var(--acento); outline-offset:1px; }
.tp-el small { font-size:clamp(6px, .9vw, 9.5px); line-height:1; }
.tp-el b { font-size:clamp(9px, 1.6vw, 16px); line-height:1; }
.tp-vazio { aspect-ratio:1/1.1; }
.tp-sep { grid-column:1/-1; height:8px; }
.tp-det { margin-top:12px; display:flex; gap:14px; align-items:center; flex-wrap:wrap; border-top:1px solid var(--linha); padding-top:12px; }
.tp-det .grande { width:92px; height:100px; border-radius:12px; display:flex; flex-direction:column; justify-content:center; align-items:center; color:#12202A; }
.tp-det .grande b { font-size:34px; } .tp-det dl { display:grid; grid-template-columns:auto auto; gap:2px 14px; margin:0; font-size:13px; }
.tp-det dt { color:var(--suave); } .tp-det dd { margin:0; font-weight:500; }
@media (max-width:640px) { .tp-el small { display:none; } }
`;
let T = null;
export function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  T = { raiz, Streamlit, ativas: new Set(Object.keys(args.cores)), filtro: "", sel: null, args };
  const leg = Object.entries(args.cores).map(([c, cor]) => `<button data-c="${c}" style="background:${cor}">${c}</button>`).join("");
  raiz.innerHTML = `<div class="tp"><div class="tp-topo"><input placeholder="Procurar (nome, símbolo ou número)…"><div class="tp-leg">${leg}</div></div>
    <div class="tp-grelha"></div><div class="tp-det">Clica num elemento para ver os detalhes.</div></div>`;
  raiz.querySelector("input").addEventListener("input", (e) => { T.filtro = e.target.value.trim().toLowerCase(); desenhar(); });
  raiz.querySelectorAll(".tp-leg button").forEach((b) => b.addEventListener("click", () => {
    const c = b.dataset.c;
    if (T.ativas.size === Object.keys(args.cores).length) { T.ativas = new Set([c]); }
    else if (T.ativas.has(c)) { T.ativas.delete(c); if (!T.ativas.size) T.ativas = new Set(Object.keys(args.cores)); }
    else T.ativas.add(c);
    raiz.querySelectorAll(".tp-leg button").forEach((x) => x.classList.toggle("off", !T.ativas.has(x.dataset.c)));
    desenhar();
  }));
  desenhar();
  new ResizeObserver(() => Streamlit.altura(raiz.scrollHeight + 4)).observe(raiz);
}
export function atualizar() {}
function posicao(e) {
  if (e.categoria === "Lantanídeo") return [9, e.z - 57 + 3];
  if (e.categoria === "Actinídeo") return [10, e.z - 89 + 3];
  return [e.periodo, e.grupo];
}
function desenhar() {
  const g = T.raiz.querySelector(".tp-grelha"), el = T.args.elementos;
  const mapa = {}; el.forEach((e) => { const [l, c] = posicao(e); mapa[l + "," + c] = e; });
  let html = "";
  for (let l = 1; l <= 10; l++) {
    if (l === 8) { html += '<div class="tp-sep"></div>'; continue; }
    for (let c = 1; c <= 18; c++) {
      const e = mapa[l + "," + c];
      if (!e) { html += '<div class="tp-vazio"></div>'; continue; }
      const corresponde = (!T.filtro || e.nome.toLowerCase().includes(T.filtro) || e.simbolo.toLowerCase() === T.filtro || String(e.z) === T.filtro);
      const ativo = T.ativas.has(e.categoria) && corresponde;
      html += `<div class="tp-el ${ativo ? "" : "apagado"} ${T.sel === e.z ? "sel" : ""}" data-z="${e.z}" title="${e.nome}"
        style="background:${T.args.cores[e.categoria]}"><small>${e.z}</small><b>${e.simbolo}</b><small>${e.massa.toLocaleString("pt-PT", { maximumFractionDigits: 2 })}</small></div>`;
    }
  }
  g.innerHTML = html;
  g.querySelectorAll(".tp-el").forEach((d) => d.addEventListener("click", () => { T.sel = +d.dataset.z; detalhe(); desenhar(); }));
}
function detalhe() {
  const e = T.args.elementos.find((x) => x.z === T.sel);
  T.raiz.querySelector(".tp-det").innerHTML = `<div class="grande" style="background:${T.args.cores[e.categoria]}"><small>${e.z}</small><b>${e.simbolo}</b></div>
    <dl><dt>Nome</dt><dd>${e.nome}</dd><dt>Número atómico</dt><dd>${e.z}</dd><dt>Massa atómica</dt><dd>${e.massa.toLocaleString("pt-PT")} u</dd>
    <dt>Família</dt><dd>${e.categoria}</dd><dt>Grupo · Período</dt><dd>${e.grupo || "—"} · ${e.periodo}</dd>
    <dt>Configuração eletrónica</dt><dd>${e.configuracao.replace(/([spdf])(\d+)/g, "$1<sup>$2</sup>")}</dd></dl>`;
  T.Streamlit.altura(T.raiz.scrollHeight + 4);
}
