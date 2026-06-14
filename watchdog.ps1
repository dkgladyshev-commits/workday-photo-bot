$botDir   = "D:\26-01 DG AGENT\workday_photo_bot"
$python   = "$botDir\.venv\Scripts\pythonw.exe"
$logFile  = "$botDir\watchdog.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $msg"
    Add-Content -Path $logFile -Value $line
}

Log "Watchdog started"

while ($true) {
    $proc = Start-Process -FilePath $python -ArgumentList "bot.py" `
        -WorkingDirectory $botDir -WindowStyle Hidden -PassThru
    Log "Bot started (PID $($proc.Id))"
    $proc.WaitForExit()
    Log "Bot exited (code $($proc.ExitCode)). Restarting in 5s..."
    Start-Sleep -Seconds 5
}
