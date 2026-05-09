import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_COLUMNS = [
    "gid",
    "emd_cd",
    "emd_nm_k",
    "emd_nm_e",
    "sgg_cd",
    "sgg_nm_k",
    "sgg_nm_e",
    "sido_cd",
    "sido_nm_k",
    "sido_nm_e",
    "raw_d_year",
    "geometry",
]


SOC_FILES = [
    (
        "(B100)국토통계_국토정책지표-경로당 접근성-250M_2023",
        "123.1 경로당(읍면동격자) 접근성.shp",
        "VALUE_Senior_citizens_centre",
    ),
    (
        "(B100)국토통계_국토정책지표-공공체육시설 접근성-250M_2023",
        "77.1 공공체육시설(읍면동격자) 접근성.shp",
        "VALUE_Public_sports_facility",
    ),
    (
        "(B100)국토통계_국토정책지표-공연문화시설 접근성-250M_2023",
        "109.1 공연문화시설(읍면동격자) 접근성.shp",
        "VALUE_Performance_cultural_facility",
    ),
    (
        "(B100)국토통계_국토정책지표-국공립도서관 접근성-250M_2023",
        "101.1 국공립도서관(읍면동격자) 접근성.shp",
        "VALUE_National_public_library",
    ),
    (
        "(B100)국토통계_국토정책지표-노인복지관 접근성-250M_2023",
        "119.1 노인복지관(읍면동격자) 접근성.shp",
        "VALUE_Senior_welfare_center",
    ),
    (
        "(B100)국토통계_국토정책지표-노인여가복지시설 접근성-250M_2023",
        "131.1 노인여가복지시설(읍면동격자) 접근성.shp",
        "VALUE_Senior_leisure_welfare_facility",
    ),
    (
        "(B100)국토통계_국토정책지표-도서관 접근성-250M_2023",
        "97.1 도서관(읍면동격자) 접근성.shp",
        "VALUE_Library",
    ),
    (
        "(B100)국토통계_국토정책지표-병원 접근성-250M_2023",
        "147.1 병원(읍면동격자) 접근성.shp",
        "VALUE_Hospital",
    ),
    (
        "(B100)국토통계_국토정책지표-보건기관 접근성-250M_2023",
        "135.1 보건기관(읍면동격자) 접근성.shp",
        "VALUE_Health_institution",
    ),
    (
        "(B100)국토통계_국토정책지표-생활권공원 접근성-250M_2023",
        "69.1 생활권공원(읍면동격자) 접근성.shp",
        "VALUE_Neighborhood_park",
    ),
    (
        "(B100)국토통계_국토정책지표-약국 접근성-250M_2023",
        "165.1 약국(읍면동격자) 접근성.shp",
        "VALUE_Pharmacy",
    ),
    (
        "(B100)국토통계_국토정책지표-어린이집 접근성-250M_2023",
        "81.1 어린이집(읍면동격자) 접근성.shp",
        "VALUE_Daycare_center",
    ),
    (
        "(B100)국토통계_국토정책지표-유치원 접근성-250M_2023",
        "85.1 유치원(읍면동격자) 접근성.shp",
        "VALUE_Kindergarten",
    ),
    (
        "(B100)국토통계_국토정책지표-응급의료시설 접근성-250M_2023",
        "159.1 응급의료시설(읍면동격자) 접근성.shp",
        "VALUE_Emergency_medical_facility",
    ),
    (
        "(B100)국토통계_국토정책지표-의원 접근성-250M_2023",
        "141.1 의원(읍면동격자) 접근성.shp",
        "VALUE_Clinic",
    ),
    (
        "(B100)국토통계_국토정책지표-작은도서관 접근성-250M_2023",
        "105.1 작은도서관(읍면동격자) 접근성.shp",
        "VALUE_Small_library",
    ),
    (
        "(B100)국토통계_국토정책지표-종합병원 접근성-250M_2023",
        "153.1 종합병원(읍면동격자) 접근성.shp",
        "VALUE_General_hospital",
    ),
    (
        "(B100)국토통계_국토정책지표-종합사회복지관 접근성-250M_2023",
        "115.1 종합사회복지관(읍면동격자) 접근성.shp",
        "VALUE_Community_welfare_center",
    ),
    (
        "(B100)국토통계_국토정책지표-주제공원 접근성-250M_2023",
        "73.1 주제공원(읍면동격자) 접근성.shp",
        "VALUE_Theme_park",
    ),
    (
        "(B100)국토통계_국토정책지표-초등학교 접근성-250M_2023",
        "89.1 초등학교(읍면동격자) 접근성.shp",
        "VALUE_Elementary_school",
    ),
]


