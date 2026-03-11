# Nextcloud Flow Manual Trigger Setup Guide

## Prerequisites
- Nextcloud instance with Flow app installed
- Admin account credentials
- Python 3 with requests library (`pip install requests`)

## Setup Steps

### 1. Enable Required Apps
```bash
# Enable Flow app (if not already enabled)
sudo -u www-data php occ app:enable workflow

# Enable webhook listeners for advanced triggering
sudo -u www-data php occ app:enable webhook_listeners

# Enable system tags (for tag operations)
sudo -u www-data php occ app:enable systemtags
```

### 2. Create App Password for API Access
1. Log into Nextcloud as admin
2. Go to Settings → Security → Devices & sessions
3. Click "Create new app password"
4. Give it a name (e.g., "flow-trigger-script")
5. Copy the generated password

### 3. Test Basic Connection
```bash
python nextcloud_flow_trigger.py \
  --url "https://your-nextcloud.com" \
  --username "admin" \
  --password "your-app-password" \
  --action list
```

### 4. Create a Test Workflow
```bash
python nextcloud_flow_trigger.py \
  --url "https://your-nextcloud.com" \
  --username "admin" \
  --password "your-app-password" \
  --action create \
  --workflow-name "Test File Trigger" \
  --event-type "OCP\\Files\\Events\\Node\\NodeCreatedEvent"
```

### 5. Trigger Workflow via File Creation
```bash
python nextcloud_flow_trigger.py \
  --url "https://your-nextcloud.com" \
  --username "admin" \
  --password "your-app-password" \
  --action trigger \
  --event-type "OCP\\Files\\Events\\Node\\NodeCreatedEvent" \
  --file-path "Documents/test_file.txt"
```

## Available Event Types

### File Events
- `OCP\\Files\\Events\\Node\\NodeCreatedEvent` - File created
- `OCP\\Files\\Events\\Node\\NodeWrittenEvent` - File modified
- `OCP\\Files\\Events\\Node\\NodeDeletedEvent` - File deleted
- `OCP\\Files\\Events\\Node\\NodeCopiedEvent` - File copied

### Tag Events
- `OCP\\SystemTag\\TagAssignedEvent` - Tag assigned
- `OCP\\SystemTag\\TagUnassignedEvent` - Tag removed

### Form Events
- `OCA\\Forms\\Events\\FormSubmittedEvent` - Form submitted

## Usage Examples

### List All Workflows
```bash
python nextcloud_flow_trigger.py \
  --url "https://cloud.example.com" \
  --username "admin" \
  --password "app-password" \
  --action list
```

### Trigger File Creation Event
```bash
python nextcloud_flow_trigger.py \
  --url "https://cloud.example.com" \
  --username "admin" \
  --password "app-password" \
  --action trigger \
  --event-type "OCP\\Files\\Events\\Node\\NodeCreatedEvent" \
  --file-path "path/to/your/file.txt"
```

### Create Simple Tag Assignment Workflow
```bash
python nextcloud_flow_trigger.py \
  --url "https://cloud.example.com" \
  --username "admin" \
  --password "app-password" \
  --action create \
  --workflow-name "Auto Tag PDFs" \
  --event-type "OCP\\Files\\Events\\Node\\NodeCreatedEvent"
```

## Integration with Existing Scripts

You can integrate this into your existing nctools.py:

```python
from nextcloud_flow_trigger import NextcloudFlowTrigger

def trigger_file_workflow(file_path):
    trigger = NextcloudFlowTrigger(
        base_url="https://your-nextcloud.com",
        username="admin", 
        password="your-app-password"
    )
    
    event_data = {"node": {"path": file_path}}
    return trigger.trigger_workflow_by_event(
        "OCP\\Files\\Events\\Node\\NodeCreatedEvent", 
        event_data
    )
```

## Troubleshooting

### Common Issues
1. **401 Unauthorized**: Check username/password or app password
2. **403 Forbidden**: Ensure admin has proper permissions
3. **404 Not Found**: Verify Flow app is enabled
4. **No workflow triggered**: Check if workflow is enabled and matches event type

### Debug Tips
- Use `--action list` to verify workflows exist
- Check Nextcloud logs for workflow errors
- Ensure file paths are relative to user directory
- Verify webhook_listeners app is enabled for advanced features

## Advanced Usage

### Custom Event Data
You can modify the script to send custom event data:

```python
# For tag assignment
event_data = {
    "objectIds": ["file123", "file456"],
    "tagIds": [1, 2, 3]
}
trigger.trigger_workflow_by_event("OCP\\SystemTag\\TagAssignedEvent", event_data)
```

### Batch Processing
Create a function to process multiple files:

```python
def batch_trigger_workflows(file_paths):
    trigger = NextcloudFlowTrigger(url, user, pass)
    for file_path in file_paths:
        event_data = {"node": {"path": file_path}}
        trigger.trigger_workflow_by_event(
            "OCP\\Files\\Events\\Node\\NodeCreatedEvent", 
            event_data
        )
```

This setup allows you to manually trigger workflows for files that were added via `files:scan`, solving your original problem.
