# VR/3D Experiment Worker -- standalone routing-plan classifier
#
# Reads one video's segments (read-only, via a dedicated backend endpoint),
# classifies each Manim segment as flat-2D vs 3D-worthy using the Anthropic
# API directly (NOT the `claude` CLI -- this deliberately avoids touching
# your Claude Code / claude.ai subscription usage; classification is billed
# to ANTHROPIC_API_KEY's pay-as-you-go account instead), and writes a
# routing plan plus per-segment code/logs to a local temp folder.
#
# Does not write to any database, manifest, or production pipeline. Manual,
# single-video_id only -- never scans or batches.
#
# Usage:
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."
#   .\run.ps1 -VideoId 133 -Email you@example.com -Password '...'

param(
    [Parameter(Mandatory = $true)][int]$VideoId,
    [string]$Email,
    [string]$Password,
    [string]$Token,
    [string]$BackendUrl = $(if ($env:VR_EXPERIMENT_BACKEND_URL) { $env:VR_EXPERIMENT_BACKEND_URL } else { "http://localhost:8000" }),
    [string]$AnthropicApiKey = $env:ANTHROPIC_API_KEY,
    [string]$Model = "claude-haiku-4-5-20251001",
    [string]$OutDir = (Join-Path $env:TEMP "vr-experiment")
)

$ErrorActionPreference = "Stop"

if (-not $AnthropicApiKey) {
    Write-Host "ERROR: ANTHROPIC_API_KEY not set (env var or -AnthropicApiKey). This is a separate pay-as-you-go API key, not your Claude Code subscription login." -ForegroundColor Red
    exit 1
}

# -- Output folder: one timestamped run per invocation ----------------------
$stamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$runDir = Join-Path $OutDir "$VideoId`_$stamp"
$segDir = Join-Path $runDir "segments"
$logDir = Join-Path $runDir "logs"
New-Item -ItemType Directory -Force -Path $segDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$logFile = Join-Path $logDir "run.log"
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

Write-Log "Output folder: $runDir"
Write-Log "Backend: $BackendUrl  Model: $Model"

# -- Step 1: get a session token. The backend gates this endpoint exactly
# like the rest of /api/admin (superadmin-only JWT check) -- there's no way
# for it to know "this is you" without one. The token is valid 30 days
# (JWT_EXPIRE_HOURS=720) and gets cached locally after the first login, so
# -Email/-Password are only needed once (or again after the cache expires).
$tokenCachePath = Join-Path $OutDir ".token"

