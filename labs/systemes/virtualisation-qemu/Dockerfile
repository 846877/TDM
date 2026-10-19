# Hyperviseur QEMU (émulation TCG, sans KVM) avec l'image cloud CirrOS 0.6.2 (~20 Mo) téléchargée au build.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       qemu-system-x86 qemu-utils ipxe-qemu seabios openssh-client sshpass socat curl ca-certificates \
       iproute2 procps vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/*
ARG CIRROS=0.6.2
ARG CIRROS_SHA256=07e44a73e54c94d988028515403c1ed762055e01b83a767edf3c2b387f78ce00
RUN mkdir -p /srv/images /srv/vms /srv/export \
    && f=/srv/images/cirros-${CIRROS}-x86_64-disk.img \
    && ( curl -fsSL -o "$f" "https://download.cirros-cloud.net/${CIRROS}/cirros-${CIRROS}-x86_64-disk.img" \
         || curl -fsSL -o "$f" "https://github.com/cirros-dev/cirros/releases/download/${CIRROS}/cirros-${CIRROS}-x86_64-disk.img" ) \
    && echo "${CIRROS_SHA256}  $f" | sha256sum -c - \
    && chmod 444 "$f"
COPY console-vm.sh /usr/local/bin/console-vm
COPY moniteur-vm.sh /usr/local/bin/moniteur-vm
COPY ssh-vm.sh /usr/local/bin/ssh-vm
RUN chmod +x /usr/local/bin/console-vm /usr/local/bin/moniteur-vm /usr/local/bin/ssh-vm
WORKDIR /srv/vms
CMD ["sleep", "infinity"]
