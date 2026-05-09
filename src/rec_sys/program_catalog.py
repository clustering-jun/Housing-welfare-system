PROGRAM_CATALOG: dict[str, dict] = {
    "P01": {"name": "관리홈닥터 운영", "category": "돌봄·안전망", "description": "왕래가 적고 돌봄과 관심이 필요한 입주민에게 안부 확인, 세대 방문, 거주 불편사항 확인, 생활 고충 상담, 가사지원 연계를 제공하는 사업입니다.", "conditions": ["고령화율 높음", "홈닥터 이용률 낮음", "서비스 이용 취약", "사회적 고립 위험"]},
    "P02": {"name": "자살·고독사 예방", "category": "돌봄·안전망", "description": "고령자와 독거세대 등 고위험군을 발굴하고 예방 인력과 지역사회 유관기관 협업을 통해 정기 모니터링과 사례 개입을 지원하는 사업입니다.", "conditions": ["초고령 비율 높음", "이상탐지 점수 높음", "거버넌스 취약", "커뮤니티 참여 부족"]},
    "P03": {"name": "홈서비스 운영", "category": "생활지원", "description": "고령 독거세대와 장애인 등 거동이 불편한 세대의 주거생활 불편을 확인하고 방문 상담, 생활 불편 처리, 외부 서비스 연계를 제공하는 사업입니다.", "conditions": ["고령화율 높음", "노후도 높음", "시설 취약", "생활 불편 해결 필요"]},
    "P04": {"name": "저장강박세대 지원", "category": "주거환경", "description": "정신건강 위기 등으로 세대 내 물건을 과도하게 적치한 가구를 발굴하고 상담, 정리 지원, 위생·안전 회복을 연계하는 서비스입니다.", "conditions": ["이상탐지 점수 높음", "사례관리 필요", "주거환경 위험", "고립 위험"]},
    "P05": {"name": "100세 이상 어르신 장수잔치상 운영", "category": "정서지원", "description": "100세 이상 어르신에게 기념품 또는 잔치상을 제공하여 경로효친 문화를 확산하고 소외감과 고립감을 완화하는 사업입니다.", "conditions": ["초고령 비율 높음", "고령자 비중 높음", "정서 지원 필요"]},
    "P06": {"name": "문화예술공연 유치", "category": "문화·커뮤니티", "description": "외부기관 협업으로 문화예술공연을 유치해 입주민의 문화 향유 기회를 확대하고 문화격차를 완화하는 사업입니다.", "conditions": ["교육문화 접근성 취약", "커뮤니티 활동 부족", "주민 교류 필요"]},
    "P07": {"name": "생활스포츠 동아리 운영", "category": "문화·커뮤니티", "description": "탁구, 게이트볼, 걷기 등 단지 특성에 맞는 생활스포츠 동아리를 운영하여 사회적 고립가구의 주민 관계망 형성을 지원하는 사업입니다.", "conditions": ["커뮤니티 참여 부족", "거버넌스 취약", "고령자 건강관리 필요"]},
    "P08": {"name": "해피아이공부방 운영", "category": "아동·교육", "description": "단지 내 가용 공간과 지역 자원을 활용하여 방학기간 돌봄이 필요한 어린이의 정서 함양, 창의력, 방과 후 학습을 지원하는 사업입니다.", "conditions": ["아동청소년 비율 높음", "교육문화 접근성 취약", "돌봄 접근성 취약"]},
    "P09": {"name": "1사1단지 결연", "category": "경제지원", "description": "지역사회 기업과 결연을 체결하고 기부받은 현금·현물을 단지 내 취약계층에게 지원하는 사업입니다.", "conditions": ["경제 지원 필요", "취약임대 단지", "영구임대 비중 높음"]},
    "P10": {"name": "관리비 지원 유치", "category": "경제지원", "description": "외부기관과 지자체 지원을 연계하여 공동 전기·수도요금, 에너지바우처, 가스요금 할인 등 주거비 부담을 경감하는 사업입니다.", "conditions": ["경제 취약", "서비스 이용 취약", "종합 취약도 높음"]},
    "P11": {"name": "퇴거위기세대 지원", "category": "긴급지원", "description": "관리비 또는 임대료 체납으로 퇴거위기가 발생한 세대에게 지역사회 지원 또는 공단 기금을 활용해 긴급 주거비와 상담을 연계하는 서비스입니다.", "conditions": ["경제지원 비율 높음", "긴급 주거비 지원 필요", "취약임대 단지"]},
    "P12": {"name": "영구임대주택 주거복지사 배치 운영", "category": "정책사업·전문인력", "description": "영구임대주택 내 수급자, 독거노인, 장애인 등 취약계층의 안정적 주거생활을 위해 주거상담, 돌봄, 주거환경 개선, 지역사회 협력 서비스를 지원하는 사업입니다.", "conditions": ["영구임대 단지", "종합 취약도 높음", "거버넌스 취약", "사례관리 필요"]},
}

