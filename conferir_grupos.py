# -*- coding: utf-8 -*-
"""conferir_grupos.py — a varredura chegou em cada grupo? quanto custou?

Roda sem gastar UMA chamada da seats.aero: le so o que o robo da nuvem
gravou de volta no repositorio (historico_<grupo>.json, cota_seats.txt,
ultima_busca.txt). Pode rodar a vontade.

    python conferir_grupos.py

A pergunta que motivou: a rodada das 9h rodou, e o grupo Brasil saiu do zero?

Le o que o robo gravou de volta no repositorio. O grupo Brasil esta mudo
desde 09/10/2026 (tinha 321 alertas so em outubro) e na noite de 27/11
tambem veio zero. A suspeita e que ele estava desligado ate 27/11, quando os
5 grupos foram ligados — mas nao da pra provar: o channels_config.json nao
esta no git (tem chave em texto puro). Esta conferida responde.

ATENCAO AO FUSO: o sent_at e gravado em UTC (a maquina do GitHub roda em
UTC). A rodada das 9h de Brasilia e 12h UTC.
"""
import datetime, json, subprocess, sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

REPO = r"C:\Sistema Viagem\Onde As Milhas Me Levam"
GRUPOS = [("America do Sul","do_sul"), ("Europa","europa"),
          ("America do Norte","do_norte"), ("America Central/Caribe","america_central"),
          ("Brasil","brasil")]

def git(*a):
    r = subprocess.run(["git","-c","core.quotepath=false",*a], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout or ""

def arq(c):
    cod, s = git("show", f"origin/main:{c}")
    return s if cod == 0 else None

agora = datetime.datetime.now()
print(f"### Rodada das 9h — conferido em {agora:%d/%m/%Y %H:%M} (Brasilia)\n")
git("fetch","-q","origin","main")

marca = (arq("ultima_busca.txt") or "").strip()
hoje = f"{datetime.date.today():%Y-%m-%d}"
rodou = marca == f"{hoje}-09"
print("A RODADA DAS 9h RODOU?")
print("-"*64)
print(f"  ultima_busca.txt: {marca or '(vazio)'}")
print(f"  esperado se rodou: {hoje}-09")
print(f"  -> {'SIM, rodou' if rodou else 'ainda NAO (ou cedeu a vez pela cota)'}")
cota = (arq("cota_seats.txt") or "").strip()
if cota:
    p = cota.split()
    print(f"  cota: {cota}" + (f"  (gasto hoje: {1000-int(p[1])})" if len(p)==2 and p[1].isdigit() else ""))

corte = (datetime.datetime.now(datetime.timezone.utc)
         - datetime.timedelta(hours=6)).replace(tzinfo=None)
print(f"\nALERTAS DESDE {corte:%d/%m %H:%M} UTC")
print("-"*64)
cod, lista = git("ls-tree","--name-only","origin/main")
arquivos = [l.strip() for l in lista.splitlines()
            if l.startswith("historico_") and l.endswith(".json")]

brasil_novos, brasil_ultimo = None, None
for rotulo, pedaco in GRUPOS:
    a = next((x for x in arquivos if pedaco in x), None)
    if not a:
        print(f"  {rotulo:24} SEM ARQUIVO"); continue
    try: d = json.loads(arq(a) or "{}")
    except ValueError: d = {}
    al = [v for v in (d.get("alerts") or {}).values() if isinstance(v, dict)]
    novos, ultimo = [], ""
    for v in al:
        q = (v.get("sent_at") or "")[:19]
        ultimo = max(ultimo, q)
        try: t = datetime.datetime.fromisoformat(q)
        except ValueError: continue
        if t >= corte: novos.append((t, v.get("route"), v.get("source"), v.get("miles")))
    novos.sort()
    print(f"  {rotulo:24} {len(novos):3d} alertas   (ultimo de todos: {ultimo[:10] or '?'})")
    for t, r, s, m in novos[:3]:
        print(f"  {'':24}     {t:%H:%M} UTC {r} {s} {m}")
    if pedaco == "brasil":
        brasil_novos, brasil_ultimo = novos, ultimo

print("\n" + "="*64)
print("O GRUPO BRASIL SAIU DO ZERO?")
if brasil_novos is None:
    print("  Nao consegui ler o historico do Brasil.")
elif brasil_novos:
    print(f"  SIM — {len(brasil_novos)} alertas. Era so o grupo estar desligado mesmo.")
else:
    print(f"  NAO. Continua mudo; ultimo alerta em {brasil_ultimo[:10] or '?'}.")
    print("  Se a rodada das 9h RODOU e mesmo assim veio zero, nao e mais")
    print("  'grupo desligado': e regua. Olhar is_award/termometro pra")
    print("  regiao 'brasil', cabine economica, origens GIG e SDU,")
    print("  programas azul/smiles/latam/american.")
