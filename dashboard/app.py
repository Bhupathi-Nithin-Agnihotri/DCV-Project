import os, math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FNAME = "merged_all_2026-10-20.csv"

PATHS = [
    os.environ.get("MERGED_CSV"),
    PROJECT_ROOT / "clean" / FNAME,
    PROJECT_ROOT / FNAME,
]

SRC = next(
    (Path(p) for p in PATHS if p and Path(p).is_file()),
    None
)

if SRC is None:
    raise FileNotFoundError(
        f"Could not find {FNAME}. Checked: {PATHS}"
    )

raw = pd.read_csv(SRC)

df = raw[~raw['Is_ByElection']].copy()          # general elections only
df['Cases'] = df['MN_Criminal_Cases']
df['Result'] = np.where(df['Winner'], 'Winner', 'Loser')

YEARS = [2014, 2019, 2024]
STATES = ['Bihar', 'Maharashtra', 'Tamil Nadu', 'Uttar Pradesh']

# derived columns
# rank of declared assets inside the seat (1 = richest)
df['Asset_Rank'] = df.groupby(['Election_Year', 'State', 'Constituency_No'])['Assets_Rs'].rank(ascending=False, method='min')

CASE_BINS = ['0', '1–2', '3–5', '6+']
df['Case_Bin'] = pd.cut(df['Cases'], [-1, 0, 2, 5, 10_000], labels=CASE_BINS)

EDU = ['Illiterate', 'Literate', '5th Pass', '8th Pass', '10th Pass', '12th Pass',
       'Graduate', 'Graduate Professional', 'Post Graduate', 'Doctorate']
AGE_BINS = ['25–34', '35–44', '45–54', '55–64', '65+']
df['Age_Bin'] = pd.cut(df['MN_Age'].where(df['MN_Age'] >= 25), [24, 34, 44, 54, 64, 120], labels=AGE_BINS)

# consecutive contests by the same person (Person_ID links names across years)
rows = []
for pid, gr in df.dropna(subset=['Person_ID']).sort_values('Election_Year').groupby('Person_ID'):
    recs = gr.drop_duplicates('Election_Year').to_dict('records')
    for a, b in zip(recs, recs[1:]):
        if b['Election_Year'] - a['Election_Year'] != 5:
            continue
        rows.append({'Person_ID': pid, 'State': b['State'], 'Name': b['Candidate'], 'Party': b['Party'],
                     'Year': b['Election_Year'], 'A0': a['Assets_Rs'], 'A1': b['Assets_Rs'],
                     'Move': ('Won' if a['Winner'] else 'Lost') + ' → ' + ('Won' if b['Winner'] else 'Lost'),
                     'dVote': b['Vote_Share_Percentage'] - a['Vote_Share_Percentage']})
pairs = pd.DataFrame(rows)
pairs = pairs[(pairs.A0 > 0) & (pairs.A1 > 0)].copy()
pairs['Ratio'] = pairs.A1 / pairs.A0
MOVES = ['Won → Won', 'Won → Lost', 'Lost → Won', 'Lost → Lost']

# people with an asset figure in 2+ elections, for the candidate picker
repeat = (df[df.Assets_Rs > 0].dropna(subset=['Person_ID'])
          .groupby('Person_ID').filter(lambda g: g.Election_Year.nunique() >= 2))
PEOPLE = (repeat.sort_values('Election_Year').groupby('Person_ID')
          .agg(Name=('Candidate', 'last'), State=('State', 'last'), Max=('Assets_Rs', 'max'))
          .sort_values('Max', ascending=False))

# theme

BG, CARD, GRID, INK, INK2 = '#000000', '#0e0e0e', '#232323', '#ffffff', '#b8b8b8'
WIN, LOSE, GREY, RED = '#c98500', '#3987e5', '#5a5e69', '#e66767'
STATE_C = {'Bihar': '#d95926', 'Maharashtra': '#199e70', 'Tamil Nadu': '#9085e9', 'Uttar Pradesh': '#d55181'}
MOVE_C = {'Won → Won': WIN, 'Won → Lost': '#d95926', 'Lost → Won': '#199e70', 'Lost → Lost': LOSE}
RUPEE_TICKS = dict(tickvals=[3, 4, 5, 6, 7, 8, 9, 10],
                   ticktext=['₹1k', '₹10k', '₹1 lakh', '₹10 lakh', '₹1 cr', '₹10 cr', '₹100 cr', '₹1000 cr'])


def cr(v):
    """Rupees -> '₹9.37 cr' or '₹28 lakh'."""
    if v is None or pd.isna(v):
        return '–'
    return f'₹{v/1e7:.2f} cr' if v >= 1e7 else f'₹{v/1e5:.0f} lakh'


def style(fig, h=420, legend=True):
    fig.update_layout(template='plotly_dark', height=h, showlegend=legend,
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Helvetica Neue, Arial, sans-serif', size=14, color=INK),
                      margin=dict(l=60, r=24, t=30, b=50),
                      legend=dict(orientation='h', x=0, y=1.12, bgcolor='rgba(0,0,0,0)'),
                      hoverlabel=dict(bgcolor='#1c1c1c', font_size=13), uniformtext=dict(minsize=12, mode='show'))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, fixedrange=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, fixedrange=True)
    return fig


def graph(fig, gid=None):
    kw = {'id': gid} if gid else {}
    return dcc.Graph(figure=fig, config={'displayModeBar': False}, **kw)


def card(title, body, caption='', md=6, cap_id=None):
    """Bold title, a plot (or any component), and a 1–2 line bold caption (cap_id lets a callback change it)."""
    if isinstance(body, go.Figure):
        body = graph(body)
    return dbc.Col(dbc.Card(dbc.CardBody([
        html.H4(title, className='card-title fw-bold'),
        body,
        dcc.Markdown(caption, className='cap', **({'id': cap_id} if cap_id else {})),
    ]), className='chart-card h-100'), md=md, className='mb-4')


def section(title):
    return html.H2(title, className='section')


def kpi(value, label, color):
    return dbc.Col(dbc.Card(dbc.CardBody([
        html.Div(value, className='metric-value'),
        html.Div(label, className='metric-label'),
    ]), className='metric-card'), md=3, xs=6, className='mb-4')


def bar_text(fig):
    fig.update_traces(textposition='outside', cliponaxis=False, textfont_size=15)
    return fig

# figures
# pick the states, return all rows, rows with assets, and repeat pairs
def filt(states):
    s = states or STATES
    g = df[df.State.isin(s)]
    return g, g[g.Assets_Rs > 0], pairs[pairs.State.isin(s)]


# median assets per group
def medians(a, by):
    return a.groupby(by)['Assets_Rs'].median()

