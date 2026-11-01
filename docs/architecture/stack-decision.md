# Yığın Kararı (Adım 2+ öncesi)

Tarih: 2026-10-30. Karar verici: kullanıcı (üç soruya yanıt).

## Kararlar

1. **Uygulama yığını:** Python API + ayrı web arayüzü.
   - Gerekçe: belge işleme ve model entegrasyonu ekosistemi; arayüz bağımsız ilerler.
2. **Barındırma:** yönetilen bulut.
   - Gerekçe: işletme yükünü en düşükte tutma; yedekleme ve ölçekleme sağlayıcıda.
3. **Dil modeli:** yönetilen model servisi.
   - Sonuç: veri model sağlayıcıya gider; gizlilik metni ve saklama politikasında belirtilmeli.

## Ertelenen Seçimler (ilgili adımda)

- İlişkisel veritabanı ürünü (Adım 3/5).
- Anlamsal dizin ürünü (Adım 5).
- Kuyruk ürünü (Adım 5).
- Bulut sağlayıcı ve somut servisler (Adım 8 öncesi).

## Etkiler

- Adım 2 iskeleti Python ile kurulur; kalıcılık soyutlaması korunur (somut DB seçilene dek bellek içi depolar).
- Model soyutlaması (Adım 4) yönetilen servis varsayımıyla tasarlanır; arayüz sağlayıcı değişimine kapalı kalır.
