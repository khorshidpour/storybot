from flask import Flask, request
import requests
from config import BOT_TOKEN, FLOWISE_ENDPOINT, BASE_URL, YOUR_CLIENT_ID, YOUR_CLIENT_SECRET, PAYPAL_MODE 
from story_session import start_session, update_session, get_session, mark_paid, reset_session
import paypalrestsdk

# Steps:
# communication with Telegram
# story session management
# payment processing with PayPal
# talking to your Flowise AI endpoint



app = Flask(__name__)
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

paypalrestsdk.configure({
    "mode": "{PAYPAL_MODE}",
    "client_id": "{YOUR_CLIENT_ID}",
    "client_secret": "{YOUR_CLIENT_SECRET}"
})

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        handle_message(chat_id, text)
    return "ok"

def send_message(chat_id, text, buttons=None):
    payload = {"chat_id": chat_id, "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": b[0], "url": b[1]}] for b in buttons]}
    requests.post(TELEGRAM_API, json=payload)

def handle_message(chat_id, text):
    session = get_session(chat_id)
    if not session:
        start_session(chat_id)
        payment_link = f"{BASE_URL}/pay/{chat_id}"
        send_message(chat_id, "Welcome! Please pay $0.20 to start your story.", buttons=[["Pay Now", payment_link]])
        return

    if not session["paid"]:
        send_message(chat_id, "Please complete payment first.")
        return

    step = session["step"]
    if step == "collecting_info":
        if "name" not in session["data"]:
            update_session(chat_id, "name", text)
            send_message(chat_id, "What is the child's gender? (e.g., boy/girl)")
        elif "gender" not in session["data"]:
            update_session(chat_id, "gender", text)
            send_message(chat_id, "What is the child's age?")
        elif "age" not in session["data"]:
            update_session(chat_id, "age", text)
            send_message(chat_id, "What language should the story be in?")
        elif "language" not in session["data"]:
            update_session(chat_id, "language", text)
            send_message(chat_id, "Any specific challenge or theme?")
        elif "challenge" not in session["data"]:
            update_session(chat_id, "challenge", text)
            send_message(chat_id, "Any special character or element to include?")
        else:
            update_session(chat_id, "element", text)
            generate_story(chat_id)

def generate_story(chat_id):
    session = get_session(chat_id)
    info = session["data"]
    prompt = (
        f"Write a story for a {info['age']}-year-old {info['gender']} named {info['name']} "
        f"in {info['language']}. The story should be about {info['challenge']} "
        f"and include {info['element']}."
    )
    response = requests.post(FLOWISE_ENDPOINT, json={"question": prompt})
    story = response.json().get("text", "Sorry, there was an error generating the story.")
    send_message(chat_id, story)
    reset_session(chat_id)

@app.route("/pay/<chat_id>")
def pay(chat_id):
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "redirect_urls": {
            "return_url": f"{BASE_URL}/success/{chat_id}",
            "cancel_url": f"{BASE_URL}/cancel"
        },
        "payer": {"payment_method": "paypal"},
        "transactions": [{
            "amount": {"total": "0.20", "currency": "USD"},
            "description": "Personalized children's story"
        }]
    })
    if payment.create():
        for link in payment.links:
            if link.method == "REDIRECT":
                return f'<meta http-equiv="refresh" content="0; url={link.href}" />'
    return "<h1>خطا در ایجاد پرداخت.</h1>"

@app.route("/success/<chat_id>")
def success(chat_id):
    mark_paid(int(chat_id))
    return "<h1>پرداخت موفق! لطفاً به تلگرام برگردید.</h1>"

@app.route("/cancel")
def cancel():
    return "<h1>پرداخت لغو شد.</h1>"
