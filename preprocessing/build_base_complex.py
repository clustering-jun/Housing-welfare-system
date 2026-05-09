import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def get_args():
    parser = argparse.ArgumentParser(description="임대단지 기본 데이터 집계 및 병합")
    parser.add_argument(
        "--housing-csv",
        type=str,
        required=True,
        help="평형별 임대단지 관리현황 CSV 경로 (cp949 인코딩)",
    )
    parser.add_argument(
        "--infra-csv",
        type=str,
        required=True,
        help="임대단지 연령별성별 사회인프라 공간조인 CSV 경로 (utf-8)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/base_complex.csv",
        help="출력 CSV 경로",
    )
    return parser.parse_args()


def weighted_mean(df, col, weight_col):
    return (df[col] * df[weight_col]).sum() / df[weight_col].sum()


def aggregate_by_complex(df1):
    area_cols = [
        "전용면적_제곱미터",
        "주거공용면적_제곱미터",
        "기타공용면적_제곱미터",
        "주차장면적_제곱미터",
        "공유대지면적_제곱미터",
    ]

    agg_rows = []
    for name, grp in df1.groupby("단지명", sort=False):
        row = {"단지명": name}
        row["단위평형코드_목록"] = ";".join(grp["단위평형코드"].astype(str).unique())
        row["평형종류수"] = grp["단위평형코드"].nunique()
        row["형별세대수_합계"] = int(grp["형별세대수"].sum())
        for col in area_cols:
            row[f"가중평균_{col}"] = round(weighted_mean(grp, col, "형별세대수"), 4)
        mode_idx = grp.groupby("방갯수")["형별세대수"].sum().idxmax()
        row["최빈_방갯수"] = int(mode_idx)
        agg_rows.append(row)

    df1_agg = pd.DataFrame(agg_rows)
    rename_map = {
        "가중평균_전용면적_제곱미터": "가중평균_전용면적_㎡",
        "가중평균_주거공용면적_제곱미터": "가중평균_주거공용면적_㎡",
        "가중평균_기타공용면적_제곱미터": "가중평균_기타공용면적_㎡",
        "가중평균_주차장면적_제곱미터": "가중평균_주차장면적_㎡",
        "가중평균_공유대지면적_제곱미터": "가중평균_공유대지면적_㎡",
    }
    df1_agg.rename(columns=rename_map, inplace=True)
    return df1_agg


def main():
    args = get_args()

    df1 = pd.read_csv(args.housing_csv, encoding="cp949")
    df2 = pd.read_csv(args.infra_csv, encoding="utf-8")

    df1_agg = aggregate_by_complex(df1)
    print(f"[df1 집계] {len(df1_agg)}개 단지")

    df_out = df2.merge(df1_agg, on="단지명", how="left")
    print(f"[병합 결과] shape: {df_out.shape}")
    print(f"df1 집계 컬럼이 채워진 행 수: {df_out['평형종류수'].notna().sum()} / {len(df_out)}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {output_path}")


if __name__ == "__main__":
    main()
