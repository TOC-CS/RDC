class RDCError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def result(self):
        error = {'code': self.code, 'message': self.message}
        if self.details is not None:
            error['details'] = self.details
        return {'ok': False, 'error': error}