# ---------------- Overview ----------------
def tab_overview(states):
    g, a, p = filt(states)
    # median assets per year, winners vs losers, and how many times richer winners are
    m = a.groupby(['Election_Year', 'Winner'])['Assets_Rs'].median().unstack()
    gap = (m[True] / m[False]).round(1)
    grew = (p.Ratio > 1).mean() * 100

    # line plot of the two medians
    f1 = go.Figure()
    for w, name, c, pos in [(True, 'Winners', WIN, 'top center'), (False, 'Losers', LOSE, 'bottom center')]:
        f1.add_scatter(x=YEARS, y=m[w].values, name=name, mode='lines+markers+text', line=dict(color=c, width=3),
                       marker_size=11, text=[cr(v) for v in m[w]], textposition=pos, textfont_size=14,
                       hovertemplate='%{x}: %{text}<extra>' + name + '</extra>')
    style(f1).update_yaxes(type='log', tickvals=[1e6, 3e6, 1e7, 3e7, 1e8, 3e8],
                           ticktext=['₹10 lakh', '₹30 lakh', '₹1 cr', '₹3 cr', '₹10 cr', '₹30 cr'])
    f1.update_xaxes(tickvals=YEARS, range=[2012.5, 2025.5])

    # bar plot of the gap
    f2 = go.Figure(go.Bar(x=[str(y) for y in YEARS], y=gap.values, marker_color=WIN, width=0.5,
                          text=[f'{v}×' for v in gap], hovertemplate='%{x}: %{y}×<extra></extra>'))
    bar_text(style(f2, legend=False)).update_yaxes(range=[0, gap.max() * 1.25], ticksuffix='×', title='Median winner ÷ median loser')
    f2.update_xaxes(title='Election year')
    f1.update_xaxes(title='Election year')
    f1.update_yaxes(title='Median declared assets (log scale)')

    # page layout: title, kpi cards, plots
    return [
        html.H1('Do winners get richer, or do the rich win?', className='page-title'),
        html.P([f'{len(g):,} candidates in {g.groupby(["State","Constituency_No"]).ngroups} seats, matched to their sworn asset declarations. '
                f'The median winner went from ', html.B(f'{gap.iloc[0]}×'), ' to ', html.B(f'{gap.iloc[-1]}×'),
                ' the median loser in ten years.'], className='lead-text'),
        dbc.Row([kpi(cr(m.loc[2024, True]), 'Median 2024 winner', WIN),
                 kpi(cr(m.loc[2024, False]), 'Median 2024 loser', LOSE),
                 kpi(f'{gap.loc[2024]}×', 'Winner–loser gap, 2024', WIN),
                 kpi(f'{grew:.0f}%', 'Repeat candidates who got richer', INK)]),
        dbc.Row([
            card('Median declared assets, by election', f1,
                 f'The typical winner declared **{cr(m.loc[2014, True])}** in 2014 and **{cr(m.loc[2024, True])}** in 2024. '
                 f'The typical loser only went from **{cr(m.loc[2014, False])}** to **{cr(m.loc[2024, False])}**.'),
            card('How many times richer is the median winner?', f2,
                 f'In 2014 the typical winner had **{gap.iloc[0]} times** the assets of the typical loser. '
                 f'By 2024 this had grown to **{gap.iloc[-1]} times**.'),
        ]),
    ]

# ---------------- Winners vs Losers ----------------
# histogram bins on log10 assets (10^3 to 10^10.5 rupees)
EDGES = np.arange(3.0, 10.51, 0.25)

def fig_hist(a, year):
    if year != 'All':
        a = a[a.Election_Year == int(year)]
    f = go.Figure()
    peaks = {}
    # count each group into the bins, as % of that group
    for w, name, c in [(False, 'Losers', LOSE), (True, 'Winners', WIN)]:
        v = np.log10(a[a.Winner == w].Assets_Rs).clip(EDGES[0], EDGES[-1] - 1e-9)
        cnt, _ = np.histogram(v, EDGES)
        pct = 100 * cnt / max(cnt.sum(), 1)
        mid = (EDGES[:-1] + EDGES[1:]) / 2
        peaks[w] = 10 ** mid[pct.argmax()]
        f.add_bar(x=mid, y=pct, width=0.23, name=f'{name} ({cnt.sum():,})', marker_color=c, opacity=0.8,
                  customdata=[f'{cr(10**(m-0.125))} – {cr(10**(m+0.125))}' for m in mid],
                  hovertemplate='%{customdata}<br>%{y:.1f}% of ' + name.lower() + '<extra></extra>')
    style(f).update_layout(barmode='overlay')
    # fixed ranges: hiding a group in the legend does not rescale the axes
    f.update_xaxes(range=[3, 10.5], autorange=False, **RUPEE_TICKS)
    f.update_yaxes(range=[0, 22], autorange=False, ticksuffix='%', title='% of group')
    f.update_xaxes(title='Declared assets (log scale)')
    return f, peaks


def tab_wl(states):
    g, a, p = filt(states)
    f_hist, peaks = fig_hist(a, 'All')

    # box plot per year, winners vs losers
    f_box = go.Figure()
    for w, name, c in [(True, 'Winners', WIN), (False, 'Losers', LOSE)]:
        s = a[a.Winner == w]
        f_box.add_box(x=s.Election_Year.astype(str), y=s.Assets_Rs, name=name, marker=dict(color=c, size=3, opacity=0.35),
                      line=dict(color=c, width=2), fillcolor=c + '33', boxpoints='outliers')
    style(f_box).update_layout(boxmode='group')
    f_box.update_yaxes(type='log', range=[3, 10.6], tickvals=[10 ** v for v in RUPEE_TICKS['tickvals']], ticktext=RUPEE_TICKS['ticktext'])
    f_box.update_xaxes(title='Election year')
    f_box.update_yaxes(title='Declared assets (log scale)')
    # numbers for the caption
    q1w = a[a.Winner].groupby('Election_Year').Assets_Rs.quantile(0.25)
    medl = a[~a.Winner].groupby('Election_Year').Assets_Rs.median()

    return [
        html.H1('Winners vs Losers', className='page-title'),
        section('The wealth gap'),
        dbc.Row([
            card('Where candidates sit on the wealth scale', html.Div([
                dbc.RadioItems(id='hist-year', options=['All'] + [str(y) for y in YEARS], value='All', inline=True, className='mb-2'),
                graph(f_hist, 'hist-graph')]),
                f'Most losers declared around **{cr(peaks[False])}**, most winners around **{cr(peaks[True])}**.'),
            card('Spread of assets in each election', f_box,
                 f'Each box holds the middle half of the candidates and the line inside is the typical one. '
                 f'Even the poorest quarter of 2024 winners (**{cr(q1w.loc[2024])}** and up) had more than the typical loser (**{cr(medl.loc[2024])}**).'),
        ]),
    ]

# ---------------- States & seats ----------------
def state_lines(a, w, unit, scale):
    # median per state per year, one line per state
    m = a[a.Winner == w].groupby(['State', 'Election_Year']).Assets_Rs.median().unstack() / scale
    f = go.Figure()
    for s in m.index:
        f.add_scatter(x=YEARS, y=m.loc[s].values, name=s, mode='lines+markers', line=dict(color=STATE_C[s], width=3), marker_size=10,
                      hovertemplate=f'{s} %{{x}}: ₹%{{y:.2f}} {unit}<extra></extra>')
    # end labels, nudged apart so they never overlap
    ends = m[2024].sort_values()
    top = m.max().max() * 1.12
    pos, last = [], -1e9
    for v in ends:
        last = max(v, last + top * 0.06)
        pos.append(last)
    for (s, v), y in zip(ends.items(), pos):
        f.add_annotation(x=2024, y=y, xanchor='left', xshift=10, showarrow=False, text=f'₹{v:.1f} {unit}', font_size=13)
    style(f).update_xaxes(tickvals=YEARS, range=[2013, 2026.6])
    f.update_yaxes(range=[0, max(pos[-1], top) * 1.05], title='Median declared assets (₹ crore)' if unit == 'cr' else 'Median declared assets (₹ lakh)')
    f.update_xaxes(title='Election year')
    return f, m


