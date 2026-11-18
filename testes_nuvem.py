"""Testes da ligação ao Supabase (py -3.14 testes_nuvem.py). Usam um Supabase falso (supabase/servidor_falso.py):
não precisam de internet nem de conta. Verificam os pedidos que a app faz; um projeto Supabase a sério pode ter
diferenças que só se veem lá (ver LEIA-ME → «Publicar a app»)."""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent / "supabase"))
import servidor_falso as falso  # noqa: E402

SRV = falso.Servidor(fornecedores=("google", "microsoft"))
sys.modules["httpx"] = falso.modulo_httpx(SRV)
import salas_backend as sb  # noqa: E402
import inicio_sessao as isess  # noqa: E402

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


def novo():
    return sb.BackendSupabase(SRV.url, SRV.chave, {})


# ---------------------------------------------------------------- contas com email
a = novo()
a.registar("ana@uc.pt", "segredo-da-ana", "Ana Costa", "Aluno")
ok("Criar conta: entra logo e cria o perfil (nome e vínculo) que os colegas das salas veem",
   a.atual()["email"] == "ana@uc.pt" and SRV.perfis[a.sessao["uid"]]["nome_completo"] == "Ana Costa")
SRV.confirmar_email = True
b = novo()
try:
    b.registar("rui@uc.pt", "segredo-do-rui", "Rui Professor", "Professor")
    ok("Com «Confirm email»: pede para confirmar o email", False)
except sb.ErroSalas as e:
    ok("Com «Confirm email»: pede para confirmar o email", "confirma a conta" in str(e) and isinstance(e, sb.ContaPorConfirmar) and not b.sessao.get("uid"))
b.entrar("Rui@UC.pt ", "segredo-do-rui")
ok("Primeira entrada depois de confirmar: cria o perfil com o nome e o vínculo escolhidos ao criar a conta",
   SRV.perfis[b.sessao["uid"]] == {"nome_completo": "Rui Professor", "vinculo": "Professor", "foto_b64": None})
try:
    novo().entrar("rui@uc.pt", "errada")
    ok("Palavra-passe errada é recusada", False)
except sb.ErroSalas:
    ok("Palavra-passe errada é recusada", True)

# ---------------------------------------------------------------- Google / Microsoft (OAuth com PKCE)
ok("Fornecedores: lê os ligados no Supabase («azure» é a Microsoft)", a.fornecedores_ativos() == ["google", "microsoft"])
estado, verificador, desafio = isess.novo_pkce()
url = novo().url_oauth("microsoft", "https://mondego.streamlit.app/", desafio)
q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
ok("Endereço do Google/Microsoft: /auth/v1/authorize com o desafio S256 e o regresso à app",
   url.startswith(SRV.url + "/auth/v1/authorize?") and q == {"provider": "azure", "redirect_to": "https://mondego.streamlit.app/",
                                                               "code_challenge": desafio, "code_challenge_method": "s256"}
   and desafio == base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
   and isess.PKCE[estado][0] == verificador)
volta = SRV.autorizar(url, "joana@outlook.pt", "Joana Silva")
codigo = parse_qs(urlparse(volta).query)["code"][0]
try:
    novo().entrar_oauth(codigo, "verificador-errado")
    ok("Regresso com o verificador errado é recusado", False)
except sb.ErroSalas:
    ok("Regresso com o verificador errado é recusado", True)
volta = SRV.autorizar(url, "joana@outlook.pt", "Joana Silva")
c = novo()
conta = c.entrar_oauth(parse_qs(urlparse(volta).query)["code"][0], verificador)
ok("Regresso com o «code» certo: entra e cria o perfil com o nome da conta Microsoft",
   conta["email"] == "joana@outlook.pt" and conta["nome"] == "Joana Silva" and c.sessao["refresh_token"])
c.mudar_perfil(nome="Joana S.")
volta = SRV.autorizar(url, "joana@outlook.pt", "Joana Silva")
c2 = novo()
c2.entrar_oauth(parse_qs(urlparse(volta).query)["code"][0], verificador)
ok("Voltar a entrar com a Microsoft não apaga o nome que a pessoa mudou", c2.atual()["nome"] == "Joana S.")
ok("Online: aluno ou professor escolhido na primeira entrada fica no perfil do Supabase",
   c2.mudar_vinculo("Professor")["vinculo"] == "Professor" and SRV.perfis[c2.sessao["uid"]]["vinculo"] == "Professor")

