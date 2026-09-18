# cliai - PowerShell integration (PSReadLine, PS 5.1+).
#
# Ctrl+x,Ctrl+a : ask     Ctrl+x,Ctrl+h : explain

if (-not (Get-Module -ListAvailable -Name PSReadLine)) { return }
if (-not (Get-Command cliai -ErrorAction SilentlyContinue)) { return }

$askChord     = if ($env:CLIAI_KEY)         { $env:CLIAI_KEY }         else { 'Ctrl+x,Ctrl+a' }
$explainChord = if ($env:CLIAI_KEY_EXPLAIN) { $env:CLIAI_KEY_EXPLAIN } else { 'Ctrl+x,Ctrl+h' }

Set-PSReadLineKeyHandler -Chord $askChord -BriefDescription 'cliai ask' -ScriptBlock {
    $line = $null; $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    $hist = (Get-History -Count 10 | ForEach-Object { $_.CommandLine }) -join "`n"
    $env:CLIAI_HISTORY = $hist
    $out = (cliai ask -- $line 2>$null | Out-String).Trim()
    Remove-Item Env:\CLIAI_HISTORY -ErrorAction SilentlyContinue
    # Failure leaves the typed line untouched.
    if ([string]::IsNullOrWhiteSpace($out)) { return }
    [Microsoft.PowerShell.PSConsoleReadLine]::Replace(0, $line.Length, $out)
}

Set-PSReadLineKeyHandler -Chord $explainChord -BriefDescription 'cliai explain' -ScriptBlock {
    $line = $null; $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    # Buffer is preserved: you still want to run what you asked about.
    Write-Host ''
    cliai explain -- $line
    [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
}
