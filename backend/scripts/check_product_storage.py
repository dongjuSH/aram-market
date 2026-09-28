# 비밀값을 출력하지 않고 상품 Storage 버킷의 생성·업로드·삭제 연결 확인

import asyncio
import json
from datetime import datetime
from urllib.error import HTTPError
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.domain.products.services.storage import product_storage


TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def run() -> None:
    if not product_storage.is_configured:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 비어 있습니다.")

    try:
        await product_storage.ensure_bucket()
        uploaded = await product_storage.upload_data_url(
            "connection-check",
            datetime.now(ZoneInfo("Asia/Seoul")),
            TINY_PNG_DATA_URL,
            "check",
        )
        await product_storage.delete(uploaded.path, strict=True)
        draft_session_id = str(uuid4())
        draft = await product_storage.upload_editor_draft(draft_session_id, TINY_PNG_DATA_URL)
        draft_paths = await product_storage._list_paths(product_storage.draft_prefix(draft_session_id))
        if draft.path not in draft_paths:
            raise RuntimeError("임시 상세 이미지가 세션 폴더 목록에서 확인되지 않습니다.")
        await product_storage.delete_draft(draft_session_id, strict=True)
        if await product_storage._list_paths(product_storage.draft_prefix(draft_session_id)):
            raise RuntimeError("임시 상세 이미지 정리 후 파일이 남아 있습니다.")
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode()).get("message", "응답 메시지 없음")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = "응답 메시지 확인 불가"
        finally:
            error.close()
        raise RuntimeError(f"Storage API 응답 실패: HTTP {error.code}, {detail}") from error
    print(f"storage connection verified: bucket={product_storage.bucket}, upload=ok, delete=ok, draft_cleanup=ok")


if __name__ == "__main__":
    asyncio.run(run())