SPATIAL_JOIN_FILES = [
    (
        "(B100)국토통계_국토정책지표-생활체육시설 접근성-500M_2019",
        "생활과 복지-14.생활체육시설접근성.shp",
        "VALUE_Community_sports_facility",
    ),
    (
        "(B100)국토통계_국토정책지표-아동 온종일 돌봄센터 접근성-250M_2023",
        "93.2 온종일 돌봄센터(시군구격자) 접근성.shp",
        "VALUE_Child_allday_care_center",
    ),
]


def get_args():
    parser = argparse.ArgumentParser(description="SOC 접근성 레이어 통합 GeoPackage 생성")
    parser.add_argument(
        "--base-dir",
        type=str,
        required=True,
        help="공간 데이터 루트 디렉토리 (SOC 하위 폴더들이 있는 위치)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="출력 GeoPackage 경로 (기본: base_dir/concat_soc.gpkg)",
    )
    return parser.parse_args()


def read_accessibility_layer(base_dir, folder_name, shapefile_name, value_column_name):
    file_path = base_dir / folder_name / shapefile_name
    gdf = gpd.read_file(file_path)
    if "value" not in gdf.columns:
        raise KeyError(f"'value' column not found in: {file_path}")
    return gdf.rename(columns={"value": value_column_name})


def build_base_grid(base_dir):
    folder_name, shapefile_name, value_column_name = SOC_FILES[0]
    base_gdf = read_accessibility_layer(base_dir, folder_name, shapefile_name, value_column_name)
    selected_columns = [c for c in BASE_COLUMNS if c in base_gdf.columns]
    result = base_gdf[selected_columns].copy()
    result[value_column_name] = base_gdf[value_column_name]
    print(f"Base grid loaded: {len(result):,} rows, CRS: {result.crs}")
    return result


def merge_same_grid_layers(base_gdf, base_dir):
    result = base_gdf.copy()
    for folder_name, shapefile_name, value_column_name in SOC_FILES[1:]:
        print(f"Merging: {value_column_name}")
        layer_gdf = read_accessibility_layer(base_dir, folder_name, shapefile_name, value_column_name)
        result = result.merge(layer_gdf[["gid", value_column_name]], on="gid", how="left")
        print(f"  Missing values: {result[value_column_name].isna().sum():,}")
    return result


def spatially_join_different_grid_layer(base_gdf, base_dir, folder_name, shapefile_name, value_column_name):
    file_path = base_dir / folder_name / shapefile_name
    print(f"Spatially joining: {value_column_name}")
    target_gdf = gpd.read_file(file_path)
    if target_gdf.crs != base_gdf.crs:
        print(f"  Reprojecting from {target_gdf.crs} to {base_gdf.crs}")
        target_gdf = target_gdf.to_crs(base_gdf.crs)
    centroids = base_gdf[["gid", "geometry"]].copy()
    centroids["geometry"] = centroids.geometry.centroid
    joined = gpd.sjoin(centroids, target_gdf[["value", "geometry"]], how="left", predicate="within")
    joined = joined[["gid", "value"]].rename(columns={"value": value_column_name})
    return joined.drop_duplicates(subset="gid")


def merge_different_grid_layers(base_gdf, base_dir):
    result = base_gdf.copy()
    for folder_name, shapefile_name, value_column_name in SPATIAL_JOIN_FILES:
        joined_values = spatially_join_different_grid_layer(
            result, base_dir, folder_name, shapefile_name, value_column_name
        )
        result = result.merge(joined_values, on="gid", how="left")
        print(f"  Missing values: {result[value_column_name].isna().sum():,}")
    return result


def reorder_columns(gdf):
    base_cols = [c for c in BASE_COLUMNS if c in gdf.columns and c != "geometry"]
    value_cols = [vc for _, _, vc in SOC_FILES] + [vc for _, _, vc in SPATIAL_JOIN_FILES]
    final_cols = base_cols + value_cols + ["geometry"]
    final_cols = [c for c in final_cols if c in gdf.columns]
    return gdf[final_cols]


def save_geopackage(gdf, output_path, layer="concat_soc"):
    if output_path.exists():
        output_path.unlink()
    gdf.to_file(output_path, driver="GPKG", layer=layer)


def main():
    args = get_args()
    base_dir = Path(args.base_dir)
    output_path = Path(args.output) if args.output else base_dir / "concat_soc.gpkg"

    base_gdf = build_base_grid(base_dir)
    result_gdf = merge_same_grid_layers(base_gdf, base_dir)
    result_gdf = merge_different_grid_layers(result_gdf, base_dir)
    result_gdf = reorder_columns(result_gdf)
    result_gdf = gpd.GeoDataFrame(result_gdf, geometry="geometry", crs=base_gdf.crs)

    print(f"\nFinal shape: {result_gdf.shape}")
    print(f"Saving to: {output_path}")
    save_geopackage(result_gdf, output_path)
    print("Done.")


if __name__ == "__main__":
    main()
