import json
import time
import urllib.parse
from io import BytesIO
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from minio import Minio
from minio.commonconfig import ENABLED, CopySource, Filter
from minio.datatypes import PostPolicy
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from app.core.config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def detect_image_content_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def init_minio():
    for _ in range(5):
        try:
            if not minio_client.bucket_exists(settings.MINIO_BUCKET):
                minio_client.make_bucket(settings.MINIO_BUCKET)

            config = LifecycleConfig(
                [
                    Rule(
                        ENABLED,
                        rule_filter=Filter(prefix="*/temp/"),
                        rule_id="auto-delete-temp-files",
                        expiration=Expiration(days=1),
                    )
                ]
            )
            minio_client.set_bucket_lifecycle(settings.MINIO_BUCKET, config)
            minio_client.set_bucket_policy(
                settings.MINIO_BUCKET,
                json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": ["*"]},
                                "Action": ["s3:GetObject"],
                                "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"],
                            }
                        ],
                    }
                ),
            )
            break
        except Exception:
            time.sleep(3)


def generate_presigned_policy(object_name: str, content_type: str):
    policy = PostPolicy(settings.MINIO_BUCKET, datetime.utcnow() + timedelta(hours=1))
    policy.add_equals_condition("$key", object_name)
    policy.add_starts_with_condition("$Content-Type", content_type)
    policy.add_content_length_range_condition(1, 5242880)

    form_data = minio_client.presigned_post_policy(policy)
    form_data["key"] = object_name

    if settings.MINIO_PUBLIC_URL:
        url = settings.MINIO_PUBLIC_URL.rstrip("/")
    else:
        protocol = "https" if settings.MINIO_SECURE else "http"
        url = f"{protocol}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}"

    return url, form_data


def build_media_url(request: Request, object_name: str) -> str:
    encoded_name = "/".join(
        urllib.parse.quote(part, safe="") for part in object_name.split("/")
    )
    if settings.MINIO_PUBLIC_URL:
        return f"{settings.MINIO_PUBLIC_URL.rstrip('/')}/{encoded_name}"

    base_url = settings.API_PUBLIC_URL or str(request.base_url).rstrip("/")
    encoded_name = "/".join(
        urllib.parse.quote(part, safe="") for part in object_name.split("/")
    )
    return f"{base_url}/api/v1/upload/media/{encoded_name}"


def upload_file(object_name: str, content_type: str, content: bytes) -> None:
    minio_client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type=content_type,
    )


def get_file(object_name: str):
    try:
        return minio_client.get_object(settings.MINIO_BUCKET, object_name)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


def _validate_stored_image(object_path: str) -> None:
    response = None
    try:
        stat = minio_client.stat_object(settings.MINIO_BUCKET, object_path)
        if stat.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        response = minio_client.get_object(settings.MINIO_BUCKET, object_path, offset=0, length=16)
        detected = detect_image_content_type(response.read(16))
        if detected != stat.content_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stored media content does not match declared image type",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Temporary media not found",
        ) from exc
    finally:
        if response is not None:
            response.close()
            response.release_conn()


def _configured_media_prefixes() -> list[str]:
    prefixes: list[str] = []
    if settings.MINIO_PUBLIC_URL:
        prefixes.append(settings.MINIO_PUBLIC_URL.rstrip("/") + "/")
    if settings.API_PUBLIC_URL:
        prefixes.append(
            settings.API_PUBLIC_URL.rstrip("/") + "/api/v1/upload/media/"
        )

    protocol = "https" if settings.MINIO_SECURE else "http"
    prefixes.append(f"{protocol}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/")
    return prefixes


def _is_dev_api_media_url(parsed: urllib.parse.ParseResult) -> bool:
    return (
        not settings.API_PUBLIC_URL
        and parsed.scheme in {"http", "https"}
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.path.startswith("/api/v1/upload/media/")
    )


def is_uploaded_media_url(media_url: str) -> bool:
    parsed = urllib.parse.urlparse(media_url)
    if not parsed.scheme and media_url.startswith("/api/v1/upload/media/"):
        return True
    if _is_dev_api_media_url(parsed):
        return True
    return any(media_url.startswith(prefix) for prefix in _configured_media_prefixes())


def extract_object_path(media_url: str) -> str:
    parsed = urllib.parse.urlparse(media_url)
    object_path = urllib.parse.unquote(parsed.path.lstrip("/"))

    media_prefix = "api/v1/upload/media/"
    if object_path.startswith(media_prefix):
        return object_path[len(media_prefix):]

    path_parts = object_path.split("/")
    if path_parts and path_parts[0] == settings.MINIO_BUCKET:
        return "/".join(path_parts[1:])

    return object_path


def promote_file(
    temp_url: str,
    permanent_folder: str,
    expected_user_id: str | None = None,
) -> str:
    if not is_uploaded_media_url(temp_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media URL does not belong to this storage bucket",
        )
    if "/temp/" not in temp_url:
        return temp_url

    object_path = extract_object_path(temp_url)
    path_parts = object_path.split("/")
    if len(path_parts) < 3 or path_parts[1] != "temp":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    user_id = path_parts[0]
    if expected_user_id and user_id != expected_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Temporary media belongs to another user",
        )

    file_name = path_parts[-1]
    new_object_path = f"{user_id}/{permanent_folder}/{file_name}"

    _validate_stored_image(object_path)

    minio_client.copy_object(
        settings.MINIO_BUCKET,
        new_object_path,
        CopySource(settings.MINIO_BUCKET, object_path),
    )
    minio_client.remove_object(settings.MINIO_BUCKET, object_path)

    return temp_url.replace(
        "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/")),
        "/".join(urllib.parse.quote(part, safe="") for part in new_object_path.split("/")),
    ).replace(object_path, new_object_path)
