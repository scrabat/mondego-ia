"""Testes do início de sessão (py -3.14 testes_inicio_sessao.py). Não precisam de internet."""
import tomllib

import inicio_sessao as isess

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


ID = "123456789-abcdefg.apps.googleusercontent.com"
ok("Validar: aceita um ID do cliente da Google e um segredo", isess.validar_google(ID, "GOCSPX-segredo123") is None)
ok("Validar: recusa IDs que não são da Google e segredos vazios",
   isess.validar_google("o-meu-id", "GOCSPX-segredo123") and isess.validar_google(ID, "")
   and isess.validar_google(ID, "tem espaços no meio"))

existente = {"auth": {"redirect_uri": "http://localhost:8501/oauth2callback",
                      "cookie_secret": "escreve-aqui-um-texto-aleatorio-comprido",
                      "auth0": {"client_id": "abc", "client_secret": "def", "server_metadata_url": "https://x.eu.auth0.com/m",
                                "client_kwargs": {"prompt": "login"}}},
             "blender": {"url": "https://blender.exemplo", "token": "t"}}
novo = isess.com_google(existente, f"  {ID} ", " GOCSPX-segredo123 ")
ok("Juntar o Google: guarda o ID e o segredo (sem espaços) com o endereço da Google",
   novo["auth"]["google"] == {"client_id": ID, "client_secret": "GOCSPX-segredo123",
                              "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration"})
ok("Juntar o Google: mantém as outras secções e fornecedores (Blender, Auth0) e não mexe no original",
   novo["blender"] == existente["blender"] and novo["auth"]["auth0"] == existente["auth"]["auth0"]
   and "google" not in existente["auth"])
ok("Juntar o Google: troca o cookie_secret do exemplo por um aleatório comprido",
   len(novo["auth"]["cookie_secret"]) == 64 and "escreve-aqui" not in novo["auth"]["cookie_secret"])
bom = isess.com_google({"auth": {"cookie_secret": "x" * 40}}, ID, "GOCSPX-segredo123")
ok("Juntar o Google: mantém um cookie_secret que já seja bom e põe o endereço de volta por defeito",
   bom["auth"]["cookie_secret"] == "x" * 40 and bom["auth"]["redirect_uri"] == isess.REDIRECT_PADRAO)
texto = isess.para_toml(novo)
ok("TOML: o ficheiro escrito volta a ler-se igual (tabelas, subtabelas e texto com aspas)",
   tomllib.loads(texto) == novo and tomllib.loads(isess.para_toml({"a": {"b": 'texto com "aspas" e \\ barra', "n": 3, "s": True}}))
   == {"a": {"b": 'texto com "aspas" e \\ barra', "n": 3, "s": True}})
ok("TOML: começa pelas chaves simples e cada tabela tem o seu cabeçalho",
   "[auth]" in texto and "[auth.google]" in texto and "[blender]" in texto and texto.endswith("\n"))
ok("Fornecedores: só contam os que têm credenciais a sério (não os «...» do exemplo)",
   isess.fornecedores_configurados(novo) == ["auth0", "google"]
   and isess.fornecedores_configurados({"auth": {"google": {"client_id": "....apps.googleusercontent.com"}}}) == []
   and isess.fornecedores_configurados({}) == [])
ok("Ler TOML vazio não rebenta", isess.ler_toml("") == {} and isess.ler_toml("  \n") == {})
MS = "1a2b3c4d-1234-5678-9abc-1234567890ab"
ms = isess.com_fornecedor({}, "microsoft", MS, "segredo~microsoft")
ok("Microsoft: contas pessoais (consumers), com o ID no formato da Microsoft",
   ms["auth"]["microsoft"]["server_metadata_url"].startswith("https://login.microsoftonline.com/consumers/v2.0/")
   and isess.validar("microsoft", MS, "segredo~microsoft") is None and isess.validar("microsoft", "abc", "segredo~microsoft"))
