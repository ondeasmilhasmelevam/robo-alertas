"""
Leitor do Rove — flights/explore/stream  (Etapa 1: só parsing, sem rede)
========================================================================
O endpoint api-v2.rove.com/api/v2/flights/explore/stream devolve um
Server-Sent Events (SSE) com vários eventos:

  flight-data / flight-data-partial -> lista de voos (award E cash)
  update-price                      -> atualiza o preço em dinheiro de uma rota

Cada voo tem: route (origem/destino), date, source (programa OU "cash"),
fare_class (Y/W/J/F), mileage_cost (milhas), total_taxes_usd, airlines
(cia OPERADORA), remaining_seats, direct, e — quando é cash — cash_price.

Este módulo NÃO acessa a internet: só transforma o texto do stream em
registros limpos. A parte de autenticação/rede vem na Etapa 2.
"""

import json
import re
import os
import sys
import time
import base64
import logging

import requests

logger = logging.getLogger("miles_bot")

CABINE = {"Y": "economy", "W": "premium", "J": "business", "F": "first"}
BASE = "https://api-v2.rove.com/api/v2/flights/explore/stream"


def _iter_events(raw):
    """Extrai os objetos JSON de cada evento do stream.
    Aceita tanto o formato SSE real ('data: {...}') quanto o copiado do
    DevTools EventStream ('1\\tmessage\\t{...}\\t')."""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        i, j = line.find("{"), line.rfind("}")
        if i == -1 or j <= i:
            continue
        try:
            obj = json.loads(line[i:j + 1])
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and "event" in obj:
            yield obj


def parse_explore_stream(raw):
    """
    Devolve um dict indexado por 'key' (GIG-MAD-2026-11-04-Y), cada um com:
      origin, dest, date, cabin, municipality,
      awards: [ {program, miles, taxes_usd, airlines, direct, seats} , ...],
      cash_usd: float|None, cash_carrier: str, cpp: float|None
    Junta award (de vários programas) + preço em dinheiro da MESMA rota/cabine.
    """
    out = {}

    def slot(f):
        key = f.get("key")
        if not key:
            return None
        if key not in out:
            r = f.get("route", {}) or {}
            out[key] = {
                "key": key,
                "origin": r.get("origin_airport", ""),
                "dest": r.get("destination_airport", ""),
                "date": f.get("date", ""),
                "cabin": CABINE.get(f.get("fare_class", ""), f.get("fare_class", "")),
                "municipality": f.get("municipality", ""),
                "awards": [],
                "cash_usd": None,
                "cash_carrier": "",
                "cpp": None,
            }
        return out[key]

    for ev in _iter_events(raw):
        etype = ev.get("event")

        if etype in ("flight-data", "flight-data-partial"):
            for f in ev.get("data", []) or []:
                s = slot(f)
                if s is None:
                    continue
                src = f.get("source", "")
                mc = f.get("mileage_cost", 0) or 0
                # opção de AWARD (source é um programa e tem custo em milhas)
                if src and src != "cash" and mc > 0:
                    s["awards"].append({
                        "program": src,
                        "miles": mc,
                        "taxes_usd": round(f.get("total_taxes_usd") or 0, 2),
                        "airlines": f.get("airlines", []) or [],
                        "direct": bool(f.get("direct")),
                        "seats": f.get("remaining_seats", 0) or 0,
                    })
                # preço em DINHEIRO embutido
                cp = f.get("cash_price")
                if isinstance(cp, dict) and cp.get("price"):
                    _set_cash(s, cp["price"], f.get("cpp"),
                              (cp.get("flight_details", {}) or {}).get("operating_carrier", {}))

        elif etype == "update-price":
            d = ev.get("data", {}) or {}
            key = d.get("key")
            if key and key in out and d.get("cash_price"):
                _set_cash(out[key], d["cash_price"], d.get("cpp"), None)

    return out


def _set_cash(slot, price, cpp, carrier):
    """Guarda o MENOR preço em dinheiro visto para a rota."""
    try:
        price = float(price)
    except (TypeError, ValueError):
        return
    if slot["cash_usd"] is None or price < slot["cash_usd"]:
        slot["cash_usd"] = round(price, 2)
        if cpp:
            slot["cpp"] = cpp
        if carrier:
            slot["cash_carrier"] = carrier.get("name") or carrier.get("iata_code", "")


def best_award(slot):
    """Melhor (menor) award da rota: dict ou None."""
    if not slot["awards"]:
        return None
    return min(slot["awards"], key=lambda a: a["miles"])


