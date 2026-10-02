#!/usr/bin/env python3
"""Generates docs/diagrams/arquitectura(.html|_en.html): the whole system as one map.

For technical readers: every container and project, what each connection
carries and with which key, and what each database keeps. The wires move in
the direction data flows, coloured by kind; hovering a box lights it up.

    python tools/architecture.py
"""

from __future__ import annotations

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
W, H = 1600, 1010

KINDS = {
    "http": ("#ffb648", "HTTP JSON", "HTTP JSON"),
    "ws": ("#4dd0e1", "SignalR (WebSocket)", "SignalR (WebSocket)"),
    "outbox": ("#6fd08c", "mensajes del outbox, con reintento", "outbox messages, retried"),
    "tcp": ("#c07a45", "TCP 9100 · ESC/POS", "TCP 9100 · ESC/POS"),
    "sql": ("#8f98a3", "SQL (EF Core · pg_dump)", "SQL (EF Core · pg_dump)"),
}


def t(es: str, en: str) -> dict:
    return {"es": es, "en": en}


# (x, y, w, h, title, lines, style)  style: zone | group | box | inner | lib | ext
BOXES = [
    (24, 128, 290, 800, t("EN EL SALÓN · WI‑FI", "ON THE FLOOR · WI‑FI"), t("", ""), "zone"),
    (330, 128, 930, 800, t("PC DEL LOCAL · DOCKER COMPOSE", "RESTAURANT'S COMPUTER · DOCKER COMPOSE"), t("", ""), "zone"),
    (1276, 128, 300, 800, t("INTERNET", "INTERNET"), t("", ""), "zone"),

    (44, 175, 250, 95, t("Tablets de mozos", "Waiters' tablets"), t("navegador · /mozo\nuna cuenta por mesa", "browser · /mozo\none tab per table"), "box"),
    (44, 290, 250, 95, t("Pantallas de cocina", "Kitchen screens"), t("/cocina?estacion=N\nuna por estación", "/cocina?estacion=N\none per station"), "box"),
    (44, 405, 250, 95, t("Caja y administración", "Register and admin"), t("/caja · /admin\nroles por persona", "/caja · /admin\nroles per person"), "box"),
    (44, 700, 250, 95, t("Impresoras térmicas", "Thermal printers"), t("una por estación\nESC/POS · CP850", "one per station\nESC/POS · CP850"), "box"),

    (350, 170, 520, 410, t("server", "server"), t("ASP.NET Core 8 · :8080 · único puerto publicado", "ASP.NET Core 8 · :8080 · the only published port"), "group"),
    (370, 215, 480, 78, t("Comanda.Api", "Comanda.Api"), t("controllers MVC · SignalR /hubs/realtime\nlogin por PIN (PBKDF2) · cookie · roles · SPA React 19", "MVC controllers · SignalR /hubs/realtime\nPIN login (PBKDF2) · cookie · roles · React 19 SPA"), "inner"),
    (370, 305, 480, 78, t("Comanda.Application", "Comanda.Application"), t("casos de uso · bus de eventos en proceso\noutbox con una fila por destino", "use cases · in-process event bus\noutbox with one queue per destination"), "inner"),
    (370, 395, 480, 62, t("Comanda.Domain", "Comanda.Domain"), t("Tab · CashShift · KitchenTicket · VoidNotice · Ingredient", "Tab · CashShift · KitchenTicket · VoidNotice · Ingredient"), "inner"),
    (370, 469, 480, 92, t("Comanda.Infrastructure", "Comanda.Infrastructure"), t("EF Core 8 + Npgsql · migraciones\nBillingClient · NotifyRouterPublisher\ncontador de comandas atómico por día", "EF Core 8 + Npgsql · migrations\nBillingClient · NotifyRouterPublisher\natomic per-day ticket counter"), "inner"),

    (930, 170, 310, 410, t("billing", "billing"), t("sin puertos publicados", "no published ports"), "group"),
    (948, 215, 274, 78, t("Comanda.Billing", "Comanda.Billing"), t("pedidos idempotentes (202)\nimportaciones · datos fiscales", "idempotent requests (202)\nimports · tax data"), "inner"),
    (948, 305, 274, 78, t("cola hacia ARCA", "queue to ARCA"), t("en orden · numeración correlativa\nreintento de 10 s a 5 min", "in order · consecutive numbers\nretry from 10 s to 5 min"), "inner"),
    (948, 395, 274, 62, t("IFiscalAuthorizer", "IFiscalAuthorizer"), t("simulado · WSAA + WSFEv1", "simulated · WSAA + WSFEv1"), "inner"),
    (948, 469, 274, 92, t("outbox → Comanda", "outbox → Comanda"), t("estados con versión\nun estado viejo no pisa\nal nuevo", "versioned statuses\nan old status never\noverwrites a newer one"), "inner"),

    (350, 830, 200, 70, t("compartido", "shared"), t("Comanda.Contracts\nComanda.Messaging", "Comanda.Contracts\nComanda.Messaging"), "lib"),

    (350, 680, 200, 120, t("print-agent", "print-agent"), t("Comanda.PrintAgent\nX-Print-Agent-Key\nperfil print", "Comanda.PrintAgent\nX-Print-Agent-Key\nprofile print"), "box"),
    (570, 680, 360, 120, t("postgres · PostgreSQL 17", "postgres · PostgreSQL 17"), t("base comanda: cuentas, caja, stock,\nOutboxMessages, InvoiceRecords\nbase billing: Invoices, FiscalProfiles,\nOutboxMessages", "comanda db: tabs, shifts, stock,\nOutboxMessages, InvoiceRecords\nbilling db: Invoices, FiscalProfiles,\nOutboxMessages"), "box"),
    (950, 680, 290, 120, t("notify-router", "notify-router"), t("Python · FastAPI · perfil notify\nPOST /events · X-API-Key\nidempotency_key = id del mensaje", "Python · FastAPI · profile notify\nPOST /events · X-API-Key\nidempotency_key = message id"), "box"),
    (570, 830, 360, 70, t("backup", "backup"), t("pg_dump de las dos bases · restore.sh", "pg_dump of both databases · restore.sh"), "box"),

    (1296, 300, 260, 100, t("ARCA", "ARCA"), t("WSFEv1 · CAE y QR\nhoy simulado", "WSFEv1 · CAE and QR\nsimulated for now"), "ext"),
    (1296, 700, 260, 100, t("Canales del dueño", "Owner's channels"), t("Telegram · email\nSlack · webhook", "Telegram · email\nSlack · webhook"), "ext"),
    (1296, 830, 260, 70, t("Disco externo o nube", "External disk or cloud"), t("BACKUP_DIR", "BACKUP_DIR"), "ext"),
]

