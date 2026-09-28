# 기존 상품 이미지를 products/카테고리/최초등록일 구조로 이동하고 DB URL을 동기화

import asyncio

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from backend.core.database import async_session, engine
from backend.domain.products.models.products import Product, ProductCategory
from backend.domain.products.services.storage import product_storage


async def run() -> None:
    moved_paths: list[tuple[str, str]] = []
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Product, ProductCategory.code)
                .join(ProductCategory, Product.category_id == ProductCategory.id)
                .order_by(Product.id)
            )
        ).all()

        desired_by_source: dict[str, str] = {}
        product_updates: list[tuple[Product, str, str]] = []
        for product, category_code in rows:
            main_destination = product_storage.relocated_path(
                product.image_path,
                category_code,
                product.created_at,
                "main",
            )
            detail_html = product.detail_html
            for source_path in sorted(product_storage.paths_from_html(product.detail_html)):
                destination_path = product_storage.relocated_path(
                    source_path,
                    category_code,
                    product.created_at,
                    "detail",
                )
                existing_destination = desired_by_source.get(source_path)
                if existing_destination and existing_destination != destination_path:
                    raise RuntimeError(f"여러 상품이 서로 다른 폴더에서 같은 이미지를 참조합니다: {source_path}")
                desired_by_source[source_path] = destination_path
                detail_html = detail_html.replace(
                    product_storage.public_url(source_path),
                    product_storage.public_url(destination_path),
                )
            existing_destination = desired_by_source.get(product.image_path)
            if existing_destination and existing_destination != main_destination:
                raise RuntimeError(f"대표 이미지 경로가 다른 이미지와 중복됩니다: {product.image_path}")
            desired_by_source[product.image_path] = main_destination
            product_updates.append((product, main_destination, detail_html))

        destinations = [destination for source, destination in desired_by_source.items() if source != destination]
        if len(destinations) != len(set(destinations)):
            raise RuntimeError("이동 대상 Storage 경로가 중복되어 작업을 중단했습니다.")

        try:
            for source_path, destination_path in desired_by_source.items():
                if source_path == destination_path:
                    continue
                await product_storage.move(source_path, destination_path)
                moved_paths.append((source_path, destination_path))
            for product, main_destination, detail_html in product_updates:
                product.image_path = main_destination
                product.detail_html = detail_html
            await session.commit()
        except Exception:
            await session.rollback()
            for source_path, destination_path in reversed(moved_paths):
                await product_storage.move(destination_path, source_path, strict=False)
            raise

    orphaned_old_paths: list[str] = []
    try:
        async with engine.connect() as connection:
            orphaned_old_paths = list(
                (
                    await connection.execute(
                        text(
                            "SELECT name FROM storage.objects "
                            "WHERE bucket_id = :bucket "
                            "AND (name LIKE 'admin/%' OR name LIKE 'admins/%') ORDER BY name"
                        ),
                        {"bucket": product_storage.bucket},
                    )
                ).scalars().all()
            )
    except SQLAlchemyError:
        pass

    removed_orphans = 0
    for old_path in orphaned_old_paths:
        await product_storage.delete(old_path, strict=True)
        removed_orphans += 1

    await engine.dispose()
    print(
        f"storage paths migrated: products={len(product_updates)} "
        f"moved={len(moved_paths)} removed_old_orphans={removed_orphans}"
    )


if __name__ == "__main__":
    asyncio.run(run())
