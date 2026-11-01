# Linevora Detaylı Geliştirme Planı (Faz 1–3)

Kaynak: 6 uzman ajan + adversarial eleştirmen analizi. Sıralama bağlayıcıdır:
önce doğruluk/güvenlik (Faz 1), sonra ürünleşme (Faz 2), en son ölçülen
tetikleyiciyle ölçeklenme (Faz 3). Çaba: S=1–3 gün, M=1–2 hafta, L=3+ hafta.

## Faz 1 — Pilot-Hazır

Çıkış kriteri: P1.1–P1.6 kabul testleri + tek CI yeşil. Yeni altyapı yok.

### P1.1 Grounding ve Değişmez-1 (M)
- extractor: quote, sayfa metninde normalize alt-dize olarak doğrulanır;
  uyumsuz yanıt reddedilir.
- RequirementStore.add: page>=1 ve quote zorunlu (ValueError).
- MatchSuggestion'a page+quote kopyası; list_suggestions kaynaksızı filtreler.
- Kabul: uydurma alıntılı sahte model yanıtı öneri üretmez; kaynaksız
  gereksinim yazılamaz; silinen gereksinimin önerisinde alıntı kalır.

### P1.2 Atomik Yeniden İşleme (M)
- handle_process_version: önce tüm sonuçlar hesaplanır, tek noktada
  eskiyle değiştirilir; hata hâlinde eski durum korunur.
- Geçersiz LINEVORA_MATCHER değeri açılışta hata verir.
- Kabul: yarıda patlayan matcher eski önerileri bozmaz.

### P1.3 Fail-Fast Kalıcılık (M)
- prod'da db_path veya snapshot_path yoksa açılış durur.
- Bozuk snapshot sessizce yutulmaz; SQLite WAL + busy_timeout;
  snapshot payload'ında schema_version.
- Blob put atomik (tmp+replace+fsync), get bütünlük doğrular.
- Kabul: bozuk yedekle sessiz boş başlangıç olmaz.

