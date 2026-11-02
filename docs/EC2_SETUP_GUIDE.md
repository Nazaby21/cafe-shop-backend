# AWS EC2 Ubuntu Deployment & Operations Guide (`docs/EC2_SETUP_GUIDE.md`)

> **Executive Summary**: This operations runbook provides complete, copy-pasteable instructions for provisioning, configuring, operating, and tearing down the Coffee Shop Kong APIM platform on an AWS EC2 instance running Ubuntu LTS in the Sydney region (`ap-southeast-2`). Every command is explicitly tagged with `[Windows]` or `[EC2]` to eliminate ambiguity.

---

## 1. Architecture Overview on AWS EC2

```
AWS Region: ap-southeast-2 (Sydney)
Instance Type: t3.medium or t3.large (Ubuntu 24.04 or 22.04 LTS)
SSH Identity Key: python-lap.pem

                            SECURITY GROUP RULES
                     +----------------------------------+
                     | Port 22   : SSH (My IP only)     |
                     | Port 8000 : Kong APIM Proxy      |
                     | Port 3000 : Next.js Frontend     |
                     +----------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                             EC2 UBUNTU INSTANCE                               |
|                                                                               |
|   +-------------------+                     +-----------------------------+   |
|   |  Next.js Frontend | <-------[HTTP]----> |   Kong Gateway OSS 3.9      |   |
|   |   (Port 3000)     |                     |   (Port 8000 Proxy)         |   |
|   +-------------------+                     |   (Port 8001 Admin - Local) |   |
|                                             +--------------+--------------+   |
|                                                            |                  |
|                             INTERNAL DOCKER NETWORK        |                  |
|             +----------------------------------------------+                  |
|             |                       |                      |                  |
|             v                       v                      v                  |
|   +-------------------+   +--------------------+  +-------------------+       |
|   |   user-service    |   | operation-service  |  |  report-service   |       |
|   |   (Port 8001)     |   | (Port 8002 + Mock) |  |  (Port 8003)      |       |
|   +---------+---------+   +---------+----------+  +---------+---------+       |
|             |                       |                       |                 |
|             +-----------------------+-----------------------+                 |
|                                     |                                         |
|                                     v                                         |
|                      +------------------------------+                         |
|                      |   PostgreSQL 16 Container    |                         |
|                      |   (Port 5432 - Internal)     |                         |
|                      +------------------------------+                         |
+-------------------------------------------------------------------------------+
```

---

## 2. Prerequisites & AWS Configuration

### 2.1 AWS Security Group Rules
In the AWS EC2 Management Console (`ap-southeast-2`):
1. Navigate to **EC2 > Security Groups > Edit Inbound Rules**.
2. Configure strictly as follows:

| Type | Protocol | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | `My IP` (`<your-public-ip>/32`) | Secure SSH access |
| **Custom TCP**| TCP | `8000` | `0.0.0.0/0` | Public Kong Gateway APIM entry |
| **Custom TCP**| TCP | `3000` | `0.0.0.0/0` | Next.js Customer Frontend |

> [!CAUTION]
> **Strict Port Isolation**: Never open ports `8001` (Kong Admin API), `5432` (PostgreSQL), `8002`, or `8003` to `0.0.0.0/0`. The Kong Admin API must only be accessed through an encrypted SSH tunnel.

---

## 3. Windows SSH Key Configuration (`icacls`)

On Windows, SSH will reject connection attempts if the private key `python-lap.pem` has overly permissive Windows NTFS access permissions (`UNPROTECTED PRIVATE KEY FILE`). Because `chmod` is not available on Windows, use `icacls.exe`.

### Step 3.1: Reset and Restrict NTFS Permissions
Run the following commands in Windows PowerShell:

```powershell
# [Windows] Navigate to directory containing python-lap.pem
cd D:\Study\Year-4\Python\APIM-setup

# [Windows] Reset inheritance and permissions
icacls.exe .\python-lap.pem /reset

# [Windows] Grant read-only access to the current Windows user exclusively
icacls.exe .\python-lap.pem /grant:r "$($env:USERNAME):(R)"

# [Windows] Remove all inherited permissions from other users/groups
icacls.exe .\python-lap.pem /inheritance:r

# [Windows] Verify permissions (only your username should have Read access)
icacls.exe .\python-lap.pem
```

---

## 4. Connecting to EC2 via SSH

### Step 4.1: Connect to the Remote Ubuntu Instance

```powershell
# [Windows] Replace <EC2_PUBLIC_IP> with your instance's public IPv4 address
ssh -i D:\Study\Year-4\Python\APIM-setup\python-lap.pem ubuntu@<EC2_PUBLIC_IP>
```

---

## 5. EC2 Ubuntu Host Preparation & Docker Installation

