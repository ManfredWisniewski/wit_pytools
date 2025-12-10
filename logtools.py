# $ pip install eliot eliot-tree requests
import os
import requests, argparse
from eliot import start_action, to_file, log_message


def check_links(urls):
    to_file(open("linkcheck.log", "a"))
    with start_action(action_type="check_links", urls=urls):
        for url in urls:
            try:
                with start_action(action_type="download", url=url):
                    response = requests.get(url)
                    response.raise_for_status()
            except Exception as e:
                raise ValueError(str(e))

#try:
#    check_links(["http://eliot.readthedocs.io", "http://nosuchurl"])
#except ValueError:
#    print("Not all links were valid.")


def checkargs():
    to_file(open("argcheck.log", "a"))
    parser = argparse.ArgumentParser(description='Process some arguments.')
    parser.add_argument('--file', type=str, help='Name of the file')
    parser.add_argument('--age', type=int, help='Age of the person')
    
    args = parser.parse_args()

    with start_action(action_type="LOG ARGUMENTS"):
        log_message(message_type="argument_logging", file=args.file, age=args.age)

try:
    checkargs()
except ValueError:
    print("Error.")


def send_gotify_alert(message, title="mailsort_nightly: leftover .eml files", priority=None, url=None, token=None):
    """Send a Gotify notification.

    Uses GOTIFY_URL, GOTIFY_TOKEN and GOTIFY_PRIORITY environment variables
    by default. Returns True on success, False if config is missing or
    if the request fails.
    """

    gotify_url = url or os.environ.get("GOTIFY_URL", "").rstrip("/")
    gotify_token = token or os.environ.get("GOTIFY_TOKEN", "")
    if not gotify_token:
        token_path = os.path.expanduser("~/.gotify_token")
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                gotify_token = f.read().strip()
        except Exception:
            gotify_token = ""

    if priority is None:
        try:
            priority = int(os.environ.get("GOTIFY_PRIORITY", "5"))
        except ValueError:
            priority = 5

    if not gotify_url or not gotify_token:
        return False

    try:
        resp = requests.post(
            f"{gotify_url}/message?token={gotify_token}",
            data={
                "title": title,
                "message": message,
                "priority": priority,
            },
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False