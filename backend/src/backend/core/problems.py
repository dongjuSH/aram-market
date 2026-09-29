# 모든 오류 응답을 RFC 9457 Problem Details(application/problem+json) 형식으로 통일

import re

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

# 상태코드별 사용자용 짧은 제목(title)
STATUS_TITLES = {
    400: "잘못된 요청",
    401: "인증이 필요합니다",
    403: "접근할 수 없습니다",
    404: "찾을 수 없습니다",
    405: "허용되지 않는 요청 방식",
    409: "요청이 충돌합니다",
    413: "요청이 너무 큽니다",
    422: "입력값을 확인해 주세요",
    429: "요청이 너무 많습니다",
    500: "서버 오류",
}

# 구조화되지 않은 오류의 기본 코드
STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


# 오류 코드(UPPER_SNAKE)를 type URI 경로(kebab-case)로 변환
def _problem_type(code: str) -> str:
    return f"/problems/{re.sub(r'_+', '-', code.lower())}"


# HTTPException.detail(문자열 또는 {code, message, ...})을 Problem Details 본문으로 변환
def build_problem(status_code: int, detail, instance: str | None = None) -> dict:
    if isinstance(detail, dict):
        code = str(detail.get("code") or STATUS_CODES.get(status_code, "REQUEST_FAILED"))
        message = str(detail.get("message") or STATUS_TITLES.get(status_code, "요청을 처리하지 못했습니다."))
        extensions = {key: value for key, value in detail.items() if key not in {"code", "message"}}
    else:
        code = STATUS_CODES.get(status_code, "REQUEST_FAILED")
        message = str(detail) if detail else STATUS_TITLES.get(status_code, "요청을 처리하지 못했습니다.")
        extensions = {}
    problem = {
        "type": _problem_type(code),
        "title": STATUS_TITLES.get(status_code, "요청을 처리하지 못했습니다."),
        "status": status_code,
        "detail": message,  # 화면에 그대로 보여줄 수 있는 한국어 안내
        "code": code,  # 프런트 분기용 안정적인 코드
        **extensions,
    }
    if instance:
        problem["instance"] = instance
    return problem


# Problem Details JSON 응답 생성(헤더의 Retry-After 등은 유지)
def problem_response(status_code: int, detail, request: Request | None = None, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(build_problem(status_code, detail, request.url.path if request else None)),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


# FastAPI·Starlette HTTPException 처리
async def http_exception_handler(request: Request, error: StarletteHTTPException) -> JSONResponse:
    return problem_response(error.status_code, error.detail, request, dict(error.headers) if error.headers else None)


# Pydantic 기본 영어 검증 메시지를 한국어 안내로 변환(직접 작성한 검증 메시지는 그대로 사용)
def _korean_validation_message(item: dict) -> str:
    kind = item.get("type", "")
    ctx = item.get("ctx") or {}
    if kind == "missing":
        return "필수 입력 항목입니다."
    if kind == "string_too_short":
        return f"{ctx.get('min_length')}자 이상 입력해 주세요."
    if kind == "string_too_long":
        return f"{ctx.get('max_length')}자 이하로 입력해 주세요."
    if kind in {"greater_than", "greater_than_equal"}:
        return f"{ctx.get('gt', ctx.get('ge'))}{'보다 큰' if kind == 'greater_than' else ' 이상의'} 값을 입력해 주세요."
    if kind in {"less_than", "less_than_equal"}:
        return f"{ctx.get('lt', ctx.get('le'))}{'보다 작은' if kind == 'less_than' else ' 이하의'} 값을 입력해 주세요."
    if kind in {"list_too_short", "too_short"}:
        return f"{ctx.get('min_length')}개 이상 선택해 주세요."
    if kind in {"list_too_long", "too_long"}:
        return f"{ctx.get('max_length')}개 이하로 선택해 주세요."
    if kind == "value_error":
        return str(item.get("msg", "")).removeprefix("Value error, ")
    if kind == "json_invalid":
        return "요청 형식이 올바르지 않습니다."
    return "입력값이 올바르지 않습니다."


# Pydantic 입력 검증 오류를 필드별 메시지가 있는 422 Problem Details로 변환
async def validation_exception_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    fields = [
        {
            "field": ".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
            "message": _korean_validation_message(item),
        }
        for item in error.errors()
    ]
    detail = "\n".join(dict.fromkeys(field["message"] for field in fields)) or "입력값을 확인해 주세요."
    body = build_problem(422, {"code": "VALIDATION_ERROR", "message": detail, "errors": fields}, request.url.path)
    return JSONResponse(status_code=422, content=jsonable_encoder(body), media_type=PROBLEM_MEDIA_TYPE)


# 처리되지 않은 예외는 내부 정보를 숨기고 일반 500 Problem Details로 응답
async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
    _ = error
    return problem_response(500, "서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", request)
