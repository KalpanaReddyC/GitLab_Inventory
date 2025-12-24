import requests
import csv
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

# Initialize script
script_start_time = datetime.now()
log("Starting GitLab Project Details script")

# =======================
# Configuration Section
# =======================
# Try to load GitLab token from environment variable first
log("Checking for GITLAB_TOKEN in environment variables...")
GITLAB_TOKEN = os.environ.get('GITLAB_TOKEN')
GITLAB_URL = os.environ.get('GITLAB_URL', 'https://gitlab.com')  # Default to gitlab.com

# GitHub token for potential future integration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

# Project filter configuration
PROJECT_LIST_FILE = None
MIGRATE_REPO_VALUES = []

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
                
                # Check for GitHub token in the same file
                if 'github_token' in token_data:
                    GITHUB_TOKEN = token_data['github_token']
                    os.environ['GITHUB_TOKEN'] = GITHUB_TOKEN
                    log("Set GITHUB_TOKEN environment variable")
                
                # Check for custom GitLab URL
                if 'gitlab_url' in token_data:
                    GITLAB_URL = token_data['gitlab_url']
                    os.environ['GITLAB_URL'] = GITLAB_URL
                    log(f"Set GITLAB_URL environment variable to: {GITLAB_URL}")
                
                # Check for project list file configuration
                if 'project_list_file' in token_data:
                    PROJECT_LIST_FILE = token_data['project_list_file']
                    log(f"Project list file configured: {PROJECT_LIST_FILE}")
                
                # Check for migrate repo values to filter on
                if 'migrate_repo_values' in token_data:
                    if isinstance(token_data['migrate_repo_values'], list):
                        MIGRATE_REPO_VALUES = token_data['migrate_repo_values']
                    elif isinstance(token_data['migrate_repo_values'], str):
                        MIGRATE_REPO_VALUES = [token_data['migrate_repo_values']]
                    log(f"Migrate repo values to filter: {MIGRATE_REPO_VALUES}")
                else:
                    # Default to 'Migrate' if not specified
                    MIGRATE_REPO_VALUES = ['Migrate']
                    log("Using default migrate repo value: ['Migrate']")
                
                log(f"Token successfully loaded from file")
                    
        except json.JSONDecodeError as e:
            log(f"ERROR: Failed to parse JSON from .token file: {e}")
            sys.exit(1)
        except KeyError as e:
            log(f"ERROR: Required key not found in .token file: {e}")
            sys.exit(1)
        except Exception as e:
            log(f"ERROR: Unexpected error reading .token file: {e}")
            sys.exit(1)
    else:
        log("ERROR: Token file not found")
        print("Please set GITLAB_TOKEN environment variable or create a .token file")
        sys.exit(1)
else:
    # If token came from environment, still try to read other values from .token file
    token_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.token')
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                
                # Check for GitHub token if not already set
                if not GITHUB_TOKEN and 'github_token' in token_data:
                    GITHUB_TOKEN = token_data['github_token']
                    os.environ['GITHUB_TOKEN'] = GITHUB_TOKEN
                    log("Set GITHUB_TOKEN environment variable")
                
                # Check for custom GitLab URL if not already set
                if GITLAB_URL == 'https://gitlab.com' and 'gitlab_url' in token_data:
                    GITLAB_URL = token_data['gitlab_url']
                    os.environ['GITLAB_URL'] = GITLAB_URL
                    log(f"Set GITLAB_URL environment variable to: {GITLAB_URL}")
                
                # Check for project list file configuration
                if 'project_list_file' in token_data:
                    PROJECT_LIST_FILE = token_data['project_list_file']
                    log(f"Project list file configured: {PROJECT_LIST_FILE}")
                
                # Check for migrate repo values
                if 'migrate_repo_values' in token_data:
                    if isinstance(token_data['migrate_repo_values'], list):
                        MIGRATE_REPO_VALUES = token_data['migrate_repo_values']
                    elif isinstance(token_data['migrate_repo_values'], str):
                        MIGRATE_REPO_VALUES = [token_data['migrate_repo_values']]
                else:
                    MIGRATE_REPO_VALUES = ['Migrate']
                
                log(f"Additional settings loaded from .token file")
            # If we can't read the file, use defaults
            if not MIGRATE_REPO_VALUES:
                MIGRATE_REPO_VALUES = ['Migrate']
            log("Could not read additional settings from .token file")

# Set up output file path in data subfolder
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data')

# Create data directory if it doesn't exist
if not os.path.exists(data_dir):
    log(f"Creating data directory: {data_dir}")
    os.makedirs(data_dir)

