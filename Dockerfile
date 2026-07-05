FROM python:3.12
WORKDIR /app
COPY .. .
RUN pip install --no-cache-dir -r requirements.txt
CMD sh -c "python main.py & python bot.py"