# Linevora

Endüstriyel taleplerden teklife (inquiry-to-quote) giden akışın MVP iskeleti.
Mimari: `docs/architecture/README.md`, veri modeli: `docs/architecture/data-model.md`.

## Kurulum

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Çalıştırma

```sh
source .venv/bin/activate
python -m uvicorn linevora.main:app --reload
```

API: `http://127.0.0.1:8000/v1/health`

## Testler

```sh
source .venv/bin/activate
pytest -q
```

## Eval Kapısı

```sh
source .venv/bin/activate
python eval/run_eval.py --cases eval/cases --extractor perfect --min-score 0.8
```

Eşik tutmazsa çıkış kodu 1 olur. `perfect`/`empty` çıkarıcılar koşum
takımının kendini sınaması içindir; `scripted` gerçek çıkarıcı kod yolunu
betiklenmiş model yanıtlarıyla çalıştırır (tesisat sınaması; gerçek
doğruluk ölçümü yönetilen model bağdaştırıcısı eklenince aynı koşucuyla yapılır).

## Panel

Arayüz `site/` (React + Vite) içindedir ve FastAPI tarafından tek porttan
sunulur: `http://127.0.0.1:8000/` vitrin, `http://127.0.0.1:8000/panel`
operasyon panelidir. Panel; giriş, talepler (sürüm yükleme, işleme,
öneri/eksik/alternatif/fark/teklif önizleme), katalog, sürümlü
fiyat/şartlar, canlı izleme ve denetim kaydını içerir.

İzleme (yalnızca admin): üstte canlı durum şeridi (sağlık, iş kuyruğu,
model), İzleme sekmesinde metrik kartları, dead-letter listesi ve canlı
denetim akışı; veriler 4 saniyede bir, sekme gizliyken duraklayarak
yenilenir.

İlk kurulumda ön yüzü bir kez derleyin (Node gerekir):

```sh
cd site && npm install && npm run build && cd ..
python -m uvicorn linevora.main:app --reload
```

Geliştirmede sıcak yenileme isterseniz `cd site && npm run dev`
(:5173, `/v1` istekleri :8000'e proxy'lenir). `site/dist` yoksa panel
geriye dönük uyumla paketteki yalın sürüme (`src/linevora/web`) düşer.
Giriş: `admin` / `admin123` (roller: admin, specialist, viewer).

## API Yüzeyleri (Adım 2-3)

- `GET /v1/health` — sağlık (açık)
- `POST /v1/auth/token` — belirteç üretimi
- `GET /v1/me` — kendini görme
- `GET /v1/audit` — denetim okuma (yalnızca admin)
- `POST /v1/inquiries` — talep açma (admin/uzman)
- `POST /v1/inquiries/{id}/versions` — sürüm yükleme (admin/uzman)
- `GET /v1/inquiries/{id}/versions` — sürüm listeleme
- `POST /v1/inquiries/{id}/versions/{v}/process` — gereksinim çıkarma + eşleştirme işi (admin/uzman)
- `GET /v1/jobs/{job}` — iş durumu
- `GET /v1/inquiries/{id}/versions/{v}/suggestions` — gereksinimler ve skorlu öneriler
- `GET /v1/inquiries/{id}/versions/{v}/gaps` — eksik bilgi listesi
- `GET /v1/inquiries/{id}/versions/{a}/diff/{b}` — sürüm fark raporu
- `GET /v1/inquiries/{id}/versions/{v}/alternatives` — ölçüt karşılaştırmalı alternatifler
- `GET/POST /v1/products`, `GET/POST /v1/prices`, `POST /v1/prices/{id}/activate` — katalog ve sürümlü fiyatlar
- `GET/POST /v1/terms`, `POST /v1/terms/{id}/activate` — sürümlü şartlar
- `POST /v1/inquiries/{id}/versions/{v}/quotes` — teklif taslağı
- `GET /v1/quotes/{id}`, `PUT /v1/quotes/{id}/lines` — teklif okuma ve taslak düzenleme
- `POST /v1/quotes/{id}/submit|return|approve`, `GET /v1/quotes/{id}/export` — onay akışı
- `GET /v1/metrics`, `POST /v1/admin/snapshot` — ölçümler ve anlık görüntü (yalnızca admin)

İşletim (yedekleme, güvenlik, pilot kabulü): `docs/operations.md`.

## Yapılandırma (ortam değişkenleri)

- `LINEVORA_SECRET_KEY`: belirteç imza anahtarı (üretimde zorunlu, güçlü değer).
- `LINEVORA_TOKEN_TTL`: belirteç ömrü, saniye (varsayılan 3600).
- `LINEVORA_USERS`: `kullanıcı:parola:rol,...` biçiminde kullanıcılar.
  Varsayılan (yalnızca geliştirme): `admin:admin123:admin,uzman:uzman123:specialist,izleyici:izleyici123:viewer`.
- `LINEVORA_ENV`: `dev` ya da `prod` (varsayılan `dev`).
- `LINEVORA_BLOB_DIR`: dosya deposu dizini (varsayılan `var/blobs`).
- `LINEVORA_SNAPSHOT_PATH`: anlık görüntü dosyası (verilmezse snapshot kapalı).
- `LINEVORA_DB_PATH`: SQLite kalıcılık dosyası (örn. `var/linevora.db`). Verilirse tüm kayıtlar yeniden başlatmada korunur; verilmezse bellek içi.
- `LINEVORA_MODEL_URL` / `LINEVORA_MODEL_API_KEY` / `LINEVORA_MODEL_NAME` / `LINEVORA_MODEL_TIMEOUT`: yönetilen model servisi (OpenAI-uyumlu chat ucu). `URL` boşsa sahte istemci kullanılır.
- `LINEVORA_MATCHER`: `lexical` (varsayılan), `vector` ya da `hybrid`.
- `LINEVORA_RATE_LIMIT_PER_MINUTE`: token ucu hız sınırı (varsayılan 60).
- Parola alanında `pbkdf2_sha256$...` karması da kabul edilir: `python -c "from linevora.auth.passwords import hash_password; print(hash_password('parola'))"`.
- Onaylı teklif PDF'i: `GET /v1/quotes/{id}/export.pdf`. Belirteç iptali: `POST /v1/auth/revoke`.
