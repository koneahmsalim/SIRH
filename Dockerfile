FROM odoo:18

USER root
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages pyzk
USER odoo
