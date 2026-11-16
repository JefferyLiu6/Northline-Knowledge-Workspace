from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.responses import JSONResponse


# Custom anomalies
class CustomException(Exception):
    def __init__(self, message: str, code: str = "500"):
        # Message is a human cue to the user, and it'll appear in the front red window.
        self.message = message
        # Code default 500 indicates business failure, login lapse 401, no permissions to pass 403.
        self.code = code


def setup_exceptions(app: FastAPI):
    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        return JSONResponse(
            # The business anomaly also returns HTTP 200. Error information is placed in the code of the responder.
            # The front side only needs to judge the code field, not handle both HTTP status codes and operating codes at once.
            status_code=status.HTTP_200_OK,
            content={"code": exc.code, "msg": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def validate_exception_handler(request: Request, exc: RequestValidationError):
        print("Captured 422 error:", exc.errors())
        """Handle 422 exception"""
        # Returns the uniform format
        return JSONResponse(
            # Again returns HTTP 200, the parameter error is expressed by code=500 in the echo body
            status_code=status.HTTP_200_OK,
            content={"code": "500", "msg": "Request parameter error"}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print("Captured system error:", repr(exc))
        """Handle all exceptions"""
        # Returns the uniform format
        response = JSONResponse(
            # The HTTP 200 is also returned by the spinster processor, and unanticipated anomalies follow a uniform format.
            status_code=status.HTTP_200_OK,
            content={"code": "500", "msg": "System error"}
        )
        # The response returned by the spin-down processor does not pass through the CRS middle, and crosses the domain to fill it up.
        # Otherwise, the front end gets a response that's blocked by the browser.
        # Allows all sources (consistent with your CORS configuration)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
