"""
Início de sessão do Mondego IA (como nas outras apps): Google, Microsoft ou Facebook pelo login nativo do Streamlit
(OpenID Connect) e conta com email e palavra-passe.

Aqui ficam as partes sem Streamlit (testes_inicio_sessao.py): validar as credenciais do Google e guardá-las em
.streamlit/secrets.toml sem estragar o que já lá estiver (outras secções, como [blender]).
O secrets.toml tem segredos: nunca é partilhado nem entra na exportação dos dados.
"""
from __future__ import annotations

import copy
import json
import re
import secrets

REDIRECT_PADRAO = "http://localhost:8501/oauth2callback"
GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"
# contas pessoais da Microsoft (Outlook, Hotmail, Live): o «consumers» tem um emissor fixo, que o Authlib valida
MICROSOFT_METADATA = "https://login.microsoftonline.com/consumers/v2.0/.well-known/openid-configuration"
# O Streamlit só aceita fornecedores OpenID Connect; o Facebook e o Apple entram através do Auth0 (plano grátis), que
# leva diretamente à ligação certa («connection»).
FORNECEDORES = {"google": "Google", "microsoft": "Microsoft", "apple": "Apple", "facebook": "Facebook"}
PELO_AUTH0 = ("apple", "facebook")


def ler_toml(texto: str) -> dict:
    if not (texto or "").strip():
        return {}
    try:
        import tomllib  # Python 3.11 ou mais recente
    except ModuleNotFoundError:  # Python 3.10
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            import toml as tomllib
    return tomllib.loads(texto)


def validar_google(client_id: str, client_secret: str) -> str | None:
    """Mensagem de erro pronta a mostrar, ou None se estiver tudo bem."""
    if not re.fullmatch(r"[\w.-]+\.apps\.googleusercontent\.com", (client_id or "").strip()):
        return "O ID do cliente da Google acaba em «.apps.googleusercontent.com». Copia-o outra vez da consola da Google."
    if len((client_secret or "").strip()) < 10 or " " in (client_secret or "").strip():
        return "Falta o segredo do cliente (copia-o da mesma página da consola da Google)."
    return None


def dominio_auth0(texto: str) -> str:
    """«https://o-meu.eu.auth0.com/» → «o-meu.eu.auth0.com»."""
    return re.sub(r"^https?://", "", (texto or "").strip()).strip("/ ")


def validar(fornecedor: str, client_id: str, client_secret: str, dominio: str = "") -> str | None:
    """Mensagem de erro pronta a mostrar, ou None se estiver tudo bem."""
    cid, segredo = (client_id or "").strip(), (client_secret or "").strip()
    if fornecedor == "google":
        return validar_google(cid, segredo)
    if fornecedor == "microsoft" and not re.fullmatch(r"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", cid):
        return "O ID da aplicação (cliente) da Microsoft tem este formato: 1a2b3c4d-1234-5678-9abc-1234567890ab."
    if fornecedor in PELO_AUTH0:
        if not re.fullmatch(r"[\w-]+(\.[\w-]+)*\.auth0\.com", dominio_auth0(dominio)):
            return "O domínio do Auth0 acaba em «.auth0.com» (por exemplo, o-teu-nome.eu.auth0.com)."
        if len(cid) < 10 or " " in cid:
            return "Falta o Client ID da aplicação do Auth0."
    if len(segredo) < 10 or " " in segredo:
        return "Falta o segredo do cliente (copia-o da mesma página)."
    return None


def com_fornecedor(config: dict, fornecedor: str, client_id: str, client_secret: str, dominio: str = "",
                   redirect_uri: str | None = None) -> dict:
    """Configuração com o fornecedor ligado. Mantém o resto; cria o cookie_secret se faltar (ou se for o do exemplo)."""
    c = copy.deepcopy(config or {})
    auth = c.setdefault("auth", {})
    if not auth.get("redirect_uri") or redirect_uri:
        auth["redirect_uri"] = redirect_uri or REDIRECT_PADRAO
    if len(str(auth.get("cookie_secret") or "")) < 32 or "escreve-aqui" in str(auth.get("cookie_secret")):
        auth["cookie_secret"] = secrets.token_hex(32)
    dados = {"client_id": client_id.strip(), "client_secret": client_secret.strip()}
    if fornecedor == "google":
        dados["server_metadata_url"] = GOOGLE_METADATA  # o Streamlit já pede «escolher conta» (prompt=select_account)
    elif fornecedor == "microsoft":
        dados["server_metadata_url"] = MICROSOFT_METADATA
    elif fornecedor in PELO_AUTH0:
        dados["server_metadata_url"] = f"https://{dominio_auth0(dominio)}/.well-known/openid-configuration"
        dados["client_kwargs"] = {"scope": "openid profile email", "prompt": "login", "connection": fornecedor}
    else:
        raise ValueError(f"Fornecedor desconhecido: {fornecedor}")
    auth[fornecedor] = dados
    return c


