import argparse
import itertools
import json
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

SEED = 42
np.random.seed(SEED)


def get_args():
    parser = argparse.ArgumentParser(description="클러스터 연관규칙 분석")
    parser.add_argument(
        "--input-file",
        type=str,
        default="outputs/welfare_blindspot/data/welfare_blindspot_results.csv",
        help="welfare_blindspot.py 최종 결과 CSV 경로",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/cluster_analysis",
        help="분석 결과 출력 디렉토리",
    )
    return parser.parse_args()


def setup_font():
    available_fonts = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    font = "Malgun Gothic" if "Malgun Gothic" in available_fonts else "DejaVu Sans"
    matplotlib.rcParams["font.family"] = font
    matplotlib.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font=font)


def load_data(source_path):
    df = pd.read_csv(source_path, encoding="utf-8-sig")
    if "cluster_label" not in df.columns:
        raise ValueError("입력 데이터에 cluster_label 컬럼이 없습니다.")
    df["cluster_label"] = df["cluster_label"].astype(int)
    return df


def select_features(df):
    numeric_candidates = [
        "고령화율", "초고령비율", "아동청소년비율", "총인구수_계산", "건설호수", "승강기대수", "CCTV대수",
        "시설종합지수", "경로당_면적", "복지관_면적", "노후도_년수",
        "접근성_의료종합", "접근성_복지종합", "접근성_교육문화종합", "접근성_돌봄종합",
        "커뮤니티_총활동횟수", "커뮤니티_총참여인원", "커뮤니티_분야다양성", "커뮤니티_유형다양성", "커뮤니티_세대당참여인원",
        "홈닥터_총지원건수", "홈닥터_세대당지원건수", "홈닥터_의료지원비율", "홈닥터_경제지원비율", "홈닥터_서비스이용률",
        "거버넌스_평균_연간합계", "거버넌스_완전연도수", "거버넌스_연간합계_2022", "거버넌스_연간합계_2023", "거버넌스_연간합계_2024", "거버넌스_추세기울기",
        "취약도_종합지수", "취약도_인구", "취약도_시설", "취약도_접근성", "취약도_서비스이용", "취약도_거버넌스", "취약도_이상탐지",
        "취약도_수동가중치", "취약도_entropy가중치", "취약도_hybrid가중치", "selected_anomaly_score", "ensemble_anomaly_score",
        "mc_selection_frequency", "mc_mean_rank", "mc_rank_std", "취약도_순위", "위험_백분위",
    ]
    binary_candidates = [
        "경로당_있음", "복지관_있음", "운동시설_있음", "커뮤니티_매핑여부", "홈닥터_매핑여부", "거버넌스_매핑여부",
        "거버넌스_악화중_여부", "selected_anomaly", "ensemble_anomaly", "사각지대_여부", "robust_high_risk",
        "영구임대_포함", "국민임대_포함", "행복주택_포함", "장기전세_포함", "취약임대_여부", "신규단지_여부", "소규모단지_여부", "대규모단지_여부",
    ]
    categorical_candidates = [
        "공급유형", "사각지대_등급", "취약_주요원인", "서비스_미매핑_구분", "판정제외_사유", "selected_anomaly_model", "sido_nm_e", "sgg_nm_e",
    ]

    binary_features = [c for c in binary_candidates if c in df.columns]
    categorical_features = [c for c in categorical_candidates if c in df.columns]
    numeric_features = [
        c for c in numeric_candidates
        if c in df.columns
        and pd.api.types.is_numeric_dtype(df[c])
        and c not in binary_features
        and c != "cluster_label"
    ]
    return numeric_features, binary_features, categorical_features


def clean_item_value(value):
    if pd.isna(value):
        return "결측"
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return "결측"
    return text.replace("&", "+").replace("=", ":")[:60]


