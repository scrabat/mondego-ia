// Visualizador 3D do Mondego IA (Three.js). Desenha modelos do formato "mondego3d" (estudio3d.py) e ficheiros GLB/glTF.
// Rodar (arrastar), aproximar (roda do rato / dois dedos), selecionar peças (clique), etiquetas, cortes transversais,
// vista explodida, capturar capa e descarregar GLB. A seleção e a capa são enviadas para a app.
// Quando o modelo foi melhorado no Blender (motor_blender.py), cada peça usa a malha feita pelo Blender (arestas
// arredondadas, superfícies lisas, relevo, materiais físicos) em vez da peça simples; nome, cor, posição e textos
// continuam a vir do modelo, por isso a seleção, as etiquetas, a lista de estruturas e o Testa-te funcionam igual.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const CSS = `
.v3-caixa { position:relative; width:100%; border-radius:16px; overflow:hidden; border:1px solid var(--linha);
  background:radial-gradient(120% 100% at 50% 35%, var(--cartao) 0%, var(--fundo) 75%); touch-action:none; }
.v3-caixa canvas { display:block; outline:none; }
.v3-barra { position:absolute; top:10px; right:10px; display:flex; flex-direction:column; gap:6px; z-index:5; }
.v3-bt { width:34px; height:34px; border-radius:10px; border:1px solid var(--linha); background:var(--cartao); color:var(--texto);
  display:grid; place-items:center; cursor:pointer; padding:0; box-shadow:0 2px 8px rgba(0,0,0,.08); }
