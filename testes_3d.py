"""Testes do 3D Studio (py -3.14 testes_3d.py). Usam uma base de dados temporária."""
import tempfile
from pathlib import Path

import biblioteca3d as b3
import estudio3d as e3
import salas_backend as sb

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


# ---------------------------------------------------------------- formato
cru = {"titulo": "Coração", "partes": [
    {"id": "Ventrículo Esquerdo", "nome": "Ventrículo esquerdo", "tipo": "sphere", "dims": {"raio": 1.2},
     "posicao": [0.4, -0.3, 0], "escala": [0.9, 1.2, 0.9], "cor": "vermelho", "etiqueta": "VE"},
    {"id": "aorta", "nome": "Aorta", "tipo": "tubo", "dims": {"raio": 0.25, "pontos": [[0, 1, 0], [0.3, 2, 0], [-0.4, 2.3, 0]]},
     "cor": "#c33", "material": {"tipo": "brilhante"}},
    {"id": "aorta", "nome": "Duplicado", "tipo": "cilindro", "dims": {"raio_topo": 0.1, "de": [0, 0, 0], "ate": [1, 1, 1]}},
    {"tipo": "dodecaedro"}, {"tipo": "esfera", "posicao": [1e9, "x", None], "dims": {"raio": -4}}]}
m = e3.normalizar_modelo(cru)
ids = [p["id"] for p in m["partes"]]
ok("Peças inválidas ignoradas, ids únicos e normalizados", ids == ["ventriculo_esquerdo", "aorta", "aorta_2", "esfera"])
ok("Sinónimos de tipo e cores por nome", m["partes"][0]["tipo"] == "esfera" and m["partes"][0]["cor"] == "#C0392B"
   and m["partes"][1]["cor"] == "#CC3333")
ok("Limites: posições e dimensões absurdas ficam dentro dos limites", m["partes"][3]["posicao"] == [50.0, 0.0, 0.0]
   and m["partes"][3]["dims"]["raio"] == 0.001)
ok("Cilindro entre dois pontos guarda de/ate", m["partes"][2]["dims"]["de"] == [0, 0, 0] and m["partes"][2]["dims"]["ate"] == [1, 1, 1])
try:
    e3.normalizar_modelo({"partes": [{"tipo": "x"}]})
    ok("Modelo sem peças válidas é recusado", False)
except e3.ErroModelo:
    ok("Modelo sem peças válidas é recusado", True)

# ---------------------------------------------------------------- edição
novo, rel = e3.aplicar_operacoes(m, [
    {"op": "alterar", "id": "aorta", "campos": {"cor": "#2E6DB4", "dims": {"raio": 0.3}}},
    {"op": "adicionar", "parte": {"id": "valvula", "nome": "Válvula aórtica", "tipo": "toro", "dims": {"raio": 0.3, "raio_tubo": 0.05}}},
    {"op": "remover", "id": "esfera"}, {"op": "remover", "id": "nao_existe"},
    {"op": "cena", "campos": {"corte": {"ativo": True, "eixo": "x"}, "explodir": 0.6}}])
ok("Edição muda só o pedido: cor e raio da aorta, pontos mantidos", novo["partes"][1]["cor"] == "#2E6DB4"
   and novo["partes"][1]["dims"]["raio"] == 0.3 and novo["partes"][1]["dims"]["pontos"] == m["partes"][1]["dims"]["pontos"])
ok("O resto do modelo fica igual", novo["partes"][0] == m["partes"][0] and novo["partes"][2] == m["partes"][2])
ok("Adicionar, remover, corte e vista explodida", [p["id"] for p in novo["partes"]][-1] == "valvula"
   and "esfera" not in [p["id"] for p in novo["partes"]] and novo["cena"]["corte"] == {"ativo": True, "eixo": "x", "posicao": 0.0, "inverter": False}
   and novo["cena"]["explodir"] == 0.6 and any("não encontrada" in r for r in rel))
