@echo off
rem Modifie ces deux lignes puis double-clique sur ce fichier.
set KIWIX=C:\kiwix\kiwix-serve.exe
set ZIM=C:\kiwix\wikipedia_fr_all.zim
"%KIWIX%" --port=8080 "%ZIM%"
pause
