"""Testes das regras do Plano de Estudo Inteligente (py -3.14 testes_plano.py).
O plano diz o que estudar em cada dia — nunca horas nem durações."""
from collections import Counter
from datetime import date, timedelta

import plano_estudo as pe

res = []


def ok(nome, cond):
    res.append(bool(cond))
    print(("PASSOU " if cond else "FALHOU ") + nome)


hoje = date(2026, 11, 16)  # segunda-feira
RESPOSTA = {"cadeiras": [
    {"cadeira": "Matemática", "temas": [
        {"tema": "Funções", "dificuldade": "Média", "importancia": "Alta",
         "estudar": "Estudar funções: domínio, contradomínio e gráfico", "praticar": "Resolver a ficha 2 de funções"},
        {"tema": "Limites", "dificuldade": "difícil", "importancia": "alta"}, {"tema": "Derivadas", "dificuldade": "Difícil"},
        {"tema": "Estudo de funções"}, {"tema": "limites"}, {"tema": ""}, 7]},
    {"cadeira": "biologia ", "temas": ["Sistema nervoso", {"tema": "Sistema endócrino", "dificuldade": "Fácil"},
                                       {"tema": "Homeostasia"}]},
    {"cadeira": "Português", "temas": [{"tema": "Interpretação"}, {"tema": "Gramática", "dificuldade": "Fácil"}]},
    {"cadeira": "Cadeira que não existe", "temas": [{"tema": "X"}]}]}
VALIDAS = ["Matemática", "Biologia", "Português"]
LIMITES = {"Matemática": date(2026, 11, 27), "Biologia": date(2026, 12, 2), "Português": date(2026, 11, 24)}
u = pe.validar_unidades(RESPOSTA, VALIDAS)

ok("Temas da IA: só cadeiras conhecidas (o nome é comparado sem acentos nem maiúsculas), sem temas repetidos nem lixo, "
   "níveis normalizados e tarefas completadas",
   list(u) == ["Matemática", "Biologia", "Português"] and [x["tema"] for x in u["Matemática"]] ==
   ["Funções", "Limites", "Derivadas", "Estudo de funções"] and u["Matemática"][1]["dificuldade"] == "Difícil"
   and u["Matemática"][1]["importancia"] == "Alta" and u["Matemática"][1]["estudar"] == "Estudar limites"
   and u["Matemática"][0]["praticar"] == "Resolver a ficha 2 de funções" and u["Biologia"][0]["tema"] == "Sistema nervoso")
ok("Plano de uma cadeira: os blocos de outras cadeiras ficam de fora; formato antigo da IA (dias) também serve",
   [x["tema"] for x in pe.validar_unidades(RESPOSTA, VALIDAS, cadeira_fixa="Português")["Português"]] == ["Interpretação", "Gramática"]
   and [x["tema"] for x in pe.validar_unidades({"dias": [{"data": "2026-11-17", "cadeira": "Biologia", "temas": "Células",
                                                           "duracao_min": 45}]}, VALIDAS)["Biologia"]] == ["Células"])
ok("Preferências: dias de folga e ritmo (tarefas por dia); vêm das antigas (horário, horas por dia) quando não há",
   pe.preferencias(None, {"horas_dia": 1, "folga": ["Domingo", "xx"]}) == {
       "folga": ["Domingo"], "ritmo": "Leve", "comecar": pe.COMECAR[0], "estilo": pe.ESTILOS[0], "por_dia": 3}
   and pe.preferencias({"horario": {d: (None if d == "Sábado" else ["09:00", "13:00"]) for d in pe.DIAS_SEMANA}})["folga"]
   == ["Sábado"]
   and pe.preferencias(None, {"horas_dia": 5})["ritmo"] == "Intenso"
   and pe.preferencias({"folga": pe.DIAS_SEMANA})["folga"] == [] and pe.preferencias({"ritmo": "Turbo"})["ritmo"] == "Equilibrado")

prefs = pe.preferencias({"folga": ["Domingo"], "ritmo": "Equilibrado"})
tarefas, info = pe.distribuir(u, LIMITES, hoje, prefs)
dias = pe.por_dia(tarefas)
CAMPOS = {"data", "cadeira", "tipo", "temas", "tema", "ordem", "final"}
ok("Tarefas sem horas nem durações: só dia, cadeira, tipo e o que fazer",
   tarefas and all(set(t) == CAMPOS and t["tipo"] in pe.TIPOS_TAREFA and t["temas"] for t in tarefas))
