FROM odoo:18

USER root
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages pyzk
USER odoo

# db_port fixe a 5432 (Postgres) volontairement : sur Render, $PORT designe
# le port HTTP public du service (routage), qui entre en collision avec
# l'usage interne de $PORT par l'entrypoint officiel Odoo (fallback pour
# db_port). En fixant db_port et en donnant un repli local a chaque
# variable (${VAR:-defaut}), la meme ligne fonctionne aussi bien en local
# via docker-compose (HOST/USER/PASSWORD deja fixes la-bas, PORT absent ->
# 8069 par defaut) que sur Render (PORT/HOST/USER/PASSWORD injectes par la
# plateforme).
CMD odoo --db_host="${HOST:-postgres}" --db_port=5432 --db_user="${USER:-odoo}" --db_password="${PASSWORD:-odoo}" --http-port="${PORT:-8069}"