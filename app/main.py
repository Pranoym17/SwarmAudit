from fastapi import FastAPI, HTTPException

from app.agents.graph import AuditGraph
from app.config import get_settings
from app.schemas import AuditReport, AuditRequest

app = FastAPI(title="SwarmAudit", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": get_settings().app_name}


@app.post("/audit", response_model=AuditReport)
async def audit(request: AuditRequest) -> AuditReport:
    try:
        graph = AuditGraph()
        return await graph.run(str(request.repo_url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}") from exc
