from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import select

from app.api.deps import DbSession, client_ip, require
from app.models import PriceList, User
from app.permissions import Permission
from app.schemas.catalog import ImportReport
from app.services import catalog_import

router = APIRouter(prefix="/catalog/import", tags=["catalog import"])

CanWrite = Annotated[User, Depends(require(Permission.CATALOG_WRITE))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("", response_model=ImportReport)
async def import_catalog(
    file: UploadFile,
    db: DbSession,
    actor: CanWrite,
    request: Request,
    dry_run: Annotated[
        bool, Query(description="true = solo valida y muestra qué cambiaría (por defecto)")
    ] = True,
) -> ImportReport:
    """Importa productos, variantes y precios desde .csv o .xlsx.

    Por seguridad el valor por defecto es `dry_run=true`: primero se previsualiza y
    luego se confirma con `dry_run=false`.
    """
    content = await file.read(catalog_import.MAX_BYTES + 1)
    try:
        return catalog_import.run(
            db, filename=file.filename or "", content=content, dry_run=dry_run,
            actor_id=actor.id, ip=client_ip(request),
        )  # fmt: skip
    except catalog_import.ImportFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None


@router.get("/template", response_class=Response)
def download_template(db: DbSession, _: CanWrite) -> Response:
    codes = list(db.scalars(select(PriceList.code).order_by(PriceList.id)))
    return Response(
        content=catalog_import.template_xlsx(codes),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="plantilla_catalogo.xlsx"'},
    )
