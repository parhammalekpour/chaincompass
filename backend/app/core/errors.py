import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_exception_handlers(application: FastAPI) -> None:
    def request_headers(request: Request) -> dict[str, str]:
        request_id = getattr(request.state, "request_id", None)
        return {"X-Request-ID": request_id} if request_id else {}

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": message},
            headers={**(exc.headers or {}), **request_headers(request)},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, __: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request validation failed",
            },
            headers=request_headers(request),
        )

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled request exception",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "An unexpected error occurred",
            },
            headers=request_headers(request),
        )
