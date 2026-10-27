# ============================================================
# JV Curve Plotting - Forward / Reverse
# Excel IV -> JV
#
# Input:
# Desktop/graph/JV/
#
# Output:
# Desktop/graph/JV/JV_output/
#
# Smaller number = Forward
# Larger number  = Reverse
#
# Input  : mV, mA
# Output : V, mA/cm2
#
# Active area = (USER SETTINGS で設定)
# Figure size = 10 x 10 inch
# ============================================================


# ============================================================
# 1. IMPORT
# ============================================================

from pathlib import Path
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator


# ============================================================
# 2. USER SETTINGS
# ============================================================

# Folder
INPUT_DIR = Path.home() / "Desktop" / "graph" / "JV"
OUTPUT_DIR = INPUT_DIR / "JV_output"

# Active area [cm2]
# 各自の環境に合わせて設定（デバイスの実効面積。以下はサンプル値）
ACTIVE_AREA_CM2 = 0.100

# Excel settings
PREFERRED_SHEET = "I-V Data"
HEADER_SEARCH_ROWS = 100
MIN_DATA_POINTS = 5

# ============================================================
# FIGURE SETTINGS
# ============================================================

# 正方形 10 x 10 inch
FIGSIZE = (10, 10)

# Resolution
DPI = 600

# Font sizes
FONT_SIZE = 22
TICK_SIZE = 19
LEGEND_SIZE = 20

# Line and marker
LINE_WIDTH = 2.2
MARKER_SIZE = 5.0
SHOW_MARKERS = True

# Colors
FORWARD_COLOR = "#D62728"
REVERSE_COLOR = "#1F77B4"

# ============================================================
# AXIS SETTINGS
# ============================================================

# 両軸0から開始
X_MIN = 0.0
Y_MIN = 0.0

# None = 上限自動設定
X_MAX = None
Y_MAX = None

# 上限の余白 5%
AXIS_MARGIN = 0.05

# 手動設定例
# X_MAX = 1.2
# Y_MAX = 30.0

# ============================================================
# SAVE SETTINGS
# ============================================================

SAVE_PNG = True
SAVE_PDF = True
SAVE_CSV = True


# ============================================================
# 3. EXTRACT FILE NUMBER
# ============================================================

def extract_file_number(path):

    match = re.search(r"\((\d+)\)", path.stem)

    if match is None:
        raise ValueError(
            f"ファイル番号が見つかりません: {path.name}"
        )

    return int(match.group(1))


# ============================================================
# 4. FIND TWO EXCEL FILES
# ============================================================

def find_excel_files():

    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(
            f"入力フォルダがありません: {INPUT_DIR}"
        )

    files = [
        p for p in INPUT_DIR.iterdir()
        if (
            p.is_file()
            and p.suffix.lower() in (".xlsx", ".xlsm")
            and not p.name.startswith("~$")
        )
    ]

    if len(files) != 2:
        raise ValueError(
            "Excelファイルを2つだけ入れてください\n"
            f"現在のファイル数: {len(files)}"
        )

    files.sort(key=extract_file_number)

    forward_file = files[0]
    reverse_file = files[1]

    if (
        extract_file_number(forward_file)
        == extract_file_number(reverse_file)
    ):
        raise ValueError(
            "2つのファイル番号が同じです"
        )

    print("=" * 60)
    print("INPUT FILES")
    print("=" * 60)
    print("Forward :", forward_file.name)
    print("Reverse :", reverse_file.name)

    return forward_file, reverse_file


# ============================================================
# 5. HEADER DETECTION
# ============================================================

def normalize_header(value):

    if pd.isna(value):
        return ""

    text = str(value).lower().strip()

    text = text.replace(" ", "")
    text = text.replace("_", "")
    text = text.replace("（", "(")
    text = text.replace("）", ")")

    return text


def is_voltage_header(value):

    text = normalize_header(value)

    has_voltage = (
        "voltage" in text
        or "電圧" in text
        or text.startswith("v(")
        or text.startswith("v[")
    )

    return has_voltage and "mv" in text


def is_current_header(value):

    text = normalize_header(value)

    if (
        "density" in text
        or "電流密度" in text
        or "/cm" in text
    ):
        return False

    has_current = (
        "current" in text
        or "電流" in text
        or text.startswith("i(")
        or text.startswith("i[")
    )

    return has_current and "ma" in text


def find_data_columns(raw_df):

    search_rows = min(
        HEADER_SEARCH_ROWS,
        len(raw_df)
    )

    for row_idx in range(search_rows):

        voltage_cols = []
        current_cols = []

        for col_idx in range(raw_df.shape[1]):

            value = raw_df.iat[row_idx, col_idx]

            if is_voltage_header(value):
                voltage_cols.append(col_idx)

            if is_current_header(value):
                current_cols.append(col_idx)

        if voltage_cols and current_cols:

            pairs = [
                (abs(v - i), v, i)
                for v in voltage_cols
                for i in current_cols
                if v != i
            ]

            if pairs:
                _, v_col, i_col = min(pairs)

                return {
                    "header_row": row_idx,
                    "voltage_col": v_col,
                    "current_col": i_col
                }

    return None


