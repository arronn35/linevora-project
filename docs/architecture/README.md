# Linevora Teknik Mimari — Genel Bakış

Durum: tasarım belgesi. Teknoloji ürünü seçimi henüz yapılmadı; Adım 2 ve sonrasına geçmeden önce yığın kararı gerekir (bkz. "Seçim Ölçütleri").

Kaynak: ürün betimlemesi (inquiry-to-quote akışı, kaynak gösterilebilirlik, ekip onayı, onaylı fiyat/şartlar) ve mimari plan.

## Mimari Yaklaşım

Sınırları net bir modüler bütün: tek dağıtım birimi, keskin iç modül sınırları. Belge işleme asenkron hat üzerinden; dil modeli çağrıları değiştirilebilir bir soyutlama arkasında. Gerekçe: küçük ekip ve doğrulanmamış ürün aşamasında dağıtık mimarinin işletme yükü değer üretmez; sınırlar doğru çizilirse parçalar sonradan bağımsızlaştırılabilir.

## Bileşenler

1. **Ekip web arayüzü.** Sorumluluk: talebi görüntüleme, eşleşme inceleme/düzeltme, raporlar, teklif onayı. Arayüz: yalnızca uygulama arayüz katmanıyla konuşur; önerinin dayandığı kaynak bölümü her ekranda tek tıkla görülür.
2. **Uygulama arayüz katmanı.** Sorumluluk: tek giriş kapısı; kimlik, yetki, girdi doğrulama, denetim kaydı. Arayüz: istemcilere ve iç modüllere HTTP üzerinden hizmet verir; iş mantığı barındırmaz.
3. **Belge işleme hattı.** Sorumluluk: dosya alımı, metin çıkarma (sayfa/bölüm yapısı korunur), gereksinim çıkarma, eşleştirme, rapor üretimi. Arayüz: kuyruğa iş yazar, çalışanlar adımları işletir; her adımın durumu, hatası ve yeniden denemesi izlenir.
4. **Dil modeli soyutlaması.** Sorumluluk: tüm model çağrılarını tek dahili arayüzden yapma, çıktıları şemayla doğrulama. Arayüz: sağlayıcı değişimi arayüzü etkilemez; şemaya uymayan yanıt hatta girmez; her çıkarım kaynak işaretçisi taşır.
5. **İş kayıtları veritabanı.** Sorumluluk: talep, sürüm, gereksinim, eşleşme, onay, teklif ve denetim kayıtları. Arayüz: modüller yalnızca kendi aggregatesine yazar; sürüm ve denetim kayıtları silinemez, yalnızca eklenir.
6. **Anlamsal arama dizini.** Sorumluluk: farklı terminolojiyle yazılmış taleplere katalog adayları üretme. Arayüz: aday listesi + skor döndürür; nihai kararı vermez; skor eşikleri yapılandırılabilir.
7. **Dosya deposu.** Sorumluluk: özgün talep dosyaları ve üretilen teklif belgelerinin değişmez saklanması. Arayüz: içerik adresiyle yazma/okuma; veritabanındaki kayıtlar dosyalara işaret eder.
8. **Katalog ve fiyat/şart modülü.** Sorumluluk: ürün kayıtları, eşanlamlılar, özellikler; sürümlü fiyat ve şartlar. Arayüz: teklif motoruna yalnızca yürürlükteki sürümü verir; eski teklifler üretildikleri sürüme bağlı kalır.
9. **Teklif motoru ve onay akışı.** Sorumluluk: onaylı girdilerden taslak üretimi, düzeltme/onay adımları, belge çıktısı. Arayüz: onay kaydı olmadan çıktı üretmez; bu kural veri katmanında denetlenir.
10. **Gözlemlenebilirlik.** Sorumluluk: kayıt, ölçüm, istek izleme, model çağrı adedi/maliyet takibi, hat adım süreleri. Arayüz: pilot metrikleri (teklif süresi, düzeltme oranı) buradan beslenir.
11. **Değerlendirme seti ve kapısı.** Sorumluluk: tarihsel taleplerden sabit test seti; eşleştirme değişiklikleri sette ölçülmeden yayımlanmaz. Arayüz: tekrar çalıştırılabilir ölçüm; eşik altında sonuç yayımlamayı durdurur.
12. **Güvenlik temeli.** Sorumluluk: aktarımda ve saklamada şifreleme, rol tabanlı yetki, yedekleme ve geri yükleme, saklama süresi politikası.

