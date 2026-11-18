"""Testes do módulo avaliacoes.py. Correr com:  py -3.14 testes_avaliacoes.py
Usa uma pasta temporária: não mexe nos teus dados."""
import sys, json, shutil, copy, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import avaliacoes as av

TMP = Path(tempfile.mkdtemp(prefix="teste_avaliacoes_"))  # nunca toca nos teus dados
F = TMP / "avaliacoes.json"
CAD = ["Álgebra", "Análise", "Programação"]
resultados = []
def ok(n, desc, cond):
    resultados.append((n, desc, bool(cond))); print(("PASSOU " if cond else "FALHOU ") + f"[{n}] {desc}")

repo = av.Avaliacoes(F)
# 1 criar
r = repo.criar("Exame final", "Álgebra", "Exame", date(2027, 6, 15), cadeiras_validas=CAD)
ok(1, "Criar uma prova", r["id"] and F.exists() and len(repo.todas()) == 1)
# 2 na data correta
ok(2, "Aparece na data correta (15/06)", [x["id"] for x in repo.filtrar(date(2027,6,15), date(2027,6,15))] == [r["id"]])
# 3 editar nome
novo, antigo = repo.atualizar(r["id"], CAD, nome="Exame de época normal")
ok(3, "Editar o nome (mesmo id)", novo["id"] == r["id"] and novo["nome"] == "Exame de época normal")
# 4-6 alterar data
repo.atualizar(r["id"], CAD, data=date(2027, 6, 20))
ok(4, "Alterar a data para 20/06", repo.obter(r["id"])["data"] == "2027-06-20")
ok(5, "Desaparece de 15/06", repo.filtrar(date(2027,6,15), date(2027,6,15)) == [])
ok(6, "Aparece em 20/06", [x["id"] for x in repo.filtrar(date(2027,6,20), date(2027,6,20))] == [r["id"]])
# 7 cadeira e tipo
repo.atualizar(r["id"], CAD, cadeira="Análise", tipo="Teste", hora="09:30", notas="sala 2.3")
x = repo.obter(r["id"])
ok(7, "Alterar cadeira, tipo e hora", (x["cadeira"], x["tipo"], x["hora"], x["notas"]) == ("Análise", "Teste", "09:30", "sala 2.3"))
# 8 apagar (a confirmação é da interface; aqui o apagar em si)
r2 = repo.criar("Trabalho 1", "Programação", "Trabalho", date(2027, 5, 2), cadeiras_validas=CAD)
repo.apagar(r2["id"])
ok(8, "Eliminar uma prova", repo.obter(r2["id"]) is None and len(repo.todas()) == 1)
# 9 persistência: novo objeto lê do disco (equivale a reiniciar a app)
repo2 = av.Avaliacoes(F)
y = repo2.obter(r["id"])
ok(9, "Persistência após 'reiniciar' (data 20/06 mantida)", y and y["data"] == "2027-06-20" and y["nome"] == "Exame de época normal")
# 11 passadas e futuras
p = repo2.criar("Mini-teste", "Álgebra", "Teste", date.today() - timedelta(days=10), cadeiras_validas=CAD)
hoje_sem_hora = repo2.criar("Entrega", "Programação", "Trabalho", date.today(), cadeiras_validas=CAD)
hora_passada = repo2.criar("Oral manhã", "Programação", "Apresentação", date.today(), hora="00:00", cadeiras_validas=CAD)
ok(11, "Passadas vs futuras (sem hora hoje NÃO está atrasada; com hora 00:00 já passou)",
   av.ja_passou(p) and not av.ja_passou(hoje_sem_hora) and av.ja_passou(hora_passada)
   and p["id"] not in [z["id"] for z in repo2.proximas()] and p in repo2.todas())
# 12 duplicados
try:
    repo2.criar("Mini-teste", "Álgebra", "Teste", date.today() - timedelta(days=10), cadeiras_validas=CAD); dup = False
except av.ErroValidacao: dup = True
ids = [z["id"] for z in repo2.todas()]
ok(12, "Sem duplicados (recusa igual; ids únicos)", dup and len(ids) == len(set(ids)))
# validações
erros = []
for kwargs in [dict(data=None), dict(cadeira="Inexistente"), dict(tipo="Festa"), dict(hora="25:99")]:
    base = dict(nome="X", cadeira="Álgebra", tipo="Teste", data=date(2027,1,1), hora=None)
    base.update(kwargs)
    try: repo2.criar(**base, cadeiras_validas=CAD); erros.append(False)
    except av.ErroValidacao: erros.append(True)
