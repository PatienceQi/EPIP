"""FastAPI application entry point for the EPIP service."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from epip import __version__
from epip.api import monitoring_router, schemas
from epip.api.dependencies import get_neo4j_client, get_redis_client, get_tenant_repository
from epip.api.middleware.metrics import MetricsMiddleware
from epip.api.middleware.tenant import TenantMiddleware
from epip.api.routes import api_router
from epip.config import settings
from epip.db import Neo4jClient, RedisClient
from epip.utils.logging import get_logger

logger = get_logger()

app = FastAPI(
    title="Enterprise Policy Insight Platform",
    description="""
EPIP (Enterprise Policy Insight Platform) 是一个基于知识图谱的政策法规智能问答系统。

## 核心功能

* **智能问答** - 基于知识图谱的政策法规查询与推理
* **事实验证** - 答案溯源与幻觉检测
* **可视化** - 推理轨迹与知识图谱可视化
* **多租户** - 企业级多租户隔离与权限管理

## 认证

所有 API 请求需要在 Header 中携带 `X-Tenant-ID` 标识租户。
""",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "EPIP Team",
        "email": "support@epip.example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {"name": "query", "description": "知识图谱查询与问答接口"},
        {"name": "visualization", "description": "推理轨迹与图谱可视化"},
        {"name": "tenants", "description": "多租户管理"},
        {"name": "cache", "description": "缓存管理"},
        {"name": "monitoring", "description": "系统监控与健康检查"},
        {"name": "system", "description": "系统状态"},
    ],
)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SPA_INDEX = STATIC_DIR / "index.html"

tenant_repository = get_tenant_repository()
app.state.tenant_repository = tenant_repository
app.add_middleware(
    TenantMiddleware,
    repository=tenant_repository,
    public_paths=(
        "/health",
        "/api/health",
        "/api/status",
        "/api/tenants",
        "/favicon.ico",
        "/monitoring/metrics",
        "/monitoring/health/live",
        "/monitoring/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
    ),
    public_prefixes=("/static/", "/assets/"),
    allow_spa_fallback=True,
)
app.add_middleware(MetricsMiddleware)
app.include_router(api_router)
app.include_router(monitoring_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True, check_dir=False), name="static")
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False), name="assets")


@app.on_event("startup")
async def startup_event() -> None:
    """应用启动时初始化默认管理员租户"""
    from epip.admin import Tenant, TenantStatus

    default_tenant = Tenant(
        tenant_id="admin",
        name="Administrator",
        status=TenantStatus.ACTIVE,
        config={"role": "admin"},
    )
    try:
        await tenant_repository.create(default_tenant)
        logger.info("default_admin_tenant_created", tenant_id="admin")
    except ValueError:
        logger.info("default_admin_tenant_exists", tenant_id="admin")


@app.get("/health", tags=["system"], response_model=schemas.HealthResponse)
async def health_check(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    redis: RedisClient = Depends(get_redis_client),
) -> schemas.HealthResponse:
    """Return detailed upstream health indicators."""
    logger.debug("health_check", debug=settings.debug)

    neo4j_ok = await neo4j.ping()
    redis_ok = await redis.ping()
    status = "healthy" if neo4j_ok and redis_ok else "unhealthy"

    return schemas.HealthResponse(
        status=status,
        services=schemas.ServiceStatus(
            neo4j="up" if neo4j_ok else "down",
            redis="up" if redis_ok else "down",
        ),
    )


def _get_spa_index() -> Path:
    """Resolve the built SPA index, ensuring the file exists."""
    if not SPA_INDEX.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return SPA_INDEX


@app.get("/", include_in_schema=False)
async def serve_spa_root() -> FileResponse:
    """Serve the SPA entry point for the root path."""
    return FileResponse(_get_spa_index())


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty favicon to avoid 404."""
    from fastapi.responses import Response

    return Response(content=b"", media_type="image/x-icon")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str) -> FileResponse:
    """Catch-all route that returns the built SPA index for client-side routing."""
    _ = full_path  # Path parameter captures client-side routes; response is always index.html.
    return FileResponse(_get_spa_index())
