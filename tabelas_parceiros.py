# -*- coding: utf-8 -*-
"""Tabelas oficiais de utilizacao de Avios, por parceira — EPOCA BAIXA.

DE ONDE VEM
iberia.com/br/iberia-club/comprar-voos-avios/#tablas -> clicar no logo da
companhia. Cada parceira oneworld tem a SUA tabela; nao da pra julgar uma
pela tabela da outra. Valores POR TRAJETO (ida e volta = o dobro).

POR QUE ISSO EXISTE
Ate 28/11/2026 o robo julgava iberia, british e qatar todos pela tabela de
distancia da Iberia. Resultado: o qatar nunca entregou UM alerta em toda a
historia, porque os precos dele sao de OUTRA tabela. Medido em 28/11/2026,
17 precos reais que o seats.aero devolveu pro qatar: 11 batem EXATO com uma
tabela de parceira (8 na de parceiro/Finnair, 3 na da British) e os 6 que nao
batem com nenhuma sao justamente os caros (45.000, 90.000, 180.000) — epoca
alta ou sobretaxa.

DAI A REGRA, que e melhor que qualquer piso chutado: se o preco e EXATAMENTE
um valor da tabela daquela banda de distancia, e award de epoca baixa e vale
alertar. Se nao e, nao vale. A tabela decide rota por rota, pela distancia —
ninguem precisa adivinhar um numero.

COMO ACRESCENTAR UMA PARCEIRA
Copiar a tabela da pagina dela e por aqui embaixo no mesmo formato. O teto de
cada faixa e o limite SUPERIOR em milhas. Use None onde a companhia nao vende
a cabine (a premium da American e da Finnair, por exemplo, so existe em
combinacao com voo do grupo Iberia).
"""

# teto_de_milhas -> {cabine: avios}. A ultima faixa cobre o resto.
FINNAIR = [
    (650,   {"economy":  6000, "premium":   9000, "business":  12500, "first":  24000}),
    (1151,  {"economy":  9000, "premium":  12500, "business":  16500, "first":  33000}),
    (2000,  {"economy": 11000, "premium":  16500, "business":  22000, "first":  44000}),
    (3000,  {"economy": 13000, "premium":  25750, "business":  38750, "first":  51500}),
    (4000,  {"economy": 20750, "premium":  41250, "business":  62000, "first":  82500}),
    (5500,  {"economy": 25750, "premium":  51500, "business":  77250, "first": 103000}),
    (6500,  {"economy": 31000, "premium":  62000, "business":  92750, "first": 123750}),
    (7000,  {"economy": 36250, "premium":  72250, "business": 108250, "first": 144250}),
    (11770, {"economy": 51500, "premium": 103000, "business": 154500, "first": 206000}),
]

BRITISH = [
    (650,   {"economy": 10000, "premium":  None, "business":  16500, "first":   None}),
    (1151,  {"economy": 13000, "premium":  None, "business":  22000, "first":   None}),
    (2000,  {"economy": 15000, "premium":  None, "business":  26750, "first":   None}),
    (3000,  {"economy": 24750, "premium": 41250, "business":  77000, "first":  46750}),
    (4000,  {"economy": 27500, "premium": 46750, "business":  88000, "first":  75000}),
    (5500,  {"economy": 33000, "premium": 52250, "business":  99000, "first":  93500}),
    (6500,  {"economy": 38500, "premium": 55000, "business": 110000, "first": 112250}),
    (7000,  {"economy": 44000, "premium": 60500, "business": 121000, "first": 131000}),
    (99999, {"economy": 55000, "premium": 88000, "business": 159500, "first": 187000}),
]

