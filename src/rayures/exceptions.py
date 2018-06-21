
class DispatchException(Exception):
    def __init__(self, message, *, process, event, proc_errors):
        self.message = message
        self.process = process
        self.event = event
        self.proc_errors = proc_errors
        super().__init__(message)

    @property
    def formatted_errors(self):
        return [{
            'id': str(pe.id),
            'func': str(pe.func),
            'message': str(pe.message)
        } for pe, _ in self.proc_errors]


class InvalidInputsError(Exception):
    def __init__(self, message, errors):
        self.message = message
        self.errors = errors
        super().__init__(message)
