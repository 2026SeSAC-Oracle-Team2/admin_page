"""OCI Object Storage helper — upload + move + presigned URL.

키 규약: DB 에는 base 없는 rel_path("12/12.png")만 저장하고, 실제 객체 키는
항상 build_key(rel_path) = IMAGE_PATH_BASE + rel_path 로 조합한다.
"""
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


def build_key(rel_path: str) -> str:
    """DB 의 rel_path("12/12.png") → 버킷 객체 키("images/12/12.png")."""
    rel_path = (rel_path or "").lstrip("/")
    base = config.IMAGE_PATH_BASE
    if base and not base.endswith("/"):
        base += "/"
    # rel_path 가 이미 base 로 시작하면 중복 부착 방지 (레거시 경로 호환)
    # 단, tmp/ 는 base 밖의 임시 공간이므로 항상 순수 키로 유지한다.
    if rel_path.startswith("tmp/"):
        return rel_path
    if base and rel_path.startswith(base):
        return rel_path
    return f"{base}{rel_path}"


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


def delete_object(object_key: str) -> None:
    """bucket-team545-problemfiles 에서 객체를 삭제한다."""
    client = _client()
    client.delete_object(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        object_name=object_key,
    )


def move_object(src_key: str, dst_key: str) -> None:
    """객체를 다른 키로 이동한다 (GET → PUT → DELETE).

    OCI copy_object는 버킷에 Object Storage 서비스 프린시펄 권한이 필요해서
    버킷 정책에 따라 InsufficientServicePermissions가 뜰 수 있으므로
    GET/PUT/DELETE 조합으로 구현한다.
    """
    client = _client()
    obj = client.get_object(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        object_name=src_key,
    )
    data: bytes = obj.data.content
    content_type = obj.headers.get("Content-Type", "application/octet-stream")
    client.put_object(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        object_name=dst_key,
        put_object_body=data,
        content_type=content_type,
    )
    client.delete_object(
        namespace_name=config.OCI_NAMESPACE,
        bucket_name=config.OCI_BUCKET_PROBLEMFILES,
        object_name=src_key,
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