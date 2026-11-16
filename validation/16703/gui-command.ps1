param([string]$Action,[string]$Mode,[int]$X,[int]$Y,[string]$Name,[string]$Display=':93')
$requestId=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$request=@{id=$requestId;action=$Action;mode=$Mode;x=$X;y=$Y;name=$Name;display=$Display}
$request | ConvertTo-Json | Set-Content -Encoding utf8NoBOM -LiteralPath "$PSScriptRoot/gui-command.json"
docker cp "$PSScriptRoot/gui-command.json" rustdesk-16942-linux:/work/16703-gui/command.json | Out-Null
for ($attempt=0; $attempt -lt 25; $attempt++) {
    $raw=docker exec rustdesk-16942-linux cat /work/16703-gui/response.json 2>$null
    if ($LASTEXITCODE -eq 0) {
        $response=$raw | ConvertFrom-Json
        if ($response.id -eq $requestId) {
            @{request=$request;response=$response} | ConvertTo-Json -Compress -Depth 12 | Add-Content -Encoding utf8NoBOM -LiteralPath "$PSScriptRoot/gui-results.jsonl"
            $raw
            exit 0
        }
    }
    Start-Sleep -Milliseconds 200
}
throw 'GUI command did not finish within the bounded response window'
