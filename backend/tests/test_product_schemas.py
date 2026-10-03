# 상품 이미지·관련 상품 입력 검증과 상세내용 HTML 정리 테스트

import asyncio
import base64
import os
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from backend.domain.products.schemas.products import EditorImageUploadRequest, ProductCreateRequest, ProductUpdateRequest
from backend.domain.products.models.products import Product, ProductAuditLog
from backend.domain.products.services.products import ProductService, korea_iso, sanitize_detail_html
from backend.domain.products.services.storage import ProductStorage
from pydantic import ValidationError


VALID_IMAGE = "data:image/png;base64," + base64.b64encode(b"small-image").decode()
UPLOAD_SESSION_ID = "123e4567-e89b-42d3-a456-426614174000"


# 반복 테스트용 정상 상품 입력값 생성
def product_payload(**overrides) -> dict:
    payload = {
        "visible": True,
        "display_order": 120,
        "category_id": 1,
        "name": "테스트 상품",
        "code": "TEST-001",
        "price": 10000,
        "image_data": VALID_IMAGE,
        "image_name": "test.png",
        "image_description": "테스트 이미지",
        "detail_html": "<p>상세내용</p>",
        "related_product_ids": [2, 3],
        "editor_upload_session_id": UPLOAD_SESSION_ID,
    }
    payload.update(overrides)
    return payload


