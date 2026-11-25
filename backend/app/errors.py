"""
Friendlier validation error responses.

FastAPI's default 422 error is detailed but a bit noisy. This handler turns it
into a short list of {field, message} pairs that is easy to read and show
to a user, for example:

{
  "detail": "Validation failed",
  "errors": [
    {"field": "people_affected", "message": "Input should be greater than or equal to 0"},
    {"field": "location", "message": "Field required"}
  ]
}
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        if error.get("type") == "json_invalid":
            errors.append({"field": "body", "message": "Invalid JSON body"})
            continue

        # error["loc"] looks like ("body", "help_needed", 0). Drop the leading "body".
        location = [str(part) for part in error["loc"] if part != "body"]
        field = ".".join(location) or "body"
        # Custom validator messages start with "Value error, " - remove that prefix.
        message = error["msg"].removeprefix("Value error, ")
        errors.append({"field": field, "message": message})

    return JSONResponse(
        status_code=422,  # 422 = "Unprocessable Content": the request body is invalid
        content={"detail": "Validation failed", "errors": errors},
    )
