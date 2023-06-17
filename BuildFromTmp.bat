set PATH=%PATH%;C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64
MakeAppx pack /d tmp/sourceNew /p tmp/sourceNew.msix /nv /o
signtool sign /fd SHA256 /a /f certificate/MyCert.pfx /p cerPassSecret tmp/sourceNew.msix 
pause