def com_google(config: dict, client_id: str, client_secret: str, redirect_uri: str | None = None) -> dict:
    return com_fornecedor(config, "google", client_id, client_secret, redirect_uri=redirect_uri)


def dados_auth0(config: dict) -> dict:
    """Domínio e Client ID do Auth0 já guardados (para não os escrever duas vezes no Facebook e no Apple)."""
    for f in PELO_AUTH0:
        d = ((config or {}).get("auth") or {}).get(f) or {}
        m = re.match(r"https://([^/]+)/", str(d.get("server_metadata_url") or ""))
        if m and d.get("client_id"):
            return {"dominio": m.group(1), "client_id": d["client_id"]}
    return {}


def _chave(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def _valor(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_valor(x) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)  # as strings do JSON são strings básicas válidas em TOML


def para_toml(dados: dict, _prefixo: str = "") -> str:
    """TOML simples (texto, números, verdadeiro/falso, listas e tabelas), que o tomllib volta a ler igual."""
    linhas = [f"{_chave(k)} = {_valor(v)}" for k, v in dados.items() if not isinstance(v, dict)]
    for k, v in dados.items():
        if isinstance(v, dict):
            nome = f"{_prefixo}.{_chave(k)}" if _prefixo else _chave(k)
            corpo = para_toml(v, nome)
            linhas += (["", f"[{nome}]"] + ([corpo] if corpo else []))
    return "\n".join(linhas).strip("\n") + ("\n" if not _prefixo else "")


def fornecedores_configurados(config: dict) -> list:
    """Que fornecedores têm credenciais a sério (não os «...» do exemplo)."""
    auth = (config or {}).get("auth") or {}
    return [f for f, d in auth.items() if isinstance(d, dict) and d.get("client_id") and "..." not in str(d.get("client_id"))]


# ---------------------------------------------------------------- sessões lembradas por browser
class SessoesLembradas:
    """«Manter a sessão iniciada»: cada browser (telemóvel, tablet, computador) guarda um código aleatório num cookie e
    aqui fica só o resumo (hash) desse código com a conta. Assim cada dispositivo tem a sua sessão (antes ficava
    lembrada para o computador inteiro). Termina ao fim de 30 dias ou em «Terminar sessão»."""

    def __init__(self, caminho):
        import sqlite3

        self._db = sqlite3.connect(str(caminho), check_same_thread=False)
        self._db.execute("create table if not exists sessoes_lembradas (hash text primary key, dados text not null, "
                         "uid text, expira real not null)")
        self._db.commit()

    @staticmethod
    def _hash(token: str) -> str:
        import hashlib

        return hashlib.sha256((token or "").encode()).hexdigest()

    def criar(self, dados: dict, dias: int = 30) -> str:
        import time

        token = secrets.token_urlsafe(32)
        self._db.execute("insert into sessoes_lembradas (hash, dados, uid, expira) values (?, ?, ?, ?)",
                         (self._hash(token), json.dumps(dados), str(dados.get("uid") or ""), time.time() + dias * 86400))
        self._db.commit()
        return token

    def obter(self, token: str) -> dict | None:
        import time

        if not token:
            return None
        linha = self._db.execute("select dados, expira from sessoes_lembradas where hash = ?", (self._hash(token),)).fetchone()
        if not linha:
            return None
        if linha[1] < time.time():
            self.apagar(token)
            return None
        return json.loads(linha[0])

    def atualizar(self, token: str, dados: dict) -> None:
        self._db.execute("update sessoes_lembradas set dados = ? where hash = ?", (json.dumps(dados), self._hash(token)))
        self._db.commit()

    def apagar(self, token: str) -> None:
        self._db.execute("delete from sessoes_lembradas where hash = ?", (self._hash(token),))
        self._db.commit()

    def apagar_da_conta(self, uid: str) -> None:
        self._db.execute("delete from sessoes_lembradas where uid = ?", (str(uid),))
        self._db.commit()

    def contar(self, uid: str) -> int:
        """Quantos browsers (dispositivos) têm a sessão desta conta lembrada e ainda válida."""
        import time

        if not uid:
            return 0
        return self._db.execute("select count(*) from sessoes_lembradas where uid = ? and expira >= ?",
                                (str(uid), time.time())).fetchone()[0]

    def apagar_outras(self, uid: str, token: str | None) -> int:
        """Termina a sessão desta conta em todos os outros browsers (fica só a do «token»). Devolve quantas saíram."""
        if not uid:
            return 0
        antes = self._db.execute("select count(*) from sessoes_lembradas where uid = ?", (str(uid),)).fetchone()[0]
        self._db.execute("delete from sessoes_lembradas where uid = ? and hash != ?", (str(uid), self._hash(token or "")))
        self._db.commit()
        return antes - self._db.execute("select count(*) from sessoes_lembradas where uid = ?", (str(uid),)).fetchone()[0]


NOME_COOKIE = "mondego_sessao"        # contas neste computador: código aleatório (ver SessoesLembradas)
NOME_COOKIE_NUVEM = "mondego_sb"       # contas no Supabase: o refresh token (codificado), que muda a cada uso
NOME_COOKIE_PKCE = "mondego_pkce"     # só durante a ida ao Google…: que verificador usar no regresso (15 min)


def js_cookie(token: str | None, dias: float = 30, nome: str = NOME_COOKIE) -> str:
    """Script que guarda (ou apaga, com token None) um cookie da sessão no browser. Corre num iframe da mesma origem
    (components.html), por isso escreve no documento da app."""
    valor, idade = (token, int(dias * 86400)) if token else ("", 0)
    if not re.fullmatch(r"[A-Za-z0-9_-]*", valor) or not re.fullmatch(r"[a-z_]+", nome):
        raise ValueError("código de sessão inválido")
    linha = f"{nome}={valor}; Max-Age={idade}; Path=/; SameSite=Lax"
    return ("<script>(function(){var s=location.protocol==='https:'?'; Secure':'';"
            f"var c='{linha}'+s;try{{window.parent.document.cookie=c;}}catch(e){{document.cookie=c;}}}})();</script>")


def codificar(texto: str) -> str:
    """Texto qualquer → só letras, números, «-» e «_» (para caber num cookie)."""
    import base64

    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def descodificar(texto: str) -> str | None:
    import base64

    try:
        return base64.urlsafe_b64decode((texto or "") + "=" * (-len(texto or "") % 4)).decode()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- PKCE (entrar com Google… pelo Supabase)
APAGAR_NUVEM: set = set()    # (conta, ficheiro) apagado aqui sem ligação: apaga online na próxima entrada
PENDENTES_NUVEM: set = set()  # (conta, ficheiro) que não foi possível enviar (sem ligação): volta a tentar
CACHE_FORNECEDORES: dict = {}  # endereço do Supabase → (quando, fornecedores ligados)
PKCE: dict = {}  # estado → (verificador, quando); fica na memória do servidor entre a ida e o regresso do Google


def novo_pkce() -> tuple[str, str, str]:
    """(estado, verificador, desafio S256). O verificador nunca sai do servidor."""
    import base64
    import hashlib
    import time

    for e in [e for e, (_, t) in PKCE.items() if time.time() - t > 900]:  # esquece os que têm mais de 15 min
        PKCE.pop(e, None)
    estado, verificador = secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    PKCE[estado] = (verificador, time.time())
    return estado, verificador, desafio


def caminho_seguro(base, chave: str):
    """Caminho dentro de «base» para uma chave vinda do servidor (ex.: dados/algebra.json), ou None se não for seguro."""
    from pathlib import Path

    if not chave or ".." in chave.replace("\\", "/").split("/") or chave.startswith(("/", "\\")) or not chave.endswith(".json"):
        return None
    alvo = (Path(base) / chave).resolve()
    try:
        alvo.relative_to(Path(base).resolve())
    except ValueError:
        return None
    return alvo


# ---------------------------------------------------------------- administradores e dados antigos
def e_admin(email: str | None, admins: list) -> bool:
    return bool(email) and email.strip().lower() in {str(a).strip().lower() for a in admins or []}


def migrar_dados_antigos(pasta, destino) -> bool:
    """Os dados de antes das contas (perfil, cadeiras, avaliações e cópias, na pasta da app) passam para a pasta da
    conta. Copia primeiro; só depois guarda os originais em «antes_das_contas» (nada se perde)."""
    import shutil
    from pathlib import Path

    pasta, destino = Path(pasta), Path(destino)
    itens = [n for n in ("perfil.json", "avaliacoes.json", "dados", "backup") if (pasta / n).exists()]
    if not itens or (destino / "perfil.json").exists():
        return False
    destino.mkdir(parents=True, exist_ok=True)
    for n in itens:
        origem = pasta / n
        if origem.is_dir():
            shutil.copytree(origem, destino / n, dirs_exist_ok=True)
        else:
            shutil.copy2(origem, destino / n)
    guarda = pasta / "antes_das_contas"
    guarda.mkdir(exist_ok=True)
    for n in itens:
        shutil.move(str(pasta / n), str(guarda / n))
    return True


# ---------------------------------------------------------------- importar os dados de outro computador (.zip)
LIMITE_IMPORTAR = 60 * 1024 * 1024  # 60 MB descomprimidos (os documentos das cadeiras vão em texto)


class ErroImportar(ValueError):
    pass


def ler_zip_dados(conteudo: bytes, preferencias=("tema", "velocidade", "idioma", "web")) -> dict:
    """Lê o .zip de «Descarregar todos os meus dados» e devolve {"ficheiros": {caminho: dados}, "preferencias": {...},
    "ignorados": [...]}. Só aceita o que a app escreve: perfil.json, avaliacoes.json, dados/<cadeira>.json e as
    preferências do config.json (nunca chaves). Recusa o .zip todo se alguma coisa não estiver certa."""
    import io
    import json
    import re
    import zipfile

    try:
        z = zipfile.ZipFile(io.BytesIO(conteudo))
    except (zipfile.BadZipFile, ValueError) as e:
        raise ErroImportar("Este ficheiro não é um .zip.") from e
    infos = [i for i in z.infolist() if not i.is_dir()]
    if sum(i.file_size for i in infos) > LIMITE_IMPORTAR:
        raise ErroImportar("O .zip é grande demais (mais de 60 MB depois de aberto).")
    ficheiros, prefs, ignorados = {}, {}, []
    for i in infos:
        nome = i.filename.replace("\\", "/")
        if nome in ("perfil.json", "avaliacoes.json", "config.json", "laboratorio.json") or re.fullmatch(r"dados/[\w\- ]+\.json", nome):
            try:
                dados = json.loads(z.read(i).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ErroImportar(f"O ficheiro «{nome}» do .zip está danificado.") from e
            if nome == "config.json":
                if isinstance(dados, dict):
                    prefs = {k: v for k, v in dados.items() if k in preferencias}
                continue
            certo = (isinstance(dados, dict) if nome in ("perfil.json", "laboratorio.json")
                     else isinstance(dados, list) if nome == "avaliacoes.json"
                     else isinstance(dados, dict) and isinstance(dados.get("nome"), str) and dados["nome"].strip())
            if not certo:
                raise ErroImportar(f"O ficheiro «{nome}» não tem o formato da app.")
            ficheiros[nome] = dados
        else:
            ignorados.append(nome)
    if "perfil.json" not in ficheiros:
        raise ErroImportar("Este .zip não tem o perfil (perfil.json). Usa o ficheiro de «Descarregar todos os meus dados».")
    return {"ficheiros": ficheiros, "preferencias": prefs, "ignorados": ignorados}


def chave_secreta(chave: str | None) -> bool:
    """A chave do Supabase é a secreta (service_role / sb_secret_…)? Essa nunca pode estar na app: dá acesso a tudo."""
    import base64
    import json

    chave = (chave or "").strip()
    if chave.startswith("sb_secret_"):
        return True
    partes = chave.split(".")
    if len(partes) == 3 and chave.startswith("eyJ"):
        try:
            dados = json.loads(base64.urlsafe_b64decode(partes[1] + "=" * (-len(partes[1]) % 4)))
            return dados.get("role") == "service_role"
        except (ValueError, UnicodeDecodeError):
            return False
    return False