ok("O modelo original não foi modificado", m["partes"][1]["cor"] == "#CC3333" and len(m["partes"]) == 4)
so, rel2 = e3.aplicar_operacoes(m, [{"op": "alterar", "id": "aorta", "campos": {"cor": "#000000"}},
                                    {"op": "alterar", "id": "ventriculo_esquerdo", "campos": {"cor": "#00FF00"}}], apenas="ventriculo_esquerdo")
ok("Com peça selecionada, só essa peça é alterada", so["partes"][1]["cor"] == "#CC3333" and so["partes"][0]["cor"] == "#00FF00"
   and any("não é a peça selecionada" in r for r in rel2))
glb = e3.normalizar_modelo({"titulo": "Crânio", "partes": [], "glb": {"id": "abc", "nome": "cranio.glb"}})
g2, _ = e3.aplicar_operacoes(glb, [{"op": "alterar", "id": "glb:Mandibula", "campos": {"cor": "azul", "etiqueta": "Mandíbula"}},
                                   {"op": "remover", "id": "glb:Dente1"}])
ok("Modelo GLB: ajustes por malha (cor, etiqueta, esconder)", g2["ajustes_glb"]["glb:Mandibula"] == {"cor": "#2E6DB4", "etiqueta": "Mandíbula"}
   and g2["ajustes_glb"]["glb:Dente1"]["visivel"] is False)
p = e3.pedido_editar(m, "faz um corte", "aorta")
ok("Pedido de edição à IA inclui o modelo atual e a peça selecionada", "«aorta»" in p and '"ventriculo_esquerdo"' in p)

# ---------------------------------------------------------------- molécula real (água, formato SDF V2000)
SDF = """962
  -OEChem-

  3  2  0     0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.2774    0.8929    0.2544 H   0  0  0  0  0  0  0  0  0  0  0  0
    0.6068   -0.2383   -0.7169 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
$$$$"""
agua = e3.molecula_de_sdf(SDF, "Água")
ok("Molécula do PubChem: 3 átomos, 2 ligações, fórmula H2O", sum(p["tipo"] == "esfera" for p in agua["partes"]) == 3
   and sum(p["tipo"] == "cilindro" for p in agua["partes"]) == 2 and "H2O" in agua["descricao"])
sup = e3.modelo_superficie("z = x² − y²", [0, 1, 2, 3], 2, 2)
ok("Superfície (gráfico 3D)", sup["partes"][0]["tipo"] == "superficie" and sup["partes"][0]["dims"]["alturas"] == [0, 1, 2, 3])

# ---------------------------------------------------------------- formas novas e informação por peça
novas = e3.normalizar_modelo({"partes": [
    {"id": "artéria", "tipo": "tubo", "dims": {"pontos": [[0, 0, 0], [0, 1, 0], [0.5, 2, 0]], "raios": [0.3, 0.2, 0.05]},
     "funcao": "Leva o sangue.", "curiosidade": "Tem paredes elásticas.", "material": {"tipo": "tecido"}},
    {"id": "rim", "tipo": "blob", "dims": {"raio": 1, "irregularidade": 9, "semente": 3}},
    {"id": "folha", "tipo": "extrude", "dims": {"forma": [[0, 0], [1, 0.5], [0, 1]], "profundidade": 0.05}},
    {"id": "mau", "tipo": "extrusao", "dims": {"forma": [[0, 0]]}}]})
t_a, t_r, t_f, t_m = novas["partes"]
ok("Tubo com espessura variável, função, curiosidade e material tecido", t_a["dims"]["raios"] == [0.3, 0.2, 0.05]
   and t_a["funcao"] == "Leva o sangue." and t_a["curiosidade"] == "Tem paredes elásticas." and t_a["material"]["tipo"] == "tecido")
ok("Forma orgânica (irregularidade limitada a 0,6)", t_r["tipo"] == "organico" and t_r["dims"]["irregularidade"] == 0.6
   and t_r["dims"]["semente"] == 3)
ok("Extrusão com forma 2D; forma inválida fica com a forma por omissão", t_f["tipo"] == "extrusao" and len(t_f["dims"]["forma"]) == 3
   and len(t_m["dims"]["forma"]) == 3)
