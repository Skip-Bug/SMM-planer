# 🚀 SMM Planner - Запуск скрипта

## 📋 Варианты запуска

### 1. **run_smm.bat** - Разовый запуск
```bash
./run_smm.bat
```
- ✅ Запускает скрипт один раз
- ✅ Активирует venv (если есть)
- ✅ Ждёт нажатия клавиши после завершения
- 📌 **Для:** Тестирования, ручной проверки

---

### 2. **start_smm.bat** - Автоперезапуск ⭐
```bash
./start_smm.bat
```
- ✅ Запускает скрипт в цикле
- ✅ Автоперезапуск при ошибке (через 5 сек)
- ✅ Пропускает перезапуск при Ctrl+C
- ✅ Показывает время запуска/остановки
- 📌 **Для:** Постоянной работы на сервере

**Остановить:** `Ctrl+C` (один раз)

---

### 3. **install_service.bat** - Служба Windows
```bash
# От имени администратора!
./install_service.bat
```
- ✅ Устанавливает как службу Windows
- ✅ Автозапуск при загрузке ОС
- ✅ Требует **nssm** (https://nssm.cc/download)
- 📌 **Для:** Продакшена, постоянной работы

**Управление службой:**
```bash
nssm edit SMM_Planner   # Изменить настройки
nssm stop SMM_Planner   # Остановить
nssm start SMM_Planner  # Запустить
nssm remove SMM_Planner # Удалить
```

---

## 🔧 Требования

| Файл | Требования |
|------|------------|
| `run_smm.bat` | Python 3.10+ |
| `start_smm.bat` | Python 3.10+ |
| `install_service.bat` | Python 3.10+, **nssm**, права админа |

---

## 📁 Структура

```
SMM-planer/
├── core.py              # Основной скрипт
├── run_smm.bat          # Разовый запуск
├── start_smm.bat        # Автоперезапуск ⭐
├── install_service.bat  # Служба Windows
└── ...
```

---

## 💡 Рекомендации

| Сценарий | Файл |
|----------|------|
| **Тестирование** | `run_smm.bat` |
| **Сервер (простой)** | `start_smm.bat` |
| **Сервер (продакшен)** | `install_service.bat` |

---

## 🐛 Если что-то не так

### Ошибка "Python не найден"
```bash
# Укажите полный путь в BAT-файле
REM Вместо:
python core.py

REM Используйте:
C:\Python310\python.exe core.py
```

### Ошибка "venv не найден"
```bash
# Создайте виртуальное окружение:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Служба не запускается
```bash
# Проверьте логи:
type service_stdout.log
type service_stderr.log

# Проверьте от имени кого запущена служба:
nssm edit SMM_Planner
```
