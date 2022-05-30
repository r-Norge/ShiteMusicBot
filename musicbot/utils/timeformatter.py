def format_ms(milliseconds):
    seconds = int(milliseconds)/1000
    formatted = ''
    hours, remainder = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        formatted += '%02d:' % hours
    formatted += '%02d:%02d' % (minutes, seconds)
    return formatted


def unformat_ms(formatted):
    hms = list(reversed([int(i) for i in formatted.split(':')]))
    seconds = hms[0]
    if len(hms) >= 2:
        seconds += hms[1] * 60
    if len(hms) == 3:
        seconds += hms[2] * 3600
    return seconds * 1000
