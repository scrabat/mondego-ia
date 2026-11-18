// Simulações de Física do Mondego IA (canvas 2D, sem bibliotecas). Os controlos atuam logo, sem esperar pelo servidor.
// args.sim: "projetil" | "pendulo" | "ondas"
const CSS = `
.fx { border:1px solid var(--linha); border-radius:16px; background:var(--cartao); overflow:hidden; }
.fx canvas { display:block; width:100%; background:var(--fundo); }
.fx-ctl { display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:10px 18px; padding:12px 14px;
  border-top:1px solid var(--linha); }
.fx-ctl label { display:flex; flex-direction:column; gap:3px; font-size:12.5px; color:var(--suave); }
.fx-ctl label b { color:var(--texto); font-weight:600; }
.fx-ctl input[type=range] { accent-color:var(--acento); width:100%; }
.fx-ctl select, .fx-ctl .fx-bt { border:1px solid var(--linha); border-radius:9px; background:var(--cartao); padding:5px 10px; cursor:pointer; }
.fx-bts { display:flex; gap:8px; align-items:end; flex-wrap:wrap; }
.fx-bt.pri { background:var(--primario); border-color:var(--primario); color:#fff; font-weight:600; }
.fx-res { display:flex; flex-wrap:wrap; gap:8px; padding:0 14px 12px; }
.fx-res span { background:var(--bolha); border-radius:999px; padding:3px 11px; font-size:12.5px; color:var(--texto); }
`;
let E = null;

export function iniciar(raiz, args, Streamlit) {
  const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  E = { raiz, Streamlit, sim: null, anim: null };
  return atualizar(args);
}

export function atualizar(args) {
  if (args.sim === E.sim) return;
  E.sim = args.sim;
  cancelAnimationFrame(E.anim);
  ({ projetil, pendulo, ondas }[args.sim] || projetil)(E.raiz, args);
  if (!E.obs) { E.obs = new ResizeObserver(() => E.Streamlit.altura(E.raiz.scrollHeight + 4)); E.obs.observe(E.raiz); }
  setTimeout(() => E.Streamlit.altura(E.raiz.scrollHeight + 4), 30);
}

function cores() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  return { texto: v("--texto"), suave: v("--suave"), linha: v("--linha"), acento: v("--acento"), fundo: v("--fundo"),
           azul: "#2AA5B8", ouro: "#E0B04B" };
}

function montar(raiz, controlos, botoes) {
  raiz.innerHTML = `<div class="fx"><canvas height="380"></canvas><div class="fx-ctl">${controlos}
      <div class="fx-bts">${botoes}</div></div><div class="fx-res"></div></div>`;
  const canvas = raiz.querySelector("canvas");
  const ui = {};
  // mudar o tamanho do canvas apaga-o: redesenha logo a seguir (as simulações animadas redesenham sozinhas)
  const ajustar = () => { const w = canvas.clientWidth; canvas.width = w * devicePixelRatio; canvas.height = 380 * devicePixelRatio;
                          canvas.style.height = "380px"; if (ui.redesenhar) ui.redesenhar(); };
  ajustar();
  new ResizeObserver(ajustar).observe(canvas);
  const val = (id) => +raiz.querySelector(`[data-v="${id}"]`).value;
  raiz.querySelectorAll("input[type=range]").forEach((inp) => {
    const out = inp.parentElement.querySelector("b");
    const mostrar = () => { out.textContent = (+inp.value).toLocaleString("pt-PT") + (inp.dataset.u || ""); };
    inp.addEventListener("input", mostrar); mostrar();
  });
  return Object.assign(ui, { canvas, ctx: canvas.getContext("2d"), val, res: raiz.querySelector(".fx-res") });
}

const deslizador = (id, rotulo, min, max, passo, valor, u = "") =>
  `<label>${rotulo}: <b></b><input type="range" data-v="${id}" min="${min}" max="${max}" step="${passo}" value="${valor}" data-u="${u}"></label>`;
const fmt = (x, d = 2) => Number(x).toLocaleString("pt-PT", { maximumFractionDigits: d, minimumFractionDigits: d });