AMERICAN = [
    (650,   {"economy": 13500, "premium":  20000, "business":  26500, "first":  51000}),
    (1151,  {"economy": 18000, "premium":  26500, "business":  35500, "first":  70500}),
    (2000,  {"economy": 20000, "premium":  35500, "business":  44000, "first":  79500}),
    (3000,  {"economy": 22000, "premium":  44000, "business":  55000, "first":  88000}),
    (4000,  {"economy": 23000, "premium":  45500, "business":  68500, "first":  91000}),
    (5500,  {"economy": 28500, "premium":  57000, "business":  85000, "first": 113500}),
    (6500,  {"economy": 34500, "premium":  68500, "business": 102500, "first": 136500}),
    (7000,  {"economy": 40000, "premium":  80500, "business": 119500, "first": 159000}),
    (11770, {"economy": 57000, "premium": 113500, "business": 170000, "first": 227000}),
]

# Royal Air Maroc. Da banda 3.001 pra cima e IDENTICA a American; so as
# quatro primeiras faixas diferem. Mantida separada de proposito: sao duas
# tabelas oficiais distintas e a Iberia pode mexer numa sem mexer na outra.
ROYAL_AIR_MAROC = [
    (650,   {"economy":  6500, "premium":  10000, "business":  14000, "first":  26500}),
    (1151,  {"economy": 10000, "premium":  14000, "business":  18500, "first":  36500}),
    (2000,  {"economy": 12500, "premium":  18500, "business":  24500, "first":  48500}),
    (3000,  {"economy": 14500, "premium":  28500, "business":  43000, "first":  57000}),
    (4000,  {"economy": 23000, "premium":  45500, "business":  68500, "first":  91000}),
    (5500,  {"economy": 28500, "premium":  57000, "business":  85000, "first": 113500}),
    (6500,  {"economy": 34500, "premium":  68500, "business": 102500, "first": 136500}),
    (7000,  {"economy": 40000, "premium":  80500, "business": 119500, "first": 159000}),
    (11770, {"economy": 57000, "premium": 113500, "business": 170000, "first": 227000}),
]

# Nome do programa no seats.aero -> tabela dele.
# FALTAM, se um dia entrarem na configuracao: cathay, japan, malaysia, qantas,
# royal jordanian, srilankan, alaska, royal air maroc, fiji, oman, vueling,
# level, latam, avianca, binter. Cada uma tem a sua pagina no mesmo lugar.
TABELAS = {
    "finnair":  FINNAIR,
    "british":  BRITISH,
    "american": AMERICAN,
    "royalairmaroc": ROYAL_AIR_MAROC,
}

# A Iberia tem tabela propria (ja em avios_chart.band_for_miles) e o Qatar em
# metal proprio tem tabela por REGIAO (avios_chart.QATAR_OFFPEAK), nao por
# distancia — por isso nenhum dos dois entra no dicionario acima.


def piso(programa, milhas, cabine):
    """O valor de epoca baixa da tabela daquela parceira, ou None."""
    tab = TABELAS.get(programa)
    if tab is None or milhas is None:
        return None
    for teto, faixa in tab:
        if milhas <= teto:
            return faixa.get(cabine)
    return None


def e_valor_de_tabela(custo, milhas, cabine, programas=None, vizinha=True):
    """O preco e EXATAMENTE um valor de epoca baixa de alguma tabela?

    Devolve a lista de tabelas em que bateu (vazia = nao bateu em nenhuma).

    `vizinha=True` tambem aceita a banda de cima e a de baixo, porque a
    distancia oficial da companhia nao e a mesma que o haversine calcula: em
    28/11/2026 o GIG->LHR executiva 121.000 e a banda 8 da British, mas pelo
    haversine (5.750 mi) o voo cai na banda 7. Errar a banda por pouco nao
    pode fazer a gente descartar um award legitimo.
    """
    if custo is None or milhas is None:
        return []
    achou = []
    for nome in (programas or TABELAS):
        tab = TABELAS.get(nome)
        if not tab:
            continue
        i_faixa = next((i for i, (t, _) in enumerate(tab) if milhas <= t), None)
        if i_faixa is None:
            continue
        janela = (i_faixa,) if not vizinha else (i_faixa - 1, i_faixa, i_faixa + 1)
        for i in janela:
            if 0 <= i < len(tab) and tab[i][1].get(cabine) == custo:
                achou.append(nome)
                break
    return achou
