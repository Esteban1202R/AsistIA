@echo off
cd /d "%~dp0"
echo Instalando librerias de AsistIA...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Listo. Ahora abre ejecutar.bat
pause
