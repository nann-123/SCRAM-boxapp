"""组成档网格：解析内核落盘的 `INIT/fractions.txt`，给出每档的代表组成与混合度。

背景（2026-09-30）：绘图里原先的"混合分数"口径是**距本次运行 t=0 初始档的偏移**
（未混合档 = t=0 有质量的档），对内混放置类运行会反向误导（t=0 读 0，物理上应为"全混合"）。
内核在初始化时把每档的组成**区间**写到 `INIT/fractions.txt`：
N_fracmax 档 × N_groups 组、每组一行 `[下界, 上界]`；最后一组是占位 (0,1)，
其份额由其余组余额决定（前 N_groups−1 组才是被离散化的）。

本模块是"档 → 代表组成 → 混合度"的唯一来源，口径如下：

- **代表组成**：从各组下界出发，把 `1 − Σ下界` 按各组剩余容量 `(上界 − 下界)` 比例填充。
  保证 Σ=1 且逐组落在自己的区间内。（内核自己也取过"档中心"，但用的是
  `0.5*(下界+上界)`——该向量经常不满足 Σ=1（如某档中点之和 1.2），只是软目标里的代理量，
  不能直接当组成用；见 `ModuleCoeffRepartitionBoxmodel.f90:1107-1114`。）
- **每档混合度** `m = 1 − max(代表组成)`：单一成分档 → 小，成分均衡 → 大，
  取值上限 `1 − 1/N_groups`。
- **不确定度**：`m` 的区间为 `[1 − min(1, max 上界), 1 − max 下界]`，取半宽作 ±。
  这是档级分辨率的诚实代价（区间越宽、读数越不确定）。
- **适用边界**：刻度依赖离散化（N_frac 与边界），**只在同一网格内可比**；
  兜底档（如"其余组全低、最后一组不限"）同时容纳"纯"与"均匀"，任何档级指标都只能取折中。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "parse_fractions",
    "expand_intervals",
    "representative",
    "mixing_degree",
    "mixing_degree_uncertainty",
    "build_grid_map",
]


def parse_fractions(path: str | Path, n_groups: int) -> list[list[tuple[float, float]]]:
    """读 `fractions.txt`：每 n_groups 行组成一档，每行 = 该组的 [下界, 上界]。"""
    pairs: list[tuple[float, float]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            pairs.append((float(parts[0]), float(parts[1])))
    if n_groups <= 0:
        raise ValueError(f"n_groups 必须为正，得到 {n_groups}")
    if len(pairs) == 0 or len(pairs) % n_groups != 0:
        raise ValueError(f"fractions.txt 行数 {len(pairs)} 不是组数 {n_groups} 的整数倍")
    return [list(pairs[start:start + n_groups]) for start in range(0, len(pairs), n_groups)]


def expand_intervals(intervals: list[tuple[float, float]]) -> list[list[float]]:
    """把最后一组的占位区间 (0,1) 换成由其余组推得的真实区间 [1−Σ上界, 1−Σ下界]。"""
    out = [[float(lo), float(hi)] for lo, hi in intervals]
    if len(out) >= 2:
        others = out[:-1]
        lo = max(0.0, 1.0 - sum(item[1] for item in others))
        hi = max(0.0, 1.0 - sum(item[0] for item in others))
        out[-1] = [lo, max(hi, lo)]
    return out


def representative(intervals: list[list[float]]) -> list[float]:
    """从下界出发按剩余容量比例填充，得到 Σ=1 且落在各区间内的代表组成。"""
    lo = [item[0] for item in intervals]
    hi = [item[1] for item in intervals]
    base = sum(lo)
    capacity = sum(high - low for low, high in zip(lo, hi))
    remaining = max(0.0, 1.0 - base)
    if capacity <= 1e-12:
        total = base if base > 0.0 else 1.0
        return [value / total for value in lo]
    fill = min(remaining, capacity)
    reps = [low + fill * (high - low) / capacity for low, high in zip(lo, hi)]
    total = sum(reps)
    if abs(total - 1.0) > 1e-9:  # 数值兜底
        reps = [value / total for value in reps]
    return reps


def mixing_degree(intervals: list[list[float]]) -> float:
    return 1.0 - max(representative(intervals))


def mixing_degree_uncertainty(intervals: list[list[float]]) -> float:
    lo_max = max(item[0] for item in intervals)
    hi_max = min(1.0, max(item[1] for item in intervals))
    return max(0.0, (hi_max - lo_max) / 2.0)


def build_grid_map(fractions_path: str | Path, n_groups: int) -> dict:
    """档号（1 起，与 CSV 的 composition_bin 对齐）→ 区间 / 代表组成 / 混合度 / 不确定度。"""
    columns: list[dict] = []
    for index, raw in enumerate(parse_fractions(fractions_path, n_groups), start=1):
        intervals = expand_intervals(raw)
        reps = representative(intervals)
        columns.append(
            {
                "index": index,
                "intervals": intervals,
                "representative": reps,
                "mixing_degree": 1.0 - max(reps),
                "max_share": max(reps),
                "uncertainty": mixing_degree_uncertainty(intervals),
            }
        )
    return {"n_groups": int(n_groups), "columns": columns}
