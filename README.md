# openneodb

Конвертер баз камер CityGuide и iGoExt в бинарную базу для видеорегистратора
Neoline X-COP R9000c.

## Структура

Пакет `openneodb`:

- [`openneodb.cityguide`](openneodb/cityguide/README.md) — чтение CityGuide
  Speedcam v2 (`.bkm`);
- [`openneodb.igo`](openneodb/igo/README.md) — чтение SpeedCamOnline iGoExt
  (`.txt`);
- [`openneodb.db`](openneodb/db/README.md) — формирование базы Neoline
  (`*_Baza_GPS.db`);
- `openneodb.rows` — общий разбор значений строк для readers;
- `openneodb.cli` — командная строка `neodb`, связывающая reader выбранного
  формата с writer Neoline.

## Использование

```text
neodb igo [-i INPUT] [-o OUTPUT] [--date DDMMYY]
neodb cityguide [-i INPUT] [-o OUTPUT] [--date DDMMYY]
```

Запуск на выбор, зависимостей нет:

- `pip install .` — появляется команда `neodb`;
- без установки — `python3 neodb.py ...`
- без установки из корня репозитория — `python3 -m openneodb ...`.

```bash
neodb igo -i cameras.txt -o X-COP_9000c_Baza_GPS.db
neodb cityguide -i SpeedCam.bkm -o X-COP_9000c_Baza_GPS.db --date 270926
cat cameras.txt | python3 -m openneodb igo > X-COP_9000c_Baza_GPS.db
```

По умолчанию используется локальная дата запуска в формате `DDMMYY`.
Внутреннее имя файла всегда `https://github.com/korableg/openneodb`.

Некорректная строка (пустой тип, нарушенная структура, неверное число,
значение вне диапазона) пропускается с предупреждением. Неизвестный непустой
тип преобразуется в базовый стационарный радар `0x06`. Ошибка всего файла
(кодировка, заголовок, CSV) или неверная `--date` завершает процесс
ненулевым кодом до записи результата. Файл `-o` заменяется атомарно: при
сбое прежняя база остаётся нетронутой.

## Проверка

Тесты используют только стандартную библиотеку Python:

```bash
python3 -m unittest discover -s tests
```
