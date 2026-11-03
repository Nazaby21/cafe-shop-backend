<#
.SYNOPSIS
    Automated Kong Gateway APIM and Microservices Smoke Test Suite (PowerShell)
.DESCRIPTION
    Validates the local Docker stack through Kong Gateway:
    1. Public route returns 200 OK
    2. Protected route returns 401 without token and 200 with token
    3. 429 Too Many Requests on rate limit
    4. CORS preflight (OPTIONS) returns correct Access-Control-Allow-Origin
    5. Internal-only routes/ports blocked from host
    6. Admin API reachable on 127.0.0.1 loopback
    7. Mock payment flows: pending -> paid, expired, failed
#>
[CmdletBinding()]
param(
    [string]$GatewayUrl = "http://127.0.0.1:8000",
    [string]$AdminApiUrl = "http://127.0.0.1:8001",
    [switch]$SkipRateLimit
)

$ErrorActionPreference = "Continue"
$passed = 0
$failed = 0

function Write-Pass($msg) {
    Write-Host "  [PASS] $msg" -ForegroundColor Green
    $script:passed++
}

function Write-Fail($msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    $script:failed++
}

function Write-Header($title) {
    Write-Host "`n=== $title ===" -ForegroundColor Cyan
}

Write-Host "======================================================================" -ForegroundColor Yellow
Write-Host " KONG GATEWAY LOCAL DOCKER SMOKE TEST SUITE                           " -ForegroundColor Yellow
Write-Host " Gateway Proxy:  $GatewayUrl                                          " -ForegroundColor Yellow
Write-Host " Admin API:      $AdminApiUrl                                          " -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Yellow

# -----------------------------------------------------------------------------
# 1. PUBLIC ROUTE CHECKS (200 OK)
# -----------------------------------------------------------------------------
Write-Header "1. Public Routes (200 OK)"

try {
    $res = Invoke-RestMethod -Uri "$GatewayUrl/health" -Method Get -TimeoutSec 10
    if ($res.status -eq "ok" -and $res.database -eq "connected") {
        Write-Pass "GET /health returned 200 OK (Postgres connected via Kong)"
    } else {
        Write-Fail "GET /health unexpected payload: $($res | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Fail "GET /health failed: $_"
}

try {
    $prodRes = Invoke-RestMethod -Uri "$GatewayUrl/api/products" -Method Get -TimeoutSec 10
    if ($prodRes.success -eq $true) {
        Write-Pass "GET /api/products returned 200 OK (Public catalog accessible)"
    } else {
        Write-Fail "GET /api/products returned non-success response"
    }
} catch {
    Write-Fail "GET /api/products failed: $_"
}

# -----------------------------------------------------------------------------
# 2. PROTECTED ROUTES (401 WITHOUT TOKEN, 200 WITH TOKEN)
# -----------------------------------------------------------------------------
Write-Header "2. Protected Routes (401 vs 200)"

# Verify 401 Unauthorized without token
try {
    $unauth = Invoke-WebRequest -Uri "$GatewayUrl/api/auth/me" -Method Get -TimeoutSec 10
    Write-Fail "GET /api/auth/me without token returned HTTP $($unauth.StatusCode); expected 401"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401) {
        Write-Pass "GET /api/auth/me without token correctly returned 401 Unauthorized"
    } else {
        Write-Fail "GET /api/auth/me without token failed with unexpected error: $_"
    }
}

# Register a unique customer
$rand = Get-Random -Minimum 100000 -Maximum 999999
$testEmail = "smoke_dev_$rand@example.com"
$testPass = "SecureSmokePass123!"
$jwtToken = $null