# Set output file path
OUTPUT_FILE = os.path.join(data_dir, 'gitlab-stats.csv')
log(f"Output file will be saved to: {OUTPUT_FILE}")

# Validate token exists
if not GITLAB_TOKEN:
    log("ERROR: No GitLab token found")
    sys.exit(1)

# Mask tokens for security in logs (show only first 8 and last 4 characters)
masked_token = f"{GITLAB_TOKEN[:8]}...{GITLAB_TOKEN[-4:]}" if len(GITLAB_TOKEN) > 12 else "***"
log(f"GitLab token found: {masked_token}")

# Display GitHub token status if available
if GITHUB_TOKEN:
    masked_gh_token = f"{GITHUB_TOKEN[:8]}...{GITHUB_TOKEN[-4:]}" if len(GITHUB_TOKEN) > 12 else "***"
    log(f"GitHub token also available: {masked_gh_token}")
else:
    log("No GitHub token found (optional)")

# GitLab API configuration
base_url = f"{GITLAB_URL}/api/v4"
headers = {'PRIVATE-TOKEN': GITLAB_TOKEN}

log(f"Using GitLab instance: {GITLAB_URL}")

# =======================
# Project Filtering
# =======================
def load_project_filter():
    """
    Load project filter from CSV file if configured.
    Returns a set of project names to process, or None to process all projects.
    """
    if not PROJECT_LIST_FILE:
        log("No project list file configured. Will process all projects in group.")
        return None
    
    # Build path to project list file (always in data subfolder)
    project_list_path = os.path.join(data_dir, PROJECT_LIST_FILE)
    
    if not os.path.exists(project_list_path):
        log(f"WARNING: Project list file not found at: {project_list_path}")
        log("Falling back to processing all projects in group.")
        return None
    
    try:
        log(f"Loading project list from: {project_list_path}")
        projects_to_migrate = set()
        
        with open(project_list_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Check if required columns exist
            if 'Migrate Repo' not in reader.fieldnames or 'Name' not in reader.fieldnames:
                log("ERROR: Required columns 'Name' or 'Migrate Repo' not found in CSV")
                log("Falling back to processing all projects in group.")
                return None
            
            # Filter projects based on Migrate Repo column
            for row in reader:
                migrate_value = row.get('Migrate Repo', '').strip()
                project_name = row.get('Name', '').strip()
                
                # Check if migrate value matches any of our filter values
                if migrate_value in MIGRATE_REPO_VALUES and project_name:
                    projects_to_migrate.add(project_name)
                    log(f"  Added '{project_name}' to filter (Migrate Repo: {migrate_value})")
        
        log(f"Loaded {len(projects_to_migrate)} projects to process from filter file")
        
        if len(projects_to_migrate) == 0:
            log(f"WARNING: No projects matched the filter values: {MIGRATE_REPO_VALUES}")
            log("Falling back to processing all projects in group.")
            return None
        
        return projects_to_migrate
        
    except Exception as e:
        log(f"ERROR: Failed to load project filter file: {e}")
        log("Falling back to processing all projects in group.")
        return None

# Load project filter
project_filter = load_project_filter()

# =======================
# Utility Functions
# =======================
def bytes_to_mb(bytes_value):
    """Convert bytes to megabytes"""
    if bytes_value is None:
        return 0
    return round(bytes_value / (1024 * 1024), 2)

def should_process_project(project, project_filter):
    """
    Determine if a project should be processed based on the filter.
    If filter is None, all projects are processed.
    """
    if project_filter is None:
        return True
    
    # Check various name fields that might match
    project_name = project.get('name', '')
    project_path = project.get('path', '')
    
    # Check if project name or path matches any in our filter
    return project_name in project_filter or project_path in project_filter

def fetch_all_groups(headers):
    """
    Fetch all groups from GitLab, handling pagination.
    Returns a list of all groups accessible to the authenticated user.
    """
    all_groups = []
    page = 1
    per_page = 50
    
    while True:
        log(f"Fetching groups page {page} (up to {per_page} per page)...")
        groups_url = f"{base_url}/groups?per_page={per_page}&page={page}&statistics=true&owned=false"
        
        try:
            response = requests.get(groups_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                log(f"ERROR: Failed to fetch groups. Status code: {response.status_code}")
                return None
            
            groups = response.json()
            
            if not groups:
                log(f"No more groups found. Total groups: {len(all_groups)}")
                break
                
            all_groups.extend(groups)
            log(f"Added {len(groups)} groups. Total so far: {len(all_groups)}")
            
            if 'X-Next-Page' in response.headers and response.headers['X-Next-Page']:
                page += 1
            else:
                log(f"Reached last page. Total groups: {len(all_groups)}")
                break
                
        except Exception as e:
            log(f"ERROR: Unexpected error fetching groups: {e}")
            return None
    
    return all_groups

def fetch_all_projects(group_name, headers):
    """
    Fetch all projects from a GitLab group, handling pagination.
    Returns a list of all projects in the group and subgroups.
    """
    all_projects = []
    page = 1
    per_page = 100
    
    # Continue fetching pages until no more projects are found
    while True:
        log(f"Fetching projects page {page} (up to {per_page} per page)...")
        # Build API URL with parameters for subgroups and statistics
        group_projects_url = f"{base_url}/groups/{group_name}/projects?per_page={per_page}&page={page}&include_subgroups=true&statistics=true"
        
        try:
            # Make API request with timeout
            response = requests.get(group_projects_url, headers=headers, timeout=30)
            
            # Handle non-200 responses
            if response.status_code != 200:
                log(f"ERROR: Failed to fetch projects. Status code: {response.status_code}")
                log(f"Response: {response.text[:500]}...")
                
                # Provide specific error messages based on status code
                if response.status_code == 401:
                    log("ERROR: Unauthorized - Check your token validity")
                elif response.status_code == 403:
                    log("ERROR: Forbidden - Check token permissions")
                elif response.status_code == 404:
                    log(f"ERROR: Group '{group_name}' not found")
                
                return None
            
            # Parse JSON response
            projects = response.json()
            
            # Check if we've reached the end of pagination
            if not projects:
                log(f"No more projects found. Total projects: {len(all_projects)}")
                break
                
            # Add projects to our collection
            all_projects.extend(projects)
            log(f"Added {len(projects)} projects. Total so far: {len(all_projects)}")
            
            # Check if there are more pages using response headers
            if 'X-Next-Page' in response.headers and response.headers['X-Next-Page']:
                page += 1
            else:
                log(f"Reached last page. Total projects: {len(all_projects)}")
                break
                
        except requests.exceptions.Timeout:
            log(f"ERROR: Request timed out on page {page}")
            return None
        except requests.exceptions.ConnectionError as e:
            log(f"ERROR: Connection error: {e}")
            return None
        except Exception as e:
            log(f"ERROR: Unexpected error fetching projects: {e}")
            return None
    
    return all_projects

def get_branch_count(project_id, headers):
    """
    Get the number of branches in a project.
    Uses HEAD request first for efficiency, falls back to GET if needed.
    """
    try:
        # Try HEAD request first (more efficient)
        branches_url = f"{base_url}/projects/{project_id}/repository/branches?per_page=1"
        response = requests.head(branches_url, headers=headers, timeout=10)
        
        # If HEAD request works and has X-Total header, use it
        if response.status_code == 200 and 'X-Total' in response.headers:
            return int(response.headers['X-Total'])
        
        # Fall back to GET request if HEAD didn't work
        response = requests.get(branches_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Prefer X-Total header if available
            if 'X-Total' in response.headers:
                return int(response.headers['X-Total'])
            # Fallback: count branches in response (only first page, may be inaccurate for repos with >100 branches)
            return len(response.json())
        else:
            return 0
    except Exception as e:
        log(f"    WARNING: Could not fetch branch count: {e}")
        return 0

def get_repository_file_count(project_id, headers):
    """
    Get the actual total number of files in the repository.
    Handles large repositories with special logic and pagination.
    """
    try:
        # First, get project info to determine repository size and default branch
        project_url = f"{base_url}/projects/{project_id}"
        project_response = requests.get(project_url, headers=headers, timeout=10)
        
        if project_response.status_code != 200:
            log(f"    WARNING: Could not fetch project info (status: {project_response.status_code})")
            return 0
        
        project_info = project_response.json()
        default_branch = project_info.get('default_branch')
        
        # Check repository size to determine counting strategy
        repo_size = project_info.get('statistics', {}).get('repository_size', 0)
        repo_size_mb = repo_size / (1024 * 1024)
        
        # Log if this is a large repository
        if repo_size_mb > 10000:  # If repo is larger than 10GB
            log(f"    Large repository detected ({repo_size_mb:.2f} MB). Using optimized counting method...")
        
        # Handle empty repositories
        if not default_branch:
            log(f"    WARNING: No default branch found - repository might be empty")
            return 0
            
        log(f"    Using default branch: {default_branch}")
        
        # Special handling for very large repositories (>10GB)
        if repo_size_mb > 10000:
            try:
                # Verify repository is accessible
                commits_url = f"{base_url}/projects/{project_id}/repository/commits?ref={default_branch}&per_page=1"
                commits_response = requests.head(commits_url, headers=headers, timeout=10)
                
                if commits_response.status_code == 200:
                    # Try to use search API for file counting (more efficient for large repos)
                    search_url = f"{base_url}/projects/{project_id}/search?scope=blobs&search=*"
                    search_response = requests.head(search_url, headers=headers, timeout=10)
                    
                    if search_response.status_code == 200 and 'X-Total' in search_response.headers:
                        file_count = int(search_response.headers.get('X-Total', 0))
                        log(f"    File count from search API: {file_count}")
                        if file_count > 0:
                            return file_count
                    
                    # If search doesn't work, log and return 0
                    log(f"    Very large repository - exact file count unavailable")
                    return 0
                    
            except Exception as e:
                log(f"    Error with alternative counting method: {e}")
        
        # Standard counting method for normal-sized repositories
        tree_url = f"{base_url}/projects/{project_id}/repository/tree"
        
        all_files = []
        page = 1
        per_page = 100
        max_pages = 50  # Limit to prevent timeout on large repos
        
        # Paginate through repository tree
        while page <= max_pages:
            params = {
                'recursive': 'true',  # Get all files recursively
                'per_page': per_page,
                'page': page,
                'ref': default_branch
            }
            
            try:
                response = requests.get(tree_url, headers=headers, params=params, timeout=30)
                
                # Handle different response codes
                if response.status_code == 404:
                    log(f"    WARNING: Repository tree not found - repository might be empty")
                    return 0
                elif response.status_code != 200:
                    log(f"    WARNING: Could not fetch repository tree (status: {response.status_code})")
                    break
                
                items = response.json()
                
                # Check if we've reached the end of results
                if not items:
                    break
                
                # Count only files (blobs), not directories
                files_on_page = [item for item in items if item.get('type') == 'blob']
                all_files.extend(files_on_page)
                
                log(f"    Page {page}: Found {len(files_on_page)} files (total so far: {len(all_files)})")
                
                # Check if there are more pages than we can process
                total_pages_header = response.headers.get('X-Total-Pages')
                if total_pages_header:
                    total_pages = int(total_pages_header)
                    if page == 1:
                        log(f"    Total pages available: {total_pages}")
                    if total_pages > max_pages:
                        log(f"    WARNING: Repository has {total_pages} pages of files. Will process first {max_pages} pages.")
                        # Estimate total files based on current sample
                        if len(all_files) > 0:
                            estimated_total = int((len(all_files) / page) * total_pages)
                            log(f"    Estimated total files: ~{estimated_total}")
                
                # Check if there's a next page
                next_page = response.headers.get('X-Next-Page')
                if not next_page:
                    break
                    
                page += 1
                
            except requests.exceptions.Timeout:
                log(f"    WARNING: Timeout on page {page}")
                break
            except Exception as e:
                log(f"    WARNING: Error on page {page}: {e}")
                break
        
        file_count = len(all_files)
        
        # Log final count with context
        if page > max_pages:
            log(f"    Large repository detected. Counted {file_count} files in first {max_pages} pages (minimum count).")
        else:
            log(f"    Total files counted: {file_count}")
        
        return file_count
        
    except Exception as e:
        log(f"    ERROR: Failed to count repository files: {type(e).__name__}: {e}")
        return 0

def get_repository_stats_via_api(project_id, headers):
    """
    Get comprehensive repository statistics using multiple API endpoints.
    Returns a dictionary with various repository metrics.
    """
    # Initialize statistics dictionary with default values
    stats = {
        'file_count': 0,
        'repository_size': 0,
        'storage_size': 0,
        'commit_count': 0,
        'branch_count': 0,
        'object_count': 0,
        'all_branches_file_count': 0,
        'has_large_file': False,
        'exceeds_6gb': False,
        'exceeds_2gb': False,
        'has_pipeline': False  # Add pipeline detection
    }
    
    try:
        # Get project details with full statistics
        project_url = f"{base_url}/projects/{project_id}?statistics=true&license=true"
        response = requests.get(project_url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            project_data = response.json()
            
            # Extract statistics from API response
            statistics = project_data.get('statistics', {})
            if statistics:
                stats['repository_size'] = statistics.get('repository_size', 0)
                stats['storage_size'] = statistics.get('storage_size', 0)
                stats['commit_count'] = statistics.get('commit_count', 0)
                
                # Check size thresholds using total storage size (not just repository)
                storage_size_bytes = stats['storage_size']
                stats['exceeds_2gb'] = storage_size_bytes > (2 * 1024 * 1024 * 1024)  # 2GB in bytes
                stats['exceeds_6gb'] = storage_size_bytes > (6 * 1024 * 1024 * 1024)  # 6GB in bytes
                
                log(f"    API Statistics - Repository size: {stats['repository_size']} bytes, "
                    f"Storage size: {stats['storage_size']} bytes, "
                    f"Commit count: {stats['commit_count']}")
        
        # Get detailed file count for default branch
        stats['file_count'] = get_repository_file_count(project_id, headers)
        
        # Get branch count
        stats['branch_count'] = get_branch_count(project_id, headers)
        
        # Check for pipeline configuration
        stats['has_pipeline'] = check_for_pipeline_config(project_id, headers)
        
        # Get file count across all branches and check for large files
        all_branches_stats = get_all_branches_file_stats(project_id, headers)
        stats['all_branches_file_count'] = all_branches_stats['total_files']
        stats['has_large_file'] = all_branches_stats['has_large_file']
        
        # Calculate total object count (commits, tags, branches, files, etc.)
        stats['object_count'] = get_repository_object_count(project_id, headers, stats)
        
        return stats
        
    except Exception as e:
        log(f"    WARNING: Error fetching repository stats: {e}")
        return stats
def check_for_pipeline_config(project_id, headers):
    """
    Check if the project has a GitLab CI/CD pipeline configuration file.
    Looks for .gitlab-ci.yml, .gitlab-ci.yaml, or gitlab-ci.yml in the root directory.
    """
    try:
        # Get project info to determine default branch
        project_url = f"{base_url}/projects/{project_id}"
        project_response = requests.get(project_url, headers=headers, timeout=10)
        
        if project_response.status_code != 200:
            log(f"    WARNING: Could not fetch project info for pipeline check")
            return False
        
        project_info = project_response.json()
        default_branch = project_info.get('default_branch')
        
        if not default_branch:
            log(f"    WARNING: No default branch found - cannot check for pipeline")
            return False
        
        # List of possible GitLab CI configuration filenames
        pipeline_files = [
            '.gitlab-ci.yml',
            '.gitlab-ci.yaml',
            'gitlab-ci.yml',
            'gitlab-ci.yaml',
            '.gitlab/ci.yml',
            '.gitlab/ci.yaml'
        ]
        
        log(f"    Checking for pipeline configuration files...")
        
        # Check each possible pipeline file
        for pipeline_file in pipeline_files:
            # Encode the file path for URL
            encoded_file_path = requests.utils.quote(pipeline_file, safe='')
            file_url = f"{base_url}/projects/{project_id}/repository/files/{encoded_file_path}"
            
            # Add the branch reference
            params = {'ref': default_branch}
            
            try:
                # Use HEAD request for efficiency (we just need to know if file exists)
                response = requests.head(file_url, headers=headers, params=params, timeout=5)
                
                if response.status_code == 200:
                    log(f"    Found pipeline configuration: {pipeline_file}")
                    return True
                
            except Exception:
                # Continue checking other files if this one fails
                continue
        
        log(f"    No pipeline configuration found")
        return False
        
    except Exception as e:
        log(f"    ERROR: Failed to check for pipeline configuration: {e}")
        return False
    
    
def get_repository_object_count(project_id, headers, existing_stats):
    """
    Calculate total number of objects in repository.
    Includes commits, branches, tags, files, and merge requests.
    """
    try:
        object_count = 0
        
        # Start with existing commit count
        object_count += existing_stats.get('commit_count', 0)
        
        # Add existing branch count
        object_count += existing_stats.get('branch_count', 0)
        
        # Get and add tag count
        tags_url = f"{base_url}/projects/{project_id}/repository/tags"
        tags_response = requests.head(tags_url, headers=headers, timeout=10)
        if tags_response.status_code == 200 and 'X-Total' in tags_response.headers:
            tag_count = int(tags_response.headers.get('X-Total', 0))
            object_count += tag_count
            log(f"    Found {tag_count} tags")
        
        # Add file and directory objects
        # Each file is a blob, estimate directory tree objects as files/10
        file_count = existing_stats.get('all_branches_file_count', existing_stats.get('file_count', 0))
        estimated_tree_objects = max(file_count // 10, 1)  # Rough estimate of directory objects
        object_count += file_count + estimated_tree_objects
        
        # Get and add merge request count (each MR creates additional commits)
        mr_url = f"{base_url}/projects/{project_id}/merge_requests?state=all&per_page=1"
        mr_response = requests.head(mr_url, headers=headers, timeout=10)
        if mr_response.status_code == 200 and 'X-Total' in mr_response.headers:
            mr_count = int(mr_response.headers.get('X-Total', 0))
            object_count += mr_count  # Each MR has at least one commit
            log(f"    Found {mr_count} merge requests")
        
        log(f"    Total estimated objects: {object_count}")
        return object_count
        
    except Exception as e:
        log(f"    WARNING: Error calculating object count: {e}")
        # Return minimum estimate based on commits and files
        return existing_stats.get('commit_count', 0) + existing_stats.get('file_count', 0)

def get_all_branches_file_stats(project_id, headers):
    """
    Get file count across all branches and check for large files.
    Due to API limitations, checks first 10 branches only.
    """
    stats = {
        'total_files': 0,
        'has_large_file': False
    }
    
    try:
        # Get all branches in the repository
        branches_url = f"{base_url}/projects/{project_id}/repository/branches?per_page=100"
        branches_response = requests.get(branches_url, headers=headers, timeout=15)
        
        if branches_response.status_code != 200:
            log(f"    WARNING: Could not fetch branches for file stats")
            return stats
        
        branches = branches_response.json()
        log(f"    Checking files across {len(branches)} branches...")
        
        # Track unique files across all branches
        unique_files = set()
        large_file_found = False
        
        # Limit branch checking to avoid timeouts (first 10 branches)
        branches_to_check = branches[:10] if len(branches) > 10 else branches
        
        # Process each branch
        for idx, branch in enumerate(branches_to_check):
            branch_name = branch.get('name')
            if not branch_name:
                continue
                
            try:
                # Get files in this branch with pagination
                tree_url = f"{base_url}/projects/{project_id}/repository/tree"
                page = 1
                max_pages_per_branch = 5  # Limit to 500 files per branch to avoid timeout
                branch_files = 0
                
                # Paginate through branch files
                while page <= max_pages_per_branch:
                    params = {
                        'recursive': 'true',
                        'per_page': 100,
                        'page': page,
                        'ref': branch_name
                    }
                    
                    tree_response = requests.get(tree_url, headers=headers, params=params, timeout=15)
                    
                    if tree_response.status_code != 200:
                        break
                    
                    items = tree_response.json()
                    
                    if not items:
                        break
                    
                    # Process each file in the response
                    for item in items:
                        if item.get('type') == 'blob':
                            # Track unique file paths
                            file_path = item.get('path', '')
                            if file_path:
                                unique_files.add(file_path)
                                branch_files += 1
                            
                            # Check for potentially large files based on extension
                            if not large_file_found and file_path:
                                # Common large file extensions
                                large_file_patterns = ['.zip', '.tar', '.gz', '.iso', '.dmg', '.exe', '.deb', '.rpm', 
                                                     '.pkg', '.msi', '.war', '.ear', '.jar', '.pdf', '.mp4', 
                                                     '.mov', '.avi', '.mkv', '.mp3', '.wav', '.flac']
                                if any(file_path.lower().endswith(ext) for ext in large_file_patterns):
                                    # Check actual file size with HEAD request
                                    file_url = f"{base_url}/projects/{project_id}/repository/files/{requests.utils.quote(file_path, safe='')}"
                                    file_params = {'ref': branch_name}
                                    
                                    try:
                                        file_response = requests.head(file_url, headers=headers, params=file_params, timeout=5)
                                        if file_response.status_code == 200:
                                            # Get file size from GitLab header
                                            file_size_str = file_response.headers.get('X-Gitlab-Size', '0')
                                            try:
                                                file_size = int(file_size_str)
                                                if file_size > 100 * 1024 * 1024:  # 100MB threshold
                                                    large_file_found = True
                                                    log(f"    Found large file (>100MB): {file_path} ({file_size / (1024*1024):.1f} MB)")
                                            except ValueError:
                                                pass
                                    except Exception:
                                        pass
                    
                    # Check for more pages
                    if 'X-Next-Page' not in tree_response.headers or not tree_response.headers['X-Next-Page']:
                        break
                    
                    page += 1
                
                # Log progress for first few branches
                if idx < 3:
                    log(f"    Branch '{branch_name}': found {branch_files} files in this branch")
                    
            except Exception as e:
                log(f"    WARNING: Error checking branch {branch_name}: {e}")
                continue
        
        # Set final statistics after processing all branches
        stats['total_files'] = len(unique_files)
        stats['has_large_file'] = large_file_found
        
        # Note if we only checked a subset of branches
        if len(branches) > 10:
            log(f"    Note: Checked first 10 branches of {len(branches)} total branches (minimum count)")
        
        log(f"    Total unique files across checked branches: {stats['total_files']}")
        
        return stats
        
    except Exception as e:
        log(f"    ERROR: Failed to get all branches file stats: {e}")
        return stats

# =======================
# Main Execution
# =======================
if __name__ == "__main__":
    # Fetch all groups from GitLab
    log(f"Discovering all GitLab groups...")
    groups = fetch_all_groups(headers)

    # Handle fetch failures
    if groups is None:
        log("ERROR: Failed to fetch groups")
        sys.exit(1)

    if not groups:
        log("WARNING: No groups found")
        sys.exit(0)

    log(f"Successfully discovered {len(groups)} groups from GitLab")
    
    # Collect all projects from all groups
    all_projects = []
    for group in groups:
        group_name = group['name']
        group_path = group['full_path']
        log(f"\nFetching projects from group: {group_name} ({group_path})")
        
        projects = fetch_all_projects(group_path, headers)
        
        if projects is None:
            log(f"  WARNING: Failed to fetch projects from group {group_name}")
            continue
        
        # Add group information to each project
        for project in projects:
            project['_group_name'] = group_name
            project['_group_path'] = group_path
        
        all_projects.extend(projects)
        log(f"  Added {len(projects)} projects from {group_name}")
    
    log(f"\nSuccessfully fetched {len(all_projects)} total projects from {len(groups)} groups")
    
    # Use all_projects instead of projects for the rest of the script
    projects = all_projects

    # Apply project filter if configured
    if project_filter is not None:
        # Filter projects based on the loaded filter
        filtered_projects = [p for p in projects if should_process_project(p, project_filter)]
        log(f"After filtering, {len(filtered_projects)} projects will be processed")
        projects = filtered_projects
    
    # Handle empty results
    if not projects:
        log("WARNING: No projects to process after filtering")
        sys.exit(0)

    # Initialize data collection
    stats = []
    failed_projects = []

    # Process each project to collect detailed statistics
    log("Collecting detailed statistics for each project...")
    for idx, project in enumerate(projects):
        project_id = project['id']
        project_name = project['name']
        
        # Show progress every 10 projects
        if (idx + 1) % 10 == 0:
            log(f"Processing project {idx + 1}/{len(projects)}...")
        
        try:
            log(f"Processing: {project_name}")
            
            # Check project archive status
            is_archived = project.get('archived', False)
            if is_archived:
                log(f"  Note: This project is ARCHIVED")
            
            # Get default branch name
            default_branch = project.get('default_branch', 'main')
            
            # Fetch contributor statistics
            log(f"  Fetching contributors...")
            commit_stats_url = f"{base_url}/projects/{project_id}/repository/contributors"
            
            commit_response = requests.get(commit_stats_url, headers=headers, timeout=15)
            
            if commit_response.status_code == 200:
                contributors = commit_response.json()
                # Calculate total commits across all contributors
                total_commits = sum(c.get('commits', 0) for c in contributors)
                log(f"  Found {len(contributors)} contributors with {total_commits} total commits")
            else:
                # Handle empty or inaccessible repositories
                log(f"  WARNING: Could not fetch contributors (status: {commit_response.status_code})")
                contributors = []
                total_commits = 0
            
            # Get comprehensive repository statistics
            log(f"  Fetching comprehensive repository statistics...")
            repo_stats = get_repository_stats_via_api(project_id, headers)
            
            # Get merge request count
            log(f"  Fetching merge requests...")
            mr_url = f"{base_url}/projects/{project_id}/merge_requests?state=all&per_page=1"
            try:
                mr_response = requests.head(mr_url, headers=headers, timeout=10)
                if mr_response.status_code == 200 and 'X-Total' in mr_response.headers:
                    merge_request_count = int(mr_response.headers.get('X-Total', 0))
                    log(f"  Found {merge_request_count} merge requests")
                else:
                    merge_request_count = 0
            except Exception as e:
                log(f"  WARNING: Could not fetch merge request count: {e}")
                merge_request_count = 0
            
            # Extract values from statistics
            repository_size = repo_stats['repository_size']
            storage_size = repo_stats['storage_size']
            file_count = repo_stats['file_count']
            branch_count = repo_stats['branch_count']
            
            # Fallback to original project data if statistics are missing
            if repository_size == 0 and storage_size == 0:
                log(f"    Checking original project data for statistics...")
                repository_size = project.get('statistics', {}).get('repository_size', 0)
                storage_size = project.get('statistics', {}).get('storage_size', 0)
                
                if repository_size > 0 or storage_size > 0:
                    log(f"    Found statistics in original data: repository_size={repository_size}, storage_size={storage_size}")
            
            # Recalculate size thresholds with final values
            exceeds_2gb = storage_size > (2 * 1024 * 1024 * 1024)  # 2GB in bytes
            exceeds_6gb = storage_size > (6 * 1024 * 1024 * 1024)  # 6GB in bytes
            
            if storage_size > 0:
                log(f"    Size check: Total storage: {bytes_to_mb(storage_size)} MB - Exceeds 2GB: {exceeds_2gb}, Exceeds 6GB: {exceeds_6gb}")
            
            log(f"  Repository stats - Files: {file_count}, Size: {bytes_to_mb(repository_size)} MB")
            
            # Build complete project statistics dictionary
            project_stats = {
                'id': project['id'],
                'group_name': project.get('_group_name', 'N/A'),
                'project_name': project['name'],
                'group_path': project.get('_group_path', 'N/A'),
                'path': project['path_with_namespace'],
                'status': 'archived' if is_archived else 'active',
                'archived': is_archived,
                'stars': project.get('star_count', 0),
                'forks': project.get('forks_count', 0),
                'open_issues': project.get('open_issues_count', 0),
                'merge_requests': merge_request_count,
                'last_activity': project.get('last_activity_at', 'N/A'),
                'contributors': len(contributors),
                'total_commits': total_commits,
                'branch_count': branch_count,
                'file_count': file_count,
                'all_branches_file_count': repo_stats.get('all_branches_file_count', file_count),
                'total_objects': repo_stats.get('object_count', 0),
                'repository_size_mb': bytes_to_mb(repository_size),
                'total_size_mb': bytes_to_mb(storage_size),
                'has_large_file_100mb': repo_stats.get('has_large_file', False),
                'exceeds_2gb': exceeds_2gb,
                'exceeds_6gb': exceeds_6gb,
                'pipeline': repo_stats.get('has_pipeline', False),  # Add pipeline status
                'visibility': project.get('visibility', 'N/A'),
                'created_at': project.get('created_at', 'N/A'),
                'default_branch': default_branch,
                'web_url': project.get('web_url', 'N/A')
            }
            
            stats.append(project_stats)
            
        except requests.exceptions.Timeout:
            log(f"  ERROR: Timeout while processing project: {project_name}")
            failed_projects.append(project_name)
            continue
        except Exception as e:
            log(f"  ERROR: Failed to process project {project_name}: {e}")
            failed_projects.append(project_name)
            continue

    # Summary of processing results
    log(f"\nCompleted processing {len(stats)} projects successfully")
    if failed_projects:
        log(f"Failed to process {len(failed_projects)} projects: {failed_projects}")
    
    if project_filter is not None:
        log(f"Note: Processing was filtered based on project list file: {PROJECT_LIST_FILE}")
        log(f"Filter values used: {MIGRATE_REPO_VALUES}")

    # Write results to CSV file
    log(f"Writing results to {OUTPUT_FILE}...")
    if stats:
        # Define explicit field order for CSV output
        fieldnames = [
            'id', 'group_name', 'project_name', 'group_path', 'path', 'status', 'archived',
            'stars', 'forks', 'open_issues', 'merge_requests',
            'last_activity', 'contributors', 'total_commits', 'branch_count',
            'file_count', 'all_branches_file_count', 'total_objects',
            'repository_size_mb', 'total_size_mb', 'has_large_file_100mb',
            'exceeds_2gb', 'exceeds_6gb', 'pipeline', 'visibility',
            'created_at', 'default_branch', 'web_url'
        ]
        
        # Write CSV with headers
        with open(OUTPUT_FILE, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stats)
        
        log(f"Successfully wrote {len(stats)} project records to {OUTPUT_FILE}")
    else:
        log("No data to write to CSV file")

    # Display environment variables that were set
    log("\nEnvironment variables set for use by other scripts:")
    log(f"GITLAB_TOKEN: {'Set' if os.environ.get('GITLAB_TOKEN') else 'Not set'}")
    log(f"GITLAB_URL: {os.environ.get('GITLAB_URL', 'Not set')}")
    log(f"GITHUB_TOKEN: {'Set' if os.environ.get('GITHUB_TOKEN') else 'Not set'}")
    
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