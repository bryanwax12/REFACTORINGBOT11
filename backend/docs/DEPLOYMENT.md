# Deployment Guide
# Руководство по развертыванию Telegram Shipping Bot

## Содержание

1. [Требования](#требования)
2. [Локальная разработка](#локальная-разработка)
3. [Production Deployment](#production-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Мониторинг](#мониторинг)
6. [Troubleshooting](#troubleshooting)

---

## Требования

### Минимальные требования:
- **CPU:** 2 cores
- **RAM:** 4GB
- **Disk:** 20GB SSD
- **OS:** Ubuntu 20.04+ / Debian 11+

### Программное обеспечение:
- Python 3.11+
- Node.js 18+
- MongoDB 6.0+
- Nginx (для production)
- Supervisor (для process management)

---

## Локальная разработка

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-org/telegram-shipping-bot.git
cd telegram-shipping-bot
```

### 2. Backend Setup

```bash
cd backend

# Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Скопировать example env
cp .env.example .env

# Отредактировать .env с вашими credentials
nano .env
```

**Обязательные переменные в .env:**
```env
MONGO_URL=mongodb://localhost:27017
MONGODB_DB_NAME=telegram_shipping_bot
TELEGRAM_BOT_TOKEN=your_token_here
SHIPSTATION_API_KEY=your_key_here
OXAPAY_API_KEY=your_key_here
```

### 3. Frontend Setup

```bash
cd ../frontend

# Установить зависимости
yarn install

# Создать .env
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
```

### 4. Запуск MongoDB

```bash
# Docker
docker run -d -p 27017:27017 --name mongodb mongo:6.0

# Или установка локально
sudo apt install mongodb-org
sudo systemctl start mongod
```

### 5. Запуск сервисов

```bash
# Backend (в отдельном терминале)
cd backend
source .venv/bin/activate
python server.py

# Frontend (в отдельном терминале)
cd frontend
yarn start
```

### 6. Проверка

- Backend: http://localhost:8001/docs
- Frontend: http://localhost:3000
- Health check: http://localhost:8001/api/health

---

## Production Deployment

### Метод 1: Supervisor + Nginx

#### 1. Установка зависимостей

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv nginx supervisor mongodb-org
```

#### 2. Подготовка приложения

```bash
# Клонировать в production директорию
sudo mkdir -p /opt/telegram-bot
sudo chown $USER:$USER /opt/telegram-bot
cd /opt/telegram-bot
git clone https://github.com/your-org/telegram-shipping-bot.git .

# Setup backend
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend
yarn install
yarn build
```

#### 3. Конфигурация Supervisor

Создать `/etc/supervisor/conf.d/telegram-bot-backend.conf`:

```ini
[program:telegram-bot-backend]
command=/opt/telegram-bot/backend/.venv/bin/python server.py
directory=/opt/telegram-bot/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/telegram-bot/backend.log
environment=PATH="/opt/telegram-bot/backend/.venv/bin"
```

Создать `/etc/supervisor/conf.d/telegram-bot-frontend.conf`:

```ini
[program:telegram-bot-frontend]
command=/usr/bin/serve -s build -l 3000
directory=/opt/telegram-bot/frontend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/telegram-bot/frontend.log
```

```bash
# Применить конфигурацию
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start telegram-bot-backend
sudo supervisorctl start telegram-bot-frontend
```

#### 4. Конфигурация Nginx

Создать `/etc/nginx/sites-available/telegram-bot`:

```nginx
# Backend API
upstream backend {
    server 127.0.0.1:8001;
}

# Frontend
upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Увеличить timeout для webhook
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }

    # Static files cache
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Активировать конфигурацию
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. SSL с Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Kubernetes Deployment

### 1. Создать namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: telegram-bot
```

### 2. MongoDB StatefulSet

```yaml
# mongodb-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: telegram-bot
spec:
  serviceName: mongodb
  replicas: 1
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
      - name: mongodb
        image: mongo:6.0
        ports:
        - containerPort: 27017
        volumeMounts:
        - name: mongo-data
          mountPath: /data/db
        env:
        - name: MONGO_INITDB_ROOT_USERNAME
          valueFrom:
            secretKeyRef:
              name: mongodb-secret
              key: username
        - name: MONGO_INITDB_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mongodb-secret
              key: password
  volumeClaimTemplates:
  - metadata:
      name: mongo-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 20Gi
```

### 3. Backend Deployment

```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: telegram-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: your-registry/telegram-bot-backend:latest
        ports:
        - containerPort: 8001
        env:
        - name: MONGO_URL
          value: "mongodb://mongodb:27017"
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: telegram-bot-secret
              key: bot-token
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: telegram-bot
spec:
  selector:
    app: backend
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP
```

### 4. Frontend Deployment

```yaml
# frontend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: telegram-bot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: your-registry/telegram-bot-frontend:latest
        ports:
        - containerPort: 3000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: telegram-bot
spec:
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 3000
  type: LoadBalancer
```

### 5. Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: telegram-bot-ingress
  namespace: telegram-bot
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - your-domain.com
    secretName: telegram-bot-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8001
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

### Применить конфигурацию

```bash
kubectl apply -f namespace.yaml
kubectl apply -f mongodb-statefulset.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f ingress.yaml
```

---

## Мониторинг

### Prometheus + Grafana

#### 1. Установка Prometheus Operator

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

#### 2. ServiceMonitor для приложения

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: telegram-bot-backend
  namespace: telegram-bot
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
  - port: http
    path: /api/metrics
```

#### 3. Alerting Rules

```yaml
# alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: telegram-bot-alerts
  namespace: telegram-bot
spec:
  groups:
  - name: telegram-bot
    interval: 30s
    rules:
    - alert: HighErrorRate
      expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected"
    
    - alert: PodDown
      expr: up{job="telegram-bot-backend"} == 0
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "Backend pod is down"
```

### Логирование (ELK Stack)

```bash
# Установка ELK
helm repo add elastic https://helm.elastic.co
helm install elasticsearch elastic/elasticsearch --namespace logging --create-namespace
helm install kibana elastic/kibana --namespace logging
helm install filebeat elastic/filebeat --namespace logging
```

---

## Troubleshooting

### Backend не запускается

```bash
# Проверить логи
sudo supervisorctl tail -f telegram-bot-backend stderr

# Проверить MongoDB подключение
mongosh --eval "db.adminCommand({ping: 1})"

# Проверить environment variables
sudo cat /etc/supervisor/conf.d/telegram-bot-backend.conf
```

### Frontend не загружается

```bash
# Проверить логи
sudo supervisorctl tail -f telegram-bot-frontend stderr

# Проверить Nginx конфигурацию
sudo nginx -t

# Проверить upstream
curl -I http://localhost:3000
```

### Telegram Bot не отвечает

```bash
# Проверить webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Установить webhook
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-domain.com/api/webhooks/telegram"}'

# Или использовать polling
# Установить TELEGRAM_BOT_MODE=polling в .env
```

### Высокая нагрузка на MongoDB

```bash
# Проверить индексы
mongosh telegram_shipping_bot --eval "db.orders.getIndexes()"

# Создать недостающие индексы
mongosh telegram_shipping_bot --eval "db.orders.createIndex({telegram_id: 1})"

# Проверить slow queries
mongosh --eval "db.setProfilingLevel(1, {slowms: 100})"
mongosh --eval "db.system.profile.find().limit(5).pretty()"
```

---

## Резервное копирование

### Автоматический backup MongoDB

```bash
# Создать скрипт backup.sh
#!/bin/bash
BACKUP_DIR="/var/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)

mongodump --uri="mongodb://localhost:27017" \
  --db=telegram_shipping_bot \
  --out="$BACKUP_DIR/$DATE"

# Сжать
tar -czf "$BACKUP_DIR/$DATE.tar.gz" "$BACKUP_DIR/$DATE"
rm -rf "$BACKUP_DIR/$DATE"

# Удалить старые бэкапы (старше 7 дней)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

# Загрузить в S3 (опционально)
aws s3 cp "$BACKUP_DIR/$DATE.tar.gz" s3://your-bucket/backups/
```

```bash
# Добавить в crontab
0 2 * * * /opt/telegram-bot/backup.sh
```

---

## Обновление приложения

### Zero-downtime deployment

```bash
# 1. Создать бэкап
./backup.sh

# 2. Обновить код
cd /opt/telegram-bot
git pull origin main

# 3. Обновить зависимости
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# 4. Применить миграции (если есть)
python migrate.py

# 5. Rolling restart
sudo supervisorctl restart telegram-bot-backend
sleep 5
sudo supervisorctl status telegram-bot-backend

# 6. Обновить frontend
cd ../frontend
yarn install
yarn build
sudo supervisorctl restart telegram-bot-frontend
```

---

## Контакты

- **DevOps Team:** devops@example.com
- **Support:** support@example.com
- **Documentation:** https://docs.example.com
