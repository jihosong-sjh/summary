import mimetypes
from dataclasses import dataclass
from pathlib import Path

import boto3

from app.core.config import get_settings
from app.schemas.recording import UploadUrlResponse


@dataclass
class StorageService:
    expires_in: int = 900

    def _client(self, endpoint_url: str | None = None):
        settings = get_settings()
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url if endpoint_url is not None else settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def build_recording_key(self, user_id: str, recording_id: str, file_name: str | None = None) -> str:
        extension = ".m4a"
        if file_name:
            guessed = Path(file_name).suffix
            if guessed:
                extension = guessed.lower()
        return f"users/{user_id}/recordings/{recording_id}/audio{extension}"

    def create_presigned_put_url(self, object_key: str, content_type: str) -> UploadUrlResponse:
        settings = get_settings()
        presign_endpoint = settings.s3_public_base_url or settings.s3_endpoint_url
        url = self._client(endpoint_url=presign_endpoint).generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": settings.s3_bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=self.expires_in,
        )
        return UploadUrlResponse(upload_url=url, object_key=object_key, expires_in=self.expires_in)

    def download_to_file(self, object_key: str, destination: Path) -> None:
        settings = get_settings()
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._client().download_file(settings.s3_bucket, object_key, str(destination))

    def delete_object(self, object_key: str) -> None:
        settings = get_settings()
        self._client().delete_object(Bucket=settings.s3_bucket, Key=object_key)

    @staticmethod
    def content_type_for(path: Path) -> str:
        return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
