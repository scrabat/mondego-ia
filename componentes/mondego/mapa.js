// Mapa interativo (Leaflet + OpenStreetMap) com locais gerados a partir de um tema (História e Geografia).
const CSS = `
.mp { border:1px solid var(--linha); border-radius:16px; overflow:hidden; background:var(--cartao); }
.mp-mapa { width:100%; }
.mp-lista { display:flex; gap:6px; flex-wrap:wrap; padding:10px 12px; border-top:1px solid var(--linha); }
.mp-lista button { border:1px solid var(--linha); background:var(--cartao); border-radius:999px; padding:3px 10px; cursor:pointer; font-size:12.5px; }
.mp-lista button:hover { border-color:var(--acento); }
.mp-num { background:var(--primario); color:#fff; border-radius:50%; width:24px; height:24px; display:grid; place-items:center;
  font-weight:700; font-size:12px; border:2px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.35); }
.leaflet-popup-content { font-family:Inter, system-ui, sans-serif; color:#12202A; }
`;
let M = null;
function carregar(url, tipo) {
  return new Promise((ok, falha) => {
    const el = document.createElement(tipo === "css" ? "link" : "script");
    if (tipo === "css") { el.rel = "stylesheet"; el.href = url; } else { el.src = url; }
    el.onload = ok; el.onerror = () => falha(new Error("Não foi possível carregar " + url));
    document.head.appendChild(el);
  });
}
export async function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  await carregar("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "css");
  await carregar("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", "js");
  M = { raiz, Streamlit, chave: null };
  raiz.innerHTML = `<div class="mp"><div class="mp-mapa" style="height:${args.altura || 480}px"></div><div class="mp-lista"></div></div>`;
  M.mapa = L.map(raiz.querySelector(".mp-mapa"), { scrollWheelZoom: true }).setView([39.5, -8], 5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>' }).addTo(M.mapa);
  M.camada = L.layerGroup().addTo(M.mapa);
  await atualizar(args);
}
export async function atualizar(args) {
  const chave = JSON.stringify(args.locais);
  if (chave === M.chave) return;
  M.chave = chave;
  M.camada.clearLayers();
  const locais = (args.locais || []).filter((l) => isFinite(l.lat) && isFinite(l.lon));
  const lista = M.raiz.querySelector(".mp-lista");
  lista.innerHTML = "";
  const marcadores = locais.map((l, i) => {
    const icone = L.divIcon({ className: "", html: `<div class="mp-num">${i + 1}</div>`, iconSize: [24, 24], iconAnchor: [12, 12] });
    const esc = (t) => String(t || "").replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
    const m = L.marker([l.lat, l.lon], { icon: icone }).bindPopup(`<b>${esc(l.nome)}</b>${l.data ? " · " + esc(l.data) : ""}<br>${esc(l.descricao)}`);
    m.addTo(M.camada);
    const b = document.createElement("button");
    b.textContent = `${i + 1}. ${l.nome}`;
    b.onclick = () => { M.mapa.flyTo([l.lat, l.lon], Math.max(M.mapa.getZoom(), 7)); m.openPopup(); };
    lista.appendChild(b);
    return m;
  });
  if (args.ligar && locais.length > 1) L.polyline(locais.map((l) => [l.lat, l.lon]), { color: "#17798A", weight: 2.5, dashArray: "6 6" }).addTo(M.camada);
  if (marcadores.length) M.mapa.fitBounds(L.featureGroup(marcadores).getBounds().pad(0.2));
  setTimeout(() => { M.mapa.invalidateSize(); M.Streamlit.altura(M.raiz.scrollHeight + 4); }, 60);
}
