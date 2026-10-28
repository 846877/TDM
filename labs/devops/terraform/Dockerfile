FROM hashicorp/terraform:1.9 AS terraform
FROM docker:28-dind
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
