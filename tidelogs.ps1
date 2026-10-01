<#
.SYNOPSIS
  Show newtide.log from every active ACTION station.

.DESCRIPTION
  Connects to each station over SSH (through the Cloudflare tunnel, using
  the entries already in your ~/.ssh/config) and shows the end of
  /home/tide/bin/tidegauge/newtide.log.

  Without -Follow: prints the last lines of each station's log, one
  station after another, then exits.
  With -Summary:   analyzes each station's warnings and errors over the
                   last 24 hours (log_summary.py, run on the station) and
                   flags anything that needs a look.
  With -Follow:    opens one Windows Terminal window split into a pane per
                   station, each following its log live (tail -F, so it
                   carries on across the midnight log rotation). Close the
                   window, or press Ctrl+C in a pane, to stop.

.PARAMETER Follow
  Follow the logs live instead of printing them once.

.PARAMETER Errors
  Only lines containing WARNING, ERROR or Traceback.

.PARAMETER Lines
  How many lines to show from each log (default 40).

.PARAMETER Summary
  Analyze instead of listing: routine network glitches, sensor gaps and
  the like are counted, and real problems are flagged in red.

.PARAMETER Hours
  With -Summary, how far back to look (default 24).

.PARAMETER Detail
  With -Summary, also list every distinct message, not just the flagged ones.

.PARAMETER Node
  Limit to some stations, e.g. -Node bbitide,dscottatide

.EXAMPLE
  .\tidelogs.ps1                      # last 40 lines from each station
  .\tidelogs.ps1 -Errors -Lines 20    # last 20 warnings/errors from each
  .\tidelogs.ps1 -Summary             # analysis of the last 24 hours
  .\tidelogs.ps1 -Summary -Hours 72   # ... of the last 3 days
  .\tidelogs.ps1 -Follow              # live, one pane per station
  .\tidelogs.ps1 -Follow -Node bbitide
#>
param(
    [switch]$Follow,
    [switch]$Errors,
    [switch]$Summary,
    [double]$Hours = 24,
    [switch]$Detail,
    [int]$Lines = 40,
    [string[]]$Node
)

# Station name -> SSH host. Add or remove stations here.
$Stations = [ordered]@{
    'bbitide'     = 'ssh.bbitide.org'
    'belfasttide' = 'ssh.belfasttide.org'
    'dscottatide' = 'ssh.dscottatide.org'
}
$SshUser = 'tide'
$LogFile = '/home/tide/bin/tidegauge/newtide.log'

if ($Node) {
    $unknown = $Node | Where-Object { -not $Stations.Contains($_) }
    if ($unknown) {
        Write-Host "Unknown station(s): $($unknown -join ', ')" -ForegroundColor Red
        Write-Host "Known: $($Stations.Keys -join ', ')"
        exit 1
    }
    $selected = [ordered]@{}
    foreach ($n in $Node) { $selected[$n] = $Stations[$n] }
    $Stations = $selected
}

# The command run on the station. Single quotes are passed through to
# the station's shell untouched; there are no semicolons, which Windows
# Terminal would treat as its own command separator.
$filter = "grep -a --line-buffered -E 'WARNING|ERROR|Traceback'"
if ($Follow) {
    if ($Errors) {
        # Starts with the warnings found in the last 2000 lines, then
        # shows new ones as they arrive.
        $remote = "tail -n 2000 -F $LogFile | $filter"
    } else {
        $remote = "tail -n $Lines -F $LogFile"
    }
} else {
    if ($Errors) {
        $remote = "grep -a -E 'WARNING|ERROR|Traceback' $LogFile | tail -n $Lines"
    } else {
        $remote = "tail -n $Lines $LogFile"
    }
}

if ($Summary) {
    # log_summary.py is sent to each station over SSH and run there, so
    # the stations don't need a copy of it.
    $analyzer = Join-Path $PSScriptRoot 'log_summary.py'
    if (-not (Test-Path $analyzer)) {
        Write-Host "Cannot find $analyzer (it belongs next to this script)." -ForegroundColor Red
        exit 1
    }
    $code = Get-Content $analyzer -Raw
    $opts = "--hours $Hours"
    if ($Detail) { $opts += ' --verbose' }
    $attention = @()
    foreach ($name in $Stations.Keys) {
        $target = "$SshUser@$($Stations[$name])"
        Write-Host ""
        Write-Host ("=" * 20 + " $name " + "=" * 20) -ForegroundColor Cyan
        $out = $code | ssh -o ConnectTimeout=20 $target "python3 - $opts" 2>&1
        $rc = $LASTEXITCODE
        foreach ($line in $out) {
            $text = "$line"
            if ($text -match '^\s+ATTENTION' -or $text -match '^\s+!') {
                Write-Host $text -ForegroundColor Red
            } elseif ($text -match '^\s+OK') {
                Write-Host $text -ForegroundColor Green
            } else {
                Write-Host $text
            }
        }
        if ($rc -eq 1) { $attention += $name }
        elseif ($rc -ne 0) {
            Write-Host "  (could not analyze: exit code $rc -- station unreachable?)" -ForegroundColor Yellow
            $attention += "$name (unreachable)"
        }
    }
    Write-Host ""
    if ($attention) {
        Write-Host "Needs a look: $($attention -join ', ')" -ForegroundColor Red
    } else {
        Write-Host "All stations OK." -ForegroundColor Green
    }
    Write-Host ""
    exit 0
}

if (-not $Follow) {
    foreach ($name in $Stations.Keys) {
        $target = "$SshUser@$($Stations[$name])"
        Write-Host ""
        Write-Host ("=" * 20 + " $name ($target) " + "=" * 20) -ForegroundColor Cyan
        ssh -o ConnectTimeout=20 $target $remote
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  (ssh exited with code $LASTEXITCODE -- station unreachable, or no log yet)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    exit 0
}

# -Follow: one Windows Terminal window, one pane per station, stacked.
$names = @($Stations.Keys)
$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if ($wt) {
    $parts = @()
    for ($i = 0; $i -lt $names.Count; $i++) {
        $name = $names[$i]
        $target = "$SshUser@$($Stations[$name])"
        $pane = "--title $name --suppressApplicationTitle ssh -t -o ServerAliveInterval=30 $target $remote"
        if ($i -eq 0) {
            $parts += "new-tab $pane"
        } else {
            # Each split takes its share of the pane above, so the panes
            # come out equal: 2/3 then 1/2 for three stations.
            $remaining = $names.Count - $i
            $size = [math]::Round($remaining / ($remaining + 1), 2)
            $parts += "split-pane -H -s $size $pane"
        }
    }
    Start-Process wt.exe -ArgumentList ($parts -join ' ; ')
} else {
    # No Windows Terminal: a separate PowerShell window per station.
    foreach ($name in $names) {
        $target = "$SshUser@$($Stations[$name])"
        # Passed base64-encoded so the quotes in the station command
        # survive the trip into the new window intact.
        $cmd = "`$host.UI.RawUI.WindowTitle = '$name'; ssh -t -o ServerAliveInterval=30 $target `"$remote`""
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
        Start-Process powershell.exe -ArgumentList '-NoExit', '-NoProfile', '-EncodedCommand', $encoded
    }
}