Use the official Docker apt repository for Ubuntu (do **not** use `snap` or outdated Ubuntu packages).

### Step 5.1: System Update & Prerequisites

```bash
# [EC2] Update package index and install required utilities
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg git
```

### Step 5.2: Install Docker Engine & Docker Compose Plugin

```bash
# [EC2] Add Docker official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# [EC2] Add Docker repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# [EC2] Install Docker Engine, CLI, Containerd, and Docker Compose Plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# [EC2] Add ubuntu user to docker group to run without sudo
sudo usermod -aG docker ubuntu
sudo systemctl enable docker
sudo systemctl start docker

# [EC2] Apply group changes (or re-login)
newgrp docker

# [EC2] Verify Docker Engine & Compose versions
docker --version
docker compose version
```

---

## 6. Deploying the Application Stack

### Step 6.1: Clone Repository & Checkout Branch

```bash
# [EC2] Clone repository onto EC2 instance
cd ~
git clone <YOUR_GIT_REPO_URL> coffee-project
cd coffee-project

# [EC2] Checkout the Kong APIM feature branch
git checkout feature/kong-apim-postgres
```

### Step 6.2: Configure Environment Variables

```bash
# [EC2] Copy environment template
cp .env.example .env

# [EC2] Generate a strong 32-byte secret for JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# [EC2] Generate a strong password for DB_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(16))"
```

Edit `.env` using `nano .env` and configure:
```env
ENVIRONMENT=production
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<generated-database-password>

# In production, MUST be at least 32 characters
JWT_SECRET_KEY=<generated-32-char-jwt-secret>

# Public IP of your EC2 instance (accessible from browser)
NEXT_PUBLIC_API_BASE_URL=http://<EC2_PUBLIC_IP>:8000

# Mock Bakong Configuration
BAKONG_MODE=mock
BAKONG_ACCOUNT_ID=merchant@bakong
BAKONG_MERCHANT_NAME=Coffee Shop
BAKONG_TOKEN=mock_token
BAKONG_REGISTERED_EMAIL=merchant@coffeeshop.kh
```

### Step 6.3: Launch Stack via Docker Compose

```bash
# [EC2] Build images and start all containers in detached mode
docker compose up -d --build

# [EC2] Check container status and health
docker compose ps
```

Expected output:
```
NAME                        IMAGE               COMMAND                  SERVICE             STATUS
coffee_postgres             postgres:16-alpine  "docker-entrypoint.s…"   postgres            running (healthy)
coffee_user_service         ...                 "uvicorn app.main:ap…"   user-service        running
coffee_operation_service    ...                 "uvicorn app.main:ap…"   operation-service   running
coffee_report_service       ...                 "uvicorn app.main:ap…"   report-service      running
coffee_kong_gateway         kong:3.9-alpine     "/entrypoint.sh kong…"   kong                running
coffee_frontend             ...                 "docker-entrypoint.s…"   frontend            running
```

---

## 7. Running Database Migrations

FastAPI models create initial schema on startup; to execute official Alembic migration revisions:

```bash
# [EC2] Run Alembic migrations against the PostgreSQL container
docker compose exec operation-service alembic upgrade head
```

---

## 8. Remote Operations & Monitoring

### 8.1 View Live Container Logs

```bash
# [EC2] View live logs across all containers
docker compose logs -f

# [EC2] View specific service logs
docker compose logs -f kong
docker compose logs -f operation-service
docker compose logs -f user-service
```

### 8.2 Verify Gateway Health

```bash
# [EC2] Primary aggregated health
curl -s http://localhost:8000/health | jq .

# [EC2] Individual microservice health through Kong
curl -s http://localhost:8000/health/user | jq .
curl -s http://localhost:8000/health/operation | jq .
curl -s http://localhost:8000/health/report | jq .
```

### 8.3 Secure SSH Tunnel to Access Kong Admin API (Port 8001)

Because the Kong Admin API is restricted to loopback for security, use SSH local port forwarding from your Windows machine to access it:

```powershell
# [Windows] Establish SSH tunnel: forwards local port 8001 to EC2 port 8001
ssh -i D:\Study\Year-4\Python\APIM-setup\python-lap.pem -L 8001:localhost:8001 -N ubuntu@<EC2_PUBLIC_IP>
```

While the tunnel is running, open a new PowerShell prompt or browser:
```powershell
# [Windows] Query Kong Admin API via encrypted tunnel
curl.exe http://localhost:8001/status
curl.exe http://localhost:8001/services
curl.exe http://localhost:8001/routes
```

### 8.4 Access Next.js Frontend

1. Open your browser and navigate to:
   ```
   http://<EC2_PUBLIC_IP>:3000
   ```
