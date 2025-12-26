import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.getenv('API_ID'))
    API_HASH = os.getenv('API_HASH')
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
    ADMIN_ID = int(os.getenv('ADMIN_ID'))
    DELAY_SECONDS = int(os.getenv('DELAY_SECONDS', 5))
    
    # Storage files
    LOG_FILE = 'forwarded_messages.log'
    GROUPS_FILE = 'groups.json'

    SCHEDULE_FILE = 'schedule.json'
