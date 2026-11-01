# İşletim: Yedekleme, Güvenlik, Pilot Kabulü

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LINEVORA_ENV` | `dev` | `dev` ya da `prod`. `prod` iken imza anahtarı ve kullanıcılar zorunlu; aksi halde uygulama açılmaz. |
| `LINEVORA_SECRET_KEY` | geliştirme değeri | Belirteç imza anahtarı. Üretimde güçlü, benzersiz değer şart. |
| `LINEVORA_TOKEN_TTL` | `3600` | Belirteç ömrü (saniye). |
| `LINEVORA_USERS` | geliştirme kullanıcıları | `ad:parola:rol,...` biçimi. Roller: `admin`, `specialist`, `viewer`. |
| `LINEVORA_BLOB_DIR` | `var/blobs` | Özgün dosyaların değişmez deposu. |
| `LINEVORA_SNAPSHOT_PATH` | (yok) | Verilirse açılışta yüklenir; `POST /v1/admin/snapshot` ile kaydedilir. |

## Yedekleme ve Geri Yükleme

Dayanıklılık iki parçadır: anlık görüntü dosyası (tüm kayıtlar) ve dosya
deposu (`blob_dir`). İkisi birlikte yedeklenir.

1. Kaydet: `POST /v1/admin/snapshot` (yalnızca `admin`). Yanıt `{"saved": true, "path": ...}` olur.
2. Kopyala: anlık görüntü dosyasını ve `blob_dir` içeriğini yedek ortamına kopyalayın.
3. Kuşaklar: her kayıtta önceki dosya `.1`–`.5` olarak saklanır; altıncı kuşak silinir.
4. Geri yükle: yedek dosyaları yerlerine koyup uygulamayı yeniden başlatın; açılışta otomatik yüklenir.

Geri yükleme denemesi (`tests/test_snapshot.py` içinde otomatik): kaydet →
yedekle → değiştir → yedeği geri koy → yükle → eski durum doğrulanır.

## Saklama Politikası (pilot)

- Denetim kayıtları: yalnızca eklenir, silinmez; pilot boyunca süresiz saklanır.
- Talep dosyaları: içerik adresli, değişmez; müşteri ilişkisi sürdükçe saklanır.
- Anlık görüntü kuşakları: son 5 kayıt; daha eskiler işletme yedeklerine taşınır.
- Model sağlayıcısına giden veri: yönetilen servis kararı gereği talep metinleri
  sağlayıcıya iletilir; gizlilik metninde müşteriye beyan edilir.

## Güvenlik Notları

- Üretimde `LINEVORA_ENV=prod` zorunludur; varsayılan anahtar/kullanıcılarla açılmaz.
- Roller: fiyat/şart ve ürün tanımlama yalnızca `admin`; teklif hazırlama
  `specialist` ve üstü; onay ve iade yalnızca `admin`; okuma tüm roller.
- Onaylanmamış teklif dışa aktarılamaz; bu kural veri katmanında denetlenir.
- Tüm karar işlemleri denetim kaydına yazılır (`GET /v1/audit`, yalnızca `admin`).
- Yanıtlar güvenlik başlıkları taşır (`nosniff`, `DENY`, `no-referrer`).
- Adım 9 ile gelenler: parola karması (`pbkdf2_sha256$...` biçimi desteklenir,
  düz metin yalnızca geriye dönük uyumluluk için), token ucu hız sınırı
  (`LINEVORA_RATE_LIMIT_PER_MINUTE`), belirteç iptali (`POST /v1/auth/revoke`),
  PDF teklif çıktısı (`GET /v1/quotes/{id}/export.pdf`), SQLite kalıcılık
  (`LINEVORA_DB_PATH`).
- Bilinen sınırlar (pilot sonrası): anahtar rotasyonu, iptal listesinin
  süreçler arası kalıcılığı, harici izleme sistemine metrik gönderimi,
  gerçek tarihsel taleplerle model doğruluk ölçümü (eval seti şu an temsilî).

## Gözlemlenebilirlik

- `GET /v1/metrics` (yalnızca `admin`): HTTP sayaçları, iş durumları, model
  çağrı sayıları, teklif durumları ve ortalama onay süresi.
- Her yanıt `X-Request-ID` taşır; istek kaydı (`linevora.http` günlüğü)
  yöntem, yol, durum ve süreyi içerir.
- Eşleştirme değişiklikleri eval kapısından geçmeden yayımlanmaz:
  `python eval/run_eval.py --cases eval/cases --extractor scripted --min-score 0.8`.

## Pilot Kabul Listesi

- [ ] Pilot ekip ve 10–20 tarihsel talep + katalog örneği hazır.
- [ ] `pytest -q` yeşil; eval kapısı eşikte (`--min-score` pilotla netleşir).
- [ ] `LINEVORA_ENV=prod`, güçlü anahtar ve gerçek kullanıcılarla açılış doğrulandı.
- [ ] Yedekleme + geri yükleme denemesi gerçek ortamda yapıldı.
- [ ] Teklif süresi, ilk-teklif doğruluğu ve düzeltme oranı ölçülüyor (`/v1/metrics`).
