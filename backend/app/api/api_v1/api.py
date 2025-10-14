from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    rag_llm_api,
    data_stats,
    data_browse_api,
    data_analytics_api,
    admin_data_api,
    excel_evaluation_api,
    ragas_standalone_api,
    rag_services_api,
    production_recommendation_api,
)

# 临时注释掉 RAGAS 相关导入，解决 uvloop 兼容性问题
# from app.api.api_v1.endpoints import ragas_evaluation_api
from app.api.api_v1.endpoints import ragas_api

api_router = APIRouter()

# Deprecated modules (kept imported for compatibility, routes disabled)
# api_router.include_router(acrac_simple.router, prefix="/acrac", tags=["acrac-v2"])                  # deprecated
# api_router.include_router(intelligent_analysis.router, prefix="/acrac/intelligent", tags=["intelligent-analysis"])  # deprecated
# api_router.include_router(three_methods_api.router, prefix="/acrac/methods", tags=["three-methods"])  # deprecated
# api_router.include_router(vector_search_api_v2.router, prefix="/acrac/vector/v2", tags=["vector-search-v2"])        # deprecated

# Include the RAG+LLM intelligent recommendation API
api_router.include_router(
    rag_llm_api.router, prefix="/acrac/rag-llm", tags=["rag-llm-recommendation"]
)

# Include simplified production recommendation API
api_router.include_router(
    production_recommendation_api.router,
    prefix="/acrac",
    tags=["production-recommendation"],
)

# Include modular RAG services API
api_router.include_router(
    rag_services_api.router, prefix="/acrac/rag-services", tags=["rag-services"]
)

# Include the data statistics API
api_router.include_router(data_stats.router, prefix="/data", tags=["data-statistics"])

# Tools/micro endpoints (migrated to rag-services). Keep disabled.
# api_router.include_router(tools_api.router, prefix="/acrac/tools", tags=["tools"])  # deprecated
api_router.include_router(
    data_browse_api.router, prefix="/acrac/data", tags=["data-browse"]
)
api_router.include_router(
    data_analytics_api.router, prefix="/acrac/analytics", tags=["data-analytics"]
)
api_router.include_router(
    admin_data_api.router, prefix="/admin/data", tags=["admin-data"]
)

# Include Excel evaluation API
api_router.include_router(
    excel_evaluation_api.router,
    prefix="/acrac/excel-evaluation",
    tags=["excel-evaluation"],
)

# Deprecated evaluation endpoints (not used by frontend now)
# api_router.include_router(evaluation_project_api.router, prefix="/evaluation", tags=["evaluation-projects"])  # deprecated
# api_router.include_router(inference_evaluation_api.router, prefix="/evaluation", tags=["inference-evaluation"])  # deprecated

# 临时注释掉 RAGAS 相关路由，解决 uvloop 兼容性问题
# api_router.include_router(ragas_evaluation_api.router, prefix="/acrac/ragas-evaluation", tags=["ragas-evaluation"])

# Include RAGAS API
api_router.include_router(ragas_api.router, prefix="/ragas", tags=["ragas"])

# Include RAGAS standalone API
api_router.include_router(
    ragas_standalone_api.router, prefix="/ragas-standalone", tags=["ragas-standalone"]
)
