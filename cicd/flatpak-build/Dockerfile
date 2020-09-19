FROM fedora:30

LABEL maintainer robozman "https://gitlab.com/robozman"

VOLUME [ "/sys/fs/cgroup", "/tmp", "/run" ]


RUN dnf -y update && \
    dnf install -y flatpak flatpak-builder ostree fuse wget curl elfutils dconf git bzip2 bzr python3 python3-pip && \
    dnf clean all

RUN flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

RUN flatpak install -y org.gnome.Platform//3.38 && \
    flatpak install -y org.gnome.Sdk//3.38

RUN pip3 install requirements-parser
