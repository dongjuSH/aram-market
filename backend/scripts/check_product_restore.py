# 실제 삭제 상품으로 복원 로직을 실행한 뒤 트랜잭션을 롤백하는 비파괴 점검

import asyncio

from sqlalchemy import select, text

from backend.core.database import async_session, engine
from backend.domain.products.models.products import Product
from backend.domain.products.services.products import ProductService


class RollbackOnlySession:
    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)

    async def commit(self) -> None:
        await self.session.flush()


async def run() -> None:
    async with async_session() as session:
        await session.execute(text("SET TIME ZONE 'Asia/Seoul'"))
        product_id = (
            await session.execute(
                select(Product.id).where(Product.status == "deleted").order_by(Product.id).limit(1)
            )
        ).scalar_one_or_none()
        if product_id is None:
            print("deleted product not found; restore dry-run skipped")
            return

        service = ProductService(RollbackOnlySession(session))
        result = await service.restore_product(product_id)
        restored = await session.get(Product, product_id)
        print(
            f"dry_run_product_id={product_id} status={restored.status} visible={restored.visible} "
            f"display_order={restored.display_order} message={result['message']}"
        )
        await session.rollback()

    async with async_session() as verification_session:
        status_after_rollback = (
            await verification_session.execute(select(Product.status).where(Product.id == product_id))
        ).scalar_one()
        print(f"status_after_rollback={status_after_rollback}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
