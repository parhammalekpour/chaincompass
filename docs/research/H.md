# Study H — Health Score and forward-return association

The samples are spaced by their forward-return horizon. Correlation
intervals use the pre-registered approximate Fisher-z calculation;
terciles use expanding past-only score cutoffs.

| Chain | H | n / n independent | Spearman rho | Approx. 95% CI | Reading | Low tercile n / mean / median | Middle n / mean / median | High n / mean / median | Tercile exclusions |
|---|---:|---:|---:|---|---|---|---|---|---:|
| btc | 30 | 97 / 97 | 0.0984 | [-0.103, 0.292] | association not distinguishable from zero | 34 / 0.0207 / 0.0332 | 38 / 0.0485 / 0.0184 | 24 / 0.0964 / 0.0322 | 1 |
| btc | 90 | 32 / 32 | 0.0136 | [-0.337, 0.361] | association not distinguishable from zero | 12 / 0.1411 / -0.0099 | 10 / 0.2288 / 0.1444 | 9 / 0.1466 / 0.0749 | 1 |
| eth | 30 | 93 / 93 | 0.0092 | [-0.195, 0.213] | association not distinguishable from zero | 40 / 0.0254 / -0.0036 | 23 / 0.0946 / 0.0445 | 29 / 0.0769 / -0.0092 | 1 |
| eth | 90 | 31 / 31 | 0.0512 | [-0.309, 0.398] | association not distinguishable from zero | 10 / 0.0000 / -0.0746 | 11 / 0.4826 / 0.2210 | 9 / -0.0234 / -0.0742 | 1 |
| sol | 30 | 52 / 52 | 0.1355 | [-0.143, 0.394] | association not distinguishable from zero | 16 / 0.0624 / 0.0096 | 13 / -0.0388 / 0.0180 | 22 / 0.1016 / -0.0062 | 1 |
| sol | 90 | 17 / 17 | 0.4706 | [-0.013, 0.776] | association not distinguishable from zero | 4 / 0.0352 / 0.0541 | 5 / -0.0210 / -0.0325 | 7 / 0.3549 / 0.3074 | 1 |
| bnb | 30 | 57 / 57 | 0.1369 | [-0.128, 0.384] | association not distinguishable from zero | 9 / 0.0300 / 0.0375 | 12 / -0.0072 / -0.0118 | 35 / 0.0307 / 0.0312 | 1 |
| bnb | 90 | 19 / 19 | 0.3175 | [-0.160, 0.674] | association not distinguishable from zero | 3 / -0.0270 / -0.1012 | 3 / 0.0808 / 0.0098 | 12 / 0.1130 / 0.0750 | 1 |

Association is descriptive, not predictive. Score inputs include
price-derived market-condition components, so any association may
reflect momentum or mean-reversion rather than on-chain information.