2. The UI communicates with Kong Gateway at `http://<EC2_PUBLIC_IP>:8000`.

---

## 9. Automated & Manual Smoke Testing on EC2

### Step 9.1: Run Automated Bash Smoke Test Suite

```bash
# [EC2] Run the complete automated smoke test script
bash scripts/smoke_test.sh
```

### Step 9.2: Manual End-to-End Test (Order -> KHQR -> Mock Pay)

```bash
# 1. Register a test customer
REG_OUT=$(curl -s -X POST http://localhost:8000/api/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"pos_test","email":"pos_test@coffee.kh","password":"Password123!"}')
echo "$REG_OUT"

# 2. Login and extract JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pos_test@coffee.kh","password":"Password123!"}' | jq -r '.data.access_token')
echo "Token: $TOKEN"

# 3. Create an order
ORDER_ID=$(curl -s -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"items": [{"product_id": 1, "quantity": 1}]}' | jq -r '.data.id')
echo "Order ID: $ORDER_ID"

# 4. Generate dynamic Bakong KHQR
PAY_RES=$(curl -s -X POST "http://localhost:8000/api/orders/$ORDER_ID/payment" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"method": "khqr", "currency": "USD"}')
QR_MD5=$(echo "$PAY_RES" | jq -r '.data.qr_md5')
echo "Generated KHQR MD5: $QR_MD5"

# 5. Simulate instant customer payment settlement
MOCK_RES=$(curl -s -X POST "http://localhost:8000/api/payments/mock-pay/$QR_MD5")
echo "Mock Pay Result: $MOCK_RES"

# 6. Verify order payment status
curl -s -X GET "http://localhost:8000/api/orders/$ORDER_ID/payment" \
  -H "Authorization: Bearer $TOKEN" | jq .data.status
```

Expected output: `"paid"`.

---

## 10. Database Backup & Recovery Procedures

### 10.1 Backup All PostgreSQL Databases (`pg_dump`)

```bash
# [EC2] Create backup directory
mkdir -p ~/backups
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# [EC2] Dump user_service_db
docker compose exec -T postgres pg_dump -U postgres user_service_db > ~/backups/user_service_${BACKUP_DATE}.sql

# [EC2] Dump operation_service_db
docker compose exec -T postgres pg_dump -U postgres operation_service_db > ~/backups/operation_service_${BACKUP_DATE}.sql

# [EC2] Dump report_service_db
docker compose exec -T postgres pg_dump -U postgres report_service_db > ~/backups/report_service_${BACKUP_DATE}.sql

# [EC2] Verify backup files
ls -lh ~/backups
```

### 10.2 Restore from Backup

```bash
# [EC2] Restore operation_service_db from dump file
cat ~/backups/operation_service_<TIMESTAMP>.sql | docker compose exec -T postgres psql -U postgres -d operation_service_db
```

---

## 11. Deployment Rollback Procedure

If a deployed release introduces errors:

1. **Rollback Git Branch / Revert**:
   ```bash
   # [EC2] Check git log and checkout known-stable commit
   git log --oneline -n 5
   git checkout <STABLE_COMMIT_HASH>
   ```
2. **Rebuild and Restart Containers**:
   ```bash
   # [EC2] Rebuild with previous code
   docker compose up -d --build
   ```
3. **Rollback Migrations (if applicable)**:
   ```bash
   # [EC2] Downgrade 1 revision in operation-service
   docker compose exec operation-service alembic downgrade -1
   ```
4. **Reload Kong Declarative Config**:
   ```bash
   # [EC2] Restart Kong container to immediately reload declarative configuration
   docker compose restart kong
   ```

---

## 12. Teardown & AWS Cost Cleanup Checklist

When finished with evaluation or grading, complete these steps to avoid ongoing AWS charges:

- [ ] **1. Stop Docker Stack on EC2**:
  ```bash
  # [EC2] Stop and remove containers and networks
  docker compose down -v
  ```
- [ ] **2. Terminate EC2 Instance**:
  In AWS Management Console (`ap-southeast-2`):
  Navigate to **EC2 > Instances > Select Instance > Instance State > Terminate instance**.
- [ ] **3. Release Elastic IPs (EIP)**:
  Navigate to **EC2 > Network & Security > Elastic IPs**.
  If an Elastic IP was allocated, select **Actions > Release Elastic IP address**.
- [ ] **4. Delete EBS Volumes**:
  Navigate to **EC2 > Elastic Block Store > Volumes**.
  Verify volumes attached to the terminated instance are deleted (or delete manually if `DeleteOnTermination` was set to false).
- [ ] **5. Remove Security Group**:
  Navigate to **EC2 > Network & Security > Security Groups**.
  Delete the temporary test security group once all instances referencing it are terminated.
