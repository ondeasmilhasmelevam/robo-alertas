"""
Processador de Dados - v4
===========================
Sistema inteligente: SmartPricing adaptativo + fallback termometro.
Iberia/British/Qatar: faixa por distancia.
Demais: SmartPricing (historico) com fallback para termometro.
"""

import json, os, sys, logging
from collections import defaultdict
from typing import Optional
from distance_service import is_distance_award, get_distance, get_band
from smart_pricing import SmartPricing
from termometro import classify as tclassify, SEND_TIERS, tier_label as t_label, emit_via, reflect_warning, reflect_warning_carrier
try:
    from emission_tips import sweet_spot_tip
except Exception:
    def sweet_spot_tip(_s, _r):
        return ""
try:
    from rove_api import cash_paga, last_rate
except Exception:
    def cash_paga(*_a):
        return None
    def last_rate():
        return 5.20

logger = logging.getLogger("miles_bot")

def _rp(f):
    if hasattr(sys,'_MEIPASS'):return os.path.join(sys._MEIPASS,f)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),f)

def load_rules():
    try:
        with open(_rp("rules_config.json"),"r",encoding="utf-8") as f:return json.load(f)
    except:return {"distance_based_sources":["iberia","british","qatar"]}

try:
    from config import AWARD_RULES, AIRPORT_REGIONS, MAX_MILES_FALLBACK
except:
    AWARD_RULES={}; AIRPORT_REGIONS={}; MAX_MILES_FALLBACK=0

# Instancia global do SmartPricing
_smart_pricing = None
def get_smart_pricing():
    global _smart_pricing
    if _smart_pricing is None:
        _smart_pricing = SmartPricing()
    return _smart_pricing

CABIN_FIELDS = {
    "economy":  {"avail":"YAvailable","cost":"YMileageCost","seats":"YRemainingSeats","tax":"YTotalTaxes","airlines":"YAirlines","airlines_direct":"YDirectAirlines"},
    "premium":  {"avail":"WAvailable","cost":"WMileageCost","seats":"WRemainingSeats","tax":"WTotalTaxes","airlines":"WAirlines","airlines_direct":"WDirectAirlines"},
    "business": {"avail":"JAvailable","cost":"JMileageCost","seats":"JRemainingSeats","tax":"JTotalTaxes","airlines":"JAirlines","airlines_direct":"JDirectAirlines"},
    "first":    {"avail":"FAvailable","cost":"FMileageCost","seats":"FRemainingSeats","tax":"FTotalTaxes","airlines":"FAirlines","airlines_direct":"FDirectAirlines"},
}

def _parse_airlines(raw):
    """Quebra o campo *Airlines (ex: 'ET, LH' ou 'Ethiopian / Lufthansa')
    numa lista de tokens limpos. Tolerante a None/vazio."""
    if not raw:
        return []
    return [t.strip() for t in str(raw).replace("/", ",").split(",") if t.strip()]
CABIN_NAMES = {"economy":"Econômica","premium":"Premium Economy","business":"Executiva","first":"Primeira Classe"}

# ─── AEGEAN Miles+Bonus (Star Alliance) ─────────────────────────
# A Aegean NÃO é fonte do seats.aero. Mas todo voo Star Alliance (que aparece
# via turkish/aeroplan/united/copa/etc.) pode ser emitido via Aegean pelo
# preço FIXO baixo dela. Então, quando o alerta for de um programa Star
# Alliance em exec/first, anexamos a dica com o valor Aegean da região.
# Valores do mapa do aulão (milheiro ~R$68 comprando pontos no Revolut).
AEGEAN_STAR = {"turkish", "copa", "aeroplan", "united", "singapore", "lufthansa"}
AEGEAN_PRECO = {   # regiao -> cabine -> (milhas_em_mil, custo_aprox_R$)
    "europa":          {"business": (55, 3700), "first": (75, 5100)},
    "asia":            {"business": (75, 5100)},   # Ásia Oriental (Or. Médio ~55k)
    "eua":             {"business": (45, 3000)},
    "africa":          {"business": (55, 3700)},
    "america_central": {"business": (21, 1400)},
    "america_sul":     {"business": (21, 1400)},
}

def aegean_hint(source, region, cabin):
    """Dica: se for voo Star Alliance em exec/first, mostra o preço Aegean."""
    if source not in AEGEAN_STAR:
        return ""
    p = AEGEAN_PRECO.get(region, {}).get(cabin)
    if not p:
        return ""
    m, r = p
    return f"Star Alliance — dá p/ emitir via Aegean: ~{m}k milhas (~R$ {r:,})".replace(",", ".")

