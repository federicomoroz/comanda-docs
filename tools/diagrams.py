#!/usr/bin/env python3
"""Generates the animated diagrams in docs/diagrams/ (Spanish and English).

Each diagram is one self-contained HTML page: an SVG that plays its steps in a
loop with CSS animations only, so it opens offline, respects
prefers-reduced-motion, and can be recorded frame by frame into a GIF
(tools/record.py) by pausing every animation at a given time.

    python tools/diagrams.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

W, H = 1200, 750
STEP = 2.8  # seconds per step


@dataclass
class Node:
    id: str
    x: int
    y: int
    w: int
    h: int
    title: dict
    sub: dict = field(default_factory=lambda: {"es": "", "en": ""})
    group: bool = False  # a container drawn behind its children


@dataclass
class Packet:
    path: list  # [(x, y), ...] walked at constant speed during the step
    label: dict
    color: str = "accent"


@dataclass
class Badge:
    x: int
    y: int
    text: dict
    color: str = "accent"
    until: int | None = None  # last step it stays on (default: only its own)
    anchor: str = "middle"


@dataclass
class Cut:
    x: int
    y: int
    until: int | None = None


@dataclass
class Step:
    title: dict
    body: dict
    active: list = field(default_factory=list)
    packets: list = field(default_factory=list)
    badges: list = field(default_factory=list)
    cuts: list = field(default_factory=list)


@dataclass
class Diagram:
    slug: str
    kicker: dict
    nodes: list
    wires: list  # list of point lists
    steps: list
    foot: dict


COLORS = {
    "accent": "#ffb648",
    "copper": "#c07a45",
    "ok": "#6fd08c",
    "stop": "#ec6a5e",
    "data": "#4dd0e1",
}


def pct(value: float) -> str:
    return f"{max(0.0, min(100.0, value)):.3f}%"


def window(step: int, total: int, until: int | None = None) -> tuple[float, float]:
    start = step / total * 100
    end = ((until if until is not None else step) + 1) / total * 100
    return start, end


def show_keyframes(name: str, start: float, end: float) -> str:
    fade = 0.6
    frames = [f"0% {{ opacity: 0; }}"]
    if start > 0:
        frames.append(f"{pct(start - 0.01)} {{ opacity: 0; }}")
    frames.append(f"{pct(start + fade)} {{ opacity: 1; }}")
    if end < 100:
        frames.append(f"{pct(end - fade)} {{ opacity: 1; }}")
        frames.append(f"{pct(end)} {{ opacity: 0; }}")
        frames.append("100% { opacity: 0; }")
    else:
        frames.append(f"{pct(99.2)} {{ opacity: 1; }}")
        frames.append("100% { opacity: 0; }")
    return f"@keyframes {name} {{ {' '.join(frames)} }}"


def move_keyframes(name: str, start: float, end: float, path: list) -> str:
    """Walks the path during the first 55% of the step window and fades out on arrival: the box's glow and badges keep the state."""
    span = end - start
    travel = span * 0.55
    lengths = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(path, path[1:])]
    total = sum(lengths) or 1
    frames = [f"0% {{ opacity: 0; transform: translate({path[0][0]}px, {path[0][1]}px); }}"]
    if start > 0:
        frames.append(f"{pct(start - 0.01)} {{ opacity: 0; transform: translate({path[0][0]}px, {path[0][1]}px); }}")
    frames.append(f"{pct(start + 0.4)} {{ opacity: 1; transform: translate({path[0][0]}px, {path[0][1]}px); }}")
    walked = 0.0
    for (x, y), length in zip(path[1:], lengths):
        walked += length
        frames.append(f"{pct(start + 0.4 + travel * walked / total)} {{ opacity: 1; transform: translate({x}px, {y}px); }}")
    last = path[-1]
    arrived = start + 0.4 + travel
    frames.append(f"{pct(arrived + span * 0.06)} {{ opacity: 1; transform: translate({last[0]}px, {last[1]}px); }}")
    frames.append(f"{pct(arrived + span * 0.14)} {{ opacity: 0; transform: translate({last[0]}px, {last[1]}px); }}")
    frames.append(f"100% {{ opacity: 0; transform: translate({last[0]}px, {last[1]}px); }}")
    return f"@keyframes {name} {{ {' '.join(frames)} }}"