def tab_states(states):
    g, a, p = filt(states)
    f_w, mw = state_lines(a, True, 'cr', 1e7)
    f_l, ml = state_lines(a, False, 'L', 1e5)

    # general vs reserved seats
    t = a.groupby(['Constituency_Type', 'Winner']).Assets_Rs.median().unstack().reindex(['GEN', 'SC', 'ST']).dropna()
    f_t = go.Figure()
    for w, name, c in [(True, 'Winners', WIN), (False, 'Losers', LOSE)]:
        f_t.add_bar(x=t.index, y=t[w] / 1e7, name=name, marker_color=c, text=[cr(v) for v in t[w]],
                    hovertemplate='%{x}: ₹%{y:.2f} cr<extra>' + name + '</extra>')
    bar_text(style(f_t, h=520)).update_layout(barmode='group', bargap=0.3)
    f_t.update_yaxes(title='Median assets (₹ crore)', range=[0, t.max().max() / 1e7 * 1.25])
    f_t.update_xaxes(title='Seat type (GEN = general, SC/ST = reserved)')

    return [
        html.H1('States & Seats', className='page-title'),
        section('By state'),
        dbc.Row([
            card('Median winner, by state (₹ crore)', f_w,
                 f'In 2024 the typical winner in **{mw[2024].idxmax()}** declared **₹{mw[2024].max():.2f} cr**, the most of the four states. '
                 f'**{mw[2024].idxmin()}** was lowest at **₹{mw[2024].min():.2f} cr**.'),
            card('Median loser, by state (₹ lakh)', f_l,
                 f'Losers declare lakhs, not crores. In 2024 the typical loser had **₹{ml[2024].max():.1f} lakh** in **{ml[2024].idxmax()}** '
                 f'and **₹{ml[2024].min():.1f} lakh** in **{ml[2024].idxmin()}**.'),
        ]),
        section('Seat types'),
        dbc.Row([
            card('Reserved (SC/ST) vs general seats', f_t,
                 'SC and ST seats can only be contested by Scheduled Caste or Scheduled Tribe candidates. '
                 f'The typical winner declared **{cr(t.loc["GEN", True])}** in general seats and **{cr(t.loc["SC", True])}** in SC seats.'
                 + (f' In ST seats it was **{cr(t.loc["ST", True])}**.' if 'ST' in t.index else ''), md=12),
        ]),
    ]

# ---------------- Parties ----------------
def fig_dumbbell(a, year):
    # median winner vs median loser for each party, one year or all
    if year != 'All':
        a = a[a.Election_Year == int(year)]
    # median and count per party, winners vs losers
    t = a[~a.Party.isin(['IND', 'OTHER'])].groupby(['Party', 'Winner']).Assets_Rs.agg(['median', 'size']).unstack()
    t = t[(t[('size', True)] >= 3) & (t[('size', False)] >= 3)]   # 3+ winners and 3+ losers
    d = pd.DataFrame({'medW': t[('median', True)], 'medL': t[('median', False)], 'nW': t[('size', True)], 'nL': t[('size', False)]})
    d['ratio'] = d.medW / d.medL
    # biggest difference on top: how many times apart the two medians are, either way
    d = d.assign(diff=np.maximum(d.ratio, 1 / d.ratio)).sort_values('diff')
    labels = [f'{p}  ({int(r.nW)} W / {int(r.nL)} L)' for p, r in d.iterrows()]

    f = go.Figure()
    # line between the two dots: amber if winners are richer, blue if losers are
    for lab, (party, r) in zip(labels, d.iterrows()):
        f.add_scatter(x=[r.medL / 1e7, r.medW / 1e7], y=[lab] * 2, mode='lines', showlegend=False, hoverinfo='skip',
                      line=dict(color=WIN if r.ratio >= 1 else LOSE, width=4))
    f.add_scatter(x=d.medL / 1e7, y=labels, mode='markers', name='Median loser', marker=dict(color=LOSE, size=15, symbol='circle'),
                  hovertemplate='%{y}<br>median loser: ₹%{x:.2f} cr<extra></extra>')
    f.add_scatter(x=d.medW / 1e7, y=labels, mode='markers', name='Median winner', marker=dict(color=WIN, size=15, symbol='diamond'),
                  hovertemplate='%{y}<br>median winner: ₹%{x:.2f} cr<extra></extra>')
    # how many times apart, written at the right end of each row
    for lab, (party, r) in zip(labels, d.iterrows()):
        txt = f'winners {r.ratio:.1f}× richer' if r.ratio >= 1 else f'losers {1 / r.ratio:.1f}× richer'
        f.add_annotation(x=np.log10(max(r.medW, r.medL) / 1e7), y=lab, xshift=14, xanchor='left', showarrow=False,
                         text=txt, font=dict(size=14, color=WIN if r.ratio >= 1 else LOSE))
    style(f, h=max(420, 48 * len(d) + 120)).update_xaxes(type='log', title='Median declared assets (₹ crore, log scale)',
                                                       tickvals=[0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100],
                                                       ticktext=['₹1 lakh', '₹3 lakh', '₹10 lakh', '₹30 lakh', '₹1 cr', '₹3 cr', '₹10 cr', '₹30 cr', '₹100 cr'],
                                                       range=[-2.2, 2.6])
    f.update_yaxes(title='Party (winners / losers counted)', tickfont_size=14)
    return f, d


def tab_parties(states):
    g, a, p = filt(states)
    f_db, d = fig_dumbbell(a, 'All')
    top = d.index[-1]
    return [
        html.H1('Parties', className='page-title'),
        dbc.Row([
            card('Winners vs losers inside each party', html.Div([
                dbc.Select(id='party-year', options=[{'label': 'All years', 'value': 'All'}] + [{'label': str(y), 'value': str(y)} for y in YEARS],
                           value='All', className='mb-2'),
                graph(f_db, 'db-graph')]),
                f'Each row is a party with at least 3 winners and 3 losers, and the biggest gaps are at the top. '
                f'In **{top}** the typical winner had **{d.loc[top, "ratio"]:.1f} times** the assets of its typical loser. Winners were richer in **{(d.ratio > 1).sum()} of {len(d)}** parties. '
                'BJP and ADMK flip only when all years are mixed together.', md=12),
        ]),
    ]


