FROM python:latest
ENV API_KEY=sk-tdm-4f9a7c21e8
RUN apt-get update && apt-get install -y curl
ADD . /app
WORKDIR /app
EXPOSE 8080
CMD python app.py
