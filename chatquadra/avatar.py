"""Simple expressive SVG faces for the 16 personas.

`render_avatar(code, expression)` renders one expression; `avatar_img` wraps it as an
<img> for Streamlit. Without `expression`, the SVG holds every expression and a
`data-expr` attribute on the SVG picks which one shows.
"""

from __future__ import annotations

import base64

from .personas import get_persona

INK = "#23253A"
BLUSH = "#F08A96"

GROUP_TINTS = {"NT": "#ECEBFC", "NF": "#FBE6EE", "SJ": "#E1F2EF", "SP": "#FCF0DC"}

# skin, hair style, hair colour, glasses
LOOKS: dict[str, tuple[str, str, str, bool]] = {
    "INTJ": ("#A86F4C", "crop", "#1E1A18", True),
    "INTP": ("#C68E6A", "long", "#3B2A20", True),
    "ENTJ": ("#F1C9A5", "bob", "#D9B26A", False),
    "ENTP": ("#D7A47E", "curly", "#2E2018", False),
    "INFJ": ("#A0694A", "bun", "#241B1B", False),
    "INFP": ("#F3D2B5", "bob", "#8E3B2E", False),
    "ENFJ": ("#6B4430", "buzz", "#1A1414", False),
    "ENFP": ("#F2C7A6", "curly", "#C8642F", False),
    "ISTJ": ("#EBC3A0", "sidepart", "#8C8C88", True),
    "ISFJ": ("#B5785A", "long", "#2A1C18", False),
    "ESTJ": ("#E3B48E", "bob", "#5A3A28", False),
    "ESFJ": ("#C9875F", "curly", "#3A2416", False),
    "ISTP": ("#D9A882", "crop", "#2B2B2B", False),
    "ISFP": ("#F5D6BE", "bun", "#B98A5A", False),
    "ESTP": ("#E8BA92", "sidepart", "#C9A15A", False),
    "ESFP": ("#8A5A3C", "long", "#5B2340", False),
}

# Hair drawn behind the head, and in front of it.
HAIR_BACK = {
    "long": "M46 90 C44 44 76 30 100 30 C126 30 156 44 154 90 L156 162 C140 170 60 170 44 162 Z",
    "bob": "M48 92 C44 46 76 32 100 32 C124 32 156 46 152 92 L150 136 C140 142 128 140 124 134 L124 104 L76 104 L76 134 C72 140 60 142 50 136 Z",
    "bun": "M100 12 a17 17 0 1 0 0.1 0 Z",
}
HAIR_FRONT = {
    "crop": "M52 88 C50 50 78 34 100 34 C124 34 152 48 148 88 C140 66 120 56 100 56 C80 56 60 66 52 88 Z",
    "long": "M52 86 C54 52 80 38 100 38 C120 38 146 52 148 86 C134 64 116 58 100 60 C86 62 66 68 52 86 Z",
    "bob": "M54 84 C58 52 80 40 100 40 C120 40 142 52 146 84 C130 70 112 62 92 66 C76 68 62 74 54 84 Z",
    "bun": "M53 84 C56 52 80 40 100 40 C120 40 144 52 147 84 C134 64 116 56 100 56 C84 56 66 64 53 84 Z",
    "sidepart": "M52 90 C48 52 74 34 104 34 C130 36 152 54 148 90 C146 70 136 58 122 54 C104 62 76 58 52 90 Z",
    "buzz": "M55 78 C60 50 80 41 100 41 C120 41 140 50 145 78 C132 62 116 57 100 57 C84 57 68 62 55 78 Z",
}
CURLS = [(58, 74, 15), (68, 55, 16), (86, 43, 16), (106, 40, 16), (125, 46, 16), (139, 62, 15), (146, 80, 11), (54, 86, 11)]

