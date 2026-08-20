# Daily LinkedIn post generator for LearnX AI
# Uses Claude Code CLI (claude.ai subscription) - no API tokens consumed
# Schedule via Windows Task Scheduler: daily at 05:00 UTC (08:00 Finnish)

# Force UTF-8 so Claude's output (em-dashes, special chars) isn't mangled
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$BUFFER_KEY = $env:BUFFER_API_KEY
$CHANNELS = @(
    "6a85ae2eccaf649a67d69433"
)

$TOPICS = @(
    "How AI is transforming the classroom for teachers in 2026",
    "Why students who use AI tools learn faster - the science behind it",
    "AI-powered personalized learning: what schools need to know",
    "From homework help to deep understanding: AI as a study partner",
    "How teachers can save 5 hours a week using AI lesson tools",
    "The future of education: AI that adapts to every student's pace",
    "Why schools that embrace AI now will lead the next decade",
    "AI-generated video lessons: making complex topics simple for students",
    "How AI is closing the learning gap between students worldwide",
    "Interactive AI tutors vs traditional textbooks: what works better",
    "How LearnX AI creates personalized video lessons in seconds",
    "The role of AI in making STEM education accessible to everyone",
    "AI for revision: how students are acing exams with smart tools",
    "Why every teacher needs an AI co-pilot in the classroom"
)

$topic = $TOPICS[(Get-Date).DayOfYear % $TOPICS.Count]
Write-Host "Topic: $topic"

$prompt = "Write an engaging LinkedIn post (max 200 words) about: $topic`n`nRequirements:`n- Strong hook first line, do not start with I`n- Focus on benefits for teachers, students, or schools`n- Naturally mention LearnX AI (https://learnx-ai.com) as a free tool`n- End with a clear call to action`n- 3 to 5 relevant hashtags at the end`n- Max 2 emojis total`nOutput ONLY the post text, nothing else."

Write-Host "Generating post with Claude..."
$postText = claude -p $prompt 2>&1

$postText = $postText -join "`n"

if (-not $postText -or $postText.Length -lt 50 -or $postText -match "^Error:") {
    Write-Host "ERROR: Claude failed - $postText"
    exit 1
}
Write-Host "Generated ($($postText.Length) chars):"
Write-Host $postText
Write-Host ""

$dueAt = (Get-Date).ToUniversalTime().Date.AddDays(1).AddHours(5).ToString("yyyy-MM-ddTHH:mm:ss+00:00")
Write-Host "Scheduling for: $dueAt"

$gqlMutation = "mutation CreatePost(`$input: CreatePostInput!) { createPost(input: `$input) { ... on PostActionSuccess { post { id status dueAt } } } }"

foreach ($channelId in $CHANNELS) {
    $body = @{
        query     = $gqlMutation
        variables = @{
            input = @{
                channelId      = $channelId
                text           = $postText
                schedulingType = "automatic"
                mode           = "customScheduled"
                dueAt          = $dueAt
            }
        }
    } | ConvertTo-Json -Depth 10

    $response = Invoke-RestMethod -Method POST `
        -Uri "https://api.buffer.com/graphql" `
        -Headers @{ Authorization = "Bearer $BUFFER_KEY" } `
        -ContentType "application/json" `
        -Body $body

    Write-Host ("Channel " + $channelId + ":")
    $response | ConvertTo-Json -Depth 5
}

Write-Host "Done."
