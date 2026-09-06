import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def error_response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "message": detail})


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.message)


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0]
    location = first_error.get("loc", ())
    field = location[-1] if location else "body"
    return error_response(422, f"{field}: {first_error.get('msg', 'Validation error')}")


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return error_response(500, "Internal server error")
