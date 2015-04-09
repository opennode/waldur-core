from nodeconductor.core.pagination import LinkHeaderPagination


class QuotaPagination(LinkHeaderPagination):
    """
    Quota display is an expensive query. Once the result set is known, it's cheaper to serialize larger output.
    """
    page_size = 500
    max_page_size = 1000