# ---------------- Same candidates ----------------
# one person's assets over the years, dot colour = won or lost
def fig_person(pid):
    s = df[(df.Person_ID == pid) & (df.Assets_Rs > 0)].sort_values('Election_Year')
    f = go.Figure(go.Scatter(x=s.Election_Year, y=s.Assets_Rs / 1e7, mode='lines+markers+text',
                             line=dict(color=INK2, width=2), marker=dict(size=16, color=[WIN if w else LOSE for w in s.Winner],
                                                                         line=dict(width=2, color=CARD)),
                             text=[f'{cr(v)} · {"Won" if w else "Lost"} ({pa})' for v, w, pa in zip(s.Assets_Rs, s.Winner, s.Party)],
                             textposition='top center', hovertemplate='%{x}: %{text}<extra></extra>', showlegend=False))
    # legend only: one dot for won, one for lost
    f.add_scatter(x=[None], y=[None], mode='markers', name='Won', marker=dict(size=14, color=WIN))
    f.add_scatter(x=[None], y=[None], mode='markers', name='Lost', marker=dict(size=14, color=LOSE))
    style(f).update_xaxes(tickvals=YEARS, range=[2012, 2026], title='Election year')
    f.update_yaxes(title='Declared assets (₹ crore)', rangemode='tozero', range=[0, s.Assets_Rs.max() / 1e7 * 1.3])
    return f


PERIODS = ['2014 → 2019', '2019 → 2024', '2014 → 2024']


# assets of the same person in two elections, and the change between them
def seat_changes(g):
    # same person in two elections, winner/loser = result at the first one
    p = g.dropna(subset=['Person_ID']).drop_duplicates(['Person_ID', 'Election_Year'])
    out = []
    for y0, y1 in [(2014, 2019), (2019, 2024), (2014, 2024)]:
        first = p[p.Election_Year == y0][['Person_ID', 'State', 'Constituency_No', 'Winner', 'Assets_Rs']]
        later = p[p.Election_Year == y1][['Person_ID', 'Assets_Rs']]
        out.append(first.merge(later, on='Person_ID', suffixes=('_0', '_1')).assign(Period=f'{y0} → {y1}'))
    m = pd.concat(out)
    m = m[(m.Assets_Rs_0 > 0) & (m.Assets_Rs_1 > 0)].copy()
    m['Gain'] = (m.Assets_Rs_1 - m.Assets_Rs_0) / 1e7   # change in crore
    return m


# histogram of asset change for one period, winners vs losers
def fig_change(period, states=None):
    m = seat_changes(filt(states)[0])
    m = m[m.Period == period]
    f = go.Figure()
    for w, name, c in [(False, 'Losers', LOSE), (True, 'Winners', WIN)]:
        v = m[m.Winner == w].Gain.clip(-10, 29.99)   # long tails pile into the end bins
        f.add_histogram(x=v, name=f'{name} ({len(v)})', marker_color=c, opacity=0.75, histnorm='percent',
                        xbins=dict(start=-10, end=30.01, size=1), hovertemplate='%{x} cr: %{y:.1f}%<extra>' + name + '</extra>')
    style(f, h=470).update_layout(barmode='overlay')
    f.add_vline(x=0, line=dict(color='#8a8d96', dash='dash', width=1.5))
    f.update_xaxes(range=[-10.5, 30.5], autorange=False, title=f'Change in declared assets, {period} (₹ crore)')
    f.update_yaxes(title='% of the group', ticksuffix='%', range=[0, 60], autorange=False)   # fixed, so periods compare
    med = m.groupby('Winner').Gain.median()
    cap = (f'Same people, two elections. Between {period.replace(" → ", " and ")} the typical winner gained **₹{med[True]:.2f} cr** and the typical loser **₹{med[False]:.2f} cr**. '
           'Winner or loser means the result at the first election. Changes beyond −10 or 30 crore are counted in the end bars.')
    return f, cap


# histogram of % change in assets for one period, winners vs losers
def fig_pct(period, states=None):
    m = seat_changes(filt(states)[0])
    m = m[m.Period == period]
    f = go.Figure()
    for w, name, c in [(False, 'Losers', LOSE), (True, 'Winners', WIN)]:
        s = m[m.Winner == w]
        v = (100 * (s.Assets_Rs_1 / s.Assets_Rs_0 - 1)).clip(-100, 499.9)   # growth past 500% piles into the last bar
        f.add_histogram(x=v, name=f'{name} ({len(v)})', marker_color=c, opacity=0.75, histnorm='percent',
                        xbins=dict(start=-100, end=500.01, size=25), hovertemplate='%{x}%: %{y:.1f}% of ' + name.lower() + '<extra></extra>')
    style(f, h=470).update_layout(barmode='overlay')
    f.add_vline(x=0, line=dict(color='#8a8d96', dash='dash', width=1.5))
    f.update_xaxes(range=[-105, 505], autorange=False, ticksuffix='%', title=f'Change in declared assets, {period} (%)')
    f.update_yaxes(title='% of the group', ticksuffix='%', range=[0, 30], autorange=False)   # fixed, so periods compare
    med = (100 * (m.Assets_Rs_1 / m.Assets_Rs_0 - 1)).groupby(m.Winner).median()
    cap = (f'Between {period.replace(" → ", " and ")} the typical winner\'s assets grew **{med[True]:.0f}%** and the typical loser\'s **{med[False]:.0f}%**. '
           'Losers start with much less, so the same % is far fewer rupees. Growth above 500% is counted in the last bar.')
    return f, cap


