FROM odoo:18

USER root
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping nmap && rm -rf /var/lib/apt/lists/*
# pandas : utilise par hrms_dashboard (join_resign_trends, get_attrition_rate).
# future : dependance transitive constatee dans le conteneur reel.
# Installes manuellement dans le conteneur a un moment donne, jamais
# captures ici avant - invisible tant que ce conteneur n'etait jamais
# reconstruit depuis zero (ex. un vrai build pour un nouveau deploiement).
RUN pip3 install --break-system-packages pyzk pandas future
COPY ./addons /mnt/extra-addons
# Modele de configuration de production, embarque dans l'image : un
# deploiement depuis un depot git (Coolify) ne dispose que des fichiers
# versionnes. Le mot de passe maitre y est un marqueur, remplace au
# demarrage par docker-cmd.sh depuis ODOO_ADMIN_PASSWD.
COPY deploy/odoo.prod.conf /etc/odoo/odoo.prod.conf
# script Windows -> normalise les fins de ligne, sinon le shebang echoue
# silencieusement au build sur un serveur Linux (Render).
COPY docker-cmd.sh /docker-cmd.sh
RUN sed -i 's/\r$//' /docker-cmd.sh && chmod +x /docker-cmd.sh

USER odoo
CMD ["/docker-cmd.sh"]