class ProductSchemaTests(unittest.TestCase):
    def test_accepts_display_order_over_99_and_two_related_products(self):
        request = ProductCreateRequest(**product_payload(code="test-001"))
        self.assertEqual(request.display_order, 120)
        self.assertEqual(request.related_product_ids, [2, 3])
        self.assertEqual(request.code, "TEST-001")

    def test_price_must_fit_supported_card_payment_range(self):
        for price in (0, 99, 2_147_483_648):
            with self.subTest(price=price), self.assertRaises(ValidationError):
                ProductCreateRequest(**product_payload(price=price))

    def test_rejects_duplicate_or_more_than_two_related_products(self):
        with self.assertRaises(ValidationError):
            ProductCreateRequest(**product_payload(related_product_ids=[2, 2]))
        with self.assertRaises(ValidationError):
            ProductCreateRequest(**product_payload(related_product_ids=[1, 2, 3]))

    def test_rejects_disallowed_image_type(self):
        invalid_image = "data:image/svg+xml;base64," + base64.b64encode(b"<svg></svg>").decode()
        with self.assertRaises(ValidationError):
            ProductCreateRequest(**product_payload(image_data=invalid_image))

    def test_update_can_keep_existing_storage_image(self):
        request = ProductUpdateRequest(**product_payload(image_data=None))
        self.assertIsNone(request.image_data)

    def test_editor_image_uses_same_validation(self):
        request = EditorImageUploadRequest(
            image_data=VALID_IMAGE,
            category_id=1,
            upload_session_id=UPLOAD_SESSION_ID,
        )
        self.assertEqual(request.image_data, VALID_IMAGE)

    def test_storage_path_uses_category_and_korea_registration_date(self):
        registered_at = datetime(2026, 9, 27, 15, 30, tzinfo=timezone.utc)
        path = ProductStorage.new_path("Food", registered_at, "main", ".JPG")
        self.assertRegex(path, r"^products/food/2026-09-28/main-[a-f0-9]{32}\.jpg$")

    def test_sanitizes_script_and_unsafe_link(self):
        sanitized = sanitize_detail_html('<p onclick="bad()">안전<script>alert(1)</script><a href="javascript:bad()">링크</a></p>')
        self.assertNotIn("script", sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertNotIn("javascript:", sanitized)
        self.assertIn("안전", sanitized)

    def test_keeps_only_own_storage_images(self):
        from backend.domain.products.services.storage import product_storage

        with patch.object(product_storage, "base_url", "https://example.supabase.co"), patch.object(product_storage, "bucket", "product-images"):
            own = "https://example.supabase.co/storage/v1/object/public/product-images/products/food/a.png"
            sanitized = sanitize_detail_html(
                f'<img src="{own}" alt="상품"><img src="javascript:bad()">'
                '<img src="https://evil.example/track.png">'
                '<img src="https://example.supabase.co/storage/v1/object/public/other-bucket/a.png">'
                '<img src="https://example.supabase.co/storage/v1/object/public/product-images/../other/a.png">'
            )
        self.assertIn(own, sanitized)
        self.assertEqual(sanitized.count("<img"), 1)
        self.assertNotIn("javascript:", sanitized)

    def test_storage_decoder_returns_original_image_bytes(self):
        content, mime_type = ProductStorage.decode_data_url(VALID_IMAGE)
        self.assertEqual(content, b"small-image")
        self.assertEqual(mime_type, "image/png")

    def test_storage_extracts_managed_editor_image_paths(self):
        storage = ProductStorage()
        storage.base_url = "https://example.supabase.co"
        storage.bucket = "product-images"
        image_url = storage.public_url("products/food/2026-09-28/detail-image.png")
        self.assertEqual(
            storage.paths_from_html(f'<p><img src="{image_url}"></p>'),
            {"products/food/2026-09-28/detail-image.png"},
        )

    def test_storage_draft_path_is_scoped_to_upload_session(self):
        self.assertEqual(
            ProductStorage.draft_prefix(UPLOAD_SESSION_ID),
            f"products/_drafts/{UPLOAD_SESSION_ID}",
        )

    def test_storage_creates_bucket_when_supabase_returns_400_not_found(self):
        storage = ProductStorage()
        storage.base_url = "https://example.supabase.co"
        storage.api_key = "test-service-role-key"
        storage.bucket = "product-images"
        methods = []

        def fake_request(method, path, body, content_type):
            methods.append(method)
            if method == "GET":
                raise HTTPError(path, 400, "Bad Request", {}, BytesIO(b'{"message":"Bucket not found"}'))
            return b""

        storage._request = fake_request
        asyncio.run(storage.ensure_bucket())
        self.assertEqual(methods, ["GET", "POST"])

    def test_storage_recovers_configuration_after_env_file_change(self):
        storage = ProductStorage()
        storage.base_url = ""
        storage.api_key = ""
        with patch("backend.domain.products.services.storage.load_dotenv"), patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "https://refreshed.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "refreshed-service-key",
                "SUPABASE_STORAGE_BUCKET": "refreshed-products",
            },
        ):
            storage._require_configuration()
        self.assertEqual(storage.base_url, "https://refreshed.supabase.co")
        self.assertEqual(storage.api_key, "refreshed-service-key")
        self.assertEqual(storage.bucket, "refreshed-products")

    def test_global_catalog_has_no_redundant_admin_columns_and_keeps_active_unique_indexes(self):
        self.assertIn("status", Product.__table__.columns)
        self.assertIn("deleted_at", Product.__table__.columns)
        self.assertNotIn("created_by_admin_id", Product.__table__.columns)
        self.assertNotIn("updated_by_admin_id", Product.__table__.columns)
        self.assertNotIn("actor_admin_id", ProductAuditLog.__table__.columns)
        self.assertNotIn("user_id", Product.__table__.columns)
        self.assertNotIn("image_data", Product.__table__.columns)
        self.assertFalse(Product.__table__.columns.image_path.nullable)
        index_names = {index.name for index in Product.__table__.indexes}
        self.assertIn("uq_products_active_code", index_names)
        self.assertIn("uq_products_active_display_order", index_names)

    def test_product_time_is_serialized_with_korea_offset(self):
        value = datetime(2026, 9, 27, 4, 15, 49, tzinfo=timezone.utc)
        self.assertEqual(korea_iso(value), "2026-09-27T13:15:49+09:00")

    def test_restore_audit_action_is_allowed(self):
        check_sql = " ".join(
            str(constraint.sqltext)
            for constraint in ProductAuditLog.__table__.constraints
            if getattr(constraint, "name", None) == "ck_product_audit_logs_action"
        )
        self.assertIn("restored", check_sql)

    def test_restore_uses_only_valid_integer_relation_ids_from_audit(self):
        changes = {"related_product_ids": {"before": [1, "2", -3, 4], "after": []}}
        self.assertEqual(ProductService._audit_before_ids(changes, "related_product_ids"), [1, 4])


if __name__ == "__main__":
    unittest.main()