// ============================================================================ lançamento de projéteis
function projetil(raiz) {
  const ui = montar(raiz,
    deslizador("v0", "Velocidade inicial", 1, 60, 0.5, 20, " m/s") + deslizador("ang", "Ângulo", 0, 90, 1, 45, "°") +
    deslizador("h0", "Altura inicial", 0, 40, 0.5, 0, " m") +
    `<label>Gravidade<select data-v="g"><option value="9.81">Terra (9,81 m/s²)</option><option value="1.62">Lua (1,62 m/s²)</option>
       <option value="3.71">Marte (3,71 m/s²)</option><option value="24.79">Júpiter (24,79 m/s²)</option></select></label>` +
    deslizador("k", "Resistência do ar (k/m)", 0, 0.1, 0.005, 0, " 1/m"),
    `<button class="fx-bt pri" data-a="lancar">Lançar</button><button class="fx-bt" data-a="limpar">Limpar trajetórias</button>`);
  const C = cores();
  let trajetorias = [], atual = null, t0 = 0;
  function calcular() {
    const v0 = ui.val("v0"), a = ui.val("ang") * Math.PI / 180, h0 = ui.val("h0"), g = ui.val("g"), k = ui.val("k");
    let x = 0, y = h0, vx = v0 * Math.cos(a), vy = v0 * Math.sin(a), t = 0, hmax = h0;
    const dt = 0.002, pts = [[0, h0, 0]];
    let passos = 0;
    while (t < 600) {
      const px = x, py = y, pt = t;
      // método do ponto médio (Runge-Kutta 2): sem ar dá exatamente a parábola da fórmula
      const ac = (ux, uy) => { const v = Math.hypot(ux, uy); return [-k * v * ux, -g - k * v * uy]; };
      const a1 = ac(vx, vy), mx = vx + a1[0] * dt / 2, my = vy + a1[1] * dt / 2, a2 = ac(mx, my);
      x += mx * dt; y += my * dt; vx += a2[0] * dt; vy += a2[1] * dt; t += dt; passos += 1;
      hmax = Math.max(hmax, y);
      if (y < 0) { const f = py / (py - y); x = px + (x - px) * f; t = pt + dt * f; y = 0; pts.push([x, 0, t]); break; }
      if (passos % 5 === 0) pts.push([x, y, t]);
    }
    return { pts, alcance: x, tempo: t, hmax, v0, ang: ui.val("ang"), g, k, h0 };
  }
  function desenhar(agora) {
    const { ctx, canvas } = ui, W = canvas.width, H = canvas.height, d = devicePixelRatio;
    ctx.clearRect(0, 0, W, H);
    const todas = trajetorias.concat(atual ? [atual] : []);
    const xmax = Math.max(10, ...todas.map((r) => r.alcance)) * 1.08, ymax = Math.max(5, ...todas.map((r) => r.hmax)) * 1.15;
    const m = 44 * d, esc = Math.min((W - 2 * m) / xmax, (H - 2 * m) / ymax);
    const X = (x) => m + x * esc, Y = (y) => H - m - y * esc;
    // eixos e grelha
    ctx.strokeStyle = C.linha; ctx.fillStyle = C.suave; ctx.lineWidth = d; ctx.font = `${11 * d}px Inter, sans-serif`;
    const passo = Math.pow(10, Math.floor(Math.log10(xmax / 5)));
    for (let x = 0; x <= xmax; x += passo * (xmax / passo > 12 ? 2 : 1)) { ctx.beginPath(); ctx.moveTo(X(x), Y(0)); ctx.lineTo(X(x), Y(ymax)); ctx.stroke(); ctx.fillText(fmt(x, 0) + " m", X(x) - 8 * d, Y(0) + 16 * d); }
    for (let y = 0; y <= ymax; y += passo * (ymax / passo > 8 ? 2 : 1)) { ctx.beginPath(); ctx.moveTo(X(0), Y(y)); ctx.lineTo(X(xmax), Y(y)); ctx.stroke(); ctx.fillText(fmt(y, 0), 6 * d, Y(y) + 4 * d); }
    ctx.strokeStyle = C.texto; ctx.lineWidth = 1.5 * d; ctx.beginPath(); ctx.moveTo(X(0), Y(0)); ctx.lineTo(X(xmax), Y(0)); ctx.stroke();
    // trajetórias anteriores
    for (const r of trajetorias) { ctx.strokeStyle = C.suave; ctx.globalAlpha = 0.45; ctx.setLineDash([5 * d, 5 * d]); tracar(r.pts, r.pts.length); }
    ctx.globalAlpha = 1; ctx.setLineDash([]);
    if (atual) {
      const tempo = Math.min((agora - t0) / 1000, atual.tempo);
      let n = atual.pts.findIndex((p) => p[2] > tempo); if (n < 0) n = atual.pts.length;
      ctx.strokeStyle = C.acento; ctx.lineWidth = 2.5 * d; tracar(atual.pts, n);
      const p = atual.pts[Math.max(0, n - 1)];
      ctx.fillStyle = C.acento; ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 7 * d, 0, 7); ctx.fill();
      if (tempo < atual.tempo) E.anim = requestAnimationFrame(desenhar);
      else { trajetorias.push(atual); atual = null; }
    }
    function tracar(pts, n) { ctx.beginPath(); pts.slice(0, n).forEach((p, i) => (i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])))); ctx.stroke(); }
  }
  function resultados(r) {
    const formula = r.k === 0 && r.h0 === 0
      ? `<span>Fórmula: v₀²·sin(2θ)/g = <b>${fmt(r.v0 ** 2 * Math.sin(2 * r.ang * Math.PI / 180) / r.g)} m</b></span>` : "";
    ui.res.innerHTML = `<span>Alcance: <b>${fmt(r.alcance)} m</b></span><span>Altura máxima: <b>${fmt(r.hmax)} m</b></span>
      <span>Tempo de voo: <b>${fmt(r.tempo)} s</b></span><span>${r.k === 0 ? "Sem resistência do ar" : "Com resistência do ar"}</span>${formula}`;
  }
  raiz.querySelector('[data-a="lancar"]').onclick = () => {
    if (atual) trajetorias.push(atual);
    atual = calcular(); t0 = performance.now(); resultados(atual); cancelAnimationFrame(E.anim); E.anim = requestAnimationFrame(desenhar);
  };
  raiz.querySelector('[data-a="limpar"]').onclick = () => { trajetorias = []; ui.res.innerHTML = ""; desenhar(performance.now()); };
  ui.redesenhar = () => { if (!atual) desenhar(performance.now()); };
  desenhar(performance.now());
}

