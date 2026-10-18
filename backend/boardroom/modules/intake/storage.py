"""Private file storage (FR-4.1, FR-12.1). Files go straight to storage with a short-lived
signed link. The provider is open (OPEN.md): S3-compatible in production, a local folder
in development and tests.

Raw uploads land under quarantine/ and are deleted once the pay-free copy is written
(FR-4.4). Only the clean copy is kept.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import jwt

from boardroom.config import get_settings

UPLOAD_LINK_SECONDS = 600


@dataclass
class UploadLink:
    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def size(self, key: str) -> int | None: ...
    def delete(self, key: str) -> None: ...
    def upload_link(self, key: str, content_type: str) -> UploadLink: ...


def raw_key(tenant_id: str, upload_id: str) -> str:
    return f"quarantine/{tenant_id}/{upload_id}/raw"


def clean_key(tenant_id: str, upload_id: str) -> str:
    return f"tenants/{tenant_id}/uploads/{upload_id}/clean.csv"


class LocalStorage:
    def __init__(self, root: str, api_url: str) -> None:
        self.root = Path(root)
        self.api_url = api_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("key outside storage root")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def size(self, key: str) -> int | None:
        path = self._path(key)
        return path.stat().st_size if path.exists() else None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def upload_link(self, key: str, content_type: str) -> UploadLink:
        return UploadLink(f"{self.api_url}/storage/upload/{sign_upload(key)}")

    def all_keys(self) -> list[str]:
        """Tests use this to prove what is, and is not, stored."""
        if not self.root.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())


class S3Storage:
    def __init__(self) -> None:
        import boto3

        s = get_settings()
        self.bucket = s.storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.storage_endpoint or None,
            region_name=s.storage_region,
            aws_access_key_id=s.storage_access_key,
            aws_secret_access_key=s.storage_secret_key,
        )

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256"
        )

    def get(self, key: str) -> bytes:
        body: bytes = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return body

    def size(self, key: str) -> int | None:
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except self.client.exceptions.ClientError:
            return None

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def upload_link(self, key: str, content_type: str) -> UploadLink:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=UPLOAD_LINK_SECONDS,
        )
        return UploadLink(url, headers={"Content-Type": content_type})


def sign_upload(key: str) -> str:
    s = get_settings()
    return jwt.encode(
        {"key": key, "typ": "upload", "exp": int(time.time()) + UPLOAD_LINK_SECONDS},
        s.jwt_secret,
        algorithm="HS256",
    )


def verify_upload(token: str) -> str:
    claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    if claims.get("typ") != "upload" or not str(claims.get("key", "")).startswith("quarantine/"):
        raise jwt.InvalidTokenError("not an upload token")
    return str(claims["key"])


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = (
            S3Storage() if s.storage_backend == "s3" else LocalStorage(s.storage_root, s.api_url)
        )
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