def numeric_to_items(data, columns):
    out = pd.DataFrame(index=data.index)
    summary_rows = []
    for col in columns:
        s = pd.to_numeric(data[col], errors="coerce")
        valid = s.dropna()
        if valid.nunique() < 2:
            continue
        binned = None
        for q in [4, 3, 2]:
            try:
                codes, bins = pd.qcut(s, q=q, labels=False, retbins=True, duplicates="drop")
                n_bins = len(bins) - 1
                if n_bins < 2:
                    continue
                label_map = {
                    2: ["하위50%", "상위50%"],
                    3: ["하위33%", "중위33%", "상위33%"],
                    4: ["하위25%", "중하위25%", "중상위25%", "상위25%"],
                }.get(n_bins, [f"구간{i+1}" for i in range(n_bins)])
                binned = codes.map(lambda x: label_map[int(x)] if pd.notna(x) else "결측")
                break
            except ValueError:
                continue
        if binned is None:
            median = valid.median()
            binned = s.map(lambda x: "결측" if pd.isna(x) else ("상위50%" if x >= median else "하위50%"))
        binned = binned.astype("object").where(pd.Series(binned, index=s.index).notna(), "결측")
        out[col] = [f"{col}={clean_item_value(v)}" for v in binned]
        qs = valid.quantile([0, 0.25, 0.5, 0.75, 1]).to_dict()
        summary_rows.append({
            "feature": col,
            "min": qs.get(0, np.nan),
            "q25": qs.get(0.25, np.nan),
            "median": qs.get(0.5, np.nan),
            "q75": qs.get(0.75, np.nan),
            "max": qs.get(1, np.nan),
            "n_missing": int(s.isna().sum()),
        })
    return out, pd.DataFrame(summary_rows)


def binary_to_items(data, columns):
    out = pd.DataFrame(index=data.index)
    for col in columns:
        s = pd.to_numeric(data[col], errors="coerce")
        vals = np.where(s.eq(1), "예", np.where(s.eq(0), "아니오", "결측"))
        out[col] = [f"{col}={v}" for v in vals]
    return out


def categorical_to_items(data, columns, max_categories=20, min_count=3):
    out = pd.DataFrame(index=data.index)
    category_summary = []
    for col in columns:
        s = data[col].map(clean_item_value)
        counts = s.value_counts(dropna=False)
        if len(counts) > max_categories:
            keep = set(counts[counts >= min_count].head(max_categories - 1).index)
            s = s.where(s.isin(keep), "기타")
        out[col] = [f"{col}={v}" for v in s]
        for value, count in s.value_counts(dropna=False).items():
            category_summary.append({
                "feature": col,
                "category": value,
                "count": int(count),
                "support": float(count / len(data)),
            })
    return out, pd.DataFrame(category_summary)


def build_item_frame(df, numeric_features, binary_features, categorical_features):
    num_items, numeric_bin_summary = numeric_to_items(df, numeric_features)
    bin_items = binary_to_items(df, binary_features)
    cat_items, category_summary = categorical_to_items(df, categorical_features)

    item_frame = pd.concat([num_items, bin_items, cat_items], axis=1)
    item_frame.insert(0, "cluster_item", df["cluster_label"].map(lambda x: f"cluster_label=C{int(x)}"))
    item_frame.insert(0, "cluster_label", df["cluster_label"].values)
    if "단지명" in df.columns:
        item_frame.insert(0, "단지명", df["단지명"].values)
    return item_frame, numeric_bin_summary, category_summary


def build_item_index(item_data, item_columns):
    n = len(item_data)
    item_index = {}
    transactions = []
    for idx, row in item_data[item_columns].iterrows():
        items = set(row.dropna().astype(str).tolist())
        transactions.append(items)
        for item in items:
            item_index.setdefault(item, set()).add(idx)
    support = {item: len(ix) / n for item, ix in item_index.items()}
    return transactions, item_index, support


def intersect_indices(item_index, combo):
    combo = tuple(combo)
    if not combo:
        return set()
    idx = item_index.get(combo[0], set()).copy()
    for item in combo[1:]:
        idx &= item_index.get(item, set())
        if not idx:
            break
    return idx


