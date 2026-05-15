# 🚀 SMM Planner - Запуск скрипта
### **start_smm.bat** - Автоперезапуск ⭐
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

---

## 🔧 Требования

| Файл | Требования |
|------|------------|
| `start_smm.bat` | Python 3.10+ |

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