def resumo_rota(slot, usd_brl=5.40):
    """Linha resumida pra depuração/exibição: dinheiro vs melhor award."""
    cash = ""
    if slot["cash_usd"]:
        cash = f"US$ {slot['cash_usd']:.0f} (~R$ {slot['cash_usd']*usd_brl:,.0f})".replace(",", ".")
        if slot["cash_carrier"]:
            cash += f" {slot['cash_carrier']}"
    aw = best_award(slot)
    award = ""
    if aw:
        award = f"{aw['miles']:,} mi {aw['program']}".replace(",", ".")
        if aw["airlines"]:
            award += f" ({'/'.join(aw['airlines'])})"
    return f"{slot['origin']}->{slot['dest']} {slot['cabin']:9s} | 💵 {cash or '—':30s} | ✈️ {award or '—'}"


# ═══════════════════════════════════════════════════════════════
# ETAPA 2 — cotação ao vivo + login automático (Supabase) + busca
# ═══════════════════════════════════════════════════════════════

def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _cfg_path():
    return os.path.join(_base_dir(), "channels_config.json")


def load_cfg():
    try:
        with open(_cfg_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cfg(cfg):
    try:
        with open(_cfg_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error(f"Rove: erro salvando config: {e}")


# ─── Cotação USD→BRL ao vivo (cache de 1h, com fallback) ────────
_rate = {"ts": 0, "val": None}


def cotacao_usd_brl(fallback=5.20):
    """Dólar comercial em tempo real. Cacheia 1h. Cai no fallback se offline."""
    if _rate["val"] and (time.time() - _rate["ts"] < 3600):
        return _rate["val"]
    fontes = [
        ("https://economia.awesomeapi.com.br/json/last/USD-BRL",
         lambda j: float(j["USDBRL"]["bid"])),
        ("https://open.er-api.com/v6/latest/USD",
         lambda j: float(j["rates"]["BRL"])),
    ]
    for url, extrai in fontes:
        try:
            v = extrai(requests.get(url, timeout=8).json())
            if v and v > 0:
                _rate.update(ts=time.time(), val=round(v, 4))
                return _rate["val"]
        except Exception:
            continue
    return _rate["val"] or fallback


# ─── Token: renova sozinho via refresh token do Supabase ────────
_tok = {"access": None, "exp": 0}


def _extract_refresh(raw):
    """Aceita o refresh_token puro, o JSON do Supabase, OU o valor do
    cookie 'sb-...-auth-token' (formato 'base64-<...>', que o navegador guarda).
    Assim o usuário só cola o cookie inteiro e o bot extrai sozinho."""
    if not raw:
        return ""
    raw = raw.strip().strip('"').strip()
    # cookie do @supabase/ssr: começa com 'base64-' (pode vir .0 + .1 colados)
    if raw.startswith("base64-"):
        b = raw[len("base64-"):]
        try:
            raw = base64.b64decode(b + "===").decode("utf-8", "ignore")
        except Exception:
            pass
    s = raw.lstrip()
    if s.startswith("{") or s.startswith("["):
        try:
            d = json.loads(raw)
            if isinstance(d, list):
                d = next((x for x in d if isinstance(x, dict)), {})
            if isinstance(d, dict):
                return d.get("refresh_token", "") or ""
        except Exception:
            pass
        m = re.search(r'"refresh_token"\s*:\s*"([^"]+)"', raw)
        return m.group(1) if m else ""
    return raw  # já era o token puro


def _refresh(cfg, log=logger.info):
    url = (cfg.get("rove_supabase_url") or "").rstrip("/")
    anon = cfg.get("rove_anon_key") or ""
    rt = (cfg.get("rove_refresh_token") or "").strip() or _extract_refresh(cfg.get("rove_session_cookie", ""))
    if not (url and anon and rt):
        log("Rove: faltam credenciais no config (supabase_url / anon_key / refresh_token).")
        return None
    try:
        r = requests.post(
            f"{url}/auth/v1/token?grant_type=refresh_token",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"refresh_token": rt}, timeout=15,
        )
        if r.status_code != 200:
            log(f"Rove: falha ao renovar login ({r.status_code}). Refresh token venceu? Pegue de novo.")
            return None
        d = r.json()
        _tok["access"] = d.get("access_token")
        _tok["exp"] = time.time() + int(d.get("expires_in", 3600))
        # Supabase ROTACIONA o refresh token — precisa salvar o novo.
        novo = d.get("refresh_token")
        if novo and novo != rt:
            cfg["rove_refresh_token"] = novo
            _save_cfg(cfg)
        return _tok["access"]
    except requests.exceptions.RequestException as e:
        log(f"Rove: erro de conexão no login: {e}")
        return None


def _token(cfg, log=logger.info):
    if _tok["access"] and time.time() < _tok["exp"] - 120:
        return _tok["access"]
    return _refresh(cfg, log)


# ─── Auth por COOKIE (o jeito fácil: usuário cola o cookie header) ──
def _access_from_cookie_header(header):
    """Extrai o access_token de dentro do cookie 'sb-...-auth-token(.0/.1)'
    que está no header de cookie do usuário."""
    if not header:
        return ""
    parts = {}
    for kv in header.split(";"):
        kv = kv.strip()
        if "=" in kv:
            k, v = kv.split("=", 1)
            parts[k.strip()] = v.strip()
    chunks = sorted(k for k in parts if re.match(r"sb-.*-auth-token(\.\d+)?$", k))
    raw = "".join(parts[k] for k in chunks)
    if raw.startswith("base64-"):
        try:
            raw = base64.b64decode(raw[7:] + "===").decode("utf-8", "ignore")
        except Exception:
            return ""
    m = re.search(r'"access_token"\s*:\s*"([^"]+)"', raw)
    return m.group(1) if m else ""


def _read_capped(resp, secs=15):
    """Lê o stream SSE por no máximo 'secs' segundos (os dados úteis chegam
    nos primeiros segundos; evita ficar pendurado quando o servidor não fecha)."""
    start = time.time()
    parts = []
    try:
        for chunk in resp.iter_content(chunk_size=16384):
            if chunk:
                parts.append(chunk)
            if time.time() - start > secs:
                break
    except Exception:
        pass
    finally:
        try:
            resp.close()
        except Exception:
            pass
    return b"".join(parts).decode("utf-8", "ignore")


def _access_from_session(raw):
    """Pega o access_token de dentro do valor colado em rove_session_cookie
    (formato 'base64-<...>' que decodifica pro JSON da sessão do Supabase)."""
    if not raw:
        return ""
    raw = raw.strip().strip('"')
    if raw.startswith("base64-"):
        try:
            raw = base64.b64decode(raw[7:] + "===").decode("utf-8", "ignore")
        except Exception:
            return ""
    m = re.search(r'"access_token"\s*:\s*"([^"]+)"', raw)
    return m.group(1) if m else ""


def _cookie_get(cfg, params, log):
    """Faz o GET usando o cookie do usuário (+ Bearer extraído dele, por garantia).
    Persiste cookies novos (Set-Cookie) de volta no config — assim, se o servidor
    do Rove renovar a sessão, o bot se mantém logado sozinho."""
    header = (cfg.get("rove_cookie_header") or "").strip()
    if not header:
        # fallback: monta o cookie a partir do rove_session_cookie que o usuário colou
        sess = (cfg.get("rove_session_cookie") or "").strip()
        if sess:
            header = f"sb-api-auth-token.0={sess}"
    if not header:
        return None
    s = requests.Session()
    for kv in header.split(";"):
        kv = kv.strip()
        if "=" in kv:
            k, v = kv.split("=", 1)
            s.cookies.set(k.strip(), v.strip(), domain=".rove.com")
    headers = {"Accept": "text/event-stream", "x-rove-client": "web",
               "User-Agent": "Mozilla/5.0", "Referer": "https://www.rove.com/"}
    acc = _access_from_cookie_header(header)
    if acc:
        headers["Authorization"] = f"Bearer {acc}"
    r = s.get(BASE, params=params, timeout=(10, 30), headers=headers, stream=True)
    # Se o servidor renovou a sessão, guarda os cookies novos.
    try:
        novos = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
        if novos and novos != header:
            cfg["rove_cookie_header"] = novos
            _save_cfg(cfg)
    except Exception:
        pass
    return r


# ─── Busca (o SSE explore) ──────────────────────────────────────
def fetch_explore(region, start_date, end_date, origin="GIG", cfg=None, log=logger.info):
    """Busca voos (award+cash) de 'origin' para uma REGIÃO (EUR/NA/AS/...).
    Prefere COOKIE (rove_cookie_header). Se não tiver, tenta Bearer via anon_key.
    Retorna o dict do parse_explore_stream, ou {} em erro."""
    cfg = cfg or load_cfg()
    params = {
        "origin_airport": origin, "destination_airport": region,
        "start_date": start_date, "end_date": end_date,
    }
    try:
        # PRIORIDADE de auth:
        # 1) header de cookie cru -> manda a sessão e GUARDA Set-Cookie
        #    (tenta se auto-renovar pelo próprio servidor do Rove)
        # 2) com anon_key -> refresh Supabase (não usado: Rove é server-side)
        # 3) access_token estático de dentro do cookie (vale ~1h)
        r = _cookie_get(cfg, params, log)   # cookie (header OU session) + auto-refresh
        if r is None:
            tok = _token(cfg, log) if cfg.get("rove_anon_key") else None
            if not tok:
                tok = _access_from_session(cfg.get("rove_session_cookie", ""))
            if not tok:
                log("sem credenciais (cookie/anon_key vazios).")
                return {}
            r = requests.get(BASE, params=params, timeout=(10, 30), stream=True, headers={
                "Authorization": f"Bearer {tok}", "Accept": "text/event-stream",
                "x-rove-client": "web", "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.rove.com/"})
        if r.status_code != 200:
            log(f"busca {region} devolveu {r.status_code} (token venceu? re-cole o cookie).")
            return {}
        return parse_explore_stream(_read_capped(r, 15))   # lê no máx. 15s
    except requests.exceptions.RequestException as e:
        log(f"Rove: erro na busca {region}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════
# ETAPA 3 — cache de PREÇO PAGO por rota (menor preço = opção 1)
# ═══════════════════════════════════════════════════════════════
# Região do bot -> código de região do Rove (só EUR confirmado por ora).
_REGIAO_ROVE = {"europa": "EUR"}
_cash_cache = {}     # (origin, dest, cabin) -> (usd, carrier)
_cache_rate = {"val": 5.20}


def last_rate():
    return _cache_rate["val"]


def cash_paga(origin, dest, cabin):
    """Menor preço pago (US$, cia) achado pra rota/cabine, ou None."""
    return _cash_cache.get((origin, dest, cabin))


def build_cash_cache(regioes, origens, dias_frente=45, cfg=None, log=logger.info):
    """Consulta o Rove 1x por ciclo e guarda o MENOR preço pago por
    (origem, destino, cabine). Só roda p/ regiões mapeadas (EUR).
    É tolerante: qualquer erro -> mantém cache vazio, alertas seguem normais."""
    cfg = cfg or load_cfg()
    if not cfg.get("rove_enabled"):
        return
    from datetime import date, timedelta
    d = (date.today() + timedelta(days=dias_frente)).isoformat()
    _cache_rate["val"] = cotacao_usd_brl(cfg.get("rove_usd_brl", 5.20))
    novo = {}
    for reg in regioes:
        code = _REGIAO_ROVE.get(reg)
        if not code:
            continue
        for origem in origens:
            by = fetch_explore(code, d, d, origin=origem, cfg=cfg, log=log)
            for s in by.values():
                if not s["cash_usd"]:
                    continue
                k = (s["origin"], s["dest"], s["cabin"])
                if k not in novo or s["cash_usd"] < novo[k][0]:
                    novo[k] = (s["cash_usd"], s["cash_carrier"])
    if novo:
        _cash_cache.clear()
        _cash_cache.update(novo)
        log(f"preço pago: {len(_cash_cache)} rotas em cache (dólar R$ {_cache_rate['val']}).")


def start_test(log_callback=None, origin="GIG", region="EUR", dias_frente=60):
    """Teste de fumaça: conecta, busca uma data e reporta o que achou.
    Chamado numa thread pelo painel quando o Rove está ligado."""
    def log(msg):
        logger.info(msg)
        if log_callback:
            try:
                log_callback(f"[Rove] {msg}")
            except Exception:
                pass

    cfg = load_cfg()
    if not cfg.get("rove_enabled"):
        return
    from datetime import date, timedelta
    d = (date.today() + timedelta(days=dias_frente)).isoformat()
    log(f"Conectando e buscando {origin}→{region} em {d}...")
    by = fetch_explore(region, d, d, origin=origin, cfg=cfg, log=log)
    if not by:
        log("Nada retornado (veja credenciais/token acima).")
        return
    usd = cotacao_usd_brl(cfg.get("rove_usd_brl", 5.20))
    com_cash = [s for s in by.values() if s["cash_usd"]]
    log(f"OK! {len(by)} rotas, {len(com_cash)} com preço em dinheiro. Dólar hoje: R$ {usd}")
    for s in sorted(com_cash, key=lambda x: x["cash_usd"])[:3]:
        log("  " + resumo_rota(s, usd))
