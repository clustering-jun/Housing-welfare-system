from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd

from rec_sys.config import get_data_path


def safe_float(value, default=None):
    try:
        number = float(value)
        return default if np.isnan(number) else number
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        number = float(value)
        return default if np.isnan(number) else int(round(number))
    except (TypeError, ValueError):
        return default


def safe_str(value, default=""):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    return str(value).strip()


class WelfareDataLoader:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = get_data_path() if not data_path else Path(data_path)
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        df = pd.read_csv(self.data_path, encoding="utf-8-sig")
        self._df = self._preprocess(df)
        return self._df

    def _preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["x", "y"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if {"x", "y"}.issubset(df.columns):
            df = df.dropna(subset=["x", "y"]).reset_index(drop=True)
        df["complex_id"] = df.index.astype(str)
        if "기본상세" in df.columns:
            df[["sido_kor", "sgg_kor"]] = df["기본상세"].apply(self._extract_admin)
        else:
            df["sido_kor"] = ""
            df["sgg_kor"] = ""
        for col in self._numeric_columns():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in self._bool_columns():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        return df

    def _extract_admin(self, address):
        parts = safe_str(address).split()
        sido = parts[0] if len(parts) > 0 else ""
        sgg = parts[1] if len(parts) > 1 else ""
        return pd.Series([sido, sgg])

    def _numeric_columns(self) -> list[str]:
        return [
            "건설호수", "승강기대수", "CCTV대수", "고령화율", "초고령비율", "아동청소년비율",
            "총인구수_계산", "경로당_면적", "복지관_면적", "노후도_년수",
            "접근성_의료종합", "접근성_복지종합", "접근성_교육문화종합", "접근성_돌봄종합",
            "커뮤니티_총활동횟수", "커뮤니티_총참여인원", "커뮤니티_분야다양성", "커뮤니티_유형다양성",
            "커뮤니티_세대당참여인원", "홈닥터_총지원건수", "홈닥터_세대당지원건수",
            "홈닥터_의료지원비율", "홈닥터_경제지원비율", "홈닥터_서비스이용률",
            "거버넌스_평균_연간합계", "거버넌스_완전연도수", "거버넌스_연간합계_2022",
            "거버넌스_연간합계_2023", "거버넌스_연간합계_2024", "거버넌스_추세기울기",
            "취약도_종합지수", "취약도_인구", "취약도_시설", "취약도_접근성",
            "취약도_서비스이용", "취약도_거버넌스", "취약도_이상탐지",
            "취약도_수동가중치", "취약도_entropy가중치", "취약도_hybrid가중치",
            "selected_anomaly_score", "ensemble_anomaly_score", "mc_selection_frequency",
            "mc_mean_rank", "mc_rank_std", "취약도_순위", "위험_백분위",
        ]

    def _bool_columns(self) -> list[str]:
        return [
            "경로당_있음", "복지관_있음", "운동시설_있음", "커뮤니티_매핑여부",
            "홈닥터_매핑여부", "거버넌스_악화중_여부", "거버넌스_매핑여부",
            "selected_anomaly", "ensemble_anomaly", "사각지대_여부", "영구임대_포함",
            "국민임대_포함", "행복주택_포함", "장기전세_포함", "취약임대_여부",
            "신규단지_여부", "소규모단지_여부", "대규모단지_여부", "robust_high_risk",
        ]

    def get_all_complexes(self) -> list[dict]:
        df = self.load()
        complexes = []
        for _, row in df.iterrows():
            score = safe_float(row.get("취약도_hybrid가중치"), 0) or safe_float(row.get("취약도_종합지수"), 0) or 0
            complexes.append({
                "id": safe_str(row["complex_id"]),
                "name": safe_str(row.get("단지명")),
                "village": safe_str(row.get("마을명")),
                "lat": safe_float(row.get("y")),
                "lng": safe_float(row.get("x")),
                "supply_type": safe_str(row.get("공급유형")),
                "risk_grade": safe_str(row.get("사각지대_등급")),
                "vulnerability_score": round(score, 4),
                "rank": safe_int(row.get("취약도_순위")),
                "cluster": safe_str(row.get("cluster_label")),
                "is_blindspot": safe_int(row.get("사각지대_여부")),
                "is_robust_highrisk": safe_int(row.get("robust_high_risk")),
                "postal_code": safe_str(row.get("우편번호")),
                "address": safe_str(row.get("기본상세")),
                "sigungu": safe_str(row.get("sgg_kor") or row.get("sgg_nm_e")),
                "sido": safe_str(row.get("sido_kor") or row.get("sido_nm_e")),
            })
        return complexes

    def search_complexes(self, query: str) -> list[dict]:
        df = self.load()
        q = query.strip().lower()
        mask = (
            df["단지명"].astype(str).str.lower().str.contains(q, na=False)
            | df["마을명"].astype(str).str.lower().str.contains(q, na=False)
            | df["기본상세"].astype(str).str.lower().str.contains(q, na=False)
            | df["sido_kor"].astype(str).str.lower().str.contains(q, na=False)
            | df["sgg_kor"].astype(str).str.lower().str.contains(q, na=False)
        )
        return [
            {
                "id": safe_str(row["complex_id"]),
                "name": safe_str(row.get("단지명")),
                "village": safe_str(row.get("마을명")),
                "risk_grade": safe_str(row.get("사각지대_등급")),
                "vulnerability_score": round(safe_float(row.get("취약도_hybrid가중치"), 0) or 0, 4),
                "sido": safe_str(row.get("sido_kor") or row.get("sido_nm_e")),
                "sigungu": safe_str(row.get("sgg_kor") or row.get("sgg_nm_e")),
            }
            for _, row in df[mask].head(30).iterrows()
        ]

    def get_complex_detail(self, complex_id: str) -> Optional[dict]:
        df = self.load()
        rows = df[df["complex_id"] == str(complex_id)]
        if rows.empty:
            return None
        return self._build_detail(rows.iloc[0])

    def _build_detail(self, row) -> dict:
        score = safe_float(row.get("취약도_hybrid가중치"), 0) or safe_float(row.get("취약도_종합지수"), 0) or 0
        risk_percentile = safe_float(row.get("위험_백분위"), 0)
        if risk_percentile is not None and risk_percentile <= 1:
            risk_percentile *= 100
        return {
            "id": safe_str(row["complex_id"]),
            "name": safe_str(row.get("단지명")),
            "village": safe_str(row.get("마을명")),
            "lat": safe_float(row.get("y")),
            "lng": safe_float(row.get("x")),
            "postal_code": safe_str(row.get("우편번호")),
            "address": safe_str(row.get("기본상세")),
            "sido": safe_str(row.get("sido_kor") or row.get("sido_nm_e")),
            "sigungu": safe_str(row.get("sgg_kor") or row.get("sgg_nm_e")),
            "emd": safe_str(row.get("emd_nm_e")),
            "supply_type": safe_str(row.get("공급유형")),
            "total_units": safe_int(row.get("건설호수")),
            "elevator_count": safe_int(row.get("승강기대수")),
            "cctv_count": safe_int(row.get("CCTV대수")),
            "building_age_years": safe_float(row.get("노후도_년수")),
            "elderly_rate": safe_float(row.get("고령화율")),
            "super_elderly_rate": safe_float(row.get("초고령비율")),
            "child_youth_rate": safe_float(row.get("아동청소년비율")),
            "total_population": safe_int(row.get("총인구수_계산")),
            "vulnerability_score": round(score, 4),
            "risk_percentile": round(risk_percentile or 0, 1),
            "rank": safe_int(row.get("취약도_순위")),
            "risk_grade": safe_str(row.get("사각지대_등급")),
            "is_blindspot": bool(safe_int(row.get("사각지대_여부"))),
            "is_robust_highrisk": bool(safe_int(row.get("robust_high_risk"))),
            "main_causes": safe_str(row.get("취약_주요원인")),
            "cluster": safe_str(row.get("cluster_label")),
            "mc_selection_freq": safe_float(row.get("mc_selection_frequency")),
            "is_new_complex": bool(safe_int(row.get("신규단지_여부"))),
            "is_small_complex": bool(safe_int(row.get("소규모단지_여부"))),
            "is_large_complex": bool(safe_int(row.get("대규모단지_여부"))),
            "permanent_rental": bool(safe_int(row.get("영구임대_포함"))),
            "national_rental": bool(safe_int(row.get("국민임대_포함"))),
            "happy_housing": bool(safe_int(row.get("행복주택_포함"))),
            "long_term_lease": bool(safe_int(row.get("장기전세_포함"))),
            "is_vulnerable_rental": bool(safe_int(row.get("취약임대_여부"))),
            "facilities": self._facilities(row),
            "accessibility": self._accessibility(row),
            "community": self._community(row),
            "home_doctor": self._home_doctor(row),
            "governance": self._governance(row),
            "vulnerability_detail": self._vulnerability(row, score),
        }

    def _facilities(self, row) -> dict:
        return {
            "senior_center": bool(safe_int(row.get("경로당_있음"))),
            "welfare_center": bool(safe_int(row.get("복지관_있음"))),
            "exercise_facility": bool(safe_int(row.get("운동시설_있음"))),
            "senior_center_area": safe_float(row.get("경로당_면적")),
            "welfare_center_area": safe_float(row.get("복지관_면적")),
            "facility_index": safe_float(row.get("시설종합지수")),
        }

    def _accessibility(self, row) -> dict:
        return {
            "medical": safe_float(row.get("접근성_의료종합")),
            "welfare": safe_float(row.get("접근성_복지종합")),
            "culture": safe_float(row.get("접근성_교육문화종합")),
            "care": safe_float(row.get("접근성_돌봄종합")),
        }

    def _community(self, row) -> dict:
        return {
            "total_activities": safe_float(row.get("커뮤니티_총활동횟수")),
            "participants": safe_float(row.get("커뮤니티_총참여인원")),
            "diversity": safe_float(row.get("커뮤니티_분야다양성")),
            "type_diversity": safe_float(row.get("커뮤니티_유형다양성")),
            "participants_per_household": safe_float(row.get("커뮤니티_세대당참여인원")),
            "mapped": bool(safe_int(row.get("커뮤니티_매핑여부"))),
        }

    def _home_doctor(self, row) -> dict:
        return {
            "total_supports": safe_float(row.get("홈닥터_총지원건수")),
            "supports_per_household": safe_float(row.get("홈닥터_세대당지원건수")),
            "medical_rate": safe_float(row.get("홈닥터_의료지원비율")),
            "economic_rate": safe_float(row.get("홈닥터_경제지원비율")),
            "usage_rate": safe_float(row.get("홈닥터_서비스이용률")),
            "mapped": bool(safe_int(row.get("홈닥터_매핑여부"))),
        }

    def _governance(self, row) -> dict:
        return {
            "avg_annual": safe_float(row.get("거버넌스_평균_연간합계")),
            "complete_years": safe_float(row.get("거버넌스_완전연도수")),
            "year_2022": safe_float(row.get("거버넌스_연간합계_2022")),
            "year_2023": safe_float(row.get("거버넌스_연간합계_2023")),
            "year_2024": safe_float(row.get("거버넌스_연간합계_2024")),
            "trend": safe_float(row.get("거버넌스_추세기울기")),
            "worsening": bool(safe_int(row.get("거버넌스_악화중_여부"))),
            "mapped": bool(safe_int(row.get("거버넌스_매핑여부"))),
        }

    def _vulnerability(self, row, score) -> dict:
        return {
            "total": round(score, 4),
            "population": safe_float(row.get("취약도_인구")),
            "facility": safe_float(row.get("취약도_시설")),
            "accessibility": safe_float(row.get("취약도_접근성")),
            "service": safe_float(row.get("취약도_서비스이용")),
            "governance": safe_float(row.get("취약도_거버넌스")),
            "anomaly": safe_float(row.get("취약도_이상탐지")),
        }
