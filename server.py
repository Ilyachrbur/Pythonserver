#!/usr/bin/env python3
import asyncio
import websockets
import json
import os
import signal
from datetime import datetime

# Хранилище клиентов
clients = {}

async def handler(websocket):
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data['type'] == 'join':
                user_id = data['userId']
                username = data['username']
                
                clients[user_id] = {
                    'websocket': websocket,
                    'username': username,
                    'joined': datetime.now().isoformat()
                }
                
                print(f"✅ {username} подключился")
                await broadcast_users()
                await broadcast_system(f"👤 {username} присоединился")
                break
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Отключение
        for uid, client in list(clients.items()):
            if client['websocket'] == websocket:
                username = client['username']
                del clients[uid]
                print(f"❌ {username} отключился")
                await broadcast_users()
                await broadcast_system(f"👋 {username} покинул чат")
                break

async def broadcast_users():
    users_data = {uid: {'username': client['username']} for uid, client in clients.items()}
    await broadcast(json.dumps({'type': 'users', 'users': users_data}))

async def broadcast_system(text):
    await broadcast(json.dumps({'type': 'system', 'text': text}))

async def broadcast(message):
    if clients:
        await asyncio.gather(*[c['websocket'].send(message) for c in clients.values()])

async def health_check(path, request_headers):
    """Для проверки здоровья сервера"""
    if path == "/health":
        return websockets.http.HTTPStatus.OK, [], b"OK\n"

async def main():
    # Порт берется из переменной окружения (Render сам это дает)
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print(f"🚀 Сервер запускается на порту {port}")
    print("=" * 50)
    
    async with websockets.serve(
        handler, 
        "0.0.0.0", 
        port,
        process_request=health_check
    ):
        await asyncio.Future()  # работаем вечно

if __name__ == "__main__":
    asyncio.run(main())
