# Mafia / Werewolf Lab

[中文文档与实验记录](README.zh.md)

## Research question

How do public coordination protocols and adversarial responses change team outcomes in a hidden-role game, and how can those effects be evaluated without giving agents information they should not have?

The current model is a 16-player police–mafia game: **4 police, 4 mafia, and 8 civilians**. Police recognize their teammates and share one private investigation per night; mafia recognize their own team. Mafia win when all police are eliminated; the police–civilian team wins when all mafia are eliminated. Deaths do not reveal roles. Werewolf-specific roles are not implemented.

## Agents and evaluation

Agents use **hand-written policies with controlled randomization**, not LLMs or unrestricted natural-language reasoning. Each policy receives only its player's permitted observations. Public actions use structured declarations, suspect lists, execution recommendations, and votes. The implemented voting variant publishes ballots sequentially and allows one tied-candidate speech and revote round.

Experiments compare frozen policies on matched deals and decision-keyed random streams, with separate development and held-out seeds. Source snapshots, configurations, per-game measurements, and replay checks are archived. Small restricted games and selected empirical payoff matrices also have exact rational equilibrium checks; those certificates do not certify the full game.

## Main result: explicit execution recommendations

A police officer may know several mafia players but publicly report only one investigation. We compare the existing protocol with one that **retains the investigation and suspect list, adds an explicit “eliminate X today” recommendation at the same speaking turn, and aligns police votes with that recommendation when legally and privately justified**.

The table reports held-out police–civilian team win rates, **before → after** the intervention. Each rate uses 2,048 simulations, with a fixed 50% local police response probability in a predefined first-day counterclaim window. The false-accusation target is the nearest or farthest eligible non-teammate later in the public speaking order. The two kill policies are frozen positional heuristics, not optimized best responses.

Mafia can win without eliminating civilians and, under the fixed continuation policies, prioritize publicly exposed police for night kills. These asymmetric objectives and restricted policies provide context for the low baseline rates; the experiments do not establish the full game’s equilibrium balance.

| Mafia kill policy | False-accusation target | Original liar repeats its claim | Teammate takes over after the liar dies |
| --- | --- | ---: | ---: |
| Late-position heuristic (`safe_late`) | Near | 7.86% → 8.15% | 7.86% → 25.15% |
| Late-position heuristic (`safe_late`) | Far | 8.54% → 8.74% | 8.54% → 27.20% |
| Positional decoy (`posterior_decoy`) | Near | 5.42% → 5.76% | 5.42% → 19.53% |
| Positional decoy (`posterior_decoy`) | Far | 5.66% → 6.01% | 5.66% → 22.12% |

All four takeover-condition improvements have simultaneous 95% paired binomial bounds above zero across the eight comparisons; the repeat-only differences remain inconclusive. The adversary can choose not to take over, so the 19–27% rates are **conditional results, not an overall robust win rate**. The lowest observed win rate across these eight conditions after the intervention is 5.76%.

See the [detailed methods and results (Chinese)](docs/police_execution_results_v26.md), [frozen configuration](results/v26/source/configs/police_execution_v26.json), and [held-out results](results/v26/holdout.json).

## Limitations

- These are fixed-policy simulations in an explicitly restricted ruleset, not estimates of human play or a solution to the full game. The coordination intervention adds public statement content and changes team vote-following together; their separate contributions have not been isolated.
- Both teams have limited candidate policies. Opponents have not been optimized against every new protocol. Information-source handling, vote-history heuristics, and timing remain incomplete; apparent gains can depend strongly on the receiving policy.
- An exact equilibrium certificate for a finite empirical matrix establishes correctness for that matrix. It does not remove Monte Carlo uncertainty, establish population exploitability, or imply full-game GTO. Earlier held-out results inspected during development are no longer untouched final validation data.
- Werewolf mechanics, LLM agents, human teaching outcomes, and transfer to poker have not been validated.
