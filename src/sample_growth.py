"""Plot growth means with sample standard deviations across replicates."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "sample" / "growth.csv"
OUTPUT_DIR = PROJECT_ROOT / "output" / "sample_growth"
REQUIRED_COLUMNS = {"time_h", "condition", "replicate", "value"}
CONDITIONS = ("Control", "Treatment A", "Treatment B")
COLORS = ("#E69F00", "#0072B2", "#009E73")
MARKERS = ("o", "s", "^")
FIGURE_SIZE = (8.5 / 2.54, 6.5 / 2.54)
FONT_SIZE = 8
DPI = 300
SD_DDOF = 1


def main():
    """Read unchanged observations, aggregate replicates, and save the figure."""
    data = pd.read_csv(INPUT_PATH)
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns in {INPUT_PATH}: {', '.join(sorted(missing))}")
    missing_values = sorted(column for column in REQUIRED_COLUMNS if data[column].isna().any())
    if missing_values:
        raise ValueError(f"Missing values in required columns: {', '.join(missing_values)}")
    unexpected = set(data["condition"]) - set(CONDITIONS)
    if unexpected:
        raise ValueError(
            "Input conditions must be Control, Treatment A, or Treatment B. "
            f"Unexpected values: {sorted(unexpected)}"
        )

    grouped = data.groupby(["condition", "time_h"], sort=True)
    replicate_counts = grouped.size()
    undersized_groups = replicate_counts[replicate_counts < 2]
    if not undersized_groups.empty:
        raise ValueError(
            "Each condition × time group requires at least 2 replicates. "
            f"Groups with fewer than 2 replicates: {undersized_groups.to_dict()}"
        )
    summary = grouped["value"].agg(
        mean="mean", sd=lambda values: values.std(ddof=SD_DDOF)
    )
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    font_family = "Arial" if "Arial" in available_fonts else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": font_family,
        "font.size": FONT_SIZE,
        "axes.labelsize": FONT_SIZE,
        "axes.titlesize": FONT_SIZE,
        "xtick.labelsize": FONT_SIZE,
        "ytick.labelsize": FONT_SIZE,
        "legend.fontsize": FONT_SIZE,
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    for condition, color, marker in zip(CONDITIONS, COLORS, MARKERS):
        if condition not in summary.index.get_level_values("condition"):
            raise ValueError(f"No observations found for required condition: {condition}")
        points = summary.loc[condition].sort_index()
        ax.errorbar(
            points.index, points["mean"], yerr=points["sd"],
            label=condition, color=color, marker=marker,
            markersize=3, linewidth=1, elinewidth=0.8, capsize=2,
        )
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("OD600")
    ax.set_xlim(-1, 49)
    ax.set_xticks([0, 12, 24, 36, 48])
    ax.set_yscale("linear")
    ax.margins(y=0.08)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=1.08)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        # bbox_inches="tight" is intentionally omitted to keep the spec size of 8.5 × 6.5 cm.
        fig.savefig(
            OUTPUT_DIR / f"sample_growth.{extension}",
            dpi=DPI,
            metadata={"CreationDate": None, "ModDate": None} if extension == "pdf" else None,
        )
    plt.close(fig)


if __name__ == "__main__":
    main()
