import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.core.storage import (
    build_media_url,
    generate_presigned_policy,
    get_file,
    upload_file,
)
from app.models.user import User
from app.schemas.upload import UploadFileResponse, UploadPolicyResponse

router = APIRouter()
ALLOWED_CONTENT_TYPES = ["image/jpeg", "image/png", "image/gif"]
MAX_UPLOAD_BYTES = 5242880


@router.post("", response_model=UploadPolicyResponse)
async def get_upload_policy(
    content_type: str,
    user: User = Depends(get_current_user),
):
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    extension = content_type.split("/")[1]
    if extension == "jpeg":
        extension = "jpg"

    file_name = f"{user.id}/temp/{uuid.uuid4()}.{extension}"
    url, form_data = generate_presigned_policy(file_name, content_type)

    return UploadPolicyResponse(url=url, form_data=form_data)


@router.post("/file", response_model=UploadFileResponse)
async def upload_media_file(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    content = await file.read()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    extension = content_type.split("/")[1]
    if extension == "jpeg":
        extension = "jpg"

    object_name = f"{user.id}/temp/{uuid.uuid4()}.{extension}"
    upload_file(object_name, content_type, content)

    return UploadFileResponse(url=build_media_url(request, object_name))


@router.get("/media/{object_name:path}")
async def read_media_file(object_name: str):
    response = get_file(object_name)
    content_type = response.headers.get("Content-Type", "application/octet-stream")

    def stream():
        try:
            yield from response.stream(32 * 1024)
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(stream(), media_type=content_type)
