# 모든 상품의 Storage 경로 확인 후 레거시 image_data 컬럼 제거

import asyncio

from sqlalchemy import text

from backend.core.database import engine


async def run() -> None:
    async with engine.begin() as connection:
        missing_image_paths = (
            await connection.execute(text("SELECT COUNT(*) FROM products WHERE image_path IS NULL"))
        ).scalar_one()
        if missing_image_paths:
            raise RuntimeError(f"image_path가 없는 상품 {missing_image_paths}건이 있어 중단했습니다.")
        await connection.execute(text("ALTER TABLE products ALTER COLUMN image_path SET NOT NULL"))
        await connection.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS image_data"))
    await engine.dispose()
    print("legacy image_data column removed")


if __name__ == "__main__":
    asyncio.run(run())
