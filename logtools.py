# $ pip install eliot eliot-tree requests
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