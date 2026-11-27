# -*- coding: utf-8 -*-
"""
Cliente Avios.com (oficial) — via navegador real
=================================================
O seats.aero NÃO carrega award da Iberia/BA saindo do Brasil (ver comparação
2026-08-10). O calendário oficial da Avios.com tem — mas o endpoint é um Server
Action do Next.js atrás de Akamai Bot Manager + actionToken que expira em 30min.
Único jeito sustentável: dirigir um Chrome de verdade (Playwright, channel=chrome)
logado na conta, em baixa frequência, e interceptar o JSON da resposta.

Fluxo:
  1) avios_login.py  -> loga uma vez (perfil persistente em .avios_profile/)
  2) avios_api usa esse perfil pra abrir a página de resultados e ler os voos.

A resposta é RSC (text/x-component); a linha "1:{...}" é JSON limpo com
departureFlights[data].journeys[].flights[].availability[] (cabin Y/W/J, rbd,
state, seatsAvailable) + peak no nível do voo. O PREÇO em Avios não vem no JSON
— a gente raspa do DOM (o "31.250" que aparece em cada cabine).
"""

import os
import re
import json
import time
import logging

logger = logging.getLogger("miles_bot")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(APP_DIR, ".avios_profile")
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# Locale da sessão (a Avios redireciona pra en-GB ou es-ES conforme a conta).
# A URL de resultados PRECISA bater com o locale da sessão, senão dá "Something
# went wrong". warmup() detecta e ajusta. Default en-GB (sessão nova cai nele).
LOCALE = "en-GB"


def _base():
    return f"https://www.avios.com/{LOCALE}/spend-avios/search-reward-flights/results"


# ---- Sinalizador de conexão (o painel registra um callback pra acender/apagar) ----
STATUS = {"connected": None, "detail": ""}
_status_cb = None


_status_listeners = []


def set_status_callback(fn):
    """O painel registra aqui pra receber (connected: bool, detalhe: str)."""
    global _status_cb
    _status_cb = fn


def add_status_listener(fn):
    """Ouvintes extras (ex.: o runner, pra avisar no Telegram quando cair)."""
    if fn not in _status_listeners:
        _status_listeners.append(fn)


def _set_status(connected, detail=""):
    if STATUS["connected"] == connected and STATUS["detail"] == detail:
        return
    STATUS["connected"] = connected
    STATUS["detail"] = detail
    for fn in ([_status_cb] if _status_cb else []) + list(_status_listeners):
        try:
            fn(connected, detail)
        except Exception:
            pass


def _detect_logged(text):
    """True/False/None a partir do texto da página (None = indefinido)."""
    t = (text or "").lower()
    if not t:
        return None
    if "iniciar sesión" in t or "iniciar sessão" in t or "log in" in t or "sign in" in t:
        return False
    if "gestionar avios" in t or "manage avios" in t or "mi cuenta" in t:
        return True
    return None


