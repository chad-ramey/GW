"""
Script: gw_export_shared_drives_acls.py - Export Shared Drive ACLs to Google Drive

Description:
This Python script automates the process of exporting ACLs (Access Control Lists) for all Shared Drives 
in a Google Workspace domain. It retrieves details about the shared drives, including the permissions 
(roles, users, etc.) for each drive, and exports them to a CSV file. The CSV file is then uploaded to a 
specified folder within a shared Google Drive. The script includes error handling for API errors 
and uses pagination to retrieve all shared drives.

Functions:
- export_shared_drive_acls(): 
  Retrieves all shared drives, fetches ACLs for each drive, and writes them to a CSV file.
  
- upload_to_drive(filename, folder_id): 
  Uploads the generated CSV file to the specified Google Drive folder.

Usage:
1. **Environment Variables**:
   - The script relies on three environment variables, which should be provided via GitHub Secrets 
     when run in a GitHub Actions workflow, or as part of an `.env` file when run locally:
     - `SERVICE_ACCOUNT_JSON`: Contains the service account credentials in JSON format.
     - `SUPER_ADMIN_EMAIL`: The super admin email address used for domain-wide delegation.
     - `FOLDER_ID`: The ID of the Google Drive folder where the CSV file will be uploaded.

2. **Google Drive Folder**:
   - The script uploads the generated CSV file to a specific Google Drive folder, identified by its folder ID.

3. **Error Handling**:
   - The script includes error handling for issues such as API request failures and permission issues.
   - If a file upload fails due to an API error, the script will log the failure.

4. **GitHub Actions Integration**:
   - This script is designed to be run within a GitHub Actions workflow. The required secrets should be 
     securely stored in GitHub.

5. **Customization**:
   - You can adjust the error handling mechanisms to suit your environment, such as adding retry logic 
     for rate limits or API quota errors.

Author: Chad Ramey  
Date: September 10, 2024
"""

import os
import json
import csv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from datetime import datetime  # Ensure this is imported
from dotenv import load_dotenv

# Load environment variables from .env file (if needed)
load_dotenv()

# Load the service account credentials from JSON in environment variable
if os.environ.get('SERVICE_ACCOUNT_JSON') is None:
    raise ValueError("SERVICE_ACCOUNT_JSON is not set! Please check your environment variable.")

try:
    service_account_info = json.loads(os.environ.get('SERVICE_ACCOUNT_JSON'))
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to decode SERVICE_ACCOUNT_JSON: {e}")

# Set up credentials using the loaded service account information
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=[
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/admin.directory.group'
    ]
)

# Delegate the credentials to the Super Admin account
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL')
if not SUPER_ADMIN_EMAIL:
    raise ValueError("SUPER_ADMIN_EMAIL is not set!")
delegated_credentials = credentials.with_subject(SUPER_ADMIN_EMAIL)

# Build the Drive API service
drive_service = build('drive', 'v3', credentials=delegated_credentials)

# Function to export shared drive ACLs to CSV
def export_shared_drive_acls():
    try:
        shared_drives = []
        page_token = None

        # Fetch all shared drives using pagination
        while True:
            response = drive_service.drives().list(
                useDomainAdminAccess=True,  # Use domain-wide access
                fields="nextPageToken, drives(id,name)",
                pageToken=page_token
            ).execute()

            shared_drives.extend(response.get('drives', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        if not shared_drives:
            print("No shared drives found.")
            return

        # Prepare CSV file
        filename = f'shared_drive_acls_{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Shared Drive Name', 'Shared Drive ID', 'Permission Email', 'Permission Role', 'Permission Type', 'Permission Display Name'])

            for drive in shared_drives:
                drive_id = drive['id']
                drive_name = drive['name']

                # Get ACLs for each shared drive
                try:
                    acls_page_token = None
                    while True:
                        acls_response = drive_service.permissions().list(
                            fileId=drive_id,
                            supportsAllDrives=True,
                            useDomainAdminAccess=True,  # Ensure we are using admin access
                            fields="nextPageToken, permissions(emailAddress,role,type,displayName)",
                            pageToken=acls_page_token
                        ).execute()

                        acls = acls_response.get('permissions', [])
                        for acl in acls:
                            writer.writerow([
                                drive_name,
                                drive_id,
                                acl.get('emailAddress', 'N/A'),
                                acl.get('role', 'N/A'),
                                acl.get('type', 'N/A'),
                                acl.get('displayName', 'N/A')
                            ])

                        acls_page_token = acls_response.get('nextPageToken')
                        if not acls_page_token:
                            break

                except HttpError as e:
                    print(f"Error fetching ACLs for {drive_name}: {e}")

        print(f"Shared Drive ACLs exported to {filename}")
        upload_to_drive(filename, os.environ.get('FOLDER_ID'))

    except HttpError as e:
        print(f"An error occurred: {e}")

# Function to upload the file to Google Drive
def upload_to_drive(filename, folder_id):
    try:
        media = MediaFileUpload(filename, mimetype='text/csv')
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        drive_service.files().create(
            body=file_metadata, media_body=media, fields='id', supportsAllDrives=True
        ).execute()
        print(f"File '{filename}' uploaded to Google Drive in folder ID: {folder_id}")
    except HttpError as e:
        print(f"Failed to upload file to Google Drive: {e}")

# Run the export
if __name__ == "__main__":
    if os.environ.get('FOLDER_ID') is None:
        raise ValueError("FOLDER_ID is not set!")
    export_shared_drive_acls()