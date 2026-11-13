@echo off
rem Double-clic : choisir le .raw puis le BMP a creer.
rem Ou glisser-deposer un fichier .raw sur ce .bat.
cd /d "%~dp0"
python carte_courbes.py %*
pause
