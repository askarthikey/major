import asyncio
import websockets

async def test():
    try:
        async with websockets.connect("ws://localhost:8000/ws/live") as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            print("Connected! Got:", msg)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

asyncio.run(test())
