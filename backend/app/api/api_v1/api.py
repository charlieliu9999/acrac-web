from fastapi import APIRouter

from app.api.api_v1.endpoints import acrac_simple, vector_search_api_v2, rag_llm_api, data_stats, tools_api, data_browse_api, admin_data_api, excel_evaluation_api, ragas_api

api_router = APIRouter()

# Include the simplified ACRAC API
api_router.include_router(acrac_simple.router, prefix="/acrac", tags=["acrac-v2"])

# Deprecated/legacy endpoints (intelligent_analysis, three_methods) are not included to simplify API surface.

# Include the new vector search API V2
api_router.include_router(vector_search_api_v2.router, prefix="/acrac/vector/v2", tags=["vector-search-v2"])

# Include the RAG+LLM intelligent recommendation API
api_router.include_router(rag_llm_api.router, prefix="/acrac/rag-llm", tags=["rag-llm-recommendation"])

# Include the data statistics API
api_router.include_router(data_stats.router, prefix="/data", tags=["data-statistics"])

# Tools/micro endpoints (rerank, LLM parse, ragas)
api_router.include_router(tools_api.router, prefix="/acrac/tools", tags=["tools"])
api_router.include_router(data_browse_api.router, prefix="/acrac/data", tags=["data-browse"])
api_router.include_router(admin_data_api.router, prefix="/admin/data", tags=["admin-data"])

# Excel evaluation API
api_router.include_router(excel_evaluation_api.router, prefix="/acrac/excel-evaluation", tags=["excel-evaluation"])
# Disabled problematic ragas_evaluation_api due to uvloop/nest_asyncio import conflict
# api_router.include_router(ragas_evaluation_api.router, prefix="/acrac/ragas-evaluation", tags=["ragas-evaluation"])

# RAGAS API (new implementation)
api_router.include_router(ragas_api.router, prefix="/ragas", tags=["ragas"])
