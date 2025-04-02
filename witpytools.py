def dryprint(dryrun, msg, content=''):
    if dryrun:
        # Make message exactly 15 characters - truncate if longer, right-align if shorter
        if len(msg) > 12:
            formatted_msg = msg[:12]
        else:
            formatted_msg = msg.rjust(12)
        print(formatted_msg + ': ' + content)
