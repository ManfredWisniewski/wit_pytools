#   prepare strings to be used correctly in regex expressions (escape special characters)
def prepregex(ostring):
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    nstring = ostring.translate(mapping)
    return nstring


def bitrate_to_bps(value):
    """Convert bitrate strings like '64k' or '0.128m' to bits per second."""
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    try:
        if text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        if text.endswith("m"):
            return int(float(text[:-1]) * 1000000)
        return int(float(text))
    except (ValueError, TypeError):
        return None


def bps_to_bitrate(value):
    """Convert bits-per-second integer into a bitrate string (e.g. '64k')."""
    if value is None:
        return None

    try:
        bps = int(value)
    except (TypeError, ValueError):
        return None

    if bps <= 0:
        return None

    if bps % 1000 == 0:
        kbps = bps // 1000
        return f"{kbps}k"

    return str(bps)