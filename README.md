# GitLab Inventory Tools

This repository contains a comprehensive set of tools for analyzing GitLab projects and facilitating migration from GitLab to GitHub. It includes Python scripts for collecting detailed statistics, GitLab Exporter tools, and migration utilities.

## Repository Structure

```
GitLab_Inventory/
├── scripts/              # Python scripts for GitLab analysis
│   ├── gitlab-details.py
│   ├── gitlab-groups.py
│   └── gitlab-group-discovery.py
├── gl-exporter/          # GitLab repository exporter tool
├── gl-migrate/           # GitLab to GitHub migration tool
└── docs/                 # Documentation
```

## Prerequisites

- GitLab Personal Access Token with appropriate permissions
- (Optional) GitHub Personal Access Token for migration features
- Internet connection to access GitLab API

## Quick Start

### 1. Install Python Dependencies

Install the required Python packages using pip:

```bash
pip install requests
```

Or use the requirements.txt file:

```bash
# From the repository root directory
pip install -r requirements.txt
```

### 2. Configure Access Tokens

Create a `.token` file in the repository root directory with the following JSON format:

```json
{
  "token": "your-gitlab-personal-access-token",
  "gitlab_url": "https://gitlab.com"
}
```

**Configuration Fields:**

- **`token`** (required): Your GitLab Personal Access Token
  - To create a token: GitLab → Settings → Access Tokens
  - Required scopes: `api`, `read_api`, `read_repository`

- **`gitlab_url`** (optional): GitLab instance URL
  - Default: `https://gitlab.com`
  - For self-hosted GitLab: `https://gitlab.your-company.com`

**Example .token file:**

```json
{
  "token": "glpat-xxxxxxxxxxxxxxxxxxxxx",
  "gitlab_url": "https://gitlab.com"
}
```

**Alternative: Environment Variables**

Instead of using a `.token` file, you can set environment variables:

```bash
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxxx"
export GITLAB_URL="https://gitlab.com"
```

## Tools Overview

### Python Scripts (`scripts/`)

Collection of Python scripts for analyzing GitLab repositories and collecting statistics.

### 1. gitlab-details.py

Collects comprehensive statistics for all GitLab projects including:
- Project metadata (name, path, group)
- Repository statistics (size, file count, commits)
- Branch and tag information
- Contributor statistics
- Merge request counts
- Pipeline configuration detection
- Large file detection

**Usage:**

```bash
cd scripts
python3 gitlab-details.py
```

**Output:**
- Creates `data/gitlab-stats.csv` with detailed project statistics
- CSV columns include: id, group_name, project_name, group_path, path, status, stars, forks, contributors, total_commits, branch_count, file_count, repository_size_mb, total_size_mb, has_large_file_100mb, exceeds_2gb, exceeds_6gb, pipeline, visibility, and more

### 2. gitlab-groups.py

Fetches and lists all GitLab groups accessible to your account.

**Usage:**

```bash
cd scripts
python3 gitlab-groups.py
```

**Output:**
- Creates `data/gitlab-groups.csv` with group information

### 3. gitlab-group-discovery.py

Discovers and analyzes GitLab group hierarchies and projects.

**Usage:**

```bash
cd scripts
python3 gitlab-group-discovery.py
```

### GitLab Exporter (`gl-exporter/`)

Ruby-based tool for exporting GitLab repositories to GitHub-compatible format. See [gl-exporter/README.md](gl-exporter/README.md) for detailed documentation.

**Key Features:**
- Export GitLab projects to GitHub format
- Preserve repository history
- Export issues, merge requests, and metadata
- Archive generation

### Migration Tool (`gl-migrate/`)

Python-based tool for automated GitLab to GitHub migrations. See [gl-migrate/README.md](gl-migrate/README.md) for detailed documentation.

**Key Features:**
- Automated repository migration
- Batch processing support
- Configuration-based migration
- Inventory tracking

## Output Directory

All scripts save their output to the `scripts/data/` directory. This directory is automatically created if it doesn't exist.

**Generated Files:**
- `gitlab-stats.csv` - Detailed project statistics
- `gitlab-groups.csv` - Group information

## Project Filtering

To process only specific projects instead of all projects:

1. Create a CSV file (e.g., `project-list.csv`) in the `scripts/data/` directory with the following columns:
   - `Name`: Project name (exact match)
   - `Migrate Repo`: Filter value (e.g., "Migrate", "Yes", "Include")

**Example CSV:**
```csv
Name,Migrate Repo
my-important-project,Migrate
another-project,Migrate
test-repo,Yes
```

2. Run the script - all projects will be processed and output to CSV

3. Review the generated CSV and manually filter as needed

## Platform-Specific Setup

For Windows users, use the batch file to set up the Python virtual environment:

```cmd
setup-venv.bat
```

### Windows

For Windows users, use the batch file to set up the Python virtual environment:

```cmd
cd scripts
setup-venv.bat
```

### Unix/Linux/macOS

For Unix-based systems, use the shell script:

```bash
cd scripts
chmod +x setup-venv.sh
./setup-venv.sh
```

## Common Workflows

### Workflow 1: Discover and Analyze All Projects

```bash
# 1. Configure your .token file
# 2. Run the discovery script
cd scripts
python3 gitlab-details.py

# 3. Review the output
cat data/gitlab-stats.csv
```

### Workflow 2: Filtered Project Analysis

```bash
# 1. Create project filter list
# Edit scripts/data/project-list.csv with your projects

# 2. Update .token file with filter configuration

# 3. Run the analysis
cd scripts
python3 gitlab-details.py
```

### Workflow 3: Export and Migrate

