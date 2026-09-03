@echo off
chcp 65001 > nul

cd /d D:\Projetos\RadarCursos

echo.
echo  ==========================================
echo         RADAR DE CURSOS DE TECNOLOGIA
echo  ==========================================
echo.

.venv\Scripts\python.exe radar.py

echo.
echo  ==========================================
echo  Processo finalizado. Verifique relatorio.html
echo  ==========================================
echo.

pause