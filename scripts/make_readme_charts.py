"""Render README charts (light and dark SVG) from the committed 2026 backtest summary.

uv run python scripts/make_readme_charts.py
"""

import json
from pathlib import Path

SUMMARY = Path('reports/backtest-2026/summary.json')
OUT = Path('docs/img')
THEMES = {
    'light': {
        'surface': '#fcfcfb',
        'ink': '#0b0b0b',
        'ink2': '#52514e',
        'muted': '#898781',
        'grid': '#e1e0d9',
        'axis': '#c3c2b7',
        'series': '#2a78d6',
    },
    'dark': {
        'surface': '#1a1a19',
        'ink': '#ffffff',
        'ink2': '#c3c2b7',
        'muted': '#898781',
        'grid': '#2c2c2a',
        'axis': '#383835',
        'series': '#3987e5',
    },
}
FONT = "font-family='-apple-system, Segoe UI, Helvetica, Arial, sans-serif'"


def bar_top(x, y, width, base):
    """Bar path with 4px rounded data-end and square baseline."""
    r = min(4, width / 2, base - y)
    return (
        f'M{x:.1f},{base:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
        f'H{x + width - r:.1f} Q{x + width:.1f},{y:.1f} {x + width:.1f},{y + r:.1f} V{base:.1f} Z'
    )


def hits_chart(summary, t):
    races = summary['per_race']
    mean = summary['top10_hits_mean']['B1']
    w, h, left, right, top, bottom = 720, 300, 44, 16, 52, 40
    plot_w, plot_h = w - left - right, h - top - bottom
    base = top + plot_h
    step = plot_w / len(races)
    bar_w = step - 2  # 2px surface gap between adjacent bars

    def y(v):
        return top + plot_h * (1 - v / 10)

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' role='img' "
        f"aria-label='Correct points scorers among the ten most likely drivers, per 2026 race'>",
        f"<rect width='{w}' height='{h}' rx='8' fill='{t['surface']}'/>",
        f"<text x='{left}' y='22' {FONT} font-size='15' font-weight='600' fill='{t['ink']}'>"
        'Correct points scorers in the top-10 picks, 2026 rounds 1–16</text>',
        f"<text x='{left}' y='40' {FONT} font-size='12' fill='{t['ink2']}'>"
        'Walk-forward backtest: each race predicted from qualifying only, model refit on earlier races</text>',
    ]
    for v in (0, 5, 10):
        parts.append(
            f"<line x1='{left}' x2='{w - right}' y1='{y(v):.1f}' y2='{y(v):.1f}' "
            f"stroke='{t['axis'] if v == 0 else t['grid']}' stroke-width='1'/>"
        )
        parts.append(
            f"<text x='{left - 8}' y='{y(v) + 4:.1f}' {FONT} font-size='11' fill='{t['muted']}' "
            f"text-anchor='end'>{v}</text>"
        )
    for i, race in enumerate(races):
        x = left + i * step + 1
        hits = race['top10_hits_B1']
        parts.append(
            f"<path d='{bar_top(x, y(hits), bar_w, base)}' fill='{t['series']}'>"
            f'<title>{race["event_id"]}: {hits} of 10</title></path>'
        )
        parts.append(
            f"<text x='{x + bar_w / 2:.1f}' y='{base + 16}' {FONT} font-size='11' fill='{t['muted']}' "
            f"text-anchor='middle'>R{race['round']}</text>"
        )
    parts.append(
        f"<line x1='{left}' x2='{w - right}' y1='{y(mean):.1f}' y2='{y(mean):.1f}' stroke='{t['ink']}' "
        "stroke-width='1.5' stroke-dasharray='4 4'/>"
    )
    parts.append(
        f"<text x='{w - right - 4}' y='{y(mean) - 6:.1f}' {FONT} font-size='12' font-weight='600' "
        f"fill='{t['ink']}' text-anchor='end'>mean {mean:.1f} / 10</text>"
    )
    parts.append('</svg>')
    return '\n'.join(parts)


def calibration_chart(summary, t):
    bins = summary['reliability_B1']
    w, h, left, right, top, bottom = 360, 360, 48, 20, 52, 44
    size = min(w - left - right, h - top - bottom)

    def px(v):
        return left + size * v

    def py(v):
        return top + size * (1 - v)

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' role='img' "
        "aria-label='Calibration: predicted chance versus how often drivers actually scored'>",
        f"<rect width='{w}' height='{h}' rx='8' fill='{t['surface']}'/>",
        f"<text x='{left}' y='22' {FONT} font-size='15' font-weight='600' fill='{t['ink']}'>"
        'Do the percentages hold up?</text>',
        f"<text x='{left}' y='40' {FONT} font-size='12' fill='{t['ink2']}'>"
        '2026 backtest, qualifying-rank model, 10% bins</text>',
    ]
    for v in (0, 0.5, 1):
        parts.append(
            f"<line x1='{px(0)}' x2='{px(1)}' y1='{py(v)}' y2='{py(v)}' stroke='{t['axis'] if v == 0 else t['grid']}'/>"
        )
        parts.append(
            f"<text x='{left - 8}' y='{py(v) + 4}' {FONT} font-size='11' fill='{t['muted']}' "
            f"text-anchor='end'>{int(v * 100)}%</text>"
        )
        parts.append(
            f"<text x='{px(v)}' y='{top + size + 16}' {FONT} font-size='11' fill='{t['muted']}' "
            f"text-anchor='middle'>{int(v * 100)}%</text>"
        )
    parts.append(
        f"<line x1='{px(0)}' y1='{py(0)}' x2='{px(1)}' y2='{py(1)}' stroke='{t['muted']}' "
        "stroke-width='1.5' stroke-dasharray='4 4'/>"
    )
    parts.append(
        f"<text x='{px(0.98)}' y='{py(0.4)}' {FONT} font-size='11' fill='{t['ink2']}' text-anchor='end'>"
        'dashed line = perfect</text>'
    )
    for b in bins:
        parts.append(
            f"<circle cx='{px(b['mean_predicted']):.1f}' cy='{py(b['observed_rate']):.1f}' r='5' "
            f"fill='{t['series']}' stroke='{t['surface']}' stroke-width='2'>"
            f'<title>predicted {b["mean_predicted"]:.0%}, scored {b["observed_rate"]:.0%} '
            f'({int(b["count"])} drivers)</title></circle>'
        )
    parts.append(
        f"<text x='{px(0.5)}' y='{h - 8}' {FONT} font-size='12' fill='{t['ink2']}' "
        "text-anchor='middle'>predicted chance of points</text>"
    )
    parts.append(
        f"<text transform='translate(14 {py(0.5)}) rotate(-90)' {FONT} font-size='12' "
        f"fill='{t['ink2']}' text-anchor='middle'>actually scored</text>"
    )
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    summary = json.loads(SUMMARY.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f'backtest-hits-{name}.svg').write_text(hits_chart(summary, theme) + '\n')
        (OUT / f'calibration-{name}.svg').write_text(calibration_chart(summary, theme) + '\n')


if __name__ == '__main__':
    main()