# (points, kind, label, label position, label anchor)
WIRES = [
    ([(294, 214), (370, 240)], "http", t("", ""), None, "middle"),
    ([(294, 230), (370, 268)], "ws", t("", ""), None, "middle"),
    ([(294, 329), (370, 240)], "http", t("", ""), None, "middle"),
    ([(294, 345), (370, 268)], "ws", t("", ""), None, "middle"),
    ([(294, 444), (370, 240)], "http", t("", ""), None, "middle"),
    ([(294, 460), (370, 268)], "ws", t("", ""), None, "middle"),
    ([(870, 260), (948, 260)], "outbox", t("pedido", "request"), (909, 252), "middle"),
    ([(948, 520), (870, 520)], "outbox", t("estado", "status"), (909, 512), "middle"),
    ([(1222, 345), (1296, 345)], "http", t("", ""), None, "middle"),
    ([(450, 680), (450, 561)], "http", t("GET /api/print/pending", "GET /api/print/pending"), (458, 673), "start"),
    ([(350, 745), (294, 745)], "tcp", t("", ""), None, "middle"),
    ([(640, 561), (640, 680)], "sql", t("", ""), None, "middle"),
    ([(1085, 561), (1085, 660), (860, 660), (860, 680)], "sql", t("", ""), None, "middle"),
    ([(780, 561), (780, 640), (1180, 640), (1180, 680)], "outbox", t("alertas", "alerts"), (1120, 632), "middle"),
    ([(1240, 745), (1296, 745)], "http", t("", ""), None, "middle"),
    ([(750, 830), (750, 800)], "sql", t("", ""), None, "middle"),
    ([(930, 865), (1296, 865)], "sql", t("", ""), None, "middle"),
]

