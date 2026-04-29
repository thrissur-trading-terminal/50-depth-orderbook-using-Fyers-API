"""
Thrissur Trading Terminal — 50 Depth Order Book Dashboard
========================
Run with:  python dashboard.py
Then open: http://127.0.0.1:8050

Architecture: single-process, in-memory shared dict.
The Fyers TBT WebSocket writes into `BOOK_STORE` dict;
Dash reads from the same dict via a dcc.Interval callback.
"""

import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

from fyers_apiv3.FyersWebsocket.tbt_ws import FyersTbtSocket, SubscriptionModes
from fyers import instruments, socket_token

# ─── Shared in-memory store ───────────────────────────────────────────────────
BOOK_STORE: dict = {sym: None for sym in instruments}
BOOK_LOCK = threading.Lock()

# ─── Fyers WebSocket callbacks ────────────────────────────────────────────────

def onopen():
    fyers_ws.subscribe(
        symbol_tickers=instruments,
        channelNo='1',
        mode=SubscriptionModes.DEPTH,
    )
    fyers_ws.switchChannel(resume_channels=['1'], pause_channels=[])
    fyers_ws.keep_running()

def on_depth_update(ticker, message):
    with BOOK_LOCK:
        BOOK_STORE[ticker] = message

def onerror(msg):       print("WS Error:", msg)
def onclose(msg):       print("WS Closed:", msg)
def onerror_message(m): print("WS Server Error:", m)

# ─── Start WebSocket in background thread ────────────────────────────────────

def start_ws():
    global fyers_ws
    fyers_ws = FyersTbtSocket(
        access_token=socket_token,
        write_to_file=False,
        log_path="",
        on_open=onopen,
        on_close=onclose,
        on_error=onerror,
        on_depth_update=on_depth_update,
        on_error_message=onerror_message,
    )
    fyers_ws.connect()

ws_thread = threading.Thread(target=start_ws, daemon=True)
ws_thread.start()

# ─── Calculation helpers ──────────────────────────────────────────────────────

def compute_metrics(msg):
    bp = np.array(msg.bidprice)
    ap = np.array(msg.askprice)
    bq = np.array(msg.bidqty)
    aq = np.array(msg.askqty)
    bo = np.array(msg.bidordn)
    ao = np.array(msg.askordn)

    best_bid = bp[0]
    best_ask = ap[0]
    mid       = (best_bid + best_ask) / 2
    spread    = best_ask - best_bid
    spread_bps = (spread / mid) * 10000

    # Microprice (top-level)
    micro = (bq[0] * best_ask + aq[0] * best_bid) / (bq[0] + aq[0])

    # Volume imbalance (all 50 levels)
    tbq = msg.tbq
    tsq = msg.tsq
    imbalance = (tbq - tsq) / (tbq + tsq)   # -1 to +1

    # Weighted mid across top-10 levels
    w_bid = np.sum(bp[:10] * bq[:10]) / np.sum(bq[:10]) if np.sum(bq[:10]) > 0 else mid
    w_ask = np.sum(ap[:10] * aq[:10]) / np.sum(aq[:10]) if np.sum(aq[:10]) > 0 else mid
    wmid  = (w_bid + w_ask) / 2

    # Cumulative depth arrays
    cum_bq = np.cumsum(bq)
    cum_aq = np.cumsum(aq)

    # Avg orders per level (iceberg proxy)
    avg_bid_orders = np.mean(bo)
    avg_ask_orders = np.mean(ao)

    # Depth-weighted imbalance by level (top 10)
    level_imb = (bq[:10] - aq[:10]) / (bq[:10] + aq[:10] + 1e-9)

    return dict(
        best_bid=best_bid, best_ask=best_ask,
        mid=mid, spread=spread, spread_bps=spread_bps,
        micro=micro, wmid=wmid,
        tbq=tbq, tsq=tsq, imbalance=imbalance,
        bp=bp, ap=ap, bq=bq, aq=aq, bo=bo, ao=ao,
        cum_bq=cum_bq, cum_aq=cum_aq,
        level_imb=level_imb,
        avg_bid_orders=avg_bid_orders,
        avg_ask_orders=avg_ask_orders,
        ts=msg.timestamp,
    )

# ─── Colour palette ───────────────────────────────────────────────────────────

BID_COL   = "#1e90ff"   # electric blue
ASK_COL   = "#cc1a1a"   # blood red
NEUT_COL  = "#c8d0e0"
BG        = "#0d0f14"
CARD_BG   = "#13161e"
BORDER    = "#1e2330"
ACCENT    = "#f0b429"
TEXT_DIM  = "#5a6480"
TEXT_MAIN = "#e2e8f4"

