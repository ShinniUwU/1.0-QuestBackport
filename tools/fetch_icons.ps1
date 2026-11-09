# Download 1.0 quest icons (webp) for quests SPT lacks and convert them to jpg
# with the Windows WebP codec, so no Python image library is needed.
# usage: powershell -File fetch_icons.ps1 <data dir> <spt database dir>
param([string]$DataDir, [string]$SptDb)

Add-Type -AssemblyName PresentationCore
$out = Join-Path $DataDir "icons"
New-Item -ItemType Directory -Force $out | Out-Null

$tasks = (Get-Content (Join-Path $DataDir "tasks_pve.json") -Raw -Encoding UTF8 | ConvertFrom-Json).data.tasks
# tarkov.dev ships tasks either as a list or as an object keyed by id
if ($tasks -isnot [array]) { $tasks = $tasks.PSObject.Properties | ForEach-Object { $_.Value } }
$spt = Get-Content (Join-Path $SptDb "templates\quests.json") -Raw -Encoding UTF8
$tmp = Join-Path $out "_dl.webp"

foreach ($t in $tasks) {
    if ($spt.Contains("`"$($t.id)`":") -or -not $t.taskImageLink) { continue }
    $jpg = Join-Path $out "$($t.id).jpg"
    if (Test-Path $jpg) { continue }
    try {
        Invoke-WebRequest -Uri $t.taskImageLink -OutFile $tmp -UseBasicParsing
        $s = [IO.File]::OpenRead($tmp)
        $frame = [Windows.Media.Imaging.BitmapDecoder]::Create($s, 'None', 'OnLoad').Frames[0]
        $enc = New-Object Windows.Media.Imaging.JpegBitmapEncoder
        $enc.QualityLevel = 90
        $enc.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($frame))
        $o = [IO.File]::Create($jpg); $enc.Save($o); $o.Close(); $s.Close()
        "  $($t.id) ok"
    } catch {
        "  $($t.id) failed: $($_.Exception.Message)"
    }
}
Remove-Item $tmp -ErrorAction SilentlyContinue
"icons: $((Get-ChildItem $out -Filter *.jpg).Count)"
