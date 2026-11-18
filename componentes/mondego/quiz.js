// Quiz ao estilo NotebookLM: uma pergunta de cada vez, opções A–D em cartões, dica, explicação de cada opção depois de
// responder, navegação Anterior/Seguinte, teclado (1–4 ou A–D, ←/→, D = dica) e ecrã final com a nota e revisão.
// O progresso fica no browser (localStorage); o resultado final é enviado para a app (histórico e temas fracos).
const CSS = `
.qz { border:1px solid var(--linha); border-radius:20px; background:var(--cartao); padding:22px 24px 18px; color:var(--texto); }
.qz-topo { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; }
.qz-titulo { font-weight:600; font-size:15px; }
.qz-conta { font-size:13px; color:var(--suave); white-space:nowrap; }
.qz-barra { height:4px; border-radius:4px; background:var(--bolha); overflow:hidden; margin-bottom:20px; }
.qz-barra i { display:block; height:100%; background:var(--acento); transition:width .25s ease; }
.qz-tema { display:inline-block; font-size:12px; color:var(--suave); background:var(--bolha); border-radius:999px; padding:2px 10px; margin-bottom:10px; }
.qz-pergunta { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:21px; line-height:1.5; margin-bottom:18px; }
.qz-pergunta p { margin:0 0 6px; }
.qz-opcoes { display:flex; flex-direction:column; gap:10px; }
.qz-op { display:flex; gap:14px; align-items:flex-start; text-align:left; width:100%; border:1.5px solid var(--linha); border-radius:14px;
  background:var(--cartao); padding:13px 16px; cursor:pointer; transition:border-color .12s, background .12s, transform .08s; }
.qz-op:hover { border-color:var(--acento); background:var(--acento-claro); }
.qz-op:active { transform:scale(.995); }
.qz-letra { flex:0 0 30px; height:30px; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:13px; background:var(--bolha); }
.qz-corpo { flex:1; min-width:0; }
.qz-corpo p { margin:3px 0; font-size:15px; line-height:1.5; }
.qz-just { margin-top:8px; font-size:13.5px; line-height:1.5; color:var(--texto); opacity:.9; border-top:1px dashed var(--linha); padding-top:8px; display:none; }
.qz-just b.ok { color:#2E7D4F; } .qz-just b.mal { color:#B3261E; }
.qz-op.certa { border-color:#2E7D4F; background:rgba(46,125,79,.10); } .qz-op.certa .qz-letra { background:#2E7D4F; color:#fff; }
.qz-op.errada { border-color:#B3261E; background:rgba(179,38,30,.08); } .qz-op.errada .qz-letra { background:#B3261E; color:#fff; }
.qz-op.vista .qz-just, .qz-op.certa .qz-just, .qz-op.errada .qz-just { display:block; }
.qz-just:empty { display:none !important; }
.qz-respondida .qz-op:not(.certa):not(.errada) { opacity:.75; }
.qz-dica { margin-top:14px; border-radius:12px; background:var(--acento-claro); padding:10px 14px; font-size:14px; display:none; }
.qz-dica.on { display:block; }
.qz-fonte { margin-top:10px; font-size:12.5px; color:var(--suave); }
.qz-rodape { display:flex; gap:10px; margin-top:20px; align-items:center; }
.qz-bt { border:1px solid var(--linha); background:var(--cartao); border-radius:11px; padding:9px 16px; cursor:pointer; font-weight:500;
  white-space:nowrap; color:var(--texto); }
@media (max-width:420px) { .qz-bt { padding:8px 11px; } .qz-rodape { gap:6px; } }
.qz-bt:hover:not(:disabled) { border-color:var(--acento); background:var(--acento-claro); }
.qz-bt:disabled { opacity:.45; cursor:default; }
.qz-bt.pri { background:var(--primario); border-color:var(--primario); color:#fff; }
.qz-bt.pri:hover:not(:disabled) { background:var(--primario-hover); border-color:var(--primario-hover); color:#fff; }
.qz-espaco { flex:1; }
.qz-atalhos { font-size:11.5px; color:var(--suave); margin-top:12px; text-align:center; }
.qz-fim { text-align:center; padding:8px 0 4px; }
.qz-anel { width:140px; height:140px; margin:6px auto 10px; border-radius:50%; display:grid; place-items:center; }
.qz-anel > div { width:114px; height:114px; border-radius:50%; background:var(--cartao); display:grid; place-items:center; }
.qz-anel b { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size:34px; }
.qz-msg { color:var(--suave); margin-bottom:16px; }
.qz-temas { display:flex; flex-wrap:wrap; justify-content:center; gap:6px; margin:0 0 16px; }
.qz-temas span { font-size:12.5px; border-radius:999px; padding:3px 10px; background:var(--bolha); }
.qz-rev { text-align:left; margin-top:14px; border-top:1px solid var(--linha); }
.qz-rev details { border-bottom:1px solid var(--linha); padding:9px 2px; }
.qz-rev summary { cursor:pointer; display:flex; gap:10px; align-items:center; list-style:none; font-size:14px; }
.qz-rev summary::-webkit-details-marker { display:none; }
.qz-rev .ic { width:22px; height:22px; border-radius:50%; display:grid; place-items:center; color:#fff; font-size:12px; flex:0 0 22px; }
.qz-rev .det { font-size:13.5px; padding:8px 0 2px 32px; line-height:1.5; }
@keyframes qz-entra { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
.qz-anim { animation:qz-entra .22s ease-out; }
`;
const LETRAS = "ABCDEF";
let Q = null, T = null;

