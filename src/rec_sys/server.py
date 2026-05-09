import os

import uvicorn


def run_server() -> None:
    uvicorn.run(
        "rec_sys.api:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    run_server()