def generate_target_cluster_rules(
    item_data,
    cluster_order,
    max_len=3,
    min_item_support=0.035,
    min_rule_support=0.015,
    min_confidence=0.20,
    min_lift=1.05,
):
    n = len(item_data)
    item_columns = [c for c in item_data.columns if c not in ["단지명", "cluster_label", "cluster_item"]]
    _, item_index, item_support = build_item_index(item_data, item_columns + ["cluster_item"])
    cluster_items = [f"cluster_label=C{c}" for c in cluster_order]
    candidate_items = sorted([
        item for item, sup in item_support.items()
        if item not in cluster_items and sup >= min_item_support
    ])

    rows = []
    for length in range(1, max_len + 1):
        for combo in itertools.combinations(candidate_items, length):
            antecedent_idx = intersect_indices(item_index, combo)
            antecedent_support = len(antecedent_idx) / n
            if antecedent_support < min_rule_support:
                continue
            for c in cluster_order:
                target_item = f"cluster_label=C{c}"
                target_idx = item_index[target_item]
                joint_count = len(antecedent_idx & target_idx)
                support = joint_count / n
                if support < min_rule_support:
                    continue
                target_support = len(target_idx) / n
                confidence = support / antecedent_support if antecedent_support else 0
                lift = confidence / target_support if target_support else np.nan
                if confidence < min_confidence or lift < min_lift:
                    continue
                conviction = np.inf if confidence >= 1 else (1 - target_support) / (1 - confidence)
                rows.append({
                    "cluster_label": c,
                    "rule": " & ".join(combo) + f" -> C{c}",
                    "antecedents": " & ".join(combo),
                    "consequent": f"cluster_label=C{c}",
                    "antecedent_len": length,
                    "support": support,
                    "antecedent_support": antecedent_support,
                    "cluster_support": target_support,
                    "confidence": confidence,
                    "lift": lift,
                    "leverage": support - antecedent_support * target_support,
                    "conviction": conviction,
                    "joint_count": joint_count,
                    "antecedent_count": len(antecedent_idx),
                    "cluster_count": len(target_idx),
                })
    rules = pd.DataFrame(rows)
    if not rules.empty:
        rules = rules.sort_values(
            ["cluster_label", "lift", "confidence", "support"],
            ascending=[True, False, False, False],
        ).reset_index(drop=True)
    return rules


