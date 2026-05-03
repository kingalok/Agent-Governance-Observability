from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.runtime import get_request_id


logger = logging.getLogger("app.errors")


def _error_body(message: str, *, code: str, details: list[dict] | None = None) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
        }
    }
    if details:
        payload["error"]["details"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning(
            "domain_error",
            extra={"path": request.url.path, "method": request.method, "request_id": get_request_id()},
        )
        return JSONResponse(status_code=400, content=_error_body(str(exc), code="bad_request"))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "validation_error",
            extra={"path": request.url.path, "method": request.method, "request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "Request validation failed.",
                code="validation_error",
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        error_id = str(uuid4())
        logger.exception(
            "unexpected_error",
            extra={"path": request.url.path, "method": request.method, "request_id": get_request_id(), "event_type": error_id},
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "Unexpected internal error.",
                code="internal_error",
                details=[{"event_id": error_id}],
            ),
        )
