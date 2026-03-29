[void][reflection.assembly]::loadwithpartialname('System.Windows.Forms')

$stdinContent = [Console]::In.ReadToEnd()
$data = $null
if ($stdinContent) {
    try { $data = $stdinContent | ConvertFrom-Json } catch {}
}

$project = if ($data -and $data.cwd) { Split-Path $data.cwd -Leaf } else { 'Claude Code' }
$sessionShort = if ($data -and $data.session_id) { $data.session_id.Substring(0, [Math]::Min(8, $data.session_id.Length)) } else { '' }
$message = if ($data -and $data.message) { $data.message } else { 'Claude가 응답을 완료했습니다' }

$title = "Claude [$project]"
$body = if ($sessionShort) { "$message`n[session: $sessionShort...]" } else { $message }

$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.ShowBalloonTip(5000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Milliseconds 500
$notify.Dispose()