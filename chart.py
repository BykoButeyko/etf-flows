"""Key chart: weekly ETF flow above, weekly change in leveraged-fund CME net short below."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import build

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def main():
    w = build.weekly()
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, facecolor=SURFACE,
                               gridspec_kw={"hspace": 0.28})
    for ax, col, color, title in (
        (a, "flow_btc", BLUE, "Weekly net flow into US spot bitcoin ETFs (thousand BTC)"),
        (b, "d_short", ORANGE, "Weekly change in leveraged funds' net short, CME bitcoin futures (thousand BTC)"),
    ):
        ax.set_facecolor(SURFACE)
        ax.bar(w.index, w[col] / 1000, width=5.2, color=color, linewidth=0)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.axvspan(build.TEST_START, w.index.max() + pd.Timedelta(days=4), color="#f0efec", zorder=0)
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=6)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=9, length=0)
    a.text(build.TEST_START + pd.Timedelta(days=7), a.get_ylim()[1] * 0.92,
           "test period (2025 on)", fontsize=9, color=INK2, va="top")
    fig.text(0.125, 0.015,
             "Wednesday to Tuesday weeks ending on CFTC report dates. Each BTC of inflow came with 0.23 BTC of new "
             "leveraged-fund short in 2025-26 (0.19 in 2024).\nSources: Farside Investors, CFTC Traders in Financial "
             "Futures (CME Bitcoin and Micro Bitcoin), Binance spot.",
             fontsize=8, color=INK2)
    fig.savefig(build.Path(__file__).with_name("chart.png"), dpi=160, bbox_inches="tight", facecolor=SURFACE)


if __name__ == "__main__":
    main()
