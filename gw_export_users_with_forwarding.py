"""
Script: exportGoogleForwardingSettingsToDrive - Export Users with Forwarding Settings to Google Drive

Description:
This Python script automates the process of exporting all active Google Workspace users who have email forwarding 
settings enabled. The script retrieves the forwarding email addresses and their dispositions (`leaveInInbox`, 
`markRead`, `archive`, `trash`) and exports them to a CSV file. The file is then uploaded to a specified folder 
within a shared Google Drive. The script includes error handling for API rate limits (429 errors) and mail service 
unavailability (400 errors). It is designed to run in a GitHub Actions environment, using secrets stored in GitHub 
for secure access to sensitive information.

Functions:
- get_active_users(customer_id): Retrieves all active users in the Google Workspace domain.
- get_forwarding_settings(user_email, retries=5, delay=30): Retrieves the forwarding settings and disposition for a 
  specific user, with retry mechanisms for handling rate limit (429) errors.
- upload_to_drive(filename, folder_id): Uploads the CSV file to the specified Google Drive folder, with support for 
  shared drives.
- export_users_with_forwarding_to_csv(users): The main function that:
  1. Generates a timestamped CSV file containing the forwarding settings and dispositions.
  2. Saves the CSV file to a specified Google Drive folder.

Usage:
1. **Environment Variables**:
   - The script relies on four environment variables, which should be provided via GitHub Secrets:
     - `SERVICE_ACCOUNT_JSON`: Contains the service account credentials in JSON format.
     - `FOLDER_ID`: The ID of the Google Drive folder where the CSV file will be uploaded.
     - `SUPER_ADMIN_EMAIL`: The super admin email address used for domain-wide delegation.
     - `CUSTOMER_ID`: The customer ID for the Google Workspace domain.
   
2. **User Retrieval**:
   - The script retrieves all active users in the domain using the Google Admin SDK Directory API.
   - It then checks the forwarding settings for each user and exports only those with forwarding enabled.

3. **Google Drive Folder**:
   - The script uploads the generated CSV file to a specific Google Drive folder, identified by its folder ID.

4. **Error Handling**:
   - The script includes error handling to manage issues such as rate limit exceeded (429 errors) and mail service 
     not enabled (400 errors).
   - If a file upload fails due to an API or SSL error, the script retries the upload operation.

Notes:
- **Permissions:** The script requires domain-wide delegation to access the Gmail API and Google Admin SDK Directory API. 
  Ensure that the necessary OAuth scopes are authorized for the service account.
- **GitHub Actions Integration:** This script is designed to be run within a GitHub Actions workflow, with secrets for 
  sensitive information stored securely in GitHub.
- **Customization:** You can adjust the retry mechanisms and delays for handling rate limit or API errors to suit your environment.

Author: Chad Ramey  
Date: September 9, 2024
"""

import csv
import time
import os
import json
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from datetime import datetime

# Load the service account credentials from JSON
if os.environ.get('SERVICE_ACCOUNT_JSON') is None:
    raise ValueError("SERVICE_ACCOUNT_JSON is not set! Please check your environment variable.")

try:
    service_account_info = json.loads(os.environ.get('SERVICE_ACCOUNT_JSON'))
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to decode SERVICE_ACCOUNT_JSON: {e}")

credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=[
        'https://www.googleapis.com/auth/admin.directory.user.readonly',
        'https://www.googleapis.com/auth/gmail.settings.basic',
        'https://www.googleapis.com/auth/drive.file'
    ]
)

# Delegate the credentials to the Super Admin account
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL')
if not SUPER_ADMIN_EMAIL:
    raise ValueError("SUPER_ADMIN_EMAIL is not set!")

delegated_credentials = credentials.with_subject(SUPER_ADMIN_EMAIL)

# Build the Admin SDK Directory API service
admin_service = build('admin', 'directory_v1', credentials=delegated_credentials)

# Build the Drive API service
drive_service = build('drive', 'v3', credentials=delegated_credentials)

# Function to retrieve only active users from Google Workspace
def get_active_users(customer_id):
    users = []
    try:
        results = admin_service.users().list(customer=customer_id, maxResults=500, orderBy='email').execute()
        users.extend(results.get('users', []))
        while 'nextPageToken' in results:
            results = admin_service.users().list(customer=customer_id, maxResults=500, orderBy='email', pageToken=results['nextPageToken']).execute()
            users.extend(results.get('users', []))
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # Filter out suspended users
    active_users = [user for user in users if not user.get('suspended', False)]
    
    return active_users

# Function to get forwarding settings and disposition for a user with retry on rate limits
def get_forwarding_settings(user_email, retries=5, delay=30):
    for attempt in range(retries):
        try:
            delegated_credentials = credentials.with_subject(user_email)
            gmail_service = build('gmail', 'v1', credentials=delegated_credentials)

            # Request forwarding settings for the user
            settings = gmail_service.users().settings().getAutoForwarding(userId='me').execute()

            if settings['enabled']:
                # Return the forwarding email and the disposition
                return settings.get('emailAddress', 'N/A'), settings.get('disposition', 'N/A')
            else:
                return None, None
        except HttpError as e:
            if e.resp.status == 429:
                print(f"Rate limit exceeded for {user_email}, retrying in {delay} seconds (Attempt {attempt + 1}/{retries})...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Could not retrieve forwarding settings for {user_email}: {e}")
                return None, None
    print(f"Rate limit exceeded for {user_email} after {retries} attempts, skipping...")
    return None, None  # Always return a tuple, even on failure

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

# Function to export users with forwarding enabled to a CSV
def export_users_with_forwarding_to_csv(users):
    filename = f'active_users_with_forwarding_{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
    headers = ['Primary Email', 'Full Name', 'Forwarding Email Address', 'Disposition']

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(headers)

        for user in users:
            forwarding_email, disposition = get_forwarding_settings(user['primaryEmail'])
            if forwarding_email:
                writer.writerow([
                    user['primaryEmail'],
                    user['name']['fullName'],
                    forwarding_email,
                    disposition
                ])

    print(f'CSV file {filename} has been successfully created!')
    upload_to_drive(filename, os.environ.get('FOLDER_ID'))  # Upload to Google Drive

if __name__ == '__main__':
    CUSTOMER_ID = os.environ.get('CUSTOMER_ID')
    if not CUSTOMER_ID:
        raise ValueError("CUSTOMER_ID is not set!")

    active_users = get_active_users(CUSTOMER_ID)
    if active_users:
        export_users_with_forwarding_to_csv(active_users)
    else:
        print('No active users found or an error occurred.')
