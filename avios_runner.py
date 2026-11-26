# -*- coding: utf-8 -*-
"""
Runner Avios — varre a Avios.com (oficial) e manda alertas no Telegram
======================================================================
Roda por trás (thread), em baixa frequência (2x/dia por padrão). Para cada rota
Avios (Iberia/British saindo do Brasil), varre o calendário (hover), classifica
pelo termômetro (faixa Avios europa) e envia no canal Europa — com dedup pelo
mesmo histórico do canal. Ver [[seats-gap-iberia-avios]].
"""
import time
import threading
import logging
from datetime import datetime

import avios_api
import avios_chart
from termometro import SEND_TIERS, tier_label
from telegram_bot import TelegramBot
from history import AlertHistory

logger = logging.getLogger("miles_bot")

# Destinos Avios cobertos pelo site oficial (Iberia = MAD/BCN, British = LHR).
DEFAULT_DESTINATIONS = ["MAD", "LHR", "BCN"]

# Fallback só se o canal não tiver origens configuradas.
DEFAULT_ROUTES = [("GIG", "MAD"), ("GIG", "LHR"), ("GIG", "BCN")]


def routes_for_channel(ch, cfg):
    """
    Rotas Avios do canal: ORIGENS do canal x DESTINOS AVIOS do canal (campo
    'Destinos Avios' no editor). Assim dá pra ter um canal só Rio->Madri, outro
    com outra combinação. Cai no padrão global se o canal não definir destinos.
    """
    origens = [o for o in (ch.get("origins") or []) if o in avios_chart.AIRPORT_COORDS]
    destinos = (ch.get("avios_destinations")
                or cfg.get("avios_destinations") or DEFAULT_DESTINATIONS)
    if not origens:
        return list(DEFAULT_ROUTES)
    return [(o, d) for o in origens for d in destinos if o != d]


def channels_for_avios(cfg):
    """
    Canais que devem ser varridos pelo Avios: os ativos que tenham 'Destinos
    Avios' preenchido. Se nenhum tiver, cai no canal Europa (comportamento antigo).
    """
    ativos = [c for c in cfg.get("channels", []) if c.get("enabled", True)]
    com_dest = [c for c in ativos if c.get("avios_destinations")]
    if com_dest:
        return com_dest
    eu = _europa_channel(cfg)
    return [eu] if eu else []

PROGRAM_LABEL = {"iberia": "Iberia Plus", "british": "British Airways",
                 "qatar": "Qatar Airways (via Iberia Club)"}
PROGRAM_SHORT = {"iberia": "Ibéria", "british": "British", "qatar": "Qatar"}
CABIN_PT = {"economy": "Econômica", "premium": "Premium",
            "business": "Executiva", "first": "Primeira"}
