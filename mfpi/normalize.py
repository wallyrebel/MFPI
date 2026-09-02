from __future__ import annotations

import math
from collections.abc import Mapping


def robust_percentiles(values: Mapping[str, float | None], neutral: float = 50.0) -> dict[str, float]:
    """Return average-rank empirical percentiles with correct tie handling.

    Outliers cannot stretch every other value because only ordering matters.
    Missing values and all-equal populations receive a transparent neutral 50.
    """

    present = [(key, float(value)) for key, value in values.items() if value is not None and math.isfinite(value)]
    result = {key: neutral for key in values}
    if len(present) < 2:
        return result
    present.sort(key=lambda item: item[1])
    if present[0][1] == present[-1][1]:
        return result
    denominator = len(present) - 1
    index = 0
    while index < len(present):
        end = index
        while end + 1 < len(present) and present[end + 1][1] == present[index][1]:
            end += 1
        average_rank = (index + end) / 2
        percentile = 100.0 * average_rank / denominator
        for position in range(index, end + 1):
            result[present[position][0]] = percentile
        index = end + 1
    return result
