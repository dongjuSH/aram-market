# 전역 상품 조회·등록·수정·삭제 및 관련 상품 검증 비즈니스 로직

from datetime import datetime
from html import escape
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from fastapi import Depends, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.products.models.products import Product, ProductAuditLog, ProductCategory, ProductRelation
from backend.domain.products.schemas.products import EditorImageUploadRequest, ProductCreateRequest, ProductUpdateRequest, ProductWriteRequest
from backend.domain.products.services.storage import product_storage
from backend.domain.admins.services.admins import api_error


ALLOWED_DETAIL_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "a", "img", "code", "pre", "hr"}
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def korea_now() -> datetime:
    return datetime.now(KOREA_TIMEZONE)


def korea_iso(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=KOREA_TIMEZONE).isoformat()
    return value.astimezone(KOREA_TIMEZONE).isoformat()


# 상세내용에서 실행 가능한 태그·속성을 제거하는 제한형 HTML 정리기
class DetailHtmlSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_DETAIL_TAGS:
            return
        safe_attrs = ""
        if tag == "a":
            href = next((value for name, value in attrs if name == "href"), "") or ""
            if href.startswith(("https://", "http://", "mailto:")):
                safe_attrs = f' href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer"'
        if tag == "img":
            source = next((value for name, value in attrs if name == "src"), "") or ""
            alternative = next((value for name, value in attrs if name == "alt"), "") or ""
            if not source.startswith(("https://", "http://")):
                return
            safe_attrs = f' src="{escape(source, quote=True)}" alt="{escape(alternative, quote=True)}"'
        self.parts.append(f"<{tag}{safe_attrs}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in ALLOWED_DETAIL_TAGS and tag not in {"br", "img", "hr"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))

    def get_html(self) -> str:
        return "".join(self.parts).strip()


# 편집기 HTML을 허용 목록 기준으로 정리
def sanitize_detail_html(value: str) -> str:
    sanitizer = DetailHtmlSanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return sanitizer.get_html()


# 상품 목록과 편집 화면용 전역 카탈로그 데이터 처리
class ProductService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    # 활성 카테고리 목록 반환
    async def list_categories(self) -> dict:
        query = select(ProductCategory).where(ProductCategory.is_active.is_(True)).order_by(ProductCategory.sort_order, ProductCategory.id)
        categories = (await self.db.execute(query)).scalars().all()
        return {"categories": [{"id": item.id, "code": item.code, "name": item.name} for item in categories]}

    # 전체 활성 상품의 상품명 또는 상품코드 검색과 페이지 단위 목록 반환
    async def list_products(self, keyword: str, page: int, page_size: int, product_status: str = "active") -> dict:
        filters = [Product.status == product_status]
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            filters.append(or_(Product.name.ilike(pattern), Product.code.ilike(pattern)))

        total = (await self.db.execute(select(func.count(Product.id)).where(*filters))).scalar_one()
        query = (
            select(Product, ProductCategory.name)
            .join(ProductCategory, Product.category_id == ProductCategory.id)
            .where(*filters)
            .order_by(Product.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(query)).all()
        items = [self._list_item(product, category_name) for product, category_name in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    # 고객 화면 전용 노출 상품 목록 반환
    async def list_catalog_products(
        self,
        keyword: str,
        category_id: int | None,
        page: int,
        page_size: int,
    ) -> dict:
        filters = [
            Product.status == "active",
            Product.visible.is_(True),
            ProductCategory.is_active.is_(True),
        ]
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        normalized_keyword = keyword.strip()
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            filters.append(or_(Product.name.ilike(pattern), Product.code.ilike(pattern)))

        base_query = select(Product).join(ProductCategory, Product.category_id == ProductCategory.id).where(*filters)
        total = (await self.db.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        query = (
            select(Product, ProductCategory.name)
            .join(ProductCategory, Product.category_id == ProductCategory.id)
            .where(*filters)
            .order_by(Product.display_order, Product.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(query)).all()
        return {
            "items": [self._catalog_list_item(product, category_name) for product, category_name in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # 고객 화면 전용 노출 상품 상세와 노출 가능한 관련 상품 반환
    async def get_catalog_product(self, product_id: int) -> dict:
        query = (
            select(Product, ProductCategory.name)
            .join(ProductCategory, Product.category_id == ProductCategory.id)
            .where(
                Product.id == product_id,
                Product.status == "active",
                Product.visible.is_(True),
                ProductCategory.is_active.is_(True),
            )
        )
        row = (await self.db.execute(query)).one_or_none()
        if not row:
            raise api_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND", "상품을 찾을 수 없습니다.")
        product, category_name = row
        related_ids = await self._relation_ids(product.id)
        related_items: list[dict] = []
        if related_ids:
            related_query = (
                select(Product, ProductCategory.name)
                .join(ProductCategory, Product.category_id == ProductCategory.id)
                .where(
                    Product.id.in_(related_ids),
                    Product.status == "active",
                    Product.visible.is_(True),
                    ProductCategory.is_active.is_(True),
                )
                .order_by(Product.display_order, Product.id)
            )
            related_rows = (await self.db.execute(related_query)).all()
            related_items = [self._catalog_list_item(item, category) for item, category in related_rows]
        return {"product": self._catalog_detail_item(product, category_name, related_items)}

    # 등록·수정 화면에서 선택한 카테고리의 관련 상품 후보 반환
    async def related_candidates(self, category_id: int, excluded_id: int | None = None) -> dict:
        return {"items": await self._related_candidates(category_id, excluded_id)}

    # 단일 상품과 같은 카테고리의 관련 상품 후보 반환
    async def get_product(self, product_id: int) -> dict:
        product = await self._get_product(product_id)
        relation_query = select(ProductRelation.related_product_id).where(ProductRelation.product_id == product.id)
        related_ids = list((await self.db.execute(relation_query)).scalars().all())
        candidates = await self._related_candidates(product.category_id, product.id)
        return {
            "product": self._detail_item(product, related_ids),
            "related_candidates": candidates,
        }

    # 전역 코드·노출순서 중복 및 관련 상품 조건 확인 후 신규 상품 저장
    async def create_product(self, request: ProductCreateRequest) -> dict:
        await self._validate_write_request(request, None)
        now = korea_now()
        category = await self.db.get(ProductCategory, request.category_id)
        detail_html, moved_editor_paths = await self._relocate_editor_images(
            sanitize_detail_html(request.detail_html),
            category.code,
            now,
            request.editor_upload_session_id,
        )
        try:
            stored_image = await product_storage.upload_data_url(
                category.code,
                now,
                request.image_data or "",
                "main",
            )
        except Exception:
            await self._rollback_storage_moves(moved_editor_paths)
            raise
        product = Product(
            visible=request.visible,
            display_order=request.display_order,
            category_id=request.category_id,
            name=request.name,
            code=request.code,
            price=request.price,
            image_path=stored_image.path,
            image_name=request.image_name,
            image_description=request.image_description,
            detail_html=detail_html,
            created_at=now,
            updated_at=now,
        )
        self.db.add(product)
        try:
            await self.db.flush()
            await self._replace_relations(product.id, request.related_product_ids)
            self.db.add(
                ProductAuditLog(
                    product_id=product.id,
                    action="created",
                    changes={"after": self._audit_snapshot(product, request.related_product_ids)},
                )
            )
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            await product_storage.delete(stored_image.path)
            await self._rollback_storage_moves(moved_editor_paths)
            await self._raise_write_conflict(request, None, error)
        except Exception:
            await self.db.rollback()
            await product_storage.delete(stored_image.path)
            await self._rollback_storage_moves(moved_editor_paths)
            raise
        if request.editor_upload_session_id:
            await product_storage.delete_draft(request.editor_upload_session_id)
        return {"message": "상품이 등록되었습니다.", "product_id": product.id}

    # 생성일은 유지하고 수정일과 입력 필드 갱신
    async def update_product(self, product_id: int, request: ProductUpdateRequest) -> dict:
        product = await self._get_product(product_id)
        await self._validate_write_request(request, product.id)
        category = await self.db.get(ProductCategory, request.category_id)
        previous_related_ids = await self._relation_ids(product.id)
        before_snapshot = self._audit_snapshot(product, previous_related_ids)
        previous_image_path = product.image_path
        previous_editor_paths = product_storage.paths_from_html(product.detail_html)
        stored_image = None
        moved_storage_paths: list[tuple[str, str]] = []
        try:
            if request.image_data:
                stored_image = await product_storage.upload_data_url(
                    category.code,
                    product.created_at,
                    request.image_data,
                    "main",
                )
            elif product.image_path:
                relocated_main_path = product_storage.relocated_path(
                    product.image_path,
                    category.code,
                    product.created_at,
                    "main",
                )
                if relocated_main_path != product.image_path:
                    await product_storage.move(product.image_path, relocated_main_path)
                    moved_storage_paths.append((product.image_path, relocated_main_path))
                    product.image_path = relocated_main_path

            detail_html, moved_editor_paths = await self._relocate_editor_images(
                sanitize_detail_html(request.detail_html),
                category.code,
                product.created_at,
                request.editor_upload_session_id,
                previous_editor_paths,
            )
            moved_storage_paths.extend(moved_editor_paths)
            product.visible = request.visible
            product.display_order = request.display_order
            product.category_id = request.category_id
            product.name = request.name
            product.code = request.code
            product.price = request.price
            if stored_image:
                product.image_path = stored_image.path
            product.image_name = request.image_name
            product.image_description = request.image_description
            product.detail_html = detail_html
            removed_editor_paths = previous_editor_paths - product_storage.paths_from_html(product.detail_html)
            product.updated_at = korea_now()
            await self._replace_relations(product.id, request.related_product_ids)
            after_snapshot = self._audit_snapshot(product, request.related_product_ids)
            changes = self._audit_changes(before_snapshot, after_snapshot)
            if changes:
                self.db.add(
                    ProductAuditLog(
                        product_id=product.id,
                        action="updated",
                        changes=changes,
                    )
                )
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            if stored_image:
                await product_storage.delete(stored_image.path)
            await self._rollback_storage_moves(moved_storage_paths)
            await self._raise_write_conflict(request, product.id, error)
        except Exception:
            await self.db.rollback()
            if stored_image:
                await product_storage.delete(stored_image.path)
            await self._rollback_storage_moves(moved_storage_paths)
            raise
        if stored_image and previous_image_path != stored_image.path:
            await product_storage.delete(previous_image_path)
        await self._delete_unreferenced_editor_images(removed_editor_paths)
        if request.editor_upload_session_id:
            await product_storage.delete_draft(request.editor_upload_session_id)
        return {"message": "상품이 수정되었습니다.", "product_id": product.id}

    # 고객 화면에서는 즉시 사라지되 DB·Storage 원본은 복구 가능하도록 소프트 삭제
    async def delete_product(self, product_id: int) -> dict:
        product = await self._get_product(product_id)
        previous_related_ids = await self._relation_ids(product.id)
        previous_incoming_ids = await self._incoming_relation_ids(product.id)
        before_snapshot = self._audit_snapshot(product, previous_related_ids)
        now = korea_now()
        product.status = "deleted"
        product.visible = False
        product.deleted_at = now
        product.updated_at = now
        await self.db.execute(
            delete(ProductRelation).where(
                or_(
                    ProductRelation.product_id == product.id,
                    ProductRelation.related_product_id == product.id,
                )
            )
        )
        after_snapshot = self._audit_snapshot(product, [])
        changes = self._audit_changes(before_snapshot, after_snapshot)
        if previous_incoming_ids:
            changes["incoming_related_product_ids"] = {"before": previous_incoming_ids, "after": []}
        self.db.add(
            ProductAuditLog(
                product_id=product.id,
                action="deleted",
                changes=changes,
            )
        )
        await self.db.commit()
        return {"message": "상품이 삭제되었습니다."}

    # 삭제 상품의 코드·카테고리 충돌을 확인하고 안전한 미노출 상태로 복원
    async def restore_product(self, product_id: int) -> dict:
        product = await self._get_deleted_product(product_id, for_update=True)
        category = await self.db.get(ProductCategory, product.category_id)
        if not category or not category.is_active:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "RESTORE_CATEGORY_INACTIVE",
                "카테고리가 비활성 상태입니다. 카테고리를 활성화한 후 복원해 주세요.",
            )

        code_exists = (
            await self.db.execute(
                select(Product.id).where(
                    Product.status == "active",
                    Product.code == product.code,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if code_exists is not None:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "RESTORE_CODE_CONFLICT",
                "같은 상품코드를 사용하는 상품이 있어 복원할 수 없습니다.",
            )

        order_exists = (
            await self.db.execute(
                select(Product.id).where(
                    Product.status == "active",
                    Product.display_order == product.display_order,
                ).limit(1)
            )
        ).scalar_one_or_none()
        reassigned_order = order_exists is not None
        if reassigned_order:
            max_order = (
                await self.db.execute(
                    select(func.coalesce(func.max(Product.display_order), 0)).where(Product.status == "active")
                )
            ).scalar_one()
            product.display_order = max_order + 1

        deleted_audit = (
            await self.db.execute(
                select(ProductAuditLog)
                .where(ProductAuditLog.product_id == product.id, ProductAuditLog.action == "deleted")
                .order_by(ProductAuditLog.created_at.desc(), ProductAuditLog.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        deleted_changes = deleted_audit.changes if deleted_audit else {}
        outgoing_ids = self._audit_before_ids(deleted_changes, "related_product_ids")
        incoming_ids = self._audit_before_ids(deleted_changes, "incoming_related_product_ids")

        valid_outgoing_ids = await self._valid_relation_targets(product, outgoing_ids, limit=2)
        valid_incoming_ids = await self._valid_incoming_sources(product, incoming_ids)
        before_snapshot = self._audit_snapshot(product, [])
        now = korea_now()
        product.status = "active"
        product.visible = False
        product.deleted_at = None
        product.updated_at = now
        await self._replace_relations(product.id, valid_outgoing_ids)
        for source_id in valid_incoming_ids:
            self.db.add(ProductRelation(product_id=source_id, related_product_id=product.id))

        after_snapshot = self._audit_snapshot(product, valid_outgoing_ids)
        changes = self._audit_changes(before_snapshot, after_snapshot)
        if valid_incoming_ids:
            changes["incoming_related_product_ids"] = {"before": [], "after": valid_incoming_ids}
        self.db.add(
            ProductAuditLog(
                product_id=product.id,
                action="restored",
                changes=changes,
            )
        )
        try:
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            raise api_error(
                status.HTTP_409_CONFLICT,
                "RESTORE_CONFLICT",
                "다른 상품 변경과 충돌했습니다. 목록을 새로고침한 후 다시 시도해 주세요.",
            ) from error

        order_notice = " 사용 중이던 노출순서는 마지막 순서로 자동 변경되었습니다." if reassigned_order else ""
        return {
            "message": f"상품이 미노출 상태로 복원되었습니다.{order_notice}",
            "product_id": product.id,
            "display_order": product.display_order,
            "restored_relation_count": len(valid_outgoing_ids) + len(valid_incoming_ids),
        }

    # 상세내용 이미지는 저장 전 임시 세션에 업로드하고 상품 저장 시 정식 경로로 이동
    async def upload_editor_image(self, request: EditorImageUploadRequest) -> dict:
        category = await self.db.get(ProductCategory, request.category_id)
        if not category or not category.is_active:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_CATEGORY", "선택한 카테고리를 사용할 수 없습니다.")
        if request.product_id is not None:
            await self._get_product(request.product_id)
        stored_image = await product_storage.upload_editor_draft(request.upload_session_id, request.image_data)
        return {"url": stored_image.public_url, "path": stored_image.path}

    # 등록·수정 취소 시 해당 화면 세션에서 아직 정식 저장하지 않은 이미지만 제거
    async def cleanup_editor_draft(self, upload_session_id: str) -> dict:
        await product_storage.delete_draft(upload_session_id)
        return {"message": "임시 상세 이미지가 정리되었습니다."}

    # 선택 카테고리와 활성 상태 및 관련 상품 동일 카테고리 검증
    async def _validate_write_request(self, request: ProductWriteRequest, product_id: int | None) -> None:
        category = await self.db.get(ProductCategory, request.category_id)
        if not category or not category.is_active:
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_CATEGORY", "선택한 카테고리를 사용할 수 없습니다.")
        conflict_filters = [
            Product.status == "active",
            or_(Product.code == request.code, Product.display_order == request.display_order),
        ]
        if product_id is not None:
            conflict_filters.append(Product.id != product_id)
        conflicts = (await self.db.execute(select(Product).where(*conflict_filters))).scalars().all()
        if any(item.code == request.code for item in conflicts):
            raise api_error(status.HTTP_409_CONFLICT, "PRODUCT_CODE_EXISTS", "이미 등록된 상품코드입니다.")
        if any(item.display_order == request.display_order for item in conflicts):
            raise api_error(status.HTTP_409_CONFLICT, "DISPLAY_ORDER_EXISTS", "이미 사용 중인 노출순서입니다.")
        if product_id is not None and product_id in request.related_product_ids:
            raise api_error(status.HTTP_400_BAD_REQUEST, "RELATED_PRODUCT_SELF", "자기 자신은 관련 상품으로 선택할 수 없습니다.")
        if not request.related_product_ids:
            return
        query = select(Product).where(
            Product.id.in_(request.related_product_ids),
            Product.status == "active",
        )
        related_products = (await self.db.execute(query)).scalars().all()
        if len(related_products) != len(request.related_product_ids):
            raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_RELATED_PRODUCT", "선택한 관련 상품을 찾을 수 없습니다.")
        if any(item.category_id != request.category_id for item in related_products):
            raise api_error(status.HTTP_400_BAD_REQUEST, "RELATED_CATEGORY_MISMATCH", "같은 카테고리의 상품만 관련 상품으로 선택할 수 있습니다.")

    # 동시 저장에서 발생한 고유 제약 충돌을 필드별 오류로 변환
    async def _raise_write_conflict(
        self,
        request: ProductWriteRequest,
        product_id: int | None,
        original_error: IntegrityError,
    ) -> None:
        filters = [
            Product.status == "active",
            or_(Product.code == request.code, Product.display_order == request.display_order),
        ]
        if product_id is not None:
            filters.append(Product.id != product_id)
        conflicts = (await self.db.execute(select(Product).where(*filters))).scalars().all()
        if any(item.code == request.code for item in conflicts):
            raise api_error(status.HTTP_409_CONFLICT, "PRODUCT_CODE_EXISTS", "이미 등록된 상품코드입니다.") from original_error
        if any(item.display_order == request.display_order for item in conflicts):
            raise api_error(status.HTTP_409_CONFLICT, "DISPLAY_ORDER_EXISTS", "이미 사용 중인 노출순서입니다.") from original_error
        raise api_error(status.HTTP_409_CONFLICT, "PRODUCT_CONFLICT", "상품 정보가 다른 데이터와 충돌했습니다.") from original_error

    # 현재 관련 상품 연결을 요청 목록으로 교체
    async def _replace_relations(self, product_id: int, related_ids: list[int]) -> None:
        await self.db.execute(delete(ProductRelation).where(ProductRelation.product_id == product_id))
        for related_id in related_ids:
            self.db.add(ProductRelation(product_id=product_id, related_product_id=related_id))

    # 현재 관련 상품 ID 목록 반환
    async def _relation_ids(self, product_id: int) -> list[int]:
        query = select(ProductRelation.related_product_id).where(ProductRelation.product_id == product_id)
        return list((await self.db.execute(query)).scalars().all())

    # 현재 상품을 관련 상품으로 가리키는 역방향 연결 목록 반환
    async def _incoming_relation_ids(self, product_id: int) -> list[int]:
        query = select(ProductRelation.product_id).where(ProductRelation.related_product_id == product_id)
        return list((await self.db.execute(query)).scalars().all())

    # 상세 HTML이 참조하는 관리 이미지들을 목표 카테고리·최초 등록일 폴더로 이동
    async def _relocate_editor_images(
        self,
        detail_html: str,
        category_code: str,
        registered_at: datetime,
        upload_session_id: str | None = None,
        existing_paths: set[str] | None = None,
    ) -> tuple[str, list[tuple[str, str]]]:
        updated_html = detail_html
        moved_paths: list[tuple[str, str]] = []
        current_paths = product_storage.paths_from_html(detail_html)
        draft_prefix = product_storage.draft_prefix(upload_session_id) + "/" if upload_session_id else ""
        foreign_drafts = {
            path for path in current_paths
            if product_storage.is_draft_path(path) and not (draft_prefix and path.startswith(draft_prefix))
        }
        if foreign_drafts:
            raise api_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_EDITOR_IMAGE_SESSION",
                "다른 편집 세션의 임시 이미지는 사용할 수 없습니다. 이미지를 다시 첨부해 주세요.",
            )
        movable_paths = set(existing_paths or set())
        if draft_prefix:
            movable_paths.update(path for path in current_paths if path.startswith(draft_prefix))
        try:
            for source_path in sorted(current_paths & movable_paths):
                destination_path = product_storage.relocated_path(
                    source_path,
                    category_code,
                    registered_at,
                    "detail",
                )
                if destination_path == source_path:
                    continue
                await product_storage.move(source_path, destination_path)
                moved_paths.append((source_path, destination_path))
                updated_html = updated_html.replace(
                    product_storage.public_url(source_path),
                    product_storage.public_url(destination_path),
                )
        except Exception:
            await self._rollback_storage_moves(moved_paths)
            raise
        return updated_html, moved_paths

    # DB 저장 실패 시 이미 이동된 Storage 객체를 원래 경로로 되돌림
    @staticmethod
    async def _rollback_storage_moves(moved_paths: list[tuple[str, str]]) -> None:
        for source_path, destination_path in reversed(moved_paths):
            await product_storage.move(destination_path, source_path, strict=False)

    # 삭제 감사 로그의 before 배열을 안전한 정수 ID 목록으로 변환
    @staticmethod
    def _audit_before_ids(changes: dict, field: str) -> list[int]:
        raw_ids = changes.get(field, {}).get("before", []) if isinstance(changes, dict) else []
        if not isinstance(raw_ids, list):
            return []
        return [item for item in raw_ids if isinstance(item, int) and item > 0]

    # 복원 대상의 기존 정방향 관계 중 현재도 활성·동일 카테고리인 상품만 반환
    async def _valid_relation_targets(self, product: Product, candidate_ids: list[int], limit: int) -> list[int]:
        if not candidate_ids:
            return []
        query = select(Product.id).where(
            Product.id.in_(candidate_ids),
            Product.id != product.id,
            Product.status == "active",
            Product.category_id == product.category_id,
        )
        valid_ids = set((await self.db.execute(query)).scalars().all())
        return [item for item in candidate_ids if item in valid_ids][:limit]

    # 역방향 관계는 출발 상품의 최대 2건 제한과 활성·동일 카테고리 조건을 함께 확인
    async def _valid_incoming_sources(self, product: Product, candidate_ids: list[int]) -> list[int]:
        valid_sources = await self._valid_relation_targets(product, candidate_ids, limit=len(candidate_ids))
        result: list[int] = []
        for source_id in valid_sources:
            relation_count = (
                await self.db.execute(
                    select(func.count(ProductRelation.related_product_id)).where(ProductRelation.product_id == source_id)
                )
            ).scalar_one()
            if relation_count < 2:
                result.append(source_id)
        return result

    # 다른 상품 본문에서 사용하지 않는 에디터 이미지 Storage 정리
    async def _delete_unreferenced_editor_images(self, paths: set[str]) -> None:
        for path in paths:
            public_url = product_storage.public_url(path)
            in_use = (
                await self.db.execute(
                    select(Product.id).where(Product.detail_html.contains(public_url)).limit(1)
                )
            ).scalar_one_or_none()
            if not in_use:
                await product_storage.delete(path)

    # 단일 관리자가 접근하는 활성 상품 조회
    async def _get_product(self, product_id: int) -> Product:
        query = select(Product).where(
            Product.id == product_id,
            Product.status == "active",
        )
        product = (await self.db.execute(query)).scalar_one_or_none()
        if not product:
            raise api_error(status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND", "상품을 찾을 수 없습니다.")
        return product

    # 복원 전용 삭제 상품 조회 및 동시 복원 방지를 위한 행 잠금
    async def _get_deleted_product(self, product_id: int, for_update: bool = False) -> Product:
        query = select(Product).where(Product.id == product_id, Product.status == "deleted")
        if for_update:
            query = query.with_for_update()
        product = (await self.db.execute(query)).scalar_one_or_none()
        if not product:
            raise api_error(status.HTTP_404_NOT_FOUND, "DELETED_PRODUCT_NOT_FOUND", "삭제된 상품을 찾을 수 없습니다.")
        return product

    # 전역 카탈로그의 같은 카테고리 관련 상품 후보 반환
    async def _related_candidates(self, category_id: int, excluded_id: int | None = None) -> list[dict]:
        filters = [
            Product.category_id == category_id,
            Product.status == "active",
        ]
        if excluded_id is not None:
            filters.append(Product.id != excluded_id)
        query = select(Product).where(*filters).order_by(Product.name, Product.id)
        products = (await self.db.execute(query)).scalars().all()
        return [{"id": item.id, "name": item.name, "code": item.code} for item in products]

    # 목록 표에 필요한 상품 데이터 직렬화
    @staticmethod
    def _list_item(product: Product, category_name: str) -> dict:
        return {
            "id": product.id,
            "visible": product.visible,
            "display_order": product.display_order,
            "category": category_name,
            "name": product.name,
            "code": product.code,
            "price": product.price,
            "created_at": korea_iso(product.created_at),
            "updated_at": korea_iso(product.updated_at),
            "deleted_at": korea_iso(product.deleted_at) if product.deleted_at else None,
            "status": product.status,
        }

    # 편집 화면에 필요한 상품 전체 데이터 직렬화
    @staticmethod
    def _detail_item(product: Product, related_ids: list[int]) -> dict:
        return {
            "id": product.id,
            "visible": product.visible,
            "display_order": product.display_order,
            "category_id": product.category_id,
            "name": product.name,
            "code": product.code,
            "price": product.price,
            "image_url": product_storage.public_url(product.image_path),
            "image_name": product.image_name,
            "image_description": product.image_description or "",
            "detail_html": product.detail_html,
            "related_product_ids": related_ids,
            "created_at": korea_iso(product.created_at),
            "updated_at": korea_iso(product.updated_at),
        }

    # 고객 목록에 필요한 공개 필드만 직렬화
    @staticmethod
    def _catalog_list_item(product: Product, category_name: str) -> dict:
        return {
            "id": product.id,
            "category": category_name,
            "name": product.name,
            "code": product.code,
            "price": product.price,
            "image_url": product_storage.public_url(product.image_path),
            "image_description": product.image_description or "",
        }

    # 고객 상세에 필요한 공개 필드만 직렬화
    @staticmethod
    def _catalog_detail_item(product: Product, category_name: str, related_products: list[dict]) -> dict:
        return {
            **ProductService._catalog_list_item(product, category_name),
            "detail_html": product.detail_html,
            "related_products": related_products,
        }

    # 감사 로그용 상품 상태 스냅샷 생성
    @staticmethod
    def _audit_snapshot(product: Product, related_ids: list[int]) -> dict:
        return {
            "visible": product.visible,
            "display_order": product.display_order,
            "category_id": product.category_id,
            "name": product.name,
            "code": product.code,
            "price": product.price,
            "image_path": product.image_path,
            "image_name": product.image_name,
            "image_description": product.image_description,
            "detail_html": product.detail_html,
            "related_product_ids": list(related_ids),
            "status": product.status,
        }

    # 변경된 필드만 이전·이후 값으로 구성
    @staticmethod
    def _audit_changes(before: dict, after: dict) -> dict:
        return {
            field: {"before": before.get(field), "after": after.get(field)}
            for field in before.keys() | after.keys()
            if before.get(field) != after.get(field)
        }