def warmup(page, log=print):
    """Abre a home, aquece a sessão (Akamai), detecta locale e estado do login."""
    global LOCALE
    _focus_tab(page)
    try:
        page.goto("https://www.avios.com/", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(8000)
        m = re.search(r"avios\.com/([a-z]{2}-[A-Z]{2})/", page.url or "")
        if m:
            LOCALE = m.group(1)
        log(f"[Avios] sessão aquecida — locale: {LOCALE}")
        try:
            est = _detect_logged(page.inner_text("body"))
        except Exception:
            est = None
        if est is not None:
            _set_status(est, "" if est else "sessão expirada — reconecte")
    except Exception as e:
        log(f"[Avios] warmup falhou: {e}")
    return LOCALE

# Códigos de cabine da Avios -> nomes internos do bot
CABIN_MAP = {"Y": "economy", "W": "premium", "J": "business", "F": "first"}


def _chrome_executable():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


# Cabine interna -> valor do filtro na URL da Avios
CABIN_FILTER = {
    "economy": "Economy",
    "premium": "Premium Economy",
    "business": "Business",
    "first": "First",
}


def build_results_url(origin, dest, departure_date=None, year=None, month=None,
                      journey="OneWay", cabins=None):
    """
    Monta a URL da página de resultados.
    - Com departure_date: abre já no detalhe daquele dia (mostra voos/preços).
    - Só com year/month: abre o calendário do mês (pra ler dias disponíveis).
    - cabins: lista de cabines internas (ex.: ["business"]) pra FILTRAR. None = todas
      (o tooltip mostra a mais barata, i.e., econômica).
    """
    from urllib.parse import urlencode
    if departure_date:
        month = int(departure_date[5:7])
    if cabins:
        cabin_vals = [CABIN_FILTER[c] for c in cabins if c in CABIN_FILTER]
    else:
        cabin_vals = ["Economy", "Premium Economy", "Business", "First"]
    params = [
        ("originAirport", origin),
        ("destinationAirport", dest),
        ("month", str(int(month)) if month else "1"),
        ("adults", "1"),
        ("youngAdults", "0"),
        ("children", "0"),
        ("infants", "0"),
        ("journeyType", journey),
    ]
    params += [("cabin", v) for v in cabin_vals]
    if departure_date:
        params.append(("departureDate", departure_date))
    return _base() + "?" + urlencode(params)


# Meses em inglês (o aria-label dos dias vem em inglês, ex.: "October 29, 2026")
_MONTHS_EN = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def read_available_days(page):
    """
    Lê os botões-dia do calendário e devolve as DATAS disponíveis (YYYY-MM-DD).
    Usa o aria-label ('October 29, 2026') que é absoluto (não depende do mês pedido).
    Se houver mais de um calendário (ida/volta), pega o PRIMEIRO (ida).
    """
    rows = page.evaluate(r"""() => {
  // CONSERTADO 27/11/2026: o Avios renomeou as classes do calendario. Era
  // "...__available" (dois sublinhados), virou "Itcara_available". Como
  // "Itcara_dayButton" ainda tem "dayButton", a checagem de pagina carregada
  // passava e a varredura lia 0 dia em TUDO, sem dar erro.
  // Cuidado: existe tambem "Itcara_unavailable", que CONTEM "available" —
  // por isso compara pedaco por pedaco, exigindo que o nome TERMINE em
  // "available" logo depois de um _ ou -, ou que seja so "available".
  const _diaLivre = b => (b.className || '').split(/\s+/)
      .some(c => /(^|[_-])available$/.test(c));
      const btns = [...document.querySelectorAll('button[class*="dayButton"]')];
      // agrupa por calendário (ancestral que contém vários dayButtons)
      const groups = new Map();
      btns.forEach(b => {
        let anc = b.parentElement;
        while (anc && anc.querySelectorAll('button[class*="dayButton"]').length < 5) {
          anc = anc.parentElement;
        }
        if (!groups.has(anc)) groups.set(anc, []);
        groups.get(anc).push({
          aria: b.getAttribute('aria-label') || '',
          available: _diaLivre(b),
        });
      });
      const arr = [...groups.values()];
      return arr.length ? arr[0] : [];
    }""")
    out = []
    for r in rows:
        if not r.get("available"):
            continue
        m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", r.get("aria", ""))
        if not m:
            continue
        mon = _MONTHS_EN.get(m.group(1).lower())
        if not mon:
            continue
        out.append(f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}")
    return sorted(set(out))


# ----------------------------------------------------------------------------
# Parsing da resposta RSC (text/x-component)
# ----------------------------------------------------------------------------
def parse_results(raw_text):
    """
    Recebe o corpo bruto (RSC) e devolve o dict com departureFlights/returnFlights.
    A gente varre linha a linha procurando o primeiro JSON que tenha
    'departureFlights'. Robusto contra os prefixos '0:', '1:', '1:I[...]' etc.
    """
    if not raw_text:
        return None
    for line in raw_text.splitlines():
        idx = line.find("{")
        if idx < 0:
            continue
        frag = line[idx:]
        try:
            obj = json.loads(frag)
        except Exception:
            continue
        if isinstance(obj, dict) and "departureFlights" in obj:
            return obj
    # fallback: tenta achar no texto inteiro
    m = re.search(r'\{"departureFlights".*\}', raw_text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


def extract_availability(parsed):
    """
    De departureFlights -> estrutura por data:
      { "2026-10-22": { "economy": {available, seats, rbd[], peak, flight, carrier},
                         "business": {...}, ... } }
    """
    out = {}
    if not parsed:
        return out
    for leg_key in ("departureFlights", "returnFlights"):
        legs = parsed.get(leg_key) or {}
        for date, info in legs.items():
            if not isinstance(info, dict):
                continue
            cabins = out.setdefault(date, {})
            for journey in info.get("journeys", []) or []:
                for flight in journey.get("flights", []) or []:
                    peak = flight.get("peak")
                    mk = flight.get("marketing") or {}
                    fno = mk.get("flightNumber")
                    carrier = mk.get("carrier")
                    for av in flight.get("availability", []) or []:
                        cab = CABIN_MAP.get(av.get("cabin"))
                        if not cab:
                            continue
                        seats = av.get("seatsAvailable") or 0
                        rbd = av.get("rbd")
                        slot = cabins.setdefault(cab, {
                            "available": False, "seats": 0, "rbd": [],
                            "peak": peak, "flight": fno, "carrier": carrier,
                            "avios": None,
                        })
                        if seats and seats > 0:
                            slot["available"] = True
                            slot["seats"] = max(slot["seats"], seats)
                        if rbd and rbd not in slot["rbd"]:
                            slot["rbd"].append(rbd)
                        if peak is not None:
                            slot["peak"] = peak
    return out


# ----------------------------------------------------------------------------
# Raspagem do preço (DOM) — o valor em Avios não vem no JSON
# ----------------------------------------------------------------------------
def scrape_prices_from_text(body_text):
    """Lista crua de números tipo 31.250 (só p/ inspeção/debug)."""
    return [m.group(1) for m in re.finditer(r"(\d{1,3}(?:\.\d{3})+)", body_text)]


# Rótulos das famílias tarifárias na tela -> (cabine interna, família)
FARE_LABELS = {
    "económica básica": ("economy", "basica"),
    "econômica básica": ("economy", "basica"),
    "economy basic": ("economy", "basica"),
    "económica comfort": ("economy", "comfort"),
    "econômica comfort": ("economy", "comfort"),
    "economy comfort": ("economy", "comfort"),
    "económica premium": ("premium", "premium"),
    "econômica premium": ("premium", "premium"),
    "premium economy": ("premium", "premium"),
    "premium": ("premium", "premium"),
    "business": ("business", "business"),
    "business comfort": ("business", "business"),
    "primera": ("first", "first"),
    "first": ("first", "first"),
}


def parse_dom_flights(body_text):
    """
    Lê a página de resultados renderizada e devolve a lista de voos:
      [{carrier, flight, fares:[{cabin, family, available, seats, avios}]}]
    Cada família tarifária vira uma linha (Básica/Comfort/Premium/Business...).
    """
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]
    flights = []
    cur = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        mvoo = re.match(r"^([A-Z]{2})\s?(\d{3,4})$", ln)  # ex.: IB0270
        low = ln.lower()
        if mvoo:
            cur = {"carrier": mvoo.group(1), "flight": mvoo.group(1) + mvoo.group(2),
                   "fares": []}
            flights.append(cur)
        elif low in FARE_LABELS and cur is not None:
            cabin, family = FARE_LABELS[low]
            avios = None
            seats = None
            agotado = False
            for w in lines[i + 1:i + 5]:
                wl = w.lower()
                if wl.startswith(("agotado", "esgotado", "sold out")):
                    agotado = True
                    break
                sm = re.match(r"^(\d+)\s+(?:asiento|assento|seat)", wl)
                if sm:
                    seats = int(sm.group(1))
                pm = re.match(r"^(\d{1,3}(?:[.,]\d{3})+)$", w)
                if pm and avios is None:
                    avios = int(re.sub(r"[.,]", "", pm.group(1)))
            cur["fares"].append({
                "cabin": cabin, "family": family,
                "available": (not agotado) and avios is not None,
                "seats": seats, "avios": avios,
            })
        i += 1
    return flights


def best_by_cabin(flights):
    """Resume os voos em: por cabine -> melhor (menor Avios) opção disponível."""
    best = {}
    for fl in flights:
        for fr in fl.get("fares", []):
            if not fr["available"] or fr["avios"] is None:
                continue
            cab = fr["cabin"]
            cur = best.get(cab)
            if cur is None or fr["avios"] < cur["avios"]:
                best[cab] = {
                    "avios": fr["avios"], "seats": fr["seats"],
                    "family": fr["family"], "flight": fl["flight"],
                    "carrier": fl["carrier"],
                }
    return best


# ----------------------------------------------------------------------------
# Chrome REAL + conexão via CDP (não deixamos o Playwright "abrir" o Chrome,
# senão o site detecta automação e o captcha do login nem renderiza).
# A gente sobe um Chrome de verdade (com perfil próprio + porta de depuração)
# e só CONECTA nele. Login é feito por humano nesse Chrome normal.
# ----------------------------------------------------------------------------
import socket
import subprocess

DEBUG_PORT = 9222


def _port_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


# Modos de janela da varredura:
#   "minimizado" - janela normal, mas minimizada na barra de tarefas  [padrão]
#   "visivel"    - janela aberta normalmente (você vê o que ele faz)
# (headless não é opção: a Akamai bloqueia — testado.)
BROWSER_MODE = "minimizado"


def _center_position(w, h):
    """Posição pra abrir a janela CENTRALIZADA na tela."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return max(0, (sw - w) // 2), max(0, (sh - h) // 2)
    except Exception:
        return 100, 60


def _minimize_windows(pid, tentativas=12, log=print):
    """
    Minimiza as janelas do Chrome que NÓS abrimos (só as do nosso pid — a janela
    pessoal do usuário não é tocada). Windows-only, via ctypes.
    """
    if not pid or os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False
    user32 = ctypes.windll.user32
    SW_MINIMIZE = 6
    achou = {"n": 0}

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            achou["n"] += 1
        return True

    for _ in range(tentativas):        # a janela demora um pouco a existir
        user32.EnumWindows(CB(_cb), 0)
        if achou["n"]:
            return True
        time.sleep(0.5)
    return False


def start_chrome(url="https://www.avios.com/", port=DEBUG_PORT, log=print, mode=None):
    """
    Sobe um Chrome REAL com perfil dedicado e porta de depuração aberta.
    Se já houver um rodando nessa porta, reaproveita. Retorna o processo (ou None).
    `mode`: visivel | discreto | oculto (ver BROWSER_MODE).
    """
    os.makedirs(PROFILE_DIR, exist_ok=True)
    if _port_open(port):
        log(f"[Avios] Chrome já aberto na porta {port} — reaproveitando.")
        return None
    mode = (mode or BROWSER_MODE or "discreto").lower()
    exe = _chrome_executable() or "chrome"
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        # sem isso o Chrome "hiberna" a janela minimizada e o preço não carrega
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
    ]
    w, h = 1280, 900
    x, y = _center_position(w, h)
    args += [f"--window-size={w},{h}", f"--window-position={x},{y}"]
    args.append(url)
    log(f"[Avios] Abrindo Chrome ({mode})...")
    proc = subprocess.Popen(args)
    for _ in range(60):  # espera até ~30s a porta abrir
        if _port_open(port):
            break
        time.sleep(0.5)
    if mode == "minimizado":
        if _minimize_windows(proc.pid, log=log):
            log("[Avios] janela minimizada.")
    return proc


def connect(port=DEBUG_PORT):
    """Conecta o Playwright a um Chrome já aberto (via CDP). Retorna (pw, browser, ctx)."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    return pw, browser, ctx


def get_page(ctx):
    """Devolve UMA página reutilizável (reaproveita uma existente ou cria)."""
    for p in ctx.pages:
        return p
    return ctx.new_page()



def _focus_tab(page):
    """Traz a aba pra frente só no modo visível (em minimizado isso restauraria a janela)."""
    if BROWSER_MODE == "visivel":
        try:
            page.bring_to_front()
        except Exception:
            pass

def fetch_route(page, origin, dest, departure_date, log=print, wait_ms=9000):
    """
    Navega a MESMA página até o detalhe de uma data e lê os voos/preços do DOM.
    Retorna (None, precos, None, body_text, dom_flights).
    """
    # usa a URL que o formulário já ensinou pra essa rota (o link montado à mão
    # quebra quando o locale/programa muda); só acrescenta a data.
    cache = _load_url_cache()
    guardada = cache.get(f"{origin}-{dest}")
    if guardada:
        from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
        p = urlsplit(guardada)
        q = [(k, v) for k, v in parse_qsl(p.query) if k != "departureDate"]
        q.append(("departureDate", departure_date))
        url = urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))
    else:
        url = build_results_url(origin, dest, departure_date, journey="Return")
    log(f"[Avios] Abrindo {origin}->{dest} {departure_date} ...")
    _focus_tab(page)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"[Avios] erro ao abrir: {e}")

    # A página mostra "Agotado" primeiro e SÓ DEPOIS popula o preço da cabine
    # disponível (chamada async). Então NÃO paramos no "agotado" — esperamos o
    # sinal de que o preço carregou ("asiento"/"impuestos"). Se nunca vier,
    # aceitamos como esgotado após o timeout.
    body_text = ""
    for _ in range(max(1, int(wait_ms / 500))):
        page.wait_for_timeout(500)
        try:
            body_text = page.inner_text("body")
        except Exception:
            body_text = ""
        low = body_text.lower()
        # tem vaga E o preço já carregou (não está mais "Cargando/Loading price")
        tem_vaga = ("asiento" in low or "assento" in low or "seat" in low)
        if tem_vaga and "cargando" not in low and "loading" not in low:
            break

    precos = scrape_prices_from_text(body_text)
    dom_flights = parse_dom_flights(body_text)
    return None, precos, None, body_text, dom_flights