export async function iniciar(raiz, args, Streamlit) {
  T = await import("./texto.js" + new URL(import.meta.url).search);
  T.carregarKatex();
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  Q = { raiz, Streamlit, chave: null };
  new ResizeObserver(() => Streamlit.altura(raiz.scrollHeight + 4)).observe(raiz);
  document.addEventListener("keydown", teclado);
  return atualizar(args);
}

export function atualizar(args) {
  if (args.quiz_id === Q.chave) return;
  Q.chave = args.quiz_id;
  Q.titulo = args.titulo || "Quiz";
  Q.perguntas = args.perguntas || [];
  Q.guardar = "mondego_quiz_" + args.quiz_id;
  let est = null;
  try { est = JSON.parse(localStorage.getItem(Q.guardar) || "null"); } catch (e) { est = null; }
  Q.e = est && est.n === Q.perguntas.length ? est : { n: Q.perguntas.length, ordem: Q.perguntas.map((_, i) => i), pos: 0, resp: {}, dicas: [], vistas: {}, fim: false, enviado: false };
  desenhar();
}

function gravar() { try { localStorage.setItem(Q.guardar, JSON.stringify(Q.e)); } catch (e) { /* sem armazenamento: segue */ } }
const correta = (i) => +(Q.perguntas[i].correta || 0);

