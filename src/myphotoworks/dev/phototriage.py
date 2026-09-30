"""Convert pairwise preference records (Photo Triage style) into schema-1 labels."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable


def pairs_to_labels(
    records: Iterable[tuple[str, str, str]], root: str = "", source: str = "phototriage"
) -> dict:
    """``records`` are (series_id, winner_file, loser_file).

    Per series the most-preferred photos (max wins) become ``picked``; ties keep every
    top photo. The raw pairs are kept for pair-accuracy scoring. Series with a single
    photo are dropped.
    """
    files: dict[str, list[str]] = {}
    wins: dict[str, Counter] = {}
    pairs: dict[str, list[list[str]]] = {}
    for sid, winner, loser in records:
        order = files.setdefault(sid, [])
        for f in (winner, loser):
            if f not in order:
                order.append(f)
        wins.setdefault(sid, Counter())[winner] += 1
        pairs.setdefault(sid, []).append([winner, loser])
    groups = []
    for gid, (sid, order) in enumerate(files.items()):
        if len(order) < 2:
            continue
        top = max(wins[sid][f] for f in order)
        groups.append({
            "id": gid,
            "series": sid,
            "files": order,
            "picked": [f for f in order if wins[sid][f] == top],
            "pairs": pairs[sid],
            "reviewed": True,
        })
    return {"schema": 1, "source": source, "root": root, "groups": groups}
