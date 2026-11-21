# Study R — regime v1 versus comparison state machine v2

V2 is comparison-only and is not adopted. Durations include the final
right-censored run; switches do not count initial state assignment.

| Chain | Version | Switches | Regime episodes | Mean duration days | Median duration days | Episodes <10 days | Stored v1 matches | Mismatches |
|---|---|---:|---:|---:|---:|---:|---|---:|
| btc | v1 | 55 | 56 | 58.79 | 27.50 | 12 | True | 0 |
| btc | v2 | 60 | 61 | 53.97 | 25.00 | 15 | — | — |
| eth | v1 | 51 | 52 | 63.31 | 31.00 | 6 | True | 0 |
| eth | v2 | 58 | 59 | 55.80 | 23.00 | 12 | — | — |
| sol | v1 | 32 | 33 | 66.73 | 29.00 | 5 | True | 0 |
| sol | v2 | 43 | 44 | 50.05 | 15.00 | 16 | — | — |
| bnb | v1 | 57 | 58 | 55.36 | 23.00 | 10 | True | 0 |
| bnb | v2 | 60 | 61 | 52.64 | 18.00 | 13 | — | — |

## Raw-stress episode lags

Lags are calendar days. A missing detection is reported as not
observed; a missing exit after detected stress is right-censored.