function desenhar() {
  const e = Q.e;
  if (e.fim) return final();
  const idx = e.ordem[e.pos], q = Q.perguntas[idx], resp = e.resp[idx], total = e.ordem.length;
  const just = Array.isArray(q.justificacoes) ? q.justificacoes : [];
  const respondida = resp !== undefined;
  Q.raiz.innerHTML = `<div class="qz"><div class="qz-topo"><span class="qz-titulo"></span><span class="qz-conta">Pergunta ${e.pos + 1} de ${total}</span></div>
    <div class="qz-barra"><i style="width:${((e.pos + (respondida ? 1 : 0)) / total) * 100}%"></i></div>
    <div class="qz-anim">${q.tema ? '<span class="qz-tema"></span>' : ""}<div class="qz-pergunta"></div>
    <div class="qz-opcoes ${respondida ? "qz-respondida" : ""}"></div><div class="qz-dica"></div><div class="qz-fonte"></div></div>
    <div class="qz-rodape"><button class="qz-bt" data-a="ant">← Anterior</button><button class="qz-bt" data-a="dica"><svg viewBox="0 0 24 24" width="15" height="15" style="vertical-align:-2px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></svg> Dica</button>
      <span class="qz-espaco"></span><button class="qz-bt ${respondida ? "pri" : ""}" data-a="seg">${e.pos === total - 1 ? "Ver resultado" : "Seguinte →"}</button></div>
    <div class="qz-atalhos">Atalhos: 1–4 escolher · ← → navegar · D dica</div></div>`;
  Q.raiz.querySelector(".qz-titulo").textContent = Q.titulo;
  if (q.tema) Q.raiz.querySelector(".qz-tema").textContent = q.tema;
  T.preencher(Q.raiz.querySelector(".qz-pergunta"), q.pergunta);
  const lista = Q.raiz.querySelector(".qz-opcoes");
  (q.opcoes || []).slice(0, 6).forEach((op, k) => {
    const b = document.createElement("button");
    b.className = "qz-op";
    if (respondida) {
      if (k === correta(idx)) b.classList.add("certa");
      else if (k === resp) b.classList.add("errada");
      if ((e.vistas[idx] || []).includes(k)) b.classList.add("vista");
    }
    b.innerHTML = `<span class="qz-letra">${respondida && k === correta(idx) ? "✓" : respondida && k === resp ? "✕" : LETRAS[k]}</span>
      <span class="qz-corpo"><span class="qz-txt"></span><div class="qz-just"></div></span>`;
    T.preencher(b.querySelector(".qz-txt"), op);
    if (just[k]) T.preencher(b.querySelector(".qz-just"), (k === correta(idx) ? "**Resposta certa.** " : "**Não exatamente.** ") + just[k]);
    else if (k === correta(idx) && q.explicacao) T.preencher(b.querySelector(".qz-just"), "**Resposta certa.** " + q.explicacao);
    else if (k !== correta(idx)) T.preencher(b.querySelector(".qz-just"), `**Não é esta.** A resposta certa é a ${LETRAS[correta(idx)]}.`);
    b.querySelector(".qz-just b")?.classList.add(k === correta(idx) ? "ok" : "mal");
    b.addEventListener("click", () => escolher(k));
    lista.appendChild(b);
  });
  const dica = Q.raiz.querySelector(".qz-dica");
  if (q.dica) T.preencher(dica, "**Dica:** " + q.dica);
  if (e.dicas.includes(idx) && !respondida) dica.classList.add("on");
  if (respondida && q.fonte) Q.raiz.querySelector(".qz-fonte").textContent = "Fonte: " + q.fonte;
  const bt = (a) => Q.raiz.querySelector(`[data-a="${a}"]`);
  bt("ant").disabled = e.pos === 0;
  bt("dica").disabled = respondida || !q.dica || e.dicas.includes(idx);
  bt("ant").onclick = () => mover(-1);
  bt("seg").onclick = () => mover(1);
  bt("dica").onclick = () => { e.dicas.push(idx); gravar(); desenhar(); };
}

function escolher(k) {
  const e = Q.e, idx = e.ordem[e.pos];
  if (e.resp[idx] === undefined) { e.resp[idx] = k; e.vistas[idx] = [k, correta(idx)]; }
  else { (e.vistas[idx] = e.vistas[idx] || []).push(k); } // depois de responder: ver a explicação das outras opções
  gravar(); desenhar();
}

function mover(passo) {
  const e = Q.e;
  if (passo > 0 && e.pos === e.ordem.length - 1) { e.fim = true; gravar(); return desenhar(); }
  e.pos = Math.max(0, Math.min(e.ordem.length - 1, e.pos + passo));
  gravar(); desenhar();
}

