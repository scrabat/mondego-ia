"""
Avaliações do Estuda Comigo — fonte única de dados.

Todas as provas (testes, exames, trabalhos, apresentações...) vivem no ficheiro
`avaliacoes.json`, ao lado da app. Cada avaliação tem um identificador único que
nunca muda, por isso editar a data, o nome, a cadeira ou o tipo atualiza sempre o
mesmo registo (nunca cria um duplicado).

Este módulo não depende do Streamlit: pode ser usado e testado sozinho.

Estrutura de cada registo:
    id          identificador único (texto)
    nome        nome da avaliação, ex.: "Exame final"
    cadeira     nome da cadeira (tem de existir na app)
    tipo        um de TIPOS
    data        "AAAA-MM-DD" (obrigatória)
    hora        "HH:MM" ou None (None = dia inteiro, nunca se inventa hora)
    notas       texto livre
    principal   True se for a avaliação que aparece na tabela "cadeiras, datas e objetivos"
    criada / atualizada   data e hora da criação / última alteração
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

TIPOS = ["Teste", "Exame", "Trabalho", "Apresentação", "Outro"]

# Cores da legenda (terracota para exames, tons quentes e discretos para o resto)
CORES = {
    "Exame": "#C96442",
    "Teste": "#D4A03A",
    "Trabalho": "#5E8C6A",
    "Apresentação": "#6A7FB0",
    "Outro": "#8C857A",
}
COR_SESSAO = "#B9B2A3"

# Tipos usados nas versões anteriores da app -> tipos novos
MAPA_TIPOS_ANTIGOS = {
    "Exame": "Exame",
    "Teste/Frequência": "Teste",
    "Teste": "Teste",
    "Frequência": "Teste",
    "Trabalho": "Trabalho",
    "Projeto": "Trabalho",
    "Oral": "Apresentação",
    "Apresentação": "Apresentação",
}

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class ErroValidacao(ValueError):
    """Dados de uma avaliação inválidos (mensagem pronta a mostrar ao utilizador)."""


# =============================================================== utilitários
def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def gravar_json_seguro(caminho: Path, dados) -> None:
    """Grava primeiro num ficheiro temporário e só depois substitui o original,
    para nunca deixar o ficheiro meio escrito se a app fechar a meio."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, caminho)


