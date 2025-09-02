from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session
from pathlib import Path
import io
import uuid
from datetime import datetime

from .db import Base, engine, get_session, ensure_database_exists
from . import models
from .report import generate_report
from .loader import load_csvs_if_needed


app = FastAPI(title="Store Monitoring API")


# Create DB tables on startup
@app.on_event("startup")
def on_startup() -> None:
    ensure_database_exists()
    Base.metadata.create_all(bind=engine)


@app.post("/trigger_report")
def trigger_report(background_tasks: BackgroundTasks) -> dict:
    with get_session() as session:
        report_id = str(uuid.uuid4())
        report = models.Report(
            id=report_id,
            status="Running",
            created_at=datetime.utcnow(),
        )
        session.add(report)
        session.commit()

        # Ensure data is loaded before computing
        background_tasks.add_task(_run_generation_task, report_id)

    return {"report_id": report_id}


def _run_generation_task(report_id: str) -> None:
    # Load data and run generation in the same DB session
    with get_session() as session:
        try:
            load_csvs_if_needed(session)
            generate_report(session, report_id)
        except Exception as exc:  # noqa: BLE001 - top-level task guard
            # Mark report as failed
            rep: models.Report | None = session.get(models.Report, report_id)
            if rep is not None:
                rep.status = "Failed"
                rep.error_message = f"{type(exc).__name__}: {exc}"
                session.commit()


@app.post("/load_data")
def load_data() -> dict:
    with get_session() as session:
        load_csvs_if_needed(session)
    return {"status": "ok"}


@app.get("/get_report")
def get_report(report_id: str):
    with get_session() as session:
        report: models.Report | None = session.get(models.Report, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report_id not found")

        if report.status != "Complete":
            # Return minimal status string as specified
            return PlainTextResponse(content="Running" if report.status == "Running" else report.status)

        path = Path(report.file_path)
        if not path.exists():
            raise HTTPException(status_code=500, detail="Report file missing")

        buf = io.BytesIO(path.read_bytes())
        headers = {
            "X-Report-Status": "Complete",
            "Content-Disposition": f"attachment; filename={path.name}",
        }
        return StreamingResponse(buf, media_type="text/csv", headers=headers)


@app.get("/debug_report")
def debug_report(report_id: str) -> dict:
    with get_session() as session:
        report: models.Report | None = session.get(models.Report, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report_id not found")
        return {
            "report_id": report.id,
            "status": report.status,
            "error_message": report.error_message,
            "file_path": report.file_path,
        }


