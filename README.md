# Google Workspace Lab

This repository contains Python and JavaScript scripts designed to automate tasks related to managing Google Workspace, including shared drive management, user settings export, and license notifications.

## Table of Contents
- [Google Workspace Lab](#google-workspace-lab)
  - [Table of Contents](#table-of-contents)
  - [Scripts Overview](#scripts-overview)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

## Scripts Overview
Here’s a list of all the scripts in this repository along with their descriptions:

1. **gw_export_shared_drives_acls.py**: Exports the Access Control List (ACL) settings for all shared drives in the Google Workspace environment.
2. **gw_export_users_with_forwarding.py**: Exports a list of all users who have email forwarding enabled.
3. **gw_gg_settings_backup.py**: Backs up the settings of Google Groups in the organization, including visibility and member settings.
4. **gw_groups_backup.py**: Exports a backup of all Google Groups and their members in the domain.
5. **gw_license_notifier.js**: Monitors and sends notifications related to Google Workspace licensing, notifying admins when licenses reach specific thresholds.

## Requirements
- **Python 3.x** (for Python scripts): Ensure that Python 3 is installed on your system.
- **Google Apps Script API** (for JavaScript scripts): Install the required libraries to interact with Google Workspace APIs.
- **API Keys**: You will need OAuth credentials and Google Workspace Admin API access tokens to authenticate API requests.

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo-name/google-workspace-automation-scripts.git
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your OAuth credentials or Google Workspace API tokens in environment variables:
   ```bash
   export GOOGLE_API_TOKEN="your-token-here"
   ```

## Usage
Run the desired script from the command line or integrate it into your Google Workspace workflows.

Example:
```bash
python3 gw_export_shared_drives_acls.py
```

## Contributing
Contributions are welcome! Feel free to submit issues or pull requests to improve the functionality or add new features.

## License
This project is licensed under the MIT License.