## Veri Akışı (uçtan uca)

1. Ekip talep dosyasını/metinini yükler → dosya deposuna yazılır, iş kayıtlarına talep + sürüm açılır.
2. İşleme hattı metni çıkarır, gereksinimleri üretir; her gereksinim kaynak işaretçisi taşır.
3. Anlamsal dizin adayları verir; eşleşme önerileri skor, gerekçe ve kaynakla kaydedilir.
4. Eksik bilgi listesi, sürüm farkı (varsa) ve alternatif önerileri üretilir.
5. Ekip inceler, düzeltir, onaylar; tüm kararlar denetim kaydına yazılır.
6. Teklif motoru yürürlükteki fiyat/şart sürümüyle taslak üretir; onay sonrası belge çıktısı alınır.

## Değişmez Kurallar

1. Kaynağı olmayan öneri kullanıcıya gösterilmez.
2. Ekip onayı olmadan teklif dışa aktarılmaz.
3. Teklif yalnızca sürümlü onaylı fiyat/şart kullanır.

Denetim noktaları `data-model.md` dosyasındadır.

## Reddedilen Alternatifler

- Başlangıçta dağıtık servislere bölünme: işletme yükü, erken aşamada gereksiz.
- Model sağlayıcısına doğrudan bağımlı kod: kilitlenme ve maliyet riski.
- Belge işlemeyi eşzamanlı yapma: uzun beklemeler, hata toleransı yokluğu.

## Teknoloji Seçim Ölçütleri (ürün adı yok)

- Uygulama dili/çatısı: ekibin hakimiyeti, belge işleme ve model entegrasyonu ekosistemi, işe alım havuzu.
- İlişkisel veritabanı: işlem bütünlüğü, sürüm/denetim desenlerine uygunluk, yedekleme kolaylığı.
- Anlamsal dizin: eşik ayarlanabilirliği, yeniden indeksleme maliyeti, barındırma yükü.
- Kuyruk/çalışan: yeniden deneme ve görünürlük, işletme yükü.
- Dosya deposu: değişmezlik, erişim denetimi, maliyet.
- Model sağlama: doğruluk, çağrı maliyeti, veri yerleşimi kısıtı.
- Barındırma: işletme yükü en düşük olandan başlanır.

## Adım Durumu

- [x] Adım 1: veri modeli ve değişmez kurallar (`data-model.md`)
- [x] Adım 2: API iskeleti + kimlik ve yetki (`src/linevora/api`, `auth`, `audit`)
- [x] Adım 3: dosya deposu ve içe aktarma (`files`, `ingest`, `inquiries`)
- [x] Adım 4: model soyutlaması + eval seti (`model`, `eval`)
- [x] Adım 5: işleme hattı ve eşleştirme (`jobs`, `matching`, `catalog`)
- [x] Adım 6: eksik/fark/alternatif raporları (`reports`)
- [x] Adım 7: teklif motoru ve onay akışı (`quotes`)
- [x] Adım 8: gözlemlenebilirlik ve güvenlik sertleştirme (`observability`, `docs/operations.md`)
- [x] Adım 9: kalıcılık (SQLite), gerçek model bağdaştırıcısı, anlamsal eşleştirme, güvenlik sertleştirme (hash/rate-limit/iptal), PDF çıktısı (`persistence`, `model/client.py`, `matching/vector_matcher.py`, `auth/passwords.py`, `quotes/pdf.py`)
