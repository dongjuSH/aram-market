# 프런트가 오류 종류를 구분할 수 있도록 {code, message, ...추가 정보} 형식의 HTTPException 생성

from fastapi import HTTPException


# 구조화된 오류 생성(core/problems.py가 RFC 9457 응답으로 변환)
def api_error(status_code: int, code: str, message: str, **metadata) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, **metadata},
    )
