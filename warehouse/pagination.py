"""Stronicowanie list (US-015) — jedna konwencja dla wszystkich ekranów."""

from django.core.paginator import Paginator

PAGE_SIZE = 100


def paginate(request, queryset, per_page=PAGE_SIZE, count=None):
    """Zwraca (strona, querystring filtrów bez `page`) do linków nawigacji.

    `get_page` toleruje śmieci i numery poza zakresem (pierwsza / ostatnia strona),
    więc parametr `page` nie da 404 ani 500. `count` — liczba wierszy znana już
    widokowi; oszczędza COUNT po zapytaniu z JOIN/GROUP BY.
    """
    paginator = Paginator(queryset, per_page)
    if count is not None:
        paginator.count = count  # cached_property — nadpisanie pomija zapytanie COUNT
    page = paginator.get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()