// ============================================================================ pêndulo (equação exata, Runge-Kutta 4)
function pendulo(raiz) {
  const ui = montar(raiz,
    deslizador("L", "Comprimento do fio", 0.2, 5, 0.1, 1.5, " m") + deslizador("th", "Ângulo inicial", 2, 85, 1, 30, "°") +
    deslizador("b", "Amortecimento", 0, 0.6, 0.01, 0, " 1/s") +
    `<label>Gravidade<select data-v="g"><option value="9.81">Terra (9,81 m/s²)</option><option value="1.62">Lua (1,62 m/s²)</option>
       <option value="3.71">Marte (3,71 m/s²)</option></select></label>`,
    `<button class="fx-bt pri" data-a="iniciar">Recomeçar</button><button class="fx-bt" data-a="pausa">Pausa</button>`);
  const C = cores();
  let th, w, t, historico, pausa = false, ultimo, passagens, Tmedido;
  function reiniciar() { th = ui.val("th") * Math.PI / 180; w = 0; t = 0; historico = []; passagens = []; Tmedido = null; ultimo = performance.now(); }
  const acel = (a, v, g, L, b) => -(g / L) * Math.sin(a) - b * v;
  function passo(dt) {
    const g = ui.val("g"), L = ui.val("L"), b = ui.val("b");
    const k1 = [w, acel(th, w, g, L, b)], k2 = [w + k1[1] * dt / 2, acel(th + k1[0] * dt / 2, w + k1[1] * dt / 2, g, L, b)];
    const k3 = [w + k2[1] * dt / 2, acel(th + k2[0] * dt / 2, w + k2[1] * dt / 2, g, L, b)];
    const k4 = [w + k3[1] * dt, acel(th + k3[0] * dt, w + k3[1] * dt, g, L, b)];
    const antes = th;
    th += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]);
    w += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]);
    t += dt;
    if (antes < 0 && th >= 0) { passagens.push(t); if (passagens.length >= 2) Tmedido = passagens[passagens.length - 1] - passagens[passagens.length - 2]; }
  }
  function desenhar(agora) {
    if (!pausa) { let dt = Math.min((agora - ultimo) / 1000, 0.05); while (dt > 0) { const h = Math.min(dt, 0.002); passo(h); dt -= h; } historico.push([t, th]); if (historico.length > 900) historico.shift(); }
    ultimo = agora;
    const { ctx, canvas } = ui, W = canvas.width, H = canvas.height, d = devicePixelRatio, L = ui.val("L"), g = ui.val("g");
    ctx.clearRect(0, 0, W, H);
    const ox = W * 0.3, oy = 40 * d, esc = (H - 110 * d) / 5, comp = L * esc;
    const bx = ox + comp * Math.sin(th), by = oy + comp * Math.cos(th);
    ctx.strokeStyle = C.linha; ctx.lineWidth = 3 * d; ctx.beginPath(); ctx.moveTo(ox - 60 * d, oy); ctx.lineTo(ox + 60 * d, oy); ctx.stroke();
    ctx.setLineDash([4 * d, 4 * d]); ctx.lineWidth = d; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox, oy + comp + 20 * d); ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle = C.texto; ctx.lineWidth = 2 * d; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(bx, by); ctx.stroke();
    ctx.fillStyle = C.acento; ctx.beginPath(); ctx.arc(bx, by, 14 * d, 0, 7); ctx.fill();
    // energia
    const m = 1, h = L * (1 - Math.cos(th)), Ep = m * g * h, Ec = 0.5 * m * (L * w) ** 2, Et = Math.max(Ep + Ec, 1e-9);
    const barra = (x, val, cor, rot) => { const hh = (H - 120 * d) * val / Math.max(m * g * L * 2, Et); ctx.fillStyle = cor; ctx.fillRect(x, H - 50 * d - hh, 26 * d, hh); ctx.fillStyle = C.suave; ctx.font = `${11 * d}px Inter`; ctx.fillText(rot, x - 2 * d, H - 32 * d); };
    barra(W * 0.56, Ep, C.azul, "Ep"); barra(W * 0.56 + 40 * d, Ec, C.ouro, "Ec");
    // gráfico θ(t)
    const gx = W * 0.68, gw = W * 0.3, gy = H / 2, ga = H * 0.32;
    ctx.strokeStyle = C.linha; ctx.lineWidth = d; ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx + gw, gy); ctx.stroke();
    ctx.fillStyle = C.suave; ctx.fillText("θ(t)", gx, gy - ga - 6 * d);
    ctx.strokeStyle = C.acento; ctx.lineWidth = 1.6 * d; ctx.beginPath();
    const th0 = ui.val("th") * Math.PI / 180;
    historico.forEach((p, i) => { const x = gx + gw * i / 900, y = gy - ga * p[1] / th0; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
    const T0 = 2 * Math.PI * Math.sqrt(L / g);
    ui.res.innerHTML = `<span>Período (pequenas oscilações) T = 2π√(L/g) = <b>${fmt(T0)} s</b></span>
      <span>Período medido: <b>${Tmedido ? fmt(Tmedido) + " s" : "a medir…"}</b></span><span>Tempo: ${fmt(t, 1)} s</span>
      <span>Ângulo: ${fmt(th * 180 / Math.PI, 1)}°</span>`;
    E.anim = requestAnimationFrame(desenhar);
  }
  raiz.querySelector('[data-a="iniciar"]').onclick = reiniciar;
  raiz.querySelector('[data-a="pausa"]').onclick = (e) => { pausa = !pausa; e.target.textContent = pausa ? "Continuar" : "Pausa"; };
  raiz.querySelectorAll("input,select").forEach((el) => el.addEventListener("change", reiniciar));
  reiniciar();
  E.anim = requestAnimationFrame(desenhar);
}

