# Fixer — Deploy на Oracle Cloud Free Tier

## Что нужно перед стартом

1. **Аккаунт Oracle Cloud** — [cloud.oracle.com](https://cloud.oracle.com) (нужна карта для верификации, списание $0)
2. **Домен** (опционально) — для HTTPS. Без домена работает по IP (HTTP)
3. **SSH-ключ** — для подключения к VM

---

## Шаг 1: Создание VM в Oracle Cloud

1. Зайди в Oracle Cloud → **Compute** → **Instances** → **Create Instance**
2. Выбери **Image**: Ubuntu 22.04 (или 24.04)
3. **Shape**: VM.Standard.A1.Flex (ARM, бесплатно) — 1 OCPU, 1 GB RAM
4. **Boot volume**: 10 GB (бесплатно)
5. В поле **SSH keys** вставь свой публичный SSH-ключ
6. Нажми **Create** и жди ~2 мин
7. После создания скопируй **Public IP** (например `129.153.xx.xx`)

---

## Шаг 2: Подключение к VM

```bash
ssh ubuntu@<PUBLIC_IP>
```

---

## Шаг 3: Загрузка проекта

На **своём компьютере** (не на VM) скинь проект на VM:

```bash
# Из папки проекта /run/media/ismail/DATA/fixer
scp -r ./* ubuntu@<PUBLIC_IP>:/tmp/fixer/
```

Или через git:
```bash
# На VM:
cd /tmp
git clone <your-repo-url> fixer
```

---

## Шаг 4: Запуск setup-скрипта

```bash
# На VM:
cd /tmp/fixer
chmod +x deploy/setup.sh

# Без домена (работает по IP):
sudo bash deploy/setup.sh

# С доменом + HTTPS:
sudo bash deploy/setup.sh your-domain.com your-email@example.com
```

Скрипт автоматически:
- Установит Python 3, nginx, certbot
- Создаст venv и установит зависимости
- Настроит systemd-сервис
- Настроит nginx reverse proxy
- (Опционально) Выдаст SSL-сертификат

---

## Шаг 5: Настройка .env (опционально)

Приложение работает сразу после установки. `.env` нужен только если хочешь включить `Secure`-cookie для HTTPS.

```bash
sudo nano /opt/fixer/.env
```

Содержимое:
```
FIXER_HTTPS=1
```

После этого перезапусти:
```bash
sudo systemctl restart fixer
```

---

## Шаг 6: Проверка

```bash
# Статус сервиса:
sudo systemctl status fixer

# Логи:
sudo journalctl -u fixer -f

# Проверка HTTP:
curl -I http://<PUBLIC_IP>
```

---

## Полезные команды

```bash
# Перезапуск
sudo systemctl restart fixer

# Логи (в реальном времени)
sudo journalctl -u fixer -f

# Логи nginx
sudo tail -f /var/log/nginx/error.log

# Ручной запуск gunicorn (для отладки)
cd /opt/fixer && .venv/bin/gunicorn app:app -c gunicorn.conf.py

# Обновление кода (из папки на VM)
cd /opt/fixer
# скопировать новые файлы сюда
sudo systemctl restart fixer

# SSL-сертификат (если не получил при setup)
sudo certbot --nginx -d your-domain.com
```

---

## Структура файлов на VM

```
/opt/fixer/
├── app.py              # Flask-приложение
├── auth.py
├── db.py
├── tasks.py
├── users.py
├── i18n.py
├── gunicorn.conf.py    # Конфиг gunicorn
├── requirements.txt
├── .env                # опционально: FIXER_HTTPS=1
├── fixer.db            # SQLite (создаётся автоматически)
├── tasks/              # Папки заданий
├── u/                  # Папки пользователей
├── static/             # CSS/JS
├── templates/          # Jinja2 шаблоны
└── .venv/              # Python venv
```

---

## Частые проблемы

### "Permission denied" при scp
```bash
# Проверь SSH-ключ или используй пароль:
ssh-copy-id ubuntu@<PUBLIC_IP>
```

### Gunicorn не стартует
```bash
# Проверь логи:
sudo journalctl -u fixer -n 50

# Запусти вручную для отладки:
cd /opt/fixer && .venv/bin/gunicorn app:app -c gunicorn.conf.py
```

### SQLite "database is locked"
```bash
# Один процесс — одна БД. Убедись что нет второго gunicorn:
sudo systemctl stop fixer
sudo fuser -k 8000/tcp
sudo systemctl start fixer
```

### Nginx 502 Bad Gateway
```bash
# Gunicorn не запущен:
sudo systemctl status fixer
sudo systemctl restart fixer
```

### HTTPS не работает
```bash
# Переустанови сертификат:
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

---

## Бэкап данных

```bash
# Бэкап БД + пользователей + заданий:
tar czf fixer-backup-$(date +%F).tar.gz \
    /opt/fixer/fixer.db \
    /opt/fixer/tasks/ \
    /opt/fixer/u/
```

---

## Обновление проекта

```bash
# 1. Загрузи новые файлы на VM
scp -r ./*.py ./*.txt ./static ./templates ubuntu@<PUBLIC_IP>:/tmp/fixer/

# 2. На VM:
sudo systemctl stop fixer
cp -r /tmp/fixer/*.py /opt/fixer/
cp -r /tmp/fixer/static /opt/fixer/
cp -r /tmp/fixer/templates /opt/fixer/
cp /tmp/fixer/requirements.txt /opt/fixer/

# 3. Если изменились зависимости:
/opt/fixer/.venv/bin/pip install -r /opt/fixer/requirements.txt

# 4. Перезапусти
sudo systemctl start fixer
```
