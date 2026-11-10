# Plan: how much of spot BTC ETF inflow is the basis trade?

Written and committed 2026-11-10, before any test statistic was computed.
If I change anything below after this commit, the change goes in the "Amendments" section at the end with a date and a reason, and the original text stays.

## Question

US spot bitcoin ETFs have taken in about $55bn net since January 2024. Some of that money is a directional bet on price. Some of it is the cash-and-carry trade: a hedge fund buys ETF shares, shorts CME bitcoin futures against them and earns the futures premium (the basis). The second group has no view on price and leaves when the premium goes away.

I want a number for the split, or at least a defensible range, and I want to know whether flows push price or follow it.

## Hypotheses

**H1. Inflows come with new CME shorts.** In weeks when ETF inflows are large, leveraged funds (CFTC Traders in Financial Futures category) add to their net short in CME bitcoin futures.

**H2. A narrowing basis is followed by outflows.** When the futures premium drops sharply, net ETF flows over the next five trading days are lower than usual, beyond what the price move alone explains.

**H3. Flows follow price.** Yesterday's bitcoin return predicts today's ETF flow better than yesterday's flow predicts today's return.

My point prediction for H1, written down so it can be wrong: the hedge ratio (BTC of new leveraged-fund net short per BTC of ETF inflow, weekly) is between 0.2 and 0.5 in the 2025-2026 test period. I expect it to be lower in 2025-2026 than in 2024, because the basis has compressed.

## Data

All free, all checked on 2026-11-10.

| Source | What | Coverage | Access | Notes |
|---|---|---|---|---|
| Farside Investors, farside.co.uk/bitcoin-etf-flow-all-data/ | Daily net flow per US spot BTC ETF, US$m | 11 Jan 2024 to today, 727 rows | One HTML page with the full history, parsed as a table. No API. robots.txt has no rule against it. | Market holidays appear as rows with "-" in every fund and Total 0: these are dropped, not read as zero flow. Today's row is a placeholder until the evening. Recent days can be revised. I fetch once per run and do not redistribute the raw table. |
| CFTC Traders in Financial Futures, futures only, publicreporting.cftc.gov dataset gpe5-46if | Weekly positions by trader category | CME Bitcoin (code 133741, 5 BTC per contract) and CME Micro Bitcoin (133742, 0.1 BTC) | Public Socrata JSON API, no key | 153 weekly reports from 5 Dec 2023 to 3 Nov 2026, no missing week. Positions are as of Tuesday, published Friday. |
| Binance USDT-margined quarterly futures and spot | Daily close of BTCUSDT spot, current quarter and next quarter contracts | 1 Jan 2024 to today, 1,045 days, no gaps | Public REST (continuousKlines), no key | Basis proxy. Offshore, USDT-settled, so it is not the CME basis. Contract expires last Friday of the quarter, 08:00 UTC. |
| Deribit quarterly futures | Daily OHLC per contract, expired ones included | Checked back to the Mar 2024 contract | Public REST (get_tradingview_chart_data), no key | Cross-check of the Binance basis. |
| Yahoo Finance BTC=F | CME front-month settlement-ish daily close | 722 days from 2 Jan 2024 | Unofficial endpoint, no key | Closest free look at the actual CME basis. Rolls monthly, close time does not match spot. Used only as a sanity check, never in a test. |

Not free and not used: CME settlement history, Glassnode/Coinglass ETF holdings, Bloomberg.

## Variables

- **Weekly window**: Wednesday to Tuesday, so each week ends on a COT as-of date.
- **ETF flow in BTC**: daily US$ flow divided by that day's BTC close at 21:00 UTC (US market close, 20:00 UTC during US daylight time; taken from Binance hourly spot). Summed over the week. Measuring in BTC removes the price level from the flow series.
- **Leveraged-fund net short**: (short minus long) of the leveraged funds category, standard contract times 5 plus micro contract times 0.1, in BTC. The weekly variable is its change versus the prior Tuesday.
- **Basis**: annualised premium of Binance quarterly futures over spot, interpolated between the current and next quarter contract to a constant 90 days to expiry. Days with fewer than 7 days to the near expiry use the next contract only.
- **Daily return**: log change in BTC spot between consecutive US closes.

## Samples

- **Calibration**: 2024 (about 50 weeks, about 245 trading days). Used only to fix thresholds and debug code.
- **Test**: 1 Jan 2025 to the last COT report available when I run the test (about 96 weeks, about 460 trading days).

The test period is not blind. The early 2025 basis unwind was widely reported, and while checking data coverage today I saw that leveraged-fund gross short fell from about 25,000 to about 7,700 standard contracts between late 2024 and November 2026. What pre-registration buys here is that thresholds, variables and pass/fail lines are fixed before I compute any relationship. It does not buy ignorance of the headlines.

## Tests and pass lines

All tests are one-sided at 5%. Standard errors are Newey-West (4 lags weekly, 5 lags daily). I report three hypotheses, so I also show whether each result survives a 5%/3 Bonferroni line; the verdict uses the plain 5% line.

