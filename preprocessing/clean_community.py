import argparse
import re
from pathlib import Path


SIDO = [
    '서울', '부산', '인천', '대구', '광주', '대전', '울산', '세종',
    '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
    '통영', '창원', '수원', '고양', '용인', '성남', '안양', '청주', '전주',
    '목포', '여수', '순천', '포항', '구미', '원주', '춘천', '제천', '충주',
    '군산', '익산', '진주', '김해', '양산', '거제', '밀양', '사천',
    '경주', '안동', '영천', '상주', '문경', '나주', '광양', '아산', '천안',
]

ORG_KW = [
    '지역사회보장협의체', '사회보장협의체', '보장협의체', '생명존중협의체',
    '재단법인', '사단법인', '재단', '법인',
    '봉사단', '자원봉사단',
    '행정복지센터', '정신건강센터', '금연지원센터', '건강생활지원센터',
    '아트센터', '의료원',
]
SAFE_TERMS = ['사이버대학', '사이버대학원']

LEAD_BRACKET_TAGS = [
    r'\d+차\s*보고', r'구성', r'경도인지', r'교육[·\s]*훈련',
    r'공동생활[^\]]*질서유지', r'안전[·\s]*위생', r'안전관리',
    r'주거복지사?', r'일자리지원', r'외부자원\s*유치', r'외부지원\s*유치',
    r'입주민[^\]]*관리', r'입주민건강지원', r'장수사진',
    r'문화예술공연', r'새마을\s*지역공동체\s*실현운동',
    r'우리동네\s*복지상담소?', r'새해맞이[^\]]*돌봄',
    r'통영시\s*공동주택[^\]]*',
    r'정상군', r'중[·\s]*장년[^\]]*',
    r'[^\]]*지사\s*문화예술프로그램[^\]]*',
]

LEAD_PAREN_TAGS = [
    r'공동[채체]?', r'문화예술공연', r'특화사업[^)]*',
    r'에너지[^)]*', r'신나는[^)]*', r'사(?=\))',
    r'입주민건강지원',
]


def clean(name: str) -> str:
    name = name.strip()
    if not name:
        return ''
    name = name.lstrip('﻿')

    name = name.replace('"', '')
    name = re.sub(r'[「」『』【】〔〕❛❜`]', ' ', name)
    name = re.sub(r"[''‛]", '', name)
    name = re.sub(r'[《》〈〉]', ' ', name)
    name = re.sub(r'[［］]', '', name)

    safe = any(s in name for s in SAFE_TERMS)
    if not safe:
        for kw in ORG_KW:
            ek = re.escape(kw)
            name = re.sub(r'\[[^\]]*' + ek + r'[^\]]*\]\s*', '', name)
            name = re.sub(r'\([^)]*' + ek + r'[^)]*\)\s*', '', name)

    if not safe:
        for kw in ORG_KW:
            ek = re.escape(kw)
            name = re.sub(r'[가-힣\w]*' + ek + r'[가-힣\w]*', '', name)

    for tag in LEAD_BRACKET_TAGS:
        name = re.sub(r'^\s*\[' + tag + r'\]\s*(?=\S)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^\s*\[([^\]]+)\]\s*(?=\S)', r'\1 ', name)

    for tag in LEAD_PAREN_TAGS:
        name = re.sub(r'^\s*\(' + tag + r'\)\s*', '', name, flags=re.IGNORECASE)

    sido_pat = '|'.join(re.escape(s) for s in sorted(SIDO, key=len, reverse=True))
    name = re.sub(r'\((?:' + sido_pat + r')[가-힣\d]+(?:단지|동|읍|면)?\)\s*', '', name)
    name = re.sub(r'\((?:' + sido_pat + r')[가-힣]+\d+\)\s*', '', name)
    name = re.sub(r'\((?:' + sido_pat + r')\)\s*', '', name)
    name = re.sub(r'(?:' + sido_pat + r')지사\s*', '', name)

    name = re.sub(r'20\d{2}\.\d+분기?\s*', '', name)
    name = re.sub(r'20\d{2}년\s*/\s*\d+분기?\s*', '', name)
    name = re.sub(r'20\d{2}년\s*\d{1,2}월\s*[~\-]\s*\d{1,2}월\s*', '', name)
    name = re.sub(r'20\d{2}년\s*\d{1,2}월\s*', '', name)
    name = re.sub(r'20\d{2}년도?\s*', '', name)
    name = re.sub(r"'?\d{2}년도?\s*", '', name)
    name = re.sub(r'(?<![가-힣\w\.])20\d{2}(?![가-힣\w])\s*', '', name)

    name = re.sub(r'^\d{1,2}월\s*[~\-]\s*\d{1,2}월\s*', '', name)
    name = re.sub(r'^\d{1,2},\d{1,2}월\s*', '', name)
    name = re.sub(r'^\d{1,2}월\s*', '', name)
    name = re.sub(r'\(\d{1,2}월\)', '', name)
    name = re.sub(r'^[~/]\d{1,2}월\s*', '', name)

    name = re.sub(r'\[?\(?\d+차\s*보고\]?\)?\s*', '', name)
    name = re.sub(r'\d+/\d+분기\s*', '', name)
    name = re.sub(r'\(?\d+[차분기회]+차?\)?\s*', '', name)
    name = re.sub(r'\(?(상|하)반기\)?\s*', '', name)
    name = re.sub(r'\(?\d+회\)?\s*', '', name)
    name = re.sub(r'(?:동계|하계|춘계|추계)\s*', '', name)

    name = re.sub(r'^[\.\s]*\d*분기\s*', '', name)
    name = re.sub(r'^[\.\s]?\d+\s+(?=[가-힣])', '', name)
    name = re.sub(r'^[\.\/~\s,]+(?=[가-힣A-Za-z])', '', name)

    name = re.sub(r'\[([^\]]+)\]', r'\1', name)
    name = re.sub(r'\(\s*\)', '', name)
    name = re.sub(r'\[\s*\]', '', name)

    name = re.sub(r'^[와과]\s+함께하는\s*', '', name)

    name = re.sub(r'\s*[_~]\s*', ' ', name)
    name = re.sub(r'^[·\-\s,]+', '', name)
    name = re.sub(r'[·\-\s,]+$', '', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def get_args():
    parser = argparse.ArgumentParser(description="커뮤니티 프로그램명 정제")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="정제할 프로그램명 텍스트 파일 경로 (utf-8-sig, 한 줄에 하나씩)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="정제 결과 출력 파일 경로 (기본: 입력 파일과 같은 폴더에 _cleaned 접미사)",
    )
    return parser.parse_args()


def main():
    args = get_args()
    input_path = Path(args.input)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = input_path.with_stem(input_path.stem + "_cleaned")

    raw_lines = input_path.read_text(encoding="utf-8-sig").splitlines()
    raw_lines = [l.strip() for l in raw_lines if l.strip()]

    cleaned_all = [clean(l) for l in raw_lines]
    cleaned_all = [c for c in cleaned_all if len(c) >= 3]

    seen = set()
    unique = []
    for c in cleaned_all:
        key = re.sub(r'\s+', ' ', c).strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    unique.sort()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(unique))

    print(f"원본: {len(raw_lines)}개 → 정제 후: {len(unique)}개  (감소: {len(raw_lines) - len(unique)}개)")
    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
