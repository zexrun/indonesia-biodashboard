"""Build Plotly legend figures for discrete and continuous layers."""

import plotly.graph_objects as go
import matplotlib.cm as cm
import matplotlib.colors as mcolors


def make_legend_figure(meta):
    """Return (fig, height_px) for the legend based on layer metadata."""
    if meta["discrete"]:
        return _discrete_legend(meta)
    return _continuous_legend(meta)


def _discrete_legend(meta):
    cats   = meta["categories"]
    labels = [v[0] for v in cats.values()]
    colors = [v[1] for v in cats.values()]
    n      = len(labels)

    fig = go.Figure()
    for i, (label, color) in enumerate(zip(labels, colors)):
        fig.add_trace(go.Scatter(
            x=[0], y=[i],
            mode="markers+text",
            marker=dict(color=color, size=16, symbol="square",
                       line=dict(color="rgba(0,0,0,0.15)", width=0.5)),
            text=["  " + label],
            textposition="middle right",
            textfont=dict(size=11.5, color="#1a1a1a", family="Inter, sans-serif"),
            showlegend=False,
            hoverinfo="skip",
        ))

    height = min(max(140, n * 28 + 20), 380)
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=8, t=8, b=8),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-0.5, 8]),
        yaxis=dict(visible=False, range=[-0.6, n - 0.4]),
    )
    return fig, height


def _continuous_legend(meta):
    try:
        cmap = cm.get_cmap(meta["colormap"], 256)
    except (ValueError, KeyError):
        cmap = cm.get_cmap("viridis", 256)
    colorscale = [[i / 255, mcolors.to_hex(cmap(i))] for i in range(256)]
    vmin, vmax = meta["vmin"], meta["vmax"]
    if vmin == vmax:
        vmax = vmin + 1
    zones      = meta.get("zones", [])
    n_zones    = len(zones)

    # Dynamic height dengan constraints
    BAR_H, TICK_H, LABEL_H, ROW_H = 32, 18, 20, 30
    TOP_PAD, BOT_PAD = 4, 14
    zone_section_h = max(130, min(n_zones * ROW_H, 220))
    total_h = TOP_PAD + BAR_H + TICK_H + LABEL_H + zone_section_h + BOT_PAD
    total_h = max(160, min(total_h, 420))

    bar_top  = 1.0 - TOP_PAD / total_h
    bar_bot  = bar_top - BAR_H / total_h
    zone_top = bar_bot - (TICK_H + LABEL_H) / total_h
    zone_bot = zone_top - (zone_section_h) / total_h

    fig = go.Figure()

    ticks     = [0, 64, 128, 192, 255]
    tick_vals = [round(vmin + (vmax - vmin) * t / 255) for t in ticks]
    fig.add_trace(go.Heatmap(
        z=[list(range(256))],
        colorscale=colorscale,
        showscale=False,
        xaxis="x", yaxis="y",
    ))

    for i, (z_min, z_max, label, keterangan) in enumerate(zones):
        mid_norm  = ((z_min + z_max) / 2 - vmin) / max(vmax - vmin, 1)
        hex_color = mcolors.to_hex(cmap(mid_norm))
        fig.add_trace(go.Scatter(
            x=[0], y=[i],
            mode="markers+text",
            marker=dict(color=hex_color, size=13, symbol="square",
                        line=dict(color="rgba(0,0,0,0.2)", width=1)),
            text=[f"  <b>{label}</b>  ({z_min}–{z_max})"],
            textposition="middle right",
            textfont=dict(size=11, color="#222"),
            showlegend=False,
            hovertemplate=(
                f"<b>{label}</b><br>"
                f"Rentang: {z_min}–{z_max}<br>"
                f"{keterangan}<extra></extra>"
            ),
            xaxis="x2", yaxis="y2",
        ))

    fig.update_layout(
        height=total_h,
        margin=dict(l=6, r=6, t=TOP_PAD, b=BOT_PAD),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            tickvals=ticks,
            ticktext=[str(v) for v in tick_vals],
            tickfont=dict(size=9, color="#939393"),
            showgrid=False, zeroline=False,
            domain=[0, 1],
        ),
        yaxis=dict(visible=False, domain=[bar_bot, bar_top]),
        xaxis2=dict(visible=False, range=[-0.5, 9], domain=[0, 1]),
        yaxis2=dict(
            visible=False,
            range=[-1.2, n_zones - 0.2],
            domain=[max(0, zone_bot), zone_top],
        ),
        shapes=[dict(
            type="line", xref="paper", yref="paper",
            x0=0, x1=1, y0=zone_top, y1=zone_top,
            line=dict(color="#e8e8e8", width=1),
        )],
        annotations=[
            dict(
                text="Kelas Interpretasi",
                xref="paper", yref="paper",
                x=0, y=zone_top + 0.02,
                xanchor="left", yanchor="bottom",
                font=dict(size=9, color="#939393"),
                showarrow=False,
            ),
        ],
    )
    return fig, total_h


def make_empty_legend():
    """Build empty placeholder legend figure when no layers are selected."""
    fig = go.Figure()

    fig.add_annotation(
        text="<b>No layers selected</b><br><span style='font-size:10px; color:#939393'>Enable a layer to view its legend</span>",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        xanchor="center", yanchor="middle",
        showarrow=False,
        font=dict(size=12, color="#666666", family="Inter, sans-serif"),
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        height=160,
        margin=dict(l=6, r=6, t=8, b=8),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig, 160