def tab_same(states):
    g, a, p = filt(states)
    m = seat_changes(g)
    res = np.where(m.Winner, 'Winners', 'Losers')

    # median change in crore and median % change, per period
    gain = m.groupby(['Period', res]).Gain.median().unstack()
    f_m = go.Figure()
    for r, c in [('Winners', WIN), ('Losers', LOSE)]:
        f_m.add_bar(x=PERIODS, y=gain.loc[PERIODS, r], name=r, marker_color=c, text=[f'₹{v:.2f} cr' for v in gain.loc[PERIODS, r]])
    bar_text(style(f_m, h=470)).update_layout(barmode='group', bargap=0.3)
    f_m.update_yaxes(range=[0, gain.max().max() * 1.25], title='Median change in declared assets (₹ crore)')
    f_m.update_xaxes(title='Between the declarations of')

    # people who ran in all three elections, grouped by how many times they won
    three = g[g.Person_ID.map(g.dropna(subset=['Person_ID']).groupby('Person_ID').Election_Year.nunique()) == 3]
    wins = three.groupby('Person_ID').Winner.sum()
    grp = wins.map(lambda k: 'Won all 3' if k == 3 else ('Never won' if k == 0 else 'Won 1 or 2'))
    three = three.assign(G=three.Person_ID.map(grp))
    t3 = three[three.Assets_Rs > 0].groupby(['G', 'Election_Year']).Assets_Rs.median().unstack()
    f3 = go.Figure()
    for k, c, pos in [('Won all 3', WIN, 'top center'), ('Won 1 or 2', '#199e70', 'bottom center'), ('Never won', LOSE, 'top center')]:
        if k not in t3.index:
            continue
        f3.add_scatter(x=YEARS, y=t3.loc[k].values / 1e7, name=f'{k} ({(grp == k).sum()})', mode='lines+markers+text', line=dict(color=c, width=3),
                       marker_size=11, text=[cr(v) if (i == 2 or (i == 0 and k != 'Won 1 or 2')) else '' for i, v in enumerate(t3.loc[k])], textposition=pos, textfont_size=13,
                       hovertemplate=k + ' %{x}: ₹%{y:.2f} cr<extra></extra>')
    style(f3, h=470).update_yaxes(type='log', tickvals=[0.1, 0.3, 1, 3, 10, 30], ticktext=['₹10 lakh', '₹30 lakh', '₹1 cr', '₹3 cr', '₹10 cr', '₹30 cr'])
    f3.update_xaxes(tickvals=YEARS, range=[2012.5, 2025.5], title='Election year')
    f3.update_yaxes(title='Median declared assets (log scale)')

    # the two period histograms and their captions
    f_ch, cap_ch = fig_change(PERIODS[0], states)
    f_pc, cap_pc = fig_pct(PERIODS[0], states)

    # dropdown list of people, richest first
    opts = [{'label': f'{r.Name.title()} ({r.State})', 'value': str(pid)} for pid, r in PEOPLE[PEOPLE.State.isin(states or STATES)].iterrows()]
    first = opts[0]['value']
    cap3 = ''
    if {'Won all 3', 'Never won'} <= set(t3.index):
        cap3 = (f'**{len(grp)}** people stood in all three elections. Those who won every time went from **{cr(t3.loc["Won all 3", 2014])}** to **{cr(t3.loc["Won all 3", 2024])}**. '
                f'Those who never won went from **{cr(t3.loc["Never won", 2014])}** to **{cr(t3.loc["Never won", 2024])}**.')
    return [
        html.H1('Same Candidates Over Time', className='page-title'),
        section('Did they get richer?'),
        dbc.Row([
            card('How much did their assets change?', html.Div([
                dbc.Select(id='change-period', options=[{'label': x, 'value': x} for x in PERIODS], value=PERIODS[0], className='mb-2'),
                graph(f_ch, 'change-graph')]), cap_ch, cap_id='change-cap'),
            card('How much did their assets grow, in %?', html.Div([
                dbc.Select(id='pct-period', options=[{'label': x, 'value': x} for x in PERIODS], value=PERIODS[0], className='mb-2'),
                graph(f_pc, 'pct-graph')]), cap_pc, cap_id='pct-cap'),
        ]),
        section('How much richer?'),
        dbc.Row([
            card('Median change in assets, winners vs losers', f_m,
                 f'Between 2019 and 2024 the typical winner added **₹{gain.loc["2019 → 2024", "Winners"]:.2f} cr** to their assets. '
                 f'The typical loser added **₹{gain.loc["2019 → 2024", "Losers"]:.2f} cr**.'),
            card('People who ran all three times', f3, cap3),
        ]),
        section('Look up a candidate'),
        dbc.Row([
            card('One person across elections', html.Div([
                dbc.Select(id='person-pick', options=opts, value=first, className='mb-2'),
                graph(fig_person(float(first)), 'person-graph')]),
                'Declared assets of one candidate at each election they contested, with richer candidates listed first.', md=12),
        ]),
    ]

# ---------------- Criminal cases ----------------
def tab_crime(states):
    g, a, p = filt(states)
    c = g[g.Cases.notna()]

    # win rate by number of cases, all vs main parties
    win_all = c.groupby('Case_Bin', observed=True).Winner.mean() * 100
    win_main = c[c.Party_Group == 'Main party'].groupby('Case_Bin', observed=True).Winner.mean() * 100
    f_w = go.Figure()
    f_w.add_bar(x=CASE_BINS, y=win_all.values, name='All candidates', marker_color=GREY, text=[f'{v:.1f}%' for v in win_all])
    f_w.add_bar(x=CASE_BINS, y=win_main.values, name='Main-party candidates', marker_color=RED, text=[f'{v:.1f}%' for v in win_main])
    bar_text(style(f_w)).update_layout(barmode='group', bargap=0.3)
    f_w.update_xaxes(type='category', title='Declared criminal cases')
    f_w.update_yaxes(range=[0, max(win_main.max(), win_all.max()) * 1.2], ticksuffix='%', title='Candidates who won (%)')

    # assets by number of cases, violin per bucket
    ca = c[c.Assets_Rs > 0]
    medc = ca.groupby('Case_Bin', observed=True).Assets_Rs.median()
    f_v = go.Figure()
    for b in CASE_BINS:
        s = np.log10(ca[ca.Case_Bin == b].Assets_Rs)
        f_v.add_violin(x=[f'{b} cases'] * len(s), y=s, line_color=RED, fillcolor=RED + '44', points=False,
                       box=dict(visible=True, width=0.18, fillcolor=BG, line_color=INK), spanmode='hard', bandwidth=0.15, hoverinfo='skip')
        f_v.add_annotation(x=f'{b} cases', y=10.3, yanchor='top', showarrow=False, text=f'median {cr(medc[b])}', font_size=13)
    style(f_v, legend=False).update_yaxes(range=[4, 10.3], autorange=False, tickvals=[5, 6, 7, 8, 9, 10],
                                          ticktext=['₹1 lakh', '₹10 lakh', '₹1 cr', '₹10 cr', '₹100 cr', '₹1000 cr'])

    f_v.update_xaxes(title='Declared criminal cases')
    f_v.update_yaxes(title='Declared assets (log scale)')

    # average cases per year, winners vs losers
    av = c.groupby(['Election_Year', 'Winner']).Cases.mean().unstack()
    anyc = c.groupby(['Election_Year', 'Winner']).Cases.apply(lambda s: 100 * (s > 0).mean()).unstack()
    f_a = go.Figure()
    for w, name, col in [(True, 'Winners', WIN), (False, 'Losers', LOSE)]:
        f_a.add_bar(x=[str(y) for y in YEARS], y=av[w].values, name=name, marker_color=col, text=[f'{v:.1f}' for v in av[w]],
                    customdata=anyc[w].values, hovertemplate='%{x}: %{y:.2f} cases<br>%{customdata:.0f}% have at least one<extra>' + name + '</extra>')
    bar_text(style(f_a)).update_layout(barmode='group', bargap=0.35)
    f_a.update_yaxes(title='Cases per candidate', range=[0, av.max().max() * 1.25])
    f_a.update_xaxes(title='Election year')

    # share of candidates with a case, parties with 40+ candidates
    big = c.Party.value_counts()
    big = big[(big >= 40) & ~big.index.isin(['IND', 'OTHER'])].index
    sh = (c[c.Party.isin(big)].groupby('Party').Cases.apply(lambda s: 100 * (s > 0).mean()).sort_values())
    f_p = go.Figure(go.Bar(y=sh.index, x=sh.values, orientation='h', marker_color=[RED if v >= 50 else GREY for v in sh],
                           text=[f'{v:.0f}%' for v in sh], hovertemplate='%{y}: %{x:.0f}% declared a case<extra></extra>', showlegend=False))
    # legend only: what the two bar colours mean
    f_p.add_bar(x=[None], y=[None], name='Half or more declared a case', marker_color=RED)
    f_p.add_bar(x=[None], y=[None], name='Less than half', marker_color=GREY)
    bar_text(style(f_p)).update_xaxes(range=[0, 100], ticksuffix='%', title='Candidates with at least one case (%)')
    f_p.update_yaxes(title='Party', dtick=1)   # show every party name
    ind = 100 * (c[c.Party == 'IND'].Cases > 0).mean()

    return [
        html.H1('Criminal Cases', className='page-title'),
        section('Cases and winning'),
        dbc.Row([
            card('Criminal cases vs win rate', f_w,
                 f'**{win_all["6+"]:.1f}%** of candidates with 6 or more cases won, against **{win_all["0"]:.1f}%** of those with none. '
                 'The same pattern shows up for main-party candidates.'),
            card('Average criminal cases: winners vs losers', f_a,
                 f'In 2024 winners had **{av.loc[2024, True]:.2f}** cases on average and losers **{av.loc[2024, False]:.2f}**. '
                 f'**{anyc.loc[2024, True]:.0f}%** of 2024 winners declared at least one case.'),
        ]),
        section('Cases, money and parties'),
        dbc.Row([
            card('Criminal cases vs assets', f_v,
                 f'Candidates with more cases tend to be richer. The typical candidate with 6 or more cases declared **{cr(medc["6+"])}**, '
                 f'against **{cr(medc["0"])}** for those with none.'),
            card('Share of candidates with at least one case, by party', f_p,
                 f'Parties with at least 40 candidates. **{sh.idxmax()}** is highest, with **{sh.max():.0f}%** of its candidates declaring a case. '
                 f'Among independents it is **{ind:.0f}%**.'),
        ]),
    ]

