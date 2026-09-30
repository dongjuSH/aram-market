# 로그인 고객 배송지 주소록 HTTP 엔드포인트

from fastapi import APIRouter, Depends, Path, status

from backend.core.dependencies import require_user_token
from backend.domain.users.schemas.users import AddressRequest
from backend.domain.users.services.addresses import AddressService

router = APIRouter(prefix="/users/me/addresses", tags=["addresses"])  # main.py에서 공통 /api 접두사 적용


# 내 배송지 목록(기본 배송지 먼저)
@router.get("", status_code=status.HTTP_200_OK)
async def list_addresses(token: str = Depends(require_user_token), service: AddressService = Depends(AddressService)):
    return await service.list_addresses(token)


# 배송지 추가(최대 10개)
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_address(
    request: AddressRequest,
    token: str = Depends(require_user_token),
    service: AddressService = Depends(AddressService),
):
    return await service.create(token, request)


# 배송지 수정
@router.put("/{address_id}", status_code=status.HTTP_200_OK)
async def update_address(
    request: AddressRequest,
    address_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: AddressService = Depends(AddressService),
):
    return await service.update(token, address_id, request)


# 기본 배송지로 지정
@router.put("/{address_id}/default", status_code=status.HTTP_200_OK)
async def set_default_address(
    address_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: AddressService = Depends(AddressService),
):
    return await service.set_default(token, address_id)


# 배송지 삭제
@router.delete("/{address_id}", status_code=status.HTTP_200_OK)
async def delete_address(
    address_id: int = Path(gt=0),
    token: str = Depends(require_user_token),
    service: AddressService = Depends(AddressService),
):
    return await service.delete(token, address_id)
