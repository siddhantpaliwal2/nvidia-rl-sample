# syntax=docker/dockerfile:1
# Local base is built from the pinned state-machine checkout; Daytona uses an equivalent sealed snapshot.
FROM champ-state-machine-champ2197-base:v1

USER root
WORKDIR /app
RUN archive="$(npm pack --silent ramda@0.30.1)" \
 && mkdir -p node_modules/ramda \
 && tar -xzf "$archive" -C node_modules/ramda --strip-components=1 \
 && rm -f "$archive" \
 && archive="$(npm pack --silent exponential-backoff@3.1.2)" \
 && mkdir -p node_modules/exponential-backoff \
 && tar -xzf "$archive" -C node_modules/exponential-backoff --strip-components=1 \
 && rm -f "$archive"
RUN mkdir -p /logs/verifier
CMD ["/bin/bash"]
