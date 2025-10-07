# 🧩 WB PRofit (python 3.12)

Этот файл описывает, как настроить и использовать проект wb profit
---

## 1. Установка зависимостей

Установите необходимые пакеты командой:

```bash
   pip install -r requirements.txt
```

## 2. Создание .env 
С помощью .enbv.example создайте .env со своими переменными

## 3. Создание и применение миграций
```bash
    alembic revision --autogenerate -m "init schema"  # создать миграцию
    alembic upgrade head                              # применить миграции
    alembic downgrade -1                              # откатить миграцию
    alembic history                                   # история миграций
```