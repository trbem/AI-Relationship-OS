from fastapi import APIRouter

from app.api.routes import chat, data, graph, group_simulations, person, reports, simulate, system, worlds

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(person.router, prefix="/person", tags=["person"])
api_router.include_router(simulate.router, prefix="/simulate", tags=["simulate"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(
    group_simulations.router,
    prefix="/group-simulations",
    tags=["group-simulations"],
)
api_router.include_router(worlds.router, tags=["persona-worlds"])