fb = isess.com_fornecedor(ms, "facebook", "AbCdEfGhIj123", "segredo-auth0-123", "https://mondego.eu.auth0.com/")
ok("Facebook pelo Auth0: endereço do domínio e vai direto à ligação «facebook» (mantém a Microsoft)",
   fb["auth"]["facebook"]["server_metadata_url"] == "https://mondego.eu.auth0.com/.well-known/openid-configuration"
   and fb["auth"]["facebook"]["client_kwargs"]["connection"] == "facebook" and "microsoft" in fb["auth"])
ok("Apple pelo Auth0: reaproveita o domínio e o Client ID já guardados", isess.dados_auth0(fb)
   == {"dominio": "mondego.eu.auth0.com", "client_id": "AbCdEfGhIj123"}
   and isess.com_fornecedor(fb, "apple", "AbCdEfGhIj123", "segredo-auth0-123", "mondego.eu.auth0.com")["auth"]["apple"]
   ["client_kwargs"]["connection"] == "apple")
ok("Auth0: recusa domínios que não são do Auth0", isess.validar("facebook", "AbCdEfGhIj123", "segredo-auth0-123", "google.com")
   and isess.validar("apple", "AbCdEfGhIj123", "segredo-auth0-123", "mondego.eu.auth0.com") is None)
ok("TOML com tabelas dentro de tabelas (client_kwargs) volta a ler-se igual", tomllib.loads(isess.para_toml(fb)) == fb)
import json, tempfile, time
from pathlib import Path
pasta = Path(tempfile.mkdtemp())
sl = isess.SessoesLembradas(pasta / "s.sqlite")
t1 = sl.criar({"backend": "local", "uid": "ana"}); t2 = sl.criar({"backend": "local", "uid": "rui"})
ok("Sessões por browser: cada código dá a sua conta e o código não fica guardado (só o resumo)",
   sl.obter(t1)["uid"] == "ana" and sl.obter(t2)["uid"] == "rui" and t1 != t2 and sl.obter("inventado") is None
   and t1 not in json.dumps(sl._db.execute("select * from sessoes_lembradas").fetchall()))
sl.apagar(t1)
ok("Terminar sessão apaga só a sessão desse browser", sl.obter(t1) is None and sl.obter(t2)["uid"] == "rui")
t3 = sl.criar({"backend": "local", "uid": "rui"}, dias=0); sl._db.execute("update sessoes_lembradas set expira = ?", (time.time() - 1,))
ok("Sessões expiradas não entram", sl.obter(t3) is None)
t4 = sl.criar({"backend": "local", "uid": "rui"}); sl.apagar_da_conta("rui")
ok("Apagar a conta apaga as sessões dela em todos os browsers", sl.obter(t4) is None)
ok("Cookie: guarda o código com validade, apaga com Max-Age=0 e recusa códigos estranhos",
   "mondego_sessao=abc_D-9; Max-Age=2592000; Path=/; SameSite=Lax" in isess.js_cookie("abc_D-9")
   and "mondego_sessao=; Max-Age=0" in isess.js_cookie(None))
try:
    isess.js_cookie("a'; alert(1)//"); ok("Cookie: código com aspas é recusado", False)
except ValueError:
    ok("Cookie: código com aspas é recusado", True)
ok("Administradores: compara emails sem maiúsculas nem espaços", isess.e_admin(" Miguel@UC.pt", ["miguel@uc.pt"])
   and not isess.e_admin("ana@uc.pt", ["miguel@uc.pt"]) and not isess.e_admin(None, ["x"]) and not isess.e_admin("a@b.pt", []))
app = Path(tempfile.mkdtemp())
(app / "perfil.json").write_text('{"nome": "Miguel"}'); (app / "dados").mkdir(); (app / "dados" / "algebra.json").write_text("{}")
(app / "avaliacoes.json").write_text("[]")
ok("Dados antigos: passam para a pasta da conta e os originais ficam guardados em «antes_das_contas»",
   isess.migrar_dados_antigos(app, app / "utilizadores" / "u1")
   and json.loads((app / "utilizadores" / "u1" / "perfil.json").read_text())["nome"] == "Miguel"
   and (app / "utilizadores" / "u1" / "dados" / "algebra.json").exists() and not (app / "perfil.json").exists()
   and (app / "antes_das_contas" / "perfil.json").exists())