def click_next_month(page):
    """
    Avança um mês. Como a tela tem DOIS calendários (ida e volta), clica na
    setinha '>' de AMBOS pra manter os dois no mesmo mês. True se clicou algum.
    """
    selectors = [
        'button[aria-label*="siguiente" i]',
        'button[aria-label*="next" i]',
        'button[aria-label*="próximo" i]',
        'button[aria-label*="proximo" i]',
    ]
    clicou = 0
    for sel in selectors:
        try:
            els = [e for e in page.query_selector_all(sel)
                   if e.is_enabled() and e.is_visible()]
        except Exception:
            els = []
        if not els:
            continue
        for el in els[:2]:          # um por calendário
            try:
                el.click()
                clicou += 1
                page.wait_for_timeout(700)
            except Exception:
                pass
        break
    return clicou > 0


def scan_calendar(page, origin, dest, months=12, log=print, wait_ms=7000):
    """
    Na MESMA página, abre o calendário (Return, lê a ida) e vai PULANDO mês a mês
    com a seta '>', coletando os dias disponíveis. Cobre até `months` meses.
    Devolve lista ordenada de datas 'YYYY-MM-DD' disponíveis.
    """
    import datetime as _dt
    hoje = _dt.date.today()
    url = build_results_url(origin, dest, year=hoje.year, month=hoje.month,
                            journey="Return")
    log(f"[Avios] Abrindo calendário {origin}->{dest} ...")
    _focus_tab(page)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"[Avios] erro ao abrir: {e}")
    page.wait_for_timeout(wait_ms)

    try:
        nbtn = page.evaluate("() => document.querySelectorAll('button[class*=\"dayButton\"]').length")
        log(f"[Avios]   (diag) botões-dia na tela: {nbtn}")
    except Exception:
        pass

    encontrados = set()
    for i in range(months):
        days = read_available_days(page)
        for d in days:
            encontrados.add(d)
        log(f"[Avios]   mês {i + 1}/{months}: {len(days)} dias disp. "
            f"(acumulado {len(encontrados)})")
        if i < months - 1:
            if not click_next_month(page):
                log("[Avios]   não achei a seta de próximo mês — parando.")
                break
            page.wait_for_timeout(3000)
    return sorted(encontrados)


