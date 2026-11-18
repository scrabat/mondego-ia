# Servidor Blender do Mondego IA (para todos os utilizadores da app online).
# Construir a partir da pasta da app:   docker build -f servidor_blender/Dockerfile -t mondego-blender .
# Correr:                               docker run -p 8080:8080 -e MONDEGO_TOKEN=uma-chave-longa-e-secreta mondego-blender
# Depois, na app: [blender] url = "https://o-teu-servidor" e token = "a mesma chave" em .streamlit/secrets.toml
FROM ubuntu:24.04

# Versão do Blender (LTS). O script funciona do 4.2 ao 5.x.
ARG BLENDER_SERIE=4.5
ARG BLENDER_VERSAO=4.5.3

RUN apt-get update && apt-get install -y --no-install-recommends python3 wget xz-utils ca-certificates \
        libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 libgl1 libegl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN wget -q "https://download.blender.org/release/Blender${BLENDER_SERIE}/blender-${BLENDER_VERSAO}-linux-x64.tar.xz" \
        -O /tmp/blender.tar.xz \
    && mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/blender.tar.xz

ENV MONDEGO_BLENDER=/opt/blender/blender PORT=8080 PYTHONUNBUFFERED=1
WORKDIR /app
COPY estudio3d.py motor_blender.py ./
COPY blender ./blender
COPY servidor_blender/servidor.py ./servidor_blender/servidor.py
RUN useradd -m mondego && chown -R mondego /app
USER mondego
EXPOSE 8080
CMD ["python3", "servidor_blender/servidor.py"]
