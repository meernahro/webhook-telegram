from fastapi import FastAPI
from pydantic import BaseModel
import os
import asyncio
import aiohttp
from binance.client import Client
from binance.enums import *
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY')
BINANCE_API_SECRET = os.environ.get('BINANCE_API_SECRET')

if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_API_SECRET]):
    logger.error("One or more environment variables are missing.")
    # You might want to exit or raise an exception here

TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

class TradingViewAlert(BaseModel):
    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: float

@app.post('/webhook')
async def webhook(alert: TradingViewAlert):
    logger.info(f"Received alert: {alert}")
    message = f"Received alert: {alert}"
    await send_message_to_telegram(message)

    # Execute trade on Binance
    order_response = await execute_trade(alert)

    # Double-check the trade execution
    if order_response.get('status') == 'FILLED':
        confirm_message = f"Trade executed: {order_response}"
    else:
        confirm_message = f"Trade failed: {order_response}"

    await send_message_to_telegram(confirm_message)
    return {'status': 'success', 'message': 'Processed alert'}

async def execute_trade(alert: TradingViewAlert):
    try:
        if alert.action.lower() == 'buy':
            order = client.create_order(
                symbol=alert.symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=alert.quantity
            )
        elif alert.action.lower() == 'sell':
            order = client.create_order(
                symbol=alert.symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=alert.quantity
            )
        else:
            return {'status': 'error', 'message': 'Invalid action'}

        # Double-check the order status
        order_status = client.get_order(
            symbol=alert.symbol,
            orderId=order['orderId']
        )
        return order_status
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        return {'status': 'error', 'message': str(e)}

async def send_message_to_telegram(message):
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(TELEGRAM_API_URL, data=payload) as response:
            resp_text = await response.text()
            if response.status != 200:
                logger.error(f"Telegram API error: {resp_text}")
            return resp_text
