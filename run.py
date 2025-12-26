import os
import asyncio
import threading
from flask import Flask

# Flask для health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return 'Bot is running', 200

@app.route('/health')
def health():
    return 'OK', 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def run_bot():
    # Импортируем здесь, чтобы избежать циклических импортов
    from bot import main
    await main()

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота в основном потоке
    asyncio.run(run_bot())
