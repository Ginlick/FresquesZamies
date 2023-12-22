import os.path
import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "1totCMhD_sRcU1b3JNICTUWXcYoYPOjQRo9KLv8NW4x8"


def get_trix(spreadsheetId, spreadsheetRange):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=spreadsheetId, range=spreadsheetRange)
            .execute()
        )
        return result.get("values", [])
    except HttpError as err:
        print(err)


# Returns an array of dictionaries read from a Google Sheet.
# The keys of each dictionnary are the values on the first (header) row.
def get_language_strings(sheetName):
    values = get_trix(SAMPLE_SPREADSHEET_ID, sheetName + "!A1:D50")
    a = []
    for row in values[1:]:
        if row[0]:  # skip empty rows
            d = dict()
            i = 0
            for i, column in enumerate(values[0]):
                d[column] = row[i]
            a.append(d)
    return a


# Returns extra events we are aware of: (title, event name, date, place, url, language, organizer)
def get_manual_events():
    values = get_trix(SAMPLE_SPREADSHEET_ID, "Manuel!A2:G50")
    a = []
    for row in values:
        if row[0]:  # skip empty rows
            a.append(
                (
                    row[0],
                    row[0],
                    datetime.date(int(row[1]), int(row[2]), int(row[3])),
                    row[4],
                    row[5],
                    row[6],
                )
            )
    return a


def main():
    a = get_language_strings()
    print(a)


if __name__ == "__main__":
    main()
