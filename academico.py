"""
Listas usadas no onboarding do Mondego IA.

Fontes:
- Licenciaturas da Universidade de Coimbra: catálogo oficial apps.uc.pt/courses (1.º ciclo, 50 cursos),
  consultado a 31/10/2026.
- Departamentos e faculdades da UC: filtro "Unidade orgânica" do mesmo catálogo, consultado a 31/10/2026.
- Mestrados integrados da UC: os quatro conhecidos (confirmar no catálogo oficial quando possível).
- Mestrados e doutoramentos: a lista oficial é muito longa e muda todos os anos, por isso o curso é
  escrito livremente (não se inventam opções).
"""

UC = "Universidade de Coimbra"

INSTITUICOES = [
    UC,
    "Politécnico de Coimbra",
    "Universidade do Porto",
    "Universidade de Lisboa",
    "Universidade NOVA de Lisboa",
    "Universidade do Minho",
    "Universidade de Aveiro",
    "Universidade da Beira Interior",
    "Universidade de Trás-os-Montes e Alto Douro",
    "Universidade de Évora",
    "Universidade do Algarve",
    "Universidade da Madeira",
    "Universidade dos Açores",
    "ISCTE – Instituto Universitário de Lisboa",
    "Universidade Católica Portuguesa",
    "Politécnico de Leiria",
    "Politécnico do Porto",
    "Politécnico de Lisboa",
    "Outra",
]

GRAUS = ["Licenciatura", "Mestrado integrado", "Mestrado", "Doutoramento", "Outro"]

CURSOS_UC = {
    "Licenciatura": [
        "Administração Pública", "Antropologia", "Arqueologia", "Biologia", "Biologia Marinha", "Bioquímica",
        "Ciência da Informação", "Ciências Bioanalíticas", "Ciências da Educação", "Ciências do Desporto",
        "Construção Digital", "Design e Multimédia", "Direito", "Economia", "Enfermagem", "Engenharia Aeroespacial",
        "Engenharia Biomédica", "Engenharia Civil", "Engenharia do Ambiente e Sustentabilidade",
        "Engenharia e Gestão Industrial", "Engenharia Eletrotécnica e de Computadores", "Engenharia Física",
        "Engenharia Informática", "Engenharia Mecânica", "Engenharia Naval e Oceânica",
        "Engenharia Química e Biotecnológica", "Estudos Artísticos", "Estudos Clássicos", "Estudos Europeus",
        "Farmácia Biomédica", "Filosofia", "Física", "Geografia", "Geologia", "Gestão",
        "Gestão de Cidades Sustentáveis e Inteligentes", "História", "História da Arte",
        "Inteligência Artificial e Ciência de Dados", "Jornalismo e Comunicação", "Línguas Modernas", "Matemática",
        "Português", "Psicologia", "Química", "Química Medicinal", "Relações Internacionais", "Serviço Social",
        "Sociologia", "Turismo, Território e Patrimónios",
    ],
    "Mestrado integrado": ["Arquitetura", "Ciências Farmacêuticas", "Medicina", "Medicina Dentária"],
}

DEPARTAMENTOS_UC = [
    "Departamento de Arquitetura (FCTUC)",
    "Departamento de Ciências da Terra (FCTUC)",
    "Departamento de Ciências da Vida (FCTUC)",
    "Departamento de Engenharia Civil (FCTUC)",
    "Departamento de Engenharia Eletrotécnica e de Computadores (FCTUC)",
    "Departamento de Engenharia Informática (FCTUC)",
    "Departamento de Engenharia Mecânica (FCTUC)",
    "Departamento de Engenharia Química (FCTUC)",
    "Departamento de Física (FCTUC)",
    "Departamento de Matemática (FCTUC)",
    "Departamento de Química (FCTUC)",
    "Faculdade de Ciências do Desporto e Educação Física",
    "Faculdade de Direito",
    "Faculdade de Economia",
    "Faculdade de Farmácia",
    "Faculdade de Letras",
    "Faculdade de Medicina",
    "Faculdade de Psicologia e de Ciências da Educação",
    "Escola Superior de Enfermagem",
    "Colégio das Artes",
    "Instituto de Investigação Interdisciplinar",
    "Outro",
]

AREAS_SECUNDARIO = [
    "Ciências e Tecnologias",
    "Ciências Socioeconómicas",
    "Línguas e Humanidades",
    "Artes Visuais",
    "Curso profissional",
    "Outro",
]

DISCIPLINAS_SECUNDARIO = [
    "Português", "Matemática A", "Matemática Aplicada às Ciências Sociais", "Física e Química A",
    "Biologia e Geologia", "Física", "Química", "Biologia", "Geologia", "História A", "História B",
    "Geografia A", "Economia A", "Filosofia", "Inglês", "Francês", "Espanhol", "Alemão", "Latim A",
    "Desenho A", "Geometria Descritiva A", "História da Cultura e das Artes", "Psicologia B", "Sociologia",
    "Aplicações Informáticas B", "Educação Física", "Outra",
]


def cursos_de(instituicao: str, grau: str) -> list:
    """Cursos conhecidos para a instituição e o grau. Lista vazia = o utilizador escreve o curso."""
    if instituicao == UC:
        return CURSOS_UC.get(grau, [])
    return []


def descricao_perfil(acad: dict) -> str:
    """Frase curta para dar contexto ao assistente."""
    if not acad:
        return ""
    partes = []
    if acad.get("vinculo") == "Professor":
        partes.append("É professor")
        if acad.get("departamentos"):
            partes.append("(" + ", ".join(acad["departamentos"]) + ")")
        if acad.get("disciplinas"):
            partes.append("de " + ", ".join(acad["disciplinas"]))
    else:
        partes.append("É aluno")
    if acad.get("nivel") == "Ensino secundário":
        partes.append(f"do ensino secundário ({acad.get('area') or 'área não indicada'})")
    elif acad.get("nivel") == "Ensino superior":
        curso = acad.get("curso")
        detalhe = ", ".join(x for x in [(f"{acad['grau']} em {curso}" if acad.get("grau") and curso else acad.get("grau") or curso or ""),
                                         acad.get("instituicao") or ""] if x)
        partes.append("do ensino superior" + (f": {detalhe}" if detalhe else ""))
    return " ".join(p for p in partes if p).strip() + "."


def resumo_perfil(acad: dict) -> str:
    """Linha curta para mostrar na app (perfil): «Aluno · Licenciatura em Engenharia Informática · Universidade de
    Coimbra». Só com o que está preenchido, sem pontuação a mais."""
    if not acad:
        return ""
    partes = [acad.get("vinculo") or "Aluno"]
    if acad.get("nivel") == "Ensino superior":
        curso = acad.get("curso")
        partes.append((f"{acad['grau']} em {curso}" if acad.get("grau") and curso else acad.get("grau") or curso or "") or "Ensino superior")
        partes.append(acad.get("instituicao") or "")
    elif acad.get("nivel"):
        partes += [acad["nivel"], acad.get("area") or ""]
    if acad.get("vinculo") == "Professor":
        partes += [", ".join(acad.get("departamentos") or []), ", ".join(acad.get("disciplinas") or [])]
    return " · ".join(p.strip() for p in partes if p and p.strip())