_EYES_OPEN = '<ellipse class="eye" cx="82" cy="98" rx="4.6" ry="5.6"/><ellipse class="eye" cx="118" cy="98" rx="4.6" ry="5.6"/>'
_EYES_UP = '<ellipse class="eye" cx="84" cy="96" rx="4.6" ry="5.6"/><ellipse class="eye" cx="120" cy="96" rx="4.6" ry="5.6"/>'
_EYES_HAPPY = (
    f'<path d="M77 99 Q82 93 87 99" stroke="{INK}" stroke-width="3" fill="none" stroke-linecap="round"/>'
    f'<path d="M113 99 Q118 93 123 99" stroke="{INK}" stroke-width="3" fill="none" stroke-linecap="round"/>'
)
_CHEEKS = f'<ellipse cx="72" cy="114" rx="8" ry="5" fill="{BLUSH}" opacity=".45"/><ellipse cx="128" cy="114" rx="8" ry="5" fill="{BLUSH}" opacity=".45"/>'

# expression -> (eyes, left brow, right brow, mouth, mouth is filled, cheeks)
EXPRESSIONS: dict[str, tuple[str, str, str, str, bool, bool]] = {
    "neutral": (_EYES_OPEN, "M72 83 Q82 80 92 83", "M108 83 Q118 80 128 83", "M90 125 Q100 128 110 125", False, False),
    "smile": (_EYES_OPEN, "M72 81 Q82 77 92 81", "M108 81 Q118 77 128 81", "M86 121 Q100 134 114 121", False, True),
    "grin": (_EYES_HAPPY, "M72 79 Q82 74 92 79", "M108 79 Q118 74 128 79", "M84 119 Q100 143 116 119 Q100 125 84 119 Z", True, True),
    "thinking": (_EYES_UP, "M72 79 Q82 74 92 80", "M108 84 Q118 82 128 84", "M93 125 Q102 122 110 126", False, False),
    "skeptic": (_EYES_OPEN, "M72 78 Q82 73 92 80", "M108 85 Q118 83 128 85", "M90 125 L110 124", False, False),
    "concern": (_EYES_OPEN, "M72 84 Q82 81 92 78", "M108 78 Q118 81 128 84", "M90 128 Q100 122 110 128", False, False),
    "stern": (_EYES_OPEN, "M72 79 Q82 81 92 86", "M108 86 Q118 81 128 79", "M90 126 L110 126", False, False),
    "smirk": (_EYES_OPEN, "M72 82 Q82 79 92 82", "M108 80 Q118 76 128 81", "M88 125 Q102 129 114 119", False, False),
    "blush": (_EYES_HAPPY, "M72 82 Q82 79 92 82", "M108 82 Q118 79 128 82", "M90 123 Q100 129 110 123", False, True),
}

EMOTION_TO_EXPRESSION = {
    "neutral": "neutral", "warm": "smile", "happy": "smile", "excited": "grin", "amused": "grin",
    "playful": "smirk", "curious": "thinking", "thoughtful": "thinking", "empathetic": "concern",
    "concerned": "concern", "serious": "stern", "skeptical": "skeptic", "confident": "smirk",
    "annoyed": "stern", "sad": "concern", "embarrassed": "blush",
}


def expression_for(emotion: str | None) -> str:
    return EMOTION_TO_EXPRESSION.get(emotion or "neutral", "neutral")


def avatar_img(
    code: str, expression: str, size: int, alt: str, typing: bool = False, blink_delay: float = 0.0
) -> str:
    """The face as an <img> data URI, for hosts that strip inline SVG (e.g. Streamlit's st.html)."""
    svg = render_avatar(code, expression, size=size, title=alt, typing=typing, blink_delay=blink_delay)
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{data}" width="{size}" height="{size}" alt="{alt}">'


def _expression_group(name: str) -> str:
    eyes, brow_l, brow_r, mouth, filled, cheeks = EXPRESSIONS[name]
    mouth_svg = (
        f'<path d="{mouth}" fill="{INK}"/>'
        if filled
        else f'<path d="{mouth}" stroke="{INK}" stroke-width="3.2" fill="none" stroke-linecap="round"/>'
    )
    return (
        f'<g class="expr expr-{name}">'
        f"{_CHEEKS if cheeks else ''}"
        f'<g class="eyes" fill="{INK}">{eyes}</g>'
        f'<path d="{brow_l}" stroke="{INK}" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
        f'<path d="{brow_r}" stroke="{INK}" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
        f"{mouth_svg}</g>"
    )


