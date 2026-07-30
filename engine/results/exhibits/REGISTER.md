# Exhibit-Register

Erzeugt aus dem Freeze-Archiv (Tag `results-freeze-v1`). 33 Exhibits, 0 offene Lücken.

Die Spalte **Platzierung** ist ein Vorschlag und in REGISTER.csv leicht änderbar; sie beeinflusst die Erzeugung nicht.

| Bezeichner | Typ | Kap. | Platzierung | Szenario | Quelle | Lauf-Hash | Titel |
|---|---|---|---|---|---|---|---|
| `abb_3_1` | Abbildung | 3 | Hauptteil | S1 | `describe.correlation` | `0800e49d75cee860` | Korrelationsmatrix der Tagesrenditen |
| `abb_3_2` | Abbildung | 3 | Hauptteil | S1 | `rf_series` | `0800e49d75cee860` | Verlauf des verketteten risikofreien Zinses |
| `tab_3_1` | Tabelle | 3 | Hauptteil | S1 | `describe.assets` | `0800e49d75cee860` | Anlageuniversum und Datenverfügbarkeit |
| `tab_3_2` | Tabelle | 3 | Hauptteil | alle | `backtest.sample + hashes` | `0800e49d75cee860` | Sample-Designs und Reproduktionsanker |
| `tab_3_3` | Tabelle | 3 | Hauptteil | S1 | `describe.assets` | `0800e49d75cee860` | Deskriptive Statistik der Einzelanlagen |
| `tab_3_4` | Tabelle | 3 | Hauptteil | S1 | `describe.rf.estr` | `0800e49d75cee860` | Verketteter risikofreier Zins (€STR / EONIA) |
| `abb_4_1` | Abbildung | 4 | Hauptteil | S1 | `timeseries` | `0800e49d75cee860` | Vermögensverlauf der Strategien |
| `abb_4_10` | Abbildung | 4 | Anhang | S1 | `analytics.distribution` | `0800e49d75cee860` | Verteilung der Tagesrenditen mit CVaR-Markierung |
| `abb_4_11` | Abbildung | 4 | Anhang | S1 | `robustness.walk_forward.oos` | `0800e49d75cee860` | Out-of-Sample-Vermögensverlauf aus dem Walk-Forward |
| `abb_4_12` | Abbildung | 4 | Anhang | S1 | `analytics.monthly` | `0800e49d75cee860` | Monatsrenditen im Zeitraster |
| `abb_4_13` | Abbildung | 4 | Hauptteil | S1 | `analytics.correlation` | `0800e49d75cee860` | Rollierende Korrelation der digitalen Assets zum Aktienindex |
| `abb_4_2` | Abbildung | 4 | Anhang | S1 | `timeseries` | `0800e49d75cee860` | Investitionsquote der Vol-Control im Zeitverlauf |
| `abb_4_3` | Abbildung | 4 | Hauptteil | S1 | `sweep.points + sweep_bootstrap.bands` | `0800e49d75cee860` | Risiko-Effekt über die Krypto-Quote mit Konfidenzbändern |
| `abb_4_4` | Abbildung | 4 | Anhang | S1 | `sweep.points + sweep_bootstrap.bands` | `0800e49d75cee860` | Sharpe-Verläufe über die Krypto-Quote (brutto) |
| `abb_4_5` | Abbildung | 4 | Hauptteil | S1 | `sweep_bootstrap.argmax` | `0800e49d75cee860` | Bootstrap-Verteilung der optimalen Krypto-Quote |
| `abb_4_6` | Abbildung | 4 | Anhang | S1 | `timeseries` | `0800e49d75cee860` | Drawdown-Verläufe im Vergleich |
| `abb_4_7` | Abbildung | 4 | Hauptteil | S1 | `robustness.param_stability` | `0800e49d75cee860` | Parameter-Stabilität über Lookback und Zielvolatilität |
| `abb_4_8` | Abbildung | 4 | Anhang | S1 | `robustness.cost_sensitivity` | `0800e49d75cee860` | Sharpe Ratio in Abhängigkeit von den Transaktionskosten |
| `abb_4_9` | Abbildung | 4 | Anhang | S1 | `analytics.rolling` | `0800e49d75cee860` | Rollierende Sharpe Ratio im Zeitverlauf |
| `tab_4_1` | Tabelle | 4 | Hauptteil | S1 | `backtest.metrics` | `0800e49d75cee860` | Kennzahlen der Strategien (Hauptspezifikation) |
| `tab_4_10` | Tabelle | 4 | Anhang | S1 | `robustness.walk_forward` | `0800e49d75cee860` | Walk-Forward: Folds und Out-of-Sample-Ergebnis |
| `tab_4_11` | Tabelle | 4 | Hauptteil | S1 | `robustness.subperiods` | `0800e49d75cee860` | Ergebnisse nach Marktregime |
| `tab_4_12` | Tabelle | 4 | Anhang | S1 | `analytics.drawdowns` | `0800e49d75cee860` | Die 5 tiefsten Drawdown-Episoden |
| `tab_4_13` | Tabelle | 4 | Hauptteil | S1 | `exposure_stats.by_target_vol` | `0800e49d75cee860` | Investitionsgrad je Zielvolatilität |
| `tab_4_2` | Tabelle | 4 | Hauptteil | S1_bh0/S1/S1_bh25/S1_bh50 | `backtest.metrics[BuyHold]` | `0800e49d75cee860` | Teilfrage 1: Risiko-Rendite-Profil des STATISCHEN Portfolios je Krypto-Quote |
| `tab_4_3` | Tabelle | 4 | Anhang | S1 | `backtest.metrics (turnover*)` | `0800e49d75cee860` | Zerlegung des Turnovers |
| `tab_4_4` | Tabelle | 4 | Hauptteil | S1 | `hypotheses.H1/H2 + holm_adjusted` | `0800e49d75cee860` | Konfirmatorische Hypothesentests H1 und H2 |
| `tab_4_5` | Tabelle | 4 | Hauptteil | S1 | `hypotheses.sweep_bootstrap.slopes` | `0800e49d75cee860` | H3: Steigung des Effekts über die Krypto-Quote (Datenebene) |
| `tab_4_6` | Tabelle | 4 | Anhang | S1 | `hypotheses.deflated_sharpe / probabilistic_sharpe` | `0800e49d75cee860` | Deflated und Probabilistic Sharpe Ratio |
| `tab_4_7` | Tabelle | 4 | Hauptteil | S1/S2/S3 | `hypotheses (drei Records)` | `0800e49d75cee860` | Szenariovergleich der konfirmatorischen Befunde |
| `tab_4_8` | Tabelle | 4 | Hauptteil | S4_2018..2022 | `hypotheses (fünf Records)` | `0800e49d75cee860` | Sensitivität gegenüber dem Startjahr |
| `tab_4_9` | Tabelle | 4 | Anhang | S1 / S1_rf3 | `backtest.metrics + hypotheses.H1` | `0800e49d75cee860` | Sensitivität gegenüber der Zinsannahme |
| `tab_a_1` | Tabelle | Anhang | Anhang | alle | `hashes + git + environment` | `0800e49d75cee860` | Reproduktionsnachweis je Record |

## Nicht erzeugbar aus dem Archiv

| Bezeichner | Kap. | Titel | Grund | Behebung |
|---|---|---|---|---|