def compute_numeric_profile(data, columns):
    rows = []
    for col in columns:
        s = pd.to_numeric(data[col], errors="coerce")
        overall_mean = s.mean()
        overall_std = s.std(ddof=0)
        overall_median = s.median()
        for c, g in data.groupby("cluster_label"):
            gs = pd.to_numeric(g[col], errors="coerce")
            mean = gs.mean()
            rows.append({
                "cluster_label": int(c),
                "feature": col,
                "n": int(gs.notna().sum()),
                "cluster_mean": mean,
                "cluster_median": gs.median(),
                "overall_mean": overall_mean,
                "overall_median": overall_median,
                "mean_diff": mean - overall_mean,
                "z_vs_overall": (mean - overall_mean) / overall_std
                if overall_std and not np.isnan(overall_std) else 0,
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["cluster_label", "z_vs_overall"], ascending=[True, False])


def compute_categorical_profile(data, columns):
    rows = []
    n_total = len(data)
    for col in columns:
        values = data[col].map(clean_item_value)
        overall_counts = values.value_counts(dropna=False)
        for c, idx in data.groupby("cluster_label").groups.items():
            cluster_values = values.loc[idx]
            n_cluster = len(cluster_values)
            cluster_counts = cluster_values.value_counts(dropna=False)
            for val, cc in cluster_counts.items():
                overall_count = overall_counts.get(val, 0)
                cluster_rate = cc / n_cluster if n_cluster else np.nan
                overall_rate = overall_count / n_total if n_total else np.nan
                rows.append({
                    "cluster_label": int(c),
                    "feature": col,
                    "category": val,
                    "cluster_count": int(cc),
                    "cluster_rate": cluster_rate,
                    "overall_count": int(overall_count),
                    "overall_rate": overall_rate,
                    "rate_diff": cluster_rate - overall_rate,
                    "lift": cluster_rate / overall_rate if overall_rate else np.nan,
                })
    out = pd.DataFrame(rows)
    return out.sort_values(["cluster_label", "lift", "cluster_rate"], ascending=[True, False, False])


def compute_item_cluster_lift(item_data, cluster_order, min_overall_support=0.03):
    item_columns = [c for c in item_data.columns if c not in ["단지명", "cluster_label", "cluster_item"]]
    tmp = item_data[["cluster_label"] + item_columns].copy()
    tmp["row_id"] = tmp.index
    long_items = tmp.melt(id_vars=["row_id", "cluster_label"], value_name="item").drop(columns="variable")
    long_items = long_items.dropna().drop_duplicates(subset=["row_id", "item"])
    overall = long_items["item"].value_counts() / len(item_data)
    rows = []
    for c in cluster_order:
        subset = long_items[long_items["cluster_label"] == c]
        n_cluster = int((item_data["cluster_label"] == c).sum())
        cluster_prev = subset["item"].value_counts() / n_cluster
        for item, prev in cluster_prev.items():
            overall_prev = overall.get(item, 0)
            if overall_prev < min_overall_support:
                continue
            rows.append({
                "cluster_label": int(c),
                "item": item,
                "cluster_prevalence": prev,
                "overall_prevalence": overall_prev,
                "prevalence_diff": prev - overall_prev,
                "lift": prev / overall_prev if overall_prev else np.nan,
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["cluster_label", "lift", "cluster_prevalence"], ascending=[True, False, False])


def build_cluster_summary(df, cluster_order, rules, numeric_profile, item_lift):
    summary_rows = []
    for c in cluster_order:
        cluster_size = int((df["cluster_label"] == c).sum())
        top_rules = rules[rules["cluster_label"] == c].head(5) if not rules.empty else pd.DataFrame()
        top_nums = numeric_profile[numeric_profile["cluster_label"] == c].copy()
        top_nums["abs_z"] = top_nums["z_vs_overall"].abs()
        top_nums = top_nums.sort_values("abs_z", ascending=False).head(6)
        top_items = item_lift[item_lift["cluster_label"] == c].head(6)
        summary_rows.append({
            "cluster_label": c,
            "단지수": cluster_size,
            "단지비율": cluster_size / len(df),
            "대표_association_rules": " | ".join(top_rules["rule"].tolist()),
            "주요_수치특성": " | ".join([f"{r.feature}({r.z_vs_overall:+.2f}z)" for r in top_nums.itertuples()]),
            "주요_item_lift": " | ".join([f"{r.item}(lift {r.lift:.2f})" for r in top_items.itertuples()]),
        })
    return pd.DataFrame(summary_rows)


def save_results(
    output_dir,
    source_path,
    df,
    cluster_order,
    item_frame,
    numeric_bin_summary,
    category_summary,
    rules,
    numeric_profile,
    categorical_profile,
    item_lift,
    cluster_characteristic_summary,
):
    data_dir = output_dir / "data"
    table_dir = output_dir / "tables"
    fig_dir = output_dir / "figures"
    for p in [output_dir, data_dir, table_dir, fig_dir]:
        p.mkdir(parents=True, exist_ok=True)

    item_frame.to_csv(data_dir / "analysis_item_transactions.csv", index=False, encoding="utf-8-sig")
    numeric_bin_summary.to_csv(table_dir / "numeric_bin_definition.csv", index=False, encoding="utf-8-sig")
    category_summary.to_csv(table_dir / "categorical_item_definition.csv", index=False, encoding="utf-8-sig")
    rules.to_csv(table_dir / "cluster_target_association_rules.csv", index=False, encoding="utf-8-sig")

    top_rules_for_excel = (
        rules.groupby("cluster_label", group_keys=False).head(500).reset_index(drop=True)
        if not rules.empty else rules.copy()
    )
    top_rules_for_excel.to_csv(table_dir / "cluster_target_association_rules_top.csv", index=False, encoding="utf-8-sig")
    numeric_profile.to_csv(table_dir / "cluster_numeric_profile.csv", index=False, encoding="utf-8-sig")
    categorical_profile.to_csv(table_dir / "cluster_categorical_profile.csv", index=False, encoding="utf-8-sig")
    item_lift.to_csv(table_dir / "cluster_item_prevalence_lift.csv", index=False, encoding="utf-8-sig")
    cluster_characteristic_summary.to_csv(table_dir / "cluster_characteristic_summary.csv", index=False, encoding="utf-8-sig")

    excel_path = output_dir / "cluster_association_analysis_summary.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        cluster_characteristic_summary.to_excel(writer, sheet_name="cluster_summary", index=False)
        top_rules_for_excel.to_excel(writer, sheet_name="target_rules_top", index=False)
        numeric_profile.to_excel(writer, sheet_name="numeric_profile", index=False)
        categorical_profile.to_excel(writer, sheet_name="categorical_profile", index=False)
        item_lift.to_excel(writer, sheet_name="item_lift", index=False)
        numeric_bin_summary.to_excel(writer, sheet_name="numeric_bins", index=False)
        category_summary.to_excel(writer, sheet_name="categorical_items", index=False)

    manifest = {
        "input_file": str(source_path),
        "output_dir": str(output_dir),
        "n_rows": int(len(df)),
        "n_clusters": int(len(cluster_order)),
        "clusters": {f"C{c}": int((df["cluster_label"] == c).sum()) for c in cluster_order},
        "rule_parameters": {
            "max_antecedent_len": 3,
            "min_item_support": 0.05,
            "min_rule_support": 0.02,
            "min_confidence": 0.25,
            "min_lift": 1.15,
        },
        "outputs": {
            "transactions": str(data_dir / "analysis_item_transactions.csv"),
            "target_rules": str(table_dir / "cluster_target_association_rules.csv"),
            "target_rules_top": str(table_dir / "cluster_target_association_rules_top.csv"),
            "numeric_profile": str(table_dir / "cluster_numeric_profile.csv"),
            "categorical_profile": str(table_dir / "cluster_categorical_profile.csv"),
            "item_lift": str(table_dir / "cluster_item_prevalence_lift.csv"),
            "summary_excel": str(excel_path),
            "figures_dir": str(fig_dir),
        },
    }
    with open(output_dir / "analysis_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return fig_dir, top_rules_for_excel


def plot_all(df, cluster_order, numeric_profile, numeric_features, fig_dir):
    cluster_counts = df["cluster_label"].value_counts().sort_index()
    x_labels = [f"군집 {i}" for i in cluster_counts.index]
    y_values = cluster_counts.values
    total_n = len(df)
    bar_colors = ["#4C78A8", "#72B7B2", "#F58518", "#54A24B", "#B279A2", "#E45756"]

    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    bars = ax.bar(x_labels, y_values, color=bar_colors[:len(y_values)], edgecolor="white", linewidth=1.8)
    ax.set_title("군집별 아파트 단지 규모 분포", fontsize=16, fontweight="bold", pad=22)
    ax.set_xlabel("군집", fontsize=12, labelpad=10)
    ax.set_ylabel("아파트 단지 수", fontsize=12, labelpad=10)
    y_max = max(y_values)
    ax.set_ylim(0, y_max * 1.22)
    for bar, v in zip(bars, y_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + y_max * 0.035,
            f"{v:,}개\n({v / total_n:.1%})",
            ha="center", va="bottom", fontsize=10.5, fontweight="bold",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.grid(axis="x", visible=False)
    plt.tight_layout()
    plt.savefig(fig_dir / "cluster_size_distribution.png", dpi=220, bbox_inches="tight")
    plt.close()

    heat_features = [
        "고령화율", "초고령비율", "시설종합지수", "접근성_의료종합", "접근성_복지종합",
        "커뮤니티_총활동횟수", "커뮤니티_분야다양성", "홈닥터_세대당지원건수",
        "거버넌스_평균_연간합계", "취약도_종합지수", "취약도_인구", "취약도_시설",
        "취약도_접근성", "취약도_서비스이용", "취약도_거버넌스",
    ]
    heat_features = [c for c in heat_features if c in numeric_features]

    heat = (
        numeric_profile[numeric_profile["feature"].isin(heat_features)]
        .pivot(index="cluster_label", columns="feature", values="z_vs_overall")
        .reindex(cluster_order)
    )

    feature_name_map = {
        "고령화율": "고령화율",
        "초고령비율": "초고령\n비율",
        "시설종합지수": "시설\n종합지수",
        "접근성_의료종합": "의료\n접근성",
        "접근성_복지종합": "복지\n접근성",
        "커뮤니티_총활동횟수": "커뮤니티\n총활동횟수",
        "커뮤니티_분야다양성": "커뮤니티\n분야다양성",
        "홈닥터_세대당지원건수": "홈닥터\n세대당지원건수",
        "거버넌스_평균_연간합계": "거버넌스\n연간합계",
        "취약도_종합지수": "취약도\n종합지수",
        "취약도_인구": "인구\n취약도",
        "취약도_시설": "시설\n취약도",
        "취약도_접근성": "접근성\n취약도",
        "취약도_서비스이용": "서비스이용\n취약도",
        "취약도_거버넌스": "거버넌스\n취약도",
    }

    heat_plot = heat.rename(columns=feature_name_map)
    heat_plot.index = [f"군집 {i}" for i in heat_plot.index]

    fig, ax = plt.subplots(figsize=(max(13, len(heat_features) * 0.85), 6.2))
    sns.heatmap(
        heat_plot,
        cmap="RdBu_r",
        center=0,
        annot=True,
        fmt=".2f",
        linewidths=0.5,
        linecolor="white",
        ax=ax,
        cbar_kws={"label": "전체 평균 대비 표준화 차이"},
    )
    ax.set_title("군집별 핵심 수치지표 특성 비교", fontsize=16, fontweight="bold", pad=18)
    ax.set_xlabel("핵심 지표", fontsize=12, labelpad=12)
    ax.set_ylabel("군집", fontsize=12, labelpad=10)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90, ha="center", va="top", fontsize=10)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=10.5)
    plt.tight_layout()
    plt.savefig(fig_dir / "cluster_numeric_zscore_heatmap.png", dpi=240, bbox_inches="tight")
    plt.close()


def main():
    args = get_args()
    setup_font()

    source_path = Path(args.input_file)
    output_dir = Path(args.output_dir)

    df = load_data(source_path)
    cluster_order = sorted(df["cluster_label"].dropna().unique().tolist())

    numeric_features, binary_features, categorical_features = select_features(df)
    print(f"수치형 변수: {len(numeric_features)}개, 이진 변수: {len(binary_features)}개, 범주형 변수: {len(categorical_features)}개")

    item_frame, numeric_bin_summary, category_summary = build_item_frame(
        df, numeric_features, binary_features, categorical_features
    )

    rules = generate_target_cluster_rules(
        item_frame,
        cluster_order,
        max_len=3,
        min_item_support=0.05,
        min_rule_support=0.02,
        min_confidence=0.25,
        min_lift=1.15,
    )

    numeric_profile = compute_numeric_profile(df, numeric_features)
    categorical_profile = compute_categorical_profile(df, binary_features + categorical_features)
    item_lift = compute_item_cluster_lift(item_frame, cluster_order)
    cluster_summary = build_cluster_summary(df, cluster_order, rules, numeric_profile, item_lift)

    fig_dir, _ = save_results(
        output_dir,
        source_path,
        df,
        cluster_order,
        item_frame,
        numeric_bin_summary,
        category_summary,
        rules,
        numeric_profile,
        categorical_profile,
        item_lift,
        cluster_summary,
    )

    plot_all(df, cluster_order, numeric_profile, numeric_features, fig_dir)

    print(f"분석 완료. 결과 저장 위치: {output_dir}")
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            print(path.relative_to(output_dir).as_posix())


if __name__ == "__main__":
    main()
