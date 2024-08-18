# main.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi import Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse
import httpx
from pydantic import BaseModel
from typing import List, Optional
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

class Merchant(BaseModel):
    name: str
    address: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    gst_registration: Optional[str] = None

class Item(BaseModel):
    item: str
    quantity: Optional[int] = 1
    unit_price: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    price: float
    category: str

class TotalPrice(BaseModel):
    subtotal_before_tax: float
    discount: Optional[float] = 0.0
    gst: Optional[float] = 0.0
    total_after_tax: float

class Payment(BaseModel):
    rounding_adjustment: Optional[float] = 0.0
    total_paid_amount: float
    payment_method: Optional[str] = None

class GSTSummary(BaseModel):
    tax_rate: Optional[float] = None
    amount_before_gst: Optional[float] = None

class Output(BaseModel):
    merchant: Merchant
    date: Optional[str] = None
    time: Optional[str] = None
    invoice_number: Optional[str] = None
    order_number: Optional[str] = None
    currency: Optional[str] = None
    items_list: List[Item]
    total_price: TotalPrice
    payment: Payment
    gst_summary: Optional[GSTSummary] = None

class TicketData(BaseModel):
    output: Output

@app.post("/generateTicket")
async def generate_ticket(ticket_data: List[TicketData]):
    for data_item in ticket_data:
        receipt = data_item.output

        # Generate HTML as before using the 'receipt' object
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Receipt</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }}
                .receipt-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    border: 1px solid #ddd;
                    padding: 20px;
                    border-radius: 8px;
                }}
                .receipt-header, .receipt-footer {{
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .receipt-header h2, .receipt-footer h3 {{
                    margin: 0;
                }}
                .receipt-details {{
                    margin-bottom: 20px;
                }}
                .receipt-details p {{
                    margin: 5px 0;
                }}
                .items-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                .items-table th, .items-table td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                .items-table th {{
                    background-color: #f2f2f2;
                }}
                .total-summary {{
                    margin-top: 20px;
                    text-align: right;
                }}
                .total-summary p {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="receipt-container">
                <!-- Receipt Header -->
                <div class="receipt-header">
                    <h2>{receipt.merchant.name}</h2>
                    <p>{receipt.merchant.address}</p>
                    {"<p>Contact: " + receipt.merchant.contact + "</p>" if receipt.merchant.contact else ''}
                    {"<p>Email: " + receipt.merchant.email + "</p>" if receipt.merchant.email else ''}
                    {"<p>GST Registration: " + receipt.merchant.gst_registration + "</p>" if receipt.merchant.gst_registration else ''}
                </div>

                <!-- Receipt Details -->
                <div class="receipt-details">
                    <p><strong>Date:</strong> {receipt.date}</p>
                    <p><strong>Time:</strong> {receipt.time}</p>
                    <p><strong>Invoice Number:</strong> {receipt.invoice_number}</p>
                    <p><strong>Order Number:</strong> {receipt.order_number}</p>
                    <p><strong>Currency:</strong> {receipt.currency}</p>
                </div>

                <!-- Item Details -->
                <table class="items-table">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Category</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Discount</th>
                            <th>Total Price</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for item in receipt.items_list:
            html += f"""
                        <tr>
                            <td>{item.item}</td>
                            <td>{item.category}</td>
                            <td>{item.quantity}</td>
                            <td>{item.unit_price}</td>
                            <td>{item.discount}</td>
                            <td>{item.price}</td>
                        </tr>
            """

        html += f"""
                    </tbody>
                </table>

                <!-- Total Summary -->
                <div class="total-summary">
                    <p><strong>Subtotal (Before Tax):</strong> {receipt.total_price.subtotal_before_tax}</p>
                    <p><strong>Discount:</strong> {receipt.total_price.discount}</p>
                    <p><strong>GST:</strong> {receipt.total_price.gst}</p>
                    <p><strong>Total (After Tax):</strong> {receipt.total_price.total_after_tax}</p>
                    {"<p><strong>Rounding Adjustment:</strong> " + str(receipt.payment.rounding_adjustment) + "</p>" if receipt.payment.rounding_adjustment else ''}
                    <p><strong>Total Paid Amount:</strong> {receipt.payment.total_paid_amount}</p>
                    <p><strong>Payment Method:</strong> {receipt.payment.payment_method}</p>
                </div>

                <!-- GST Summary -->
                <div class="gst-summary">
                    {"<p><strong>GST Rate:</strong> " + str(receipt.gst_summary.tax_rate) + "%</p>" if receipt.gst_summary and receipt.gst_summary.tax_rate is not None else ''}
                    {"<p><strong>Amount Before GST:</strong> " + str(receipt.gst_summary.amount_before_gst) + "</p>" if receipt.gst_summary and receipt.gst_summary.amount_before_gst is not None else ''}
                </div>

                <!-- Receipt Footer -->
                <div class="receipt-footer">
                    <h3>Thank you for your purchase!</h3>
                </div>
            </div>
        </body>
        </html>
        """

        # Save the generated HTML to a file
        with open("lastticket.html", "w", encoding="utf-8") as file:
            file.write(html)

    return {"message": "HTML ticket generated successfully!"}

# Utiliser Jinja2 pour gérer les templates HTML
templates = Jinja2Templates(directory="templates")

# URL cible pour le POST
# WEBHOOK_URL = "https://n8.c54.ovh/webhook-test/9bc9b752-c660-41ac-9294-99e5e0f12b03"
WEBHOOK_URL= "https://n8.c54.ovh/webhook/9bc9b752-c660-41ac-9294-99e5e0f12b03"

@app.get("/uploadTicket", response_class=HTMLResponse)
async def upload_ticket_form(request: Request):
    return templates.TemplateResponse("upload_ticket.html", {"request": request})

@app.post("/uploadTicket")
async def upload_ticket(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Vérifier si le fichier est bien un JPG
    if file.content_type != "image/jpeg":
        return HTMLResponse(content="Invalid file type. Only JPG images are accepted.", status_code=400)

    # Lire le contenu du fichier une seule fois ici
    file_content = await file.read()

    # Envoyer le fichier en arrière-plan pour ne pas bloquer la réponse
    background_tasks.add_task(send_file_to_webhook, file.filename, file_content, file.content_type)

    # Retourner la réponse HTML
    return templates.TemplateResponse("upload_ticket.html", {
        "request": request,
        "message": "File uploaded successfully and sent to the webhook!"
    })

async def send_file_to_webhook(filename: str, content: bytes, content_type: str):
    # Envoyer le fichier au webhook en POST
    async with httpx.AsyncClient() as client:
        files = {'file': (filename, content, content_type)}
        response = await client.post(WEBHOOK_URL, files=files)
        response.raise_for_status()

@app.get("/viewTicket")
async def view_ticket():
    try:
        file_path = os.path.abspath("lastticket.html")
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type='text/html')
        else:
            raise HTTPException(status_code=404, detail="Ticket not found. Please generate a ticket first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")