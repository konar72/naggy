# common/motivators.py
import csv, os, random
from typing import Dict, List, Optional

# {category: {tone: [template, ...]}}
_MOTIVATORS: Dict[str, Dict[str, List[str]]] = {}

def _load_csv_once() -> None:
    if _MOTIVATORS:
        return
    here = os.path.dirname(__file__)
    path = os.path.join(here, "motivators.csv")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row["category"].strip().lower()
            tone = row["tone"].strip().lower()
            tpl = row["template"].strip()
            _MOTIVATORS.setdefault(cat, {}).setdefault(tone, []).append(tpl)

def _weighted_tone_choice(tone_weights: Dict[str, float], available: List[str]) -> str:
    if not available:
        raise ValueError("No tones available.")
    weights = [max(0.0, float(tone_weights.get(t, 0.0))) for t in available] if tone_weights else [0.0]*len(available)
    total = sum(weights)
    if total <= 1e-12:
        return random.choice(available)
    x, acc = random.random() * total, 0.0
    for t, w in zip(available, weights):
        acc += w
        if x <= acc:
            return t
    return available[-1]

def pick_motivator_by_category(category: Optional[str],
                               tone_weights: Optional[Dict[str, float]]) -> Optional[str]:
    """
    category: e.g. 'text', 'task', etc. If None/empty → return None (no motivator).
    tone_weights: {"gentle":0.7,"medium":0.3} or None.

    Returns a template string or None if not found.
    """
    _load_csv_once()
    if not category:
        return None
    cat = category.strip().lower()
    by_tone = _MOTIVATORS.get(cat)
    if not by_tone:
        return None

    tones = list(by_tone.keys())
    chosen = _weighted_tone_choice(tone_weights or {}, tones)
    pool = by_tone.get(chosen) or []
    if pool:
        return random.choice(pool)

    # fallback if chosen tone bucket empty
    all_pool = [tpl for arr in by_tone.values() for tpl in arr]
    return random.choice(all_pool) if all_pool else None
