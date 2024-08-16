import base64
import json
import os
import re
from email import header, message_from_bytes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the token.json file.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    # "https://www.googleapis.com/auth/gmail.compose",
    # "https://www.googleapis.com/auth/gmail.readonly",
    # "https://www.googleapis.com/auth/gmail.labels",
]

BASE_DIR = os.getenv("SECRETS_DIR")
SERVICE_FILE = os.getenv("GOOGLE_SERVICE_CREDENTIALS")
CREDENTIALS_FILE = os.getenv("GOOGLE_AUTH_CREDENTIALS")
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL")

def get_creds(SCOPES=SCOPES, renew=False, base_dir=BASE_DIR):
    """
    Obtains the user's credentials to access the Gmail API, with an option to renew credentials.

    Parameters:
        SCOPES (list): A list of strings representing the authorization scopes.
        renew (bool): If True, the existing token.json file will be deleted and new credentials will be obtained.

    Returns:
        Credentials: A Credentials object containing the user's access tokens.
    """
    creds = None
    token_json_path = os.path.join(base_dir, "token.json")
    credentials_path = CREDENTIALS_FILE

    # Delete the token.json file if renew is True
    if renew and os.path.exists(token_json_path):
        os.remove(token_json_path)

    # Attempt to load existing credentials
    if os.path.exists(token_json_path):
        creds = Credentials.from_authorized_user_file(token_json_path, SCOPES)

    # If credentials do not exist, are invalid, or expired, obtain new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error attempting to refresh the token: {e}")
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error obtaining new credentials: {e}")
                return None

        # Save the new credentials for future runs
        with open(token_json_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds

def get_service(subject_email=DEFAULT_EMAIL, base_dir=BASE_DIR):
    """
    Creates a Gmail service object authenticated via a service account with domain-wide delegation.

    This function initializes a service client for the Gmail API using delegated credentials
    from a service account. This allows the service account to act on behalf of a user within
    the domain, specified by the 'subject_email'.

    Args:
        base_dir (str): The base directory path where the service account JSON file is located.
        subject_email (str): The email address of the user for whom the service account is delegated.

    Returns:
        googleapiclient.discovery.Resource: An authorized Gmail API service instance.
    """
    service_file = SERVICE_FILE
    # Load the service account credentials from a JSON file.
    creds = service_account.Credentials.from_service_account_file(
        service_file, scopes=SCOPES
    )

    # Delegate credentials for the specified user within the domain.
    delegated_credentials = creds.with_subject(subject_email)
    # Build the Gmail service using the delegated credentials.
    service = build("gmail", "v1", credentials=delegated_credentials)
    return service

def get_or_create_label(
    subject_email,
    label_name="AI",
    text_color="#ffffff",
    bg_color="#a479e2",
):
    """
    Retrieves the ID of a Gmail label by its name or creates a new one if it does not exist.

    This function first attempts to find a label by the specified name. If it exists,
    the ID of the label is returned. If not, a new label with the provided name, text color,
    and background color is created, and its ID is returned.

    Args:
        subject_email (str): The email address of the user for whom the service account is delegated.
                             This user's Gmail account is searched for the label or is used to create the label.
        label_name (str): The name of the label to find or create.
        text_color (str): The text color of the label when created. Default is white ("#ffffff").
        bg_color (str): The background color of the label when created. Default is a shade of purple ("#a479e2").

    Returns:
        str: The ID of the existing or newly created label.

    Raises:
        googleapiclient.errors.HttpError: If an error occurs during API calls to Gmail.

    Examples:
        # Retrieve or create a label named 'AI' with default colors
        label_id = get_or_create_label(subject_email='user@example.com')

        # Retrieve or create a label with custom name and colors
        label_id = get_or_create_label(
            subject_email='user@example.com',
            label_name='Urgent',
            text_color='#FFFFFF',
            bg_color='#FF0000'
        )
    """
    service = get_service(subject_email=subject_email)
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    # Check if label exists
    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]

    # Create label if not found
    label_body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
        "color": {"textColor": text_color, "backgroundColor": bg_color},
    }
    label = service.users().labels().create(userId="me", body=label_body).execute()
    return label["id"]


