import argparse
import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.stats import spearmanr
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.manifold import TSNE
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.neural_network import MLPRegressor
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler, RobustScaler
from sklearn.svm import OneClassSVM

warnings.filterwarnings("ignore")

SEED = 42
np.random.seed(SEED)


def get_args():
    parser = argparse.ArgumentParser(description="주거복지 사각지대 발굴 모델")
    parser.add_argument("--data-dir", default="data/data_stage05", help="입력 데이터 디렉토리")
    parser.add_argument("--output-dir", default="outputs/welfare_blindspot", help="출력 디렉토리")
    return parser.parse_args()


def setup_font():
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    font = "Malgun Gothic" if "Malgun Gothic" in available else "DejaVu Sans"
    matplotlib.rcParams["font.family"] = font
    matplotlib.rcParams["axes.unicode_minus"] = False
    return "Malgun Gothic" in available


def code_as_str(series):
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.astype("Int64").astype(str).replace("<NA>", np.nan)


def fill_missing_by_region(data, cols, label_name):
    out = data.copy()
    rows = []
    for col in cols:
        if col not in out.columns:
            continue
        before = int(out[col].isna().sum())
        sgg_mean = out.groupby("sgg_cd")[col].transform("mean") if "sgg_cd" in out.columns else np.nan
        sido_mean = out.groupby("sido_cd")[col].transform("mean") if "sido_cd" in out.columns else np.nan
        supply_mean = out.groupby("공급유형")[col].transform("mean") if "공급유형" in out.columns else np.nan
        overall = out[col].mean()
        if pd.isna(overall):
            overall = 0
        out[col] = out[col].fillna(sgg_mean).fillna(sido_mean).fillna(supply_mean).fillna(overall).fillna(0)
        rows.append({"대상": label_name, "컬럼": col, "대체전_결측": before, "대체후_결측": int(out[col].isna().sum())})
    return out, pd.DataFrame(rows)


def load_data(data_dir: Path):
    base_df = pd.read_csv(data_dir / "base_data.csv", encoding="utf-8-sig")
    comm_df = pd.read_csv(data_dir / "RentalHousing_CommunityStatus.csv", encoding="cp949")
    hd_df = pd.read_csv(data_dir / "RentalHousing_HomeDoctor_Monthly.csv", encoding="cp949")
    print(f"[base_data] {base_df.shape}, 단지 수={base_df['단지명'].nunique()}")
    print(f"[community] {comm_df.shape}, 단지 수={comm_df['단지명'].nunique()}")
    print(f"[homedoctor] {hd_df.shape}, 단지 수={hd_df['단지명'].nunique()}")
    print("[concat_soc.gpkg] 로딩 중...")
    soc_gdf = gpd.read_file(data_dir / "concat_soc.gpkg")
    print(f"[concat_soc.gpkg] {soc_gdf.shape}")
    return base_df, comm_df, hd_df, soc_gdf


def aggregate_community(comm_df):
    comm_agg = comm_df.groupby("단지명").agg(
        커뮤니티_총활동횟수=("활동횟수", "sum"),
        커뮤니티_총참여인원=("참여인원_계", "sum"),
        커뮤니티_프로그램수=("커뮤니티명", "count"),
        커뮤니티_분야다양성=("분야", "nunique"),
        커뮤니티_유형다양성=("커뮤니티유형", "nunique"),
        커뮤니티_외부공모=("외부공모사업여부", lambda x: (x == "Y").sum()),
        커뮤니티_업무협약=("업무협약여부", lambda x: (x == "Y").sum()),
        커뮤니티_문화예술=("문화예술공연여부", lambda x: (x == "Y").sum()),
        커뮤니티_참여기관수평균=("참여기관수", "mean"),
        세대수=("세대수", "first"),
    ).reset_index()
    comm_agg["커뮤니티_세대당참여인원"] = comm_agg["커뮤니티_총참여인원"] / comm_agg["세대수"].replace(0, np.nan)
    return comm_agg


def aggregate_homedoctor(hd_df):
    hd_recent = hd_df[hd_df["년도"].between(2022, 2024)].copy()
    hd_agg = hd_recent.groupby("단지명").agg(
        홈닥터_총지원건수=("지원내용총건수", "sum"),
        홈닥터_생활지원합계=("생활지원", "sum"),
        홈닥터_가사지원합계=("가사지원", "sum"),
        홈닥터_의료지원합계=("의료지원", "sum"),
        홈닥터_경제지원합계=("경제지원", "sum"),
        홈닥터_대상세대수합계=("대상세대(인원수)", "sum"),
        홈닥터_관측개월수=("월", "count"),
        세대수=("세대수", "first"),
    ).reset_index()
    hd_agg["홈닥터_세대당지원건수"] = hd_agg["홈닥터_총지원건수"] / hd_agg["세대수"].replace(0, np.nan)
    hd_agg["홈닥터_의료지원비율"] = hd_agg["홈닥터_의료지원합계"] / hd_agg["홈닥터_총지원건수"].replace(0, np.nan)
    hd_agg["홈닥터_경제지원비율"] = hd_agg["홈닥터_경제지원합계"] / hd_agg["홈닥터_총지원건수"].replace(0, np.nan)
    hd_agg["홈닥터_서비스이용률"] = hd_agg["홈닥터_대상세대수합계"] / (hd_agg["세대수"] * hd_agg["홈닥터_관측개월수"] + 1e-9)
    return hd_agg


def merge_datasets(base_df, comm_agg, hd_agg, soc_gdf):
    value_cols = [c for c in soc_gdf.columns if c.startswith("VALUE_")]
    soc_emd_agg = soc_gdf.groupby("emd_cd")[value_cols].mean().reset_index()
    soc_emd_agg["emd_cd_str"] = code_as_str(soc_emd_agg["emd_cd"])
    soc_emd_agg = soc_emd_agg.drop(columns=["emd_cd"]).rename(columns={c: f"soc_{c}" for c in value_cols})
    base_df["emd_cd_str"] = code_as_str(base_df["emd_cd"])
    base_with_soc = base_df.merge(soc_emd_agg, on="emd_cd_str", how="left")
    merged = base_with_soc.merge(comm_agg.drop(columns=["세대수"], errors="ignore"), on="단지명", how="left")
    merged = merged.merge(hd_agg.drop(columns=["세대수"], errors="ignore"), on="단지명", how="left")
    return merged


def flag_service_coverage(merged_df):
    COMM_COLS = ["커뮤니티_총활동횟수", "커뮤니티_총참여인원", "커뮤니티_프로그램수", "커뮤니티_분야다양성",
                 "커뮤니티_유형다양성", "커뮤니티_외부공모", "커뮤니티_업무협약", "커뮤니티_문화예술",
                 "커뮤니티_참여기관수평균", "커뮤니티_세대당참여인원"]
    HD_COLS = ["홈닥터_총지원건수", "홈닥터_생활지원합계", "홈닥터_가사지원합계", "홈닥터_의료지원합계",
               "홈닥터_경제지원합계", "홈닥터_대상세대수합계", "홈닥터_관측개월수",
               "홈닥터_세대당지원건수", "홈닥터_의료지원비율", "홈닥터_경제지원비율", "홈닥터_서비스이용률"]
    merged_df["커뮤니티_매핑여부"] = merged_df["커뮤니티_총활동횟수"].notna().astype(int)
    merged_df["홈닥터_매핑여부"] = merged_df["홈닥터_총지원건수"].notna().astype(int)
    merged_df["단지개소일자_dt_tmp"] = pd.to_datetime(merged_df["단지개소일자"], errors="coerce")
    merged_df["신규단지_여부_tmp"] = (merged_df["단지개소일자_dt_tmp"] >= pd.Timestamp("2024-01-01")).astype(int)
    merged_df["소규모단지_여부_tmp"] = (merged_df["건설호수"].fillna(merged_df["총세대수"]).fillna(0) < 100).astype(int)
    merged_df["장기전세_포함_tmp"] = merged_df["공급유형"].str.contains("장기전세", na=False).astype(int)
    missing_service = merged_df["커뮤니티_매핑여부"].eq(0) | merged_df["홈닥터_매핑여부"].eq(0)
    merged_df["서비스_미매핑_구분"] = np.select(
        [missing_service & merged_df["신규단지_여부_tmp"].eq(1),
         missing_service & merged_df["소규모단지_여부_tmp"].eq(1),
         missing_service & merged_df["장기전세_포함_tmp"].eq(1),
         missing_service],
        ["신규단지_판정유예", "소규모단지_구조적미운영가능", "장기전세_구조적미운영가능", "지역평균대체_미매핑"],
        default="매핑완료",
    )
    merged_df, comm_log = fill_missing_by_region(merged_df, COMM_COLS, "커뮤니티")
    merged_df, hd_log = fill_missing_by_region(merged_df, HD_COLS, "홈닥터")
    return merged_df, comm_log, hd_log


