#!/usr/bin/env python3
"""
Script to manually trigger Nextcloud Flow workflows
"""

import requests
import json
import sys
import argparse
from typing import Dict, Any, Optional

class NextcloudFlowTrigger:
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize Nextcloud Flow trigger
        
        Args:
            base_url: Nextcloud base URL (e.g., 'https://cloud.example.com')
            username: Admin username
            password: Admin password or app password
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'OCS-APIRequest': 'true',
            'Content-Type': 'application/json'
        })
    
    def list_workflows(self) -> Dict[str, Any]:
        """List all existing workflows"""
        url = f"{self.base_url}/ocs/v2.php/apps/workflowengine/api/v1/workflows/global"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse OCS response
            ocs_data = response.json()
            if ocs_data.get('ocs', {}).get('meta', {}).get('status') == 'ok':
                return ocs_data['ocs']['data']
            else:
                raise Exception(f"API Error: {ocs_data.get('ocs', {}).get('meta', {}).get('message')}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")
    
    def trigger_workflow_by_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Trigger a workflow by simulating an event
        
        Args:
            event_type: Event type (e.g., 'OCP\\Files\\Events\\Node\\NodeCreatedEvent')
            event_data: Event data payload
        
        Returns:
            True if successful, False otherwise
        """
        # Note: This is a workaround since direct trigger API doesn't exist
        # We'll use the webhook_listeners app if available, or create a file operation
        
        if event_type == 'OCP\\Files\\Events\\Node\\NodeCreatedEvent':
            return self._trigger_file_created_event(event_data)
        elif event_type == 'OCP\\SystemTag\\TagAssignedEvent':
            return self._trigger_tag_assigned_event(event_data)
        else:
            print(f"Event type {event_type} not yet implemented")
            return False
    
    def _trigger_file_created_event(self, event_data: Dict[str, Any]) -> bool:
        """Trigger file created event by touching a file via WebDAV"""
        try:
            file_path = event_data.get('node', {}).get('path', '')
            if not file_path:
                print("Error: File path required in event_data.node.path")
                return False
            
            # Use WebDAV to touch the file, which should trigger workflows
            webdav_url = f"{self.base_url}/remote.php/dav/files/{self.session.auth[0]}/{file_path.lstrip('/')}"
            
            # Create/empty file to trigger NodeCreatedEvent
            response = self.session.put(webdav_url, data='')
            response.raise_for_status()
            
            print(f"Triggered file creation event for: {file_path}")
            return True
            
        except Exception as e:
            print(f"Failed to trigger file created event: {e}")
            return False
    
    def _trigger_tag_assigned_event(self, event_data: Dict[str, Any]) -> bool:
        """Trigger tag assignment via OCS API"""
        try:
            object_ids = event_data.get('objectIds', [])
            tag_ids = event_data.get('tagIds', [])
            
            if not object_ids or not tag_ids:
                print("Error: objectIds and tagIds required in event_data")
                return False
            
            # Use system tags API to assign tags
            for object_id in object_ids:
                for tag_id in tag_ids:
                    url = f"{self.base_url}/ocs/v2.php/apps/systemtags/api/v2/tags/{tag_id}/objects"
                    tag_data = {"objectType": "files", "objectId": object_id}
                    
                    response = self.session.post(url, json=tag_data)
                    response.raise_for_status()
            
            print(f"Triggered tag assignment for objects: {object_ids}")
            return True
            
        except Exception as e:
            print(f"Failed to trigger tag assignment event: {e}")
            return False
    
    def create_manual_trigger_workflow(self, name: str, event_type: str, operation: str) -> Dict[str, Any]:
        """
        Create a simple workflow that can be manually triggered
        
        Args:
            name: Workflow name
            event_type: Event type to listen for
            operation: Operation to perform (e.g., 'tag', 'move', 'delete')
        
        Returns:
            Created workflow data
        """
        workflow_data = {
            "name": name,
            "enabled": True,
            "entity": "OCA\\WorkflowEngine\\Entity\\File",
            "event": event_type,
            "operations": [
                {
                    "class": f"OCA\\WorkflowEngine\\Operation\\{operation.capitalize()}",
                    "name": operation,
                    "checks": [],
                    "configuration": {}
                }
            ]
        }
        
        url = f"{self.base_url}/ocs/v2.php/apps/workflowengine/api/v1/workflows/global"
        
        try:
            response = self.session.post(url, json=workflow_data)
            response.raise_for_status()
            
            ocs_data = response.json()
            if ocs_data.get('ocs', {}).get('meta', {}).get('status') == 'ok':
                return ocs_data['ocs']['data']
            else:
                raise Exception(f"API Error: {ocs_data.get('ocs', {}).get('meta', {}).get('message')}")
                
        except Exception as e:
            raise Exception(f"Failed to create workflow: {e}")

def main():
    parser = argparse.ArgumentParser(description='Trigger Nextcloud Flow workflows')
    parser.add_argument('--url', required=True, help='Nextcloud base URL')
    parser.add_argument('--username', required=True, help='Admin username')
    parser.add_argument('--password', required=True, help='Admin password or app password')
    parser.add_argument('--action', choices=['list', 'trigger', 'create'], required=True, help='Action to perform')
    parser.add_argument('--event-type', help='Event type to trigger')
    parser.add_argument('--file-path', help='File path for file events')
    parser.add_argument('--workflow-name', help='Name for new workflow')
    
    args = parser.parse_args()
    
    trigger = NextcloudFlowTrigger(args.url, args.username, args.password)
    
    try:
        if args.action == 'list':
            workflows = trigger.list_workflows()
            print("Existing workflows:")
            for wf in workflows:
                print(f"  ID: {wf['id']}, Name: {wf['name']}, Event: {wf['event']}")
        
        elif args.action == 'trigger':
            if not args.event_type:
                print("Error: --event-type required for trigger action")
                sys.exit(1)
            
            if args.event_type == 'OCP\\Files\\Events\\Node\\NodeCreatedEvent':
                if not args.file_path:
                    print("Error: --file-path required for file events")
                    sys.exit(1)
                
                event_data = {
                    "node": {"path": args.file_path}
                }
            else:
                event_data = {}
            
            success = trigger.trigger_workflow_by_event(args.event_type, event_data)
            if success:
                print("Workflow triggered successfully")
            else:
                print("Failed to trigger workflow")
                sys.exit(1)
        
        elif args.action == 'create':
            if not args.workflow_name or not args.event_type:
                print("Error: --workflow-name and --event-type required for create action")
                sys.exit(1)
            
            workflow = trigger.create_manual_trigger_workflow(args.workflow_name, args.event_type, 'tag')
            print(f"Created workflow: {workflow}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