SOURCE_DISPLAY = {
    "azul":("Azul","TudoAzul / Azul Fidelidade"),"smiles":("GOL","Smiles"),"gol":("GOL","Smiles"),
    "aeroplan":("Air Canada","Aeroplan"),"american":("American Airlines","AAdvantage"),
    "delta":("Delta","SkyMiles"),"united":("United","MileagePlus"),
    "emirates":("Emirates","Skywards"),"turkish":("Turkish Airlines","Miles&Smiles"),
    "qatar":("Qatar Airways","Privilege Club"),"singapore":("Singapore Airlines","KrisFlyer"),
    "flyingblue":("Air France/KLM","Flying Blue"),"lufthansa":("Lufthansa","Miles & More"),
    "virginatlantic":("Virgin Atlantic","Flying Club"),"copa":("Copa Airlines","ConnectMiles"),
    "jetblue":("JetBlue","TrueBlue"),"alaska":("Alaska Airlines","Atmos Rewards"),
    "qantas":("Qantas","Frequent Flyer"),"etihad":("Etihad","Guest"),
    "finnair":("Finnair","Plus"),"iberia":("Iberia","Avios"),
    "british":("British Airways","Executive Club"),"latam":("LATAM","LATAM Pass"),
    "tap":("TAP","Miles&Go"),
}

AIRPORT_COUNTRIES = {
    "GIG":("Rio de Janeiro","\U0001f1e7\U0001f1f7"),"GRU":("São Paulo","\U0001f1e7\U0001f1f7"),
    "CNF":("Belo Horizonte","\U0001f1e7\U0001f1f7"),"BSB":("Brasília","\U0001f1e7\U0001f1f7"),
    "SDU":("Rio de Janeiro","\U0001f1e7\U0001f1f7"),"CGH":("São Paulo","\U0001f1e7\U0001f1f7"),
    "SSA":("Salvador","\U0001f1e7\U0001f1f7"),"REC":("Recife","\U0001f1e7\U0001f1f7"),
    "FOR":("Fortaleza","\U0001f1e7\U0001f1f7"),"MCZ":("Maceio","\U0001f1e7\U0001f1f7"),
    "POA":("Porto Alegre","\U0001f1e7\U0001f1f7"),"CWB":("Curitiba","\U0001f1e7\U0001f1f7"),
    "FLN":("Florianopolis","\U0001f1e7\U0001f1f7"),"NAT":("Natal","\U0001f1e7\U0001f1f7"),
    "BEL":("Belem","\U0001f1e7\U0001f1f7"),"MAO":("Manaus","\U0001f1e7\U0001f1f7"),
    "VCP":("Campinas","\U0001f1e7\U0001f1f7"),"AJU":("Aracaju","\U0001f1e7\U0001f1f7"),
    "JPA":("Joao Pessoa","\U0001f1e7\U0001f1f7"),"IGU":("Foz do Iguacu","\U0001f1e7\U0001f1f7"),
    "VIX":("Vitoria","\U0001f1e7\U0001f1f7"),"SLZ":("Sao Luis","\U0001f1e7\U0001f1f7"),
    "THE":("Teresina","\U0001f1e7\U0001f1f7"),"FEN":("Fernando de Noronha","\U0001f1e7\U0001f1f7"),
    "LHR":("Londres","\U0001f1ec\U0001f1e7"),"CDG":("Paris","\U0001f1eb\U0001f1f7"),
    "FCO":("Roma","\U0001f1ee\U0001f1f9"),"MXP":("Milao","\U0001f1ee\U0001f1f9"),
    "MAD":("Madrid","\U0001f1ea\U0001f1f8"),"BCN":("Barcelona","\U0001f1ea\U0001f1f8"),
    "LIS":("Lisboa","\U0001f1f5\U0001f1f9"),"OPO":("Porto","\U0001f1f5\U0001f1f9"),
    "FRA":("Frankfurt","\U0001f1e9\U0001f1ea"),"AMS":("Amsterdam","\U0001f1f3\U0001f1f1"),
    "IST":("Istambul","\U0001f1f9\U0001f1f7"),"DXB":("Dubai","\U0001f1e6\U0001f1ea"),
    "DOH":("Doha","\U0001f1f6\U0001f1e6"),"JFK":("Nova York","\U0001f1fa\U0001f1f8"),
    "MIA":("Miami","\U0001f1fa\U0001f1f8"),"LAX":("Los Angeles","\U0001f1fa\U0001f1f8"),
    "ORD":("Chicago","\U0001f1fa\U0001f1f8"),"MCO":("Orlando","\U0001f1fa\U0001f1f8"),
    "BOS":("Boston","\U0001f1fa\U0001f1f8"),"EZE":("Buenos Aires","\U0001f1e6\U0001f1f7"),
    "AEP":("Buenos Aires","\U0001f1e6\U0001f1f7"),"SCL":("Santiago","\U0001f1e8\U0001f1f1"),
    "LIM":("Lima","\U0001f1f5\U0001f1ea"),"BOG":("Bogotá","\U0001f1e8\U0001f1f4"),
    "ASU":("Assunção","\U0001f1f5\U0001f1fe"),"MVD":("Montevidéu","\U0001f1fa\U0001f1fe"),
    "MDE":("Medellín","\U0001f1e8\U0001f1f4"),"PDP":("Punta del Este","\U0001f1fa\U0001f1fe"),
    "PTY":("Panama","\U0001f1f5\U0001f1e6"),"MEX":("Cidade do Mexico","\U0001f1f2\U0001f1fd"),
    "CUN":("Cancun","\U0001f1f2\U0001f1fd"),"NRT":("Toquio","\U0001f1ef\U0001f1f5"),
    "SIN":("Singapura","\U0001f1f8\U0001f1ec"),"SYD":("Sydney","\U0001f1e6\U0001f1fa"),
}