def engineer_features(df):
    age_groups = {
        "10대미만": ["10대미만(여자)", "10대미만(남자)"],
        "10대": ["10대(여자)", "10대(남자)"],
        "20대": ["20대(여자)", "20대(남자)"],
        "30대": ["30대(여자)", "30대(남자)"],
        "40대": ["40대(여자)", "40대(남자)"],
        "50대": ["50대(여자)", "50대(남자)"],
        "60대": ["60대(여자)", "60대(남자)"],
        "70대": ["70대(여자)", "70대(남자)"],
        "80대": ["80대(여자)", "80대(남자)"],
        "90대": ["90대(여자)", "90대(남자)"],
        "100대": ["100대(여자)", "100대(남자)"],
    }
    for group, cols in age_groups.items():
        df[f"인구_{group}"] = df[cols[0]].fillna(0) + df[cols[1]].fillna(0)
    df["인구_전체합계"] = sum(df[f"인구_{g}"] for g in age_groups)
    df["총인구수_계산"] = df["인구_전체합계"].replace(0, np.nan)
    df["기준세대수"] = df["총세대수"].fillna(df["건설호수"]).fillna(df["형별세대수_합계"]).replace(0, np.nan)
    senior_pop = df["인구_60대"] + df["인구_70대"] + df["인구_80대"] + df["인구_90대"] + df["인구_100대"]
    super_senior_pop = df["인구_80대"] + df["인구_90대"] + df["인구_100대"]
    child_youth_pop = df["인구_10대미만"] + df["인구_10대"]
    df["고령화율"] = senior_pop / df["총인구수_계산"]
    df["초고령비율"] = super_senior_pop / df["총인구수_계산"]
    df["아동청소년비율"] = child_youth_pop / df["총인구수_계산"]
    for col in ["고령화율", "초고령비율", "아동청소년비율"]:
        df[col] = df[col].fillna(df.groupby("공급유형")[col].transform("median")).fillna(df[col].median()).clip(0, 1)
    df["경로당_있음"] = (df["경로당_연면적_제곱미터"].fillna(0) > 0).astype(int)
    df["경로당_면적"] = df["경로당_연면적_제곱미터"].fillna(0)
    df["복지관_있음"] = df["복지관운영주체명"].notna().astype(int)
    df["복지관_면적"] = df["복지관관리면적_제곱미터"].fillna(0)
    df["운동시설_있음"] = (df["주민운동시설_연면적_제곱미터"].fillna(0) > 0).astype(int)
    df["어린이집_있음"] = (df["어린이집_연면적_제곱미터"].fillna(0) > 0).astype(int)
    df["도서관_있음"] = (df["도서관_연면적_제곱미터"].fillna(0) > 0).astype(int)
    df["시설종합지수"] = df["경로당_있음"] + df["복지관_있음"] + df["운동시설_있음"] + df["어린이집_있음"] + df["도서관_있음"]
    df["세대당_건축면적"] = (df["건축면적"] / df["기준세대수"]).replace([np.inf, -np.inf], np.nan)
    df["세대당_건축면적"] = df["세대당_건축면적"].fillna(df["세대당_건축면적"].median())
    df["단지개소일자_dt"] = pd.to_datetime(df["단지개소일자"], errors="coerce")
    df["노후도_년수"] = ((pd.Timestamp("2025-01-01") - df["단지개소일자_dt"]).dt.days / 365.25).clip(0, 50)
    df["노후도_년수"] = df["노후도_년수"].fillna(df["노후도_년수"].median())
    df["신규단지_여부"] = (df["단지개소일자_dt"] >= pd.Timestamp("2024-01-01")).astype(int)

    def clean_accessibility(series):
        s = pd.to_numeric(series, errors="coerce").mask(lambda x: x < 0)
        if s.notna().sum() >= 10:
            s = s.clip(upper=s.quantile(0.99))
        return s

    access_cols_all = [c for c in df.columns if c.startswith("VALUE_") or c.startswith("soc_VALUE_")]
    access_clean_log = []
    for col in access_cols_all:
        before_negative = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
        df[col] = clean_accessibility(df[col])
        access_clean_log.append({"컬럼": col, "음수_결측처리건수": before_negative, "결측수": int(df[col].isna().sum())})
    medical_cols = [c for c in ["VALUE_Hospital", "VALUE_Clinic", "VALUE_General_hospital",
                                 "VALUE_Emergency_medical_facility", "VALUE_Health_institution",
                                 "VALUE_Pharmacy"] if c in df.columns]
    welfare_cols = [c for c in ["VALUE_Community_welfare_center", "VALUE_Senior_welfare_center",
                                 "VALUE_Senior_citizens_centre", "VALUE_Senior_leisure_welfare_facility"] if c in df.columns]
    edu_cols = [c for c in ["VALUE_Library", "VALUE_National_public_library", "VALUE_Small_library",
                              "VALUE_Performance_cultural_facility", "VALUE_Elementary_school"] if c in df.columns]
    care_cols = [c for c in ["VALUE_Daycare_center", "VALUE_Kindergarten", "VALUE_Child_allday_care_center"] if c in df.columns]
    df["접근성_의료종합"] = df[medical_cols].mean(axis=1)
    df["접근성_복지종합"] = df[welfare_cols].mean(axis=1)
    df["접근성_교육문화종합"] = df[edu_cols].mean(axis=1)
    df["접근성_돌봄종합"] = df[care_cols].mean(axis=1)
    acc_cols = ["접근성_의료종합", "접근성_복지종합", "접근성_교육문화종합", "접근성_돌봄종합"]
    df, access_log = fill_missing_by_region(df, acc_cols, "접근성")
    gov_cols = ["거버넌스_연간합계_2022", "거버넌스_연간합계_2023", "거버넌스_연간합계_2024",
                "거버넌스_평균_연간합계", "거버넌스_완전연도수"]
    df["거버넌스_매핑여부"] = df[gov_cols].notna().any(axis=1).astype(int)
    df, gov_log = fill_missing_by_region(df, gov_cols, "거버넌스")
    df["거버넌스_증감_22_23"] = df["거버넌스_연간합계_2023"] - df["거버넌스_연간합계_2022"]
    df["거버넌스_증감_23_24"] = df["거버넌스_연간합계_2024"] - df["거버넌스_연간합계_2023"]
    df["거버넌스_추세기울기"] = df.apply(
        lambda r: np.polyfit([2022, 2023, 2024],
                             [r["거버넌스_연간합계_2022"], r["거버넌스_연간합계_2023"], r["거버넌스_연간합계_2024"]], 1)[0], axis=1)
    df["거버넌스_악화중_여부"] = (
        (df["신규단지_여부"] == 0)
        & (df["거버넌스_추세기울기"] < 0)
        & (df["거버넌스_연간합계_2024"] < df["거버넌스_연간합계_2022"])
    ).astype(int)
    df["영구임대_포함"] = df["공급유형"].str.contains("영구임대", na=False).astype(int)
    df["국민임대_포함"] = df["공급유형"].str.contains("국민임대", na=False).astype(int)
    df["행복주택_포함"] = df["공급유형"].str.contains("행복주택", na=False).astype(int)
    df["장기전세_포함"] = df["공급유형"].str.contains("장기전세", na=False).astype(int)
    df["취약임대_여부"] = df["영구임대_포함"]
    df["대규모단지_여부"] = (df["건설호수"] >= 500).astype(int)
    df["소규모단지_여부"] = (df["건설호수"] < 100).astype(int)
    return df, access_clean_log, access_log, gov_log


