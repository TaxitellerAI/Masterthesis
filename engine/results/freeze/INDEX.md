# Ergebnis-Freeze — Archivübersicht

Erzeugt: 2026-07-27T18:48:57+00:00  
Commit: `results-freeze-v1-2-g35beace` (35beaceae20509cafcf7c0ac4c75389691b2462f)
Umgebung: Python 3.14.4 · numpy 2.5.0 · pandas 3.0.3 · scipy 1.18.0 · statsmodels 0.14.6 · Darwin 25.6.0 arm64

| Record | Fenster | n | Datensatz-Hash | Lauf-Hash | Laufzeit |
|---|---|---:|---|---|---:|
| S1 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `f0129516a99f9c4a` | 0.6s |
| S2 | 2015-01-02–2025-12-31 | 2765 | `ebf5ba110371d633` | `f3e55eb08c91c93b` | 0.6s |
| S3 | 2021-01-04–2025-12-31 | 1254 | `f10f75b3cc68093b` | `6cb43825ee6860a3` | 0.5s |
| S4_2018 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `eade5ce249da9ebb` | 8.5s |
| S4_2019 | 2019-01-02–2025-12-31 | 1759 | `393b9fff8c45e318` | `4b3c9e6e5d94c226` | 7.2s |
| S4_2020 | 2020-01-02–2025-12-31 | 1507 | `4aaa25e937fa7322` | `9ee0b737af2a6365` | 6.2s |
| S4_2021 | 2021-01-04–2025-12-31 | 1254 | `43c7318e1fb4c7a6` | `92be61991a3fa7c1` | 5.2s |
| S4_2022 | 2022-01-03–2025-12-31 | 1002 | `282cd7a47293c575` | `a3838800c6c7407e` | 4.3s |
| S1_rf3 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `eca6dde9182002a5` | 7.8s |
| S1_bh0 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `f0129516a99f9c4a` | 0.6s |
| S1_bh25 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `f0129516a99f9c4a` | 0.6s |
| S1_bh50 | 2018-01-02–2025-12-31 | 2010 | `715caf81d0dd19d5` | `f0129516a99f9c4a` | 0.6s |

## Kernzahlen je Record

| Record | H1 ΔMDD | H1 BCa | H2 ΔSharpe | H2 BCa | H3 Steigung | H3 KI | Argmax |
|---|---:|---|---:|---|---:|---|---:|
| S1 | +0.0847 | [+0.0365; +0.2022] | +0.0753 | [-0.1586; +0.3408] | 0.7099 | [0.3836; 0.9653] | 0.15 |
| S2 | +0.0832 | [+0.0446; +0.1830] | +0.0345 | [-0.1429; +0.2303] | 0.6469 | [0.1982; 0.8169] | 0.50 |
| S3 | +0.0713 | [+0.0349; +0.1674] | -0.1998 | [-0.8168; +0.1683] | 0.7165 | [0.3072; 0.8806] | 0.17 |
| S4_2018 | +0.0847 | [+0.0365; +0.2022] | +0.0753 | [-0.1586; +0.3408] | 0.7099 | [0.3836; 0.9653] | 0.15 |
| S4_2019 | +0.0847 | [+0.0409; +0.1733] | -0.0630 | [-0.3171; +0.2034] | 0.5190 | [0.3027; 0.8340] | 0.30 |
| S4_2020 | +0.1567 | [+0.0467; +0.3643] | +0.1708 | [-0.2332; +0.7518] | 0.3825 | [0.2780; 0.7885] | 0.30 |
| S4_2021 | +0.0646 | [+0.0254; +0.1556] | -0.1912 | [-0.7334; +0.1575] | 0.6175 | [0.2783; 0.8477] | 0.17 |
| S4_2022 | +0.0516 | [+0.0031; +0.0963] | +0.1511 | [-0.1623; +0.4805] | 0.5290 | [0.2222; 0.7722] | 0.28 |
| S1_rf3 | +0.0853 | [+0.0294; +0.1768] | +0.0718 | [-0.1656; +0.3351] | 0.7113 | [0.3951; 1.0091] | 0.35 |
| S1_bh0 | +0.0847 | [+0.0365; +0.2022] | +0.0753 | [-0.1586; +0.3408] | 0.7099 | [0.3836; 0.9653] | 0.15 |
| S1_bh25 | +0.0847 | [+0.0365; +0.2022] | +0.0753 | [-0.1586; +0.3408] | 0.7099 | [0.3836; 0.9653] | 0.15 |
| S1_bh50 | +0.0847 | [+0.0365; +0.2022] | +0.0753 | [-0.1586; +0.3408] | 0.7099 | [0.3836; 0.9653] | 0.15 |

## rf-Sensitivität (S1)

Verkettete €STR/EONIA-Tagesreihe gegen konstante 3 % p. a.

| Strategie | Sharpe €STR | Sharpe rf=3 % | Δ | MaxDD €STR | MaxDD rf=3 % |
|---|---:|---:|---:|---:|---:|
| BuyHold | 0.9040 | 0.7770 | -0.1270 | -0.2714 | -0.2714 |
| VolControl_5 | 1.0005 | 0.8680 | -0.1325 | -0.0997 | -0.0981 |
| VolControl_10 | 0.9795 | 0.8488 | -0.1307 | -0.1867 | -0.1862 |
| VolControl_15 | 0.9888 | 0.8599 | -0.1289 | -0.2355 | -0.2353 |
| Benchmark_TrueBH | 0.7280 | 0.6630 | -0.0650 | -0.4371 | -0.4371 |
| Benchmark_6040 | 0.5820 | 0.4231 | -0.1589 | -0.2274 | -0.2274 |
| Benchmark_RiskParity | 1.1118 | 0.9867 | -0.1251 | -0.2084 | -0.2084 |

H1 ΔMDD: +0.084662 gegen +0.085257; H2 ΔSharpe: +0.075343 gegen +0.071850.


Der Zins wirkt an ZWEI Stellen, die nicht verwechselt werden dürfen. In der RENDITEREIHE nur bei der Vol-Control, über die Cash-Quote (1 − Exposure) · rf: die Buy-and-Hold-Reihe ist dort tatsächlich unberührt (Rendite p. a. 0,159200 in beiden Läufen, MaxDD −0,271400 in beiden). Im SHARPE dagegen bei allen Strategien, weil rf der Vergleichszins im Zähler ist — deshalb fällt auch der Buy-and-Hold-Sharpe um 0,1270.

Die Sharpe-Änderung folgt eng −ē · Δrf / σ (ē = mittleres Exposure): vorhergesagt −0,1281 / −0,1455 / −0,1450 / −0,1382 für BH und VC 5/10/15, gemessen −0,1270 / −0,1325 / −0,1307 / −0,1289. Die Vol-Control verliert je Einheit mehr, weil ihre kleinere Volatilität im Nenner steht.

Für die berichteten VERGLEICHE ist der Effekt daher klein: der Sharpe-Vorsprung der Vol-Control gegenüber Buy-and-Hold geht von +0,0755 auf +0,0718 zurück (−0,0037), der Drawdown-Vorsprung steigt leicht von +0,0847 auf +0,0852. Die naheliegende Vermutung, eine konstante positive Zinsannahme schmeichle der Vol-Control, bestätigt sich in dieser Stichprobe NICHT — sie verschiebt vor allem das NIVEAU aller Sharpe-Werte um rund 0,13, nicht die Rangfolge. Wer Niveaus zitiert, muss die Zinskonvention mitnennen; die Hypothesentests H1 und H2 sind gegenüber dieser Annahme nahezu invariant.
