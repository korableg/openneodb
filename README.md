# openneodb

Конвертер баз камер CityGuide, iGo и iGoExt в бинарную базу для видеорегистратора
Neoline X-COP R9000c.

## Структура

Пакет `openneodb`:

- [`openneodb.cityguide`](openneodb/cityguide/README.md) — чтение CityGuide
  Speedcam v2 (`.bkm`);
- [`openneodb.igo`](openneodb/igo/README.md) — чтение iGo и iGoExt
  (`.txt`);
- [`openneodb.db`](openneodb/db/README.md) — формирование базы Neoline
  (`*_Baza_GPS.db`);
- `openneodb.rows` — общий разбор значений строк для readers;
- `openneodb.cli` — командная строка `neodb`, связывающая reader выбранного
  формата с writer Neoline.

## Установка
### pypi
```bash
pip install openneodb
```

### клонирование репозитория
```bash
git clone git@github.com:korableg/openneodb.git
```

## Использование

```bash
# генерация из igo и igoext
neodb igo [-i INPUT] [-o OUTPUT] [--date DDMMYY]
neodb igoext [-i INPUT] [-o OUTPUT] [--date DDMMYY]
# генерация из cityguide
neodb cityguide [-i INPUT] [-o OUTPUT] [--date DDMMYY]
# генерация напрямую из speedcamonline.ru
curl https://speedcamonline.ru/cg77/Rus | neodb cityguide -o X-COP_9000c_Baza_GPS.db
# справка и версия
neodb --help
neodb --version
```

## Ежедневная база России

[Скачать свежую базу](https://github.com/korableg/openneodb/releases/tag/russia-latest).

## Использование как библиотеки

Все публичные классы доступны из корня пакета:

```python
from openneodb import IGoExtReader, NeolineDBWriter

with open("speedcam_igoext.txt", "rb") as source:
    result = IGoExtReader().read(source)

for message in result.stats.warning_messages:
    print(message)

data = NeolineDBWriter(date="270926").build(result.records)
with open("X-COP_9000c_Baza_GPS.db", "wb") as target:
    target.write(data)
```

- `IGoReader`, `IGoExtReader` и `CityGuideReader` через `.read(source)` принимают
  бинарный поток и возвращают `ReadResult`: кортеж `records` и статистику
  `stats` (`read`, `skipped`, `fallback`, `warning_messages`). Библиотека
  ничего не печатает и не пишет в лог.
- `NeolineDBWriter(date).build(records)` принимает любые `CameraRecord`
  и возвращает готовую базу как `bytes`; дата — строка `DDMMYY`.
- Ошибки: `IGoFormatError`, `CityGuideFormatError` (весь входной файл
  некорректен) и `NeolineDBError` (неверная дата, запись вне диапазона,
  превышен размер базы). Все наследуют `ValueError`.
- Пакет содержит аннотации типов (`py.typed`), версия — `openneodb.__version__`.

### `CameraRecord`

Записи можно собирать самостоятельно. Поля — целые числа в единицах формата
Neoline, например координаты в градусах × 10000 с округлением вниз
(`55.75583` → `557558`). Значение каждого поля описано в
[структуре записи](https://github.com/korableg/openneodb/blob/main/openneodb/db/README.md#структура-записи).

```python
from openneodb import CameraRecord, NeolineDBWriter

camera = CameraRecord(
    camera_type=0x06,
    latitude=557558,
    longitude=376173,
    direction=90,
    direction_type=1,
    speed=60,
)
data = NeolineDBWriter(date="270926").build([camera])
```

## Проверка

Тесты используют только стандартную библиотеку Python:

```bash
python3 -m unittest discover -s tests
```
