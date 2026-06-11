FROM python:3.11-slim

WORKDIR /app

# 安裝 camoufox (Firefox stealth) 所需的系統套件
RUN apt-get update && apt-get install -y \
    wget curl ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libx11-6 libxcb1 \
    libxext6 libxtst6 libpango-1.0-0 libpangocairo-1.0-0 \
    fonts-noto-cjk fonts-noto-cjk-extra \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 下載 camoufox 瀏覽器（Scrapling 的 stealth 引擎）
RUN scrapling install

COPY . .

EXPOSE 8090

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
