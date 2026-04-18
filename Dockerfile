FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY sync_mfp.py sync_intervals.py sync_fitbit.py ./

CMD ["python", "sync_mfp.py"]
