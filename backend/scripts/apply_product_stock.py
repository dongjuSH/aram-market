# 상품 재고·주문 재고 상태(033)를 기존 DB에 적용(재실행 안전, 적용 전 상품 수와 테스트용 립밤 행을 읽기 전용으로 출력)

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

from backend.core.database import engine

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "migrations" / "033_product_stock.sql"
LOW_STOCK_PRODUCT_ID = 16
LOW_STOCK_PRODUCT_NAME = "데일리 무향 립밤 4g"


# 주석 줄을 빼고 세미콜론으로 나누되 $$ 로 감싼 DO 블록 안의 세미콜론은 문장 경계로 보지 않음
def split_statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    statements: list[str] = []
    current: list[str] = []
    in_dollar_quote = False
    index = 0
    while index < len(body):
        if body.startswith("$$", index):
            in_dollar_quote = not in_dollar_quote
            current.append("$$")
            index += 2
            continue
        char = body[index]
        if char == ";" and not in_dollar_quote:
            statements.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    statements.append("".join(current).strip())
    return [statement for statement in statements if statement]


# 적용 결과와 관계없이 연결 풀을 정리
async def run() -> int:
    try:
        return await _apply()
    finally:
        await engine.dispose()


# 테스트용 립밤 행이 예상과 다르면 재고 초기값을 잘못 채우지 않도록 적용 전에 중단(종료 코드 1)
async def _apply() -> int:
    statements = split_statements(MIGRATION_FILE.read_text(encoding="utf-8"))
    async with engine.begin() as connection:
        counts = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'active') AS active, "
                    "COUNT(*) FILTER (WHERE status = 'active' AND visible) AS visible, "
                    "COUNT(*) FILTER (WHERE status = 'deleted') AS deleted FROM products"
                )
            )
        ).mappings().one()
        print(f"products_before total={counts['total']} active={counts['active']} visible={counts['visible']} deleted={counts['deleted']}")
        has_stock = (
            await connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'stock')"
                )
            )
        ).scalar_one()
        print(f"stock_column_exists_before={str(has_stock).lower()}")
        target = (
            await connection.execute(text("SELECT id, name, status, visible FROM products WHERE id = :id"), {"id": LOW_STOCK_PRODUCT_ID})
        ).mappings().one_or_none()
        print(f"low_stock_product_before={dict(target) if target else None}")
        if not has_stock and (target is None or target["name"] != LOW_STOCK_PRODUCT_NAME):
            print("migration aborted: product 16 is not the expected lip balm")
            return 1
        for statement in statements:
            await connection.execute(text(statement))
    print("product stock migration applied")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
