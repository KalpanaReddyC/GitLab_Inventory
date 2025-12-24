import requests
import csv
import sys
import os
import json
from datetime import datetime
from pathlib import Path

def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# Initialize script
script_start_time = datetime.now()
log("Starting GitLab Groups Discovery script")

# =======================
# Configuration Section
# =======================
# Try to load GitLab token from environment variable first
log("Checking for GITLAB_TOKEN in environment variables...")
GITLAB_TOKEN = os.environ.get('GITLAB_TOKEN')
GITLAB_URL = os.environ.get('GITLAB_URL', 'https://gitlab.com')  # Default to gitlab.com

# If no environment variable, try to load from .token file
if not GITLAB_TOKEN:
    log("Environment variable not found. Checking for .token file...")
    # Build path to .token file in parent directory
    token_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.token')
    log(f"Looking for token file at: {token_file}")
    
    if os.path.exists(token_file):
        try:
            log("Token file found. Reading token...")
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                GITLAB_TOKEN = token_data.get('token')
                
                # Set environment variables for reuse by other scripts
                if GITLAB_TOKEN:
                    os.environ['GITLAB_TOKEN'] = GITLAB_TOKEN
                    log("Set GITLAB_TOKEN environment variable")
                
                # Check for custom GitLab URL
                if 'gitlab_url' in token_data:
                    GITLAB_URL = token_data['gitlab_url']
                    os.environ['GITLAB_URL'] = GITLAB_URL
                    log(f"Set GITLAB_URL environment variable to: {GITLAB_URL}")
                
                log(f"Token successfully loaded from file")
                    
        except json.JSONDecodeError as e:
            log(f"ERROR: Failed to parse JSON from .token file: {e}")
            sys.exit(1)
        except Exception as e:
            log(f"ERROR: Unexpected error reading .token file: {e}")
            sys.exit(1)
    else:
        log("ERROR: Token file not found")
        print("Please set GITLAB_TOKEN environment variable or create a .token file")
        sys.exit(1)
else:
    # If token came from environment, still try to read GitLab URL from .token file
    token_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.token')
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                
                # Check for custom GitLab URL if not already set
                if GITLAB_URL == 'https://gitlab.com' and 'gitlab_url' in token_data:
                    GITLAB_URL = token_data['gitlab_url']
                    os.environ['GITLAB_URL'] = GITLAB_URL
                    log(f"Set GITLAB_URL environment variable to: {GITLAB_URL}")
        except:
            pass

# Set up output file path in data subfolder
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data')

# Create data directory if it doesn't exist
if not os.path.exists(data_dir):
    log(f"Creating data directory: {data_dir}")
    os.makedirs(data_dir)

# Set output file path
OUTPUT_FILE = os.path.join(data_dir, 'gitlab-groups.csv')
log(f"Output file will be saved to: {OUTPUT_FILE}")

# Validate token exists
if not GITLAB_TOKEN:
    log("ERROR: No GitLab token found")
    sys.exit(1)

# Mask tokens for security in logs (show only first 8 and last 4 characters)
masked_token = f"{GITLAB_TOKEN[:8]}...{GITLAB_TOKEN[-4:]}" if len(GITLAB_TOKEN) > 12 else "***"
log(f"GitLab token found: {masked_token}")

# GitLab API configuration
base_url = f"{GITLAB_URL}/api/v4"
headers = {'PRIVATE-TOKEN': GITLAB_TOKEN}

log(f"Using GitLab instance: {GITLAB_URL}")

# =======================
# Utility Functions
# =======================
def bytes_to_mb(bytes_value):
    """Convert bytes to megabytes"""
    if bytes_value is None:
        return 0
    return round(bytes_value / (1024 * 1024), 2)