# ─── Dash app ─────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@700;800&display=swap",
    ],
    title="Thrissur Trading Terminal — 50 Depth Order Book",
)

CARD = {
    "background": CARD_BG,
    "border": f"1px solid {BORDER}",
    "borderRadius": "8px",
    "padding": "18px",
}

def stat_box(label, id_val, color=TEXT_MAIN):
    return html.Div([
        html.Div(label, style={"fontSize": "10px", "color": TEXT_DIM,
                               "letterSpacing": "0.12em", "textTransform": "uppercase",
                               "fontFamily": "JetBrains Mono", "marginBottom": "4px"}),
        html.Div("—", id=id_val, style={"fontSize": "20px", "fontWeight": "600",
                                         "fontFamily": "JetBrains Mono", "color": color}),
    ], style={"padding": "12px 16px", "background": "#0d0f14",
              "borderRadius": "6px", "border": f"1px solid {BORDER}"})

app.layout = html.Div(style={"background": BG, "minHeight": "100vh",
                              "fontFamily": "JetBrains Mono", "color": TEXT_MAIN,
                              "padding": "24px 32px"}, children=[

    # ── Header ──
    html.Div([
        html.Div([
            html.Span("Thrissur Trading Terminal", style={"fontFamily": "Syne", "fontSize": "22px",
                                     "fontWeight": "800", "color": ACCENT,
                                     "letterSpacing": "-0.02em"}),
            html.Span(" · 50 Depth Order Book", style={"fontFamily": "Syne", "fontSize": "18px",
                                             "fontWeight": "700", "color": TEXT_DIM,
                                             "letterSpacing": "-0.01em"}),
            html.Div("Open Source · Powered by Fyers API", style={
                "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.1em",
                "fontFamily": "JetBrains Mono", "marginTop": "3px"}),
        ]),
        html.Div([
            dcc.Dropdown(
                id="sym-select",
                options=[{"label": s.split(":")[1], "value": s} for s in instruments],
                value=instruments[0],
                clearable=False,
                style={"width": "320px", "fontFamily": "JetBrains Mono",
                       "fontSize": "13px", "background": CARD_BG},
            ),
            html.Div(id="last-update", style={"fontSize": "11px", "color": TEXT_DIM,
                                               "marginLeft": "16px", "alignSelf": "center"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={"display": "flex", "justifyContent": "space-between",
              "alignItems": "center", "marginBottom": "24px"}),

    # ── Instrument name banner ──
    html.Div(id="instrument-banner", style={
        "fontFamily": "Syne", "fontSize": "20px", "fontWeight": "700",
        "color": TEXT_MAIN, "letterSpacing": "0.04em",
        "marginBottom": "16px", "paddingLeft": "4px",
    }),

    # ── KPI row ──
    html.Div([
        stat_box("Best Bid",    "kpi-bid",    BID_COL),
        stat_box("Best Ask",    "kpi-ask",    ASK_COL),
        stat_box("Mid",         "kpi-mid",    NEUT_COL),
        stat_box("Microprice",  "kpi-micro",  ACCENT),
        stat_box("Spread",      "kpi-spread", NEUT_COL),
        stat_box("Spread bps",  "kpi-spbps",  NEUT_COL),
        stat_box("Imbalance",   "kpi-imb",    ACCENT),
        stat_box("Total Bid Q", "kpi-tbq",    BID_COL),
        stat_box("Total Ask Q", "kpi-tsq",    ASK_COL),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(9, 1fr)",
              "gap": "10px", "marginBottom": "20px"}),

    # ── Main layout: left = full-height ladder, right = stacked charts ──
    html.Div([

        # Left: Depth ladder — full page height
        html.Div([
            html.Div("50-LEVEL DEPTH LADDER", style={
                "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.12em",
                "marginBottom": "12px"}),
            dcc.Graph(id="depth-ladder", config={"displayModeBar": False},
                      style={"height": "calc(100vh - 160px)", "minHeight": "1100px"}),
        ], style={**CARD, "flex": "1.1"}),

        # Right: stacked charts
        html.Div([

            html.Div([
                html.Div("CUMULATIVE DEPTH", style={
                    "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.12em",
                    "marginBottom": "12px"}),
                dcc.Graph(id="cum-depth", config={"displayModeBar": False},
                          style={"height": "280px"}),
            ], style={**CARD, "marginBottom": "16px"}),

            html.Div([
                html.Div("LEVEL IMBALANCE — TOP 10", style={
                    "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.12em",
                    "marginBottom": "12px"}),
                dcc.Graph(id="imb-bar", config={"displayModeBar": False},
                          style={"height": "200px"}),
            ], style={**CARD, "marginBottom": "16px"}),

            html.Div([
                html.Div("ORDER COUNT HEATMAP", style={
                    "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.12em",
                    "marginBottom": "12px"}),
                dcc.Graph(id="ordn-heat", config={"displayModeBar": False},
                          style={"height": "160px"}),
            ], style={**CARD, "marginBottom": "16px"}),

            html.Div([
                html.Div("AGGREGATE DEPTH PROFILE", style={
                    "fontSize": "10px", "color": TEXT_DIM, "letterSpacing": "0.12em",
                    "marginBottom": "12px"}),
                dcc.Graph(id="agg-bar", config={"displayModeBar": False},
                          style={"height": "160px"}),
            ], style={**CARD}),

        ], style={"flex": "0.9", "display": "flex", "flexDirection": "column"}),

    ], style={"display": "flex", "gap": "16px"}),

    dcc.Interval(id="tick", interval=500, n_intervals=0),
])

# ─── Callback ─────────────────────────────────────────────────────────────────

TRANSPARENT = {"paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)"}
AXIS_STYLE  = {"color": TEXT_DIM, "gridcolor": BORDER, "zerolinecolor": BORDER,
                "tickfont": {"family": "JetBrains Mono", "size": 10, "color": TEXT_DIM}}

@app.callback(
    Output("kpi-bid",    "children"),
    Output("kpi-ask",    "children"),
    Output("kpi-mid",    "children"),
    Output("kpi-micro",  "children"),
    Output("kpi-spread", "children"),
    Output("kpi-spbps",  "children"),
    Output("kpi-imb",    "children"),
    Output("kpi-tbq",    "children"),
    Output("kpi-tsq",    "children"),
    Output("last-update","children"),
    Output("instrument-banner", "children"),
    Output("depth-ladder","figure"),
    Output("cum-depth",  "figure"),
    Output("imb-bar",    "figure"),
    Output("ordn-heat",  "figure"),
    Output("agg-bar",    "figure"),
    Input("tick",        "n_intervals"),
    Input("sym-select",  "value"),
)
def refresh(_, symbol):
    empty = dash.no_update

    with BOOK_LOCK:
        msg = BOOK_STORE.get(symbol)

    if msg is None:
        no_data = go.Figure().update_layout(**TRANSPARENT,
            annotations=[{"text": "Waiting for data…", "showarrow": False,
                           "font": {"color": TEXT_DIM, "family": "JetBrains Mono"}}])
        return ("—",)*10 + ("",) + (no_data,)*5

    m = compute_metrics(msg)
    ts_str = datetime.fromtimestamp(m["ts"]).strftime("%H:%M:%S")

    # ── KPIs ──
    imb_pct = f"{m['imbalance']*100:+.1f}%"
    instrument_name = symbol.split(":")[1]
    kpis = (
        f"{m['best_bid']:.2f}",
        f"{m['best_ask']:.2f}",
        f"{m['mid']:.2f}",
        f"{m['micro']:.3f}",
        f"{m['spread']:.2f}",
        f"{m['spread_bps']:.1f}",
        imb_pct,
        f"{m['tbq']:,}",
        f"{m['tsq']:,}",
        f"last tick  {ts_str}",
        instrument_name,
    )

    # ── Depth Ladder ──
    levels = list(range(1, 51))
    fig_ladder = go.Figure()
    max_qty = int(max(np.max(m["bq"]), np.max(m["aq"])))
    bid_labels = [f"{p:.2f}  {q:,}" for p, q in zip(m["bp"], m["bq"])]
    ask_labels = [f"{p:.2f}  {q:,}" for p, q in zip(m["ap"], m["aq"])]

    fig_ladder.add_trace(go.Bar(
        x=[-q for q in m["bq"]], y=levels, orientation="h",
        name="Bid", marker_color=BID_COL, opacity=0.85,
        text=bid_labels,
        textposition="outside",
        textfont={"family": "JetBrains Mono", "size": 9, "color": BID_COL},
        cliponaxis=False,
        hovertemplate="Price %{customdata:.2f}<br>Qty %{x:,}<extra>BID</extra>",
        customdata=m["bp"],
    ))
    fig_ladder.add_trace(go.Bar(
        x=m["aq"], y=levels, orientation="h",
        name="Ask", marker_color=ASK_COL, opacity=0.85,
        text=ask_labels,
        textposition="outside",
        textfont={"family": "JetBrains Mono", "size": 9, "color": ASK_COL},
        cliponaxis=False,
        hovertemplate="Price %{customdata:.2f}<br>Qty %{x:,}<extra>ASK</extra>",
        customdata=m["ap"],
    ))
    fig_ladder.update_layout(
        **TRANSPARENT, barmode="overlay", bargap=0.08,
        margin={"l": 120, "r": 120, "t": 10, "b": 30},
        legend={"font": {"family": "JetBrains Mono", "size": 10, "color": TEXT_DIM},
                "bgcolor": "rgba(0,0,0,0)"},
        xaxis={**AXIS_STYLE, "title": "Quantity",
               "range": [-max_qty * 1.6, max_qty * 1.6],
               "fixedrange": True},
        yaxis={**AXIS_STYLE, "title": "Level", "autorange": "reversed"},
        shapes=[{"type": "line", "x0": 0, "x1": 0, "y0": 0, "y1": 51,
                 "line": {"color": ACCENT, "width": 1, "dash": "dot"}}],
    )

    # ── Cumulative Depth ──
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(
        x=m["cum_bq"], y=m["bp"],
        fill="tozerox", fillcolor="rgba(30,144,255,0.15)",
        line={"color": BID_COL, "width": 1.5}, name="Cum Bid",
        hovertemplate="Cum Bid %{x:,}<br>Price %{y:.2f}<extra></extra>",
    ))
    fig_cum.add_trace(go.Scatter(
        x=m["cum_aq"], y=m["ap"],
        fill="tozerox", fillcolor="rgba(204,26,26,0.15)",
        line={"color": ASK_COL, "width": 1.5}, name="Cum Ask",
        hovertemplate="Cum Ask %{x:,}<br>Price %{y:.2f}<extra></extra>",
    ))
    fig_cum.update_layout(
        **TRANSPARENT,
        margin={"l": 50, "r": 10, "t": 10, "b": 30},
        xaxis={**AXIS_STYLE, "title": "Cumulative Qty"},
        yaxis={**AXIS_STYLE, "title": "Price"},
        legend={"font": {"family": "JetBrains Mono", "size": 10, "color": TEXT_DIM},
                "bgcolor": "rgba(0,0,0,0)"},
    )

    # ── Level Imbalance Bar (top 10) ──
    limb = m["level_imb"]
    colors_imb = [BID_COL if v >= 0 else ASK_COL for v in limb]
    fig_imb = go.Figure(go.Bar(
        x=list(range(1, 11)), y=limb,
        marker_color=colors_imb, opacity=0.9,
        hovertemplate="Level %{x}<br>Imbalance %{y:.3f}<extra></extra>",
    ))
    fig_imb.update_layout(
        **TRANSPARENT,
        margin={"l": 30, "r": 10, "t": 10, "b": 30},
        xaxis={**AXIS_STYLE, "title": "Level"},
        yaxis={**AXIS_STYLE, "title": "Imbalance", "range": [-1, 1]},
        shapes=[{"type": "line", "x0": 0, "x1": 11, "y0": 0, "y1": 0,
                 "line": {"color": ACCENT, "width": 1, "dash": "dot"}}],
    )

    # ── Order Count Heatmap ──
    fig_ordn = go.Figure(go.Heatmap(
        z=[list(m["bo"][:10]), list(m["ao"][:10])],
        x=list(range(1, 11)),
        y=["Bid Orders", "Ask Orders"],
        colorscale=[[0, "#0d0f14"], [0.5, "#0a2a4a"], [1, ACCENT]],
        showscale=False,
        hovertemplate="Level %{x}<br>%{y}: %{z}<extra></extra>",
    ))
    fig_ordn.update_layout(
        **TRANSPARENT,
        margin={"l": 80, "r": 10, "t": 10, "b": 30},
        xaxis={**AXIS_STYLE, "title": "Level"},
        yaxis={**AXIS_STYLE},
    )

    # ── Aggregate bars (horizontal) ──
    fig_agg = go.Figure(go.Bar(
        y=["Total Bid", "Total Ask"],
        x=[m["tbq"], m["tsq"]],
        orientation="h",
        marker_color=[BID_COL, ASK_COL],
        opacity=0.9,
        text=[f"{m['tbq']:,}", f"{m['tsq']:,}"],
        textposition="inside",
        textfont={"family": "JetBrains Mono", "size": 12, "color": "#ffffff"},
    ))
    fig_agg.update_layout(
        **TRANSPARENT,
        margin={"l": 70, "r": 20, "t": 10, "b": 20},
        xaxis={**AXIS_STYLE},
        yaxis={**AXIS_STYLE, "tickfont": {"family": "JetBrains Mono", "size": 11, "color": TEXT_MAIN}},
        showlegend=False,
    )

    return kpis + (fig_ladder, fig_cum, fig_imb, fig_ordn, fig_agg)


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False, port=8050)