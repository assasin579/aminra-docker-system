FROM postgres:15-alpine

# Install additional extensions + patch all OS packages with available security fixes
RUN apk add --no-cache postgresql-contrib && \
    apk upgrade --no-cache && \
    rm -rf /var/cache/apk/*

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Set locale
ENV LANG en_US.utf8