CORE_CANDIDATES = {"P01", "P02", "P03", "P04", "P09", "P10", "P11", "P12"}
COMPLEMENTARY_CANDIDATES = {"P05", "P06", "P07", "P08"}

EXAMPLE_ACTIVITIES: dict[str, list[str]] = {
    "P01": ["정기 안부 확인", "세대 방문 상담", "생활 고충 접수", "가사지원 연계"],
    "P02": ["고위험군 발굴", "생명지킴이 연계", "정서지원 상담", "지역 정신건강기관 협업"],
    "P03": ["생활 불편 방문 점검", "거동불편 세대 상담", "소규모 주거생활 불편 처리", "외부 서비스 연계"],
    "P04": ["저장강박 의심세대 상담", "정리 지원 연계", "정신건강기관 협업", "위생·안전 회복 모니터링"],
    "P05": ["장수 기념품 전달", "어르신 축하 방문", "경로효친 행사", "정서적 지지 활동"],
    "P06": ["문화예술공연 유치", "입주민 문화행사", "외부 예술단체 협업", "문화격차 완화 프로그램"],
    "P07": ["탁구 동아리", "게이트볼 모임", "걷기 모임", "건강 생활체육 프로그램"],
    "P08": ["방학 공부방", "방과 후 학습 지원", "아동 정서활동", "창의 체험 프로그램"],
    "P09": ["기업 후원물품 전달", "취약계층 생활물품 지원", "지역기업 결연", "명절 나눔 행사"],
    "P10": ["에너지바우처 안내", "공동요금 지원 유치", "주거비 부담 상담", "지자체 감면제도 연계"],
    "P11": ["체납위기 상담", "긴급 주거비 연계", "퇴거위기 사례관리", "지역 복지자원 연결"],
    "P12": ["주거복지 상담", "취약계층 사례관리", "지역사회 협력망 운영", "복합 문제 세대 지원"],
}

PROGRAM_NAME_VARIANTS: dict[str, list[str]] = {
    "P01": ["찾아가는 안부확인·생활상담", "고립위험세대 관리홈닥터", "정기 방문형 생활고충 상담", "취약세대 안부확인 돌봄"],
    "P02": ["고독사 예방 안심모니터링", "생명안전 관계망 지원", "위기세대 정서안전 프로그램", "독거세대 고위험군 사례관리"],
    "P03": ["고령 독거세대 생활불편 지원", "거동불편세대 홈서비스", "방문형 주거생활 불편 상담", "생활지원 홈케어 프로그램"],
    "P04": ["저장강박 주거환경 회복 지원", "위생·안전 주거정리 지원", "고위험세대 주거환경 사례관리", "주거환경 개선 동행지원"],
    "P05": ["장수 어르신 축하 방문", "100세 어르신 정서지원 행사", "장수 기념품 전달 프로그램", "어르신 만수무강 축하 나눔"],
    "P06": ["입주민 문화예술 나눔공연", "찾아오는 문화공연 유치", "단지 문화향유 프로그램", "외부기관 협력 문화행사"],
    "P07": ["게이트볼·걷기 생활스포츠 모임", "고령자 건강동아리", "주민 관계망 생활체육", "탁구·걷기 건강모임"],
    "P08": ["방학 돌봄 공부방", "해피아이 방과후 학습지원", "아동 정서·창의 공부방", "임대주택 어린이 학습돌봄"],
    "P09": ["지역기업 결연 나눔", "취약계층 후원물품 연계", "1사1단지 생활물품 지원", "지역사회 결연 후원 프로그램"],
    "P10": ["주거비 부담 완화 연계", "관리비·에너지바우처 지원 안내", "공동요금 지원자원 유치", "주거비 절감 상담 프로그램"],
    "P11": ["퇴거위기 긴급 주거비 연계", "체납위기세대 주거안정 상담", "긴급 주거비 사례관리", "퇴거예방 생활안정 지원"],
    "P12": ["영구임대 통합 주거복지 상담", "취약세대 주거복지사 사례관리", "주거복지 전문상담·지역연계", "고위험 단지 주거복지 통합지원"],
}


def get_program_display_name(pid: str, detail: dict | None = None) -> str:
    variants = PROGRAM_NAME_VARIANTS.get(pid) or [PROGRAM_CATALOG[pid]["name"]]
    if not detail:
        return variants[0]
    key = f"{detail.get('id', '')}|{detail.get('name', '')}|{pid}"
    return variants[sum(ord(ch) for ch in key) % len(variants)]


