class CantScrollException(Exception):
    pass


class BasePaginator:
    def __init__(self, max_size=2000, max_units=10):
        self._pages = []
        self._current_page_size = 0
        self._current_units = 0
        self._max_size = max_size
        self._max_units = max_units

    def close_page(self):
        pass

    def add_page_indicator(self, localizer, localizer_str=None, **kvpairs):
        self.close_page()
        if localizer_str:
            for i, page in enumerate(self._pages, start=1):
                page.set_footer(text=localizer.format_str(localizer_str, _current=i,
                                                          _total=len(self._pages), **kvpairs))
        else:
            for i, page in enumerate(self._pages, start=1):
                page.set_footer(text=f"{i}/{len(self._pages)}")

    def append_paginator(self, paginator):
        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')
        self.close_page()
        for page in paginator.pages:
            self.pages.append(page)

    @property
    def pages(self):
        if self._current_page_size > 0:
            self.close_page()
        return self._pages