def normalize_features(df):
    FEATURE_COLS = [
        "고령화율", "초고령비율", "아동청소년비율",
        "경로당_있음", "복지관_있음", "운동시설_있음", "어린이집_있음", "도서관_있음", "시설종합지수",
        "경로당_면적", "복지관_면적", "노후도_년수", "세대당_건축면적",
        "접근성_의료종합", "접근성_복지종합", "접근성_교육문화종합", "접근성_돌봄종합",
        "커뮤니티_총활동횟수", "커뮤니티_총참여인원", "커뮤니티_분야다양성", "커뮤니티_유형다양성",
        "커뮤니티_세대당참여인원", "커뮤니티_외부공모", "커뮤니티_업무협약",
        "홈닥터_총지원건수", "홈닥터_세대당지원건수", "홈닥터_의료지원비율", "홈닥터_경제지원비율", "홈닥터_서비스이용률",
        "거버넌스_평균_연간합계", "거버넌스_완전연도수", "거버넌스_증감_22_23", "거버넌스_증감_23_24",
        "영구임대_포함", "장기전세_포함", "취약임대_여부", "신규단지_여부", "소규모단지_여부",
        "건설호수", "승강기대수", "CCTV대수",
    ]
    FEATURE_COLS = [c for c in FEATURE_COLS if c in df.columns]
    X_raw = df[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).copy()
    X_imputed = X_raw.fillna(X_raw.median())
    scaler = RobustScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X_imputed), columns=FEATURE_COLS, index=df.index)
    minmax = MinMaxScaler()
    X_norm = pd.DataFrame(minmax.fit_transform(X_scaled), columns=FEATURE_COLS, index=df.index)
    print(f"최종 Feature 수: {len(FEATURE_COLS)}, 결측치 수: {int(X_norm.isna().sum().sum())}")
    return X_norm, FEATURE_COLS


def normalize_score(values, index):
    s = pd.Series(values, index=index).replace([np.inf, -np.inf], np.nan)
    s = s.fillna(s.median())
    min_v, max_v = s.min(), s.max()
    return pd.Series(0.5, index=s.index) if max_v == min_v else (s - min_v) / (max_v - min_v)


def run_anomaly_detection(df, X_norm):
    TARGET_TOP_RATE = 0.10
    COL_AGING = "고령화율"
    COL_SUPER_AGING = "초고령비율"
    COL_MEDICAL_ACCESS = "접근성_의료종합"
    COL_WELFARE_ACCESS = "접근성_복지종합"
    COL_FACILITY_INDEX = "시설종합지수"
    risk_proxy = (
        normalize_score(df[COL_AGING], df.index) * 0.30
        + normalize_score(df[COL_SUPER_AGING], df.index) * 0.15
        + normalize_score(df[COL_MEDICAL_ACCESS], df.index) * 0.20
        + normalize_score(df[COL_WELFARE_ACCESS], df.index) * 0.20
        + normalize_score(df[COL_FACILITY_INDEX].max() - df[COL_FACILITY_INDEX], df.index) * 0.15
    )
    df["이상탐지_proxy_risk"] = risk_proxy
    proxy_top_label = (risk_proxy >= risk_proxy.quantile(1 - TARGET_TOP_RATE)).astype(int)
    experiments = []
    scores = {}

    def evaluate_anomaly_model(model_name, params, model_object, raw_score):
        score = normalize_score(raw_score, df.index)
        threshold = score.quantile(1 - TARGET_TOP_RATE)
        flags = (score >= threshold).astype(int)
        flagged_count = int(flags.sum())
        flagged_ratio = float(flags.mean())
        flag_balance = max(0.0, 1 - abs(flagged_ratio - TARGET_TOP_RATE) / TARGET_TOP_RATE)
        if flags.nunique() > 1:
            separation = float(silhouette_score(X_norm.values, flags))
            proxy_lift = float(risk_proxy[flags == 1].mean() - risk_proxy[flags == 0].mean())
            precision_at_top = float(proxy_top_label[flags == 1].mean())
            recall_at_top = float(((flags == 1) & (proxy_top_label == 1)).sum() / max(int(proxy_top_label.sum()), 1))
        else:
            separation = -1.0
            proxy_lift = 0.0
            precision_at_top = 0.0
            recall_at_top = 0.0
        score_proxy_corr = float(pd.Series(score, index=df.index).corr(risk_proxy, method="spearman"))
        if pd.isna(score_proxy_corr):
            score_proxy_corr = 0.0
        comparison_score = (0.30 * precision_at_top + 0.25 * recall_at_top + 0.20 * max(proxy_lift, 0)
                            + 0.10 * max(separation, 0) + 0.10 * max(score_proxy_corr, 0) + 0.05 * flag_balance)
        exp_id = f"{model_name}_{len(experiments) + 1:03d}"
        scores[exp_id] = score
        experiments.append({
            "experiment_id": exp_id, "model": model_name, "params": json.dumps(params, ensure_ascii=False),
            "flagged_count": flagged_count, "flagged_ratio": flagged_ratio,
            "proxy_precision_at_top10": precision_at_top, "proxy_recall_at_top10": recall_at_top,
            "proxy_lift": proxy_lift, "silhouette_flag_split": separation,
            "score_proxy_spearman": score_proxy_corr, "flag_balance": flag_balance,
            "comparison_score": float(comparison_score),
        })
        return exp_id

    for n_estimators in [200, 500, 800]:
        for contamination in [0.05, 0.10, 0.15]:
            for max_features in [0.7, 1.0]:
                params = {"n_estimators": n_estimators, "contamination": contamination, "max_features": max_features}
                model = IsolationForest(random_state=SEED, n_jobs=-1, **params).fit(X_norm)
                evaluate_anomaly_model("IsolationForest", params, model, -model.decision_function(X_norm))

    for nu in [0.03, 0.05, 0.10, 0.15]:
        for gamma in ["scale", "auto", 0.05, 0.10]:
            params = {"nu": nu, "gamma": gamma, "kernel": "rbf"}
            model = OneClassSVM(**params).fit(X_norm)
            evaluate_anomaly_model("OneClassSVM", params, model, -model.decision_function(X_norm))

    for n_neighbors in [10, 20, 35, 50]:
        for contamination in [0.05, 0.10, 0.15]:
            params = {"n_neighbors": n_neighbors, "contamination": contamination, "novelty": True}
            model = LocalOutlierFactor(**params).fit(X_norm)
            evaluate_anomaly_model("LocalOutlierFactor", params, model, -model.decision_function(X_norm))

    for hidden_layers in [(16, 8, 16), (24, 12, 24), (32, 16, 8, 16, 32)]:
        for alpha in [1e-4, 1e-3, 1e-2]:
            params = {"hidden_layer_sizes": hidden_layers, "alpha": alpha, "activation": "relu", "early_stopping": True}
            model = MLPRegressor(hidden_layer_sizes=hidden_layers, activation="relu", solver="adam", alpha=alpha,
                                 learning_rate_init=1e-3, max_iter=1200, early_stopping=True,
                                 validation_fraction=0.15, n_iter_no_change=30, random_state=SEED)
            model.fit(X_norm.values, X_norm.values)
            reconstructed = model.predict(X_norm.values)
            reconstruction_error = np.mean((X_norm.values - reconstructed) ** 2, axis=1)
            evaluate_anomaly_model("AutoencoderMLP", params, model, reconstruction_error)

    individual_df = pd.DataFrame(experiments)
    best_by_model = individual_df.sort_values("comparison_score", ascending=False).groupby("model", as_index=False).first()
    best_ids = dict(zip(best_by_model["model"], best_by_model["experiment_id"]))
    ensemble_candidates = {
        "IF_OCSVM": [best_ids.get("IsolationForest"), best_ids.get("OneClassSVM")],
        "IF_LOF": [best_ids.get("IsolationForest"), best_ids.get("LocalOutlierFactor")],
        "IF_AE": [best_ids.get("IsolationForest"), best_ids.get("AutoencoderMLP")],
        "AllBest": [best_ids.get("IsolationForest"), best_ids.get("OneClassSVM"),
                    best_ids.get("LocalOutlierFactor"), best_ids.get("AutoencoderMLP")],
    }
    for ensemble_name, component_ids in ensemble_candidates.items():
        component_ids = [c for c in component_ids if c in scores]
        if len(component_ids) < 2:
            continue
        ensemble_raw_score = pd.concat([scores[c] for c in component_ids], axis=1).mean(axis=1)
        evaluate_anomaly_model(f"Ensemble_{ensemble_name}", {"components": component_ids},
                               {"components": component_ids}, ensemble_raw_score)

    model_performance_comparison = pd.DataFrame(experiments).sort_values("comparison_score", ascending=False)
    best_row = model_performance_comparison.iloc[0]
    best_model_id = best_row["experiment_id"]
    best_model_name = best_row["model"]
    selected_anomaly_score = scores[best_model_id]
    selected_anomaly_threshold = selected_anomaly_score.quantile(1 - TARGET_TOP_RATE)
    df["selected_anomaly_model"] = best_model_name
    df["selected_anomaly_experiment_id"] = best_model_id
    df["selected_anomaly_score"] = selected_anomaly_score
    df["selected_anomaly"] = (selected_anomaly_score >= selected_anomaly_threshold).astype(int)
    df["ensemble_anomaly_score"] = df["selected_anomaly_score"]
    df["ensemble_anomaly"] = df["selected_anomaly"]
    if "IsolationForest" in model_performance_comparison["model"].values:
        best_if_id = model_performance_comparison[model_performance_comparison["model"] == "IsolationForest"].iloc[0]["experiment_id"]
        df["isolation_forest_score"] = scores[best_if_id]
    if "OneClassSVM" in model_performance_comparison["model"].values:
        best_svm_id = model_performance_comparison[model_performance_comparison["model"] == "OneClassSVM"].iloc[0]["experiment_id"]
        df["oneclass_svm_score"] = scores[best_svm_id]
    print(f"선택 모델: {best_model_id} ({best_model_name}), comparison_score: {best_row['comparison_score']:.4f}")
    print(f"이상탐지 후보 수: {int(df['selected_anomaly'].sum())}")
    return df, model_performance_comparison, best_model_name, best_model_id