def fetch_all_groups(headers):
    """
    Fetch all groups from GitLab, handling pagination.
    Returns a list of all groups accessible to the authenticated user.
    """
    all_groups = []
    page = 1
    per_page = 50  # Reduced from 100 to avoid timeouts
    
    # Continue fetching pages until no more groups are found
    while True:
        log(f"Fetching groups page {page} (up to {per_page} per page)...")
        # Build API URL with parameters - removed all_available which can cause 500 errors
        groups_url = f"{base_url}/groups?per_page={per_page}&page={page}&statistics=true&owned=false"
        
        try:
            # Make API request with timeout
            response = requests.get(groups_url, headers=headers, timeout=30)
            
            # Handle non-200 responses
            if response.status_code != 200:
                log(f"ERROR: Failed to fetch groups. Status code: {response.status_code}")
                log(f"Response: {response.text[:500]}...")
                
                # Provide specific error messages based on status code
                if response.status_code == 401:
                    log("ERROR: Unauthorized - Check your token validity")
                elif response.status_code == 403:
                    log("ERROR: Forbidden - Check token permissions")
                
                return None
            
            # Parse JSON response
            groups = response.json()
            
            # Check if we've reached the end of pagination
            if not groups:
                log(f"No more groups found. Total groups: {len(all_groups)}")
                break
                
            # Add groups to our collection
            all_groups.extend(groups)
            log(f"Added {len(groups)} groups. Total so far: {len(all_groups)}")
            
            # Check if there are more pages using response headers
            if 'X-Next-Page' in response.headers and response.headers['X-Next-Page']:
                page += 1
            else:
                log(f"Reached last page. Total groups: {len(all_groups)}")
                break
                
        except requests.exceptions.Timeout:
            log(f"ERROR: Request timed out on page {page}")
            return None
        except requests.exceptions.ConnectionError as e:
            log(f"ERROR: Connection error: {e}")
            return None
        except Exception as e:
            log(f"ERROR: Unexpected error fetching groups: {e}")
            return None
    
    return all_groups

def get_group_project_count(group_id, headers):
    """
    Get the number of projects in a group (including subgroups).
    Uses HEAD request for efficiency.
    """
    try:
        projects_url = f"{base_url}/groups/{group_id}/projects?per_page=1&include_subgroups=true"
        response = requests.head(projects_url, headers=headers, timeout=10)
        
        if response.status_code == 200 and 'X-Total' in response.headers:
            return int(response.headers['X-Total'])
        
        # Fallback to GET request
        response = requests.get(projects_url, headers=headers, timeout=10)
        if response.status_code == 200:
            if 'X-Total' in response.headers:
                return int(response.headers['X-Total'])
            return len(response.json())
        else:
            return 0
    except Exception as e:
        log(f"    WARNING: Could not fetch project count: {e}")
        return 0

def get_subgroup_count(group_id, headers):
    """
    Get the number of direct subgroups in a group.
    Uses HEAD request for efficiency.
    """
    try:
        subgroups_url = f"{base_url}/groups/{group_id}/subgroups?per_page=1"
        response = requests.head(subgroups_url, headers=headers, timeout=10)
        
        if response.status_code == 200 and 'X-Total' in response.headers:
            return int(response.headers['X-Total'])
        
        # Fallback to GET request
        response = requests.get(subgroups_url, headers=headers, timeout=10)
        if response.status_code == 200:
            if 'X-Total' in response.headers:
                return int(response.headers['X-Total'])
            return len(response.json())
        else:
            return 0
    except Exception as e:
        log(f"    WARNING: Could not fetch subgroup count: {e}")
        return 0

def get_group_member_count(group_id, headers):
    """
    Get the number of members in a group.
    Uses HEAD request for efficiency.
    """
    try:
        members_url = f"{base_url}/groups/{group_id}/members?per_page=1"
        response = requests.head(members_url, headers=headers, timeout=10)
        
        if response.status_code == 200 and 'X-Total' in response.headers:
            return int(response.headers['X-Total'])
        
        # Fallback to GET request
        response = requests.get(members_url, headers=headers, timeout=10)
        if response.status_code == 200:
            if 'X-Total' in response.headers:
                return int(response.headers['X-Total'])
            return len(response.json())
        else:
            return 0
    except Exception as e:
        log(f"    WARNING: Could not fetch member count: {e}")
        return 0

