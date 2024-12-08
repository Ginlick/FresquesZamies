import os.path
import datetime
from typing import List

from google.auth.transport.requests import Request
from attrs import define, field
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
def get_language_strings(sheetName, range):
    values = get_trix(SAMPLE_SPREADSHEET_ID, sheetName + "!" + range)
    a = []
    for row in values[1:]:
        if row[0]:  # skip empty rows
            d = dict()
            i = 0
            for i, column in enumerate(values[0]):
                d[column] = row[i]
            a.append(d)
    return a


# TODO: move this to a library.
@define
class Event:
    name: str
    date: datetime.date
    location: str
    url: str
    language: str
    organizer: str = None
    city: str = None


# Returns events read from a Google sheet.
# The first row is assumed to contain column headers.
# The header variables the column names to use for each corresponding to Event field.
# If validHeader is not empty, the cell must contain "Yes" for the row to be picked up.
# Languages are comma-separated. Multiple events are created for events with multiple languages.
def get_manual_events(
    sheetId: str,
    sheetNameAndRange: str,
    workshopHeader: str,
    dateHeader: str,
    locationHeader: str,
    urlHeader: str,
    languagesHeader: str,
    validHeader: str,
    organizer: str,
) -> List[Event]:
    values = get_trix(sheetId, sheetNameAndRange)
    row = values[0]
    indices = dict()
    for i, cell in enumerate(row):
        indices[cell] = i
    a = []
    for row in values[1:]:
        if len(row) == 0:
            continue  # skip empty row
        if validHeader:
            index = indices[validHeader]
            if index >= len(row) or row[index] != "Yes":
                continue  # skip incomplete or unwanted row
        languages = row[indices[languagesHeader]]
        for language in languages.split(","):
            a.append(
                Event(
                    name=row[indices[workshopHeader]],
                    date=datetime.datetime.strptime(
                        row[indices[dateHeader]], "%A, %B %d, %Y"
                    ),
                    location=row[indices[locationHeader]],
                    url=row[indices[urlHeader]],
                    organizer=organizer,
                    language=language,
                )
            )
    return a


# TODO: move this to a library.
@define
class WorkshopMetadata:
    title: str
    language: str
    calendar_link: str
    site_link: str


# Returns the list of calendars to read.
def get_workshops() -> List[WorkshopMetadata]:
    values = get_trix(SAMPLE_SPREADSHEET_ID, "Workshops")
    a = []
    for row in values:
        if row[0] == "TRUE":  # skip non-enabled rows
            a.append(
                WorkshopMetadata(
                    title=row[1],
                    language=row[2],
                    calendar_link=row[3],
                    site_link=row[4],
                )
            )
    return a


if __name__ == "__main__":
    main()