# ============================================================
# 6. READ EXCEL AND CONVERT IV -> JV
# ============================================================

def read_iv_excel(file_path):

    with pd.ExcelFile(
        file_path,
        engine="openpyxl"
    ) as xls:

        sheet_names = xls.sheet_names

        # I-V Dataを優先
        if PREFERRED_SHEET in sheet_names:

            ordered_sheets = [
                PREFERRED_SHEET
            ] + [
                s for s in sheet_names
                if s != PREFERRED_SHEET
            ]

        else:
            ordered_sheets = sheet_names

        detected = None

        for sheet_name in ordered_sheets:

            raw_df = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                header=None
            )

            if raw_df.empty:
                continue

            columns = find_data_columns(raw_df)

            if columns is not None:
                detected = (
                    sheet_name,
                    raw_df,
                    columns
                )
                break

    if detected is None:
        raise ValueError(
            f"IVデータが見つかりません: {file_path.name}"
        )

    sheet_name, raw_df, columns = detected

    header_row = columns["header_row"]
    v_col = columns["voltage_col"]
    i_col = columns["current_col"]

    # Excel上の行番号
    source_rows = np.arange(
        header_row + 2,
        len(raw_df) + 1
    )

    data = pd.DataFrame({

        "Excel_Row": source_rows,

        "Voltage_mV": pd.to_numeric(
            raw_df.iloc[header_row + 1:, v_col].to_numpy(),
            errors="coerce"
        ),

        "Current_mA": pd.to_numeric(
            raw_df.iloc[header_row + 1:, i_col].to_numpy(),
            errors="coerce"
        )
    })

    # 最初の連続した数値領域を取得
    valid = (
        np.isfinite(data["Voltage_mV"].to_numpy())
        & np.isfinite(data["Current_mA"].to_numpy())
    )

    positions = np.flatnonzero(valid)

    if len(positions) == 0:
        raise ValueError(
            f"測定データがありません: {file_path.name}"
        )

    first = positions[0]
    end = first

    while end < len(data) and valid[end]:
        end += 1

    data = data.iloc[first:end].copy()
    data = data.reset_index(drop=True)

    if len(data) < MIN_DATA_POINTS:
        raise ValueError(
            f"測定点数が不足しています: {file_path.name}"
        )

    # ========================================================
    # IV -> JV
    # ========================================================

    # mV -> V
    data["Voltage_V"] = (
        data["Voltage_mV"] / 1000.0
    )

    # mA -> mA/cm2
    data["CurrentDensity_mA_cm2"] = (
        data["Current_mA"] / ACTIVE_AREA_CM2
    )

    print()
    print("Loaded:", file_path.name)
    print("Sheet:", sheet_name)
    print("Header row:", header_row + 1)
    print("Voltage column:", v_col + 1)
    print("Current column:", i_col + 1)
    print("Data points:", len(data))

    return data


# ============================================================
# 7. OUTPUT FILENAME
# ============================================================

def make_output_name(forward_file, reverse_file):

    name = (
        f"{forward_file.stem}_"
        f"{reverse_file.stem}_JV"
    )

    name = re.sub(
        r'[\\/:*?"<>|]',
        "_",
        name
    )

    return name


# ============================================================
# 8. PLOT JV
# ============================================================

