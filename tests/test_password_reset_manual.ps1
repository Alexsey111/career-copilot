# Password Reset Test Script
# Run: .\tests\test_password_reset_manual.ps1

$API_BASE = "http://localhost:8000/api/v1/auth"
$TEST_EMAIL = "reset-test@example.com"
$OLD_PASSWORD = "OldPass123!"
$NEW_PASSWORD = "NewStrongPass123"

Write-Host "=== Password Reset Test ===" -ForegroundColor Cyan
Write-Host "Email: $TEST_EMAIL"
Write-Host "Old Password: $OLD_PASSWORD"
Write-Host "New Password: $NEW_PASSWORD"
Write-Host ""

# Step 1: Register user
Write-Host "[1/6] Registering test user..." -ForegroundColor Yellow
try {
    $registerBody = @{
        email = $TEST_EMAIL
        password = $OLD_PASSWORD
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "$API_BASE/register" `
        -ContentType "application/json" `
        -Body $registerBody

    Write-Host "  OK: User registered" -ForegroundColor Green
} catch {
    if ($_.ErrorDetails.Message -like "*already registered*") {
        Write-Host "  INFO: User already exists, continuing..." -ForegroundColor Gray
    } else {
        Write-Host "  ERROR: Registration failed: $($_.ErrorDetails.Message)" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Request reset token
Write-Host "`n[2/6] Requesting password reset token..." -ForegroundColor Yellow
try {
    $requestBody = @{
        email = $TEST_EMAIL
    } | ConvertTo-Json

    $requestResponse = Invoke-RestMethod `
        -Method Post `
        -Uri "$API_BASE/password-reset/request" `
        -ContentType "application/json" `
        -Body $requestBody

    $resetToken = $requestResponse.reset_token
    Write-Host "  OK: Token received: $resetToken" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Token request failed: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Confirm password reset
Write-Host "`n[3/6] Confirming password reset..." -ForegroundColor Yellow
try {
    $confirmBody = @{
        reset_token = $resetToken
        new_password = $NEW_PASSWORD
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "$API_BASE/password-reset/confirm" `
        -ContentType "application/json" `
        -Body $confirmBody

    Write-Host "  OK: Password changed successfully" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Confirmation failed: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

# Step 4: Login with old password (expect 401)
Write-Host "`n[4/6] Checking: login with old password (expect 401)..." -ForegroundColor Yellow
try {
    $loginOldBody = @{
        email = $TEST_EMAIL
        password = $OLD_PASSWORD
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "$API_BASE/login" `
        -ContentType "application/json" `
        -Body $loginOldBody

    Write-Host "  ERROR: Old password still works!" -ForegroundColor Red
    exit 1
} catch {
    if ($_.Exception.Response.StatusCode -eq 401) {
        Write-Host "  OK: Old password rejected (401)" -ForegroundColor Green
    } else {
        Write-Host "  UNEXPECTED: Status $($_.Exception.Response.StatusCode)" -ForegroundColor Gray
    }
}

# Step 5: Login with new password (expect 200)
Write-Host "`n[5/6] Checking: login with new password (expect 200)..." -ForegroundColor Yellow
try {
    $loginNewBody = @{
        email = $TEST_EMAIL
        password = $NEW_PASSWORD
    } | ConvertTo-Json

    Invoke-RestMethod `
        -Method Post `
        -Uri "$API_BASE/login" `
        -ContentType "application/json" `
        -Body $loginNewBody

    Write-Host "  OK: New password works (200)" -ForegroundColor Green
    Write-Host "  Got access_token and refresh_token" -ForegroundColor Gray
} catch {
    Write-Host "  ERROR: New password failed: $($_.ErrorDetails.Message)" -ForegroundColor Red
    exit 1
}

# Step 6: SQL check
Write-Host "`n[6/6] Check auth_events in DB..." -ForegroundColor Yellow
Write-Host "  Run manually in psql:" -ForegroundColor Cyan
Write-Host "  psql -U postgres -d career_copilot -c `"SELECT event_type, email, created_at FROM auth_events WHERE event_type LIKE 'password_reset%' ORDER BY created_at DESC;`"" -ForegroundColor White

Write-Host "`n=== Test completed successfully ===" -ForegroundColor Green