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

Должны быть: `app.py`, `auth.py`, `db.py`, `deploy/`, `requirements.txt` и т.д.

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
2. Появится конфигурация твоего приложения. Заполни:

| Поле | Значение |
|---|---|
| **Source code** | `/home/<твойлогин>/fixer` |
| **Working directory** | `/home/<твойлогин>/fixer` |
| **WSGI configuration file** | `/home/<твойлогин>/fixer/deploy/pythonanywhere/wsgi.py` |

> Если пути не редактируются — в **wsgi.py** замени `<your-login>` на свой логин и сохрани.

3. **Static files** (ниже, "+ Add a static file"):

```
URL:      /static/
Directory: /home/<твойлогин>/fixer/static/
```

4. Прокрути вверх и нажми **Reload**

---

## Шаг 6. Проверка

Открой в браузере:

```
https://твойлогин.pythonanywhere.com
```

Должна открыться страница регистрации Fixer.

Проверка в консоли (если что-то не так):

```bash
cd ~/fixer
FLASK_APP=app.py FLASK_ENV=production flask run  # для локальной проверки
```

Посмотреть ошибки: **Web** → твоё приложение → раздел **Error log** (внизу).

---

## Как обновлять после изменений кода

```bash
cd ~/fixer
git pull
# если менялись зависимости:
pip3.12 install --user -r deploy/pythonanywhere/requirements-pa.txt
```

Затем в **Web** нажми **Reload**.

---

## Как сделать свой git-пуш автоматически (пока не нужно, лишнее)

PythonAnywhere умеет автоматически обновлять код (Git → Rescan). Для начала достаточно ручного `git pull`, как выше.

---

## Бэкап данных

```bash
cd ~
tar czf fixer-backup-$(date +%F).tar.gz fixer/fixer.db fixer/tasks fixer/u
```

Сохрани архив себе (меню **Files** → скачать).

---

## Частые проблемы

### Ошибка 500 после Reload
Открой **Web** → **Error log** → увидишь traceback. Часто причина:
- не поставил зависимости (Шаг 3)
- `<your-login>` не заменён в wsgi.py

### Static не грузится (нет CSS)
Проверь блок **Static files**: URL `/static/` → папка `~/fixer/static/`, затем **Reload**.

### Данные «пропали»
На PythonAnywhere они не пропадают. Ищи сайт с `http` вместо `https` или старые задания в `~/fixer/tasks/`. SQLite лежит в `~/fixer/fixer.db`.

### Не хватает места (512 МБ)
Удали вложения/аватары из `~/fixer/tasks/` и `~/fixer/u/`, удали старые `.tar.gz`.

---

## Ссылки

- Консоль (Bash): https://www.pythonanywhere.com/consoles/
- Твой веб-интерфейс: https://www.pythonanywhere.com/user/<твойлогин>/webapps/