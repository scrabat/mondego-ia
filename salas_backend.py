"""
Salas do Mondego IA — armazenamento.

Duas implementações com a mesma interface:
- BackendLocal: SQLite neste computador. Funciona já (contas, salas, códigos, chat, ficheiros), mas os dados ficam
  só aqui — serve para experimentar e para testar professor/aluno com duas contas.
- BackendSupabase: base de dados e ficheiros online (ver supabase/esquema.sql). Para colegas em computadores
  diferentes. Precisa do Project URL e da chave anon (Perfil → Chaves e dados → Salas online).

As regras de acesso são as de salas.py (iguais às políticas RLS do Supabase).
"""

from __future__ import annotations

import hashlib
import json
import hmac
import re
import secrets
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import salas as sl

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErroSalas(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def validar_registo(email: str, palavra_passe: str, nome: str, vinculo: str) -> tuple[str, str]:
    email = (email or "").strip().lower()
    nome = " ".join((nome or "").split())
    if not EMAIL_RE.match(email):
        raise ErroSalas("Escreve um email válido.")
    if len(palavra_passe or "") < 8:
        raise ErroSalas("A palavra-passe tem de ter pelo menos 8 caracteres.")
    if len(nome) < 2:
        raise ErroSalas("Escreve o teu nome.")
    if vinculo not in ("Aluno", "Professor"):
        raise ErroSalas("Escolhe se és aluno ou professor.")
    return email, nome


def validar_nome_sala(nome: str) -> str:
    nome = " ".join((nome or "").split())
    if not 2 <= len(nome) <= 80:
        raise ErroSalas("O nome da sala tem de ter entre 2 e 80 caracteres.")
    return nome


# ====================================================================== LOCAL (SQLite)
class BackendLocal:
    nome = "local"

    def __init__(self, caminho: Path, sessao: dict):
        """sessao: dicionário guardado no st.session_state (aqui fica o id do utilizador com sessão iniciada)."""
        self.caminho = Path(caminho)
        self.sessao = sessao
        self._db = sqlite3.connect(self.caminho, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript("""
            create table if not exists utilizadores (id text primary key, email text unique not null, nome text not null,
                vinculo text not null, sal blob not null, hash blob not null, criado_em text);
            create table if not exists salas (id text primary key, nome text not null, tipo text not null, cadeira text,
                criador_id text not null references utilizadores(id) on delete cascade, codigo text unique not null,
                chat_ativo integer not null default 0, criada_em text);
            create table if not exists membros (sala_id text references salas(id) on delete cascade,
                utilizador_id text references utilizadores(id) on delete cascade, papel text not null, entrou_em text,
                primary key (sala_id, utilizador_id));
            create table if not exists ficheiros (id text primary key, sala_id text not null references salas(id) on delete cascade,
                dono_id text not null references utilizadores(id) on delete cascade, nome text not null, tipo_mime text,
                pasta_fixa integer not null default 0, texto text, dados blob, enviado_em text);
            create table if not exists mensagens (id integer primary key autoincrement,
                sala_id text not null references salas(id) on delete cascade,
                autor_id text not null references utilizadores(id) on delete cascade, texto text not null, enviada_em text);
        """)
        self._migrar()
        self._db.commit()

    def _migrar(self) -> None:
        """Acrescenta as colunas novas (definições da sala e foto) às bases de dados de versões anteriores."""
        colunas = {r["name"] for r in self._db.execute("pragma table_info(salas)")}
        novas = {"descricao": "text default ''", "cor": "text", "aviso": "text default ''", "chat_modo": "text",
                 "quem_publica": "text", "ficheiros_privados": "integer default 1", "assistente_ativo": "integer default 1",
                 "convites": "text default 'todos'", "entrada_aberta": "integer default 1",
                 "laboratorio": "integer default 0", "ferramentas_lab": "text default '[]'", "icone": "text default ''"}
        for nome, tipo in novas.items():
            if nome not in colunas:
                self._db.execute(f"alter table salas add column {nome} {tipo}")
        # salas antigas: a conversa vem de chat_ativo; nos grupos todos partilham, nas salas de cadeira só o criador
        self._db.execute("update salas set chat_modo = case when chat_ativo then 'todos' else 'desligado' end where chat_modo is null")
        self._db.execute("update salas set quem_publica = case when tipo = 'cadeira' then 'criador' else 'todos' end "
                         "where quem_publica is null")
        self._db.execute("update salas set cor = case when tipo = 'cadeira' then 'azul' else 'terracota' end where cor is null")
        if "foto" not in {r["name"] for r in self._db.execute("pragma table_info(utilizadores)")}:
            self._db.execute("alter table utilizadores add column foto blob")

    # ------------------------------------------------------------- contas
    @staticmethod
    def _hash(palavra_passe: str, sal: bytes) -> bytes:
        return hashlib.scrypt(palavra_passe.encode(), salt=sal, n=2 ** 14, r=8, p=1)

    def registar(self, email, palavra_passe, nome, vinculo) -> dict:
        email, nome = validar_registo(email, palavra_passe, nome, vinculo)
        if self._db.execute("select 1 from utilizadores where email = ?", (email,)).fetchone():
            raise ErroSalas("Já existe uma conta com este email. Usa «Entrar».")
        sal = secrets.token_bytes(16)
        uid = uuid.uuid4().hex
        self._db.execute("insert into utilizadores (id, email, nome, vinculo, sal, hash, criado_em) values (?, ?, ?, ?, ?, ?, ?)",
                         (uid, email, nome, vinculo, sal, self._hash(palavra_passe, sal), _agora()))
        self._db.commit()
        self.sessao["uid"] = uid
        return self.atual()

    def existe(self, email: str) -> bool:
        """Já há uma conta com este email? (o ecrã de entrada pede a palavra-passe ou cria a conta)"""
        return self._db.execute("select 1 from utilizadores where email = ?", ((email or "").strip().lower(),)).fetchone() \
            is not None

    def entrar(self, email, palavra_passe) -> dict:
        linha = self._db.execute("select * from utilizadores where email = ?", ((email or "").strip().lower(),)).fetchone()
        if not linha or not hmac.compare_digest(self._hash(palavra_passe or "", linha["sal"]), linha["hash"]):
            raise ErroSalas("Email ou palavra-passe errados.")
        self.sessao["uid"] = linha["id"]
        return self.atual()

    def entrar_externo(self, email: str, nome: str, vinculo: str = "Aluno") -> dict:
        """Entrada com uma conta Google/Facebook/Microsoft (verificada pelo Streamlit): usa a conta local com o mesmo
        email ou cria-a (sem palavra-passe utilizável — só se entra por esse fornecedor)."""
        email = (email or "").strip().lower()
        if not EMAIL_RE.match(email):
            raise ErroSalas("A conta externa não indicou um email válido.")
        linha = self._db.execute("select id from utilizadores where email = ?", (email,)).fetchone()
        if linha:
            uid = linha["id"]
        else:
            uid = uuid.uuid4().hex
            sal = secrets.token_bytes(16)
            self._db.execute("insert into utilizadores (id, email, nome, vinculo, sal, hash, criado_em) values (?, ?, ?, ?, ?, ?, ?)",
                             (uid, email, " ".join((nome or email.split("@")[0]).split())[:80],
                              vinculo if vinculo in ("Aluno", "Professor") else "Aluno", sal,
                              self._hash(secrets.token_urlsafe(32), sal), _agora()))
            self._db.commit()
        self.sessao["uid"] = uid
        return self.atual()

    def sair(self) -> None:
        self.sessao.pop("uid", None)

    def apagar_conta(self) -> None:
        """Apaga a conta com sessão iniciada (e, em cascata, as salas que criou, os ficheiros e as mensagens)."""
        uid = self.sessao.get("uid")
        if uid:
            self._db.execute("delete from utilizadores where id = ?", (uid,))
            self._db.commit()
        self.sessao.pop("uid", None)

    def atual(self) -> dict | None:
        uid = self.sessao.get("uid")
        if not uid:
            return None
        linha = self._db.execute("select id, email, nome, vinculo, foto from utilizadores where id = ?", (uid,)).fetchone()
        return dict(linha) if linha else None

    def mudar_perfil(self, nome: str | None = None, foto: bytes | None = None, apagar_foto: bool = False) -> dict:
        """Nome e fotografia da conta (os colegas das salas veem-nos)."""
        uid = self._uid()
        if nome is not None:
            nome = " ".join(str(nome).split())
            if not 2 <= len(nome) <= 80:
                raise ErroSalas("O nome tem de ter entre 2 e 80 caracteres.")
            self._db.execute("update utilizadores set nome = ? where id = ?", (nome, uid))
        if foto is not None or apagar_foto:
            if foto is not None and len(foto) > 400_000:
                raise ErroSalas("A fotografia é demasiado grande.")
            self._db.execute("update utilizadores set foto = ? where id = ?", (None if apagar_foto else foto, uid))
        self._db.commit()
        return self.atual()

    def mudar_vinculo(self, vinculo: str) -> dict:
        """Aluno ou professor (escolhido na primeira entrada ou no Perfil): decide o tipo de sala que a pessoa cria."""
        if vinculo not in ("Aluno", "Professor"):
            raise ErroSalas("Escolhe se és aluno ou professor.")
        self._db.execute("update utilizadores set vinculo = ? where id = ?", (vinculo, self._uid()))
        self._db.commit()
        return self.atual()

    def mudar_palavra_passe(self, atual: str, nova: str) -> None:
        """Muda a palavra-passe da conta com sessão iniciada. Pede a atual (quem tem só a sessão aberta não a muda)."""
        uid = self._uid()
        linha = self._db.execute("select sal, hash from utilizadores where id = ?", (uid,)).fetchone()
        if not linha or not hmac.compare_digest(self._hash(atual or "", linha["sal"]), linha["hash"]):
            raise ErroSalas("A palavra-passe atual não está certa.")
        if len(nova or "") < 8:
            raise ErroSalas("A palavra-passe nova tem de ter pelo menos 8 caracteres.")
        if nova == atual:
            raise ErroSalas("A palavra-passe nova tem de ser diferente da atual.")
        sal = secrets.token_bytes(16)
        self._db.execute("update utilizadores set sal = ?, hash = ? where id = ?", (sal, self._hash(nova, sal), uid))
        self._db.commit()

    def _uid(self) -> str:
        u = self.atual()
        if not u:
            raise ErroSalas("Inicia sessão primeiro.")
        return u["id"]

    # ------------------------------------------------------------- salas
    def _membros_obj(self, sala_id: str) -> list[sl.Membro]:
        return [sl.Membro(r["sala_id"], r["utilizador_id"], r["papel"])
                for r in self._db.execute("select * from membros where sala_id = ?", (sala_id,))]

    def _papel(self, sala_id: str, uid: str) -> str | None:
        r = self._db.execute("select papel from membros where sala_id = ? and utilizador_id = ?", (sala_id, uid)).fetchone()
        return r["papel"] if r else None

    def _codigo_livre(self) -> str:
        for _ in range(50):
            codigo = sl.gerar_codigo()
            if not self._db.execute("select 1 from salas where codigo = ?", (codigo,)).fetchone():
                return codigo
        raise ErroSalas("Não foi possível gerar um código. Tenta outra vez.")

    def criar_sala(self, nome: str, chat_ativo: bool | None = None, cadeira: str | None = None, **definicoes) -> dict:
        """Cria a sala com as definições escolhidas (as que faltarem ficam com os valores por omissão do tipo de sala)."""
        uid = self._uid()
        nome = validar_nome_sala(nome)
        tipo = sl.tipo_de_sala_permitido(self.atual()["vinculo"])
        try:
            d = sl.validar_definicoes(definicoes, sl.definicoes_padrao(tipo, chat_ativo))
        except sl.ErroDefinicoes as erro:
            raise ErroSalas(str(erro)) from None
        sid = uuid.uuid4().hex
        self._db.execute(
            "insert into salas (id, nome, tipo, cadeira, criador_id, codigo, chat_ativo, criada_em, descricao, cor, aviso, "
            "chat_modo, quem_publica, ficheiros_privados, assistente_ativo, convites, entrada_aberta, laboratorio, "
            "ferramentas_lab, icone) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, nome, tipo, (cadeira or None) if tipo == "cadeira" else None, uid, self._codigo_livre(),
             int(d["chat_modo"] != "desligado"), _agora(), d["descricao"], d["cor"], d["aviso"], d["chat_modo"],
             d["quem_publica"], int(d["ficheiros_privados"]), int(d["assistente_ativo"]), d["convites"],
             int(d["entrada_aberta"]), int(d["laboratorio"]), json.dumps(d["ferramentas_lab"]), d.get("icone") or ""))
        self._db.execute("insert into membros values (?, ?, ?, ?)", (sid, uid, "criador", _agora()))
        self._db.commit()
        return self.obter_sala(sid)

    def entrar_com_codigo(self, codigo: str) -> dict:
        uid = self._uid()
        linha = self._db.execute("select id, entrada_aberta from salas where codigo = ?", (sl.normalizar_codigo(codigo),)).fetchone()
        if not linha:
            raise ErroSalas("Não existe nenhuma sala com esse código.")
        if not self._papel(linha["id"], uid):
            if not linha["entrada_aberta"]:
                raise ErroSalas("Esta sala não está a aceitar novos membros. Fala com quem a criou.")
            papel = "professor" if self.atual()["vinculo"] == "Professor" else "aluno"
            self._db.execute("insert into membros values (?, ?, ?, ?)", (linha["id"], uid, papel, _agora()))
            self._db.commit()
        return self.obter_sala(linha["id"])

    def _sala_dict(self, linha, uid) -> dict:
        d = dict(linha)
        for k in ("ficheiros_privados", "assistente_ativo", "entrada_aberta"):
            d[k] = bool(d.get(k, 1))
        d["laboratorio"] = bool(d.get("laboratorio") or 0)
        try:
            d["ferramentas_lab"] = [f for f in json.loads(d.get("ferramentas_lab") or "[]") if f in sl.FERRAMENTAS_LAB]
        except (TypeError, ValueError):
            d["ferramentas_lab"] = []
        d["chat_ativo"] = sl.chat_ativo(d)
        d["papel"] = self._papel(d["id"], uid)
        d["e_criador"] = d["criador_id"] == uid
        d["n_membros"] = self._db.execute("select count(*) from membros where sala_id = ?", (d["id"],)).fetchone()[0]
        d["n_documentos"] = self._db.execute("select count(*) from ficheiros where sala_id = ? and pasta_fixa = 1",
                                             (d["id"],)).fetchone()[0]
        if not sl.pode_ver_convite(d, uid):
            d["codigo"] = None  # o código só aparece a quem pode convidar
        return d

    def minhas_salas(self) -> list[dict]:
        uid = self._uid()
        linhas = self._db.execute("select s.* from salas s join membros m on m.sala_id = s.id where m.utilizador_id = ? "
                                  "order by s.criada_em desc", (uid,)).fetchall()
        return [self._sala_dict(l, uid) for l in linhas]

    def obter_sala(self, sala_id: str) -> dict:
        uid = self._uid()
        linha = self._db.execute("select * from salas where id = ?", (sala_id,)).fetchone()
        if not linha or not self._papel(sala_id, uid):
            raise ErroSalas("Esta sala não existe ou não és membro.")
        return self._sala_dict(linha, uid)

    def _sala_do_criador(self, sala_id: str) -> dict:
        sala = self.obter_sala(sala_id)
        if not sala["e_criador"]:
            raise ErroSalas("Só quem criou a sala a pode configurar.")
        return sala

    def atualizar_sala(self, sala_id: str, nome: str | None = None, chat_ativo: bool | None = None, **definicoes) -> dict:
        """Só o criador. Aceita nome, descricao, cor, aviso, chat_modo, quem_publica, ficheiros_privados,
        assistente_ativo, convites e entrada_aberta (chat_ativo continua a funcionar: liga/desliga a conversa)."""
        sala = self._sala_do_criador(sala_id)
        campos = dict(definicoes)
        if nome is not None:
            campos["nome"] = nome
        if chat_ativo is not None and "chat_modo" not in campos:
            campos["chat_modo"] = ("todos" if sala["chat_modo"] == "desligado" else sala["chat_modo"]) if chat_ativo else "desligado"
        try:
            novo = sl.validar_definicoes(campos, sala)
        except sl.ErroDefinicoes as erro:
            raise ErroSalas(str(erro)) from None
        self._db.execute(
            "update salas set nome = ?, descricao = ?, cor = ?, aviso = ?, chat_modo = ?, chat_ativo = ?, quem_publica = ?, "
            "ficheiros_privados = ?, assistente_ativo = ?, convites = ?, entrada_aberta = ?, laboratorio = ?, "
            "ferramentas_lab = ?, icone = ? where id = ?",
            (novo["nome"], novo["descricao"], novo["cor"], novo["aviso"], novo["chat_modo"], int(novo["chat_modo"] != "desligado"),
             novo["quem_publica"], int(novo["ficheiros_privados"]), int(novo["assistente_ativo"]), novo["convites"],
             int(novo["entrada_aberta"]), int(novo.get("laboratorio", False)), json.dumps(novo.get("ferramentas_lab") or []),
             novo.get("icone") or "", sala_id))
        self._db.commit()
        return self.obter_sala(sala_id)

    def novo_codigo(self, sala_id: str) -> str:
        """O código antigo deixa de funcionar (útil se foi partilhado com quem não devia)."""
        self._sala_do_criador(sala_id)
        codigo = self._codigo_livre()
        self._db.execute("update salas set codigo = ? where id = ?", (codigo, sala_id))
        self._db.commit()
        return codigo

    def apagar_sala(self, sala_id: str) -> None:
        sala = self.obter_sala(sala_id)
        if not sala["e_criador"]:
            raise ErroSalas("Só quem criou a sala a pode apagar.")
        self._db.execute("delete from salas where id = ?", (sala_id,))
        self._db.commit()

    def sair_da_sala(self, sala_id: str) -> None:
        sala = self.obter_sala(sala_id)
        if sala["e_criador"]:
            raise ErroSalas("Quem criou a sala não pode sair; podes apagá-la.")
        self._db.execute("delete from membros where sala_id = ? and utilizador_id = ?", (sala_id, self._uid()))
        self._db.commit()

    def remover_membro(self, sala_id: str, utilizador_id: str) -> None:
        sala = self._sala_do_criador(sala_id)
        if not sl.pode_remover_membro(sala, utilizador_id, self._uid()):
            raise ErroSalas("Não podes remover quem criou a sala.")
        self._db.execute("delete from membros where sala_id = ? and utilizador_id = ?", (sala_id, utilizador_id))
        self._db.commit()

    def membros(self, sala_id: str) -> list[dict]:
        self.obter_sala(sala_id)
        return [dict(r) for r in self._db.execute(
            "select m.utilizador_id, m.papel, m.entrou_em, u.nome, u.foto from membros m "
            "join utilizadores u on u.id = m.utilizador_id where m.sala_id = ? order by m.entrou_em", (sala_id,))]

    # ------------------------------------------------------------- ficheiros
    def enviar_ficheiro(self, sala_id: str, nome: str, dados: bytes, tipo_mime: str, pasta_fixa: bool, texto: str) -> dict:
        """pasta_fixa=True: documento partilhado (materiais da sala); False: privado (só o dono o vê)."""
        uid = self._uid()
        sala = self.obter_sala(sala_id)
        if pasta_fixa and not sl.pode_partilhar(sala, uid):
            raise ErroSalas("Nesta sala só quem a criou pode pôr documentos nos materiais.")
        if not pasta_fixa and not sl.pode_ter_privados(sala):
            raise ErroSalas("Esta sala não tem ficheiros privados.")
        fid = uuid.uuid4().hex
        self._db.execute("insert into ficheiros values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (fid, sala_id, uid, nome, tipo_mime, int(pasta_fixa), texto, dados, _agora()))
        self._db.commit()
        return next(f for f in self.ficheiros(sala_id) if f["id"] == fid)

    def ficheiros(self, sala_id: str) -> list[dict]:
        """Só os ficheiros que o utilizador pode ver (regras de salas.py)."""
        uid = self._uid()
        sala = self.obter_sala(sala_id)
        membros = self._membros_obj(sala_id)
        resultado = []
        for r in self._db.execute("select f.id, f.sala_id, f.dono_id, f.nome, f.tipo_mime, f.pasta_fixa, f.texto, f.enviado_em, "
                                  "length(f.dados) as tamanho, u.nome as dono_nome from ficheiros f "
                                  "join utilizadores u on u.id = f.dono_id where f.sala_id = ? order by f.enviado_em", (sala_id,)):
            obj = sl.Ficheiro(r["id"], r["sala_id"], r["dono_id"], r["nome"], bool(r["pasta_fixa"]))
            if sl.pode_ver_ficheiro(obj, uid, membros):
                d = dict(r)
                d["pasta_fixa"] = bool(d["pasta_fixa"])
                d["texto_extraido"] = d.pop("texto") or ""
                d["pode_apagar"] = sl.pode_apagar_ficheiro(sala, d["dono_id"], uid)
                resultado.append(d)
        return resultado

    def dados_ficheiro(self, ficheiro_id: str) -> bytes:
        """Ficheiro original (para descarregar), só se o utilizador o puder ver."""
        r = self._db.execute("select sala_id from ficheiros where id = ?", (ficheiro_id,)).fetchone()
        if not r or ficheiro_id not in {f["id"] for f in self.ficheiros(r["sala_id"])}:
            raise ErroSalas("Sem acesso a este ficheiro.")
        return bytes(self._db.execute("select dados from ficheiros where id = ?", (ficheiro_id,)).fetchone()["dados"] or b"")

    def apagar_ficheiro(self, ficheiro_id: str) -> None:
        r = self._db.execute("select dono_id, sala_id from ficheiros where id = ?", (ficheiro_id,)).fetchone()
        if not r:
            raise ErroSalas("Este ficheiro já não existe.")
        sala = self.obter_sala(r["sala_id"])
        if not sl.pode_apagar_ficheiro(sala, r["dono_id"], self._uid()):
            raise ErroSalas("Só podes apagar os teus ficheiros.")
        self._db.execute("delete from ficheiros where id = ?", (ficheiro_id,))
        self._db.commit()

    # ------------------------------------------------------------- conversa entre membros
    def mensagens(self, sala_id: str, limite: int = 200) -> list[dict]:
        sala = self.obter_sala(sala_id)
        if not sl.chat_ativo(sala):
            return []
        uid = self._uid()
        linhas = self._db.execute("select m.*, u.nome as autor_nome from mensagens m join utilizadores u on u.id = m.autor_id "
                                  "where m.sala_id = ? order by m.id desc limit ?", (sala_id, limite)).fetchall()
        return [{**dict(l), "pode_apagar": sl.pode_apagar_mensagem(sala, l["autor_id"], uid)} for l in reversed(linhas)]

    def enviar_mensagem(self, sala_id: str, texto: str) -> None:
        uid = self._uid()
        sala = self.obter_sala(sala_id)
        if not sl.chat_ativo(sala):
            raise ErroSalas("Esta sala não tem conversa ativa.")
        if not sl.pode_escrever_no_chat(sala, uid, self._membros_obj(sala_id)):
            raise ErroSalas("Nesta sala só quem a criou escreve na conversa.")
        texto = (texto or "").strip()
        if not 1 <= len(texto) <= 4000:
            raise ErroSalas("A mensagem tem de ter entre 1 e 4000 caracteres.")
        self._db.execute("insert into mensagens (sala_id, autor_id, texto, enviada_em) values (?, ?, ?, ?)",
                         (sala_id, uid, texto, _agora()))
        self._db.commit()

    def apagar_mensagem(self, mensagem_id: int) -> None:
        r = self._db.execute("select sala_id, autor_id from mensagens where id = ?", (mensagem_id,)).fetchone()
        if not r:
            return
        sala = self.obter_sala(r["sala_id"])
        if not sl.pode_apagar_mensagem(sala, r["autor_id"], self._uid()):
            raise ErroSalas("Só podes apagar as tuas mensagens.")
        self._db.execute("delete from mensagens where id = ?", (mensagem_id,))
        self._db.commit()


# ====================================================================== SUPABASE (online)
class ContaPorConfirmar(ErroSalas):
    """A conta foi criada mas o Supabase pede para confirmar o email antes de entrar."""


class BackendSupabase:
    """Usa a API REST do Supabase (Auth, PostgREST, Storage) com httpx. As permissões são aplicadas no servidor
    pelas políticas RLS de supabase/esquema.sql. AINDA NÃO TESTADO com um projeto real."""
    nome = "supabase"

    def __init__(self, url: str, chave_anon: str, sessao: dict):
        import httpx

        self.url = url.rstrip("/")
        self.chave = chave_anon
        self.sessao = sessao  # access_token, refresh_token, utilizador
        self.http = httpx.Client(timeout=30)

    def _cab(self, extra: dict | None = None) -> dict:
        # Com sessão: o token da pessoa. Sem sessão: a chave anon antiga (é um JWT) também vai no Authorization; a chave
        # «publishable» nova (sb_publishable_…) não é um JWT e vai só no apikey.
        token = self.sessao.get("access_token") or (self.chave if self.chave.startswith("eyJ") else None)
        cab = {"apikey": self.chave, "Content-Type": "application/json"}
        if token:
            cab["Authorization"] = f"Bearer {token}"
        cab.update(extra or {})
        return cab

    def _pedido(self, metodo: str, caminho: str, **kw):
        extra = kw.pop("headers", None)
        resposta = self.http.request(metodo, f"{self.url}{caminho}", headers=self._cab(extra), **kw)
        if resposta.status_code == 401 and self.sessao.get("refresh_token"):
            self._renovar()
            resposta = self.http.request(metodo, f"{self.url}{caminho}", headers=self._cab(extra), **kw)
        if resposta.status_code >= 400:
            try:
                detalhe = resposta.json()
                msg = detalhe.get("msg") or detalhe.get("message") or detalhe.get("error_description") or str(detalhe)
            except ValueError:
                msg = resposta.text[:300]
            raise ErroSalas(f"O servidor recusou o pedido: {msg}")
        return resposta.json() if resposta.content else None

    def _guardar_sessao(self, dados: dict) -> None:
        import time

        self.sessao.update({"access_token": dados["access_token"], "refresh_token": dados.get("refresh_token"),
                            "uid": dados["user"]["id"], "email": dados["user"].get("email"),
                            "expira": float(dados.get("expires_at") or time.time() + float(dados.get("expires_in") or 3600))})

    def renovar_se_preciso(self, margem: float = 300) -> bool:
        """Renova a sessão antes de o acesso expirar (1 hora no Supabase). Devolve True se renovou (o refresh token
        mudou: a app guarda o novo no browser)."""
        import time

        if self.sessao.get("refresh_token") and self.sessao.get("expira", 0) - time.time() < margem:
            self._renovar()
            return True
        return False

    def _garantir_perfil(self, dados: dict) -> None:
        """Cria o perfil (nome e vínculo que os colegas das salas veem) se ainda não existir; se existir, fica igual."""
        utilizador = dados.get("user") or {}
        meta = utilizador.get("user_metadata") or {}
        nome = " ".join(str(meta.get("nome") or meta.get("full_name") or meta.get("name")
                            or (utilizador.get("email") or "").split("@")[0]).split())[:80]
        vinculo = meta.get("vinculo") if meta.get("vinculo") in ("Aluno", "Professor") else "Aluno"
        try:
            self._pedido("POST", "/rest/v1/perfis", json={"id": self.sessao["uid"], "nome_completo": nome or "Utilizador",
                                                          "vinculo": vinculo},
                         headers={"Prefer": "resolution=ignore-duplicates,return=minimal"})
        except ErroSalas:
            pass

    def _renovar(self) -> None:
        r = self.http.post(f"{self.url}/auth/v1/token?grant_type=refresh_token",
                           headers={"apikey": self.chave, "Content-Type": "application/json"},
                           json={"refresh_token": self.sessao.get("refresh_token")})
        if r.status_code >= 400:
            self.sessao.clear()
            raise ErroSalas("A sessão expirou. Entra outra vez.")
        self._guardar_sessao(r.json())

    # ------------------------------------------------------------- entrar com Google, Microsoft, Apple, Facebook
    # O Supabase trata do OAuth (PKCE): a app manda o browser para /auth/v1/authorize e, no regresso, troca o
    # «code» pela sessão. Os fornecedores ligam-se no painel do Supabase (Authentication → Providers).
    NOMES_OAUTH = {"google": "google", "microsoft": "azure", "apple": "apple", "facebook": "facebook"}

    def fornecedores_ativos(self) -> list:
        """Fornecedores ligados no Supabase (nomes da app: google, microsoft, apple, facebook)."""
        r = self.http.get(f"{self.url}/auth/v1/settings", headers={"apikey": self.chave})
        externos = (r.json() or {}).get("external", {}) if r.status_code < 400 else {}
        return [f for f, nome_sb in self.NOMES_OAUTH.items() if externos.get(nome_sb)]

    def url_oauth(self, fornecedor: str, redirect_to: str, code_challenge: str) -> str:
        from urllib.parse import urlencode

        return f"{self.url}/auth/v1/authorize?" + urlencode({
            "provider": self.NOMES_OAUTH[fornecedor], "redirect_to": redirect_to,
            "code_challenge": code_challenge, "code_challenge_method": "s256"})

    def entrar_oauth(self, codigo: str, verificador: str) -> dict:
        r = self.http.post(f"{self.url}/auth/v1/token?grant_type=pkce",
                           headers={"apikey": self.chave, "Content-Type": "application/json"},
                           json={"auth_code": codigo, "code_verifier": verificador})
        if r.status_code >= 400:
            raise ErroSalas("Não foi possível entrar com essa conta. Tenta outra vez.")
        dados = r.json()
        self._guardar_sessao(dados)
        self._garantir_perfil(dados)
        return self.atual()

    def entrar_com_refresh(self, refresh_token: str) -> dict:
        """Volta a entrar com a sessão lembrada neste browser (o refresh token muda a cada uso)."""
        self.sessao["refresh_token"] = refresh_token
        self._renovar()
        return self.atual()

    # ------------------------------------------------------------- dados de estudo de cada pessoa (tabela com RLS)
    def dados_ler_todos(self) -> dict:
        linhas = self._pedido("GET", f"/rest/v1/dados_utilizador?uid=eq.{self.sessao['uid']}&select=chave,valor") or []
        return {l["chave"]: l["valor"] for l in linhas}

    def dados_guardar(self, chave: str, valor) -> None:
        self._pedido("POST", "/rest/v1/dados_utilizador", json={"uid": self.sessao["uid"], "chave": chave, "valor": valor},
                     headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def dados_apagar(self, chave: str) -> None:
        from urllib.parse import quote

        self._pedido("DELETE", f"/rest/v1/dados_utilizador?uid=eq.{self.sessao['uid']}&chave=eq.{quote(chave, safe='')}")

    def apagar_conta(self) -> None:
        """Apaga a conta (e, em cascata, os dados, o perfil e as salas que criou) com a função apagar_a_minha_conta."""
        self._pedido("POST", "/rest/v1/rpc/apagar_a_minha_conta", json={})
        self.sessao.clear()

    def registar(self, email, palavra_passe, nome, vinculo) -> dict:
        email, nome = validar_registo(email, palavra_passe, nome, vinculo)
        dados = self._pedido("POST", "/auth/v1/signup", json={"email": email, "password": palavra_passe,
                                                              "data": {"nome": nome, "vinculo": vinculo}})
        if not dados or not dados.get("access_token"):
            raise ContaPorConfirmar("Conta criada. Abre o email que te enviámos, confirma a conta e depois inicia sessão "
                                    "aqui.")
        self._guardar_sessao(dados)
        self._pedido("POST", "/rest/v1/perfis", json={"id": self.sessao["uid"], "nome_completo": nome, "vinculo": vinculo},
                     headers={"Prefer": "resolution=merge-duplicates"})
        return self.atual()

    def entrar(self, email, palavra_passe) -> dict:
        r = self.http.post(f"{self.url}/auth/v1/token?grant_type=password",
                           headers={"apikey": self.chave, "Content-Type": "application/json"},
                           json={"email": (email or "").strip().lower(), "password": palavra_passe})
        if r.status_code >= 400:
            raise ErroSalas("Email ou palavra-passe errados (ou email ainda não confirmado).")
        self._guardar_sessao(r.json())
        self._garantir_perfil(r.json())  # contas confirmadas por email: o perfil ainda não existia
        return self.atual()

    def mudar_palavra_passe(self, atual: str, nova: str) -> None:
        """Muda a palavra-passe no Supabase Auth. Confirma primeiro a atual (entrada com email e palavra-passe, numa
        sessão à parte) e pede a mudança com essa sessão acabada de criar — assim também passa quando o projeto exige
        um início de sessão recente para mudar a palavra-passe. No fim, essa sessão temporária é terminada
        (logout com scope=local: só ela; a sessão desta pessoa continua)."""
        if not self.sessao.get("uid") or not self.sessao.get("email"):
            raise ErroSalas("Inicia sessão primeiro.")
        if len(nova or "") < 8:
            raise ErroSalas("A palavra-passe nova tem de ter pelo menos 8 caracteres.")
        if nova == atual:
            raise ErroSalas("A palavra-passe nova tem de ser diferente da atual.")
        cab = {"apikey": self.chave, "Content-Type": "application/json"}
        r = self.http.post(f"{self.url}/auth/v1/token?grant_type=password", headers=cab,
                           json={"email": self.sessao["email"], "password": atual or ""})
        if r.status_code >= 400:
            raise ErroSalas("A palavra-passe atual não está certa.")
        temp = {**cab, "Authorization": f"Bearer {r.json().get('access_token')}"}
        try:
            resp = self.http.request("PUT", f"{self.url}/auth/v1/user", headers=temp,
                                     json={"password": nova, "current_password": atual})
            if resp.status_code >= 400:
                try:
                    d = resp.json()
                    msg = d.get("msg") or d.get("message") or d.get("error_description") or str(d)
                except ValueError:
                    msg = resp.text[:300]
                raise ErroSalas(f"O servidor recusou a mudança: {msg}")
        finally:  # a sessão criada só para confirmar não fica aberta
            try:
                self.http.post(f"{self.url}/auth/v1/logout?scope=local", headers=temp)
            except Exception:  # noqa: BLE001
                pass

    def sair(self) -> None:
        if self.sessao.get("access_token"):  # termina também no servidor (o refresh token deixa de valer)
            try:
                self.http.post(f"{self.url}/auth/v1/logout", headers=self._cab())
            except Exception:  # noqa: BLE001
                pass
        self.sessao.clear()

    def atual(self) -> dict | None:
        if not self.sessao.get("uid"):
            return None
        if "perfil" not in self.sessao:
            linhas = self._pedido("GET", f"/rest/v1/perfis?id=eq.{self.sessao['uid']}&select=nome_completo,vinculo,foto_b64") or []
            self.sessao["perfil"] = linhas[0] if linhas else {"nome_completo": self.sessao.get("email", ""), "vinculo": "Aluno"}
        p = self.sessao["perfil"]
        import base64
        return {"id": self.sessao["uid"], "email": self.sessao.get("email"), "nome": p["nome_completo"], "vinculo": p["vinculo"],
                "foto": base64.b64decode(p["foto_b64"]) if p.get("foto_b64") else None}

    def mudar_perfil(self, nome=None, foto=None, apagar_foto=False) -> dict:
        campos = {}
        if nome is not None:
            nome = " ".join(str(nome).split())
            if not 2 <= len(nome) <= 80:
                raise ErroSalas("O nome tem de ter entre 2 e 80 caracteres.")
            campos["nome_completo"] = nome
        if foto is not None or apagar_foto:
            import base64
            campos["foto_b64"] = None if apagar_foto else base64.b64encode(foto).decode()
        if campos:
            self._pedido("PATCH", f"/rest/v1/perfis?id=eq.{self.sessao['uid']}", json=campos)
            self.sessao.pop("perfil", None)
        return self.atual()

    def mudar_vinculo(self, vinculo: str) -> dict:
        if vinculo not in ("Aluno", "Professor"):
            raise ErroSalas("Escolhe se és aluno ou professor.")
        self._pedido("PATCH", f"/rest/v1/perfis?id=eq.{self.sessao['uid']}", json={"vinculo": vinculo})
        self.sessao.pop("perfil", None)
        return self.atual()

    def _com_icone(self, metodo: str, caminho: str, corpo: dict, **kw):
        """Envia a sala com o ícone; se o projeto do Supabase ainda não tiver a coluna «icone» (esquema.sql antigo),
        volta a enviar sem ela — a sala fica criada/guardada e o ícone passa a ser o sugerido pelo nome."""
        if getattr(self, "_sem_coluna_icone", False):
            corpo = {k: v for k, v in corpo.items() if k != "icone"}
        try:
            return self._pedido(metodo, caminho, json=corpo, **kw)
        except ErroSalas as erro:
            if "icone" not in str(erro) or "icone" not in corpo:
                raise
            self._sem_coluna_icone = True
            return self._pedido(metodo, caminho, json={k: v for k, v in corpo.items() if k != "icone"}, **kw)

    def criar_sala(self, nome, chat_ativo=None, cadeira=None, **definicoes) -> dict:
        u = self.atual()
        tipo = sl.tipo_de_sala_permitido(u["vinculo"])
        try:
            d = sl.validar_definicoes(definicoes, sl.definicoes_padrao(tipo, chat_ativo))
        except sl.ErroDefinicoes as erro:
            raise ErroSalas(str(erro)) from None
        corpo = {"nome": validar_nome_sala(nome), "tipo": tipo, "cadeira": cadeira if tipo == "cadeira" else None,
                 "criador_id": u["id"], "codigo": sl.gerar_codigo(), "chat_ativo": d["chat_modo"] != "desligado",
                 **{k: d[k] for k in sl.CAMPOS_DEFINICOES if k != "nome"}}
        sala = self._com_icone("POST", "/rest/v1/salas", corpo, headers={"Prefer": "return=representation"})[0]
        self._pedido("POST", "/rest/v1/membros", json={"sala_id": sala["id"], "utilizador_id": u["id"], "papel": "criador"})
        return self.obter_sala(sala["id"])

    def entrar_com_codigo(self, codigo) -> dict:
        sala_id = self._pedido("POST", "/rest/v1/rpc/entrar_com_codigo", json={"p_codigo": sl.normalizar_codigo(codigo)})
        return self.obter_sala(sala_id)

    def _completar(self, sala: dict, papel: str, n_membros: int) -> dict:
        uid = self.sessao.get("uid")
        d = {**sl.definicoes_padrao(sala.get("tipo", "grupo_estudo")), **{k: v for k, v in sala.items() if v is not None}}
        d["ferramentas_lab"] = [f for f in (d.get("ferramentas_lab") or []) if f in sl.FERRAMENTAS_LAB]
        d["laboratorio"] = bool(d.get("laboratorio"))
        d.update(papel=papel, n_membros=n_membros, e_criador=d.get("criador_id") == uid, chat_ativo=sl.chat_ativo(d),
                 n_documentos=d.get("n_documentos", 0))
        if not sl.pode_ver_convite(d, uid):
            d["codigo"] = None
        return d

    def minhas_salas(self) -> list[dict]:
        linhas = self._pedido("GET", f"/rest/v1/membros?utilizador_id=eq.{self.sessao['uid']}&select=papel,salas(*)") or []
        ids = [l["salas"]["id"] for l in linhas if l.get("salas")]
        contagem = {}
        if ids:
            for m in self._pedido("GET", f"/rest/v1/membros?sala_id=in.({','.join(ids)})&select=sala_id") or []:
                contagem[m["sala_id"]] = contagem.get(m["sala_id"], 0) + 1
        return [self._completar(l["salas"], l["papel"], contagem.get(l["salas"]["id"], 1)) for l in linhas if l.get("salas")]

    def obter_sala(self, sala_id) -> dict:
        salas = [s for s in self.minhas_salas() if s["id"] == sala_id]
        if not salas:
            raise ErroSalas("Esta sala não existe ou não és membro.")
        return salas[0]

    def atualizar_sala(self, sala_id, nome=None, chat_ativo=None, **definicoes) -> dict:
        sala = self.obter_sala(sala_id)
        if not sala["e_criador"]:
            raise ErroSalas("Só quem criou a sala a pode configurar.")
        campos = dict(definicoes)
        if nome is not None:
            campos["nome"] = nome
        if chat_ativo is not None and "chat_modo" not in campos:
            campos["chat_modo"] = ("todos" if sala["chat_modo"] == "desligado" else sala["chat_modo"]) if chat_ativo else "desligado"
        try:
            novo = sl.validar_definicoes(campos, sala)
        except sl.ErroDefinicoes as erro:
            raise ErroSalas(str(erro)) from None
        enviar = {k: novo[k] for k in sl.CAMPOS_DEFINICOES}
        enviar["chat_ativo"] = novo["chat_modo"] != "desligado"
        self._com_icone("PATCH", f"/rest/v1/salas?id=eq.{sala_id}", enviar)
        return self.obter_sala(sala_id)

    def novo_codigo(self, sala_id) -> str:
        codigo = sl.gerar_codigo()
        self._pedido("PATCH", f"/rest/v1/salas?id=eq.{sala_id}", json={"codigo": codigo})
        return codigo

    def apagar_sala(self, sala_id) -> None:
        self._pedido("DELETE", f"/rest/v1/salas?id=eq.{sala_id}")

    def sair_da_sala(self, sala_id) -> None:
        self._pedido("DELETE", f"/rest/v1/membros?sala_id=eq.{sala_id}&utilizador_id=eq.{self.sessao['uid']}")

    def remover_membro(self, sala_id, utilizador_id) -> None:
        self._pedido("DELETE", f"/rest/v1/membros?sala_id=eq.{sala_id}&utilizador_id=eq.{utilizador_id}")

    def membros(self, sala_id) -> list[dict]:
        import base64
        linhas = self._pedido("GET", f"/rest/v1/membros?sala_id=eq.{sala_id}&select=utilizador_id,papel,entrou_em,"
                                     "perfis(nome_completo,foto_b64)") or []
        saida = []
        for l in linhas:
            p = l.get("perfis") or {}
            saida.append({"utilizador_id": l["utilizador_id"], "papel": l["papel"], "entrou_em": l.get("entrou_em"),
                          "nome": p.get("nome_completo", "?"), "foto": base64.b64decode(p["foto_b64"]) if p.get("foto_b64") else None})
        return saida

    def enviar_ficheiro(self, sala_id, nome, dados, tipo_mime, pasta_fixa, texto) -> dict:
        sala = self.obter_sala(sala_id)
        if pasta_fixa and not sl.pode_partilhar(sala, self.sessao.get("uid")):
            raise ErroSalas("Nesta sala só quem a criou pode pôr documentos nos materiais.")
        if not pasta_fixa and not sl.pode_ter_privados(sala):
            raise ErroSalas("Esta sala não tem ficheiros privados.")
        caminho = f"{sala_id}/{self.sessao['uid']}/{uuid.uuid4().hex[:8]}_{re.sub(r'[^A-Za-z0-9._-]', '_', nome)}"
        r = self.http.post(f"{self.url}/storage/v1/object/salas/{caminho}", content=dados,
                           headers={"apikey": self.chave, "Authorization": f"Bearer {self.sessao.get('access_token')}",
                                    "Content-Type": tipo_mime or "application/octet-stream"})
        if r.status_code >= 400:
            raise ErroSalas("Não foi possível guardar o ficheiro no servidor.")
        linha = self._pedido("POST", "/rest/v1/ficheiros", headers={"Prefer": "return=representation"},
                             json={"sala_id": sala_id, "dono_id": self.sessao["uid"], "nome": nome, "caminho_storage": caminho,
                                   "tipo_mime": tipo_mime, "pasta_fixa": bool(pasta_fixa), "texto_extraido": texto})[0]
        return linha

    def ficheiros(self, sala_id) -> list[dict]:
        sala = self.obter_sala(sala_id)
        uid = self.sessao.get("uid")
        linhas = self._pedido("GET", f"/rest/v1/ficheiros?sala_id=eq.{sala_id}&order=enviado_em.asc"
                                     "&select=id,nome,dono_id,pasta_fixa,tipo_mime,texto_extraido,enviado_em,caminho_storage,"
                                     "perfis(nome_completo)") or []
        return [{**l, "dono_nome": (l.pop("perfis", None) or {}).get("nome_completo", "?"),
                 "pode_apagar": sl.pode_apagar_ficheiro(sala, l["dono_id"], uid)} for l in linhas]

    def dados_ficheiro(self, ficheiro_id) -> bytes:
        linhas = self._pedido("GET", f"/rest/v1/ficheiros?id=eq.{ficheiro_id}&select=caminho_storage") or []
        if not linhas:
            raise ErroSalas("Sem acesso a este ficheiro.")
        r = self.http.get(f"{self.url}/storage/v1/object/salas/{linhas[0]['caminho_storage']}",
                          headers={"apikey": self.chave, "Authorization": f"Bearer {self.sessao.get('access_token')}"})
        if r.status_code >= 400:
            raise ErroSalas("Não foi possível descarregar o ficheiro.")
        return r.content

    def apagar_ficheiro(self, ficheiro_id) -> None:
        self._pedido("DELETE", f"/rest/v1/ficheiros?id=eq.{ficheiro_id}")

    def mensagens(self, sala_id, limite=200) -> list[dict]:
        sala = self.obter_sala(sala_id)
        uid = self.sessao.get("uid")
        linhas = self._pedido("GET", f"/rest/v1/mensagens?sala_id=eq.{sala_id}&order=enviada_em.desc&limit={limite}"
                                     "&select=id,autor_id,texto,enviada_em,perfis(nome_completo)") or []
        return [{**l, "autor_nome": (l.pop("perfis", None) or {}).get("nome_completo", "?"),
                 "pode_apagar": sl.pode_apagar_mensagem(sala, l["autor_id"], uid)} for l in reversed(linhas)]

    def enviar_mensagem(self, sala_id, texto) -> None:
        texto = (texto or "").strip()
        if not 1 <= len(texto) <= 4000:
            raise ErroSalas("A mensagem tem de ter entre 1 e 4000 caracteres.")
        self._pedido("POST", "/rest/v1/mensagens", json={"sala_id": sala_id, "autor_id": self.sessao["uid"], "texto": texto})

    def apagar_mensagem(self, mensagem_id) -> None:
        self._pedido("DELETE", f"/rest/v1/mensagens?id=eq.{mensagem_id}")
