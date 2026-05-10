import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.core.storage import generate_presigned_policy
from app.models.user import User
from app.schemas.upload import UploadPolicyResponse

router = APIRouter()


@router.post("", response_model=UploadPolicyResponse)
async def get_upload_policy(
    content_type: str,
    user: User = Depends(get_current_user),
):
    if content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    extension = content_type.split("/")[1]
    if extension == "jpeg":
        extension = "jpg"

    file_name = f"{user.id}/temp/{uuid.uuid4()}.{extension}"
    url, form_data = generate_presigned_policy(file_name, content_type)

    return UploadPolicyResponse(url=url, form_data=form_data)