ok("Dados antigos: só uma vez (sem dados na pasta da app não faz nada)", not isess.migrar_dados_antigos(app, app / "utilizadores" / "u2"))
import io, zipfile


def zip_(**ficheiros):
    m = io.BytesIO()
    with zipfile.ZipFile(m, "w") as z:
        for nome, dados in ficheiros.items():
            z.writestr(nome.replace("__", "/"), dados if isinstance(dados, (str, bytes)) else json.dumps(dados))
    return m.getvalue()


lido = isess.ler_zip_dados(zip_(**{"perfil.json": {"nome": "Miguel", "concluido": True}, "avaliacoes.json": [],
                                   "dados__algebra.json": {"nome": "Álgebra"}, "modelos3d__cubo_ab12.json": {"x": 1},
                                   "config.json": {"tema": "Escuro", "chaves": {"Gemini": "AIza-nao-pode-entrar"}}}))
ok("Importar .zip: aceita perfil, avaliações, cadeiras e só as preferências (nunca as chaves)",
   set(lido["ficheiros"]) == {"perfil.json", "avaliacoes.json", "dados/algebra.json"}
   and lido["preferencias"] == {"tema": "Escuro"} and "AIza" not in json.dumps(lido)
   and lido["ignorados"] == ["modelos3d/cubo_ab12.json"])
lido = isess.ler_zip_dados(zip_(**{"perfil.json": {"nome": "M"}, "../fora.json": {"nome": "x"},
                                   "dados__sub__x.json": {"nome": "x"}, "backup__a.json": {}}))
ok("Importar .zip: caminhos estranhos (../, subpastas, cópias) ficam de fora", set(lido["ficheiros"]) == {"perfil.json"}
   and len(lido["ignorados"]) == 3)


def recusa(conteudo, texto):
    try:
        isess.ler_zip_dados(conteudo)
        return False
    except isess.ErroImportar as e:
        return texto in str(e)


ok("Importar .zip: recusa o que não é um .zip, um .zip sem perfil e ficheiros danificados ou com outro formato",
   recusa(b"isto nao e um zip", "não é um .zip") and recusa(zip_(**{"dados__a.json": {"nome": "A"}}), "perfil.json")
   and recusa(zip_(**{"perfil.json": "{nao e json"}), "danificado") and recusa(zip_(**{"perfil.json": []}), "formato")
   and recusa(zip_(**{"perfil.json": {}, "dados__a.json": {"sem": "nome"}}), "formato")
   and recusa(zip_(**{"perfil.json": {}, "avaliacoes.json": {}}), "formato"))
grande = io.BytesIO()
with zipfile.ZipFile(grande, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("perfil.json", "{}"); z.writestr("dados/a.json", b" " * (isess.LIMITE_IMPORTAR + 1))
ok("Importar .zip: recusa .zip que fica enorme depois de aberto", recusa(grande.getvalue(), "grande demais"))
ok("Cookie com validade curta (o do regresso do Google dura 15 minutos)",
   "mondego_pkce=abc; Max-Age=900;" in isess.js_cookie("abc", dias=1 / 96, nome=isess.NOME_COOKIE_PKCE))
import base64 as _b64


def _jwt(papel):
    corpo = _b64.urlsafe_b64encode(json.dumps({"role": papel, "iss": "supabase"}).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiJ9.{corpo}.assinatura"


ok("Chave do Supabase: reconhece a secreta (service_role ou sb_secret_…) e aceita a anon e a publishable",
   isess.chave_secreta(_jwt("service_role")) and isess.chave_secreta("sb_secret_abc123")
   and not isess.chave_secreta(_jwt("anon")) and not isess.chave_secreta("sb_publishable_abc123")
   and not isess.chave_secreta("") and not isess.chave_secreta(None))
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
