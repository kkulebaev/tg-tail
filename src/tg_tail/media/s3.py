from typing import Any

import aioboto3
import structlog
from botocore.exceptions import ClientError

log = structlog.get_logger(__name__)


class S3Client:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        bucket: str,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        self._bucket = bucket
        self._session = aioboto3.Session()

    @property
    def bucket(self) -> str:
        return self._bucket

    def _client(self) -> Any:
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name=self._region,
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self._bucket)
                return
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in ("404", "NoSuchBucket", "NotFound"):
                    raise
            log.info("bucket_create", bucket=self._bucket)
            await s3.create_bucket(Bucket=self._bucket)

    async def put_object(self, key: str, data: bytes, content_type: str | None = None) -> str:
        async with self._client() as s3:
            kwargs: dict[str, Any] = {
                "Bucket": self._bucket,
                "Key": key,
                "Body": data,
            }
            if content_type:
                kwargs["ContentType"] = content_type
            await s3.put_object(**kwargs)
        return f"s3://{self._bucket}/{key}"