# ---------------------------------------------------------------- sessão lembrada (refresh token que muda)
antigo = c2.sessao["refresh_token"]
d = novo()
d.entrar_com_refresh(antigo)
ok("Voltar a abrir a app: entra com o refresh token e recebe um novo (o antigo deixa de valer)",
   d.atual()["email"] == "joana@outlook.pt" and d.sessao["refresh_token"] != antigo and antigo not in SRV.refreshes)
try:
    novo().entrar_com_refresh(antigo)
    ok("Um refresh token já usado é recusado", False)
except sb.ErroSalas:
    ok("Um refresh token já usado é recusado", True)
d.sessao["expira"] = time.time() + 30
r_antes = d.sessao["refresh_token"]
ok("Renova sozinha antes de o acesso expirar (e só quando falta pouco)",
   d.renovar_se_preciso() and d.sessao["refresh_token"] != r_antes and not d.renovar_se_preciso())
SRV.acessos[d.sessao["access_token"]] = (d.sessao["uid"], time.time() - 1)  # o acesso expirou entretanto
ok("Acesso expirado a meio: renova e repete o pedido", d.dados_ler_todos() == {} and d.sessao["access_token"] in SRV.acessos)

# ---------------------------------------------------------------- dados de cada pessoa
d.dados_guardar("perfil.json", {"nome": "Joana", "conversas": {"c1": {"titulo": "Matrizes"}}})
d.dados_guardar("dados/algebra.json", {"nome": "Álgebra", "ficheiros": {"a.pdf": "texto"}})
d.dados_guardar("perfil.json", {"nome": "Joana Silva"})
ok("Dados: grava, substitui (o mesmo ficheiro não fica duplicado) e lê tudo",
   d.dados_ler_todos() == {"dados/algebra.json": {"nome": "Álgebra", "ficheiros": {"a.pdf": "texto"}},
                           "perfil.json": {"nome": "Joana Silva"}})
ok("Dados: cada pessoa só vê os seus (a Ana não lê os da Joana)", a.dados_ler_todos() == {})
d.dados_apagar("dados/algebra.json")
ok("Dados: apagar uma cadeira apaga a cópia online", list(d.dados_ler_todos()) == ["perfil.json"])

# ---------------------------------------------------------------- terminar sessão e apagar a conta
uid_d = d.sessao["uid"]
d.sair()
ok("Terminar sessão termina também no servidor (o refresh token deixa de valer)",
   not d.sessao and uid_d not in SRV.refreshes.values())
a.dados_guardar("perfil.json", {"nome": "Ana"})
uid_a = a.sessao["uid"]
a.apagar_conta()
ok("Apagar a conta: a conta, o perfil e os dados desaparecem do servidor (RGPD)",
   uid_a not in SRV.utilizadores and uid_a not in SRV.perfis and not any(k[0] == uid_a for k in SRV.dados) and not a.sessao)
SRV.offline = True
try:
    b.dados_ler_todos()
    ok("Sem ligação: o erro chega à app (que avisa e guarda para enviar depois)", False)
except Exception as e:  # noqa: BLE001
    ok("Sem ligação: o erro chega à app (que avisa e guarda para enviar depois)", not isinstance(e, sb.ErroSalas))
SRV.offline = False
pub = sb.BackendSupabase(SRV.url, "sb_publishable_falsa", {})
ok("Chave «publishable» nova: vai no apikey e não no Authorization (não é um JWT)",
   "Authorization" not in pub._cab() and pub._cab()["apikey"] == "sb_publishable_falsa"
   and sb.BackendSupabase(SRV.url, "eyJ.anon.x", {})._cab()["Authorization"] == "Bearer eyJ.anon.x")
ok("Os pedidos levam sempre a chave anon (nunca a service_role) e nunca põem a chave no endereço",
   all("anon" not in p and "apikey" not in p for _, p in SRV.pedidos))
print(f"\nResumo: {sum(res)} de {len(res)} passaram")
