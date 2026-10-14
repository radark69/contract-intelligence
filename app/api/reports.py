import uuid

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from fastapi.responses import Response

from app.reports.service import report_service

router = APIRouter(prefix="/documents", tags=["reports"])


@router.get("/{document_id}/report.{fmt}")
async def download_report(
    document_id: uuid.UUID,
    fmt: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("documents:download")),
) -> Response:
    if fmt not in ("docx", "pdf", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be docx, pdf, or xlsx")
    try:
        payload, media_type, filename = await report_service.generate(document_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"report generation failed: {e}") from e

    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
