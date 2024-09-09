"""
Script: Backup Google Groups Settings to Google Drive

Description:
This Python script exports the settings of Google Groups in your organization to a CSV file 
and uploads it to a specified Google Drive folder. The script is designed to run on a schedule 
using GitHub Actions, ensuring that a backup of Google Groups settings is consistently maintained.

Functions:
- `get_google_groups()`: Retrieves all Google Groups in the organization.
- `get_group_settings(group_email)`: Fetches detailed settings for a specific Google Group.
- `check_folder_exists(drive_service, folder_id)`: Verifies if the specified Google Drive folder exists.
- `upload_file_to_drive(drive_service, csv_file, filename, folder_id)`: Uploads the CSV file to the specified 
  Google Drive folder with retry logic in case of failures.
- `export_groups_settings_to_csv(groups, folder_id)`: Exports the settings of all Google Groups to a CSV file 
  and uploads it to Google Drive.

Usage:
1. **Service Account Setup:**
   - Ensure you have a Google Cloud service account with the necessary API scopes authorized 
     for domain-wide delegation.
   - The required scopes are:
     - `https://www.googleapis.com/auth/admin.directory.group.readonly`
     - `https://www.googleapis.com/auth/apps.groups.settings`
     - `https://www.googleapis.com/auth/drive.file`

2. **GitHub Secrets:**
   - Store the following sensitive information in GitHub Secrets:
     - `SERVICE_ACCOUNT_JSON`: The content of the service account JSON file.
     - `FOLDER_ID`: The Google Drive folder ID where the CSV file will be uploaded.
     - `SUPER_ADMIN_EMAIL`: The email of a super admin account in the organization.

3. **GitHub Actions Workflow:**
   - This script is intended to be run as part of a GitHub Actions workflow. 
     A sample workflow YAML file is provided in the documentation to set up scheduled 
     backups of Google Groups settings.

Notes:
- **Error Handling:** The script includes retry logic for handling temporary issues 
  such as SSL errors or API rate limits.
- **Customization:** You can modify the fields exported to the CSV file by adjusting 
  the `fields` list in the `export_groups_settings_to_csv()` function.

Author: Chad Ramey
Date: August 29, 2024
"""

import os
import csv
import time
import ssl
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import json

# Load secrets from environment variables
SERVICE_ACCOUNT_INFO = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
FOLDER_ID = os.environ["FOLDER_ID"]
SUPER_ADMIN_EMAIL = os.environ["SUPER_ADMIN_EMAIL"]

# Scopes required to list Google Groups and access Google Drive
SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
    'https://www.googleapis.com/auth/apps.groups.settings',
    'https://www.googleapis.com/auth/drive.file'
]

# Create credentials using the service account info
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES)

# Use domain-wide delegation
delegated_credentials = credentials.with_subject(SUPER_ADMIN_EMAIL)

# Build the service for Admin SDK Directory API and Groups Settings API
directory_service = build('admin', 'directory_v1', credentials=delegated_credentials)
groups_settings_service = build('groupssettings', 'v1', credentials=delegated_credentials)
drive_service = build('drive', 'v3', credentials=delegated_credentials)

# Function to get all Google Groups
def get_google_groups():
    groups = []
    request = directory_service.groups().list(customer='my_customer', maxResults=50)  # Limit for testing
    while request is not None:
        response = request.execute()
        groups.extend(response.get('groups', []))
        request = directory_service.groups().list_next(previous_request=request, previous_response=response)
    return groups

# Function to get detailed settings for a group with retry logic
def get_group_settings(group_email):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = groups_settings_service.groups().get(groupUniqueId=group_email).execute()
            return response
        except (HttpError, TimeoutError) as error:
            print(f"Attempt {attempt + 1} failed for {group_email}: {error}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(5 * (attempt + 1))
            else:
                print(f"Max retries reached for {group_email}. Skipping...")
                return None

# Function to check if the folder exists
def check_folder_exists(drive_service, folder_id):
    try:
        results = drive_service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)", supportsAllDrives=True).execute()
        files = results.get('files', [])
        if files is not None:
            print(f"Folder ID {folder_id} is valid and contains {len(files)} file(s).")
        return True
    except HttpError as error:
        print(f"Error verifying folder ID: {error}")
        return False

