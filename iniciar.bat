@echo off
cd /d "%~dp0"
echo A preparar o Mondego IA (na primeira vez pode demorar um pouco)...
py -3.14 -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO ao instalar as bibliotecas. Tira uma captura de ecra desta janela.
  pause
  exit /b
)
echo.
echo A abrir a app no browser... Se nao abrir, vai a http://localhost:8501
echo Para fechar a app, fecha esta janela.
echo.
py -3.14 -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
