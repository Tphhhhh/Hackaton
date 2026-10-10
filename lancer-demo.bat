@echo off
rem Double-cliquer sur ce fichier pour lancer la demo (Windows).
cd /d "%~dp0"
echo Mise a jour du code...
git pull
echo.
rem Arrete un ancien serveur de demo encore actif sur le port 8000.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
echo.
rem Repart d'une demo vide : efface les candidatures deposees lors des essais precedents.
if exist out\applications.json del out\applications.json
rem Les pages s'ouvrent 3 secondes apres, le temps que le serveur demarre.
start /b cmd /c "timeout /t 3 >nul & start "" http://localhost:8000/apply & start "" http://localhost:8000/recruiter"
echo Serveur de demo lance. Fermez cette fenetre pour l'arreter.
python -m metadata.live.server
pause