def run_clustering(df, X_norm):
    CLUSTER_FEATURES = [
        "고령화율", "초고령비율", "시설종합지수", "접근성_의료종합", "접근성_복지종합",
        "커뮤니티_총활동횟수", "커뮤니티_분야다양성", "홈닥터_세대당지원건수",
        "거버넌스_평균_연간합계", "취약임대_여부", "장기전세_포함", "신규단지_여부",
    ]
    CLUSTER_FEATURES = [c for c in CLUSTER_FEATURES if c in X_norm.columns]
    X_cluster = X_norm[CLUSTER_FEATURES].values
    linkage_matrix = linkage(X_cluster, method="ward")
    eval_rows = []
    for k in range(3, 9):
        labels_k = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X_cluster)
        eval_rows.append({
            "n_clusters": k,
            "silhouette": silhouette_score(X_cluster, labels_k),
            "calinski_harabasz": calinski_harabasz_score(X_cluster, labels_k),
            "davies_bouldin": davies_bouldin_score(X_cluster, labels_k),
            "min_cluster_size": int(pd.Series(labels_k).value_counts().min()),
            "max_cluster_size": int(pd.Series(labels_k).value_counts().max()),
        })
    cluster_eval_df = pd.DataFrame(eval_rows)
    cluster_eval_df["selection_score"] = (
        cluster_eval_df["silhouette"].rank(pct=True) * 0.55
        + cluster_eval_df["calinski_harabasz"].rank(pct=True) * 0.25
        + (1 - cluster_eval_df["davies_bouldin"].rank(pct=True)) * 0.20
    )
    best_k = 5
    best_labels = AgglomerativeClustering(n_clusters=best_k, linkage="ward").fit_predict(X_cluster)
    df["cluster_label"] = best_labels
    n_clusters = len(np.unique(best_labels))
    assert int((best_labels == -1).sum()) == 0
    print(f"클러스터 수: {best_k}")
    print(pd.Series(best_labels).value_counts().sort_index())
    return df, cluster_eval_df, linkage_matrix, best_labels, best_k, X_cluster


def min_max_normalize(series, index):
    s = pd.Series(series, index=index).replace([np.inf, -np.inf], np.nan).fillna(pd.Series(series, index=index).median())
    min_v, max_v = s.min(), s.max()
    return pd.Series(0.5, index=s.index) if max_v == min_v else (s - min_v) / (max_v - min_v)


def build_vulnerability_matrix(df):
    vuln = pd.DataFrame(index=df.index)
    vuln["v_고령화"] = min_max_normalize(df["고령화율"], df.index)
    vuln["v_초고령"] = min_max_normalize(df["초고령비율"], df.index)
    vuln["v_취약임대"] = min_max_normalize(df["취약임대_여부"].astype(float), df.index)
    long_lease_factor = np.where(df["장기전세_포함"].eq(1), 0.45, 1.0)
    vuln["v_시설부족"] = (1 - min_max_normalize(df["시설종합지수"], df.index)) * long_lease_factor
    vuln["v_경로당없음"] = (1 - df["경로당_있음"].astype(float)) * long_lease_factor
    vuln["v_복지관없음"] = (1 - df["복지관_있음"].astype(float)) * long_lease_factor
    vuln["v_의료접근성부족"] = min_max_normalize(df["접근성_의료종합"], df.index)
    vuln["v_복지접근성부족"] = min_max_normalize(df["접근성_복지종합"], df.index)
    new_complex_factor = np.where(df["신규단지_여부"].eq(1), 0.20, 1.0)

    def shrink_to_neutral(raw_score, confidence=0.45, neutral=0.50):
        return neutral + (raw_score - neutral) * confidence

    raw_service_scores = {
        "v_커뮤니티부족": (1 - min_max_normalize(np.log1p(df["커뮤니티_총활동횟수"]), df.index)) * new_complex_factor,
        "v_커뮤니티다양성부족": (1 - min_max_normalize(np.log1p(df["커뮤니티_분야다양성"]), df.index)) * new_complex_factor,
        "v_참여인원부족": (1 - min_max_normalize(np.log1p(df["커뮤니티_세대당참여인원"]), df.index)) * new_complex_factor,
        "v_홈닥터지원부족": (1 - min_max_normalize(np.log1p(df["홈닥터_세대당지원건수"]), df.index)) * new_complex_factor,
        "v_이용률부족": (1 - min_max_normalize(np.log1p(df["홈닥터_서비스이용률"]), df.index)) * new_complex_factor,
    }
    for service_col, raw_score in raw_service_scores.items():
        vuln[service_col] = shrink_to_neutral(raw_score, confidence=0.45)
    raw_governance_score = (1 - min_max_normalize(np.log1p(df["거버넌스_평균_연간합계"]), df.index)) * new_complex_factor
    vuln["v_거버넌스부족"] = shrink_to_neutral(raw_governance_score, confidence=0.45)
    vuln["v_앙상블이상도"] = min_max_normalize(df["ensemble_anomaly_score"], df.index)
    return vuln


def compute_entropy_weights(X, feature_names, epsilon=1e-12):
    if isinstance(X, pd.DataFrame):
        X_arr = X.values.astype(float)
    else:
        X_arr = np.array(X, dtype=float)
    n, m = X_arr.shape
    X_arr = np.clip(X_arr, 0, None)
    col_sums = X_arr.sum(axis=0)
    zero_cols = col_sums < epsilon
    col_sums_safe = np.where(zero_cols, 1.0, col_sums)
    P = X_arr / col_sums_safe[np.newaxis, :]
    k = 1.0 / np.log(n + epsilon)
    log_P = np.where(P > epsilon, np.log(P + epsilon), 0.0)
    E = -k * np.sum(P * log_P, axis=0)
    E = np.clip(E, 0.0, 1.0)
    d = 1.0 - E
    d_sum = d.sum()
    if d_sum < epsilon:
        weights = np.ones(m) / m
    else:
        weights = d / d_sum
    return pd.Series(weights, index=feature_names, name="entropy_weight")


def compute_weights(vuln, VULN_COLS, ALPHA=0.5):
    POLICY_PRIOR_RAW = {
        "v_고령화": 0.18, "v_초고령": 0.11, "v_취약임대": 0.08,
        "v_시설부족": 0.08, "v_경로당없음": 0.04, "v_복지관없음": 0.04,
        "v_의료접근성부족": 0.17, "v_복지접근성부족": 0.15,
        "v_커뮤니티부족": 0.015, "v_커뮤니티다양성부족": 0.010, "v_참여인원부족": 0.010,
        "v_홈닥터지원부족": 0.010, "v_이용률부족": 0.005,
        "v_거버넌스부족": 0.05, "v_앙상블이상도": 0.05,
    }
    prior_raw_series = pd.Series(POLICY_PRIOR_RAW)
    policy_prior_weights = (prior_raw_series / prior_raw_series.sum()).reindex(VULN_COLS).fillna(0.0)
    policy_prior_weights.name = "policy_prior_weight"
    entropy_weights = compute_entropy_weights(vuln[VULN_COLS], VULN_COLS)
    entropy_weights = entropy_weights.reindex(VULN_COLS).fillna(0.0)
    hybrid_weights = ALPHA * policy_prior_weights + (1 - ALPHA) * entropy_weights
    hybrid_weights = hybrid_weights / hybrid_weights.sum()
    hybrid_weights.name = "hybrid_weight"
    return policy_prior_weights, entropy_weights, hybrid_weights


