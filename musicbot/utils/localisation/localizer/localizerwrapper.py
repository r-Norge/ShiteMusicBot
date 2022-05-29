class LocalizerWrapper:
    def __init__(self, localizer, lang=None, prefix=None):
        self.localizer = localizer
        self.lang = lang
        self.prefix = prefix

    def format_str(self, s, **kvpairs):
        return self.localizer.format_str(s, self.lang, self.prefix, **kvpairs)

    def format_dict(self, d, **kvpairs):
        return self.localizer.format_dict(d, self.lang, self.prefix, **kvpairs)

    def format_embed(self, embed, **kvpairs):
        return self.localizer.format_embed(embed, self.lang, self.prefix, **kvpairs)
