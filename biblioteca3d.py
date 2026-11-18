"""
Biblioteca 3D do Mondego IA — modelos pessoais, versões, publicação na comunidade, gostos, favoritos, coleções,
partilha de modelos privados e remix.

Reutiliza as contas das Salas (salas_backend): no modo local guarda tudo no mesmo SQLite (salas_local.sqlite);
no modo Supabase usa as tabelas de supabase/esquema.sql (AINDA NÃO TESTADO com um projeto real).

Regras de acesso (iguais nos dois modos):
- um modelo público e publicado é visível para todos;
- um modelo privado só é visível para o dono e para as pessoas com quem ele o partilhou;
- só o dono altera, publica, partilha ou apaga;
- o remix só é possível em modelos públicos com remix autorizado e cria uma cópia independente (o original nunca muda).
"""

from __future__ import annotations

import base64
import json
import unicodedata
import uuid
from datetime import datetime

import estudio3d as e3

VISIBILIDADES = ("publico", "privado")
LICENCAS = {
    "CC BY 4.0 (permite remix com crédito)": True,
    "CC BY-NC 4.0 (remix com crédito, sem fins comerciais)": True,
    "Todos os direitos reservados (sem remix)": False,
}
MAX_CAPA = 900_000          # bytes (PNG/JPG)
MAX_GLB = 25_000_000        # bytes
MAX_MODELO = 2_500_000      # caracteres do JSON


