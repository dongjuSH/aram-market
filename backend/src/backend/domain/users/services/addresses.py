# 회원 배송지 주소록 조회·추가·수정·삭제·기본 배송지 지정 규칙(최대 10개, 기본 배송지는 1개)

from fastapi import Depends, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.errors import api_error
from backend.domain.users.models.users import User, UserAddress
from backend.domain.users.schemas.users import AddressRequest
from backend.domain.users.services.users import UserService

MAX_ADDRESSES = 10  # 회원당 저장할 수 있는 배송지 수


# 배송지 주소록 서비스(인증은 고객 접근 토큰 검증을 그대로 사용)
class AddressService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_service = UserService(db)

    # 개수 제한·기본 배송지 규칙이 동시 요청에도 지켜지도록 변경 전에 회원 행을 잠금
    async def _locked_user_id(self, token: str) -> int:
        user = await self.user_service._get_user_from_access_token(token)
        await self.db.execute(select(User.id).where(User.id == user.id).with_for_update())
        return user.id

    @staticmethod
    def _item(address: UserAddress) -> dict:
        return {
            "id": address.id,
            "label": address.label,
            "recipient_name": address.recipient_name,
            "recipient_phone": address.recipient_phone,
            "postcode": address.postcode or "",
            "address": address.address,
            "address_detail": address.address_detail or "",
            "is_default": address.is_default,
        }

    # 기본 배송지 먼저, 그다음 최근 등록순
    async def _payload(self, user_id: int) -> dict:
        rows = (
            await self.db.execute(
                select(UserAddress)
                .where(UserAddress.user_id == user_id)
                .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc(), UserAddress.id.desc())
            )
        ).scalars().all()
        return {"addresses": [self._item(row) for row in rows], "max_addresses": MAX_ADDRESSES}

    # 본인 배송지만 다룰 수 있음(남의 배송지는 존재 여부도 드러내지 않도록 404)
    async def _own(self, user_id: int, address_id: int) -> UserAddress:
        address = (
            await self.db.execute(select(UserAddress).where(UserAddress.id == address_id, UserAddress.user_id == user_id))
        ).scalar_one_or_none()
        if address is None:
            raise api_error(status.HTTP_404_NOT_FOUND, "ADDRESS_NOT_FOUND", "배송지를 찾을 수 없습니다.")
        return address

    async def _clear_default(self, user_id: int) -> None:
        await self.db.execute(update(UserAddress).where(UserAddress.user_id == user_id, UserAddress.is_default.is_(True)).values(is_default=False))

    async def list_addresses(self, token: str) -> dict:
        user = await self.user_service._get_user_from_access_token(token)
        return await self._payload(user.id)

    async def create(self, token: str, request: AddressRequest) -> dict:
        user_id = await self._locked_user_id(token)
        count = (await self.db.execute(select(func.count()).where(UserAddress.user_id == user_id))).scalar_one()
        if count >= MAX_ADDRESSES:
            raise api_error(status.HTTP_409_CONFLICT, "ADDRESS_LIMIT_REACHED", f"배송지는 최대 {MAX_ADDRESSES}개까지 저장할 수 있어요. 사용하지 않는 배송지를 삭제해 주세요.")
        make_default = request.is_default or count == 0  # 첫 배송지는 자동으로 기본 배송지
        if make_default:
            await self._clear_default(user_id)
        self.db.add(
            UserAddress(
                user_id=user_id,
                label=request.label,
                recipient_name=request.recipient_name,
                recipient_phone=request.recipient_phone,
                postcode=request.postcode or None,
                address=request.address,
                address_detail=request.address_detail or None,
                is_default=make_default,
            )
        )
        await self.db.commit()
        return await self._payload(user_id)

    # 수정(기본 배송지를 해제하려면 다른 배송지를 기본으로 지정해야 하므로 기본 배송지의 is_default=False는 무시)
    async def update(self, token: str, address_id: int, request: AddressRequest) -> dict:
        user_id = await self._locked_user_id(token)
        address = await self._own(user_id, address_id)
        if request.is_default and not address.is_default:
            await self._clear_default(user_id)
            address.is_default = True
        address.label = request.label
        address.recipient_name = request.recipient_name
        address.recipient_phone = request.recipient_phone
        address.postcode = request.postcode or None
        address.address = request.address
        address.address_detail = request.address_detail or None
        address.updated_at = func.now()
        await self.db.commit()
        return await self._payload(user_id)

    async def set_default(self, token: str, address_id: int) -> dict:
        user_id = await self._locked_user_id(token)
        address = await self._own(user_id, address_id)
        if not address.is_default:
            await self._clear_default(user_id)
            address.is_default = True
            await self.db.commit()
        return await self._payload(user_id)

    # 삭제(기본 배송지를 지우면 가장 최근 배송지가 기본 배송지가 됨)
    async def delete(self, token: str, address_id: int) -> dict:
        user_id = await self._locked_user_id(token)
        address = await self._own(user_id, address_id)
        was_default = address.is_default
        await self.db.execute(delete(UserAddress).where(UserAddress.id == address.id))
        if was_default:
            newest = (
                await self.db.execute(
                    select(UserAddress).where(UserAddress.user_id == user_id).order_by(UserAddress.created_at.desc(), UserAddress.id.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if newest is not None:
                newest.is_default = True
        await self.db.commit()
        return await self._payload(user_id)
