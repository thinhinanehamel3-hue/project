FROM python:3.11-slim

WORKDIR /app

# تثبيت الأدوات الضرورية لبناء dlib وبعض المكتبات
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libboost-all-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# تحديث pip قبل التثبيت (مهم مع مكتبات حديثة)
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تعطيل notify / telemetry
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT

