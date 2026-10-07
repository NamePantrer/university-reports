# ЛР6. Исследование malloc/free и сравнение аллокаторов памяти

**Отчёт:** [`ОС_ЛР6_Исследование_malloc_free_и_аллокаторов.pdf`](ОС_ЛР6_Исследование_malloc_free_и_аллокаторов.pdf) (12 страниц; титульная страница вырезана).

Время `malloc`, `malloc` с касанием памяти и `free` для 503 размеров от 16 Б
до 4 МБ (30 прогревочных и 300 измерительных итераций, медиана). Усложнённый
вариант — сравнение glibc с jemalloc, mimalloc и tcmalloc через `LD_PRELOAD`.

## Код (из приложений А–В отчёта)

| Файл | Что это |
|---|---|
| `код/malloc_bench.c` | бенчмарк (приложение А), код совпадает с листингом, добавлены комментарии |
| `код/run_allocators.sh` | сборка и запуск с четырьмя аллокаторами (приложение Б) |
| `код/plot_compare.py` | графики `compare_malloc_median_ns.png`, `compare_touch_median_ns.png` (приложение В) |
| `код/summary_table.py` | *дополнительно:* таблицы 2–4 отчёта (16 Б, 4 КБ, 64 КБ, 1 МБ, 4 МБ) из полученных CSV |
| `код/Makefile` | `make run` — полный прогон, `make table` — сводные таблицы |

```bash
sudo apt install libjemalloc2 libmimalloc3 libtcmalloc-minimal4t64 python3-pandas python3-matplotlib
cd код && make run && make table
```

CSV и графики не хранятся в репозитории: абсолютные значения зависят от стенда
(в отчёте — Ubuntu в VirtualBox, 2 vCPU, i5-1135G7).