NOTES = [
    (t("HTTP + SignalR por el Wi‑Fi del local", "HTTP + SignalR over the local Wi‑Fi"), 44, 530, "start"),
    (t("X-Service-Key, una por sentido", "X-Service-Key, one each way"), 909, 600, "middle"),
]


def lines(x: float, y: float, text: str, cls: str, gap: int, anchor: str) -> str:
    return "".join(
        f'<text x="{x}" y="{y + i * gap}" class="{cls}" text-anchor="{anchor}">{escape(line)}</text>'
        for i, line in enumerate(text.split("\n")) if line
    )


def render(lang: str) -> str:
    out: list[str] = []
    for x, y, w, h, title, sub, style in BOXES:
        if style == "zone":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="zone"/>')
            out.append(lines(x + 18, y + 26, title[lang], "zone-title", 18, "start"))
        elif style == "group":
            out.append(f'<g class="hover"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="group"/>')
            out.append(lines(x + 18, y + 28, title[lang], "group-title", 18, "start"))
            out.append(lines(x + w - 18, y + 28, sub[lang], "sub", 16, "end") + "</g>")
        else:
            cls = {"inner": "inner", "lib": "lib", "ext": "ext", "box": "box"}[style]
            sub_lines = [l for l in sub[lang].split("\n") if l]
            if style == "inner" or style == "lib":
                out.append(f'<g class="hover"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" class="{cls}"/>')
                out.append(lines(x + 14, y + 23, title[lang], "title-left", 18, "start"))
                out.append(lines(x + 14, y + 43, sub[lang], "sub", 16, "start") + "</g>")
            else:
                block = 20 + 16 * len(sub_lines)
                top = y + h / 2 - block / 2 + 13
                out.append(f'<g class="hover"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="{cls}"/>')
                out.append(lines(x + w / 2, top, title[lang], "title", 18, "middle"))
                out.append(lines(x + w / 2, top + 21, sub[lang], "sub", 16, "middle") + "</g>")

    for points, kind, label, pos, anchor in WIRES:
        color = KINDS[kind][0]
        pts = " ".join(f"{x},{y}" for x, y in points)
        out.append(f'<polyline points="{pts}" class="wire" stroke="{color}"/>')
        out.append(f'<polyline points="{pts}" class="current" stroke="{color}"/>')
        end = points[-1]
        out.append(f'<circle cx="{end[0]}" cy="{end[1]}" r="3.2" fill="{color}"/>')
        if label[lang] and pos:
            out.append(f'<text x="{pos[0]}" y="{pos[1]}" class="wire-label" fill="{color}" text-anchor="{anchor}">{escape(label[lang])}</text>')

    for text, x, y, anchor in NOTES:
        out.append(f'<text x="{x}" y="{y}" class="note" text-anchor="{anchor}">{escape(text[lang])}</text>')

    legend_x = 44
    legend: list[str] = []
    for kind, (color, es, en) in KINDS.items():
        label = es if lang == "es" else en
        legend.append(f'<line x1="{legend_x}" y1="962" x2="{legend_x + 34}" y2="962" stroke="{color}" stroke-width="2.4" class="current-legend"/>')
        legend.append(f'<text x="{legend_x + 44}" y="967" class="legend">{escape(label)}</text>')
        legend_x += 64 + 7.6 * len(label)

    title = "Arquitectura" if lang == "es" else "Architecture"
    lead = ("Qué corre dónde, cómo se hablan y qué guarda cada uno." if lang == "es"
            else "What runs where, how the pieces talk and what each one keeps.")
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comanda · {title}</title>
<style>
  :root {{ color-scheme: dark; }}
  html, body {{ margin: 0; background: #171c22; }}
  body {{ display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  svg {{ width: 100%; max-width: {W}px; height: auto; display: block; font-family: "Archivo", "Segoe UI", system-ui, sans-serif; }}
  .kicker {{ fill: #ebe6dc; font-size: 22px; font-weight: 800; letter-spacing: 0.14em; }}
  .lead {{ fill: #a3abb5; font-size: 18px; }}
  .meta {{ fill: #848d98; font: 15px Consolas, "JetBrains Mono", monospace; }}
  .rule {{ stroke: #c07a45; stroke-width: 2; opacity: 0.55; }}
  .zone {{ fill: none; stroke: #313944; stroke-width: 1.2; stroke-dasharray: 2 6; }}
  .zone-title {{ fill: #848d98; font-size: 13px; font-weight: 800; letter-spacing: 0.14em; }}
  .group {{ fill: #1f252d; stroke: #6e4a31; stroke-width: 1.4; stroke-dasharray: 6 5; }}
  .group-title {{ fill: #c07a45; font: 800 17px Consolas, "JetBrains Mono", monospace; }}
  .box, .ext {{ fill: #262d36; stroke: #4a5461; stroke-width: 1.2; }}
  .ext {{ stroke-dasharray: 4 4; }}
  .inner {{ fill: #262d36; stroke: #4a5461; stroke-width: 1.1; }}
  .lib {{ fill: #1b2128; stroke: #4a5461; stroke-width: 1.1; }}
  .title {{ fill: #ebe6dc; font-size: 16.5px; font-weight: 700; }}
  .title-left {{ fill: #ebe6dc; font: 700 15px Consolas, "JetBrains Mono", monospace; }}
  .sub {{ fill: #a3abb5; font: 12.6px Consolas, "JetBrains Mono", monospace; }}
  .note {{ fill: #848d98; font: italic 13px "Archivo", "Segoe UI", sans-serif; }}
  .wire {{ fill: none; stroke-width: 1.4; opacity: 0.35; }}
  .current {{ fill: none; stroke-width: 2; stroke-dasharray: 4 10; animation: flow 0.84s linear infinite; }}
  .current-legend {{ stroke-dasharray: 4 10; animation: flow 0.84s linear infinite; }}
  .wire-label {{ font: 700 12.5px Consolas, "JetBrains Mono", monospace; }}
  .legend {{ fill: #a3abb5; font-size: 14px; }}
  .hover rect {{ transition: stroke 0.15s; }}
  .hover:hover rect {{ stroke: #ffb648; }}
  @keyframes flow {{ to {{ stroke-dashoffset: -14; }} }}
  @media (prefers-reduced-motion: reduce) {{ .current, .current-legend {{ animation: none; }} }}
</style>
</head>
<body>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="Comanda · {title}">
  <rect width="{W}" height="{H}" fill="#171c22"/>
  <rect x="44" y="38" width="10" height="10" fill="#ffb648"/>
  <text x="66" y="50" class="kicker">COMANDA · {title.upper()}</text>
  <text x="{W - 44}" y="50" class="meta" text-anchor="end">.NET 8 · React 19 · PostgreSQL 17 · Docker</text>
  <line x1="44" y1="72" x2="{W - 44}" y2="72" class="rule"/>
  <text x="44" y="104" class="lead">{escape(lead)}</text>
  {"".join(out)}
  {"".join(legend)}
</svg>
</body>
</html>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, name in (("es", "arquitectura.html"), ("en", "arquitectura_en.html")):
        (OUT / name).write_text(render(lang), encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
