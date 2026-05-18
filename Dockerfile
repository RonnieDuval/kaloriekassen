FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py run_sync.py sync_intervals.py sync_fitbit.py ./
COPY src ./src
COPY GOOGLE_HEALTH_API ./GOOGLE_HEALTH_API
COPY INTERVALS_ICU ./INTERVALS_ICU
COPY MYFITNESSPAL ./MYFITNESSPAL
COPY settings.py ./

CMD ["python", "run_sync.py", "all"]
