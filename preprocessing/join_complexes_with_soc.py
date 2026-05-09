import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


def get_args():
    parser = argparse.ArgumentParser(description="임대단지 CSV와 SOC GeoPackage 공간 조인")
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="임대단지 CSV 경로 (x, y 좌표 컬럼 포함, utf-8-sig)",
    )
    parser.add_argument(
        "--gpkg",
        type=str,
        required=True,
        help="SOC 접근성 GeoPackage 경로 (concat_soc.gpkg)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/임대단지_사회인프라_공간조인.csv",
        help="출력 CSV 경로",
    )
    parser.add_argument("--x-col", type=str, default="x", help="경도 컬럼명")
    parser.add_argument("--y-col", type=str, default="y", help="위도 컬럼명")
    parser.add_argument("--crs", type=str, default="EPSG:4326", help="입력 CSV 좌표계")
    return parser.parse_args()


def load_csv_as_geodataframe(csv_path, x_col="x", y_col="y", crs="EPSG:4326"):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    geometry = gpd.points_from_xy(df[x_col], df[y_col])
    return gpd.GeoDataFrame(df, geometry=geometry, crs=crs)


def spatial_join_with_infrastructure(source_gdf, infrastructure_gdf):
    source_projected = source_gdf.to_crs(infrastructure_gdf.crs)
    joined = gpd.sjoin(source_projected, infrastructure_gdf, how="left", predicate="within")
    joined = joined.drop(columns=["index_right", "geometry"], errors="ignore")
    return pd.DataFrame(joined)


def main():
    args = get_args()

    housing_gdf = load_csv_as_geodataframe(args.csv, x_col=args.x_col, y_col=args.y_col, crs=args.crs)
    infrastructure_gdf = gpd.read_file(args.gpkg)

    print(f"GPKG CRS: {infrastructure_gdf.crs}")
    print(f"GPKG shape: {len(infrastructure_gdf):,} rows, {len(infrastructure_gdf.columns):,} columns")

    joined_df = spatial_join_with_infrastructure(housing_gdf, infrastructure_gdf)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joined_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {output_path}")
    print(f"Output shape: {len(joined_df):,} rows, {len(joined_df.columns):,} columns")


if __name__ == "__main__":
    main()
