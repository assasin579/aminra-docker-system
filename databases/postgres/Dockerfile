FROM postgres:15-alpine

# Install additional extensions
RUN apk add --no-cache postgresql-contrib

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Set locale
ENV LANG en_US.utf8