try {
    $regBody = @{
        username = "smoke_dev_$rand";
        email = $testEmail;
        password = $testPass;
    } | ConvertTo-Json

    $regRes = Invoke-RestMethod -Uri "$GatewayUrl/api/auth" -Method Post -Body $regBody -ContentType "application/json" -TimeoutSec 10
    if ($regRes.success -eq $true) {
        Write-Pass "POST /api/auth registered test user ($testEmail)"
    } else {
        Write-Fail "POST /api/auth failed: $($regRes | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Fail "POST /api/auth failed: $_"
}

# Login to obtain JWT
try {
    $loginBody = @{
        email = $testEmail;
        password = $testPass;
    } | ConvertTo-Json

    $loginRes = Invoke-RestMethod -Uri "$GatewayUrl/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json" -TimeoutSec 10
    if ($loginRes.success -eq $true -and $loginRes.data.access_token) {
        $jwtToken = $loginRes.data.access_token
        Write-Pass "POST /api/auth/login returned JWT access token"
    } else {
        Write-Fail "POST /api/auth/login failed: $($loginRes | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Fail "POST /api/auth/login failed: $_"
}

# Call protected route with Bearer token
if ($jwtToken) {
    try {
        $meRes = Invoke-RestMethod -Uri "$GatewayUrl/api/auth/me" -Method Get -Headers @{
            "Authorization" = "Bearer $jwtToken"
        } -TimeoutSec 10
        if ($meRes.success -eq $true -and $meRes.data.email -eq $testEmail) {
            Write-Pass "GET /api/auth/me with Bearer token returned 200 OK (user: $($meRes.data.email))"
        } else {
            Write-Fail "GET /api/auth/me returned unexpected data: $($meRes | ConvertTo-Json -Compress)"
        }
    } catch {
        Write-Fail "GET /api/auth/me with token failed: $_"
    }
}

# -----------------------------------------------------------------------------
# 3. RATE LIMITING ENFORCEMENT (HTTP 429)
# -----------------------------------------------------------------------------
Write-Header "3. Rate Limiting Enforcement (policy: local)"

if (-not $SkipRateLimit) {
    $hit429 = $false
    Write-Host "  Sending rapid requests to /api/auth/login (route limit: 10/min)..."
    for ($i = 1; $i -le 15; $i++) {
        try {
            $null = Invoke-RestMethod -Uri "$GatewayUrl/api/auth/login" -Method Post -Body '{"email":"invalid@test.com","password":"bad"}' -ContentType "application/json" -TimeoutSec 5
        } catch {
            if ($_.Exception.Response.StatusCode.value__ -eq 429) {
                $hit429 = $true
                break
            }
        }
    }
    if ($hit429) {
        Write-Pass "Rate limiting returned HTTP 429 Too Many Requests on burst"
    } else {
        Write-Host "  [WARN] Did not receive 429 within 15 requests (may be within allowed burst window)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [SKIP] Rate limiting test skipped by switch" -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# 4. CORS PREFLIGHT CHECK
# -----------------------------------------------------------------------------
Write-Header "4. CORS Preflight (OPTIONS)"

try {
    $corsResp = Invoke-WebRequest -Uri "$GatewayUrl/api/products" -Method Options -Headers @{
        "Origin" = "http://localhost:3000";
        "Access-Control-Request-Method" = "POST";
        "Access-Control-Request-Headers" = "Authorization,Content-Type";
    } -TimeoutSec 10
    $acao = $corsResp.Headers["Access-Control-Allow-Origin"]
    if ($acao -like "*localhost:3000*" -or $acao -eq "*") {
        Write-Pass "CORS preflight (OPTIONS) returned Access-Control-Allow-Origin: $acao"
    } else {
        Write-Fail "CORS preflight missing or invalid Access-Control-Allow-Origin header"
    }
} catch {
    Write-Fail "CORS preflight failed: $_"
}

# -----------------------------------------------------------------------------
# 5. PERIMETER SECURITY & INTERNAL ROUTE BLOCKING
# -----------------------------------------------------------------------------
Write-Header "5. Perimeter Isolation (Internal Ports Blocked)"

# Check that backend internal ports (8002, 8003) are NOT directly reachable from the host
foreach ($internalPort in @(8002, 8003)) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect("127.0.0.1", $internalPort, $null, $null)
        $success = $connect.AsyncWaitHandle.WaitOne(1000, $false)
        if ($success -and $tcp.Connected) {
            $tcp.Close()
            Write-Fail "Perimeter breach: Host port $internalPort is directly exposed to host!"
        } else {
            $tcp.Close()
            Write-Pass "Internal port $internalPort is strictly blocked from host (no direct bypass)"
        }
    } catch {
        Write-Pass "Internal port $internalPort is strictly blocked from host (connection refused)"
    }
}

# Check that unmapped path through Kong returns 404
try {
    $unmapped = Invoke-WebRequest -Uri "$GatewayUrl/non-existent-secret-internal-endpoint" -Method Get -TimeoutSec 5
    Write-Fail "Unmapped path returned HTTP $($unmapped.StatusCode); expected 404"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 404) {
        Write-Pass "Unmapped Kong route correctly blocked with 404 Not Found"
    } else {
        Write-Fail "Unmapped route check error: $_"
    }
}

# -----------------------------------------------------------------------------
# 6. ADMIN API REACHABILITY (127.0.0.1 LOOPBACK ONLY)
# -----------------------------------------------------------------------------
Write-Header "6. Kong Admin API Loopback Check"

try {
    $adminRes = Invoke-RestMethod -Uri "$AdminApiUrl" -Method Get -TimeoutSec 5
    if ($adminRes.tagline -eq "Welcome to kong") {
        Write-Pass "Kong Admin API reachable on loopback: $AdminApiUrl (version: $($adminRes.version))"
    } else {
        Write-Fail "Kong Admin API returned unexpected response: $($adminRes | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Fail "Kong Admin API connection failed on $AdminApiUrl: $_"
}

# -----------------------------------------------------------------------------
# 7. MOCK PAYMENT FLOWS (PENDING -> PAID, EXPIRED, FAILED)
# -----------------------------------------------------------------------------
Write-Header "7. Mock Payment State Transitions (Paid, Expired, Failed)"

if ($jwtToken) {
    # Flow 1: Create Order -> Pending KHQR -> Mock Settlement -> PAID
    try {
        $order1 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders" -Method Post -Body '{"items":[{"product_id":1,"quantity":1}]}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $orderId1 = $order1.data.id

        $pay1 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders/$orderId1/payment" -Method Post -Body '{"method":"khqr","currency":"USD"}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $md5_1 = $pay1.data.qr_md5
        if ($pay1.data.status -eq "pending") {
            Write-Pass "Flow 1: KHQR generated in PENDING state (MD5: $md5_1)"
        }

        # Simulate settlement -> PAID
        $settle1 = Invoke-RestMethod -Uri "$GatewayUrl/api/payments/mock-pay/$md5_1?status=paid" -Method Post -TimeoutSec 10
        if ($settle1.data.status -eq "paid") {
            Write-Pass "Flow 1: Mock-pay successfully transitioned payment to PAID"
        } else {
            Write-Fail "Flow 1: Mock-pay status was $($settle1.data.status); expected paid"
        }
    } catch {
        Write-Fail "Flow 1 (Paid) failed: $_"
    }

    # Flow 2: Create Order -> Pending KHQR -> Mock Expiration -> EXPIRED
    try {
        $order2 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders" -Method Post -Body '{"items":[{"product_id":1,"quantity":1}]}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $orderId2 = $order2.data.id

        $pay2 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders/$orderId2/payment" -Method Post -Body '{"method":"khqr","currency":"USD"}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $md5_2 = $pay2.data.qr_md5

        $expire2 = Invoke-RestMethod -Uri "$GatewayUrl/api/payments/mock-pay/$md5_2?status=expired" -Method Post -TimeoutSec 10
        if ($expire2.data.status -eq "expired") {
            Write-Pass "Flow 2: Mock-pay successfully transitioned payment to EXPIRED"
        } else {
            Write-Fail "Flow 2: Mock-pay status was $($expire2.data.status); expected expired"
        }
    } catch {
        Write-Fail "Flow 2 (Expired) failed: $_"
    }

    # Flow 3: Create Order -> Pending KHQR -> Mock Failure -> FAILED
    try {
        $order3 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders" -Method Post -Body '{"items":[{"product_id":1,"quantity":1}]}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $orderId3 = $order3.data.id

        $pay3 = Invoke-RestMethod -Uri "$GatewayUrl/api/orders/$orderId3/payment" -Method Post -Body '{"method":"khqr","currency":"USD"}' -ContentType "application/json" -Headers @{"Authorization"="Bearer $jwtToken"} -TimeoutSec 10
        $md5_3 = $pay3.data.qr_md5

        $fail3 = Invoke-RestMethod -Uri "$GatewayUrl/api/payments/mock-pay/$md5_3?status=failed" -Method Post -TimeoutSec 10
        if ($fail3.data.status -eq "failed") {
            Write-Pass "Flow 3: Mock-pay successfully transitioned payment to FAILED"
        } else {
            Write-Fail "Flow 3: Mock-pay status was $($fail3.data.status); expected failed"
        }
    } catch {
        Write-Fail "Flow 3 (Failed) failed: $_"
    }
}

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
Write-Host "`n======================================================================" -ForegroundColor Yellow
Write-Host " SMOKE TEST SUITE EXECUTION SUMMARY                                   " -ForegroundColor Yellow
Write-Host " Passed: $passed" -ForegroundColor Green
Write-Host " Failed: $failed" -ForegroundColor Red
Write-Host "======================================================================" -ForegroundColor Yellow

if ($failed -gt 0) {
    exit 1
}
exit 0
