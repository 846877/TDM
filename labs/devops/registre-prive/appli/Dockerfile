# Petite image à publier dans le registre : docker build --build-arg VERSION=1.0 -t ... .
FROM alpine:3.20
ARG VERSION=dev
LABEL org.opencontainers.image.version=$VERSION
RUN echo "$VERSION" > /version
CMD ["sh", "-c", "echo Bonjour, version $(cat /version)"]
