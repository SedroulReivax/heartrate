import asyncio
import websockets
import json
from capture import CaptureSession

async def handler(websocket):
    print("Client connected")
    queue = asyncio.Queue(maxsize=2)
    session = CaptureSession()
    capture_task = asyncio.create_task(session.run_loop(queue))
    
    try:
        while True:
            state = await queue.get()
            await websocket.send(json.dumps(state))
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        session.stop()
        if not capture_task.done():
            capture_task.cancel()

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8000):
        print("WebSocket server started on ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
