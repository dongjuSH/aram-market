# Supabase Storage 상품 이미지 업로드·삭제 및 공개 URL 생성

import asyncio
import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import status
from dotenv import load_dotenv

from backend.core.config import ENV_FILE, settings
from backend.domain.admins.services.admins import api_error


ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif"}
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
STORAGE_SEGMENT_PATTERN = re.compile(r"[^a-z0-9_-]+")
STORAGE_ROOT = "products"
DRAFT_FOLDER = "_drafts"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredImage:
    path: str
    public_url: str


# 서버 자격증명을 사용하는 Supabase 공개 상품 이미지 버킷 클라이언트
class ProductStorage:
    def __init__(self) -> None:
        self.base_url = settings.supabase_url.rstrip("/")
        self.api_key = settings.supabase_service_role_key.strip()
        self.bucket = settings.supabase_storage_bucket.strip() or "product-images"

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    # 실행 중 .env가 갱신된 개발 환경에서도 서버 재기동 전 한 번 설정을 복구
    def _refresh_configuration(self) -> None:
        load_dotenv(dotenv_path=ENV_FILE, override=True)
        self.base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.api_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "product-images").strip() or "product-images"

    # Base64 data URL 검증 및 원본 바이트·MIME 분리
    @staticmethod
    def decode_data_url(value: str) -> tuple[bytes, str]:
        try:
            header, encoded = value.split(",", 1)
            mime_type = header.removeprefix("data:").removesuffix(";base64").lower()
            if mime_type not in ALLOWED_IMAGE_TYPES or not header.endswith(";base64"):
                raise ValueError
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_IMAGE", "이미지 데이터가 올바르지 않습니다.") from error
        if not content or len(content) > 5 * 1024 * 1024:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_IMAGE_SIZE", "이미지는 5MB 이하만 등록할 수 있습니다.")
        return content, mime_type

    # 서버 시작 시 공개 이미지 버킷이 없으면 생성
    async def ensure_bucket(self) -> None:
        if not self.is_configured:
            self._refresh_configuration()
        if not self.is_configured:
            return
        bucket_options = {
            "public": True,
            "file_size_limit": 5 * 1024 * 1024,
            "allowed_mime_types": list(ALLOWED_IMAGE_TYPES),
        }
        create_payload = json.dumps({
            "id": self.bucket,
            "name": self.bucket,
            **bucket_options,
        }).encode()
        update_payload = json.dumps(bucket_options).encode()
        try:
            await asyncio.to_thread(self._request, "GET", f"/storage/v1/bucket/{quote(self.bucket)}", None, "application/json")
        except HTTPError as error:
            try:
                error_body = error.read().decode(errors="replace")
            finally:
                error.close()
            bucket_not_found = error.code == 404 or (error.code == 400 and "Bucket not found" in error_body)
            if not bucket_not_found:
                raise
            await asyncio.to_thread(self._request, "POST", "/storage/v1/bucket", create_payload, "application/json")
            return
        await asyncio.to_thread(self._request, "PUT", f"/storage/v1/bucket/{quote(self.bucket)}", update_payload, "application/json")

    # 카테고리·최초 등록일 폴더에 종류가 구분된 무작위 파일명으로 이미지 업로드
    async def upload_data_url(
        self,
        category_code: str,
        registered_at: datetime,
        data_url: str,
        image_kind: str = "main",
    ) -> StoredImage:
        self._require_configuration()
        content, mime_type = self.decode_data_url(data_url)
        extension = ALLOWED_IMAGE_TYPES[mime_type]
        path = self.new_path(category_code, registered_at, image_kind, extension)
        encoded_path = quote(path, safe="/")
        try:
            await asyncio.to_thread(self._request, "POST", f"/storage/v1/object/{quote(self.bucket)}/{encoded_path}", content, mime_type)
        except (HTTPError, URLError) as error:
            raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "STORAGE_UPLOAD_FAILED", "이미지 저장소에 업로드하지 못했습니다.") from error
        return StoredImage(path=path, public_url=self.public_url(path))

    # 상품 저장 전 에디터 이미지는 임시 세션 폴더에 격리하여 취소 시 정리 가능하게 업로드
    async def upload_editor_draft(self, upload_session_id: str, data_url: str) -> StoredImage:
        self._require_configuration()
        content, mime_type = self.decode_data_url(data_url)
        extension = ALLOWED_IMAGE_TYPES[mime_type]
        path = f"{self.draft_prefix(upload_session_id)}/detail-{uuid4().hex}{extension}"
        encoded_path = quote(path, safe="/")
        try:
            await asyncio.to_thread(
                self._request,
                "POST",
                f"/storage/v1/object/{quote(self.bucket)}/{encoded_path}",
                content,
                mime_type,
            )
        except (HTTPError, URLError) as error:
            raise api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_UPLOAD_FAILED",
                "이미지 저장소에 업로드하지 못했습니다.",
            ) from error
        return StoredImage(path=path, public_url=self.public_url(path))

    # 동일 버킷 내 객체를 새 폴더로 이동
    async def move(self, source_path: str, destination_path: str, *, strict: bool = True) -> None:
        if source_path == destination_path:
            return
        self._require_configuration()
        payload = json.dumps({
            "bucketId": self.bucket,
            "sourceKey": source_path,
            "destinationKey": destination_path,
        }).encode()
        try:
            await asyncio.to_thread(self._request, "POST", "/storage/v1/object/move", payload, "application/json")
        except (HTTPError, URLError) as error:
            if strict:
                raise api_error(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "STORAGE_MOVE_FAILED",
                    "이미지 저장 경로를 변경하지 못했습니다.",
                ) from error

    # products/카테고리/최초등록일/이미지종류-무작위파일명 경로 생성
    @classmethod
    def new_path(
        cls,
        category_code: str,
        registered_at: datetime,
        image_kind: str,
        extension: str,
    ) -> str:
        folder = cls.folder_prefix(category_code, registered_at)
        kind = cls._safe_segment(image_kind)
        return f"{folder}/{kind}-{uuid4().hex}{extension.lower()}"

    # 기존 파일명을 보존하면서 목표 카테고리·등록일 폴더 경로 생성
    @classmethod
    def relocated_path(
        cls,
        source_path: str,
        category_code: str,
        registered_at: datetime,
        image_kind: str,
    ) -> str:
        folder = cls.folder_prefix(category_code, registered_at)
        kind = cls._safe_segment(image_kind)
        filename = PurePosixPath(source_path).name
        if not filename.startswith(f"{kind}-"):
            filename = f"{kind}-{filename}"
        return f"{folder}/{filename}"

    # 카테고리 코드와 한국 기준 최초 등록일로 공통 폴더 경로 생성
    @classmethod
    def folder_prefix(cls, category_code: str, registered_at: datetime) -> str:
        category = cls._safe_segment(category_code)
        localized = registered_at.replace(tzinfo=KOREA_TIMEZONE) if registered_at.tzinfo is None else registered_at.astimezone(KOREA_TIMEZONE)
        return f"{STORAGE_ROOT}/{category}/{localized.date().isoformat()}"

    # UUID 검증을 마친 업로드 세션의 임시 폴더 경로
    @staticmethod
    def draft_prefix(upload_session_id: str) -> str:
        return f"{STORAGE_ROOT}/{DRAFT_FOLDER}/{upload_session_id}"

    # 정식 상품 이미지와 임시 편집 이미지를 구분
    @staticmethod
    def is_draft_path(path: str) -> bool:
        return path.startswith(f"{STORAGE_ROOT}/{DRAFT_FOLDER}/")

    @staticmethod
    def _safe_segment(value: str) -> str:
        normalized = STORAGE_SEGMENT_PATTERN.sub("-", value.strip().lower()).strip("-_")
        if not normalized:
            raise ValueError("Storage 폴더 이름으로 사용할 수 없는 값입니다.")
        return normalized

    # DB 반영 완료 후 교체·삭제된 이미지 제거
    async def delete(self, path: str | None, *, strict: bool = False) -> None:
        if not path or not self.is_configured:
            return
        payload = json.dumps({"prefixes": [path]}).encode()
        last_error: HTTPError | URLError | None = None
        for attempt in range(2):
            try:
                await asyncio.to_thread(self._request, "DELETE", f"/storage/v1/object/{quote(self.bucket)}", payload, "application/json")
                return
            except (HTTPError, URLError) as error:
                last_error = error
                if attempt == 0:
                    await asyncio.sleep(0.25)
        # DB 작업은 완료되었으므로 일반 수정 응답은 유지하되 재시도 대상 경로를 로그에 남김
        if strict and last_error:
            raise last_error
        logger.warning("storage object cleanup failed path=%s", path)

    # 임시 세션 폴더의 직접 하위 파일을 조회해 일괄 삭제
    async def delete_draft(self, upload_session_id: str, *, strict: bool = False) -> None:
        if not self.is_configured:
            return
        prefix = self.draft_prefix(upload_session_id)
        try:
            paths = await self._list_paths(prefix)
        except (HTTPError, URLError, ValueError, json.JSONDecodeError) as error:
            if strict:
                raise error
            logger.warning("storage draft listing failed prefix=%s", prefix)
            return
        for path in paths:
            await self.delete(path, strict=strict)

    # Supabase list API는 prefix 기준 파일명만 반환하므로 전체 객체 경로로 복원
    async def _list_paths(self, prefix: str) -> list[str]:
        payload = json.dumps({
            "prefix": prefix,
            "limit": 1000,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        }).encode()
        response = await asyncio.to_thread(
            self._request,
            "POST",
            f"/storage/v1/object/list/{quote(self.bucket)}",
            payload,
            "application/json",
        )
        items = json.loads(response.decode())
        if not isinstance(items, list):
            raise ValueError("Storage 파일 목록 응답이 올바르지 않습니다.")
        return [f"{prefix}/{item['name']}" for item in items if isinstance(item, dict) and item.get("name")]

    # 공개 버킷의 CDN URL 생성
    def public_url(self, path: str | None) -> str:
        if path is None or not self.base_url:
            return ""
        return f"{self.base_url}/storage/v1/object/public/{quote(self.bucket)}/{quote(path, safe='/')}"

    # 저장된 상세 HTML에서 현재 버킷에 속한 이미지 경로 추출
    def paths_from_html(self, value: str) -> set[str]:
        public_prefix = self.public_url("")
        if not public_prefix:
            return set()
        pattern = re.compile(rf'src=["\']{re.escape(public_prefix)}([^"\']+)["\']')
        return {unquote(matched) for matched in pattern.findall(value)}

    # Supabase Storage 공통 인증 요청
    def _request(self, method: str, path: str, body: bytes | None, content_type: str) -> bytes:
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
                "x-upsert": "false",
            },
        )
        with urlopen(request, timeout=20) as response:
            return response.read()

    # 스토리지 미설정 상태에서 DB에 이미지 데이터가 저장되는 것을 차단
    def _require_configuration(self) -> None:
        if not self.is_configured:
            self._refresh_configuration()
        if not self.is_configured:
            raise api_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_NOT_CONFIGURED",
                "상품 이미지 저장소가 설정되지 않았습니다. 서버 환경변수를 확인해 주세요.",
            )


product_storage = ProductStorage()
