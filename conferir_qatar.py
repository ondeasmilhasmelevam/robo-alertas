# -*- coding: utf-8 -*-
"""conferir_qatar.py — o Qatar merece voltar pra varredura?

POR QUE EXISTE
O programa `qatar` ficou ligado meses em dois grupos (Europa e America Central)
e nunca entregou UM alerta, enquanto iberia entregou 22 e british 15. Em
27/11/2026 ele foi desligado (PROGRAMAS_DESLIGADOS no engine.py) porque saindo
da America do Sul ele vai pra Doha, e `get_destination_region('DOH')` devolve
`asia` — regiao que nenhum dos 5 grupos compra. O robo pedia, recebia Doha e
jogava fora, cinco vezes por dia.

Ficou UMA duvida sem resposta: o Qatar Privilege Club tambem emite em parceiro
oneworld. Se o seats.aero devolver GRU->MAD na Iberia cobrado em Avios do
Qatar, o programa tem valor e deve voltar. Em 27/11 nao deu pra medir — a cota
do dia estava em zero (HTTP 429).

Este programa responde isso. Gasta 2 chamadas da API (de 1000 por dia) e nao
envia nada pra ninguem.

COMO RODAR
    python conferir_qatar.py
Depois das 21h de Brasilia, que e quando a cota da seats.aero vira (meia-noite
UTC). Antes disso pode dar 429.

COMO LER
Ele mostra, por programa, os destinos que voltam e em que regiao cada um cai.
Se na linha do qatar aparecer destino em regiao que algum grupo compra
(europa, america_sul, eua, america_central, brasil), o qatar TEM valor: tirar
"qatar" de PROGRAMAS_DESLIGADOS no engine.py. Se vier so Doha/asia, ele fica
desligado e o assunto esta encerrado.
"""
import sys
import collections
import requests

from channels import load_config
from engine import get_destination_region

# As regioes que os grupos do usuario realmente compram. Se um destino do
# qatar cair em qualquer uma delas, o alerta chegaria em alguem.
REGIOES_QUE_ALGUEM_COMPRA = {"europa", "america_sul", "eua",
                             "america_central", "brasil"}


def olhar(chave, programa, cabine="economy"):
    # /availability (nao /search): o /search exige origin_airport ou
    # destination_airport e devolve 400 "missing_airports" quando a gente
    # pergunta por regiao. E o mesmo endpoint que seats_api.bulk_availability
    # usa, so que aqui numa pagina unica, pra gastar 1 chamada em vez de 15.
    r = requests.get("https://seats.aero/partnerapi/availability",
                     params={"source": programa,
                             "origin_region": "South America",
                             "cabin": cabine, "take": 1000},
                     headers={"Partner-Authorization": chave,
                              "Accept": "application/json"},
                     timeout=90)
    sobrou = r.headers.get("X-Ratelimit-Remaining", "?")
    print(f"\n=== {programa.upper()} ({cabine}) — HTTP {r.status_code} "
          f"| cota restante: {sobrou}")
    if r.status_code == 429:
        print("    A cota do dia acabou. Rode depois das 21h de Brasilia.")
        return None
    if r.status_code != 200:
        print("   ", r.text[:300])
        return None

    dados = r.json().get("data", [])
    print(f"    {len(dados)} resultados brutos saindo da America do Sul")
    if not dados:
        print("    Nada. Esse programa nao tem award ex-America do Sul hoje.")
        return False

    porregiao = collections.Counter()
    exemplos = {}
    for d in dados:
        rota = d.get("Route", {})
        orig = rota.get("OriginAirport", "?")
        dest = rota.get("DestinationAirport", "?")
        reg = get_destination_region(dest) or "(sem regiao)"
        porregiao[reg] += 1
        exemplos.setdefault(reg, set()).add(f"{orig}->{dest}")

    serve = False
    for reg, n in porregiao.most_common():
        vale = reg in REGIOES_QUE_ALGUEM_COMPRA
        serve = serve or vale
        marca = "<<< ALGUM GRUPO COMPRA" if vale else "ninguem compra"
        rotas = ", ".join(sorted(exemplos[reg])[:6])
        print(f"      {reg:18} {n:5d}  {marca}")
        print(f"                         {rotas}")
    return serve


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = load_config()
    chave = cfg.get("seats_api_key")
    if not chave:
        print("Falta a chave do seats.aero (SEATS_API_KEY ou channels_config.json).")
        return 2

    # iberia entra como CONTROLE: ele comprovadamente entrega alerta, entao se
    # a linha dele vier vazia o problema e a consulta, nao o qatar.
    serve_qatar = olhar(chave, "qatar")
    olhar(chave, "iberia")

    print("\n" + "=" * 60)
    if serve_qatar is None:
        print("VEREDITO: nao deu pra medir. Rode depois das 21h.")
    elif serve_qatar:
        print("VEREDITO: o qatar TEM valor — apareceu destino que um grupo compra.")
        print("Religar: tirar \"qatar\" de PROGRAMAS_DESLIGADOS no engine.py.")
    else:
        print("VEREDITO: o qatar so vai pra onde ninguem compra. Fica desligado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
