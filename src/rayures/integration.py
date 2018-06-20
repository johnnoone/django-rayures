class BaseCustomerFinder:
    def find(self, request):
        """Find customer based on request.

        Must return a rayure.Customer instance or None
        """
        raise NotImplementedError
