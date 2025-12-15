#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import dataclasses
import heapq
import pathlib
import re
from typing import Any, Literal

import yaml


@dataclasses.dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h


Side = Literal["left", "right", "top", "bottom"]


def _round_svg(v: float) -> int:
    return int(round(v))


def _anchor(rect: Rect, side: Side) -> tuple[float, float]:
    if side == "left":
        return (rect.left, rect.cy)
    if side == "right":
        return (rect.right, rect.cy)
    if side == "top":
        return (rect.cx, rect.top)
    if side == "bottom":
        return (rect.cx, rect.bottom)
    raise ValueError(f"unknown side: {side}")


def _pick_sides(src: Rect, dst: Rect) -> tuple[Side, Side]:
    dx = dst.cx - src.cx
    dy = dst.cy - src.cy
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def _orthogonal_path(
    src: Rect,
    dst: Rect,
    margin: float = 14.0,
) -> str:
    src_side, dst_side = _pick_sides(src, dst)
    sx, sy = _anchor(src, src_side)
    ex, ey = _anchor(dst, dst_side)

    points: list[tuple[float, float]] = [(sx, sy)]

    if src_side in ("left", "right") and dst_side in ("left", "right"):
        if _round_svg(sy) == _round_svg(ey):
            points.append((ex, ey))
        else:
            if dst_side == "left":
                mid_x = min(ex - margin, (sx + ex) / 2)
            else:
                mid_x = max(ex + margin, (sx + ex) / 2)
            points.extend([(mid_x, sy), (mid_x, ey), (ex, ey)])
    elif src_side in ("top", "bottom") and dst_side in ("top", "bottom"):
        if _round_svg(sx) == _round_svg(ex):
            points.append((ex, ey))
        else:
            if dst_side == "top":
                mid_y = min(ey - margin, (sy + ey) / 2)
            else:
                mid_y = max(ey + margin, (sy + ey) / 2)
            points.extend([(sx, mid_y), (ex, mid_y), (ex, ey)])
    else:
        if src_side in ("left", "right"):
            points.extend([(ex, sy), (ex, ey)])
        else:
            points.extend([(sx, ey), (ex, ey)])

    d_parts: list[str] = [f"M{_round_svg(points[0][0])} {_round_svg(points[0][1])}"]
    for x, y in points[1:]:
        d_parts.append(f"L{_round_svg(x)} {_round_svg(y)}")
    return " ".join(d_parts)


def _expand(rect: Rect, pad: float) -> Rect:
    return Rect(rect.x - pad, rect.y - pad, rect.w + pad * 2, rect.h + pad * 2)


def _segment_clear(
    a: tuple[float, float],
    b: tuple[float, float],
    obstacles: list[Rect],
) -> bool:
    x1, y1 = a
    x2, y2 = b
    if x1 != x2 and y1 != y2:
        return False
    if x1 == x2:
        x = x1
        y_lo, y_hi = (y1, y2) if y1 <= y2 else (y2, y1)
        for r in obstacles:
            if not (r.left < x < r.right):
                continue
            # Strict overlap so running along border is allowed.
            if max(y_lo, r.top) < min(y_hi, r.bottom):
                return False
        return True
    y = y1
    x_lo, x_hi = (x1, x2) if x1 <= x2 else (x2, x1)
    for r in obstacles:
        if not (r.top < y < r.bottom):
            continue
        if max(x_lo, r.left) < min(x_hi, r.right):
            return False
    return True