def decode_mime_words(s):
    """
    Decodes MIME encoded-words in a string to a proper charset.

    MIME encoding is often used in email headers to allow for characters that are
    not supported by ASCII, such as international characters. This function takes a
    string with potential MIME encoded-words and decodes them to a readable format,
    defaulting to UTF-8 encoding if the charset is not specified.

    Args:
        s (str): The string containing MIME encoded-words.

    Returns:
        str: A decoded string with all MIME encoded-words converted to the specified
             or default charset.
    """
    # Decode each MIME encoded-word found in the string:
    return " ".join(
        word.decode(charset or "utf-8") if charset else str(word)
        for word, charset in header.decode_header(s)
    )

def extract_email_content(mime_msg):
    """
    Extracts the email content from a MIME message, preferring plain text but falling back to HTML if necessary.

    Parameters:
        mime_msg (email.message.EmailMessage): The MIME message object.

    Returns:
        str: The email content in plain text or HTML, with errors in encoding handled gracefully.
    """
    text_content = None
    html_content = None

    if mime_msg.is_multipart():
        for part in mime_msg.walk():
            content_type = part.get_content_type()
            charset = (
                part.get_content_charset() or "utf-8"
            )  # Default to UTF-8 if charset is not specified

            if content_type == "text/plain" and not text_content:
                try:
                    text_content = part.get_payload(decode=True).decode(
                        charset, errors="replace"
                    )
                except Exception as e:
                    print(f"Error decoding text/plain: {e}")
            elif content_type == "text/html" and not html_content:
                try:
                    html_content = part.get_payload(decode=True).decode(
                        charset, errors="replace"
                    )
                except Exception as e:
                    print(f"Error decoding text/html: {e}")
    else:
        payload = mime_msg.get_payload(decode=True)
        content_type = mime_msg.get_content_type()
        charset = mime_msg.get_content_charset() or "utf-8"

        if content_type == "text/plain":
            text_content = payload.decode(charset, errors="replace")
        elif content_type == "text/html":
            html_content = payload.decode(charset, errors="replace")

    # Prefer plain text over HTML
    return text_content if text_content is not None else html_content