_CABIN_NAME = {
    "económica premium": "premium", "econômica premium": "premium",
    "premium economy": "premium",
    "económica": "economy", "econômica": "economy", "economy": "economy",
    "premium": "premium", "business": "business",
    "primera": "first", "first": "first",
}

# Marca os dias disponíveis dos DOIS calendários da mesma tela:
#   data-avscan="0" = calendário da IDA (esquerda)
#   data-avscan="1" = calendário da VOLTA (direita)
# Assim uma única busca já dá ida e volta (não precisa varrer a rota invertida).
_TAG_JS = r"""() => {
  // CONSERTADO 27/11/2026: o Avios renomeou as classes do calendario. Era
  // "...__available" (dois sublinhados), virou "Itcara_available". Como
  // "Itcara_dayButton" ainda tem "dayButton", a checagem de pagina carregada
  // passava e a varredura lia 0 dia em TUDO, sem dar erro.
  // Cuidado: existe tambem "Itcara_unavailable", que CONTEM "available" —
  // por isso compara pedaco por pedaco, exigindo que o nome TERMINE em
  // "available" logo depois de um _ ou -, ou que seja so "available".
  const _diaLivre = b => (b.className || '').split(/\s+/)
      .some(c => /(^|[_-])available$/.test(c));
  document.querySelectorAll('[data-avscan]').forEach(e => e.removeAttribute('data-avscan'));
  const btns = [...document.querySelectorAll('button[class*="dayButton"]')];
  const groups = new Map();
  btns.forEach(b => {
    let a = b.parentElement;
    while (a && a.querySelectorAll('button[class*="dayButton"]').length < 5) a = a.parentElement;
    if (!groups.has(a)) groups.set(a, []);
    groups.get(a).push(b);
  });
  const arr = [...groups.values()];
  const out = [0, 0];
  arr.slice(0, 2).forEach((g, idx) => {
    g.forEach(b => {
      if (_diaLivre(b)) {
        b.setAttribute('data-avscan', String(idx));
        out[idx]++;
      }
    });
  });
  return out;
}"""

