# Bloxlink HTTP Interactions (WIP)

**WARNING: the code here is a WORK-IN-PROGRESS**

This repository contains the code for the upcoming HTTP interactions which will replace how Bloxlink handles commands in the future. This is accomplished by running a web server that handles all interaction commands instead of a websocket which is what the current version of Bloxlink uses.

## Instructions
Running this is relatively simple, but is different depending on whether you're running it on your own computer (local) or in a production environment.

## Dependencies
* Create a [Discord application](https://discord.com/developers/applications) and note down the Public Key.
* Make sure Python 3.10 is installed.
* Install the dependencies with `python3.10 -m pip install -r requirements.txt`. Depending on your OS, `python`, `python3`, or `py3` might be used instead.
* Rename `.env.example` to `.env`. Modify the config file with your Discord Public Key, Discord token, and MongoDB database information. https://www.mongodb.com/ has a free MongoDB instance that you can use for your local environment.
* Run Redis and put the information in `.env`.
* Run [The Bot API](https://github.com/bloxlink/bot-api). Make sure the Auth in the Bot API matches the Auth on the Discord bot. Update config.py as necessary. If you are having issues, make sure the port number is included in the BOT_API url.

## Local
* Run the SSH command: `ssh -R 80:localhost:8010 localhost.run`. This will tunnel your local traffic from the bot and spit out an https domain name that you will use.
* Run the web server: `python3.10 src/bot.py`
* Put the https domain name found from step 2 in your [Developer Dashboard](https://discord.com/developers/applications) Application under the "Interactions Endpoint Url" option.

## Production
Instructions are coming soon.
