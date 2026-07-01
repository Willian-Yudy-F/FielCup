"""Circular knockout poster for FielCup.

The renderer deliberately uses drawn flag badges instead of federation crests.
That keeps the public GitHub Pages artifact self-contained and avoids depending
on official badge assets or external CDNs.
"""

from __future__ import annotations

import math
import re
from html import escape
from typing import Any

from dixon_coles import analisar_jogo
from talento import ALPHA_PADRAO, ratings_blendados


DISPLAY = {
    "Bosnia and Herzegovina": "Bosnia",
    "Czech Republic": "Czechia",
    "United States": "USA",
}

ROUND32_FIXTURES = [
    {"match": "73", "home": "South Africa", "away": "Canada", "status": "confirmed"},
    {"match": "74", "home": "Germany", "away": "Paraguay", "status": "confirmed"},
    {"match": "75", "home": "Netherlands", "away": "Morocco", "status": "confirmed"},
    {"match": "76", "home": "Brazil", "away": "Japan", "status": "confirmed"},
    {"match": "77", "home": "France", "away": None, "status": "TBD third-place team"},
    {"match": "78", "home": "Ivory Coast", "away": "Norway", "status": "confirmed"},
    {"match": "79", "home": "Mexico", "away": None, "status": "TBD third-place team"},
    {"match": "80", "home": None, "away": None, "status": "Group L winner vs TBD"},
    {
        "match": "81",
        "home": "United States",
        "away": "Bosnia and Herzegovina",
        "status": "confirmed",
    },
    {"match": "82", "home": "Belgium", "away": None, "status": "TBD third-place team"},
    {"match": "83", "home": None, "away": None, "status": "Group K runner-up vs Group L runner-up"},
    {"match": "84", "home": "Spain", "away": None, "status": "TBD Group J runner-up"},
    {"match": "85", "home": "Switzerland", "away": None, "status": "TBD third-place team"},
    {"match": "86", "home": "Argentina", "away": "Cape Verde", "status": "confirmed"},
    {"match": "87", "home": None, "away": None, "status": "Group K winner vs TBD"},
    {"match": "88", "home": "Australia", "away": "Egypt", "status": "confirmed"},
]

COUNTRY_CODES = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Belgium": "BEL",
    "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Cape Verde": "CPV",
    "Egypt": "EGY",
    "France": "FRA",
    "Germany": "GER",
    "Ivory Coast": "CIV",
    "Japan": "JPN",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "Norway": "NOR",
    "Paraguay": "PAR",
    "South Africa": "RSA",
    "Spain": "ESP",
    "Switzerland": "SUI",
    "United States": "USA",
}

INK = "#111111"
PAPER = "#f2efe6"
MUTED = "#8a867a"
LINE = "#47433c"
RED = "#c0392b"
GOLD = "#c9a227"
GREEN = "#2c9f63"


def nm(team: str | None) -> str:
    if team is None:
        return "TBD"
    return DISPLAY.get(team, team)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def advance_probability(home_win: float, draw: float, away_win: float) -> tuple[float, float]:
    decided = home_win + away_win
    penalty_home = home_win / decided if decided else 0.5
    home_advance = home_win + draw * penalty_home
    return home_advance, 1.0 - home_advance