def _manhattan(a: tuple[float, float], b: tuple[float, float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _a_star(
    start: tuple[float, float],
    goal: tuple[float, float],
    nodes: list[tuple[float, float]],
    edges: dict[tuple[float, float], list[tuple[float, float]]],
) -> list[tuple[float, float]] | None:
    open_heap: list[tuple[float, tuple[float, float]]] = []
    heapq.heappush(open_heap, (_manhattan(start, goal), start))
    came_from: dict[tuple[float, float], tuple[float, float]] = {}
    g_score: dict[tuple[float, float], float] = {start: 0.0}
    in_open: set[tuple[float, float]] = {start}

    while open_heap:
        _, current = heapq.heappop(open_heap)
        in_open.discard(current)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for nxt in edges.get(current, []):
            tentative = g_score[current] + _manhattan(current, nxt)
            if tentative < g_score.get(nxt, float("inf")):
                came_from[nxt] = current
                g_score[nxt] = tentative
                if nxt not in in_open:
                    heapq.heappush(open_heap, (tentative + _manhattan(nxt, goal), nxt))
                    in_open.add(nxt)
    return None


def _compress_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    out = [points[0]]
    for i in range(1, len(points) - 1):
        x0, y0 = out[-1]
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if (x0 == x1 == x2) or (y0 == y1 == y2):
            continue
        out.append((x1, y1))
    out.append(points[-1])
    return out


def _route_avoiding_tables(
    src_rect: Rect,
    dst_rect: Rect,
    all_table_rects: dict[str, Rect],
    src_id: str,
    dst_id: str,
    pad: float = 8.0,
    margin: float = 14.0,
) -> str:
    src_side, dst_side = _pick_sides(src_rect, dst_rect)
    start = _anchor(src_rect, src_side)
    goal = _anchor(dst_rect, dst_side)

    # Expand obstacles slightly so we don't graze through boxes.
    obstacles: list[Rect] = []
    for tid, r in all_table_rects.items():
        if tid in (src_id, dst_id):
            continue
        obstacles.append(_expand(r, pad))

    # Candidate grid lines: obstacle edges +/- margin plus endpoints.
    xs: set[float] = {start[0], goal[0]}
    ys: set[float] = {start[1], goal[1]}
    for r in obstacles:
        xs.update([r.left - margin, r.left, r.right, r.right + margin])
        ys.update([r.top - margin, r.top, r.bottom, r.bottom + margin])

    # Also include all table edges so we can route between columns/rows cleanly.
    for r in all_table_rects.values():
        xs.update([r.left, r.right])
        ys.update([r.top, r.bottom])

    xs_list = sorted(xs)
    ys_list = sorted(ys)

    def blocked(x: float, y: float) -> bool:
        for r in obstacles:
            if r.left < x < r.right and r.top < y < r.bottom:
                return True
        return False

    nodes: list[tuple[float, float]] = []
    for x in xs_list:
        for y in ys_list:
            if not blocked(x, y):
                nodes.append((x, y))

    node_set = set(nodes)
    node_set.add(start)
    node_set.add(goal)

    # Build adjacency via nearest neighbors along x/y (visibility graph on grid).
    edges: dict[tuple[float, float], list[tuple[float, float]]] = {n: [] for n in node_set}

    by_x: dict[float, list[tuple[float, float]]] = {}
    by_y: dict[float, list[tuple[float, float]]] = {}
    for x, y in node_set:
        by_x.setdefault(x, []).append((x, y))
        by_y.setdefault(y, []).append((x, y))

    for x, pts in by_x.items():
        pts.sort(key=lambda p: p[1])
        for a, b in zip(pts, pts[1:]):
            if _segment_clear(a, b, obstacles):
                edges[a].append(b)
                edges[b].append(a)

    for y, pts in by_y.items():
        pts.sort(key=lambda p: p[0])
        for a, b in zip(pts, pts[1:]):
            if _segment_clear(a, b, obstacles):
                edges[a].append(b)
                edges[b].append(a)

    path = _a_star(start, goal, nodes, edges)
    if not path:
        return _orthogonal_path(src_rect, dst_rect, margin=margin)

    path = _compress_collinear(path)
    d_parts: list[str] = [f"M{_round_svg(path[0][0])} {_round_svg(path[0][1])}"]
    for x, y in path[1:]:
        d_parts.append(f"L{_round_svg(x)} {_round_svg(y)}")
    return " ".join(d_parts)


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _computed_table_rects(model: dict[str, Any]) -> dict[str, Rect]:
    computed = model.get("computed")
    if not isinstance(computed, dict):
        raise ValueError("missing computed")
    tables = computed.get("tables")
    if not isinstance(tables, list):
        raise ValueError("missing computed.tables")

    rects: dict[str, Rect] = {}
    for t in tables:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not isinstance(tid, str):
            continue
        rects[tid] = Rect(
            x=float(t["x"]),
            y=float(t["y"]),
            w=float(t["w"]),
            h=float(t["h"]),
        )
    return rects


def _table_name_map(model: dict[str, Any]) -> dict[str, str]:
    tables = model.get("tables")
    if not isinstance(tables, list):
        return {}
    out: dict[str, str] = {}
    for t in tables:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        name = t.get("name")
        if isinstance(tid, str) and isinstance(name, str):
            out[tid] = name
    return out


def _relations(model: dict[str, Any]) -> list[tuple[str, str]]:
    rels = model.get("relations")
    if not isinstance(rels, list):
        raise ValueError("missing relations")
    out: list[tuple[str, str]] = []
    for r in rels:
        if not isinstance(r, dict):
            continue
        f = r.get("from")
        t = r.get("to")
        if isinstance(f, str) and isinstance(t, str):
            out.append((f, t))
    return out


def _render_paths_block(
    rels: list[tuple[str, str]],
    rects: dict[str, Rect],
    names: dict[str, str],
) -> str:
    lines: list[str] = ["  paths:"]
    for f, t in rels:
        src = rects.get(f)
        dst = rects.get(t)
        if src is None or dst is None:
            raise ValueError(f"missing computed.tables for relation: {f} -> {t}")
        d = _route_avoiding_tables(src, dst, rects, f, t)
        from_label = names.get(f, f)
        to_label = names.get(t, t)
        lines.append(f"    # {from_label} -> {to_label}")
        lines.append(f"    - d: {d}")
    return "\n".join(lines) + "\n"


def _replace_computed_paths_section(original: str, new_block: str) -> str:
    pattern = re.compile(r"(?ms)^\s{2}paths:\n(?:^\s{4}.*\n)*")
    match = pattern.search(original)
    if not match:
        raise ValueError("could not find '  paths:' section under computed")
    return original[: match.start()] + new_block + original[match.end() :]


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    yml_path = root / "データモデル.yml"
    model = _load_yaml(yml_path)
    rects = _computed_table_rects(model)
    names = _table_name_map(model)
    rels = _relations(model)

    new_paths_block = _render_paths_block(rels, rects, names)

    original = yml_path.read_text(encoding="utf-8")
    updated = _replace_computed_paths_section(original, new_paths_block)
    if updated != original:
        yml_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
