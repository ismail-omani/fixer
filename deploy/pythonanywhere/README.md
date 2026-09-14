# Fixer — Deploy на PythonAnywhere (бесплатно, без карты)

Ограничения бесплатного плана: 512 МБ диска, 1 веб-приложение, HTTPS на поддомене `твойлогин.pythonanywhere.com`. Файлы и SQLite на диске **постоянные** (данные не теряются).

Репозиторий: https://github.com/ismail-omani/fixer

---

## Шаг 1. Регистрация

1. Зайди на https://www.pythonanywhere.com
2. **Create a Beginner account** (бесплатно, карта НЕ нужна)
3. Введи email + пароль
4. Логин = имя аккаунта → твой адрес будет `https://твойлогин.pythonanywhere.com`

---

## Шаг 2. Клонирование репозитория

1. В PythonAnywhere перейди в **Consoles** → **Bash**
2. Выполни:

```bash
cd ~
git clone https://github.com/ismail-omani/fixer.git
cd fixer
```

3. Проверь содержимое:

```bash
ls -la
```

Должны быть: `app.py`, `auth.py`, `db.py`, `chat.py`, `deploy/` и т.д.

---

## Шаг 3. Установка зависимостей

В той же консоли:

```bash
cd ~/fixer
pip3.12 install --user -r deploy/pythonanywhere/requirements-pa.txt
```

(`requirements-pa.txt` — без gunicorn: PythonAnywhere запускает WSGI-сервер сам.)

---

## Шаг 4. Создание .env (включить Secure-cookie)

```bash
cd ~/fixer
echo "FIXER_HTTPS=1" > .env
cat .env
```

---

## Шаг 5. Настройка веб-приложения

В PythonAnywhere открой **Web** → **Add a new web app**:

1. **Next** → выбери **Manual configuration** → **Python 3.12** → **Next**
2. Появится конфигурация приложения. В разделе **Code** скопируй **полное содержимое** скрипта ниже в WSGI-файл
   `/var/www/fixer_pythonanywhere_com_wsgi.py` (в новом макете PythonAnywhere путь к нему фиксированный, но содержимое можно менять):

```python
import os
import sys

path = "/home/fixer/fixer"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("FIXER_HTTPS", "1")

from app import app as application
```

   Поля **Source code** / **Working directory** в новом макете заполнять не нужно — код лежит в `/home/fixer/fixer` (путь задан в WSGI).

3. **Static files** (раздел **Static / media**, если он доступен), либо просто оставь как есть: Flask сам отдаёт `/static/` из своей папки.
4. Прокрути вверх и нажми **Reload**

---

## Шаг 6. Проверка

Открой в браузере:

```
https://твойлогин.pythonanywhere.com
```

Должна открыться страница регистрации Fixer.

Посмотреть ошибки: **Web** → твоё приложение → раздел **Error log** (внизу).

---

## Как обновлять после изменений кода (git)

1. В **Consoles** → **Bash** выполни:

```bash
cd ~/fixer
git pull
```

2. Если менялись зависимости (это было в коммите) — то же в консоли:

```bash
pip3.12 install --user -r deploy/pythonanywhere/requirements-pa.txt
```

3. В **Web** нажми **Reload**.

Таблицы БД создаются автоматически при старте (`CREATE TABLE IF NOT EXISTS`) — ничего вручную мигрировать не нужно.

---

## Как сделать свой git-пуш автоматически (пока не нужно, лишнее)

PythonAnywhere умеет автоматически обновлять код (Git → Rescan). Для начала достаточно ручного `git pull`, как выше.

---

## Бэкап данных

```bash
cd ~
tar czf fixer-backup-$(date +%F).tar.gz fixer/fixer.db fixer/tasks fixer/u fixer/chat_files
```

Сохрани архив себе (меню **Files** → скачать).

---

## Частые проблемы

### Ошибка 500 после Reload
Открой **Web** → **Error log** → увидишь traceback. Часто причина:
- не поставил зависимости (Шаг 3)
- WSGI-файл `/var/www/fixer_pythonanywhere_com_wsgi.py` пустой или с другим путём

### Static не грузится (нет CSS)
Flask отдаёт `/static/` сам — достаточно чтобы в `~/fixer/static/` были файлы. После `git pull` сделай **Reload**.

### Данные «пропали»
На PythonAnywhere они не пропадают. Ищи сайт с `http` вместо `https` или старые задания в `~/fixer/tasks/`. SQLite лежит в `~/fixer/fixer.db`.

### Не хватает места (512 МБ)
Удали вложения/аватары из `~/fixer/tasks/`, `~/fixer/u/` и `~/fixer/chat_files/`, удали старые `.tar.gz`.

---

## Ссылки

- Консоль (Bash): https://www.pythonanywhere.com/consoles/
- Твой веб-интерфейс: https://www.pythonanywhere.com/user/<твойлогин>/webapps/