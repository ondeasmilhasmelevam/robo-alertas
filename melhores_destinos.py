"""
Melhores Destinos v5
======================
MD atrelado ao canal: cada canal decide se quer MD e recebe so sua regiao.
Classificacao corrigida. Caracteres limpos.
"""
import re, json, os, sys, hashlib, logging
import xml.etree.ElementTree as ET
from datetime import datetime
import requests

logger = logging.getLogger("miles_bot")

RSS_URLS = [
    "http://www.melhoresdestinos.com.br/category/promocao-de-milhas/feed",
    "http://www.melhoresdestinos.com.br/feed",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
HISTORY_FILE = "md_history.json"

KW_EXCLUDE = [
    "compre milhas","compra de milhas","venda de milhas",
    "transferencia de pontos","transferir pontos","bonus na transferencia",
    "pagol","maxmilhas","clube smiles","assine o clube","assinatura",
    "cartao de credito","cartoes de credito","ranking de cartoes",
    "seguro viagem","cruzeiro","hotel","hoteis","resort","hospedagem",
    "mala","bagagem","visto","passaporte","milheiro",
    "comprar pontos","compre pontos","bonus ao transferir",
    "livelo","esfera","chip internacional","aluguel de carro",
]

REGIONS = {
    "brasil": {
        "label": "Brasil",
        "keywords": ["nacional","domestico","brasil",
            "salvador","recife","fortaleza","natal","maceio","florianopolis",
            "porto alegre","curitiba","belo horizonte","brasilia","manaus",
            "belem","fernando de noronha","rio de janeiro","sao paulo",
            "foz do iguacu","vitoria","aracaju","joao pessoa","sao luis",
            "cuiaba","goiania","campo grande","teresina","porto seguro",
            "buzios","paraty","jericoacoara","chapada","lencois","bonito",
            "gramado","cnf","ssa","rec","for","nat","mcz","fln","poa","cwb",
            "bsb","mao","bel","fen","igu","vix","gig","gru","sdu","cgh"],
    },
    "europa": {
        "label": "Europa",
        "keywords": ["europa","londres","london","paris","roma","rome","madrid",
            "barcelona","lisboa","lisbon","porto","amsterdam","frankfurt",
            "munique","munich","milao","milan","zurique","viena",
            "bruxelas","dublin","atenas","istambul","praga","budapeste",
            "edimburgo","copenhague","oslo","estocolmo","santorini",
            "italia","franca","espanha","portugal","alemanha","holanda",
            "turquia","grecia","suica","belgica","irlanda","austria",
            "reino unido","inglaterra","escocia"],
    },
    "eua": {
        "label": "EUA / Canada",
        "keywords": ["estados unidos","eua","usa","nova york","new york","miami",
            "orlando","los angeles","chicago","san francisco","dallas",
            "houston","boston","washington","las vegas","atlanta","seattle",
            "fort lauderdale","toronto","montreal","vancouver","canada"],
    },
    "asia": {
        "label": "Asia / Oriente Medio",
        "keywords": ["asia","toquio","tokyo","japao","seul","coreia",
            "hong kong","singapura","bangkok","tailandia",
            "dubai","abu dhabi","doha","emirados","india",
            "kuala lumpur","china","maldivas","israel","tel aviv",
            "oriente medio","jordania","bali","indonesia","vietna"],
    },
    "america_sul": {
        "label": "America do Sul",
        "keywords": ["buenos aires","argentina","santiago","chile","lima","peru",
            "bogota","colombia","montevideu","uruguai","equador","quito",
            "paraguai","bolivia","patagonia","mendoza","bariloche",
            "cartagena das indias"],
    },
    "america_central": {
        "label": "Caribe e Mexico",
        "keywords": ["caribe","cancun","mexico","cidade do mexico","panama",
            "costa rica","havana","cuba","punta cana","republica dominicana",
            "aruba","curacao","jamaica","porto rico","san andres"],
    },
    "africa": {
        "label": "Africa",
        "keywords": ["africa","joanesburgo","cidade do cabo","cairo","egito",
            "marrocos","casablanca","africa do sul","quenia","tanzania","safari"],
    },
    "oceania": {
        "label": "Oceania",
        "keywords": ["oceania","sydney","melbourne","australia",
            "nova zelandia","auckland"],
    },
}

def _get_path():
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), HISTORY_FILE)

