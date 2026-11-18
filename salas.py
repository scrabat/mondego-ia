"""
Salas do Mondego IA — regras (não dependem do servidor; testadas em testes_salas.py).

Uma sala tem um criador e membros. SÓ O CRIADOR configura a sala:
- conversa entre membros: desligada, todos escrevem, ou só o criador escreve (avisos);
- quem pode pôr documentos nos materiais da sala: só o criador ou todos os membros;
- se cada membro pode ter ficheiros privados (só ele e o seu assistente os veem);
- se a sala tem assistente de IA;
- quem pode ver o código/link de convite e se a sala aceita novos membros;
- nome, descrição, cor e um aviso fixo no topo.
O criador também pode apagar documentos e mensagens de outros (moderação) e remover membros.
As mesmas regras estão nas políticas RLS do Supabase (supabase/esquema.sql).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I, para não haver confusões

CORES_SALA = {"terracota": "#C96442", "azul": "#2E6DB4", "verde": "#3E8E5A", "amarelo": "#D9A21F",
              "roxo": "#7D4FA8", "turquesa": "#2AA5B8", "rosa": "#D9708F", "cinzento": "#8C857A"}
# Ícone da sala (Material Symbols): quem cria escolhe um; sem escolha, a app sugere um pelo nome, pela cadeira e pela
# descrição (ver icone_sugerido). Fica guardado só o identificador (a chave).
ICONES_SALA = {
    "estudo": ("school", "Estudo"), "grupo": ("groups", "Grupo"), "leitura": ("menu_book", "Leitura"),
    "escrita": ("edit_note", "Escrita"), "matematica": ("functions", "Matemática"), "calculo": ("calculate", "Cálculo"),
    "fisica": ("rocket_launch", "Física"), "quimica": ("science", "Química"), "biologia": ("biotech", "Biologia"),
    "saude": ("medical_services", "Saúde"), "programacao": ("code", "Programação"), "historia": ("history_edu", "História"),
    "geografia": ("public", "Geografia"), "linguas": ("translate", "Línguas"), "economia": ("trending_up", "Economia"),
    "direito": ("balance", "Direito"), "artes": ("palette", "Artes"), "musica": ("music_note", "Música"),
    "desporto": ("sports_soccer", "Desporto"), "ideias": ("lightbulb", "Ideias"),
}
_PALAVRAS_ICONE = [  # (palavras sem acentos, ícone) — a primeira que aparecer ganha
    (("algebra", "analise", "matemat", "geometria", "estatist", "probabil", "equac"), "matematica"),
    (("calculo", "contas", "aritmet"), "calculo"),
    (("fisica", "mecanica", "eletro", "termodin", "otica", "astronom"), "fisica"),
    (("quimic", "laborator", "reac"), "quimica"),
    (("biolog", "genetic", "anatom", "celul", "botanic", "zoolog", "ecolog"), "biologia"),
    (("medicin", "enfermag", "saude", "farmac", "fisiolog"), "saude"),
    (("program", "python", "java", "informat", "codigo", "software", "algoritm", "computa", "dados"), "programacao"),
    (("histori",), "historia"), (("geograf", "mapa"), "geografia"),
    (("ingles", "frances", "alemao", "espanhol", "linguas", "lingua", "idioma", "portugues", "literat"), "linguas"),
    (("economi", "gestao", "financ", "contabil", "marketing"), "economia"),
    (("direito", "juridic", "lei"), "direito"), (("arte", "desenho", "design", "pintura"), "artes"),
    (("music",), "musica"), (("desport", "educacao fisica", "treino"), "desporto"),
    (("escrita", "redac", "ensaio"), "escrita"), (("leitura", "livro"), "leitura"),
    (("estud", "revis", "exame", "teste", "explica", "apontament", "resum", "trabalho"), "estudo"),  # genéricas: no fim
]
CHAT_MODOS = {"todos": "Todos os membros escrevem", "criador": "Só eu escrevo (avisos)", "desligado": "Sem conversa"}
QUEM_PUBLICA = {"criador": "Só eu", "todos": "Todos os membros"}
QUEM_CONVIDA = {"todos": "Todos os membros", "criador": "Só eu"}
CAMPOS_DEFINICOES = ("nome", "descricao", "cor", "aviso", "chat_modo", "quem_publica", "ficheiros_privados",
                     "assistente_ativo", "convites", "entrada_aberta", "laboratorio", "ferramentas_lab", "icone")

# Laboratório da sala (opcional): as ferramentas que existem na app, por área. Quem cria a sala escolhe quais os
# membros têm. Identificador de cada ferramenta: "área.ferramenta" (é isto que fica guardado na sala).
LABORATORIO = {
    "historia": ("História e Geografia", ":material/public:", {
        "explicar": "Explicar acontecimentos", "documentos": "Analisar documentos", "cronologia": "Cronologias",
        "comparar": "Comparar", "testes": "Preparar testes", "resumos": "Resumos", "mapa": "Mapas"}),
    "biologia": ("Biologia", ":material/genetics:", {
        "explicar": "Explicar conceitos", "processos": "Processos passo a passo", "genetica": "Genética",
        "experiencias": "Experiências", "dados": "Gráficos e dados", "testes": "Preparar testes",
        "glossario": "Glossário", "simulacoes": "Simulações"}),
    "quimica": ("Química", ":material/science:", {
        "ia": "IA de Química", "tabela": "Tabela periódica", "massa": "Massa molar", "equacoes": "Acertar equações",
        "moleculas": "Moléculas 3D"}),
    "fisica": ("Física", ":material/rocket_launch:", {"ia": "IA de Física (com simulações)"}),
    "matematica": ("Matemática", ":material/function:", {
        "ia": "IA de Matemática", "graficos2d": "Gráficos 2D", "graficos3d": "Gráficos 3D"}),
    "programacao": ("Programação", ":material/code:", {"ia": "IA de Programação", "python": "Editor de Python"}),
}
FERRAMENTAS_LAB = tuple(f"{a}.{f}" for a, (_, _, fs) in LABORATORIO.items() for f in fs)


def ferramentas_por_area(ferramentas) -> dict:
    """{"historia": ["explicar", ...], ...} pela ordem do catálogo, só com as ferramentas que existem."""
    escolhidas = set(ferramentas or [])
    saida = {}
    for area, (_, _, fs) in LABORATORIO.items():
        lista = [f for f in fs if f"{area}.{f}" in escolhidas]
        if lista:
            saida[area] = lista
    return saida


def nome_ferramenta(ident: str) -> str:
    area, _, f = str(ident).partition(".")
    return LABORATORIO.get(area, ("", "", {}))[2].get(f, ident)


@dataclass
class Membro:
    sala_id: str
    utilizador_id: str
    papel: str              # "criador", "professor" ou "aluno"


@dataclass
class Ficheiro:
    id: str
    sala_id: str
    dono_id: str
    nome: str
    pasta_fixa: bool = False  # True = documento partilhado (materiais da sala, todos os membros veem)
    tipo_mime: str = ""
    texto_extraido: str = field(default="", repr=False)


class ErroDefinicoes(ValueError):
    """Definição inválida (mensagem pronta a mostrar)."""


def gerar_codigo(tamanho: int = 6) -> str:
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(tamanho))


def normalizar_codigo(codigo: str) -> str:
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


def tipo_de_sala_permitido(vinculo: str) -> str:
    """Alunos criam grupos de estudo; professores criam salas da sua cadeira."""
    return "cadeira" if vinculo == "Professor" else "grupo_estudo"


def link_convite(base_url: str, codigo: str) -> str:
    return f"{base_url.rstrip('/')}/?sala={normalizar_codigo(codigo)}"


# ------------------------------------------------------------------------------------------- definições
def definicoes_padrao(tipo: str, chat_ativo: bool | None = None) -> dict:
    """Sala de cadeira (professor): só ele publica e escreve avisos. Grupo de estudo: todos partilham e conversam."""
    cadeira = tipo == "cadeira"
    chat = ("todos" if chat_ativo else "desligado") if chat_ativo is not None else ("criador" if cadeira else "todos")
    return {"descricao": "", "cor": "azul" if cadeira else "turquesa", "aviso": "", "chat_modo": chat,
            "quem_publica": "criador" if cadeira else "todos", "ficheiros_privados": True, "assistente_ativo": True,
            "convites": "todos", "entrada_aberta": True, "laboratorio": False, "ferramentas_lab": [], "icone": ""}


def validar_definicoes(campos: dict, atuais: dict | None = None) -> dict:
    """Junta as alterações às definições atuais, validando cada uma. Ignora campos desconhecidos."""
    novo = dict(atuais or {})
    for k, v in (campos or {}).items():
        if k not in CAMPOS_DEFINICOES or v is None:
            continue
        if k == "nome":
            v = " ".join(str(v).split())
            if not 2 <= len(v) <= 80:
                raise ErroDefinicoes("O nome da sala tem de ter entre 2 e 80 caracteres.")
        elif k == "descricao":
            v = " ".join(str(v).split())[:300]
        elif k == "aviso":
            v = str(v).strip()[:500]
        elif k == "cor":
            if v not in CORES_SALA:
                raise ErroDefinicoes("Cor desconhecida.")
        elif k == "icone":
            v = str(v or "")
            if v and v not in ICONES_SALA:
                raise ErroDefinicoes("Ícone desconhecido.")
        elif k == "chat_modo":
            if v not in CHAT_MODOS:
                raise ErroDefinicoes("Modo de conversa desconhecido.")
        elif k == "quem_publica":
            if v not in QUEM_PUBLICA:
                raise ErroDefinicoes("Opção de documentos desconhecida.")
        elif k == "convites":
            if v not in QUEM_CONVIDA:
                raise ErroDefinicoes("Opção de convites desconhecida.")
        elif k == "ferramentas_lab":
            if isinstance(v, str):
                v = [x for x in v.replace(";", ",").split(",") if x.strip()]
            pedidas = [str(x).strip() for x in (v or [])]
            desconhecidas = [x for x in pedidas if x not in FERRAMENTAS_LAB]
            if desconhecidas:
                raise ErroDefinicoes(f"Ferramenta de laboratório desconhecida: {desconhecidas[0]}.")
            v = [f for f in FERRAMENTAS_LAB if f in pedidas]  # sem repetidas, pela ordem do catálogo
        else:  # ficheiros_privados, assistente_ativo, entrada_aberta, laboratorio
            v = bool(v)
        novo[k] = v
    if novo.get("laboratorio") and not novo.get("ferramentas_lab"):
        raise ErroDefinicoes("Com o Laboratório ativo, escolhe pelo menos uma ferramenta.")
    return novo


def icone_sugerido(nome: str, descricao: str = "", cadeira: str = "", tipo: str = "grupo_estudo") -> str:
    """Ícone que a sala recebe quando ninguém escolheu: pelo nome, pela cadeira e pela descrição (sem acentos)."""
    import unicodedata

    texto = " ".join(str(x or "") for x in (nome, cadeira, descricao)).lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    for palavras, icone in _PALAVRAS_ICONE:
        if any(p in texto for p in palavras):
            return icone
    return "leitura" if tipo == "cadeira" else "grupo"


def icone_da_sala(sala: dict) -> str:
    """O nome Material Symbols do ícone da sala (o escolhido ou, sem escolha, o sugerido)."""
    chave = sala.get("icone") if sala.get("icone") in ICONES_SALA else \
        icone_sugerido(sala.get("nome", ""), sala.get("descricao", ""), sala.get("cadeira", ""), sala.get("tipo", "grupo_estudo"))
    return ICONES_SALA[chave][0]


# ------------------------------------------------------------------------------------------- permissões
def e_criador(sala: dict, utilizador_id: str) -> bool:
    return bool(utilizador_id) and sala.get("criador_id") == utilizador_id


def pode_configurar(sala: dict, utilizador_id: str) -> bool:
    return e_criador(sala, utilizador_id)


def pode_partilhar(sala: dict, utilizador_id: str) -> bool:
    """Pôr documentos nos materiais da sala (todos os membros veem)."""
    return e_criador(sala, utilizador_id) or sala.get("quem_publica") == "todos"


def pode_ter_privados(sala: dict) -> bool:
    return bool(sala.get("ficheiros_privados", True))


def pode_ver_ficheiro(ficheiro: Ficheiro, utilizador_id: str, membros_da_sala: list[Membro]) -> bool:
    """Membros veem os documentos partilhados; os privados só o dono os vê."""
    e_membro = any(m.utilizador_id == utilizador_id and m.sala_id == ficheiro.sala_id for m in membros_da_sala)
    if not e_membro:
        return False
    return ficheiro.dono_id == utilizador_id or ficheiro.pasta_fixa


def pode_apagar_ficheiro(sala: dict, dono_id: str, utilizador_id: str) -> bool:
    return dono_id == utilizador_id or e_criador(sala, utilizador_id)


def chat_ativo(sala: dict) -> bool:
    return sala.get("chat_modo", "desligado") != "desligado"


def pode_escrever_no_chat(sala: dict, utilizador_id: str, membros_da_sala: list[Membro]) -> bool:
    e_membro = any(m.utilizador_id == utilizador_id and m.sala_id == sala.get("id") for m in membros_da_sala)
    modo = sala.get("chat_modo", "desligado")
    return e_membro and (modo == "todos" or (modo == "criador" and e_criador(sala, utilizador_id)))


def pode_apagar_mensagem(sala: dict, autor_id: str, utilizador_id: str) -> bool:
    return autor_id == utilizador_id or e_criador(sala, utilizador_id)


def pode_ver_convite(sala: dict, utilizador_id: str) -> bool:
    return e_criador(sala, utilizador_id) or sala.get("convites", "todos") == "todos"


def pode_remover_membro(sala: dict, alvo_id: str, utilizador_id: str) -> bool:
    return e_criador(sala, utilizador_id) and alvo_id != utilizador_id


def ficheiros_para_assistente(ficheiros: list[Ficheiro], utilizador_id: str, membros: list[Membro]) -> list[Ficheiro]:
    """O assistente da sala responde só com os ficheiros que esta pessoa pode ver."""
    return [f for f in ficheiros if pode_ver_ficheiro(f, utilizador_id, membros)]