_TIP_JS = r"""() => {
  let best = '';
  document.querySelectorAll('body *').forEach(el => {
    const t = (el.textContent || '').trim();
    if (/Desde|From/i.test(t) && /\d[.,]\d{3}/.test(t) && t.length < 90) {
      if (t.length > best.length) best = t;
    }
  });
  return best;
}"""


def _aria_to_date(aria):
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", aria or "")
    if not m:
        return None
    mon = _MONTHS_EN.get(m.group(1).lower())
    return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}" if mon else None


def parse_tooltip(text):
    """
    De 'Disponible1Vuelo4EconómicaDesde31.250...' (es-ES) ou
    'Available1Flight4EconomyFrom31,250...' (en-GB) -> {avios, seats, cabin}.
    """
    if not text:
        return None
    price = None
    m = re.search(r"(?:Desde|From)\s*(\d{1,3}(?:[.,]\d{3})+)", text, re.I)
    if m:
        price = int(re.sub(r"[.,]", "", m.group(1)))
    seats = cabin = None
    # CONSERTADO 27/11/2026: o site passou a escrever "9+" quando tem nove ou
    # mais assentos ("...8vuelos9+Económica Premium..."). Sem aceitar o "+",
    # assentos e cabine vinham sempre vazios.
    m2 = re.search(r"(\d+)\+?\s*(Económica Premium|Econômica Premium|Premium Economy|"
                   r"Económica|Econômica|Economy|Premium|Business|Primera|First)",
                   text, re.I)
    if m2:
        seats = int(m2.group(1))
        cabin = _CABIN_NAME.get(m2.group(2).lower())
    return {"avios": price, "seats": seats, "cabin": cabin}


# URLs que já deram certo (aprendidas pelo formulário) — evita refazer o processo.
URL_CACHE_FILE = os.path.join(APP_DIR, "avios_urls.json")


