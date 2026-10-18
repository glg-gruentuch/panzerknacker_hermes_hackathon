# Static site image for the Panzerknacker website.
# Build context: repository root. Dockerfile path: deploy/website/Dockerfile
# The site content is built by: uv run nemotron-challenge run site --work-dir artifacts
FROM nginx:1.27-alpine
COPY deliverables/website/ /usr/share/nginx/html/