```bash
# 1. Collect project statistics
cd scripts
python3 gitlab-details.py

# 2. Use gl-exporter to export repositories
cd ../gl-exporter
# See gl-exporter/README.md for usage

# 3. Use gl-migrate for batch migration
cd ../gl-migrate
# See gl-migrate/README.md for usage
```

## Troubleshooting

### Common Issues

**1. Token Authentication Failed**
- Verify your GitLab token is valid
- Check token has required scopes: `api`, `read_api`, `read_repository`
- Ensure token hasn't expired

**2. 404 Errors for Groups**
- Verify you have access to the groups
- Check the group path is correct
- Some subgroups may be private or require specific permissions

**3. Script Timeout**
- Large repositories may cause timeouts
- The script has built-in timeout handling and will skip problematic projects
- Check the log output for specific timeout messages
- Consider increasing timeout values for very large repositories

**4. Missing Dependencies**
- Install required packages: `pip install requests`
- For full requirements: `pip install -r requirements.txt`
- Ensure Python 3.7+ is installed: `python3 --version`

**5. Empty Repositories**
- Projects with no commits will show 0 statistics
- This is expected behavior for newly created projects
- Archived projects are marked with status='archived'

**6. File Path Issues**
- Ensure you're running scripts from the correct directory
- Use absolute paths or navigate to `scripts/` directory before running
- Check that `.token` file is in the repository root

**7. CSV Format Issues**
- Ensure project filter CSV has proper headers: `Name,Migrate Repo`
- Check for extra spaces or special characters
- Save CSV in UTF-8 encoding

## Script Features

### gitlab-details.py Features

- **Automatic Pagination**: Handles large numbers of projects and groups
- **Rate Limit Handling**: Built-in delays to respect API rate limits
- **Error Recovery**: Continues processing even if individual projects fail
- **Progress Logging**: Timestamped logs for tracking progress
- **Large Repository Support**: Optimized handling for repositories >10GB
- **File Count Detection**: Accurate file counting with pagination
- **Pipeline Detection**: Checks for GitLab CI/CD configuration
- **Size Threshold Detection**: Flags projects exceeding 2GB and 6GB
- **Large File Detection**: Identifies files over 100MB

## Security Notes

- **Never commit the `.token` file to version control**
- Add `.token` to your `.gitignore` file
- Rotate tokens regularly (recommended: every 90 days)
- Use tokens with minimum required permissions
- Store tokens securely (use password managers or secret managers)
- Review token access scopes before creating
- Revoke tokens immediately if compromised
- Use separate tokens for different environments (dev/staging/prod)

## Performance Notes

Processing time depends on:
- Number of projects and groups
- Repository sizes and file counts
- Number of branches per repository
- Network speed and latency
- GitLab API rate limits
- GitLab instance performance

**Expected Processing Time:**
- ~10 projects: 3-5 minutes
- ~50 projects: 10-20 minutes
- ~100 projects: 30-60 minutes
- ~500+ projects: 2-4 hours

**Optimization Tips:**
- Use project filtering to reduce scope
- Run during off-peak hours
- Process in batches for large installations
- Monitor API rate limits
- Consider running on a server with better network connectivity

## CSV Output Schema

### gitlab-stats.csv Columns

| Column | Description |
|--------|-------------|
| id | GitLab project ID |
| group_name | Parent group name |
| project_name | Project name |
| group_path | Full group path |
| path | Full project path with namespace |
| status | active or archived |
| archived | Boolean flag |
| stars | Number of stars |
| forks | Number of forks |
| open_issues | Count of open issues |
| merge_requests | Total merge requests |
| last_activity | Last activity timestamp |
| contributors | Number of contributors |
| total_commits | Total commit count |
| branch_count | Number of branches |
| file_count | File count in default branch |
| all_branches_file_count | Unique files across all branches |
| total_objects | Estimated total Git objects |
| repository_size_mb | Repository size in MB |
| total_size_mb | Total storage size in MB |
| has_large_file_100mb | Boolean for files >100MB |
| exceeds_2gb | Boolean for repos >2GB |
| exceeds_6gb | Boolean for repos >6GB |
| pipeline | Boolean for CI/CD pipeline |
| visibility | public, internal, or private |
| created_at | Project creation timestamp |
| default_branch | Default branch name |
| web_url | GitLab web URL |

## Best Practices

1. **Before Running Scripts:**
   - Verify token permissions
   - Test with a small subset first
   - Review and update `.token` configuration
   - Ensure adequate disk space for output files

2. **During Execution:**
   - Monitor log output for errors
   - Check network connectivity
   - Watch for rate limit warnings
   - Note any failed projects for retry

3. **After Completion:**
   - Review CSV output for accuracy
   - Validate statistics against GitLab UI
   - Archive results with timestamps
   - Document any anomalies or issues

4. **Regular Maintenance:**
   - Update scripts periodically
   - Refresh GitLab tokens before expiry
   - Clean up old output files
   - Review and optimize filters

## Additional Resources

- [GitLab API Documentation](https://docs.gitlab.com/ee/api/)
- [GitHub Migration Guide](https://docs.github.com/en/migrations)
- [gl-exporter Documentation](gl-exporter/README.md)
- [gl-migrate Documentation](gl-migrate/README.md)
- [GitHub Partner Support](docs/github-partner-support.md)

## Support and Contributions

For issues or questions:
1. Check the log output for detailed error messages
2. Review this README and tool-specific documentation
3. Verify token permissions and configuration
4. Check GitLab API rate limits and status

**Log Information Includes:**
- Timestamped progress messages
- Error details with context
- Project processing status
- API response codes
- Performance metrics

## License

Refer to individual tool directories for license information.

