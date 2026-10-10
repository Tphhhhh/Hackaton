@echo off
rem Double-cliquer sur ce fichier pour lancer la démo (Windows).
cd /d "%~dp0"
echo Mise a jour du code...
git pull
echo.
echo Ouverture des pages dans le navigateur...
start "" "http://localhost:8000/apply"
start "" "http://localhost:8000/recruiter"
echo Serveur de demo lance. Fermez cette fenetre pour l'arreter.
python -m metadata.live.server
pause