def safe_number(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def score_programs(detail: dict) -> list[tuple[str, float, list[str]]]:
    vuln = detail.get("vulnerability_detail", {})
    acc = detail.get("accessibility", {})
    comm = detail.get("community", {})
    hd = detail.get("home_doctor", {})
    elderly = safe_number(detail.get("elderly_rate"))
    super_elderly = safe_number(detail.get("super_elderly_rate"))
    child_youth = safe_number(detail.get("child_youth_rate"))
    v_total = safe_number(vuln.get("total"))
    v_facility = safe_number(vuln.get("facility"))
    v_service = safe_number(vuln.get("service"))
    v_governance = safe_number(vuln.get("governance"))
    v_anomaly = safe_number(vuln.get("anomaly"))
    culture_access = clip(safe_number(acc.get("culture")) / 10)
    care_access = clip(safe_number(acc.get("care")) / 10)
    low_community = clip(1.0 - safe_number(comm.get("participants_per_household")) / 0.3)
    hd_economic = safe_number(hd.get("economic_rate"))
    hd_usage_gap = clip(1.0 - safe_number(hd.get("usage_rate")))
    permanent = 1.0 if detail.get("permanent_rental") else 0.0
    vulnerable = 1.0 if detail.get("is_vulnerable_rental") else 0.0
    building_age = clip(safe_number(detail.get("building_age_years")) / 30)
    is_blindspot = 1.0 if detail.get("is_blindspot") else 0.0
    rows = {
        "P01": (elderly * 2.0 + v_service * 1.6 + hd_usage_gap + low_community * 0.8, ["고령 세대 돌봄 필요", "서비스 이용 취약", "사회적 고립 위험"]),
        "P02": (super_elderly * 3.0 + v_anomaly * 1.8 + v_governance * 1.2 + low_community * 0.8, ["초고령 비율 높음", "이상탐지 점수 높음", "거버넌스 취약"]),
        "P03": (elderly * 1.4 + v_facility * 1.5 + building_age * 1.2 + v_service * 0.8, ["고령 세대 생활지원 필요", "시설 취약", "노후 단지"]),
        "P04": (v_anomaly * 2.8 + v_governance * 0.8 + is_blindspot * 0.5, ["이상탐지 기반 사례관리 필요", "주거환경 위험"]),
        "P05": (super_elderly * 4.0 + elderly * 0.6, ["초고령 비율 높음", "고령자 정서지원 필요"]),
        "P06": (culture_access * 1.8 + low_community * 1.4 + v_governance * 0.6, ["교육문화 접근성 취약", "커뮤니티 활동 부족"]),
        "P07": (low_community * 1.8 + v_governance * 1.3 + elderly * 0.6, ["주민 관계망 형성 필요", "고령자 건강·교류 필요"]),
        "P08": (child_youth * 4.2 + culture_access * 0.6 + care_access * 0.6, ["아동청소년 비율 높음", "돌봄·교육 접근성 보완 필요"]),
        "P09": (vulnerable * 1.8 + permanent * 1.5 + hd_economic * 1.4 + v_total * 0.5, ["취약임대 단지", "경제지원 수요 확인"]),
        "P10": (vulnerable * 1.4 + permanent * 1.2 + hd_economic * 2.0 + v_total * 0.8, ["주거비 부담 완화 필요", "종합 취약도 높음"]),
        "P11": (hd_economic * 2.6 + vulnerable * 0.8 + is_blindspot * 0.4, ["긴급 주거비 지원 가능성 점검", "사각지대 단지"]),
        "P12": (permanent * 2.5 + v_total * 1.6 + v_governance + is_blindspot * 0.6, ["영구임대 단지", "종합 취약도 높음", "통합 사례관리 필요"]),
    }
    return sorted([(pid, max(score, 0.01), reasons) for pid, (score, reasons) in rows.items()], key=lambda item: item[1], reverse=True)


def diversify_program_order(scored: list[tuple[str, float, list[str]]], candidates: set[str], limit: int, min_ratio: float) -> list[str]:
    rows = [(pid, score) for pid, score, _ in scored if pid in candidates]
    if not rows:
        return []
    top_score = max(score for _, score in rows) or 1.0
    remaining = [(pid, score) for pid, score in rows if score >= top_score * min_ratio]
    selected = []
    used_categories = set()
    while remaining and len(selected) < limit:
        best = max(remaining, key=lambda item: (PROGRAM_CATALOG[item[0]]["category"] not in used_categories, item[1]))
        selected.append(best[0])
        used_categories.add(PROGRAM_CATALOG[best[0]]["category"])
        remaining.remove(best)
    for pid, _ in rows:
        if len(selected) >= limit:
            break
        if pid not in selected:
            selected.append(pid)
    return selected[:limit]


def select_programs(detail: dict) -> tuple[list[str], list[str], dict[str, list[str]]]:
    scored = score_programs(detail)
    reasons = {pid: reason for pid, _, reason in scored}
    core = diversify_program_order(scored, CORE_CANDIDATES, 4, 0.45)
    comp = diversify_program_order(scored, COMPLEMENTARY_CANDIDATES, 2, 0.25)
    return core or ["P01", "P03"], comp or ["P06"], reasons
