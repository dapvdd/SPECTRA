#!/bin/sh
set -e

# If the database does not exist in the volume (e.g. fresh volume mounted over /app/data),
# initialize it from the template so an empty volume does not mask the database.
if [ ! -f /app/data/spectra.db ] && [ -f /app/data-template/spectra.db ]; then
    echo "Initializing database in persistent volume from template..."
    cp /app/data-template/spectra.db /app/data/spectra.db
fi

exec "$@"
