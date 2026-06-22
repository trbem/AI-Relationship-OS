import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import SimulationSession, StrategyReport, User

router = APIRouter()


class ReportRequest(BaseModel):
    session_id: str
    title: str | None = None


def _session(db: Session, session_id: str, user_id: str) -> SimulationSession:
    session = db.get(SimulationSession, session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="simulation session not found")
    return session


def _build_report(session: SimulationSession) -> tuple[str, dict, list[dict]]:
    scenarios = []
    evidence: dict[str, dict] = {}
    for item in session.scenarios:
        result = json.loads(item.result_json) if item.result_json else {}
        top = (result.get("prediction") or [{}])[0]
        scenarios.append(
            {
                "label": item.label,
                "wording": item.wording,
                "timing": item.timing,
                "channel": item.channel,
                "goal": item.goal,
                "likely_response": top.get("text"),
                "probability": top.get("probability"),
                "confidence": result.get("confidence_summary", {}).get("score"),
                "advantages": top.get("supporting_factors", []),
                "risks": top.get("counter_factors", []),
            }
        )
        for source in result.get("evidence", []):
            evidence[source["id"]] = source
    title = f"Communication strategy: {session.title}"
    lines = [
        f"# {title}",
        "",
        "## Goal and context",
        session.original_question,
        "",
        "## Options",
    ]
    for item in scenarios:
        lines.extend(
            [
                "",
                f"### {item['label']}",
                f"- Wording: {item['wording']}",
                f"- Timing: {item['timing'] or 'Unspecified'}",
                f"- Channel: {item['channel'] or 'Unspecified'}",
                f"- Likely response: {item['likely_response'] or 'Insufficient data'}",
                f"- Probability: {item['probability'] or 0:.0%}",
                f"- Confidence: {item['confidence'] or 0:.0%}",
            ]
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "Prefer the option whose wording fits the goal while retaining the strongest evidence coverage. Treat probabilities as scenario comparisons, not certainty.",
            "",
            "## Uncertainty",
            "This report summarizes historical patterns and cannot determine a real person's future behavior.",
            "",
            "## Evidence",
        ]
    )
    for item in evidence.values():
        lines.append(f"- [{item['type']}] {item['excerpt']}")
    return "\n".join(lines), {"scenarios": scenarios}, list(evidence.values())


@router.post("", status_code=201)
def create_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = _session(db, request.session_id, current_user.id)
    markdown, payload, evidence = _build_report(session)
    report = StrategyReport(
        user_id=current_user.id,
        session_id=session.id,
        title=request.title or f"Communication strategy: {session.title}",
        content_markdown=markdown,
        payload_json=json.dumps(payload, ensure_ascii=False),
        evidence_snapshot_json=json.dumps(evidence, ensure_ascii=False),
    )
    db.add(report)
    db.commit()
    return {"id": report.id, "title": report.title, "status": report.status}


@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    report = db.get(StrategyReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="report not found")
    return {
        "id": report.id,
        "session_id": report.session_id,
        "title": report.title,
        "status": report.status,
        "markdown": report.content_markdown,
        "payload": json.loads(report.payload_json),
        "evidence_snapshot": json.loads(report.evidence_snapshot_json),
        "created_at": report.created_at.isoformat(),
    }


@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|json|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    report = db.get(StrategyReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="report not found")
    if format == "json":
        content = json.dumps(
            {
                "title": report.title,
                "markdown": report.content_markdown,
                "payload": json.loads(report.payload_json),
                "evidence_snapshot": json.loads(report.evidence_snapshot_json),
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        return Response(content, media_type="application/json")
    if format == "pdf":
        return Response(
            _simple_pdf(report.title, report.content_markdown),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{report.id}.pdf"'},
        )
    return Response(
        report.content_markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


def _simple_pdf(title: str, markdown: str) -> bytes:
    lines = [title] + [line[:100] for line in markdown.splitlines() if line.strip()][:45]
    escaped = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    stream = ["BT", "/F1 11 Tf", "50 790 Td"]
    for index, line in enumerate(escaped):
        if index:
            stream.append("0 -16 Td")
        stream.append(f"({line.encode('ascii', 'replace').decode('ascii')}) Tj")
    stream.append("ET")
    body = "\n".join(stream).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(body)} >>\nstream\n".encode() + body + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return output.getvalue()