function Get-FreshTokenViaLogin {
    if (-not $Email -or -not $Password) {
        Write-Log "No cached/valid token, and no -Email/-Password supplied to log in." "ERROR"
        exit 1
    }
    Write-Log "Logging in as $Email ..."
    $loginBody = @{ email = $Email; password = $Password } | ConvertTo-Json
    $loginResp = Invoke-RestMethod -Uri "$BackendUrl/api/auth/login/password" -Method Post `
        -ContentType "application/json" -Body $loginBody
    if (-not $loginResp.token) { throw "login response had no token" }
    Write-Log "Login OK (account_type=$($loginResp.user.account_type))"
    $loginResp.token | Out-File $tokenCachePath -Encoding utf8 -NoNewline
    return $loginResp.token
}

if ($Token) {
    Write-Log "Using token passed via -Token."
} elseif (Test-Path $tokenCachePath) {
    Write-Log "Using cached token from a previous login ($tokenCachePath)."
    $Token = (Get-Content $tokenCachePath -Raw).Trim()
} else {
    try {
        $Token = Get-FreshTokenViaLogin
    } catch {
        Write-Log "Login failed: $($_.Exception.Message)" "ERROR"
        exit 1
    }
}

# -- Step 2: fetch the video + segments (read-only). If the token turns out
# to be expired/invalid, log in fresh once and retry, rather than failing. --
Write-Log "Fetching video $VideoId ..."
try {
    $video = Invoke-RestMethod -Uri "$BackendUrl/api/admin/vr-experiment/video/$VideoId" -Method Get `
        -Headers @{ Authorization = "Bearer $Token" }
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 401 -or $statusCode -eq 403) {
        Write-Log "Token rejected (expired/invalid) - trying a fresh login." "WARN"
        try {
            $Token = Get-FreshTokenViaLogin
            $video = Invoke-RestMethod -Uri "$BackendUrl/api/admin/vr-experiment/video/$VideoId" -Method Get `
                -Headers @{ Authorization = "Bearer $Token" }
        } catch {
            Write-Log "Fetch failed after re-login: $($_.Exception.Message)" "ERROR"
            exit 1
        }
    } else {
        Write-Log "Fetch failed: $($_.Exception.Message)" "ERROR"
        exit 1
    }
}
$video | ConvertTo-Json -Depth 10 | Out-File (Join-Path $runDir "video_raw.json") -Encoding utf8
Write-Log "Fetched $($video.segments.Count) segment(s) for video $VideoId ('$($video.prompt)')"

if ($video.segments.Count -eq 0) {
    Write-Log "No segments found -- this video may be the single-scene (non-multimodal) pipeline. Nothing to classify." "WARN"
    exit 0
}

# -- Step 3: classify Manim segments via the Anthropic API directly ---------
function Invoke-ManimClassification {
    param([string]$SegmentId, [string]$ManimCode)

    $prompt = @"
You are deciding whether a Manim animation segment has genuine 3D spatial
structure that would benefit from being rendered as real 3D geometry in VR,
versus content that is inherently flat (equations, 2D diagrams, text).

Segment Manim code:
$ManimCode

Respond ONLY with JSON:
{"render_mode": "3d" or "2d", "reasoning": "one sentence"}

Guidance:
- "3d": force vectors in space, molecular structure, field lines, orbital
  shapes, anything where depth/rotation would aid understanding
- "2d": equations, graphs, flat labeled diagrams, text-heavy explanations
"@

    $reqBody = @{
        model      = $Model
        max_tokens = 300
        messages   = @(@{ role = "user"; content = $prompt })
    } | ConvertTo-Json -Depth 10

    $reqBody | Out-File (Join-Path $logDir "$SegmentId`_llm_request.json") -Encoding utf8

    try {
        $resp = Invoke-RestMethod -Uri "https://api.anthropic.com/v1/messages" -Method Post `
            -Headers @{ "x-api-key" = $AnthropicApiKey; "anthropic-version" = "2023-06-01" } `
            -ContentType "application/json" -Body $reqBody

        $resp | ConvertTo-Json -Depth 10 | Out-File (Join-Path $logDir "$SegmentId`_llm_response.json") -Encoding utf8

        $text = $resp.content[0].text.Trim()
        $clean = $text -replace '```json', '' -replace '```', ''
        $parsed = $clean | ConvertFrom-Json

        if ($parsed.render_mode -eq "3d" -or $parsed.render_mode -eq "2d") {
            return @{ render_mode = $parsed.render_mode; reasoning = $parsed.reasoning; classified_ok = $true }
        }
        Write-Log "Segment $SegmentId : unexpected render_mode '$($parsed.render_mode)' -- defaulting to 2d" "WARN"
        return @{ render_mode = "2d"; reasoning = "unrecognized model output, defaulted to 2d (fail-safe)"; classified_ok = $false }
    } catch {
        Write-Log "Segment $SegmentId : classification call failed - $($_.Exception.Message) -- defaulting to 2d" "WARN"
        return @{ render_mode = "2d"; reasoning = "classification call failed, defaulted to 2d (fail-safe)"; classified_ok = $false }
    }
}

# -- Step 4: build the routing plan ------------------------------------------
$plan = @()
$cursor = 0.0
$sorted = $video.segments | Sort-Object segment_order

foreach ($seg in $sorted) {
    $segId    = $seg.segment_id
    $duration = if ($seg.actual_duration_seconds) { $seg.actual_duration_seconds }
                elseif ($seg.target_duration_seconds) { $seg.target_duration_seconds }
                else { 0 }

    # Save this segment's raw metadata individually, for later inspection.
    $seg | ConvertTo-Json -Depth 10 | Out-File (Join-Path $segDir "$segId.json") -Encoding utf8

    $entry = [ordered]@{
        segment_id = $segId
        start_t    = [math]::Round($cursor, 2)
        duration   = $duration
    }

    if ($seg.type -eq "manim") {
        if ($seg.generated_code) {
            # Save the raw Manim source as its own runnable .py file.
            $seg.generated_code | Out-File (Join-Path $segDir "$segId.py") -Encoding utf8
            Write-Log "Segment $segId (manim): classifying ..."
            $result = Invoke-ManimClassification -SegmentId $segId -ManimCode $seg.generated_code
            $entry.mode      = if ($result.render_mode -eq "3d") { "spatial_3d" } else { "video_panel" }
            $entry.reasoning = $result.reasoning
            $entry.asset_url = $seg.clip_url
            if ($entry.mode -eq "spatial_3d") {
                $entry.manim_code_file = "segments/$segId.py"
            }
            Write-Log "Segment $segId : $($entry.mode) - $($result.reasoning)"
        } else {
            Write-Log "Segment $segId (manim): no generated_code stored -- defaulting to video_panel" "WARN"
            $entry.mode      = "video_panel"
            $entry.reasoning = "manim segment had no stored source code to classify"
            $entry.asset_url = $seg.clip_url
        }
    } elseif ($seg.type -eq "video") {
        $entry.mode      = "billboard_video"
        $entry.asset_url = $seg.clip_url
        Write-Log "Segment $segId (video): billboard_video (never classified)"
    } else {
        # "image" (nano banana) and any other still-image type
        $entry.mode      = "billboard_image"
        $entry.asset_url = if ($seg.clip_url) { $seg.clip_url } else { $seg.source_asset_url }
        Write-Log "Segment $segId (image): billboard_image (never classified)"
    }

    $plan += [pscustomobject]$entry
    $cursor += $duration
}

# -- Step 5: write the routing plan ------------------------------------------
$routingPlan = [ordered]@{
    video_id     = $VideoId
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    plan         = $plan
}
$planPath = Join-Path $runDir "routing_plan.json"
$routingPlan | ConvertTo-Json -Depth 10 | Out-File $planPath -Encoding utf8

Write-Log "Routing plan written: $planPath"
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
$plan | Select-Object segment_id, mode, start_t, duration | Format-Table -AutoSize
Write-Host "Full output: $runDir" -ForegroundColor Cyan
