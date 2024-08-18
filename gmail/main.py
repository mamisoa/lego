# main.py
import os, json
from pydantic import BaseModel, Field
from typing import Optional
from utils import get_last_5_emails, get_new_email, create_draft_email, delete_email_by_id
from fastapi import FastAPI, Body, HTTPException

# service_file = os.getenv("GOOGLE_SERVICE_CREDENTIALS", "/app/secrets/service.json")
# credentials_file = os.getenv("GOOGLE_AUTH_CREDENTIALS", "/app/secrets/credentials.json")
default_email = os.getenv("DEFAULT_EMAIL")

# with open(service_file) as f:
#     SERVICE = json.load(f)

# with open(credentials_file) as f:
#     CREDENTIALS = json.load(f)

app = FastAPI()

class EmailParams(BaseModel):
    subject_email: str = default_email
    ai_label_id: Optional[str] = "Label_15"
    query: Optional[str] = "is:unread"
    # maxResult: Optional[int] = 5
    mark_as_read: Optional[bool] = False

class DraftEmailParams(BaseModel):
    subject: Optional[str] = Field(default="")
    content: Optional[str] = Field(default="<html><body><p>Bonjour, nous allons répondre à votre email dans les plus brefs délais.</p></body></html>")

@app.get("/")
def read_root():
    return {"app": "FastAPI gmail server"}

@app.get("/last5")
def last_5():
    return get_last_5_emails(subject_email=default_email)

@app.post("/getNewEmail")
async def get_new_email_endpoint(
    params: EmailParams = Body(...)
):
    result = get_new_email(
        subject_email=params.subject_email,
        ai_label_id=params.ai_label_id,
        query=params.query,
        # maxResult=params.maxResult,
        mark_as_read=params.mark_as_read,
    )
    return json.loads(result)

@app.post("/createDraftEmail")
async def create_draft_email_endpoint(params: DraftEmailParams = Body(...)):
    # Appeler la fonction pour créer le brouillon
    draft = create_draft_email(
        subject=params.subject,
        content=params.content
    )
    return draft

@app.delete("/delete-email/{message_id}")
def delete_email(message_id: str, subject_email: str):
    """
    Endpoint to delete an email by its message ID.

    Args:
        message_id (str): The ID of the email message to be deleted.
        subject_email (str): The email used to authenticate and use the Gmail API service.

    Returns:
        JSON response indicating success or failure.
    """
    result = delete_email_by_id(subject_email, message_id)
    
    result_dict = json.loads(result)

    if result_dict["status"] == "error":
        raise HTTPException(status_code=500, detail=result_dict["message"])

    return result_dict