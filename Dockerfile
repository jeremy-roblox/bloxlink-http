FROM python:3.10.4

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /src

CMD [ "python", "./bot.py" ]