ok("Cada cadeira só tem tarefas antes da sua avaliação e nunca nos dias de folga",
   all(hoje.isoformat() <= t["data"] < LIMITES[t["cadeira"]].isoformat() for t in tarefas)
   and all(date.fromisoformat(d).weekday() != 6 for d in dias))
ok("Carga equilibrada: nenhum dia passa o ritmo (4) e não há dias vazios entre dias de estudo",
   max(len(v) for v in dias.values()) <= 4 and not info["cheios"]
   and len(dias) == len(pe.dias_de_estudo(hoje, max(LIMITES.values()), ["Domingo"])))
ok("Toda a matéria é dada: cada tema tem «Estudar» e «Praticar» (o exercício depois do estudo)",
   all(sum(1 for t in tarefas if t["cadeira"] == c and t["tema"] == x["tema"] and t["tipo"] == "Estudar") == 1
       and min(t["data"] for t in tarefas if t["cadeira"] == c and t["tema"] == x["tema"] and t["tipo"] == "Praticar")
       >= min(t["data"] for t in tarefas if t["cadeira"] == c and t["tema"] == x["tema"] and t["tipo"] == "Estudar")
       for c, lista in u.items() for x in lista))
ok("Cadeiras intercaladas: logo no primeiro dia há tarefas de todas as cadeiras",
   {t["cadeira"] for t in dias[hoje.isoformat()]} == set(LIMITES))
rev = [t for t in tarefas if t["cadeira"] == "Matemática" and t["tema"] == "Limites" and t["tipo"] == "Rever"]
est = next(t["data"] for t in tarefas if t["cadeira"] == "Matemática" and t["tema"] == "Limites" and t["tipo"] == "Estudar")
ok("Revisões espaçadas: os temas difíceis têm várias revisões, em dias diferentes, depois de os estudar, e exercícios refeitos",
   len(rev) >= 2 and len({t["data"] for t in rev}) == len(rev) and all(t["data"] > est for t in rev)
   and any(t["temas"] == "Refazer os exercícios de limites que correram pior" for t in tarefas))
ok("Sem repetições: nenhuma tarefa aparece duas vezes (nem no mesmo dia nem noutro)",
   not [k for k, n in Counter((t["cadeira"], t["temas"]) for t in tarefas).items() if n > 1])
fin = {c: [t for t in tarefas if t["cadeira"] == c and t["final"]] for c in LIMITES}
ok("Nos últimos dias antes de cada avaliação: revisão geral e depois um teste de treino",
   all([t["tipo"] for t in fin[c]] == ["Rever", "Testar"] and fin[c][-1]["data"] == max(t["data"] for t in tarefas if t["cadeira"] == c)
       and fin[c][0]["data"] <= fin[c][1]["data"] for c in LIMITES))
dif = pe.distribuir(u, LIMITES, hoje, prefs | {"comecar": pe.COMECAR[0]})[0]
bas = pe.distribuir(u, LIMITES, hoje, prefs | {"comecar": pe.COMECAR[1]})[0]
primeiro = lambda tt: next(t["tema"] for t in tt if t["cadeira"] == "Matemática" and t["tipo"] == "Estudar")
ok("«Pelos mais difíceis» começa por Limites; «pelas bases» segue a ordem da matéria (Funções)",
   primeiro(dif) == "Limites" and primeiro(bas) == "Funções")
testes = pe.distribuir(u, LIMITES, hoje, prefs | {"estilo": pe.ESTILOS[3], "ritmo": "Intenso"})[0]
teoria = pe.distribuir(u, LIMITES, hoje, prefs | {"estilo": "Mais teoria"})[0]
ok("Estilo: «muitos testes» junta mini-testes; «mais teoria» não pede exercícios dos temas fáceis",
   any(t["temas"].startswith("Fazer um mini-teste sobre") for t in testes)
   and not any(t["tipo"] == "Praticar" and t["tema"] == "Gramática" for t in teoria))