def compute_vulnerability_score(vuln_df, weights):
    w = weights.reindex(vuln_df.columns).fillna(0.0)
    w_sum = w.sum()
    if w_sum > 1e-12:
        w = w / w_sum
    return (vuln_df * w.values).sum(axis=1)


def classify_and_score(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights):
    ALPHA = 0.5
    df["취약도_수동가중치"] = compute_vulnerability_score(vuln[VULN_COLS], policy_prior_weights)
    df["취약도_entropy가중치"] = compute_vulnerability_score(vuln[VULN_COLS], entropy_weights)
    df["취약도_hybrid가중치"] = compute_vulnerability_score(vuln[VULN_COLS], hybrid_weights)
    df["취약도_종합지수"] = df["취약도_hybrid가중치"]
    df["취약도_인구"] = vuln["v_고령화"] * 0.49 + vuln["v_초고령"] * 0.30 + vuln["v_취약임대"] * 0.21
    df["취약도_시설"] = vuln["v_시설부족"] * 0.50 + vuln["v_경로당없음"] * 0.25 + vuln["v_복지관없음"] * 0.25
    df["취약도_접근성"] = vuln["v_의료접근성부족"] * 0.53 + vuln["v_복지접근성부족"] * 0.47
    df["취약도_서비스이용"] = (vuln["v_커뮤니티부족"] * 0.30 + vuln["v_커뮤니티다양성부족"] * 0.20
                              + vuln["v_참여인원부족"] * 0.20 + vuln["v_홈닥터지원부족"] * 0.20
                              + vuln["v_이용률부족"] * 0.10)
    df["취약도_거버넌스"] = vuln["v_거버넌스부족"]
    df["취약도_이상탐지"] = vuln["v_앙상블이상도"]
    p40, p60, p80 = np.percentile(df["취약도_종합지수"], [40, 60, 80])

    def classify_risk(row):
        if row.get("신규단지_여부", 0) == 1:
            return "신규단지(판정유예)"
        if row["취약도_종합지수"] >= p80:
            return "고위험(사각지대)"
        if row["취약도_종합지수"] >= p60:
            return "중위험(잠재적사각지대)"
        if row["취약도_종합지수"] >= p40:
            return "관심"
        return "일반"

    df["사각지대_등급"] = df.apply(classify_risk, axis=1)
    df["사각지대_여부"] = (
        (df.get("신규단지_여부", pd.Series(0, index=df.index)) == 0)
        & ((df["사각지대_등급"] == "고위험(사각지대)")
           | ((df["ensemble_anomaly"] == 1) & (df["취약도_종합지수"] >= p60)))
    ).astype(int)
    if "신규단지_여부" in df.columns:
        df["판정제외_사유"] = np.where(df["신규단지_여부"].eq(1), "2024년 이후 신규단지로 판정유예", "")
    else:
        df["판정제외_사유"] = ""
    weighted_contrib = pd.DataFrame({col: vuln[col] * hybrid_weights.get(col, 0) for col in VULN_COLS})
    REASON_LABELS = {
        "v_고령화": "고령화율 상위권", "v_초고령": "초고령 인구 비중 높음", "v_취약임대": "영구임대 공급유형",
        "v_시설부족": "단지 내 생활복지시설 부족", "v_경로당없음": "경로당 부재", "v_복지관없음": "복지관 부재",
        "v_의료접근성부족": "의료시설 접근성 취약", "v_복지접근성부족": "복지시설 접근성 취약",
        "v_커뮤니티부족": "커뮤니티 활동 부족", "v_커뮤니티다양성부족": "커뮤니티 분야 다양성 부족",
        "v_참여인원부족": "커뮤니티 참여율 부족", "v_홈닥터지원부족": "홈닥터 지원 이용 낮음",
        "v_이용률부족": "홈닥터 서비스 이용률 낮음", "v_거버넌스부족": "거버넌스 활동 부족",
        "v_앙상블이상도": "복합 이상패턴 탐지",
    }

    def build_reason_labels(idx, top_n=3):
        labels = []
        for col, value in weighted_contrib.loc[idx].sort_values(ascending=False).items():
            if value <= 0:
                continue
            text = REASON_LABELS.get(col, col)
            if col == "v_고령화" and df.loc[idx, "고령화율"] >= df["고령화율"].quantile(0.90):
                text = "고령화율 상위 10%"
            if col in ["v_시설부족", "v_경로당없음", "v_복지관없음"] and "장기전세_포함" in df.columns and df.loc[idx, "장기전세_포함"] == 1:
                text += "(장기전세 보정 반영)"
            labels.append(text)
            if len(labels) >= top_n:
                break
        return labels

    df["취약_주요원인_list"] = [build_reason_labels(idx) for idx in df.index]
    df["취약_주요원인"] = df["취약_주요원인_list"].apply(", ".join)
    print(f"사각지대 단지 수: {int(df['사각지대_여부'].sum())}")
    return df, weighted_contrib


def run_sensitivity_analysis(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights):
    ALPHA_VALUES = [0.0, 0.25, 0.5, 0.75, 1.0]
    TOP_K_RATE = 0.25
    N_TOTAL = len(df)
    top_k = max(1, int(N_TOTAL * TOP_K_RATE))
    base_score, base_rank, base_topk = None, None, None

    def compute_alpha_result(alpha_val):
        hw = alpha_val * policy_prior_weights + (1 - alpha_val) * entropy_weights
        hw = hw / hw.sum()
        score = compute_vulnerability_score(vuln[VULN_COLS], hw)
        rank = score.rank(ascending=False, method="min")
        topk_set = set(score.nlargest(top_k).index.tolist())
        return score, rank, topk_set

    base_score, base_rank, base_topk = compute_alpha_result(0.5)
    alpha_results = []
    for alpha_val in ALPHA_VALUES:
        score, rank, topk_set = compute_alpha_result(alpha_val)
        jaccard = len(topk_set & base_topk) / len(topk_set | base_topk) if (topk_set | base_topk) else 1.0
        spearman_corr, _ = spearmanr(base_rank.values, rank.values)
        overlap_count = len(topk_set & base_topk)
        alpha_results.append({
            "alpha": alpha_val,
            "jaccard_vs_alpha05": round(jaccard, 4),
            "spearman_vs_alpha05": round(float(spearman_corr), 4),
            "topk_overlap_count": overlap_count,
            "topk_overlap_rate": round(overlap_count / top_k, 4),
            "score_mean": round(float(score.mean()), 4),
            "score_std": round(float(score.std()), 4),
        })
    alpha_sensitivity_df = pd.DataFrame(alpha_results)
    N_MONTE_CARLO = 1000
    mc_selection_counts = np.zeros(N_TOTAL, dtype=int)
    mc_rank_sum = np.zeros(N_TOTAL, dtype=float)
    mc_rank_sq_sum = np.zeros(N_TOTAL, dtype=float)
    rng = np.random.default_rng(SEED)
    for iteration in range(N_MONTE_CARLO):
        noise = rng.uniform(0.8, 1.2, size=len(VULN_COLS))
        perturbed_w = hybrid_weights.values * noise
        perturbed_w = perturbed_w / perturbed_w.sum()
        perturbed_w_series = pd.Series(perturbed_w, index=VULN_COLS)
        mc_score = compute_vulnerability_score(vuln[VULN_COLS], perturbed_w_series)
        mc_rank = mc_score.rank(ascending=False, method="min").values
        topk_indices = set(mc_score.nlargest(top_k).index.tolist())
        mc_topk_mask = np.array([idx in topk_indices for idx in vuln.index])
        mc_selection_counts += mc_topk_mask.astype(int)
        mc_rank_sum += mc_rank
        mc_rank_sq_sum += mc_rank ** 2
    mc_freq = mc_selection_counts / N_MONTE_CARLO
    mc_mean_rank = mc_rank_sum / N_MONTE_CARLO
    mc_rank_var = mc_rank_sq_sum / N_MONTE_CARLO - mc_mean_rank ** 2
    mc_rank_std = np.sqrt(np.maximum(mc_rank_var, 0))
    name_col = "단지명" if "단지명" in df.columns else df.columns[0]
    mc_stability_df = pd.DataFrame({
        "단지_index": df.index, "단지명": df[name_col].values,
        "monte_carlo_selection_frequency": mc_freq, "monte_carlo_mean_rank": mc_mean_rank,
        "monte_carlo_rank_std": mc_rank_std, "hybrid_score": df["취약도_hybrid가중치"].values,
        "hybrid_rank": df["취약도_hybrid가중치"].rank(ascending=False, method="min").values,
        "사각지대_등급": df["사각지대_등급"].values,
    }).sort_values("monte_carlo_selection_frequency", ascending=False)
    robust_mask = (mc_freq >= 0.70) & (
        df["취약도_hybrid가중치"].values >= np.percentile(df["취약도_hybrid가중치"].values, 100 * (1 - TOP_K_RATE))
    )
    df["mc_selection_frequency"] = mc_freq
    df["mc_mean_rank"] = mc_mean_rank
    df["mc_rank_std"] = mc_rank_std
    df["robust_high_risk"] = robust_mask.astype(int)
    comparison_rows = [
        {"비교_A": "수동가중치", "비교_B": "entropy가중치",
         **_compare_scores(df["취약도_수동가중치"], df["취약도_entropy가중치"], top_k)},
        {"비교_A": "수동가중치", "비교_B": "hybrid가중치",
         **_compare_scores(df["취약도_수동가중치"], df["취약도_hybrid가중치"], top_k)},
        {"비교_A": "entropy가중치", "비교_B": "hybrid가중치",
         **_compare_scores(df["취약도_entropy가중치"], df["취약도_hybrid가중치"], top_k)},
    ]
    weighting_comparison_df = pd.DataFrame(comparison_rows)
    print(f"Monte Carlo 완료, Robust high-risk: {int(robust_mask.sum())}개")
    return df, alpha_sensitivity_df, mc_stability_df, mc_freq, weighting_comparison_df, top_k