# ---------------- Education & age ----------------
def tab_people(states):
    g, a, p = filt(states)
    # median assets and win rate by education
    e = a[a.MN_Education.isin(EDU)]
    me = e.groupby('MN_Education').Assets_Rs.median().reindex(EDU)
    we = g[g.MN_Education.isin(EDU)].groupby('MN_Education').Winner.mean().reindex(EDU) * 100
    f_e = go.Figure(go.Bar(y=EDU, x=me.values / 1e5, orientation='h', marker_color=LOSE, text=[cr(v) for v in me],
                           hovertemplate='%{y}: ₹%{x:.1f} lakh<extra></extra>'))
    bar_text(style(f_e, h=460, legend=False)).update_xaxes(type='log', title='Median assets (₹ lakh, log)', range=[0, math.log10(me.max() / 1e5) + 0.4], tickvals=[1, 10, 100], ticktext=['₹1 lakh', '₹10 lakh', '₹1 cr'])
    f_e.update_yaxes(title='Education')
    f_ew = go.Figure(go.Bar(y=EDU, x=we.values, orientation='h', marker_color=WIN, text=[f'{v:.1f}%' for v in we],
                            hovertemplate='%{y}: %{x:.1f}% won<extra></extra>'))
    bar_text(style(f_ew, h=460, legend=False)).update_xaxes(range=[0, we.max() * 1.25], ticksuffix='%', title='Candidates who won (%)')
    f_ew.update_yaxes(title='Education')

    # median assets by age group
    ag = a[a.Age_Bin.notna()]
    ma = ag.groupby(['Age_Bin', 'Winner'], observed=True).Assets_Rs.median().unstack()
    f_a = go.Figure()
    for w, name, c in [(True, 'Winners', WIN), (False, 'Losers', LOSE)]:
        f_a.add_bar(x=AGE_BINS, y=ma[w].values / 1e7, name=name, marker_color=c, text=[cr(v) for v in ma[w]],
                    hovertemplate='%{x}: ₹%{y:.2f} cr<extra>' + name + '</extra>')
    bar_text(style(f_a)).update_layout(barmode='group', bargap=0.3)
    f_a.update_yaxes(title='Median assets (₹ crore)', range=[0, ma.max().max() / 1e7 * 1.25])
    f_a.update_xaxes(title='Age group (years)')

    # age of winners vs losers, split violins
    gg = g[g.MN_Age >= 25]
    f_ad = go.Figure()
    for w, name, c in [(True, 'Winners', WIN), (False, 'Losers', LOSE)]:
        s = gg[gg.Winner == w].MN_Age
        f_ad.add_violin(x=[str(y) for y in gg[gg.Winner == w].Election_Year], y=s, name=name, line_color=c, fillcolor=c + '44',
                        side='positive' if w else 'negative', points=False, meanline_visible=True, hoverinfo='skip', scalemode='width')
    style(f_ad).update_layout(violinmode='overlay', violingap=0)
    f_ad.update_yaxes(title='Age (years)', range=[20, 90])
    f_ad.update_xaxes(type='category', range=[-0.6, 2.6], title='Election year')
    agew = gg.groupby('Winner').MN_Age.median()

    return [
        html.H1('Education & Age', className='page-title'),
        section('Education'),
        dbc.Row([
            card('Median assets by education', f_e,
                 f'More education usually means more assets. The typical candidate with a doctorate declared **{cr(me["Doctorate"])}**, '
                 f'an illiterate candidate **{cr(me["Illiterate"])}**.'),
            card('Win rate by education', f_ew,
                 f'**{we["Doctorate"]:.1f}%** of candidates with a doctorate won, against **{we["Illiterate"]:.1f}%** of illiterate candidates.'),
        ]),
        section('Age'),
        dbc.Row([
            card('Median assets by age group', f_a,
                 f'Among winners, the **{ma[True].idxmax()}** age group is the richest, at **{cr(ma[True].max())}** for the typical one. '
                 'In every age group winners declare more than losers.'),
            card('Age of winners vs losers', f_ad,
                 f'The typical winner is **{agew[True]:.0f}** years old and the typical loser **{agew[False]:.0f}**. '
                 'Each shape shows how ages are spread, and the line across it is the average.'),
        ]),
    ]

