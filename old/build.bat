REM aggiungo al path il percorso con i tool 
set PATH=%PATH%;C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64


del source.msix
MakeAppx pack /d source /p source.msix /nv 
signtool sign /fd SHA256 /a /f MyKey.pfx /p test source.msix
pause