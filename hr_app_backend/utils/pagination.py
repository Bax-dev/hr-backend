from django.core.paginator import Paginator

from .errors import ValidationError

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _positive_int(value, *, default, maximum=None):
    if value is None or value == '':
        result = default
    else:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError('Pagination values must be integers.') from exc
        if result < 1:
            raise ValidationError('Pagination values must be greater than zero.')
    if maximum is not None:
        result = min(result, maximum)
    return result


def paginate_queryset(
    request,
    queryset,
    *,
    default_page_size=DEFAULT_PAGE_SIZE,
    max_page_size=MAX_PAGE_SIZE,
):
    """Slice ``queryset`` using ``page``/``page_size`` query params.

    Returns ``(object_list, meta)`` where ``meta`` is a dict describing the
    current page. Out-of-range pages clamp to the last available page so the
    client always receives a consistent envelope.
    """
    page_size = _positive_int(
        request.GET.get('page_size'),
        default=default_page_size,
        maximum=max_page_size,
    )
    page_number = _positive_int(request.GET.get('page'), default=1)

    paginator = Paginator(queryset, page_size)
    page_number = min(page_number, paginator.num_pages or 1)
    page = paginator.page(page_number)

    meta = {
        'page': page.number,
        'page_size': page_size,
        'total_items': paginator.count,
        'total_pages': paginator.num_pages,
        'has_next': page.has_next(),
        'has_previous': page.has_previous(),
    }
    return list(page.object_list), meta


def paginated_data(request, queryset, serializer, *, key, **kwargs):
    """Build the ``data`` payload for a paginated ``JsonResponse``.

    ``serializer`` is called once per item and the results are stored under
    ``key`` alongside a ``pagination`` block, e.g.::

        data = paginated_data(request, employees, serialize_employee, key='employees')
        return JsonResponse({'success': True, 'data': data})
    """
    object_list, meta = paginate_queryset(request, queryset, **kwargs)
    return {
        key: [serializer(item) for item in object_list],
        'pagination': meta,
    }