def build_round32(model: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Price the visible Round of 32 fixtures with the FielCup model."""
    model = model or ratings_blendados(ALPHA_PADRAO)
    rows: list[dict[str, Any]] = []
    for fixture in ROUND32_FIXTURES:
        home = fixture["home"]
        away = fixture["away"]
        if home and away:
            analysis = analisar_jogo(model, home, away, neutro=True)
            home_adv, away_adv = advance_probability(
                analysis["p_casa"],
                analysis["p_empate"],
                analysis["p_fora"],
            )
            pick = home if home_adv >= away_adv else away
            rows.append(
                {
                    "match": fixture["match"],
                    "home": home,
                    "away": away,
                    "homeLabel": nm(home),
                    "awayLabel": nm(away),
                    "status": "confirmed",
                    "pHome": pct(analysis["p_casa"]),
                    "pDraw": pct(analysis["p_empate"]),
                    "pAway": pct(analysis["p_fora"]),
                    "homeAdvance": pct(home_adv),
                    "awayAdvance": pct(away_adv),
                    "homeAdvanceValue": home_adv,
                    "awayAdvanceValue": away_adv,
                    "advancePick": nm(pick),
                    "advancePickTeam": pick,
                    "advancePickValue": max(home_adv, away_adv),
                    "xg": f"{analysis['xg_casa']:.2f}-{analysis['xg_fora']:.2f}",
                    "likelyScore": (
                        f"{analysis['placar_provavel'][0]}-"
                        f"{analysis['placar_provavel'][1]}"
                    ),
                }
            )
        else:
            rows.append(
                {
                    "match": fixture["match"],
                    "home": home,
                    "away": away,
                    "homeLabel": nm(home) if home else "TBD",
                    "awayLabel": nm(away) if away else "TBD",
                    "status": fixture["status"],
                }
            )
    return rows


def _polar(cx: float, cy: float, radius: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg - 90)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)


def _path(points: list[tuple[float, float]]) -> str:
    first, *rest = points
    commands = [f"M {first[0]:.1f} {first[1]:.1f}"]
    commands.extend(f"L {x:.1f} {y:.1f}" for x, y in rest)
    return " ".join(commands)


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: int,
    fill: str = PAPER,
    weight: int = 700,
    anchor: str = "middle",
    extra: str = "",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Archivo, Helvetica, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" {extra}>'
        f"{escape(value)}</text>"
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _flag_badge(team: str | None, x: float, y: float, r: float, uid: str) -> str:
    clip = f"clip-{uid}"
    code = "TBD" if team is None else COUNTRY_CODES.get(team, nm(team)[:3].upper())
    parts = [f'<clipPath id="{clip}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/></clipPath>']

    def rect(rx: float, ry: float, rw: float, rh: float, color: str) -> None:
        parts.append(
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
            f'fill="{color}" clip-path="url(#{clip})"/>'
        )

    def circle(cx: float, cy: float, cr: float, color: str) -> None:
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{cr:.1f}" fill="{color}" '
            f'clip-path="url(#{clip})"/>'
        )

    x0, y0 = x - r, y - r
    d = 2 * r
    if team is None:
        circle(x, y, r, "#242321")
        parts.append(_text(x, y + 5, "TBD", size=12, fill="#b8b0a4", weight=900))
    elif team == "Brazil":
        circle(x, y, r, "#229e45")
        parts.append(
            f'<path d="M {x:.1f} {y0 + 8:.1f} L {x0 + d - 8:.1f} {y:.1f} '
            f'L {x:.1f} {y0 + d - 8:.1f} L {x0 + 8:.1f} {y:.1f} Z" '
            f'fill="#f6d04d" clip-path="url(#{clip})"/>'
        )
        circle(x, y, r * 0.35, "#234a9f")
    elif team == "Japan":
        circle(x, y, r, "#ffffff")
        circle(x, y, r * 0.42, "#bc002d")
    elif team == "Canada":
        rect(x0, y0, d * 0.28, d, "#d52b1e")
        rect(x0 + d * 0.28, y0, d * 0.44, d, "#ffffff")
        rect(x0 + d * 0.72, y0, d * 0.28, d, "#d52b1e")
        circle(x, y, r * 0.16, "#d52b1e")
    elif team in {"France", "Ivory Coast", "Mexico", "Belgium"}:
        colors = {
            "France": ("#0055a4", "#ffffff", "#ef4135"),
            "Ivory Coast": ("#f77f00", "#ffffff", "#009e60"),
            "Mexico": ("#006847", "#ffffff", "#ce1126"),
            "Belgium": ("#111111", "#fdda24", "#ef3340"),
        }[team]
        for i, color in enumerate(colors):
            rect(x0 + i * d / 3, y0, d / 3, d, color)
    elif team in {"Germany", "Netherlands", "Paraguay", "Spain", "Argentina", "Egypt"}:
        colors = {
            "Germany": ("#111111", "#dd0000", "#ffce00"),
            "Netherlands": ("#ae1c28", "#ffffff", "#21468b"),
            "Paraguay": ("#d52b1e", "#ffffff", "#0038a8"),
            "Spain": ("#aa151b", "#f1bf00", "#aa151b"),
            "Argentina": ("#75aadb", "#ffffff", "#75aadb"),
            "Egypt": ("#ce1126", "#ffffff", "#111111"),
        }[team]
        heights = (d * 0.25, d * 0.5, d * 0.25) if team == "Spain" else (d / 3, d / 3, d / 3)
        offset = y0
        for height, color in zip(heights, colors):
            rect(x0, offset, d, height, color)
            offset += height
        if team == "Argentina":
            circle(x, y, r * 0.12, "#f6b40e")
    elif team == "United States":
        for i in range(7):
            rect(x0, y0 + i * d / 7, d, d / 7, "#b22234" if i % 2 == 0 else "#ffffff")
        rect(x0, y0, d * 0.48, d * 0.48, "#3c3b6e")
        circle(x0 + d * 0.24, y0 + d * 0.24, r * 0.08, "#ffffff")
    elif team == "Switzerland":
        circle(x, y, r, "#d52b1e")
        rect(x - r * 0.16, y - r * 0.52, r * 0.32, r * 1.04, "#ffffff")
        rect(x - r * 0.52, y - r * 0.16, r * 1.04, r * 0.32, "#ffffff")
    elif team == "Norway":
        circle(x, y, r, "#ba0c2f")
        rect(x0, y - r * 0.22, d, r * 0.44, "#ffffff")
        rect(x - r * 0.44, y0, r * 0.44, d, "#ffffff")
        rect(x0, y - r * 0.11, d, r * 0.22, "#00205b")
        rect(x - r * 0.33, y0, r * 0.22, d, "#00205b")
    elif team == "Morocco":
        circle(x, y, r, "#c1272d")
        parts.append(
            f'<path d="M {x:.1f} {y - r * .38:.1f} L {x + r * .22:.1f} {y + r * .28:.1f} '
            f'L {x - r * .36:.1f} {y - r * .12:.1f} L {x + r * .36:.1f} {y - r * .12:.1f} '
            f'L {x - r * .22:.1f} {y + r * .28:.1f} Z" fill="none" stroke="#006233" '
            f'stroke-width="{max(2.0, r * .08):.1f}" clip-path="url(#{clip})"/>'
        )
    elif team == "Cape Verde":
        circle(x, y, r, "#003893")
        rect(x0, y + r * 0.10, d, r * 0.16, "#ffffff")
        rect(x0, y + r * 0.22, d, r * 0.09, "#cf2027")
        circle(x - r * 0.28, y + r * 0.16, r * 0.08, "#f7d116")
    elif team == "Australia":
        circle(x, y, r, "#012169")
        circle(x + r * 0.28, y + r * 0.08, r * 0.12, "#ffffff")
        rect(x0, y0, d * 0.46, d * 0.42, "#012169")
        rect(x0, y0 + d * 0.18, d * 0.46, d * 0.08, "#ffffff")
        rect(x0 + d * 0.18, y0, d * 0.08, d * 0.42, "#ffffff")
    elif team == "South Africa":
        circle(x, y, r, "#007a4d")
        parts.append(
            f'<path d="M {x0:.1f} {y0:.1f} L {x + r * .08:.1f} {y:.1f} L {x0:.1f} {y0 + d:.1f} Z" '
            f'fill="#000000" clip-path="url(#{clip})"/>'
        )
        parts.append(
            f'<path d="M {x0 + r * .16:.1f} {y0:.1f} L {x + r * .22:.1f} {y:.1f} '
            f'L {x0 + r * .16:.1f} {y0 + d:.1f}" fill="none" stroke="#ffb81c" '
            f'stroke-width="{r * .22:.1f}" clip-path="url(#{clip})"/>'
        )
    elif team == "Bosnia and Herzegovina":
        circle(x, y, r, "#002f6c")
        parts.append(
            f'<path d="M {x + r * .12:.1f} {y0:.1f} L {x + r:.1f} {y0 + d:.1f} '
            f'L {x + r * .12:.1f} {y0 + d:.1f} Z" fill="#f7d116" clip-path="url(#{clip})"/>'
        )
    else:
        circle(x, y, r, "#28313f")
        parts.append(_text(x, y + 5, code, size=12, fill=PAPER, weight=900))

    parts.append(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="none" '
        f'stroke="#f2efe6" stroke-opacity=".35" stroke-width="1.2"/>'
    )
    return "\n".join(parts)


def _team_node(
    game: dict[str, Any],
    key: str,
    x: float,
    y: float,
    *,
    selected: bool,
    side: int,
    uid: str,
) -> str:
    team = game.get(key)
    value = game.get(f"{key}AdvanceValue")
    stroke = RED if selected else LINE
    label_anchor = "start" if side >= 0 else "end"
    label_x = x + side * 50
    percent = "--" if value is None else f"{value * 100:.0f}%"
    name = nm(team)
    if len(name) > 15:
        name = name[:14] + "."
    return f"""
  <g>
    <circle cx="{x:.1f}" cy="{y:.1f}" r="35" fill="#1b1a18" stroke="{stroke}" stroke-width="{3 if selected else 1.5}"/>
    {_flag_badge(team, x, y, 28, uid)}
    {_text(label_x, y - 5, name.upper(), size=17, fill=PAPER if selected else "#bdb5a8", weight=900, anchor=label_anchor)}
    {_text(label_x, y + 18, percent, size=15, fill=RED if selected else GOLD, weight=900, anchor=label_anchor)}
  </g>"""


def _winner_node(team: str | None, x: float, y: float, value: float | None, color: str, uid: str) -> str:
    percent = "" if value is None else f"{value * 100:.0f}%"
    return f"""
  <g>
    <circle cx="{x:.1f}" cy="{y:.1f}" r="28" fill="{color}" stroke="{PAPER}" stroke-opacity=".28" stroke-width="1"/>
    {_flag_badge(team, x, y, 23, uid)}
    {_text(x, y + 51, percent, size=13, fill=PAPER, weight=900)}
  </g>"""


def render_circular_bracket_svg(
    round32: list[dict[str, Any]],
    *,
    title: str = "FIELCUP 2026",
    subtitle: str = "chance de avanco por jogo",
    size: int = 1600,
) -> str:
    """Render a circular SVG bracket with FielCup advancement percentages."""
    cx = cy = size / 2
    outer_r = size * 0.406
    meet_r = size * 0.297
    winner_r = size * 0.209
    inner_r = size * 0.148
    rotation = 360 / (len(round32) * 2)

    parts = [
        f'<svg class="fielcup-circle-bracket" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="{escape(title)} circular knockout bracket">',
        "<defs>",
        '<radialGradient id="bracketGlow" cx="50%" cy="50%" r="50%">',
        f'<stop offset="0%" stop-color="{GOLD}" stop-opacity=".52"/>',
        f'<stop offset="44%" stop-color="{GOLD}" stop-opacity=".08"/>',
        f'<stop offset="100%" stop-color="{INK}" stop-opacity="0"/>',
        "</radialGradient>",
        '<filter id="paperGrain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 .09"/></feComponentTransfer></filter>',
        "</defs>",
        f'<rect width="{size}" height="{size}" fill="{INK}"/>',
        f'<rect width="{size}" height="{size}" filter="url(#paperGrain)" opacity=".5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{size * .197:.1f}" fill="url(#bracketGlow)"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{inner_r:.1f}" fill="none" stroke="{GOLD}" stroke-opacity=".38" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{winner_r:.1f}" fill="none" stroke="{LINE}" stroke-opacity=".58" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{meet_r:.1f}" fill="none" stroke="{LINE}" stroke-opacity=".28" stroke-width="1.5"/>',
        f'<ellipse cx="{cx}" cy="{cy + 118:.1f}" rx="70" ry="18" fill="#000" opacity=".35"/>',
        f'<path d="M {cx - 42:.1f} {cy - 20:.1f} C {cx - 70:.1f} {cy - 88:.1f}, {cx + 70:.1f} {cy - 88:.1f}, {cx + 42:.1f} {cy - 20:.1f} C {cx + 26:.1f} {cy + 38:.1f}, {cx - 26:.1f} {cy + 38:.1f}, {cx - 42:.1f} {cy - 20:.1f} Z" fill="{GOLD}"/>',
        f'<rect x="{cx - 18:.1f}" y="{cy + 28:.1f}" width="36" height="88" rx="12" fill="{GOLD}"/>',
        f'<path d="M {cx - 52:.1f} {cy + 118:.1f} L {cx + 52:.1f} {cy + 118:.1f} L {cx + 72:.1f} {cy + 154:.1f} L {cx - 72:.1f} {cy + 154:.1f} Z" fill="#d7b34c"/>',
        f'<path d="M {cx - 98:.1f} {cy - 38:.1f} C {cx - 146:.1f} {cy - 10:.1f}, {cx - 116:.1f} {cy + 42:.1f}, {cx - 50:.1f} {cy + 18:.1f}" fill="none" stroke="#d7b34c" stroke-width="18" stroke-linecap="round"/>',
        f'<path d="M {cx + 98:.1f} {cy - 38:.1f} C {cx + 146:.1f} {cy - 10:.1f}, {cx + 116:.1f} {cy + 42:.1f}, {cx + 50:.1f} {cy + 18:.1f}" fill="none" stroke="#d7b34c" stroke-width="18" stroke-linecap="round"/>',
        _text(cx, cy + 214, title, size=30, fill=PAPER, weight=900, extra='letter-spacing="4"'),
        _text(cx, cy + 247, subtitle, size=17, fill="#a59d8e", weight=700, extra='letter-spacing="2"'),
    ]

    projected: list[tuple[str, float, float]] = []
    for index, game in enumerate(round32):
        angle = rotation + index * 360 / len(round32)
        spread = 4.7
        home_x, home_y = _polar(cx, cy, outer_r, angle - spread)
        away_x, away_y = _polar(cx, cy, outer_r, angle + spread)
        meet_x, meet_y = _polar(cx, cy, meet_r, angle)
        win_x, win_y = _polar(cx, cy, winner_r, angle)
        side = 1 if math.cos(math.radians(angle - 90)) >= 0 else -1

        winner = game.get("advancePickTeam") or game.get("home") or game.get("away")
        winner_value = game.get("advancePickValue")
        active_color = RED if winner == "Brazil" else GOLD if (winner_value or 0) >= 0.58 else GREEN
        if winner_value is None:
            active_color = LINE

        home_color = active_color if game.get("home") == winner else LINE
        away_color = active_color if game.get("away") == winner else LINE
        parts.append(
            f'<path d="{_path([(home_x, home_y), (meet_x, meet_y), (win_x, win_y)])}" '
            f'fill="none" stroke="{home_color}" stroke-width="{5 if game.get("home") == winner else 2.2}" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="{.92 if game.get("home") == winner else .48}"/>'
        )
        parts.append(
            f'<path d="{_path([(away_x, away_y), (meet_x, meet_y), (win_x, win_y)])}" '
            f'fill="none" stroke="{away_color}" stroke-width="{5 if game.get("away") == winner else 2.2}" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="{.92 if game.get("away") == winner else .48}"/>'
        )
        parts.append(f'<circle cx="{meet_x:.1f}" cy="{meet_y:.1f}" r="8" fill="{GOLD if winner_value else LINE}" opacity=".9"/>')
        parts.append(f'<circle cx="{win_x:.1f}" cy="{win_y:.1f}" r="6" fill="{active_color}" opacity=".9"/>')
        parts.append(_text(meet_x, meet_y - 18, f"M{game['match']}", size=12, fill=MUTED, weight=900))
        slug = _slug(f"{game['match']}-{game.get('home') or 'tbd'}")
        parts.append(_team_node(game, "home", home_x, home_y, selected=(game.get("home") == winner), side=side, uid=f"{slug}-home"))
        slug = _slug(f"{game['match']}-{game.get('away') or 'tbd'}")
        parts.append(_team_node(game, "away", away_x, away_y, selected=(game.get("away") == winner), side=side, uid=f"{slug}-away"))
        parts.append(_winner_node(winner, win_x, win_y, winner_value, active_color, f"winner-{game['match']}"))
        if winner and winner_value is not None:
            projected.append((winner, winner_value, angle))

    projected.sort(key=lambda row: row[1], reverse=True)
    for team, value, angle in projected[:4]:
        win_x, win_y = _polar(cx, cy, winner_r, angle)
        inner_x, inner_y = _polar(cx, cy, inner_r, angle)
        color = RED if team == "Brazil" else GOLD
        parts.append(
            f'<path d="{_path([(win_x, win_y), (inner_x, inner_y), (cx, cy)])}" '
            f'fill="none" stroke="{color}" stroke-width="{4 if team == "Brazil" else 2.4}" '
            f'stroke-linecap="round" opacity=".44"/>'
        )
        parts.append(_text(inner_x, inner_y - 10, nm(team).upper(), size=12, fill=color, weight=900))
        parts.append(_text(inner_x, inner_y + 8, f"{value * 100:.0f}%", size=12, fill=PAPER, weight=900))

    parts.append(_text(70, 74, "FIELCUP", size=36, fill=PAPER, weight=900, anchor="start", extra='letter-spacing="4"'))
    parts.append(_text(70, 108, "CIRCULAR KNOCKOUT MODEL", size=16, fill=RED, weight=900, anchor="start", extra='letter-spacing="3"'))
    parts.append(
        _text(
            70,
            size - 58,
            "Bandeiras desenhadas em SVG. Percentuais: chance de avanco no confronto.",
            size=15,
            fill=MUTED,
            weight=700,
            anchor="start",
        )
    )
    parts.append("</svg>")
    return "\n".join(parts)
