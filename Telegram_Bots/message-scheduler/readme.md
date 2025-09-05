TimeSender Bot

A Telegram bot for scheduled message delivery to a specified chat. Write a message now — receive it at exactly the right time!
Features

    Scheduled Delivery: Set a precise time for sending any message.

    Any Chat: Send messages to any group or channel where the bot has been added.

    Simple Interface: Interact with the bot through intuitive buttons.

    Flexibility: Supports text and images.

Installation and Setup (Self-Hosted)

You can deploy your own instance of this bot.
Prerequisites

    Python 3.8 or higher

    PostgreSQL server

    Telegram Bot Token (get from @BotFather)

    Your Telegram ID (find out by messaging @userinfobot)

1. Cloning the Repository
bash

git clone https://github.com/yourusername/your-bot-repo.git
cd your-bot-repo

2. Setting Up a Virtual Environment and Dependencies
bash

# Create a virtual environment
python -m venv venv

# Activation (Linux/macOS)
source venv/bin/activate

# Activation (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -e .

3. Configuring Environment Variables

Create a .env file based on the example:
bash

cp .env_example .env

Edit the .env file in any text editor, filling in your details:
env

# Required settings
BOT_TOKEN=your_bot_token_here_from_botfather
ADMIN_ID=your_telegram_id_here
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

Where to get the data:

    BOT_TOKEN: Get it from @BotFather when creating your bot.

    ADMIN_ID: Find out by sending /start to the bot @userinfobot.

    DATABASE_URL: Connection string for your PostgreSQL database.

4. Database Initialization

Run the script - the necessary tables will create themselves.
5. Starting the Bot
bash

python bot/main.py

The bot should start and send you a message about successful initialization.
6. Adding the Bot to a Chat

Add your bot to the desired groups or channels and appoint it as an administrator with the permission to send messages.
Technical Information

    Technology Stack: Python, Aiogram, APScheduler, AsyncPG, PostgreSQL

    License: MIT

Support

Encountering problems with setup?

    Create an Issue in the repository

    Subscribe to the channel: https://t.me/vrode_it

You are free to use and modify this code.