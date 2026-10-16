"""Descriptive Monte Carlo intervals, not equilibrium certificates."""
from math import log, sqrt


def win_summary(values):
    n = len(values)
    if not n:
        return {"n": 0, "wins": 0, "rate": None, "ci95_wilson": None}
    wins = sum(values)
    p, z = wins/n, 1.959963984540054
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    half = z*sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return {"n": n, "wins": wins, "rate": p,
            "ci95_wilson": [max(0, center-half), min(1, center+half)]}


def paired_summary(control, treatment):
    if len(control) != len(treatment):
        raise ValueError("Paired samples must have same length")
    n = len(control)
    if not n:
        return {"n": 0, "delta": None, "ci95_normal": None}
    differences = [b-a for a, b in zip(control, treatment)]
    mean = sum(differences)/n
    variance = sum((d-mean)**2 for d in differences)/(n-1) if n > 1 else None
    half = 1.959963984540054*sqrt(variance/n) if variance is not None else None
    return {"n": n, "delta": mean,
            "ci95_normal": [max(-1, mean-half), min(1, mean+half)] if half is not None else None,
            "ci95_hoeffding": [max(-1, mean-sqrt(2*log(40)/n)),
                                min(1, mean+sqrt(2*log(40)/n))],
            "normal_interval_warning": "Exploratory Wald interval; zero sample variance does not prove equality.",
            "improved": differences.count(1), "worsened": differences.count(-1),
            "unchanged": differences.count(0)}
