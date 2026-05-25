FROM python:3.11-slim

WORKDIR /app

# Instala fontes e libs do sistema necessárias pro reportlab gerar PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu \
    fonts-liberation \
    libfreetype6 \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
