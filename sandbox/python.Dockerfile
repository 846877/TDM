# Image du bac à sable Python (moulinette + terminal des exercices).
FROM python:3.12-slim
RUN useradd --create-home --uid 1000 eleve
USER eleve
WORKDIR /work
CMD ["python"]
