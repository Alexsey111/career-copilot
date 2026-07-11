# app/services/storage/s3_storage_provider.py

"""S3/MinIO-провайдер хранилища (бывшая логика StorageService)."""

from __future__ import annotations

from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
import boto3

from app.core.config import get_settings
from app.services.storage.file_storage_provider import FileStorageProvider


class S3StorageProvider(FileStorageProvider):
    def __init__(self) -> None:
        settings = get_settings()
        scheme = "https" if settings.minio_secure else "http"
        endpoint_url = f"{scheme}://{settings.minio_endpoint}"

        self.bucket_name = settings.minio_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def ensure_ready(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return
        except ClientError:
            pass

        try:
            self.client.create_bucket(Bucket=self.bucket_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise

    def upload_bytes(
        self,
        *,
        storage_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        self.ensure_ready()
        extra_args: dict[str, str] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=storage_key,
            Body=content,
            **extra_args,
        )
        return storage_key

    def download_bytes(self, *, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response["Body"].read()

    def delete(self, *, storage_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_key)
        except ClientError:
            # Idempotent: молчим об ошибках удаления несуществующего объекта.
            return

    def healthcheck(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False