| Chain | Version | Raw stress episode | Detection lag days | Exit lag days | Detection | Exit censoring |
|---|---|---|---:|---:|---|---|
| btc | v1 | 2018-08-16–2019-04-02 | 4 | 7 | observed | False |
| btc | v1 | 2019-04-04–2019-04-04 | 0 | 5 | observed | False |
| btc | v1 | 2020-03-12–2020-03-23 | 4 | 13 | observed | False |
| btc | v1 | 2020-03-27–2020-03-31 | 0 | 5 | observed | False |
| btc | v1 | 2021-06-21–2021-06-21 | — | — | not observed | False |
| btc | v1 | 2021-06-25–2021-06-25 | — | — | not observed | False |
| btc | v1 | 2021-07-16–2021-07-20 | 4 | 5 | observed | False |
| btc | v1 | 2022-05-09–2023-01-28 | 4 | 24 | observed | False |
| btc | v1 | 2023-01-30–2023-01-31 | 0 | 21 | observed | False |
| btc | v1 | 2023-02-02–2023-02-14 | 0 | 7 | observed | False |
| btc | v1 | 2023-02-16–2023-02-16 | 0 | 5 | observed | False |
| btc | v1 | 2023-02-24–2023-03-12 | 4 | 5 | observed | False |
| btc | v1 | 2026-06-05–2026-06-06 | — | — | not observed | False |
| btc | v1 | 2026-06-09–2026-06-10 | — | — | not observed | False |
| btc | v1 | 2026-06-24–2026-07-02 | 4 | 5 | observed | False |
| btc | v1 | 2026-07-08–2026-07-08 | — | — | not observed | False |
| btc | v2 | 2018-08-16–2019-04-02 | 0 | 7 | observed | False |
| btc | v2 | 2019-04-04–2019-04-04 | 0 | 5 | observed | False |
| btc | v2 | 2020-03-12–2020-03-23 | 0 | 13 | observed | False |
| btc | v2 | 2020-03-27–2020-03-31 | 0 | 5 | observed | False |
| btc | v2 | 2021-06-21–2021-06-21 | 0 | 9 | observed | False |
| btc | v2 | 2021-06-25–2021-06-25 | 0 | 5 | observed | False |
| btc | v2 | 2021-07-16–2021-07-20 | 0 | 5 | observed | False |
| btc | v2 | 2022-05-09–2023-01-28 | 0 | 24 | observed | False |
| btc | v2 | 2023-01-30–2023-01-31 | 0 | 21 | observed | False |
| btc | v2 | 2023-02-02–2023-02-14 | 0 | 7 | observed | False |
| btc | v2 | 2023-02-16–2023-02-16 | 0 | 5 | observed | False |
| btc | v2 | 2023-02-24–2023-03-12 | 0 | 5 | observed | False |
| btc | v2 | 2026-06-05–2026-06-06 | 0 | 9 | observed | False |
| btc | v2 | 2026-06-09–2026-06-10 | 0 | 5 | observed | False |
| btc | v2 | 2026-06-24–2026-07-02 | 0 | 5 | observed | False |
| btc | v2 | 2026-07-08–2026-07-08 | 0 | 5 | observed | False |
| eth | v1 | 2018-08-16–2019-06-16 | 4 | 8 | observed | False |
| eth | v1 | 2019-06-18–2019-06-19 | 0 | 5 | observed | False |
| eth | v1 | 2019-07-14–2019-07-30 | 4 | 5 | observed | False |
| eth | v1 | 2019-08-29–2019-08-30 | — | — | not observed | False |
| eth | v1 | 2019-09-06–2019-09-06 | — | — | not observed | False |
| eth | v1 | 2019-09-24–2019-09-24 | — | — | not observed | False |
| eth | v1 | 2019-09-26–2019-09-26 | — | — | not observed | False |
| eth | v1 | 2019-09-29–2019-09-29 | — | — | not observed | False |
| eth | v1 | 2019-10-23–2019-10-24 | — | — | not observed | False |
| eth | v1 | 2019-11-21–2020-01-16 | 4 | 24 | observed | False |
| eth | v1 | 2020-01-19–2020-01-26 | 0 | 14 | observed | False |
| eth | v1 | 2020-03-12–2020-04-05 | 4 | 21 | observed | False |
| eth | v1 | 2020-04-07–2020-04-07 | 0 | 19 | observed | False |
| eth | v1 | 2020-04-09–2020-04-15 | 0 | 11 | observed | False |
| eth | v1 | 2021-06-21–2021-06-28 | 4 | 8 | observed | False |
| eth | v1 | 2021-07-12–2021-07-22 | 4 | 5 | observed | False |
| eth | v1 | 2022-05-09–2023-03-16 | 4 | 16 | observed | False |
| eth | v1 | 2023-03-18–2023-03-18 | 0 | 14 | observed | False |
| eth | v1 | 2023-03-20–2023-03-20 | 0 | 12 | observed | False |
| eth | v1 | 2023-03-22–2023-03-22 | 0 | 10 | observed | False |
| eth | v1 | 2023-03-24–2023-03-25 | 0 | 7 | observed | False |
| eth | v1 | 2023-03-27–2023-03-27 | 0 | 5 | observed | False |
| eth | v1 | 2025-03-09–2025-03-18 | 4 | 9 | observed | False |
| eth | v1 | 2025-03-20–2025-03-22 | 0 | 5 | observed | False |
| eth | v1 | 2025-03-28–2025-05-07 | 4 | 5 | observed | False |
| eth | v1 | 2026-02-01–2026-04-16 | 4 | 131 | observed | False |
| eth | v1 | 2026-04-18–2026-08-20 | 0 | 5 | observed | False |
| eth | v2 | 2018-08-16–2019-06-16 | 0 | 8 | observed | False |
| eth | v2 | 2019-06-18–2019-06-19 | 0 | 5 | observed | False |
| eth | v2 | 2019-07-14–2019-07-30 | 0 | 5 | observed | False |
| eth | v2 | 2019-08-29–2019-08-30 | 0 | 5 | observed | False |
| eth | v2 | 2019-09-06–2019-09-06 | 0 | 5 | observed | False |
| eth | v2 | 2019-09-24–2019-09-24 | 0 | 10 | observed | False |
| eth | v2 | 2019-09-26–2019-09-26 | 0 | 8 | observed | False |
| eth | v2 | 2019-09-29–2019-09-29 | 0 | 5 | observed | False |
| eth | v2 | 2019-10-23–2019-10-24 | 0 | 5 | observed | False |
| eth | v2 | 2019-11-21–2020-01-16 | 0 | 24 | observed | False |
| eth | v2 | 2020-01-19–2020-01-26 | 0 | 14 | observed | False |
| eth | v2 | 2020-03-12–2020-04-05 | 0 | 21 | observed | False |
| eth | v2 | 2020-04-07–2020-04-07 | 0 | 19 | observed | False |
| eth | v2 | 2020-04-09–2020-04-15 | 0 | 11 | observed | False |
| eth | v2 | 2021-06-21–2021-06-28 | 0 | 8 | observed | False |
| eth | v2 | 2021-07-12–2021-07-22 | 0 | 5 | observed | False |
| eth | v2 | 2022-05-09–2023-03-16 | 0 | 16 | observed | False |
| eth | v2 | 2023-03-18–2023-03-18 | 0 | 14 | observed | False |
| eth | v2 | 2023-03-20–2023-03-20 | 0 | 12 | observed | False |
| eth | v2 | 2023-03-22–2023-03-22 | 0 | 10 | observed | False |
| eth | v2 | 2023-03-24–2023-03-25 | 0 | 7 | observed | False |
| eth | v2 | 2023-03-27–2023-03-27 | 0 | 5 | observed | False |
| eth | v2 | 2025-03-09–2025-03-18 | 0 | 9 | observed | False |
| eth | v2 | 2025-03-20–2025-03-22 | 0 | 5 | observed | False |
| eth | v2 | 2025-03-28–2025-05-07 | 0 | 5 | observed | False |
| eth | v2 | 2026-02-01–2026-04-16 | 0 | 131 | observed | False |
| eth | v2 | 2026-04-18–2026-08-20 | 0 | 5 | observed | False |
| sol | v1 | 2022-01-20–2022-03-31 | 4 | 473 | observed | False |
| sol | v1 | 2022-04-05–2023-07-12 | 0 | 5 | observed | False |
| sol | v1 | 2023-07-25–2023-07-25 | — | — | not observed | False |
| sol | v1 | 2023-08-02–2023-08-07 | 4 | 5 | observed | False |
| sol | v1 | 2023-09-10–2023-09-13 | — | — | not observed | False |
| sol | v1 | 2025-03-09–2025-03-13 | 4 | 14 | observed | False |
| sol | v1 | 2025-03-16–2025-03-18 | 0 | 9 | observed | False |
| sol | v1 | 2025-03-20–2025-03-22 | 0 | 5 | observed | False |
| sol | v1 | 2025-03-28–2025-04-11 | 4 | 9 | observed | False |
| sol | v1 | 2025-04-13–2025-04-15 | 0 | 5 | observed | False |
| sol | v1 | 2025-11-21–2025-11-23 | — | — | not observed | False |
| sol | v1 | 2025-12-01–2025-12-01 | — | — | not observed | False |
| sol | v1 | 2025-12-14–2026-01-01 | 4 | 5 | observed | False |
| sol | v1 | 2026-01-20–2026-01-20 | — | — | not observed | False |
| sol | v1 | 2026-01-23–2026-01-25 | — | — | not observed | False |
| sol | v1 | 2026-01-29–2026-09-20 | 4 | 9 | observed | False |
| sol | v1 | 2026-09-23–2026-09-24 | 0 | 5 | observed | False |
| sol | v1 | 2026-10-08–2026-10-08 | — | — | not observed | False |
| sol | v1 | 2026-11-14–2026-11-16 | — | — | not observed | False |
| sol | v1 | 2026-11-19–2026-11-19 | — | — | not observed | False |
| sol | v2 | 2022-01-20–2022-03-31 | 0 | 473 | observed | False |
| sol | v2 | 2022-04-05–2023-07-12 | 0 | 5 | observed | False |
| sol | v2 | 2023-07-25–2023-07-25 | 0 | 5 | observed | False |
| sol | v2 | 2023-08-02–2023-08-07 | 0 | 5 | observed | False |
| sol | v2 | 2023-09-10–2023-09-13 | 0 | 5 | observed | False |
| sol | v2 | 2025-03-09–2025-03-13 | 0 | 14 | observed | False |
| sol | v2 | 2025-03-16–2025-03-18 | 0 | 9 | observed | False |
| sol | v2 | 2025-03-20–2025-03-22 | 0 | 5 | observed | False |
| sol | v2 | 2025-03-28–2025-04-11 | 0 | 9 | observed | False |
| sol | v2 | 2025-04-13–2025-04-15 | 0 | 5 | observed | False |
| sol | v2 | 2025-11-21–2025-11-23 | 0 | 5 | observed | False |
| sol | v2 | 2025-12-01–2025-12-01 | 0 | 5 | observed | False |
| sol | v2 | 2025-12-14–2026-01-01 | 0 | 5 | observed | False |
| sol | v2 | 2026-01-20–2026-01-20 | 0 | 252 | observed | False |
| sol | v2 | 2026-01-23–2026-01-25 | 0 | 247 | observed | False |
| sol | v2 | 2026-01-29–2026-09-20 | 0 | 9 | observed | False |
| sol | v2 | 2026-09-23–2026-09-24 | 0 | 5 | observed | False |
| sol | v2 | 2026-10-08–2026-10-08 | 0 | 5 | observed | False |
| sol | v2 | 2026-11-14–2026-11-16 | 0 | — | observed | True |
| sol | v2 | 2026-11-19–2026-11-19 | 0 | — | observed | True |
| bnb | v1 | 2018-11-05–2019-02-08 | 4 | 7 | observed | False |
| bnb | v1 | 2019-09-23–2019-10-27 | 4 | 5 | observed | False |
| bnb | v1 | 2019-11-18–2020-02-05 | 4 | 5 | observed | False |
| bnb | v1 | 2020-02-26–2020-03-01 | 4 | 5 | observed | False |
| bnb | v1 | 2020-03-08–2020-07-06 | 4 | 5 | observed | False |
| bnb | v1 | 2021-05-19–2021-05-19 | — | — | not observed | False |
| bnb | v1 | 2021-05-21–2021-05-23 | — | — | not observed | False |
| bnb | v1 | 2021-05-28–2021-05-30 | — | — | not observed | False |
| bnb | v1 | 2021-06-18–2021-06-19 | — | — | not observed | False |
| bnb | v1 | 2021-06-21–2021-08-05 | 4 | 5 | observed | False |
| bnb | v1 | 2021-09-27–2021-09-28 | — | — | not observed | False |
| bnb | v1 | 2022-05-09–2022-05-23 | 4 | 168 | observed | False |
| bnb | v1 | 2022-05-25–2022-08-09 | 0 | 90 | observed | False |
| bnb | v1 | 2022-08-11–2022-08-11 | 0 | 88 | observed | False |
| bnb | v1 | 2022-08-13–2022-11-02 | 0 | 5 | observed | False |
| bnb | v1 | 2022-11-09–2022-12-07 | 4 | 38 | observed | False |
| bnb | v1 | 2022-12-11–2023-01-03 | 0 | 11 | observed | False |
| bnb | v1 | 2026-02-05–2026-02-05 | — | — | not observed | False |
| bnb | v1 | 2026-02-07–2026-03-03 | 4 | 14 | observed | False |
| bnb | v1 | 2026-03-05–2026-03-12 | 0 | 5 | observed | False |
| bnb | v1 | 2026-03-18–2026-05-09 | 4 | 5 | observed | False |
| bnb | v1 | 2026-05-17–2026-05-20 | — | — | not observed | False |
| bnb | v1 | 2026-05-22–2026-05-22 | — | — | not observed | False |
| bnb | v1 | 2026-05-27–2026-05-29 | — | — | not observed | False |
| bnb | v1 | 2026-06-02–2026-08-19 | 4 | 5 | observed | False |
| bnb | v2 | 2018-11-05–2019-02-08 | 0 | 7 | observed | False |
| bnb | v2 | 2019-09-23–2019-10-27 | 0 | 5 | observed | False |
| bnb | v2 | 2019-11-18–2020-02-05 | 0 | 5 | observed | False |
| bnb | v2 | 2020-02-26–2020-03-01 | 0 | 5 | observed | False |
| bnb | v2 | 2020-03-08–2020-07-06 | 0 | 5 | observed | False |
| bnb | v2 | 2021-05-19–2021-05-19 | 0 | 16 | observed | False |
| bnb | v2 | 2021-05-21–2021-05-23 | 0 | 12 | observed | False |
| bnb | v2 | 2021-05-28–2021-05-30 | 0 | 5 | observed | False |
| bnb | v2 | 2021-06-18–2021-06-19 | 0 | 52 | observed | False |
| bnb | v2 | 2021-06-21–2021-08-05 | 0 | 5 | observed | False |
| bnb | v2 | 2021-09-27–2021-09-28 | 0 | 7 | observed | False |
| bnb | v2 | 2022-05-09–2022-05-23 | 0 | 168 | observed | False |
| bnb | v2 | 2022-05-25–2022-08-09 | 0 | 90 | observed | False |
| bnb | v2 | 2022-08-11–2022-08-11 | 0 | 88 | observed | False |
| bnb | v2 | 2022-08-13–2022-11-02 | 0 | 5 | observed | False |
| bnb | v2 | 2022-11-09–2022-12-07 | 0 | 38 | observed | False |
| bnb | v2 | 2022-12-11–2023-01-03 | 0 | 11 | observed | False |
| bnb | v2 | 2026-02-05–2026-02-05 | 0 | 40 | observed | False |
| bnb | v2 | 2026-02-07–2026-03-03 | 0 | 14 | observed | False |
| bnb | v2 | 2026-03-05–2026-03-12 | 0 | 5 | observed | False |
| bnb | v2 | 2026-03-18–2026-05-09 | 0 | 5 | observed | False |
| bnb | v2 | 2026-05-17–2026-05-20 | 0 | 96 | observed | False |
| bnb | v2 | 2026-05-22–2026-05-22 | 0 | 94 | observed | False |
| bnb | v2 | 2026-05-27–2026-05-29 | 0 | 87 | observed | False |
| bnb | v2 | 2026-06-02–2026-08-19 | 0 | 5 | observed | False |
