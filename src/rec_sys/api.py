import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rec_sys.config import STATIC_DIR, get_openai_api_key
from rec_sys.data_loader import WelfareDataLoader
from rec_sys.recommender import clear_cache, generate_recommendation


load_dotenv()

app = FastAPI(title="주거복지 프로그램 추천 시스템", description="임대주택 단지 맞춤형 복지 프로그램 추천 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

data_loader = WelfareDataLoader(os.getenv("DATA_PATH"))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RecommendRequest(BaseModel):
    use_cache: bool = True
    force_refresh: bool = False


@app.get("/")
async def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "주거복지 프로그램 추천 시스템 API가 실행 중입니다."}


@app.get("/api/complexes")
async def get_all_complexes():
    try:
        complexes = data_loader.get_all_complexes()
        return {"total": len(complexes), "complexes": complexes}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"데이터 로딩 오류: {exc}")


@app.get("/api/complexes/search")
async def search_complexes(q: str = Query(..., min_length=1)):
    try:
        results = data_loader.search_complexes(q)
        return {"query": q, "total": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/complexes/{complex_id}")
async def get_complex_detail(complex_id: str):
    detail = data_loader.get_complex_detail(complex_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다.")
    return detail


@app.post("/api/complexes/{complex_id}/recommend")
async def recommend_programs(complex_id: str, body: RecommendRequest = RecommendRequest()):
    detail = data_loader.get_complex_detail(complex_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다.")
    model = os.getenv("LLM_MODEL", "gpt-4o")
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "3500"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    if body.force_refresh:
        clear_cache(complex_id, model)
    result = generate_recommendation(detail=detail, api_key=get_openai_api_key(), model=model, max_tokens=max_tokens, temperature=temperature, use_cache=body.use_cache and not body.force_refresh)
    return {"complex_id": complex_id, "complex_name": detail["name"], "recommendation": result}


@app.delete("/api/cache/{complex_id}")
async def clear_complex_cache(complex_id: str):
    clear_cache(complex_id, os.getenv("LLM_MODEL", "gpt-4o"))
    return {"message": f"단지 {complex_id}의 추천 캐시를 삭제했습니다."}


@app.delete("/api/cache")
async def clear_all_cache():
    clear_cache()
    return {"message": "전체 추천 캐시를 삭제했습니다."}


@app.get("/api/stats")
async def get_stats():
    try:
        df = data_loader.load()
        cluster_dist = {str(k): int(v) for k, v in df["cluster_label"].value_counts().to_dict().items()} if "cluster_label" in df.columns else {}
        supply_dist: dict[str, int] = {}
        if "공급유형" in df.columns:
            for value in df["공급유형"].dropna():
                for item in str(value).split(","):
                    item = item.strip()
                    if item:
                        supply_dist[item] = supply_dist.get(item, 0) + 1
        return {
            "total_complexes": int(len(df)),
            "blindspot_count": int(df["사각지대_여부"].sum()) if "사각지대_여부" in df.columns else 0,
            "robust_highrisk_count": int(df["robust_high_risk"].sum()) if "robust_high_risk" in df.columns else 0,
            "cluster_distribution": cluster_dist,
            "supply_type_distribution": supply_dist,
            "avg_vulnerability": round(float(df["취약도_hybrid가중치"].mean()), 4) if "취약도_hybrid가중치" in df.columns else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
