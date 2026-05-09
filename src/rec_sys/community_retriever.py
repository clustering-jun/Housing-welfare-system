from functools import lru_cache
import re

import pandas as pd

from rec_sys.config import get_community_csv_path, get_community_names_path


BANNED_PATTERNS = ["이동식", "이동형", "이동 차량", "의료차", "버스", "셔틀", "설치", "신설", "건립", "공사", "보수공사", "창문 강제", "적치물 처리"]
GOOD_KEYWORDS = ["관리홈닥터", "안부", "고독사", "자살", "홈서비스", "저장강박", "장수", "문화", "공연", "스포츠", "동아리", "게이트볼", "탁구", "공부방", "학습", "돌봄", "1사1단지", "결연", "관리비", "에너지", "퇴거", "상담", "나눔", "후원", "건강", "방문", "정서", "관계망"]


def clean_name(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name or "")).strip()
    return re.sub(r"^(?:\d+[\.\)]\s*|\d+\s+)", "", text)


def is_program_like(name: str) -> bool:
    text = clean_name(name)
    if len(text) < 3:
        return False
    if any(pattern in text for pattern in BANNED_PATTERNS):
        return False
    return any(keyword in text for keyword in GOOD_KEYWORDS)


@lru_cache(maxsize=1)
def load_unique_program_names() -> list[str]:
    path = get_community_names_path()
    if not path.exists():
        return []
    names = []
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        name = clean_name(line)
        if is_program_like(name) and name not in names:
            names.append(name)
    return names


@lru_cache(maxsize=1)
def load_community_csv() -> pd.DataFrame:
    path = get_community_csv_path()
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="cp949", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    keep = [c for c in ["단지명", "공급유형", "커뮤니티유형", "커뮤니티명", "활동내용", "예산주체"] if c in df.columns]
    if not keep or "커뮤니티명" not in keep:
        return pd.DataFrame()
    df = df[keep].copy()
    df["커뮤니티명"] = df["커뮤니티명"].map(clean_name)
    df = df[df["커뮤니티명"].map(is_program_like)]
    if "활동내용" in df.columns:
        df["활동내용"] = df["활동내용"].fillna("").map(clean_name)
    return df.drop_duplicates("커뮤니티명")


def sample_rows(frame: pd.DataFrame, limit: int) -> list[dict]:
    if frame.empty:
        return []
    rows = []
    group_col = "커뮤니티유형" if "커뮤니티유형" in frame.columns else None
    if group_col:
        grouped = frame.groupby(group_col, dropna=False)
        for _, sub in grouped:
            for _, row in sub.head(max(1, limit // max(len(grouped), 1))).iterrows():
                rows.append({"type": str(row.get("커뮤니티유형", "프로그램")), "name": str(row.get("커뮤니티명", "")), "activity": str(row.get("활동내용", ""))[:80]})
                if len(rows) >= limit:
                    return rows
    for _, row in frame.head(limit).iterrows():
        rows.append({"type": str(row.get("커뮤니티유형", "프로그램")), "name": str(row.get("커뮤니티명", "")), "activity": str(row.get("활동내용", ""))[:80]})
    return rows[:limit]


def get_example_programs(detail: dict) -> dict:
    df = load_community_csv()
    name = str(detail.get("name", "")).strip()
    supply = str(detail.get("supply_type", "")).strip()
    same_complex = []
    similar_supply = []
    if not df.empty:
        if "단지명" in df.columns:
            same_complex = sample_rows(df[df["단지명"].astype(str).str.strip() == name], 12)
        if "공급유형" in df.columns:
            keyword = supply.split(",")[0].strip()
            supply_df = df[df["공급유형"].astype(str).str.contains(keyword, na=False)] if keyword else df
            similar_supply = sample_rows(supply_df, 18)
    curated = [{"type": "정제목록", "name": n, "activity": ""} for n in load_unique_program_names()[:30]]
    return {"same_complex": same_complex, "similar_supply": similar_supply, "curated_names": curated}


def format_for_prompt(programs: dict) -> str:
    sections = []
    for key, title in [("same_complex", "동일 단지 운영 프로그램"), ("similar_supply", "유사 공급유형 운영 프로그램"), ("curated_names", "정제된 프로그램명 참고")]:
        items = programs.get(key, [])
        if not items:
            continue
        sections.append(f"### {title}")
        for item in items[:15]:
            activity = f" - {item['activity']}" if item.get("activity") else ""
            sections.append(f"- [{item.get('type', '프로그램')}] {item.get('name', '')}{activity}")
    return "\n".join(sections) if sections else "참고 가능한 운영 프로그램 데이터 없음"