# ---------------- Experimental ----------------
def tab_exp(states):
    g, a, p = filt(states)
    # win rate by asset rank inside the seat (1 = richest)
    rk = g[g.Asset_Rank.notna()]
    wr = rk.groupby(rk.Asset_Rank.clip(upper=6)).Winner.mean() * 100
    labels = ['Richest', '2nd', '3rd', '4th', '5th', '6th or lower']
    f_r = go.Figure(go.Bar(x=labels, y=wr.values, width=0.6, marker_color=[WIN] + [GREY] * 5, text=[f'{v:.1f}%' for v in wr],
                           hovertemplate='%{x}: %{y:.1f}% won<extra></extra>'))
    bar_text(style(f_r, legend=False)).update_yaxes(range=[0, wr.max() * 1.25], ticksuffix='%', title='Candidates who won (%)')
    f_r.update_xaxes(title='Asset rank inside the seat')

    # every candidate: assets vs vote share
    f_vs = go.Figure()
    for w, name, c, sz, op in [(False, 'Losers', LOSE, 5, 0.35), (True, 'Winners', WIN, 7, 0.85)]:
        s = a[a.Winner == w]
        f_vs.add_scattergl(x=np.log10(s.Assets_Rs), y=s.Vote_Share_Percentage, mode='markers', name=name,
                           marker=dict(color=c, size=sz, opacity=op), text=s.Candidate.str.title(),
                           hovertemplate='%{text}: %{y}% of votes<extra></extra>')
    style(f_vs).update_xaxes(range=[3, 10.5], title='Declared assets (log scale)', **RUPEE_TICKS)
    f_vs.update_yaxes(range=[0, 80], ticksuffix='%', title='Vote share (%)')
    rho = a.Assets_Rs.rank().corr(a.Vote_Share_Percentage.rank())

    # every candidate across the three elections (Sankey)
    pos = g.dropna(subset=['Person_ID']).drop_duplicates(['Person_ID', 'Election_Year']).pivot(index='Person_ID', columns='Election_Year', values='Winner')
    fate = pos.apply(lambda col: col.map({True: 'Won', False: 'Lost'})).fillna('Not running')   # not in that year's list = not running
    S = ['Won', 'Lost', 'Not running']
    nodes = [f'{s} {y}' for y in YEARS for s in S]
    col = lambda n: WIN if n.startswith('Won') else (LOSE if n.startswith('Lost') else GREY)
    src, tgt, val = [], [], []
    for y0, y1 in [(2014, 2019), (2019, 2024)]:
        for s0 in S:
            for s1 in S:
                src.append(nodes.index(f'{s0} {y0}')); tgt.append(nodes.index(f'{s1} {y1}'))
                val.append(int(((fate[y0] == s0) & (fate[y1] == s1)).sum()))
    tot = {f'{s} {y}': int((fate[y] == s).sum()) for y in YEARS for s in S}
    f_sk = go.Figure(go.Sankey(arrangement='snap',
                               node=dict(label=[f'{n} ({tot[n]:,})' for n in nodes], color=[col(n) for n in nodes], pad=18, thickness=18, line_width=0),
                               link=dict(source=src, target=tgt, value=val, color=[col(nodes[s]) + '66' for s in src])))
    style(f_sk, h=560, legend=False).update_layout(margin=dict(l=10, r=10, t=10, b=10))
    won_all = int((fate == 'Won').all(axis=1).sum())
    once = int((fate != 'Not running').sum(axis=1).eq(1).sum())

    return [
        html.H1('Experimental / Cool', className='page-title'),
        section('Money and votes'),
        dbc.Row([
            card('Win rate by asset rank inside the seat', f_r,
                 'Candidates in each seat are ranked by their assets. '
                 f'The richest one won **{wr.iloc[0]:.1f}%** of the time, while those ranked 6th or lower won **{wr.iloc[-1]:.1f}%**.'),
            card('Assets vs vote share, every candidate', f_vs,
                 f'Each dot is one candidate. Richer candidates tend to get more votes (rank correlation **{rho:.2f}**, where 1 would be a perfect match). '
                 f'The poorest winner declared **{cr(a[a.Winner].Assets_Rs.min())}**.'),
        ]),
        section('Careers'),
        dbc.Row([
            card('Every candidate across 2014, 2019 and 2024', f_sk,
                 f'Follows every candidate through the three elections. **{once:,}** of {len(fate):,} stood only once, and only **{won_all}** won all three times. '
                 '"Not running" means they were not on that year\'s list, or their name could not be matched.', md=12),
        ]),
    ]

# ---------------- Data ----------------
def find(name):
    # the raw and interim files sit next to the clean folder in the project
    for folder in ['../raw/lok_sabha_candidate_dfs', '../interim', '../clean', './clean', '.', './myneta_prep']:
        if os.path.exists(f'{folder}/{name}'):
            return f'{folder}/{name}'
    raise FileNotFoundError(name)


# myneta: share of rows with a usable asset figure, raw scrape vs clean file
mn_raw = pd.read_csv(find('candidates_all_years.csv'))
mn_clean = pd.read_csv(find('myneta_candidates_clean_2026-10-20.csv'))
MN_BEFORE = mn_raw.total_assets.notna().groupby(mn_raw.year).mean() * 100   # image rows have no text
MN_AFTER = mn_clean.assets_rs.notna().groupby(mn_clean.year).mean() * 100

# opencity: total vote share per seat, with and without the by-election rows
def seat_totals(general_only):
    out = []
    for y in [2014, 2019]:
        h = pd.read_csv(find(f'opencity_electiondata_{y}.csv'), low_memory=False)
        h = h[h.State_Name.str.replace('_', ' ').isin(STATES)]
        if general_only:
            h = h[h.Poll_No == 0]
        t = h.groupby(['State_Name', 'Constituency_No']).agg(Name=('Constituency_Name', 'first'), Total=('Vote_Share_Percentage', 'sum')).reset_index()
        out.append(pd.DataFrame({'Seat': t.Name.str.title() + f' {y}', 'Total': t.Total}))
    return pd.concat(out, ignore_index=True)

OC_BEFORE, OC_AFTER = seat_totals(False), seat_totals(True)


