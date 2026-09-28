# 실제 DB의 상품 등록 상태를 민감정보 없이 확인

import asyncio

from sqlalchemy import text

from backend.core.config import settings
from backend.core.database import engine


async def run() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SET TIME ZONE 'Asia/Seoul'"))
        database_timezone = (await connection.execute(text("SHOW TIMEZONE"))).scalar_one()
        database_now = (
            await connection.execute(
                text(
                    "SELECT CURRENT_TIMESTAMP AS absolute_now, "
                    "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul' AS korea_now"
                )
            )
        ).mappings().one()
        configured_timezones = (
            await connection.execute(
                text(
                    "SELECT COALESCE(d.datname, '*') AS database_name, "
                    "COALESCE(r.rolname, '*') AS role_name, s.setconfig "
                    "FROM pg_db_role_setting s "
                    "LEFT JOIN pg_database d ON d.oid = s.setdatabase "
                    "LEFT JOIN pg_roles r ON r.oid = s.setrole "
                    "WHERE EXISTS (SELECT 1 FROM unnest(s.setconfig) value WHERE value LIKE 'timezone=%')"
                )
            )
        ).mappings().all()
        rows = (
            await connection.execute(
                text(
                    "SELECT p.id, p.name, p.code, p.visible, p.display_order, c.name AS category, "
                    "p.price, p.image_path, p.status, p.created_at, p.updated_at, "
                    "CHAR_LENGTH(p.detail_html) AS detail_length, "
                    "((CHAR_LENGTH(p.detail_html) - CHAR_LENGTH(REPLACE(p.detail_html, '<img', ''))) / 4) "
                    "AS detail_image_count, "
                    "(SELECT COUNT(*) FROM product_relations r WHERE r.product_id = p.id) AS related_count "
                    "FROM products p JOIN product_categories c ON c.id = p.category_id "
                    "ORDER BY p.id"
                )
            )
        ).mappings().all()
        index_names = set(
            (
                await connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'products'"
                    )
                )
            ).scalars().all()
        )
        product_columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'products'"
                    )
                )
            ).scalars().all()
        )
        audit_columns = set(
            (
                await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'product_audit_logs'"
                    )
                )
            ).scalars().all()
        )
        audit_log_count = (
            await connection.execute(text("SELECT COUNT(*) FROM product_audit_logs"))
        ).scalar_one()
        legacy_image_count = 0
        if "image_data" in product_columns:
            legacy_image_count = (
                await connection.execute(text("SELECT COUNT(*) FROM products WHERE image_data IS NOT NULL"))
            ).scalar_one()
        lifecycle_error_count = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM products WHERE "
                    "(status = 'active' AND deleted_at IS NOT NULL) OR "
                    "(status = 'deleted' AND (deleted_at IS NULL OR visible = TRUE))"
                )
            )
        ).scalar_one()
        invalid_relation_count = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM product_relations r "
                    "JOIN products p ON p.id = r.product_id "
                    "JOIN products rp ON rp.id = r.related_product_id "
                    "WHERE p.status <> 'active' OR rp.status <> 'active' "
                    "OR p.category_id <> rp.category_id"
                )
            )
        ).scalar_one()
        too_many_relation_sources = (
            await connection.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "SELECT product_id FROM product_relations GROUP BY product_id HAVING COUNT(*) > 2"
                    ") invalid"
                )
            )
        ).scalar_one()
        audit_action_constraint = (
            await connection.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_product_audit_logs_action'"
                )
            )
        ).scalar_one_or_none()
        storage_path_counts = (
            await connection.execute(
                text(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE name LIKE 'products/%' AND name NOT LIKE 'products/_drafts/%') AS new_paths, "
                    "COUNT(*) FILTER (WHERE name LIKE 'admin/%' OR name LIKE 'admins/%') AS old_paths, "
                    "COUNT(*) FILTER (WHERE name LIKE 'products/_drafts/%') AS draft_paths "
                    "FROM storage.objects WHERE bucket_id = :bucket"
                ),
                {"bucket": settings.supabase_storage_bucket},
            )
        ).mappings().one()

    print(
        f"database_timezone={database_timezone} "
        f"absolute_now={database_now['absolute_now'].isoformat()} "
        f"korea_now={database_now['korea_now'].isoformat()}"
    )
    print(f"configured_timezones={[dict(item) for item in configured_timezones]}")
    print(f"products={len(rows)}")
    for row in rows:
        print(
            f"id={row['id']} status={row['status']} visible={row['visible']} "
            f"order={row['display_order']} category={row['category']} "
            f"code={row['code']} name={row['name']} price={row['price']} "
            f"storage_image={'yes' if row['image_path'] else 'no'} storage_path={row['image_path'] or '-'} "
            f"detail_length={row['detail_length']} detail_images={row['detail_image_count']} "
            f"related_count={row['related_count']} "
            f"created_at={row['created_at'].isoformat()} updated_at={row['updated_at'].isoformat()}"
        )
    print(
        "global_unique_indexes="
        f"{sorted(index_names & {'uq_products_active_code', 'uq_products_active_display_order'})}"
    )
    print(
        "redundant_admin_columns="
        f"{sorted(product_columns & {'created_by_admin_id', 'updated_by_admin_id'})}"
    )
    print(f"audit_logs={audit_log_count}")
    print(f"redundant_audit_actor_columns={sorted(audit_columns & {'actor_admin_id'})}")
    print(f"legacy_image_column_present={'image_data' in product_columns} legacy_image_rows={legacy_image_count}")
    print(f"invalid_lifecycle_rows={lifecycle_error_count}")
    print(f"invalid_relations={invalid_relation_count}")
    print(f"relation_sources_over_limit={too_many_relation_sources}")
    print(
        f"products_without_detail_image={sum(row['detail_image_count'] == 0 for row in rows)} "
        f"products_over_one_detail_image={sum(row['detail_image_count'] > 1 for row in rows)}"
    )
    print(f"audit_action_constraint={audit_action_constraint}")
    print(
        f"storage_new_paths={storage_path_counts['new_paths']} "
        f"storage_old_paths={storage_path_counts['old_paths']} "
        f"storage_draft_paths={storage_path_counts['draft_paths']}"
    )


if __name__ == "__main__":
    asyncio.run(run())
