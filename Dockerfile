FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a container
ENV UV_LINK_MODE=copy

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the project's dependencies from uv.lock and pyproject.toml
# We use --frozen to ensure we use the lockfile exactly
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Place executable symlinks in the path
ENV PATH="/app/.venv/bin:$PATH"

# Install Playwright browsers (now that playwright is in the venv)
RUN playwright install --with-deps chrome

# Copy project files
COPY main.py run_sync.py settings.py sync_myfitnesspal.py ./
COPY src ./src
COPY GOOGLE_HEALTH_API ./GOOGLE_HEALTH_API
COPY INTERVALS_ICU ./INTERVALS_ICU
COPY MYFITNESSPAL ./MYFITNESSPAL

# The project itself (if needed)
RUN uv sync --frozen --no-dev

CMD ["python", "run_sync.py", "all"]