def extract_email_ics(mime_msg):
    """
    Extracts specific attributes and the original content from a .ics file within a MIME message if available.

    Parameters:
        mime_msg (email.message.EmailMessage): The MIME message object.

    Returns:
        dict: A dictionary with specific parsed attributes and the raw .ics content for export, or None if no .ics file is found.
    """

    def parse_ics(content):
        """
        Parses the content of an ICS (iCalendar) file to extract key event-specific attributes,
        while also managing nested structures such as VEVENT and VALARM components.

        This function handles the continuation of lines (as denoted by lines beginning with spaces)
        by replacing '\r\n ' with an empty string, ensuring that the data is read as a continuous line.
        It selectively extracts data only from VEVENT blocks unless they are nested within VALARM blocks,
        ensuring that alarm-specific summaries do not overwrite event summaries.

        Parameters:
            content (str): A string containing the entire content of an ICS file.

        Returns:
            dict: A dictionary containing extracted data from the ICS file including:
                - 'summary': The summary or title of the event.
                - 'datetime_start': The start datetime of the event.
                - 'datetime_end': The end datetime of the event.
                - 'tzid': The timezone identifier.
                - 'organizer_name': The name of the organizer (if specified).
                - 'organizer_email': The email address of the organizer.
                - 'name': The name of the attendee (extracted from the ATTENDEE line).
                - 'email': The email of the attendee.
                - 'ics_file': The original raw content of the ICS file.

        The function uses state flags 'in_event' and 'in_alarm' to track whether the current line being
        parsed is within an event or an alarm. This is crucial to correctly associate properties like
        SUMMARY with either the event or the alarm.

        Example:
            parsed_data = parse_ics(content_of_ics_file)
            print(parsed_data['summary'])  # Outputs the summary of the event
        """
        # Handle line continuation as specified by the iCalendar standard
        lines = content.replace("\r\n ", "").replace("\n ", "").splitlines()
        in_event = False
        in_alarm = False
        in_timezone = False
        parsed_data = {
            "summary": "",
            "datetime_start": "",
            "datetime_end": "",
            "tzid": "",
            "organizer_name": "",
            "organizer_email": "",
            "attendees": [],
            "ics_file": content,  # Keep the original content
        }

        for line in lines:
            if line.startswith("BEGIN:VTIMEZONE"):
                in_timezone = True
            elif line.startswith("END:VTIMEZONE"):
                in_timezone = False
            elif line.startswith("BEGIN:VEVENT"):
                in_event = True
            elif line.startswith("END:VEVENT"):
                in_event = False
                parsed_data["tzid"] = tzid if 'tzid' in locals() else ""  # Assign TZID if available
            elif line.startswith("BEGIN:VALARM"):
                in_alarm = True
            elif line.startswith("END:VALARM"):
                in_alarm = False

            if in_timezone and line.startswith("TZID:"):
                tzid = line.split(":", 1)[1]  # Capture TZID from the VTIMEZONE component

            if in_event and not in_alarm:
                if line.startswith("SUMMARY:"):
                    parsed_data["summary"] = line.split(":", 1)[1]
                elif line.startswith("DTSTART:"):
                    parsed_data["datetime_start"] = line.split(":", 1)[1]
                elif line.startswith("DTEND:"):
                    parsed_data["datetime_end"] = line.split(":", 1)[1]
                elif "ORGANIZER" in line:
                    organizer_info = re.search(r"mailto:(.*)", line)
                    parsed_data["organizer_email"] = (
                        organizer_info.group(1) if organizer_info else ""
                    )
                    cn_info = re.search(r"CN=(.*?)(:|;)", line)
                    parsed_data["organizer_name"] = cn_info.group(1) if cn_info else ""
            if "ATTENDEE" in line and not in_alarm:
                attendee_info = re.search(r"mailto:(.*)", line)
                attendee_email = attendee_info.group(1) if attendee_info else ""
                cn_info = re.search(r"CN=(.*?)(:|;)", line)
                attendee_name = cn_info.group(1) if cn_info else ""
                parsed_data["attendees"].append({
                    "name": attendee_name,
                    "email": attendee_email
                })

        return parsed_data

    if mime_msg.is_multipart():
        for part in mime_msg.walk():
            if part.get_content_type() == "text/calendar":
                file_data = part.get_payload(decode=True)
                try:
                    decoded_file = file_data.decode("utf-8")
                    return parse_ics(decoded_file)
                except UnicodeDecodeError:
                    return {"Error": "Error decoding .ics file content"}
    return None


def get_last_5_emails(subject_email):
    """
    Retrieves the last 5 emails from secretaire@ophtalmologiste.be, including title, content in raw text, and any .ics file attachments in base64.

    Returns:
        A JSON formatted string containing details of the last 5 emails.
    """

    service = get_service(subject_email=subject_email)

    result = (
        service.users()
        .messages()
        .list(userId="me", q="from: secretaire@ophtalmologiste.be", maxResults=5)
        .execute()
    )
    messages = result.get("messages", [])

    emails_info = []

    for msg in messages:
        msg_id = msg["id"]
        message = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="raw")
            .execute()
        )

        # Decode email bytes and parse to MIME message
        msg_raw = base64.urlsafe_b64decode(message["raw"].encode("ASCII"))
        mime_msg = message_from_bytes(msg_raw)

        email_data = {
            "title": decode_mime_words(mime_msg["Subject"]),
            "content": extract_email_content(mime_msg),
            # "attachment": extract_email_ics(mime_msg),
        }

        # Check and handle for attachments and content here, as before.
        # This can be extended or modified to handle specific attachment types or additional email parts.

        emails_info.append(email_data)

    return json.dumps(emails_info, indent=4, ensure_ascii=False)


