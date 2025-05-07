from flask import Flask, request
import requests
import paypalrestsdk
from config import BOT_TOKEN, FLOWISE_ENDPOINT, BASE_URL, PAYPAL_CLIENT_ID, PAYPAL_SECRET, PAYPAL_MODE
from story_session import *

app = Flask(__name__)
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# print("\n\n✅ TOKEN:", BOT_TOKEN)

WELCOME_TEXT = (
    "✨ *Hi, I'm your Magical Storyteller Bot!* ✨\n\n"
    "I create personalized, heartwarming stories for children based on the details you provide – name, age, favorite characters, and even special challenges.\n\n"
    "To start this magical journey, please pay just *$0.01* ✨"
)

# پیکربندی PayPal
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_SECRET
})

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        handle_message(chat_id, text)

    #print("📥 Message received:", data)
    #if "message" in data:
    #    chat_id = data["message"]["chat"]["id"]
    #    send_message(chat_id, "✅ پیام شما دریافت شد.")
    return "ok"

def send_message(chat_id, text, buttons=None):
    payload = {"chat_id": chat_id, "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": b[0], "url": b[1]}] for b in buttons]}
    requests.post(TELEGRAM_API, json=payload)


def handle_message(chat_id, text):

    if text.strip().lower() == "/start":
        reset_session(chat_id)
        start_session(chat_id)
        payment_link = f"{BASE_URL}/pay/{chat_id}"
        send_message(chat_id, WELCOME_TEXT, buttons=[["🔮 Pay & Begin", payment_link]])
        return
     
    session = get_session(chat_id)

    # If no session exists, send payment link
    if not session:
        start_session(chat_id)
        payment_link = f"{BASE_URL}/pay/{chat_id}"
        send_message(chat_id, WELCOME_TEXT, buttons=[["🔮 Pay & Begin", payment_link]])
        return

    # If payment not completed, stop here
    if not session.get("paid"):
        send_message(chat_id, "💳 Please complete the payment first.")
        return
        
    step = session.get("step")
    if step == "collecting_info":
        # 🔸 Check if session has expired (after payment)
        if is_session_expired(session):
            refunded = issue_refund(chat_id)
            if refunded:
                send_message(chat_id, "⏰ Your session expired due to inactivity. Payment has been refunded. Please start again.")
            else:
                send_message(chat_id, "⚠️ Session expired, but refund failed. Please contact support.")
            reset_session(chat_id)
            start_session(chat_id)
            payment_link = f"{BASE_URL}/pay/{chat_id}"
            send_message(chat_id, WELCOME_TEXT, buttons=[["🔮 Pay & Begin", payment_link]])
            return

        # 🔸 Update last activity
        session["last_active"] = datetime.utcnow()
        save_session(chat_id, session)

        # Check which info is missing and ask next
        if "name" not in session["data"]:
            update_session(chat_id, "name", text)
            send_message(chat_id, "🧒 What is the child's gender? (e.g., boy/girl)")
        elif "gender" not in session["data"]:
            update_session(chat_id, "gender", text)
            send_message(chat_id, "🎂 What is the child's age?")
        elif "age" not in session["data"]:
            update_session(chat_id, "age", text)
            send_message(chat_id, "🌍 What language should the story be in?")
        elif "language" not in session["data"]:
            update_session(chat_id, "language", text)
            send_message(chat_id, "📚 Any specific challenge or theme?")
        elif "challenge" not in session["data"]:
            update_session(chat_id, "challenge", text)
            send_message(chat_id, "✨ Any special character or element to include?")
        else:
            update_session(chat_id, "element", text)
            generate_story(chat_id)


def generate_story(chat_id):
    session = get_session(chat_id)
    info = session["data"]
    prompt = (
        f"Write a story for a {info['age']}-year-old {info['gender']} named {info['name']} "
        f"in {info['language']}."
    )
    if info.get("challenge"):
        prompt += f" The story should be about {info['challenge']}."
    if info.get("element"):
        prompt += f" Moreove include {info['element']} in the story."

     # ✨ Let user know that generation is in progress
    send_message(chat_id, f"🪄 Creating a magical story for {info['name']}, a {info['age']}-year-old {info['gender']}, in {info['language']}... Please wait a moment!")

    # Call Flowise to generate story
    response = requests.post(FLOWISE_ENDPOINT, json={"question": prompt})
    story = response.json().get("text", "")

    # Story validation and retry logic
    if not story or "error" in story.lower():
        retry_count = get_retry_count(chat_id)
        if retry_count == 0:
            mark_retry(chat_id)
            send_message(chat_id, "⚠️ Error generating story. Retrying...")
            generate_story(chat_id)
        else:
            refunded = issue_refund(chat_id)
            if refunded:
                send_message(chat_id, "❌ Failed to generate story. Your payment has been refunded.")
            else:
                send_message(chat_id, "❌ Story generation failed and refund was unsuccessful. Please contact support at support@example.com or message @your_support_username on Telegram.")
            reset_session(chat_id)
    else:
        send_message(chat_id, story)
        reset_session(chat_id)
        start_session(chat_id)
        payment_link = f"{BASE_URL}/pay/{chat_id}"
        send_message(chat_id, WELCOME_TEXT, buttons=[["🔮 Pay & Begin", payment_link]])
    


def issue_refund(user_id):
    try:
        sale_id = get_sale_id(user_id)
        sale = paypalrestsdk.Sale.find(sale_id)
        refund = sale.refund({
            "amount": {"total": "0.01", "currency": "USD"}
        })
        return refund.success()
    except Exception as e:
        print("Refund error:", e)
        return False

@app.route("/pay/<chat_id>")
def pay(chat_id):
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": f"{BASE_URL}/success/{chat_id}",
            "cancel_url": f"{BASE_URL}/cancel"
        },
        "transactions": [{
            "amount": {"total": "0.01", "currency": "USD"},
            "description": "Personalized children's story"
        }]
    })

    if payment.create():
        store_payment_id(int(chat_id), payment.id)
        for link in payment.links:
            if link.method == "REDIRECT":
                return f'<meta http-equiv="refresh" content="0; url={link.href}" />'
    return "<h1>Error creating PayPal payment</h1>"


@app.route("/success/<chat_id>")
def success(chat_id):
    user_id = int(chat_id)
    payment_id = get_payment_id(user_id)
    payment = paypalrestsdk.Payment.find(payment_id)

    try:
        # Get related resources
        related = payment.transactions[0].related_resources

        # Find the 'sale' object and save its ID
        for resource in related:
            if "sale" in resource:
                sale_id = resource["sale"]["id"]
                store_sale_id(user_id, sale_id)
                break
        else:
            print("⚠️ No 'sale' found in related_resources.")

    except Exception as e:
        print("❌ Error processing PayPal payment:", str(e))

    # Mark session as paid and start collecting info
    session = get_session(user_id)
    session["paid"] = True
    session["step"] = "collecting_info"
    session["data"] = {}
    save_session(user_id, session)

    # Send the first question: child's name
    send_message(user_id, "👶 What is the child's name?")

    return "<h1>✅ Payment successful! Please return to Telegram to continue.</h1>"


@app.route("/cancel")
def cancel():
    return "<h1>❌ Payment cancelled.</h1>"

@app.route("/ping")
def ping():
    return "✅ Flask is alive!"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
