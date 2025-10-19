import asyncio
import os
from dotenv import load_dotenv
import aiohttp
import logging

# --- Configuration ---
WEBSOCKET_URI = "100.96.0.7:13724/client-secret-ws"

async def run_test():
    load_dotenv()

    token = os.environ.get("TEST_JWT")
    if not token:
        raise ValueError("TEST_JWT is missing")

    print(f"\nConnecting to {WEBSOCKET_URI}")
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Cookie": f"JWT={token}"}
            async with session.get( "http://" + WEBSOCKET_URI, headers=headers) as resp:
                print(resp.status, resp.reason)
            async with session.ws_connect( "ws://" + WEBSOCKET_URI, headers=headers) as ws:
                print("Listening...")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        logging.info(f"Received message: {msg.data}")
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        logging.info(f"Received binary message: {msg.data.decode()}")
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logging.warning("Connection closed by server.")
                        break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logging.error(f"Connection closed with error: {ws.exception()}")
                        break
            logging.info("Connection closed.")
    except aiohttp.ClientError as e:
        logging.error(f"Failed to connect:", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    try:
        asyncio.run(run_test())
    except Exception as e:
        logging.error(f"An error occurred:", exc_info=True)