// ============================================================================ ondas: sobreposição, batimentos, ondas estacionárias
function ondas(raiz) {
  const ui = montar(raiz,
    deslizador("A1", "Amplitude 1", 0, 2, 0.05, 1) + deslizador("L1", "Comprimento de onda 1", 0.5, 6, 0.1, 3, " m") +
    deslizador("f1", "Frequência 1", 0.1, 3, 0.05, 0.5, " Hz") +
    deslizador("A2", "Amplitude 2", 0, 2, 0.05, 1) + deslizador("L2", "Comprimento de onda 2", 0.5, 6, 0.1, 3, " m") +
    deslizador("f2", "Frequência 2", 0.1, 3, 0.05, 0.5, " Hz") + deslizador("fase", "Desfasamento", 0, 360, 5, 0, "°") +
    `<label>Sentido da onda 2<select data-v="sent"><option value="1">Mesmo sentido</option><option value="-1">Sentido oposto (onda estacionária)</option></select></label>`,
    `<button class="fx-bt" data-a="pausa">Pausa</button>`);
  const C = cores();
  let t = 0, ultimo = performance.now(), pausa = false;
  function desenhar(agora) {
    if (!pausa) t += (agora - ultimo) / 1000;
    ultimo = agora;
    const { ctx, canvas } = ui, W = canvas.width, H = canvas.height, d = devicePixelRatio;
    ctx.clearRect(0, 0, W, H);
    const v = (id) => ui.val(id), XM = 12, faixa = H / 3;
    const y1 = (x) => v("A1") * Math.sin(2 * Math.PI * (x / v("L1") - v("f1") * t));
    const y2 = (x) => v("A2") * Math.sin(2 * Math.PI * (x / v("L2") - v("sent") * v("f2") * t) + v("fase") * Math.PI / 180);
    const curva = (f, cy, cor, esc, rot) => {
      ctx.strokeStyle = C.linha; ctx.lineWidth = d; ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(W, cy); ctx.stroke();
      ctx.strokeStyle = cor; ctx.lineWidth = 2.2 * d; ctx.beginPath();
      for (let i = 0; i <= 600; i++) { const x = XM * i / 600, px = W * i / 600, py = cy - f(x) * esc; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
      ctx.stroke(); ctx.fillStyle = C.suave; ctx.font = `${11.5 * d}px Inter`; ctx.fillText(rot, 8 * d, cy - faixa * 0.36);
    };
    curva(y1, faixa * 0.5, C.azul, faixa * 0.18, "Onda 1");
    curva(y2, faixa * 1.5, C.ouro, faixa * 0.18, "Onda 2");
    curva((x) => y1(x) + y2(x), faixa * 2.5, C.acento, faixa * 0.11, "Soma (princípio da sobreposição)");
    const vel1 = v("L1") * v("f1"), vel2 = v("L2") * v("f2"), bat = Math.abs(v("f1") - v("f2"));
    ui.res.innerHTML = `<span>v₁ = λ·f = <b>${fmt(vel1)} m/s</b></span><span>v₂ = <b>${fmt(vel2)} m/s</b></span>
      ${bat > 0.001 && v("sent") > 0 ? `<span>Batimentos: <b>${fmt(bat)} Hz</b></span>` : ""}
      ${v("sent") < 0 && v("L1") === v("L2") && v("f1") === v("f2") ? `<span>Onda estacionária: nodos a cada <b>${fmt(v("L1") / 2)} m</b></span>` : ""}`;
    E.anim = requestAnimationFrame(desenhar);
  }
  raiz.querySelector('[data-a="pausa"]').onclick = (e) => { pausa = !pausa; e.target.textContent = pausa ? "Continuar" : "Pausa"; };
  E.anim = requestAnimationFrame(desenhar);
}
