# -*- coding: utf-8 -*-
"""conferir_brasil.py — por que o grupo Brasil esta mudo desde 09/10/2026?

POR QUE EXISTE
O grupo "OndeAsMilhasMeLevam Brasil" esta LIGADO (enabled=True), e varrido
em toda rodada completa e nao entrega alerta nenhum desde 09/10/2026 — tendo
entregue 321 em outubro. Hipotese descartada: nao e "grupo desligado".
Sobram duas: (a) a API nao devolve voo domestico ex-GIG/SDU, ou (b) devolve e
a regua corta tudo.

Este programa responde qual das duas. Gasta 1 chamada por programa (4 no
total, de 1000 por dia) e NAO envia nada pra ninguem.

COMO RODAR
    python conferir_brasil.py
Depois das 21h de Brasilia, que e quando a cota vira (meia-noite UTC).

COMO LER
- "0 resultados" nos quatro -> a API nao tem domestico: nao e regua, e oferta.
- resultados vindo e todos ACIMA do teto -> e regua: o teto de
  config.py/brasil_economy esta abaixo do que o mercado pratica hoje.
- resultados vindo e algum ABAIXO do teto -> o problema nao e nem um nem
  outro: olhar o historico (memoria de melhor preco) e o is_award.
"""
import collections
import requests

from channels import load_config
from config import AWARD_RULES
from engine import get_destination_region

ORIGENS = {"GIG", "SDU"}
PROGRAMAS = ["azul", "smiles", "latam", "american"]
TETOS = AWARD_RULES["brasil_economy"]


def olhar(chave, programa):
    r = requests.get("https://seats.aero/partnerapi/availability",
                     params={"source": programa,
                             "origin_region": "South America",
                             "cabin": "economy", "take": 1000},
                     headers={"Partner-Authorization": chave,
                              "Accept": "application/json"},
                     timeout=90)
    sobrou = r.headers.get("X-Ratelimit-Remaining", "?")
    print(f"\n=== {programa.upper()} — HTTP {r.status_code} | cota restante: {sobrou}")
    if r.status_code == 429:
        print("    Cota do dia acabou. Rode depois das 21h de Brasilia.")
        return None
    if r.status_code != 200:
        print("   ", r.text[:300])
        return None

    dados = r.json().get("data", [])
    print(f"    {len(dados)} resultados brutos ex-America do Sul")

    teto = TETOS.get(programa)
    dentro, fora, rotas = [], [], collections.Counter()
    for d in dados:
        rota = d.get("Route", {})
        orig = rota.get("OriginAirport", "?")
        dest = rota.get("DestinationAirport", "?")
        if orig not in ORIGENS:
            continue
        if get_destination_region(dest) != "brasil":
            continue
        milhas = d.get("YMileageCostRaw") or d.get("YMileageCost") or 0
        try:
            milhas = int(str(milhas).replace(".", "").replace(",", "") or 0)
        except ValueError:
            milhas = 0
        rotas[f"{orig}->{dest}"] += 1
        if milhas and teto and milhas <= teto:
            dentro.append((f"{orig}->{dest}", milhas))
        else:
            fora.append((f"{orig}->{dest}", milhas))

    print(f"    domestico saindo de GIG/SDU: {len(dentro) + len(fora)}")
    if not rotas:
        print("    NENHUM voo domestico ex-GIG/SDU neste programa.")
        return "sem-oferta"
    print(f"    teto da regua ({programa}): {teto:,} milhas".replace(",", "."))
    print(f"    PASSARIAM na regua: {len(dentro)}   cortados: {len(fora)}")
    for rota, m in sorted(dentro, key=lambda x: x[1])[:5]:
        print(f"       dentro: {rota:12s} {m:>9,}".replace(",", "."))
    for rota, m in sorted(fora, key=lambda x: x[1])[:5]:
        print(f"       cortado: {rota:12s} {m:>9,}".replace(",", "."))
    return "dentro" if dentro else "regua"


def main():
    cfg = load_config()
    chave = cfg.get("seats_api_key", "")
    if not chave:
        print("Sem seats_api_key no channels_config.json.")
        return

    veredito = [olhar(chave, p) for p in PROGRAMAS]
    print("\n" + "=" * 60)
    print("VEREDITO")
    if all(v is None for v in veredito):
        print("  Nao deu pra medir (cota). Rode depois das 21h.")
    elif all(v in (None, "sem-oferta") for v in veredito):
        print("  A API NAO devolve domestico ex-GIG/SDU. Nao e regua:")
        print("  e oferta. O grupo Brasil so volta a falar quando aparecer")
        print("  award domestico — ou mudando as origens/regiao do grupo.")
    elif any(v == "dentro" for v in veredito):
        print("  Tem voo PASSANDO na regua. Entao nao e regua nem oferta:")
        print("  o corte esta depois — memoria de melhor preco ou is_award.")
    else:
        print("  Tem voo, mas TODOS acima do teto. E REGUA.")
        print("  O teto de brasil_economy em config.py esta abaixo do")
        print("  que o mercado domestico pratica hoje.")


if __name__ == "__main__":
    main()
