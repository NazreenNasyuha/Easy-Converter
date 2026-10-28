#!/usr/bin/env pwsh
Set-Location -LiteralPath $PSScriptRoot
$uvExe = if (Test-Path "$env:USERPROFILE\.local\bin\uv.exe") { "$env:USERPROFILE\.local\bin\uv.exe" } else { "uv" }
& $uvExe run --no-project --system-certs --with-requirements requirements.txt python main.py @args
