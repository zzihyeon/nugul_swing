from __future__ import annotations


def rs_bucket(rs_percentile: float) -> int:
    if rs_percentile >= 90:
        return 1
    if rs_percentile >= 80:
        return 2
    if rs_percentile >= 70:
        return 3
    return 4


def rs_bucket_label(rs_percentile: float) -> str:
    bucket = rs_bucket(rs_percentile)
    return {1: "RS 상위 10%", 2: "RS 상위 20%", 3: "RS 상위 30%", 4: "RS 하위 구간"}[bucket]


def sort_rs_priority(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            rs_bucket(float(item.get("rs_percentile", 0))),
            -float(item.get("raw_vote_score", 0)),
            int(item.get("rs_rank", 9999)),
        ),
    )
