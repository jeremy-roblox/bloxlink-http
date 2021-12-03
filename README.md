# Bloxlink HTTP Interactions (WIP)

**WARNING: the code here is a WORK-IN-PROGRESS and is NOT done.**

This repository will contain the code for the upcoming HTTP interactions.

## Instructions
Running this is relatively simple, but is different depending on whether you're running it on your own computer (local) or in a production environment.

### Local
* Run the SSH command: `ssh -R 80:localhost:8000 localhost.run`. This will spit out an https domain name that you will use.
* Put the https domain name in your [Developer Dashboard](https://discord.com/developers/applications) under the "Interactions Endpoint Url" option.
* Run the bot: `python3.8 src/bot.py`

Disclaimer: https://localhost.run is a great service that can quickly tunnel your local traffic, but their free plan will periodically change your domain name, requiring you to change the domain name in your [Developer Dashboard](https://discord.com/developers/applications) each time. As such, it's recommended to subscribe to their premium plan to use a static domain, or you can find another tunneling service.

### Production
Instructions are coming soon.
