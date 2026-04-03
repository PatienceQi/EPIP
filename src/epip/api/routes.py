"""Routing configuration for EPIP's public API."""

from fastapi import APIRouter, Depends

from epip import __version__
from epip.api import schemas
from epip.api.admin import admin_graph_router
from epip.api.dependencies import (
    get_entity_linker,
    get_kg_builder,
    get_query_cache,
    get_query_engine,
    get_query_parser,
    get_query_planner,
    get_settings,
)
from epip.api.graph import router as graph_router
from epip.api.tenants import router as tenants_router
from epip.api.visualization import router as visualization_router
from epip.cache import QueryCache
from epip.config import Settings
from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.core.query_engine import QueryEngine
from epip.query.linker import EntityLinker
from epip.query.parser import QueryParser
from epip.query.planner import QueryPlanner

api_router = APIRouter()
core_router = APIRouter(prefix="/api", tags=["query"])


@core_router.get(
    "/health",
    response_model=schemas.HealthResponse,
    summary="API 健康检查",
    description="返回 API 服务健康状态，用于前端快速检测。",
)
async def api_health() -> schemas.HealthResponse:
    """Simple health check for frontend."""
    return schemas.HealthResponse(
        status="healthy",
        services=schemas.ServiceStatus(neo4j="up", redis="up"),
    )


@core_router.get(
    "/status",
    response_model=schemas.StatusResponse,
    summary="获取系统状态",
    description="返回当前部署环境和版本信息。",
)
async def get_status(settings: Settings = Depends(get_settings)) -> schemas.StatusResponse:
    """Expose runtime details for quick checks."""
    return schemas.StatusResponse(environment=settings.environment, version=__version__)


@core_router.post(
    "/query",
    response_model=schemas.QueryResponse,
    summary="执行知识图谱查询",
    description="""
执行知识图谱查询，支持自然语言问答。

查询流程：
1. 解析用户问题，识别意图和实体
2. 实体链接到知识图谱
3. 生成查询计划
4. 执行查询并返回结果

返回结果包含答案文本和元数据（意图、复杂度、查询计划等）。
""",
    responses={
        200: {
            "description": "查询成功",
            "content": {
                "application/json": {
                    "example": {
                        "result": "根据《数据安全法》第二十一条...",
                        "metadata": {
                            "source": "api",
                            "intent": "FACTUAL",
                            "complexity": "MEDIUM",
                        },
                    }
                }
            },
        }
    },
)
async def execute_query(
    payload: schemas.QueryRequest,
    engine: QueryEngine = Depends(get_query_engine),
    kg_builder: KnowledgeGraphBuilder = Depends(get_kg_builder),
    parser: QueryParser = Depends(get_query_parser),
    linker: EntityLinker = Depends(get_entity_linker),
    planner: QueryPlanner = Depends(get_query_planner),
) -> schemas.QueryResponse:
    """Run a lightweight query orchestration pipeline."""
    parsed = await parser.parse(payload.query)
    linked = await linker.link(parsed.entities, kg_builder)
    plan = await planner.plan(parsed, linked)
    result = await engine.query(payload.query)
    plan_payload = planner.to_json(plan)
    metadata = {
        "source": payload.source,
        "intent": parsed.intent.value,
        "complexity": str(parsed.complexity),
        "plan": plan_payload,
    }
    return schemas.QueryResponse(result=result, metadata=metadata)


@core_router.get(
    "/cache/stats",
    response_model=schemas.CacheStatsResponse,
    tags=["cache"],
    summary="获取缓存统计",
    description="返回查询缓存的命中率、大小和内存使用情况。",
)
async def get_cache_stats(
    cache: QueryCache = Depends(get_query_cache),
) -> schemas.CacheStatsResponse:
    """Expose cache insights for observability."""
    stats = await cache.stats()
    return schemas.CacheStatsResponse(
        hits=stats.hits,
        misses=stats.misses,
        hit_rate=stats.hit_rate,
        size=stats.size,
        memory_usage=stats.memory_usage,
    )


@core_router.post(
    "/cache/clear",
    response_model=schemas.CacheClearResponse,
    tags=["cache"],
    summary="清理缓存",
    description="按模式清理查询缓存。支持通配符模式，如 `query:*` 清理所有查询缓存。",
)
async def clear_cache(
    payload: schemas.CacheClearRequest,
    cache: QueryCache = Depends(get_query_cache),
) -> schemas.CacheClearResponse:
    removed = await cache.clear(payload.pattern)
    return schemas.CacheClearResponse(pattern=payload.pattern, cleared=removed)


api_router.include_router(core_router)
api_router.include_router(visualization_router)
api_router.include_router(tenants_router)
api_router.include_router(graph_router)
api_router.include_router(admin_graph_router)
