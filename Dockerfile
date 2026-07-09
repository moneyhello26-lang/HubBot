FROM python:3.12
WORKDIR /app

ENV TZ=Asia/Almaty
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY .. .
RUN pip install --no-cache-dir -r requirements.txt
CMD sh -c "python main.py & python bot.py"