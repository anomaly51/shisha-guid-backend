import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user
from app.core.storage import (
    build_media_url,
    detect_image_content_type,
    generate_presigned_policy,
    get_file,
    upload_file,
)
from app.models.user import User
from app.schemas.upload import UploadFileResponse, UploadPolicyResponse

router = APIRouter()
ALLOWED_CONTENT_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


@router.post("", response_model=UploadPolicyResponse)
async def get_upload_policy(
    request: Request,
    content_type: str,
    user: User = Depends(get_current_user),
):
    await enforce_rate_limit(request, "upload", settings.UPLOAD_RATE_LIMIT_PER_MINUTE)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    extension = CONTENT_TYPE_EXTENSIONS[content_type]

    file_name = f"{user.id}/temp/{uuid.uuid4()}.{extension}"
    url, form_data = generate_presigned_policy(file_name, content_type)

    return UploadPolicyResponse(url=url, form_data=form_data)


@router.post("/file", response_model=UploadFileResponse)
async def upload_media_file(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    await enforce_rate_limit(request, "upload", settings.UPLOAD_RATE_LIMIT_PER_MINUTE)
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    content = await file.read()
    if not content or len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    detected_content_type = detect_image_content_type(content)
    if detected_content_type != content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file content does not match declared image type",
        )

    extension = CONTENT_TYPE_EXTENSIONS[content_type]

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
