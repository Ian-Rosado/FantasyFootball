# Gridiron Grind — Findings Summary (as of Aug 2026)

Confidence tags: **[FACT]** = hard data · **[SOLID]** = clear pattern · **[LEAN]** = weak/small-sample signal, directional only.

## League history
- **[FACT]** Titles: JGERK 4 (2009,12,13,19), SimonMiller 3 (2018,20,25), BurrowingMule 2, madmax 2, then 1 each: Ryan505(2011), Joles(2015), ajg21(2016), **Iyano1911/Ian (2017)**, zach_montoya(2022), Chance145(2023).
- **[FACT]** BurrowingMule = winningest reg-season (.611) but 2-for-5 in finals. Ryan505 = 1 title, 5 runner-ups (bridesmaid).
- Champions are taken from the actual title game; Fleaflicker's "postseason rank" field is unreliable and is NOT used.

## Luck (actual wins vs all-play expected wins)
- **[SOLID]** JGERK unluckiest all-time (~-13 wins), zach_montoya luckiest (~+8). Ian roughly neutral.

## Head-to-head (Ian)
- **[FACT]** 121-123 all-time. Owns Chance (15-4), Peter (13-8). Owned by Derek (10-19), Dawkins (5-14), Simon (8-14). Coin-flips: vs Gerk 11-10, vs Ryan 9-11.

## Draft strategy -> wins (auction era, n=36)
- **[LEAN]** Draft **RB** = best predictor (r=+0.32, ~10% of variance, borderline sig). RB-lean 7.4 wins vs WR-lean 6.7.
- **[LEAN]** Don't pay up for **TE** (-0.28) or **QB** (-0.12). Stars-and-scrubs vs balanced = no difference.
- **[SOLID-ish]** All 3 auction champions were RB-forward; cellar was WR/TE-heavy.

## FAAB -> wins (2021-25)
- **[LEAN]** Volume slightly beats aggression (cheap churn > big splashes).
- **[LEAN]** Save budget for late — late-season spend r=+0.23 (strongest FAAB signal). Field over-spends by Week 5.
- **[LEAN]** Heavy RB *waiver* spend correlates with losing (-0.16) — a distress signal, not a plan.

## Trades -> wins
- **[LEAN/none]** Trade count barely relates (+0.19). Contenders trade ~2x more but volume alone doesn't drive it; quality does (unmeasured).

## Combined recipe (cleanest story)
- **[LEAN]** RB-heavy draft + active FAAB = 8.1 wins / 4.8 rank (best of the 2x2). RB draft WITHOUT active FAAB finished worst (6.0). Draft RB, then work the wire to keep the backfield healthy, saving powder for the playoff push.

## League market tendencies (over/underpay vs fair value)
- **[SOLID]** Pay ~fair for studs (0.98x), slight discount mid-tier (0.91x), big overpay on $1 sleepers (2.6x). Mid-tier = value zone; never chase $3-5 fliers. Pattern holds even excluding the most value-averse managers (Derek/Joles).

## TE-cliff test
- **[SOLID]** TE has the SMALLEST elite-to-replacement drop-off. Elite TE ~71 pts over replacement vs ~140 for elite RB/WR. The cliff is at RB/WR, not TE — which is why paying up for TE has hurt. (VOR is already built into the model's prices.)

## 2026 plan (one-keeper year)
- **[ACTIONABLE]** Keep **Puka Nacua** ($58); $142 left. Lean RB, WR2 efficient, punt QB/TE ($7 TE), save FAAB. Three scenarios in the workbook (A: RB-Heavy, B: Two-Stud, C: Balanced).

## How much to trust this
- History/H2H/luck/market/TE = firm. Strategy correlations (draft/FAAB/trade) = 3 auction seasons, n=36; treat as *tilts, not laws*. The `analysis/trend_report.md` tracks whether each signal strengthens or fades as seasons are added.
