// Editor de Python que corre no browser (Pyodide): nada é executado no servidor nem no computador fora do browser.
const CSS = `
.cd { border:1px solid var(--linha); border-radius:16px; background:var(--cartao); overflow:hidden; }
.cd-barra { display:flex; gap:8px; align-items:center; padding:8px 10px; border-bottom:1px solid var(--linha); flex-wrap:wrap; }
.cd-bt { border:1px solid var(--linha); border-radius:9px; background:var(--cartao); padding:5px 12px; cursor:pointer; }
.cd-bt.pri { background:var(--primario); border-color:var(--primario); color:#fff; font-weight:600; }
.cd-bt:disabled { opacity:.5; cursor:wait; }
.cd-estado { font-size:12px; color:var(--suave); margin-left:auto; }
.cd-ed { display:flex; background:#1E1D1A; }
.cd-nums { padding:12px 8px; color:#7A7466; text-align:right; user-select:none; font:13px/1.55 'JetBrains Mono', Consolas, monospace; white-space:pre; }
.cd-ed textarea { flex:1; border:0; outline:0; resize:vertical; min-height:260px; padding:12px; background:#1E1D1A; color:#F2EEE6;
  caret-color:#F2EEE6; font:13px/1.55 'JetBrains Mono', Consolas, monospace; tab-size:4; white-space:pre; overflow:auto; }
.cd-saida { margin:0; padding:10px 12px; min-height:70px; max-height:260px; overflow:auto; background:var(--fundo); color:var(--texto);
  font:12.5px/1.5 'JetBrains Mono', Consolas, monospace; white-space:pre-wrap; border-top:1px solid var(--linha); }
.cd-saida .err { color:#B3261E; }
`;
let C = null;
export function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  C = { raiz, Streamlit, chave: null, py: null };
  raiz.innerHTML = `<div class="cd"><div class="cd-barra"><button class="cd-bt pri" data-a="correr">▶ Executar</button>
      <button class="cd-bt" data-a="ajuda">Pedir ajuda à IA</button><button class="cd-bt" data-a="limpar">Limpar saída</button>
      <span class="cd-estado">Python 3 no browser (Pyodide)</span></div>
    <div class="cd-ed"><div class="cd-nums">1</div><textarea spellcheck="false" aria-label="Código Python"></textarea></div>
    <pre class="cd-saida" aria-live="polite"></pre></div>`;
  const ta = raiz.querySelector("textarea");
  ta.addEventListener("input", numerar);
  ta.addEventListener("scroll", () => { raiz.querySelector(".cd-nums").scrollTop = ta.scrollTop; });
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") { e.preventDefault(); const i = ta.selectionStart; ta.setRangeText("    ", i, ta.selectionEnd, "end"); numerar(); }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); correr(); }
  });
  raiz.querySelector('[data-a="correr"]').onclick = correr;
  raiz.querySelector('[data-a="limpar"]').onclick = () => { raiz.querySelector(".cd-saida").textContent = ""; };
  raiz.querySelector('[data-a="ajuda"]').onclick = () => Streamlit.valor({ evento: "ajuda", codigo: ta.value,
    saida: raiz.querySelector(".cd-saida").textContent.slice(-4000), t: Date.now() });
  new ResizeObserver(() => Streamlit.altura(raiz.scrollHeight + 4)).observe(raiz);
  return atualizar(args);
}
export function atualizar(args) {
  if (args.chave_codigo !== C.chave) {
    C.chave = args.chave_codigo;
    C.raiz.querySelector("textarea").value = args.codigo || "";
    numerar();
  }
}
function numerar() {
  const n = C.raiz.querySelector("textarea").value.split("\n").length;
  C.raiz.querySelector(".cd-nums").textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n");
}
async function correr() {
  const bt = C.raiz.querySelector('[data-a="correr"]'), estado = C.raiz.querySelector(".cd-estado"), saida = C.raiz.querySelector(".cd-saida");
  bt.disabled = true;
  saida.textContent = "";
  const escrever = (t, erro) => { const s = document.createElement("span"); if (erro) s.className = "err"; s.textContent = t + "\n"; saida.appendChild(s); };
  try {
    if (!C.py) {
      estado.textContent = "A preparar o Python (só na primeira vez, pode demorar uns segundos)…";
      if (!window.loadPyodide) await new Promise((ok, falha) => { const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"; s.onload = ok; s.onerror = () => falha(new Error("sem ligação à internet")); document.head.appendChild(s); });
      C.py = await loadPyodide();
    }
    C.py.setStdout({ batched: (t) => escrever(t) });
    C.py.setStderr({ batched: (t) => escrever(t, true) });
    C.py.setStdin({ stdin: () => prompt("O programa pede um valor (input):") ?? "" });
    const codigo = C.raiz.querySelector("textarea").value;
    estado.textContent = "A executar…";
    await C.py.loadPackagesFromImports(codigo);
    const t0 = performance.now();
    await C.py.runPythonAsync(codigo);
    estado.textContent = `Executado em ${((performance.now() - t0) / 1000).toFixed(2)} s`;
    if (!saida.textContent) escrever("(o programa não escreveu nada — usa print() para ver resultados)");
  } catch (erro) {
    const msg = String(erro && erro.message || erro);
    const linhas = msg.split("\n").filter((l) => !l.includes("/lib/python") && !l.includes("_pyodide"));
    escrever(linhas.join("\n").trim(), true);
    estado.textContent = "Erro — usa «Pedir ajuda à IA» para perceber o que falhou";
  } finally {
    bt.disabled = false;
    C.Streamlit.altura(C.raiz.scrollHeight + 4);
  }
}