def para_data(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def para_hora(valor) -> str | None:
    """Aceita time, "HH:MM", "H:MM" ou vazio. Devolve "HH:MM" ou None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    texto = str(valor).strip()
    try:
        return datetime.strptime(texto[:5] if len(texto) >= 5 else texto, "%H:%M").strftime("%H:%M")
    except ValueError as erro:
        raise ErroValidacao(f"Hora inválida: «{texto}». Usa o formato HH:MM.") from erro


def data_hora(registo: dict) -> datetime:
    """Momento da avaliação. Sem hora, conta como o fim do dia (não fica 'atrasada' durante o dia)."""
    dia = para_data(registo["data"])
    if registo.get("hora"):
        h, m = map(int, registo["hora"].split(":"))
        return datetime.combine(dia, time(h, m))
    return datetime.combine(dia, time(23, 59, 59))


def ja_passou(registo: dict, agora: datetime | None = None) -> bool:
    return data_hora(registo) < (agora or datetime.now())


def dias_ate(registo: dict, hoje: date | None = None) -> int:
    return (para_data(registo["data"]) - (hoje or date.today())).days


def texto_faltam(registo: dict, agora: datetime | None = None) -> str:
    agora = agora or datetime.now()
    if ja_passou(registo, agora):
        dias = -dias_ate(registo, agora.date())
        return "hoje (já passou)" if dias == 0 else ("ontem" if dias == 1 else f"há {dias} dias")
    dias = dias_ate(registo, agora.date())
    if dias == 0:
        return f"hoje às {registo['hora']}" if registo.get("hora") else "hoje"
    return "amanhã" if dias == 1 else f"faltam {dias} dias"


def ordenar(registos: list) -> list:
    return sorted(registos, key=lambda r: (r["data"], r.get("hora") or "99:99", r["nome"].lower()))


# =============================================================== repositório
class Avaliacoes:
    """Lê e grava as avaliações num único ficheiro JSON."""

    def __init__(self, ficheiro: Path, ao_gravar=None):
        self.ficheiro = Path(ficheiro)
        self.ao_gravar = ao_gravar  # ex.: enviar a cópia para o Supabase (app publicada)
        self.registos: dict[str, dict] = self._ler()

    # ---------------------------------------------------- leitura / gravação
    def _ler(self) -> dict:
        try:
            lista = json.loads(self.ficheiro.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as erro:
            # Não apagar nada: guardar uma cópia do ficheiro estragado e começar vazio
            copia = self.ficheiro.with_name(f"{self.ficheiro.stem}.danificado-{datetime.now():%Y%m%d%H%M%S}.json")
            try:
                self.ficheiro.replace(copia)
            except OSError:
                pass
            print(f"[avaliacoes] ficheiro ilegível, cópia guardada em {copia}: {erro}")
            return {}
        return {r["id"]: r for r in lista if isinstance(r, dict) and r.get("id") and para_data(r.get("data"))}

    def gravar(self) -> None:
        gravar_json_seguro(self.ficheiro, ordenar(list(self.registos.values())))
        if self.ao_gravar:
            self.ao_gravar(self.ficheiro)

    def recarregar(self) -> None:
        self.registos = self._ler()

    # ---------------------------------------------------- consultas
    def todas(self) -> list:
        return ordenar(list(self.registos.values()))

    def obter(self, ident: str) -> dict | None:
        return self.registos.get(ident)

    def da_cadeira(self, cadeira: str) -> list:
        return [r for r in self.todas() if r["cadeira"] == cadeira]

    def filtrar(self, inicio: date | None = None, fim: date | None = None,
                cadeiras: list | None = None, tipos: list | None = None) -> list:
        resultado = []
        for r in self.todas():
            dia = para_data(r["data"])
            if inicio and dia < inicio:
                continue
            if fim and dia > fim:
                continue
            if cadeiras is not None and r["cadeira"] not in cadeiras:
                continue
            if tipos is not None and r["tipo"] not in tipos:
                continue
            resultado.append(r)
        return resultado

    def proximas(self, cadeira: str | None = None, agora: datetime | None = None) -> list:
        return [r for r in self.todas() if not ja_passou(r, agora) and (cadeira is None or r["cadeira"] == cadeira)]

    def proxima(self, cadeira: str, agora: datetime | None = None) -> dict | None:
        futuras = self.proximas(cadeira, agora)
        return futuras[0] if futuras else None

    def principal(self, cadeira: str) -> dict | None:
        """A avaliação ligada à tabela de cadeiras: a marcada como principal ou, se não houver, a próxima."""
        marcadas = [r for r in self.da_cadeira(cadeira) if r.get("principal")]
        return marcadas[0] if marcadas else self.proxima(cadeira)

    # ---------------------------------------------------- validação
    def _validar(self, dados: dict, cadeiras_validas, ignorar_id: str | None = None) -> dict:
        cadeira = (dados.get("cadeira") or "").strip()
        if not cadeira:
            raise ErroValidacao("Escolhe a cadeira desta avaliação.")
        if cadeiras_validas is not None and cadeira not in cadeiras_validas:
            raise ErroValidacao(f"A cadeira «{cadeira}» não existe. Cria-a primeiro na barra lateral.")
        tipo = dados.get("tipo") or "Exame"
        if tipo not in TIPOS:
            raise ErroValidacao(f"Tipo de avaliação inválido: «{tipo}».")
        dia = para_data(dados.get("data"))
        if dia is None:
            raise ErroValidacao("A data é obrigatória (formato AAAA-MM-DD).")
        if not (2000 <= dia.year <= 2100):
            raise ErroValidacao("A data parece errada: confirma o ano.")
        hora = para_hora(dados.get("hora"))
        nome = re_espacos(dados.get("nome") or "") or f"{tipo} de {cadeira}"
        if len(nome) > 120:
            raise ErroValidacao("O nome é demasiado longo (máximo 120 caracteres).")
        notas = (dados.get("notas") or "").strip()
        if len(notas) > 4000:
            raise ErroValidacao("As notas são demasiado longas (máximo 4000 caracteres).")
        limpo = {"nome": nome, "cadeira": cadeira, "tipo": tipo, "data": dia.isoformat(), "hora": hora, "notas": notas}
        for r in self.registos.values():
            if r["id"] != ignorar_id and r["cadeira"] == cadeira and r["data"] == limpo["data"] \
                    and (r.get("hora") or None) == hora and r["nome"].lower() == nome.lower():
                raise ErroValidacao("Já existe uma avaliação igual (mesmo nome, cadeira, data e hora).")
        return limpo

    # ---------------------------------------------------- criar / editar / apagar
    def criar(self, nome: str, cadeira: str, tipo: str, data, hora=None, notas: str = "",
              cadeiras_validas=None, principal: bool = False) -> dict:
        limpo = self._validar({"nome": nome, "cadeira": cadeira, "tipo": tipo, "data": data, "hora": hora,
                               "notas": notas}, cadeiras_validas)
        agora = _agora_iso()
        registo = {"id": uuid.uuid4().hex[:12], **limpo, "principal": bool(principal), "criada": agora,
                   "atualizada": agora}
        if principal:
            for r in self.registos.values():
                if r["cadeira"] == registo["cadeira"]:
                    r["principal"] = False
        self.registos[registo["id"]] = registo
        self.gravar()
        return registo

    def atualizar(self, ident: str, cadeiras_validas=None, **campos) -> tuple[dict, dict]:
        """Altera um registo existente (mesmo id). Devolve (registo_novo, valores_antigos)."""
        atual = self.registos.get(ident)
        if atual is None:
            raise ErroValidacao("Esta avaliação já não existe (pode ter sido apagada).")
        juntos = {k: atual.get(k) for k in ("nome", "cadeira", "tipo", "data", "hora", "notas")}
        juntos.update({k: v for k, v in campos.items() if k in juntos})
        limpo = self._validar(juntos, cadeiras_validas, ignorar_id=ident)
        antigo = dict(atual)
        atual.update(limpo)
        if "principal" in campos:
            atual["principal"] = bool(campos["principal"])
            if atual["principal"]:
                for r in self.registos.values():
                    if r["id"] != ident and r["cadeira"] == atual["cadeira"]:
                        r["principal"] = False
        if atual["cadeira"] != antigo["cadeira"]:
            atual["principal"] = False  # mudou de cadeira: deixa de ser a principal da cadeira antiga
        atual["atualizada"] = _agora_iso()
        self.gravar()
        return atual, antigo

    def apagar(self, ident: str) -> dict:
        registo = self.registos.pop(ident, None)
        if registo is None:
            raise ErroValidacao("Esta avaliação já não existe.")
        self.gravar()
        return registo

    def apagar_da_cadeira(self, cadeira: str) -> int:
        ids = [i for i, r in self.registos.items() if r["cadeira"] == cadeira]
        for i in ids:
            del self.registos[i]
        if ids:
            self.gravar()
        return len(ids)

    def definir_principal(self, cadeira: str, data, tipo: str, cadeiras_validas=None) -> dict | None:
        """Usado pela tabela 'cadeiras, datas e objetivos': cria ou atualiza a avaliação principal da cadeira."""
        if para_data(data) is None:
            return None
        tipo = MAPA_TIPOS_ANTIGOS.get(tipo, tipo if tipo in TIPOS else "Exame")
        atual = self.principal(cadeira)
        if atual:
            if atual["data"] == para_data(data).isoformat() and atual["tipo"] == tipo:
                return atual
            return self.atualizar(atual["id"], cadeiras_validas, data=data, tipo=tipo, principal=True)[0]
        return self.criar("", cadeira, tipo, data, cadeiras_validas=cadeiras_validas, principal=True)


def re_espacos(texto: str) -> str:
    return " ".join(str(texto).split())


# =============================================================== migração das versões anteriores
def migrar_de_cadeiras(repo: Avaliacoes, cadeiras: dict, pasta_backup: Path) -> list:
    """As versões anteriores guardavam UMA data por cadeira em cadeira["avaliacao"].
    Passa essas datas para o repositório central (sem duplicar) e o objetivo/dificuldade para
    cadeira["objetivo"]. Guarda antes uma cópia de segurança. Devolve as cadeiras alteradas."""
    alteradas = []
    por_migrar = {n: d for n, d in cadeiras.items() if isinstance(d.get("avaliacao"), dict)}
    if not por_migrar:
        return alteradas
    copia = Path(pasta_backup) / f"avaliacoes_antes_do_calendario_{datetime.now():%Y%m%d%H%M%S}.json"
    gravar_json_seguro(copia, {n: d["avaliacao"] for n, d in por_migrar.items()})
    for nome, d in por_migrar.items():
        antiga = d["avaliacao"]
        if para_data(antiga.get("data")):
            tipo = MAPA_TIPOS_ANTIGOS.get(antiga.get("tipo"), "Exame")
            ja_existe = any(r["cadeira"] == nome and r["data"] == para_data(antiga["data"]).isoformat()
                            for r in repo.registos.values())
            if not ja_existe:
                repo.criar("", nome, tipo, antiga["data"], principal=True)
        objetivo = d.setdefault("objetivo", {})
        objetivo.setdefault("nota_alvo", antiga.get("nota_alvo"))
        objetivo.setdefault("dificuldade", antiga.get("dificuldade"))
        del d["avaliacao"]
        alteradas.append(nome)
    return alteradas


# =============================================================== sessões de estudo (planos)
def id_sessao(sessao: dict, cadeira: str | None = None) -> str:
    """Mesmo formato já usado pela app para marcar tarefas feitas: data|cadeira|temas."""
    return f"{str(sessao.get('data', ''))[:10]}|{sessao.get('cadeira') or cadeira}|{sessao.get('temas')}"


def sessoes_de_estudo(perfil: dict, cadeiras: dict) -> list:
    """Todas as sessões dos planos (geral e por cadeira), com a indicação de feita ou não."""
    feitas = set(perfil.get("feitas", []))
    sessoes = []
    for s in (perfil.get("plano_geral") or {}).get("dias", []):
        if para_data(s.get("data")):
            ident = id_sessao(s)
            sessoes.append({**s, "data": str(s["data"])[:10], "origem": "Plano geral", "id": ident,
                            "feita": ident in feitas})
    for nome, d in cadeiras.items():
        for s in (d.get("plano") or {}).get("dias", []):
            if para_data(s.get("data")):
                ident = id_sessao(s, nome)
                sessoes.append({**s, "cadeira": s.get("cadeira") or nome, "data": str(s["data"])[:10],
                                "origem": f"Plano de {nome}", "id": ident, "feita": ident in feitas})
    return sorted(sessoes, key=lambda s: (s["data"], s.get("ordem", 10 ** 6), s.get("cadeira") or ""))


def estado_plano_cadeira(plano: dict | None, repo: Avaliacoes, feitas: set) -> dict | None:
    """Se o plano foi criado para uma avaliação cuja data mudou (ou que foi apagada), devolve os detalhes."""
    if not plano or not plano.get("avaliacao_id"):
        return None
    registo = repo.obter(plano["avaliacao_id"])
    cadeira = plano.get("cadeira")
    concluidas = [s for s in plano.get("dias", []) if id_sessao(s, cadeira) in feitas]
    if registo is None:
        return {"motivo": "apagada", "data_plano": plano.get("data_avaliacao"), "data_nova": None,
                "concluidas": len(concluidas), "depois_da_prova": 0}
    if registo["data"] == plano.get("data_avaliacao"):
        return None
    nova = para_data(registo["data"])
    depois = [s for s in plano.get("dias", []) if (para_data(s.get("data")) or nova) > nova]
    return {"motivo": "data", "data_plano": plano.get("data_avaliacao"), "data_nova": registo["data"],
            "concluidas": len(concluidas), "depois_da_prova": len(depois), "avaliacao": registo}


def fotografia_datas(repo: Avaliacoes) -> dict:
    """Datas das avaliações no momento em que um plano é criado (para detetar mudanças depois)."""
    return {r["id"]: f"{r['data']} {r.get('hora') or ''}".strip() for r in repo.todas()}


def mudancas_desde(fotografia: dict | None, repo: Avaliacoes) -> list:
    """Avaliações que mudaram de data, foram criadas ou apagadas desde a fotografia."""
    if fotografia is None:
        return []
    atual = fotografia_datas(repo)
    mudancas = []
    for ident, quando in atual.items():
        if ident not in fotografia:
            mudancas.append(("nova", repo.obter(ident), None))
        elif fotografia[ident] != quando:
            mudancas.append(("data", repo.obter(ident), fotografia[ident]))
    for ident, quando in fotografia.items():
        if ident not in atual:
            mudancas.append(("apagada", None, quando))
    return mudancas


def fundir_plano(dias_antigos: list, dias_novos: list, feitas: set, hoje: date, cadeira: str | None = None) -> list:
    """Reorganiza um plano sem perder trabalho: mantém as sessões já feitas e as que já passaram,
    descarta só as futuras por fazer e junta as novas sessões (de hoje em diante)."""
    mantidas = [s for s in dias_antigos
                if id_sessao(s, cadeira) in feitas or (para_data(s.get("data")) or hoje) < hoje]
    novas = [s for s in dias_novos if (para_data(s.get("data")) or date.min) >= hoje]
    vistos, resultado = set(), []
    for s in mantidas + novas:
        chave = id_sessao(s, cadeira)
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(s)
    return sorted(resultado, key=lambda s: str(s.get("data", "")))


# =============================================================== grelhas de datas
def semanas_do_mes(ano: int, mes: int) -> list:
    """Lista de semanas (segunda a domingo) que cobrem o mês; cada semana é uma lista de 7 datas."""
    primeiro = date(ano, mes, 1)
    inicio = primeiro - timedelta(days=primeiro.weekday())
    ultimo = (date(ano + (mes == 12), mes % 12 + 1, 1)) - timedelta(days=1)
    semanas, dia = [], inicio
    while dia <= ultimo:
        semanas.append([dia + timedelta(days=i) for i in range(7)])
        dia += timedelta(days=7)
    return semanas


def inicio_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def mudar_mes(dia: date, delta: int) -> date:
    mes = dia.month - 1 + delta
    return date(dia.year + mes // 12, mes % 12 + 1, 1)
