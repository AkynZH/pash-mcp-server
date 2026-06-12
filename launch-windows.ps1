# launch-windows.ps1
# Нативный скрипт инициализации для Windows (без Docker)

Write-Host "🚀 Запуск нативной инициализации Felix MCP Standalone..." -ForegroundColor Cyan

# Проверка наличия Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Ошибка: Python не найден. Убедитесь, что он добавлен в системный PATH." -ForegroundColor Red
    exit 1
}

# Создание виртуального окружения, если его нет
if (!(Test-Path -Path "venv")) {
    Write-Host "📦 Создание виртуального окружения (venv)..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "✅ Виртуальное окружение уже существует." -ForegroundColor Green
}

# Активация окружения
Write-Host "⚡ Активация виртуального окружения..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Установка зависимостей
Write-Host "📥 Установка зависимостей из pyproject.toml..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -e .

Write-Host "✅ Инициализация завершена! Сервер готов к запуску." -ForegroundColor Green
Write-Host "💡 Для проверки связи запустите: .\venv\Scripts\python.exe scripts\test_odysseus_connection.py" -ForegroundColor Cyan