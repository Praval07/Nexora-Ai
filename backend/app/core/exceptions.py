class AppException(Exception):
    status_code = 500
    message = "An unexpected error occurred"

    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__()
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["status"] = "error"
        rv["message"] = self.message
        return rv

class NotFoundException(AppException):
    status_code = 404
    message = "Resource not found"

class BadRequestException(AppException):
    status_code = 400
    message = "Bad request"

class UnauthorizedException(AppException):
    status_code = 401
    message = "Unauthorized access"

class ForbiddenException(AppException):
    status_code = 403
    message = "Action forbidden"

class ConflictException(AppException):
    status_code = 409
    message = "Resource conflict"
