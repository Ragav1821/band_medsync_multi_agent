"""
MedSync AI — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.api import router
from routers.auth_router import auth_router
from routers.video_router import video_router

app = FastAPI(
    title="MedSync AI",
    description="AI-Powered Multi-Agent Hospital Emergency Coordination Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — P1-2: wildcard removed; only specific approved origins allowed
# Add your deployed frontend URL here before going to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Mount all routers under /api/v1
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(video_router, prefix="/api/v1")  # Phase 20: Video Generator


@app.get("/")
async def root():
    return {
        "name": "MedSync AI",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/api/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "agents": "ready"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

