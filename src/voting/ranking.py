from __future__ import annotations

from src.voting.rs_priority_ranker import rs_bucket


def final_grade(rs_percentile: float, raw_vote_score: float, veto: bool = False) -> str:
    if veto:
        return "Excluded"
    if rs_percentile >= 90 and raw_vote_score >= 80:
        return "Strong Buy Candidate"
    if rs_percentile >= 80 and raw_vote_score >= 70:
        return "Buy Candidate"
    if rs_percentile >= 70 and raw_vote_score >= 60:
        return "Watchlist"
    if rs_bucket(rs_percentile) >= 4 or raw_vote_score < 60:
        return "Weak Watch"
    return "Watchlist"
