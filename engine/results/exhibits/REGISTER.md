# Exhibit-Register

Erzeugt aus dem Freeze-Archiv (Tag `results-freeze-v1`). 26 Exhibits, 5 offene Lücken.

Die Spalte **Platzierung** ist ein Vorschlag und in REGISTER.csv leicht änderbar; sie beeinflusst die Erzeugung nicht.

| Bezeichner | Typ | Kap. | Platzierung | Szenario | Quelle | Lauf-Hash | Titel |
|---|---|---|---|---|---|---|---|
| `abb_3_1` | Abbildung | 3 | Hauptteil | S1 | `describe.correlation` | `f0129516a99f9c4a` | Korrelationsmatrix der Tagesrenditen |
| `tab_3_1` | Tabelle | 3 | Hauptteil | S1 | `describe.assets` | `f0129516a99f9c4a` | Anlageuniversum und Datenverfügbarkeit |
| `tab_3_2` | Tabelle | 3 | Hauptteil | alle | `backtest.sample + hashes` | `f0129516a99f9c4a` | Sample-Designs und Reproduktionsanker |
| `tab_3_3` | Tabelle | 3 | Hauptteil | S1 | `describe.assets` | `f0129516a99f9c4a` | Deskriptive Statistik der Einzelanlagen |
| `tab_3_4` | Tabelle | 3 | Hauptteil | S1 | `describe.rf.estr` | `f0129516a99f9c4a` | Verketteter risikofreier Zins (€STR / EONIA) |
| `abb_4_10` | Abbildung | 4 | Anhang | S1 | `analytics.distribution` | `f0129516a99f9c4a` | Verteilung der Tagesrenditen mit CVaR-Markierung |
| `abb_4_11` | Abbildung | 4 | Anhang | S1 | `robustness.walk_forward.oos` | `f0129516a99f9c4a` | Out-of-Sample-Vermögensverlauf aus dem Walk-Forward |
| `abb_4_12` | Abbildung | 4 | Anhang | S1 | `analytics.monthly` | `f0129516a99f9c4a` | Monatsrenditen im Zeitraster |
| `abb_4_3` | Abbildung | 4 | Hauptteil | S1 | `sweep.points + sweep_bootstrap.bands` | `f0129516a99f9c4a` | Risiko-Effekt über die Krypto-Quote mit Konfidenzbändern |
| `abb_4_4` | Abbildung | 4 | Anhang | S1 | `sweep.points + sweep_bootstrap.bands` | `f0129516a99f9c4a` | Sharpe-Verläufe über die Krypto-Quote (brutto) |
| `abb_4_5` | Abbildung | 4 | Hauptteil | S1 | `sweep_bootstrap.argmax` | `f0129516a99f9c4a` | Bootstrap-Verteilung der optimalen Krypto-Quote |
| `abb_4_7` | Abbildung | 4 | Hauptteil | S1 | `robustness.param_stability` | `f0129516a99f9c4a` | Parameter-Stabilität über Lookback und Zielvolatilität |
| `abb_4_8` | Abbildung | 4 | Anhang | S1 | `robustness.cost_sensitivity` | `f0129516a99f9c4a` | Sharpe Ratio in Abhängigkeit von den Transaktionskosten |
| `abb_4_9` | Abbildung | 4 | Anhang | S1 | `analytics.rolling` | `f0129516a99f9c4a` | Rollierende Sharpe Ratio im Zeitverlauf |
| `tab_4_1` | Tabelle | 4 | Hauptteil | S1 | `backtest.metrics` | `f0129516a99f9c4a` | Kennzahlen der Strategien (Hauptspezifikation) |
| `tab_4_10` | Tabelle | 4 | Anhang | S1 | `robustness.walk_forward` | `f0129516a99f9c4a` | Walk-Forward: Folds und Out-of-Sample-Ergebnis |
| `tab_4_11` | Tabelle | 4 | Hauptteil | S1 | `robustness.subperiods` | `f0129516a99f9c4a` | Ergebnisse nach Marktregime |
| `tab_4_12` | Tabelle | 4 | Anhang | S1 | `analytics.drawdowns` | `f0129516a99f9c4a` | Die 5 tiefsten Drawdown-Episoden |
| `tab_4_3` | Tabelle | 4 | Anhang | S1 | `backtest.metrics (turnover*)` | `f0129516a99f9c4a` | Zerlegung des Turnovers |
| `tab_4_4` | Tabelle | 4 | Hauptteil | S1 | `hypotheses.H1/H2 + holm_adjusted` | `f0129516a99f9c4a` | Konfirmatorische Hypothesentests H1 und H2 |
| `tab_4_5` | Tabelle | 4 | Hauptteil | S1 | `hypotheses.sweep_bootstrap.slopes` | `f0129516a99f9c4a` | H3: Steigung des Effekts über die Krypto-Quote (Datenebene) |
| `tab_4_6` | Tabelle | 4 | Anhang | S1 | `hypotheses.deflated_sharpe / probabilistic_sharpe` | `f0129516a99f9c4a` | Deflated und Probabilistic Sharpe Ratio |
| `tab_4_7` | Tabelle | 4 | Hauptteil | S1/S2/S3 | `hypotheses (drei Records)` | `f0129516a99f9c4a` | Szenariovergleich der konfirmatorischen Befunde |
| `tab_4_8` | Tabelle | 4 | Hauptteil | S4_2018..2022 | `hypotheses (fünf Records)` | `f0129516a99f9c4a` | Sensitivität gegenüber dem Startjahr |
| `tab_4_9` | Tabelle | 4 | Anhang | S1 / S1_rf3 | `backtest.metrics + hypotheses.H1` | `f0129516a99f9c4a` | Sensitivität gegenüber der Zinsannahme |
| `tab_a_1` | Tabelle | Anhang | Anhang | alle | `hashes + git + environment` | `f0129516a99f9c4a` | Reproduktionsnachweis je Record |

