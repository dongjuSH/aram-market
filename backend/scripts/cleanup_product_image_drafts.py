# 비정상 종료로 남은 상품 에디터 임시 이미지를 보관시간 기준으로 정리

import argparse
import asyncio

from sqlalchemy import text

from backend.core.database import engine
from backend.domain.products.services.storage import product_storage


# Storage 메타데이터에서 만료된 임시 객체를 조회하고 API를 통해 삭제
async def run(retention_hours: int) -> None:
    if retention_hours < 1:
        raise ValueError("임시 이미지 보관시간은 1시간 이상이어야 합니다.")
    async with engine.connect() as connection:
        expired_paths = list(
            (
                await connection.execute(
                    text(
                        "SELECT name FROM storage.objects "
                        "WHERE bucket_id = :bucket "
                        "AND name LIKE 'products/_drafts/%' "
                        "AND created_at < now() - make_interval(hours => :retention_hours) "
                        "ORDER BY created_at"
                    ),
                    {
                        "bucket": product_storage.bucket,
                        "retention_hours": retention_hours,
                    },
                )
            ).scalars().all()
        )
    for path in expired_paths:
        await product_storage.delete(path, strict=True)
    await engine.dispose()
    print(f"expired product image drafts removed: count={len(expired_paths)} retention_hours={retention_hours}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retention-hours", type=int, default=24)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.retention_hours))