def _load_url_cache():
    try:
        with open(URL_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_url_cache(cache):
    try:
        with open(URL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def _com_cabines(url, cabins):
    """Aplica o filtro de cabine numa URL de resultados já pronta."""
    if not cabins:
        return url
    from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k != "cabin"]
    q += [("cabin", CABIN_FILTER[c]) for c in cabins if c in CABIN_FILTER]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


def page_alive(page):
    """False se a aba/navegador foi fechado (aí o chamador reabre)."""
    try:
        page.evaluate("() => 1")
        return True
    except Exception:
        return False


# URLs aprendidas pelo formulário NESTA varredura: o formulário roda 1x por par
# de aeroportos e as outras cabines reaproveitam a URL (só trocam o filtro).
_SESSAO_URLS = {}


def reset_session_urls():
    _SESSAO_URLS.clear()


def _esperar(page, cond_js, max_ms, passo=300):
    """Espera até a condição JS ser verdadeira (ou estourar max_ms). Rápido quando carrega logo."""
    t = 0
    while t < max_ms:
        try:
            if page.evaluate(cond_js):
                return True
        except Exception:
            pass
        page.wait_for_timeout(passo)
        t += passo
    return False


_JS_TEM_DIAS = "()=>document.querySelectorAll('button[class*=\"dayButton\"]').length>0"


def search_via_form(page, origin, dest, log=print):
    """
    Caminho 'humano': abre a tela de busca, APAGA o que estiver no campo, digita
    o código do aeroporto, escolhe a sugestão que aparece embaixo e clica em
    Search. Devolve a URL de resultados gerada (ou None).
    """
    sync_locale(page)   # o programa selecionado define o idioma da URL
    url = f"https://www.avios.com/{LOCALE}/spend-avios/search-reward-flights"
    log(f"[Avios] busca pelo formulário {origin}->{dest} ...")
    # Campos do formulário pela POSIÇÃO (1º = origem, 2º = destino): o texto muda
    # com o idioma ("Select departure" / "Seleccionar salida" / "Selecione a partida").
    _CAMPOS = 'input[id^="react-aria"][placeholder]'
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        _esperar(page, f"()=>document.querySelectorAll('{_CAMPOS}').length>=2", 12000)
    except Exception as e:
        log(f"[Avios] não abriu a tela de busca: {e}")
        return None

    def escolher(posicao, code):
        campos = [c for c in page.query_selector_all(_CAMPOS) if c.is_visible()]
        if len(campos) <= posicao:
            log(f"[Avios] campo {'origem' if posicao == 0 else 'destino'} não encontrado")
            return False
        el = campos[posicao]
        el.click()
        page.wait_for_timeout(300)
        page.keyboard.press("Control+A")     # apaga o que já estava
        page.keyboard.press("Delete")
        page.keyboard.type(code, delay=120)
        try:
            page.click(rf'text=/\({code}\)/', timeout=8000)  # sugestão de baixo
            page.wait_for_timeout(600)
            return True
        except Exception:
            log(f"[Avios] sugestão de {code} não apareceu")
            return False

    if not escolher(0, origin) or not escolher(1, dest):
        return None
    try:
        # botão de buscar em qualquer idioma (Search / Buscar / Pesquisar)
        btn = (page.query_selector('form button[type="submit"]')
               or page.query_selector('button:has-text("Search")')
               or page.query_selector('button:has-text("Buscar")')
               or page.query_selector('button:has-text("Pesquisar")'))
        if not btn:
            log("[Avios] botão de buscar não encontrado")
            return None
        btn.click()
        # espera a URL de resultados + o calendário aparecer (em vez de 13s fixos)
        _esperar(page, "()=>location.href.includes('results?')", 15000)
        _esperar(page, _JS_TEM_DIAS, 12000)
    except Exception as e:
        log(f"[Avios] falha ao clicar em Search: {e}")
        return None

    final = page.url or ""
    if "results?" in final and "originAirport" in final:
        cache = _load_url_cache()
        cache[f"{origin}-{dest}"] = final
        _save_url_cache(cache)
        _SESSAO_URLS[f"{origin}-{dest}"] = final
        log(f"[Avios] URL aprendida para {origin}-{dest}")
        return final
    return None


def scan_calendar_hover(page, origin, dest, months=12, cabin=None, log=print,
                        wait_ms=10000):
    """
    VARREDURA RÁPIDA: abre o calendário (Return, lê a ida), e em cada mês passa o
    mouse nos dias disponíveis lendo o tooltip ('Desde X' + cabine + assentos) —
    SEM abrir o detalhe dia a dia. Devolve { 'YYYY-MM-DD': {avios, seats, cabin} }.
    Se `cabin` (ex.: 'business'), FILTRA a busca só naquela cabine — assim o
    tooltip mostra o preço DAQUELA cabine (senão mostra a mais barata/econômica).
    """
    import datetime as _dt
    hoje = _dt.date.today()
    cabins = [cabin] if cabin else None
    url = build_results_url(origin, dest, year=hoje.year, month=hoje.month,
                            journey="Return", cabins=cabins)
    log(f"[Avios] Varredura (hover) {origin}->{dest} "
        f"[{cabin or 'todas'}] ...")
    _focus_tab(page)

    # O locale muda junto com o programa (Iberia=es-ES, British=en-GB): realinha
    # antes de montar a URL, senão a página dá erro.
    sync_locale(page)

    def _tentar_url(u):
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            log(f"[Avios] erro ao abrir: {e}")
            return False
        # espera o calendário aparecer (ou a tela de erro) — sem tempo fixo
        _esperar(page, "()=>document.querySelectorAll('button[class*=\"dayButton\"]').length>0"
                       " || /something went wrong|algo ha salido mal|algo deu errado/i"
                       ".test(document.body.innerText)", wait_ms)
        if page_failed(page):
            return False
        try:
            if not page.evaluate(_JS_TEM_DIAS):
                return False
        except Exception:
            return False
        # dá um respiro pro "available" ser aplicado nos botões
        page.wait_for_timeout(1200)
        return True

    # CAMINHO PRINCIPAL: pesquisa este par de aeroportos pelo formulário — mas
    # só UMA vez por varredura; as outras cabines reaproveitam a URL.
    ok = False
    chave = f"{origin}-{dest}"
    nova = _SESSAO_URLS.get(chave) or search_via_form(page, origin, dest, log=log)
    if nova:
        ok = _tentar_url(_com_cabines(nova, cabins))
        if not ok and chave in _SESSAO_URLS:      # URL da sessão falhou: refaz o form
            _SESSAO_URLS.pop(chave, None)
            nova = search_via_form(page, origin, dest, log=log)
            if nova:
                ok = _tentar_url(_com_cabines(nova, cabins))
    if not ok:                      # reservas: URL aprendida antes / URL montada
        cache = _load_url_cache()
        guardada = cache.get(f"{origin}-{dest}")
        if guardada:
            ok = _tentar_url(_com_cabines(guardada, cabins))
    if not ok:
        ok = _tentar_url(build_results_url(origin, dest, year=hoje.year,
                                           month=hoje.month, journey="Return",
                                           cabins=cabins))
    if not ok:
        log("[Avios] ⚠️ não consegui carregar a busca nem pelo formulário.")
        return {"ida": {}, "volta": {}}

    resultados = {"ida": {}, "volta": {}}
    for i in range(months):
        try:
            page.evaluate(_TAG_JS)
        except Exception:
            pass
        n_mes = 0
        # 0 = calendário da IDA (esquerda) | 1 = da VOLTA (direita) — mesma tela!
        for idx, perna in ((0, "ida"), (1, "volta")):
            for h in page.query_selector_all(f'button[data-avscan="{idx}"]'):
                date = _aria_to_date(h.get_attribute("aria-label"))
                if not date:
                    continue
                n_mes += 1
                try:                       # limpa o tooltip anterior
                    page.mouse.move(3, 3)
                except Exception:
                    pass
                try:
                    h.hover()
                except Exception:
                    continue
                # passa o mouse E ESPERA o preço carregar (some o "Cargando...")
                info = None
                for _ in range(20):        # ~5s no máximo por dia, checando a cada 250ms
                    page.wait_for_timeout(250)
                    try:
                        parsed = parse_tooltip(page.evaluate(_TIP_JS))
                    except Exception:
                        parsed = None
                    if parsed and parsed.get("avios"):
                        info = parsed
                        break
                if info:
                    resultados[perna][date] = info
        mes_atual = _mes_na_tela(page)
        log(f"[Avios]   mês {i + 1} ({mes_atual or '?'}): {n_mes} dias "
            f"(ida {len(resultados['ida'])} | volta {len(resultados['volta'])})")
        if i < months - 1:
            antes = _primeiro_dia(page)
            if not click_next_month(page):
                log(f"[Avios]   último mês disponível: {mes_atual or '?'}")
                break
            # espera o calendário realmente trocar de mês (em vez de tempo fixo)
            _esperar(page, "()=>{const b=document.querySelector('button[class*=\"dayButton\"]');"
                           f"return !!b && b.getAttribute('aria-label') !== {json.dumps(antes)}}}",
                     4000, passo=200)
            page.wait_for_timeout(700)
    return resultados


def _primeiro_dia(page):
    try:
        return page.evaluate("()=>{const b=document.querySelector('button[class*=\"dayButton\"]');"
                             "return b?b.getAttribute('aria-label'):''}") or ""
    except Exception:
        return ""


def _mes_na_tela(page):
    """'October 2026' a partir do 1º botão-dia do calendário da ida."""
    try:
        aria = page.evaluate("()=>{const b=document.querySelector('button[class*=\"dayButton\"]');"
                             "return b?b.getAttribute('aria-label'):''}")
    except Exception:
        return None
    m = re.match(r"([A-Za-z]+)\s+\d{1,2},\s+(\d{4})", aria or "")
    return f"{m.group(1)} {m.group(2)}" if m else None


def scan_route(page, origin, dest, cabins=("economy",), months=12, log=print,
               volta=True):
    """
    Varre uma rota nas cabines pedidas. IDA e VOLTA saem da MESMA busca (a tela
    mostra os dois calendários), então é UMA passada por cabine — metade do tempo.
    Devolve { cabine: { 'ida': {data: {avios, seats}}, 'volta': {data: {...}} } }.
    """
    out = {}
    for cab in cabins:
        res = scan_calendar_hover(page, origin, dest, months=months, cabin=cab, log=log)
        out[cab] = {
            perna: {d: {"avios": i["avios"], "seats": i.get("seats")}
                    for d, i in res.get(perna, {}).items() if i.get("avios")}
            for perna in ("ida", "volta")
        }
    return out


def fetch_detail(page, origin, dest, date, log=print, wait_ms=12000):
    """Preço/assentos por cabine de uma data (melhor opção por cabine)."""
    _, _, _, _, dom_flights = fetch_route(page, origin, dest, date, log=log, wait_ms=wait_ms)
    return best_by_cabin(dom_flights)


# Programa (opco) do site: a busca só retorna award do programa SELECIONADO.
# Se o site estiver em "British Airways Club" e você buscar GIG->MAD (voo Iberia),
# volta VAZIO — e o calendário nem renderiza ("sem seta de próximo mês").
PROGRAMME_LABEL = {"iberia": "Iberia Club", "british": "British Airways Club",
                   "aerlingus": "AerClub"}


# A página de erro aparece no idioma da sessão — precisa detectar em todos.
_ERRO_MARCAS = ("something went wrong", "algo ha salido mal", "algo deu errado",
                "inténtelo de nuevo", "se ha producido un error")


def page_failed(page):
    """True se a tela de resultados falhou (em qualquer idioma)."""
    try:
        t = page.inner_text("body").lower()
    except Exception:
        return True
    return any(m in t for m in _ERRO_MARCAS)


def sync_locale(page):
    """Realinha o LOCALE com a URL atual (muda ao trocar de programa: IB=es-ES, BA=en-GB)."""
    global LOCALE
    m = re.search(r"avios\.com/([a-z]{2}-[A-Z]{2})/", page.url or "")
    if m and m.group(1) != LOCALE:
        LOCALE = m.group(1)
    return LOCALE


def _sem_acento(t):
    """'Clube Ibérico' -> 'clube iberico' (compara sem depender de acento)."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                   if unicodedata.category(c) != "Mn")


def current_programme(page):
    """Lê o programa selecionado no cabeçalho ('Iberia Club', etc.) ou None."""
    try:
        return page.evaluate("""() => {
          const b = document.querySelector('button[class*="Dropdown"]');
          return b ? (b.textContent || '').trim() : null;
        }""")
    except Exception:
        return None


def ensure_programme(page, prog, log=print):
    """
    Garante que o site está no programa certo (iberia/british). Troca pelo
    seletor do cabeçalho se precisar. Retorna True se está no programa desejado.
    """
    # O rótulo muda de idioma: "Iberia Club" (en), "Clube Ibérico" (pt),
    # "Club Iberia" (es). Casamos por raiz SEM ACENTO: iber / british / aer.
    chave = {"iberia": "iber", "british": "british", "aerlingus": "aer"}.get(prog)
    if not chave:
        return True
    atual = current_programme(page) or ""
    if chave in _sem_acento(atual):
        return True
    log(f"[Avios] trocando programa: {atual or '?'} -> {prog}")
    for tentativa in range(2):
        try:
            # recarrega a home pra abrir o menu num estado limpo (ele é instável
            # se a página já estiver com o dropdown meio aberto)
            page.goto("https://www.avios.com/", wait_until="domcontentloaded",
                      timeout=45000)
            page.wait_for_timeout(7000)
            btn = page.query_selector('button[class*="Dropdown"]')
            if not btn:
                log("[Avios] não achei o seletor de programa.")
                continue
            btn.click()
            page.wait_for_timeout(2500)
            alvo_el = None
            for el in page.query_selector_all('li button, button, [role=option]'):
                try:
                    t = _sem_acento((el.text_content() or "").strip())
                    if chave in t and len(t) < 45 and el.is_visible():
                        alvo_el = el
                        break
                except Exception:
                    continue
            if not alvo_el:
                log(f"[Avios] opção '{prog}' não apareceu (tentativa {tentativa + 1}).")
                continue
            alvo_el.click()
            page.wait_for_timeout(10000)
            sync_locale(page)
            novo = current_programme(page) or ""
            if chave in _sem_acento(novo):
                log(f"[Avios] programa agora: {novo} (locale {LOCALE})")
                return True
            log(f"[Avios] ainda em '{novo}' (tentativa {tentativa + 1})")
        except Exception as e:
            log(f"[Avios] falha ao trocar programa: {e}")
    log(f"[Avios] ⚠️ não consegui trocar para {prog} — os preços virão do "
        f"programa '{current_programme(page) or '?'}'. "
        f"Dica: marque 'Mostrar navegador', abra e troque uma vez na mão.")
    return False


def open_login_window(log=print):
    """
    Abre o Chrome (perfil dedicado) na Avios.com pro usuário logar NA MÃO.
    Chamado pelo botão do painel — não precisa de terminal. A sessão fica salva
    sozinha no perfil quando o usuário fecha a janela.
    """
    log("[Avios] Abrindo o navegador para login...")
    proc = start_chrome("https://www.avios.com/", log=log)
    if proc is None:
        log("[Avios] (o navegador Avios já estava aberto — use a janela existente)")
    log("[Avios] Faça login na sua conta Avios/Iberia nessa janela.")
    log("[Avios] Quando terminar, é só FECHAR a janela — a sessão fica salva.")
    return proc


def watch_login(log=print, timeout=420, interval=12):
    """
    Depois de abrir a janela de login, fica observando (SEM navegar, pra não
    atrapalhar quem está digitando) até detectar que a conta logou. Só acende o
    sinal verde — nunca marca como desconectado aqui.
    """
    fim = time.time() + timeout
    while time.time() < fim:
        time.sleep(interval)
        pw = None
        try:
            pw, browser, ctx = connect()
            for p in ctx.pages:
                try:
                    if _detect_logged(p.inner_text("body")) is True:
                        log("[Avios] Conta conectada ✅")
                        _set_status(True, "")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            try:
                if pw:
                    pw.stop()
            except Exception:
                pass
    return False


def check_login(log=print, close_after=False):
    """
    Verifica se a sessão da Avios está válida (usa o endpoint /auth-gateway/user
    dentro da própria página; cai pro texto da home se falhar).
    Retorna (logado: bool, nome: str|None).
    """
    proc = start_chrome("https://www.avios.com/", log=log)
    pw = None
    try:
        pw, browser, ctx = connect()
        page = get_page(ctx)
        warmup(page, log=log)
        info = None
        try:
            info = page.evaluate("""async () => {
              try {
                const r = await fetch('/auth-gateway/user', {credentials:'include'});
                if (!r.ok) return {ok:false, status:r.status};
                const j = await r.json();
                return {ok:true, data:j};
              } catch (e) { return {ok:false, err:String(e)}; }
            }""")
        except Exception:
            pass
        nome = None
        if info and info.get("ok"):
            d = info.get("data") or {}
            for k in ("firstName", "first_name", "name", "givenName"):
                if isinstance(d, dict) and d.get(k):
                    nome = str(d[k])
                    break
            if nome or (isinstance(d, dict) and d):
                log(f"[Avios] Sessão VÁLIDA{' — ' + nome if nome else ''} ✅")
                _set_status(True, nome or "")
                return True, nome
        # fallback: procura sinal de login no texto da home
        try:
            txt = page.inner_text("body").lower()
        except Exception:
            txt = ""
        logado = bool(_detect_logged(txt))
        log("[Avios] Sessão " + ("VÁLIDA ✅" if logado else
                                 "NÃO conectada ❌ — use 'Conectar conta Avios'"))
        _set_status(logado, "" if logado else "sessão expirada — reconecte")
        return logado, None
    except Exception as e:
        log(f"[Avios] não consegui verificar: {e}")
        _set_status(False, "erro ao verificar")
        return False, None
    finally:
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
        if close_after and proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass


def is_logged_in(ctx):
    """Heurística simples: procura indício de sessão (nome/saldo) na home."""
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto("https://www.avios.com/es-ES", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        txt = page.inner_text("body").lower()
        return ("avios" in txt and ("mi cuenta" in txt or "cerrar sesión" in txt
                                    or "wellington" in txt or "gestionar" in txt))
    except Exception:
        return False
