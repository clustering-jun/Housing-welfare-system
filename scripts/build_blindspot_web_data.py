import argparse
from pathlib import Path

import pandas as pd


WEB_COMPLEX_COLUMNS = [
    "단지명",
    "sido_kr",
    "sgg_kr",
    "sido_nm_e",
    "sgg_nm_e",
    "x",
    "y",
    "공급유형",
    "건설호수",
    "사각지대_등급",
    "취약도_hybrid가중치",
    "취약도_수동가중치",
    "취약도_entropy가중치",
    "취약도_인구",
    "취약도_시설",
    "취약도_접근성",
    "취약도_서비스이용",
    "취약도_거버넌스",
    "취약도_이상탐지",
    "mc_selection_frequency",
    "mc_mean_rank",
    "mc_rank_std",
    "robust_high_risk",
    "cluster_label",
    "취약_주요원인",
    "취약도_순위",
    "위험_백분위",
]


def get_args():
    parser = argparse.ArgumentParser(description="복지 사각지대 웹 대시보드용 CSV 데이터 생성")
    parser.add_argument(
        "--results-dir",
        type=str,
        default="outputs/welfare_blindspot",
        help="welfare_blindspot.py 출력 디렉토리",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="web/blindspot/data",
        help="웹 CSV 데이터 출력 디렉토리",
    )
    return parser.parse_args()


def extract_region(address):
    if not isinstance(address, str):
        return "", ""
    parts = address.strip().split()
    sido = parts[0] if len(parts) > 0 else ""
    sgg = parts[1] if len(parts) > 1 else ""
    return sido, sgg


def round_float_columns(frame):
    out = frame.copy()
    float_cols = out.select_dtypes(include=["float64"]).columns
    out[float_cols] = out[float_cols].round(4)
    return out


def read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig")


def main():
    args = get_args()
    results_dir = Path(args.results_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result_path = results_dir / "data" / "welfare_blindspot_results.csv"
    regional_path = results_dir / "dashboard" / "result_sgg_vulnerability_summary.csv"
    weights_path = results_dir / "data" / "weight_comparison_table.csv"
    alpha_path = results_dir / "data" / "alpha_sensitivity_analysis.csv"

    df = read_csv(result_path)
    print(f"Loaded: {len(df)} rows, {len(df.columns)} cols")

    if "기본주소" in df.columns:
        regions = df["기본주소"].apply(extract_region)
        df["sido_kr"] = [region[0] for region in regions]
        df["sgg_kr"] = [region[1] for region in regions]
    else:
        df["sido_kr"] = ""
        df["sgg_kr"] = ""

    keep_cols = [column for column in WEB_COMPLEX_COLUMNS if column in df.columns]
    missing_cols = [column for column in WEB_COMPLEX_COLUMNS if column not in df.columns]
    if missing_cols:
        print(f"Skipped missing columns: {', '.join(missing_cols)}")

    complexes = round_float_columns(df[keep_cols])
    complexes.to_csv(out_dir / "complexes.csv", index=False, encoding="utf-8-sig")
    print(f"Saved complexes.csv: {len(complexes)} rows")

    regional = round_float_columns(read_csv(regional_path))
    regional.to_csv(out_dir / "regional.csv", index=False, encoding="utf-8-sig")
    print(f"Saved regional.csv: {len(regional)} rows")

    weights = round_float_columns(read_csv(weights_path))
    weights.to_csv(out_dir / "weights.csv", index=False, encoding="utf-8-sig")
    print(f"Saved weights.csv: {len(weights)} rows")

    if alpha_path.exists():
        alpha = round_float_columns(read_csv(alpha_path))
        alpha.to_csv(out_dir / "alpha.csv", index=False, encoding="utf-8-sig")
        print(f"Saved alpha.csv: {len(alpha)} rows")

    print(f"완료: {out_dir}")


if __name__ == "__main__":
    main()