# =======================
# Main Execution
# =======================
if __name__ == "__main__":
    # Fetch all groups from GitLab
    log(f"Fetching all groups from GitLab...")
    groups = fetch_all_groups(headers)

    # Handle fetch failures
    if groups is None:
        log("ERROR: Failed to fetch groups")
        sys.exit(1)

    log(f"Successfully fetched {len(groups)} groups from GitLab")

    # Handle empty results
    if not groups:
        log("WARNING: No groups found")
        sys.exit(0)

    # Initialize data collection
    stats = []
    failed_groups = []

    # Process each group to collect detailed statistics
    log("Collecting detailed statistics for each group...")
    for idx, group in enumerate(groups):
        group_id = group['id']
        group_name = group['name']
        group_path = group['full_path']
        
        # Show progress every 10 groups
        if (idx + 1) % 10 == 0:
            log(f"Processing group {idx + 1}/{len(groups)}...")
        
        try:
            log(f"Processing: {group_name} ({group_path})")
            
            # Get project count (including subgroups)
            log(f"  Fetching project count...")
            project_count = get_group_project_count(group_id, headers)
            log(f"  Found {project_count} projects")
            
            # Get subgroup count
            log(f"  Fetching subgroup count...")
            subgroup_count = get_subgroup_count(group_id, headers)
            log(f"  Found {subgroup_count} subgroups")
            
            # Get member count
            log(f"  Fetching member count...")
            member_count = get_group_member_count(group_id, headers)
            log(f"  Found {member_count} members")
            
            # Extract storage statistics if available
            statistics = group.get('statistics', {})
            storage_size = statistics.get('storage_size', 0)
            repository_size = statistics.get('repository_size', 0)
            
            # Build complete group statistics dictionary
            group_stats = {
                'id': group['id'],
                'name': group['name'],
                'path': group['path'],
                'full_path': group['full_path'],
                'description': group.get('description', ''),
                'visibility': group.get('visibility', 'N/A'),
                'project_count': project_count,
                'subgroup_count': subgroup_count,
                'member_count': member_count,
                'storage_size_mb': bytes_to_mb(storage_size),
                'repository_size_mb': bytes_to_mb(repository_size),
                'created_at': group.get('created_at', 'N/A'),
                'parent_id': group.get('parent_id', ''),
                'web_url': group.get('web_url', 'N/A')
            }
            
            stats.append(group_stats)
            
        except requests.exceptions.Timeout:
            log(f"  ERROR: Timeout while processing group: {group_name}")
            failed_groups.append(group_name)
            continue
        except Exception as e:
            log(f"  ERROR: Failed to process group {group_name}: {e}")
            failed_groups.append(group_name)
            continue

    # Summary of processing results
    log(f"\nCompleted processing {len(stats)} groups successfully")
    if failed_groups:
        log(f"Failed to process {len(failed_groups)} groups: {failed_groups}")

    # Write results to CSV file
    log(f"Writing results to {OUTPUT_FILE}...")
    if stats:
        # Define explicit field order for CSV output
        fieldnames = [
            'id', 'name', 'path', 'full_path', 'description', 'visibility',
            'project_count', 'subgroup_count', 'member_count',
            'storage_size_mb', 'repository_size_mb',
            'created_at', 'parent_id', 'web_url'
        ]
        
        # Write CSV with headers
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stats)
        
        log(f"Successfully wrote {len(stats)} group records to {OUTPUT_FILE}")
    else:
        log("No data to write to CSV file")

    # Display environment variables that were set
    log("\nEnvironment variables set for use by other scripts:")
    log(f"GITLAB_TOKEN: {'Set' if os.environ.get('GITLAB_TOKEN') else 'Not set'}")
    log(f"GITLAB_URL: {os.environ.get('GITLAB_URL', 'Not set')}")
    
# Calculate and log execution time
script_end_time = datetime.now()
execution_time = script_end_time - script_start_time

# Convert to hours and minutes
total_seconds = int(execution_time.total_seconds())
hours = total_seconds // 3600
minutes = (total_seconds % 3600) // 60
seconds = total_seconds % 60

log("\n" + "="*50)
if hours > 0:
    log(f"Script execution time: {hours} hours, {minutes} minutes, {seconds} seconds")
elif minutes > 0:
    log(f"Script execution time: {minutes} minutes, {seconds} seconds")
else:
    log(f"Script execution time: {seconds} seconds")
log("="*50)

log("Script completed")
