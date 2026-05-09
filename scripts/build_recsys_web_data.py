import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rec_sys.static_builder import build_recommendation_data


def get_args():
    parser = argparse.ArgumentParser(description="복지 추천 시스템 웹 JSON 데이터 빌드")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="web/recsys/data",
        help="JSON 데이터 출력 디렉토리",
    )
    return parser.parse_args()


def main():
    args = get_args()
    build_recommendation_data(args.output_dir)
    print(f"빌드 완료: {Path(args.output_dir)}")


if __name__ == "__main__":
    main()
