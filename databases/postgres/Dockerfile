FROM postgres:15-alpine

# Install additional extensions + patch all OS packages with available security fixes
RUN apk add --no-cache postgresql-contrib && \
    apk upgrade --no-cache && \
    rm -rf /var/cache/apk/*

# Copy initialization scripts (run alphabetically by postgres entrypoint)
COPY init.sql /docker-entrypoint-initdb.d/01-aminra-init.sql
COPY 02-keycloak-init.sh /docker-entrypoint-initdb.d/02-keycloak-init.sh

# Set locale
ENV LANG en_US.utf8