def tab_data(states):
    g, a, p = filt(states)
    # candidates per state and year
    ss = [s for s in STATES if s in set(g.State)]
    cnt = g.groupby(['Election_Year', 'State']).size().unstack()[ss]
    f_c = go.Figure()
    for y, c in zip(YEARS, ['#c6dbef', '#6baed6', '#2171b5']):   # light to dark blue, older year = lighter
        f_c.add_bar(x=ss, y=cnt.loc[y].values, name=str(y), marker_color=c, text=cnt.loc[y].values)
    bar_text(style(f_c)).update_layout(barmode='group')
    f_c.update_yaxes(range=[0, cnt.max().max() * 1.2], title='Candidates (count)')
    f_c.update_xaxes(title='State')

    # share matched to an affidavit, heatmap
    cov = g.groupby(['State', 'Election_Year']).Has_Assets.mean().unstack().loc[ss] * 100
    f_h = go.Figure(go.Heatmap(z=cov.values, x=[str(y) for y in YEARS], y=ss, colorscale=[[0, '#deebf7'], [1, '#4292c6']], zmin=90, zmax=100,
                               colorbar=dict(title='%'), text=[[f'{v:.1f}%' for v in r] for r in cov.values], texttemplate='%{text}',
                               textfont=dict(size=18, color='black'), xgap=3, ygap=3, hovertemplate='%{y} %{x}: %{z:.1f}%<extra></extra>'))
    style(f_h, legend=False).update_yaxes(autorange='reversed')
    f_h.update_xaxes(side='top', title='Election year')
    f_h.update_yaxes(title='State')

    # myneta before / after: share of candidates with an asset figure we can use, per year
    f_mn = go.Figure()
    for name, v, c in [('Before (raw scrape)', MN_BEFORE, GREY), ('After (OCR + cleaning)', MN_AFTER, LOSE)]:
        f_mn.add_bar(x=[str(y) for y in YEARS], y=v.loc[YEARS].values, name=name, marker_color=c, text=[f'{x:.1f}%' for x in v.loc[YEARS]],
                     hovertemplate='%{x}: %{y:.1f}% usable<extra>' + name + '</extra>')
    bar_text(style(f_mn)).update_layout(barmode='group', bargap=0.3)
    f_mn.update_yaxes(range=[0, 115], ticksuffix='%', title='Candidates with a usable asset figure (%)')
    f_mn.update_xaxes(title='Election year')

    # opencity before / after: seats whose vote shares do not add up to 100%, per year
    off = lambda t: [int(((t.Total - 100).abs() > 0.5)[t.Seat.str.endswith(str(y))].sum()) for y in [2014, 2019]]
    f_oc = go.Figure()
    for name, t, c in [('Before (with by-election rows)', OC_BEFORE, GREY), ('After cleaning', OC_AFTER, LOSE)]:
        f_oc.add_bar(x=['2014', '2019'], y=off(t), name=name, marker_color=c, text=off(t),
                     hovertemplate='%{x}: %{y} seats<extra>' + name + '</extra>')
    bar_text(style(f_oc)).update_layout(barmode='group', bargap=0.3)
    f_oc.update_yaxes(range=[0, max(off(OC_BEFORE)) * 1.4], dtick=1, title='Seats not adding up to 100% (count)')
    f_oc.update_xaxes(title='Election year')
    bad = OC_BEFORE[(OC_BEFORE.Total - 100).abs() > 0.5]
    return [
        html.H1('Data', className='page-title'),
        dbc.Row([
            card('Candidates per state and election', f_c,
                 f'**{len(g):,}** candidate results across **{len(ss)}** states and three elections. '
                 f'**{cnt.sum().idxmax()}** has the most candidates because it has the most seats.'),
            card('Share with a matched affidavit (%)', f_h,
                 'Share of candidates we could link to their asset declaration on MyNeta. '
                 f'It is between **{cov.values.min():.1f}%** and **{cov.values.max():.1f}%** in every state and year.'),
        ]),
        section('Before and after cleaning'),
        dbc.Row([
            card('MyNeta: asset figures we can use', f_mn,
                 f'Before cleaning only **{MN_BEFORE.mean():.0f}%** of candidates had their assets as text, because MyNeta shows every third one as an image. '
                 f'After reading the images with OCR it is **{MN_AFTER.mean():.0f}%**.'),
            card('OpenCity: does each seat add up to 100%?', f_oc,
                 'In every seat the vote shares of all candidates should add up to 100%. '
                 f'Before cleaning **{len(bad)}** seats added up to about **{bad.Total.max():.0f}%** because by-election results were mixed in ({", ".join(bad.Seat)}). '
                 'After removing those rows every seat adds up to 100%.'),
        ]),
    ]


# tab key: (tab name, function that builds it)
TABS = {'overview': ('Overview', tab_overview), 'wl': ('Winners vs Losers', tab_wl), 'parties': ('Parties', tab_parties),
        'same': ('Repeat Candidates', tab_same), 'states': ('States', tab_states), 'crime': ('Crime', tab_crime),
        'people': ('Education & Age', tab_people), 'exp': ('Experimental', tab_exp),
        'data': ('Data', tab_data)}

# quick self-test: build every tab once so errors show up here, not inside the app
for key, (name, fn) in TABS.items():
    fn(STATES)

# layout
CSS = '''
body{background:#000;color:#fff;font-family:'Helvetica Neue',Arial,sans-serif}
.topbar{background:#2b2b2b;padding:14px 0;margin-bottom:28px}
.topbar .brand{font-weight:800;font-size:1.35rem;letter-spacing:.5px;color:#fff;margin:0}
.wrap{max-width:1320px;margin:0 auto;padding:0 20px}
.page-title{font-weight:800;font-size:2.3rem;margin:1.6rem 0 1.2rem}
.section{font-weight:800;font-size:1.7rem;margin:2rem 0 1rem}
.chart-card{background:#000;border:1px solid #262626;border-radius:6px}
.chart-card .card-body{display:flex;flex-direction:column}
.cap{margin-top:auto}
.chart-card .card-title{font-size:1.15rem;font-weight:700}
.cap p{font-size:1.05rem;font-weight:700;margin:.5rem 0 0;color:#fff}
.cap strong{color:#fff}
.lead-text{font-size:1.15rem;font-weight:600;max-width:960px;color:#e6e6e6}
.metric-card{background:#000;border:1px solid #262626;border-radius:6px}
.metric-value{font-size:2rem;font-weight:800;color:#fff}
.metric-label{font-size:.95rem;font-weight:700;color:#b8b8b8}
.form-check-input{background-color:#000;border:1px solid #9a9a9a}
.form-check-input:checked{background-color:#6cb4f8;border-color:#6cb4f8}
.form-select{background-color:#111;color:#fff;border-color:#333;font-weight:600}
'''

# CSES-style tabs: plain uppercase links, the active one in a grey box, one rule underneath
TAB_STYLE = {'background': 'transparent', 'border': 'none', 'color': '#6cb4f8', 'fontWeight': 500, 'padding': '6px 12px',
             'textTransform': 'uppercase', 'letterSpacing': '.3px', 'fontSize': '15px', 'width': 'auto', 'flex': '0 0 auto'}
TAB_ON = {**TAB_STYLE, 'background': '#3a3a3a', 'color': '#ffffff', 'border': 'none'}

app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY],
           suppress_callback_exceptions=True, title='Lok Sabha Assets')
app.index_string = app.index_string.replace('{%css%}', '{%css%}<style>' + CSS + '</style>')

app.layout = html.Div([
    html.Div(html.Div(html.P('LOK SABHA ASSETS', className='brand'), className='wrap'), className='topbar'),
    html.Div([
        dcc.Tabs(id='tabs', value='overview', children=[
            dcc.Tab(label=name, value=key, style=TAB_STYLE, selected_style=TAB_ON) for key, (name, _) in TABS.items()
        ], style={'borderBottom': '1px solid #8a8a8a', 'display': 'flex', 'flexWrap': 'wrap', 'gap': '4px'},
           parent_style={'width': '100%'}),
        dcc.Loading(html.Div(id='tab-content'), type='dot', color='#6cb4f8'),
    ], className='wrap'),
])

# callbacks

@app.callback(Output('tab-content', 'children'), Input('tabs', 'value'))
def render_tab(tab):
    return TABS[tab][1](STATES)


@app.callback(Output('hist-graph', 'figure'), Input('hist-year', 'value'))
def update_hist(year):
    return fig_hist(filt(STATES)[1], year)[0]


@app.callback(Output('db-graph', 'figure'), Input('party-year', 'value'))
def update_dumbbell(year):
    return fig_dumbbell(filt(STATES)[1], year)[0]


@app.callback(Output('change-graph', 'figure'), Output('change-cap', 'children'), Input('change-period', 'value'))
def update_change(period):
    return fig_change(period)


@app.callback(Output('pct-graph', 'figure'), Output('pct-cap', 'children'), Input('pct-period', 'value'))
def update_pct(period):
    return fig_pct(period)


@app.callback(Output('person-graph', 'figure'), Input('person-pick', 'value'))
def update_person(pid):
    return fig_person(float(pid))

server = app.server

if __name__ == "__main__":
    app.run(debug=True)