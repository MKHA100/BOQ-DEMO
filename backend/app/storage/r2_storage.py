from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from app.core.config import settings

try:
    import boto3
    from botocore.config import Config
except Exception:  # pragma: no cover - boto3 is optional for local storage mode
    boto3 = None
    Config = None


class R2Storage:
    """Cloudflare R2 storage adapter using the S3-compatible API.

    R2 is only active in APP_MODE=production. Local mode can safely keep R2
    credentials in .env without using them.
    """

    def __init__(self) -> None:
        self.public_base_url = (settings.r2_public_base_url or "").rstrip("/") or None
        self._client = None

    @property
    def bucket(self) -> str | None:
        return settings.r2_bucket_name

    @property
    def endpoint_url(self) -> str | None:
        return settings.r2_endpoint_url

    def is_configured(self) -> bool:
        return bool(
            settings.use_r2
            and self.bucket
            and self.endpoint_url
            and settings.r2_access_key_id
            and settings.r2_secret_access_key
            and boto3 is not None
        )

    def require_configured(self) -> None:
        if self.is_configured():
            return
        if not settings.use_r2:
            raise RuntimeError("R2 storage is disabled. Set APP_MODE=production to use Cloudflare R2.")
        if boto3 is None:
            raise RuntimeError("Cloudflare R2 requires boto3/botocore to be installed.")
        missing = []
        for name, value in [
            ("R2_ENDPOINT_URL", self.endpoint_url),
            ("R2_BUCKET_NAME", self.bucket),
            ("R2_ACCESS_KEY_ID", settings.r2_access_key_id),
            ("R2_SECRET_ACCESS_KEY", settings.r2_secret_access_key),
        ]:
            if not value:
                missing.append(name)
        raise RuntimeError(f"APP_MODE=production requires Cloudflare R2 settings: {', '.join(missing)}")

    @property
    def client(self):
        self.require_configured()
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4") if Config else None,
            )
        return self._client

    def upload_file(self, source: Path, key: str, content_type: str | None = None) -> str:
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra_args)
        else:
            self.client.upload_file(str(source), self.bucket, key)
        return key

    def upload_bytes(self, content: bytes, key: str, content_type: str | None = None) -> str:
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra_args)
        else:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key

    def download_file(self, key: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))
        return destination

    def delete_prefix(self, prefix: str) -> None:
        if not self.is_configured():
            return
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})

    def delete_file(self, key: str) -> None:
        if not self.is_configured() or not key:
            return
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def object_exists(self, key: str) -> bool:
        if not self.is_configured() or not key:
            return False
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def presigned_get_url(self, key: str, expires_in: int | None = None) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in or settings.r2_presigned_url_ttl_seconds,
        )

    def public_url(self, key: str) -> str | None:
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{quote(key)}"
