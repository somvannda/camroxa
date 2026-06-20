def _fmt_time(sec: float) -> str:
    s = max(0.0, float(sec))
    mm = int(s // 60)
    ss = int(s % 60)
    return f'{mm:02d}:{ss:02d}'

def _get_anchor_coords(anchor: str, offset_x: float, offset_y: float, w: int, h: int) -> tuple[float, float]:
    a = str(anchor).lower().strip()
    if 'left' in a:
        cx = 0.0
    elif 'right' in a:
        cx = float(w)
    else:
        cx = float(w) * 0.5
    if 'top' in a:
        cy = float(h)
    elif 'bottom' in a:
        cy = 0.0
    else:
        cy = float(h) * 0.5
    return (cx + float(offset_x), cy - float(offset_y))

def _smooth_env(prev: float, target: float, smoothing: float) -> float:
    s = float(max(0.0, min(0.99, smoothing)))
    t = float(max(0.0, min(1.0, target)))
    return float(float(prev) * s + t * (1.0 - s))