.v3-bt:hover, .v3-bt.ativo { border-color:var(--acento); background:var(--acento-claro); }
.v3-bt svg { width:18px; height:18px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
.v3-painel { position:absolute; left:10px; bottom:10px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; z-index:5;
  background:var(--cartao); border:1px solid var(--linha); border-radius:12px; padding:6px 10px; font-size:12.5px; color:var(--texto);
  max-width:calc(100% - 70px); }
.v3-painel label { display:flex; align-items:center; gap:6px; white-space:nowrap; }
.v3-painel input[type=range] { width:110px; accent-color:var(--acento); }
.v3-painel select { border:1px solid var(--linha); border-radius:6px; background:var(--cartao); padding:1px 4px; }
.v3-dica { position:absolute; left:12px; top:10px; font-size:12px; color:var(--suave); z-index:4; pointer-events:none; }
.v3-tip { position:absolute; pointer-events:none; z-index:6; background:var(--cartao); color:var(--texto); border:1px solid var(--linha);
  border-radius:8px; padding:3px 8px; font-size:12px; white-space:nowrap; transform:translate(12px, -28px); display:none; }
.v3-etq { background:var(--cartao); color:var(--texto); border:1px solid var(--linha); border-radius:999px; padding:2px 9px;
  font-size:11.5px; font-weight:500; white-space:nowrap; box-shadow:0 2px 6px rgba(0,0,0,.12); pointer-events:none; }
.v3-etq.sel { border-color:var(--acento); color:var(--acento); }
.v3-aviso { position:absolute; inset:0; display:grid; place-items:center; color:var(--suave); z-index:3; pointer-events:none; }
.v3-info { position:absolute; left:10px; top:34px; max-width:min(320px, calc(100% - 70px)); z-index:5; display:none;
  background:var(--cartao); border:1px solid var(--acento); border-radius:12px; padding:8px 11px; font-size:12.5px; line-height:1.45; }
.v3-info b { display:block; font-size:13.5px; margin-bottom:2px; }
.v3-info .g { display:inline-block; font-size:11px; color:var(--suave); background:var(--bolha); border-radius:999px; padding:0 7px; margin-bottom:4px; }
.v3-info .s { margin-top:5px; } .v3-info .s em { font-style:normal; font-weight:600; }
.v3-info .acoes { display:flex; gap:6px; margin-top:7px; }
.v3-mini { border:1px solid var(--linha); background:var(--cartao); color:var(--texto); border-radius:8px; padding:3px 9px; font-size:12px; cursor:pointer; }
.v3-mini:hover, .v3-mini.on { border-color:var(--acento); background:var(--acento-claro); }
.v3-lista { position:absolute; top:10px; right:54px; bottom:10px; width:250px; z-index:6; display:none; flex-direction:column;
  background:var(--cartao); border:1px solid var(--linha); border-radius:14px; box-shadow:0 6px 24px rgba(0,0,0,.14); overflow:hidden; }
.v3-lista.on { display:flex; }
.v3-lista-topo { padding:9px 10px; border-bottom:1px solid var(--linha); display:flex; flex-direction:column; gap:7px; }
.v3-lista-topo input[type=search] { border:1px solid var(--borda-campo); border-radius:8px; padding:5px 8px; background:var(--campo); color:var(--campo-texto); font:inherit; font-size:12.5px; }
.v3-lista-topo label { font-size:12px; color:var(--suave); display:flex; align-items:center; gap:6px; }
.v3-lista-topo input[type=range] { flex:1; accent-color:var(--acento); }
.v3-itens { overflow:auto; flex:1; padding:4px 0; }
.v3-grupo { font-size:11px; letter-spacing:.04em; text-transform:uppercase; color:var(--suave); padding:8px 12px 3px; }
.v3-item { display:flex; align-items:center; gap:6px; padding:4px 8px 4px 12px; font-size:12.5px; cursor:pointer; }
.v3-item:hover { background:var(--bolha); } .v3-item.sel { background:var(--acento-claro); color:var(--acento); font-weight:600; }
.v3-item .cor { width:10px; height:10px; border-radius:3px; flex:0 0 10px; }
.v3-item .nome { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.v3-item .olho { border:0; background:transparent; color:var(--suave); cursor:pointer; padding:0 2px; font-size:13px; }
.v3-item.oculto .nome { opacity:.45; text-decoration:line-through; }
.v3-teste { position:absolute; left:50%; top:12px; transform:translateX(-50%); z-index:7; display:none; text-align:center;
  background:var(--cartao); border:1.5px solid var(--acento); border-radius:14px; padding:8px 14px; font-size:13.5px; box-shadow:0 6px 20px rgba(0,0,0,.15); }
.v3-teste.on { display:block; } .v3-teste b { color:var(--acento); }
.v3-teste .res { font-size:12.5px; margin-top:3px; min-height:17px; } .v3-teste .ok { color:#2E7D4F; } .v3-teste .mal { color:#B3261E; }
`;
const ICONES = {
  repor: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
  rodar: '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-9-9c2.5 0 4.8 1 6.4 2.6L21 8"/><path d="M21 3v5h-5"/></svg>',
  etiquetas: '<svg viewBox="0 0 24 24"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/></svg>',
  corte: '<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/></svg>',
  explodir: '<svg viewBox="0 0 24 24"><path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l3 3M16 16l3 3M5 19l3-3M16 8l3-3"/></svg>',
  capa: '<svg viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3.5"/></svg>',
  glb: '<svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>',
  ecra: '<svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>',
  lista: '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  teste: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/></svg>',
};

let S = null; // estado do visualizador

export async function iniciar(raiz, args, Streamlit, escuro) {
  const estilo = document.createElement("style");
  estilo.textContent = CSS;
  document.head.appendChild(estilo);
  const altura = args.altura || 520;
  raiz.innerHTML = `<div class="v3-caixa" style="height:${altura}px">
      <div class="v3-dica">Arrasta para rodar · roda do rato para aproximar · clica numa peça para a selecionar</div>
      <div class="v3-barra"></div><div class="v3-painel"></div><div class="v3-tip"></div><div class="v3-aviso"></div>
      <div class="v3-info"></div><div class="v3-lista"></div><div class="v3-teste"></div></div>`;
  const caixa = raiz.querySelector(".v3-caixa");
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  caixa.prepend(renderer.domElement);
  const etiquetas = new CSS2DRenderer();
  etiquetas.domElement.style.cssText = "position:absolute;top:0;left:0;pointer-events:none;z-index:2";
  caixa.appendChild(etiquetas.domElement);

  const cena = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  cena.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
  cena.add(new THREE.HemisphereLight(0xffffff, 0x8a8170, 0.55));
  const sol = new THREE.DirectionalLight(0xffffff, 1.3);
  sol.position.set(4, 7, 5);
  cena.add(sol);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 500);
  camera.position.set(6, 4, 8);
  const controlos = new OrbitControls(camera, renderer.domElement);
  controlos.enableDamping = true;
  controlos.dampingFactor = 0.08;
  controlos.autoRotateSpeed = 1.6;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  sol.castShadow = true;
  sol.shadow.mapSize.set(1024, 1024);
  sol.shadow.radius = 6;
  const chao = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShadowMaterial({ opacity: 0.16 }));
  chao.rotation.x = -Math.PI / 2;
  chao.receiveShadow = true;
  cena.add(chao);
  const grupo = new THREE.Group();
  cena.add(grupo);
  const plano = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);

  S = { raiz, caixa, renderer, etiquetas, cena, camera, controlos, grupo, plano, Streamlit, args: null, malhas: [], chao, sol,
        ocultas: new Set(), isolar: false, raiox: 1, teste: null, voo: null,
        chaveModelo: null, chaveGlb: null, chaveEnquadrar: null, cenaAplicada: null, selecionada: null,
        local: { etiquetas: true, rodar: false, corte: false, eixo: "y", pos: 0, inverter: false, explodir: 0 },
        centro: new THREE.Vector3(), raioModelo: 3, glbRaiz: null, escuro };
  // acesso para diagnóstico e testes automáticos (desenhar uma imagem mesmo com o separador do browser escondido)
  window.__mondego3d = { estado: () => S, desenhar: () => { controlos.update(); renderer.render(cena, camera); etiquetas.render(cena, camera); arrumarEtiquetas(true); } };
  montarBarra();
  ligarRato();
  new ResizeObserver(redimensionar).observe(caixa);
  redimensionar();
  renderer.setAnimationLoop(() => {
    if (S.voo) {
      const t = Math.min((performance.now() - S.voo.t0) / 650, 1), k = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      controlos.target.lerpVectors(S.voo.alvo0, S.voo.alvo1, k);
      camera.position.lerpVectors(S.voo.cam0, S.voo.cam1, k);
      if (t >= 1) S.voo = null;
    }
    controlos.update();
    renderer.render(cena, camera);
    etiquetas.render(cena, camera);
    arrumarEtiquetas();
  });
  Streamlit.altura(altura + 2);
  await atualizar(args, escuro);
}

export async function atualizar(args, escuro) {
  S.args = args;
  S.escuro = escuro;
  const altura = args.altura || 520;
  if (S.caixa.style.height !== altura + "px") { S.caixa.style.height = altura + "px"; S.Streamlit.altura(altura + 2); }
  const modelo = args.modelo || { partes: [] };
  if (args.blender && args.blender !== S.chaveBlender) {          // malhas feitas pelo Blender
    S.chaveBlender = args.blender;
    try { S.blender = await carregarBlender(args.blender); } catch (e) { console.warn("GLB do Blender", e); S.blender = null; }
    S.chaveModelo = null;
  } else if (!args.blender && S.blender) { S.blender = null; S.chaveBlender = null; S.chaveModelo = null; }
  S.idsBlender = new Set(args.blender_ids || []);
  const chave = JSON.stringify(modelo) + "|" + (args.glb ? args.glb.length : 0) + "|" + (args.blender || "") + (args.blender_ids || []).join(",");
  if (args.glb && args.glb_id !== S.chaveGlb) await carregarGlb(args.glb, args.glb_id);
  if (!args.glb && S.glbRaiz) { S.grupo.remove(S.glbRaiz); S.glbRaiz = null; S.chaveGlb = null; }
  if (chave !== S.chaveModelo) {
    S.chaveModelo = chave;
    construirPartes(modelo);
    aplicarAjustesGlb(modelo.ajustes_glb || {});
    calcularCentro();
    desenharLista();
  }
  const cenaTxt = JSON.stringify(modelo.cena || {});
  if (cenaTxt !== S.cenaAplicada) { // a IA (ou um ficheiro) mudou a vista: aplicar
    S.cenaAplicada = cenaTxt;
    const c = modelo.cena || {};
    Object.assign(S.local, { etiquetas: c.etiquetas !== false, rodar: !!c.rodar, explodir: c.explodir || 0,
                             corte: !!(c.corte && c.corte.ativo), eixo: (c.corte && c.corte.eixo) || "y",
                             pos: (c.corte && c.corte.posicao) || 0, inverter: !!(c.corte && c.corte.inverter) });
    sincronizarPainel();
  }
  if ((args.enquadrar || "") !== S.chaveEnquadrar) { S.chaveEnquadrar = args.enquadrar || ""; enquadrar(); }
  // só a app manda na seleção quando a envia (no 3D Studio); noutras páginas a seleção fica no visualizador
  if ("selecionada" in args) S.selecionada = args.selecionada || null;
  S.raiz.querySelector('[data-id="capa"]').style.display = args.capa === false ? "none" : "";
  aplicarVista();
  S.raiz.querySelector(".v3-aviso").textContent = S.malhas.length ? "" : "Sem peças para mostrar.";
}

// ----------------------------------------------------------------------------- construção das peças
function geometria(p) {
  const d = p.dims || {};
  switch (p.tipo) {
    case "esfera": return new THREE.SphereGeometry(d.raio || 0.5, 48, 32);
    case "caixa": return new THREE.BoxGeometry(d.largura || 1, d.altura || 1, d.profundidade || 1);
    case "cilindro": return new THREE.CylinderGeometry(d.raio_topo ?? 0.3, d.raio_base ?? 0.3, comprimentoDeAte(d) || d.altura || 1, 40, 1);
    case "cone": return new THREE.ConeGeometry(d.raio || 0.4, comprimentoDeAte(d) || d.altura || 1, 40);
    case "toro": return new THREE.TorusGeometry(d.raio || 0.8, d.raio_tubo || 0.2, 24, 72, d.arco || Math.PI * 2);
    case "capsula": return new THREE.CapsuleGeometry(d.raio || 0.3, Math.max(0.001, (comprimentoDeAte(d) || d.comprimento || 1) - (d.de ? 2 * (d.raio || 0.3) : 0)), 10, 24);
    case "tubo": {
      const pts = (d.pontos || []).map((q) => new THREE.Vector3(q[0], q[1], q[2]));
      const curva = new THREE.CatmullRomCurve3(pts, !!d.fechado, "centripetal");
      if (Array.isArray(d.raios) && d.raios.length >= 2) return tuboVariavel(curva, d.raios, Math.max(64, pts.length * 24), !!d.fechado);
      return new THREE.TubeGeometry(curva, Math.max(48, pts.length * 20), d.raio || 0.1, 18, !!d.fechado);
    }
    case "organico": {
      const g = new THREE.IcosahedronGeometry(d.raio || 0.5, 5), pos = g.attributes.position, v = new THREE.Vector3();
      const irr = d.irregularidade ?? 0.15, freq = d.frequencia ?? 2.2, sem = d.semente ?? 1;
      for (let i = 0; i < pos.count; i++) {
        v.fromBufferAttribute(pos, i);
        const n = ruido(v.x * freq + sem, v.y * freq - sem, v.z * freq + sem * 0.7);
        v.multiplyScalar(1 + irr * n);
        pos.setXYZ(i, v.x, v.y, v.z);
      }
      g.computeVertexNormals();
      return g;
    }
    case "extrusao": {
      const forma = new THREE.Shape((d.forma || [[0, 0], [1, 0], [0.5, 1]]).map((q) => new THREE.Vector2(q[0], q[1])));
      const g = new THREE.ExtrudeGeometry(forma, { depth: d.profundidade || 0.2, bevelEnabled: true, bevelSize: Math.min(0.05, (d.profundidade || 0.2) / 3),
                                                   bevelThickness: Math.min(0.05, (d.profundidade || 0.2) / 3), bevelSegments: 3, curveSegments: 24 });
      g.center();
      return g;
    }
    case "torno": return new THREE.LatheGeometry((d.perfil || []).map((q) => new THREE.Vector2(q[0], q[1])), 72);
    case "superficie": {
      const g = new THREE.PlaneGeometry(d.largura || 6, d.profundidade || 6, (d.nx || 2) - 1, (d.ny || 2) - 1);
      g.rotateX(-Math.PI / 2);
      const pos = g.attributes.position, alt = d.alturas || [];
      let min = Infinity, max = -Infinity;
      for (let i = 0; i < pos.count; i++) { const z = alt[i] || 0; pos.setY(i, z); min = Math.min(min, z); max = Math.max(max, z); }
      if (d.cores_por_altura) {
        const cores = [], c = new THREE.Color();
        for (let i = 0; i < pos.count; i++) {
          const t = max > min ? (pos.getY(i) - min) / (max - min) : 0.5;
          c.setHSL(0.62 - 0.62 * t, 0.62, 0.52); // azul (baixo) → vermelho (alto)
          cores.push(c.r, c.g, c.b);
        }
        g.setAttribute("color", new THREE.Float32BufferAttribute(cores, 3));
      }
      g.computeVertexNormals();
      return g;
    }
  }
  return new THREE.SphereGeometry(0.3, 16, 12);
}

// ruído suave (soma de senos com fases diferentes): dá formas naturais e irregulares a órgãos, células, rochas…
function ruido(x, y, z) {
  return (Math.sin(x * 1.7 + Math.cos(y * 1.3)) * 0.5 + Math.sin(y * 2.1 + Math.cos(z * 1.9)) * 0.3 +
          Math.sin(z * 2.7 + Math.cos(x * 2.3)) * 0.2);
}

// tubo cuja espessura muda ao longo da curva (vasos que afunilam, raízes, ramos, nervos)
function tuboVariavel(curva, raios, segmentos, fechado) {
  const radial = 18, frames = curva.computeFrenetFrames(segmentos, fechado), pos = [], ind = [], p = new THREE.Vector3();
  const raio = (t) => { const x = t * (raios.length - 1), i = Math.min(Math.floor(x), raios.length - 2); return raios[i] + (raios[i + 1] - raios[i]) * (x - i); };
  for (let i = 0; i <= segmentos; i++) {
    const t = i / segmentos, c = curva.getPointAt(t), r = raio(t), N = frames.normals[i], B = frames.binormals[i];
    for (let j = 0; j <= radial; j++) {
      const a = (j / radial) * Math.PI * 2, s = Math.sin(a), co = -Math.cos(a);
      p.set(c.x + r * (co * N.x + s * B.x), c.y + r * (co * N.y + s * B.y), c.z + r * (co * N.z + s * B.z));
      pos.push(p.x, p.y, p.z);
    }
  }
  for (let i = 1; i <= segmentos; i++) for (let j = 1; j <= radial; j++) {
    const a = (radial + 1) * (i - 1) + (j - 1), b = (radial + 1) * i + (j - 1), c = (radial + 1) * i + j, e = (radial + 1) * (i - 1) + j;
    ind.push(a, b, e, b, c, e);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(ind);
  g.computeVertexNormals();
  return g;
}

function comprimentoDeAte(d) {
  if (!d.de || !d.ate) return 0;
  return new THREE.Vector3(...d.ate).distanceTo(new THREE.Vector3(...d.de));
}

function material(p) {
  const m = p.material || {}, tipo = m.tipo || "padrao", op = m.opacidade ?? 1;
  const cor = new THREE.Color(p.cor || "#C9C2B4");
  const base = { color: cor, side: (p.tipo === "torno" || p.tipo === "superficie" || op < 1) ? THREE.DoubleSide : THREE.FrontSide };
  if (p.tipo === "superficie" && p.dims && p.dims.cores_por_altura) { base.vertexColors = true; base.color = new THREE.Color("#ffffff"); }
  let mat;
  if (tipo === "brilhante") mat = new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.28, metalness: 0.02, clearcoat: 0.7, clearcoatRoughness: 0.2 });
  else if (tipo === "mate") mat = new THREE.MeshStandardMaterial({ ...base, roughness: 0.95, metalness: 0 });
  else if (tipo === "metal") mat = new THREE.MeshStandardMaterial({ ...base, roughness: 0.28, metalness: 0.92 });
  else if (tipo === "vidro") mat = new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.08, metalness: 0, clearcoat: 1, transparent: true, opacity: Math.min(op, 0.4), depthWrite: false });
  else if (tipo === "tecido") mat = new THREE.MeshPhysicalMaterial({ ...base, roughness: 0.62, metalness: 0, sheen: 0.6, sheenRoughness: 0.5,
                                                                       sheenColor: cor.clone().lerp(new THREE.Color("#ffffff"), 0.4), clearcoat: 0.15 });
  else if (tipo === "emissivo") mat = new THREE.MeshStandardMaterial({ ...base, roughness: 0.5, emissive: cor, emissiveIntensity: 0.65 });
  else mat = new THREE.MeshStandardMaterial({ ...base, roughness: 0.55, metalness: 0.04 });
  if (op < 1 && tipo !== "vidro") { mat.transparent = true; mat.opacity = op; mat.depthWrite = false; }
  return mat;
}

// leitor de GLB com descompressão Draco (os ficheiros do Blender vêm comprimidos: muito mais leves)
function leitorGltf() {
  if (!S.leitor) {
    const draco = new DRACOLoader();
    draco.setDecoderPath("https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/draco/gltf/");
    S.leitor = new GLTFLoader().setDRACOLoader(draco);
  }
  return S.leitor;
}

async function carregarBlender(url) {
  const resposta = await fetch(url);
  if (!resposta.ok) throw new Error("HTTP " + resposta.status);
  const buffer = await resposta.arrayBuffer();
  const gltf = await new Promise((ok, falha) => leitorGltf().parse(buffer, "", ok, falha));
  const mapa = new Map();
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const g = o.geometry.clone();
    g.applyMatrix4(o.matrixWorld);
    mapa.set(o.name, { geometria: g, material: Array.isArray(o.material) ? o.material[0] : o.material });
  });
  return mapa;
}

// material do Blender com a cor, a opacidade e o brilho da peça (editáveis sem voltar ao Blender)
function materialBlender(base, p) {
  const m = base.clone(), mt = p.material || {}, tipo = mt.tipo || "padrao", op = mt.opacidade ?? 1;
  const cor = new THREE.Color(p.cor || "#C9C2B4");
  if (m.color) m.color.copy(cor);
  if (tipo === "emissivo" && m.emissive) { m.emissive.copy(cor); m.emissiveIntensity = Math.max(m.emissiveIntensity || 1, 1.2); }
  if (tipo === "tecido" && m.sheenColor) m.sheenColor.copy(cor.clone().lerp(new THREE.Color("#ffffff"), 0.4));
  if (p.tipo === "torno" || op < 1) m.side = THREE.DoubleSide;
  if (tipo === "vidro" && !(m.transmission > 0)) { m.transparent = true; m.opacity = Math.min(op, 0.55); m.depthWrite = false; }
  else if (op < 1) { m.transparent = true; m.opacity = op; m.depthWrite = false; }  // o vidro do Blender já é transparente de verdade (transmissão)
  return m;
}

function limparPartes() {
  for (const m of S.malhas.filter((m) => !m.userData.glb)) {
    S.grupo.remove(m);
    m.geometry.dispose();
    m.material.dispose();
    if (m.userData.etiqueta) m.remove(m.userData.etiqueta);
  }
  S.malhas = S.malhas.filter((m) => m.userData.glb);
}

function construirPartes(modelo) {
  limparPartes();
  for (const p of modelo.partes || []) {
    let malha;
    const bl = S.blender && S.idsBlender && S.idsBlender.has(p.id) ? S.blender.get(p.id) : null;
    try { malha = bl ? new THREE.Mesh(bl.geometria.clone(), materialBlender(bl.material, p)) : new THREE.Mesh(geometria(p), material(p)); }
    catch (e) { console.warn("peça ignorada", p.id, e); continue; }
    const d = p.dims || {};
    if (d.de && d.ate && ["cilindro", "cone", "capsula"].includes(p.tipo)) {
      const a = new THREE.Vector3(...d.de), b = new THREE.Vector3(...d.ate);
      malha.position.copy(a).add(b).multiplyScalar(0.5);
      malha.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    } else {
      malha.position.set(...(p.posicao || [0, 0, 0]));
      malha.rotation.set(...(p.rotacao || [0, 0, 0]).map((g) => (g * Math.PI) / 180));
      malha.scale.set(...(p.escala || [1, 1, 1]));
    }
    malha.visible = p.visivel !== false;
    malha.castShadow = true;
    malha.userData = { id: p.id, nome: p.nome, etiquetaTxt: p.etiqueta || "", descricao: p.descricao || "", grupo: p.grupo || "",
                       funcao: p.funcao || "", curiosidade: p.curiosidade || "", visivelModelo: p.visivel !== false, cor: p.cor || "#C9C2B4",
                       opacidadeBase: malha.material.opacity ?? 1,
                       base: malha.position.clone(), corOriginal: malha.material.emissive ? malha.material.emissive.clone() : null,
                       intensidadeOriginal: malha.material.emissiveIntensity || 0 };
    criarEtiqueta(malha);
    S.grupo.add(malha);
    S.malhas.push(malha);
  }
}

// Etiquetas sem se sobreporem: as das peças maiores (e a da peça selecionada) ficam; as que chocam com outra já
// colocada escondem-se até haver espaço (ao rodar ou aproximar voltam a aparecer).
function arrumarEtiquetas(forcar = false) {
  const agora = performance.now();
  if (!forcar && agora - (S.ultArrumar || 0) < 120) return;
  S.ultArrumar = agora;
  const lista = S.malhas.filter((m) => m.userData.etiqueta && m.userData.etiqueta.visible);
  lista.sort((a, b) => (b.userData.id === S.selecionada) - (a.userData.id === S.selecionada) || (b.userData.tamanho || 0) - (a.userData.tamanho || 0));
  const colocadas = [];
  for (const m of lista) {
    const el = m.userData.etiqueta.element, r = el.getBoundingClientRect();
    if (!r.width) continue;
    const choca = colocadas.some((o) => r.left < o.right + 4 && r.right > o.left - 4 && r.top < o.bottom + 2 && r.bottom > o.top - 2);
    el.style.visibility = choca ? "hidden" : "";
    if (!choca) colocadas.push(r);
  }
}

function criarEtiqueta(malha) {
  if (!malha.userData.etiquetaTxt) return;
  const div = document.createElement("div");
  div.className = "v3-etq";
  div.textContent = malha.userData.etiquetaTxt;
  const obj = new CSS2DObject(div);
  malha.geometry.computeBoundingBox();
  const caixa = malha.geometry.boundingBox;
  malha.userData.tamanho = caixa.getSize(new THREE.Vector3()).multiply(malha.scale).length();
  obj.position.set(0, caixa.max.y * 0.92, 0);
  malha.add(obj);
  malha.userData.etiqueta = obj;
}

async function carregarGlb(dataUrl, glbId) {
  S.chaveGlb = glbId;
  if (S.glbRaiz) { S.grupo.remove(S.glbRaiz); S.malhas = S.malhas.filter((m) => !m.userData.glb); }
  const resposta = await fetch(dataUrl);
  const buffer = await resposta.arrayBuffer();
  const gltf = await new Promise((ok, falha) => leitorGltf().parse(buffer, "", ok, falha));
  const raizGlb = gltf.scene;
  // centrar e ajustar o tamanho (cabe numa caixa de 6 unidades)
  const caixa = new THREE.Box3().setFromObject(raizGlb);
  const tam = caixa.getSize(new THREE.Vector3()), centro = caixa.getCenter(new THREE.Vector3());
  const k = 6 / Math.max(tam.x, tam.y, tam.z, 1e-6);
  raizGlb.scale.setScalar(k);
  raizGlb.position.copy(centro).multiplyScalar(-k);
  const lista = [], usados = new Set();
  let n = 0;
  raizGlb.traverse((o) => {
    if (!o.isMesh) return;
    n += 1;
    let id = "glb:" + (o.name || "malha_" + n);
    while (usados.has(id)) id += "_" + n;
    usados.add(id);
    o.material = Array.isArray(o.material) ? o.material.map((m) => m.clone()) : o.material.clone();
    const mat = Array.isArray(o.material) ? o.material[0] : o.material;
    o.userData = { id, nome: o.name || "Malha " + n, glb: true, etiquetaTxt: "", descricao: "", base: o.position.clone(),
                   corInicial: mat.color ? mat.color.clone() : null, escalaInicial: o.scale.clone(),
                   corOriginal: mat.emissive ? mat.emissive.clone() : null, intensidadeOriginal: mat.emissiveIntensity || 0 };
    S.malhas.push(o);
    lista.push({ id, nome: o.userData.nome });
  });
  S.glbRaiz = raizGlb;
  S.grupo.add(raizGlb);
  if (S.args && S.args.pedir_malhas) S.Streamlit.valor({ evento: "malhas", lista, t: Date.now() });
}

function aplicarAjustesGlb(ajustes) {
  for (const o of S.malhas.filter((m) => m.userData.glb)) {
    const aj = ajustes[o.userData.id] || {};
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (m.color) m.color.copy(aj.cor ? new THREE.Color(aj.cor) : o.userData.corInicial || m.color);
      const op = aj.material && aj.material.opacidade;
      if (op !== undefined) { m.transparent = op < 1; m.opacity = op; m.depthWrite = op >= 1; }
    }
    o.visible = aj.visivel !== false;
    o.userData.visivelModelo = aj.visivel !== false;
    o.userData.opacidadeBase = (aj.material && aj.material.opacidade) ?? 1;
    o.userData.cor = aj.cor || (o.userData.corInicial ? "#" + o.userData.corInicial.getHexString() : "#C9C2B4");
    o.castShadow = true;
    o.scale.copy(o.userData.escalaInicial).multiplyScalar(aj.escala || 1);
    if (o.userData.etiqueta) { o.remove(o.userData.etiqueta); o.userData.etiqueta = null; }
    o.userData.etiquetaTxt = aj.etiqueta || "";
    o.userData.descricao = aj.descricao || "";
    criarEtiqueta(o);
  }
}

function calcularCentro() {
  const caixa = new THREE.Box3();
  for (const m of S.malhas) if (m.visible) caixa.expandByObject(m);
  if (caixa.isEmpty()) { S.centro.set(0, 0, 0); S.raioModelo = 3; return; }
  caixa.getCenter(S.centro);
  S.raioModelo = Math.max(caixa.getSize(new THREE.Vector3()).length() / 2, 0.5);
  S.chao.position.set(S.centro.x, caixa.min.y - 0.02, S.centro.z);
  S.chao.scale.setScalar(S.raioModelo * 6);
  S.sol.position.set(S.centro.x + S.raioModelo * 1.5, S.centro.y + S.raioModelo * 3, S.centro.z + S.raioModelo * 2);
  S.sol.target.position.copy(S.centro);
  S.cena.add(S.sol.target);
  const cam = S.sol.shadow.camera, r = S.raioModelo * 2;
  Object.assign(cam, { left: -r, right: r, top: r, bottom: -r, near: 0.1, far: S.raioModelo * 10 });
  cam.updateProjectionMatrix();
  for (const m of S.malhas) {
    if (m.userData.glb) continue;
    const c = new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3());
    m.userData.direcao = c.sub(S.centro);
  }
}

function enquadrar() {
  const r = S.raioModelo;
  const dist = r / Math.sin((S.camera.fov * Math.PI) / 360) * 1.15;
  S.camera.position.copy(S.centro).add(new THREE.Vector3(0.55, 0.35, 1).normalize().multiplyScalar(dist));
  S.camera.near = Math.max(dist / 200, 0.005);
  S.camera.far = dist * 50;
  S.camera.updateProjectionMatrix();
  S.controlos.target.copy(S.centro);
  S.controlos.update();
}

// ----------------------------------------------------------------------------- vista: corte, explodir, etiquetas, seleção
function aplicarVista() {
  const L = S.local;
  S.controlos.autoRotate = L.rodar;
  // vista explodida: cada peça afasta-se do centro na sua direção
  for (const m of S.malhas) {
    if (m.userData.glb || !m.userData.direcao) continue;
    m.position.copy(m.userData.base).addScaledVector(m.userData.direcao, L.explodir * 1.3);
  }
  // corte transversal (plano de recorte)
  if (L.corte) {
    const normal = { x: new THREE.Vector3(-1, 0, 0), y: new THREE.Vector3(0, -1, 0), z: new THREE.Vector3(0, 0, -1) }[L.eixo];
    if (L.inverter) normal.negate();
    S.plano.normal.copy(normal);
    const c = S.centro[L.eixo] + L.pos;
    S.plano.constant = L.inverter ? -c : c;
    S.renderer.clippingPlanes = [S.plano];
  } else {
    S.renderer.clippingPlanes = [];
  }
  // peças escondidas no painel, isolar a selecionada e raio-X (as outras ficam transparentes)
  for (const m of S.malhas) {
    const base = m.userData.visivelModelo !== false;
    m.visible = base && !S.ocultas.has(m.userData.id) && !(S.isolar && S.selecionada && m.userData.id !== S.selecionada);
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    const alvo = S.selecionada && m.userData.id !== S.selecionada ? Math.min(S.raiox, m.userData.opacidadeBase ?? 1) : (m.userData.opacidadeBase ?? 1);
    for (const mat of mats) {
      if (mat.opacity === alvo && (alvo < 1) === mat.transparent) continue;
      mat.opacity = alvo; mat.transparent = alvo < 1; mat.depthWrite = alvo >= 1; mat.needsUpdate = true;
    }
  }
  // quadro com o nome, o sistema, a explicação, a função e uma curiosidade da peça selecionada
  const info = S.raiz.querySelector(".v3-info"), sel = S.malhas.find((m) => m.userData.id === S.selecionada);
  if (sel && !S.teste) {
    const u = sel.userData;
    info.innerHTML = "";
    const add = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; e.textContent = txt; info.appendChild(e); return e; };
    if (u.grupo) add("span", "g", u.grupo);
    add("b", "", u.nome);
    if (u.descricao) add("div", "", u.descricao);
    if (u.funcao) { const d = add("div", "s", ""); d.innerHTML = "<em>Função:</em> "; d.appendChild(document.createTextNode(u.funcao)); }
    if (u.curiosidade) { const d = add("div", "s", ""); d.innerHTML = "<em>Sabias que…</em> "; d.appendChild(document.createTextNode(u.curiosidade)); }
    const acoes = add("div", "acoes", "");
    const bt = (txt, on, f) => { const b = document.createElement("button"); b.className = "v3-mini" + (on ? " on" : ""); b.textContent = txt; b.onclick = f; acoes.appendChild(b); };
    bt(S.isolar ? "Mostrar tudo" : "Isolar", S.isolar, () => { S.isolar = !S.isolar; aplicarVista(); });
    bt("Centrar", false, () => voarPara(sel));
    bt("Esconder", false, () => { S.ocultas.add(u.id); S.selecionada = null; S.isolar = false; aplicarVista(); desenharLista(); });
    info.style.display = "block";
  } else {
    info.style.display = "none";
  }
  S.raiz.querySelectorAll(".v3-item").forEach((el) => el.classList.toggle("sel", el.dataset.id === S.selecionada));
  // etiquetas e seleção
  const corSel = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue("--acento").trim() || "#17798A");
  for (const m of S.malhas) {
    if (m.userData.etiqueta) {
      m.userData.etiqueta.visible = L.etiquetas && m.visible;
      m.userData.etiqueta.element.classList.toggle("sel", m.userData.id === S.selecionada);
    }
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    for (const mat of mats) {
      if (!mat.emissive) continue;
      if (m.userData.id === S.selecionada) { mat.emissive.copy(corSel); mat.emissiveIntensity = 0.45; }
      else if (m.userData.corOriginal) { mat.emissive.copy(m.userData.corOriginal); mat.emissiveIntensity = m.userData.intensidadeOriginal; }
    }
  }
}

function montarBarra() {
  const barra = S.raiz.querySelector(".v3-barra");
  const botoes = [
    ["repor", "Repor a vista", () => enquadrar()],
    ["rodar", "Rodar automaticamente", () => { S.local.rodar = !S.local.rodar; sincronizarPainel(); aplicarVista(); }],
    ["etiquetas", "Mostrar ou esconder etiquetas", () => { S.local.etiquetas = !S.local.etiquetas; sincronizarPainel(); aplicarVista(); }],
    ["corte", "Corte transversal", () => { S.local.corte = !S.local.corte; sincronizarPainel(); aplicarVista(); }],
    ["explodir", "Vista explodida (separar as peças)", () => { S.local.explodir = S.local.explodir > 0 ? 0 : 0.6; sincronizarPainel(); aplicarVista(); }],
    ["lista", "Estruturas: lista, procurar, esconder, raio-X", () => { S.raiz.querySelector(".v3-lista").classList.toggle("on"); sincronizarBotoes(); }],
    ["teste", "Testa-te: encontra as estruturas no modelo", alternarTeste],
    ["capa", "Usar esta vista como imagem de capa", capturarCapa],
    ["glb", "Descarregar o modelo 3D (.glb)", descarregarGlb],
    ["ecra", "Ecrã inteiro", () => { const c = S.caixa; (document.fullscreenElement ? document.exitFullscreen() : c.requestFullscreen?.()); }],
  ];
  for (const [id, titulo, acao] of botoes) {
    const b = document.createElement("button");
    b.className = "v3-bt";
    b.dataset.id = id;
    b.title = titulo;
    b.setAttribute("aria-label", titulo);
    b.innerHTML = ICONES[id];
    b.addEventListener("click", acao);
    barra.appendChild(b);
  }
  const painel = S.raiz.querySelector(".v3-painel");
  painel.innerHTML = `
    <label title="Separar as peças"><span>Explodir</span><input type="range" min="0" max="1" step="0.02" data-c="explodir"></label>
    <label class="v3-corte" title="Plano de corte"><span>Corte</span>
      <select data-c="eixo"><option value="x">X</option><option value="y">Y</option><option value="z">Z</option></select>
      <input type="range" min="-1" max="1" step="0.01" data-c="pos"></label>`;
  painel.querySelector('[data-c="explodir"]').addEventListener("input", (e) => { S.local.explodir = +e.target.value; aplicarVista(); sincronizarBotoes(); });
  painel.querySelector('[data-c="eixo"]').addEventListener("change", (e) => { S.local.eixo = e.target.value; S.local.corte = true; sincronizarPainel(); aplicarVista(); });
  painel.querySelector('[data-c="pos"]').addEventListener("input", (e) => { S.local.pos = +e.target.value * S.raioModelo; S.local.corte = true; aplicarVista(); sincronizarBotoes(); });
}

function sincronizarBotoes() {
  const L = S.local;
  const estado = { rodar: L.rodar, etiquetas: L.etiquetas, corte: L.corte, explodir: L.explodir > 0,
                   lista: S.raiz.querySelector(".v3-lista").classList.contains("on"), teste: !!S.teste };
  S.raiz.querySelectorAll(".v3-bt").forEach((b) => b.classList.toggle("ativo", !!estado[b.dataset.id]));
}

function sincronizarPainel() {
  const p = S.raiz.querySelector(".v3-painel");
  p.querySelector('[data-c="explodir"]').value = S.local.explodir;
  p.querySelector('[data-c="eixo"]').value = S.local.eixo;
  p.querySelector('[data-c="pos"]').value = S.raioModelo ? S.local.pos / S.raioModelo : 0;
  p.querySelector(".v3-corte").style.opacity = S.local.corte ? "1" : "0.6";
  sincronizarBotoes();
}

// ----------------------------------------------------------------------------- rato: selecionar e passar por cima
function ligarRato() {
  const el = S.renderer.domElement, tip = S.raiz.querySelector(".v3-tip");
  const ray = new THREE.Raycaster(), ponteiro = new THREE.Vector2();
  let inicio = null;
  const apanhar = (ev) => {
    const r = el.getBoundingClientRect();
    ponteiro.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ponteiro, S.camera);
    const alvos = S.malhas.filter((m) => m.visible);
    const hits = ray.intersectObjects(alvos, false).filter((h) => !S.renderer.clippingPlanes.length || S.plano.distanceToPoint(h.point) >= 0);
    return hits.length ? hits[0].object : null;
  };
  el.addEventListener("pointerdown", (ev) => { inicio = [ev.clientX, ev.clientY]; });
  el.addEventListener("pointerup", (ev) => {
    if (!inicio || Math.hypot(ev.clientX - inicio[0], ev.clientY - inicio[1]) > 5) return;
    const alvo = apanhar(ev);
    const id = alvo ? alvo.userData.id : null;
    if (S.teste) { if (alvo) responderTeste(alvo); return; }
    S.selecionada = id === S.selecionada ? null : id;
    aplicarVista();
    if (S.args.enviar_selecao !== false)
      S.Streamlit.valor({ evento: "selecao", id: S.selecionada, nome: alvo ? alvo.userData.nome : null, t: Date.now() });
  });
  el.addEventListener("pointermove", (ev) => {
    if (ev.buttons) { tip.style.display = "none"; return; }
    const alvo = apanhar(ev);
    if (!alvo) { tip.style.display = "none"; el.style.cursor = "grab"; return; }
    const r = S.caixa.getBoundingClientRect();
    tip.textContent = alvo.userData.nome;
    tip.style.left = ev.clientX - r.left + "px";
    tip.style.top = ev.clientY - r.top + "px";
    tip.style.display = "block";
    el.style.cursor = "pointer";
  });
  el.addEventListener("pointerleave", () => { tip.style.display = "none"; });
}

function redimensionar() {
  const w = S.caixa.clientWidth || 600, h = S.caixa.clientHeight || 400;
  S.renderer.setSize(w, h, false);
  S.renderer.domElement.style.width = w + "px";
  S.renderer.domElement.style.height = h + "px";
  S.etiquetas.setSize(w, h);
  S.camera.aspect = w / h;
  S.camera.updateProjectionMatrix();
}

// ----------------------------------------------------------------------------- capa e exportação
function capturarCapa() {
  S.renderer.render(S.cena, S.camera);
  const origem = S.renderer.domElement;
  const tela = document.createElement("canvas");
  tela.width = 800; tela.height = 500;
  const ctx = tela.getContext("2d");
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--fundo").trim() || "#F6F8F7";
  ctx.fillRect(0, 0, tela.width, tela.height);
  const k = Math.max(tela.width / origem.width, tela.height / origem.height);
  const w = origem.width * k, h = origem.height * k;
  ctx.drawImage(origem, (tela.width - w) / 2, (tela.height - h) / 2, w, h);
  const url = tela.toDataURL("image/jpeg", 0.86);
  S.Streamlit.valor({ evento: "capa", imagem: url, t: Date.now() });
  const b = S.raiz.querySelector('[data-id="capa"]');
  b.classList.add("ativo");
  setTimeout(() => b.classList.remove("ativo"), 900);
}

function descarregarGlb() {
  const exportar = new THREE.Group();
  for (const m of S.malhas) {
    if (!m.visible) continue;
    const c = m.clone(false);               // sem filhos (as etiquetas não vão para o ficheiro)
    m.updateWorldMatrix(true, false);
    m.matrixWorld.decompose(c.position, c.quaternion, c.scale);
    exportar.add(c);
  }
  new GLTFExporter().parse(exportar, (resultado) => {
    const blob = new Blob([resultado], { type: "model/gltf-binary" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = ((S.args.modelo && S.args.modelo.titulo) || "modelo").replace(/[^\p{L}\p{N} _-]/gu, "_") + ".glb";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }, (erro) => console.error(erro), { binary: true });
}

// ----------------------------------------------------------------------------- painel de estruturas
function desenharLista() {
  const painel = S.raiz.querySelector(".v3-lista");
  const filtro = (painel.querySelector("input[type=search]") || {}).value || "";
  painel.innerHTML = `<div class="v3-lista-topo"><input type="search" placeholder="Procurar estrutura…">
      <label>Raio-X <input type="range" min="0.05" max="1" step="0.05" value="${S.raiox}"></label>
      <div style="display:flex;gap:6px"><button class="v3-mini" data-l="todas">Mostrar todas</button><button class="v3-mini" data-l="fechar">Fechar</button></div></div>
    <div class="v3-itens"></div>`;
  const procura = painel.querySelector("input[type=search]");
  procura.value = filtro;
  procura.oninput = () => preencherItens(procura.value);
  painel.querySelector("input[type=range]").oninput = (e) => { S.raiox = +e.target.value; aplicarVista(); };
  painel.querySelector('[data-l="todas"]').onclick = () => { S.ocultas.clear(); S.isolar = false; aplicarVista(); preencherItens(procura.value); };
  painel.querySelector('[data-l="fechar"]').onclick = () => { painel.classList.remove("on"); sincronizarBotoes(); };
  preencherItens(filtro);
}

function preencherItens(filtro) {
  const caixa = S.raiz.querySelector(".v3-itens"), f = (filtro || "").toLowerCase();
  const grupos = {};
  for (const m of S.malhas) {
    const u = m.userData;
    if (f && !(u.nome || "").toLowerCase().includes(f) && !(u.grupo || "").toLowerCase().includes(f)) continue;
    (grupos[u.grupo || "Peças"] = grupos[u.grupo || "Peças"] || []).push(m);
  }
  caixa.innerHTML = "";
  for (const [g, lista] of Object.entries(grupos)) {
    const t = document.createElement("div"); t.className = "v3-grupo"; t.textContent = g; caixa.appendChild(t);
    for (const m of lista) {
      const u = m.userData, el = document.createElement("div");
      el.className = "v3-item" + (S.ocultas.has(u.id) ? " oculto" : "") + (u.id === S.selecionada ? " sel" : "");
      el.dataset.id = u.id;
      el.innerHTML = `<span class="cor"></span><span class="nome"></span><button class="olho" title="Esconder/mostrar">${S.ocultas.has(u.id) ? "◌" : "●"}</button>`;
      el.querySelector(".cor").style.background = u.cor || "#C9C2B4";
      el.querySelector(".nome").textContent = u.nome;
      el.querySelector(".olho").onclick = (ev) => { ev.stopPropagation(); S.ocultas.has(u.id) ? S.ocultas.delete(u.id) : S.ocultas.add(u.id); aplicarVista(); preencherItens(filtro); };
      el.onclick = () => { S.selecionada = u.id; S.ocultas.delete(u.id); aplicarVista(); voarPara(m); preencherItens(filtro);
        if (S.args.enviar_selecao !== false) S.Streamlit.valor({ evento: "selecao", id: u.id, nome: u.nome, t: Date.now() }); };
      caixa.appendChild(el);
    }
  }
  if (!caixa.children.length) caixa.innerHTML = '<div class="v3-grupo">Nada encontrado</div>';
}

function voarPara(malha) {
  const caixa = new THREE.Box3().setFromObject(malha);
  if (caixa.isEmpty()) return;
  const centro = caixa.getCenter(new THREE.Vector3()), r = Math.max(caixa.getSize(new THREE.Vector3()).length() / 2, S.raioModelo * 0.25);
  const dir = S.camera.position.clone().sub(S.controlos.target).normalize();
  const dist = r / Math.sin((S.camera.fov * Math.PI) / 360) * 1.4;
  S.voo = { t0: performance.now(), alvo0: S.controlos.target.clone(), alvo1: centro, cam0: S.camera.position.clone(),
            cam1: centro.clone().addScaledVector(dir, dist) };
}

// ----------------------------------------------------------------------------- Testa-te (encontrar estruturas)
function alternarTeste() {
  if (S.teste) { S.teste = null; S.raiz.querySelector(".v3-teste").classList.remove("on"); sincronizarBotoes(); aplicarVista(); return; }
  const candidatas = S.malhas.filter((m) => m.visible && (m.userData.etiquetaTxt || m.userData.grupo || m.userData.descricao));
  const nomes = [...new Map(candidatas.map((m) => [m.userData.nome, m])).values()];
  if (nomes.length < 2) { S.raiz.querySelector(".v3-aviso").textContent = "Este modelo tem poucas estruturas com nome para o Testa-te."; return; }
  S.teste = { lista: nomes.sort(() => Math.random() - 0.5).slice(0, Math.min(10, nomes.length)), pos: 0, certas: 0 };
  S.selecionada = null;
  S.raiz.querySelector(".v3-teste").classList.add("on");
  perguntaTeste();
  sincronizarBotoes();
  aplicarVista();
}

function perguntaTeste(resultado = "") {
  const t = S.teste, caixa = S.raiz.querySelector(".v3-teste");
  if (t.pos >= t.lista.length) {
    caixa.innerHTML = `Acertaste <b>${t.certas} de ${t.lista.length}</b><div class="res"><button class="v3-mini" data-t="outra">Outra vez</button> <button class="v3-mini" data-t="sair">Sair</button></div>`;
    caixa.querySelector('[data-t="outra"]').onclick = () => { S.teste = null; alternarTeste(); };
    caixa.querySelector('[data-t="sair"]').onclick = alternarTeste;
    return;
  }
  caixa.innerHTML = `Pergunta ${t.pos + 1} de ${t.lista.length} · Clica em: <b></b><div class="res"></div>`;
  caixa.querySelector("b").textContent = t.lista[t.pos].userData.nome;
  caixa.querySelector(".res").innerHTML = resultado;
}

function responderTeste(alvo) {
  const t = S.teste, certa = t.lista[t.pos];
  const ok = alvo.userData.nome === certa.userData.nome;
  if (ok) t.certas += 1;
  S.selecionada = certa.userData.id;
  aplicarVista();
  t.pos += 1;
  const esc = (x) => String(x).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
  perguntaTeste(ok ? '<span class="ok">Certo!</span>' : `<span class="mal">Não: isso é «${esc(alvo.userData.nome)}». Está agora destacada a certa.</span>`);
  setTimeout(() => { if (S.teste === t) { S.selecionada = null; aplicarVista(); } }, 1400);
}
