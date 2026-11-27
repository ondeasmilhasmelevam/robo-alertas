# -*- coding: utf-8 -*-
"""
publicar_site.py — deixa os alertas enviados num arquivo que o site lê.
=======================================================================
O site ondeasmilhasmelevam.com.br já mostra passagens: ele tem um robô de
plantão que lê os grupos do Telegram e grava em `dados/alertas.json`.

Só que esse leitor NÃO entende o formato das mensagens daqui (ele espera
"Fortaleza (FOR) x Madrid (MAD)" com linhas "Companhia:", "Cabine:" e
"Programa:"; a gente escreve "Fortaleza (FOR) ➜ Madrid (MAD)" com tudo numa
linha só). Conferido em 26/11/2026: nenhum dos quatro formatos passava.

Em vez de mexer na mensagem que o cliente vê no grupo, ou de ficar adivinhando
texto com expressão regular, este arquivo entrega ao site o que o robô já tem
certo: os dados. O site lê `alertas_site.json` pelo endereço público do
repositório e junta com o que veio do Telegram.

Quem monta o formato final é o site (ferramentas/robo.py), que sabe os nomes
das cidades e o padrão dele. Aqui só vai o fato: rota, programa, milhas, taxa
e datas.

Regras que seguem as do próprio site:
  - uma linha por rota + programa + cabine;
  - rota já avisada só "renasce" (volta a aparecer como nova) se o preço cair;
  - guarda 14 dias; o site mostra 72 horas.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alertas_site.json")
DIAS_GUARDADOS = 14

# Cabine do jeito que o site escreve.
CABINE_SITE = {
    "economy": "Econômica",
    "premium": "Premium Economy",
    "business": "Executiva",
    "first": "Primeira Classe",
}


def _agora():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _chave(alerta):
    return "{}-{}-{}-{}".format(alerta.get("origin", ""), alerta.get("destination", ""),
                                alerta.get("source", ""), alerta.get("cabin", ""))


def _datas(datas):
    """[{'date':'2026-12-11','seats':2}, ...] -> [{'ano':2026,'mes':12,'dias':'11 (2)'}]

    Mês e ano vão separados de propósito: quem escreve "dezembro" ou "DEZ/26" é
    o site, no padrão dele. Aqui não se inventa texto.
    """
    # Mesma regra do formatter.fmt_dates(), que é o que o cliente vê no grupo:
    # uma linha por data (a mesma data vem repetida, um registro por voo —
    # sem isso o site mostrava "27 (4), 27 (4), 27 (4)..." quinze vezes), com
    # o MAIOR número de assentos visto, e o número só aparece quando é de 1 a 4
    # (acima disso não é escassez, é só ruído).
    assentos_por_data = {}
    for d in datas or []:
        txt = str(d.get("date", ""))[:10]
        if len(txt) != 10 or txt.count("-") != 2:
            continue
        n = d.get("seats") or 0
        if txt not in assentos_por_data or n > assentos_por_data[txt]:
            assentos_por_data[txt] = n

    por_mes = {}
    for txt in sorted(assentos_por_data):
        try:
            ano, mes, dia = int(txt[:4]), int(txt[5:7]), int(txt[8:10])
        except ValueError:
            continue
        n = assentos_por_data[txt]
        por_mes.setdefault((ano, mes), []).append(
            f"{dia} ({n})" if 1 <= n <= 4 else str(dia))
    return [{"ano": a, "mes": m, "dias": ", ".join(v)}
            for (a, m), v in sorted(por_mes.items())]


def _ler():
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (IOError, ValueError):
        return []


_pendentes = []


def registrar(alerta, volta=None):
    """Guarda na memória um alerta que ACABOU de ser enviado. Grava no salvar()."""
    if not alerta or not alerta.get("origin") or not alerta.get("destination"):
        return
    try:
        milhas = int(alerta.get("miles") or 0)
    except (TypeError, ValueError):
        milhas = 0
    if milhas <= 0:
        return

    item = {
        "id": _chave(alerta),
        "origem_iata": alerta["origin"],
        "destino_iata": alerta["destination"],
        "programa_id": alerta.get("source", ""),
        "programa": alerta.get("programa", ""),
        "companhia": alerta.get("companhia", ""),
        "cabine": CABINE_SITE.get(alerta.get("cabin", ""), alerta.get("cabin_name", "")),
        "milhas_ida": milhas,
        "taxa_ida": round(float(alerta.get("tax") or 0), 2),
        "datas_ida": _datas(alerta.get("dates")),
        "milhas_volta": 0,
        "taxa_volta": 0,
        "datas_volta": [],
    }
    if volta:
        try:
            mv = int(volta.get("miles") or 0)
        except (TypeError, ValueError):
            mv = 0
        if mv > 0:
            item["milhas_volta"] = mv
            item["taxa_volta"] = round(float(volta.get("tax") or 0), 2)
            item["datas_volta"] = _datas(volta.get("dates"))
    _pendentes.append(item)


def salvar(callback=None):
    """Junta o que foi registrado no ciclo com o que já estava no arquivo."""
    def log(msg):
        if callback:
            callback(msg)

    if not _pendentes:
        return 0

    antigos = {x.get("id"): x for x in _ler() if isinstance(x, dict) and x.get("id")}
    agora = _agora()
    novos = 0
    for item in _pendentes:
        antes = antigos.get(item["id"])
        # Compara SÓ a ida. Comparar o total (ida+volta) dava falso "preço
        # novo": a mesma rota achada hoje sem volta tem total menor que a de
        # ontem com volta, e ela voltava pro topo do site à toa. A ida também
        # é o número pelo qual o site classifica a passagem.
        antes_ida = (antes or {}).get("milhas_ida", 10 ** 9)
        if antes and item["milhas_ida"] >= antes_ida:
            # Mesma rota pelo mesmo preço (ou pior): mantém a data do primeiro
            # aviso, senão ela voltaria pro topo do site a cada varredura.
            item["data"] = antes["data"]
        else:
            item["data"] = _iso(agora)
            novos += 1
        item["total_milhas"] = item["milhas_ida"] + item["milhas_volta"]
        item["fonte"] = "robo-alertas"
        antigos[item["id"]] = item

    limite = _iso(agora - timedelta(days=DIAS_GUARDADOS))
    lista = [x for x in antigos.values() if x.get("data", "") >= limite]
    lista.sort(key=lambda x: x.get("data", ""), reverse=True)

    pasta = os.path.dirname(ARQUIVO) or "."
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=pasta,
                                      delete=False, suffix=".tmp")
    try:
        json.dump(lista, tmp, ensure_ascii=False, indent=1)
        tmp.write("\n")
        tmp.close()
        os.replace(tmp.name, ARQUIVO)
    except Exception:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

    log(f"Site: {len(_pendentes)} alerta(s) no arquivo ({novos} com preço novo), "
        f"{len(lista)} no total")
    del _pendentes[:]
    return novos