ok("Pedido de geração segue o utilizador à letra e omite opções automáticas",
   "segue-o à letra" in e3.pedido_gerar("um carro vermelho", "Automático", "Alto", "Automático", "Automático", "", True)
   and "Tipo de modelo" not in e3.pedido_gerar("um carro vermelho", "Automático", "Alto", "Automático", "Automático", "", True))
ok("Verificação final compara o modelo com o pedido", "Pedido original do utilizador: um carro" in e3.pedido_rever("um carro", novas)
   and '"arteria"' in e3.pedido_rever("um carro", novas))

# ---------------------------------------------------------------- biblioteca (contas reais do modo local)
pasta = Path(tempfile.mkdtemp())
sa, sb_, sc = {}, {}, {}
ana = sb.BackendLocal(pasta / "s.sqlite", sa); ana.registar("ana@uc.pt", "segredo123", "Ana", "Aluno")
rui = sb.BackendLocal(pasta / "s.sqlite", sb_); rui.registar("rui@uc.pt", "segredo123", "Rui", "Aluno")
anon = sb.BackendLocal(pasta / "s.sqlite", sc)
bib_a, bib_r, bib_x = b3.abrir(ana), b3.abrir(rui), b3.abrir(anon)
criado = bib_a.criar(m)
mid = criado["id"]
ok("Criar modelo: fica privado, em rascunho, versão 1", criado["visibilidade"] == "privado" and not criado["publicado"]
   and criado["versao_atual"] == 1)
try:
    bib_r.obter(mid); ok("Modelo privado não é visível para outros", False)
except b3.Erro3D:
    ok("Modelo privado não é visível para outros", True)
n2 = bib_a.guardar_versao(mid, novo, "Aorta azul")
n3 = bib_a.guardar_versao(mid, so, "Ventrículo verde")
ok("Versões guardadas por ordem", [v["n"] for v in bib_a.versoes(mid)] == [3, 2, 1] and bib_a.obter(mid)["modelo"]["partes"][0]["cor"] == "#00FF00")
bib_a.desfazer(mid)
d1 = bib_a.obter(mid)["modelo"]
bib_a.desfazer(mid)
d2 = bib_a.obter(mid)["modelo"]
ok("Desfazer volta atrás passo a passo (3 → 2 → 1) sem apagar o histórico",
   d1["partes"][1]["cor"] == "#2E6DB4" and d2["partes"][1]["cor"] == "#CC3333" and len(bib_a.versoes(mid)) == 5)
bib_a.restaurar(mid, 3)
ok("Recuperar uma versão antiga", bib_a.obter(mid)["modelo"]["partes"][0]["cor"] == "#00FF00")
try:
    bib_r.guardar_versao(mid, novo, "x"); ok("Só o dono altera", False)
except b3.Erro3D:
    ok("Só o dono altera", True)
campos = dict(titulo="Coração humano", descricao="Modelo do coração com as quatro cavidades.", categoria="Anatomia",
              etiquetas="coração, anatomia, cardiologia", capa=b"\x89PNG fake", visibilidade="publico",
              creditos="Ana", licenca="CC BY 4.0 (permite remix com crédito)")
for falta, valor in (("descricao", "curta"), ("etiquetas", ""), ("capa", b""), ("categoria", "X"), ("creditos", "")):
    try:
        bib_a.publicar(mid, **{**campos, falta: valor}); ok(f"Publicar exige {falta}", False)
    except b3.Erro3D:
        ok(f"Publicar exige {falta}", True)
pub = bib_a.publicar(mid, **campos)
ok("Publicar: público, com etiquetas e remix permitido", pub["publicado"] and pub["etiquetas"] == ["coração", "anatomia", "cardiologia"]
   and pub["permite_remix"])
ok("Aparece na pesquisa por título, descrição, categoria e etiqueta (sem acentos)",
   all(bib_x.pesquisar(t) for t in ("coracao", "quatro cavidades", "anatomia", "cardiologia")) and not bib_x.pesquisar("motor"))
