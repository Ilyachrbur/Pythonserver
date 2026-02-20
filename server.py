#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import websockets
import json
import os
import sys
import signal
from datetime import datetime

# Хранилище клиентов
clients = {}
# Для логирования
print = lambda *args: sys.stdout.write(' '.join(map(str, args)) + '\n')

async def handler(websocket):
    """Обработчик подключения"""
    client_id = None
    username = None
    
    try:
        # Ждем первое сообщение (информация о пользователе)
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data['type'] == 'join':
                    client_id = data.get('userId')
                    username = data.get('username', 'Unknown')
                    
                    # Сохраняем клиента
                    clients[client_id] = {
                        'websocket': websocket,
                        'username': username,
                        'joined': datetime.now().isoformat()
                    }
                    
                    print(f"✅ {username} подключился. Всего: {len(clients)}")
                    
                    # Отправляем обновленный список всем
                    await broadcast_users()
                    await broadcast_system(f"👤 {username} присоединился к чату")
                    
                    # Выходим из цикла ожидания первого сообщения
                    break
                    
            except json.JSONDecodeError:
                print(f"❌ Получен некорректный JSON: {message}")
                continue
        
        # Теперь обрабатываем обычные сообщения
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data['type'] == 'message':
                    # Рассылаем сообщение всем
                    await broadcast(json.dumps({
                        'type': 'message',
                        'text': data['text'],
                        'username': data['username'],
                        'userId': data['userId'],
                        'time': datetime.now().isoformat()
                    }))
                    
            except json.JSONDecodeError:
                print(f"❌ Некорректный JSON: {message}")
            except Exception as e:
                print(f"❌ Ошибка обработки сообщения: {e}")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"📴 Соединение закрыто: {e}")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")
    finally:
        # Удаляем клиента при отключении
        if client_id and client_id in clients:
            user = clients[client_id]['username']
            del clients[client_id]
            print(f"❌ {user} отключился. Осталось: {len(clients)}")
            await broadcast_users()
            await broadcast_system(f"👋 {user} покинул чат")

async def broadcast_users():
    """Отправляем всем список пользователей"""
    try:
        users_data = {
            uid: {'username': data['username']}
            for uid, data in clients.items()
        }
        
        message = json.dumps({
            'type': 'users',
            'users': users_data
        })
        
        await broadcast(message)
    except Exception as e:
        print(f"❌ Ошибка broadcast_users: {e}")

async def broadcast_system(text):
    """Отправляем системное сообщение"""
    try:
        await broadcast(json.dumps({
            'type': 'system',
            'text': text
        }))
    except Exception as e:
        print(f"❌ Ошибка broadcast_system: {e}")

async def broadcast(message):
    """Отправляем сообщение всем клиентам"""
    if not clients:
        return
        
    # Создаем список задач для отправки
    tasks = []
    disconnected = []
    
    for client_id, client in clients.items():
        try:
            tasks.append(client['websocket'].send(message))
        except Exception:
            disconnected.append(client_id)
    
    # Удаляем отключившихся клиентов
    for client_id in disconnected:
        del clients[client_id]
    
    # Отправляем сообщения
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def health_check(request):
    """HTTP-эндпоинт для проверки здоровья"""
    return websockets.http.Response(
        status=200,
        headers={"Content-Type": "text/plain"},
        body=b"OK\n"
    )

async def main():
    """Основная функция"""
    # Порт из окружения Render или 5000 по умолчанию
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print(f"🚀 Чат-сервер запускается...")
    print(f"📡 Порт: {port}")
    print(f"⏰ Время: {datetime.now().isoformat()}")
    print("=" * 50)
    
    # Настройка обработки сигналов для graceful shutdown
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set_result, None)
    
    # Запускаем сервер
    async with websockets.serve(
        handler,
        "0.0.0.0",
        port,
        ping_interval=20,
        ping_timeout=60,
        close_timeout=30,
        process_request=health_check  # Добавляем health check
    ):
        print(f"✅ Сервер успешно запущен на порту {port}")
        print(f"💡 Health check: http://localhost:{port}/health")
        print("=" * 50)
        
        # Ждем сигнала остановки
        await stop
    
    print("🛑 Сервер остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
