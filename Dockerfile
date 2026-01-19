FROM python:3.11-slim

WORKDIR /app

# تثبيت build tools الضرورية
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تعطيل notify / telemetry
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=$PORT"]
