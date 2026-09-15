@echo off
REM ---------------------------------------------------------------------------
REM Lanceur Windows pour backup_sirh.sh (Planificateur de taches).
REM
REM Le planificateur n'arrive pas a demarrer bash.exe directement : la tache
REM se termine avec un code 0 sans que le script ne soit jamais execute, ce qui
REM donne l'illusion d'une sauvegarde qui fonctionne. Passer par cmd.exe, que
REM le planificateur lance de maniere fiable, resout le probleme.
REM
REM Inutile sur le VPS : cron appelle backup_sirh.sh directement.
REM ---------------------------------------------------------------------------
setlocal

REM Racine du projet = dossier parent de scripts\
set "RACINE=%~dp0.."

REM Recherche de Git Bash plutot qu'un chemin en dur : l'installation peut
REM changer de disque (elle est ici sur D:, pas sur C:).
set "BASH="
for %%D in ("%ProgramFiles%\Git" "%ProgramFiles(x86)%\Git" "C:\Git" "D:\Git") do (
    if exist "%%~D\bin\bash.exe" if not defined BASH set "BASH=%%~D\bin\bash.exe"
)

if not defined BASH (
    echo [ERREUR] Git Bash introuvable : impossible de lancer la sauvegarde.>> "%RACINE%\backups\backup.log"
    exit /b 1
)

cd /d "%RACINE%"
"%BASH%" scripts/backup_sirh.sh
exit /b %ERRORLEVEL%
