Приложение использует папки как хралище файлов midi и wav форматов поэтому перед запуском
создайте в корневой папке проекта папки midi и uploads

Создайте виртуальное окружение используя версию python 3.11

Команды для запуска проекта(PowerShell)
pip install -r requetments.txt
uvicorn main:app --reload