## Nicht erzeugbar aus dem Archiv

| Bezeichner | Kap. | Titel | Grund | Behebung |
|---|---|---|---|---|
| `tab_4_2` | 4 | Teilfrage 1: Buy-and-Hold bei Krypto-Quote 0/10/25/50 %, netto | Das Archiv hält backtest.metrics nur für die angefragte Quote (10 %). sweep.points führt zwar alle 21 Quoten, aber BRUTTO und nur mit d_mdd/d_cvar/sharpe_bh/sharpe_vc — ohne Rendite, CAGR, Vol, MaxDD, CVaR. | RECORDS in freeze_run.py um S1_bh0/S1_bh25/S1_bh50 ergänzen (crypto_share 0.0/0.25/0.50) und das Archiv neu erzeugen. |
| `abb_3_2` | 3 | Verlauf der verketteten €STR/EONIA-Tagesreihe | describe.rf.estr enthält nur Kennzahlen der Reihe (Mittel, Min, Max, Anteil negativer Tage), nicht die Tageswerte selbst. | rf-Tagesreihe im Record ablegen — sie liegt in der Engine bereits vor (cfg.rf_for). Ersatzweise deckt tab_3_4 die Kennzahlen ab. |
| `abb_4_1` | 4 | Vermögensverlauf VC 5/10/15 gegen Buy-and-Hold und True Buy-and-Hold | Der /timeseries-Endpoint wurde beim Archivieren nicht aufgerufen; im Record liegt nur der Out-of-Sample-Verlauf aus dem Walk-Forward (robustness.walk_forward.oos), der als abb_4_11 erzeugt wurde. | 'timeseries' in die compute()-Blockliste von freeze_run.py aufnehmen und das Archiv neu erzeugen. |
| `abb_4_2` | 4 | Exposure-Pfad der Vol-Control 10 % mit Hebelgrenze | Gleiche Ursache: der Exposure-Pfad kommt aus /timeseries. | wie abb_4_1. |
| `abb_4_6` | 4 | Drawdown-Verläufe VC 10 % gegen Buy-and-Hold | Gleiche Ursache. analytics.drawdowns führt nur die fünf tiefsten Episoden als Liste — daraus wurde tab_4_12 erzeugt, nicht aber der Verlauf. | wie abb_4_1. |
