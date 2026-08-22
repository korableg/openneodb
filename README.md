# neoline

Референсный кодек + CLI для баз GPS-камер Neoline X-COP (`*_Baza_GPS.db`).
Формат вскрыт реверс инжинирингом официальных файлов обновления —
полная спецификация по байтам в [FORMAT.md](FORMAT.md).

Позволяет собрать свою `*_Baza_GPS.db` из выгрузки SpeedCamOnline iGoExt,
либо перепаковать db с другой версии/прошивки устройства так, чтобы её
принял целевой девайс.

## Структура проекта

- `neodb.py` — точка входа CLI (argparse, диспетчер команд).
- `db_codec.py` — кодек бинарного `.db`: `decode()` (байты -> записи) и
  `encode()` (записи -> байты). Обе стороны и `igo_codec.decode()`
  используют один формат записи: `{date, build, ver, fname, recs}`, где
  `recs` — список `dict(type, lat, lon, angle, speed, b11, flags, b22, b23)`.
- `igo_codec.py` — только декодер: превращает выгрузку SpeedCamOnline
  iGoExt в тот же формат записи, наследуя подтип/флаги/профиль оповещения
  у донора для совпавших камер.
- `reference/X-COP_9000c_Baza_GPS.db` — зашитый донор, используется всеми
  `encode-*` командами для мета-полей (date/build/ver/fname), а для
  `encode-igo` — ещё и для наследования профиля по камерам.

Сторонних зависимостей нет — только стандартная библиотека (Python 3.7+).

## Использование

```
python3 neodb.py encode-igo <igoext.txt> <out.db> [--date DDMMYY] [--fname NAME]
python3 neodb.py encode-db  <source.db>  <out.db> [--date DDMMYY] [--fname NAME]
python3 neodb.py verify     <file.db>
```

**encode-igo** — сборка db из выгрузки SpeedCamOnline iGoExt
(`IDX,X,Y,TYPE,SPEED,DIRTYPE,DIRECTION`). Камеры, совпавшие с донором по
(широта, долгота, азимут), наследуют его подтип/флаги/b23; для новых —
дефолты по TYPE выгрузки (192→`a5`, 68→`a2`, 199→`e9`, 206→`a4`, 227→`a5`;
193/194/197 отбрасываются, как делает вендор). Мета берётся из донора,
если не переопределена.

```
python3 neodb.py encode-igo SpeedCamOnline.ru_2026-08-22_iGoExt_Rus.txt out.db
```

**encode-db** — записи берутся как есть из другого db (например, с более
новой прошивки), меняется только мета (date/build/ver/fname) — из донора,
чтобы файл соответствовал обёртке, ожидаемой целевым устройством.
Сопоставление по координатам не требуется — исходные записи уже валидны.

```
python3 neodb.py encode-db X-COP_R750_Baza_GPS.db out.db
```

**verify** — разбирает db и пересобирает обратно, проверяя побайтовое
совпадение с оригиналом. При расхождении завершается с ненулевым кодом.

```
python3 neodb.py verify X-COP_R750_Baza_GPS.db
```

## Спецификация

Полное описание заголовка/записи, XOR-масок, маппинга типов камер и
открытых вопросов — в [FORMAT.md](FORMAT.md).
