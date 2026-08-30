"""OCI Object Storage helper — upload + presigned URL."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import oci

from . import config


_CONFIG_PATH = os.path.expanduser(config.OCI_CONFIG_PATH)


def _client():
    conf = oci.config.from_file(_CONFIG_PATH, config.OCI_CONFIG_PROFILE)
    return oci.object_storage.ObjectStorageClient(conf)


def extract_ext(filename: str) -> str | None:
    """지원하는 이미지 확장자 추출 (소문자)."""
    if not filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("jpg", "jpeg", "png", "webp"):
        return ext
    return None


def upload_object(object_key: str, file_bytes: bytes, content_type: str) -> None:
    """bucket-team545-problemfiles 에 객체를 업로드한다."""
    client = _client()
    client.put_object(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        object_name=object_key,
        put_object_body=file_bytes,
        content_type=content_type,
    )


def generate_presigned_url(object_key: str, expiry_minutes: int = 30) -> str:
    """Pre-Authenticated Request (PAR) 를 생성해 반환한다."""
    client = _client()
    expires = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
        name=f"admin-par-{uuid.uuid4().hex[:8]}",
        bucket_listing_action="Deny",
        object_name=object_key,
        access_type="ObjectRead",
        time_expires=expires,
    )
    resp = client.create_preauthenticated_request(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        create_preauthenticated_request_details=par_details,
    )
    return resp.data.full_path