def get_new_email(
    subject_email: str,
    ai_label_id: str = "Label_15",
    query: str = "from: secretaire@ophtalmologiste.be is:unread",
    maxResult: int = 5,
    mark_as_read: bool = False,
):
    """
    Retrieves new (unread) emails from secretaire@ophtalmologiste.be, including title, content in raw text,
    and any .ics file attachments in base64. Optionally marks retrieved emails as read.

    Args:
        subject_email (str): The email used to authenticate and use the Gmail API service.
        ai_label_id (str): The Gmail label ID to add to emails that don't already have it.
        query (str): The query to filter the emails.
        maxResult (int): The maximum number of emails to retrieve.
        mark_as_read (bool): Whether to mark the retrieved emails as read. Defaults to True.

    Returns:
        A JSON formatted string containing details of new emails.
    """
    service = get_service(subject_email=subject_email)

    # Query for unread emails from the specific sender
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=maxResult)
        .execute()
    )
    messages = result.get("messages", [])

    emails_info = []

    for msg in messages:
        msg_id = msg["id"]
        message = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="raw")
            .execute()
        )

        # Decode email bytes and parse to MIME message
        msg_raw = base64.urlsafe_b64decode(message["raw"].encode("ASCII"))
        mime_msg = message_from_bytes(msg_raw)

        email_data = {
            "title": decode_mime_words(mime_msg["Subject"]),
            "content": extract_email_content(mime_msg),
            "attachment_ics": extract_email_ics(
                mime_msg
            ),  # extract only if content_type is "text/calendar"
        }

        emails_info.append(email_data)

        # Check current labels and add 'ai_label_id' if not present
        existing_labels = message.get("labelIds", [])
        if ai_label_id not in existing_labels:
            body = {"addLabelIds": [ai_label_id]}  # Add a custom label by its ID
            service.users().messages().modify(
                userId="me", id=msg_id, body=body
            ).execute()
        
        # Mark as read if the mark_as_read flag is True
        if mark_as_read:
            service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()

    return json.dumps(emails_info, indent=4, ensure_ascii=False)

def create_draft_email(subject: str,
                     content: str = "<html><body><p>Bonjour, <\br> nous allons répondre à votre email dans les plus brefs délais.</p></body></html>",
                     subject_email: str = DEFAULT_EMAIL
                     ):
    """
    Creates a draft email with the specified subject, label, and content.

    Args:
        subject (str): The subject of the email, defaulting to the given suffix.
        ai_label_id (str): The Gmail label ID to add to the email.
        content (str): The HTML content of the email.

    Returns:
        A dictionary containing information about the created draft.
    """
    
    # Step 1: Prepare the MIME message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject + " | Centre Médical Bruxelles-Schuman" if subject else " | Centre Médical Bruxelles-Schuman"
    message.attach(MIMEText(content, "html"))

    # Encode the message as base64 and prepare the draft body
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft_body = {
        "message": {
            "raw": raw_message,
        }

    }
    # Step 2: Create the draft
    service = get_service(subject_email=subject_email)
    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    draft_id = draft["id"]

    # Step 3: Update the draft by prefixing the subject with the draft ID
    new_subject = f"DRAFT#{draft_id} {message["Subject"]}"
    message.replace_header("Subject", new_subject)

    # Encode the updated message
    updated_raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Prepare the updated draft body
    updated_draft_body = {
        "message": {
            "raw": updated_raw_message,
        }
    }

    # Update the draft with the new subject
    updated_draft = service.users().drafts().update(userId="me", id=draft_id, body=updated_draft_body).execute()
    
    return updated_draft