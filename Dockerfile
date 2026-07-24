FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# fonts-noto-cjk is CFF/OTF and cannot be embedded by reportlab; the transit
# planner (services/planner) needs a glyf-outline TrueType JP font, so add
# IPAex (Gothic + Mincho). IPAex ships a single weight, so JP bold renders at
# regular weight; for true bold drop Noto Sans/Serif JP static TTFs into
# services/planner/fonts/ (register_fonts prefers them automatically).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        fonts-ipaexfont \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY routes.py config.py acg.py ./
COPY services/ ./services/
COPY templates/ ./templates/
COPY static/ ./static/
COPY data/ ./data/
COPY ephe/ ./ephe/
COPY cards/ ./cards/
COPY kaii/ ./kaii/
COPY personal-edition/ ./personal-edition/

CMD ["sh", "-c", "python -m uvicorn routes:app --host 0.0.0.0 --port ${PORT:-8080}"]