class Erro3D(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sem_acentos(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


# ------------------------------------------------------------------ regras (testáveis, iguais às políticas RLS)
def pode_ver(m: dict, uid: str | None, partilhado: bool = False) -> bool:
    if m.get("publicado") and m.get("visibilidade") == "publico":
        return True
    return bool(uid) and (m.get("dono_id") == uid or partilhado)


def pode_editar(m: dict, uid: str | None) -> bool:
    return bool(uid) and m.get("dono_id") == uid


def pode_remix(m: dict, uid: str | None) -> bool:
    return (bool(uid) and bool(m.get("publicado")) and m.get("visibilidade") == "publico"
            and bool(m.get("permite_remix")) and m.get("dono_id") != uid)


def validar_publicacao(titulo, descricao, categoria, etiquetas, capa, visibilidade, creditos, licenca) -> dict:
    titulo = " ".join(str(titulo or "").split())
    descricao = str(descricao or "").strip()
    creditos = " ".join(str(creditos or "").split())
    if not 3 <= len(titulo) <= 100:
        raise Erro3D("O título tem de ter entre 3 e 100 caracteres.")
    if not 10 <= len(descricao) <= 2000:
        raise Erro3D("Escreve uma descrição com pelo menos 10 caracteres (máximo 2000).")
    if categoria not in e3.CATEGORIAS:
        raise Erro3D("Escolhe uma categoria.")
    if isinstance(etiquetas, str):
        etiquetas = etiquetas.split(",")
    tags = []
    for t in etiquetas or []:
        t = " ".join(str(t).replace("#", "").split()).lower()[:30]
        if t and t not in tags:
            tags.append(t)
    if not 1 <= len(tags) <= 10:
        raise Erro3D("Põe entre 1 e 10 etiquetas, separadas por vírgulas.")
    if not capa:
        raise Erro3D("Falta a imagem de capa (captura a vista do visualizador ou carrega uma imagem).")
    if len(capa) > MAX_CAPA:
        raise Erro3D("A imagem de capa é demasiado grande (máximo 900 KB).")
    if visibilidade not in VISIBILIDADES:
        raise Erro3D("Escolhe se o modelo é público ou privado.")
    if len(creditos) < 2:
        raise Erro3D("Indica os créditos de autoria.")
    if licenca not in LICENCAS:
        raise Erro3D("Escolhe uma licença.")
    return {"titulo": titulo, "descricao": descricao, "categoria": categoria, "etiquetas": tags, "capa": capa,
            "visibilidade": visibilidade, "creditos": creditos[:300], "licenca": licenca,
            "permite_remix": LICENCAS[licenca]}


def _dados_modelo(modelo: dict) -> str:
    modelo = e3.normalizar_modelo(modelo)
    texto = json.dumps(modelo, ensure_ascii=False, separators=(",", ":"))
    if len(texto) > MAX_MODELO:
        raise Erro3D("O modelo é demasiado grande para guardar.")
    return texto


def corresponde(m: dict, texto: str) -> bool:
    """Pesquisa por título, descrição, categoria e etiquetas, sem distinguir maiúsculas nem acentos."""
    alvo = _sem_acentos(" ".join([m.get("titulo", ""), m.get("descricao", ""), m.get("categoria", ""),
                                  " ".join(m.get("etiquetas") or [])]))
    return all(p in alvo for p in _sem_acentos(texto).split())


def ordenar(lista: list, ordem: str) -> list:
    if ordem == "recentes":
        return sorted(lista, key=lambda m: m.get("publicado_em") or "", reverse=True)
    if ordem == "vistos":
        return sorted(lista, key=lambda m: (m.get("visualizacoes", 0), m.get("gostos", 0)), reverse=True)
    return sorted(lista, key=lambda m: (m.get("gostos", 0), m.get("visualizacoes", 0), m.get("publicado_em") or ""),
                  reverse=True)


# ====================================================================== LOCAL (SQLite das Salas)
class Biblioteca3DLocal:
    nome = "local"

    def __init__(self, backend_salas):
        """backend_salas: salas_backend.BackendLocal (dá a ligação à base de dados e a conta com sessão iniciada)."""
        self.contas = backend_salas
        self._db = backend_salas._db
        self._db.executescript("""
            create table if not exists modelos3d (id text primary key,
                dono_id text not null references utilizadores(id) on delete cascade,
                titulo text not null, descricao text not null default '', categoria text not null default 'Outro',
                etiquetas text not null default '[]', visibilidade text not null default 'privado',
                permite_remix integer not null default 0, licenca text not null default '', creditos text not null default '',
                capa blob, dados text not null, versao_atual integer not null default 1,
                origem_id text, origem_titulo text, origem_autor text, publicado integer not null default 0,
                criado_em text, atualizado_em text, publicado_em text, visualizacoes integer not null default 0);
            create table if not exists versoes3d (modelo_id text not null references modelos3d(id) on delete cascade,
                n integer not null, dados text not null, nota text, anterior integer, autor_id text, criado_em text,
                primary key (modelo_id, n));
            create table if not exists gostos3d (modelo_id text references modelos3d(id) on delete cascade,
                utilizador_id text references utilizadores(id) on delete cascade, primary key (modelo_id, utilizador_id));
            create table if not exists favoritos3d (modelo_id text references modelos3d(id) on delete cascade,
                utilizador_id text references utilizadores(id) on delete cascade, primary key (modelo_id, utilizador_id));
            create table if not exists partilhas3d (modelo_id text references modelos3d(id) on delete cascade,
                utilizador_id text references utilizadores(id) on delete cascade, primary key (modelo_id, utilizador_id));
            create table if not exists colecoes3d (id text primary key,
                dono_id text not null references utilizadores(id) on delete cascade, nome text not null, criada_em text);
            create table if not exists colecao_itens3d (colecao_id text references colecoes3d(id) on delete cascade,
                modelo_id text references modelos3d(id) on delete cascade, primary key (colecao_id, modelo_id));
            create table if not exists glb3d (id text primary key,
                dono_id text not null references utilizadores(id) on delete cascade, nome text, dados blob not null,
                criado_em text);
        """)
        self._db.commit()

    # ------------------------------------------------------------- auxiliares
    def _uid(self, obrigatorio: bool = True) -> str | None:
        u = self.contas.atual()
        if not u and obrigatorio:
            raise Erro3D("Inicia sessão primeiro.")
        return u["id"] if u else None

    def _partilhado(self, modelo_id: str, uid: str | None) -> bool:
        return bool(uid) and bool(self._db.execute("select 1 from partilhas3d where modelo_id = ? and utilizador_id = ?",
                                                   (modelo_id, uid)).fetchone())

    def _linha(self, modelo_id: str):
        r = self._db.execute("select m.*, u.nome as dono_nome from modelos3d m join utilizadores u on u.id = m.dono_id "
                             "where m.id = ?", (modelo_id,)).fetchone()
        if not r:
            raise Erro3D("Este modelo não existe.")
        return r

    def _cartao(self, r, uid) -> dict:
        d = {k: r[k] for k in r.keys() if k != "dados"}
        d["etiquetas"] = json.loads(d["etiquetas"] or "[]")
        d["publicado"] = bool(d["publicado"])
        d["permite_remix"] = bool(d["permite_remix"])
        d["gostos"] = self._db.execute("select count(*) from gostos3d where modelo_id = ?", (d["id"],)).fetchone()[0]
        d["gostei"] = bool(uid) and bool(self._db.execute("select 1 from gostos3d where modelo_id = ? and utilizador_id = ?",
                                                           (d["id"], uid)).fetchone())
        d["favorito"] = bool(uid) and bool(self._db.execute("select 1 from favoritos3d where modelo_id = ? and utilizador_id = ?",
                                                             (d["id"], uid)).fetchone())
        return d

    def _obter_visivel(self, modelo_id: str):
        uid = self._uid(obrigatorio=False)
        r = self._linha(modelo_id)
        if not pode_ver(dict(r), uid, self._partilhado(modelo_id, uid)):
            raise Erro3D("Este modelo é privado.")
        return r, uid

    def _obter_meu(self, modelo_id: str):
        uid = self._uid()
        r = self._linha(modelo_id)
        if not pode_editar(dict(r), uid):
            raise Erro3D("Só o dono pode alterar este modelo.")
        return r, uid

    # ------------------------------------------------------------- criar, abrir, versões
    def criar(self, modelo: dict, nota: str = "Criado", origem: dict | None = None, creditos: str = "") -> dict:
        uid = self._uid()
        dados = _dados_modelo(modelo)
        mid = uuid.uuid4().hex
        titulo = json.loads(dados)["titulo"]
        self._db.execute(
            "insert into modelos3d (id, dono_id, titulo, descricao, dados, creditos, origem_id, origem_titulo, origem_autor, "
            "criado_em, atualizado_em) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, uid, titulo, json.loads(dados)["descricao"], dados, creditos,
             (origem or {}).get("id"), (origem or {}).get("titulo"), (origem or {}).get("autor"), _agora(), _agora()))
        self._db.execute("insert into versoes3d values (?, 1, ?, ?, NULL, ?, ?)", (mid, dados, nota[:200], uid, _agora()))
        self._db.commit()
        return self.obter(mid)

    def obter(self, modelo_id: str) -> dict:
        r, uid = self._obter_visivel(modelo_id)
        d = self._cartao(r, uid)
        d["modelo"] = json.loads(r["dados"])
        d["pode_editar"] = pode_editar(d, uid)
        d["pode_remix"] = pode_remix(d, uid)
        return d

    def guardar_versao(self, modelo_id: str, modelo: dict, nota: str) -> int:
        r, uid = self._obter_meu(modelo_id)
        dados = _dados_modelo(modelo)
        n = r["versao_atual"] + 1
        self._db.execute("insert into versoes3d values (?, ?, ?, ?, ?, ?, ?)",
                         (modelo_id, n, dados, (nota or "Alteração")[:200], r["versao_atual"], uid, _agora()))
        self._db.execute("update modelos3d set dados = ?, versao_atual = ?, atualizado_em = ? where id = ?",
                         (dados, n, _agora(), modelo_id))
        self._db.commit()
        return n

    def versoes(self, modelo_id: str) -> list[dict]:
        self._obter_meu(modelo_id)
        return [dict(v) for v in self._db.execute("select n, nota, anterior, criado_em, length(dados) as tamanho "
                                                  "from versoes3d where modelo_id = ? order by n desc", (modelo_id,))]

    def _versao(self, modelo_id: str, n: int):
        v = self._db.execute("select * from versoes3d where modelo_id = ? and n = ?", (modelo_id, n)).fetchone()
        if not v:
            raise Erro3D("Essa versão não existe.")
        return v

    def restaurar(self, modelo_id: str, n: int) -> int:
        """Recupera uma versão anterior sem apagar nada: cria uma versão nova igual à escolhida."""
        r, uid = self._obter_meu(modelo_id)
        v = self._versao(modelo_id, n)
        novo = r["versao_atual"] + 1
        self._db.execute("insert into versoes3d values (?, ?, ?, ?, ?, ?, ?)",
                         (modelo_id, novo, v["dados"], f"Recuperada a versão {n}", v["anterior"], uid, _agora()))
        self._db.execute("update modelos3d set dados = ?, versao_atual = ?, atualizado_em = ? where id = ?",
                         (v["dados"], novo, _agora(), modelo_id))
        self._db.commit()
        return novo

    def desfazer(self, modelo_id: str) -> int | None:
        """Volta ao estado anterior à última alteração (repetir continua a recuar no histórico)."""
        r, _ = self._obter_meu(modelo_id)
        atual = self._versao(modelo_id, r["versao_atual"])
        if not atual["anterior"]:
            return None
        alvo = self._versao(modelo_id, atual["anterior"])
        novo = r["versao_atual"] + 1
        self._db.execute("insert into versoes3d values (?, ?, ?, ?, ?, ?, ?)",
                         (modelo_id, novo, alvo["dados"], f"Desfeito (voltou à versão {alvo['n']})", alvo["anterior"],
                          r["dono_id"], _agora()))
        self._db.execute("update modelos3d set dados = ?, versao_atual = ?, atualizado_em = ? where id = ?",
                         (alvo["dados"], novo, _agora(), modelo_id))
        self._db.commit()
        return novo

    def duplicar(self, modelo_id: str) -> dict:
        r, uid = self._obter_meu(modelo_id)
        modelo = json.loads(r["dados"])
        modelo["titulo"] = (modelo["titulo"] + " (cópia)")[:100]
        return self.criar(modelo, nota=f"Cópia de «{r['titulo']}»", creditos=r["creditos"])

    def remix(self, modelo_id: str) -> dict:
        r, uid = self._obter_visivel(modelo_id)
        if not pode_remix(dict(r), uid):
            raise Erro3D("Este modelo não permite remix." if uid else "Inicia sessão para fazer remix.")
        modelo = json.loads(r["dados"])
        modelo["titulo"] = ("Remix de " + r["titulo"])[:100]
        return self.criar(modelo, nota=f"Remix de «{r['titulo']}» de {r['dono_nome']}",
                          origem={"id": r["id"], "titulo": r["titulo"], "autor": r["dono_nome"]},
                          creditos=f"Baseado em «{r['titulo']}» de {r['dono_nome']} ({r['licenca']})")

    def mudar_titulo(self, modelo_id: str, titulo: str) -> None:
        self._obter_meu(modelo_id)
        titulo = " ".join(str(titulo or "").split())[:100]
        if len(titulo) < 3:
            raise Erro3D("O título tem de ter pelo menos 3 caracteres.")
        self._db.execute("update modelos3d set titulo = ?, atualizado_em = ? where id = ?", (titulo, _agora(), modelo_id))
        self._db.commit()

    def apagar(self, modelo_id: str) -> None:
        self._obter_meu(modelo_id)
        self._db.execute("delete from modelos3d where id = ?", (modelo_id,))
        self._db.commit()

    # ------------------------------------------------------------- publicação
    def publicar(self, modelo_id: str, **campos) -> dict:
        r, _ = self._obter_meu(modelo_id)
        v = validar_publicacao(**campos)
        self._db.execute(
            "update modelos3d set titulo = ?, descricao = ?, categoria = ?, etiquetas = ?, capa = ?, visibilidade = ?, "
            "permite_remix = ?, creditos = ?, licenca = ?, publicado = 1, publicado_em = coalesce(publicado_em, ?), "
            "atualizado_em = ? where id = ?",
            (v["titulo"], v["descricao"], v["categoria"], json.dumps(v["etiquetas"], ensure_ascii=False), v["capa"],
             v["visibilidade"], int(v["permite_remix"]), v["creditos"], v["licenca"], _agora(), _agora(), modelo_id))
        self._db.commit()
        return self.obter(modelo_id)

    def retirar_publicacao(self, modelo_id: str) -> None:
        self._obter_meu(modelo_id)
        self._db.execute("update modelos3d set publicado = 0, atualizado_em = ? where id = ?", (_agora(), modelo_id))
        self._db.commit()

    # ------------------------------------------------------------- pesquisa e listas
    def pesquisar(self, texto: str = "", categoria: str | None = None, ordem: str = "populares", limite: int = 60) -> list[dict]:
        uid = self._uid(obrigatorio=False)
        linhas = self._db.execute("select m.*, u.nome as dono_nome from modelos3d m join utilizadores u on u.id = m.dono_id "
                                  "where m.publicado = 1 and m.visibilidade = 'publico'").fetchall()
        lista = [self._cartao(r, uid) for r in linhas if (not categoria or r["categoria"] == categoria)]
        lista = [m for m in lista if corresponde(m, texto)] if texto.strip() else lista
        return ordenar(lista, ordem)[:limite]

    def meus(self, filtro: str = "todos") -> list[dict]:
        uid = self._uid()
        base = "select m.*, u.nome as dono_nome from modelos3d m join utilizadores u on u.id = m.dono_id "
        if filtro == "favoritos":
            linhas = self._db.execute(base + "join favoritos3d f on f.modelo_id = m.id where f.utilizador_id = ?", (uid,)).fetchall()
            linhas = [r for r in linhas if pode_ver(dict(r), uid, self._partilhado(r["id"], uid))]
        elif filtro == "partilhados":
            linhas = self._db.execute(base + "join partilhas3d p on p.modelo_id = m.id where p.utilizador_id = ?", (uid,)).fetchall()
        else:
            linhas = self._db.execute(base + "where m.dono_id = ?", (uid,)).fetchall()
            if filtro == "publicos":
                linhas = [r for r in linhas if r["publicado"] and r["visibilidade"] == "publico"]
            elif filtro == "privados":
                linhas = [r for r in linhas if r["publicado"] and r["visibilidade"] == "privado"]
            elif filtro == "rascunhos":
                linhas = [r for r in linhas if not r["publicado"]]
        return sorted((self._cartao(r, uid) for r in linhas), key=lambda m: m.get("atualizado_em") or "", reverse=True)

    # ------------------------------------------------------------- gostos, favoritos, visualizações
    def _alternar(self, tabela: str, modelo_id: str) -> bool:
        _, uid = self._obter_visivel(modelo_id)
        if not uid:
            raise Erro3D("Inicia sessão primeiro.")
        if self._db.execute(f"select 1 from {tabela} where modelo_id = ? and utilizador_id = ?", (modelo_id, uid)).fetchone():
            self._db.execute(f"delete from {tabela} where modelo_id = ? and utilizador_id = ?", (modelo_id, uid))
            ativo = False
        else:
            self._db.execute(f"insert into {tabela} values (?, ?)", (modelo_id, uid))
            ativo = True
        self._db.commit()
        return ativo

    def gostar(self, modelo_id: str) -> bool:
        return self._alternar("gostos3d", modelo_id)

    def favorito(self, modelo_id: str) -> bool:
        return self._alternar("favoritos3d", modelo_id)

    def registar_visualizacao(self, modelo_id: str) -> None:
        self._obter_visivel(modelo_id)
        self._db.execute("update modelos3d set visualizacoes = visualizacoes + 1 where id = ?", (modelo_id,))
        self._db.commit()

    # ------------------------------------------------------------- partilha de modelos privados
    def partilhar(self, modelo_id: str, email: str) -> str:
        self._obter_meu(modelo_id)
        u = self._db.execute("select id, nome from utilizadores where email = ?", ((email or "").strip().lower(),)).fetchone()
        if not u:
            raise Erro3D("Não há nenhuma conta com esse email.")
        if u["id"] == self._uid():
            raise Erro3D("Esse email é o teu.")
        self._db.execute("insert or ignore into partilhas3d values (?, ?)", (modelo_id, u["id"]))
        self._db.commit()
        return u["nome"]

    def partilhas(self, modelo_id: str) -> list[dict]:
        self._obter_meu(modelo_id)
        return [dict(r) for r in self._db.execute("select u.id, u.nome, u.email from partilhas3d p join utilizadores u "
                                                  "on u.id = p.utilizador_id where p.modelo_id = ?", (modelo_id,))]

    def remover_partilha(self, modelo_id: str, utilizador_id: str) -> None:
        self._obter_meu(modelo_id)
        self._db.execute("delete from partilhas3d where modelo_id = ? and utilizador_id = ?", (modelo_id, utilizador_id))
        self._db.commit()

    # ------------------------------------------------------------- coleções
    def colecoes(self) -> list[dict]:
        uid = self._uid()
        return [dict(r) for r in self._db.execute(
            "select c.id, c.nome, count(i.modelo_id) as n from colecoes3d c left join colecao_itens3d i on i.colecao_id = c.id "
            "where c.dono_id = ? group by c.id order by c.criada_em", (uid,))]

    def criar_colecao(self, nome: str) -> str:
        uid = self._uid()
        nome = " ".join(str(nome or "").split())[:60]
        if len(nome) < 2:
            raise Erro3D("Dá um nome à coleção.")
        cid = uuid.uuid4().hex
        self._db.execute("insert into colecoes3d values (?, ?, ?, ?)", (cid, uid, nome, _agora()))
        self._db.commit()
        return cid

    def _colecao_minha(self, colecao_id: str) -> None:
        r = self._db.execute("select dono_id from colecoes3d where id = ?", (colecao_id,)).fetchone()
        if not r or r["dono_id"] != self._uid():
            raise Erro3D("Esta coleção não é tua.")

    def apagar_colecao(self, colecao_id: str) -> None:
        self._colecao_minha(colecao_id)
        self._db.execute("delete from colecoes3d where id = ?", (colecao_id,))
        self._db.commit()

    def adicionar_a_colecao(self, colecao_id: str, modelo_id: str) -> None:
        self._colecao_minha(colecao_id)
        self._obter_visivel(modelo_id)
        self._db.execute("insert or ignore into colecao_itens3d values (?, ?)", (colecao_id, modelo_id))
        self._db.commit()

    def remover_da_colecao(self, colecao_id: str, modelo_id: str) -> None:
        self._colecao_minha(colecao_id)
        self._db.execute("delete from colecao_itens3d where colecao_id = ? and modelo_id = ?", (colecao_id, modelo_id))
        self._db.commit()

    def itens_colecao(self, colecao_id: str) -> list[dict]:
        self._colecao_minha(colecao_id)
        uid = self._uid()
        linhas = self._db.execute("select m.*, u.nome as dono_nome from colecao_itens3d i join modelos3d m on m.id = i.modelo_id "
                                  "join utilizadores u on u.id = m.dono_id where i.colecao_id = ?", (colecao_id,)).fetchall()
        return [self._cartao(r, uid) for r in linhas if pode_ver(dict(r), uid, self._partilhado(r["id"], uid))]

    # ------------------------------------------------------------- ficheiros GLB/glTF
    def guardar_glb(self, nome: str, dados: bytes) -> str:
        uid = self._uid()
        if not dados or len(dados) > MAX_GLB:
            raise Erro3D("O ficheiro 3D tem de ter no máximo 25 MB.")
        if dados[:4] != b"glTF" and not dados.lstrip()[:1] == b"{":
            raise Erro3D("O ficheiro não parece ser GLB nem glTF.")
        gid = uuid.uuid4().hex
        self._db.execute("insert into glb3d values (?, ?, ?, ?, ?)", (gid, uid, (nome or "modelo.glb")[:120], dados, _agora()))
        self._db.commit()
        return gid

    def obter_glb(self, glb_id: str, modelo_id: str | None = None) -> bytes:
        r = self._db.execute("select dono_id, dados from glb3d where id = ?", (glb_id,)).fetchone()
        if not r:
            raise Erro3D("O ficheiro 3D deste modelo já não existe.")
        uid = self._uid(obrigatorio=False)
        if r["dono_id"] != uid:
            if not modelo_id:
                raise Erro3D("Sem acesso a este ficheiro 3D.")
            m = self.obter(modelo_id)  # verifica se o utilizador pode ver o modelo
            if glb_id not in ((m["modelo"].get("glb") or {}).get("id"), (m["modelo"].get("blender") or {}).get("id")):
                raise Erro3D("Sem acesso a este ficheiro 3D.")
        return bytes(r["dados"])

    def anexar_blender(self, modelo_id: str, modelo: dict) -> None:
        """Junta o resultado do Blender à versão atual (não cria versão nova: é a mesma forma, melhor desenhada)."""
        r, _uid = self._obter_meu(modelo_id)
        dados = _dados_modelo(modelo)
        self._db.execute("update modelos3d set dados = ?, atualizado_em = ? where id = ?", (dados, _agora(), modelo_id))
        self._db.execute("update versoes3d set dados = ? where modelo_id = ? and n = ?", (dados, modelo_id, r["versao_atual"]))
        self._db.commit()


# ====================================================================== SUPABASE (online) — AINDA NÃO TESTADO
class Biblioteca3DSupabase:
    """Mesma interface, sobre as tabelas de supabase/esquema.sql (secção 3D Studio). As permissões são aplicadas pelo
    servidor (RLS). AINDA NÃO TESTADO com um projeto real."""
    nome = "supabase"

    def __init__(self, backend_salas):
        self.contas = backend_salas
        self._pedido = backend_salas._pedido

    def _uid(self, obrigatorio: bool = True):
        u = self.contas.atual()
        if not u and obrigatorio:
            raise Erro3D("Inicia sessão primeiro.")
        return u["id"] if u else None

    def _cartao(self, l: dict) -> dict:
        uid = self._uid(obrigatorio=False)
        d = dict(l)
        d["dono_nome"] = (d.pop("perfis", None) or {}).get("nome_completo", "?")
        d["capa"] = base64.b64decode(d.pop("capa_b64")) if d.get("capa_b64") else None
        d["etiquetas"] = d.get("etiquetas") or []
        d["gostei"] = bool(uid) and any(g.get("utilizador_id") == uid for g in d.pop("gostos3d", []) or [])
        d["favorito"] = bool(uid) and any(g.get("utilizador_id") == uid for g in d.pop("favoritos3d", []) or [])
        return d

    _SEL = ("id,dono_id,titulo,descricao,categoria,etiquetas,visibilidade,permite_remix,licenca,creditos,capa_b64,"
            "versao_atual,origem_id,origem_titulo,origem_autor,publicado,criado_em,atualizado_em,publicado_em,visualizacoes,"
            "gostos,perfis(nome_completo),gostos3d(utilizador_id),favoritos3d(utilizador_id)")

    def criar(self, modelo, nota="Criado", origem=None, creditos="") -> dict:
        uid = self._uid()
        dados = json.loads(_dados_modelo(modelo))
        linha = self._pedido("POST", "/rest/v1/modelos3d", headers={"Prefer": "return=representation"},
                             json={"dono_id": uid, "titulo": dados["titulo"], "descricao": dados["descricao"], "dados": dados,
                                   "creditos": creditos, "origem_id": (origem or {}).get("id"),
                                   "origem_titulo": (origem or {}).get("titulo"), "origem_autor": (origem or {}).get("autor")})[0]
        self._pedido("POST", "/rest/v1/versoes3d", json={"modelo_id": linha["id"], "n": 1, "dados": dados, "nota": nota[:200],
                                                         "autor_id": uid})
        return self.obter(linha["id"])

    def obter(self, modelo_id) -> dict:
        linhas = self._pedido("GET", f"/rest/v1/modelos3d?id=eq.{modelo_id}&select={self._SEL},dados") or []
        if not linhas:
            raise Erro3D("Este modelo não existe ou é privado.")
        d = self._cartao(linhas[0])
        d["modelo"] = d.pop("dados")
        uid = self._uid(obrigatorio=False)
        d["pode_editar"] = pode_editar(d, uid)
        d["pode_remix"] = pode_remix(d, uid)
        return d

    def guardar_versao(self, modelo_id, modelo, nota) -> int:
        m = self.obter(modelo_id)
        if not m["pode_editar"]:
            raise Erro3D("Só o dono pode alterar este modelo.")
        dados = json.loads(_dados_modelo(modelo))
        n = m["versao_atual"] + 1
        self._pedido("POST", "/rest/v1/versoes3d", json={"modelo_id": modelo_id, "n": n, "dados": dados, "nota": (nota or "")[:200],
                                                         "anterior": m["versao_atual"], "autor_id": self._uid()})
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={"dados": dados, "versao_atual": n,
                                                                            "atualizado_em": _agora()})
        return n

    def versoes(self, modelo_id) -> list[dict]:
        return self._pedido("GET", f"/rest/v1/versoes3d?modelo_id=eq.{modelo_id}&select=n,nota,anterior,criado_em&order=n.desc") or []

    def _versao(self, modelo_id, n) -> dict:
        v = self._pedido("GET", f"/rest/v1/versoes3d?modelo_id=eq.{modelo_id}&n=eq.{n}&select=*") or []
        if not v:
            raise Erro3D("Essa versão não existe.")
        return v[0]

    def restaurar(self, modelo_id, n) -> int:
        v = self._versao(modelo_id, n)
        m = self.obter(modelo_id)
        novo = m["versao_atual"] + 1
        self._pedido("POST", "/rest/v1/versoes3d", json={"modelo_id": modelo_id, "n": novo, "dados": v["dados"],
                                                         "nota": f"Recuperada a versão {n}", "anterior": v["anterior"],
                                                         "autor_id": self._uid()})
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={"dados": v["dados"], "versao_atual": novo})
        return novo

    def desfazer(self, modelo_id):
        m = self.obter(modelo_id)
        atual = self._versao(modelo_id, m["versao_atual"])
        if not atual.get("anterior"):
            return None
        return self.restaurar(modelo_id, atual["anterior"])

    def duplicar(self, modelo_id) -> dict:
        m = self.obter(modelo_id)
        if not m["pode_editar"]:
            raise Erro3D("Só o dono pode duplicar este modelo.")
        modelo = m["modelo"]
        modelo["titulo"] = (modelo["titulo"] + " (cópia)")[:100]
        return self.criar(modelo, nota=f"Cópia de «{m['titulo']}»", creditos=m["creditos"])

    def remix(self, modelo_id) -> dict:
        m = self.obter(modelo_id)
        if not m["pode_remix"]:
            raise Erro3D("Este modelo não permite remix.")
        modelo = m["modelo"]
        modelo["titulo"] = ("Remix de " + m["titulo"])[:100]
        return self.criar(modelo, nota=f"Remix de «{m['titulo']}» de {m['dono_nome']}",
                          origem={"id": m["id"], "titulo": m["titulo"], "autor": m["dono_nome"]},
                          creditos=f"Baseado em «{m['titulo']}» de {m['dono_nome']} ({m['licenca']})")

    def mudar_titulo(self, modelo_id, titulo) -> None:
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={"titulo": " ".join(str(titulo).split())[:100]})

    def apagar(self, modelo_id) -> None:
        self._pedido("DELETE", f"/rest/v1/modelos3d?id=eq.{modelo_id}")

    def publicar(self, modelo_id, **campos) -> dict:
        v = validar_publicacao(**campos)
        m = self.obter(modelo_id)
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={
            "titulo": v["titulo"], "descricao": v["descricao"], "categoria": v["categoria"], "etiquetas": v["etiquetas"],
            "capa_b64": base64.b64encode(v["capa"]).decode(), "visibilidade": v["visibilidade"],
            "permite_remix": v["permite_remix"], "creditos": v["creditos"], "licenca": v["licenca"], "publicado": True,
            "publicado_em": m.get("publicado_em") or _agora()})
        return self.obter(modelo_id)

    def retirar_publicacao(self, modelo_id) -> None:
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={"publicado": False})

    def pesquisar(self, texto="", categoria=None, ordem="populares", limite=60) -> list[dict]:
        filtro = "publicado=eq.true&visibilidade=eq.publico"
        if categoria:
            filtro += f"&categoria=eq.{categoria}"
        linhas = self._pedido("GET", f"/rest/v1/modelos3d?{filtro}&select={self._SEL}&limit=500") or []
        lista = [self._cartao(l) for l in linhas]
        lista = [m for m in lista if corresponde(m, texto)] if (texto or "").strip() else lista
        return ordenar(lista, ordem)[:limite]

    def meus(self, filtro="todos") -> list[dict]:
        uid = self._uid()
        if filtro == "favoritos":
            ids = [f["modelo_id"] for f in self._pedido("GET", f"/rest/v1/favoritos3d?utilizador_id=eq.{uid}&select=modelo_id") or []]
        elif filtro == "partilhados":
            ids = [f["modelo_id"] for f in self._pedido("GET", f"/rest/v1/partilhas3d?utilizador_id=eq.{uid}&select=modelo_id") or []]
        else:
            ids = None
        if ids is not None:
            if not ids:
                return []
            linhas = self._pedido("GET", f"/rest/v1/modelos3d?id=in.({','.join(ids)})&select={self._SEL}") or []
        else:
            linhas = self._pedido("GET", f"/rest/v1/modelos3d?dono_id=eq.{uid}&select={self._SEL}") or []
        lista = [self._cartao(l) for l in linhas]
        if filtro == "publicos":
            lista = [m for m in lista if m["publicado"] and m["visibilidade"] == "publico"]
        elif filtro == "privados":
            lista = [m for m in lista if m["publicado"] and m["visibilidade"] == "privado"]
        elif filtro == "rascunhos":
            lista = [m for m in lista if not m["publicado"]]
        return sorted(lista, key=lambda m: m.get("atualizado_em") or "", reverse=True)

    def _alternar(self, tabela, modelo_id) -> bool:
        uid = self._uid()
        existe = self._pedido("GET", f"/rest/v1/{tabela}?modelo_id=eq.{modelo_id}&utilizador_id=eq.{uid}&select=modelo_id") or []
        if existe:
            self._pedido("DELETE", f"/rest/v1/{tabela}?modelo_id=eq.{modelo_id}&utilizador_id=eq.{uid}")
            return False
        self._pedido("POST", f"/rest/v1/{tabela}", json={"modelo_id": modelo_id, "utilizador_id": uid})
        return True

    def gostar(self, modelo_id) -> bool:
        return self._alternar("gostos3d", modelo_id)

    def favorito(self, modelo_id) -> bool:
        return self._alternar("favoritos3d", modelo_id)

    def registar_visualizacao(self, modelo_id) -> None:
        self._pedido("POST", "/rest/v1/rpc/ver_modelo3d", json={"p_modelo": modelo_id})

    def partilhar(self, modelo_id, email) -> str:
        r = self._pedido("POST", "/rest/v1/rpc/partilhar_modelo3d", json={"p_modelo": modelo_id,
                                                                          "p_email": (email or "").strip().lower()})
        return r or email

    def partilhas(self, modelo_id) -> list[dict]:
        linhas = self._pedido("GET", f"/rest/v1/partilhas3d?modelo_id=eq.{modelo_id}&select=utilizador_id,perfis(nome_completo)") or []
        return [{"id": l["utilizador_id"], "nome": (l.get("perfis") or {}).get("nome_completo", "?"), "email": ""} for l in linhas]

    def remover_partilha(self, modelo_id, utilizador_id) -> None:
        self._pedido("DELETE", f"/rest/v1/partilhas3d?modelo_id=eq.{modelo_id}&utilizador_id=eq.{utilizador_id}")

    def colecoes(self) -> list[dict]:
        uid = self._uid()
        linhas = self._pedido("GET", f"/rest/v1/colecoes3d?dono_id=eq.{uid}&select=id,nome,colecao_itens3d(modelo_id)") or []
        return [{"id": l["id"], "nome": l["nome"], "n": len(l.get("colecao_itens3d") or [])} for l in linhas]

    def criar_colecao(self, nome) -> str:
        nome = " ".join(str(nome or "").split())[:60]
        if len(nome) < 2:
            raise Erro3D("Dá um nome à coleção.")
        return self._pedido("POST", "/rest/v1/colecoes3d", headers={"Prefer": "return=representation"},
                            json={"dono_id": self._uid(), "nome": nome})[0]["id"]

    def apagar_colecao(self, colecao_id) -> None:
        self._pedido("DELETE", f"/rest/v1/colecoes3d?id=eq.{colecao_id}")

    def adicionar_a_colecao(self, colecao_id, modelo_id) -> None:
        self._pedido("POST", "/rest/v1/colecao_itens3d", json={"colecao_id": colecao_id, "modelo_id": modelo_id},
                     headers={"Prefer": "resolution=ignore-duplicates"})

    def remover_da_colecao(self, colecao_id, modelo_id) -> None:
        self._pedido("DELETE", f"/rest/v1/colecao_itens3d?colecao_id=eq.{colecao_id}&modelo_id=eq.{modelo_id}")

    def itens_colecao(self, colecao_id) -> list[dict]:
        linhas = self._pedido("GET", f"/rest/v1/colecao_itens3d?colecao_id=eq.{colecao_id}&select=modelos3d({self._SEL})") or []
        return [self._cartao(l["modelos3d"]) for l in linhas if l.get("modelos3d")]

    def guardar_glb(self, nome, dados) -> str:
        if not dados or len(dados) > MAX_GLB:
            raise Erro3D("O ficheiro 3D tem de ter no máximo 25 MB.")
        return self._pedido("POST", "/rest/v1/glb3d", headers={"Prefer": "return=representation"},
                            json={"dono_id": self._uid(), "nome": (nome or "")[:120],
                                  "dados_b64": base64.b64encode(dados).decode()})[0]["id"]

    def obter_glb(self, glb_id, modelo_id=None) -> bytes:
        linhas = self._pedido("GET", f"/rest/v1/glb3d?id=eq.{glb_id}&select=dados_b64") or []
        if not linhas:
            raise Erro3D("Sem acesso a este ficheiro 3D.")
        return base64.b64decode(linhas[0]["dados_b64"])

    def anexar_blender(self, modelo_id, modelo) -> None:
        m = self.obter(modelo_id)
        if not m["pode_editar"]:
            raise Erro3D("Só o dono pode alterar este modelo.")
        dados = json.loads(_dados_modelo(modelo))
        self._pedido("PATCH", f"/rest/v1/modelos3d?id=eq.{modelo_id}", json={"dados": dados, "atualizado_em": _agora()})
        self._pedido("PATCH", f"/rest/v1/versoes3d?modelo_id=eq.{modelo_id}&n=eq.{m['versao_atual']}", json={"dados": dados})


def abrir(backend_salas):
    """Biblioteca do mesmo tipo que as Salas (local ou Supabase)."""
    return Biblioteca3DSupabase(backend_salas) if backend_salas.nome == "supabase" else Biblioteca3DLocal(backend_salas)
