# 상품 재고·주문 재고 상태(033) 적용 여부를 확인하는 읽기 전용 스크립트(누락·음수 재고가 있으면 종료 코드 1)

import asyncio
import sys

from sqlalchemy import text

from backend.core.database import engine

LOW_STOCK_PRODUCT_ID = 16
# (테이블, 컬럼) → 기대 정의: 형식·NULL 허용·기본값(정규화한 문자열)·최대 길이
EXPECTED_COLUMNS = {
    ("products", "stock"): {"data_type": "integer", "is_nullable": "NO", "column_default": "0", "character_maximum_length": None},
    ("orders", "stock_status"): {
        "data_type": "character varying",
        "is_nullable": "YES",
        "column_default": None,
        "character_maximum_length": 20,
    },
}
# 제약 이름 → pg_get_constraintdef 결과에 모두 들어 있어야 하는 조각
EXPECTED_CHECKS = {
    "ck_products_stock_nonnegative": ("stock >= 0",),
    "ck_orders_stock_status": ("stock_status IS NULL", "'reserved'", "'released'", "'shortage'"),
}


# 기본값 표기 정규화: PostgreSQL은 '0'::integer 같은 형식으로 돌려줄 수 있음
def normalize_default(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split("::")[0].strip("'() ")


# 컬럼 정의(형식·NULL·기본값·길이)와 CHECK 정의를 기대값과 비교해 (잘못된 컬럼, 없는 제약, 잘못된 제약) 반환(없는 컬럼은 따로 판정)
def definition_problems(definitions: dict, constraints: dict) -> tuple[list[str], list[str], list[str]]:
    wrong_columns = []
    for key, expected in EXPECTED_COLUMNS.items():
        row = definitions.get(key)
        if row is None:
            continue
        actual = {
            "data_type": row["data_type"],
            "is_nullable": row["is_nullable"],
            "column_default": normalize_default(row["column_default"]),
            "character_maximum_length": row["character_maximum_length"],
        }
        if actual != expected:
            wrong_columns.append(f"{key[0]}.{key[1]}:{actual}")
    missing_constraints = [name for name in EXPECTED_CHECKS if name not in constraints]
    wrong_checks = [
        name for name, parts in EXPECTED_CHECKS.items() if name in constraints and not all(part in constraints[name] for part in parts)
    ]
    return wrong_columns, missing_constraints, wrong_checks


# 컬럼 정의·CHECK 정의가 기대와 같고 음수 재고가 없으면 종료 코드 0(컬럼이 없으면 not_checked)
async def run() -> int:
    async with engine.connect() as connection:
        product_columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'products'")
                )
            ).scalars()
        )
        order_columns = set(
            (
                await connection.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'orders'")
                )
            ).scalars()
        )
        constraints = dict(
            (
                await connection.execute(
                    text(
                        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'c' "
                        "AND conrelid IN ('public.products'::regclass, 'public.orders'::regclass)"
                    )
                )
            ).all()
        )
        definitions = {
            (row["table_name"], row["column_name"]): row
            for row in (
                await connection.execute(
                    text(
                        "SELECT table_name, column_name, data_type, is_nullable, column_default, character_maximum_length "
                        "FROM information_schema.columns WHERE table_schema = 'public' "
                        "AND ((table_name = 'products' AND column_name = 'stock') OR (table_name = 'orders' AND column_name = 'stock_status'))"
                    )
                )
            ).mappings()
        }
        stock_summary = None
        low_stock_row = None
        stock_status_counts = []
        if "stock" in product_columns:
            stock_summary = (
                await connection.execute(
                    text(
                        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE stock < 0) AS negative, "
                        "COUNT(*) FILTER (WHERE stock = 0) AS sold_out, MIN(stock) AS min_stock, MAX(stock) AS max_stock FROM products"
                    )
                )
            ).mappings().one()
            low_stock_row = (
                await connection.execute(text("SELECT id, name, stock FROM products WHERE id = :id"), {"id": LOW_STOCK_PRODUCT_ID})
            ).mappings().one_or_none()
        if "stock_status" in order_columns:
            stock_status_counts = (
                await connection.execute(text("SELECT COALESCE(stock_status, 'none'), COUNT(*) FROM orders GROUP BY 1 ORDER BY 1"))
            ).all()
    await engine.dispose()

    has_columns = "stock" in product_columns and "stock_status" in order_columns
    wrong_columns, missing_constraints, wrong_checks = definition_problems(definitions, constraints)
    print(f"stock_columns_ok={str(has_columns).lower()}")
    print("wrong_column_definitions=" + (" | ".join(wrong_columns) or "none"))
    print("missing_constraints=" + (",".join(missing_constraints) or "none"))
    print("wrong_check_definitions=" + (",".join(wrong_checks) or "none"))
    if stock_summary is None:
        print("stock_summary=not_checked")
    else:
        print(
            f"stock_summary total={stock_summary['total']} negative={stock_summary['negative']} sold_out={stock_summary['sold_out']} "
            f"min={stock_summary['min_stock']} max={stock_summary['max_stock']}"
        )
        print(f"low_stock_product={dict(low_stock_row) if low_stock_row else None}")
    print("orders_by_stock_status=" + (", ".join(f"{name}:{count}" for name, count in stock_status_counts) or "not_checked"))
    ok = has_columns and not wrong_columns and not missing_constraints and not wrong_checks and stock_summary is not None and stock_summary["negative"] == 0
    print("product_stock_ok=" + str(ok).lower())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
