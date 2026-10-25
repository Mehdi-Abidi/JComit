# JComit sandbox image: NVIDIA's OpenShell base with the JComit code baked in.
# The policy makes /app read-only; only /sandbox/data is writable.
FROM ghcr.io/nvidia/openshell-community/sandboxes/base:latest

COPY src /app/src