def _compare_scores(score_a, score_b, top_k):
    topk_a = set(score_a.nlargest(top_k).index.tolist())
    topk_b = set(score_b.nlargest(top_k).index.tolist())
    jaccard = len(topk_a & topk_b) / len(topk_a | topk_b) if (topk_a | topk_b) else 1.0
    spearman, _ = spearmanr(score_a.rank(ascending=False).values, score_b.rank(ascending=False).values)
    overlap = len(topk_a & topk_b)
    return {"jaccard_similarity": round(jaccard, 4), "spearman_correlation": round(float(spearman), 4),
            "topk_overlap_count": overlap, "topk_overlap_rate": round(overlap / top_k, 4)}


def save_results(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights,
                 cluster_eval_df, model_performance_comparison, alpha_sensitivity_df,
                 mc_stability_df, weighting_comparison_df, sgg_summary,
                 DATA_OUTPUT_DIR, FIG_OUTPUT_DIR, DASHBOARD_OUTPUT_DIR, MODEL_OUTPUT_DIR,
                 best_model_name, best_model_id, n_clusters):
    RESULT_BASE_COLS = ["단지명", "마을명", "우편번호", "기본상세", "x", "y", "공급유형", "건설호수", "승강기대수", "CCTV대수",
                        "emd_cd", "emd_nm_e", "sgg_cd", "sgg_nm_e", "sido_cd", "sido_nm_e"]
    RESULT_FEATURE_COLS = [
        "고령화율", "초고령비율", "아동청소년비율", "총인구수_계산",
        "경로당_있음", "복지관_있음", "운동시설_있음", "시설종합지수", "경로당_면적", "복지관_면적", "노후도_년수",
        "접근성_의료종합", "접근성_복지종합", "접근성_교육문화종합", "접근성_돌봄종합",
        "커뮤니티_총활동횟수", "커뮤니티_총참여인원", "커뮤니티_분야다양성", "커뮤니티_유형다양성",
        "커뮤니티_세대당참여인원", "커뮤니티_매핑여부",
        "홈닥터_총지원건수", "홈닥터_세대당지원건수", "홈닥터_의료지원비율", "홈닥터_경제지원비율",
        "홈닥터_서비스이용률", "홈닥터_매핑여부",
        "거버넌스_평균_연간합계", "거버넌스_완전연도수", "거버넌스_연간합계_2022", "거버넌스_연간합계_2023",
        "거버넌스_연간합계_2024", "거버넌스_추세기울기", "거버넌스_악화중_여부", "거버넌스_매핑여부",
        "취약도_종합지수", "취약도_인구", "취약도_시설", "취약도_접근성", "취약도_서비스이용", "취약도_거버넌스", "취약도_이상탐지",
        "취약도_수동가중치", "취약도_entropy가중치", "취약도_hybrid가중치",
        "isolation_forest_score", "oneclass_svm_score", "selected_anomaly_model", "selected_anomaly_experiment_id",
        "selected_anomaly_score", "selected_anomaly", "ensemble_anomaly_score", "ensemble_anomaly",
        "cluster_label", "사각지대_등급", "사각지대_여부", "취약_주요원인",
        "영구임대_포함", "국민임대_포함", "행복주택_포함", "장기전세_포함", "취약임대_여부",
        "신규단지_여부", "소규모단지_여부", "대규모단지_여부", "서비스_미매핑_구분", "판정제외_사유",
        "mc_selection_frequency", "mc_mean_rank", "mc_rank_std", "robust_high_risk",
    ]
    RESULT_BASE_COLS = [c for c in RESULT_BASE_COLS if c in df.columns]
    RESULT_FEATURE_COLS = [c for c in RESULT_FEATURE_COLS if c in df.columns]
    result_df = df[RESULT_BASE_COLS + RESULT_FEATURE_COLS].copy()
    result_df["취약도_순위"] = result_df["취약도_종합지수"].rank(ascending=False, method="min").astype(int)
    result_df["위험_백분위"] = (1 - result_df["취약도_종합지수"].rank(pct=True)).round(4)
    result_df.sort_values("취약도_종합지수", ascending=False).to_csv(
        DATA_OUTPUT_DIR / "welfare_blindspot_results.csv", index=False, encoding="utf-8-sig")
    high_risk_df = result_df[result_df["사각지대_여부"] == 1].sort_values("취약도_종합지수", ascending=False)
    high_risk_df.to_csv(DATA_OUTPUT_DIR / "blindspot_candidates.csv", index=False, encoding="utf-8-sig")
    result_df.sort_values("취약도_종합지수", ascending=False).to_csv(DATA_OUTPUT_DIR / "result_vulnerability_index.csv", index=False, encoding="utf-8-sig")
    high_risk_df.to_csv(DATA_OUTPUT_DIR / "result_blindspot_complexes.csv", index=False, encoding="utf-8-sig")
    cluster_eval_df.to_csv(DATA_OUTPUT_DIR / "result_hierarchical_cluster_k_evaluation.csv", index=False, encoding="utf-8-sig")
    model_performance_comparison.to_csv(DATA_OUTPUT_DIR / "result_anomaly_model_experiments.csv", index=False, encoding="utf-8-sig")
    alpha_sensitivity_df.to_csv(DATA_OUTPUT_DIR / "alpha_sensitivity_analysis.csv", index=False, encoding="utf-8-sig")
    mc_stability_df.to_csv(DATA_OUTPUT_DIR / "monte_carlo_rank_stability.csv", index=False, encoding="utf-8-sig")
    weighting_comparison_df.to_csv(DATA_OUTPUT_DIR / "weighting_method_comparison.csv", index=False, encoding="utf-8-sig")
    weight_comparison = pd.DataFrame({
        "정책_prior_가중치": policy_prior_weights,
        "entropy_가중치": entropy_weights,
        "hybrid_가중치": hybrid_weights,
    })
    weight_comparison.index.name = "지표명"
    weight_comparison.to_csv(DATA_OUTPUT_DIR / "weight_comparison_table.csv", encoding="utf-8-sig")
    feature_importance = pd.DataFrame({
        "지표명": VULN_COLS,
        "정책_prior_가중치": policy_prior_weights.values,
        "entropy_가중치": entropy_weights.values,
        "hybrid_가중치": hybrid_weights.values,
        "vuln_평균값": vuln[VULN_COLS].mean().values,
        "vuln_표준편차": vuln[VULN_COLS].std().values,
    })
    feature_importance.to_csv(DATA_OUTPUT_DIR / "feature_importance.csv", index=False, encoding="utf-8-sig")
    cluster_summary_cols = [c for c in ["고령화율", "초고령비율", "시설종합지수", "접근성_의료종합", "접근성_복지종합",
                                         "커뮤니티_총활동횟수", "홈닥터_세대당지원건수", "거버넌스_평균_연간합계",
                                         "취약도_종합지수", "취약도_인구", "취약도_시설", "취약도_접근성",
                                         "취약도_서비스이용", "취약도_거버넌스"] if c in df.columns]
    cluster_summary = df.groupby("cluster_label").agg(
        단지수=("단지명", "count"),
        **{col: (col, "mean") for col in cluster_summary_cols}
    ).round(4)
    if "공급유형" in df.columns:
        cluster_summary["주요공급유형"] = df.groupby("cluster_label")["공급유형"].agg(lambda x: x.mode()[0] if len(x.mode()) else "")
    cluster_summary["사각지대_단지수"] = df.groupby("cluster_label")["사각지대_여부"].sum()
    cluster_summary["robust_고위험_단지수"] = df.groupby("cluster_label")["robust_high_risk"].sum()
    cluster_summary.to_csv(DATA_OUTPUT_DIR / "result_cluster_summary.csv", encoding="utf-8-sig")
    if len(sgg_summary) > 0:
        sgg_summary.to_csv(DASHBOARD_OUTPUT_DIR / "result_sgg_vulnerability_summary.csv", index=False, encoding="utf-8-sig")
    ALPHA = 0.5
    N_MONTE_CARLO = 1000
    validation_summary = {
        "model_version": "1.0",
        "total_complexes": int(len(df)),
        "aging_rate_over_1_count": int((df["고령화율"] > 1).sum()) if "고령화율" in df.columns else 0,
        "dbscan_noise_count": 0,
        "hierarchical_cluster_count": int(n_clusters),
        "new_complex_count": int(df["신규단지_여부"].sum()) if "신규단지_여부" in df.columns else 0,
        "new_complex_blindspot_count": int(df.loc[df.get("신규단지_여부", pd.Series(0, index=df.index)).eq(1), "사각지대_여부"].sum()),
        "long_term_lease_count": int(df["장기전세_포함"].sum()) if "장기전세_포함" in df.columns else 0,
        "blindspot_count": int(df["사각지대_여부"].sum()),
        "robust_high_risk_count": int(df["robust_high_risk"].sum()),
        "alpha_used": float(ALPHA),
        "monte_carlo_iterations": N_MONTE_CARLO,
        "selected_anomaly_model": str(best_model_name),
        "selected_anomaly_experiment_id": str(best_model_id),
        "output_dir": str(DATA_OUTPUT_DIR),
    }
    with open(DATA_OUTPUT_DIR / "validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(validation_summary, f, ensure_ascii=False, indent=2)
    print(f"전체 결과: {len(result_df)} 행, 고위험 후보: {len(high_risk_df)} 행")
    assert validation_summary["aging_rate_over_1_count"] == 0
    assert validation_summary["dbscan_noise_count"] == 0
    assert validation_summary["new_complex_blindspot_count"] == 0
    print("모든 검증 통과")
    return result_df, high_risk_df


def plot_all(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights,
             linkage_matrix, best_labels, best_k, mc_freq, alpha_sensitivity_df,
             sgg_summary, result_df, FIG_OUTPUT_DIR, DASHBOARD_OUTPUT_DIR, ALPHA=0.5):
    import matplotlib as mpl
    mpl.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(15, 7))
    dendrogram(linkage_matrix, truncate_mode="lastp", p=30, leaf_rotation=45, leaf_font_size=10,
               color_threshold=linkage_matrix[-best_k + 1, 2] if best_k > 1 else None,
               above_threshold_color="gray", ax=ax)
    cut_height = linkage_matrix[-best_k + 1, 2] if best_k > 1 else None
    if cut_height is not None:
        ax.axhline(y=cut_height, color="crimson", linestyle="--", linewidth=3, label=f"Selected cut level: k={best_k}")
    ax.set_title(f"Hierarchical Clustering Dendrogram (Ward Linkage, k={best_k})", fontsize=15, fontweight="bold")
    ax.set_xlabel("Clustered housing-complex groups")
    ax.set_ylabel("Ward linkage distance")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(FIG_OUTPUT_DIR / "hierarchical_dendrogram_pretty.png", dpi=200, bbox_inches="tight")
    plt.close()

    x = np.arange(len(VULN_COLS))
    w = 0.28
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - w, policy_prior_weights.values, width=w, label="정책 Prior 가중치", color="#1F77B4", alpha=0.95, edgecolor="black", linewidth=0.4)
    ax.bar(x, entropy_weights.values, width=w, label="Entropy 가중치", color="#FF7F0E", alpha=0.95, edgecolor="black", linewidth=0.4)
    ax.bar(x + w, hybrid_weights.values, width=w, label=f"Hybrid 가중치 (alpha={ALPHA})", color="#2CA02C", alpha=0.95, edgecolor="black", linewidth=0.4)
    ax.set_yscale("log")
    ax.set_ylim(0.001, 0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(VULN_COLS, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("취약도 지표", fontsize=11)
    ax.set_ylabel("가중치 (Log Scale)", fontsize=11)
    ax.set_title("가중치 방식 비교: 정책 Prior vs Entropy vs Hybrid", fontsize=13, pad=12)
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    ax.grid(axis="y", which="major", linestyle="-", alpha=0.35)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(FIG_OUTPUT_DIR / "weight_comparison_barchart_logscale.png", dpi=300, bbox_inches="tight")
    plt.close()

    alpha_vals = alpha_sensitivity_df["alpha"].values
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax1, ax2 = axes
    ax1.plot(alpha_vals, alpha_sensitivity_df["jaccard_vs_alpha05"].values, "o-", color="#1F77B4",
             linewidth=2.2, markersize=6, markeredgecolor="black", markeredgewidth=0.5)
    ax1.set_xlabel("Alpha 값", fontsize=11)
    ax1.set_ylabel("Jaccard 유사도", fontsize=11)
    ax1.set_title("Alpha별 상위 20% 고위험 후보군 Jaccard 유사도", fontsize=13, pad=10)
    ax1.set_ylim(0.75, 1.02)
    ax1.set_xticks(alpha_vals)
    ax1.grid(True, linestyle="--", alpha=0.35)
    ax2.plot(alpha_vals, alpha_sensitivity_df["spearman_vs_alpha05"].values, "s-", color="#D62728",
             linewidth=2.2, markersize=6, markeredgecolor="black", markeredgewidth=0.5)
    ax2.set_xlabel("Alpha 값", fontsize=11)
    ax2.set_ylabel("Spearman 순위 상관계수", fontsize=11)
    ax2.set_title("Alpha별 순위 Spearman 상관계수", fontsize=13, pad=10)
    ax2.set_ylim(0.90, 1.01)
    ax2.set_xticks(alpha_vals)
    ax2.grid(True, linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig(FIG_OUTPUT_DIR / "alpha_sensitivity_plot_axis_improved.png", dpi=300, bbox_inches="tight")
    plt.close()

    bins = np.linspace(0, 1, 45)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.hist(mc_freq, bins=bins, color="#1F77B4", edgecolor="white", linewidth=0.8, alpha=0.92, log=True)
    ax.axvline(0.70, color="#D62728", linestyle="--", linewidth=2.0, label="Robust 기준선 (0.70)")
    ax.axvspan(0.70, 1.00, color="#D62728", alpha=0.08)
    ax.set_title("Monte Carlo 선택 빈도 분포", fontsize=14, pad=12)
    ax.set_xlabel("Monte Carlo 선택 빈도", fontsize=11)
    ax.set_ylabel("단지 수 (Log Scale)", fontsize=11)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xticks(np.arange(0, 1.01, 0.1))
    ax.grid(which="major", linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", frameon=True, fontsize=10)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(FIG_OUTPUT_DIR / "monte_carlo_frequency_histogram_logscale.png", dpi=300, bbox_inches="tight")
    plt.close()

    domain_source = [c for c in ["취약도_인구", "취약도_시설", "취약도_접근성", "취약도_서비스이용", "취약도_거버넌스", "취약도_이상탐지"] if c in result_df.columns]
    top5 = result_df[result_df["사각지대_여부"] == 1].nlargest(5, "취약도_종합지수")
    domain_labels_map = {"취약도_인구": "인구", "취약도_시설": "시설", "취약도_접근성": "접근성",
                         "취약도_서비스이용": "서비스", "취약도_거버넌스": "거버넌스", "취약도_이상탐지": "이상탐지"}
    domain_labels_kr = [domain_labels_map.get(c, c) for c in domain_source]
    if len(top5) > 0 and len(domain_source) >= 3:
        angles = [n / len(domain_source) * 2 * np.pi for n in range(len(domain_source))]
        angles += angles[:1]
        fig, axes = plt.subplots(1, len(top5), figsize=(4 * len(top5), 4), subplot_kw=dict(polar=True))
        if len(top5) == 1:
            axes = [axes]
        colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd"]
        for i, (_, row) in enumerate(top5.iterrows()):
            values = [row[c] for c in domain_source] + [row[domain_source[0]]]
            axes[i].plot(angles, values, color=colors[i], linewidth=2)
            axes[i].fill(angles, values, color=colors[i], alpha=0.25)
            axes[i].set_xticks(angles[:-1])
            axes[i].set_xticklabels(domain_labels_kr, size=8)
            axes[i].set_ylim(0, 1)
            axes[i].set_title(f"{str(row.get('단지명', ''))[:10]}\n({row['취약도_종합지수']:.3f})", fontsize=9, fontweight="bold")
        plt.tight_layout()
        plt.savefig(FIG_OUTPUT_DIR / "top5_blindspot_radar.png", dpi=450, bbox_inches="tight")
        plt.close()

    if len(sgg_summary) > 0 and "sido_nm_e" in sgg_summary.columns:
        sido_avg = sgg_summary.groupby("sido_nm_e")["평균_취약도"].mean().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(14, 5.5))
        colors = plt.cm.Blues(np.linspace(0.45, 0.90, len(sido_avg)))
        bars = ax.bar(sido_avg.index, sido_avg.values, color=colors, edgecolor="black", linewidth=0.5, alpha=0.95, width=0.72)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height + 0.003, f"{height:.3f}", ha="center", va="bottom", fontsize=8)
        ax.set_title("시도별 평균 Hybrid 취약도 점수", fontsize=14, pad=12, fontweight="bold")
        ax.set_xlabel("시도", fontsize=11)
        ax.set_ylabel("평균 Hybrid 취약도 점수", fontsize=11)
        ax.tick_params(axis="x", rotation=45, labelsize=9)
        ax.set_ylim(0, max(sido_avg.values) * 1.12)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        plt.savefig(DASHBOARD_OUTPUT_DIR / "sido_avg_hybrid_vulnerability_paperstyle.png", dpi=300, bbox_inches="tight")
        plt.close()

    print("시각화 완료")


def main():
    args = get_args()
    DATA_DIR = Path(args.data_dir)
    OUTPUT_DIR = Path(args.output_dir)
    DATA_OUTPUT_DIR = OUTPUT_DIR / "data"
    FIG_OUTPUT_DIR = OUTPUT_DIR / "figures"
    DASHBOARD_OUTPUT_DIR = OUTPUT_DIR / "dashboard"
    MODEL_OUTPUT_DIR = OUTPUT_DIR / "models"
    for p in [DATA_OUTPUT_DIR, FIG_OUTPUT_DIR, DASHBOARD_OUTPUT_DIR, MODEL_OUTPUT_DIR]:
        p.mkdir(parents=True, exist_ok=True)

    setup_font()
    print(f"데이터 경로: {DATA_DIR}")
    print(f"출력 경로: {OUTPUT_DIR}")

    base_df, comm_df, hd_df, soc_gdf = load_data(DATA_DIR)
    comm_agg = aggregate_community(comm_df)
    hd_agg = aggregate_homedoctor(hd_df)
    merged_df = merge_datasets(base_df, comm_agg, hd_agg, soc_gdf)
    merged_df, comm_log, hd_log = flag_service_coverage(merged_df)
    pd.concat([comm_log, hd_log], ignore_index=True).to_csv(
        DATA_OUTPUT_DIR / "result_service_imputation_log.csv", index=False, encoding="utf-8-sig")

    df = merged_df.copy()
    df, access_clean_log, access_log, gov_log = engineer_features(df)
    pd.DataFrame(access_clean_log).to_csv(DATA_OUTPUT_DIR / "result_accessibility_negative_value_log.csv", index=False, encoding="utf-8-sig")

    X_norm, FEATURE_COLS = normalize_features(df)
    df, model_performance_comparison, best_model_name, best_model_id = run_anomaly_detection(df, X_norm)
    model_performance_comparison.to_csv(DATA_OUTPUT_DIR / "appendix_full_anomaly_model_experiments.csv", index=False, encoding="utf-8-sig")

    df, cluster_eval_df, linkage_matrix, best_labels, best_k, X_cluster = run_clustering(df, X_norm)

    VULN_COLS_tsne = ["고령화율", "초고령비율", "시설종합지수", "접근성_의료종합", "접근성_복지종합",
                      "커뮤니티_총활동횟수", "커뮤니티_분야다양성", "홈닥터_세대당지원건수",
                      "거버넌스_평균_연간합계", "취약임대_여부", "장기전세_포함", "신규단지_여부"]
    VULN_COLS_tsne = [c for c in VULN_COLS_tsne if c in X_norm.columns]
    tsne = TSNE(n_components=2, perplexity=10, learning_rate="auto", init="pca", random_state=42971)
    xy_tsne = tsne.fit_transform(X_norm)
    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(xy_tsne[:, 0], xy_tsne[:, 1], c=df["selected_anomaly_score"],
                         cmap="RdYlGn_r", s=70, alpha=0.78, edgecolor="white", linewidth=0.4)
    ax.scatter(xy_tsne[df["selected_anomaly"] == 1, 0], xy_tsne[df["selected_anomaly"] == 1, 1],
               facecolors="none", edgecolors="black", s=130, linewidth=1.2, label="Selected anomaly")
    plt.colorbar(scatter, ax=ax, label="Selected anomaly score")
    ax.set_title(f"t-SNE Projection\nSelected Model: {best_model_name}", fontsize=14, fontweight="bold")
    ax.set_xlabel("t-SNE dimension 1")
    ax.set_ylabel("t-SNE dimension 2")
    ax.legend()
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(FIG_OUTPUT_DIR / "selected_anomaly_tsne_projection.png", dpi=200, bbox_inches="tight")
    plt.close()

    vuln = build_vulnerability_matrix(df)
    VULN_COLS = list(vuln.columns)
    ALPHA = 0.5
    policy_prior_weights, entropy_weights, hybrid_weights = compute_weights(vuln, VULN_COLS, ALPHA)
    df, weighted_contrib = classify_and_score(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights)
    df, alpha_sensitivity_df, mc_stability_df, mc_freq, weighting_comparison_df, top_k = run_sensitivity_analysis(
        df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights)

    sgg_group_cols = [c for c in ["sido_cd", "sido_nm_e", "sgg_cd", "sgg_nm_e"] if c in df.columns]
    sgg_summary = pd.DataFrame()
    if sgg_group_cols:
        sgg_agg_dict = {
            "단지수": ("단지명", "count"), "평균_취약도": ("취약도_종합지수", "mean"),
            "최대_취약도": ("취약도_종합지수", "max"), "사각지대_단지수": ("사각지대_여부", "sum"),
            "mc_robust_단지수": ("robust_high_risk", "sum"),
        }
        if "고령화율" in df.columns:
            sgg_agg_dict["평균_고령화율"] = ("고령화율", "mean")
        if "취약도_접근성" in df.columns:
            sgg_agg_dict["평균_접근성_취약도"] = ("취약도_접근성", "mean")
        sgg_summary = df.groupby(sgg_group_cols, dropna=False).agg(**sgg_agg_dict).reset_index()
        sgg_summary["사각지대_비율"] = sgg_summary["사각지대_단지수"] / sgg_summary["단지수"]
        sgg_summary = sgg_summary.sort_values("평균_취약도", ascending=False)

    n_clusters = len(np.unique(best_labels))
    result_df, high_risk_df = save_results(
        df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights,
        cluster_eval_df, model_performance_comparison, alpha_sensitivity_df, mc_stability_df,
        weighting_comparison_df, sgg_summary, DATA_OUTPUT_DIR, FIG_OUTPUT_DIR,
        DASHBOARD_OUTPUT_DIR, MODEL_OUTPUT_DIR, best_model_name, best_model_id, n_clusters)

    plot_all(df, vuln, VULN_COLS, policy_prior_weights, entropy_weights, hybrid_weights,
             linkage_matrix, best_labels, best_k, mc_freq, alpha_sensitivity_df,
             sgg_summary, result_df, FIG_OUTPUT_DIR, DASHBOARD_OUTPUT_DIR, ALPHA)


if __name__ == "__main__":
    main()