def text_lines(x: float, y: float, text: str, cls: str, gap: int = 18, anchor: str = "middle") -> str:
    lines = text.split("\n")
    return "".join(
        f'<text x="{x}" y="{y + i * gap}" class="{cls}" text-anchor="{anchor}">{escape(line)}</text>' for i, line in enumerate(lines)
    )


def wrap(text: str, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


def render(d: Diagram, lang: str) -> str:
    total = len(d.steps)
    cycle = total * STEP
    css: list[str] = []
    svg: list[str] = []

    for wire in d.wires:
        points = " ".join(f"{x},{y}" for x, y in wire)
        svg.append(f'<polyline points="{points}" class="wire"/>')
        svg.append(f'<polyline points="{points}" class="current"/>')

    for node in d.nodes:
        cls = "group" if node.group else "box"
        svg.append(f'<rect x="{node.x}" y="{node.y}" width="{node.w}" height="{node.h}" rx="8" class="{cls}"/>')
        svg.append(f'<rect id="glow-{node.id}" x="{node.x}" y="{node.y}" width="{node.w}" height="{node.h}" rx="8" class="glow"/>')
        if node.group:
            svg.append(text_lines(node.x + 16, node.y + 26, node.title[lang], "group-title", anchor="start"))
            if node.sub[lang]:
                svg.append(text_lines(node.x + node.w - 16, node.y + 26, node.sub[lang], "sub", anchor="end"))
        else:
            sub_lines = node.sub[lang].split("\n") if node.sub[lang] else []
            block = 22 + 17 * len(sub_lines)
            top = node.y + node.h / 2 - block / 2 + 15
            svg.append(text_lines(node.x + node.w / 2, top, node.title[lang], "title"))
            if sub_lines:
                svg.append(text_lines(node.x + node.w / 2, top + 22, node.sub[lang], "sub", gap=17))

    for node in d.nodes:
        steps = [i for i, s in enumerate(d.steps) if node.id in s.active]
        if not steps:
            continue
        frames = ["0% { opacity: 0; }"]
        for i in steps:
            start, end = window(i, total)
            frames.append(f"{pct(start - 0.01)} {{ opacity: 0; }} {pct(start + 0.6)} {{ opacity: 1; }}")
            frames.append(f"{pct(end - 0.6)} {{ opacity: 1; }} {pct(end)} {{ opacity: 0; }}")
        frames.append("100% { opacity: 0; }")
        css.append(f"@keyframes g-{node.id} {{ {' '.join(frames)} }}")
        css.append(f"#glow-{node.id} {{ animation: g-{node.id} {cycle}s linear infinite; }}")

    serial = 0
    for i, step in enumerate(d.steps):
        start, end = window(i, total)
        for packet in step.packets:
            serial += 1
            name = f"p{serial}"
            color = COLORS[packet.color]
            label = packet.label[lang]
            width = max(36, 8.2 * len(label) + 22)
            css.append(move_keyframes(name, start, end, packet.path))
            svg.append(
                f'<g class="packet" style="animation: {name} {cycle}s linear infinite;">'
                f'<rect x="{-width / 2}" y="-13" width="{width}" height="26" rx="13" fill="#171c22" stroke="{color}" stroke-width="1.6"/>'
                f'<circle cx="{-width / 2 + 13}" cy="0" r="4" fill="{color}"/>'
                f'<text x="{-width / 2 + 23}" y="4.5" class="packet-text" fill="{color}">{escape(label)}</text></g>'
            )
        for badge in step.badges:
            serial += 1
            name = f"b{serial}"
            b_start, b_end = window(i, total, badge.until)
            color = COLORS[badge.color]
            css.append(show_keyframes(name, b_start, b_end))
            lines = badge.text[lang].split("\n")
            width = max(8.0 * max(len(l) for l in lines) + 26, 40)
            height = 14 + 18 * len(lines)
            left = badge.x - width / 2 if badge.anchor == "middle" else badge.x
            svg.append(
                f'<g style="animation: {name} {cycle}s linear infinite; opacity: 0;">'
                f'<rect x="{left}" y="{badge.y - 15}" width="{width}" height="{height}" rx="6" fill="#171c22" stroke="{color}" stroke-width="1.2"/>'
                + "".join(
                    f'<text x="{left + width / 2}" y="{badge.y + 1 + k * 18}" class="badge-text" fill="{color}" text-anchor="middle">{escape(l)}</text>'
                    for k, l in enumerate(lines)
                )
                + "</g>"
            )
        for cut in step.cuts:
            serial += 1
            name = f"c{serial}"
            c_start, c_end = window(i, total, cut.until)
            css.append(show_keyframes(name, c_start, c_end))
            svg.append(
                f'<g style="animation: {name} {cycle}s linear infinite; opacity: 0;" class="cut">'
                f'<circle cx="{cut.x}" cy="{cut.y}" r="15" fill="#171c22" stroke="#ec6a5e" stroke-width="2"/>'
                f'<path d="M{cut.x - 6},{cut.y - 6} L{cut.x + 6},{cut.y + 6} M{cut.x + 6},{cut.y - 6} L{cut.x - 6},{cut.y + 6}" stroke="#ec6a5e" stroke-width="2.4"/></g>'
            )

    # Step header: number, title and body, one set per step.
    head: list[str] = []
    for i, step in enumerate(d.steps):
        serial += 1
        name = f"h{serial}"
        start, end = window(i, total)
        css.append(show_keyframes(name, start, end))
        body = "".join(
            f'<text x="160" y="{170 + k * 27}" class="body">{escape(line)}</text>' for k, line in enumerate(wrap(step.body[lang], 82))
        )
        head.append(
            f'<g style="animation: {name} {cycle}s linear infinite; opacity: 0;">'
            f'<rect x="56" y="98" width="76" height="76" rx="10" class="num-box"/>'
            f'<text x="94" y="149" class="num" text-anchor="middle">{i + 1}</text>'
            f'<text x="160" y="134" class="step-title">{escape(step.title[lang])}</text>{body}</g>'
        )
        dot_x = W / 2 - (total - 1) * 11 + i * 22
        css.append(f"@keyframes d{serial} {{ 0% {{ fill: #4a5461; }} {pct(start)} {{ fill: #4a5461; }} {pct(start + 0.1)} {{ fill: #ffb648; }} {pct(end)} {{ fill: #ffb648; }} {pct(end + 0.1)} {{ fill: #4a5461; }} 100% {{ fill: #4a5461; }} }}")
        svg.append(f'<circle cx="{dot_x}" cy="{H - 104}" r="4" style="animation: d{serial} {cycle}s linear infinite;"/>')

    foot = "".join(
        f'<text x="56" y="{H - 52 + k * 24}" class="foot">{escape(line)}</text>' for k, line in enumerate(wrap(d.foot[lang], 120))
    )
    title = d.kicker[lang]
    lang_attr = "es" if lang == "es" else "en"
    return f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comanda · {escape(title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  html, body {{ margin: 0; background: #171c22; }}
  body {{ display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  svg {{ width: 100%; max-width: {W}px; height: auto; display: block; font-family: "Archivo", "Segoe UI", system-ui, sans-serif; }}
  .frame {{ fill: #171c22; }}
  .kicker {{ fill: #ebe6dc; font-size: 22px; font-weight: 800; letter-spacing: 0.14em; }}
  .meta {{ fill: #848d98; font: 15px Consolas, "JetBrains Mono", monospace; }}
  .rule {{ stroke: #c07a45; stroke-width: 2; opacity: 0.55; }}
  .num-box {{ fill: rgba(255, 182, 72, 0.10); stroke: #ffb648; stroke-width: 2; }}
  .num {{ fill: #ffb648; font-size: 38px; font-weight: 800; }}
  .step-title {{ fill: #ebe6dc; font-size: 34px; font-weight: 800; }}
  .body {{ fill: #a3abb5; font-size: 19px; }}
  .box {{ fill: #262d36; stroke: #4a5461; stroke-width: 1.2; }}
  .group {{ fill: #1f252d; stroke: #6e4a31; stroke-width: 1.4; stroke-dasharray: 6 5; }}
  .glow {{ fill: rgba(255, 182, 72, 0.07); stroke: #ffb648; stroke-width: 2; opacity: 0; }}
  .title {{ fill: #ebe6dc; font-size: 18px; font-weight: 700; }}
  .group-title {{ fill: #c07a45; font-size: 14px; font-weight: 800; letter-spacing: 0.12em; }}
  .sub {{ fill: #848d98; font: 13.5px Consolas, "JetBrains Mono", monospace; }}
  .wire {{ fill: none; stroke: #4a5461; stroke-width: 1.6; }}
  .current {{ fill: none; stroke: #c07a45; stroke-width: 1.6; stroke-dasharray: 3 9; animation: flow 0.8s linear infinite; opacity: 0.8; }}
  @keyframes flow {{ to {{ stroke-dashoffset: -12; }} }}
  .packet-text {{ font: 700 13px Consolas, "JetBrains Mono", monospace; }}
  .badge-text {{ font: 600 13.5px Consolas, "JetBrains Mono", monospace; }}
  .dot {{ fill: #4a5461; }}
  .foot {{ fill: #a3abb5; font-size: 17px; }}
  .foot-band {{ fill: #1f252d; }}
  .foot-edge {{ fill: #c07a45; }}
  {chr(10).join("  " + rule for rule in css)}
  @media (prefers-reduced-motion: reduce) {{
    .current {{ animation: none; }}
  }}
</style>
</head>
<body>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">
  <rect width="{W}" height="{H}" class="frame"/>
  <rect x="56" y="38" width="10" height="10" fill="#ffb648"/>
  <text x="78" y="50" class="kicker">{escape(title.upper())}</text>
  <text x="{W - 56}" y="50" class="meta" text-anchor="end">Comanda · .NET 8 · React · PostgreSQL</text>
  <line x1="56" y1="74" x2="{W - 56}" y2="74" class="rule"/>
  {"".join(head)}
  {"".join(svg)}
  <rect x="0" y="{H - 84}" width="{W}" height="84" class="foot-band"/>
  <rect x="0" y="{H - 84}" width="5" height="84" class="foot-edge"/>
  {foot}
</svg>
</body>
</html>
"""


def t(es: str, en: str) -> dict:
    return {"es": es, "en": en}


# 1. From the table to the invoice ---------------------------------------------------------

STA_X, STA_W = 700, 210
circuit = Diagram(
    slug="circuito",
    kicker=t("De la mesa a la factura", "From the table to the invoice"),
    nodes=[
        Node("mozo", 50, 300, 190, 120, t("Mozo", "Waiter"), t("tablet\nMesa 4", "tablet\nTable 4")),
        Node("server", 330, 280, 270, 160, t("Comanda", "Comanda"), t("salón · cocina · caja\nPC del local", "floor · kitchen · register\nrestaurant's computer")),
        Node("parrilla", STA_X, 262, STA_W, 58, t("Parrilla", "Grill"), t("pantalla + impresora", "screen + printer")),
        Node("cocina", STA_X, 331, STA_W, 58, t("Cocina", "Kitchen"), t("pantalla + impresora", "screen + printer")),
        Node("barra", STA_X, 400, STA_W, 58, t("Barra", "Bar"), t("pantalla", "screen")),
        Node("caja", 330, 520, 270, 100, t("Caja", "Register"), t("cobro y turno", "payments and shift")),
        Node("billing", 700, 520, 210, 100, t("Facturación", "Billing"), t("servicio aparte", "separate service")),
        Node("arca", 990, 520, 160, 100, t("ARCA", "ARCA"), t("autoridad fiscal", "tax authority")),
    ],
    wires=[
        [(240, 360), (330, 360)],
        [(600, 330), (650, 330), (650, 291), (700, 291)],
        [(600, 360), (700, 360)],
        [(600, 390), (650, 390), (650, 429), (700, 429)],
        [(465, 440), (465, 520)],
        [(600, 570), (700, 570)],
        [(910, 570), (990, 570)],
    ],
    steps=[
        Step(t("El mozo carga y envía", "The waiter takes the order"),
             t("Una tablet por mozo, en el Wi‑Fi del local. Lo que carga queda en la cuenta de la mesa hasta que lo envía.",
               "One tablet per waiter, on the restaurant's Wi‑Fi. What they enter stays on the table's tab until they send it."),
             active=["mozo", "server"],
             packets=[Packet([(130, 360), (240, 360), (330, 360)], t("Mesa 4 · 5 ítems", "Table 4 · 5 items"))]),
        Step(t("Una comanda por estación", "One ticket per station"),
             t("Cada estación recibe solo lo suyo, numerado en el día: en pantalla y, si tiene impresora, también en papel.",
               "Each station gets only its own items, numbered within the day: on screen and, if it has a printer, on paper."),
             active=["server", "parrilla", "cocina", "barra"],
             packets=[Packet([(600, 330), (650, 330), (650, 291), (700, 291)], t("#23", "#23")),
                      Packet([(600, 360), (700, 360)], t("#24", "#24")),
                      Packet([(600, 390), (650, 390), (650, 429), (700, 429)], t("#25", "#25"))]),
        Step(t("Listo, y el mozo se entera", "Ready, and the waiter knows"),
             t("La cocina marca listo y la tablet del mozo lo muestra en el momento, sin recargar la pantalla.",
               "The kitchen marks it ready and the waiter's tablet shows it right away, with no reload."),
             active=["parrilla", "mozo"],
             packets=[Packet([(700, 291), (650, 291), (650, 330), (600, 330), (465, 330), (465, 360), (330, 360), (240, 360)], t("listo", "ready"), "ok")],
             badges=[Badge(145, 448, t("3 listos", "3 ready"), "ok")]),
        Step(t("La caja cobra", "The register takes payment"),
             t("Pagos divididos entre efectivo, tarjeta y QR, con propina y vuelto. Al cerrar el turno, el arqueo compara lo esperado con lo contado.",
               "Split payments across cash, card and QR, with tips and change. Closing the shift compares expected and counted cash."),
             active=["server", "caja"],
             packets=[Packet([(465, 400), (465, 440), (465, 520)], t("Mesa 4", "Table 4"))],
             badges=[Badge(465, 650, t("efectivo + QR · propina", "cash + QR · tip"), "accent")]),
        Step(t("Factura, sin hacer esperar", "Invoiced, with no waiting"),
             t("La caja pide la factura y sigue con la próxima mesa. Facturación la manda a ARCA desde su propia cola.",
               "The register asks for the invoice and moves on. Billing sends it to ARCA from its own queue."),
             active=["caja", "billing", "arca"],
             packets=[Packet([(530, 570), (600, 570), (700, 570)], t("pedido", "request")),
                      Packet([(860, 570), (910, 570), (990, 570)], t("CAE?", "CAE?"), "data")]),
        Step(t("CAE y QR, de vuelta en la caja", "CAE and QR, back at the register"),
             t("Factura B autorizada, con el QR de ARCA. En esta versión ARCA está simulado y la factura se imprime como «sin validez fiscal».",
               "Invoice B authorized, with ARCA's QR. In this version ARCA is simulated and the invoice prints as \"not valid for tax purposes\"."),
             active=["billing", "caja"],
             packets=[Packet([(990, 570), (910, 570)], t("CAE", "CAE"), "data"),
                      Packet([(760, 570), (700, 570), (600, 570)], t("autorizada", "authorized"), "ok")],
             badges=[Badge(465, 650, t("Factura B 00003-00000124 · QR", "Invoice B 00003-00000124 · QR"), "ok")]),
    ],
    foot=t("Salón, cocina y caja comparten una base y una transacción. Facturación va aparte, con su base y su cola: si ARCA se cae, el salón ni se entera.",
           "Floor, kitchen and register share one database and one transaction. Billing runs apart, with its own database and queue: if ARCA goes down, the floor never notices."),
)

# 2. Billing can go down and nothing is lost -------------------------------------------------

outbox = Diagram(
    slug="facturacion",
    kicker=t("Si Facturación se cae, nada se pierde", "If billing goes down, nothing is lost"),
    nodes=[
        Node("caja", 40, 335, 170, 110, t("Caja", "Register"), t("Mesa 4", "Table 4")),
        Node("comanda", 265, 265, 330, 250, t("COMANDA", "COMANDA"), t("base propia", "own database"), group=True),
        Node("cuentas", 285, 305, 290, 70, t("cuentas y cobros", "tabs and payments"), t("copia de cada factura", "a copy of each invoice")),
        Node("outbox-c", 285, 395, 290, 90, t("outbox", "outbox"), t("lo que falta mandar", "what is still to send")),
        Node("billing", 655, 265, 330, 250, t("FACTURACIÓN", "BILLING"), t("base propia", "own database"), group=True),
        Node("cola", 675, 305, 290, 70, t("cola hacia ARCA", "queue to ARCA"), t("en orden · numeración correlativa", "in order · consecutive numbers")),
        Node("outbox-b", 675, 395, 290, 90, t("outbox", "outbox"), t("estados con versión", "versioned statuses")),
        Node("arca", 1040, 285, 130, 110, t("ARCA", "ARCA"), t("CAE", "CAE")),
    ],
    wires=[
        [(210, 390), (285, 390)],
        [(575, 420), (675, 340)],
        [(675, 460), (575, 460)],
        [(965, 340), (1040, 340)],
    ],
    steps=[
        Step(t("Se guarda primero", "Saved first"),
             t("El pedido de factura entra al outbox en la misma transacción que la cuenta. Si algo falla después, el pedido ya está guardado.",
               "The invoice request goes into the outbox in the same transaction as the tab. If anything fails later, the request is already saved."),
             active=["caja", "outbox-c"],
             packets=[Packet([(150, 390), (210, 390), (285, 390), (300, 420)], t("factura", "invoice"))]),
        Step(t("Facturación no responde", "Billing does not answer"),
             t("La caja muestra «Esperando a Facturación» y el motivo. El cajero no vuelve a cargar nada: el pedido espera en el outbox.",
               "The register shows \"Waiting for billing\" and why. The cashier re-enters nothing: the request waits in the outbox."),
             active=["outbox-c", "caja"],
             cuts=[Cut(625, 380)],
             badges=[Badge(125, 495, t("Esperando a\nFacturación", "Waiting for\nbilling"), "accent"),
                     Badge(430, 545, t("reintenta: 10 s · 30 s · 2 min…", "retries: 10 s · 30 s · 2 min…"), "copper")]),
        Step(t("Vuelve, y sale solo", "It comes back, and it goes out"),
             t("Medido con las imágenes de producción: el pedido salió solo 14 segundos después de que Facturación volvió.",
               "Measured with the production images: the request went out on its own 14 seconds after billing came back."),
             active=["outbox-c", "cola"],
             packets=[Packet([(560, 420), (575, 420), (675, 340), (690, 340)], t("pedido", "request"))]),
        Step(t("ARCA caída", "ARCA is down"),
             t("La factura espera en la cola de Facturación, en orden, para que la numeración siga correlativa. Cada reintento llega más espaciado.",
               "The invoice waits in billing's queue, in order, so numbering stays consecutive. Each retry comes further apart."),
             active=["cola"],
             cuts=[Cut(1002, 340)],
             badges=[Badge(820, 545, t("intento 1 · 2 · 3", "attempt 1 · 2 · 3"), "stop"),
                     Badge(125, 495, t("ARCA no\nrespondió", "ARCA did not\nanswer"), "stop")]),
        Step(t("ARCA vuelve: CAE", "ARCA is back: CAE"),
             t("La cola sigue sola desde la primera factura pendiente. Nadie tiene que reintentar a mano.",
               "The queue resumes on its own from the first pending invoice. Nobody has to retry by hand."),
             active=["cola", "arca"],
             packets=[Packet([(950, 330), (1040, 330)], t("CAE?", "CAE?"), "data"),
                      Packet([(1040, 360), (950, 360)], t("CAE", "CAE"), "data")]),
        Step(t("El estado vuelve a Comanda", "The status goes back to Comanda"),
             t("Cada cambio viaja con un número de versión: si uno viejo llega tarde, no pisa al nuevo. Con Comanda caída, espera en el outbox de Facturación.",
               "Every change travels with a version number: an old one arriving late never overwrites a newer one. With Comanda down, it waits in billing's outbox."),
             active=["outbox-b", "cuentas", "caja"],
             packets=[Packet([(690, 460), (675, 460), (575, 460), (560, 460)], t("v3", "v3"), "ok")],
             badges=[Badge(125, 495, t("Autorizada", "Authorized"), "ok"),
                     Badge(430, 545, t("v3 aplicada · un v2 tardío se ignora", "v3 applied · a late v2 is ignored"), "ok")]),
    ],
    foot=t("Cada servicio guarda en su outbox lo que tiene que mandarle al otro y reintenta hasta que llega. Repetir no duplica: el pedido lleva un id y el estado, una versión.",
           "Each service keeps what it owes the other in its outbox and retries until it arrives. Repeating never duplicates: the request carries an id and the status a version."),
)

# 3. Runs on the restaurant's computer, with or without internet -----------------------------

DEV_X, DEV_W = 40, 200
local = Diagram(
    slug="instalacion",
    kicker=t("Funciona sin internet", "Works without internet"),
    nodes=[
        Node("mozos", DEV_X, 255, DEV_W, 64, t("Tablets de mozos", "Waiters' tablets"), t("Wi‑Fi del local", "local Wi‑Fi")),
        Node("pantallas", DEV_X, 335, DEV_W, 64, t("Pantallas de cocina", "Kitchen screens"), t("una por estación", "one per station")),
        Node("caja", DEV_X, 415, DEV_W, 64, t("Caja", "Register"), t("PC o tablet", "PC or tablet")),
        Node("impresoras", DEV_X, 495, DEV_W, 64, t("Impresoras térmicas", "Thermal printers"), t("red, puerto 9100", "network, port 9100")),
        Node("pc", 320, 245, 520, 330, t("PC DEL LOCAL · DOCKER", "RESTAURANT'S COMPUTER · DOCKER"), t("", ""), group=True),
        Node("server", 345, 290, 230, 80, t("Comanda", "Comanda"), t("salón · cocina · caja", "floor · kitchen · register")),
        Node("facturacion", 590, 290, 230, 80, t("Facturación", "Billing"), t("cola hacia ARCA", "queue to ARCA")),
        Node("db", 345, 390, 230, 70, t("PostgreSQL", "PostgreSQL"), t("dos bases", "two databases")),
        Node("backup", 590, 390, 230, 70, t("Respaldos", "Backups"), t("las dos bases", "both databases")),
        Node("agente", 345, 480, 475, 70, t("Agente de impresión", "Print agent"), t("ESC/POS por TCP", "ESC/POS over TCP")),
        Node("arca", 960, 265, 200, 70, t("ARCA", "ARCA"), t("facturas", "invoices")),
        Node("avisos", 960, 365, 200, 70, t("Avisos al dueño", "Owner alerts"), t("Telegram · mail", "Telegram · email")),
        Node("disco", 960, 495, 200, 70, t("Disco externo", "External disk"), t("o carpeta en la nube", "or a cloud folder")),
    ],
    wires=[
        [(240, 287), (345, 330)],
        [(240, 367), (345, 345)],
        [(240, 447), (345, 360)],
        [(240, 527), (345, 515)],
        [(820, 330), (890, 330), (890, 300), (960, 300)],
        [(820, 345), (890, 345), (890, 400), (960, 400)],
        [(820, 425), (900, 425), (900, 530), (960, 530)],
    ],
    steps=[
        Step(t("Todo pasa por el Wi‑Fi del local", "Everything runs on the local Wi‑Fi"),
             t("Tablets, pantallas de cocina, caja e impresoras hablan con una PC del restaurante, no con un servidor en la nube.",
               "Tablets, kitchen screens, the register and the printers talk to a computer in the restaurant, not to a cloud server."),
             active=["mozos", "pantallas", "caja", "server"],
             packets=[Packet([(200, 287), (240, 287), (345, 330)], t("pedido", "order")),
                      Packet([(345, 345), (240, 367), (200, 367)], t("#24", "#24")),
                      Packet([(345, 515), (240, 527), (200, 527)], t("ticket", "ticket"), "copper")]),
        Step(t("Se corta internet", "The internet goes down"),
             t("El salón sigue igual: se toman pedidos, la cocina recibe sus comandas y la caja cobra.",
               "The floor carries on: orders are taken, the kitchen gets its tickets and the register takes payments."),
             active=["mozos", "pantallas", "caja", "server"],
             cuts=[Cut(925, 300, until=2), Cut(925, 400, until=2)],
             packets=[Packet([(200, 287), (240, 287), (345, 330)], t("pedido", "order")),
                      Packet([(345, 345), (240, 367), (200, 367)], t("#25", "#25")),
                      Packet([(200, 447), (240, 447), (345, 360)], t("cobro", "payment"))]),
        Step(t("Lo que necesita internet, espera", "What needs the internet waits"),
             t("Las facturas esperan en la cola de Facturación y los avisos al dueño, en el outbox. La caja ve cuántas hay en espera.",
               "Invoices wait in billing's queue and the owner's alerts in the outbox. The register sees how many are waiting."),
             active=["facturacion", "server"],
             badges=[Badge(705, 600, t("3 facturas en cola", "3 invoices queued"), "accent"),
                     Badge(460, 600, t("2 avisos esperando", "2 alerts waiting"), "copper")]),
        Step(t("Vuelve internet, y sale todo", "The internet is back, and it all goes out"),
             t("La cola de facturas y la de avisos se vacían solas, en el orden en que pasaron las cosas.",
               "The invoice queue and the alert queue drain on their own, in the order things happened."),
             active=["facturacion", "arca", "avisos"],
             packets=[Packet([(790, 330), (820, 330), (890, 330), (890, 300), (960, 300)], t("3 facturas", "3 invoices"), "data"),
                      Packet([(790, 345), (820, 345), (890, 345), (890, 400), (960, 400)], t("2 avisos", "2 alerts"), "copper")]),
        Step(t("Respaldo de las dos bases", "Both databases backed up"),
             t("Al arrancar, si el último respaldo tiene más de un día, y después una vez por día. Se restaura con un comando.",
               "On start if the last backup is over a day old, then once a day. Restoring takes one command."),
             active=["backup", "disco", "db"],
             packets=[Packet([(790, 425), (820, 425), (900, 425), (900, 530), (960, 530)], t("respaldo", "backup"), "ok")]),
    ],
    foot=t("Internet solo hace falta para facturar y avisar al dueño, y las dos cosas esperan en cola. Una caída de internet no frena el servicio.",
           "The internet is only needed to invoice and to alert the owner, and both wait in a queue. An outage does not stop service."),
)

DIAGRAMS = [circuit, outbox, local]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for diagram in DIAGRAMS:
        for lang in ("es", "en"):
            suffix = "" if lang == "es" else "_en"
            path = OUT / f"{diagram.slug}{suffix}.html"
            path.write_text(render(diagram, lang), encoding="utf-8", newline="\n")
            print("wrote", path.relative_to(OUT.parent.parent))


if __name__ == "__main__":
    main()
