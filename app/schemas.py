from __future__ import annotations

from pydantic import BaseModel


class TriggerReportResponse(BaseModel):
    report_id: str


class ReportStatusResponse(BaseModel):
    status: str