### P1.4 Demo Verisi ve Para (S)
- Demo fiyat/şart prod'da asla otomatik yürürlüğe girmez
  (LINEVORA_SEED_DEMO, prod'da zorla kapalı).
- Para hesabı Decimal ile yapılır (yuvarlama kayması yok).
- Kabul: prod taze DB'de onaysız fiyatla teklif kurulamaz; kuruş testleri tutar.

### P1.5 Sahiplik ve Sertleştirme (M)
- Inquiry created_by taşır (sahiplik kaydı). Not: mevcut test sözleşmesi
  viewer'ı ekip-içi salt-okunur rol olarak tanımlar; çapraz-kiracı
  kısıtı Faz 3 (Tenant) ile gelir, pilot tek ekipte rol kontrolü yeterlidir.
- Upload streaming boyut limiti, magic-byte ve PDF sayfa sınırı.
- prod'da düz metin parola reddi; demo-model prod'da kapalı;
  login ipucu kaldırılır.
- Kabul: büyük dosya belleğe alınmadan reddedilir; sahiplik alanı tüm kayıtlarda dolu.

### P1.6 CI ve Dürüst Eval (M)
- GitHub Actions: pytest + eval (scripted=smoke) + node --check; make check.
- Golden set (insan etiketli) Faz 2'ye tohum; gerçek model kapısı nightly/manuel.
- Kabul: CI yeşil olmadan merge yok.

## Faz 2 — Ürünleşme

Çıkış kriteri: uzman ekibi günlük işi panelden, iz bırakarak yapar.

### P2.1 Öneri Karar ve Düzeltme (L)
- PATCH suggestion accept/reject/override; gereksinim düzeltme; her karar audit.
- Gap cevaplama; zorunlu gap açıkken teklif bloklanır.
- Alternatif "bunu kullan" aksiyonu; kararlar eval/synonym havuzuna beslenir.
- Kabul: panelden red + gerekçe, denetimde görünür; zorunlu eksikte teklif engellenir.

### P2.2 Kaynak Görüntüleyici ve PDF (M)
- export.pdf UI'a bağlanır; önizleme status değiştirmez, resmî export değiştirir.
- Alıntı vurgusu ve tıklanabilir atıf; router_ui cache başlıkları; print stylesheet.
- Kabul: tek tık PDF indirme; önizleme status'ü bozmaz.

### P2.3 Panel Dayanıklılığı (M)
- Kalıcı oturum + revoke kullanımı, hash deep-link, odak koruyan render,
  loading/AbortController, erişilebilirlik paketi (label/aria/dialog/focus).
- Liste arama/filtre/sayfalama; iade nedeni; katalog düzenleme.
- Kabul: yenilemede oturum korunur; 100+ audit kaydı sayfalanır.

### P2.4 Kalıcılık v2 (L)
- Satır bazlı yazım, unit-of-work, get() kopya döndürür, cursor sayfalama.
- Şifreli/checksum'lı zamanlanmış yedek; RPO/RTO hedefli restore tatbikatı.
- Kabul: 10k katalogda mutasyon O(N) JSON'a bağlı değil (benchmark).

### P2.5 Model Maliyet ve Kalite (M)
- Token/$ metering, inquiry bütçesi, backoff retry, sayfa chunking.
- Birim/aralık normalizasyonu; matcher A/B golden setle, eşik kalibrasyonu.
- Kabul: extraction F1 ve Recall@3 raporlanır; maliyet metrics'te görünür.

## Faz 3 — Ölçeklenme (yalnızca tetikleyiciyle)

- P3.1 PostgreSQL + Alembic. Tetikleyici: çok worker ihtiyacı / SQLite kilit ölçümü.
- P3.2 Dayanıklı kuyruk + pipeline ayrıştırması. Tetikleyici: kuyruk kaybı/gecikme ölçümü.
- P3.3 Gerçek embedding dizini (pgvector/faiss). Tetikleyici: golden sette Lexical yetersizliği.
- P3.4 Tenant/SSO/KVKK. Tetikleyici: ikinci müşteri veya sözleşme şartı.
- P3.5 Konteyner/IaC, Prometheus/OTel, SLO/yük testi. Tetikleyici: SLA taahhüdü.

## Kararlar

- K1 Kalıcılık: Faz 1–2 SQLite(WAL); PostgreSQL Faz 3 tetikleyicisinde.
- K2 Kimlik: HMAC + sahiplik pilot için yeterli; JWT/OIDC SSO talebinde.
- K3 Para: Decimal, tartışmasız ve hemen.
- K4 Matcher: varsayılan Lexical; karar golden A/B ile; geçersiz değer fail-fast.
- K5 Model: tek sağlayıcı soyutlaması büyütülmez; usage alanı şimdi eklenir.
- K6 Export: önizleme ≠ resmî export ayrımı Faz 2'de.
- K7 Gizlilik: model sağlayıcıya veri akışı pilot sözleşmesinden önce yazılı karar.

## Anti-hedefler (pilot öncesi yapılmayacak)

PostgreSQL göçü, Celery/DLQ, ayrı embedding servisi, Tenant/SSO/KMS,
IaC/SLO programı, %85 coverage kapısı, mikroservis, SSR frontend yeniden yazımı.

## Durum

- [x] Faz 1 (P1.1–P1.6 uygulandı; kabul testleri tests/test_phase1.py)
- [x] Faz 2 (P2.1–P2.5 çekirdeği uygulandı; kabul testleri tests/test_phase2.py. Not: /metrics yanıt şekli mevcut test sözleşmesi gereği sabit; token tahmini CallRecord.estimated_tokens olarak sunuluyor. Panel JS sözdizimi CI’da node --check ile doğrulanır. Tamamlama: store get/list kopya güvenliği, satır bazlı artımlı SQLite yazımı (store_rows), kaynak alıntı vurgusu, /v1/metrics/model-usage ucu; testler tests/test_phase2_completion.py.)
- [~] Faz 3 (çekirdek uygulandı; testler tests/test_phase3.py)
  - P3.1: migration runner + LINEVORA_DB_URL (sqlite) aktif; PostgreSQL DDL hazır, canlı repository psycopg + tetikleyici bekliyor.
  - P3.2: pipeline servisi ayrıştı, job recovery + backoff + GET /v1/jobs/dead-letter aktif.
  - P3.3: EmbeddingMatcher + HttpEmbedder aktif (LINEVORA_MATCHER=embedding).
  - P3.4: tenant izolasyonu (kullanıcı kaydında 4. alan) + DELETE KVKK silme aktif; SSO/OIDC, IdP seçimi gerektirdiği için uygulanmadı.
  - P3.5: Dockerfile/compose, Prometheus ucu, readiness, scripts/load_test.py hazır; docker bu makinede yok, canlı bind sandbox nedeniyle doğrulanamadı.