MONTHS_PT = {1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
             7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"}
CITY_NAMES = {
    "GIG": "Rio de Janeiro", "GRU": "São Paulo", "VCP": "Campinas",
    "SSA": "Salvador", "REC": "Recife", "FOR": "Fortaleza", "BSB": "Brasília",
    "CNF": "Belo Horizonte", "POA": "Porto Alegre", "BEL": "Belém", "NAT": "Natal",
    "MAD": "Madrid", "BCN": "Barcelona", "LHR": "Londres", "AMS": "Amsterdã",
    "LIS": "Lisboa", "CDG": "Paris", "FCO": "Roma", "FRA": "Frankfurt",
    "DXB": "Dubai", "DOH": "Doha", "GRU": "São Paulo",
}


def _source_for(dest):
    """
    Quem opera o trecho: Doha = Qatar (resgate pelo Iberia Club),
    Londres = British, resto = Iberia.
    """
    if dest == "DOH":
        return "qatar"
    return "british" if dest == "LHR" else "iberia"


def _hist_file(name):
    slug = name.replace(" ", "_").replace("/", "_").replace(chr(92), "_").lower()
    return f"historico_{slug}.json"


def _europa_channel(cfg):
    for ch in cfg.get("channels", []):
        regs = [r.lower() for r in ch.get("regions", [])]
        if "europa" in regs and ch.get("enabled", True):
            return ch
    return None


def _fmt_k(n):
    """20000 -> '20' ; 40500 -> '40,5' ; 31250 -> '31,25'."""
    return f"{n / 1000:g}".replace(".", ",")


def _dates_by_month(dates):
    """
    Lista de 'YYYY-MM-DD' -> agrupado por ANO e depois por mês:
        2026
          NOV: 19
        2027
          FEV: 25
    (sem o ano ninguém entende: a janela é de 12 meses e vira o ano no meio.)
    """
    by = {}
    for d in sorted(dates):
        by.setdefault(int(d[:4]), {}).setdefault(int(d[5:7]), []).append(d[8:10])
    linhas = []
    for ano, meses in sorted(by.items()):
        linhas.append(f"    ▸ {ano}")
        for m, dias in sorted(meses.items()):
            linhas.append(f"       {MONTHS_PT[m]}: {','.join(dias)}")
    return "\n".join(linhas)


def format_alert(a):
    src = a["source"]
    prog = PROGRAM_LABEL.get(src, src.title())
    progs = PROGRAM_SHORT.get(src, src.title())
    cab = CABIN_PT.get(a["cabin"], a["cabin"])
    tl = tier_label(a.get("tier", "")) or a.get("tier", "").upper()
    city_o = CITY_NAMES.get(a["origin"], a["origin"])
    city_d = CITY_NAMES.get(a["destination"], a["destination"])
    seats = a.get("seats")
    linhas = [
        f"🗺️ Rota: 🛫 {city_o} ({a['origin']}) 🛬 {city_d} ({a['destination']})",
        f"🌐 Programa: {prog} (Milhas Avios)",
        f"💲 Custo: {_fmt_k(a['miles'])} mil Avios/trecho + taxas",
        f"🌡️ {tl} (época baixa)",
        f"🔄 Trajeto: Ida e/ou volta",
        f"💺 Cabine: {cab} - {progs}",
    ]
    if a.get("dates_ida"):
        linhas.append("\n    Datas Ida:\n" + _dates_by_month(a["dates_ida"]))
    if a.get("dates_volta"):
        linhas.append("\n    Datas Volta:\n" + _dates_by_month(a["dates_volta"]))
    smax = a.get("seats_max")
    if seats and smax and smax != seats:
        nota = f"*Assentos: de {seats} a {smax} por data (varia)."
    elif seats:
        nota = f"*Todas as datas com {seats} assento(s)."
    else:
        nota = "*Disponibilidade sujeita a alteração."
    linhas.append("\n" + nota)
    return "\n".join(linhas)


LOG_FILE = "avios.log"


def _com_arquivo(log):
    """Tudo que o Avios loga vai TAMBÉM pro avios.log (com data/hora) — antes só
    existia na tela e não dava pra saber o que aconteceu de madrugada."""
    if getattr(log, "_grava_arquivo", False):
        return log

    def _log(msg):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
        except Exception:
            pass
        try:
            log(msg)
        except Exception:
            pass
    _log._grava_arquivo = True
    return _log


def run_once(cfg, log=print, send=True, routes=None, months=None, page=None):
    """
    Varredura completa: percorre os CANAIS configurados pro Avios (cada um com
    suas origens e destinos) e envia os alertas no chat de cada canal.
    Se `page` for passado, reaproveita; senão sobe o Chrome e conecta.
    """
    log = _com_arquivo(log)
    avios_api.reset_session_urls()      # formulário 1x por par de aeroportos
    t0 = time.time()
    log(f"[Avios] ===== varredura iniciada {datetime.now():%d/%m %H:%M} =====")
    canais = channels_for_avios(cfg)
    if not canais:
        log("[Avios] nenhum canal configurado pro Avios — nada a fazer.")
        return []

    own_browser = page is None
    estado = {"pw": None, "proc": None, "page": page}

    def abrir():
        """(Re)abre o navegador e devolve uma página viva."""
        avios_api.BROWSER_MODE = cfg.get("avios_browser_mode", "minimizado")
        estado["proc"] = avios_api.start_chrome(log=log)
        pw2, _b, ctx2 = avios_api.connect()
        estado["pw"] = pw2
        estado["page"] = avios_api.get_page(ctx2)
        avios_api.warmup(estado["page"], log=log)
        return estado["page"]

    def pagina():
        """Página viva — reabre sozinha se a janela tiver sido fechada."""
        p = estado["page"]
        if p is not None and avios_api.page_alive(p):
            return p
        log("[Avios] navegador fechado — reabrindo...")
        try:
            if estado["pw"]:
                estado["pw"].stop()
        except Exception:
            pass
        estado["page"] = None
        return abrir()

    if own_browser:
        abrir()
    else:
        avios_api.warmup(page, log=log)

    todos = []
    try:
        for ch in canais:
            log(f"[Avios] === canal: {ch['name']} ===")
            try:
                todos += _scan_channel(cfg, ch, pagina, log=log, send=send,
                                       routes=routes, months=months)
            except Exception as e:
                log(f"[Avios] erro no canal {ch['name']}: {e}")
    finally:
        if own_browser:
            try:
                if estado["pw"]:
                    estado["pw"].stop()
            except Exception:
                pass
            if estado["proc"] is not None and not cfg.get("avios_keep_browser", True):
                try:
                    estado["proc"].terminate()
                except Exception:
                    pass
    log(f"[Avios] ciclo terminado — {len(todos)} alerta(s) em "
        f"{(time.time() - t0) / 60:.0f} min.")
    return todos


def _scan_channel(cfg, ch, pagina, log=print, send=True, routes=None, months=None):
    """Varre um canal (origens x destinos dele) e envia no chat dele."""
    token = cfg.get("telegram_bot_token")
    chat = ch.get("chat_id")
    marcadas = [c for c in ch.get("cabins", ["economy"])
                if c in ("economy", "premium", "business", "first")] or ["economy"]
    # ordem de busca: EXECUTIVA primeiro, depois econômica, depois o resto
    _prio = {"business": 0, "first": 1, "economy": 2, "premium": 3}
    cabins = sorted(marcadas, key=lambda c: _prio.get(c, 9))
    # teto de meses: a varredura para sozinha no ÚLTIMO mês disponível no site
    months = months or int(cfg.get("avios_months", 14))
    # rotas: o que o usuário marcou no canal (origens) x destinos Avios
    routes = routes or cfg.get("avios_routes") or routes_for_channel(ch, cfg)
    log(f"[Avios] rotas: {['-'.join(r) for r in routes]} | cabines: {cabins} "
        f"| {months} meses")
    bot = TelegramBot(token, chat) if (send and token and chat) else None
    history = AlertHistory(_hist_file(ch["name"]))

    enviados = []
    if True:
        for origin, dest in routes:
            src = _source_for(dest)
            page = pagina()          # reabre o navegador se tiver sido fechado
            # o site só devolve award do PROGRAMA selecionado (Iberia x British)
            avios_api.ensure_programme(page, src, log=log)
            try:
                data = avios_api.scan_route(page, origin, dest, cabins=cabins,
                                            months=months, log=log)
            except Exception as e:
                log(f"[Avios] erro varrendo {origin}->{dest}: {e}")
                continue

            # por cabine: só o PISO de época baixa (regra do usuário); junta ida+volta
            for cab, legs in data.items():
                floor = avios_chart.offpeak_floor(origin, dest, cab)
                if not floor:
                    continue
                ida_ok = {d: i for d, i in legs.get("ida", {}).items()
                          if i.get("avios") and i["avios"] <= floor}
                volta_ok = {d: i for d, i in legs.get("volta", {}).items()
                            if i.get("avios") and i["avios"] <= floor}
                if not ida_ok and not volta_ok:
                    continue

                todos = list(ida_ok.values()) + list(volta_ok.values())
                miles = min(i["avios"] for i in todos)      # preço-manchete (menor)
                tier = avios_chart.rate_avios(origin, dest, cab, miles)
                if tier not in SEND_TIERS:
                    continue
                seats_vals = [i.get("seats") for i in todos if i.get("seats")]
                seats = min(seats_vals) if seats_vals else None
                seats_max = max(seats_vals) if seats_vals else None

                alert = {
                    "origin": origin, "destination": dest, "source": src,
                    "cabin": cab, "miles": miles, "tier": tier, "seats": seats,
                    "seats_max": seats_max,
                    "dates_ida": sorted(ida_ok), "dates_volta": sorted(volta_ok),
                    # p/ dedup: chave inclui todas as datas ida+volta
                    "dates": [{"date": d} for d in sorted(list(ida_ok) + list(volta_ok))],
                }
                if not history.is_new(alert):
                    continue
                if not history.is_price_worth_sending(alert):
                    continue
                msg = format_alert(alert)
                if send and bot:
                    if bot.send_message(msg):
                        history.mark_sent(alert)
                        enviados.append(alert)
                        log(f"[Avios] ✅ enviado: {origin}->{dest} {cab} {miles}")
                        time.sleep(1.5)
                else:
                    enviados.append(alert)
                    log("[Avios] (dry-run) alertaria:\n" + msg)
    return enviados


# Horários de abertura de award Iberia/British/Qatar (varredura roda nesses)
AVIOS_RUN_HOURS = [0, 2, 3, 6, 21]


def keepalive(cfg, log=print):
    """
    'Toca' o site de tempos em tempos pra sessão não expirar por inatividade
    (foi assim que caiu na 1ª noite). Deixa o Chrome aberto/minimizado.
    """
    avios_api.BROWSER_MODE = cfg.get("avios_browser_mode", "minimizado")
    avios_api.start_chrome(log=log)
    pw = None
    try:
        pw, browser, ctx = avios_api.connect()
        page = avios_api.get_page(ctx)
        avios_api.warmup(page, log=log)   # também atualiza o sinalizador
    except Exception as e:
        log(f"[Avios] keep-alive falhou: {e}")
    finally:
        try:
            if pw:
                pw.stop()
        except Exception:
            pass


def _on_session_drop(cfg, log=print):
    """Quando a sessão cai: avisa no Telegram e (opcional) abre a janela de login."""
    detalhe = avios_api.STATUS.get("detail") or "sessão expirada"
    # NUNCA avisa nos canais dos clientes. Só manda se houver um chat ADMIN
    # privado configurado (avios_admin_chat); senão fica só no log do painel.
    admin = cfg.get("avios_admin_chat")
    token = cfg.get("telegram_bot_token")
    if admin and token:
        try:
            TelegramBot(token, str(admin)).send_message(
                f"⚠️ Avios: a sessão do site caiu ({detalhe}).\n"
                "Abra o sistema e clique em 'Conectar conta Avios' pra religar.",
                silent=True)
        except Exception as e:
            log(f"[Avios] não consegui avisar o admin: {e}")
    if cfg.get("avios_auto_login_window", True):
        log("[Avios] abrindo a janela de login pra você reconectar...")
        try:
            avios_api.BROWSER_MODE = "visivel"   # login precisa ser visível
            avios_api.open_login_window(log)
            avios_api.watch_login(log)           # acende o verde quando logar
        except Exception as e:
            log(f"[Avios] falha ao abrir login: {e}")
        finally:
            avios_api.BROWSER_MODE = cfg.get("avios_browser_mode", "minimizado")


def start_background(get_cfg, log=print):
    """Thread que roda a varredura nos HORÁRIOS de abertura (0h, 6h, 21h por
    padrão — configurável em cfg['avios_run_hours']), só quando cfg['avios_enabled']
    estiver ligado. Verifica o relógio a cada minuto."""
    log = _com_arquivo(log)   # o loop também grava no avios.log
    log(f"[Avios] agendador ligado — horários: "
        f"{(get_cfg() or {}).get('avios_run_hours', AVIOS_RUN_HOURS)}")
    # avisa/reabre login quando a sessão cair (uma vez por queda)
    estado = {"ultimo": None, "tratando": False}

    def _listener(connected, detail=""):
        try:
            cfg = get_cfg() or {}
        except Exception:
            cfg = {}
        if not cfg.get("avios_enabled"):
            return
        if connected is False and estado["ultimo"] is not False and not estado["tratando"]:
            estado["tratando"] = True
            def _tratar():
                try:
                    _on_session_drop(cfg, log=log)
                finally:
                    estado["tratando"] = False
            threading.Thread(target=_tratar, daemon=True).start()
        estado["ultimo"] = connected

    avios_api.add_status_listener(_listener)

    def loop():
        last_key = None
        last_ka = 0.0
        while True:
            try:
                cfg = get_cfg() or {}
            except Exception:
                cfg = {}
            if cfg.get("avios_enabled"):
                hours = cfg.get("avios_run_hours", AVIOS_RUN_HOURS)
                now = datetime.now()
                key = (now.date().isoformat(), now.hour)
                if now.hour in hours and key != last_key:
                    last_key = key
                    log(f"[Avios] {now:%H:%M} — janela de abertura, varrendo...")
                    try:
                        run_once(cfg, log=log, send=True)
                    except Exception as e:
                        log(f"[Avios] erro no ciclo: {e}")
                    last_ka = time.time()
                else:
                    # keep-alive: mantém a sessão viva entre as varreduras
                    minutos = float(cfg.get("avios_keepalive_minutes", 40))
                    if minutos > 0 and (time.time() - last_ka) >= minutos * 60:
                        last_ka = time.time()
                        log("[Avios] keep-alive (mantendo a sessão viva)...")
                        try:
                            keepalive(cfg, log=log)
                        except Exception as e:
                            log(f"[Avios] keep-alive: {e}")
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True, name="AviosRunner")
    t.start()
    return t
