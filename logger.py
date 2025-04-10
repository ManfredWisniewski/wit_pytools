from eliot import to_file, FileDestination
from eliot.json import EliotJSONEncoder
import os
import json
from datetime import datetime

class CustomEliotEncoder(EliotJSONEncoder):
    def default(self, obj):
        result = super().default(obj)
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return result

def format_message(message):
    """Format the Eliot message to our preferences"""
    try:
        # Convert timestamp to readable format
        if 'timestamp' in message:
            timestamp = datetime.fromtimestamp(message['timestamp'])
            message['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Remove task_uuid
        message.pop('task_uuid', None)
        
        formatted = json.dumps(message, cls=CustomEliotEncoder)
        print(f"DEBUG: Formatted log message: {formatted}")  # Debug print
        return formatted
    except Exception as e:
        print(f"DEBUG: Error formatting message: {e}")
        return json.dumps(message)  # Fallback to basic formatting

# Global log file handle
_log_file = None
_destination = None

def log_setup(logdir=os.getcwd()):
    """Setup Eliot logging with the given configuration"""
    global _log_file, _destination
    
    try:
        print(f"DEBUG: Setting up logging in directory: {logdir}")  # Debug print
        
        # Don't open a new file if one is already open
        if _log_file is not None:
            print("DEBUG: Log file already open")  # Debug print
            return
            
        # Create directory if it doesn't exist
        os.makedirs(logdir, exist_ok=True)
        
        log_path = os.path.join(logdir, "mailsort.log")
        print(f"DEBUG: Opening log file: {log_path}")  # Debug print
        _log_file = open(log_path, "a")
        _destination = FileDestination(file=_log_file, encoder=CustomEliotEncoder)
        to_file(_log_file, encoder=CustomEliotEncoder)
        print("DEBUG: Logging setup complete")  # Debug print
    except Exception as e:
        print(f"Error setting up log file: {e}")
        # If we failed to set up logging, make sure we clean up
        if _log_file:
            _log_file.close()
            _log_file = None

def log_close():
    """Close the log file if it's open"""
    global _log_file, _destination
    if _log_file:
        _log_file.close()
        _log_file = None
    _destination = None