leve = pe.distribuir(u, LIMITES, hoje, prefs | {"ritmo": "Leve"})
ok("Ritmo leve: no máximo 3 tarefas por dia (as revisões que não cabem ficam de fora, a matéria não)",
   max(Counter(t["data"] for t in leve[0]).values()) <= 3 and leve[1]["revisoes_cortadas"] > 0
   and sum(1 for t in leve[0] if t["tipo"] == "Estudar") == sum(len(v) for v in u.values()))
aperto = pe.distribuir({"Física": [{"tema": f"Tema {i}", "dificuldade": "Difícil", "importancia": "Média",
                                    "estudar": f"Estudar o tema {i}", "praticar": f"Resolver os exercícios do tema {i}",
                                    "rever": f"Rever o tema {i}"} for i in range(1, 13)]},
                       {"Física": hoje + timedelta(days=5)}, hoje, pe.preferencias({}))
por_dia_aperto = Counter(t["data"] for t in aperto[0])
ok("Pouco tempo e muita matéria: estudar e praticar juntos numa tarefa, espalhados por igual (não tudo no último dia)",
   len(set(por_dia_aperto.values())) == 1
   and all("; depois, resolver os exercícios" in t["temas"] for t in aperto[0] if t["tipo"] == "Estudar"))
sem = pe.distribuir({"Física": u["Biologia"]}, {"Física": None}, hoje, prefs)[0]
ok("Cadeira sem avaliação marcada: plano para as próximas duas semanas, sem revisão geral nem teste de treino",
   sem and max(t["data"] for t in sem) < (hoje + timedelta(days=14)).isoformat() and not any(t["final"] for t in sem))
ja = pe.distribuir(u, LIMITES, hoje, prefs, estudados={"Matemática": {"Limites"}})[0]
ok("Temas já estudados: não voltam a ser dados, só uma revisão",
   not any(t["tema"] == "Limites" and t["tipo"] in ("Estudar", "Praticar") for t in ja)
   and sum(1 for t in ja if t["tema"] == "Limites" and t["tipo"] == "Rever") == 1)

# ---------------------------------------------------------------- reorganizar e adiar
feitas = {pe.id_sessao(t) for t in tarefas if t["data"] == hoje.isoformat()}
depois = hoje + timedelta(days=3)   # os dias 17 e 18 ficaram por fazer
novo, inf = pe.reorganizar(tarefas, feitas, depois, LIMITES, prefs)
por_fazer = [t for t in novo if pe.id_sessao(t) not in feitas]
ok("Reorganizar: as tarefas feitas não mudam e nada por fazer fica em dias que já passaram",
   feitas <= {pe.id_sessao(t) for t in novo} and all(t["data"] >= depois.isoformat() for t in por_fazer))
ok("Reorganizar: a matéria toda continua no plano, antes de cada avaliação, sem passar o ritmo",
   {(t["cadeira"], t["tema"]) for t in tarefas if t["tipo"] == "Estudar"} ==
   {(t["cadeira"], t["tema"]) for t in novo if t["tipo"] == "Estudar"}
   and all(t["data"] < LIMITES[t["cadeira"]].isoformat() for t in novo)
   and max(Counter(t["data"] for t in por_fazer).values()) <= 4 and not inf["cheios"])
dia_d = depois.isoformat()
feitas2 = feitas | {pe.id_sessao(t) for t in tarefas if t["data"] == dia_d}  # hoje já fez as tarefas do dia
novo2 = pe.reorganizar(tarefas, feitas2, depois, LIMITES, prefs)[0]
ok("Reorganizar: as tarefas já feitas hoje contam para o ritmo de hoje (o dia não fica com mais do que 4)",
   0 < sum(1 for t in novo2 if t["data"] == dia_d) <= 4
   and pe.ocupados(tarefas, feitas2, depois) == {depois: sum(1 for t in tarefas if t["data"] == dia_d)})