def _load_history():
    p = _get_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return set(json.load(f).get("sent_ids", []))
        except: pass
    return set()

def _save_history(ids):
    try:
        with open(_get_path(), "w", encoding="utf-8") as f:
            json.dump({"sent_ids": list(ids)[-1000:], "updated": datetime.now().isoformat()}, f, ensure_ascii=False)
    except: pass

def _make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]

def _clean_html(text):
    """Remove HTML tags e entidades."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&#8211;", "-").replace("&#8212;", "-")
    text = text.replace("&#8220;", '"').replace("&#8221;", '"')
    text = text.replace("&#8217;", "'").replace("&amp;", "&")
    text = text.replace("&nbsp;", " ").replace("&#039;", "'")
    return text.strip()

def _classify(text):
    """Classifica texto por regiao. Brasil tem prioridade sobre outros."""
    t = text.lower()
    regions = []

    # Brasil primeiro (para nao confundir rota nacional com internacional)
    br_kws = REGIONS["brasil"]["keywords"]
    # Verificar se AMBAS origem e destino sao Brasil
    has_br_origin = any(kw in t for kw in ["saindo de sao paulo","saindo de rio","saindo do rio",
        "saindo de recife","saindo de fortaleza","saindo de salvador",
        "saindo de belo horizonte","saindo de curitiba","saindo de brasilia",
        "saindo de porto alegre","saindo de florianopolis"])
    has_br_dest = any(kw in t for kw in ["para salvador","para recife","para fortaleza",
        "para natal","para maceio","para florianopolis","para porto alegre",
        "para curitiba","para belo horizonte","para brasilia","para manaus",
        "para belem","para fernando de noronha","para foz","para vitoria",
        "pelo brasil","destinos nacionais","voos nacionais","cidades brasileiras"])

    # So classifica como Brasil se menciona destino BR (nao so origem)
    if has_br_dest or ("nacional" in t) or ("domestico" in t) or ("pelo brasil" in t):
        regions.append("brasil")

    # Outras regioes
    for rkey, rdata in REGIONS.items():
        if rkey == "brasil": continue
        for kw in rdata["keywords"]:
            if kw in t:
                if rkey not in regions: regions.append(rkey)
                break

    return regions

def _is_passagem(text):
    t = text.lower()
    for kw in KW_EXCLUDE:
        if kw in t: return False
    if re.search(r'r\$\s*[\d\.]', t): return True
    if re.search(r'\d+[\.\d]*\s*(mil\s+)?(milhas|pontos|avios)', t): return True
    if any(w in t for w in ["passagens","passagem","voos para","voo para","voo direto",
        "voos diretos","trecho","ida e volta","saindo de","resgate"]): return True
    return False

def _extract(text):
    t = text.lower()
    info = {"reais":None,"milhas":None,"unidade":"milhas","programa":None,"cabine":"Economica","origem":None,"destino":None}

    m = re.search(r'r\$\s*([\d\.]+[\,]?\d*)', t)
    if m: info["reais"] = m.group(1)

    m = re.search(r'(\d+[\.\d]*)\s*(mil\s+)?(milhas|pontos|avios)', t)
    if m:
        val = m.group(1).replace(".", "")
        try:
            v = int(val)
            if m.group(2): v *= 1000
            info["milhas"] = v; info["unidade"] = m.group(3)
        except: pass

    progs = {"smiles":"Smiles","tudoazul":"TudoAzul","azul":"Azul",
        "latam pass":"LATAM Pass","latam":"LATAM","avios":"Avios","iberia":"Iberia",
        "flying blue":"Flying Blue","tap":"TAP","gol":"GOL/Smiles",
        "american":"AAdvantage","privilege club":"Qatar Airways"}
    for k, v in progs.items():
        if k in t: info["programa"] = v; break

    if any(w in t for w in ["executiva","business"]): info["cabine"] = "Executiva"

    # Extrair origem
    m = re.search(r'saindo d[eo]\s+([A-Z][\w\s]*?)(?:\s+(?:a partir|por|com|para|\d|,|\-))', text)
    if m: info["origem"] = m.group(1).strip()

    # Extrair destino
    m = re.search(r'(?:para|rumo a|destino)\s+([A-Z][\w\s]*?)(?:\s+(?:a partir|por|com|saindo|\d|,|\-))', text)
    if m: info["destino"] = m.group(1).strip()

    return info

def _format(title, info, region_label):
    """Formato limpo e direto."""
    lines = []

    # Rota se disponivel
    if info.get("origem") and info.get("destino"):
        lines.append(f"\u2708\ufe0f {info['origem']} -> {info['destino']}")
    elif info.get("destino"):
        lines.append(f"\u2708\ufe0f Destino: {info['destino']}")
    lines.append("")

    if info.get("milhas"):
        val = f"{info['milhas']:,}".replace(",",".")
        lines.append(f"\U0001f4b0 {val} {info['unidade']} o trecho")
    elif info.get("reais"):
        lines.append(f"\U0001f4b0 R$ {info['reais']} ida e volta")

    if info.get("programa"):
        lines.append(f"\U0001f3f7\ufe0f {info['programa']}")
    if info["cabine"] != "Economica":
        lines.append(f"\U0001f4ba {info['cabine']}")

    lines.append("")
    lines.append(f"\U0001f4cc {title}")
    lines.append("")
    lines.append(f"\u26a1 Corra, procos assim acabam rapido!")

    return "\n".join(lines)


def fetch_md_promos(callback=None):
    def log(msg):
        logger.info(f"[MD] {msg}")
        if callback: callback(f"[MD] {msg}")

    log("Buscando promocoes...")
    promos = []

    for url in RSS_URLS:
        try:
            resp = requests.get(url, timeout=15, headers=HEADERS)
            if resp.status_code != 200: continue
            root = ET.fromstring(resp.content)
            channel = root.find("channel")
            if channel is None: continue
            items = channel.findall("item")

            for item in items:
                title = _clean_html(item.findtext("title", ""))
                link = item.findtext("link", "").strip()
                desc = _clean_html(item.findtext("description", ""))
                if not title: continue
                full_text = f"{title} {desc}"
                if not _is_passagem(full_text): continue

                regions = _classify(full_text)
                info = _extract(full_text)
                promos.append({"id": _make_id(f"{title}|{link}"), "title": title,
                    "regions": regions, "info": info})

            if promos: break
        except Exception as e:
            log(f"Erro: {e}")

    log(f"{len(promos)} promocoes de passagens")
    return promos


def send_md_for_channel(promos, bot, channel, callback=None):
    """`bot` pode ser o objeto do bot (tem .for_chat) ou o token em texto.

    Aceitar os dois e de proposito: em modo teste quem chega aqui e o
    BotDeTeste, e passando so o token a gente perdia isso e mandava de
    verdade pro grupo.
    """
    """Envia promos MD filtradas para UM canal especifico."""
    import time
    def log(msg):
        logger.info(f"[MD] {msg}")
        if callback: callback(f"[MD] {msg}")

    if not channel.get("melhores_destinos", False):
        return 0

    ch_regions = channel.get("regions", [])
    chat_id = channel["chat_id"]
    ch_name = channel["name"]

    sent_ids = _load_history()
    total = 0

    for promo in promos:
        if promo["id"] in sent_ids: continue
        promo_regions = promo["regions"]

        # So envia se a regiao da promo bate com o canal
        matching = [r for r in promo_regions if r in ch_regions]
        if not matching:
            # Se promo nao tem regiao e nao e o ideal, pular
            if not promo_regions:
                continue
            continue

        region_label = REGIONS.get(matching[0], {}).get("label", "")
        msg = _format(promo["title"], promo["info"], region_label)

        if hasattr(bot, "for_chat"):
            ch_bot = bot.for_chat(chat_id)
        else:
            from telegram_bot import TelegramBot
            ch_bot = TelegramBot(bot, chat_id)
        if ch_bot.send_message(msg):
            total += 1
            log(f"-> {ch_name}: {promo['title'][:50]}...")
        time.sleep(1.5)

        sent_ids.add(promo["id"])

    _save_history(sent_ids)
    if total > 0: log(f"{ch_name}: {total} promos MD enviadas")
    return total
