"""Dashboard: declared assets and Lok Sabha outcomes, 2014 to 2024.

Run from the project folder:  python dashboard.py
Static copy:                  python dashboard.py --static
Needs clean/merged_general_<date>.csv and clean/opencity_results_cleaning_log_<date>.csv.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc

COLLECTION_DATE = "2026-10-20"

def find_project_dir():
    # works from the project folder or from notebooks/
    for folder in [Path.cwd(), Path.cwd().parent]:
        if (folder / "clean").exists():
            return folder
    raise FileNotFoundError("Run this from the project folder or from notebooks/ (a clean/ folder must be next to it)")

clean_dir = find_project_dir() / "clean"
results = pd.read_csv(clean_dir / f"merged_general_{COLLECTION_DATE}.csv")
log = pd.read_csv(clean_dir / f"opencity_results_cleaning_log_{COLLECTION_DATE}.csv")

YEARS = [2014, 2019, 2024]
STATES = sorted(results["State"].unique())

# Local and new parties are few, so they share one group; independents get a short name
results["Party_Group2"] = results["Party_Type"].replace(
    {"Local Party": "Local or new party", "Not in TCPD": "Local or new party", "Independents": "Independent"})

print(results.shape, "| with declared assets:", int(results["Has_Assets"].sum()))
print("states:", STATES)

HIGHLIGHT = "#D55E00"   # the point of the chart: winners, the latest election, the group to notice
INK = "#202124"         # second comparison group, text
GREY = "#BCC0C4"        # context: other candidates, earlier elections
GRID = "#E8EAED"
TEXT = "#3C4043"
FONT = dict(family="Inter, Helvetica, Arial, sans-serif", size=12, color=TEXT)

def style(fig, title, height=400, legend=True):
    fig.update_layout(
        title=dict(text=title, x=0.0, xanchor="left", y=0.97, yanchor="top", font=dict(size=15, color=INK)),
        height=height, margin=dict(l=64, r=24, t=96, b=60), font=FONT,
        paper_bgcolor="white", plot_bgcolor="white", showlegend=legend,
        legend=dict(orientation="h", x=0.0, xanchor="left", y=1.02, yanchor="bottom", bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font_size=12))
    fig.update_xaxes(showgrid=False, linecolor=INK, ticks="outside", tickcolor=INK)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig

# money axis: ticks in lakh and crore (1 lakh = 1e5 rupees, 1 crore = 1e7 rupees)
MONEY = {3: "₹1k", 4: "₹10k", 5: "₹1 lakh", 6: "₹10 lakh", 7: "₹1 crore", 8: "₹10 crore", 9: "₹100 crore", 10: "₹1,000 crore"}

SHORT_MONEY = {5: "₹1L", 7: "₹1Cr", 9: "₹100Cr"}   # for narrow panels (L = lakh, Cr = crore)

def money_ticks(powers, as_log10=False, short=False):
    names = SHORT_MONEY if short else MONEY
    return dict(tickvals=[p if as_log10 else 10.0 ** p for p in powers], ticktext=[names[p] for p in powers])

def fmt_rs(x):
    if x >= 1e9:
        return f"₹{x / 1e7:,.0f} crore"
    if x >= 1e7:
        return f"₹{x / 1e7:,.2f} crore"
    if x >= 1e5:
        return f"₹{x / 1e5:,.1f} lakh"
    return f"₹{x:,.0f}"

def pc(x, digits=1):
    return f"{x:.{digits}f}%"

def message_figure(title, text):
    fig = go.Figure()
    fig.add_annotation(text=text, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=14, color=TEXT))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style(fig, title, legend=False)

CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

def subset(states):
    d = results[results["State"].isin(states)]
    a = d[d["Has_Assets"]].copy()
    a["Pct"] = a.groupby("Election_Year")["Assets_Rs"].rank(pct=True) * 100
    a["Decile"] = np.ceil(a["Pct"] / 10).clip(1, 10).astype(int)
    a["Seat"] = list(zip(a["Election_Year"], a["State"], a["Constituency_No"]))
    return d, a

def fig_distribution(a):
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.03,
                        subplot_titles=[f"{y} (n = {int((a['Election_Year'] == y).sum()):,})" for y in YEARS])
    med = {}
    for i, y in enumerate(YEARS, start=1):
        s = a.loc[a["Election_Year"] == y, "Assets_Rs"]
        med[y] = s.median()
        fig.add_trace(go.Histogram(x=np.log10(s[s > 0]), xbins=dict(start=3, end=10.5, size=0.25),
                                   marker=dict(color="#D0D3D6", line=dict(color="white", width=0.6)),
                                   showlegend=False, hovertemplate="%{y} candidates in this range<extra></extra>"), row=1, col=i)
        fig.add_vline(x=np.log10(med[y]), line=dict(color=HIGHLIGHT, width=3.5), row=1, col=i)
        fig.add_annotation(x=np.log10(med[y]) + 0.12, y=0.99, xref="x" if i == 1 else f"x{i}", yref="paper",
                           text=f"median<br>{fmt_rs(med[y])}", showarrow=False, xanchor="left", yanchor="top",
                           font=dict(color=HIGHLIGHT, size=11))
    fig.update_xaxes(range=[3, 10.5], tickangle=0, **money_ticks([5, 7, 9], as_log10=True, short=True))
    fig.update_xaxes(title_text="Declared total assets (₹, log scale; L = lakh, Cr = crore)", row=1, col=2)
    fig.update_yaxes(title_text="Candidates (count)", range=[0, 470], row=1, col=1)
    style(fig, "Declared assets of candidates, by election", 400, legend=False)
    fig.update_layout(margin=dict(t=100))
    for note in fig.layout.annotations[:3]:
        note.update(font=dict(size=12, color=INK), y=1.03)

    s24 = a.loc[a["Election_Year"] == 2024, "Assets_Rs"]
    nil = int((a["Assets_Rs"] == 0).sum())
    cap = (f"The typical candidate (median, vermilion line) declared {fmt_rs(med[2014])} in 2014 and {fmt_rs(med[2024])} in 2024. "
           f"The spread is huge: {pc((s24 >= 1e7).mean() * 100)} of 2024 candidates declared ₹1 crore or more and the richest declared {fmt_rs(s24.max())}, "
           f"which is why the axis is logarithmic. The {nil} candidates who declared nil cannot be drawn on a log axis.")
    return fig, cap

def fig_gap(a):
    rows = []
    for y in YEARS:
        w = a[(a["Election_Year"] == y) & a["Winner"]]["Assets_Rs"]
        o = a[(a["Election_Year"] == y) & ~a["Winner"]]["Assets_Rs"]
        rows.append(dict(year=str(y), win=w.median(), other=o.median(), n_win=len(w), n_other=len(o)))
    t = pd.DataFrame(rows)
    t["ratio"] = t["win"] / t["other"]

    fig = go.Figure()
    for r in t.itertuples():
        fig.add_trace(go.Scatter(x=[r.other, r.win], y=[r.year, r.year], mode="lines", line=dict(color=GREY, width=4),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t["other"], y=t["year"], mode="markers", name="Other candidates",
                             marker=dict(symbol="circle", size=14, color=GREY, line=dict(color=INK, width=1.3)),
                             customdata=np.c_[t["n_other"], [fmt_rs(v) for v in t["other"]]],
                             hovertemplate="%{y}, other candidates<br>median %{customdata[1]}<br>n = %{customdata[0]:,}<extra></extra>"))
    fig.add_trace(go.Scatter(x=t["win"], y=t["year"], mode="markers+text", name="Winners",
                             marker=dict(symbol="diamond", size=17, color=HIGHLIGHT, line=dict(color=INK, width=1.3)),
                             text=[f"{v:.0f}×" for v in t["ratio"]], textposition="middle right",
                             textfont=dict(size=15, color=INK),
                             customdata=np.c_[t["n_win"], [fmt_rs(v) for v in t["win"]]],
                             hovertemplate="%{y}, winners<br>median %{customdata[1]}<br>n = %{customdata[0]:,}<extra></extra>"))
    fig.update_xaxes(type="log", range=[np.log10(2e5), np.log10(6e9)], showgrid=True, gridcolor=GRID,
                     title_text="Median declared total assets (₹, log scale)", **money_ticks([5, 6, 7, 8, 9]))
    fig.update_yaxes(type="category", autorange="reversed", title_text="Election", showgrid=False)
    style(fig, "Median declared assets: winners and other candidates", 400)

    r = t.set_index("year")
    cap = (f"Winners' median declared assets rose from {fmt_rs(r.loc['2014', 'win'])} in 2014 to {fmt_rs(r.loc['2024', 'win'])} in 2024, "
           f"while other candidates' medians moved from {fmt_rs(r.loc['2014', 'other'])} to {fmt_rs(r.loc['2024', 'other'])}. "
           f"The gap grew from {r.loc['2014', 'ratio']:.0f}× to {r.loc['2024', 'ratio']:.0f}× (nominal rupees, not adjusted for inflation).")
    return fig, cap, r

YEAR_STYLE = {
    2014: dict(color=GREY, symbol="circle", dash="dot", width=2.5, label="bottom right"),
    2019: dict(color=INK, symbol="square", dash="dash", width=2.5, label="bottom right"),
    2024: dict(color=HIGHLIGHT, symbol="diamond", dash="solid", width=4, label="top right"),
}

def fig_decile(a):
    t = (a.groupby(["Election_Year", "Decile"]).agg(wins=("Winner", "sum"), n=("Winner", "size")).reset_index())
    t["rate"] = t["wins"] / t["n"] * 100
    fig = go.Figure()
    for y in YEARS:
        tt = t[t["Election_Year"] == y]
        s = YEAR_STYLE[y]
        labels = [""] * (len(tt) - 1) + [f"{y}: {tt['rate'].iloc[-1]:.0f}%"]
        fig.add_trace(go.Scatter(x=tt["Decile"], y=tt["rate"], mode="lines+markers+text", name=str(y),
                                 line=dict(color=s["color"], width=s["width"], dash=s["dash"]),
                                 marker=dict(symbol=s["symbol"], size=10, color=s["color"], line=dict(color="white", width=1)),
                                 text=labels, textposition=f"{s['label']}", textfont=dict(color=INK, size=12),
                                 customdata=np.c_[tt["wins"], tt["n"]],
                                 hovertemplate="%{x}th tenth: %{y:.1f}% won (%{customdata[0]} of %{customdata[1]})<extra>" + str(y) + "</extra>"))
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 11)), range=[0.7, 12.6],
                     title_text="Declared-assets decile within the election (1 = poorest tenth, 10 = richest tenth)")
    fig.update_yaxes(title_text="Candidates who won (% of the decile)", range=[0, 42], ticksuffix="%")
    style(fig, "Chance of winning, by declared-assets decile", 400)

    top = t[t["Decile"] == 10].set_index("Election_Year")["rate"]
    w24 = t[t["Election_Year"] == 2024]
    low_wins = int(w24.loc[w24["Decile"] <= 5, "wins"].sum())
    all_wins = int(w24["wins"].sum())
    overall = all_wins / w24["n"].sum() * 100
    per_seat = w24["n"].sum() / all_wins
    cap = (f"In 2024, {pc(top[2024])} of candidates in the richest tenth won, up from {pc(top[2014])} in 2014, while only {low_wins} of {all_wins} winners "
           f"came from the poorer half. Overall just {pc(overall)} of candidates win, because each seat has one winner among about {per_seat:.0f} candidates with declared assets.")
    return fig, cap

def fig_seat_rank(a):
    b = a.copy()
    keys = ["Election_Year", "State", "Constituency_No"]
    b["RankSeat"] = b.groupby(keys)["Assets_Rs"].rank(ascending=False, method="min")
    b["NSeat"] = b.groupby(keys)["Assets_Rs"].transform("size")
    w = b[b["Winner"]]
    t = w.groupby("Election_Year").agg(seats=("Winner", "size"),
                                       richest=("RankSeat", lambda s: (s == 1).mean() * 100),
                                       top3=("RankSeat", lambda s: (s <= 3).mean() * 100),
                                       chance1=("NSeat", lambda s: (1 / s).mean() * 100),
                                       chance3=("NSeat", lambda s: (np.minimum(3, s) / s).mean() * 100))
    x = [f"{y}<br>({int(t.loc[y, 'seats'])} seats)" for y in YEARS]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[t.loc[y, "richest"] for y in YEARS], name="Winner was the richest candidate",
                         marker=dict(color=HIGHLIGHT, line=dict(color=INK, width=1)), text=[pc(t.loc[y, "richest"], 0) for y in YEARS],
                         textposition="outside", cliponaxis=False,
                         hovertemplate="%{y:.1f}% of seats<extra>the richest</extra>"))
    fig.add_trace(go.Bar(x=x, y=[t.loc[y, "top3"] for y in YEARS], name="Winner was among the 3 richest",
                         marker=dict(color=GREY, line=dict(color=INK, width=1)), text=[pc(t.loc[y, "top3"], 0) for y in YEARS],
                         textposition="outside", cliponaxis=False,
                         hovertemplate="%{y:.1f}% of seats<extra>among the 3 richest</extra>"))
    fig.update_layout(barmode="group", bargap=0.35)
    fig.update_xaxes(title_text="Election (number of constituencies counted)")
    fig.update_yaxes(title_text="Constituencies (%)", range=[0, 105], ticksuffix="%")
    style(fig, "Was the winner among the richest candidates of the seat?", 400)

    cap = (f"In 2024 the richest candidate won in {pc(t.loc[2024, 'richest'], 0)} of {int(t.loc[2024, 'seats'])} seats and one of the three richest won in {pc(t.loc[2024, 'top3'], 0)}, "
           f"up from {pc(t.loc[2014, 'richest'], 0)} and {pc(t.loc[2014, 'top3'], 0)} in 2014. If assets did not matter, picking at random would give the richest a "
           f"{pc(t.loc[2024, 'chance1'], 0)} chance and the top three {pc(t.loc[2024, 'chance3'], 0)}.")
    return fig, cap, t

def fig_trajectory(a):
    title = "Declared assets of candidates who contested all three elections"
    per = a.pivot_table(index="Person_ID", columns="Election_Year", values="Assets_Rs", aggfunc="first")
    per = per.dropna()
    n_all3 = len(per)
    per = per[(per > 0).all(axis=1)]
    left_out = n_all3 - len(per)
    won = a.groupby("Person_ID")["Winner"].any().reindex(per.index)
    if len(per) < 4 or won.sum() < 2 or (~won).sum() < 2:
        return message_figure(title, "Too few candidates in this selection contested all three elections"), \
               f"Only {len(per)} candidates in this selection have declared assets in all three elections, too few to compare groups.", None

    groups = [("Won at least once", won, HIGHLIGHT, "diamond", "solid"), ("Never won", ~won, INK, "square", "dash")]
    xs = [str(y) for y in YEARS]
    fig = go.Figure()
    stats = {}
    for name, mask, colour, symbol, dash in groups:
        sub = per[mask]
        xline, yline = [], []
        for _, row in sub.iterrows():
            xline += xs + [xs[-1]]
            yline += list(row.values) + [None]
        fig.add_trace(go.Scatter(x=xline, y=yline, mode="lines", line=dict(color=colour, width=1), opacity=0.28,
                                 showlegend=False, hoverinfo="skip", legendgroup=name))
        med = sub.median()
        growth = (sub[2024] / sub[2014]).median()
        stats[name] = dict(n=len(sub), med=med, growth=growth)
        fig.add_trace(go.Scatter(x=xs, y=med.values, mode="lines+markers+text", name=f"{name}, median (n = {len(sub)})", legendgroup=name,
                                 line=dict(color=colour, width=4.5, dash=dash),
                                 marker=dict(symbol=symbol, size=12, color=colour, line=dict(color="white", width=1.5)),
                                 text=["", "", f"×{growth:.1f}"], textposition="middle right", textfont=dict(size=14, color=INK),
                                 customdata=[fmt_rs(v) for v in med.values],
                                 hovertemplate="%{x}: median %{customdata}<extra>" + name + "</extra>"))
    fig.update_xaxes(type="category", range=[-0.3, 2.7], title_text="Election")
    lo = int(np.floor(np.log10(per.values.min())))
    hi = int(np.ceil(np.log10(per.values.max())))
    fig.update_yaxes(type="log", range=[lo - 0.1, hi + 0.1], showgrid=True, gridcolor=GRID,
                     title_text="Declared total assets (₹, log scale)", **money_ticks([p for p in range(max(lo, 3), min(hi, 10) + 1)]))
    style(fig, title, 400)

    s1, s2 = stats["Won at least once"], stats["Never won"]
    cap = (f"{len(per)} candidates declared assets in all three elections; {s1['n']} won at least once. In 2014 their median was {fmt_rs(s1['med'][2014])}, against {fmt_rs(s2['med'][2014])} for those who never won. "
           f"By 2024 the median candidate in each group had grown by ×{s1['growth']:.1f} and ×{s2['growth']:.1f}, so the gap comes from where they started, not from faster growth (nominal rupees{'; ' + str(left_out) + ' with nil assets in some year left out' if left_out else ''}).")
    return fig, cap, stats

def fig_party(a):
    title = "Chance of winning by declared-assets fifth, within party type"
    b = a[a["Party_Group2"].isin(["National Party", "State-based Party"])].copy()
    b["Q"] = np.ceil(b.groupby(["Election_Year", "Party_Group2"])["Assets_Rs"].rank(pct=True) * 5).clip(1, 5).astype(int)
    t = b.groupby(["Party_Group2", "Q"]).agg(wins=("Winner", "sum"), n=("Winner", "size")).reset_index()
    t["rate"] = t["wins"] / t["n"] * 100
    spec = {"National Party": dict(name="National parties", color=INK, symbol="square", dash="dash", label="top right"),
            "State-based Party": dict(name="State-based parties", color=HIGHLIGHT, symbol="diamond", dash="solid", label="bottom right")}
    fig = go.Figure()
    for key, s in spec.items():
        tt = t[t["Party_Group2"] == key]
        if tt.empty:
            continue
        labels = [""] * (len(tt) - 1) + [f"{tt['rate'].iloc[-1]:.0f}%"]
        fig.add_trace(go.Scatter(x=tt["Q"], y=tt["rate"], mode="lines+markers+text", name=f"{s['name']} (n = {int(tt['n'].sum()):,})",
                                 line=dict(color=s["color"], width=4 if key == "State-based Party" else 2.5, dash=s["dash"]),
                                 marker=dict(symbol=s["symbol"], size=11, color=s["color"], line=dict(color="white", width=1)),
                                 text=labels, textposition=s["label"], textfont=dict(color=INK, size=12),
                                 customdata=np.c_[tt["wins"], tt["n"]],
                                 hovertemplate="fifth %{x}: %{y:.1f}% won (%{customdata[0]} of %{customdata[1]})<extra>" + s["name"] + "</extra>"))
    fig.update_xaxes(tickmode="array", tickvals=[1, 2, 3, 4, 5], range=[0.7, 5.8],
                     title_text="Declared-assets fifth within election and party type (1 = poorest, 5 = richest)")
    fig.update_yaxes(title_text="Candidates who won (% of the fifth)", rangemode="tozero", ticksuffix="%")
    style(fig, title, 400)

    sb = t[t["Party_Group2"] == "State-based Party"].set_index("Q")["rate"]
    na = t[t["Party_Group2"] == "National Party"].set_index("Q")["rate"]
    if sb.empty or na.empty:
        return fig, "Not enough candidates of both party types in this selection.", t
    cap = (f"Among state-based parties the win rate climbs from {pc(sb.iloc[0])} in the poorest fifth to {pc(sb.iloc[-1])} in the richest. "
           f"Among national parties it is {pc(na.iloc[0])} in the poorest fifth, peaks at {pc(na.max())} and is {pc(na.iloc[-1])} in the richest, "
           f"so much of the wealth gap in Chart 3 reflects which party gives the ticket (association, not cause).")
    return fig, cap, t

CLEANING_ITEMS = [
    ("Finishing position wrong (NOTA ranked as a candidate)", r"position recomputed", "count"),
    ("Vote counts and vote shares stored as text", r"text to number", "count"),
    ("Candidate names with dots in initials", r"candidate names: has dot", "count"),
    ("Candidate names in mixed case", r"candidate names: not upper case", "count"),
    ("Candidate names with a title (Dr, Adv, ...)", r"candidate names: has title", "count"),
    ("Candidate names with a comma", r"candidate names: has comma", "count"),
    ("Party names with double spaces", r"party names: double spaces", "count"),
    ("Candidate names with double spaces", r"candidate names: double space", "count"),
    ("By-election rows inside general-election rows", r"drop by-election rows", "affected"),
    ("Seats spelled in more than one way", r"one name per seat", "affected"),
]

def fig_cleaning(log):
    rows = []
    for label, pattern, kind in CLEANING_ITEMS:
        part = log[log["step"].str.contains(pattern, regex=True)]
        if part.empty:
            continue
        before = part["count_before"].sum() if kind == "count" else part["rows_affected"].sum()
        after = part["count_after"].sum() if kind == "count" else 0
        rows.append(dict(label=label, before=int(before), after=int(after)))
    t = pd.DataFrame(rows)
    t = t[t["before"] > 0].sort_values("before")

    fig = go.Figure()
    fig.add_trace(go.Bar(y=t["label"], x=t["after"], orientation="h", name="After cleaning",
                         marker=dict(color=INK), text=[f"{v:,}" for v in t["after"]], textposition="outside", cliponaxis=False,
                         hovertemplate="%{y}<br>%{x:,} after<extra></extra>"))
    fig.add_trace(go.Bar(y=t["label"], x=t["before"], orientation="h", name="Before cleaning",
                         marker=dict(color=GREY, line=dict(color=INK, width=1), pattern=dict(shape="/", fgcolor=INK, size=5)),
                         text=[f"{v:,}" for v in t["before"]], textposition="outside", cliponaxis=False,
                         hovertemplate="%{y}<br>%{x:,} before<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.25, legend=dict(traceorder="reversed"))
    fig.update_xaxes(title_text="Problems found in the raw OpenCity results (count of names, cells or rows, three elections)",
                     range=[0, t["before"].max() * 1.15], showgrid=True, gridcolor=GRID)
    fig.update_yaxes(title_text="", automargin=True)
    style(fig, f"Before and after cleaning: {int(t['before'].sum()):,} problems found, {int(t['after'].sum())} left", 520)
    fig.update_layout(margin=dict(l=24, r=40, t=96, b=70), legend=dict(traceorder="reversed"))
    pos = t[t["label"].str.startswith("Finishing position")]
    if len(pos):
        fig.add_annotation(x=int(pos["before"].iloc[0]), y=pos["label"].iloc[0], text="most consequential for winner comparisons",
                           showarrow=False, xanchor="left", xshift=52, yshift=8, font=dict(color=HIGHLIGHT, size=12))

    def value(prefix):
        hit = t[t["label"].str.startswith(prefix)]
        return int(hit["before"].iloc[0]) if len(hit) else 0

    cap = (f"The raw OpenCity results had {int(t['before'].sum()):,} problems of {len(t)} kinds (counts of names, cells or rows); after cleaning {int(t['after'].sum())} remain. "
           f"The most consequential was the finishing position, wrong for {value('Finishing position'):,} candidates in 2014 and 2019 because NOTA (none of the above) was ranked like a candidate. "
           f"The {value('By-election rows'):,} by-election rows stored with the general election made some seats' vote shares add up to 200%.")
    return fig, cap

def kpis(d, a, gap, seat):
    r24 = gap.loc["2024"]
    return {
        "k1": (f"{len(a):,}", f"candidates with declared assets, of {len(d):,} ({pc(len(a) / len(d) * 100)})"),
        "k2": (fmt_rs(r24["win"]), f"median assets of 2024 winners; other candidates: {fmt_rs(r24['other'])}"),
        "k3": (f"{r24['ratio']:.0f}×", f"winners to other candidates, 2024; 2014: {gap.loc['2014', 'ratio']:.0f}×"),
        "k4": (pc(seat.loc[2024, "richest"], 0), f"of 2024 seats were won by the richest candidate; 2014: {pc(seat.loc[2014, 'richest'], 0)}"),
    }

GRAPHS = ["distribution", "gap", "decile", "seat", "trajectory", "party", "cleaning"]
KPIS = ["k1", "k2", "k3", "k4"]
FIG_CLEANING, CAP_CLEANING = fig_cleaning(log)

def build(states):
    states = list(states) if states else list(STATES)
    d, a = subset(states)
    f1, c1 = fig_distribution(a)
    f2, c2, gap = fig_gap(a)
    f3, c3 = fig_decile(a)
    f4, c4, seat = fig_seat_rank(a)
    f5, c5, _ = fig_trajectory(a)
    f6, c6, _ = fig_party(a)
    figs = dict(zip(GRAPHS, [f1, f2, f3, f4, f5, f6, FIG_CLEANING]))
    caps = dict(zip(GRAPHS, [c1, c2, c3, c4, c5, c6, CAP_CLEANING]))
    return figs, caps, kpis(d, a, gap, seat)

CARD = {"border": f"1px solid {GRID}", "borderRadius": "6px"}
CAPTION = {"fontSize": "13px", "color": TEXT, "borderTop": f"1px solid {GRID}", "paddingTop": "10px", "marginTop": "4px", "marginBottom": "0"}

def kpi_card(key):
    return dbc.Card(dbc.CardBody([
        html.H3(id=f"{key}-value", style={"color": HIGHLIGHT, "fontWeight": "700", "marginBottom": "2px"}),
        html.P(id=f"{key}-text", style={"fontSize": "13px", "color": TEXT, "marginBottom": "0"}),
    ]), style=CARD, className="h-100")

def graph_card(key):
    return dbc.Card(dbc.CardBody([
        dcc.Graph(id=f"fig-{key}", config=CONFIG),
        html.P(id=f"cap-{key}", style=CAPTION),
    ]), style=CARD, className="h-100")

NOTES = '''
**Data.** Election results: OpenCity (data.opencity.in); 2014 and 2019 results are credited there to the Trivedi Centre for Political Data (LokDhaba), 2024 results to the Election Commission of India.
Declared assets, age and education: MyNeta (ADR) affidavit summaries. Party names and types: TCPD Party Table (1962 to 2021).

**Read with care.**
- Assets are self-declared in nominal rupees and are not adjusted for inflation, so rupee amounts of different years are not directly comparable; Charts 3, 4 and 6 use ranks within each election for that reason.
- Candidates were linked across sources and elections by name, seat and party; some candidates (4 to 6% each year) have no affidavit match and are left out.
- Everything shown is an association; richer candidates may be given tickets by stronger parties, so these charts do not show that wealth causes wins.

**Tools.** Python, pandas, Plotly, Dash and Dash Bootstrap Components. The cleaning, matching and chart code was written with the help of an AI assistant (Claude) and checked against the data by the team.
'''

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="Declared assets and election outcomes")

app.layout = dbc.Container([
    dbc.Row(dbc.Col([
        html.H1("Declared assets and who wins: Lok Sabha 2014, 2019, 2024", style={"fontWeight": "700", "fontSize": "30px", "marginTop": "18px", "marginBottom": "2px", "color": INK}),
        html.P("Bihar, Maharashtra, Uttar Pradesh and Tamil Nadu: 207 seats per election. How did declared assets change for candidates, winners against the rest?",
               style={"color": TEXT, "marginBottom": "12px"}),
    ], width=12)),
    dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
        html.Span("States (charts 1 to 6 update):", style={"fontWeight": "600", "marginRight": "8px"}),
        dcc.Checklist(id="states", options=[{"label": s, "value": s} for s in STATES], value=STATES, inline=True,
                      inputStyle={"marginRight": "5px", "marginLeft": "18px"}, style={"display": "inline-block"}),
    ], style={"padding": "10px 16px"}), style=CARD), width=12), className="mb-3"),
    dbc.Row([dbc.Col(kpi_card(k), md=3, sm=6) for k in KPIS], className="g-3 mb-3"),
    dbc.Row([dbc.Col(graph_card("distribution"), lg=6), dbc.Col(graph_card("gap"), lg=6)], className="g-3 mb-3"),
    dbc.Row([dbc.Col(graph_card("decile"), lg=6), dbc.Col(graph_card("seat"), lg=6)], className="g-3 mb-3"),
    dbc.Row([dbc.Col(graph_card("trajectory"), lg=6), dbc.Col(graph_card("party"), lg=6)], className="g-3 mb-3"),
    dbc.Row([dbc.Col(graph_card("cleaning"), lg=8),
             dbc.Col(dbc.Card(dbc.CardBody([html.H5("Data, limits and tools", style={"color": INK}), dcc.Markdown(NOTES, style={"fontSize": "13px", "color": TEXT})]),
                              style=CARD, className="h-100"), lg=4)], className="g-3 mb-4"),
], fluid=True, style={"maxWidth": "1500px", "backgroundColor": "#F8F9FA"})

@app.callback(
    [Output(f"fig-{g}", "figure") for g in GRAPHS] + [Output(f"cap-{g}", "children") for g in GRAPHS]
    + [Output(f"{k}-value", "children") for k in KPIS] + [Output(f"{k}-text", "children") for k in KPIS],
    Input("states", "value"))
def update(states):
    figs, caps, cards = build(states)
    return ([figs[g] for g in GRAPHS] + [caps[g] for g in GRAPHS]
            + [cards[k][0] for k in KPIS] + [cards[k][1] for k in KPIS])

def export_static_html(path):
    figs, caps, cards = build(STATES)
    cards_html = "".join(
        f'<div class="col-md-3 col-sm-6"><div class="card h-100" style="border:1px solid {GRID}"><div class="card-body">'
        f'<h3 style="color:{HIGHLIGHT};font-weight:700">{cards[k][0]}</h3><p style="font-size:13px;margin:0">{cards[k][1]}</p></div></div></div>' for k in KPIS)

    def panel(key, width, first=False):
        graph = figs[key].to_html(full_html=False, include_plotlyjs=True if first else False, config=CONFIG)
        return (f'<div class="col-lg-{width}"><div class="card h-100" style="border:1px solid {GRID}"><div class="card-body">{graph}'
                f'<p style="font-size:13px;border-top:1px solid {GRID};padding-top:10px">{caps[key]}</p></div></div></div>')

    rows = [[("distribution", 6, True), ("gap", 6)], [("decile", 6), ("seat", 6)], [("trajectory", 6), ("party", 6)], [("cleaning", 12)]]
    body = "".join('<div class="row g-3 mb-3">' + "".join(panel(*p) for p in row) + "</div>" for row in rows)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Declared assets and election outcomes</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
            f'<style>body{{background:#F8F9FA;color:{TEXT};font-family:Inter,Helvetica,Arial,sans-serif}}</style></head>'
            f'<body><div class="container-fluid" style="max-width:1500px"><h1 style="font-size:30px;font-weight:700;margin-top:18px">Declared assets and who wins: Lok Sabha 2014, 2019, 2024</h1>'
            f'<p>Bihar, Maharashtra, Uttar Pradesh and Tamil Nadu: 207 seats per election. All states selected.</p>'
            f'<div class="row g-3 mb-3">{cards_html}</div>{body}</div></body></html>')
    Path(path).write_text(page, encoding="utf-8")
    return path

if __name__ == "__main__":
    if "--static" in sys.argv:
        print("saved", export_static_html(clean_dir / f"dashboard_static_{COLLECTION_DATE}.html"))
    else:
        app.run(debug=False, port=8050)