def plot_jv(forward_data, reverse_data, output_base):

    # 正方形
    fig, ax = plt.subplots(figsize=FIGSIZE)

    marker = "o" if SHOW_MARKERS else None

    # Forward
    ax.plot(
        forward_data["Voltage_V"],
        forward_data["CurrentDensity_mA_cm2"],
        color=FORWARD_COLOR,
        linewidth=LINE_WIDTH,
        marker=marker,
        markersize=MARKER_SIZE,
        label="Forward",
        zorder=3
    )

    # Reverse
    ax.plot(
        reverse_data["Voltage_V"],
        reverse_data["CurrentDensity_mA_cm2"],
        color=REVERSE_COLOR,
        linewidth=LINE_WIDTH,
        marker=marker,
        markersize=MARKER_SIZE,
        label="Reverse",
        zorder=2
    )

    # ========================================================
    # AXIS LABELS
    # ========================================================

    ax.set_xlabel(
        "Voltage [V]",
        fontsize=FONT_SIZE,
        labelpad=12
    )

    ax.set_ylabel(
        r"Current density [mA cm$^{-2}$]",
        fontsize=FONT_SIZE,
        labelpad=12
    )

    # ========================================================
    # AXIS RANGE
    # ========================================================

    x_data_max = max(
        forward_data["Voltage_V"].max(),
        reverse_data["Voltage_V"].max()
    )

    y_data_max = max(
        forward_data["CurrentDensity_mA_cm2"].max(),
        reverse_data["CurrentDensity_mA_cm2"].max()
    )

    if X_MAX is None:
        x_upper = max(
            x_data_max * (1 + AXIS_MARGIN),
            0.1
        )
    else:
        x_upper = X_MAX

    if Y_MAX is None:
        y_upper = max(
            y_data_max * (1 + AXIS_MARGIN),
            1.0
        )
    else:
        y_upper = Y_MAX

    if x_upper <= X_MIN or y_upper <= Y_MIN:
        raise ValueError(
            "軸の上限が下限以下です"
        )

    # X軸・Y軸を0から開始
    ax.set_xlim(
        X_MIN,
        x_upper
    )

    ax.set_ylim(
        Y_MIN,
        y_upper
    )

    # ========================================================
    # TICK SETTINGS
    # ========================================================

    ax.tick_params(
        axis="both",
        which="major",
        direction="in",
        length=8,
        width=1.5,
        labelsize=TICK_SIZE
    )

    ax.tick_params(
        axis="both",
        which="minor",
        direction="in",
        length=4,
        width=1.0
    )

    ax.xaxis.set_minor_locator(
        AutoMinorLocator()
    )

    ax.yaxis.set_minor_locator(
        AutoMinorLocator()
    )

    # ========================================================
    # FRAME
    # ========================================================

    for spine in ax.spines.values():
        spine.set_linewidth(1.5)

    # ========================================================
    # LEGEND
    # ========================================================

    ax.legend(
        loc="best",
        fontsize=LEGEND_SIZE,
        frameon=False
    )

    # ========================================================
    # NO TITLE / NO GRID
    # ========================================================

    ax.set_title("")
    ax.grid(False, which="both")

    # ========================================================
    # SQUARE LAYOUT
    # ========================================================

    # 保存画像の縦横比を正確に1:1にする
    # bbox_inches="tight" は使用しない
    fig.subplots_adjust(
        left=0.18,
        right=0.96,
        bottom=0.15,
        top=0.96
    )

    # ========================================================
    # SAVE
    # ========================================================

    if SAVE_PNG:

        png_path = output_base.with_suffix(".png")

        fig.savefig(
            png_path,
            dpi=DPI,
            facecolor="white"
        )

        print("Saved PNG:", png_path)

    if SAVE_PDF:

        pdf_path = output_base.with_suffix(".pdf")

        fig.savefig(
            pdf_path,
            facecolor="white"
        )

        print("Saved PDF:", pdf_path)

    plt.show()

    plt.close(fig)


# ============================================================
# 9. SAVE CSV
# ============================================================

def save_jv_csv(forward_data, reverse_data, output_base):

    combined = pd.DataFrame({

        "Forward_Excel_Row":
            pd.Series(
                forward_data["Excel_Row"].to_numpy()
            ),

        "Forward_Voltage_mV":
            pd.Series(
                forward_data["Voltage_mV"].to_numpy()
            ),

        "Forward_Current_mA":
            pd.Series(
                forward_data["Current_mA"].to_numpy()
            ),

        "Forward_Voltage_V":
            pd.Series(
                forward_data["Voltage_V"].to_numpy()
            ),

        "Forward_J_mA_cm2":
            pd.Series(
                forward_data[
                    "CurrentDensity_mA_cm2"
                ].to_numpy()
            ),

        "Reverse_Excel_Row":
            pd.Series(
                reverse_data["Excel_Row"].to_numpy()
            ),

        "Reverse_Voltage_mV":
            pd.Series(
                reverse_data["Voltage_mV"].to_numpy()
            ),

        "Reverse_Current_mA":
            pd.Series(
                reverse_data["Current_mA"].to_numpy()
            ),

        "Reverse_Voltage_V":
            pd.Series(
                reverse_data["Voltage_V"].to_numpy()
            ),

        "Reverse_J_mA_cm2":
            pd.Series(
                reverse_data[
                    "CurrentDensity_mA_cm2"
                ].to_numpy()
            )
    })

    csv_path = output_base.with_suffix(".csv")

    combined.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("Saved CSV:", csv_path)


# ============================================================
# 10. MAIN
# ============================================================

def main():

    print("=" * 60)
    print("JV CURVE PROCESSING")
    print("=" * 60)

    print("Active area:", ACTIVE_AREA_CM2, "cm2")
    print("Figure size:", FIGSIZE)
    print("DPI:", DPI)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Forward / Reverse判定
    forward_file, reverse_file = find_excel_files()

    # 保存ファイル名
    output_name = make_output_name(
        forward_file,
        reverse_file
    )

    output_base = OUTPUT_DIR / output_name

    print()
    print("Output name:", output_name)

    # Excel読み込み
    forward_data = read_iv_excel(
        forward_file
    )

    reverse_data = read_iv_excel(
        reverse_file
    )

    # CSV保存
    if SAVE_CSV:

        save_jv_csv(
            forward_data,
            reverse_data,
            output_base
        )

    # グラフ作成
    plot_jv(
        forward_data,
        reverse_data,
        output_base
    )

    print()
    print("=" * 60)
    print("PROCESSING COMPLETED")
    print("=" * 60)
    print("Output folder:", OUTPUT_DIR)


# ============================================================
# 11. EXECUTE
# ============================================================

main()
