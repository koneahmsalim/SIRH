FROM odoo:18

USER root
RUN pip3 install --break-system-packages pyzk
USER odoo
