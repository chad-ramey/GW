"""
Script: exportGoogleGroupsToDrive - Export Google Groups and Members to Google Drive

Description:
This Python script automates the process of exporting all Google Groups and their members within a Google Workspace domain to a CSV file. The CSV file is then uploaded to a specified folder within a shared Google Drive. The script includes error handling for common issues such as Google API service unavailability (503 errors) and SSL/TLS connection errors. The script is designed to run in a GitHub Actions environment, using secrets stored in GitHub for secure access to sensitive information.

Functions:
- `get_google_groups()`: Retrieves all Google Groups in the Google Workspace domain.
- `check_folder_exists(drive_service, folder_id)`: Verifies the existence of the specified Google Drive folder and checks if it is accessible.
- `get_group_members(service, group_email, retries=3, delay=5)`: Retrieves the members of a specific Google Group, with a retry mechanism for handling 503 errors.
- `upload_file_to_drive(drive_service, csv_file, filename, folder_id, retries=3, delay=5)`: Uploads the CSV file to the specified Google Drive folder, with a retry mechanism for handling SSL and HTTP errors.
- `export_groups_to_csv(groups, folder_id)`: The main function that:
  1. Generates a timestamped CSV file containing the group and member data.
  2. Saves the CSV file to a specified Google Drive folder.

Usage:
1. **Environment Variables**:
   - The script relies on three environment variables, which should be provided via GitHub Secrets:
     - `SERVICE_ACCOUNT_JSON`: Contains the service account credentials in JSON format.
     - `FOLDER_ID`: The ID of the Google Drive folder where the CSV file will be uploaded.
     - `SUPER_ADMIN_EMAIL`: The super admin email address used for domain-wide delegation.
   - The script writes the `SERVICE_ACCOUNT_JSON` to a file at runtime, which is used to authenticate with the Google APIs.

2. **Google Groups Retrieval**:
   - The script retrieves all Google Groups in the domain using the Google Admin SDK Directory API.
   - It then iterates over each group to retrieve its members.
   - If a group member retrieval fails due to a 503 error, the script retries the operation up to three times before skipping the group.

3. **Google Drive Folder**:
   - The script uploads the generated CSV file to a specific Google Drive folder, identified by its folder ID.

4. **Error Handling**:
   - The script includes robust error handling to manage issues such as service unavailability (503 errors) and SSL connection problems.
   - If a file upload fails due to an SSL or HTTP error, the script retries the upload operation up to three times before failing.

Notes:
- **Permissions:** The script requires domain-wide delegation to access the Google Admin SDK Directory API and Google Drive API. Ensure that the necessary OAuth scopes are authorized for the service account.
- **GitHub Actions Integration:** This script is designed to be run within a GitHub Actions workflow, with secrets for sensitive information stored securely in GitHub.
- **Customization:** You can customize the retry mechanisms and delays for handling specific errors to suit your environment.

Author: Chad Ramey
Date: August 28, 2024
"""

import os
import csv
import time
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import ssl

# Load environment variables from GitHub Actions secrets
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')
FOLDER_ID = os.environ.get('FOLDER_ID')
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL')

# Write the service account key to a file
SERVICE_ACCOUNT_FILE = 'service_account_key.json'
with open(SERVICE_ACCOUNT_FILE, 'w') as f:
    f.write(SERVICE_ACCOUNT_JSON)

# Scopes required to list Google Groups and access Google Drive
SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

# Create credentials using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Use domain-wide delegation
delegated_credentials = credentials.with_subject(SUPER_ADMIN_EMAIL)

# Build the service for Admin SDK Directory API
service = build('admin', 'directory_v1', credentials=delegated_credentials)
drive_service = build('drive', 'v3', credentials=delegated_credentials)

# Function to get all Google Groups
def get_google_groups():
    groups = []
    request = service.groups().list(customer='my_customer', maxResults=200)
    while request is not None:
        response = request.execute()
        groups.extend(response.get('groups', []))
        request = service.groups().list_next(previous_request=request, previous_response=response)
    return groups

# Function to check if the folder exists
def check_folder_exists(drive_service, folder_id):
    try:
        # Attempt to list files in the folder to verify its existence
        results = drive_service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)", supportsAllDrives=True).execute()
        files = results.get('files', [])
        if files is not None:
            print(f"Folder ID {folder_id} is valid and contains {len(files)} file(s).")
        return True
    except HttpError as error:
        print(f"Error verifying folder ID: {error}")
        return False

# Function to retrieve members with retry for 503 errors
def get_group_members(service, group_email, retries=3, delay=5):
    for attempt in range(retries):
        try:
            members_result = service.members().list(groupKey=group_email).execute()
            return members_result.get('members', [])
        except HttpError as error:
            if error.resp.status == 503:
                print(f"Service unavailable for group {group_email} on attempt {attempt + 1}: {error}")
                if attempt < retries - 1:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("Max retries reached. Skipping this group.")
                    return []
            else:
                raise  # Re-raise other errors

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

# Export Google Groups to CSV with timestamp
def export_groups_to_csv(groups, folder_id):
    # Generate a timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'gg_backup_{timestamp}.csv'
    csv_file = f'/tmp/{filename}'

    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Group Email', 'Member Email', 'Role', 'Status'])

        for group in groups:
            group_email = group['email']
            try:
                members = get_group_members(service, group_email)
                for member in members:
                    # Use .get() with a default value to avoid KeyError
                    writer.writerow([
                        group_email,
                        member.get('email', 'N/A'),
                        member.get('role', 'N/A'),
                        member.get('status', 'N/A')  # Handle missing 'status' key
                    ])
            except HttpError as error:
                print(f"Failed to retrieve members for group {group_email}: {error}")
                continue  # Skip this group and move on to the next

    print(f'Google Groups and Members exported to {csv_file}')

    # Upload the CSV file to the specified folder in Google Drive
    upload_file_to_drive(drive_service, csv_file, filename, folder_id)

# Main function
def main():
    folder_id = FOLDER_ID  # Use the folder ID from environment variables
    if check_folder_exists(drive_service, folder_id):
        groups = get_google_groups()
        export_groups_to_csv(groups, folder_id)
    else:
        print("Folder ID is invalid or inaccessible. Please check the folder ID and permissions.")

if __name__ == '__main__':
    main()
