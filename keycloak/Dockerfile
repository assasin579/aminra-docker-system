# Phase 4c-10: production-optimized Keycloak image.
#
# Two-stage build that pins the build-time settings into the image so the
# runtime can boot via `kc.sh start --optimized` (no re-augmentation on
# every start). Runtime URL / password / hostname env vars stay configurable
# in docker-compose.
#
# Reference: https://www.keycloak.org/server/containers
FROM quay.io/keycloak/keycloak:25.0 AS builder

# Build-time configuration — these are baked into the image. Changing any of
# them requires a rebuild.
ENV KC_DB=postgres
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=true
ENV KC_HTTP_ENABLED=true

# Run the augmentation step (compiles theme + provider + caches db driver).
RUN /opt/keycloak/bin/kc.sh build


FROM quay.io/keycloak/keycloak:25.0

COPY --from=builder /opt/keycloak/ /opt/keycloak/

# `start --optimized` skips re-augmentation at boot. Runtime env supplies
# KC_DB_URL / KC_DB_USERNAME / KC_DB_PASSWORD / KEYCLOAK_ADMIN_* / KC_HOSTNAME
# / KC_PROXY from docker-compose.
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized"]
