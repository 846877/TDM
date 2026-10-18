FROM willhallonline/ansible:latest
# Les clients écoutent en SSH sur le port 2222.
RUN mkdir -p /home/ansible/.ssh && printf 'Host client*\n  Port 2222\n  StrictHostKeyChecking accept-new\n' > /home/ansible/.ssh/config && chmod 700 /home/ansible/.ssh && chmod 600 /home/ansible/.ssh/config
# Playbook cassé de l'exercice de dépannage.
COPY --chown=ansible:ansible casse.yml /home/ansible/casse.yml
WORKDIR /home/ansible
CMD ["sleep", "infinity"]
