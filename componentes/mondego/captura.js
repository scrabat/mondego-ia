// «Tirar captura de ecrã» no «+» da barra de conversa (no computador, como no Claude).
// O iframe deste componente não tem autorização do Streamlit para captar o ecrã, por isso o pedido é feito pela página
// principal da app (a mesma origem): o clique no botão dá-lhe essa autorização e o browser pergunta o que partilhar
// (ecrã inteiro, uma janela ou um separador). A imagem fica nos anexos da conversa; nada é guardado sem a pessoa enviar.
const C = {};
const ICONE = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" ' +
  'd="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-6v2h3v2H7v-2h3v-2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 2v10h16V6H4z"/></svg>';

export function iniciar(raiz, args, Streamlit) {
  Object.assign(C, { raiz, args, Streamlit });
  raiz.innerHTML = `<style>
    .cp { display:flex; align-items:center; gap:0.65rem; width:100%; box-sizing:border-box; padding:0.5rem 0.55rem;
          border:0; border-radius:8px; background:transparent; color:var(--texto); font:inherit; font-size:15px;
          line-height:1.35; cursor:pointer; text-align:left; transition:background .12s ease; }
    .cp:hover { background:var(--bolha); }
    .cp:focus-visible { outline:2px solid var(--acento); outline-offset:-2px; }
    .cp svg { color:var(--suave); flex:none; }
    .cp[disabled] { opacity:0.6; cursor:progress; }
    .cp-msg { margin:0; padding:0 0.55rem 0.4rem 2.6rem; font-size:12.5px; color:var(--suave); }
  </style>
  <button type="button" class="cp">${ICONE}<span>Tirar captura de ecrã</span></button>
  <p class="cp-msg" role="status" aria-live="polite" hidden></p>`;
  raiz.querySelector(".cp").addEventListener("click", capturar);
  ajustar();
}

export function atualizar(args) { C.args = args; }

function ajustar() { C.Streamlit.altura(C.raiz.scrollHeight); }

function mostrar(texto) {
  const msg = C.raiz.querySelector(".cp-msg");
  msg.textContent = texto; msg.hidden = !texto; ajustar();
}

async function capturar() {
  const botao = C.raiz.querySelector(".cp");
  let md = null;
  try { md = window.parent.navigator.mediaDevices; } catch (e) { md = navigator.mediaDevices; }
  if (!md || !md.getDisplayMedia) {
    mostrar("Este browser não deixa captar o ecrã. Usa «Adicionar ficheiros ou fotos».");
    return;
  }
  botao.disabled = true;
  let stream = null;
  try {
    stream = await md.getDisplayMedia({ video: true, audio: false });
  } catch (e) {
    console.warn("Captura de ecrã:", e && e.name, e && e.message);
    botao.disabled = false;
    mostrar(e && e.name === "NotAllowedError" ? "Captura cancelada." : "Não foi possível captar o ecrã.");
    return;
  }
  try {
    const video = document.createElement("video");
    video.muted = true; video.playsInline = true; video.srcObject = stream;
    await video.play();
    await new Promise((r) => setTimeout(r, 250));  // a primeira imagem do vídeo pode vir em branco
    const w = video.videoWidth || 1280, h = video.videoHeight || 720;
    const escala = Math.min(1, 1920 / Math.max(w, h));
    const tela = document.createElement("canvas");
    tela.width = Math.round(w * escala); tela.height = Math.round(h * escala);
    tela.getContext("2d").drawImage(video, 0, 0, tela.width, tela.height);
    C.Streamlit.valor({ evento: "captura", imagem: tela.toDataURL("image/jpeg", 0.88), t: Date.now() });
    mostrar("Captura adicionada aos anexos.");
  } catch (e) {
    console.warn("Captura de ecrã (imagem):", e && e.name, e && e.message);
    mostrar("Não foi possível captar o ecrã.");
  } finally {
    stream.getTracks().forEach((t) => t.stop());
    botao.disabled = false;
  }
}