ok("v", "Validação: data obrigatória, cadeira existente, tipo válido, hora válida", all(erros))
# 13 planos não são corrompidos ao mudar a data
perfil = {"feitas": [], "plano_geral": {"dias": [{"data": "2027-06-01", "cadeira": "Análise", "temas": "Limites"}]}}
plano = {"avaliacao_id": r["id"], "data_avaliacao": "2027-06-20", "cadeira": "Análise",
         "dias": [{"data": "2027-06-01", "temas": "Limites", "duracao_min": 60},
                  {"data": "2027-06-10", "temas": "Derivadas", "duracao_min": 60},
                  {"data": "2027-06-18", "temas": "Integrais", "duracao_min": 60}]}
cad = {"Análise": {"nome": "Análise", "plano": copy.deepcopy(plano), "ficheiros": {}}}
perfil["feitas"].append(av.id_sessao(plano["dias"][0], "Análise"))
perfil["plano_geral"]["datas"] = av.fotografia_datas(repo2)
antes = json.dumps(cad["Análise"]["plano"], sort_keys=True)
repo2.atualizar(r["id"], CAD, data=date(2027, 6, 12))
estado = av.estado_plano_cadeira(cad["Análise"]["plano"], repo2, set(perfil["feitas"]))
inalterado = json.dumps(cad["Análise"]["plano"], sort_keys=True) == antes
mud = av.mudancas_desde(perfil["plano_geral"]["datas"], repo2)
fund = av.fundir_plano(plano["dias"], [{"data": date.today().isoformat(), "temas": "Revisão"}], set(perfil["feitas"]),
                       date(2027, 6, 5), "Análise")
ok(13, "Planos não são corrompidos: mudança detetada, nada alterado em silêncio, sessão feita preservada ao reorganizar",
   inalterado and estado and estado["data_nova"] == "2027-06-12" and estado["concluidas"] == 1
   and estado["depois_da_prova"] == 1 and any(m[0] == "data" for m in mud)
   and any(s["temas"] == "Limites" for s in fund) and not any(s["temas"] == "Derivadas" for s in fund))
# sessões de estudo
ses = av.sessoes_de_estudo(perfil, cad)
ok("s", "Sessões de estudo lidas dos planos, com a feita marcada", len(ses) == 4 and sum(s["feita"] for s in ses) == 2)
# 10 (parte de dados) navegação entre meses
ok("10a", "Navegação de meses (dez->jan, jan->dez) e grelhas de 7 dias",
   av.mudar_mes(date(2026,12,15), 1) == date(2027,1,1) and av.mudar_mes(date(2027,1,3), -1) == date(2026,12,1)
   and all(len(s) == 7 for s in av.semanas_do_mes(2026, 2)) and av.semanas_do_mes(2026,10)[0][0] == date(2026,9,28))
# ficheiro danificado não apaga nada
F.write_text("{isto não é json", encoding="utf-8")
repo3 = av.Avaliacoes(F)
ok("d", "Ficheiro danificado: guarda cópia e não rebenta", repo3.todas() == [] and list(TMP.glob("avaliacoes.danificado-*.json")))

# migração do formato antigo (uma data por cadeira) — dados de exemplo em memória
M = TMP / "mig"; M.mkdir()
cadeiras = {n: {"nome": n, "ficheiros": {}, "avaliacao": {"data": dt, "tipo": "Exame", "nota_alvo": 20, "dificuldade": "Média"}}
            for n, dt in [("algebra", "2026-11-11"), ("analise", "2026-11-04"), ("programacao", "2026-10-26")]}
datas_antes = {n: d["avaliacao"]["data"] for n, d in cadeiras.items()}
rm = av.Avaliacoes(M / "avaliacoes.json")
alteradas = av.migrar_de_cadeiras(rm, cadeiras, M / "backup")
segunda = av.migrar_de_cadeiras(rm, cadeiras, M / "backup")
migradas = {r["cadeira"]: r["data"] for r in rm.todas()}
ok("m", "Migração do formato antigo: datas iguais, objetivo preservado, cópia de segurança, sem duplicar ao repetir",
   migradas == datas_antes and len(alteradas) == 3 and segunda == [] and len(rm.todas()) == 3
   and all("avaliacao" not in d and d["objetivo"]["nota_alvo"] == 20 for d in cadeiras.values())
   and len(list((M / "backup").glob("*.json"))) == 1)
shutil.rmtree(TMP, ignore_errors=True)
print("\nResumo:", sum(r[2] for r in resultados), "de", len(resultados), "passaram")