FUN_FACTS = {
    "LHR":"Londres tem mais de 170 museus.",
    "CDG":"Paris recebe mais de 30 milhoes de turistas por ano.",
    "FCO":"Roma tem mais de 900 igrejas.",
    "LIS":"Lisboa e a capital mais antiga da Europa Ocidental.",
    "MAD":"Madrid tem o mercado de comida mais antigo da Europa.",
    "MIA":"Miami e conhecida como a capital das Americas.",
    "JFK":"Nova York tem mais de 800 idiomas falados.",
    "DXB":"Dubai tem o predio mais alto do mundo (828m).",
    "EZE":"Buenos Aires e chamada de Paris da America do Sul.",
    "SCL":"Santiago tem vista para a Cordilheira dos Andes.",
    "SSA":"Salvador foi a primeira capital do Brasil.",
    "REC":"Recife e chamada de Veneza Brasileira.",
    "FOR":"Fortaleza tem mais de 34 km de praias urbanas.",
    "FLN":"Florianopolis tem 42 praias paradisiacas.",
    "FEN":"Fernando de Noronha e Patrimonio da Humanidade pela UNESCO.",
    "IGU":"As Cataratas do Iguacu sao uma das 7 maravilhas naturais.",
    "POA":"Porto Alegre e a capital do churrasco.",
    "CWB":"Curitiba e referencia mundial em urbanismo.",
}

def parse_cost(value) -> Optional[int]:
    if value is None or value=="" or value=="0":return None
    try:return int(str(value).replace(",","").replace(".","").strip())
    except:return None

def airport_display(code):return AIRPORT_COUNTRIES.get(code,(code,"\u2708\ufe0f"))
def source_display(source):return SOURCE_DISPLAY.get(source,(source,source))
def get_destination_region(code):return AIRPORT_REGIONS.get(code,"")


def _is_award_distance(cost, source, origin, dest, cabin):
    """Filtro por faixa de distancia (Iberia/British/Qatar)."""
    is_good, band, distance, low_fare, high_fare = is_distance_award(cost, origin, dest, cabin)
    return is_good

def _is_award_termometro(cost, source, dest, cabin):
    """Filtro pelo termometro (fallback quando SmartPricing nao tem dados)."""
    region = get_destination_region(dest)
    if not region: return False
    cabin_suffix = "economy" if cabin == "economy" else "business"
    key = f"{region}_{cabin_suffix}"
    if key in AWARD_RULES:
        mx = AWARD_RULES[key].get(source, 0)
    elif region in AWARD_RULES:
        mx = AWARD_RULES[region].get(source, 0)
    else: return False
    return mx > 0 and cost <= mx


def _ceiling_for(source, dest, cabin):
    """
    Teto absoluto da regua (AWARD_RULES) para source+regiao+cabine.
    Retorna 0 quando nao ha teto definido (nesse caso, nao corta).

    - premium: usa teto _premium; se nao existir, cai no de business.
    - first:   usa teto _first; se nao existir, usa ~1.6x o de business.
    """
    region = get_destination_region(dest)
    if not region:
        return 0

    def rule(suffix):
        d = AWARD_RULES.get(f"{region}_{suffix}")
        return d.get(source, 0) if d else 0

    if cabin == "first":
        c = rule("first")
        if c:
            return c
        b = rule("business")
        return int(b * 1.6) if b else 0

    if cabin == "premium":
        c = rule("premium")
        return c if c else rule("business")

    # economy / business
    return rule(cabin)