_ANIMATION_CSS = (
    ".eye{transform-box:fill-box;transform-origin:center;animation:cqblink 5.5s infinite}"
    "@keyframes cqblink{0%,95%,100%{transform:scaleY(1)}97%{transform:scaleY(.1)}}"
    ".cq-typing .head{transform:translateY(3px) rotate(-2deg);transform-origin:100px 140px}"
    "@media (prefers-reduced-motion:reduce){.eye{animation:none}}"
)


def _style_block(all_expressions: bool, blink_delay: float = 0.0) -> str:
    css = _ANIMATION_CSS
    if blink_delay:
        # A negative delay starts mid-cycle, so faces shown together don't blink in unison.
        css += f".eye{{animation-delay:-{blink_delay:.2f}s}}"
    if all_expressions:
        css += ".cq-face .expr{display:none}" + "".join(
            f'.cq-face[data-expr="{n}"] .expr-{n}{{display:inline}}' for n in EXPRESSIONS
        )
    return f"<style>{css}</style>"


def render_avatar(
    code: str,
    expression: str | None = None,
    size: int = 160,
    title: str | None = None,
    typing: bool = False,
    blink_delay: float = 0.0,
) -> str:
    persona = get_persona(code)
    skin, style, hair, glasses = LOOKS[persona.code]
    tint = GROUP_TINTS[persona.group]
    label = title or f"{persona.name}'s face"

    parts = [f'<circle cx="100" cy="100" r="100" fill="{tint}"/>']
    # shoulders
    parts.append(f'<path d="M40 200 C44 160 70 146 100 146 C130 146 156 160 160 200 Z" fill="{persona.color}"/>')
    parts.append(f'<rect x="88" y="134" width="24" height="20" rx="8" fill="{skin}"/>')
    parts.append('<g class="head">')
    if style in HAIR_BACK:
        parts.append(f'<path d="{HAIR_BACK[style]}" fill="{hair}"/>')
    parts.append(f'<ellipse cx="53" cy="100" rx="7" ry="10" fill="{skin}"/><ellipse cx="147" cy="100" rx="7" ry="10" fill="{skin}"/>')
    parts.append(f'<ellipse cx="100" cy="94" rx="48" ry="54" fill="{skin}"/>')
    if style == "curly":
        parts.extend(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{hair}"/>' for x, y, r in CURLS)
    elif style in HAIR_FRONT:
        parts.append(f'<path d="{HAIR_FRONT[style]}" fill="{hair}"/>')
    names = [expression] if expression else list(EXPRESSIONS)
    parts.append('<g class="face-features">')
    parts.extend(_expression_group(n) for n in names)
    parts.append("</g>")
    if glasses:
        parts.append(
            f'<g fill="none" stroke="{INK}" stroke-width="2.4"><rect x="69" y="87" width="26" height="21" rx="8"/>'
            f'<rect x="105" y="87" width="26" height="21" rx="8"/><path d="M95 96 Q100 93 105 96"/></g>'
        )
    parts.append("</g>")

    classes = "cq-face cq-typing" if typing else "cq-face"
    return (
        f'<svg class="{classes}" viewBox="0 0 200 200" width="{size}" height="{size}" '
        f'data-expr="{expression or "neutral"}" '
        f'role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">'
        f"{_style_block(all_expressions=expression is None, blink_delay=blink_delay)}"
        f'<defs><clipPath id="cq-clip-{persona.code}"><circle cx="100" cy="100" r="100"/></clipPath></defs>'
        f'<g clip-path="url(#cq-clip-{persona.code})">{"".join(parts)}</g></svg>'
    )
