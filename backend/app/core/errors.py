from fastapi import HTTPException


def not_found(message: str = "Resource not found") -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)



def unauthorized(message: str = "Authentication is required") -> HTTPException:
    return HTTPException(status_code=401, detail=message)


def forbidden(message: str = "Access is not allowed") -> HTTPException:
    return HTTPException(status_code=403, detail=message)

def unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def service_unavailable(message: str) -> HTTPException:
    return HTTPException(status_code=503, detail=message)
