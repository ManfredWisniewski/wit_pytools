from eliot import add_destinations, FileDestination
from eliot.json import EliotJSONEncoder
import os
from datetime import datetime
import requests

class LokiDestination:
    def __init__(self, url, labels=None):
        self.url = url
        self.labels = labels or {"application": "witnctools"}
        
    def __call__(self, message):
        try:
            timestamp = int(datetime.now().timestamp() * 1e9)
            payload = {
                "streams": [{
                    "stream": self.labels,
                    "values": [[str(timestamp), str(message)]]
                }]
            }
            requests.post(f"{self.url}/loki/api/v1/push", json=payload)
        except Exception as e:
            print(f"Failed to send log to Loki: {e}")

class CustomEliotEncoder(EliotJSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

# Global variables
_log_file = None
_destination = None
_loki_destination = None

def log_setup(logdir=os.getcwd(), logfile="pytools.log", level="INFO"):
    """Setup Eliot logging with log level filtering"""
    global _log_file, _destination
    import eliot
    
    LEVELS = {"INFO": 10, "WARNING": 20, "ERROR": 30}
    selected_level = LEVELS.get(level.upper(), 10)

    def filtered_log_message(message, **fields):
        msg_level = fields.get("level", "INFO").upper()
        msg_value = LEVELS.get(msg_level, 10)
        if msg_value >= selected_level:
            eliot._orig_log_message(message, **fields)

    try:
        print(f"DEBUG: Setting up logging in directory: {logdir}")  # Debug print
        # Don't open a new file if one is already open
        if _log_file is not None:
            print("DEBUG: Log file already open")  # Debug print
            return
        # Create directory if it doesn't exist
        os.makedirs(logdir, exist_ok=True)
        log_path = os.path.join(logdir, logfile)
        print(f"DEBUG: Opening log file: {log_path}")  # Debug print
        _log_file = open(log_path, "a")
        _destination = FileDestination(file=_log_file, encoder=CustomEliotEncoder)
        add_destinations(_destination)
        # Monkey-patch eliot.log_message for level filtering
        if not hasattr(eliot, '_orig_log_message'):
            eliot._orig_log_message = eliot.log_message
        eliot.log_message = filtered_log_message
        print("DEBUG: Logging setup complete with level filter")  # Debug print
    except Exception as e:
        print(f"Error setting up logging: {e}")
        # If we failed to set up logging, make sure we clean up
        if _log_file:
            _log_file.close()
            _log_file = None

def log_close():
    """Close the log file if it's open"""
    global _log_file, _destination, _loki_destination
    if _log_file:
        _log_file.close()
        _log_file = None
    _destination = None
    _loki_destination = None
