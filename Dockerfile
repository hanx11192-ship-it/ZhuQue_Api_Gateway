# syntax=docker/dockerfile:1
# 多阶段构建：第一阶段用 Node 构建前端，第二阶段用 Python 运行后端。
# 仓库无需包含 web/dist（构建产物），clone 后 `docker build` 即可出完整镜像。

# ---------------- 阶段 1：构建前端 ----------------
FROM node:20-slim AS frontend
WORKDIR /frontend
# 先装依赖（利用层缓存），再拷源码
COPY frontend/package.json frontend/package-lock.json* ./
RUN corepack enable \
    && corepack prepare pnpm@latest --activate \
    && pnpm install --frozen-lockfile || pnpm install
COPY frontend/ ./
RUN pnpm build

# ---------------- 阶段 2：运行后端 ----------------
ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    DATA_DIR=/srv/gateway/data

WORKDIR /srv/gateway

# 换成清华镜像加速 apt（bookworm 使用 deb822 格式）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm openssh-server ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip3 install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY backend/app ./app
COPY backend/examples ./examples
COPY backend/docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# 第一阶段构建出的前端静态资源
COPY --from=frontend /frontend/dist ./web/dist

RUN mkdir -p "$DATA_DIR"/scripts \
    && chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000 22

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
