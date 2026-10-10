@echo off
rem Double-cliquer sur ce fichier pour lancer la demo (Windows).
cd /d "%~dp0"
echo Mise a jour du code...
git pull
echo.
rem Les pages s'ouvrent 3 secondes apres, le temps que le serveur demarre.
start /b cmd /c "timeout /t 3 >nul & start "" http://localhost:8000/apply & start "" http://localhost:8000/recruiter"
echo Serveur de demo lance. Fermez cette fenetre pour l'arreter.
python -m metadata.live.server
pause
