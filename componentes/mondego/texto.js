// Texto com fórmulas "como no papel" dentro dos componentes (KaTeX) e um markdown simples (negrito, itálico, código,
// listas, mudanças de linha). Todo o texto é escapado antes: nada vindo da IA é executado como HTML.
let katexPronto = null;

export function carregarKatex() {
  if (katexPronto) return katexPronto;
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css";
  document.head.appendChild(css);
  const script = (src) => new Promise((ok, falha) => {
    const s = document.createElement("script");
    s.src = src; s.onload = ok; s.onerror = () => falha(new Error("KaTeX indisponível"));
    document.head.appendChild(s);
  });
  katexPronto = script("https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js")
    .then(() => script("https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"))
    .catch((e) => { console.warn(e); });
  return katexPronto;
}

const escapar = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function html(texto) {
  // normaliza delimitadores como no servidor (\( \) e \[ \])
  let t = String(texto ?? "").replace(/\\\[([\s\S]+?)\\\]/g, (_, f) => `$$${f}$$`).replace(/\\\(([\s\S]+?)\\\)/g, (_, f) => `$${f}$`);
  // protege as fórmulas antes do markdown (para * e _ dentro delas não virarem itálico)
  const formulas = [];
  t = t.replace(/\$\$[\s\S]+?\$\$|\$[^$\n]+?\$/g, (f) => { formulas.push(f); return `\u0000${formulas.length - 1}\u0000`; });
  t = escapar(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>")
    // texto antigo sem LaTeX (ex.: «x^2», «sqrt(x)»): expoentes em cima e raiz com o símbolo, como no papel
    .replace(/([\w)\]])\^\{([^}]{1,12})\}/g, "$1<sup>$2</sup>")
    .replace(/([\w)\]])\^(-?[\w.]{1,6})/g, "$1<sup>$2</sup>")
    .replace(/\bsqrt\(/g, "√(");
  const linhas = t.split("\n");
  let saida = "", lista = false;
  for (const l of linhas) {
    const item = l.match(/^\s*[-•]\s+(.*)/);
    if (item) { if (!lista) { saida += "<ul>"; lista = true; } saida += `<li>${item[1]}</li>`; continue; }
    if (lista) { saida += "</ul>"; lista = false; }
    saida += l.trim() ? `<p>${l}</p>` : "";
  }
  if (lista) saida += "</ul>";
  return saida.replace(/\u0000(\d+)\u0000/g, (_, i) => escapar(formulas[+i]));
}

export async function formulas(el) {
  await carregarKatex();
  if (window.renderMathInElement) {
    window.renderMathInElement(el, { delimiters: [{ left: "$$", right: "$$", display: true }, { left: "$", right: "$", display: false }],
                                     throwOnError: false });
  }
}

export function preencher(el, texto) {
  el.innerHTML = html(texto);
  formulas(el);
}