# Function to upload the file to Google Drive with retries
def upload_file_to_drive(drive_service, csv_file, filename, folder_id, retries=3, delay=5):
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    media = MediaFileUpload(csv_file, mimetype='text/csv')

    for attempt in range(retries):
        try:
            file = drive_service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
            print(f'Backup uploaded to Google Drive with File ID: {file.get("id")}')
            return file.get("id")
        except ssl.SSLEOFError as e:
            print(f"SSL Error on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Failed to upload file.")
                raise
        except HttpError as error:
            print(f"HttpError on attempt {attempt + 1}: {error}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Failed to upload file.")
                raise

# Export Google Groups settings to CSV with timestamp
def export_groups_settings_to_csv(groups, folder_id):
    # Generate a timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'gg_settings_backup_{timestamp}.csv'
    csv_file = f'/tmp/{filename}'

    # Fields to export
    fields = [
        'email', 'id', 'name', 'description', 'directMembersCount', 'adminCreated',
        'aliases', 'nonEditableAliases', 'allowExternalMembers', 'allowWebPosting', 
        'archiveOnly', 'customFooterText', 'customRolesEnabledForSettingsToBeMerged',
        'defaultMessageDenyNotificationText', 'defaultSender', 'enableCollaborativeInbox',
        'includeCustomFooter', 'includeInGlobalAddressList', 'isArchived',
        'membersCanPostAsTheGroup', 'messageModerationLevel', 'primaryLanguage', 'replyTo',
        'sendMessageDenyNotification', 'spamModerationLevel', 'whoCanContactOwner', 'whoCanJoin',
        'whoCanLeaveGroup', 'whoCanPostMessage', 'whoCanViewGroup', 'whoCanViewMembership',
        'whoCanDiscoverGroup', 'showInGroupDirectory', 'whoCanAssistContent', 'whoCanAssignTopics',
        'whoCanEnterFreeFormTags', 'whoCanHideAbuse', 'whoCanMakeTopicsSticky', 'whoCanMarkDuplicate',
        'whoCanMarkFavoriteReplyOnAnyTopic', 'whoCanMarkNoResponseNeeded', 'whoCanModifyTagsAndCategories',
        'whoCanTakeTopics', 'whoCanUnassignTopic', 'whoCanUnmarkFavoriteReplyOnAnyTopic', 'whoCanModerateContent',
        'whoCanApproveMessages', 'whoCanDeleteAnyPost', 'whoCanDeleteTopics', 'whoCanLockTopics',
        'whoCanMoveTopicsIn', 'whoCanMoveTopicsOut', 'whoCanPostAnnouncements', 'whoCanModerateMembers',
        'whoCanAdd', 'whoCanApproveMembers', 'whoCanBanUsers', 'whoCanInvite', 'whoCanModifyMembers',
        'allowGoogleCommunication', 'favoriteRepliesOnTop', 'maxMessageBytes', 'messageDisplayFont',
        'whoCanAddReferences', 'whoCanMarkFavoriteReplyOnOwnTopic'
    ]

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(fields)  # Write header

        for group in groups:
            group_email = group.get('email')
            settings = get_group_settings(group_email)
            if settings:
                row = [settings.get(field, 'N/A') for field in fields]
                writer.writerow(row)

    print(f'Google Groups settings exported to {csv_file}')

    # Upload the CSV file to the specified folder in Google Drive
    upload_file_to_drive(drive_service, csv_file, filename, folder_id)

# Main function
def main():
    if check_folder_exists(drive_service, FOLDER_ID):
        groups = get_google_groups()
        export_groups_settings_to_csv(groups, FOLDER_ID)
    else:
        print("Folder ID is invalid or inaccessible. Please check the folder ID and permissions.")

if __name__ == '__main__':
    main()
