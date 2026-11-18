// Modelo interativo feito pela IA do Laboratório (a pedido do aluno).
// O código da IA corre numa moldura isolada: sandbox sem "allow-same-origin" (não vê a app, os cookies nem os ficheiros)
// e uma política de segurança que bloqueia qualquer pedido à internet. Só pode desenhar e animar dentro da moldura.
const CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; " +
  "font-src data:; media-src data: blob:; form-action 'none'";
const CSS = `
.sim { position:relative; }
.sim-f { display:block; width:100%; border:0; background:transparent; border-radius:12px; color-scheme:normal; }
`;
let S = null;

function cores(escuro) {
  return escuro
    ? { fundo: "#0E1519", cartao: "#172328", texto: "#E6EEF0", suave: "#93A6AB", linha: "#26353B", bolha: "#1C2B31",
        acento: "#4CC3D2", acento2: "#5FA8D3", acento3: "#E0B04B", acento4: "#6FBF8B" }
    : { fundo: "#F6F8F7", cartao: "#FFFFFF", texto: "#16232B", suave: "#5A6B70", linha: "#DCE3E1", bolha: "#E8EEED",
        acento: "#17798A", acento2: "#2E6DB4", acento3: "#D9A21F", acento4: "#3E8E5A" };
}

function documento(html, escuro) {
  // as cores da app ganham sempre (!important), mesmo que o código da IA tente pôr outras: o modelo fica com o
  // aspeto do resto da app, no tema claro e no escuro
  const vars = Object.entries(cores(escuro)).map(([k, v]) => `--${k}:${v} !important`).join(";");
  const base = `<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>:root{${vars};color-scheme:${escuro ? "dark" : "light"}}
html,body{min-height:0 !important}
html,body{margin:0;padding:0;background:transparent;color:var(--texto);font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;font-size:14px;line-height:1.45}
*{box-sizing:border-box} button,input,select{font:inherit;color:inherit}
button{background:var(--cartao);border:1px solid var(--linha);border-radius:10px;padding:5px 12px;cursor:pointer}
button:hover{border-color:var(--acento)} input[type=range]{accent-color:var(--acento)} canvas{max-width:100%}</style>
<script>(function(){var u=0;function a(){var b=document.body,h=Math.max(document.documentElement.scrollHeight,b?b.scrollHeight:0);
if(h&&Math.abs(h-u)>2){u=h;parent.postMessage({mondegoSim:1,altura:h},"*");}}
addEventListener("load",a);setInterval(a,500);window.alert=window.confirm=window.prompt=function(){return null;};
addEventListener("error",function(e){parent.postMessage({mondegoSim:1,erro:String(e.message||e)},"*");});})();<\/script>`;
  let doc = String(html || "")
    .replace(/<meta[^>]+http-equiv[^>]*>/gi, "")   // nada de redireções nem de outra política
    .replace(/<base[^>]*>/gi, "");
  if (/<head[^>]*>/i.test(doc)) return doc.replace(/<head[^>]*>/i, (m) => m + base);
  if (/<html[^>]*>/i.test(doc)) return doc.replace(/<html[^>]*>/i, (m) => m + "<head>" + base + "</head>");
  return "<!doctype html><html lang=\"pt\"><head>" + base + "</head><body>" + doc + "</body></html>";
}

function resumo(t) {  // identifica o conteúdo (para só recarregar quando muda)
  let h = 0;
  for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) | 0;
  return t.length + ":" + h;
}

export function iniciar(raiz, args, Streamlit, escuro) {
  const estilo = document.createElement("style");
  estilo.textContent = CSS;
  document.head.appendChild(estilo);
  raiz.innerHTML = '<div class="sim"><iframe class="sim-f" sandbox="allow-scripts" referrerpolicy="no-referrer" ' +
    'title="Modelo interativo"></iframe></div>';
  S = { raiz, Streamlit, f: raiz.querySelector("iframe"), chave: null, reportado: false };
  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!S || ev.source !== S.f.contentWindow || !d || !d.mondegoSim) return;
    if (d.altura) {
      const h = Math.max(180, Math.min(900, Number(d.altura) || 0));
      S.f.style.height = h + "px";
      S.Streamlit.altura(h + 4);
    }
    if (d.erro && !S.reportado && !/ResizeObserver|Script error/i.test(d.erro)) {
      S.reportado = true;
      S.Streamlit.valor({ evento: "erro", erro: String(d.erro).slice(0, 400), t: Date.now() });
    }
  });
  return atualizar(args, escuro);
}

export function atualizar(args, escuro) {
  const html = String(args.html || "");
  const chave = resumo(html) + (escuro ? ":e" : ":c");
  if (chave === S.chave) return;
  S.chave = chave;
  S.reportado = false;
  const h = args.altura || 420;
  S.f.style.height = h + "px";
  S.f.srcdoc = documento(html, escuro);
  S.Streamlit.altura(h + 4);
}