function teclado(ev) {
  if (!Q || Q.e.fim || ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;
  const k = ev.key.toUpperCase();
  if (/^[1-6]$/.test(k)) escolher(+k - 1);
  else if (k === "D") Q.raiz.querySelector('[data-a="dica"]')?.click();
  else if (ev.key === "ArrowRight") mover(1);
  else if (ev.key === "ArrowLeft") mover(-1);
}

function final() {
  const e = Q.e, ordem = e.ordem;
  const certas = ordem.filter((i) => e.resp[i] === correta(i)).length, total = ordem.length;
  const pct = total ? certas / total : 0;
  const temas = {};
  ordem.forEach((i) => { const t = (Q.perguntas[i].tema || "Geral").trim(); temas[t] = temas[t] || [0, 0];
    if (e.resp[i] !== undefined) { temas[t][1] += 1; if (e.resp[i] === correta(i)) temas[t][0] += 1; } });
  if (!e.enviado) {
    e.enviado = true; gravar();
    Q.Streamlit.valor({ evento: "resultado", certas, total, completo: total === Q.perguntas.length, temas, t: Date.now() });
  }
  const msg = pct >= 0.85 ? "Excelente! Dominas esta matéria." : pct >= 0.6 ? "Bom trabalho — revê as que falhaste." : "Ainda há temas a rever. Começa pelas que erraste.";
  const cor = pct >= 0.6 ? "#2E7D4F" : "var(--acento)";
  Q.raiz.innerHTML = `<div class="qz"><div class="qz-fim qz-anim"><div class="qz-titulo"></div>
    <div class="qz-anel" style="background:conic-gradient(${cor} ${pct * 360}deg, var(--bolha) 0)"><div><b>${certas}/${total}</b></div></div>
    <div class="qz-msg">${(20 * pct).toFixed(1).replace(".", ",")} valores · ${msg}</div><div class="qz-temas"></div>
    <div class="qz-rodape" style="justify-content:center"><button class="qz-bt pri" data-a="erradas" ${certas === total ? "disabled" : ""}>Rever as que errei</button>
      <button class="qz-bt" data-a="repetir">Repetir o quiz</button></div></div><div class="qz-rev"></div></div>`;
  Q.raiz.querySelector(".qz-titulo").textContent = Q.titulo;
  const tdiv = Q.raiz.querySelector(".qz-temas");
  Object.entries(temas).forEach(([t, [c, n]]) => { if (!n) return; const s = document.createElement("span"); s.textContent = `${t}: ${c}/${n}`; tdiv.appendChild(s); });
  const rev = Q.raiz.querySelector(".qz-rev");
  ordem.forEach((i, n) => {
    const q = Q.perguntas[i], r = e.resp[i], ok = r === correta(i);
    const d = document.createElement("details");
    d.innerHTML = `<summary><span class="ic" style="background:${r === undefined ? "#7C8C91" : ok ? "#2E7D4F" : "#B3261E"}">${r === undefined ? "–" : ok ? "✓" : "✕"}</span><span class="t"></span></summary><div class="det"></div>`;
    T.preencher(d.querySelector(".t"), `**${n + 1}.** ${q.pergunta}`);
    const just = Array.isArray(q.justificacoes) ? q.justificacoes : [];
    T.preencher(d.querySelector(".det"), (r !== undefined && !ok ? `**A tua resposta:** ${q.opcoes[r]}\n` : "") +
      `**Resposta certa:** ${q.opcoes[correta(i)]}\n${just[correta(i)] || q.explicacao || ""}`);
    rev.appendChild(d);
  });
  Q.raiz.querySelector('[data-a="erradas"]').onclick = () => {
    const erradas = ordem.filter((i) => e.resp[i] !== correta(i));
    Q.e = { n: Q.perguntas.length, ordem: erradas, pos: 0, resp: {}, dicas: [], vistas: {}, fim: false, enviado: false }; gravar(); desenhar();
  };
  Q.raiz.querySelector('[data-a="repetir"]').onclick = () => {
    Q.e = { n: Q.perguntas.length, ordem: Q.perguntas.map((_, i) => i), pos: 0, resp: {}, dicas: [], vistas: {}, fim: false, enviado: false }; gravar(); desenhar();
  };
}
