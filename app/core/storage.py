import json
import time
import urllib.parse
from datetime import datetime, timedelta

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


def promote_file(temp_url: str, permanent_folder: str) -> str:
    if "/temp/" not in temp_url:
        return temp_url

    parsed = urllib.parse.urlparse(temp_url)
    path_parts = parsed.path.lstrip("/").split("/")

    if path_parts[0] == settings.MINIO_BUCKET:
        object_path = "/".join(path_parts[1:])
    else:
        object_path = "/".join(path_parts)

    file_name = object_path.split("/")[-1]
    user_id = object_path.split("/")[0]
    new_object_path = f"{user_id}/{permanent_folder}/{file_name}"

    minio_client.copy_object(
        settings.MINIO_BUCKET,
        new_object_path,
        CopySource(settings.MINIO_BUCKET, object_path),
    )
    minio_client.remove_object(settings.MINIO_BUCKET, object_path)

    return temp_url.replace(object_path, new_object_path)
