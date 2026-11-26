"""
Tradutor de alertas do grupo "VMM - Passagens Nacionais"
========================================================
Lê o texto de uma mensagem do VMM, extrai os dados e remonta no
formato "Onde As Milhas Me Levam" (com a nossa cara).

Não depende de rede — só parsing/formatação. Testável isolado.
Usado pelo repost_vmm.py (userbot Telethon).
"""

import re
import hashlib

MESES = {
    "JAN": "JAN", "FEV": "FEV", "MAR": "MAR", "ABR": "ABR",
    "MAI": "MAI", "JUN": "JUN", "JUL": "JUL", "AGO": "AGO",
    "SET": "SET", "OUT": "OUT", "NOV": "NOV", "DEZ": "DEZ",
}


def _num(s):
    """'18.802' -> 18802 ; '24,99' -> 24.99 ; '' -> None"""
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if "," in s:  # decimal BR
        return float(s.replace(".", "").replace(",", "."))
    return int(s.replace(".", ""))


def _fmt_miles(m):
    return f"{int(m):,}".replace(",", ".")


def _fmt_datas(bloco):
    """'OUT26: 1,2,5,9' (uma ou mais linhas) -> 'OUT/26: 1, 2, 5, 9'"""
    out = []
    for linha in bloco.strip().splitlines():
        linha = linha.strip()
        m = re.match(r"([A-Za-z]{3})\s*/?\s*(\d{2}):\s*(.+)", linha)
        if not m:
            continue
        mes = MESES.get(m.group(1).upper(), m.group(1).upper())
        ano = m.group(2)
        dias = ", ".join(d.strip() for d in m.group(3).split(",") if d.strip())
        out.append(f"{mes}/{ano}: {dias}")
    return "\n".join(out)


def parse_vmm(text):
    """
    Extrai os campos de uma mensagem do VMM. Retorna dict ou None
    se não parecer um alerta (falta rota/milhas).
    """
    if not text:
        return None

    d = {}

    # Rota: "✈️ Chapecó (XAP) 🇧🇷 x Belo Horizonte (CNF) 🇧🇷"
    # Captura nome, código e a BANDEIRA (par de indicadores regionais) de cada lado.
    _FLAG = r"[\U0001F1E6-\U0001F1FF]{2}"
    mrota = re.search(
        r"([A-Za-zÀ-ÿ'.\- ]+?)\s*\(([A-Z]{3})\)\s*(" + _FLAG + r")?.*?\sx\s+"
        r"([A-Za-zÀ-ÿ'.\- ]+?)\s*\(([A-Z]{3})\)\s*(" + _FLAG + r")?",
        text,
    )
    if not mrota:
        return None
    d["origem_nome"] = mrota.group(1).strip()
    d["origem"] = mrota.group(2)
    d["origem_flag"] = (mrota.group(3) or "").strip()
    d["destino_nome"] = mrota.group(4).strip()
    d["destino"] = mrota.group(5)
    d["destino_flag"] = (mrota.group(6) or "").strip()

    def grab(pat):
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    d["companhia"] = grab(r"Companhia:\s*(.+)")
    d["cabine"] = grab(r"Cabine:\s*(.+)")
    d["programa"] = grab(r"Programa:\s*(.+)")

    mmi = re.search(r"TOTAL.*?:\s*([\d.]+)\s*milhas", text, re.IGNORECASE)
    if not mmi:
        return None
    d["milhas_total"] = _num(mmi.group(1))

    d["milheiro"] = _num(grab(r"Milheiro[^:]*:\s*R\$\s*([\d.,]+)"))
    d["custo"] = _num(grab(r"Custo Estimado[^:]*:\s*R\$\s*([\d.,]+)"))

    # Datas de Ida / Volta (captura o bloco até a próxima seção).
    # Para em: outra 📅, curiosidade 💡, seção Feriados 🎉, ou fim.
    _STOP = r"(?=📅|💡|🎉|Feriados|Datas de Volta|$)"
    _STOP_V = r"(?=📅|💡|🎉|Feriados|$)"
    mi = re.search(r"Datas de Ida:\s*(.+?)" + _STOP, text, re.IGNORECASE | re.DOTALL)
    mv = re.search(r"Datas de Volta:\s*(.+?)" + _STOP_V, text, re.IGNORECASE | re.DOTALL)
    d["datas_ida"] = _fmt_datas(mi.group(1)) if mi else ""
    d["datas_volta"] = _fmt_datas(mv.group(1)) if mv else ""

    return d


def dedup_key(d):
    """Chave estável p/ não repostar o mesmo alerta (rota+programa+milhas+datas)."""
    base = f"{d['origem']}-{d['destino']}|{d.get('programa','')}|{d.get('milhas_total','')}|{d.get('datas_ida','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def format_repost(d):
    """Remonta no formato 'Onde As Milhas Me Levam'."""
    L = []
    of = d.get("origem_flag") or "\U0001f1e7\U0001f1f7"   # default 🇧🇷 se faltar
    df = d.get("destino_flag") or "\U0001f1e7\U0001f1f7"
    L.append(f"✈️ {d['origem_nome']} ({d['origem']}) {of} ➜ {d['destino_nome']} ({d['destino']}) {df}")
    L.append("")
    cab = d.get("cabine") or "Econômica"
    comp = d.get("companhia") or ""
    prog = d.get("programa") or ""
    L.append(f"\U0001f4ba {cab} | {comp} ({prog})")
    L.append("")
    L.append(f"\U0001f4b0 IDA e VOLTA: {_fmt_miles(d['milhas_total'])} milhas + taxas")
    if d.get("custo"):
        L.append(f"\U0001f4b5 Custo estimado: ~R$ {d['custo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    if d.get("datas_ida"):
        L.append("")
        L.append("\U0001f4c5 Datas de Ida:")
        L.append(d["datas_ida"])
    if d.get("datas_volta"):
        L.append("")
        L.append("\U0001f4c5 Datas de Volta:")
        L.append(d["datas_volta"])
    L.append("")
    L.append("✈️ Onde As Milhas Me Levam")
    return "\n".join(L)