ok("Filtro por categoria", bib_x.pesquisar(categoria="Anatomia") and not bib_x.pesquisar(categoria="Química"))
bib_r.registar_visualizacao(mid); bib_r.gostar(mid)
ok("Gostos e visualizações", bib_x.pesquisar("coração")[0]["gostos"] == 1 and bib_x.pesquisar("coração")[0]["visualizacoes"] == 1
   and bib_r.obter(mid)["gostei"])
ok("Gostar outra vez retira o gosto", bib_r.gostar(mid) is False and bib_x.pesquisar("coração")[0]["gostos"] == 0)
try:
    bib_x.gostar(mid); ok("Gostar exige sessão iniciada", False)
except b3.Erro3D:
    ok("Gostar exige sessão iniciada", True)
rmx = bib_r.remix(mid)
ok("Remix: cópia independente do Rui, com referência ao original", rmx["dono_id"] == rui.atual()["id"]
   and rmx["origem_id"] == mid and rmx["origem_autor"] == "Ana" and "Ana" in rmx["creditos"] and rmx["visibilidade"] == "privado")
bib_r.guardar_versao(rmx["id"], so, "mudança no remix")
ok("Alterar o remix não muda o original", bib_a.obter(mid)["modelo"] == bib_a.obter(mid)["modelo"]
   and bib_a.obter(mid)["versao_atual"] == 6 and bib_r.obter(rmx["id"])["versao_atual"] == 2)
try:
    bib_a.remix(mid); ok("O dono não faz remix do próprio (duplica)", False)
except b3.Erro3D:
    ok("O dono não faz remix do próprio (duplica)", True)
bib_a.publicar(mid, **{**campos, "licenca": "Todos os direitos reservados (sem remix)"})
try:
    bib_r.remix(mid); ok("Sem licença de remix, o botão não funciona", False)
except b3.Erro3D:
    ok("Sem licença de remix, o botão não funciona", True)
bib_a.publicar(mid, **{**campos, "visibilidade": "privado"})
ok("Publicado como privado sai da pesquisa", not bib_x.pesquisar("coração"))
bib_a.partilhar(mid, "rui@uc.pt")
ok("Partilhado com o Rui: ele vê, outros não", bib_r.obter(mid)["titulo"] == "Coração humano"
   and [m_["id"] for m_ in bib_r.meus("partilhados")] == [mid])
try:
    bib_x.obter(mid); ok("Sem sessão não vê o privado", False)
except b3.Erro3D:
    ok("Sem sessão não vê o privado", True)
dup = bib_a.duplicar(mid)
ok("Duplicar cria cópia privada em rascunho", dup["titulo"].endswith("(cópia)") and not dup["publicado"]
   and {x["id"] for x in bib_a.meus("rascunhos")} == {dup["id"]} and {x["id"] for x in bib_a.meus("privados")} == {mid})
col = bib_r.criar_colecao("Anatomia"); bib_r.adicionar_a_colecao(col, mid); bib_r.favorito(mid)
ok("Coleções e favoritos", bib_r.colecoes()[0]["n"] == 1 and bib_r.itens_colecao(col)[0]["id"] == mid
   and bib_r.meus("favoritos")[0]["id"] == mid)
bib_a.remover_partilha(mid, rui.atual()["id"])
ok("Retirar a partilha esconde-o outra vez (também da coleção e favoritos)", not bib_r.itens_colecao(col) and not bib_r.meus("favoritos"))
gid = bib_a.guardar_glb("cubo.glb", b"glTF\x02\x00\x00\x00resto")
mg = bib_a.criar({"titulo": "GLB", "partes": [], "glb": {"id": gid, "nome": "cubo.glb"}})
bib_a.publicar(mg["id"], **{**campos, "titulo": "Cubo GLB"})
ok("GLB guardado e lido por quem pode ver o modelo", bib_r.obter_glb(gid, mg["id"]).startswith(b"glTF"))
try:
    bib_a.guardar_glb("x.glb", b"isto nao e 3d"); ok("Ficheiro que não é GLB/glTF é recusado", False)
except b3.Erro3D:
    ok("Ficheiro que não é GLB/glTF é recusado", True)
bib_a.apagar(dup["id"])
ok("Apagar (só o dono)", dup["id"] not in {x["id"] for x in bib_a.meus()})
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
