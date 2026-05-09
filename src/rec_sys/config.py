from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache"
STATIC_DIR = BASE_DIR / "web"


def get_path(env_name: str, default: Path) -> Path:
    value = os.getenv(env_name, "").strip()
    return Path(value) if value else default


def get_data_path() -> Path:
    return get_path("DATA_PATH", DATA_DIR / "processed" / "result_vulnerability_index.csv")


def get_community_csv_path() -> Path:
    return get_path("COMMUNITY_CSV_PATH", DATA_DIR / "raw" / "community" / "RentalHousing_CommunityStatus.csv")


def get_community_names_path() -> Path:
    return get_path("COMMUNITY_NAMES_PATH", DATA_DIR / "processed" / "unique_community_names_cleaned.txt")


def get_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "YOUR_OPENAI_API_KEY":
        return ""
    return key
