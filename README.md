# Thrissur Trading Terminal — 50 Depth Order Book

> **Open Source · Powered by Fyers API**
> A real-time 50-level order book dashboard for NSE instruments (Futures & Options), built with Python, Dash, and Plotly.

![Dashboard Preview](screenshot.png)

---

## Table of Contents

1. [What This Is](#what-this-is)
2. [Setup & Installation](#setup--installation)
3. [Project Structure](#project-structure)
4. [Market Microstructure Calculations](#market-microstructure-calculations)
   - [1. Mid Price](#1-mid-price)
   - [2. Spread](#2-spread)
   - [3. Spread in Basis Points](#3-spread-in-basis-points)
   - [4. Microprice](#4-microprice)
   - [5. Weighted Mid (Top 10 Levels)](#5-weighted-mid-top-10-levels)
   - [6. Volume Imbalance (Full 50 Levels)](#6-volume-imbalance-full-50-levels)
   - [7. Level Imbalance (Per Level, Top 10)](#7-level-imbalance-per-level-top-10)
   - [8. Cumulative Depth](#8-cumulative-depth)
   - [9. Order Count Heatmap & Iceberg Detection](#9-order-count-heatmap--iceberg-detection)
   - [10. Aggregate Depth Profile](#10-aggregate-depth-profile)
5. [Reading the Dashboard](#reading-the-dashboard)
6. [License](#license)

---

## What This Is

Most retail traders only see the top 5 levels of the order book. NSE via the Fyers TBT (Tick-By-Tick) WebSocket exposes all **50 levels** on each side — 50 bid price/qty/order-count rows and 50 ask price/qty/order-count rows, updated in real time.

This dashboard visualises all 50 levels and computes a set of **market microstructure metrics** used by quantitative traders and market makers to understand order flow, liquidity, and short-term price pressure.

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- A Fyers API account with a valid access token ([Fyers API docs](https://myapi.fyers.in/))

### Install

```bash
git clone https://github.com/thrissur-trading-terminal/orderbook-50depth
cd orderbook-50depth
pip install -r requirements.txt
```

### Configure Credentials

Edit `fyers.py` with your own credentials:

```python
client_id    = "YOUR_CLIENT_ID"       # e.g. "ABCD1234-100"
access_token = "YOUR_ACCESS_TOKEN"    # JWT token from Fyers login flow
instruments  = [
    'NSE:NIFTY26MAYFUT',
    'NSE:NIFTY2650524000CE',
    'NSE:NIFTY2650524000PE',
]
```

### Run

```bash
python dashboard.py
```

Open your browser at **http://127.0.0.1:8050**

> `127.0.0.1` is localhost — your data never leaves your machine.

---

## Project Structure

```
.
├── app.py            # Fyers WebSocket connection (standalone test)
├── dashboard.py      # Main Dash dashboard (run this)
├── fyers.py          # Credentials & instrument list
├── requirements.txt  # All dependencies
└── README.md
```

---

## Market Microstructure Calculations

All calculations use live data from the Fyers TBT WebSocket. The examples below use a real snapshot from `NSE:NIFTY26MAYFUT`:

```
Timestamp  : 1777446258
Best Bid   : 24443.30  |  Qty: 260   |  Orders: 2
Best Ask   : 24444.50  |  Qty: 65    |  Orders: 1
TBQ        : 524,485
TSQ        : 220,870
```

---

### 1. Mid Price

The simple arithmetic average of the best bid and best ask.

$$P_{mid} = \frac{P_{bid,L1} + P_{ask,L1}}{2}$$

**Where:**
- $P_{bid,L1}$ = best bid price (Level 1 bid)
- $P_{ask,L1}$ = best ask price (Level 1 ask)

**Example:**

$$P_{mid} = \frac{24443.30 + 24444.50}{2} = \mathbf{24443.90}$$

> The mid price is the neutral reference point. It does not account for where the weight of liquidity actually sits — that is what Microprice corrects for.

---

### 2. Spread

The cost of immediately buying and selling the same instrument.

$$\text{Spread} = P_{ask,L1} - P_{bid,L1}$$

**Example:**

$$\text{Spread} = 24444.50 - 24443.30 = \mathbf{1.20}$$

> NIFTY futures have a tick size of ₹0.05. A spread of 1.20 means **24 ticks** between best bid and best ask at this snapshot.

---

### 3. Spread in Basis Points

Normalises the spread relative to price level, making it comparable across instruments regardless of their absolute price.

$$\text{Spread}_{bps} = \frac{\text{Spread}}{P_{mid}} \times 10{,}000$$

**Where:**
- $\text{Spread}$ = raw tick spread from above
- $P_{mid}$ = mid price
- 10,000 = conversion factor from decimal to basis points

**Example:**

$$\text{Spread}_{bps} = \frac{1.20}{24443.90} \times 10{,}000 = \mathbf{0.49 \text{ bps}}$$

> Comparing NIFTY Futures (0.49 bps) vs a deep OTM option (often 50–200 bps) using spread bps immediately shows how much more expensive it is to trade the option.

---

### 4. Microprice

A volume-weighted mid price using Level 1 quantities. Unlike the raw mid which treats both sides equally, the microprice pulls toward whichever side has more liquidity at the touch — giving a more accurate short-term price estimate.

$$P_{micro} = \frac{V_{bid,L1} \cdot P_{ask,L1} + V_{ask,L1} \cdot P_{bid,L1}}{V_{bid,L1} + V_{ask,L1}}$$

**Where:**
- $V_{bid,L1}$ = quantity at the best bid (Level 1 bid qty)
- $V_{ask,L1}$ = quantity at the best ask (Level 1 ask qty)
- $P_{bid,L1}$, $P_{ask,L1}$ = best bid and ask prices

**Example:**

$$P_{micro} = \frac{260 \times 24444.50 + 65 \times 24443.30}{260 + 65}$$

$$= \frac{6{,}355{,}570 + 1{,}588{,}814.50}{325} = \frac{7{,}944{,}384.50}{325} = \mathbf{24443.95}$$

> The microprice (24443.95) is slightly above the raw mid (24443.90), pulled toward the ask because the bid has 4× more quantity (260 vs 65). This suggests mild upward price pressure at the touch.

---

### 5. Weighted Mid (Top 10 Levels)

Extends the microprice concept across the top 10 levels on each side, giving a deeper view of where price is anchored.

$$\bar{P}_{bid,10} = \frac{\sum_{i=1}^{10} P_{bid,i} \cdot V_{bid,i}}{\sum_{i=1}^{10} V_{bid,i}}, \qquad \bar{P}_{ask,10} = \frac{\sum_{i=1}^{10} P_{ask,i} \cdot V_{ask,i}}{\sum_{i=1}^{10} V_{ask,i}}$$

$$P_{wmid} = \frac{\bar{P}_{bid,10} + \bar{P}_{ask,10}}{2}$$

**Example (top 10 bid levels):**

| Level | Price | Qty | Price × Qty |
|-------|-------|-----|-------------|
| 1 | 24443.30 | 260 | 6,355,358 |
| 2 | 24441.30 | 65 | 1,588,684.50 |
| 3 | 24440.40 | 65 | 1,588,626 |
| 4 | 24440.20 | 260 | 6,354,452 |
| 5 | 24440.10 | 650 | 15,886,065 |
| 6 | 24440.00 | 7,540 | 184,277,600 |
| 7 | 24439.80 | 390 | 9,531,522 |
| 8 | 24439.70 | 65 | 1,588,580.50 |
| 9 | 24439.60 | 130 | 3,177,148 |
| 10 | 24439.50 | 65 | 1,588,567.50 |

$$\sum V_{bid,10} = 9{,}040, \qquad \sum (P \cdot V)_{bid,10} = 231{,}936{,}603.50$$

$$\bar{P}_{bid,10} = \frac{231{,}936{,}603.50}{9{,}040} \approx 25{,}657.81$$

> Notice how the 7,540 qty at Level 6 (24440.00) dominates and pulls the weighted bid price down significantly. This is a large resting order acting as a **support wall** — a key signal for directional traders.

---

### 6. Volume Imbalance (Full 50 Levels)

Measures the net directional bias of the entire visible order book. Ranges from −1 (pure sell pressure) to +1 (pure buy pressure).

$$I = \frac{TBQ - TSQ}{TBQ + TSQ} \in [-1, +1]$$

**Where:**
- $TBQ$ = Total Bid Quantity = sum of all 50 bid level quantities
- $TSQ$ = Total Ask Quantity = sum of all 50 ask level quantities
- $I > 0$ indicates net buying pressure
- $I < 0$ indicates net selling pressure
- $I \approx 0$ indicates a balanced book

**Example:**

$$TBQ = 524{,}485, \qquad TSQ = 220{,}870$$

$$I = \frac{524{,}485 - 220{,}870}{524{,}485 + 220{,}870} = \frac{303{,}615}{745{,}355} = \mathbf{+0.407}$$

Displayed as **+40.7%** on the dashboard.

> A +40.7% imbalance means the bid side of the book carries 2.37× more visible volume than the ask side. This is a strong bullish signal — buyers are committing significantly more liquidity than sellers at this snapshot.

---

### 7. Level Imbalance (Per Level, Top 10)

The same imbalance concept applied individually to each of the top 10 price levels. This reveals which specific levels are contested and which are dominated by one side.

$$I_k = \frac{V_{bid,k} - V_{ask,k}}{V_{bid,k} + V_{ask,k}}, \qquad k = 1, 2, \ldots, 10$$

**Where:**
- $V_{bid,k}$ = bid quantity at level $k$
- $V_{ask,k}$ = ask quantity at level $k$
- $I_k = +1$ means no ask liquidity at that level (pure bid wall)
- $I_k = -1$ means no bid liquidity at that level (pure ask wall)
- $I_k \approx 0$ means the level is evenly contested

**Example (top 5 levels):**

| Level | Bid Qty | Ask Qty | $I_k$ | Interpretation |
|-------|---------|---------|--------|----------------|
| 1 | 260 | 65 | **+0.60** | Bid-heavy touch |
| 2 | 65 | 260 | **−0.60** | Ask-heavy level 2 |
| 3 | 65 | 260 | **−0.60** | Ask-heavy level 3 |
| 4 | 260 | 3,965 | **−0.88** | Large ask wall at L4 |
| 5 | 650 | 325 | **+0.33** | Mild bid lean at L5 |
| 6 | 7,540 | 65 | **+0.98** | Massive bid wall at L6 |

> Level 6 ($I_6 = +0.98$) is the dominant feature of this snapshot — 7,540 lots bid at 24440.00 against only 65 lots ask. This is a large resting support order, likely from a single institutional participant.

---

### 8. Cumulative Depth

The running total of available liquidity as you walk away from the best price on each side.

$$CumBid_k = \sum_{i=1}^{k} V_{bid,i}, \qquad CumAsk_k = \sum_{i=1}^{k} V_{ask,i}, \qquad k = 1, 2, \ldots, 50$$

**Where:**
- $CumBid_k$ = total bid liquidity available within $k$ levels of the best bid
- $CumAsk_k$ = total ask liquidity available within $k$ levels of the best ask

**Example (first 6 levels):**

| Level | Bid Qty | CumBid | Ask Qty | CumAsk |
|-------|---------|--------|---------|--------|
| 1 | 260 | 260 | 65 | 65 |
| 2 | 65 | 325 | 260 | 325 |
| 3 | 65 | 390 | 260 | 585 |
| 4 | 260 | 650 | 3,965 | 4,550 |
| 5 | 650 | 1,300 | 325 | 4,875 |
| 6 | 7,540 | 8,840 | 65 | 4,940 |

> The step at Level 6 on the bid side (cumulative jumps from 1,300 to 8,840) and Level 4 on the ask side (cumulative jumps from 585 to 4,550) are the **liquidity walls** — visible as steep vertical steps in the cumulative depth chart. A market order large enough to consume these levels would move price significantly.

---

### 9. Order Count Heatmap & Iceberg Detection

The exchange provides not just quantity but also the **number of individual orders** at each price level. This combination reveals order structure.

$$\text{Avg size per order at level } k = \frac{V_k}{N_k}$$

**Where:**
- $V_k$ = total quantity at level $k$
- $N_k$ = number of individual orders at level $k$

**Example — the suspicious Level 6 bid:**

| Level | Price | Qty | Orders | Avg Size/Order |
|-------|-------|-----|--------|----------------|
| Bid L6 | 24440.00 | 7,540 | 24 | **314 lots/order** |
| Ask L20 | 24450.00 | 12,675 | 117 | **108 lots/order** |
| Ask L4 | 24445.00 | 3,965 | 10 | **397 lots/order** |
| Ask L14 | 24449.00 | 3,575 | 20 | **179 lots/order** |

> **Bid Level 6:** 7,540 lots across 24 orders = 314 lots per order average. This is large but distributed — likely multiple institutional participants or a systematic strategy placing repeated orders at the support level.
>
> **Ask Level 20:** 12,675 lots across **117 orders** = only 108 lots/order. This is fragmented retail/algo activity — many small participants stacking at the 24450.00 psychological round number.
>
> **Red flag pattern:** A level with very high qty and very **few** orders (e.g. 5,000 lots in 1 order) is a classic iceberg indicator — a single large participant hiding size. If that order cancels, the level disappears instantly.

---

### 10. Aggregate Depth Profile

The total visible liquidity on each side of the book across all 50 levels.

$$TBQ = \sum_{i=1}^{50} V_{bid,i}, \qquad TSQ = \sum_{i=1}^{50} V_{ask,i}$$

**Example:**

$$TBQ = 524{,}485 \text{ lots}, \qquad TSQ = 220{,}870 \text{ lots}$$

$$\frac{TBQ}{TSQ} = \frac{524{,}485}{220{,}870} \approx \mathbf{2.37\times}$$

> The bid side carries 2.37× more visible volume than the ask across all 50 levels. For a NIFTY Futures contract at lot size 25, TBQ represents **₹32,000 crore** notional on the bid side vs **₹13,500 crore** on the ask. This is a strongly bullish book at this snapshot.

---

## Reading the Dashboard

| Widget | What to look for |
|--------|-----------------|
| **Depth Ladder** | Asymmetric bars — one side with much longer bars at a level = wall. Bars that keep refreshing after fills = iceberg. |
| **Microprice vs Mid** | If microprice > mid, bid is heavier at the touch — short-term upward lean. If microprice < mid, ask is heavier. |
| **Imbalance %** | Above +30% = strong buy pressure. Below −30% = strong sell pressure. Near 0% = balanced, expect mean reversion. |
| **Cumulative Depth** | Steep steps = large walls. Gradual slope = distributed liquidity. Asymmetry between bid and ask curves shows directional commitment. |
| **Level Imbalance** | Bars near +1 or −1 at top levels = one side has almost no presence — fragile level, large price move possible if hit. |
| **Order Count Heatmap** | Bright cells with low order count = potential iceberg. Bright cells with high order count = genuine market consensus. |

---

## License

MIT License — free to use, modify, and distribute with attribution.

Built by [Thrissur Trading Terminal](https://quantttt.com) · [@thrissur-trading-terminal](https://github.com/thrissur-trading-terminal)