**H1.**
- Main test: OLS of weekly change in leveraged-fund net short (BTC) on weekly ETF flow (BTC), test period. The slope is the hedge ratio. Supported if the slope is positive and significant.
- Large-week check: a large inflow week is one above the 80th percentile of 2024 weekly flows (threshold computed from 2024 only and written into the amendments section before the test runs). Supported if the mean change in net short in large weeks is above the mean in all other weeks (block bootstrap, 4-week blocks).
- H1 passes if the main test passes. The large-week check is reported either way.

**H2.**
- Event: the 5-day change in the 90-day basis is below the 10th percentile of 2024 5-day changes (threshold from 2024 only, written into the amendments before the test).
- Outcome: sum of ETF flow (BTC) over the next 5 trading days.
- Main test: OLS of next-5-day flow on the past 5-day basis change, controlling for the past 5-day return, daily, overlapping windows, Newey-West with 5 lags. Supported if the basis coefficient is positive (a fall in basis predicts lower flow) and significant with the return control in.
- Event check: mean next-5-day flow after events versus all other days, block bootstrap with 5-day blocks. Reported either way.
- The return control matters: basis and price fall together, so without it H2 would be H3 in disguise.

**H3.**
- Two regressions on the test sample, daily, 5 lags of both variables in each:
  - flow(t) on return(t-1..t-5) and flow(t-1..t-5)
  - return(t) on flow(t-1..t-5) and return(t-1..t-5)
- Flow is standardised by its trailing 60-day standard deviation so both sides are in comparable units.
- Supported if the return lags are jointly significant in the flow equation (Wald test) and the flow lags are not jointly significant in the return equation. If both are significant I compare the sum of standardised lag coefficients and report it as "both directions", not as support.

## Sample size limits

- About 96 test weeks for H1. A weekly correlation needs to be about 0.25 or larger to be detected with 80% power at one-sided 5%. Smaller effects will show as nulls.
- The calibration year has about 50 weeks, so the percentile thresholds are noisy.
- COT gives category totals. A leveraged-fund short can hedge an ETF position, a spot position on another venue, or be a plain bet. The hedge ratio is an upper bound on basis-driven flow only if no other leveraged-fund shorts rise with ETF inflows, and a lower bound if some basis traders sit in other categories. I will say this next to the number.
- The Binance basis is a proxy. CME basis has usually been higher. If the Binance and Yahoo CME series disagree in direction over the test period, I report that and treat H2 as weak evidence at best.

## Output

- One chart: weekly ETF flow (BTC) on top, weekly change in leveraged-fund net short (BTC) below, two stacked panels with a shared time axis, test period shaded. No dual axis.
- A README with the three verdicts, the hedge ratio with its interval, and the null results stated as plainly as the positive ones.
- I publish whatever comes out.

## Amendments

### 2026-11-10, thresholds from 2024 (before any test)

Computed by `thresholds.py` on data fetched 2026-11-10 (sha256 of farside.html starts 2e20cd5f, cftc.json 4ac68f97, binance.json 7f3a4945). Nothing from 2025 or later was used.

- H1 large inflow week: weekly ETF flow above **20,563 BTC** (80th percentile of 51 calibration weeks).
- H2 basis-drop event: 5-day change in the 90-day annualised basis below **-2.23 percentage points** (10th percentile of 240 calibration days).

Clarifications of details the plan left open, also fixed before any test:

- One-sided p-value = half the two-sided HAC p-value when the coefficient has the predicted sign, else 1 minus that.
- Block bootstraps: moving blocks, 10,000 resamples, seed 0. p = share of resampled differences with the wrong sign.
- H3: the return is also divided by its trailing 60-day standard deviation, and both trailing windows end at t-1 so no day scales itself. This changes nothing in the Wald tests; it only puts the coefficient sums on the same scale.
- The first calibration week (ending 2024-01-16) has 3 trading days because the ETFs launched on 11 January. It stays in.
- The Binance daily close is 24:00 UTC, four to five hours after the US close. The H2 outcome starts the next US trading day, so this does not leak the outcome into the predictor.
- Deribit daily candles run 08:00 to 08:00 UTC and repeat the last price after expiry. In the cross-check each contract is cut at its expiry and compared with Binance hourly spot at the same 08:00 timestamp.

### 2026-11-10, after the first test run

Two bug fixes. Neither touches a test input or a threshold; the H1-H3 numbers came out the same before and after.

- Yahoo CME cross-check: the first run compared Yahoo's close (16:00 Chicago) with Binance's 24:00 UTC daily close. That gap made the CME premium noisy enough to show -1.4% for Q1 2025. Now it uses Binance hourly spot at 16:00 Chicago, and skips days within 10 days of the monthly expiry (was 7), because I don't know when Yahoo rolls to the next contract. Before the fix the direction check failed (quarterly correlation -0.69); after it, it passes (0.41). I flag this because the plan ties the reading of H2 to this check. H2 failed on its own test either way.
- The quarterly expiry list started in January 2024, so December 2023 basis used the wrong contract. Only December 2023 changed, and no test or threshold uses it.