def is_award(cost, source, origin, dest, cabin="business"):
    """
    Sistema inteligente de avaliacao:
    1. Iberia/British/Qatar -> faixa por distancia
    2. Demais -> SmartPricing (historico adaptativo) + fallback termometro
    3. TETO DURO da regua (AWARD_RULES) -> vale SEMPRE nos sources SmartPricing,
       mesmo que o SmartPricing tenha classificado como "otimo". Isso impede
       que precos absolutos absurdos passem so por serem baratos no historico
       da propria rota (ex: Smiles/Copa muito acima do chart do programa).
    """
    rules = load_rules()
    distance_sources = rules.get("distance_based_sources", ["iberia","british","qatar"])

    # Sistema 1: Iberia/British/Qatar (Avios).
    # PRIMEIRO tenta o termometro (valores Avios do mapa por regiao) — ele e
    # mais fiel que a tabela de distancia, que subestimava muito a economica
    # de longo curso (ex: Iberia GRU-MAD eco 42,5k era barrada). Se a regiao
    # nao estiver no termometro (Africa/Oceania/etc.), cai na faixa por distancia.
    if source in distance_sources:
        tier = tclassify(source, dest, cabin, cost)
        if tier is not None:
            if tier in SEND_TIERS:
                return True
            logger.info(f"Termometro cortou {source} {origin}->{dest} {cabin}: {cost:,} = {tier}")
            return False
        return _is_award_distance(cost, source, origin, dest, cabin)

    # Sistema 2: TERMOMETRO absoluto (regua do painel do Rudi)
    # Quando o termometro cobre a rota, ele decide: so passa BOM ou melhor.
    tier = tclassify(source, dest, cabin, cost)
    if tier is not None:
        if tier in SEND_TIERS:
            return True
        logger.info(f"Termometro cortou {source} {origin}->{dest} {cabin}: {cost:,} = {tier}")
        return False

    # MODO ESTRITO (rules_config "exigir_regua"): sem regua para este
    # programa/regiao/cabine, NAO envia. O pedido do usuario e que so entre o que
    # a regua classifica como espetacular/muito bom/bom; cair no SmartPricing
    # (historico relativo da rota) deixaria passar coisa fora desse criterio.
    # Os Avios nao chegam aqui: eles saem antes, pela tabela de distancia.
    if rules.get("exigir_regua", True):
        logger.info(f"Sem regua para {source} {origin}->{dest} {cabin}: cortado (modo estrito)")
        return False

    # Sistema 3: SmartPricing adaptativo (fallback quando termometro nao cobre)
    sp = get_smart_pricing()
    evaluation = sp.evaluate(origin, dest, source, cabin, cost)

    if evaluation["decision"] == "send":
        relativo = True
    elif evaluation["decision"] == "skip":
        return False
    else:
        # Fallback: usar termometro quando historico insuficiente
        relativo = _is_award_termometro(cost, source, dest, cabin)

    if not relativo:
        return False

    # Sistema 3: TETO DURO da regua (guia) — corta valor super elevado
    teto = _ceiling_for(source, dest, cabin)
    if teto > 0 and cost > teto:
        logger.info(f"Regua cortou {source} {origin}->{dest} {cabin}: {cost:,} > teto {teto:,}")
        return False

    return True


# Programas onde vale a dica de UPGRADE (econômica -> executiva sai mais barato
# que a executiva cheia quando as DUAS cabines estão disponíveis no mesmo voo).
UPGRADE_SOURCES = {"smiles", "gol"}


