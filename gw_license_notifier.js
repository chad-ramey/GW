/*
 * Script Name: Google Workspace License Notifier
 * Author: Chad Ramey
 * Date: July 1, 2024
 * Forked from Goldy Arora https://www.goldyarora.com/blog/license-notifier
 * 
 * Description:
 * This script fetches license data from Google Workspace, checks the remaining license counts against predefined thresholds, 
 * and sends notifications to Slack channels when thresholds are met. It also allows manual generation of license reports 
 * that can be sent to Slack channels.
 * 
 * Requirements:
 * - Google Admin SDK enabled for License Manager API
 * - Slack webhooks for notifications
 * - The script is triggered by a custom menu added to Google Sheets.
 * 
 * Dependencies:
 * - Google Admin License Manager API
 * - Slack API for sending notifications via webhooks
 * 
 */

// Adds a custom menu to the Google Sheet upon opening
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('CollabSys') // Custom menu for Collaboration Systems
    .addItem('Get Licenses', 'getLicenses') // Option to fetch licenses
    .addItem('Send Report', 'buildReport') // Option to send a report
    .addToUi();
}

// SKU ID to Name mapping for Google Workspace license types
const skuIdToNameMapping = {
  "1010020020": "Google Workspace Enterprise Plus",
  "1010020026": "Google Workspace Enterprise Standard",
  "1010340001": "Google Workspace Enterprise Plus - Archived User",
  "1010340004": "Google Workspace Enterprise Standard - Archived User",
  "1010470001": "Gemini"
  // Add any additional SKU mappings here
};

// Fetches the license data from Google Workspace and writes it to the 'License Notifier' sheet
function getLicenses() {
  const sheet = SpreadsheetApp.getActive().getSheetByName("License Notifier");
  const domainName = Session.getActiveUser().getEmail().replace(/.*@/, ""); // Extracts domain from user email
  let fileArray = [["User Email", "Assigned License"]]; // Headers for license data

  const productIds = [
    "Google-Apps",
    "101031",
    "Google-Drive-storage",
    "Google-Vault",
    "101001",
    "101005",
    "101033",
    "101034",
    "101047"
  ];

  // Fetch license data for each product
  productIds.forEach(product => {
    let pageToken;
    do {
      let optionalArgs = { maxResults: 100, pageToken: pageToken }; // Pagination to handle large datasets
      try {
        const page = AdminLicenseManager.LicenseAssignments.listForProduct(product, domainName, optionalArgs);
        page.items.forEach(prod => {
          const skuName = skuIdToNameMapping[prod.skuId] || prod.skuId; // Map SKU ID to name, or use ID if no mapping is found
          fileArray.push([prod.userId, skuName]); // Add license data to array
        });
        pageToken = page.nextPageToken; // Continue to next page if token exists
      } catch (error) {
        Logger.log("Error fetching license data for product " + product + ": " + error); // Log error in case of failure
        return;
      }
    } while (pageToken);
  });

  // Clears existing content in the 'License Notifier' sheet from row 2 onwards
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) { // Only clear if there is data beyond the header
    sheet.getRange(2, 1, lastRow - 1, 2).clearContent();
  }

  // Writes the fetched license data into the sheet
  sheet.getRange(2, 1, fileArray.length - 1, 2).setValues(fileArray.slice(1)); // Skips header when writing data

  // Check licenses against thresholds and send alerts if needed
  checkAndNotifyForLicenses();
}

// License thresholds to trigger alerts
const licenseThresholds = {
  "Google Workspace Enterprise Plus": 20,
  "Google Workspace Enterprise Standard": 20,
  "Google Workspace Enterprise Plus - Archived User": 0,
  "Google Workspace Enterprise Standard - Archived User": 0,
  "Gemini": 0
  // Add more thresholds as needed
};

// Checks licenses in the sheet against thresholds and sends Slack alerts if necessary
function checkAndNotifyForLicenses() {
  const sheet = SpreadsheetApp.getActive().getSheetByName("License Notifier");
  const licenseDataRange = sheet.getRange("E2:F" + sheet.getLastRow()); // Fetches license data from columns E and F
  const licenseData = licenseDataRange.getValues();
  let alertsToSend = [];

  // Compare license counts to thresholds
  licenseData.forEach(row => {
    const licenseType = row[0]; // License name
    const licensesLeft = row[1]; // Remaining licenses
    const threshold = licenseThresholds[licenseType]; // Threshold for this license type

    // If remaining licenses are at or below the threshold, prepare an alert
    if (threshold !== undefined && licensesLeft <= threshold) {
      alertsToSend.push(`${licenseType} has only ${licensesLeft} licenses left, which is at or below the threshold of ${threshold}.`);
    }
  });

  // Send alerts if any licenses are below thresholds
  if (alertsToSend.length > 0) {
    sendAlertToSlack(alertsToSend.join("\n")); // Send a combined alert message
  }
}

// Constructs and sends Slack alerts for low license counts
function sendAlertToSlack(message) {
  const payload = {
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": message // Message text to display in Slack
        }
      }
    ]
  };
  sendAlert(payload);
}

// Builds a summary report of the license counts and sends it to Slack
function buildReport() {
  const ss = SpreadsheetApp.getActive();
  let data = ss.getSheetByName('License Notifier').getRange("E1:F6").getValues(); // Fetches license data summary
  let payload = buildAlert(data); // Constructs a Slack message payload
  sendAlert(payload); // Sends the report to Slack channels
}

// Constructs the payload for the Slack alert message with license breakdown
function buildAlert(data) {
  let licenseBreakdown = data.slice(1).map(function(row) {
    return row[0] + ": " + row[1]; // Format each license type and its count
  }).join("\n");

  let payload = {
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": ":ice_cube::robot_face::google: *Available GW Licenses* :google::robot_face::ice_cube:" // Header text for the Slack message
        }
      },
      {
        "type": "divider"
      },
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": licenseBreakdown // Detailed breakdown of license counts
        }
      }
    ]
  };
  return payload;
}


// Send alert to multiple Slack channels
function sendAlert(payload) {
  const webhooks = [
    "https://hooks.slack.com/services/"  // Slack channel webhook
  ];

  var options = {
    "method": "post", 
    "contentType": "application/json", 
    "muteHttpExceptions": true, 
    "payload": JSON.stringify(payload) 
  };

  webhooks.forEach(webhook => {
    try {
      UrlFetchApp.fetch(webhook, options);
    } catch(e) {
      Logger.log("Error sending alert to Slack: " + e);
    }
  });
}