estudo = {(e["cadeira"], e["tema"]): e["data"] for e in novo if e["tipo"] == "Estudar"}
ok("Reorganizar: a revisão geral e o teste de treino continuam no fim; o que é revisto vem depois de estudado",
   all(max(t["data"] for t in novo if t["cadeira"] == c) ==
       next(t["data"] for t in novo if t["cadeira"] == c and t["final"] and t["tipo"] == "Testar") for c in LIMITES)
   and all(t["data"] > estudo[(t["cadeira"], t["tema"])] for t in por_fazer
           if t["tipo"] == "Rever" and not t["final"] and (t["cadeira"], t["tema"]) in estudo))
antecipada = {**LIMITES, "Português": depois + timedelta(days=2)}
mudou = pe.reorganizar(tarefas, feitas, depois, antecipada, prefs)
ok("Avaliação antecipada: o plano dessa cadeira encolhe para os dias que restam",
   all(t["data"] < antecipada["Português"].isoformat() for t in mudou[0]
       if t["cadeira"] == "Português" and pe.id_sessao(t) not in feitas))
passou = pe.reorganizar(tarefas, feitas, date(2026, 11, 25), LIMITES, prefs)
ok("Avaliação que já passou: as tarefas por fazer dessa cadeira saem do plano (as feitas ficam)",
   not any(t["cadeira"] == "Português" and pe.id_sessao(t) not in feitas for t in passou[0]) and passou[1]["retiradas"] > 0
   and any(t["cadeira"] == "Português" for t in passou[0]))
copia = [dict(t) for t in tarefas]
sab = next(t for t in copia if t["data"] == "2026-11-21" and not t["final"])
teste_pt = next(t for t in copia if t["cadeira"] == "Português" and t["final"] and t["tipo"] == "Testar")
ok("Adiar: passa para o próximo dia de estudo (salta a folga de domingo) e não passa da avaliação",
   pe.adiar(copia, pe.id_sessao(sab), hoje, ["Domingo"]) == f"2026-11-23|{sab['cadeira']}|{sab['temas']}"
   and pe.adiar(copia, pe.id_sessao(teste_pt), hoje, ["Domingo"], limite=LIMITES["Português"]) is None)
antigo = [{"data": "2026-11-10", "cadeira": "Física", "temas": "Cinemática", "tarefas": "ler cap. 1", "hora": "09:00",
           "duracao_min": 45, "tipo": "Teoria"},
          {"data": "2026-11-12", "cadeira": "Física", "temas": "Dinâmica", "hora": "18:00", "duracao_min": 60, "tipo": "Exercícios"}]
reo = pe.reorganizar(antigo, set(), hoje, {"Física": hoje + timedelta(days=5)}, prefs)[0]
ok("Planos antigos (com horas): continuam a funcionar; ao reorganizar perdem a hora e a duração",
   pe.texto_da_tarefa(antigo[0]) == ("Cinemática", "ler cap. 1") and pe.tipo_de(antigo[1]) == "Praticar"
   and len(reo) == 2 and all("hora" not in t and "duracao_min" not in t and t["data"] >= hoje.isoformat() for t in reo))
mantido = pe.fundir(tarefas, ja, feitas, hoje)
feitas_estudar = [t for t in tarefas if pe.id_sessao(t) in feitas and t["tipo"] == "Estudar"]
ok("Refazer mantendo o que foi feito: ficam as tarefas feitas e entra o plano novo (sem duplicados)",
   feitas <= {pe.id_sessao(t) for t in mantido} and len(mantido) == len({pe.id_sessao(t) for t in mantido})
   and pe.estudados(tarefas, feitas) == {c: {t["tema"] for t in feitas_estudar if t["cadeira"] == c}
                                         for c in {t["cadeira"] for t in feitas_estudar}})
r = pe.resumo(tarefas, feitas, hoje=depois)
ok("Resumo: conta tarefas (não minutos), as feitas e as que ficaram para trás",
   r["total"] == len(tarefas) and r["feitas"] == len(feitas) and r["atrasadas"] > 0 and "minutos" not in r)
ok("Identificador igual ao do resto da app (data|cadeira|temas)", pe.id_sessao({"data": "2026-11-02", "temas": "x"}, "Álgebra")
   == "2026-11-02|Álgebra|x" and pe.ids_do_plano(tarefas[:1]) == {pe.id_sessao(tarefas[0])})

print(f"\nResumo: {sum(res)} de {len(res)} passaram")
raise SystemExit(0 if all(res) else 1)