def process_results(results, origin_airports, cabin="business", max_miles=0):
    """Processa resultados com sistema inteligente."""
    fields = CABIN_FIELDS.get(cabin, CABIN_FIELDS["business"])
    groups = defaultdict(list)
    rejected = 0
    sp = get_smart_pricing()

    for r in results:
        route = r.get("Route",{})
        origin = route.get("OriginAirport",r.get("OriginAirport",""))
        dest = route.get("DestinationAirport",r.get("DestinationAirport",""))
        source = r.get("Source",route.get("Source",""))

        if origin_airports and origin not in origin_airports: continue
        if not r.get(fields["avail"],False): continue

        cost = parse_cost(r.get(fields["cost"]))
        if cost is None or cost==0: continue

        # Registrar no SmartPricing (TODOS os precos, mesmo rejeitados)
        rules = load_rules()
        dist_sources = rules.get("distance_based_sources",["iberia","british","qatar"])
        if source not in dist_sources:
            sp.record_price(origin, dest, source, cabin, cost)

        # Filtro inteligente
        if not is_award(cost, source, origin, dest, cabin):
            rejected += 1
            continue

        date = r.get("Date","")
        if isinstance(date,str) and "T" in date: date = date.split("T")[0]
        seats = r.get(fields["seats"],0) or 0
        tax = r.get(fields["tax"],0) or 0
        airlines = _parse_airlines(r.get(fields.get("airlines"))) + \
                   _parse_airlines(r.get(fields.get("airlines_direct")))

        # UPGRADE: se for ECONÔMICA no Smiles/GOL e a EXECUTIVA também estiver
        # verde no MESMO voo/data, guarda o custo dela. (Dá pra pedir econômica
        # e fazer o upgrade — costuma sair mais barato que a executiva cheia.)
        biz_cost = None
        if cabin == "economy" and source in UPGRADE_SOURCES:
            bf = CABIN_FIELDS["business"]
            if r.get(bf["avail"], False):
                biz_cost = parse_cost(r.get(bf["cost"]))

        key = (origin,dest,source)
        groups[key].append({"date":date,"seats":seats,"cost":cost,"tax":tax,
                            "airlines":airlines,"biz_cost":biz_cost})

    alerts = []
    for (origin,dest,source), entries in groups.items():
        entries.sort(key=lambda x:x["date"])

        # Usar o MENOR preco como principal (melhor oferta)
        costs = [e["cost"] for e in entries]
        min_cost = min(costs)

        # Tolerancia: incluir datas ate 10% acima do menor preco
        tolerance = min_cost * 1.10
        good_entries = [e for e in entries if e["cost"] <= tolerance]

        # Se nenhuma data ficou apos filtro, pegar as do menor preco exato
        if not good_entries:
            good_entries = [e for e in entries if e["cost"] == min_cost]

        taxes = [e["tax"] for e in good_entries if e["tax"]>0]
        main_tax = taxes[0] if taxes else 0
        companhia,programa = source_display(source)
        region = get_destination_region(dest)
        dist = get_distance(origin,dest)
        band = get_band(dist) if dist>0 else 0

        # Obter score do SmartPricing
        stats = sp.get_route_stats(origin,dest,source,cabin)
        score = 50  # default
        classification = "desconhecido"
        rules = load_rules()
        if source not in rules.get("distance_based_sources",[]):
            ev = sp.evaluate(origin,dest,source,cabin,min_cost)
            score = ev["score"]
            classification = ev["classification"]

        alert = {
            "origin":origin,"destination":dest,
            "source":source,"companhia":companhia,"programa":programa,
            "cabin":cabin,"cabin_name":CABIN_NAMES.get(cabin,cabin),
            "miles":min_cost,"tax":main_tax,"tax_currency":"BRL",
            "region":region,"distance":round(dist) if dist>0 else 0,"band":band,
            "score":score,"classification":classification,
            "dates":[{"date":e["date"],"seats":e["seats"],"cost":e["cost"]} for e in good_entries],
        }
        # Termometro "A Verdade das Milhas": selo (espetacular/muito bom/bom) + parceria
        tier = tclassify(source, dest, cabin, min_cost)
        alert["tier"] = tier or ""
        alert["tier_label"] = t_label(tier) if tier else ""
        alert["emit_via"] = emit_via(source)
        # Aviso "pode nao refletir": por programa (source) OU por cia operadora.
        all_airlines = set()
        for e in good_entries:
            all_airlines.update(e.get("airlines", []))
        alert["warn_reflect"] = reflect_warning(source) or reflect_warning_carrier(all_airlines)
        alert["aegean"] = aegean_hint(source, region, cabin)
        alert["sweet"] = sweet_spot_tip(source, region)
        # UPGRADE p/ executiva: menor custo de exec entre as datas onde ela
        # também estava disponível junto com a econômica.
        biz_costs = [e["biz_cost"] for e in good_entries if e.get("biz_cost")]
        alert["upgrade_exec"] = min(biz_costs) if biz_costs else 0
        # Preço PAGO real (Rove), se disponível pra essa rota/cabine.
        cp = cash_paga(origin, dest, cabin)
        if cp:
            alert["cash_usd"] = cp[0]
            alert["cash_carrier"] = cp[1]
            alert["cash_brl"] = round(cp[0] * last_rate())
        alerts.append(alert)

    # Salvar historico periodicamente
    sp.save_periodically()

    logger.info(f"Processadas {len(alerts)} rotas AWARD de {len(results)} resultados ({rejected} rejeitados)")
    return alerts
