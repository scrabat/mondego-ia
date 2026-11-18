"""Supabase falso (só na memória), usado pelos testes (testes_nuvem.py) para testar a app sem internet nem conta: Auth (signup, password, refresh com rotação, PKCE,
logout, settings) e PostgREST (perfis, dados_utilizador, rpc apagar_a_minha_conta), com as mesmas regras de acesso
(cada pessoa só lê/escreve as suas linhas). Imita os pedidos e as respostas da API REST documentada do Supabase."""
import base64
import hashlib
import json as _json
import secrets
import time
import types
from urllib.parse import parse_qs, urlparse, urlencode


class Resposta:
    def __init__(self, status, dados=None):
        self.status_code = status
        self._dados = dados
        self.content = b"" if dados is None else _json.dumps(dados).encode()
        self.text = self.content.decode()

    def json(self):
        if self._dados is None:
            raise ValueError("sem corpo")
        return self._dados


class Servidor:
    def __init__(self, url="https://falso.supabase.co", chave="anon-falsa", confirmar_email=False,
                 fornecedores=("google",), duracao=3600):
        self.url, self.chave, self.confirmar_email, self.duracao = url, chave, confirmar_email, duracao
        self.fornecedores = set(fornecedores)
        self.utilizadores = {}      # uid → {email, password, meta}
        self.acessos = {}           # access_token → (uid, expira)
        self.refreshes = {}         # refresh_token → uid (os válidos)
        self.codigos = {}           # code → (uid, desafio)
        self.perfis = {}            # uid → linha
        self.dados = {}             # (uid, chave) → valor
        self.pedidos = []           # (método, caminho)
        self.offline = False        # sem ligação nenhuma
        self.falhar = set()         # caminhos que respondem 503 (servidor com problemas)

    # ---------------------------------------------------------------- ajudas
    def _sessao(self, uid):
        acesso, refresh = "at_" + secrets.token_urlsafe(12), "rt_" + secrets.token_urlsafe(12)
        self.acessos[acesso] = (uid, time.time() + self.duracao)
        self.refreshes[refresh] = uid
        u = self.utilizadores[uid]
        return {"access_token": acesso, "refresh_token": refresh, "expires_in": self.duracao,
                "expires_at": int(time.time() + self.duracao), "token_type": "bearer",
                "user": {"id": uid, "email": u["email"], "user_metadata": u["meta"]}}

    def criar_utilizador(self, email, password=None, meta=None):
        uid = "u-" + hashlib.sha256(email.encode()).hexdigest()[:20]
        self.utilizadores[uid] = {"email": email, "password": password, "meta": meta or {}}
        return uid

    def autorizar(self, endereco, email, nome="Pessoa Google"):
        """Faz de browser + Google: abre o /authorize da app e devolve o endereço de regresso com o «code»."""
        u = urlparse(endereco)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        assert u.path == "/auth/v1/authorize" and q["code_challenge_method"] == "s256", q
        assert q["provider"] in self.fornecedores_sb(), q["provider"]
        uid = next((i for i, x in self.utilizadores.items() if x["email"] == email), None) or \
            self.criar_utilizador(email, meta={"full_name": nome, "name": nome})
        codigo = secrets.token_urlsafe(10)
        self.codigos[codigo] = (uid, q["code_challenge"])
        regresso = q["redirect_to"]
        return regresso + ("&" if "?" in regresso else "?") + urlencode({"code": codigo})

    def _uid(self, cab):
        token = (cab.get("Authorization") or "").removeprefix("Bearer ")
        if not token or token == self.chave:  # sem sessão: papel «anon»
            return None
        info = self.acessos.get(token)
        if not info or info[1] < time.time():
            return False
        return info[0]

    # ---------------------------------------------------------------- pedidos
    def tratar(self, metodo, endereco, headers=None, json=None, content=None):
        if self.offline:
            raise ConnectionError("sem ligação")
        cab = headers or {}
        u = urlparse(endereco)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.pedidos.append((metodo, u.path + ("?" + u.query if u.query else "")))
        if u.path in self.falhar:
            return Resposta(503, {"message": "Service Unavailable"})
        if cab.get("apikey") != self.chave:
            return Resposta(401, {"message": "Invalid API key"})
        corpo = json or {}
        caminho = u.path
        if caminho == "/auth/v1/settings":
            return Resposta(200, {"external": {n: (n in {"azure" if f == "microsoft" else f for f in self.fornecedores})
                                               for n in ("google", "azure", "apple", "facebook", "email")}})
        if caminho == "/auth/v1/signup":
            if any(x["email"] == corpo["email"] for x in self.utilizadores.values()):
                return Resposta(422, {"msg": "User already registered"})
            uid = self.criar_utilizador(corpo["email"], corpo["password"], corpo.get("data"))
            if self.confirmar_email:
                return Resposta(200, {"id": uid, "email": corpo["email"]})
            return Resposta(200, self._sessao(uid))
        if caminho == "/auth/v1/token":
            tipo = q.get("grant_type")
            if tipo == "password":
                uid = next((i for i, x in self.utilizadores.items()
                            if x["email"] == corpo["email"] and x["password"] == corpo["password"]), None)
                return Resposta(200, self._sessao(uid)) if uid else Resposta(400, {"error_description": "Invalid login credentials"})
            if tipo == "refresh_token":
                uid = self.refreshes.pop(corpo.get("refresh_token"), None)  # rotação: o antigo deixa de valer
                return Resposta(200, self._sessao(uid)) if uid in self.utilizadores else \
                    Resposta(400, {"error_description": "Invalid Refresh Token"})
            if tipo == "pkce":
                uid, desafio = self.codigos.pop(corpo.get("auth_code"), (None, None))
                certo = base64.urlsafe_b64encode(hashlib.sha256((corpo.get("code_verifier") or "").encode()).digest()
                                                 ).decode().rstrip("=")
                if not uid or certo != desafio:
                    return Resposta(400, {"error_description": "invalid flow state"})
                return Resposta(200, self._sessao(uid))
        uid = self._uid(cab)
        if uid is False:
            return Resposta(401, {"message": "JWT expired"})
        if caminho == "/auth/v1/logout":
            if q.get("scope") == "local":  # só esta sessão: o access token deixa de valer
                token = (cab.get("Authorization") or "").removeprefix("Bearer ")
                self.acessos.pop(token, None)
                return Resposta(204)
            for r, d in list(self.refreshes.items()):
                if d == uid:
                    del self.refreshes[r]
            return Resposta(204)
        if caminho == "/auth/v1/user" and metodo == "PUT":
            if not uid:
                return Resposta(401, {"message": "sem sessão"})
            if "password" in corpo:
                if len(corpo["password"] or "") < 6:
                    return Resposta(422, {"msg": "Password should be at least 6 characters"})
                if "current_password" in corpo and corpo["current_password"] != self.utilizadores[uid]["password"]:
                    return Resposta(400, {"msg": "Current password is incorrect"})
                self.utilizadores[uid]["password"] = corpo["password"]
            u = self.utilizadores[uid]
            return Resposta(200, {"id": uid, "email": u["email"], "user_metadata": u["meta"]})
        if uid is None and caminho.startswith("/rest/"):
            return Resposta(401, {"message": "sem sessão"})
        if caminho == "/rest/v1/perfis":
            if metodo == "GET":
                alvo = q.get("id", "").removeprefix("eq.")
                return Resposta(200, [self.perfis[alvo]] if alvo == uid and alvo in self.perfis else [])
            if metodo == "POST":
                if corpo.get("id") != uid:
                    return Resposta(403, {"message": "new row violates row-level security policy"})
                prefer = cab.get("Prefer", "")
                if uid in self.perfis and "ignore-duplicates" in prefer:
                    return Resposta(201)
                if uid in self.perfis and "merge-duplicates" not in prefer:
                    return Resposta(409, {"message": "duplicate key"})
                self.perfis[uid] = {**self.perfis.get(uid, {}), **{k: v for k, v in corpo.items() if k != "id"},
                                    "foto_b64": self.perfis.get(uid, {}).get("foto_b64")}
                return Resposta(201)
            if metodo == "PATCH":
                self.perfis.setdefault(uid, {}).update(corpo)
                return Resposta(204)
        if caminho == "/rest/v1/dados_utilizador":
            if metodo == "GET":
                dono = q.get("uid", "").removeprefix("eq.")
                return Resposta(200, [{"chave": c, "valor": v} for (u_, c), v in sorted(self.dados.items())
                                      if u_ == uid and dono == uid])
            if metodo == "POST":
                if corpo.get("uid") != uid:
                    return Resposta(403, {"message": "new row violates row-level security policy"})
                if (uid, corpo["chave"]) in self.dados and "merge-duplicates" not in cab.get("Prefer", ""):
                    return Resposta(409, {"message": "duplicate key"})
                self.dados[(uid, corpo["chave"])] = _json.loads(_json.dumps(corpo["valor"]))
                return Resposta(201)
            if metodo == "DELETE":
                dono, chave = q.get("uid", "").removeprefix("eq."), q.get("chave", "").removeprefix("eq.")
                if dono == uid:
                    self.dados.pop((uid, chave), None)
                return Resposta(204)
        if caminho == "/rest/v1/rpc/apagar_a_minha_conta":
            self.utilizadores.pop(uid, None)
            self.perfis.pop(uid, None)
            for k in [k for k in self.dados if k[0] == uid]:
                del self.dados[k]
            for r, d in list(self.refreshes.items()):
                if d == uid:
                    del self.refreshes[r]
            return Resposta(204)
        if metodo == "GET" and caminho.startswith("/rest/v1/"):
            return Resposta(200, [])  # salas, membros, 3D…: vazio
        return Resposta(404, {"message": f"falso: {metodo} {caminho} não existe"})


def _fornecedores_sb(self):
    return {"azure" if f == "microsoft" else f for f in self.fornecedores}


Servidor.fornecedores_sb = _fornecedores_sb  # nomes do Supabase (a Microsoft chama-se «azure»)


def modulo_httpx(servidor: Servidor):
    """Um «httpx» que manda os pedidos ao Supabase falso."""
    m = types.ModuleType("httpx")

    class Client:
        def __init__(self, *a, **k):
            pass

        def request(self, metodo, endereco, headers=None, json=None, content=None, **k):
            return servidor.tratar(metodo, endereco, headers, json, content)

        def get(self, endereco, headers=None, **k):
            return self.request("GET", endereco, headers=headers)

        def post(self, endereco, headers=None, json=None, content=None, **k):
            return self.request("POST", endereco, headers=headers, json=json, content=content)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    m.Client = Client
    return m
