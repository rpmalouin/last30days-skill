FROM python:3.12-slim

WORKDIR /app

COPY . .

# Production deps are empty (stdlib-only engine), dev deps are not needed.
# uv is not strictly needed at runtime but available for add-on workflows.
# yt-dlp makes the YouTube source detectable/usable (engine requires it).
RUN pip install --no-cache-dir uv yt-dlp

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]